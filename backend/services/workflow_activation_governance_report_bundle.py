"""
Frozen governance bundles, filesystem persistence, and report diffing (Phase 5).

Read-only advisory helpers. No DB, no runtime activation, no enforcement.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence, Set, Tuple

from services.workflow_activation_governance_report import (
    APPROVE_FOR_LIMITED_ACTIVATION,
    BLOCKED_PENDING_GOVERNANCE,
    HOLD_PENDING_EVIDENCE,
    REPORT_VERSION,
)
from services.workflow_activation_calibration import LOW_RUNTIME_CONFIDENCE
from services.workflow_activation_governance import GOVERNANCE_REVIEW_REQUIRED, ROLLBACK_NOT_DEFINED, ROLLBACK_UNCERTAIN

BUNDLE_SCHEMA_VERSION = "workflow_activation_governance_bundle_v1"

NO_SIGNIFICANT_DRIFT = "NO_SIGNIFICANT_DRIFT"
LOW_GOVERNANCE_DRIFT = "LOW_GOVERNANCE_DRIFT"
MODERATE_GOVERNANCE_DRIFT = "MODERATE_GOVERNANCE_DRIFT"
HIGH_GOVERNANCE_DRIFT = "HIGH_GOVERNANCE_DRIFT"
CRITICAL_GOVERNANCE_DRIFT = "CRITICAL_GOVERNANCE_DRIFT"

_RUNTIME_CONF_ORDER = {"HIGH_RUNTIME_CONFIDENCE": 0, "MODERATE_RUNTIME_CONFIDENCE": 1, "LOW_RUNTIME_CONFIDENCE": 2, "UNKNOWN_RUNTIME_CONFIDENCE": 3, "": 99}
_ROLLBACK_ORDER = {"ROLLBACK_READY": 0, "ROLLBACK_REQUIRES_REVIEW": 1, "ROLLBACK_UNCERTAIN": 2, "ROLLBACK_NOT_DEFINED": 3, "": 99}
_ESCALATION_ORDER = {"CRITICAL": 0, "HIGH": 1, "MODERATE": 2, "WARNING": 3, "INFO": 4, "": 99}


def _deep_copy_json(obj: Any) -> Any:
    return json.loads(json.dumps(obj, default=str))


def normalize_governance_report_for_diff(report: Mapping[str, Any]) -> Dict[str, Any]:
    """
    Stable shape for hashing and equality: sorted keys, sorted family rows,
    strips timestamp fields from hash/diff payload.
    """
    data = _deep_copy_json(dict(report))
    data.pop("generated_at", None)
    fams = data.get("family_activation_reports")
    if isinstance(fams, list):
        data["family_activation_reports"] = sorted(
            [dict(sorted((dict(r) if isinstance(r, Mapping) else {}).items(), key=lambda kv: str(kv[0]))) for r in fams],
            key=lambda x: str(x.get("workflow_family") or ""),
        )
    # Sort list-of-string candidate sections
    for key in (
        "approved_activation_candidates",
        "blocked_activation_candidates",
        "conditional_activation_candidates",
        "observe_only_candidates",
        "deferred_architecture_candidates",
        "calibration_stage_confirmed_candidates",
        "governance_blocked_registry_candidates",
        "highest_risk_activation_families",
        "safest_activation_families",
    ):
        if isinstance(data.get(key), list):
            data[key] = sorted(str(x) for x in data[key])
    if isinstance(data.get("operational_review_priorities"), list):
        data["operational_review_priorities"] = sorted(
            [dict(sorted(dict(x).items(), key=lambda kv: str(kv[0]))) for x in data["operational_review_priorities"] if isinstance(x, Mapping)],
            key=lambda x: (str(x.get("operational_priority_band")), str(x.get("workflow_family") or "")),
        )
    rt_snap = data.get("runtime_activation_snapshot")
    if isinstance(rt_snap, Mapping):
        rt = dict(rt_snap)
        fam_rows = rt.get("families")
        if isinstance(fam_rows, list):
            rt["families"] = sorted(
                [dict(sorted((dict(r) if isinstance(r, Mapping) else {}).items(), key=lambda kv: str(kv[0]))) for r in fam_rows],
                key=lambda x: str(x.get("activation_family") or ""),
            )
        data["runtime_activation_snapshot"] = dict(sorted(rt.items(), key=lambda kv: str(kv[0])))
    return dict(sorted(data.items(), key=lambda kv: str(kv[0])))


def governance_report_hash_payload(normalized_report: Mapping[str, Any]) -> str:
    """Compact deterministic JSON for hashing (no timestamps in normalized payload)."""
    return json.dumps(dict(normalized_report), sort_keys=True, separators=(",", ":"))


def compute_diagnostic_bundle_hash(normalized_report: Mapping[str, Any]) -> str:
    payload = governance_report_hash_payload(normalized_report)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _extract_report(payload: Mapping[str, Any]) -> Dict[str, Any]:
    if isinstance(payload.get("report"), Mapping):
        return dict(payload["report"])
    return dict(payload)


def build_frozen_governance_bundle(
    report: Mapping[str, Any],
    *,
    environment_label: str,
    generated_at_iso: str,
) -> Dict[str, Any]:
    """Wrap unified report with reproducible bundle metadata (advisory)."""
    rep = dict(report)
    rep.setdefault("generated_at", generated_at_iso)
    normalized = normalize_governance_report_for_diff(rep)
    diag_hash = compute_diagnostic_bundle_hash(normalized)
    bundle_id = f"{REPORT_VERSION}:{environment_label}:{diag_hash}"
    src_versions = {
        "activation_readiness_summary": (rep.get("activation_readiness_summary") or {}).get("schema_version"),
        "runtime_calibration_summary": (rep.get("runtime_calibration_summary") or {}).get("schema_version"),
        "runtime_confidence_summary": (rep.get("runtime_confidence_summary") or {}).get("schema_version"),
        "governance_review_summary": (rep.get("governance_review_summary") or {}).get("schema_version"),
        "governance_drift_summary": (rep.get("governance_drift_summary") or {}).get("schema_version"),
        "escalation_risk_summary": (rep.get("escalation_risk_summary") or {}).get("schema_version"),
        "rollback_posture_summary": (rep.get("rollback_posture_summary") or {}).get("schema_version"),
        "evidence_gap_summary": (rep.get("evidence_gap_summary") or {}).get("schema_version"),
        "convergence_visibility_summary": (rep.get("convergence_visibility_summary") or {}).get("schema_version"),
        "activation_decision_summary": (rep.get("activation_decision_summary") or {}).get("schema_version"),
        "governance_readiness_overview": (rep.get("governance_readiness_overview") or {}).get("schema_version"),
        "report_version": rep.get("report_version"),
        "bundle_schema_version": BUNDLE_SCHEMA_VERSION,
    }
    bundle: Dict[str, Any] = {
        "audit_only": True,
        "bundle_schema_version": BUNDLE_SCHEMA_VERSION,
        "diagnostic_bundle_hash": diag_hash,
        "environment_label": str(environment_label),
        "generated_at": generated_at_iso,
        "governance_bundle_id": bundle_id,
        "non_blocking": True,
        "report": dict(sorted(rep.items(), key=lambda kv: str(kv[0]))),
        "report_version": rep.get("report_version", REPORT_VERSION),
        "runtime_behavior_changed": False,
        "source_snapshot_versions": dict(sorted((k, v) for k, v in src_versions.items() if v is not None)),
    }
    return dict(sorted(bundle.items(), key=lambda kv: str(kv[0])))


def write_workflow_activation_governance_report(
    output_path: str | Path,
    report: Mapping[str, Any],
    *,
    environment_label: str = "unspecified",
    generated_at_iso: str,
) -> Dict[str, Any]:
    """Persist frozen governance bundle to filesystem (JSON only, no DB)."""
    bundle = build_frozen_governance_bundle(
        report,
        environment_label=environment_label,
        generated_at_iso=generated_at_iso,
    )
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(bundle, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    path.write_text(text, encoding="utf-8")
    return bundle


def load_workflow_activation_governance_report(path: str | Path) -> Dict[str, Any]:
    """Load bundle or bare report JSON from filesystem."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping):
        raise ValueError("governance_report_file_must_be_json_object")
    return dict(raw)


