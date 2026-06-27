"""
Enterprise Notification Orchestrator.
Single entry point for all transactional email and SMS.
No route, job, webhook, or provisioning logic may send email/SMS directly.
"""
from __future__ import annotations

import logging
import os
import re
import random
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional, Tuple

from database import database
from models import AuditAction
from utils.audit import create_audit_log

logger = logging.getLogger(__name__)

# Governed onboarding recovery sends via ADMIN_MANUAL; template requires_provisioned must not
# block pre-provisioning payment/continuation emails (intake complete, payment not yet done).
ONBOARDING_RECOVERY_EVENT_TYPES = frozenset(
    {
        "onboarding_recovery_payment_continuation",
        "onboarding_recovery_continuation",
    }
)

# Governed commercial entitlement continuity — may send before full provisioning.
COMMERCIAL_ENTITLEMENT_EVENT_TYPES = frozenset(
    {
        "commercial_entitlement_continuity",
    }
)


def _normalized_idempotency_key(idempotency_key: Optional[str]) -> Optional[str]:
    """
    Return a non-empty idempotency key, or None.

    message_logs has a unique sparse index on idempotency_key. Documents with the field
    set to null still occupy one index entry, so only one row may have idempotency_key=null
    cluster-wide — subsequent inserts E11000 and send() returns duplicate_ignored.
    Callers that omit dedupe (e.g. forgot-password) must not store the field at all.
    """
    if idempotency_key is None:
        return None
    s = str(idempotency_key).strip()
    return s if s else None


def _strip_html_to_text(html: str) -> str:
    """Crude HTML strip for plain-text fallback (e.g. scheduled-report message)."""
    if not html:
        return ""
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:5000] if len(text) > 5000 else text


def _context_message_is_full_html_document(context: Dict) -> bool:
    """
    True when context['message'] is a full HTML document meant to be the entire email body.

    Used for admin-manual: DB templates often wrap {{message}} in a customer shell; passing a
    complete <html> document would nest two shells. Fragments (<p>, <div>, …) still use the DB path.
    """
    msg = context.get("message")
    if msg is None:
        return False
    s = str(msg).strip().lstrip("\ufeff")
    if not s:
        return False
    head = s[:512].lower()
    if head.startswith("<!doctype html"):
        return True
    return bool(re.match(r"<\s*html\b", head))


DEFAULT_SENDER = os.getenv("EMAIL_SENDER", "info@pleerityenterprise.co.uk")
POSTMARK_MESSAGE_STREAM = os.getenv("POSTMARK_MESSAGE_STREAM", "outbound").strip() or "outbound"
EMAIL_REPLY_TO = (os.getenv("EMAIL_REPLY_TO") or "").strip()

# Deferred retry backoff (notification_retry_queue). Used for SMS transient failures and for EMAIL
# only when postmark_inline_exhausted is false (see send() / process_retry guards). Email that exhausts
# inline Postmark retries in postmark_delivery.deliver_postmark_email is terminal: we do not enqueue
# here, to avoid duplicate sends from inline + deferred retry both firing for the same logical message.
EMAIL_BACKOFFS = [30, 120, 600]
SMS_BACKOFFS = [60]
MAX_EMAIL_ATTEMPTS = 3
MAX_SMS_ATTEMPTS = 2

# Global outbound throttling (per minute, rolling window)
NOTIFICATION_EMAIL_PER_MINUTE_LIMIT = int(os.getenv("NOTIFICATION_EMAIL_PER_MINUTE_LIMIT", "60"))
NOTIFICATION_SMS_PER_MINUTE_LIMIT = int(os.getenv("NOTIFICATION_SMS_PER_MINUTE_LIMIT", "30"))


@dataclass
class NotificationResult:
    outcome: str  # sent | blocked | failed | duplicate_ignored
    message_id: Optional[str] = None
    block_reason: Optional[str] = None
    error_message: Optional[str] = None
    status_code: Optional[int] = None  # 403 for ACCOUNT_NOT_READY / PLAN_GATE_DENIED
    details: Dict[str, Any] = field(default_factory=dict)


async def _operational_evidence_notification_queued(
    message_id: str,
    client_id: Optional[str],
    channel: str,
    template_key: str,
) -> None:
    try:
        from services.operational_evidence.producers import emit_notification_queued

        await emit_notification_queued(
            message_id=message_id,
            client_id=client_id,
            channel=channel,
            template_key=template_key,
        )
    except Exception:
        pass


async def _operational_evidence_notification_result(
    message_id: Optional[str],
    client_id: Optional[str],
    channel: str,
    template_key: str,
    result: NotificationResult,
) -> None:
    if not message_id or result.outcome in ("duplicate_ignored", "blocked"):
        return
    try:
        from services.operational_evidence.producers import emit_notification_outcome

        await emit_notification_outcome(
            message_id=message_id,
            client_id=client_id,
            channel=channel,
            template_key=template_key,
            outcome=result.outcome,
            error_message=result.error_message,
            transient=bool(result.details.get("transient")),
            attempt_count=result.details.get("attempt_count"),
        )
    except Exception:
        pass


def _is_transient_error(exc: Exception) -> bool:
    """True if error is retryable (timeout, 5xx)."""
    if isinstance(exc, TimeoutError):
        return True
    s = str(exc).lower()
    if "timeout" in s or "timed out" in s:
        return True
    if hasattr(exc, "code"):
        c = getattr(exc, "code", None)
        if c and (isinstance(c, int) and 500 <= c < 600 or str(c).startswith("5")):
            return True
    if hasattr(exc, "status_code") and isinstance(getattr(exc, "status_code"), int):
        sc = getattr(exc, "status_code")
        if 500 <= sc < 600:
            return True
    return False


