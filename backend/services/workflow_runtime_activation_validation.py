"""
Phase 1B: read-only validation of COMPLIANCE_SCORE_RECALC controlled runtime activation.

Advisory only — no enforcement, no queue/worker/registry mutation. Callers supply
snapshots and sample enqueue results (tests use mocks).
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from services.workflow_activation_readiness import (
    FAMILY_COMPLIANCE_SCORE_RECALC,
    FAMILY_REGENERATION_RECALC,
    FAMILY_REQUIREMENT_STATE_TRANSITION_CORE_BACKBONE,
)
from services.workflow_runtime_activation_registry import (
    ACTIVATION_DISABLED,
    ACTIVATION_ENABLED,
    ACTIVATION_GOVERNANCE_VERSION,
    ACTIVATION_LIMITED,
    ACTIVATION_OBSERVE_ONLY,
    GUARD_RESULT_BLOCKED_DEFERRED_FAMILY,
    GUARD_RESULT_BLOCKED_NON_SCOPED_FAMILY,
    GUARD_RESULT_BLOCKED_REGISTRY_DISABLED,
    GUARD_RESULT_BLOCKED_REGISTRY_OBSERVE_ONLY,
    GUARD_RESULT_PERMITTED,
    build_activation_rollout_visibility,
    build_activation_state_summary,
    build_runtime_activation_snapshot,
    build_workflow_activation_context,
    resolve_compliance_recalc_activation_gate,
    resolve_regeneration_recalc_activation_gate,
    resolve_requirement_state_transition_core_backbone_gate,
)

VALIDATION_SCHEMA_VERSION = "workflow_runtime_activation_validation_v1"

# --- Activation validation (overall posture) ---
VALIDATION_CONFIRMED = "VALIDATION_CONFIRMED"
VALIDATION_PARTIAL = "VALIDATION_PARTIAL"
VALIDATION_DEGRADED = "VALIDATION_DEGRADED"
VALIDATION_FAILED = "VALIDATION_FAILED"
VALIDATION_INSUFFICIENT_EVIDENCE = "VALIDATION_INSUFFICIENT_EVIDENCE"

# --- Queue continuity (advisory; no live queue inspection) ---
QUEUE_CONTINUITY_CONFIRMED = "QUEUE_CONTINUITY_CONFIRMED"
QUEUE_CONTINUITY_PARTIAL = "QUEUE_CONTINUITY_PARTIAL"
QUEUE_CONTINUITY_UNVERIFIED = "QUEUE_CONTINUITY_UNVERIFIED"

# --- Rollback posture ---
ROLLBACK_VALIDATED = "ROLLBACK_VALIDATED"
ROLLBACK_PARTIAL = "ROLLBACK_PARTIAL"
ROLLBACK_UNVERIFIED = "ROLLBACK_UNVERIFIED"

# --- Observability ---
OBSERVABILITY_CONFIRMED = "OBSERVABILITY_CONFIRMED"
OBSERVABILITY_PARTIAL = "OBSERVABILITY_PARTIAL"
OBSERVABILITY_GAP = "OBSERVABILITY_GAP"

# --- Drift (advisory) ---
LOW_VALIDATION_DRIFT = "LOW_VALIDATION_DRIFT"
MODERATE_VALIDATION_DRIFT = "MODERATE_VALIDATION_DRIFT"
HIGH_VALIDATION_DRIFT = "HIGH_VALIDATION_DRIFT"
CRITICAL_VALIDATION_DRIFT = "CRITICAL_VALIDATION_DRIFT"

_RECALC_DOWNSTREAM_SUBSTR = "compliance_recalc_queue.enqueue_compliance_recalc"
_REGEN_DOWNSTREAM_SUBSTR = "risk_signal_regen_queue.enqueue_risk_signal_regen"

_PHASE2_LIMITED_ACTIVATION_FAMILIES = frozenset({FAMILY_COMPLIANCE_SCORE_RECALC, FAMILY_REGENERATION_RECALC})

_EXPECTED_RST_CORE_BACKBONE_SCOPE = "requirement_state_transition_core_backbone_only"

_EXPECTED_ACTIVATION_SCOPE = {
    FAMILY_COMPLIANCE_SCORE_RECALC: "compliance_recalc_enqueue_only",
    FAMILY_REGENERATION_RECALC: "risk_signal_regen_enqueue_only",
}

_ACTIVATION_ORDER = {
    ACTIVATION_DISABLED: 0,
    ACTIVATION_OBSERVE_ONLY: 1,
    ACTIVATION_LIMITED: 2,
    ACTIVATION_ENABLED: 3,
}

# Worker-visible job document fields (must stay stable for Phase 1 / 1B).
COMPLIANCE_RECALC_QUEUE_DOC_FIELD_NAMES: Tuple[str, ...] = (
    "property_id",
    "client_id",
    "trigger_reason",
    "actor_type",
    "actor_id",
    "correlation_id",
    "status",
    "attempts",
    "retry_count",
    "retry_exhausted",
    "next_run_at",
    "last_error",
    "created_at",
    "updated_at",
)


def _ordered(ceiling: str) -> int:
    return _ACTIVATION_ORDER.get(ceiling, -1)


def validate_activation_gate_internal_consistency(gate_ctx: Mapping[str, Any]) -> Tuple[str, List[str]]:
    """
    Verify gate dict is self-consistent (deterministic guard semantics).
    Returns (classification, finding_codes).
    """
    findings: List[str] = []
    permitted = bool(gate_ctx.get("permitted"))
    guard = str(gate_ctx.get("activation_guard_result") or "")
    eff = str(gate_ctx.get("activation_state") or "")
    ceiling = str(gate_ctx.get("registry_ceiling") or "")
    fam = str(gate_ctx.get("activation_family") or "")

    if fam not in _PHASE2_LIMITED_ACTIVATION_FAMILIES:
        findings.append("gate_family_not_phase2_limited_activation_family")

    ver = str(gate_ctx.get("activation_governance_version") or "")
    if ver != ACTIVATION_GOVERNANCE_VERSION:
        findings.append("activation_governance_version_mismatch")

    scope = str(gate_ctx.get("activation_scope") or "")
    if scope != _EXPECTED_ACTIVATION_SCOPE.get(fam, ""):
        findings.append("activation_scope_unexpected")

    if permitted and guard != GUARD_RESULT_PERMITTED:
        findings.append("permitted_but_guard_not_permitted")
    if not permitted and guard == GUARD_RESULT_PERMITTED:
        findings.append("not_permitted_but_guard_permitted")

    if eff == ACTIVATION_LIMITED and permitted and ceiling != ACTIVATION_LIMITED:
        findings.append("limited_effective_without_limited_ceiling")
    if eff == ACTIVATION_OBSERVE_ONLY and permitted:
        findings.append("observe_only_effective_but_permitted")
    if eff == ACTIVATION_DISABLED and permitted:
        findings.append("disabled_effective_but_permitted")

    if findings:
        return VALIDATION_FAILED, findings
    return VALIDATION_CONFIRMED, []


def validate_live_compliance_recalc_gate() -> Dict[str, Any]:
    """Read-only: current registry gate + internal consistency (no exceptions expected)."""
    gate = resolve_compliance_recalc_activation_gate()
    cls, findings = validate_activation_gate_internal_consistency(gate)
    return {
        "activation_validation": cls,
        "finding_codes": sorted(findings),
        "gate": dict(gate),
        "schema_version": "activation_gate_validation_v1",
    }


def validate_live_regeneration_recalc_gate() -> Dict[str, Any]:
    """Read-only: regeneration enqueue registry gate + internal consistency."""
    gate = resolve_regeneration_recalc_activation_gate()
    cls, findings = validate_activation_gate_internal_consistency(gate)
    return {
        "activation_validation": cls,
        "finding_codes": sorted(findings),
        "gate": dict(gate),
        "schema_version": "regeneration_activation_gate_validation_v1",
    }


def validate_rst_core_backbone_gate_internal_consistency(gate_ctx: Mapping[str, Any]) -> Tuple[str, List[str]]:
    """Composite RST backbone gate self-consistency (read-only)."""
    findings: List[str] = []
    permitted = bool(gate_ctx.get("permitted"))
    guard = str(gate_ctx.get("activation_guard_result") or "")
    fam = str(gate_ctx.get("activation_family") or "")
    if fam != FAMILY_REQUIREMENT_STATE_TRANSITION_CORE_BACKBONE:
        findings.append("rst_core_backbone_gate_family_mismatch")
    ver = str(gate_ctx.get("activation_governance_version") or "")
    if ver != ACTIVATION_GOVERNANCE_VERSION:
        findings.append("rst_core_backbone_gate_governance_version_mismatch")
    scope = str(gate_ctx.get("activation_scope") or "")
    if scope != _EXPECTED_RST_CORE_BACKBONE_SCOPE:
        findings.append("rst_core_backbone_gate_scope_unexpected")
    if not isinstance(gate_ctx.get("child_compliance_recalc_gate"), Mapping):
        findings.append("rst_core_backbone_missing_child_compliance_gate")
    if not isinstance(gate_ctx.get("child_regeneration_recalc_gate"), Mapping):
        findings.append("rst_core_backbone_missing_child_regeneration_gate")
    if permitted and guard != GUARD_RESULT_PERMITTED:
        findings.append("rst_core_backbone_permitted_but_guard_not_permitted")
    if not permitted and guard == GUARD_RESULT_PERMITTED:
        findings.append("rst_core_backbone_not_permitted_but_guard_permitted")
    if findings:
        return VALIDATION_FAILED, findings
    return VALIDATION_CONFIRMED, []


def validate_live_rst_core_backbone_gate() -> Dict[str, Any]:
    gate = resolve_requirement_state_transition_core_backbone_gate()
    cls, findings = validate_rst_core_backbone_gate_internal_consistency(gate)
    return {
        "activation_validation": cls,
        "finding_codes": sorted(findings),
        "gate": dict(gate),
        "schema_version": "rst_core_backbone_activation_gate_validation_v1",
    }


def validate_rst_core_backbone_convergence_continuity(
    *,
    transition_traces: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Advisory: traces with recalc downstream expose backbone metadata."""
    findings: List[str] = []
    checked = 0
    for tr in transition_traces:
        rows = _downstream_rows(tr)
        if not any(_RECALC_DOWNSTREAM_SUBSTR in str(r.get("downstream_target") or "") for r in rows):
            continue
        checked += 1
        if "rst_core_backbone_activation" not in tr:
            findings.append("rst_core_backbone_trace_missing_activation_blob_with_recalc_downstream")
        blob = tr.get("rst_core_backbone_activation")
        if isinstance(blob, Mapping) and blob.get("propagation_skipped_visibility") is None:
            findings.append("rst_core_backbone_blob_missing_skip_visibility")
    if checked == 0:
        return {
            "activation_validation": VALIDATION_INSUFFICIENT_EVIDENCE,
            "finding_codes": ["rst_core_backbone_no_recalc_downstream_rows_in_traces"],
            "schema_version": "rst_core_backbone_convergence_continuity_v1",
            "traces_checked": 0,
        }
    cls = VALIDATION_CONFIRMED if not findings else VALIDATION_PARTIAL
    return {
        "activation_validation": cls,
        "finding_codes": sorted(set(findings)),
        "schema_version": "rst_core_backbone_convergence_continuity_v1",
        "traces_checked": checked,
    }


