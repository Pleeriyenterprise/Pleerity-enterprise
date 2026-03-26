"""Security monitoring, threat detection, and incident management."""
from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from database import database

logger = logging.getLogger(__name__)

# Dedupe high-volume auth.token_used: same (user, fingerprint, IP) within this window is one stored event.
_TOKEN_USE_COOLDOWN_SEC = 15.0
_token_use_last: Dict[str, float] = {}
_token_use_lock = asyncio.Lock()

SECURITY_EVENTS_COLLECTION = "security_events"
SECURITY_INCIDENTS_COLLECTION = "security_incidents"
SECURITY_LOCKS_COLLECTION = "security_locks"
SECURITY_BLOCKS_COLLECTION = "security_blocks"

# High volume of admin API responses from one IP (possible automation / probing).
def _admin_route_spike_limit() -> int:
    raw = (os.environ.get("SECURITY_ADMIN_ROUTE_SPIKE_PER_IP") or "").strip()
    if raw.isdigit():
        return max(100, min(int(raw), 50_000))
    return 1200


try:
    _ADMIN_ROUTE_SPIKE_WINDOW_MINUTES = int(
        (os.environ.get("SECURITY_ADMIN_ROUTE_SPIKE_WINDOW_MINUTES") or "10").strip() or "10"
    )
except ValueError:
    _ADMIN_ROUTE_SPIKE_WINDOW_MINUTES = 10
_ADMIN_ROUTE_SPIKE_WINDOW_MINUTES = max(1, min(_ADMIN_ROUTE_SPIKE_WINDOW_MINUTES, 60))


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: Optional[datetime] = None) -> str:
    return (dt or _now()).isoformat()


def _hash_value(raw: str) -> str:
    return hashlib.sha256((raw or "").encode("utf-8")).hexdigest()


def _incident_key(incident_type: str, principal: str) -> str:
    return _hash_value(f"{incident_type}|{principal}")


def _principal_from_event(event_type: str, user_id: Optional[str], ip: Optional[str], details: Dict[str, Any]) -> str:
    if event_type.startswith("auth.") and details.get("email"):
        return f"email:{str(details.get('email')).strip().lower()}"
    if user_id:
        return f"user:{user_id}"
    return f"ip:{ip or 'unknown'}"


async def _upsert_incident(
    *,
    incident_type: str,
    severity: str,
    user_id: Optional[str],
    ip: Optional[str],
    details: Dict[str, Any],
) -> str:
    db = database.get_db()
    principal = _principal_from_event(incident_type, user_id, ip, details)
    key = _incident_key(incident_type, principal)
    now_iso = _iso()
    await db[SECURITY_INCIDENTS_COLLECTION].update_one(
        {"incident_key": key},
        {
            "$set": {
                "type": incident_type,
                "severity": severity,
                "timestamp": now_iso,
                "user_id": user_id,
                "ip": ip,
                "details": details,
                "updated_at": now_iso,
                "status": "open",
            },
            "$setOnInsert": {"incident_key": key, "created_at": now_iso},
            "$inc": {"occurrences": 1},
        },
        upsert=True,
    )
    return key


async def _lock_principal(lock_type: str, principal: str, minutes: int, reason: str) -> None:
    db = database.get_db()
    expires_at = _iso(_now() + timedelta(minutes=max(1, minutes)))
    await db[SECURITY_LOCKS_COLLECTION].update_one(
        {"lock_type": lock_type, "principal": principal},
        {"$set": {"lock_type": lock_type, "principal": principal, "reason": reason, "expires_at": expires_at, "updated_at": _iso()}, "$setOnInsert": {"created_at": _iso()}},
        upsert=True,
    )


async def _block_ip(ip: str, minutes: int, reason: str) -> None:
    if not ip:
        return
    db = database.get_db()
    expires_at = _iso(_now() + timedelta(minutes=max(1, minutes)))
    await db[SECURITY_BLOCKS_COLLECTION].update_one(
        {"ip": ip},
        {"$set": {"ip": ip, "reason": reason, "expires_at": expires_at, "updated_at": _iso()}, "$setOnInsert": {"created_at": _iso()}},
        upsert=True,
    )


