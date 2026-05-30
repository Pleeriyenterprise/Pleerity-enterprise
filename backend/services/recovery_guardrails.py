"""Phase 2A recovery guardrails — guidance only, no authority mutations."""
from __future__ import annotations

from typing import Any, Dict, FrozenSet, Mapping, Optional

from services.recovery_constants import (
    AUTHORITY_SAFE_RECOVERY_ACTIONS,
    FORBIDDEN_RECOVERY_ACTIONS,
)

FORBIDDEN_MUTATION_FIELDS: FrozenSet[str] = frozenset(
    {
        "price_status",
        "schedule_status",
        "status",
        "contractor_id",
        "evidence_review_state",
        "compliance_state",
        "verified_at",
        "assurance_tier",
    }
)

FORBIDDEN_COPY_TERMS: FrozenSet[str] = frozenset(
    {
        "workflow engine",
        "orchestration",
        "escalation algorithm",
        "confidence model",
        "reconciliation layer",
        "state mismatch",
        "workflow entity",
        "server-confirmed",
    }
)


def is_authority_safe_recovery_action(action_id: str) -> bool:
    aid = (action_id or "").strip().lower()
    if not aid:
        return False
    if aid in FORBIDDEN_RECOVERY_ACTIONS:
        return False
    return aid in AUTHORITY_SAFE_RECOVERY_ACTIONS


def assert_recovery_guidance_safe(recovery: Mapping[str, Any]) -> None:
    if not recovery.get("authority_safe", True):
        raise ValueError("Recovery guidance must be authority_safe")
    for action in recovery.get("suggested_actions") or []:
        aid = action.get("action_id") if isinstance(action, dict) else str(action)
        if not is_authority_safe_recovery_action(aid):
            raise ValueError(f"Forbidden recovery action: {aid}")
    blob = " ".join(
        [
            str(recovery.get("recovery_summary") or ""),
            str(recovery.get("recovery_explanation") or ""),
        ]
    ).lower()
    for term in FORBIDDEN_COPY_TERMS:
        if term in blob:
            raise ValueError(f"Forbidden terminology in recovery copy: {term}")


def assert_no_authority_mutation_in_payload(payload: Mapping[str, Any]) -> None:
    for key in payload:
        if key in FORBIDDEN_MUTATION_FIELDS:
            raise ValueError(f"Authority mutation forbidden in recovery automation: {key}")


def filter_authority_safe_actions(actions: Optional[list]) -> list:
    out = []
    for a in actions or []:
        if isinstance(a, dict):
            aid = a.get("action_id") or ""
            if is_authority_safe_recovery_action(aid):
                out.append(a)
        elif isinstance(a, str) and is_authority_safe_recovery_action(a):
            out.append({"action_id": a, "label": a.replace("_", " ").title()})
    return out


def assert_recovery_convergence(
    surfaces: Mapping[str, Mapping[str, Any]],
) -> None:
    """Ensure recovery truth does not contradict across surfaces."""
    waiting_parties: set = set()
    blocked_flags: set = set()
    for name, data in surfaces.items():
        if not data:
            continue
        w = data.get("waiting_on_summary") or data.get("waiting_on_party")
        if w:
            waiting_parties.add(str(w).lower())
        if data.get("is_blocked") or data.get("blocked_count", 0) > 0:
            blocked_flags.add(name)
        disclosure = data.get("recovery_disclosure") or {}
        if disclosure.get("has_recovery_attention") and disclosure.get("blocked_count", 0) == 0:
            if data.get("stalled_reason") and "cannot currently move forward" in str(data.get("stalled_reason")):
                raise ValueError(f"False calm on {name}: dead-end without blocked disclosure")
    if len(waiting_parties) > 1 and blocked_flags:
        raise ValueError("Contradictory waiting-on parties across recovery surfaces")