class NotificationOrchestrator:
    """Single entry point for all client transactional email and SMS."""

    def __init__(self):
        self._postmark_client = None
        self._twilio_client = None
        postmark_token = os.getenv("POSTMARK_SERVER_TOKEN")
        if postmark_token:
            try:
                from postmarker.core import PostmarkClient
                self._postmark_client = PostmarkClient(server_token=postmark_token)
            except Exception as e:
                logger.warning(f"Postmark client init failed: {e}")
        if os.getenv("SMS_ENABLED", "").lower() == "true":
            sid = os.getenv("TWILIO_ACCOUNT_SID")
            token = os.getenv("TWILIO_AUTH_TOKEN")
            if sid and token:
                try:
                    from twilio.rest import Client
                    self._twilio_client = Client(sid, token)
                except Exception as e:
                    logger.warning(f"Twilio client init failed: {e}")

    async def _check_global_throttle(
        self,
        db,
        channel: str,
        message_id: str,
        client_id: Optional[str],
        template_key: str,
    ) -> Optional[NotificationResult]:
        """
        If global per-minute limit for channel is reached: set MessageLog to DEFERRED_THROTTLED,
        enqueue retry in 30-60s, audit NOTIFICATION_THROTTLED, and return that result.
        Otherwise return None.
        """
        limit = NOTIFICATION_EMAIL_PER_MINUTE_LIMIT if channel == "EMAIL" else NOTIFICATION_SMS_PER_MINUTE_LIMIT
        since = datetime.now(timezone.utc) - timedelta(minutes=1)
        count = await db.message_logs.count_documents({
            "channel": channel,
            "created_at": {"$gte": since},
        })
        if count < limit:
            return None
        now = datetime.now(timezone.utc)
        next_run = now + timedelta(seconds=random.randint(30, 60))
        await db.message_logs.update_one(
            {"message_id": message_id},
            {"$set": {"status": "DEFERRED_THROTTLED", "error_message": f"Global throttle: {channel} limit {limit}/min"}},
        )
        await db.notification_retry_queue.insert_one({
            "message_id": message_id,
            "template_key": template_key,
            "client_id": client_id,
            "channel": channel,
            "attempt_count": 1,
            "next_run_at": next_run,
            "status": "PENDING",
            "created_at": now,
        })
        await create_audit_log(
            action=AuditAction.NOTIFICATION_THROTTLED,
            client_id=client_id,
            metadata={"channel": channel, "limit": limit, "window_minutes": 1, "template_key": template_key, "message_id": message_id},
        )
        return NotificationResult(
            outcome="blocked",
            block_reason="DEFERRED_THROTTLED",
            message_id=message_id,
            details={"channel": channel, "limit": limit},
        )

    async def send(
        self,
        template_key: str,
        client_id: Optional[str],
        context: Dict[str, Any],
        idempotency_key: Optional[str] = None,
        event_type: Optional[str] = None,
    ) -> NotificationResult:
        """
        Send a notification (email or SMS) via the orchestrator.
        client_id may be None for internal/admin/lead sends; then context must contain "recipient" (or "to_email").
        Returns NotificationResult with outcome: sent | blocked | failed | duplicate_ignored.
        """
        db = database.get_db()
        idempotency_key = _normalized_idempotency_key(idempotency_key)

        # Load template
        template = await db.notification_templates.find_one(
            {"template_key": template_key, "is_active": True},
            {"_id": 0},
        )
        if not template:
            logger.warning(f"Notification template not found or inactive: {template_key}")
            # Record attempt in message_logs so it appears in notification health
            try:
                msg_id = str(uuid.uuid4())
                recipient = (context or {}).get("recipient") or (context or {}).get("to_email") or (context or {}).get("email") or ""
                await db.message_logs.insert_one({
                    "message_id": msg_id,
                    "client_id": client_id,
                    "recipient": str(recipient).strip() if recipient else None,
                    "template_key": template_key,
                    "channel": "EMAIL",
                    "status": "FAILED",
                    "error_message": f"Template {template_key} not found or inactive",
                    "attempt_count": 1,
                    "metadata": {"event_type": event_type or "send"},
                    "created_at": datetime.now(timezone.utc),
                })
            except Exception as e:
                logger.warning(f"Failed to write message_log for missing template: {e}")
            return NotificationResult(
                outcome="failed",
                error_message=f"Template {template_key} not found or inactive",
                status_code=500,
            )

        # Internal/admin/lead send: no client_id, recipient from context
        if not client_id:
            recipient = (context or {}).get("recipient") or (context or {}).get("to_email") or (context or {}).get("email")
            if not recipient or not str(recipient).strip():
                return NotificationResult(outcome="failed", error_message="client_id and recipient required", status_code=400)
            client = {"client_id": None, "notification_preferences": {}}
            channel = template.get("channel", "EMAIL")
            message_id = str(uuid.uuid4())
            if idempotency_key:
                existing = await db.message_logs.find_one(
                    {"idempotency_key": idempotency_key},
                    {"_id": 0, "message_id": 1, "status": 1},
                )
                if existing:
                    return NotificationResult(outcome="duplicate_ignored", message_id=existing.get("message_id"), details={"idempotency_key": idempotency_key})
            log_doc = {
                "message_id": message_id,
                "client_id": None,
                "recipient": str(recipient).strip(),
                "template_key": template_key,
                "channel": channel,
                "status": "PENDING",
                "attempt_count": 1,
                "metadata": {
                    "event_type": event_type,
                    **(
                        {
                            k: str(v)
                            for k, v in (context or {}).items()
                            if k not in ("recipient", "to_email", "email", "attachments")
                        }
                    ),
                },
                "created_at": datetime.now(timezone.utc),
            }
            if idempotency_key:
                log_doc["idempotency_key"] = idempotency_key
            try:
                await db.message_logs.insert_one(log_doc)
            except Exception as e:
                if "duplicate key" in str(e).lower() or "E11000" in str(e):
                    existing = await db.message_logs.find_one({"idempotency_key": idempotency_key}, {"_id": 0, "message_id": 1})
                    return NotificationResult(outcome="duplicate_ignored", message_id=existing.get("message_id") if existing else None, details={"idempotency_key": idempotency_key})
                raise
            await _operational_evidence_notification_queued(message_id, None, channel, template_key)
            throttle_result = await self._check_global_throttle(db, channel, message_id, None, template_key)
            if throttle_result:
                return throttle_result
            if channel == "EMAIL":
                result = await self._send_email(template_key, template, client, context, message_id, db, datetime.now(timezone.utc), str(recipient).strip())
            else:
                result = await self._send_sms(template_key, template, client, context, message_id, db, datetime.now(timezone.utc), str(recipient).strip())
            await _operational_evidence_notification_result(message_id, None, channel, template_key, result)
            return result

        # Load client
        client = await db.clients.find_one(
            {"client_id": client_id},
            {
                "_id": 0,
                "client_id": 1,
                "email": 1,
                "contact_email": 1,
                "full_name": 1,
                "contact_name": 1,
                "onboarding_status": 1,
                "subscription_status": 1,
                "entitlement_status": 1,
            },
        )
        if not client:
            return NotificationResult(
                outcome="failed",
                error_message="Client not found",
                status_code=404,
            )
        prefs = await db.notification_preferences.find_one(
            {"client_id": client_id},
            {
                "_id": 0,
                "sms_enabled": 1,
                "sms_phone_number": 1,
                "sms_phone_verified": 1,
                "system_announcements": 1,
                "quiet_hours_enabled": 1,
                "quiet_hours_start": 1,
                "quiet_hours_end": 1,
                "compliance_notifications_enabled": 1,
                "reporting_notifications_enabled": 1,
                "marketing_notifications_enabled": 1,
            },
        )
        client["notification_preferences"] = prefs or {}

        # Idempotency: if key provided, try to insert a placeholder first
        message_id = str(uuid.uuid4())
        if idempotency_key:
            existing = await db.message_logs.find_one(
                {"idempotency_key": idempotency_key},
                {"_id": 0, "message_id": 1, "status": 1},
            )
            if existing:
                return NotificationResult(
                    outcome="duplicate_ignored",
                    message_id=existing.get("message_id"),
                    details={"idempotency_key": idempotency_key},
                )
            # We will insert with idempotency_key below; if race and duplicate key, we'll catch and return duplicate_ignored

        # Gating
        channel = template.get("channel", "EMAIL")
        block_result = await self._apply_gating(template, client, client_id, template_key, context, channel, event_type)
        if block_result:
            return block_result

        # Category-based preference check (email only; system_critical and internal always sent)
        # When client_id is None (e.g. lead emails), we do not block on preferences; lead consent is enforced at sequence level.
        if channel == "EMAIL" and client_id:
            category = template.get("email_category")
            if category and category not in ("system_critical", "internal"):
                prefs = client.get("notification_preferences") or {}
                allowed = True
                if category == "compliance_notifications":
                    allowed = prefs.get("compliance_notifications_enabled", True)
                elif category == "reporting_notifications":
                    allowed = prefs.get("reporting_notifications_enabled", True)
                elif category == "marketing_notifications":
                    allowed = prefs.get("marketing_notifications_enabled", True)
                elif category == "lead_nurture":
                    allowed = prefs.get("lead_nurture_enabled", True)
                if not allowed:
                    await self._write_blocked_log(
                        db, client_id, template_key, channel, "BLOCKED_PREFERENCE_DISABLED", None, idempotency_key, context, event_type,
                    )
                    await create_audit_log(
                        action=AuditAction.NOTIFICATION_BLOCKED_PREFERENCE_DISABLED,
                        client_id=client_id,
                        metadata={"template_key": template_key, "email_category": category},
                    )
                    return NotificationResult(
                        outcome="blocked",
                        block_reason="BLOCKED_PREFERENCE_DISABLED",
                        details={"email_category": category},
                    )
            # Explicit user preference for system/platform announcements.
            is_system_announcement = (
                category == "system_announcements"
                or template_key in {"SYSTEM_ANNOUNCEMENT", "PLATFORM_ANNOUNCEMENT"}
                or (event_type or "").lower() in {"system_announcement", "platform_announcement"}
            )
            if is_system_announcement and not (client.get("notification_preferences") or {}).get("system_announcements", True):
                await self._write_blocked_log(
                    db, client_id, template_key, channel, "BLOCKED_PREFERENCE_DISABLED", None, idempotency_key, context, event_type,
                )
                return NotificationResult(
                    outcome="blocked",
                    block_reason="BLOCKED_PREFERENCE_DISABLED",
                    details={"preference_key": "system_announcements"},
                )

        # Resolve recipient (context may override for e.g. scheduled report recipients)
        recipient = (context or {}).get("recipient")
        if recipient:
            recipient = str(recipient).strip()
        if not recipient:
            recipient = self._resolve_recipient(client, channel)
        if not recipient:
            await self._write_blocked_log(
                db, client_id, template_key, channel, "no_recipient", None, idempotency_key, context, event_type,
            )
            await create_audit_log(
                action=AuditAction.EMAIL_SKIPPED_NO_RECIPIENT,
                client_id=client_id,
                metadata={"template_key": template_key, "channel": channel},
            )
            return NotificationResult(outcome="blocked", block_reason="no_recipient", status_code=400)

        # SMS 24h throttle (per client; skip for OTP where client_id is None)
        if channel == "SMS" and client_id is not None:
            throttle_ok = await self._check_sms_throttle(db, client_id, template_key)
            if not throttle_ok:
                await self._write_blocked_log(
                    db, client_id, template_key, channel, "sms_24h_throttle", None, idempotency_key, context, event_type,
                )
                return NotificationResult(outcome="blocked", block_reason="sms_24h_throttle")

        # Insert PENDING message log (with idempotency_key for duplicate detection)
        now = datetime.now(timezone.utc)
        meta = {
            "event_type": event_type,
            **({k: str(v) for k, v in (context or {}).items() if k != "attachments"}),
        }
        if template.get("email_category"):
            meta["email_category"] = template["email_category"]
        log_doc = {
            "message_id": message_id,
            "client_id": client_id,
            "recipient": recipient,
            "template_key": template_key,
            "channel": channel,
            "status": "PENDING",
            "attempt_count": 1,
            "metadata": meta,
            "created_at": now,
        }
        if idempotency_key:
            log_doc["idempotency_key"] = idempotency_key
        try:
            await db.message_logs.insert_one(log_doc)
        except Exception as e:
            if "duplicate key" in str(e).lower() or "E11000" in str(e):
                existing = await db.message_logs.find_one(
                    {"idempotency_key": idempotency_key},
                    {"_id": 0, "message_id": 1},
                )
                return NotificationResult(
                    outcome="duplicate_ignored",
                    message_id=existing.get("message_id") if existing else None,
                    details={"idempotency_key": idempotency_key},
                )
            raise

        await _operational_evidence_notification_queued(message_id, client_id, channel, template_key)
        throttle_result = await self._check_global_throttle(db, channel, message_id, client_id, template_key)
        if throttle_result:
            return throttle_result

        # Send
        if channel == "EMAIL":
            result = await self._send_email(template_key, template, client, context, message_id, db, now, recipient)
        else:
            result = await self._send_sms(template_key, template, client, context, message_id, db, now, recipient)

        if result.outcome == "sent":
            await _operational_evidence_notification_result(message_id, client_id, channel, template_key, result)
            return result
        if result.outcome == "failed" and result.details.get("transient") and result.details.get("attempt_count") is not None:
            # Enqueue retry
            backoffs = SMS_BACKOFFS if channel == "SMS" else EMAIL_BACKOFFS
            attempt = result.attempt_count
            if attempt <= len(backoffs) and not result.details.get("postmark_inline_exhausted"):
                next_run = now + timedelta(seconds=backoffs[attempt - 1])
                await db.notification_retry_queue.insert_one({
                    "message_id": message_id,
                    "template_key": template_key,
                    "client_id": client_id,
                    "channel": channel,
                    "attempt_count": attempt + 1,
                    "next_run_at": next_run,
                    "status": "PENDING",
                    "created_at": now,
                })
        elif result.outcome == "failed" and not result.details.get("transient"):
            await create_audit_log(
                action=AuditAction.NOTIFICATION_FAILED_PERMANENT,
                client_id=client_id,
                metadata={
                    "message_id": message_id,
                    "template_key": template_key,
                    "channel": channel,
                    "error": result.error_message,
                },
            )
        await _operational_evidence_notification_result(message_id, client_id, channel, template_key, result)
        return result

    async def _apply_gating(
        self,
        template: Dict,
        client: Dict,
        client_id: str,
        template_key: str,
        context: Dict,
        channel: str,
        event_type: Optional[str] = None,
    ) -> Optional[NotificationResult]:
        db = database.get_db()

        if template.get("requires_provisioned"):
            recovery_continuation = (event_type or "") in ONBOARDING_RECOVERY_EVENT_TYPES
            commercial_continuity = (event_type or "") in COMMERCIAL_ENTITLEMENT_EVENT_TYPES
            if (
                not recovery_continuation
                and not commercial_continuity
                and client.get("onboarding_status") != "PROVISIONED"
            ):
                await self._write_blocked_log(
                    db, client_id, template_key, channel, "BLOCKED_PROVISIONING_INCOMPLETE", None, None, context, None,
                )
                await create_audit_log(
                    action=AuditAction.NOTIFICATION_BLOCKED_PROVISIONING_INCOMPLETE,
                    client_id=client_id,
                    metadata={"template_key": template_key, "event_type": event_type},
                )
                return NotificationResult(
                    outcome="blocked",
                    block_reason="BLOCKED_PROVISIONING_INCOMPLETE",
                    status_code=403,
                    details={"error_code": "ACCOUNT_NOT_READY", "message": "Provisioning not completed."},
                )

        if template.get("requires_active_subscription"):
            if (client.get("subscription_status") or "").upper() != "ACTIVE":
                await self._write_blocked_log(
                    db, client_id, template_key, channel, "BLOCKED_SUBSCRIPTION_INACTIVE", None, None, context, None,
                )
                await create_audit_log(
                    action=AuditAction.NOTIFICATION_BLOCKED_SUBSCRIPTION_INACTIVE,
                    client_id=client_id,
                    metadata={"template_key": template_key, "subscription_status": client.get("subscription_status")},
                )
                return NotificationResult(outcome="blocked", block_reason="BLOCKED_SUBSCRIPTION_INACTIVE")

        if template.get("requires_entitlement_enabled"):
            if (client.get("entitlement_status") or "").upper() != "ENABLED":
                await self._write_blocked_log(
                    db, client_id, template_key, channel, "BLOCKED_SUBSCRIPTION_INACTIVE", None, None, context, None,
                )
                await create_audit_log(
                    action=AuditAction.NOTIFICATION_BLOCKED_SUBSCRIPTION_INACTIVE,
                    client_id=client_id,
                    metadata={"template_key": template_key},
                )
                return NotificationResult(outcome="blocked", block_reason="BLOCKED_SUBSCRIPTION_INACTIVE")

        plan_feature = template.get("plan_required_feature_key")
        if plan_feature:
            from services.plan_registry import plan_registry
            allowed, msg, details = await plan_registry.enforce_feature(client_id, plan_feature)
            if not allowed:
                await self._write_blocked_log(
                    db, client_id, template_key, channel, "BLOCKED_PLAN_GATE", msg, None, context, None,
                )
                await create_audit_log(
                    action=AuditAction.PLAN_GATE_DENIED,
                    client_id=client_id,
                    metadata={"template_key": template_key, "feature_key": plan_feature, "reason": msg, **(details or {})},
                )
                return NotificationResult(
                    outcome="blocked",
                    block_reason="BLOCKED_PLAN_GATE",
                    status_code=403,
                    details={"error_code": "PLAN_GATE_DENIED", "message": msg or "Feature not available on plan"},
                )
        # Quiet-hours gate for non-critical notifications.
        prefs = client.get("notification_preferences") or {}
        category = template.get("email_category")
        if channel in ("EMAIL", "SMS") and category not in ("system_critical", "internal"):
            if self._is_in_quiet_hours(prefs):
                await self._write_blocked_log(
                    db, client_id, template_key, channel, "BLOCKED_QUIET_HOURS", None, None, context, event_type,
                )
                return NotificationResult(
                    outcome="blocked",
                    block_reason="BLOCKED_QUIET_HOURS",
                )
        return None

    def _resolve_recipient(self, client: Dict, channel: str) -> Optional[str]:
        if channel == "EMAIL":
            email = (client.get("contact_email") or client.get("email") or "").strip()
            return email or None
        if channel == "SMS":
            prefs = client.get("notification_preferences") or {}
            if not prefs.get("sms_enabled"):
                return None
            if not prefs.get("sms_phone_verified"):
                return None
            phone = (prefs.get("sms_phone_number") or client.get("sms_phone_number") or "").strip()
            return phone or None
        return None

    def _is_in_quiet_hours(self, prefs: Dict[str, Any]) -> bool:
        """True if current UTC time falls in configured quiet hours window."""
        if not prefs or not prefs.get("quiet_hours_enabled"):
            return False
        try:
            start_str = (prefs.get("quiet_hours_start") or "22:00").strip()
            end_str = (prefs.get("quiet_hours_end") or "08:00").strip()
            sh, sm = start_str.split(":")
            eh, em = end_str.split(":")
            start_min = int(sh) * 60 + int(sm)
            end_min = int(eh) * 60 + int(em)
            now = datetime.now(timezone.utc)
            now_min = now.hour * 60 + now.minute
            if start_min > end_min:
                return now_min >= start_min or now_min < end_min
            return start_min <= now_min < end_min
        except Exception:
            return False

    async def _write_blocked_log(
        self,
        db,
        client_id: str,
        template_key: str,
        channel: str,
        block_reason: str,
        error_message: Optional[str],
        idempotency_key: Optional[str],
        context: Dict,
        event_type: Optional[str],
    ) -> None:
        now = datetime.now(timezone.utc)
        ik = _normalized_idempotency_key(idempotency_key)
        doc = {
            "message_id": str(uuid.uuid4()),
            "client_id": client_id,
            "recipient": None,
            "template_key": template_key,
            "channel": channel,
            "status": block_reason,
            "attempt_count": 1,
            "error_message": error_message,
            "metadata": {"event_type": event_type, "block_reason": block_reason},
            "created_at": now,
        }
        if ik:
            doc["idempotency_key"] = ik
        try:
            await db.message_logs.insert_one(doc)
        except Exception as e:
            if "duplicate key" in str(e).lower() or "E11000" in str(e):
                pass
            else:
                logger.warning(f"Failed to write blocked log: {e}")

    async def _check_sms_throttle(self, db, client_id: str, template_key: str) -> bool:
        since = datetime.now(timezone.utc) - timedelta(hours=24)
        n = await db.message_logs.count_documents({
            "client_id": client_id,
            "template_key": template_key,
            "channel": "SMS",
            "status": "SENT",
            "created_at": {"$gte": since},
        })
        return n == 0

    async def _send_email(
        self,
        template_key: str,
        template: Dict,
        client: Dict,
        context: Dict,
        message_id: str,
        db,
        now: datetime,
        recipient: str,
    ) -> NotificationResult:
        if not self._postmark_client:
            err_msg = "POSTMARK_SERVER_TOKEN not set"
            await db.message_logs.update_one(
                {"message_id": message_id},
                {"$set": {"status": "FAILED", "error_message": err_msg}},
            )
            await create_audit_log(
                action=AuditAction.NOTIFICATION_PROVIDER_NOT_CONFIGURED,
                client_id=client.get("client_id"),
                metadata={"template_key": template_key, "channel": "EMAIL"},
            )
            return NotificationResult(outcome="blocked", block_reason="BLOCKED_PROVIDER_NOT_CONFIGURED")

        alias_str = template.get("email_template_alias") or "password-setup"
        subject = (context.get("subject") or "Compliance Vault Pro").strip()
        render_ctx = {k: v for k, v in (context or {}).items() if k != "attachments"}
        try:
            html_body, text_body, email_subject = await self._render_email(
                db, alias_str, render_ctx, subject, client.get("client_id")
            )
        except Exception as e:
            logger.exception(f"Render email failed: {e}")
            await db.message_logs.update_one(
                {"message_id": message_id},
                {"$set": {"status": "FAILED", "error_message": str(e)[:500], "attempt_count": 1}},
            )
            return NotificationResult(outcome="failed", error_message=str(e), message_id=message_id)

        try:
            extras = (render_ctx or {}).get("_email_send_extras") or {}
            if not isinstance(extras, dict):
                extras = {}
            reply_override = (extras.get("reply_to") or "").strip() or None
            from_name = (extras.get("from_display_name") or "").strip() or None
            from_addr = DEFAULT_SENDER
            if from_name:
                safe_name = from_name.replace("\\", "\\\\").replace('"', '\\"')
                from_addr = f'"{safe_name}" <{DEFAULT_SENDER}>'
            send_kw = dict(
                From=from_addr,
                To=recipient,
                Subject=email_subject,
                HtmlBody=html_body,
                TextBody=text_body,
                TrackOpens=True,
                TrackLinks="HtmlOnly",
                Tag=template_key,
                MessageStream=POSTMARK_MESSAGE_STREAM,
            )
            if reply_override:
                send_kw["ReplyTo"] = reply_override
            elif EMAIL_REPLY_TO:
                send_kw["ReplyTo"] = EMAIL_REPLY_TO
            attachments = (context or {}).get("attachments")
            if attachments and isinstance(attachments, list):
                send_kw["Attachments"] = [
                    {"Name": a.get("Name", "file"), "Content": a.get("Content"), "ContentType": a.get("ContentType", "application/octet-stream")}
                    for a in attachments if a.get("Content")
                ]
            from services.postmark_delivery import deliver_postmark_email

            response, err_msg, attempts_used = await deliver_postmark_email(
                self._postmark_client,
                send_kw,
                template_name=template_key,
                recipient=recipient,
                message_id=message_id,
                client_id=client.get("client_id"),
                db=db,
            )
            if response:
                provider_id = response.get("MessageID")
                sent_at = datetime.now(timezone.utc)
                await db.message_logs.update_one(
                    {"message_id": message_id},
                    {
                        "$set": {
                            "status": "SENT",
                            "provider_message_id": provider_id,
                            "postmark_message_id": provider_id,
                            "sent_at": sent_at,
                            "subject": email_subject,
                            "attempt_count": attempts_used,
                        }
                    },
                )
                await create_audit_log(
                    action=AuditAction.EMAIL_SENT,
                    client_id=client.get("client_id"),
                    metadata={"template_key": template_key, "message_id": message_id, "postmark_id": provider_id},
                )
                return NotificationResult(outcome="sent", message_id=message_id, details={"provider_message_id": provider_id})

            await db.message_logs.update_one(
                {"message_id": message_id},
                {
                    "$set": {
                        "status": "FAILED",
                        "error_message": err_msg or "send failed",
                        "attempt_count": attempts_used,
                    }
                },
            )
            return NotificationResult(
                outcome="failed",
                message_id=message_id,
                error_message=err_msg,
                details={
                    "transient": False,
                    "attempt_count": attempts_used,
                    "postmark_inline_exhausted": True,
                },
            )
        except Exception as e:
            logger.exception("Postmark delivery unexpected error: %s", e)
            err_msg = str(e)[:500]
            await db.message_logs.update_one(
                {"message_id": message_id},
                {"$set": {"status": "FAILED", "error_message": err_msg, "attempt_count": 1}},
            )
            return NotificationResult(
                outcome="failed",
                message_id=message_id,
                error_message=err_msg,
                details={"transient": _is_transient_error(e), "attempt_count": 1},
            )

    async def _render_email(
        self,
        db,
        alias_str: str,
        context: Dict,
        default_subject: str,
        client_id: Optional[str] = None,
    ) -> Tuple[str, str, str]:
        from models import EmailTemplateAlias
        from services.branding_resolver_service import merge_email_branding_context

        if context is None:
            context = {}
        await merge_email_branding_context(context, alias_str, client_id)
        alias_map = {a.value: a for a in EmailTemplateAlias}
        alias = alias_map.get(alias_str)
        # scheduled-report: always use code-built layout (job path has report_rows; manual path passes pre-built message).
        # This avoids stale DB email_templates overriding the canonical layout.
        if alias_str == "scheduled-report":
            # Pre-rendered HTML (e.g. manual report with attachment) bypasses EmailService.
            if context.get("message"):
                html = str(context["message"])
                text = (context.get("text_message") or "").strip() or _strip_html_to_text(html)
                subj = (context.get("subject") or default_subject)
                return html, text, subj
            # Job-driven digest: structured summary and/or requirement rows — never raw CSV in body.
            if context.get("report_rows") is not None or context.get("report_summary") is not None:
                from services.email_service import EmailService

                svc = EmailService()
                model = context or {}
                html = svc._build_html_body(EmailTemplateAlias.SCHEDULED_REPORT, model)
                text = svc._build_text_body(EmailTemplateAlias.SCHEDULED_REPORT, model)
                subj = (context.get("subject") or default_subject)
                return html, text, subj
        if alias_str == "order-intake-confirmation" and context.get("message"):
            html = str(context["message"])
            text = (context.get("text_message") or "").strip() or _strip_html_to_text(html)
            subj = (context.get("subject") or default_subject)
            return html, text, subj
        # admin-manual: when message is already a full HTML document, skip DB merge — otherwise
        # {{message}} is embedded in a second shell (e.g. LEAD_FOLLOWUP markdown_to_html + admin-manual row).
        if alias_str == "admin-manual" and _context_message_is_full_html_document(context):
            msg = str(context.get("message") or "").strip()
            html = msg
            text = (context.get("text_message") or "").strip() or _strip_html_to_text(html)
            subj = (context.get("subject") or default_subject).strip()
            return html, text, subj
        # Subscription payment receipt: always use code-built layout (structured context from Stripe webhook).
        if alias_str == "payment-receipt" and context.get("payment_receipt_layout") == "structured":
            from services.email_service import EmailService
            from models import EmailTemplateAlias

            svc = EmailService()
            model = context or {}
            html = svc._build_html_body(EmailTemplateAlias.PAYMENT_RECEIPT, model)
            text = svc._build_text_body(EmailTemplateAlias.PAYMENT_RECEIPT, model)
            subj = (context.get("subject") or default_subject).strip()
            return html, text, subj
        # Activation reminder uses canonical customer layout (not stale DB overrides).
        if alias_str == "activation-reminder":
            from services.email_service import EmailService
            from models import EmailTemplateAlias

            svc = EmailService()
            model = context or {}
            html = svc._build_html_body(EmailTemplateAlias.ACTIVATION_REMINDER, model)
            text = svc._build_text_body(EmailTemplateAlias.ACTIVATION_REMINDER, model)
            subj = (context.get("subject") or default_subject).strip()
            return html, text, subj
        # Post-password dashboard milestone (avoid stale DB portal-ready overriding copy).
        if alias_str == "portal-ready" and context.get("dashboard_milestone_email"):
            from services.email_service import EmailService
            from models import EmailTemplateAlias

            svc = EmailService()
            model = context or {}
            html = svc._build_html_body(EmailTemplateAlias.PORTAL_READY, model)
            text = svc._build_text_body(EmailTemplateAlias.PORTAL_READY, model)
            subj = (context.get("subject") or default_subject).strip()
            return html, text, subj
        if alias_str == "client-operational-notice":
            from services.email_service import EmailService
            from models import EmailTemplateAlias

            svc = EmailService()
            model = context or {}
            html = svc._build_html_body(EmailTemplateAlias.CLIENT_OPERATIONAL_NOTICE, model)
            text = svc._build_text_body(EmailTemplateAlias.CLIENT_OPERATIONAL_NOTICE, model)
            subj = (context.get("subject") or default_subject).strip()
            return html, text, subj
        if alias_str == "client-quote-review-required":
            from services.email_service import EmailService
            from models import EmailTemplateAlias

            svc = EmailService()
            model = context or {}
            html = svc._build_html_body(EmailTemplateAlias.CLIENT_QUOTE_REVIEW_REQUIRED, model)
            text = svc._build_text_body(EmailTemplateAlias.CLIENT_QUOTE_REVIEW_REQUIRED, model)
            subj = (context.get("subject") or default_subject).strip()
            return html, text, subj
        if alias_str == "client-proof-uploaded":
            from services.email_service import EmailService
            from models import EmailTemplateAlias

            svc = EmailService()
            model = context or {}
            html = svc._build_html_body(EmailTemplateAlias.CLIENT_PROOF_UPLOADED, model)
            text = svc._build_text_body(EmailTemplateAlias.CLIENT_PROOF_UPLOADED, model)
            subj = (context.get("subject") or default_subject).strip()
            return html, text, subj
        if alias_str == "client-invoice-review-required":
            from services.email_service import EmailService
            from models import EmailTemplateAlias

            svc = EmailService()
            model = context or {}
            html = svc._build_html_body(EmailTemplateAlias.CLIENT_INVOICE_REVIEW_REQUIRED, model)
            text = svc._build_text_body(EmailTemplateAlias.CLIENT_INVOICE_REVIEW_REQUIRED, model)
            subj = (context.get("subject") or default_subject).strip()
            return html, text, subj
        if alias_str == "contractor-job-assignment-quote-required":
            from services.email_service import EmailService
            from models import EmailTemplateAlias

            svc = EmailService()
            model = context or {}
            html = svc._build_html_body(EmailTemplateAlias.CONTRACTOR_JOB_ASSIGNMENT_QUOTE_REQUIRED, model)
            text = svc._build_text_body(EmailTemplateAlias.CONTRACTOR_JOB_ASSIGNMENT_QUOTE_REQUIRED, model)
            subj = (context.get("subject") or default_subject).strip()
            return html, text, subj
        if alias_str == "contractor-quote-approved":
            from services.email_service import EmailService
            from models import EmailTemplateAlias

            svc = EmailService()
            model = context or {}
            html = svc._build_html_body(EmailTemplateAlias.CONTRACTOR_QUOTE_APPROVED, model)
            text = svc._build_text_body(EmailTemplateAlias.CONTRACTOR_QUOTE_APPROVED, model)
            subj = (context.get("subject") or default_subject).strip()
            return html, text, subj
        if alias_str == "contractor-visit-confirmed":
            from services.email_service import EmailService
            from models import EmailTemplateAlias

            svc = EmailService()
            model = context or {}
            html = svc._build_html_body(EmailTemplateAlias.CONTRACTOR_VISIT_CONFIRMED, model)
            text = svc._build_text_body(EmailTemplateAlias.CONTRACTOR_VISIT_CONFIRMED, model)
            subj = (context.get("subject") or default_subject).strip()
            return html, text, subj
        if alias_str == "contractor-proof-required":
            from services.email_service import EmailService
            from models import EmailTemplateAlias

            svc = EmailService()
            model = context or {}
            html = svc._build_html_body(EmailTemplateAlias.CONTRACTOR_PROOF_REQUIRED, model)
            text = svc._build_text_body(EmailTemplateAlias.CONTRACTOR_PROOF_REQUIRED, model)
            subj = (context.get("subject") or default_subject).strip()
            return html, text, subj
        if alias_str == "contractor-invoice-ready":
            from services.email_service import EmailService
            from models import EmailTemplateAlias

            svc = EmailService()
            model = context or {}
            html = svc._build_html_body(EmailTemplateAlias.CONTRACTOR_INVOICE_READY, model)
            text = svc._build_text_body(EmailTemplateAlias.CONTRACTOR_INVOICE_READY, model)
            subj = (context.get("subject") or default_subject).strip()
            return html, text, subj
        # Monthly digest: always code-built (action email + PDF); avoids DB template placeholder leakage.
        if alias_str == "monthly-digest":
            from services.email_service import EmailService
            from models import EmailTemplateAlias

            svc = EmailService()
            model = context or {}
            html = svc._build_html_body(EmailTemplateAlias.MONTHLY_DIGEST, model)
            text = svc._build_text_body(EmailTemplateAlias.MONTHLY_DIGEST, model)
            subj = (context.get("subject") or default_subject).strip()
            for k, v in (context or {}).items():
                if str(k).startswith("_") or isinstance(v, (dict, list, set)):
                    continue
                placeholder = "{{" + str(k) + "}}"
                subj = subj.replace(placeholder, str(v))
            return html, text, subj
        from services.lifecycle_reminder_template_registry import is_lifecycle_reminder_email_alias

        if is_lifecycle_reminder_email_alias(alias_str):
            from services.email_service import EmailService

            svc = EmailService()
            model = context or {}
            html = svc._build_html_body(alias, model)
            text = svc._build_text_body(alias, model)
            subj = (context.get("subject") or default_subject).strip()
            return html, text, subj
        db_template = await db.email_templates.find_one({"alias": alias_str, "is_active": True}, {"_id": 0})
        if db_template:
            from services.branding_resolver_service import finalize_db_email_html

            html = db_template.get("html_body", "")
            text = db_template.get("text_body", "")
            subj = db_template.get("subject", default_subject)
            for k, v in (context or {}).items():
                if str(k).startswith("_") or isinstance(v, (dict, list, set)):
                    continue
                placeholder = "{{" + str(k) + "}}"
                vs = str(v)
                html = html.replace(placeholder, vs)
                text = text.replace(placeholder, vs)
                subj = subj.replace(placeholder, vs)
            html, text = finalize_db_email_html(html, text, context, alias_str, client_id)
            return html, text, subj
        # Fallback built-in
        from services.email_service import EmailService
        svc = EmailService()
        if alias is None:
            alias = EmailTemplateAlias.PASSWORD_SETUP
        model = context or {}
        html = svc._build_html_body(alias, model)
        text = svc._build_text_body(alias, model)
        subj = default_subject
        for k, v in (context or {}).items():
            placeholder = "{{" + str(k) + "}}"
            subj = subj.replace(placeholder, str(v))
        return html, text, subj

    async def _send_sms(
        self,
        template_key: str,
        template: Dict,
        client: Dict,
        context: Dict,
        message_id: str,
        db,
        now: datetime,
        recipient: str,
    ) -> NotificationResult:
        if not self._twilio_client or os.getenv("SMS_ENABLED", "").lower() != "true":
            await db.message_logs.update_one(
                {"message_id": message_id},
                {"$set": {"status": "BLOCKED_PROVIDER_NOT_CONFIGURED", "error_message": "SMS not configured"}},
            )
            await create_audit_log(
                action=AuditAction.NOTIFICATION_PROVIDER_NOT_CONFIGURED,
                client_id=client.get("client_id"),
                metadata={"template_key": template_key, "channel": "SMS"},
            )
            return NotificationResult(outcome="blocked", block_reason="BLOCKED_PROVIDER_NOT_CONFIGURED")

        messaging_service_sid = os.getenv("TWILIO_MESSAGING_SERVICE_SID", "").strip()
        from_number = os.getenv("TWILIO_PHONE_NUMBER", "").strip() if not messaging_service_sid else None
        if not messaging_service_sid and not from_number:
            await db.message_logs.update_one(
                {"message_id": message_id},
                {"$set": {"status": "BLOCKED_PROVIDER_NOT_CONFIGURED", "error_message": "TWILIO_PHONE_NUMBER or TWILIO_MESSAGING_SERVICE_SID not set"}},
            )
            await create_audit_log(
                action=AuditAction.NOTIFICATION_PROVIDER_NOT_CONFIGURED,
                client_id=client.get("client_id"),
                metadata={"template_key": template_key, "channel": "SMS"},
            )
            return NotificationResult(outcome="blocked", block_reason="BLOCKED_PROVIDER_NOT_CONFIGURED")

        body = (template.get("sms_body") or context.get("sms_body") or context.get("body") or "Notification").strip()
        for k, v in (context or {}).items():
            body = body.replace("{{" + str(k) + "}}", str(v))
        if not recipient.startswith("+"):
            recipient = "+" + recipient

        try:
            from twilio.rest import Client
            if messaging_service_sid:
                msg = self._twilio_client.messages.create(body=body[:1600], messaging_service_sid=messaging_service_sid, to=recipient)
            else:
                msg = self._twilio_client.messages.create(body=body[:1600], from_=from_number, to=recipient)
            provider_id = msg.sid
            sent_at = datetime.now(timezone.utc)
            await db.message_logs.update_one(
                {"message_id": message_id},
                {"$set": {"status": "SENT", "provider_message_id": provider_id, "sent_at": sent_at}},
            )
            await create_audit_log(
                action=AuditAction.EMAIL_SENT,  # reuse; or add SMS_SENT if desired
                client_id=client.get("client_id"),
                metadata={"template_key": template_key, "message_id": message_id, "twilio_sid": provider_id},
            )
            return NotificationResult(outcome="sent", message_id=message_id, details={"provider_message_id": provider_id})
        except Exception as e:
            transient = _is_transient_error(e)
            err_msg = str(e)[:500]
            await db.message_logs.update_one(
                {"message_id": message_id},
                {"$set": {"status": "FAILED", "error_message": err_msg, "attempt_count": 1}},
            )
            return NotificationResult(
                outcome="failed",
                message_id=message_id,
                error_message=err_msg,
                details={"transient": transient, "attempt_count": 1},
            )


    async def process_retry(self, message_id: str) -> NotificationResult:
        """Process one message from the retry queue (called by retry worker)."""
        db = database.get_db()
        log = await db.message_logs.find_one({"message_id": message_id}, {"_id": 0})
        if not log:
            return NotificationResult(outcome="failed", error_message="message_log not found")
        client_id = log.get("client_id")
        template_key = log.get("template_key")
        channel = log.get("channel", "EMAIL")
        attempt = log.get("attempt_count", 1)
        recipient = log.get("recipient")
        metadata = log.get("metadata") or {}
        context = {k: v for k, v in metadata.items() if k not in ("event_type", "block_reason")}

        throttle_result = await self._check_global_throttle(db, channel, message_id, client_id, template_key)
        if throttle_result:
            return throttle_result

        template = await db.notification_templates.find_one(
            {"template_key": template_key, "is_active": True},
            {"_id": 0},
        )
        if not template:
            return NotificationResult(outcome="failed", error_message="template not found")
        if not recipient:
            return NotificationResult(outcome="failed", error_message="recipient missing")
        if client_id is None:
            client = {"client_id": None, "email": None, "contact_email": None, "full_name": None, "contact_name": None}
        else:
            client = await db.clients.find_one(
                {"client_id": client_id},
                {"_id": 0, "client_id": 1, "email": 1, "contact_email": 1, "full_name": 1, "contact_name": 1},
            )
            if not client:
                return NotificationResult(outcome="failed", error_message="client not found")

        max_attempts = MAX_SMS_ATTEMPTS if channel == "SMS" else MAX_EMAIL_ATTEMPTS
        backoffs = SMS_BACKOFFS if channel == "SMS" else EMAIL_BACKOFFS
        now = datetime.now(timezone.utc)

        if channel == "EMAIL":
            result = await self._send_email(
                template_key, template, client, context, message_id, db, now, recipient,
            )
        else:
            result = await self._send_sms(
                template_key, template, client, context, message_id, db, now, recipient,
            )

        await db.notification_retry_queue.delete_many({"message_id": message_id})

        if result.outcome == "sent":
            await _operational_evidence_notification_result(message_id, client_id, channel, template_key, result)
            return result
        if result.outcome == "failed":
            new_attempt = attempt + 1
            await db.message_logs.update_one(
                {"message_id": message_id},
                {"$set": {"status": "FAILED", "attempt_count": new_attempt, "error_message": result.error_message}},
            )
            if (
                result.details.get("transient")
                and not result.details.get("postmark_inline_exhausted")
                and new_attempt <= max_attempts
                and new_attempt <= len(backoffs)
            ):
                next_run = now + timedelta(seconds=backoffs[new_attempt - 1])
                await db.notification_retry_queue.insert_one({
                    "message_id": message_id,
                    "template_key": template_key,
                    "client_id": client_id,
                    "channel": channel,
                    "attempt_count": new_attempt,
                    "next_run_at": next_run,
                    "status": "PENDING",
                    "created_at": now,
                })
            else:
                await create_audit_log(
                    action=AuditAction.NOTIFICATION_FAILED_PERMANENT,
                    client_id=client_id,
                    metadata={"message_id": message_id, "template_key": template_key, "channel": channel},
                )
        await _operational_evidence_notification_result(message_id, client_id, channel, template_key, result)
        return result


notification_orchestrator = NotificationOrchestrator()
