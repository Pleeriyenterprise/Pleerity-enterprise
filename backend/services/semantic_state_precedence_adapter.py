from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from services.semantic_state_read_contract import (
    PORTFOLIO_SCORE,
    REMINDER_ENGINE,
    REPORT_EXPORT,
    WIDESPREAD_COLLAPSE_DEPENDENCY,
    audit_semantic_state_interpretation_diff,
)

# Adapter interpretation modes (audit-phase only)
LEGACY_RUNTIME_INTERPRETATION = "LEGACY_RUNTIME_INTERPRETATION"
SEMANTIC_AWARE_INTERPRETATION = "SEMANTIC_AWARE_INTERPRETATION"
HYBRID_AUDIT_INTERPRETATION = "HYBRID_AUDIT_INTERPRETATION"

# Audit-mode runtime controls (must remain non-enforcing in Phase 4)
SEMANTIC_STATE_ADAPTER_AUDIT_MODE = True
SEMANTIC_STATE_RUNTIME_ENFORCEMENT = False

# Delta impact labels
NO_DELTA = "NO_DELTA"
LOW_DELTA = "LOW_DELTA"
HIGH_DELTA = "HIGH_DELTA"
BEHAVIORALLY_SIGNIFICANT_DELTA = "BEHAVIORALLY_SIGNIFICANT_DELTA"
WIDESPREAD_COLLAPSE_DELTA = "WIDESPREAD_COLLAPSE_DELTA"

# Rollout-readiness guidance (audit-only)
LOW_RISK_FIRST_MIGRATION = "LOW_RISK_FIRST_MIGRATION"
HIGH_COLLAPSE_HIGH_PRIORITY = "HIGH_COLLAPSE_HIGH_PRIORITY"
BEHAVIORALLY_RISKY_TO_SWITCH = "BEHAVIORALLY_RISKY_TO_SWITCH"
INSUFFICIENT_SAMPLE_VOLUME = "INSUFFICIENT_SAMPLE_VOLUME"

_OBSERVED_DELTA_EVENTS: List[Dict[str, Any]] = []
_MAX_OBSERVED_EVENTS = 5000


def classify_delta_impact(diff: Dict[str, Any]) -> str:
    if not bool(diff.get("delta_detected")):
        return NO_DELTA
    raw = str(diff.get("delta_impact") or "").strip().upper()
    if raw == WIDESPREAD_COLLAPSE_DEPENDENCY:
        return WIDESPREAD_COLLAPSE_DELTA
    if raw == "HIGH_IMPACT":
        return HIGH_DELTA
    if raw == "MEDIUM_IMPACT":
        return BEHAVIORALLY_SIGNIFICANT_DELTA
    if raw == "LOW_IMPACT":
        return LOW_DELTA
    return HIGH_DELTA


def _adapt_for_consumer(
    consumer: str,
    semantic_state: str,
    *,
    mode: str = LEGACY_RUNTIME_INTERPRETATION,
) -> Dict[str, Any]:
    row = audit_semantic_state_interpretation_diff(consumer, semantic_state)
    legacy = row.get("current_interpretation")
    semantic = row.get("expected_interpretation")
    delta_detected = bool(row.get("collapse_detected"))
    out = {
        "consumer": consumer,
        "semantic_state": str(semantic_state or "").strip().upper(),
        "legacy_interpretation": legacy,
        "semantic_interpretation": semantic,
        "delta_detected": delta_detected,
        "delta_impact": row.get("impact_level"),
        "delta_classification": classify_delta_impact(
            {"delta_detected": delta_detected, "delta_impact": row.get("impact_level")}
        ),
        "risk_classifications": list(row.get("risk") or []),
        "mode": mode,
        "non_blocking": True,
    }
    # Phase 4 safety: runtime output remains legacy unless future phases explicitly enable enforcement.
    runtime_selected = legacy
    if SEMANTIC_STATE_RUNTIME_ENFORCEMENT and mode == SEMANTIC_AWARE_INTERPRETATION:
        runtime_selected = semantic
    out["runtime_selected_interpretation"] = runtime_selected
    return out


def _append_observed_event(event: Dict[str, Any]) -> None:
    _OBSERVED_DELTA_EVENTS.append(event)
    if len(_OBSERVED_DELTA_EVENTS) > _MAX_OBSERVED_EVENTS:
        del _OBSERVED_DELTA_EVENTS[0 : len(_OBSERVED_DELTA_EVENTS) - _MAX_OBSERVED_EVENTS]