async def is_auth_locked(*, email: Optional[str], ip: Optional[str]) -> bool:
    db = database.get_db()
    now_iso = _iso()
    principals = []
    if email:
        principals.append({"lock_type": "auth_email", "principal": str(email).strip().lower()})
    if ip:
        principals.append({"lock_type": "auth_ip", "principal": ip})
    if not principals:
        return False
    hit = await db[SECURITY_LOCKS_COLLECTION].find_one(
        {"$or": principals, "expires_at": {"$gt": now_iso}},
        {"_id": 0, "principal": 1},
    )
    return bool(hit)


async def should_block_ip(ip: Optional[str]) -> bool:
    if not ip:
        return False
    db = database.get_db()
    hit = await db[SECURITY_BLOCKS_COLLECTION].find_one(
        {"ip": ip, "expires_at": {"$gt": _iso()}},
        {"_id": 0, "ip": 1},
    )
    return bool(hit)


async def record_security_event(
    *,
    event_type: str,
    user_id: Optional[str] = None,
    ip: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    severity: str = "low",
) -> str:
    """Record a security event and apply detection/auto-response rules."""
    details = details or {}
    if event_type == "auth.token_used" and user_id:
        fp = (details.get("token_fingerprint") or "").strip()
        tkey = f"{user_id}|{fp}|{ip or ''}"
        now_ts = time.monotonic()
        async with _token_use_lock:
            last = _token_use_last.get(tkey, 0.0)
            if now_ts - last < _TOKEN_USE_COOLDOWN_SEC:
                return ""
            _token_use_last[tkey] = now_ts
            while len(_token_use_last) > 50_000:
                _token_use_last.pop(next(iter(_token_use_last)), None)

    db = database.get_db()
    now = _now()
    now_iso = now.isoformat()
    event_id = _hash_value(f"{event_type}|{user_id or ''}|{ip or ''}|{now_iso}|{details.get('path','')}")
    event_doc = {
        "event_id": event_id,
        "event_type": event_type,
        "severity": severity,
        "timestamp": now_iso,
        "user_id": user_id,
        "ip": ip,
        "details": details,
    }
    await db[SECURITY_EVENTS_COLLECTION].update_one({"event_id": event_id}, {"$setOnInsert": event_doc}, upsert=True)

    logger.info(
        "security.event event_type=%s severity=%s ip=%s user_present=%s",
        event_type,
        severity,
        ip or "-",
        bool(user_id),
    )

    # Detection rules
    try:
        # Brute force / repeated failed auth
        if event_type == "auth.login_failed":
            email_key = (details.get("email") or "").strip().lower()
            since = (now - timedelta(minutes=15)).isoformat()
            count_ip = await db[SECURITY_EVENTS_COLLECTION].count_documents(
                {"event_type": "auth.login_failed", "ip": ip, "timestamp": {"$gte": since}}
            )
            count_email = await db[SECURITY_EVENTS_COLLECTION].count_documents(
                {"event_type": "auth.login_failed", "details.email": email_key, "timestamp": {"$gte": since}}
            ) if email_key else 0
            if count_ip >= 8 or count_email >= 8:
                await _upsert_incident(
                    incident_type="brute_force_login",
                    severity="high",
                    user_id=user_id,
                    ip=ip,
                    details={"count_ip_15m": int(count_ip), "count_email_15m": int(count_email), "email": email_key},
                )
                if ip:
                    await _lock_principal("auth_ip", ip, 30, "too_many_failed_logins")
                if email_key:
                    await _lock_principal("auth_email", email_key, 30, "too_many_failed_logins")
            since_2m = (now - timedelta(minutes=2)).isoformat()
            rapid_ip = await db[SECURITY_EVENTS_COLLECTION].count_documents(
                {"event_type": "auth.login_failed", "ip": ip, "timestamp": {"$gte": since_2m}}
            )
            rapid_email = (
                await db[SECURITY_EVENTS_COLLECTION].count_documents(
                    {"event_type": "auth.login_failed", "details.email": email_key, "timestamp": {"$gte": since_2m}}
                )
                if email_key
                else 0
            )
            if rapid_ip >= 5 or rapid_email >= 5:
                await _upsert_incident(
                    incident_type="rapid_failed_auth",
                    severity="high",
                    user_id=user_id,
                    ip=ip,
                    details={"count_ip_2m": int(rapid_ip), "count_email_2m": int(rapid_email)},
                )
                if ip:
                    await _lock_principal("auth_ip", ip, 15, "rapid_failed_auth")
                if email_key:
                    await _lock_principal("auth_email", email_key, 15, "rapid_failed_auth")

        # Token reuse from multiple IPs
        if event_type == "auth.token_used" and user_id:
            token_fingerprint = (details.get("token_fingerprint") or "").strip()
            if token_fingerprint:
                since = (now - timedelta(minutes=30)).isoformat()
                ips = await db[SECURITY_EVENTS_COLLECTION].distinct(
                    "ip",
                    {"event_type": "auth.token_used", "user_id": user_id, "details.token_fingerprint": token_fingerprint, "timestamp": {"$gte": since}},
                )
                ip_count = len([x for x in ips if x])
                if ip_count >= 3:
                    await _upsert_incident(
                        incident_type="token_reuse_multi_ip",
                        severity="high",
                        user_id=user_id,
                        ip=ip,
                        details={"distinct_ip_30m": ip_count},
                    )
                    # Invalidate active sessions by bumping session_version.
                    await db.portal_users.update_many(
                        {"portal_user_id": user_id},
                        {"$inc": {"session_version": 1}, "$set": {"updated_at": now_iso}},
                    )
                    await db[SECURITY_EVENTS_COLLECTION].update_one(
                        {"event_id": _hash_value(f"token_misuse|{user_id}|{token_fingerprint}|{now_iso}")},
                        {
                            "$setOnInsert": {
                                "event_id": _hash_value(f"token_misuse|{user_id}|{token_fingerprint}|{now_iso}"),
                                "event_type": "auth.token_misuse_detected",
                                "severity": "high",
                                "timestamp": now_iso,
                                "user_id": user_id,
                                "ip": ip,
                                "details": {
                                    "token_fingerprint": token_fingerprint,
                                    "distinct_ip_30m": ip_count,
                                },
                            }
                        },
                        upsert=True,
                    )

        # Webhook signature failures (per-IP when known; stricter threshold when IP missing e.g. internal caller)
        if event_type == "webhook.signature_failed":
            since = (now - timedelta(minutes=10)).isoformat()
            q: Dict[str, Any] = {"event_type": "webhook.signature_failed", "timestamp": {"$gte": since}}
            if ip:
                q["ip"] = ip
            count = await db[SECURITY_EVENTS_COLLECTION].count_documents(q)
            threshold = 3 if ip else 8
            if count >= threshold:
                await _upsert_incident(
                    incident_type="webhook_signature_attack",
                    severity="high",
                    user_id=user_id,
                    ip=ip,
                    details={"count_10m": int(count), "grouped_by_ip": bool(ip)},
                )

        # Endpoint probing
        if event_type in ("http.404", "http.403", "http.401"):
            since = (now - timedelta(minutes=10)).isoformat()
            count = await db[SECURITY_EVENTS_COLLECTION].count_documents(
                {"event_type": {"$in": ["http.404", "http.403", "http.401"]}, "ip": ip, "timestamp": {"$gte": since}}
            )
            if count >= 25:
                await _upsert_incident(
                    incident_type="endpoint_probing",
                    severity="medium",
                    user_id=user_id,
                    ip=ip,
                    details={"count_10m": int(count)},
                )
                await _block_ip(ip or "", 30, "endpoint_probing")

        # Admin route request spike (same IP hammering /api/admin/* — possible scanner or broken integration).
        if event_type == "http.admin_access_attempt" and ip:
            since_adm = (now - timedelta(minutes=_ADMIN_ROUTE_SPIKE_WINDOW_MINUTES)).isoformat()
            adm_count = await db[SECURITY_EVENTS_COLLECTION].count_documents(
                {"event_type": "http.admin_access_attempt", "ip": ip, "timestamp": {"$gte": since_adm}}
            )
            spike_limit = _admin_route_spike_limit()
            if adm_count >= spike_limit:
                await _upsert_incident(
                    incident_type="admin_route_request_spike",
                    severity="medium",
                    user_id=user_id,
                    ip=ip,
                    details={
                        "admin_requests_window_minutes": _ADMIN_ROUTE_SPIKE_WINDOW_MINUTES,
                        "admin_request_count": int(adm_count),
                        "threshold": spike_limit,
                    },
                )
                await _block_ip(ip, 25, "admin_route_request_spike")

        # Malformed request spikes
        if event_type == "http.validation_failed":
            since = (now - timedelta(minutes=10)).isoformat()
            count = await db[SECURITY_EVENTS_COLLECTION].count_documents(
                {"event_type": "http.validation_failed", "ip": ip, "timestamp": {"$gte": since}}
            )
            if count >= 10:
                await _upsert_incident(
                    incident_type="malformed_request_spike",
                    severity="medium",
                    user_id=user_id,
                    ip=ip,
                    details={"count_10m": int(count)},
                )

        # Suspicious data access patterns: unusual burst of document downloads.
        if event_type == "document.download":
            principal_user = user_id or ""
            principal_ip = ip or ""
            since = (now - timedelta(minutes=10)).isoformat()
            q = {"event_type": "document.download", "timestamp": {"$gte": since}}
            if principal_user:
                q["user_id"] = principal_user
            elif principal_ip:
                q["ip"] = principal_ip
            count_downloads = await db[SECURITY_EVENTS_COLLECTION].count_documents(q)
            distinct_resources = await db[SECURITY_EVENTS_COLLECTION].distinct("details.resource_id", q)
            distinct_count = len([x for x in distinct_resources if x])
            if count_downloads >= 30 or distinct_count >= 20:
                await _upsert_incident(
                    incident_type="suspicious_data_access_pattern",
                    severity="high",
                    user_id=user_id,
                    ip=ip,
                    details={
                        "download_count_10m": int(count_downloads),
                        "distinct_resources_10m": int(distinct_count),
                    },
                )
                if user_id:
                    await db.portal_users.update_many(
                        {"portal_user_id": user_id},
                        {"$inc": {"session_version": 1}, "$set": {"updated_at": now_iso}},
                    )

        # Repeated denied document reads indicate cross-user probing / bypass attempts.
        if event_type == "document.access_denied":
            since = (now - timedelta(minutes=10)).isoformat()
            denied_count = await db[SECURITY_EVENTS_COLLECTION].count_documents(
                {"event_type": "document.access_denied", "ip": ip, "timestamp": {"$gte": since}}
            )
            if denied_count >= 8:
                await _upsert_incident(
                    incident_type="cross_user_data_access_probe",
                    severity="medium",
                    user_id=user_id,
                    ip=ip,
                    details={"denied_document_access_10m": int(denied_count)},
                )
                await _block_ip(ip or "", 30, "cross_user_data_access_probe")

    except Exception as e:
        logger.warning("Security detection rule evaluation failed: %s", e)

    return event_id