def validate_deferred_and_non_scoped_guards() -> Dict[str, Any]:
    """Read-only: blocked families keep deterministic guards (no DB)."""
    findings: List[str] = []
    ctx_def = build_workflow_activation_context("CACHE_INVALIDATION")
    if ctx_def.get("activation_guard_result") != GUARD_RESULT_BLOCKED_DEFERRED_FAMILY:
        findings.append("deferred_family_guard_invariant_broken")
    if ctx_def.get("permitted"):
        findings.append("deferred_family_must_not_permit")

    ctx_ns = build_workflow_activation_context("NOTIFICATION_DISPATCH")
    if ctx_ns.get("activation_guard_result") != GUARD_RESULT_BLOCKED_NON_SCOPED_FAMILY:
        findings.append("non_scoped_family_guard_invariant_broken")
    if ctx_ns.get("permitted"):
        findings.append("non_scoped_family_must_not_permit")

    cls = VALIDATION_CONFIRMED if not findings else VALIDATION_FAILED
    return {
        "activation_validation": cls,
        "finding_codes": sorted(findings),
        "schema_version": "activation_family_guard_validation_v1",
    }


def validate_enqueue_result_continuity(
    *,
    gate_ctx: Mapping[str, Any],
    enqueue_result: Any,
) -> Dict[str, Any]:
    """
    Advisory continuity: enqueue result vs gate (mocked or real result object).

    Does not call the database. Expects EnqueueComplianceRecalcResult-like shape.
    """
    findings: List[str] = []
    q_cont = QUEUE_CONTINUITY_UNVERIFIED
    act_val = VALIDATION_INSUFFICIENT_EVIDENCE

    permitted = bool(gate_ctx.get("permitted"))
    enq = bool(getattr(enqueue_result, "enqueued", False))
    skipped = bool(getattr(enqueue_result, "activation_skipped", False))
    dup = getattr(enqueue_result, "duplicate_suppression_reason", None)
    cid = str(getattr(enqueue_result, "correlation_id", "") or "")

    if not cid:
        findings.append("enqueue_result_missing_correlation_id")

    if permitted:
        if skipped:
            findings.append("permitted_but_activation_skipped")
        if skipped:
            q_cont = QUEUE_CONTINUITY_UNVERIFIED
        elif enq:
            q_cont = QUEUE_CONTINUITY_CONFIRMED
        elif dup:
            q_cont = QUEUE_CONTINUITY_CONFIRMED
        else:
            findings.append("permitted_not_enqueued_without_duplicate_reason")
            q_cont = QUEUE_CONTINUITY_PARTIAL
    else:
        if not skipped:
            findings.append("not_permitted_but_activation_not_skipped_flag")
        if enq:
            findings.append("not_permitted_but_enqueued_true")
        q_cont = QUEUE_CONTINUITY_UNVERIFIED

    # Regeneration delegate: fields exist and are typed consistently (additive).
    if not hasattr(enqueue_result, "regeneration_requeued"):
        findings.append("enqueue_result_missing_regeneration_requeued")
    if not hasattr(enqueue_result, "regeneration_error"):
        findings.append("enqueue_result_missing_regeneration_error")

    # Metadata when gate blocked
    if not permitted:
        for attr in (
            "activation_state",
            "activation_reason",
            "activation_scope",
            "activation_family",
            "activation_guard_result",
            "activation_governance_version",
        ):
            if not getattr(enqueue_result, attr, None):
                findings.append(f"activation_skip_missing_{attr}")
    elif enq or dup:
        for attr in (
            "activation_state",
            "activation_reason",
            "activation_scope",
            "activation_family",
            "activation_guard_result",
            "activation_governance_version",
        ):
            if not getattr(enqueue_result, attr, None):
                findings.append(f"activation_path_missing_{attr}")

    if findings:
        act_val = VALIDATION_FAILED if any(f.startswith("not_permitted_but_enqueued") for f in findings) else VALIDATION_PARTIAL
    else:
        act_val = VALIDATION_CONFIRMED

    return {
        "activation_validation": act_val,
        "finding_codes": sorted(findings),
        "queue_continuity": q_cont,
        "schema_version": "enqueue_continuity_validation_v1",
    }