def observe_consumer_precedence_delta(
    consumer: str,
    semantic_state: str,
    *,
    property_id: str | None = None,
    requirement_id: str | None = None,
    mode: str = HYBRID_AUDIT_INTERPRETATION,
) -> Dict[str, Any]:
    """
    Observe-only runtime hook: returns audit payload and appends an in-memory event.
    Never raises to runtime callers.
    """
    try:
        if consumer == REMINDER_ENGINE:
            row = adapt_reminder_semantic_interpretation(semantic_state, mode=mode)
        elif consumer == REPORT_EXPORT:
            row = adapt_report_export_semantic_interpretation(semantic_state, mode=mode)
        elif consumer == PORTFOLIO_SCORE:
            row = adapt_portfolio_score_semantic_interpretation(semantic_state, mode=mode)
        else:
            row = {
                "consumer": consumer,
                "semantic_state": str(semantic_state or "").strip().upper(),
                "legacy_interpretation": None,
                "semantic_interpretation": None,
                "delta_detected": False,
                "delta_impact": NO_DELTA,
                "delta_classification": NO_DELTA,
                "risk_classifications": [],
                "mode": mode,
                "runtime_selected_interpretation": None,
                "non_blocking": True,
                "observation_error": f"unsupported_consumer:{consumer}",
            }
        event = {
            "consumer": row.get("consumer"),
            "semantic_state": row.get("semantic_state"),
            "legacy_interpretation": row.get("legacy_interpretation"),
            "semantic_interpretation": row.get("semantic_interpretation"),
            "delta_detected": bool(row.get("delta_detected")),
            "delta_impact": row.get("delta_classification") or row.get("delta_impact"),
            "risk_classifications": list(row.get("risk_classifications") or []),
            "property_id": property_id,
            "requirement_id": requirement_id,
            "sampled_at": datetime.now(timezone.utc).isoformat(),
            "non_blocking": True,
        }
        _append_observed_event(event)
        return event
    except Exception as exc:  # pragma: no cover - hard safety path
        fallback = {
            "consumer": consumer,
            "semantic_state": str(semantic_state or "").strip().upper(),
            "legacy_interpretation": None,
            "semantic_interpretation": None,
            "delta_detected": False,
            "delta_impact": NO_DELTA,
            "risk_classifications": [],
            "property_id": property_id,
            "requirement_id": requirement_id,
            "sampled_at": datetime.now(timezone.utc).isoformat(),
            "non_blocking": True,
            "observation_error": type(exc).__name__,
        }
        _append_observed_event(fallback)
        return fallback


def get_observed_delta_events() -> List[Dict[str, Any]]:
    return list(_OBSERVED_DELTA_EVENTS)


def reset_observed_delta_events() -> None:
    _OBSERVED_DELTA_EVENTS.clear()


def summarize_observed_deltas() -> Dict[str, Any]:
    by_consumer: Dict[str, int] = {}
    by_state: Dict[str, int] = {}
    by_impact: Dict[str, int] = {}
    delta_total = 0
    for e in _OBSERVED_DELTA_EVENTS:
        c = str(e.get("consumer") or "")
        s = str(e.get("semantic_state") or "")
        i = str(e.get("delta_impact") or "")
        by_consumer[c] = by_consumer.get(c, 0) + 1
        by_state[s] = by_state.get(s, 0) + 1
        by_impact[i] = by_impact.get(i, 0) + 1
        if bool(e.get("delta_detected")):
            delta_total += 1
    return {
        "event_count": len(_OBSERVED_DELTA_EVENTS),
        "delta_count": delta_total,
        "by_consumer": by_consumer,
        "by_semantic_state": by_state,
        "by_delta_impact": by_impact,
        "non_blocking": True,
    }


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


