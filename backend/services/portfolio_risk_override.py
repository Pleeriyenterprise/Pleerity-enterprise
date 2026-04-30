"""
Portfolio risk override model (Phase 3).

Preserves aggregate portfolio score while preventing average-washing in risk language when
serious unresolved issues exist.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from services.policy_reason_codes import PolicyReasonCode
from services.scoring_semantics_v1 import resolve_property_score_status
from utils.risk_bands import score_to_risk_level

_ORDER = {
    "Low Risk": 0,
    "Moderate Risk": 1,
    "High Risk": 2,
    "Critical Risk": 3,
}

_UNKNOWN_OR_STALE_STATUSES = frozenset(
    {"stale", "unknown", "unavailable", "reconciliation_required", "calculating"}
)


def _normalize_risk_level(raw: Optional[str]) -> Optional[str]:
    if not raw or not isinstance(raw, str):
        return None
    s = raw.strip().lower()
    if s == "low risk":
        return "Low Risk"
    if s == "moderate risk":
        return "Moderate Risk"
    if s == "high risk":
        return "High Risk"
    if s == "critical risk":
        return "Critical Risk"
    return None


def _max_risk(a: Optional[str], b: Optional[str]) -> Optional[str]:
    na = _normalize_risk_level(a)
    nb = _normalize_risk_level(b)
    if na is None:
        return nb
    if nb is None:
        return na
    return na if _ORDER[na] >= _ORDER[nb] else nb


def _score_from_any(raw: Any) -> Optional[float]:
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _count_unknown_or_stale_properties(
    properties: Iterable[Dict[str, Any]],
    property_breakdown: Optional[Iterable[Dict[str, Any]]] = None,
) -> int:
    by_pid_status: Dict[str, str] = {}
    for row in property_breakdown or []:
        pid = str(row.get("property_id") or "").strip()
        if not pid:
            continue
        st = str(row.get("score_status") or "").strip().lower()
        if st:
            by_pid_status[pid] = st

    out = 0
    for p in properties:
        pid = str(p.get("property_id") or "").strip()
        st = by_pid_status.get(pid)
        if not st:
            st = resolve_property_score_status(p)
        if st in _UNKNOWN_OR_STALE_STATUSES:
            out += 1
    return out


def _count_critical_properties(
    properties: Iterable[Dict[str, Any]],
    property_breakdown: Optional[Iterable[Dict[str, Any]]] = None,
) -> int:
    # Operationally "critical property escalation": overdue unresolved mandatory pressure or
    # a critical/high persisted risk with severe score.
    by_pid_row: Dict[str, Dict[str, Any]] = {}
    for row in property_breakdown or []:
        pid = str(row.get("property_id") or "").strip()
        if pid:
            by_pid_row[pid] = row

    count = 0
    for p in properties:
        pid = str(p.get("property_id") or "").strip()
        r = by_pid_row.get(pid, {})
        score = _score_from_any(r.get("score"))
        if score is None:
            score = _score_from_any(p.get("compliance_score"))
        risk = (
            _normalize_risk_level(r.get("risk_level"))
            or _normalize_risk_level(p.get("risk_level"))
            or (_normalize_risk_level(score_to_risk_level(int(round(score)))) if score is not None else None)
        )
        overdue_count = int(r.get("overdue") or r.get("overdue_count") or p.get("overdue_count") or 0)
        severe_score = score is not None and score < 40
        severe_risk = risk in ("High Risk", "Critical Risk")
        if overdue_count > 0 and (severe_score or severe_risk):
            count += 1
    return count


def derive_portfolio_risk_override(
    *,
    base_portfolio_risk_state: Optional[str],
    properties: List[Dict[str, Any]],
    property_breakdown: Optional[List[Dict[str, Any]]] = None,
    gap_engine: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Legacy override output (pre-PR5 switch path).

    Kept for compatibility; reason codes are canonicalized to PolicyReasonCode values.
    """
    by_sev = (gap_engine or {}).get("by_severity") if isinstance(gap_engine, dict) else {}
    by_sev = by_sev if isinstance(by_sev, dict) else {}
    critical_gap_count = int(by_sev.get("CRITICAL") or 0)
    high_gap_count = int(by_sev.get("HIGH") or 0)
    high_risk_gap_count = critical_gap_count + high_gap_count

    critical_property_count = _count_critical_properties(properties, property_breakdown)
    unknown_or_stale_property_count = _count_unknown_or_stale_properties(properties, property_breakdown)

    attention_required = high_risk_gap_count > 0 or critical_property_count > 0
    critical_property_escalation = critical_gap_count > 0 or critical_property_count > 0
    suppress_positive_headline = (
        attention_required or critical_property_escalation or unknown_or_stale_property_count > 0
    )

    reasons: List[str] = []
    if critical_gap_count > 0:
        reasons.append(PolicyReasonCode.UNRESOLVED_CRITICAL_MANDATORY_BREACH.value)
    if high_gap_count > 0:
        reasons.append(PolicyReasonCode.UNRESOLVED_HIGH_RISK_GAP.value)
    if critical_property_count > 0:
        reasons.append(PolicyReasonCode.CRITICAL_PROPERTY_ESCALATION.value)
    if unknown_or_stale_property_count > 0:
        reasons.append(PolicyReasonCode.UNKNOWN_OR_STALE_SUPPRESSION.value)

    effective = _normalize_risk_level(base_portfolio_risk_state) or "Low Risk"
    if critical_property_escalation:
        if critical_gap_count > 0 or critical_property_count > 1:
            effective = _max_risk(effective, "Critical Risk") or "Critical Risk"
        else:
            effective = _max_risk(effective, "High Risk") or "High Risk"
    elif attention_required:
        effective = _max_risk(effective, "High Risk") or "High Risk"
    elif unknown_or_stale_property_count > 0:
        effective = _max_risk(effective, "Moderate Risk") or "Moderate Risk"

    return {
        "base_portfolio_risk_state": _normalize_risk_level(base_portfolio_risk_state),
        "effective_portfolio_risk_state": effective,
        "risk_override_reasons": reasons,
        "critical_property_count": critical_property_count,
        "high_risk_gap_count": high_risk_gap_count,
        "unknown_or_stale_property_count": unknown_or_stale_property_count,
        "attention_required": attention_required,
        "critical_property_escalation": critical_property_escalation,
        "suppress_positive_headline": suppress_positive_headline,
    }