def validate_risk_signal_regen_enqueue_mapping_continuity(
    *,
    gate_ctx: Mapping[str, Any],
    result_mapping: Mapping[str, Any],
) -> Dict[str, Any]:
    """Advisory continuity for ``enqueue_risk_signal_regen`` dict results vs activation gate."""
    findings: List[str] = []
    q_cont = QUEUE_CONTINUITY_UNVERIFIED
    permitted = bool(gate_ctx.get("permitted"))
    skipped = bool(result_mapping.get("activation_skipped"))
    queued = bool(result_mapping.get("queued"))
    merged = bool(result_mapping.get("merged"))

    if permitted:
        if skipped:
            findings.append("regen_permitted_but_activation_skipped_flag")
        if not queued and not skipped:
            findings.append("regen_permitted_not_queued_without_skip")
        if queued and not skipped:
            q_cont = QUEUE_CONTINUITY_CONFIRMED
    else:
        if not skipped:
            findings.append("regen_not_permitted_but_activation_not_skipped")
        if queued:
            findings.append("regen_not_permitted_but_queued_true")

    if not permitted:
        for key in (
            "activation_state",
            "activation_reason",
            "activation_scope",
            "activation_family",
            "activation_guard_result",
            "activation_governance_version",
        ):
            if not result_mapping.get(key):
                findings.append(f"regen_activation_skip_missing_{key}")
    elif queued or merged:
        for key in (
            "activation_state",
            "activation_reason",
            "activation_scope",
            "activation_family",
            "activation_guard_result",
            "activation_governance_version",
        ):
            if not result_mapping.get(key):
                findings.append(f"regen_activation_path_missing_{key}")

    act_val = VALIDATION_FAILED if any("regen_not_permitted_but_queued" in f for f in findings) else VALIDATION_CONFIRMED if not findings else VALIDATION_PARTIAL
    return {
        "activation_validation": act_val,
        "finding_codes": sorted(findings),
        "queue_continuity": q_cont,
        "schema_version": "regeneration_enqueue_continuity_validation_v1",
    }