def _filtered_events(
    *,
    consumer: Optional[str] = None,
    semantic_state: Optional[str] = None,
    delta_impact: Optional[str] = None,
    delta_detected: Optional[bool] = None,
    high_impact_only: bool = False,
    collapse_risk_only: bool = False,
    since_iso: Optional[str] = None,
    until_iso: Optional[str] = None,
) -> List[Dict[str, Any]]:
    since_dt = _parse_iso(since_iso)
    until_dt = _parse_iso(until_iso)
    out: List[Dict[str, Any]] = []
    for e in _OBSERVED_DELTA_EVENTS:
        if consumer and str(e.get("consumer") or "").upper() != str(consumer).upper():
            continue
        if semantic_state and str(e.get("semantic_state") or "").upper() != str(semantic_state).upper():
            continue
        if delta_impact and str(e.get("delta_impact") or "").upper() != str(delta_impact).upper():
            continue
        if delta_detected is not None and bool(e.get("delta_detected")) != bool(delta_detected):
            continue
        if high_impact_only and str(e.get("delta_impact") or "").upper() not in (
            HIGH_DELTA,
            WIDESPREAD_COLLAPSE_DELTA,
            "HIGH_IMPACT",
            "WIDESPREAD_COLLAPSE_DEPENDENCY",
        ):
            continue
        if collapse_risk_only and not bool(e.get("delta_detected")):
            continue
        if since_dt or until_dt:
            sampled = _parse_iso(e.get("sampled_at"))
            if sampled is None:
                continue
            if since_dt and sampled < since_dt:
                continue
            if until_dt and sampled > until_dt:
                continue
        out.append(e)
    return out


def get_semantic_delta_summary(**filters: Any) -> Dict[str, Any]:
    rows = _filtered_events(**filters)
    by_consumer: Dict[str, int] = {}
    by_state: Dict[str, int] = {}
    by_impact: Dict[str, int] = {}
    delta_count = 0
    for r in rows:
        c = str(r.get("consumer") or "")
        s = str(r.get("semantic_state") or "")
        i = str(r.get("delta_impact") or "")
        by_consumer[c] = by_consumer.get(c, 0) + 1
        by_state[s] = by_state.get(s, 0) + 1
        by_impact[i] = by_impact.get(i, 0) + 1
        if bool(r.get("delta_detected")):
            delta_count += 1
    return {
        "event_count": len(rows),
        "delta_count": delta_count,
        "by_consumer": by_consumer,
        "by_semantic_state": by_state,
        "by_delta_impact": by_impact,
        "non_blocking": True,
    }


def get_semantic_delta_summary_by_consumer(**filters: Any) -> Dict[str, Any]:
    rows = _filtered_events(**filters)
    out: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        c = str(r.get("consumer") or "")
        slot = out.setdefault(c, {"event_count": 0, "delta_count": 0, "highest_impact": NO_DELTA})
        slot["event_count"] += 1
        if bool(r.get("delta_detected")):
            slot["delta_count"] += 1
        impact = str(r.get("delta_impact") or "")
        if slot["highest_impact"] != WIDESPREAD_COLLAPSE_DELTA:
            if impact == WIDESPREAD_COLLAPSE_DELTA:
                slot["highest_impact"] = WIDESPREAD_COLLAPSE_DELTA
            elif impact in (HIGH_DELTA, "HIGH_IMPACT") and slot["highest_impact"] not in (
                WIDESPREAD_COLLAPSE_DELTA,
                HIGH_DELTA,
            ):
                slot["highest_impact"] = HIGH_DELTA
            elif impact in (BEHAVIORALLY_SIGNIFICANT_DELTA, "MEDIUM_IMPACT") and slot["highest_impact"] == NO_DELTA:
                slot["highest_impact"] = BEHAVIORALLY_SIGNIFICANT_DELTA
            elif impact in (LOW_DELTA, "LOW_IMPACT") and slot["highest_impact"] == NO_DELTA:
                slot["highest_impact"] = LOW_DELTA
    return {"by_consumer": out, "non_blocking": True}


def get_semantic_delta_summary_by_semantic_state(**filters: Any) -> Dict[str, Any]:
    rows = _filtered_events(**filters)
    out: Dict[str, Dict[str, int]] = {}
    for r in rows:
        s = str(r.get("semantic_state") or "")
        slot = out.setdefault(s, {"event_count": 0, "delta_count": 0})
        slot["event_count"] += 1
        if bool(r.get("delta_detected")):
            slot["delta_count"] += 1
    return {"by_semantic_state": out, "non_blocking": True}


def get_semantic_delta_summary_by_impact(**filters: Any) -> Dict[str, Any]:
    rows = _filtered_events(**filters)
    out: Dict[str, int] = {}
    for r in rows:
        i = str(r.get("delta_impact") or NO_DELTA)
        out[i] = out.get(i, 0) + 1
    return {"by_delta_impact": out, "non_blocking": True}


