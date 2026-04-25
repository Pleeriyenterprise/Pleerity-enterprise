from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from utils.expiry_utils import get_effective_expiry_date, is_included_for_calendar
from services.requirement_evidence_authority import authority_runtime_requirement_status

COLLECTION_REMINDER_ITEM_STATE = "reminder_item_state"
COLLECTION_REMINDER_EVALUATION_LOG = "reminder_evaluation_log"

REASON_ITEM_NOT_FOUND = "ITEM_NOT_FOUND"
REASON_NOT_RELEVANT = "NOT_RELEVANT"
REASON_NO_EFFECTIVE_DATE = "NO_EFFECTIVE_DATE"
REASON_ALREADY_RESOLVED = "ALREADY_RESOLVED"
REASON_NO_LONGER_DUE = "NO_LONGER_DUE"
REASON_COOLDOWN_ACTIVE = "COOLDOWN_ACTIVE"
REASON_ZERO_PENDING_ITEMS = "ZERO_PENDING_ITEMS"

DEFAULT_REMINDER_COOLDOWN_HOURS_BY_TYPE = {
    "DAILY_COMPLIANCE_EXPIRY_EMAIL": 24,
    "DAILY_COMPLIANCE_EXPIRY_SMS": 24,
    "PENDING_VERIFICATION_DIGEST": 24,
}

_SEVERITY_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}


def _gap_engine_context_for_reminder(requirement: Dict[str, Any]) -> Dict[str, Any]:
    """Attach governed gap classification (same engine as vault / Command Centre)."""
    try:
        from services.compliance_gap_engine import infer_compliance_gaps_for_requirement

        gaps = infer_compliance_gaps_for_requirement(requirement, property_doc=None)
    except Exception:
        return {"gaps": [], "gap_kinds": [], "max_severity": None}
    best = -1
    max_sev: Optional[str] = None
    for g in gaps:
        o = _SEVERITY_ORDER.get((g.severity or "").upper(), -1)
        if o >= best:
            best = o
            max_sev = g.severity
    return {
        "gap_kinds": [g.gap_kind for g in gaps],
        "max_severity": max_sev,
        "gaps": [{"gap_kind": g.gap_kind, "severity": g.severity, "title": g.title} for g in gaps],
    }


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def _requirement_state_key(requirement: Dict[str, Any], reminder_type: str) -> Dict[str, str]:
    req_type = (
        requirement.get("requirement_code")
        or requirement.get("requirement_type")
        or requirement.get("code")
        or ""
    )
    return {
        "client_id": requirement.get("client_id") or "",
        "property_id": requirement.get("property_id") or "",
        "requirement_code": str(req_type).upper(),
        "target_ref": requirement.get("requirement_id") or "",
        "reminder_type": reminder_type,
    }


def get_reminder_cooldown_hours(reminder_type: str, fallback_hours: Optional[int] = None) -> int:
    """
    Resolve cooldown from env by reminder type.
    Env key convention:
      REMINDER_COOLDOWN_HOURS_<REMINDER_TYPE>
    Example:
      REMINDER_COOLDOWN_HOURS_DAILY_COMPLIANCE_EXPIRY_EMAIL=48
    """
    normalized = str(reminder_type or "").upper().strip()
    default_hours = int(
        fallback_hours
        if fallback_hours is not None
        else DEFAULT_REMINDER_COOLDOWN_HOURS_BY_TYPE.get(normalized, 24)
    )
    env_key = f"REMINDER_COOLDOWN_HOURS_{normalized}"
    raw = (os.getenv(env_key) or "").strip()
    if not raw:
        return max(1, default_hours)
    try:
        return max(1, int(raw))
    except Exception:
        return max(1, default_hours)


async def _log_evaluation(
    db,
    *,
    reminder_type: str,
    state_key: Dict[str, str],
    decision: str,
    suppression_reason: Optional[str],
    underlying_state: Dict[str, Any],
) -> None:
    await db.reminder_evaluation_log.insert_one(
        {
            **state_key,
            "reminder_type": reminder_type,
            "decision": decision,  # evaluated_sent | evaluated_suppressed
            "suppression_reason": suppression_reason,
            "underlying_state": underlying_state,
            "created_at": _now_iso(),
        }
    )