def validate_observability_on_regen_enqueue_mapping(result_mapping: Mapping[str, Any]) -> Dict[str, Any]:
    """Activation metadata completeness on risk regen enqueue mapping."""
    findings: List[str] = []
    if result_mapping.get("activation_skipped"):
        if not result_mapping.get("activation_reason"):
            findings.append("regen_skipped_missing_activation_reason")
        if not result_mapping.get("activation_guard_result"):
            findings.append("regen_skipped_missing_activation_guard_result")
    if not result_mapping.get("activation_governance_version"):
        findings.append("regen_missing_activation_governance_version")
    v = str(result_mapping.get("activation_governance_version") or "")
    if v and v != ACTIVATION_GOVERNANCE_VERSION:
        findings.append("regen_activation_governance_version_not_registry_current")

    obs = OBSERVABILITY_CONFIRMED if not findings else OBSERVABILITY_PARTIAL if len(findings) <= 2 else OBSERVABILITY_GAP
    cls = VALIDATION_CONFIRMED if not findings else VALIDATION_PARTIAL
    return {
        "activation_validation": cls,
        "finding_codes": sorted(findings),
        "observability": obs,
        "schema_version": "regeneration_enqueue_observability_validation_v1",
    }


def validate_worker_payload_field_set(*, job_doc_keys: Sequence[str]) -> Dict[str, Any]:
    """Read-only: job document keys match expected worker-facing contract (subset check)."""
    keys = set(str(k) for k in job_doc_keys)
    expected = set(COMPLIANCE_RECALC_QUEUE_DOC_FIELD_NAMES)
    missing = sorted(expected - keys)
    extra = sorted(keys - expected)
    findings: List[str] = []
    if missing:
        findings.append(f"worker_doc_missing_fields:{','.join(missing)}")
    # Extra keys are allowed if additive in future; do not fail validation for extras.
    cls = VALIDATION_CONFIRMED if not missing else VALIDATION_FAILED
    return {
        "activation_validation": cls,
        "finding_codes": findings,
        "extra_doc_keys": extra,
        "schema_version": "worker_payload_continuity_validation_v1",
    }