def _rollout_signal(event_count: int, delta_count: int, highest_impact: str) -> str:
    if event_count < 5:
        return INSUFFICIENT_SAMPLE_VOLUME
    if highest_impact == WIDESPREAD_COLLAPSE_DELTA:
        return HIGH_COLLAPSE_HIGH_PRIORITY
    if highest_impact in (HIGH_DELTA,):
        return BEHAVIORALLY_RISKY_TO_SWITCH
    if delta_count == 0:
        return LOW_RISK_FIRST_MIGRATION
    return BEHAVIORALLY_RISKY_TO_SWITCH


def build_semantic_delta_export_snapshot(**filters: Any) -> Dict[str, Any]:
    by_consumer = get_semantic_delta_summary_by_consumer(**filters).get("by_consumer") or {}
    rows = []
    for consumer, stats in by_consumer.items():
        rows.append(
            {
                "consumer": consumer,
                "event_count": int(stats.get("event_count") or 0),
                "delta_count": int(stats.get("delta_count") or 0),
                "highest_impact": stats.get("highest_impact") or NO_DELTA,
                "runtime_behavior_changed": False,
            }
        )
    rows.sort(key=lambda r: (-int(r.get("delta_count") or 0), r.get("consumer") or ""))
    return {"snapshot": rows, "non_blocking": True}


def build_semantic_delta_rollout_summary(**filters: Any) -> Dict[str, Any]:
    snap = build_semantic_delta_export_snapshot(**filters).get("snapshot") or []
    rows = []
    for r in snap:
        signal = _rollout_signal(
            event_count=int(r.get("event_count") or 0),
            delta_count=int(r.get("delta_count") or 0),
            highest_impact=str(r.get("highest_impact") or NO_DELTA),
        )
        rows.append({**r, "rollout_signal": signal})
    return {"rollout_summary": rows, "non_blocking": True}


def adapt_reminder_semantic_interpretation(semantic_state: str, *, mode: str = LEGACY_RUNTIME_INTERPRETATION) -> Dict[str, Any]:
    return _adapt_for_consumer(REMINDER_ENGINE, semantic_state, mode=mode)


def adapt_report_export_semantic_interpretation(
    semantic_state: str, *, mode: str = LEGACY_RUNTIME_INTERPRETATION
) -> Dict[str, Any]:
    return _adapt_for_consumer(REPORT_EXPORT, semantic_state, mode=mode)


def adapt_portfolio_score_semantic_interpretation(
    semantic_state: str, *, mode: str = LEGACY_RUNTIME_INTERPRETATION
) -> Dict[str, Any]:
    return _adapt_for_consumer(PORTFOLIO_SCORE, semantic_state, mode=mode)


def build_semantic_adapter_snapshot() -> Dict[str, Any]:
    rows = [
        adapt_reminder_semantic_interpretation("OPERATIONALLY_OPEN", mode=HYBRID_AUDIT_INTERPRETATION),
        adapt_reminder_semantic_interpretation("EXPIRY_REVIEW_REQUIRED", mode=HYBRID_AUDIT_INTERPRETATION),
        adapt_portfolio_score_semantic_interpretation("PARTIALLY_COMPLETE", mode=HYBRID_AUDIT_INTERPRETATION),
        adapt_portfolio_score_semantic_interpretation(
            "ASSESSMENT_FOLLOWUP_REQUIRED", mode=HYBRID_AUDIT_INTERPRETATION
        ),
        adapt_report_export_semantic_interpretation("EXPIRY_REVIEW_REQUIRED", mode=HYBRID_AUDIT_INTERPRETATION),
        adapt_report_export_semantic_interpretation("OPERATIONALLY_OPEN", mode=HYBRID_AUDIT_INTERPRETATION),
    ]
    matrix = [
        {
            "consumer": r["consumer"],
            "semantic_state": r["semantic_state"],
            "legacy_interpretation": r["legacy_interpretation"],
            "semantic_interpretation": r["semantic_interpretation"],
            "delta": r["delta_detected"],
            "impact": r["delta_classification"],
        }
        for r in rows
    ]
    return {
        "phase": "Semantic-State Consumer Precedence Adapters Phase 4",
        "audit_mode": SEMANTIC_STATE_ADAPTER_AUDIT_MODE,
        "runtime_enforcement": SEMANTIC_STATE_RUNTIME_ENFORCEMENT,
        "non_blocking": True,
        "matrix": matrix,
    }