def verify_bundle_integrity(bundle: Mapping[str, Any]) -> Tuple[bool, str]:
    """Recompute hash from embedded report; ignores outer generated_at for hash."""
    rep = _extract_report(bundle)
    expected = str(bundle.get("diagnostic_bundle_hash") or "")
    if not expected:
        return True, "no_diagnostic_bundle_hash_skipped"
    got = compute_diagnostic_bundle_hash(normalize_governance_report_for_diff(rep))
    if expected != got:
        return False, f"hash_mismatch expected={expected} computed={got}"
    return True, "ok"


def _family_index(rows: Sequence[Mapping[str, Any]]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        if isinstance(r, Mapping) and r.get("workflow_family"):
            out[str(r["workflow_family"])] = dict(r)
    return out


def _diff_severity_rank(s: str) -> int:
    return {
        NO_SIGNIFICANT_DRIFT: 0,
        LOW_GOVERNANCE_DRIFT: 1,
        MODERATE_GOVERNANCE_DRIFT: 2,
        HIGH_GOVERNANCE_DRIFT: 3,
        CRITICAL_GOVERNANCE_DRIFT: 4,
    }.get(s, 0)


def _classify_diff_severity(
    *,
    newly_blocked: Sequence[str],
    newly_approved: Sequence[str],
    posture_changes: Sequence[Mapping[str, Any]],
    priority_changes: Sequence[Mapping[str, Any]],
    conf_regress: Sequence[Mapping[str, Any]],
    esc_regress: Sequence[Mapping[str, Any]],
    rb_regress: Sequence[Mapping[str, Any]],
    vis_regress: Sequence[Mapping[str, Any]],
    readiness_changed: bool,
    cal_changed: bool,
    ap_lost: Sequence[str],
) -> str:
    candidates: List[str] = []
    if readiness_changed or cal_changed:
        candidates.append(LOW_GOVERNANCE_DRIFT)
    if posture_changes or priority_changes or conf_regress or esc_regress or rb_regress or vis_regress or newly_approved:
        candidates.append(MODERATE_GOVERNANCE_DRIFT)
    if newly_blocked or ap_lost:
        candidates.append(HIGH_GOVERNANCE_DRIFT)
    if any(str(p.get("to")) == "PRIORITY_P0_CRITICAL" for p in priority_changes):
        candidates.append(CRITICAL_GOVERNANCE_DRIFT)
    if any(str(x.get("to")) == "CRITICAL" for x in esc_regress):
        candidates.append(CRITICAL_GOVERNANCE_DRIFT)
    for ch in posture_changes:
        if str(ch.get("from")) == APPROVE_FOR_LIMITED_ACTIVATION and str(ch.get("to")) in (
            BLOCKED_PENDING_GOVERNANCE,
            HOLD_PENDING_EVIDENCE,
        ):
            candidates.append(HIGH_GOVERNANCE_DRIFT)
    if not candidates:
        return LOW_GOVERNANCE_DRIFT
    return max(candidates, key=lambda s: _diff_severity_rank(s))


def _max_esc_from_row(row: Mapping[str, Any]) -> str:
    best = "INFO"
    for er in row.get("escalation_risks") or []:
        if not isinstance(er, Mapping):
            continue
        sev = str(er.get("escalation_severity") or "INFO")
        if _ESCALATION_ORDER.get(sev, 99) < _ESCALATION_ORDER.get(best, 99):
            best = sev
    return best


def diff_workflow_activation_governance_reports(
    report_a: Mapping[str, Any],
    report_b: Mapping[str, Any],
) -> Dict[str, Any]:
    """
    Deterministic advisory diff between two unified reports (not outer bundle wrappers).
    """
    na = normalize_governance_report_for_diff(report_a)
    nb = normalize_governance_report_for_diff(report_b)
    if governance_report_hash_payload(na) == governance_report_hash_payload(nb):
        return {
            "activation_decision_posture_changes": [],
            "approved_activation_lost_families": [],
            "calibration_summary_changed": False,
            "confidence_regressions": [],
            "diff_severity": NO_SIGNIFICANT_DRIFT,
            "escalation_regressions": [],
            "governance_priority_changes": [],
            "newly_approved_families": [],
            "newly_blocked_families": [],
            "readiness_summary_changed": False,
            "rollback_regressions": [],
            "runtime_visibility_regressions": [],
            "schema_version": "workflow_activation_governance_report_diff_v1",
        }

    def _cand_set(m: Mapping[str, Any], key: str) -> Set[str]:
        v = m.get(key)
        return set(v) if isinstance(v, list) else set()

    ap_a, ap_b = _cand_set(report_a, "approved_activation_candidates"), _cand_set(report_b, "approved_activation_candidates")
    bl_a, bl_b = _cand_set(report_a, "blocked_activation_candidates"), _cand_set(report_b, "blocked_activation_candidates")
    newly_blocked = sorted((bl_b - bl_a) | (ap_a & bl_b))
    newly_approved = sorted(ap_b - ap_a)
    ap_lost = sorted(ap_a - ap_b)

    fa = _family_index(na.get("family_activation_reports") or [])
    fb = _family_index(nb.get("family_activation_reports") or [])
    all_fams = sorted(set(fa.keys()) | set(fb.keys()))

    posture_changes: List[Dict[str, str]] = []
    priority_changes: List[Dict[str, str]] = []
    conf_regress: List[Dict[str, Any]] = []
    esc_regress: List[Dict[str, Any]] = []
    rb_regress: List[Dict[str, Any]] = []
    vis_regress: List[Dict[str, Any]] = []

    for fam in all_fams:
        ra, rb = fa.get(fam, {}), fb.get(fam, {})
        pa, pb = str(ra.get("governance_decision_posture")), str(rb.get("governance_decision_posture"))
        if pa != pb:
            posture_changes.append({"from": pa, "to": pb, "workflow_family": fam})
        pria, prib = str(ra.get("operational_priority_band")), str(rb.get("operational_priority_band"))
        if pria != prib:
            priority_changes.append({"from": pria, "to": prib, "workflow_family": fam})
        ca, cb = str(ra.get("runtime_confidence")), str(rb.get("runtime_confidence"))
        if _RUNTIME_CONF_ORDER.get(cb, 99) > _RUNTIME_CONF_ORDER.get(ca, 99) and ca and cb:
            conf_regress.append({"from": ca, "to": cb, "workflow_family": fam})
        ea, eb = _max_esc_from_row(ra), _max_esc_from_row(rb)
        if _ESCALATION_ORDER.get(eb, 99) < _ESCALATION_ORDER.get(ea, 99):
            esc_regress.append({"from": ea, "to": eb, "workflow_family": fam})
        rba, rbb = str(ra.get("rollback_readiness")), str(rb.get("rollback_readiness"))
        if _ROLLBACK_ORDER.get(rbb, 99) > _ROLLBACK_ORDER.get(rba, 99) and rba and rbb:
            rb_regress.append({"from": rba, "to": rbb, "workflow_family": fam})
        sca = int((ra.get("evidence_scores") or {}).get("convergence_visibility_score") or 0) if isinstance(ra.get("evidence_scores"), Mapping) else 0
        scb = int((rb.get("evidence_scores") or {}).get("convergence_visibility_score") or 0) if isinstance(rb.get("evidence_scores"), Mapping) else 0
        if scb < sca - 20:
            vis_regress.append({"from_score": sca, "to_score": scb, "workflow_family": fam})

    posture_changes = sorted(posture_changes, key=lambda x: (x.get("workflow_family"), x.get("from"), x.get("to")))
    priority_changes = sorted(priority_changes, key=lambda x: (x.get("workflow_family"), x.get("from"), x.get("to")))
    conf_regress = sorted(conf_regress, key=lambda x: str(x.get("workflow_family")))
    esc_regress = sorted(esc_regress, key=lambda x: str(x.get("workflow_family")))
    rb_regress = sorted(rb_regress, key=lambda x: str(x.get("workflow_family")))
    vis_regress = sorted(vis_regress, key=lambda x: str(x.get("workflow_family")))

    readiness_a = json.dumps(report_a.get("activation_readiness_summary") or {}, sort_keys=True, separators=(",", ":"))
    readiness_b = json.dumps(report_b.get("activation_readiness_summary") or {}, sort_keys=True, separators=(",", ":"))
    cal_a = json.dumps(report_a.get("runtime_calibration_summary") or {}, sort_keys=True, separators=(",", ":"))
    cal_b = json.dumps(report_b.get("runtime_calibration_summary") or {}, sort_keys=True, separators=(",", ":"))
    readiness_changed = readiness_a != readiness_b
    cal_changed = cal_a != cal_b

    severity = _classify_diff_severity(
        newly_blocked=newly_blocked,
        newly_approved=newly_approved,
        posture_changes=posture_changes,
        priority_changes=priority_changes,
        conf_regress=conf_regress,
        esc_regress=esc_regress,
        rb_regress=rb_regress,
        vis_regress=vis_regress,
        readiness_changed=readiness_changed,
        cal_changed=cal_changed,
        ap_lost=ap_lost,
    )

    return dict(
        sorted(
            {
                "activation_decision_posture_changes": posture_changes,
                "approved_activation_lost_families": ap_lost,
                "calibration_summary_changed": cal_changed,
                "confidence_regressions": conf_regress,
                "diff_severity": severity,
                "escalation_regressions": esc_regress,
                "governance_priority_changes": priority_changes,
                "newly_approved_families": newly_approved,
                "newly_blocked_families": newly_blocked,
                "readiness_summary_changed": readiness_changed,
                "rollback_regressions": rb_regress,
                "runtime_visibility_regressions": vis_regress,
                "schema_version": "workflow_activation_governance_report_diff_v1",
            }.items()
        )
    )


def format_governance_diff_operator_summary(diff: Mapping[str, Any]) -> str:
    """Deterministic diff lines for ops (no generative prose)."""
    lines = [
        f"diff_severity={diff.get('diff_severity') or 'n_a'}",
        f"newly_blocked_families={','.join(diff.get('newly_blocked_families') or [])}",
        f"newly_approved_families={','.join(diff.get('newly_approved_families') or [])}",
        f"approved_activation_lost_families={','.join(diff.get('approved_activation_lost_families') or [])}",
        f"readiness_summary_changed={diff.get('readiness_summary_changed', False)}",
        f"calibration_summary_changed={diff.get('calibration_summary_changed', False)}",
        f"activation_decision_posture_change_count={len(diff.get('activation_decision_posture_changes') or [])}",
        f"governance_priority_change_count={len(diff.get('governance_priority_changes') or [])}",
        f"confidence_regression_count={len(diff.get('confidence_regressions') or [])}",
        f"escalation_regression_count={len(diff.get('escalation_regressions') or [])}",
        f"rollback_regression_count={len(diff.get('rollback_regressions') or [])}",
        f"runtime_visibility_regression_count={len(diff.get('runtime_visibility_regressions') or [])}",
    ]
    return "\n".join(lines) + "\n"


def format_governance_report_operator_summary(payload: Mapping[str, Any]) -> str:
    """Deterministic concise text for ops (no generative prose)."""
    bundle = payload if isinstance(payload.get("report"), Mapping) else {"report": dict(payload)}
    rep = _extract_report(bundle)
    sev = str(bundle.get("diff_severity") or "")
    lines: List[str] = []
    lines.append(f"governance_bundle_id={bundle.get('governance_bundle_id') or 'n_a'}")
    lines.append(f"diagnostic_bundle_hash={bundle.get('diagnostic_bundle_hash') or 'n_a'}")
    lines.append(f"environment_label={bundle.get('environment_label') or 'n_a'}")
    lines.append(f"report_version={rep.get('report_version') or 'n_a'}")
    lines.append(f"generated_at={rep.get('generated_at') or bundle.get('generated_at') or 'n_a'}")
    if sev:
        lines.append(f"diff_severity={sev}")
    lines.append(f"approved_families={','.join(rep.get('approved_activation_candidates') or [])}")
    lines.append(f"blocked_families={','.join(rep.get('blocked_activation_candidates') or [])}")
    lines.append(f"conditional_families={','.join(rep.get('conditional_activation_candidates') or [])}")
    lines.append(f"highest_risk_families={','.join(rep.get('highest_risk_activation_families') or [])}")
    ov = rep.get("governance_readiness_overview") or {}
    lines.append(f"readiness_indicator={ov.get('controlled_activation_readiness_indicator') or 'n_a'}")
    find = rep.get("governance_readiness_findings") or {}
    lines.append(f"low_runtime_confidence_family_count={find.get('low_runtime_confidence_family_count', 'n_a')}")
    lines.append(f"rollback_uncertain_family_count={find.get('rollback_uncertain_family_count', 'n_a')}")
    lines.append(f"drift_detected_family_count={find.get('drift_detected_family_count', 'n_a')}")
    gr = rep.get("governance_review_summary") or {}
    by_g = gr.get("by_activation_governance_state") or {}
    req = int(by_g.get("GOVERNANCE_REVIEW_REQUIRED") or 0)
    lines.append(f"governance_review_required_family_count={req}")
    fam_rows = rep.get("family_activation_reports") or []
    rb_unc_f = sorted(
        str(r.get("workflow_family") or "")
        for r in fam_rows
        if isinstance(r, Mapping)
        and str(r.get("rollback_readiness") or "") in (ROLLBACK_UNCERTAIN, ROLLBACK_NOT_DEFINED)
    )
    lines.append(f"rollback_uncertain_families={','.join(rb_unc_f)}")
    low_rt_f = sorted(
        str(r.get("workflow_family") or "")
        for r in fam_rows
        if isinstance(r, Mapping) and str(r.get("runtime_confidence") or "") == LOW_RUNTIME_CONFIDENCE
    )
    lines.append(f"low_runtime_confidence_families={','.join(low_rt_f)}")
    gr_req_f = sorted(
        str(r.get("workflow_family") or "")
        for r in fam_rows
        if isinstance(r, Mapping) and str(r.get("activation_governance_state") or "") == GOVERNANCE_REVIEW_REQUIRED
    )
    lines.append(f"governance_review_required_families={','.join(gr_req_f)}")
    return "\n".join(lines) + "\n"


def diff_frozen_governance_bundles(bundle_a: Mapping[str, Any], bundle_b: Mapping[str, Any]) -> Dict[str, Any]:
    """Diff two frozen bundles by comparing embedded reports."""
    return diff_workflow_activation_governance_reports(_extract_report(bundle_a), _extract_report(bundle_b))