def _finalize_policy_override_reason_codes(
    *,
    effective: str,
    reasons: List[str],
    critical_breach_count: int,
    high_risk_count: int,
    attention_only_count: int,
    unknown_count: int,
) -> List[str]:
    """Ensure elevated effective states always carry canonical PolicyReasonCode values."""
    out = list(dict.fromkeys(reasons))
    ne = _normalize_risk_level(effective) or "Low Risk"

    if ne == "Critical Risk":
        if critical_breach_count > 0:
            if PolicyReasonCode.UNRESOLVED_CRITICAL_MANDATORY_BREACH.value not in out:
                out.insert(0, PolicyReasonCode.UNRESOLVED_CRITICAL_MANDATORY_BREACH.value)
        else:
            dom = PolicyReasonCode.PERSISTED_PORTFOLIO_HEADLINE_DOMINATES_EFFECTIVE.value
            if dom not in out:
                out.append(dom)

    if ne != "Low Risk" and not out:
        if critical_breach_count > 0:
            out.append(PolicyReasonCode.UNRESOLVED_CRITICAL_MANDATORY_BREACH.value)
        elif high_risk_count > 0:
            out.append(PolicyReasonCode.UNRESOLVED_HIGH_RISK_GAP.value)
        elif attention_only_count > 0:
            out.append(PolicyReasonCode.ATTENTION_ONLY_GAP.value)
        elif unknown_count > 0:
            out.append(PolicyReasonCode.UNKNOWN_OR_STALE_SUPPRESSION.value)
        else:
            out.append(PolicyReasonCode.PERSISTED_PORTFOLIO_HEADLINE_DOMINATES_EFFECTIVE.value)

    return list(dict.fromkeys(out))