async def list_security_incidents(*, status: Optional[str] = None, severity: Optional[str] = None, limit: int = 100, skip: int = 0) -> Dict[str, Any]:
    db = database.get_db()
    q: Dict[str, Any] = {}
    if status:
        q["status"] = status
    if severity:
        q["severity"] = severity
    total = await db[SECURITY_INCIDENTS_COLLECTION].count_documents(q)
    rows = await db[SECURITY_INCIDENTS_COLLECTION].find(q, {"_id": 0}).sort("timestamp", -1).skip(skip).limit(limit).to_list(limit)
    return {"items": rows, "total": total}


async def resolve_security_incident(incident_key: str, actor_id: str, note: Optional[str]) -> bool:
    db = database.get_db()
    res = await db[SECURITY_INCIDENTS_COLLECTION].update_one(
        {"incident_key": incident_key, "status": "open"},
        {"$set": {"status": "resolved", "resolved_at": _iso(), "resolved_by": actor_id, "resolution_note": note or "", "updated_at": _iso()}},
    )
    return bool(res.modified_count)


async def list_security_events(*, event_type: Optional[str] = None, limit: int = 200, skip: int = 0) -> Dict[str, Any]:
    db = database.get_db()
    q: Dict[str, Any] = {}
    if event_type:
        q["event_type"] = event_type
    total = await db[SECURITY_EVENTS_COLLECTION].count_documents(q)
    rows = await db[SECURITY_EVENTS_COLLECTION].find(q, {"_id": 0}).sort("timestamp", -1).skip(skip).limit(limit).to_list(limit)
    return {"items": rows, "total": total}