async def evaluate_requirement_for_daily_reminder(
    db,
    requirement: Dict[str, Any],
    *,
    reminder_days: int,
    cooldown_hours: int = 24,
    reminder_type: str = "DAILY_COMPLIANCE_EXPIRY_EMAIL",
) -> Dict[str, Any]:
    """
    Live truth-check for requirement reminder eligibility.
    Returns dict with:
      - eligible: bool
      - suppression_reason: str|None
      - classification: "overdue"|"expiring"|None
      - state_key: dict key fields for item-level reminder state
      - current_requirement: current requirement document (if found)
    """
    state_key = _requirement_state_key(requirement, reminder_type)
    now = _now()

    current = await db.requirements.find_one(
        {
            "requirement_id": requirement.get("requirement_id"),
            "client_id": requirement.get("client_id"),
        },
        {"_id": 0},
    )
    if not current:
        await db.reminder_item_state.update_one(
            state_key,
            {
                "$set": {
                    **state_key,
                    "suppressed_at": now.isoformat(),
                    "suppression_reason": REASON_ITEM_NOT_FOUND,
                    "last_evaluated_at": now.isoformat(),
                    "last_underlying_state": {"status": None},
                    "updated_at": now.isoformat(),
                },
                "$setOnInsert": {"created_at": now.isoformat()},
            },
            upsert=True,
        )
        await _log_evaluation(
            db,
            reminder_type=reminder_type,
            state_key=state_key,
            decision="evaluated_suppressed",
            suppression_reason=REASON_ITEM_NOT_FOUND,
            underlying_state={"status": None, "gap_engine": {"gaps": [], "gap_kinds": [], "max_severity": None}},
        )
        return {
            "eligible": False,
            "suppression_reason": REASON_ITEM_NOT_FOUND,
            "classification": None,
            "state_key": state_key,
            "current_requirement": None,
            "gap_engine": {"gaps": [], "gap_kinds": [], "max_severity": None},
        }

    gap_ctx = _gap_engine_context_for_reminder(current)

    status = str(
        authority_runtime_requirement_status(current)
        or current.get("status")
        or ""
    ).upper()
    applicability = str(current.get("applicability") or "").upper()
    if status in {"COMPLIANT", "VERIFIED", "RESOLVED", "COMPLETED", "REGULARISED", "REGULARIZED", "REPLACED"} or applicability == "NOT_REQUIRED":
        await db.reminder_item_state.update_one(
            state_key,
            {
                "$set": {
                    **state_key,
                    "resolved_at": now.isoformat(),
                    "suppressed_at": now.isoformat(),
                    "suppression_reason": REASON_ALREADY_RESOLVED,
                    "last_evaluated_at": now.isoformat(),
                    "last_underlying_state": {"status": status, "applicability": applicability},
                    "updated_at": now.isoformat(),
                },
                "$setOnInsert": {"created_at": now.isoformat()},
            },
            upsert=True,
        )
        await _log_evaluation(
            db,
            reminder_type=reminder_type,
            state_key=state_key,
            decision="evaluated_suppressed",
            suppression_reason=REASON_ALREADY_RESOLVED,
            underlying_state={"status": status, "applicability": applicability, "gap_engine": gap_ctx},
        )
        return {
            "eligible": False,
            "suppression_reason": REASON_ALREADY_RESOLVED,
            "classification": None,
            "state_key": state_key,
            "current_requirement": current,
            "gap_engine": gap_ctx,
        }

    if not is_included_for_calendar(current):
        await db.reminder_item_state.update_one(
            state_key,
            {
                "$set": {
                    **state_key,
                    "suppressed_at": now.isoformat(),
                    "suppression_reason": REASON_NOT_RELEVANT,
                    "last_evaluated_at": now.isoformat(),
                    "last_underlying_state": {"status": status, "applicability": applicability},
                    "updated_at": now.isoformat(),
                },
                "$setOnInsert": {"created_at": now.isoformat()},
            },
            upsert=True,
        )
        await _log_evaluation(
            db,
            reminder_type=reminder_type,
            state_key=state_key,
            decision="evaluated_suppressed",
            suppression_reason=REASON_NOT_RELEVANT,
            underlying_state={"status": status, "applicability": applicability, "gap_engine": gap_ctx},
        )
        return {
            "eligible": False,
            "suppression_reason": REASON_NOT_RELEVANT,
            "classification": None,
            "state_key": state_key,
            "current_requirement": current,
            "gap_engine": gap_ctx,
        }

    due_date = get_effective_expiry_date(current)
    if due_date is None:
        await db.reminder_item_state.update_one(
            state_key,
            {
                "$set": {
                    **state_key,
                    "suppressed_at": now.isoformat(),
                    "suppression_reason": REASON_NO_EFFECTIVE_DATE,
                    "last_evaluated_at": now.isoformat(),
                    "last_underlying_state": {"status": status, "applicability": applicability},
                    "updated_at": now.isoformat(),
                },
                "$setOnInsert": {"created_at": now.isoformat()},
            },
            upsert=True,
        )
        await _log_evaluation(
            db,
            reminder_type=reminder_type,
            state_key=state_key,
            decision="evaluated_suppressed",
            suppression_reason=REASON_NO_EFFECTIVE_DATE,
            underlying_state={"status": status, "applicability": applicability, "gap_engine": gap_ctx},
        )
        return {
            "eligible": False,
            "suppression_reason": REASON_NO_EFFECTIVE_DATE,
            "classification": None,
            "state_key": state_key,
            "current_requirement": current,
            "gap_engine": gap_ctx,
        }

    days_until_due = (due_date - now).days
    classification = None
    if days_until_due < 0:
        classification = "overdue"
    elif 0 <= days_until_due <= int(reminder_days):
        classification = "expiring"
    if not classification:
        await db.reminder_item_state.update_one(
            state_key,
            {
                "$set": {
                    **state_key,
                    "suppressed_at": now.isoformat(),
                    "suppression_reason": REASON_NO_LONGER_DUE,
                    "last_evaluated_at": now.isoformat(),
                    "last_underlying_state": {"status": status, "days_until_due": days_until_due},
                    "updated_at": now.isoformat(),
                },
                "$setOnInsert": {"created_at": now.isoformat()},
            },
            upsert=True,
        )
        await _log_evaluation(
            db,
            reminder_type=reminder_type,
            state_key=state_key,
            decision="evaluated_suppressed",
            suppression_reason=REASON_NO_LONGER_DUE,
            underlying_state={"status": status, "days_until_due": days_until_due, "gap_engine": gap_ctx},
        )
        return {
            "eligible": False,
            "suppression_reason": REASON_NO_LONGER_DUE,
            "classification": None,
            "state_key": state_key,
            "current_requirement": current,
            "gap_engine": gap_ctx,
        }

    state = await db.reminder_item_state.find_one(state_key, {"_id": 0, "next_eligible_send_at": 1})
    next_eligible = _parse_iso((state or {}).get("next_eligible_send_at"))
    if next_eligible and next_eligible > now:
        await db.reminder_item_state.update_one(
            state_key,
            {
                "$set": {
                    **state_key,
                    "suppressed_at": now.isoformat(),
                    "suppression_reason": REASON_COOLDOWN_ACTIVE,
                    "last_evaluated_at": now.isoformat(),
                    "last_underlying_state": {"status": status, "days_until_due": days_until_due},
                    "updated_at": now.isoformat(),
                },
                "$setOnInsert": {"created_at": now.isoformat()},
            },
            upsert=True,
        )
        await _log_evaluation(
            db,
            reminder_type=reminder_type,
            state_key=state_key,
            decision="evaluated_suppressed",
            suppression_reason=REASON_COOLDOWN_ACTIVE,
            underlying_state={"status": status, "days_until_due": days_until_due, "gap_engine": gap_ctx},
        )
        return {
            "eligible": False,
            "suppression_reason": REASON_COOLDOWN_ACTIVE,
            "classification": None,
            "state_key": state_key,
            "current_requirement": current,
            "gap_engine": gap_ctx,
        }

    await db.reminder_item_state.update_one(
        state_key,
        {
            "$set": {
                **state_key,
                "suppression_reason": None,
                "suppressed_at": None,
                "last_evaluated_at": now.isoformat(),
                "last_underlying_state": {"status": status, "days_until_due": days_until_due},
                "updated_at": now.isoformat(),
            },
            "$setOnInsert": {"created_at": now.isoformat()},
        },
        upsert=True,
    )
    await _log_evaluation(
        db,
        reminder_type=reminder_type,
        state_key=state_key,
        decision="evaluated_send",
        suppression_reason=None,
        underlying_state={"status": status, "days_until_due": days_until_due, "gap_engine": gap_ctx},
    )
    return {
        "eligible": True,
        "suppression_reason": None,
        "classification": classification,
        "state_key": state_key,
        "current_requirement": current,
        "gap_engine": gap_ctx,
    }


async def mark_requirement_reminder_sent(
    db,
    state_key: Dict[str, str],
    *,
    cooldown_hours: int = 24,
) -> None:
    now = _now()
    await db.reminder_item_state.update_one(
        state_key,
        {
            "$set": {
                "last_sent_at": now.isoformat(),
                "next_eligible_send_at": (now + timedelta(hours=max(1, int(cooldown_hours)))).isoformat(),
                "suppressed_at": None,
                "suppression_reason": None,
                "updated_at": now.isoformat(),
            },
            "$setOnInsert": {"created_at": now.isoformat()},
        },
        upsert=True,
    )


async def get_pending_verification_snapshot(db) -> Dict[str, int]:
    cutoff_24h = (_now() - timedelta(hours=24)).isoformat()
    count_pending = await db.documents.count_documents({"status": "UPLOADED"})
    count_older_24h = await db.documents.count_documents(
        {"status": "UPLOADED", "uploaded_at": {"$lte": cutoff_24h}}
    )
    return {"count_pending": int(count_pending or 0), "count_older_24h": int(count_older_24h or 0)}
