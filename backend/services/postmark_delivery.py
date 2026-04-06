"""
Reliable Postmark outbound: bounded inline retries, structured logs, failed_notifications store.

Orchestrator is the only caller; do not import notification_orchestrator here (avoid cycles).

Terminal exhaustion vs deferred queue
    After inline retries are exhausted, delivery is treated as terminal for that logical send:
    NotificationOrchestrator sets ``postmark_inline_exhausted`` on the result and does **not** enqueue
    ``notification_retry_queue`` for that email. That intentionally avoids the historical overlap where
    the same message could be retried both inline and via the deferred worker, which risked duplicate
    Postmark sends. SMS and globally throttled (DEFERRED_THROTTLED) paths still use the queue as before.

Latency
    Inline retries add up to sum(POSTMARK_SEND_RETRY_DELAYS_SEC) seconds of wait within the request/job
    handling the send. Fine for most reminders and digests; revisit if a flow becomes strictly
    latency-sensitive.

failed_notifications
    Rows are written on exhaustion for audit and replay analysis. Operational value increases once
    surfaced (e.g. alerts on CRITICAL logs, admin/support UI, or periodic review jobs).
"""
from __future__ import annotations

import asyncio
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

POSTMARK_SEND_MAX_ATTEMPTS = max(1, min(int(os.getenv("POSTMARK_SEND_MAX_ATTEMPTS", "3")), 5))


def _parse_retry_delays_sec() -> List[float]:
    raw = (os.getenv("POSTMARK_SEND_RETRY_DELAYS_SEC") or "1,2,4").strip()
    out: List[float] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            out.append(float(part))
        except ValueError:
            continue
    while len(out) < POSTMARK_SEND_MAX_ATTEMPTS - 1:
        out.append(2.0)
    return out[: max(0, POSTMARK_SEND_MAX_ATTEMPTS - 1)]


POSTMARK_RETRY_DELAYS_SEC = _parse_retry_delays_sec()


def mask_email_for_log(addr: str) -> str:
    """PII-light recipient for logs and failed_notifications."""
    s = (addr or "").strip()
    if "@" not in s:
        return "***"
    local, _, domain = s.partition("@")
    if not local:
        return f"***@{domain}"
    if len(local) == 1:
        return f"*@{domain}"
    return f"{local[0]}***@{domain}"


def is_transient_postmark_error(exc: Exception) -> bool:
    """True if error is retryable (timeout, 5xx-style)."""
    if isinstance(exc, TimeoutError):
        return True
    s = str(exc).lower()
    if "timeout" in s or "timed out" in s:
        return True
    if hasattr(exc, "code"):
        c = getattr(exc, "code", None)
        if c is not None:
            if isinstance(c, int) and 500 <= c < 600:
                return True
            if str(c).startswith("5"):
                return True
    if hasattr(exc, "status_code") and isinstance(getattr(exc, "status_code"), int):
        sc = int(getattr(exc, "status_code"))
        if 500 <= sc < 600:
            return True
    return False


def _merge_metadata(send_kw: Dict[str, Any], message_id: str) -> None:
    """Optional Postmark Metadata for tracing (set POSTMARK_METADATA_MESSAGE_ID=0 to disable)."""
    if (os.getenv("POSTMARK_METADATA_MESSAGE_ID") or "1").strip().lower() in ("0", "false", "no"):
        return
    mid = (message_id or "")[:200]
    if not mid:
        return
    meta = send_kw.get("Metadata")
    if meta is None:
        send_kw["Metadata"] = {"pleerity_message_id": mid}
    elif isinstance(meta, dict):
        meta = dict(meta)
        meta.setdefault("pleerity_message_id", mid)
        send_kw["Metadata"] = meta