def validate_observability_on_enqueue_result(enqueue_result: Any) -> Dict[str, Any]:
    """Check activation metadata completeness on a result object."""
    findings: List[str] = []
    obs = OBSERVABILITY_GAP
    if getattr(enqueue_result, "activation_skipped", False):
        if not getattr(enqueue_result, "activation_reason", None):
            findings.append("skipped_missing_activation_reason")
        if not getattr(enqueue_result, "activation_guard_result", None):
            findings.append("skipped_missing_activation_guard_result")
    if not getattr(enqueue_result, "activation_governance_version", None):
        findings.append("missing_activation_governance_version")
    if getattr(enqueue_result, "activation_governance_version", None) not in (None, "", ACTIVATION_GOVERNANCE_VERSION):
        findings.append("activation_governance_version_not_registry_current")

    if not findings:
        obs = OBSERVABILITY_CONFIRMED
    elif len(findings) <= 1:
        obs = OBSERVABILITY_PARTIAL
    else:
        obs = OBSERVABILITY_GAP

    cls = VALIDATION_CONFIRMED if not findings else VALIDATION_PARTIAL
    return {
        "activation_validation": cls,
        "finding_codes": sorted(findings),
        "observability": obs,
        "schema_version": "enqueue_observability_validation_v1",
    }


def _downstream_rows(trace: Mapping[str, Any]) -> List[Mapping[str, Any]]:
    rows = trace.get("downstream_trigger_targets") or trace.get("downstream_propagation") or []
    if not isinstance(rows, list):
        return []
    out: List[Mapping[str, Any]] = []
    for r in rows:
        if isinstance(r, Mapping):
            out.append(r)
    return out


