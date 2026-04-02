"""
Admin Communications: recipient resolution, preview checksums, send orchestration, audit records.
All targeting is server-side. Uses NotificationOrchestrator for email (Postmark).
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple

from auth import JWT_SECRET
from database import database
from models import AuditAction
from services.plan_registry import plan_registry
from utils.audit import create_audit_log
from utils.branding import SUPPORT_EMAIL

logger = logging.getLogger(__name__)

MESSAGE_TYPES_CRITICAL = frozenset(
    {
        "INCIDENT",
        "SERVICE_UPDATE",
        "MAINTENANCE_NOTICE",
        "ACCOUNT_ALERT",
        "DIRECT_SUPPORT_MESSAGE",
        # Phase 5.1 canonical broadcast labels (same delivery + audit pipeline)
        "SYSTEM_UPDATE",
        "DOWNTIME_ALERT",
        "IMPORTANT_NOTICE",
    }
)
MESSAGE_TYPES_ANNOUNCEMENT = frozenset(
    {
        "GENERAL_ANNOUNCEMENT",
        "FEATURE_ANNOUNCEMENT",
        "SYSTEM_UPDATE",
        "IMPORTANT_NOTICE",
    }
)

TARGET_SCOPES = frozenset({"ALL_CLIENTS", "SELECTED", "SINGLE"})

# Platform letterhead for broadcast-style notices (not account-specific support mail).
MESSAGE_TYPES_PLATFORM_LETTERHEAD = frozenset(
    {
        "INCIDENT",
        "MAINTENANCE_NOTICE",
        "SERVICE_UPDATE",
        "GENERAL_ANNOUNCEMENT",
        "FEATURE_ANNOUNCEMENT",
        "SYSTEM_UPDATE",
        "DOWNTIME_ALERT",
        "IMPORTANT_NOTICE",
    }
)


def requires_high_risk_acknowledgement(target_scope: str, message_type: str) -> bool:
    """Broad sends and high-impact types require explicit admin checkbox."""
    if target_scope == "ALL_CLIENTS":
        return True
    if message_type == "INCIDENT":
        return True
    if message_type == "DOWNTIME_ALERT":
        return True
    return False

MAX_ADMIN_COMM_RECIPIENTS = int(os.getenv("ADMIN_COMM_MAX_RECIPIENTS", "50000"))
# In-process email retries for admin broadcasts (distinct idempotency keys per attempt after the first).
ADMIN_COMM_EMAIL_MAX_ATTEMPTS = max(1, int(os.getenv("ADMIN_COMM_EMAIL_MAX_ATTEMPTS", "3")))
ADMIN_COMM_EMAIL_RETRY_DELAY_SEC = float(os.getenv("ADMIN_COMM_EMAIL_RETRY_DELAY_SEC", "2"))
BATCH_SIZE = int(os.getenv("ADMIN_COMM_BATCH_SIZE", "400"))

_EVENT_HANDLER_ATTR = re.compile(r"\s+on\w+\s*=", re.IGNORECASE)


def use_platform_letterhead_email(message_type: str) -> bool:
    return (message_type or "") in MESSAGE_TYPES_PLATFORM_LETTERHEAD


def sanitize_admin_html(html: str) -> str:
    """Remove obvious active content; admin-supplied HTML is trusted for structure only."""
    if not html:
        return ""
    s = html
    for tag in ("script", "iframe", "object", "embed", "form"):
        s = re.sub(rf"<\s*{tag}\b[^>]*>.*?</\s*{tag}\s*>", "", s, flags=re.DOTALL | re.IGNORECASE)
        s = re.sub(rf"<\s*{tag}\b[^>]*/\s*>", "", s, flags=re.IGNORECASE)
    s = _EVENT_HANDLER_ATTR.sub("", s)
    return s


def _canonical_filters(filters: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    f = filters or {}
    return json.loads(json.dumps(f, sort_keys=True, default=str))


def compute_preview_checksum(payload: Dict[str, Any]) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hmac.new(JWT_SECRET.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).hexdigest()


def notification_template_key_for_message_type(message_type: str) -> str:
    if message_type in MESSAGE_TYPES_ANNOUNCEMENT:
        return "ADMIN_CLIENT_COMMUNICATION_ANNOUNCEMENT"
    return "ADMIN_CLIENT_COMMUNICATION_CRITICAL"


def apply_template_variables(template: str, variables: Dict[str, Any]) -> str:
    if not template:
        return ""
    out = template
    for key, val in variables.items():
        token = "{{" + str(key) + "}}"
        out = out.replace(token, "" if val is None else str(val))
    out = re.sub(r"\{\{[a-zA-Z0-9_]+\}\}", "", out)
    return out


def _strip_html_simple(html: str) -> str:
    if not html:
        return ""
    t = re.sub(r"<[^>]+>", " ", html)
    t = re.sub(r"\s+", " ", t).strip()
    return t[:8000]


async def _white_label_client_ids(db, enabled: bool) -> List[str]:
    q = {"white_label_enabled": True} if enabled else {}
    cur = db.branding_settings.find(q, {"_id": 0, "client_id": 1})
    rows = await cur.to_list(length=None)
    return [r["client_id"] for r in rows if r.get("client_id")]


def _apply_white_label_filter(q: Dict[str, Any], wl_ids: List[str], mode: str) -> None:
    if mode == "white_label_only":
        if not wl_ids:
            q["client_id"] = {"$in": []}
            return
        cur_c = q.get("client_id")
        if isinstance(cur_c, str):
            q["client_id"] = cur_c if cur_c in wl_ids else "__none__"
        elif isinstance(cur_c, dict) and "$in" in cur_c:
            q["client_id"] = {"$in": [x for x in cur_c["$in"] if x in wl_ids]}
        else:
            q["client_id"] = {"$in": wl_ids}
    elif mode == "non_white_label_only" and wl_ids:
        cur_c = q.get("client_id")
        if isinstance(cur_c, str):
            q["client_id"] = cur_c if cur_c not in wl_ids else "__none__"
        elif isinstance(cur_c, dict) and "$in" in cur_c:
            q["client_id"] = {"$in": [x for x in cur_c["$in"] if x not in wl_ids]}
        else:
            q["client_id"] = {"$nin": wl_ids}


async def build_recipient_mongo_query(target_scope: str, filters: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Mongo filter for clients matching scope + filters (server-side targeting)."""
    if target_scope not in TARGET_SCOPES:
        raise ValueError("invalid target_scope")
    db = database.get_db()
    f = filters or {}
    base_query: Dict[str, Any] = {}

    if target_scope == "SINGLE":
        cid = (f.get("client_id") or "").strip()
        if not cid:
            return {"client_id": "__none__"}
        base_query["client_id"] = cid
    elif target_scope == "SELECTED":
        ids = f.get("client_ids") or []
        if isinstance(ids, str):
            ids = [x.strip() for x in ids.split(",") if x.strip()]
        ids = [str(x).strip() for x in ids if str(x).strip()]
        emails = f.get("emails") or []
        if isinstance(emails, str):
            emails = [x.strip().lower() for x in emails.split(",") if x.strip()]
        or_clauses = []
        if ids:
            or_clauses.append({"client_id": {"$in": ids}})
        if emails:
            or_clauses.append({"contact_email": {"$in": emails}})
            or_clauses.append({"email": {"$in": emails}})
        if or_clauses:
            base_query["$or"] = or_clauses

    plan_codes = f.get("plan_codes") or f.get("plan_types")
    if plan_codes:
        base_query["billing_plan"] = {"$in": list(plan_codes)}

    sub_statuses = f.get("subscription_statuses") or f.get("billing_statuses")
    if f.get("subscription_active_only"):
        base_query["subscription_status"] = "ACTIVE"
    elif sub_statuses:
        base_query["subscription_status"] = {"$in": [str(s).upper() for s in sub_statuses]}

    ob_states = f.get("onboarding_statuses")
    if ob_states:
        base_query["onboarding_status"] = {"$in": list(ob_states)}

    if f.get("entitlement_statuses"):
        base_query["entitlement_status"] = {"$in": list(f["entitlement_statuses"])}

    wl_mode = (f.get("white_label_mode") or "").strip().lower()
    if wl_mode == "white_label_only":
        _apply_white_label_filter(base_query, await _white_label_client_ids(db, True), "white_label_only")
    elif wl_mode == "non_white_label_only":
        _apply_white_label_filter(base_query, await _white_label_client_ids(db, True), "non_white_label_only")

    if "client_id" not in base_query and "$or" not in base_query:
        base_query["client_id"] = {"$exists": True, "$ne": "", "$nin": [None, ""]}

    return base_query