def derive_policy_portfolio_risk_override(
    *,
    base_portfolio_risk_state: Optional[str],
    gap_engine: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Policy-backed override output (PR5).

    Uses policy aggregate counters only (no severity-only escalation).
    Persistent anti-flap is applied in ``apply_persistent_critical_escalation_latch`` (Mongo).
    """
    policy = (gap_engine or {}).get("policy") if isinstance(gap_engine, dict) else {}
    policy = policy if isinstance(policy, dict) else {}

    critical_breach_count = int(policy.get("critical_mandatory_breach_count") or 0)
    high_risk_count = int(policy.get("high_risk_gap_count") or 0)
    attention_only_count = int(policy.get("attention_only_gap_count") or 0)
    unknown_count = int(policy.get("unknown_or_stale_signal_count") or 0)

    reasons: List[str] = []
    if critical_breach_count > 0:
        reasons.append(PolicyReasonCode.UNRESOLVED_CRITICAL_MANDATORY_BREACH.value)
    if high_risk_count > 0:
        reasons.append(PolicyReasonCode.UNRESOLVED_HIGH_RISK_GAP.value)
    if attention_only_count > 0:
        reasons.append(PolicyReasonCode.ATTENTION_ONLY_GAP.value)
    if unknown_count > 0:
        reasons.append(PolicyReasonCode.UNKNOWN_OR_STALE_SUPPRESSION.value)

    attention_required = (critical_breach_count + high_risk_count + attention_only_count) > 0
    critical_property_escalation = critical_breach_count > 0
    suppress_positive_headline = attention_required or unknown_count > 0

    effective = _normalize_risk_level(base_portfolio_risk_state) or "Low Risk"
    if critical_breach_count > 0:
        effective = _max_risk(effective, "Critical Risk") or "Critical Risk"
    elif high_risk_count > 0:
        effective = _max_risk(effective, "High Risk") or "High Risk"
    elif attention_only_count > 0 or unknown_count > 0:
        effective = _max_risk(effective, "Moderate Risk") or "Moderate Risk"

    reasons = _finalize_policy_override_reason_codes(
        effective=effective,
        reasons=reasons,
        critical_breach_count=critical_breach_count,
        high_risk_count=high_risk_count,
        attention_only_count=attention_only_count,
        unknown_count=unknown_count,
    )

    return {
        "base_portfolio_risk_state": _normalize_risk_level(base_portfolio_risk_state),
        "effective_portfolio_risk_state": effective,
        "risk_override_reasons": reasons,
        # Keep output shape stable; policy path does not use property heuristics.
        "critical_property_count": 0,
        "high_risk_gap_count": critical_breach_count + high_risk_count,
        "unknown_or_stale_property_count": unknown_count,
        "attention_required": attention_required,
        "critical_property_escalation": critical_property_escalation,
        "suppress_positive_headline": suppress_positive_headline,
    }


def select_effective_portfolio_risk_override(
    *,
    legacy_override_output: Dict[str, Any],
    policy_override_output: Dict[str, Any],
    policy_switch_enabled: bool,
    policy_coverage_percent: float,
    policy_coverage_threshold_percent: float,
    drift_detected: bool,
    reconciliation_in_progress: bool,
    policy_aggregate_unavailable: bool,
) -> Dict[str, Any]:
    """
    Choose effective output from legacy/policy with explicit, observable fallback gates.
    """
    fallback_reasons: List[str] = []
    if policy_aggregate_unavailable:
        fallback_reasons.append(PolicyReasonCode.POLICY_AGGREGATE_UNAVAILABLE.value)
    if policy_coverage_percent < float(policy_coverage_threshold_percent):
        fallback_reasons.append(PolicyReasonCode.POLICY_FIELDS_INCOMPLETE.value)
    if drift_detected:
        fallback_reasons.append(PolicyReasonCode.POLICY_DRIFT_DETECTED.value)
    if reconciliation_in_progress:
        fallback_reasons.append(PolicyReasonCode.RECONCILIATION_IN_PROGRESS.value)

    if not policy_switch_enabled:
        selected = dict(legacy_override_output)
        source = "legacy"
        fallback_applied = False
    elif fallback_reasons:
        selected = dict(legacy_override_output)
        source = "legacy_fallback"
        fallback_applied = True
    else:
        selected = dict(policy_override_output)
        source = "policy"
        fallback_applied = False

    selected["override_output_source"] = source
    selected["fallback_applied"] = fallback_applied
    selected["fallback_reason_codes"] = list(dict.fromkeys(fallback_reasons))
    return selected