def validate_downstream_activation_metadata(
    *,
    transition_traces: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Rows targeting gated enqueue surfaces should carry activation fields when outcomes imply activation."""
    findings: List[str] = []
    checked_recalc = 0
    checked_regen = 0
    for tr in transition_traces:
        for row in _downstream_rows(tr):
            tgt = str(row.get("downstream_target") or "")
            gated = False
            if _RECALC_DOWNSTREAM_SUBSTR in tgt:
                checked_recalc += 1
                gated = True
            elif _REGEN_DOWNSTREAM_SUBSTR in tgt:
                checked_regen += 1
                gated = True
            if not gated:
                continue
            oc = str(row.get("enqueue_outcome") or "")
            if oc == "ENQUEUE_SKIPPED":
                if not row.get("activation_guard_result"):
                    findings.append("downstream_skipped_missing_activation_guard_result")
                if not row.get("activation_state"):
                    findings.append("downstream_skipped_missing_activation_state")
            elif oc in ("ENQUEUE_ACCEPTED", "ENQUEUE_DUPLICATE_SUPPRESSED", "ENQUEUE_PARTIAL_FAILURE", "ENQUEUE_DEGRADED"):
                if row.get("activation_state") and not row.get("activation_governance_version"):
                    findings.append("downstream_activation_state_without_governance_version")

    checked = checked_recalc + checked_regen
    if checked == 0:
        return {
            "activation_validation": VALIDATION_INSUFFICIENT_EVIDENCE,
            "finding_codes": ["no_gated_downstream_rows_in_traces"],
            "observability": OBSERVABILITY_GAP,
            "recalc_downstream_rows_checked": 0,
            "regen_downstream_rows_checked": 0,
            "schema_version": "downstream_activation_observability_v1",
        }

    obs = OBSERVABILITY_CONFIRMED if not findings else OBSERVABILITY_PARTIAL if len(findings) < 3 else OBSERVABILITY_GAP
    cls = VALIDATION_CONFIRMED if not findings else VALIDATION_PARTIAL
    return {
        "activation_validation": cls,
        "finding_codes": sorted(set(findings)),
        "observability": obs,
        "recalc_downstream_rows_checked": checked_recalc,
        "regen_downstream_rows_checked": checked_regen,
        "schema_version": "downstream_activation_observability_v1",
    }


def validate_governance_runtime_activation_visibility(governance_report: Mapping[str, Any]) -> Dict[str, Any]:
    """Report must embed runtime activation sections aligned on governance version."""
    findings: List[str] = []
    for key in ("runtime_activation_snapshot", "runtime_activation_state_summary", "runtime_activation_rollout_visibility"):
        if key not in governance_report:
            findings.append(f"governance_report_missing_{key}")

    rt = governance_report.get("runtime_activation_snapshot")
    ver_report = None
    if isinstance(rt, Mapping):
        ver_report = rt.get("activation_governance_version")
        if not ver_report:
            findings.append("runtime_snapshot_missing_activation_governance_version")
        rows = rt.get("families") or []
        if isinstance(rows, list):
            for r in rows:
                if not isinstance(r, Mapping):
                    continue
                fam = str(r.get("activation_family") or "")
                if fam not in (
                    FAMILY_COMPLIANCE_SCORE_RECALC,
                    FAMILY_REGENERATION_RECALC,
                    FAMILY_REQUIREMENT_STATE_TRANSITION_CORE_BACKBONE,
                ):
                    continue
                if fam == FAMILY_REQUIREMENT_STATE_TRANSITION_CORE_BACKBONE:
                    prefix = "rst_core_backbone"
                else:
                    prefix = "compliance" if fam == FAMILY_COMPLIANCE_SCORE_RECALC else "regeneration"
                rv = str(r.get("activation_governance_version") or "")
                if not rv:
                    findings.append(f"{prefix}_row_missing_activation_governance_version")
                elif ver_report and rv != str(ver_report):
                    findings.append(f"{prefix}_row_version_mismatch_in_snapshot")
        vis = governance_report.get("runtime_activation_rollout_visibility")
        if isinstance(vis, Mapping) and ver_report is not None and vis.get("activation_governance_version") != ver_report:
            findings.append("governance_report_version_alignment_broken")

    obs = OBSERVABILITY_CONFIRMED if not findings else OBSERVABILITY_PARTIAL
    cls = VALIDATION_CONFIRMED if not findings else VALIDATION_FAILED
    return {
        "activation_validation": cls,
        "finding_codes": sorted(set(findings)),
        "observability": obs,
        "schema_version": "governance_runtime_activation_visibility_v1",
    }


def validate_registry_rollback_posture(*, from_ceiling: str, to_ceiling: str) -> Dict[str, Any]:
    """
    Advisory: rollback transitions that reduce exposure without migrations.

    Valid rollbacks: LIMITED→OBSERVE_ONLY, LIMITED→DISABLED, OBSERVE_ONLY→DISABLED.
    """
    findings: List[str] = []
    if _ordered(from_ceiling) < 0 or _ordered(to_ceiling) < 0:
        findings.append("unknown_ceiling_in_rollback_spec")
    if _ordered(to_ceiling) > _ordered(from_ceiling):
        findings.append("rollback_must_not_increase_activation")
    if from_ceiling == to_ceiling:
        findings.append("rollback_no_op_ceiling_unchanged")

    if "rollback_must_not_increase_activation" in findings:
        rb = ROLLBACK_UNVERIFIED
    elif not findings:
        rb = ROLLBACK_VALIDATED
    else:
        rb = ROLLBACK_PARTIAL

    cls = VALIDATION_CONFIRMED if not findings else VALIDATION_PARTIAL
    return {
        "activation_validation": cls,
        "finding_codes": sorted(findings),
        "rollback_posture": rb,
        "schema_version": "activation_rollback_posture_validation_v1",
        "from_ceiling": from_ceiling,
        "to_ceiling": to_ceiling,
    }


def classify_validation_drift(*, finding_codes: Sequence[str]) -> str:
    """Map accumulated finding codes to advisory drift band (deterministic)."""
    codes = set(finding_codes)
    critical_tokens = (
        "not_permitted_but_enqueued",
        "permitted_but_activation_skipped",
        "regen_not_permitted_but_queued_true",
        "rollback_must_not_increase_activation",
    )
    if any(any(tok in c for tok in critical_tokens) for c in codes):
        return CRITICAL_VALIDATION_DRIFT
    if any(
        c.startswith("gate_family_not")
        or c.endswith("_mismatch_in_snapshot")
        or c == "governance_report_version_alignment_broken"
        or c.startswith("regeneration_row_")
        for c in codes
    ):
        return HIGH_VALIDATION_DRIFT
    if codes:
        return MODERATE_VALIDATION_DRIFT
    return LOW_VALIDATION_DRIFT


def build_validation_drift_findings(
    *,
    gate_validation: Mapping[str, Any],
    deferred_validation: Mapping[str, Any],
    regeneration_gate_validation: Optional[Mapping[str, Any]] = None,
    rst_core_backbone_gate_validation: Optional[Mapping[str, Any]] = None,
    observability_report: Optional[Mapping[str, Any]] = None,
    observability_downstream: Optional[Mapping[str, Any]] = None,
    governance_visibility: Optional[Mapping[str, Any]] = None,
    enqueue_continuity_blocks: Optional[Sequence[Mapping[str, Any]]] = None,
) -> Dict[str, Any]:
    """Merge finding codes and classify drift (read-only)."""
    merged: List[str] = []
    for block in (
        gate_validation,
        deferred_validation,
        regeneration_gate_validation or {},
        rst_core_backbone_gate_validation or {},
        observability_report or {},
        observability_downstream or {},
        governance_visibility or {},
    ):
        fc = block.get("finding_codes") or []
        if isinstance(fc, list):
            merged.extend(str(x) for x in fc)
    if enqueue_continuity_blocks:
        for b in enqueue_continuity_blocks:
            if not isinstance(b, Mapping):
                continue
            for sub in ("continuity", "observability"):
                inner = b.get(sub)
                if isinstance(inner, Mapping):
                    fc = inner.get("finding_codes") or []
                    if isinstance(fc, list):
                        merged.extend(str(x) for x in fc)
    merged_sorted = sorted(set(merged))
    drift = classify_validation_drift(finding_codes=merged_sorted)
    return {
        "drift_classification": drift,
        "finding_codes": merged_sorted,
        "schema_version": "activation_validation_drift_v1",
    }


def build_runtime_activation_validation_snapshot(
    *,
    generated_at_iso: str,
    governance_report: Optional[Mapping[str, Any]] = None,
    transition_traces: Optional[Sequence[Mapping[str, Any]]] = None,
    enqueue_samples: Optional[Sequence[Tuple[Mapping[str, Any], Any]]] = None,
    regeneration_enqueue_samples: Optional[Sequence[Tuple[Mapping[str, Any], Mapping[str, Any]]]] = None,
) -> Dict[str, Any]:
    """
    Aggregate read-only validations. Optional governance_report / traces / (gate, result) samples.

    No mutation of registry; uses live resolve + snapshot builders.
    """
    rt_snap = build_runtime_activation_snapshot(generated_at_iso=generated_at_iso)
    gate_live = validate_live_compliance_recalc_gate()
    regen_gate_live = validate_live_regeneration_recalc_gate()
    rst_bb_live = validate_live_rst_core_backbone_gate()
    deferred = validate_deferred_and_non_scoped_guards()

    gov_vis: Optional[Dict[str, Any]] = None
    if governance_report is not None:
        gov_vis = validate_governance_runtime_activation_visibility(governance_report)

    downstream: Optional[Dict[str, Any]] = None
    rst_bb_conv: Optional[Dict[str, Any]] = None
    if transition_traces is not None:
        downstream = validate_downstream_activation_metadata(transition_traces=list(transition_traces))
        rst_bb_conv = validate_rst_core_backbone_convergence_continuity(transition_traces=list(transition_traces))

    enqueue_blocks: List[Dict[str, Any]] = []
    if enqueue_samples:
        for gate_ctx, er in enqueue_samples:
            enqueue_blocks.append(
                {
                    "continuity": validate_enqueue_result_continuity(gate_ctx=dict(gate_ctx), enqueue_result=er),
                    "observability": validate_observability_on_enqueue_result(er),
                }
            )

    regen_enqueue_blocks: List[Dict[str, Any]] = []
    if regeneration_enqueue_samples:
        for gate_ctx, rm in regeneration_enqueue_samples:
            regen_enqueue_blocks.append(
                {
                    "continuity": validate_risk_signal_regen_enqueue_mapping_continuity(
                        gate_ctx=dict(gate_ctx),
                        result_mapping=dict(rm),
                    ),
                    "observability": validate_observability_on_regen_enqueue_mapping(dict(rm)),
                }
            )

    drift = build_validation_drift_findings(
        gate_validation=gate_live,
        deferred_validation=deferred,
        regeneration_gate_validation=regen_gate_live,
        observability_downstream=downstream,
        governance_visibility=gov_vis,
        enqueue_continuity_blocks=(list(enqueue_blocks or []) + list(regen_enqueue_blocks or [])) or None,
    )

    overall = VALIDATION_CONFIRMED
    for b in (gate_live, regen_gate_live, deferred, gov_vis, downstream):
        if not b:
            continue
        v = str(b.get("activation_validation") or "")
        if v == VALIDATION_FAILED:
            overall = VALIDATION_FAILED
            break
        if v == VALIDATION_PARTIAL and overall == VALIDATION_CONFIRMED:
            overall = VALIDATION_PARTIAL
        if v == VALIDATION_INSUFFICIENT_EVIDENCE and overall == VALIDATION_CONFIRMED:
            overall = VALIDATION_INSUFFICIENT_EVIDENCE

    return {
        "activation_governance_version": ACTIVATION_GOVERNANCE_VERSION,
        "deferred_and_scoped_guard_validation": deferred,
        "drift": drift,
        "enqueue_sample_validations": enqueue_blocks,
        "gate_validation": gate_live,
        "generated_at_iso": generated_at_iso,
        "governance_runtime_visibility": gov_vis,
        "overall_activation_validation": overall,
        "regeneration_enqueue_sample_validations": regen_enqueue_blocks,
        "regeneration_recalc_gate_validation": regen_gate_live,
        "rst_core_backbone_convergence_continuity": rst_bb_conv,
        "rst_core_backbone_gate_validation": rst_bb_live,
        "runtime_activation_snapshot": rt_snap,
        "schema_version": VALIDATION_SCHEMA_VERSION,
        "transition_downstream_observability": downstream,
    }


def build_activation_validation_summary(snapshot: Mapping[str, Any]) -> Dict[str, Any]:
    """Counts validation classifications inside a validation snapshot."""
    counts: Dict[str, int] = {}
    for key in (
        "gate_validation",
        "regeneration_recalc_gate_validation",
        "rst_core_backbone_gate_validation",
        "deferred_and_scoped_guard_validation",
        "governance_runtime_visibility",
        "transition_downstream_observability",
        "rst_core_backbone_convergence_continuity",
    ):
        block = snapshot.get(key)
        if not isinstance(block, Mapping):
            continue
        v = str(block.get("activation_validation") or "UNKNOWN")
        counts[v] = counts.get(v, 0) + 1
    for sample in snapshot.get("enqueue_sample_validations") or []:
        if not isinstance(sample, Mapping):
            continue
        for sub in ("continuity", "observability"):
            b = sample.get(sub)
            if isinstance(b, Mapping):
                v = str(b.get("activation_validation") or "UNKNOWN")
                counts[v] = counts.get(v, 0) + 1
    for sample in snapshot.get("regeneration_enqueue_sample_validations") or []:
        if not isinstance(sample, Mapping):
            continue
        for sub in ("continuity", "observability"):
            b = sample.get(sub)
            if isinstance(b, Mapping):
                v = str(b.get("activation_validation") or "UNKNOWN")
                counts[v] = counts.get(v, 0) + 1
    drift = snapshot.get("drift") if isinstance(snapshot.get("drift"), Mapping) else {}
    return {
        "by_activation_validation": dict(sorted(counts.items())),
        "drift_classification": drift.get("drift_classification") if isinstance(drift, Mapping) else None,
        "overall_activation_validation": snapshot.get("overall_activation_validation"),
        "schema_version": "activation_validation_summary_v1",
    }


def build_activation_continuity_summary(snapshot: Mapping[str, Any]) -> Dict[str, Any]:
    q_counts: Dict[str, int] = {}
    for sample in snapshot.get("enqueue_sample_validations") or []:
        if not isinstance(sample, Mapping):
            continue
        cont = sample.get("continuity")
        if isinstance(cont, Mapping):
            q = str(cont.get("queue_continuity") or "UNKNOWN")
            q_counts[q] = q_counts.get(q, 0) + 1
    for sample in snapshot.get("regeneration_enqueue_sample_validations") or []:
        if not isinstance(sample, Mapping):
            continue
        cont = sample.get("continuity")
        if isinstance(cont, Mapping):
            q = str(cont.get("queue_continuity") or "UNKNOWN")
            q_counts[q] = q_counts.get(q, 0) + 1
    return {
        "by_queue_continuity": dict(sorted(q_counts.items())) if q_counts else {},
        "schema_version": "activation_continuity_summary_v1",
    }


def build_activation_rollback_summary() -> Dict[str, Any]:
    """Deterministic table of rollback transitions (code-only posture; advisory)."""
    transitions = [
        validate_registry_rollback_posture(from_ceiling=ACTIVATION_LIMITED, to_ceiling=ACTIVATION_OBSERVE_ONLY),
        validate_registry_rollback_posture(from_ceiling=ACTIVATION_LIMITED, to_ceiling=ACTIVATION_DISABLED),
        validate_registry_rollback_posture(from_ceiling=ACTIVATION_OBSERVE_ONLY, to_ceiling=ACTIVATION_DISABLED),
    ]
    all_ok = all(t.get("rollback_posture") == ROLLBACK_VALIDATED for t in transitions)
    return {
        "advisory_only": True,
        "rst_core_backbone_family": FAMILY_REQUIREMENT_STATE_TRANSITION_CORE_BACKBONE,
        "limited_activation_family_scope": sorted(_PHASE2_LIMITED_ACTIVATION_FAMILIES),
        "rollback_posture": ROLLBACK_VALIDATED if all_ok else ROLLBACK_PARTIAL,
        "rollback_posture_applies_to_registry_ceiling_order": True,
        "schema_version": "activation_rollback_summary_v1",
        "transitions": transitions,
    }