async def count_recipients(target_scope: str, filters: Optional[Dict[str, Any]]) -> int:
    db = database.get_db()
    q = await build_recipient_mongo_query(target_scope, filters)
    return await db.clients.count_documents(q)


CLIENT_PROJECTION = {
    "_id": 0,
    "client_id": 1,
    "company_name": 1,
    "full_name": 1,
    "email": 1,
    "contact_email": 1,
    "customer_reference": 1,
    "billing_plan": 1,
    "subscription_status": 1,
    "onboarding_status": 1,
}


async def _enrich_client_docs_with_portal_users(db, client_docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not client_docs:
        return []
    ids = [c["client_id"] for c in client_docs if c.get("client_id")]
    if not ids:
        return []
    users = await db.portal_users.find(
        {
            "client_id": {"$in": ids},
            "role": {"$in": ["ROLE_CLIENT_ADMIN", "ROLE_CLIENT"]},
            "status": "ACTIVE",
        },
        {"_id": 0, "client_id": 1, "portal_user_id": 1},
    ).to_list(length=None)
    by_c: Dict[str, List[str]] = {}
    for u in users:
        cid = u.get("client_id")
        puid = u.get("portal_user_id")
        if cid and puid:
            by_c.setdefault(cid, []).append(puid)
    out: List[Dict[str, Any]] = []
    for c in client_docs:
        cid = c.get("client_id")
        if not cid:
            continue
        plan_code = c.get("billing_plan") or "PLAN_1_SOLO"
        pdef = plan_registry.get_plan_by_code_string(plan_code)
        email = (c.get("contact_email") or c.get("email") or "").strip()
        out.append(
            {
                "client_id": cid,
                "company_name": c.get("company_name") or "",
                "full_name": c.get("full_name") or "",
                "email": email,
                "plan_code": plan_code,
                "plan_name": (pdef.get("name") if pdef else None) or plan_code,
                "subscription_status": c.get("subscription_status"),
                "onboarding_status": c.get("onboarding_status"),
                "customer_reference": c.get("customer_reference"),
                "portal_user_ids": by_c.get(cid, []),
            }
        )
    return out


async def resolve_recipients(
    target_scope: str,
    filters: Optional[Dict[str, Any]],
    *,
    limit_sample: int = 50,
) -> Tuple[List[Dict[str, Any]], int]:
    """
    Returns (sample_rows, total_count). Each row: client_id, company_name, email, plan_code, plan_name,
    subscription_status, onboarding_status, portal_user_ids (for in-app).
    """
    db = database.get_db()
    base_query = await build_recipient_mongo_query(target_scope, filters)
    total = await db.clients.count_documents(base_query)
    cursor = db.clients.find(base_query, CLIENT_PROJECTION).sort("created_at", -1).limit(limit_sample)
    raw = await cursor.to_list(length=limit_sample)
    enriched = await _enrich_client_docs_with_portal_users(db, raw)
    return enriched, total


async def iter_recipient_batches(
    target_scope: str,
    filters: Optional[Dict[str, Any]],
    *,
    batch_size: int = BATCH_SIZE,
) -> AsyncIterator[List[Dict[str, Any]]]:
    """Stream recipients in stable batches (by client_id) for large sends without loading all into RAM."""
    db = database.get_db()
    base_query = await build_recipient_mongo_query(target_scope, filters)
    cursor = db.clients.find(base_query, CLIENT_PROJECTION).sort("client_id", 1).batch_size(batch_size)
    buf: List[Dict[str, Any]] = []
    async for doc in cursor:
        buf.append(doc)
        if len(buf) >= batch_size:
            yield await _enrich_client_docs_with_portal_users(db, buf)
            buf = []
    if buf:
        yield await _enrich_client_docs_with_portal_users(db, buf)


async def client_matches_banner_target(client_id: str, banner: Dict[str, Any]) -> bool:
    """True if this client should see the banner (dynamic filter resolution, not capped ID lists)."""
    if banner.get("target_all"):
        return True
    tids = banner.get("target_client_ids") or []
    if client_id in tids:
        return True
    ts = banner.get("target_scope")
    tf = banner.get("target_filters")
    if ts in TARGET_SCOPES and tf is not None:
        db = database.get_db()
        q = await build_recipient_mongo_query(str(ts), dict(tf))
        q = {**q, "client_id": client_id}
        n = await db.clients.count_documents(q)
        return n > 0
    return False


async def banner_is_active_now(banner: Dict[str, Any], now: datetime) -> bool:
    if not banner.get("active"):
        return False
    start = banner.get("start_at")
    end = banner.get("end_at")
    if start is not None and isinstance(start, datetime) and start > now:
        return False
    if end is not None and isinstance(end, datetime) and end < now:
        return False
    return True


def _banner_fields_for_communication(
    target_scope: str,
    canonical: Dict[str, Any],
) -> Dict[str, Any]:
    """Persist how to resolve banner visibility (dynamic filters; no capped client ID lists)."""
    target_all = target_scope == "ALL_CLIENTS" and not canonical
    base: Dict[str, Any] = {
        "target_all": bool(target_all),
        "target_client_ids": [],
        "target_scope": None,
        "target_filters": None,
    }
    if target_all:
        return base
    if target_scope == "SINGLE":
        cid = (canonical or {}).get("client_id")
        if cid:
            base["target_client_ids"] = [str(cid).strip()]
        return base
    base["target_scope"] = target_scope
    base["target_filters"] = dict(canonical) if canonical else {}
    return base


async def _deliver_recipient_batches(
    *,
    communication_id: str,
    now: datetime,
    target_scope: str,
    target_filters: Optional[Dict[str, Any]],
    total: int,
    message_type: str,
    severity: str,
    channels: List[str],
    safe_html: str,
    text_body: str,
    subject_stripped: str,
    in_app_title: Optional[str],
    in_app_body: Optional[str],
) -> Tuple[int, int, int, int, int]:
    """Returns (email_sent, email_failed, email_blocked, in_app_sent, in_app_failed)."""
    from services.notification_orchestrator import NotificationOrchestrator
    from services.order_service import create_in_app_notification

    db = database.get_db()
    notif_template_key = notification_template_key_for_message_type(message_type)
    orch = NotificationOrchestrator()
    force_platform = use_platform_letterhead_email(message_type)

    email_sent = email_failed = email_blocked = 0
    in_app_sent = in_app_failed = 0
    processed = 0

    async for batch in iter_recipient_batches(target_scope, target_filters):
        for row in batch:
            processed += 1
            if processed > MAX_ADMIN_COMM_RECIPIENTS:
                raise ValueError(
                    f"Recipient count exceeds configured maximum ({MAX_ADMIN_COMM_RECIPIENTS}). "
                    "Raise ADMIN_COMM_MAX_RECIPIENTS if appropriate."
                )
            cid = row["client_id"]
            extras = {"incident_title": subject_stripped}
            vars_ctx = build_variable_context(row, extras)
            rendered_html = apply_template_variables(safe_html, vars_ctx)
            rendered_subject = apply_template_variables(subject_stripped, vars_ctx)
            per_text = apply_template_variables(text_body, vars_ctx)

            delivery_id = f"DLV-{uuid.uuid4().hex[:10].upper()}"
            ddoc: Dict[str, Any] = {
                "delivery_id": delivery_id,
                "communication_id": communication_id,
                "client_id": cid,
                "email": row.get("email"),
                "created_at": now,
                "email_status": "SKIPPED",
                "in_app_status": "SKIPPED",
                "postmark_message_id": None,
                "error_message": None,
                "email_attempts": [],
            }

            # In-app first so portal users see the message even if email later fails or retries.
            if "in_app" in channels:
                title = apply_template_variables((in_app_title or rendered_subject)[:200], vars_ctx)
                body_ia = apply_template_variables((in_app_body or per_text)[:4000], vars_ctx)
                link = vars_ctx["portal_link"]
                ok_any = False
                for puid in row.get("portal_user_ids") or []:
                    try:
                        await create_in_app_notification(
                            recipient_id=puid,
                            title=title,
                            message=body_ia,
                            notification_type=f"ADMIN_COMMUNICATION:{message_type}",
                            link=link,
                            metadata={
                                "communication_id": communication_id,
                                "message_type": message_type,
                                "severity": severity,
                            },
                        )
                        ok_any = True
                    except Exception as e:
                        logger.warning("in_app notification failed %s %s: %s", cid, puid, e)
                if ok_any:
                    ddoc["in_app_status"] = "SENT"
                    in_app_sent += 1
                else:
                    ddoc["in_app_status"] = "FAILED" if row.get("portal_user_ids") else "SKIPPED"
                    in_app_failed += 1

            if "email" in channels:
                if not row.get("email"):
                    ddoc["email_status"] = "SKIPPED"
                    ddoc["error_message"] = "no_email"
                    email_blocked += 1
                else:
                    ctx = {
                        "subject": rendered_subject,
                        "email_header_title": rendered_subject[:200],
                        "message": rendered_html,
                        "text_message": per_text,
                        "client_name": vars_ctx["client_name"],
                        "customer_reference": vars_ctx.get("customer_reference") or "",
                        "portal_link": vars_ctx["portal_link"],
                        "communication_id": communication_id,
                        "message_type": message_type,
                        "show_notification_preferences_link": notif_template_key
                        == "ADMIN_CLIENT_COMMUNICATION_ANNOUNCEMENT",
                    }
                    if force_platform:
                        ctx["_force_pleerity_email_branding"] = True

                    last_res = None
                    email_done = False
                    for attempt in range(ADMIN_COMM_EMAIL_MAX_ATTEMPTS):
                        idempotency_key = (
                            f"{communication_id}:{cid}:email"
                            if attempt == 0
                            else f"{communication_id}:{cid}:email:r{attempt}"
                        )
                        res = await orch.send(
                            notif_template_key,
                            cid,
                            ctx,
                            idempotency_key=idempotency_key,
                            event_type="admin_communication",
                        )
                        last_res = res
                        ddoc["email_attempts"].append(
                            {
                                "attempt": attempt + 1,
                                "outcome": res.outcome,
                                "at": datetime.now(timezone.utc).isoformat(),
                                "error": res.error_message or res.block_reason,
                                "idempotency_key": idempotency_key,
                            }
                        )

                        if res.outcome in ("sent", "duplicate_ignored"):
                            ddoc["email_status"] = "SENT"
                            ddoc["postmark_message_id"] = (res.details or {}).get("provider_message_id")
                            if res.outcome == "duplicate_ignored":
                                ddoc["error_message"] = "duplicate_ignored"
                            email_sent += 1
                            email_done = True
                            break
                        if res.outcome == "blocked":
                            ddoc["email_status"] = "BLOCKED"
                            ddoc["error_message"] = res.block_reason
                            email_blocked += 1
                            email_done = True
                            break
                        if attempt + 1 < ADMIN_COMM_EMAIL_MAX_ATTEMPTS:
                            logger.warning(
                                "admin comm email retry comm=%s client=%s attempt=%s/%s outcome=%s",
                                communication_id,
                                cid,
                                attempt + 1,
                                ADMIN_COMM_EMAIL_MAX_ATTEMPTS,
                                res.outcome,
                            )
                            await asyncio.sleep(ADMIN_COMM_EMAIL_RETRY_DELAY_SEC)
                    if not email_done:
                        ddoc["email_status"] = "FAILED"
                        ddoc["error_message"] = (last_res.error_message if last_res else None) or "send_failed"
                        email_failed += 1

            await db.communication_deliveries.insert_one(ddoc)

    if processed != total:
        logger.warning(
            "admin communication delivery count drift: processed=%s mongodb_count=%s comm=%s",
            processed,
            total,
            communication_id,
        )

    return email_sent, email_failed, email_blocked, in_app_sent, in_app_failed


def build_variable_context(client_row: Dict[str, Any], extras: Dict[str, Any]) -> Dict[str, Any]:
    from utils.app_urls import get_app_base_url

    base = get_app_base_url(for_email_links=True).rstrip("/")
    display = (client_row.get("company_name") or client_row.get("full_name") or "").strip()
    return {
        "client_name": display or "there",
        "plan_name": client_row.get("plan_name") or "",
        "incident_title": extras.get("incident_title") or "",
        "support_email": SUPPORT_EMAIL,
        "portal_link": base + "/dashboard",
        "customer_reference": client_row.get("customer_reference") or "",
    }


async def send_communication(
    *,
    admin_user: Dict[str, Any],
    message_type: str,
    severity: str,
    target_scope: str,
    target_filters: Optional[Dict[str, Any]],
    subject: str,
    body_html: str,
    body_text: Optional[str],
    in_app_title: Optional[str],
    in_app_body: Optional[str],
    banner_title: Optional[str],
    banner_message: Optional[str],
    channels: List[str],
    template_id: Optional[str],
    preview_checksum: str,
    expected_recipient_count: int,
    confirm_send: bool,
    acknowledge_high_risk: bool,
) -> Dict[str, Any]:
    """Validate checksum, resolve recipients, send, persist audit + deliveries."""
    if not confirm_send:
        raise ValueError("confirm_send must be true")
    db = database.get_db()
    canonical = _canonical_filters(target_filters)
    checksum_payload = {
        "message_type": message_type,
        "severity": severity,
        "target_scope": target_scope,
        "target_filters": canonical,
        "subject": subject.strip(),
        "body_html": body_html,
        "body_text": body_text or "",
        "in_app_title": in_app_title or "",
        "in_app_body": in_app_body or "",
        "banner_title": banner_title or "",
        "banner_message": banner_message or "",
        "channels": sorted(channels),
    }
    if compute_preview_checksum(checksum_payload) != preview_checksum:
        raise ValueError("preview_checksum mismatch — run preview again")

    if requires_high_risk_acknowledgement(target_scope, message_type):
        if not acknowledge_high_risk:
            raise ValueError(
                "acknowledge_high_risk required for all-client sends, INCIDENT, or DOWNTIME_ALERT"
            )

    total = await count_recipients(target_scope, target_filters)
    if total != expected_recipient_count:
        raise ValueError(
            f"Recipient count changed (was {expected_recipient_count}, now {total}). Re-run preview."
        )
    if total == 0:
        raise ValueError("No recipients — send blocked")

    dup_check = hashlib.sha256(
        f"{preview_checksum}:{admin_user.get('portal_user_id')}".encode()
    ).hexdigest()[:32]
    from datetime import timedelta

    since = datetime.now(timezone.utc) - timedelta(minutes=10)
    recent = await db.communication_messages.find_one(
        {"dedupe_key": dup_check, "status": {"$in": ["SENT", "PARTIAL_FAILURE"]}, "created_at": {"$gte": since}},
        {"_id": 1},
    )
    if recent:
        raise ValueError("Duplicate send blocked — identical preview was already sent recently")

    communication_id = f"ACM-{uuid.uuid4().hex[:12].upper()}"
    now = datetime.now(timezone.utc)
    admin_id = admin_user.get("portal_user_id") or "unknown"
    safe_html = sanitize_admin_html(body_html)
    text_body = (body_text or "").strip() or _strip_html_simple(safe_html)

    msg_doc = {
        "communication_id": communication_id,
        "status": "SENDING",
        "message_type": message_type,
        "severity": severity,
        "target_scope": target_scope,
        "target_filters": canonical,
        "channels": channels,
        "subject": subject.strip(),
        "body_html_snapshot": safe_html[:200000],
        "body_text_snapshot": text_body[:50000],
        "in_app_title": in_app_title,
        "in_app_body": in_app_body,
        "banner_title": banner_title,
        "banner_message": banner_message,
        "template_id": template_id,
        "sent_by_portal_user_id": admin_id,
        "sent_by_role": admin_user.get("role"),
        "recipient_count": total,
        "created_at": now,
        "updated_at": now,
        "dedupe_key": dup_check,
        "preview_checksum": preview_checksum,
    }
    await db.communication_messages.insert_one(msg_doc)

    total2 = await count_recipients(target_scope, target_filters)
    if total2 != total:
        await db.communication_messages.update_one(
            {"communication_id": communication_id},
            {"$set": {"status": "FAILED", "error": "recipient_count_race", "updated_at": datetime.now(timezone.utc)}},
        )
        raise RuntimeError("Recipient set changed during send")

    banner_id = None
    if "banner" in channels and (banner_title or banner_message):
        banner_id = f"BNR-{uuid.uuid4().hex[:10].upper()}"
        bt = _banner_fields_for_communication(target_scope, canonical)
        await db.system_banners.insert_one(
            {
                "banner_id": banner_id,
                "title": (banner_title or subject[:120]).strip(),
                "message": (banner_message or _strip_html_simple(safe_html)[:500]).strip(),
                "severity": (severity or "info").lower(),
                "start_at": now,
                "end_at": None,
                "active": True,
                "target_all": bt["target_all"],
                "target_client_ids": bt["target_client_ids"],
                "target_scope": bt["target_scope"],
                "target_filters": bt["target_filters"],
                "persistent_display": (severity or "").upper() in ("CRITICAL", "HIGH", "EMERGENCY"),
                "communication_id": communication_id,
                "created_by_portal_user_id": admin_id,
                "created_at": now,
                "updated_at": now,
            }
        )

    try:
        email_sent, email_failed, email_blocked, in_app_sent, in_app_failed = await _deliver_recipient_batches(
            communication_id=communication_id,
            now=now,
            target_scope=target_scope,
            target_filters=target_filters,
            total=total,
            message_type=message_type,
            severity=severity,
            channels=channels,
            safe_html=safe_html,
            text_body=text_body,
            subject_stripped=subject.strip(),
            in_app_title=in_app_title,
            in_app_body=in_app_body,
        )
    except Exception as e:
        await db.communication_messages.update_one(
            {"communication_id": communication_id},
            {"$set": {"status": "FAILED", "error": str(e)[:500], "updated_at": datetime.now(timezone.utc)}},
        )
        raise

    final_status = await _finalize_communication_status(
        communication_id,
        total=total,
        channels=channels,
        banner_id=banner_id,
        email_sent=email_sent,
        email_failed=email_failed,
        email_blocked=email_blocked,
        in_app_sent=in_app_sent,
        in_app_failed=in_app_failed,
    )

    await create_audit_log(
        action=AuditAction.ADMIN_COMMUNICATION_SENT,
        actor_id=admin_id,
        actor_role=None,
        metadata={
            "communication_id": communication_id,
            "message_type": message_type,
            "target_scope": target_scope,
            "recipient_count": total,
            "channels": channels,
            "status": final_status,
        },
    )

    return {
        "communication_id": communication_id,
        "status": final_status,
        "recipient_count": total,
        "summary": {
            "email_sent": email_sent,
            "email_failed": email_failed,
            "email_blocked": email_blocked,
            "in_app_sent": in_app_sent,
            "in_app_failed": in_app_failed,
            "banner_id": banner_id,
        },
    }


async def list_messages(
    *,
    message_type: Optional[str] = None,
    sent_by: Optional[str] = None,
    target_scope: Optional[str] = None,
    status: Optional[str] = None,
    client_id: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    include_drafts_and_scheduled: bool = False,
    skip: int = 0,
    limit: int = 50,
) -> Tuple[List[Dict], int]:
    db = database.get_db()
    q: Dict[str, Any] = {}
    if message_type:
        q["message_type"] = message_type
    if sent_by:
        q["sent_by_portal_user_id"] = sent_by
    if target_scope:
        q["target_scope"] = target_scope
    if status:
        q["status"] = status
    elif not include_drafts_and_scheduled:
        q["status"] = {"$nin": ["DRAFT", "SCHEDULED"]}
    if date_from or date_to:
        q["created_at"] = {}
        if date_from:
            q["created_at"]["$gte"] = date_from
        if date_to:
            q["created_at"]["$lte"] = date_to
    if client_id:
        q["$or"] = [
            {"target_filters.client_id": client_id},
            {"target_filters.client_ids": client_id},
        ]
    total = await db.communication_messages.count_documents(q)
    cur = (
        db.communication_messages.find(q, {"_id": 0})
        .sort("created_at", -1)
        .skip(skip)
        .limit(min(limit, 200))
    )
    rows = await cur.to_list(length=limit)
    return rows, total


async def resend_failed_communication_delivery_email(
    *,
    delivery_id: str,
    admin_user: Dict[str, Any],
) -> Dict[str, Any]:
    """Retry email for a single FAILED admin communication delivery row. Audited."""
    db = database.get_db()
    ddoc = await db.communication_deliveries.find_one({"delivery_id": delivery_id})
    if not ddoc:
        raise ValueError("Delivery not found")
    if ddoc.get("email_status") != "FAILED":
        raise ValueError("Resend is only available when email_status is FAILED")

    msg = await db.communication_messages.find_one({"communication_id": ddoc["communication_id"]})
    if not msg:
        raise ValueError("Communication message not found")

    cid = ddoc["client_id"]
    row = None
    async for batch in iter_recipient_batches("SINGLE", {"client_id": cid}):
        for r in batch:
            if r.get("client_id") == cid:
                row = r
                break
        if row:
            break
    if not row or not row.get("email"):
        raise ValueError("Recipient email could not be resolved for this client")

    from services.notification_orchestrator import NotificationOrchestrator

    message_type = str(msg.get("message_type") or "GENERAL_ANNOUNCEMENT")
    notif_template_key = notification_template_key_for_message_type(message_type)
    force_platform = use_platform_letterhead_email(message_type)
    safe_html = msg.get("body_html_snapshot") or ""
    text_body = (msg.get("body_text_snapshot") or "").strip() or _strip_html_simple(safe_html)
    subject_stripped = (msg.get("subject") or "").strip()
    extras = {"incident_title": subject_stripped}
    vars_ctx = build_variable_context(row, extras)
    rendered_html = apply_template_variables(safe_html, vars_ctx)
    rendered_subject = apply_template_variables(subject_stripped, vars_ctx)
    per_text = apply_template_variables(text_body, vars_ctx)

    ctx = {
        "subject": rendered_subject,
        "email_header_title": rendered_subject[:200],
        "message": rendered_html,
        "text_message": per_text,
        "client_name": vars_ctx["client_name"],
        "customer_reference": vars_ctx.get("customer_reference") or "",
        "portal_link": vars_ctx["portal_link"],
        "communication_id": ddoc["communication_id"],
        "message_type": message_type,
        "show_notification_preferences_link": notif_template_key == "ADMIN_CLIENT_COMMUNICATION_ANNOUNCEMENT",
    }
    if force_platform:
        ctx["_force_pleerity_email_branding"] = True

    orch = NotificationOrchestrator()
    resend_key = f"{ddoc['communication_id']}:{cid}:email:resend:{uuid.uuid4().hex[:12]}"
    res = await orch.send(
        notif_template_key,
        cid,
        ctx,
        idempotency_key=resend_key,
        event_type="admin_communication_resend",
    )

    now = datetime.now(timezone.utc)
    resend_entry = {
        "at": now.isoformat(),
        "outcome": res.outcome,
        "error": res.error_message or res.block_reason,
        "idempotency_key": resend_key,
        "by_portal_user_id": admin_user.get("portal_user_id"),
    }
    await db.communication_deliveries.update_one(
        {"delivery_id": delivery_id},
        {
            "$push": {"email_resend_attempts": resend_entry},
            "$set": {
                "updated_at": now,
                "email_last_resend_at": now,
            },
        },
    )

    new_status = "FAILED"
    err = res.error_message
    pmid = None
    if res.outcome in ("sent", "duplicate_ignored"):
        new_status = "SENT"
        pmid = (res.details or {}).get("provider_message_id")
        if res.outcome == "duplicate_ignored":
            err = "duplicate_ignored"
        else:
            err = None
    elif res.outcome == "blocked":
        new_status = "BLOCKED"
        err = res.block_reason

    await db.communication_deliveries.update_one(
        {"delivery_id": delivery_id},
        {
            "$set": {
                "email_status": new_status,
                "postmark_message_id": pmid,
                "error_message": err,
                "updated_at": now,
            }
        },
    )

    admin_id = admin_user.get("portal_user_id") or "unknown"
    await create_audit_log(
        action=AuditAction.ADMIN_ACTION,
        actor_id=admin_id,
        client_id=cid,
        resource_type="communication_delivery",
        resource_id=delivery_id,
        metadata={
            "action_type": "admin_communication_delivery_resend",
            "delivery_id": delivery_id,
            "communication_id": ddoc["communication_id"],
            "outcome": res.outcome,
        },
    )

    return {"delivery_id": delivery_id, "email_status": new_status, "outcome": res.outcome, "error": err}


async def get_message_detail(communication_id: str) -> Optional[Dict[str, Any]]:
    db = database.get_db()
    doc = await db.communication_messages.find_one({"communication_id": communication_id}, {"_id": 0})
    if not doc:
        return None
    dels = (
        await db.communication_deliveries.find({"communication_id": communication_id}, {"_id": 0})
        .sort("created_at", 1)
        .limit(5000)
        .to_list(length=5000)
    )
    doc["deliveries"] = dels
    return doc


def _checksum_payload_from_stored(doc: Dict[str, Any]) -> Dict[str, Any]:
    canonical = doc.get("target_filters") or {}
    return {
        "message_type": doc.get("message_type"),
        "severity": doc.get("severity"),
        "target_scope": doc.get("target_scope"),
        "target_filters": _canonical_filters(canonical),
        "subject": (doc.get("subject") or "").strip(),
        "body_html": doc.get("body_html_snapshot") or "",
        "body_text": doc.get("body_text_snapshot") or "",
        "in_app_title": doc.get("in_app_title") or "",
        "in_app_body": doc.get("in_app_body") or "",
        "banner_title": doc.get("banner_title") or "",
        "banner_message": doc.get("banner_message") or "",
        "channels": sorted(doc.get("channels") or []),
    }


async def upsert_communication_draft(
    admin_user: Dict[str, Any],
    *,
    draft_communication_id: Optional[str],
    target_scope: str,
    target_filters: Optional[Dict[str, Any]],
    message_type: str,
    severity: str,
    subject: str,
    body_html: str,
    channels: List[str],
    in_app_title: Optional[str],
    in_app_body: Optional[str],
    banner_title: Optional[str],
    banner_message: Optional[str],
    template_id: Optional[str],
    draft_name: Optional[str],
) -> str:
    db = database.get_db()
    now = datetime.now(timezone.utc)
    admin_id = admin_user.get("portal_user_id") or "unknown"
    canonical = _canonical_filters(target_filters)
    safe_html = sanitize_admin_html(body_html)
    text_body = _strip_html_simple(safe_html)
    doc = {
        "status": "DRAFT",
        "message_type": message_type,
        "severity": severity,
        "target_scope": target_scope,
        "target_filters": canonical,
        "channels": channels,
        "subject": subject.strip(),
        "body_html_snapshot": safe_html[:200000],
        "body_text_snapshot": text_body[:50000],
        "in_app_title": in_app_title,
        "in_app_body": in_app_body,
        "banner_title": banner_title,
        "banner_message": banner_message,
        "template_id": template_id,
        "draft_name": (draft_name or "").strip() or None,
        "sent_by_portal_user_id": admin_id,
        "sent_by_role": admin_user.get("role"),
        "updated_at": now,
    }
    if draft_communication_id:
        existing = await db.communication_messages.find_one(
            {"communication_id": draft_communication_id, "status": "DRAFT", "sent_by_portal_user_id": admin_id}
        )
        if not existing:
            raise ValueError("Draft not found")
        await db.communication_messages.update_one(
            {"communication_id": draft_communication_id},
            {"$set": doc},
        )
        await create_audit_log(
            action=AuditAction.ADMIN_COMMUNICATION_DRAFT_SAVED,
            actor_id=admin_id,
            metadata={"communication_id": draft_communication_id},
        )
        return draft_communication_id
    cid = f"DRAFT-{uuid.uuid4().hex[:12].upper()}"
    doc["communication_id"] = cid
    doc["created_at"] = now
    await db.communication_messages.insert_one(doc)
    await create_audit_log(
        action=AuditAction.ADMIN_COMMUNICATION_DRAFT_SAVED,
        actor_id=admin_id,
        metadata={"communication_id": cid},
    )
    return cid


async def list_communication_drafts(sent_by_portal_user_id: str) -> List[Dict[str, Any]]:
    db = database.get_db()
    cur = (
        db.communication_messages.find(
            {"status": "DRAFT", "sent_by_portal_user_id": sent_by_portal_user_id},
            {"_id": 0},
        )
        .sort("updated_at", -1)
        .limit(100)
    )
    return await cur.to_list(length=100)


async def delete_communication_draft(communication_id: str, admin_id: str) -> bool:
    db = database.get_db()
    res = await db.communication_messages.delete_one(
        {"communication_id": communication_id, "status": "DRAFT", "sent_by_portal_user_id": admin_id}
    )
    return res.deleted_count > 0


async def schedule_communication(
    admin_user: Dict[str, Any],
    *,
    target_scope: str,
    target_filters: Optional[Dict[str, Any]],
    message_type: str,
    severity: str,
    subject: str,
    body_html: str,
    body_text: Optional[str],
    in_app_title: Optional[str],
    in_app_body: Optional[str],
    banner_title: Optional[str],
    banner_message: Optional[str],
    channels: List[str],
    template_id: Optional[str],
    preview_checksum: str,
    expected_recipient_count: int,
    acknowledge_high_risk: bool,
    scheduled_at: datetime,
) -> str:
    if scheduled_at.tzinfo is None:
        raise ValueError("scheduled_at must be timezone-aware (UTC)")
    if scheduled_at <= datetime.now(timezone.utc):
        raise ValueError("scheduled_at must be in the future")
    db = database.get_db()
    canonical = _canonical_filters(target_filters)
    checksum_payload = {
        "message_type": message_type,
        "severity": severity,
        "target_scope": target_scope,
        "target_filters": canonical,
        "subject": subject.strip(),
        "body_html": body_html,
        "body_text": body_text or "",
        "in_app_title": in_app_title or "",
        "in_app_body": in_app_body or "",
        "banner_title": banner_title or "",
        "banner_message": banner_message or "",
        "channels": sorted(channels),
    }
    if compute_preview_checksum(checksum_payload) != preview_checksum:
        raise ValueError("preview_checksum mismatch — run preview again")
    if requires_high_risk_acknowledgement(target_scope, message_type):
        if not acknowledge_high_risk:
            raise ValueError(
                "acknowledge_high_risk required for all-client schedules, INCIDENT, or DOWNTIME_ALERT"
            )
    total = await count_recipients(target_scope, target_filters)
    if total != expected_recipient_count:
        raise ValueError(
            f"Recipient count changed (was {expected_recipient_count}, now {total}). Re-run preview."
        )
    if total == 0:
        raise ValueError("No recipients — schedule blocked")

    communication_id = f"ACM-{uuid.uuid4().hex[:12].upper()}"
    now = datetime.now(timezone.utc)
    admin_id = admin_user.get("portal_user_id") or "unknown"
    safe_html = sanitize_admin_html(body_html)
    text_body = (body_text or "").strip() or _strip_html_simple(safe_html)
    await db.communication_messages.insert_one(
        {
            "communication_id": communication_id,
            "status": "SCHEDULED",
            "scheduled_at": scheduled_at,
            "expected_recipient_count": expected_recipient_count,
            "preview_checksum": preview_checksum,
            "message_type": message_type,
            "severity": severity,
            "target_scope": target_scope,
            "target_filters": canonical,
            "channels": channels,
            "subject": subject.strip(),
            "body_html_snapshot": safe_html[:200000],
            "body_text_snapshot": text_body[:50000],
            "in_app_title": in_app_title,
            "in_app_body": in_app_body,
            "banner_title": banner_title,
            "banner_message": banner_message,
            "template_id": template_id,
            "sent_by_portal_user_id": admin_id,
            "sent_by_role": admin_user.get("role"),
            "recipient_count": total,
            "created_at": now,
            "updated_at": now,
        }
    )
    await create_audit_log(
        action=AuditAction.ADMIN_COMMUNICATION_SCHEDULED,
        actor_id=admin_id,
        metadata={"communication_id": communication_id, "scheduled_at": scheduled_at.isoformat(), "recipient_count": total},
    )
    return communication_id


async def _finalize_communication_status(
    communication_id: str,
    *,
    total: int,
    channels: List[str],
    banner_id: Optional[str],
    email_sent: int,
    email_failed: int,
    email_blocked: int,
    in_app_sent: int,
    in_app_failed: int,
) -> str:
    delivery_attempted = any(c in channels for c in ("email", "in_app"))
    any_ok = (email_sent + in_app_sent) > 0 or bool(banner_id)
    any_fail = (email_failed + in_app_failed) > 0
    if not any_ok and delivery_attempted and total > 0:
        final_status = "FAILED"
    elif any_fail and any_ok:
        final_status = "PARTIAL_FAILURE"
    elif any_fail:
        final_status = "FAILED"
    else:
        final_status = "SENT"
    await database.get_db().communication_messages.update_one(
        {"communication_id": communication_id},
        {
            "$set": {
                "status": final_status,
                "updated_at": datetime.now(timezone.utc),
                "summary": {
                    "email_sent": email_sent,
                    "email_failed": email_failed,
                    "email_blocked": email_blocked,
                    "in_app_sent": in_app_sent,
                    "in_app_failed": in_app_failed,
                    "banner_id": banner_id,
                },
            }
        },
    )
    return final_status


async def execute_scheduled_communication_delivery(doc: Dict[str, Any]) -> str:
    """Deliver a SCHEDULED row (caller must have set status to SENDING)."""
    db = database.get_db()
    communication_id = doc["communication_id"]
    admin_id = doc.get("sent_by_portal_user_id") or "unknown"
    canonical = doc.get("target_filters") or {}
    target_scope = doc["target_scope"]
    payload = _checksum_payload_from_stored(doc)
    if compute_preview_checksum(payload) != doc.get("preview_checksum"):
        raise ValueError("checksum mismatch on stored scheduled message")
    total = await count_recipients(target_scope, canonical)
    if total != doc.get("expected_recipient_count"):
        raise ValueError("recipient count changed since schedule — aborting send")
    safe_html = doc.get("body_html_snapshot") or ""
    text_body = doc.get("body_text_snapshot") or ""
    subject_stripped = (doc.get("subject") or "").strip()
    channels = list(doc.get("channels") or [])
    message_type = doc.get("message_type")
    severity = doc.get("severity") or "info"
    now = datetime.now(timezone.utc)

    banner_id = None
    if "banner" in channels and (doc.get("banner_title") or doc.get("banner_message")):
        banner_id = f"BNR-{uuid.uuid4().hex[:10].upper()}"
        bt = _banner_fields_for_communication(target_scope, canonical)
        await db.system_banners.insert_one(
            {
                "banner_id": banner_id,
                "title": (doc.get("banner_title") or subject_stripped[:120] or "Notice").strip(),
                "message": (doc.get("banner_message") or _strip_html_simple(safe_html)[:500]).strip(),
                "severity": str(severity).lower(),
                "start_at": now,
                "end_at": None,
                "active": True,
                "target_all": bt["target_all"],
                "target_client_ids": bt["target_client_ids"],
                "target_scope": bt["target_scope"],
                "target_filters": bt["target_filters"],
                "persistent_display": str(severity).upper() in ("CRITICAL", "HIGH", "EMERGENCY"),
                "communication_id": communication_id,
                "created_by_portal_user_id": admin_id,
                "created_at": now,
                "updated_at": now,
            }
        )

    email_sent, email_failed, email_blocked, in_app_sent, in_app_failed = await _deliver_recipient_batches(
        communication_id=communication_id,
        now=now,
        target_scope=target_scope,
        target_filters=canonical,
        total=total,
        message_type=message_type,
        severity=severity,
        channels=channels,
        safe_html=safe_html,
        text_body=text_body,
        subject_stripped=subject_stripped,
        in_app_title=doc.get("in_app_title"),
        in_app_body=doc.get("in_app_body"),
    )

    final_status = await _finalize_communication_status(
        communication_id,
        total=total,
        channels=channels,
        banner_id=banner_id,
        email_sent=email_sent,
        email_failed=email_failed,
        email_blocked=email_blocked,
        in_app_sent=in_app_sent,
        in_app_failed=in_app_failed,
    )
    await create_audit_log(
        action=AuditAction.ADMIN_COMMUNICATION_SENT,
        actor_id=admin_id,
        metadata={
            "communication_id": communication_id,
            "message_type": message_type,
            "target_scope": target_scope,
            "recipient_count": total,
            "channels": channels,
            "status": final_status,
            "phase": "scheduled_execute",
        },
    )
    return final_status


async def process_due_scheduled_communications() -> Dict[str, Any]:
    db = database.get_db()
    now = datetime.now(timezone.utc)
    due = (
        await db.communication_messages.find(
            {"status": "SCHEDULED", "scheduled_at": {"$lte": now}},
            {"_id": 1},
        )
        .sort("scheduled_at", 1)
        .limit(8)
        .to_list(length=8)
    )
    processed = 0
    for ref in due:
        doc = await db.communication_messages.find_one({"_id": ref["_id"], "status": "SCHEDULED"})
        if not doc:
            continue
        lock = await db.communication_messages.update_one(
            {"_id": ref["_id"], "status": "SCHEDULED"},
            {"$set": {"status": "SENDING", "updated_at": now}},
        )
        if lock.modified_count == 0:
            continue
        try:
            await execute_scheduled_communication_delivery(doc)
            processed += 1
        except Exception as e:
            logger.exception("Scheduled communication failed %s", doc.get("communication_id"))
            await db.communication_messages.update_one(
                {"_id": ref["_id"]},
                {
                    "$set": {
                        "status": "FAILED",
                        "error": str(e)[:500],
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
            )
    return {"message": f"Executed {processed} scheduled communication(s)", "count": processed}
