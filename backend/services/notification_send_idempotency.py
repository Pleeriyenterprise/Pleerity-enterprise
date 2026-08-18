"""
Stable idempotency helpers for high-volume notification sends (L-008).

See ``docs/audit/NOTIFICATION_OWNERSHIP_READINESS.md`` — daily reminders must not
suppress a materially different batch solely because the calendar day and recipient match;
``COMPLIANCE_ALERT`` batches must not collide when many property IDs exceed legacy join truncation.
"""
from __future__ import annotations

import hashlib
from typing import Any, Dict, Iterable, List, Optional


def daily_compliance_reminder_item_idempotency_key(
    *,
    client_id: str,
    template_key: str,
    date_key: str,
    recipient_suffix: str,
    requirement_id: str,
    property_id: str,
    due_date: str,
    lifecycle_window: str,
) -> str:
    """
    Per-requirement daily reminder idempotency (one email = one requirement = one window).

    Identity is stable requirement/property/due-date/window — never display names.
    ``date_key`` is the governed send calendar day; ``due_date`` is the requirement's
    effective due/expiry date (YYYY-MM-DD). ``lifecycle_window`` is ``overdue`` or ``upcoming``.
    """
    rid = str(requirement_id or "").strip() or "NOREQ"
    pid = str(property_id or "").strip() or "NOPROP"
    due = str(due_date or "").strip() or "NODATE"
    window = str(lifecycle_window or "").strip().lower() or "unknown"
    blob = f"{rid}|{pid}|{due}|{window}"
    fp = hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]
    cid = str(client_id or "").strip() or "NOCLIENT"
    tk = str(template_key or "").strip() or "COMPLIANCE_EXPIRY_REMINDER"
    dk = str(date_key or "").strip() or "NODAY"
    rs = str(recipient_suffix or "").strip() or "client"
    return f"{cid}_{tk}_{dk}_{rs}_{fp}"


def daily_compliance_reminder_scope_fingerprint(
    *,
    reminder_refs: Optional[List[Dict[str, Any]]],
) -> str:
    """
    Short deterministic fingerprint for one reminder batch (same day, same recipient).

    Uses ``reminder_refs`` from ``services.jobs`` (requirement_id + due_date + property_id).
    When refs are missing, falls back to a low-cardinality placeholder (legacy callers).
    """
    if not reminder_refs:
        return "NOREFS"
    parts: List[str] = []
    for raw in reminder_refs:
        if not isinstance(raw, dict):
            continue
        rid = str(raw.get("requirement_id") or "").strip()
        due = str(raw.get("due_date") or "").strip()
        pid = str(raw.get("property_id") or "").strip()
        if not (rid or due or pid):
            continue
        parts.append(f"{rid}|{due}|{pid}")
    if not parts:
        return "EMPTYREFS"
    parts.sort()
    blob = ";".join(parts)[:8000]
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def compliance_alert_property_scope_fingerprint(property_ids: Iterable[str]) -> str:
    """
    Deterministic idempotency fragment for ``COMPLIANCE_ALERT`` (degraded-property batch per client/day).

    Legacy keys used ``"_".join(sorted(property_ids))[:32]``, which could treat two different large
    portfolios as identical. For joins longer than 32 characters, this returns a full SHA-256 hex
    digest of the sorted join so distinct batches do not collide.

    When the sorted join is **32 characters or fewer**, returns that string unchanged (same as the
    legacy truncation for those inputs).
    """
    joined = "_".join(sorted(str(p or "").strip() for p in property_ids))
    if len(joined) <= 32:
        return joined
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()