async def get_security_dashboard_summary(days: int = 7) -> Dict[str, Any]:
    db = database.get_db()
    since = (_now() - timedelta(days=max(1, min(days, 90)))).isoformat()

    # Authentication activity from audit + security_events.
    auth_actions = [
        "USER_LOGIN_SUCCESS",
        "USER_LOGIN_FAILED",
        "ADMIN_LOGIN_SUCCESS",
        "ADMIN_LOGIN_FAILED",
        "PASSWORD_RESET_BY_OWNER",
        "FORGOT_PASSWORD_REQUESTED",
    ]
    auth_by_action = await db.audit_logs.aggregate(
        [
            {"$match": {"timestamp": {"$gte": since}, "action": {"$in": auth_actions}}},
            {"$group": {"_id": "$action", "count": {"$sum": 1}}},
        ]
    ).to_list(100)
    auth_map = {r.get("_id"): int(r.get("count") or 0) for r in auth_by_action}
    password_reset_total = auth_map.get("PASSWORD_RESET_BY_OWNER", 0) + auth_map.get("FORGOT_PASSWORD_REQUESTED", 0)

    # Access control: denied = HTTP outcomes; role_violations counted separately (same request may emit both).
    denied_counts = await db[SECURITY_EVENTS_COLLECTION].count_documents(
        {"event_type": {"$in": ["http.401", "http.403", "document.access_denied"]}, "timestamp": {"$gte": since}}
    )
    admin_attempts = await db[SECURITY_EVENTS_COLLECTION].count_documents(
        {"event_type": "http.admin_access_attempt", "timestamp": {"$gte": since}}
    )

    # API abuse.
    rate_limit_hits = await db[SECURITY_EVENTS_COLLECTION].count_documents({"event_type": "abuse.rate_limited", "timestamp": {"$gte": since}})
    malformed_requests = await db[SECURITY_EVENTS_COLLECTION].count_documents({"event_type": "http.validation_failed", "timestamp": {"$gte": since}})
    request_spikes = await db[SECURITY_INCIDENTS_COLLECTION].count_documents(
        {
            "type": {"$in": ["malformed_request_spike", "endpoint_probing", "admin_route_request_spike"]},
            "timestamp": {"$gte": since},
        }
    )

    # Webhooks.
    webhook_fail = await db[SECURITY_EVENTS_COLLECTION].count_documents({"event_type": "webhook.signature_failed", "timestamp": {"$gte": since}})
    webhook_duplicates = await db[SECURITY_EVENTS_COLLECTION].count_documents({"event_type": "webhook.duplicate_detected", "timestamp": {"$gte": since}})
    rejected_webhooks = await db[SECURITY_EVENTS_COLLECTION].count_documents({"event_type": {"$in": ["webhook.signature_failed", "webhook.invalid_payload"]}, "timestamp": {"$gte": since}})

    # File/document access from audit + events.
    downloads = await db.audit_logs.count_documents({"timestamp": {"$gte": since}, "action": {"$in": ["ORDER_RECEIPT_PDF_ACCESSED", "DOCUMENT_VIEWED"]}})
    failed_access = await db[SECURITY_EVENTS_COLLECTION].count_documents({"event_type": "document.access_denied", "timestamp": {"$gte": since}})
    cross_user_attempts = await db[SECURITY_EVENTS_COLLECTION].count_documents({"event_type": "document.cross_user_access_attempt", "timestamp": {"$gte": since}})

    # System integrity.
    jwt_failures = await db[SECURITY_EVENTS_COLLECTION].count_documents({"event_type": "auth.jwt_invalid", "timestamp": {"$gte": since}})
    token_misuse = await db[SECURITY_EVENTS_COLLECTION].count_documents({"event_type": "auth.token_misuse_detected", "timestamp": {"$gte": since}})
    invalid_sessions = await db[SECURITY_EVENTS_COLLECTION].count_documents({"event_type": "auth.invalid_session", "timestamp": {"$gte": since}})

    incidents_open = await db[SECURITY_INCIDENTS_COLLECTION].count_documents({"status": "open"})
    incidents_recent = await db[SECURITY_INCIDENTS_COLLECTION].find({"timestamp": {"$gte": since}}, {"_id": 0}).sort("timestamp", -1).limit(20).to_list(20)
    detection_counts = await db[SECURITY_INCIDENTS_COLLECTION].aggregate(
        [
            {"$match": {"timestamp": {"$gte": since}}},
            {"$group": {"_id": "$type", "count": {"$sum": 1}}},
        ]
    ).to_list(100)
    detection_map = {str(r.get("_id")): int(r.get("count") or 0) for r in detection_counts}
    active_locks = await db[SECURITY_LOCKS_COLLECTION].count_documents({"expires_at": {"$gt": _iso()}})
    active_ip_blocks = await db[SECURITY_BLOCKS_COLLECTION].count_documents({"expires_at": {"$gt": _iso()}})

    return {
        "window_days": days,
        "authentication_activity": {
            "successful_logins": auth_map.get("USER_LOGIN_SUCCESS", 0) + auth_map.get("ADMIN_LOGIN_SUCCESS", 0),
            "failed_attempts": auth_map.get("USER_LOGIN_FAILED", 0) + auth_map.get("ADMIN_LOGIN_FAILED", 0),
            "password_resets": int(password_reset_total),
        },
        "access_control": {
            "admin_route_access_attempts": int(admin_attempts),
            "denied_requests": int(denied_counts),
            "role_violations": int(await db[SECURITY_EVENTS_COLLECTION].count_documents({"event_type": "auth.role_violation", "timestamp": {"$gte": since}})),
        },
        "api_abuse": {
            "rate_limit_hits": int(rate_limit_hits),
            "request_spikes": int(request_spikes),
            "malformed_requests": int(malformed_requests),
        },
        "payment_webhook_integrity": {
            "stripe_signature_failures": int(webhook_fail),
            "duplicate_webhook_detection": int(webhook_duplicates),
            "rejected_events": int(rejected_webhooks),
        },
        "file_document_access": {
            "downloads": int(downloads),
            "failed_access": int(failed_access),
            "cross_user_access_attempts": int(cross_user_attempts),
        },
        "system_integrity": {
            "jwt_validation_failures": int(jwt_failures),
            "token_misuse": int(token_misuse),
            "invalid_sessions": int(invalid_sessions),
        },
        "incidents": {
            "open": int(incidents_open),
            "recent": incidents_recent,
        },
        "threat_detections": {
            "brute_force_login": int(detection_map.get("brute_force_login", 0)),
            "rapid_failed_auth": int(detection_map.get("rapid_failed_auth", 0)),
            "token_reuse_multi_ip": int(detection_map.get("token_reuse_multi_ip", 0)),
            "suspicious_data_access_pattern": int(detection_map.get("suspicious_data_access_pattern", 0)),
            "cross_user_data_access_probe": int(detection_map.get("cross_user_data_access_probe", 0)),
            "endpoint_probing": int(detection_map.get("endpoint_probing", 0)),
            "admin_route_request_spike": int(detection_map.get("admin_route_request_spike", 0)),
            "webhook_signature_attack": int(detection_map.get("webhook_signature_attack", 0)),
            "malformed_request_spike": int(detection_map.get("malformed_request_spike", 0)),
        },
        "auto_response": {
            "active_temporary_locks": int(active_locks),
            "active_ip_blocks": int(active_ip_blocks),
            "token_invalidations": int(token_misuse),
        },
    }
