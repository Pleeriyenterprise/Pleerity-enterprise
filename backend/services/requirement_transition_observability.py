"""
Requirement evidence-authority sync: transition correlation, trace, and operational snapshots.

Additive only — does not change authority computation, gap upserts, or scoring semantics.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Mapping, MutableMapping, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

# Transition outcome labels (operational visibility; not enforcement)
TRANSITION_APPLIED = "TRANSITION_APPLIED"
TRANSITION_NOOP = "TRANSITION_NOOP"
TRANSITION_REPLAY_DETECTED = "TRANSITION_REPLAY_DETECTED"
TRANSITION_PARTIAL_PROPAGATION = "TRANSITION_PARTIAL_PROPAGATION"
TRANSITION_DEGRADED_DOWNSTREAM = "TRANSITION_DEGRADED_DOWNSTREAM"
TRANSITION_PENDING_RECONCILIATION = "TRANSITION_PENDING_RECONCILIATION"
TRANSITION_FAILED = "TRANSITION_FAILED"

# --- Phase 7: automated / system / operational lineage (distinct from human review paths) ---

TRANSITION_ORIGIN_FAMILY_OUTCOME_ENGINE = "OUTCOME_ENGINE_SYNC"
TRANSITION_ORIGIN_FAMILY_DOCUMENT_TOUCH = "DOCUMENT_TOUCH_SYNC"
TRANSITION_ORIGIN_FAMILY_BACKFILL = "BACKFILL_AUTHORITY_SYNC"
TRANSITION_ORIGIN_FAMILY_SYSTEM_RECONCILIATION = "SYSTEM_RECONCILIATION_SYNC"
TRANSITION_ORIGIN_FAMILY_OPTIONAL_AUTOMATION = "OPTIONAL_FUTURE_AUTOMATION_SYNC"


def transition_origin_outcome_engine(suffix: str) -> str:
    return f"{TRANSITION_ORIGIN_FAMILY_OUTCOME_ENGINE}:{suffix}"


def transition_origin_document_touch(suffix: str) -> str:
    return f"{TRANSITION_ORIGIN_FAMILY_DOCUMENT_TOUCH}:{suffix}"


def transition_origin_backfill(suffix: str) -> str:
    return f"{TRANSITION_ORIGIN_FAMILY_BACKFILL}:{suffix}"


def transition_origin_system_reconciliation(suffix: str) -> str:
    return f"{TRANSITION_ORIGIN_FAMILY_SYSTEM_RECONCILIATION}:{suffix}"


def transition_origin_optional_future_automation(suffix: str) -> str:
    return f"{TRANSITION_ORIGIN_FAMILY_OPTIONAL_AUTOMATION}:{suffix}"


def automated_outcome_engine_traces(traces: Sequence[Mapping[str, Any]]) -> List[Mapping[str, Any]]:
    prefix = f"{TRANSITION_ORIGIN_FAMILY_OUTCOME_ENGINE}:"
    return [t for t in traces if str(t.get("transition_origin") or "").startswith(prefix)]


def generic_document_touch_traces(traces: Sequence[Mapping[str, Any]]) -> List[Mapping[str, Any]]:
    prefix = f"{TRANSITION_ORIGIN_FAMILY_DOCUMENT_TOUCH}:"
    return [t for t in traces if str(t.get("transition_origin") or "").startswith(prefix)]


def backfill_authority_traces(traces: Sequence[Mapping[str, Any]]) -> List[Mapping[str, Any]]:
    prefix = f"{TRANSITION_ORIGIN_FAMILY_BACKFILL}:"
    return [t for t in traces if str(t.get("transition_origin") or "").startswith(prefix)]


def system_reconciliation_traces(traces: Sequence[Mapping[str, Any]]) -> List[Mapping[str, Any]]:
    prefix = f"{TRANSITION_ORIGIN_FAMILY_SYSTEM_RECONCILIATION}:"
    return [t for t in traces if str(t.get("transition_origin") or "").startswith(prefix)]


def ensure_requirement_transition_correlation_id(
    *,
    requirement_id: str,
    property_id: Optional[str],
    client_id: Optional[str],
    correlation_id: Optional[str],
) -> str:
    raw = (correlation_id or "").strip()
    if raw:
        return raw
    cid = (client_id or "").strip() or "unknown_client"
    pid = (property_id or "").strip() or "unknown_property"
    return f"REQ_TRANSITION:{requirement_id}:{pid}:{cid}:{uuid.uuid4().hex}"


def normalize_requirement_transition_context(
    *,
    correlation_id: str,
    transition_origin: Optional[str],
    requirement_id: str,
    property_id: Optional[str],
    client_id: Optional[str],
) -> Dict[str, Any]:
    return {
        "correlation_id": correlation_id,
        "transition_origin": (transition_origin or "").strip() or "unspecified",
        "requirement_id": str(requirement_id),
        "property_id": property_id,
        "client_id": client_id,
    }


def _authority_signature(requirement: Mapping[str, Any]) -> Tuple[Any, ...]:
    ea = requirement.get("evidence_authority") or {}
    st = ea.get("state")
    if st is not None and isinstance(st, str):
        st = st.strip().upper()
    return (
        requirement.get("status"),
        requirement.get("due_date"),
        requirement.get("evidence_state"),
        ea.get("version"),
        st,
    )


def classify_transition_outcome(
    *,
    before_sig: Tuple[Any, ...],
    after_requirement: Mapping[str, Any],
    gap_errors: Sequence[Any],
    gap_exception: Optional[Exception],
    transition_origin: Optional[str] = None,
) -> str:
    after_sig = _authority_signature(after_requirement)
    noop = before_sig == after_sig
    if gap_exception is not None:
        return TRANSITION_DEGRADED_DOWNSTREAM
    if gap_errors:
        if noop:
            return TRANSITION_PENDING_RECONCILIATION
        return TRANSITION_PARTIAL_PROPAGATION
    if noop:
        to = (transition_origin or "").lower()
        if "replay" in to or "reconcile" in to:
            return TRANSITION_REPLAY_DETECTED
        return TRANSITION_NOOP
    return TRANSITION_APPLIED


def build_requirement_transition_trace(
    *,
    transition_id: str,
    correlation_id: str,
    transition_origin: Optional[str],
    requirement_id: str,
    property_id: Optional[str],
    client_id: Optional[str],
    before_requirement: Mapping[str, Any],
    after_requirement: Mapping[str, Any],
    gap_errors: Sequence[Any],
    gap_exception: Optional[Exception],
    downstream_propagation: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    before_sig = _authority_signature(before_requirement)
    outcome = classify_transition_outcome(
        before_sig=before_sig,
        after_requirement=after_requirement,
        gap_errors=gap_errors,
        gap_exception=gap_exception,
        transition_origin=transition_origin,
    )
    noop = before_sig == _authority_signature(after_requirement)
    targets = list(downstream_propagation)
    return {
        "transition_id": transition_id,
        "correlation_id": correlation_id,
        "transition_origin": (transition_origin or "").strip() or "unspecified",
        "requirement_id": str(requirement_id),
        "property_id": property_id,
        "client_id": client_id,
        "previous_state": before_requirement.get("status"),
        "resulting_state": after_requirement.get("status"),
        "semantic_state": after_requirement.get("semantic_state"),
        "state_reason": after_requirement.get("state_reason"),
        "duplicate_transition_possible": bool(noop),
        "replay_possible": bool(noop),
        "downstream_trigger_count": len(targets),
        "downstream_trigger_targets": targets,
        "partial_downstream_failure": bool(gap_errors),
        "retry_possible": bool(gap_errors or gap_exception is not None),
        "transition_outcome": outcome,
        "downstream_propagation": targets,
        "replay_chain_detected": False,
        "repeated_transition_origin": False,
        "repeated_correlation_seen": False,
        "downstream_retrigger_possible": False,
        "stale_transition_replayed": False,
        "non_blocking": True,
    }


def build_transition_fanout_trace(**kwargs: Any) -> Dict[str, Any]:
    """Alias for high-fanout documentation; identical to ``build_requirement_transition_trace``."""
    return build_requirement_transition_trace(**kwargs)


def build_requirement_transition_operational_snapshot(
    *,
    transition_traces: Sequence[Mapping[str, Any]],
    generated_at_iso: str,
) -> Dict[str, Any]:
    keys = sorted(range(len(transition_traces)))
    rows = [dict(transition_traces[i]) for i in keys]
    rows.sort(key=lambda r: (r.get("requirement_id"), r.get("transition_id")))
    return {
        "schema_version": "requirement_transition_operational_snapshot_v1",
        "generated_at": generated_at_iso,
        "transition_traces": rows,
        "audit_only_visibility": True,
        "non_blocking": True,
    }


def build_transition_health_summary(traces: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    """Roll up counts from in-memory traces (deterministic for sorted input)."""
    by_outcome: Dict[str, int] = {}
    degraded = 0
    partial = 0
    missing_corr = 0
    for t in traces:
        oc = str(t.get("transition_outcome") or "")
        by_outcome[oc] = by_outcome.get(oc, 0) + 1
        if oc in (TRANSITION_DEGRADED_DOWNSTREAM, TRANSITION_PARTIAL_PROPAGATION):
            degraded += 1
        if t.get("partial_downstream_failure"):
            partial += 1
        if not (t.get("correlation_id") or "").strip():
            missing_corr += 1
    return {
        "outcome_histogram": dict(sorted(by_outcome.items())),
        "degraded_or_partial_propagation_count": degraded,
        "partial_downstream_failure_count": partial,
        "missing_correlation_count": missing_corr,
        "health_posture": "NON_BLOCKING_OBSERVABILITY_ONLY",
    }


def build_transition_reconciliation_markers(traces: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    markers: List[Dict[str, str]] = []
    for t in traces:
        rid = str(t.get("requirement_id") or "")
        if t.get("transition_outcome") == TRANSITION_PENDING_RECONCILIATION:
            markers.append({"requirement_id": rid, "code": "GAP_PENDING_RECONCILIATION", "severity": "INFO"})
        if t.get("transition_outcome") == TRANSITION_DEGRADED_DOWNSTREAM:
            markers.append({"requirement_id": rid, "code": "GAP_SYNC_EXCEPTION", "severity": "WARNING"})
    return {"markers": sorted(markers, key=lambda m: (m["requirement_id"], m["code"])), "non_blocking": True}


# --- Phase 4: high-fanout enqueue / regen visibility (additive; no queue semantics change) ---

ENQUEUE_ACCEPTED = "ENQUEUE_ACCEPTED"
ENQUEUE_DUPLICATE_SUPPRESSED = "ENQUEUE_DUPLICATE_SUPPRESSED"
ENQUEUE_PARTIAL_FAILURE = "ENQUEUE_PARTIAL_FAILURE"
ENQUEUE_DEGRADED = "ENQUEUE_DEGRADED"
ENQUEUE_SKIPPED = "ENQUEUE_SKIPPED"
ENQUEUE_FAILED = "ENQUEUE_FAILED"

# Phase 2A: RST core backbone propagation continuity (observability only; non-enforcing).
PROPAGATION_CONTINUITY_ACTIVE = "PROPAGATION_CONTINUITY_ACTIVE"
PROPAGATION_CONTINUITY_SKIPPED_REGISTRY = "PROPAGATION_CONTINUITY_SKIPPED_REGISTRY"
PROPAGATION_CONTINUITY_SKIPPED_COMPOSITE_CHILD = "PROPAGATION_CONTINUITY_SKIPPED_COMPOSITE_CHILD"
DOWNSTREAM_PROPAGATION_PENDING = "DOWNSTREAM_PROPAGATION_PENDING"
DOWNSTREAM_PROPAGATION_BLOCKED = "DOWNSTREAM_PROPAGATION_BLOCKED"
RECONCILIATION_CONTINUITY_VISIBLE = "RECONCILIATION_CONTINUITY_VISIBLE"
RECONCILIATION_CONTINUITY_BLOCKED = "RECONCILIATION_CONTINUITY_BLOCKED"
REPLAY_CONTINUITY_VISIBLE = "REPLAY_CONTINUITY_VISIBLE"
DEGRADED_PROPAGATION_CONTINUITY_VISIBLE = "DEGRADED_PROPAGATION_CONTINUITY_VISIBLE"


def merge_rst_core_backbone_activation_into_fanout(
    fanout: MutableMapping[str, Any],
    gate_ctx: Mapping[str, Any],
    *,
    propagation_continuity: str,
) -> None:
    """Attach composite backbone activation metadata to a transition fanout trace (mutates)."""
    permitted = bool(gate_ctx.get("permitted"))
    fanout["rst_core_backbone_activation"] = dict(
        sorted(
            {
                "activation_family": gate_ctx.get("activation_family"),
                "activation_governance_version": gate_ctx.get("activation_governance_version"),
                "activation_guard_result": gate_ctx.get("activation_guard_result"),
                "activation_reason": gate_ctx.get("activation_reason"),
                "activation_scope": gate_ctx.get("activation_scope"),
                "activation_state": gate_ctx.get("activation_state"),
                "child_compliance_recalc_permitted": bool(
                    (gate_ctx.get("child_compliance_recalc_gate") or {}).get("permitted")
                ),
                "child_regeneration_recalc_permitted": bool(
                    (gate_ctx.get("child_regeneration_recalc_gate") or {}).get("permitted")
                ),
                "degraded_propagation_continuity": DEGRADED_PROPAGATION_CONTINUITY_VISIBLE,
                "downstream_propagation_state": DOWNSTREAM_PROPAGATION_PENDING
                if permitted
                else DOWNSTREAM_PROPAGATION_BLOCKED,
                "permitted": permitted,
                "propagation_continuity": propagation_continuity,
                "propagation_skipped_visibility": not permitted,
                "registry_ceiling": gate_ctx.get("registry_ceiling"),
                "reconciliation_continuity": RECONCILIATION_CONTINUITY_VISIBLE
                if permitted
                else RECONCILIATION_CONTINUITY_BLOCKED,
                "replay_continuity": REPLAY_CONTINUITY_VISIBLE,
            }.items(),
            key=lambda kv: str(kv[0]),
        )
    )


def normalize_transition_fanout_context(
    *,
    base_correlation_id: str,
    transition_origin: str,
    requirement_id: str,
    property_id: Optional[str],
    client_id: Optional[str],
) -> Dict[str, Any]:
    """Normalize fields for fanout logging / downstream rows (planning helper)."""
    return normalize_requirement_transition_context(
        correlation_id=base_correlation_id,
        transition_origin=transition_origin,
        requirement_id=requirement_id,
        property_id=property_id,
        client_id=client_id,
    )


def classify_enqueue_outcome(
    *,
    attempted: bool,
    enqueue_result: Any = None,
    enqueue_exc: Optional[Exception] = None,
    duplicate_suppression_reason: Optional[str] = None,
) -> Tuple[str, Optional[bool], Optional[str]]:
    """
    Return (enqueue_outcome, enqueue_succeeded, duplicate_reason_for_row).

    ``enqueue_result`` may be bool, ``EnqueueComplianceRecalcResult``, or a mapping (risk regen).
    """
    if not attempted:
        return ENQUEUE_SKIPPED, None, None
    if enqueue_exc is not None:
        return ENQUEUE_FAILED, False, None
    if enqueue_result is None:
        return ENQUEUE_SKIPPED, None, None

    try:
        from services.compliance_recalc_queue import EnqueueComplianceRecalcResult as _ECR
    except ImportError:
        _ECR = None  # type: ignore[misc,assignment]

    if _ECR is not None and isinstance(enqueue_result, _ECR):
        if getattr(enqueue_result, "activation_skipped", False):
            ar = getattr(enqueue_result, "activation_reason", None) or "activation_gate"
            return ENQUEUE_SKIPPED, False, str(ar)
        dup = enqueue_result.duplicate_suppression_reason or duplicate_suppression_reason
        if enqueue_result.enqueued:
            if enqueue_result.regeneration_error:
                return ENQUEUE_PARTIAL_FAILURE, True, enqueue_result.regeneration_error
            return ENQUEUE_ACCEPTED, True, None
        if dup:
            return ENQUEUE_DUPLICATE_SUPPRESSED, False, dup
        if enqueue_result.regeneration_error:
            return ENQUEUE_FAILED, False, enqueue_result.regeneration_error
        return ENQUEUE_DUPLICATE_SUPPRESSED, False, dup or "enqueue_returned_false"

    if isinstance(enqueue_result, bool):
        if enqueue_result:
            return ENQUEUE_ACCEPTED, True, None
        return ENQUEUE_DUPLICATE_SUPPRESSED, False, duplicate_suppression_reason or "enqueue_returned_false"

    if isinstance(enqueue_result, Mapping):
        if enqueue_result.get("activation_skipped"):
            ar = enqueue_result.get("activation_reason") or "activation_gate"
            return ENQUEUE_SKIPPED, False, str(ar)
        if enqueue_result.get("queued") is True and enqueue_result.get("merged") is True:
            return ENQUEUE_DEGRADED, True, "risk_regen_debounce_merge"
        if enqueue_result.get("queued") is True:
            return ENQUEUE_ACCEPTED, True, None
        if enqueue_result.get("queued") is False:
            return ENQUEUE_FAILED, False, None
        return ENQUEUE_PARTIAL_FAILURE, False, "unknown_risk_regen_shape"

    return ENQUEUE_DEGRADED, False, "unknown_enqueue_result_shape"


# Optional downstream-row keys for replay / support forensics (never client-facing API contracts).
_REPLAY_SUPPORT_CONTEXT_KEYS = frozenset(
    {
        "idempotency_boundary",
        "enqueue_property_id",
        "resolved_queue_correlation_id",
        "replay_duplicate_enqueue_safe",
    }
)


def attach_downstream_trigger_observation(
    trace: MutableMapping[str, Any],
    *,
    downstream_target: str,
    trigger_mode: str,
    propagation_stage: str,
    downstream_correlation_id: Optional[str] = None,
    trigger_origin: Optional[str] = None,
    enqueue_attempted: bool = True,
    enqueue_result: Any = None,
    enqueue_exc: Optional[Exception] = None,
    duplicate_suppression_reason: Optional[str] = None,
    reconciliation_recommended: bool = False,
    degraded_possible: bool = False,
    activation_gate_overlay: Optional[Mapping[str, Any]] = None,
    replay_support_context: Optional[Mapping[str, Any]] = None,
) -> None:
    """Append a downstream row and refresh counters on an existing transition trace dict (mutates)."""
    trace.setdefault("replay_chain_detected", False)
    trace.setdefault("repeated_transition_origin", False)
    trace.setdefault("repeated_correlation_seen", False)
    trace.setdefault("downstream_retrigger_possible", False)
    trace.setdefault("stale_transition_replayed", False)

    outcome, succeeded, dup_reason = classify_enqueue_outcome(
        attempted=enqueue_attempted,
        enqueue_result=enqueue_result,
        enqueue_exc=enqueue_exc,
        duplicate_suppression_reason=duplicate_suppression_reason,
    )
    rec_recommended = bool(
        reconciliation_recommended
        or outcome == ENQUEUE_DUPLICATE_SUPPRESSED
        or trace.get("partial_downstream_failure")
    )
    row: Dict[str, Any] = {
        "downstream_target": downstream_target,
        "trigger_mode": trigger_mode,
        "enqueue_attempted": enqueue_attempted,
        "enqueue_succeeded": succeeded,
        "enqueue_outcome": outcome,
        "duplicate_suppression_reason": dup_reason,
        "propagation_stage": propagation_stage,
        "reconciliation_recommended": rec_recommended,
        "degraded_possible": degraded_possible or outcome in (ENQUEUE_DEGRADED, ENQUEUE_PARTIAL_FAILURE, ENQUEUE_FAILED),
        "downstream_correlation_id": downstream_correlation_id,
        "trigger_origin": trigger_origin,
        "replay_chain_detected": bool(trace.get("replay_chain_detected")),
        "document_replacement_detected": bool(trace.get("document_replacement_detected")),
        "verification_replay_possible": bool(trace.get("verification_replay_possible")),
        "revert_retrigger_possible": bool(trace.get("revert_retrigger_possible")),
        "stale_document_transition_possible": bool(trace.get("stale_document_transition_possible")),
        "review_chain_reentry_detected": bool(trace.get("review_chain_reentry_detected")),
        "admin_override_possible": bool(trace.get("admin_override_possible")),
        "review_reversal_possible": bool(trace.get("review_reversal_possible")),
        "reviewer_retrigger_possible": bool(trace.get("reviewer_retrigger_possible")),
        "reassignment_replay_possible": bool(trace.get("reassignment_replay_possible")),
        "authority_override_replay_possible": bool(trace.get("authority_override_replay_possible")),
    }
    if trace.get("document_id"):
        row["document_id"] = str(trace.get("document_id"))
    if trace.get("review_id"):
        row["review_id"] = str(trace.get("review_id"))
    if enqueue_exc is not None:
        row["error_type"] = type(enqueue_exc).__name__
    row["automated_transition_possible"] = bool(trace.get("automated_transition_possible"))
    row["generic_touch_sync"] = bool(trace.get("generic_touch_sync"))
    row["reconciliation_sync_possible"] = bool(trace.get("reconciliation_sync_possible"))
    if activation_gate_overlay:
        for ok, ov in activation_gate_overlay.items():
            if ov is not None:
                row[str(ok)] = ov
    row["backfill_replay_possible"] = bool(trace.get("backfill_replay_possible"))
    row["system_reentry_possible"] = bool(trace.get("system_reentry_possible"))
    if replay_support_context:
        for rk, rv in replay_support_context.items():
            if rk in _REPLAY_SUPPORT_CONTEXT_KEYS and rv is not None:
                row[str(rk)] = rv
    try:
        from services.compliance_recalc_queue import EnqueueComplianceRecalcResult as _ECR2

        if isinstance(enqueue_result, _ECR2) and (
            getattr(enqueue_result, "activation_state", None)
            or getattr(enqueue_result, "activation_guard_result", None)
        ):
            if getattr(enqueue_result, "activation_state", None):
                row["activation_state"] = enqueue_result.activation_state
            if getattr(enqueue_result, "activation_reason", None):
                row["activation_reason"] = enqueue_result.activation_reason
            if getattr(enqueue_result, "activation_scope", None):
                row["activation_scope"] = enqueue_result.activation_scope
            if getattr(enqueue_result, "activation_family", None):
                row["activation_family"] = enqueue_result.activation_family
            if getattr(enqueue_result, "activation_guard_result", None):
                row["activation_guard_result"] = enqueue_result.activation_guard_result
            if getattr(enqueue_result, "activation_governance_version", None):
                row["activation_governance_version"] = enqueue_result.activation_governance_version
    except ImportError:
        pass
    if isinstance(enqueue_result, Mapping) and (
        enqueue_result.get("activation_skipped")
        or enqueue_result.get("activation_state")
        or enqueue_result.get("activation_guard_result")
    ):
        if enqueue_result.get("activation_state"):
            row["activation_state"] = enqueue_result.get("activation_state")
        if enqueue_result.get("activation_reason"):
            row["activation_reason"] = enqueue_result.get("activation_reason")
        if enqueue_result.get("activation_scope"):
            row["activation_scope"] = enqueue_result.get("activation_scope")
        if enqueue_result.get("activation_family"):
            row["activation_family"] = enqueue_result.get("activation_family")
        if enqueue_result.get("activation_guard_result"):
            row["activation_guard_result"] = enqueue_result.get("activation_guard_result")
        if enqueue_result.get("activation_governance_version"):
            row["activation_governance_version"] = enqueue_result.get("activation_governance_version")
    targets = trace.setdefault("downstream_trigger_targets", [])
    targets.append(row)
    trace["downstream_propagation"] = targets
    trace["downstream_trigger_count"] = len(targets)
    if succeeded is True:
        trace["downstream_retrigger_possible"] = True

    try:
        from utils.compliance_fanout_log import compliance_fanout_extra

        _to = str(trace.get("transition_origin") or "")
        if _to.startswith(TRANSITION_ORIGIN_FAMILY_OUTCOME_ENGINE):
            _op = "automated_outcome_transition_fanout"
        elif _to.startswith(TRANSITION_ORIGIN_FAMILY_DOCUMENT_TOUCH):
            _op = "generic_touch_transition_fanout"
        elif _to.startswith(TRANSITION_ORIGIN_FAMILY_BACKFILL):
            _op = "backfill_transition_fanout"
        elif _to.startswith(TRANSITION_ORIGIN_FAMILY_SYSTEM_RECONCILIATION):
            _op = "system_reconciliation_transition_fanout"
        elif "routes.evidence_review" in _to:
            _op = "evidence_review_transition_fanout"
        elif "routes.admin" in _to:
            _op = "admin_transition_fanout"
        elif trace.get("document_id"):
            _op = "document_transition_fanout"
        else:
            _op = "requirement_transition_fanout"

        logger.info(
            "compliance_fanout: transition_downstream_row requirement_id=%s target=%s outcome=%s",
            trace.get("requirement_id"),
            downstream_target,
            outcome,
            extra=compliance_fanout_extra(
                op=_op,
                stage="downstream_row",
                client_id=str(trace.get("client_id") or "") or None,
                property_id=str(trace.get("property_id") or "") or None,
                requirement_id=str(trace.get("requirement_id") or "") or None,
                document_id=str(trace.get("document_id") or "").strip() or None,
                review_id=str(trace.get("review_id") or "").strip() or None,
                correlation_id=str(trace.get("correlation_id") or "") or None,
                transition_id=str(trace.get("transition_id") or "") or None,
                transition_origin=str(trace.get("transition_origin") or "") or None,
                downstream_target=downstream_target,
                enqueue_outcome=outcome,
                duplicate_suppression_reason=dup_reason,
                propagation_stage=propagation_stage,
                replay_chain_detected=bool(trace.get("replay_chain_detected")),
                degraded_possible=bool(row.get("degraded_possible")),
                automated_transition_possible=(
                    bool(trace["automated_transition_possible"]) if "automated_transition_possible" in trace else None
                ),
                generic_touch_sync=(bool(trace["generic_touch_sync"]) if "generic_touch_sync" in trace else None),
                reconciliation_sync_possible=(
                    bool(trace["reconciliation_sync_possible"]) if "reconciliation_sync_possible" in trace else None
                ),
                backfill_replay_possible=(
                    bool(trace["backfill_replay_possible"]) if "backfill_replay_possible" in trace else None
                ),
                system_reentry_possible=(
                    bool(trace["system_reentry_possible"]) if "system_reentry_possible" in trace else None
                ),
                admin_override_possible=(
                    bool(trace["admin_override_possible"]) if "admin_override_possible" in trace else None
                ),
                review_reversal_possible=(
                    bool(trace["review_reversal_possible"]) if "review_reversal_possible" in trace else None
                ),
                reviewer_retrigger_possible=(
                    bool(trace["reviewer_retrigger_possible"]) if "reviewer_retrigger_possible" in trace else None
                ),
            ),
        )
    except Exception as log_exc:  # pragma: no cover - observability must not break callers
        logger.debug("transition_fanout log skipped: %s", log_exc)


def merge_fanout_lineage_flags(
    trace: MutableMapping[str, Any],
    *,
    replay_chain_detected: Optional[bool] = None,
    repeated_transition_origin: Optional[bool] = None,
    repeated_correlation_seen: Optional[bool] = None,
    stale_transition_replayed: Optional[bool] = None,
    downstream_retrigger_possible: Optional[bool] = None,
) -> None:
    if replay_chain_detected is not None:
        trace["replay_chain_detected"] = bool(replay_chain_detected)
    if repeated_transition_origin is not None:
        trace["repeated_transition_origin"] = bool(repeated_transition_origin)
    if repeated_correlation_seen is not None:
        trace["repeated_correlation_seen"] = bool(repeated_correlation_seen)
    if stale_transition_replayed is not None:
        trace["stale_transition_replayed"] = bool(stale_transition_replayed)
    if downstream_retrigger_possible is not None:
        trace["downstream_retrigger_possible"] = bool(downstream_retrigger_possible)


def merge_review_admin_lineage_flags(
    trace: MutableMapping[str, Any],
    *,
    review_id: Optional[str] = None,
    admin_override_possible: Optional[bool] = None,
    review_reversal_possible: Optional[bool] = None,
    reviewer_retrigger_possible: Optional[bool] = None,
    reassignment_replay_possible: Optional[bool] = None,
    review_chain_reentry_detected: Optional[bool] = None,
    authority_override_replay_possible: Optional[bool] = None,
) -> None:
    """Human review / admin mutation hints (observability only)."""
    if review_id:
        trace["review_id"] = str(review_id).strip()
    if admin_override_possible is not None:
        trace["admin_override_possible"] = bool(admin_override_possible)
    if review_reversal_possible is not None:
        trace["review_reversal_possible"] = bool(review_reversal_possible)
    if reviewer_retrigger_possible is not None:
        trace["reviewer_retrigger_possible"] = bool(reviewer_retrigger_possible)
    if reassignment_replay_possible is not None:
        trace["reassignment_replay_possible"] = bool(reassignment_replay_possible)
    if review_chain_reentry_detected is not None:
        trace["review_chain_reentry_detected"] = bool(review_chain_reentry_detected)
    if authority_override_replay_possible is not None:
        trace["authority_override_replay_possible"] = bool(authority_override_replay_possible)


def merge_pre_authority_optimistic_requirement_promotion_marker(
    trace: MutableMapping[str, Any],
    *,
    applied: bool,
    basis: str,
    transition_origin: str,
    requirement_id: Optional[str] = None,
) -> None:
    """
    Records a direct ``requirements`` promotion **before** ``sync_requirement_evidence_authority``
    (verify / external-verify paths). Observability and support forensics only — **no** control-flow change.

    **Reconciliation expectation:** authority sync follows in the same request; client-visible truth must
    follow ``project_requirement_row_client_runtime`` / evidence authority (see ``COMPLIANCE_CLIENT_STATUS_AUTHORITY.md``).
    """
    trace["pre_authority_optimistic_requirement_promotion"] = {
        "applied": bool(applied),
        "basis": str(basis or "")[:500],
        "transition_origin": str(transition_origin or "")[:500],
        "requirement_id": str(requirement_id).strip() if requirement_id else None,
        "authority_reconciliation_expected": True,
        "client_truth_after_sync": "requirement_evidence_authority_plus_runtime_projection",
    }


def merge_document_path_lineage_flags(
    trace: MutableMapping[str, Any],
    *,
    document_id: Optional[str] = None,
    document_replacement_detected: Optional[bool] = None,
    verification_replay_possible: Optional[bool] = None,
    revert_retrigger_possible: Optional[bool] = None,
    stale_document_transition_possible: Optional[bool] = None,
) -> None:
    """Additive document-workflow markers (observability only; does not gate behavior)."""
    if document_id:
        trace["document_id"] = str(document_id).strip()
    if document_replacement_detected is not None:
        trace["document_replacement_detected"] = bool(document_replacement_detected)
    if verification_replay_possible is not None:
        trace["verification_replay_possible"] = bool(verification_replay_possible)
    if revert_retrigger_possible is not None:
        trace["revert_retrigger_possible"] = bool(revert_retrigger_possible)
    if stale_document_transition_possible is not None:
        trace["stale_document_transition_possible"] = bool(stale_document_transition_possible)


def merge_automated_system_lineage_flags(
    trace: MutableMapping[str, Any],
    *,
    generic_touch_sync: Optional[bool] = None,
    reconciliation_sync_possible: Optional[bool] = None,
    automated_transition_possible: Optional[bool] = None,
    system_reentry_possible: Optional[bool] = None,
    backfill_replay_possible: Optional[bool] = None,
) -> None:
    """Automated / scripted / generic-touch lineage (observability only; not human-review semantics)."""
    if generic_touch_sync is not None:
        trace["generic_touch_sync"] = bool(generic_touch_sync)
    if reconciliation_sync_possible is not None:
        trace["reconciliation_sync_possible"] = bool(reconciliation_sync_possible)
    if automated_transition_possible is not None:
        trace["automated_transition_possible"] = bool(automated_transition_possible)
    if system_reentry_possible is not None:
        trace["system_reentry_possible"] = bool(system_reentry_possible)
    if backfill_replay_possible is not None:
        trace["backfill_replay_possible"] = bool(backfill_replay_possible)


def document_path_transition_traces(traces: Sequence[Mapping[str, Any]]) -> List[Mapping[str, Any]]:
    """Traces that carry document correlation (Phase 5 rollups)."""
    out: List[Mapping[str, Any]] = []
    for t in traces:
        if str(t.get("document_id") or "").strip():
            out.append(t)
            continue
        to = str(t.get("transition_origin") or "")
        if "routes.documents" in to:
            out.append(t)
    return out


def build_document_transition_operational_snapshot(
    *,
    transition_traces: Sequence[Mapping[str, Any]],
    generated_at_iso: str,
) -> Dict[str, Any]:
    doc_traces = document_path_transition_traces(transition_traces)
    inner = build_requirement_transition_operational_snapshot(
        transition_traces=list(doc_traces),
        generated_at_iso=generated_at_iso,
    )
    inner["schema_version"] = "document_transition_operational_snapshot_v1"
    inner["document_fanout_health"] = build_document_transition_health_summary(transition_traces)
    inner["document_replay_visibility"] = build_document_replay_visibility_summary(transition_traces)
    inner["enqueue_distribution"] = build_transition_enqueue_distribution(doc_traces)
    inner["non_blocking"] = True
    return inner


def build_document_transition_health_summary(traces: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    doc_traces = document_path_transition_traces(traces)
    base = build_fanout_health_summary(doc_traces)
    base["document_trace_count"] = len(doc_traces)
    base["verification_replay_marked"] = sum(1 for t in doc_traces if t.get("verification_replay_possible"))
    base["revert_retrigger_marked"] = sum(1 for t in doc_traces if t.get("revert_retrigger_possible"))
    base["document_replacement_marked"] = sum(1 for t in doc_traces if t.get("document_replacement_detected"))
    base["stale_document_transition_marked"] = sum(1 for t in doc_traces if t.get("stale_document_transition_possible"))
    return base


def review_transition_traces(traces: Sequence[Mapping[str, Any]]) -> List[Mapping[str, Any]]:
    out: List[Mapping[str, Any]] = []
    for t in traces:
        to = str(t.get("transition_origin") or "")
        if "routes.evidence_review" in to:
            out.append(t)
            continue
        if str(t.get("review_id") or "").strip():
            out.append(t)
    return out


def admin_transition_traces(traces: Sequence[Mapping[str, Any]]) -> List[Mapping[str, Any]]:
    out: List[Mapping[str, Any]] = []
    for t in traces:
        if "routes.admin" in str(t.get("transition_origin") or ""):
            out.append(t)
    return out


def build_review_transition_operational_snapshot(
    *,
    transition_traces: Sequence[Mapping[str, Any]],
    generated_at_iso: str,
) -> Dict[str, Any]:
    rev = review_transition_traces(transition_traces)
    inner = build_requirement_transition_operational_snapshot(
        transition_traces=list(rev),
        generated_at_iso=generated_at_iso,
    )
    inner["schema_version"] = "review_transition_operational_snapshot_v1"
    inner["review_fanout_health"] = build_fanout_health_summary(rev)
    inner["review_reentry_visibility"] = build_review_reentry_visibility_summary(transition_traces)
    inner["enqueue_distribution"] = build_transition_enqueue_distribution(rev)
    inner["non_blocking"] = True
    return inner


def build_admin_transition_operational_snapshot(
    *,
    transition_traces: Sequence[Mapping[str, Any]],
    generated_at_iso: str,
) -> Dict[str, Any]:
    adm = admin_transition_traces(transition_traces)
    inner = build_requirement_transition_operational_snapshot(
        transition_traces=list(adm),
        generated_at_iso=generated_at_iso,
    )
    inner["schema_version"] = "admin_transition_operational_snapshot_v1"
    inner["admin_fanout_health"] = build_fanout_health_summary(adm)
    inner["enqueue_distribution"] = build_transition_enqueue_distribution(adm)
    inner["non_blocking"] = True
    return inner


def build_automated_transition_operational_snapshot(
    *,
    transition_traces: Sequence[Mapping[str, Any]],
    generated_at_iso: str,
) -> Dict[str, Any]:
    auto = automated_outcome_engine_traces(transition_traces)
    inner = build_requirement_transition_operational_snapshot(
        transition_traces=list(auto),
        generated_at_iso=generated_at_iso,
    )
    inner["schema_version"] = "automated_transition_operational_snapshot_v1"
    inner["automated_sync_trace_count"] = len(auto)
    inner["automated_fanout_health"] = build_fanout_health_summary(auto)
    inner["enqueue_distribution"] = build_transition_enqueue_distribution(auto)
    inner["system_reentry_visibility"] = build_system_reentry_visibility_summary(auto)
    inner["non_blocking"] = True
    return inner


def build_generic_touch_operational_snapshot(
    *,
    transition_traces: Sequence[Mapping[str, Any]],
    generated_at_iso: str,
) -> Dict[str, Any]:
    g = generic_document_touch_traces(transition_traces)
    inner = build_requirement_transition_operational_snapshot(
        transition_traces=list(g),
        generated_at_iso=generated_at_iso,
    )
    inner["schema_version"] = "generic_touch_operational_snapshot_v1"
    inner["generic_touch_trace_count"] = len(g)
    inner["generic_touch_fanout_health"] = build_fanout_health_summary(g)
    inner["enqueue_distribution"] = build_transition_enqueue_distribution(g)
    inner["generic_touch_noise_indicators"] = {
        "noop_transition_count": sum(1 for t in g if t.get("transition_outcome") == TRANSITION_NOOP),
        "replay_or_reconcile_noop_count": sum(
            1 for t in g if t.get("transition_outcome") in (TRANSITION_REPLAY_DETECTED, TRANSITION_NOOP)
        ),
        "non_blocking": True,
    }
    inner["non_blocking"] = True
    return inner


def build_backfill_transition_operational_snapshot(
    *,
    transition_traces: Sequence[Mapping[str, Any]],
    generated_at_iso: str,
) -> Dict[str, Any]:
    bf = backfill_authority_traces(transition_traces)
    inner = build_requirement_transition_operational_snapshot(
        transition_traces=list(bf),
        generated_at_iso=generated_at_iso,
    )
    inner["schema_version"] = "backfill_transition_operational_snapshot_v1"
    inner["backfill_sync_trace_count"] = len(bf)
    inner["backfill_replay_visibility"] = {
        "backfill_replay_marked_count": sum(1 for t in bf if t.get("backfill_replay_possible")),
        "replay_possible_trace_count": sum(1 for t in bf if t.get("replay_possible")),
        "non_blocking": True,
    }
    inner["backfill_fanout_health"] = build_fanout_health_summary(bf)
    inner["enqueue_distribution"] = build_transition_enqueue_distribution(bf)
    inner["non_blocking"] = True
    return inner


def build_system_reentry_visibility_summary(traces: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    dup_rows = 0
    degraded_rows = 0
    for t in traces:
        for row in t.get("downstream_trigger_targets") or []:
            if row.get("enqueue_outcome") == ENQUEUE_DUPLICATE_SUPPRESSED:
                dup_rows += 1
            if row.get("degraded_possible"):
                degraded_rows += 1
    return {
        "trace_count": len(traces),
        "system_reentry_possible_count": sum(1 for t in traces if t.get("system_reentry_possible")),
        "automated_transition_possible_count": sum(1 for t in traces if t.get("automated_transition_possible")),
        "generic_touch_sync_count": sum(1 for t in traces if t.get("generic_touch_sync")),
        "backfill_replay_possible_count": sum(1 for t in traces if t.get("backfill_replay_possible")),
        "reconciliation_sync_possible_count": sum(1 for t in traces if t.get("reconciliation_sync_possible")),
        "replay_chain_detected_count": sum(1 for t in traces if t.get("replay_chain_detected")),
        "stale_transition_replayed_count": sum(1 for t in traces if t.get("stale_transition_replayed")),
        "downstream_duplicate_enqueue_row_count": dup_rows,
        "downstream_degraded_row_count": degraded_rows,
        "non_blocking": True,
    }


def build_review_reentry_visibility_summary(traces: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    rev = review_transition_traces(traces)
    row_flags = 0
    for t in rev:
        for row in t.get("downstream_trigger_targets") or []:
            if row.get("review_chain_reentry_detected"):
                row_flags += 1
    return {
        "review_trace_count": len(rev),
        "review_chain_reentry_trace_count": sum(1 for t in rev if t.get("review_chain_reentry_detected")),
        "reviewer_retrigger_marked_count": sum(1 for t in rev if t.get("reviewer_retrigger_possible")),
        "review_reversal_marked_count": sum(1 for t in rev if t.get("review_reversal_possible")),
        "admin_override_marked_count": sum(1 for t in rev if t.get("admin_override_possible")),
        "reassignment_replay_marked_count": sum(1 for t in rev if t.get("reassignment_replay_possible")),
        "authority_override_replay_marked_count": sum(1 for t in rev if t.get("authority_override_replay_possible")),
        "downstream_row_review_chain_flag_count": row_flags,
        "non_blocking": True,
    }


def build_document_replay_visibility_summary(traces: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    doc_traces = document_path_transition_traces(traces)
    replay_rows = 0
    for t in doc_traces:
        for row in t.get("downstream_trigger_targets") or []:
            if row.get("replay_chain_detected"):
                replay_rows += 1
    return {
        "document_trace_count": len(doc_traces),
        "trace_replay_chain_detected_count": sum(1 for t in doc_traces if t.get("replay_chain_detected")),
        "trace_repeated_correlation_seen_count": sum(1 for t in doc_traces if t.get("repeated_correlation_seen")),
        "trace_stale_transition_replayed_count": sum(1 for t in doc_traces if t.get("stale_transition_replayed")),
        "downstream_row_replay_flag_count": replay_rows,
        "verification_replay_possible_count": sum(1 for t in doc_traces if t.get("verification_replay_possible")),
        "revert_retrigger_possible_count": sum(1 for t in doc_traces if t.get("revert_retrigger_possible")),
        "non_blocking": True,
    }


def build_transition_fanout_operational_snapshot(
    *,
    transition_traces: Sequence[Mapping[str, Any]],
    generated_at_iso: str,
) -> Dict[str, Any]:
    inner = build_requirement_transition_operational_snapshot(
        transition_traces=transition_traces,
        generated_at_iso=generated_at_iso,
    )
    inner["schema_version"] = "transition_fanout_operational_snapshot_v1"
    inner["fanout_health"] = build_fanout_health_summary(transition_traces)
    inner["enqueue_distribution"] = build_transition_enqueue_distribution(transition_traces)
    return inner


def build_fanout_health_summary(traces: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    base = build_transition_health_summary(traces)
    accepted = 0
    dup = 0
    failed = 0
    degraded = 0
    skipped = 0
    for t in traces:
        for row in t.get("downstream_trigger_targets") or []:
            oc = str(row.get("enqueue_outcome") or "")
            if oc == ENQUEUE_ACCEPTED:
                accepted += 1
            elif oc == ENQUEUE_DUPLICATE_SUPPRESSED:
                dup += 1
            elif oc == ENQUEUE_FAILED:
                failed += 1
            elif oc in (ENQUEUE_DEGRADED, ENQUEUE_PARTIAL_FAILURE):
                degraded += 1
            elif oc == ENQUEUE_SKIPPED:
                skipped += 1
    out = dict(base)
    out["enqueue_accepted_count"] = accepted
    out["enqueue_duplicate_suppressed_count"] = dup
    out["enqueue_failed_count"] = failed
    out["enqueue_degraded_or_partial_count"] = degraded
    out["enqueue_skipped_count"] = skipped
    return out


def build_transition_enqueue_distribution(traces: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    by_target: Dict[str, Dict[str, int]] = {}
    for t in traces:
        for row in t.get("downstream_trigger_targets") or []:
            tgt = str(row.get("downstream_target") or "unknown")
            oc = str(row.get("enqueue_outcome") or "unknown")
            by_target.setdefault(tgt, {})
            by_target[tgt][oc] = by_target[tgt].get(oc, 0) + 1
    sorted_targets = dict(sorted((k, dict(sorted(v.items()))) for k, v in by_target.items()))
    return {"by_downstream_target": sorted_targets}
