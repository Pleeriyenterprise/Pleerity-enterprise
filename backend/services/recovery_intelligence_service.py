"""Recovery intelligence — pattern signals with coarse confidence only."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from services.recovery_constants import (
    CONFIDENCE_HIGH,
    CONFIDENCE_LOW,
    CONFIDENCE_MODERATE,
    RECOVERY_CONTRACTOR_NON_RESPONSE,
    RECOVERY_EVIDENCE_REJECTION_LOOP,
    RECOVERY_OPERATIONAL_DEAD_END,
    RECOVERY_QUOTE_NEGOTIATION_LOOP,
    RECOVERY_VISIT_RESCHEDULE_LOOP,
    RECOVERY_WORKFLOW_STATE_DRIFT,
    RECOVERY_WORK_ORDER_ABANDONMENT_RISK,
)

_INSTABILITY_TYPES = frozenset(
    {
        RECOVERY_QUOTE_NEGOTIATION_LOOP,
        RECOVERY_VISIT_RESCHEDULE_LOOP,
        RECOVERY_EVIDENCE_REJECTION_LOOP,
        RECOVERY_WORKFLOW_STATE_DRIFT,
    }
)


def _coarse_confidence(*, repetition_count: int, age_hours: Optional[float], nudge_count: int) -> str:
    score = 0
    if repetition_count >= 3:
        score += 2
    elif repetition_count >= 2:
        score += 1
    if age_hours is not None:
        if age_hours >= 72:
            score += 2
        elif age_hours >= 24:
            score += 1
    if nudge_count >= 2:
        score += 1
    if score >= 4:
        return CONFIDENCE_HIGH
    if score >= 2:
        return CONFIDENCE_MODERATE
    return CONFIDENCE_LOW


def detect_instability_signals(recovery_type: str, *, repetition_count: int, age_hours: Optional[float]) -> List[str]:
    signals: List[str] = []
    if recovery_type == RECOVERY_CONTRACTOR_NON_RESPONSE and age_hours and age_hours >= 48:
        signals.append("Contractor has missed multiple response windows.")
    if recovery_type == RECOVERY_QUOTE_NEGOTIATION_LOOP and repetition_count >= 2:
        signals.append("Quote back-and-forth continues without a decision.")
    if recovery_type == RECOVERY_VISIT_RESCHEDULE_LOOP and repetition_count >= 2:
        signals.append("This visit has been rescheduled several times.")
    if recovery_type == RECOVERY_EVIDENCE_REJECTION_LOOP and repetition_count >= 2:
        signals.append("This requirement has had repeated evidence rejection.")
    if recovery_type == RECOVERY_WORK_ORDER_ABANDONMENT_RISK:
        signals.append("Activity on this job has dropped despite reminders.")
    if recovery_type == RECOVERY_OPERATIONAL_DEAD_END:
        signals.append("This workflow may require manual intervention.")
    if recovery_type in _INSTABILITY_TYPES and age_hours and age_hours >= 72:
        signals.append("Delays are increasing and may need direct follow-up.")
    return signals


def detect_escalation_progression(*, age_hours: Optional[float], nudge_count: int, repetition_count: int) -> int:
    level = 0
    if age_hours and age_hours >= 24:
        level = 1
    if age_hours and age_hours >= 72:
        level = 2
    if nudge_count >= 2 and level < 2:
        level = 2
    if repetition_count >= 3:
        level = max(level, 2)
    return level


def assess_recovery_likelihood(
    recovery_type: str,
    *,
    repetition_count: int,
    age_hours: Optional[float],
    nudge_count: int,
    has_safe_action: bool,
) -> str:
    """Coarse likelihood that guidance alone will unblock — not a probability."""
    if not has_safe_action or recovery_type == RECOVERY_OPERATIONAL_DEAD_END:
        return CONFIDENCE_LOW
    if nudge_count >= 3 or repetition_count >= 4:
        return CONFIDENCE_LOW
    if recovery_type in _INSTABILITY_TYPES and repetition_count >= 2:
        return CONFIDENCE_LOW
    if age_hours and age_hours >= 72:
        return CONFIDENCE_MODERATE
    return CONFIDENCE_HIGH


def enrich_recovery_intelligence(
    recovery: Dict[str, Any],
    *,
    nudge_count: int = 0,
    has_safe_action: bool = True,
) -> Dict[str, Any]:
    rtype = recovery.get("recovery_type") or ""
    rep = int(recovery.get("repetition_count") or 0)
    age = recovery.get("age_hours")
    signals = detect_instability_signals(rtype, repetition_count=rep, age_hours=age)
    recovery["instability_signals"] = signals
    recovery["escalation_level"] = detect_escalation_progression(
        age_hours=age,
        nudge_count=nudge_count,
        repetition_count=rep,
    )
    recovery["recovery_confidence"] = _coarse_confidence(
        repetition_count=rep,
        age_hours=age,
        nudge_count=nudge_count,
    )
    recovery["recovery_likelihood"] = assess_recovery_likelihood(
        rtype,
        repetition_count=rep,
        age_hours=age,
        nudge_count=nudge_count,
        has_safe_action=has_safe_action,
    )
    if signals:
        recovery["intelligence_summary"] = signals[0]
    return recovery
