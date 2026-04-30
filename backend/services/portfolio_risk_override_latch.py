"""
PR5 readiness: tenant-scoped persistent latch for policy critical escalation anti-flapping.

Writes are tenant-scoped only (filter includes client_id). No cross-tenant queries.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from services.portfolio_override_policy_health import JOB_GAP_RECONCILIATION
from services.policy_reason_codes import PolicyReasonCode

LATCH_COLLECTION = "portfolio_risk_override_latches"


def _gap_checkpoint_cycle_tuple(ref: Optional[Dict[str, Any]]) -> Tuple[str, str]:
    if not isinstance(ref, dict):
        return ("", "")
    ca = str(ref.get("checkpoint_completed_at") or ref.get("completed_at") or "").strip()
    ua = str(ref.get("checkpoint_updated_at") or ref.get("updated_at") or "").strip()
    return (ca, ua)


def gap_reconciliation_cycle_is_newer_than(
    current: Optional[Dict[str, Any]],
    latched: Optional[Dict[str, Any]],
) -> bool:
    """True iff current gap-reconciliation cycle is strictly newer than latched ref (ISO tuples)."""
    ca, ua = _gap_checkpoint_cycle_tuple(current)
    lb, lc = _gap_checkpoint_cycle_tuple(latched)
    if (ca, ua) > (lb, lc):
        return True
    return False


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def load_critical_escalation_latch(db: Any, *, client_id: str) -> Optional[Dict[str, Any]]:
    row = await db[LATCH_COLLECTION].find_one({"client_id": client_id}, {"_id": 0})
    if not row or not row.get("active"):
        return None
    return row


async def _upsert_latch(
    db: Any,
    *,
    client_id: str,
    patch: Dict[str, Any],
) -> None:
    await db[LATCH_COLLECTION].update_one(
        {"client_id": client_id},
        {"$set": {**patch, "updated_at": _utc_iso()}, "$setOnInsert": {"client_id": client_id, "created_at": _utc_iso()}},
        upsert=True,
    )


async def clear_critical_escalation_latch(db: Any, *, client_id: str) -> None:
    await db[LATCH_COLLECTION].update_one(
        {"client_id": client_id},
        {"$set": {"active": False, "cleared_at": _utc_iso(), "updated_at": _utc_iso()}},
        upsert=False,
    )


async def apply_persistent_critical_escalation_latch(
    db: Any,
    *,
    client_id: str,
    policy_override_output: Dict[str, Any],
    gap_engine: Dict[str, Any],
    gap_reconciliation_checkpoint: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Persist and apply tenant-scoped critical escalation latch.

    Clear rule (all required):
    a) policy critical_mandatory_breach_count == 0
    b) gap reconciliation checkpoint status is completed
    c) current gap reconciliation cycle is newer than the latched event ref
    """
    policy = (gap_engine or {}).get("policy") if isinstance(gap_engine, dict) else {}
    policy = policy if isinstance(policy, dict) else {}
    critical_breach = int(policy.get("critical_mandatory_breach_count") or 0)

    cur_ref = {
        "job_name": JOB_GAP_RECONCILIATION,
        "checkpoint_completed_at": gap_reconciliation_checkpoint.get("completed_at"),
        "checkpoint_updated_at": gap_reconciliation_checkpoint.get("updated_at"),
        "status": gap_reconciliation_checkpoint.get("status"),
    }
    gap_ok = str(gap_reconciliation_checkpoint.get("status") or "").lower() == "completed"

    out = dict(policy_override_output)
    existing = await load_critical_escalation_latch(db, client_id=client_id)

    # Clear latch when all conditions hold
    if (
        critical_breach == 0
        and gap_ok
        and existing
        and gap_reconciliation_cycle_is_newer_than(cur_ref, existing.get("latch_reconciliation_cycle_ref"))
    ):
        await clear_critical_escalation_latch(db, client_id=client_id)
        existing = None

    # Activate / refresh latch on critical breach
    if critical_breach > 0:
        reasons = list(out.get("risk_override_reasons") or [])
        if PolicyReasonCode.UNRESOLVED_CRITICAL_MANDATORY_BREACH.value not in reasons:
            reasons.insert(0, PolicyReasonCode.UNRESOLVED_CRITICAL_MANDATORY_BREACH.value)
        out["risk_override_reasons"] = list(dict.fromkeys(reasons))
        out["critical_property_escalation"] = True
        out["attention_required"] = True
        out["suppress_positive_headline"] = True
        eff = str(out.get("effective_portfolio_risk_state") or "")
        if eff != "Critical Risk":
            out["effective_portfolio_risk_state"] = "Critical Risk"
        # First activation or re-activation after clear: capture cycle ref at breach observation
        if not existing:
            await _upsert_latch(
                db,
                client_id=client_id,
                patch={
                    "active": True,
                    "latched_critical_escalation": True,
                    "last_effective_portfolio_risk_state": out.get("effective_portfolio_risk_state"),
                    "latch_reason_codes": list(dict.fromkeys(reasons)),
                    "latch_reconciliation_cycle_ref": cur_ref,
                },
            )
        else:
            await _upsert_latch(
                db,
                client_id=client_id,
                patch={
                    "active": True,
                    "latched_critical_escalation": True,
                    "last_effective_portfolio_risk_state": out.get("effective_portfolio_risk_state"),
                    "latch_reason_codes": list(dict.fromkeys(reasons)),
                },
            )
        return out

    # Hold: breach cleared in policy aggregate but latch not yet cleared by reconciliation cycle
    if existing and existing.get("latched_critical_escalation") and critical_breach == 0:
        held = dict(out)
        held["effective_portfolio_risk_state"] = existing.get("last_effective_portfolio_risk_state") or "Critical Risk"
        held["critical_property_escalation"] = True
        held["attention_required"] = True
        held["suppress_positive_headline"] = True
        r = list(held.get("risk_override_reasons") or [])
        if PolicyReasonCode.ANTI_FLAPPING_RECONCILIATION_HOLD.value not in r:
            r.append(PolicyReasonCode.ANTI_FLAPPING_RECONCILIATION_HOLD.value)
        held["risk_override_reasons"] = list(dict.fromkeys(r))
        return held

    return out
