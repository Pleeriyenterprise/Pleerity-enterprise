"""
Shared authority mutation observability (admin / evidence review / document paths).

Additive only — queue and authority semantics unchanged.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence

from services.requirement_evidence_authority import sync_requirement_evidence_authority
from services.requirement_transition_observability import (
    PROPAGATION_CONTINUITY_ACTIVE,
    PROPAGATION_CONTINUITY_SKIPPED_REGISTRY,
    attach_downstream_trigger_observation,
    ensure_requirement_transition_correlation_id,
    merge_rst_core_backbone_activation_into_fanout,
)
from services.workflow_runtime_activation_registry import resolve_requirement_state_transition_core_backbone_gate

logger = logging.getLogger(__name__)


def _compliance_recalc_replay_support_context(
    *,
    property_id: str,
    correlation_id: str,
    recalc_result: Any = None,
    recalc_exc: Optional[Exception] = None,
) -> Dict[str, Any]:
    """
    Support/audit metadata for queue idempotency (same request replay / duplicate enqueue).
    Does not change enqueue behaviour.
    """
    resolved = str(correlation_id or "").strip()
    if recalc_exc is None and recalc_result is not None:
        rc = getattr(recalc_result, "correlation_id", None)
        if rc:
            resolved = str(rc).strip() or resolved
    return {
        "idempotency_boundary": "compliance_recalc_queue unique (property_id, correlation_id)",
        "enqueue_property_id": str(property_id or "").strip(),
        "resolved_queue_correlation_id": resolved or None,
        "replay_duplicate_enqueue_safe": True,
    }


async def authority_sync_with_transition_observability(
    db,
    requirement_id: str,
    *,
    property_id: Optional[str],
    client_id: str,
    correlation_base: str,
    transition_origin: str,
    transition_fanout: Dict[str, Any],
) -> None:
    backbone_gate = resolve_requirement_state_transition_core_backbone_gate()
    merge_rst_core_backbone_activation_into_fanout(
        transition_fanout,
        backbone_gate,
        propagation_continuity=PROPAGATION_CONTINUITY_SKIPPED_REGISTRY
        if not backbone_gate.get("permitted")
        else PROPAGATION_CONTINUITY_ACTIVE,
    )
    if not backbone_gate.get("permitted"):
        overlay = {
            "activation_family": backbone_gate.get("activation_family"),
            "activation_governance_version": backbone_gate.get("activation_governance_version"),
            "activation_guard_result": backbone_gate.get("activation_guard_result"),
            "activation_reason": backbone_gate.get("activation_reason"),
            "activation_scope": backbone_gate.get("activation_scope"),
            "activation_state": backbone_gate.get("activation_state"),
        }
        attach_downstream_trigger_observation(
            transition_fanout,
            downstream_target="requirement_state_transition.core_backbone.authority_sync",
            trigger_mode="rst_core_backbone_gate",
            propagation_stage="rst_core_backbone_blocked_pre_authority_sync",
            trigger_origin=transition_origin,
            enqueue_attempted=False,
            enqueue_result=None,
            duplicate_suppression_reason=str(backbone_gate.get("activation_reason") or "rst_core_backbone_blocked"),
            activation_gate_overlay=overlay,
        )
        return

    cid = ensure_requirement_transition_correlation_id(
        requirement_id=str(requirement_id),
        property_id=property_id,
        client_id=client_id,
        correlation_id=correlation_base,
    )
    await sync_requirement_evidence_authority(
        db,
        requirement_id,
        property_id_hint=property_id,
        correlation_id=cid,
        transition_origin=transition_origin,
        transition_observability_out=transition_fanout,
    )


def attach_risk_regen_delegate_row(
    trace: Dict[str, Any],
    recalc_result: Any,
    *,
    trigger_origin: str,
    propagation_stage: str,
) -> None:
    if recalc_result is None:
        return
    err = getattr(recalc_result, "regeneration_error", None) or None
    requeued = bool(getattr(recalc_result, "regeneration_requeued", False))
    if err:
        attach_downstream_trigger_observation(
            trace,
            downstream_target="risk_signal_regen_queue.enqueue_risk_signal_regen",
            trigger_mode="delegate_from_recalc_enqueue",
            propagation_stage=f"{propagation_stage}:risk_regen_error",
            trigger_origin=trigger_origin,
            enqueue_attempted=True,
            enqueue_result=False,
            duplicate_suppression_reason=f"regeneration_delegate_failed:{err}",
            degraded_possible=True,
        )
    elif requeued:
        attach_downstream_trigger_observation(
            trace,
            downstream_target="risk_signal_regen_queue.enqueue_risk_signal_regen",
            trigger_mode="delegate_from_recalc_enqueue",
            propagation_stage=f"{propagation_stage}:risk_regen_delegate_ok",
            trigger_origin=trigger_origin,
            enqueue_attempted=True,
            enqueue_result=True,
        )


async def enqueue_compliance_recalc_with_fanout(
    transition_fanout: Optional[Dict[str, Any]],
    *,
    property_id: str,
    client_id: str,
    trigger_reason: str,
    actor_type: str,
    actor_id: Optional[str],
    correlation_id: str,
    trigger_origin: str,
    propagation_stage: str,
    fanout_op: str = "authority_mutation_fanout",
    broadcast_traces: Optional[Sequence[Optional[Dict[str, Any]]]] = None,
) -> None:
    """Enqueue recalc once; attach downstream rows to ``transition_fanout`` and optional ``broadcast_traces``."""
    from services.compliance_recalc_queue import enqueue_compliance_recalc
    from services.requirement_transition_observability import (
        PROPAGATION_CONTINUITY_ACTIVE as _PCA,
        PROPAGATION_CONTINUITY_SKIPPED_REGISTRY as _PCSR,
    )
    from utils.compliance_fanout_log import compliance_fanout_extra

    targets_pre: List[Optional[Dict[str, Any]]] = []
    if transition_fanout is not None:
        targets_pre.append(transition_fanout)
    if broadcast_traces:
        targets_pre.extend([t for t in broadcast_traces if t is not None])
    backbone_gate = resolve_requirement_state_transition_core_backbone_gate()
    for tf in targets_pre:
        if tf:
            merge_rst_core_backbone_activation_into_fanout(
                tf,
                backbone_gate,
                propagation_continuity=_PCSR if not backbone_gate.get("permitted") else _PCA,
            )

    if targets_pre and not backbone_gate.get("permitted"):
        bb_overlay = {
            "activation_family": backbone_gate.get("activation_family"),
            "activation_governance_version": backbone_gate.get("activation_governance_version"),
            "activation_guard_result": backbone_gate.get("activation_guard_result"),
            "activation_reason": backbone_gate.get("activation_reason"),
            "activation_scope": backbone_gate.get("activation_scope"),
            "activation_state": backbone_gate.get("activation_state"),
        }
        seen_ids2: set[int] = set()
        for tf in targets_pre:
            if not tf:
                continue
            tid = id(tf)
            if tid in seen_ids2:
                continue
            seen_ids2.add(tid)
            if not (tf.get("transition_id") or str(tf.get("correlation_id") or "").strip()):
                continue
            attach_downstream_trigger_observation(
                tf,
                downstream_target="compliance_recalc_queue.enqueue_compliance_recalc",
                trigger_mode="rst_core_backbone_gate",
                propagation_stage=f"{propagation_stage}:rst_core_backbone_blocked_skip_enqueue",
                trigger_origin=trigger_origin,
                enqueue_attempted=False,
                enqueue_result=None,
                duplicate_suppression_reason=str(backbone_gate.get("activation_reason") or "rst_core_backbone_blocked"),
                activation_gate_overlay=bb_overlay,
                replay_support_context=_compliance_recalc_replay_support_context(
                    property_id=property_id,
                    correlation_id=correlation_id,
                ),
            )
            attach_risk_regen_delegate_row(
                tf,
                None,
                trigger_origin=trigger_origin,
                propagation_stage=f"{propagation_stage}:rst_core_backbone_blocked_skip_regen_delegate",
            )
        return

    recalc_result = None
    recalc_exc: Optional[Exception] = None
    try:
        recalc_result = await enqueue_compliance_recalc(
            property_id=property_id,
            client_id=client_id,
            trigger_reason=trigger_reason,
            actor_type=actor_type,
            actor_id=actor_id,
            correlation_id=correlation_id,
        )
    except Exception as exc:
        recalc_exc = exc
        logger.warning(
            "authority_mutation_fanout: enqueue_compliance_recalc failed: %s",
            exc,
            extra=compliance_fanout_extra(
                op=fanout_op,
                stage="recalc_enqueue_exception",
                client_id=client_id,
                property_id=property_id,
                correlation_id=correlation_id,
                trigger_reason=trigger_reason,
                exc_type=type(exc).__name__,
            ),
        )

    targets: List[Optional[Dict[str, Any]]] = []
    if transition_fanout is not None:
        targets.append(transition_fanout)
    if broadcast_traces:
        targets.extend([t for t in broadcast_traces if t is not None])

    seen_ids: set[int] = set()
    for tf in targets:
        if not tf:
            continue
        tid = id(tf)
        if tid in seen_ids:
            continue
        seen_ids.add(tid)
        if not (tf.get("transition_id") or str(tf.get("correlation_id") or "").strip()):
            continue
        attach_downstream_trigger_observation(
            tf,
            downstream_target="compliance_recalc_queue.enqueue_compliance_recalc",
            trigger_mode="async_queue",
            propagation_stage=propagation_stage,
            downstream_correlation_id=getattr(recalc_result, "correlation_id", None)
            if recalc_result is not None
            else correlation_id,
            trigger_origin=trigger_origin,
            enqueue_result=recalc_result,
            enqueue_exc=recalc_exc,
            replay_support_context=_compliance_recalc_replay_support_context(
                property_id=property_id,
                correlation_id=correlation_id,
                recalc_result=recalc_result,
                recalc_exc=recalc_exc,
            ),
        )
        attach_risk_regen_delegate_row(
            tf,
            recalc_result,
            trigger_origin=trigger_origin,
            propagation_stage=propagation_stage,
        )