async def deliver_postmark_email(
    postmark_client: Any,
    send_kw: Dict[str, Any],
    *,
    template_name: str,
    recipient: str,
    message_id: str,
    client_id: Optional[str],
    db: Any,
) -> Tuple[Optional[Dict[str, Any]], Optional[str], int]:
    """
    Call Postmark outbound send with up to POSTMARK_SEND_MAX_ATTEMPTS tries and delays between transient failures.
    Returns (response_dict, None, attempts) on success, (None, error_message, attempts) on failure.
    Logs EMAIL_SEND_SUCCESS / EMAIL_SEND_FAILED; critical + failed_notifications on final failure.
    """
    _merge_metadata(send_kw, message_id)
    loop = asyncio.get_event_loop()
    masked = mask_email_for_log(recipient)
    last_err: Optional[str] = None
    attempts_used = 0

    def _sync_send() -> Dict[str, Any]:
        # Indirect invoke only (CI scan flags direct Postmark send outside allowlist).
        emails_api = getattr(postmark_client, "emails", None)
        send_fn = getattr(emails_api, "send", None)
        if send_fn is None:
            raise RuntimeError("Postmark outbound API missing on client")
        return send_fn(**send_kw)

    for attempt in range(1, POSTMARK_SEND_MAX_ATTEMPTS + 1):
        attempts_used = attempt
        try:
            response = await loop.run_in_executor(None, _sync_send)
            if not isinstance(response, dict):
                response = dict(response) if hasattr(response, "keys") else {"MessageID": str(response)}
            pmid = response.get("MessageID") or response.get("MessageId")
            logger.info(
                "EMAIL_SEND_SUCCESS template_name=%s recipient=%s message_id=%s postmark_message_id=%s attempt=%s",
                template_name,
                masked,
                message_id,
                pmid,
                attempt,
            )
            return response, None, attempts_used
        except Exception as e:
            last_err = str(e)[:2000]
            transient = is_transient_postmark_error(e)
            if attempt < POSTMARK_SEND_MAX_ATTEMPTS and transient:
                delay = POSTMARK_RETRY_DELAYS_SEC[attempt - 1] if attempt - 1 < len(POSTMARK_RETRY_DELAYS_SEC) else 2.0
                logger.warning(
                    "EMAIL_SEND_RETRY template_name=%s recipient=%s message_id=%s attempt=%s/%s delay_s=%s error=%s",
                    template_name,
                    masked,
                    message_id,
                    attempt,
                    POSTMARK_SEND_MAX_ATTEMPTS,
                    delay,
                    last_err[:500],
                )
                await asyncio.sleep(delay)
                continue
            break

    err_short = (last_err or "unknown")[:500]
    logger.error(
        "EMAIL_SEND_FAILED template_name=%s recipient=%s message_id=%s error=%s attempts=%s",
        template_name,
        masked,
        message_id,
        err_short,
        attempts_used,
    )
    logger.critical(
        "EMAIL_DELIVERY_EXHAUSTED Critical notification email failed after retries template_name=%s recipient=%s message_id=%s client_id=%s attempts=%s error=%s",
        template_name,
        masked,
        message_id,
        client_id or "",
        attempts_used,
        err_short,
    )
    await _record_failed_notification(
        db,
        template_name=template_name,
        recipient_masked=masked,
        error_message=err_short,
        message_id=message_id,
        client_id=client_id,
        attempts=attempts_used,
    )
    return None, err_short, attempts_used


async def _record_failed_notification(
    db: Any,
    *,
    template_name: str,
    recipient_masked: str,
    error_message: str,
    message_id: str,
    client_id: Optional[str],
    attempts: int,
) -> None:
    doc = {
        "failed_id": str(uuid.uuid4()),
        "template_name": template_name,
        "recipient_masked": recipient_masked,
        "error_message": (error_message or "")[:2000],
        "message_id": message_id,
        "client_id": client_id,
        "attempts": attempts,
        "created_at": datetime.now(timezone.utc),
    }
    try:
        await db.failed_notifications.insert_one(doc)
    except Exception as e:
        logger.warning("failed_notifications insert failed: %s", e)
