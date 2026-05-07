"""
Governance validation engine (read-only, structured diagnostics for CI).

Does not alter scoring, resolver, evidence authority, or requirement truth.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from services.compliance_evidence_record_service import EVIDENCE_MODE_DOCUMENT_UPLOAD
from services.governance_coverage_registry import GOVERNANCE_SURFACE_REGISTRY, list_governance_surface_ids
from services.requirement_code_registry import normalize_requirement_code
from services.requirement_workflow_audit import WC_DOCUMENT_UPLOAD, WC_EXTERNAL_ASSESSMENT_EVIDENCE, compute_workflow_mismatch_flags
from services.workflow_behaviour_governance import (
    CONDITION_STANDARD_ACTIVE_STANDARD,
    EFFECT_EXPIRY_LIFECYCLE,
    EXECUTION_SEMANTICS_METADATA,
    WC_GUIDED_DECLARATION,
    get_workflow_capabilities,
    list_governance_workflow_keys,
)


def _result(
    surface: str,
    *,
    severity: str,
    violations: Optional[List[str]] = None,
    warnings: Optional[List[str]] = None,
) -> Dict[str, Any]:
    return {
        "surface": surface,
        "severity": severity,
        "violations": list(violations or []),
        "warnings": list(warnings or []),
    }


def validate_workflow_contract_coverage() -> Dict[str, Any]:
    """Ensure every capability workflow key has semantic + execution contracts."""
    violations: List[str] = []
    warnings: List[str] = []
    keys = sorted(list_governance_workflow_keys())
    required_semantic = (
        "workflow_meaning",
        "reporting_narrative",
        "forbidden_collapses",
    )
    required_exec = (
        "execution_triggers",
        "system_execution_effects",
        "completion_authority",
        "score_impact_strength",
        "non_equivalence_rules",
        "may_trigger_score_recalculation",
        "may_append_audit_timeline",
    )
    for k in keys:
        caps = get_workflow_capabilities(k)
        for f in required_semantic:
            if f not in caps or not caps.get(f):
                violations.append(f"missing_or_empty_semantic:{k}:{f}")
        for f in required_exec:
            if f not in caps:
                violations.append(f"missing_execution_field:{k}:{f}")
            elif f == "system_execution_effects" and not caps.get(f):
                violations.append(f"empty_system_execution_effects:{k}")
            elif f == "non_equivalence_rules" and not caps.get(f):
                violations.append(f"empty_non_equivalence_rules:{k}")
        if caps.get("score_impact_strength") and not str(caps.get("score_impact_strength")).strip():
            violations.append(f"empty_score_impact_strength:{k}")
        if caps.get("completion_authority") and not str(caps.get("completion_authority")).strip():
            violations.append(f"empty_completion_authority:{k}")
    if set(EXECUTION_SEMANTICS_METADATA.keys()) != set(keys):
        violations.append("EXECUTION_SEMANTICS_METADATA_keys_mismatch_workflow_capability_keys")
    sev = "FAIL" if violations else "OK"
    return {"summary": sev, "results": [_result("workflow_contract_coverage", severity=sev, violations=violations, warnings=warnings)]}


def validate_surface_governance_alignment() -> Dict[str, Any]:
    """Every surface in GOVERNANCE_SURFACE_REGISTRY declares enforcement_level and contract booleans."""
    violations: List[str] = []
    allowed_el = {"NONE", "PARTIAL", "STRICT"}
    for sid, row in GOVERNANCE_SURFACE_REGISTRY.items():
        el = str(row.get("enforcement_level") or "").upper()
        if el not in allowed_el:
            violations.append(f"invalid_enforcement_level:{sid}:{el!r}")
        for field in (
            "consumes_workflow_contract",
            "consumes_requirement_display_contract",
            "consumes_reporting_semantics",
            "consumes_execution_semantics",
            "uses_local_fallback_logic",
            "allows_noncanonical_requirement_rows",
        ):
            if field not in row:
                violations.append(f"missing_field:{sid}:{field}")
            elif not isinstance(row.get(field), bool):
                violations.append(f"non_bool:{sid}:{field}")
        if row.get("enforcement_level") == "STRICT":
            if not row.get("consumes_workflow_contract"):
                violations.append(f"STRICT_surface_must_consume_workflow_contract:{sid}")
            if row.get("uses_local_fallback_logic"):
                violations.append(f"STRICT_surface_must_not_use_fallback:{sid}")
    sev = "FAIL" if violations else "OK"
    return {"summary": sev, "results": [_result("surface_governance_alignment", severity=sev, violations=violations)]}


def validate_requirement_contract_alignment(enriched: Dict[str, Any], *, reference_class: str, reference_source: str) -> Dict[str, Any]:
    """Run workflow mismatch diagnostics (read-only) on a single enriched requirement dict."""
    flags = compute_workflow_mismatch_flags(
        enriched,
        reference_class=reference_class,
        reference_source=reference_source,
    )
    violations = [str(f.get("id")) for f in flags if str(f.get("severity") or "").upper() == "HIGH"]
    warnings = [str(f.get("id")) for f in flags if str(f.get("severity") or "").upper() in ("MEDIUM", "LOW")]
    sev = "FAIL" if violations else ("WARN" if warnings else "OK")
    return {"summary": sev, "results": [_result("requirement_contract_alignment", severity=sev, violations=violations, warnings=warnings)]}


def validate_reporting_semantic_alignment(enriched: Dict[str, Any], *, reference_class: str, reference_source: str) -> Dict[str, Any]:
    """Subset of flags related to reporting / semantic collapse (heuristic)."""
    flags = compute_workflow_mismatch_flags(enriched, reference_class=reference_class, reference_source=reference_source)
    ids = {str(f.get("id") or "") for f in flags}
    reporting_ids = {
        "WORKFLOW_REPORTING_SEMANTIC_DRIFT",
        "WORKFLOW_SEMANTIC_COLLAPSE_RISK",
        "DECLARATION_REPORTED_AS_EXTERNALLY_VERIFIED",
        "CONDITION_STANDARD_REPORTED_AS_DOCUMENT_COMPLIANT",
        "ASSESSMENT_REPORTED_AS_REMEDIATED",
    }
    hit = sorted(ids & reporting_ids)
    violations = [i for i in hit if "DRIFT" in i or "COLLAPSE" in i]
    warnings = [i for i in hit if i not in violations]
    sev = "FAIL" if violations else ("WARN" if warnings else "OK")
    return {"summary": sev, "results": [_result("reporting_semantic_alignment", severity=sev, violations=violations, warnings=warnings)]}


def validate_execution_semantic_alignment(enriched: Dict[str, Any], *, reference_class: str, reference_source: str) -> Dict[str, Any]:
    flags = compute_workflow_mismatch_flags(enriched, reference_class=reference_class, reference_source=reference_source)
    ids = {str(f.get("id") or "") for f in flags}
    exec_ids = {
        "WORKFLOW_COMPLETION_SEMANTIC_DRIFT",
        "WORKFLOW_SCORE_SEMANTIC_DRIFT",
        "ASSESSMENT_PRESENTED_AS_REMEDIATED",
        "CONDITION_STANDARD_PRESENTED_AS_UPLOAD_COMPLETE",
        "DOCUMENT_WORKFLOW_MISSING_EXPIRY_SEMANTICS",
    }
    hit = sorted(ids & exec_ids)
    violations = [i for i in hit if i in ("WORKFLOW_COMPLETION_SEMANTIC_DRIFT", "ASSESSMENT_PRESENTED_AS_REMEDIATED", "CONDITION_STANDARD_PRESENTED_AS_UPLOAD_COMPLETE")]
    warnings = [i for i in hit if i not in violations]
    sev = "FAIL" if violations else ("WARN" if warnings else "OK")
    return {"summary": sev, "results": [_result("execution_semantic_alignment", severity=sev, violations=violations, warnings=warnings)]}


def validate_document_upload_expiry_semantics_present() -> Dict[str, Any]:
    """Governance contract: DOCUMENT_UPLOAD profile supports expiry tracking in capabilities."""
    c = get_workflow_capabilities(WC_DOCUMENT_UPLOAD)
    violations: List[str] = []
    if not c.get("supports_expiry_tracking"):
        violations.append("DOCUMENT_UPLOAD_must_support_expiry_tracking_in_capabilities")
    if EFFECT_EXPIRY_LIFECYCLE not in (c.get("system_execution_effects") or frozenset()):
        violations.append("DOCUMENT_UPLOAD_execution_semantics_must_include_expiry_lifecycle")
    sev = "FAIL" if violations else "OK"
    return {"summary": sev, "results": [_result("document_upload_expiry_semantics", severity=sev, violations=violations)]}


def validate_external_assessment_non_remediation_invariants() -> Dict[str, Any]:
    """Non-equivalence rules must explicitly exclude remediation completion for external assessment."""
    rules = get_workflow_capabilities(WC_EXTERNAL_ASSESSMENT_EVIDENCE).get("non_equivalence_rules") or frozenset()
    violations: List[str] = []
    if "assessment_complete_not_remediation_complete" not in rules:
        violations.append("missing_non_equivalence_assessment_vs_remediation")
    sev = "FAIL" if violations else "OK"
    return {"summary": sev, "results": [_result("external_assessment_non_remediation", severity=sev, violations=violations)]}


def validate_condition_standard_upload_only_forbidden() -> Dict[str, Any]:
    c = get_workflow_capabilities(CONDITION_STANDARD_ACTIVE_STANDARD)
    violations: List[str] = []
    if c.get("completion_authority") != "MUST_NOT_COMPLETE_FROM_UPLOAD_ONLY":
        violations.append("condition_standard_completion_authority_must_forbid_upload_only")
    if not c.get("must_not_complete_from_document_only"):
        violations.append("condition_standard_must_not_complete_from_document_only_capability")
    sev = "FAIL" if violations else "OK"
    return {"summary": sev, "results": [_result("condition_standard_upload_only", severity=sev, violations=violations)]}


def validate_guided_declaration_moderate_score_semantics() -> Dict[str, Any]:
    c = get_workflow_capabilities(WC_GUIDED_DECLARATION)
    violations: List[str] = []
    if str(c.get("score_impact_strength") or "") != "MODERATE_CONTEXTUAL":
        violations.append("guided_declaration_score_impact_must_be_MODERATE_CONTEXTUAL")
    sev = "FAIL" if violations else "OK"
    return {"summary": sev, "results": [_result("guided_declaration_score_semantics", severity=sev, violations=violations)]}


def validate_no_forbidden_generic_blocking_copy_in_repo() -> Dict[str, Any]:
    """
    CI guard: exact forbidden phrase must not appear in governed frontend paths.
    (Presentation-only surfaces remain partially governed — this asserts no worst-case string.)
    """
    violations: List[str] = []
    needle = "missing document — blocking compliance"
    needle2 = "missing document - blocking compliance"
    backend_root = Path(__file__).resolve().parent.parent
    roots = [
        backend_root.parent / "frontend" / "src",
        backend_root / "routes",
        backend_root / "services",
    ]
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.suffix.lower() not in (".js", ".jsx", ".ts", ".tsx", ".vue", ".py"):
                continue
            if path.name == "governance_validation_engine.py":
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore").lower()
            except OSError:
                continue
            if needle in text or needle2 in text:
                violations.append(f"forbidden_generic_blocking_copy:{path.relative_to(backend_root.parent)}")
    sev = "FAIL" if violations else "OK"
    return {"summary": sev, "results": [_result("forbidden_generic_blocking_copy", severity=sev, violations=violations)]}


def validate_noncanonical_requirement_ids(enriched: Dict[str, Any]) -> Dict[str, Any]:
    """Flag synthetic storage when canonical normalization is absent for governed rows."""
    violations: List[str] = []
    raw = str(enriched.get("requirement_code") or enriched.get("requirement_type") or "").strip()
    canon = normalize_requirement_code(raw)
    if raw and not canon:
        violations.append(f"noncanonical_requirement_code:{raw!r}")
    sev = "FAIL" if violations else "OK"
    return {"summary": sev, "results": [_result("noncanonical_requirement_ids", severity=sev, violations=violations)]}


def validate_governed_document_row_modes(enriched: Dict[str, Any]) -> Dict[str, Any]:
    """DOCUMENT_UPLOAD reference with satisfied appearance should not be document-only without expiry hints (governance drift)."""
    violations: List[str] = []
    modes = enriched.get("allowed_evidence_modes") or []
    if not isinstance(modes, list):
        modes = []
    norm = [str(m or "").strip().upper() for m in modes if m]
    doc_only = len(norm) == 1 and norm[0] == EVIDENCE_MODE_DOCUMENT_UPLOAD
    if enriched.get("workflow_class") in (WC_DOCUMENT_UPLOAD, "LEGACY_DOCUMENT_UPLOAD") and doc_only:
        violations.append("document_workflow_document_only_modes_on_row")
    sev = "FAIL" if violations else "OK"
    return {"summary": sev, "results": [_result("governed_document_row_modes", severity=sev, violations=violations)]}


def validate_command_centre_requirement_backed_rows(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Command-centre Phase 2 diagnostics (audit-only):
    - requirement rows should carry canonical requirement_id
    - requirement rows should carry requirement_display contract
    - requirement rows should carry resolver-enriched metadata.take_action
    - forbid generic missing-document compliance wording
    - flag local CTA fallback when resolver take_action primary label exists
    """
    violations: List[str] = []
    warnings: List[str] = []
    for idx, row in enumerate(rows or []):
        if not isinstance(row, dict):
            continue
        st = str(row.get("source_type") or "").strip().lower()
        if st != "requirement":
            continue
        md = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        rid = (
            row.get("requirement_id")
            or md.get("requirement_id")
            or md.get("linked_property_requirement_id")
            or md.get("related_requirement_id")
        )
        if rid is None or not str(rid).strip():
            violations.append(f"command_centre_missing_canonical_requirement_id:row[{idx}]")

        rd = md.get("requirement_display")
        if not isinstance(rd, dict) or not rd:
            violations.append(f"command_centre_missing_requirement_display:row[{idx}]")

        take = md.get("take_action")
        if not isinstance(take, dict) or not take:
            violations.append(f"command_centre_missing_take_action:row[{idx}]")
        else:
            pri = take.get("primary") if isinstance(take.get("primary"), dict) else {}
            ta_label = str(pri.get("label") or "").strip().lower()
            row_label = str(row.get("primary_action_label") or "").strip().lower()
            if ta_label and row_label and ta_label != row_label:
                warnings.append(f"command_centre_local_cta_fallback_with_resolver_take_action:row[{idx}]")

        generic = "missing document - blocking compliance"
        generic2 = "missing document — blocking compliance"
        haystack = " ".join(
            [
                str(row.get("title") or ""),
                str(row.get("description") or ""),
                str(row.get("primary_action_label") or ""),
                str(md.get("timing_label") or ""),
            ]
        ).lower()
        if generic in haystack or generic2 in haystack:
            violations.append(f"command_centre_forbidden_generic_wording:row[{idx}]")

    sev = "FAIL" if violations else ("WARN" if warnings else "OK")
    return {
        "summary": sev,
        "results": [
            _result(
                "command_centre_requirement_backed_alignment",
                severity=sev,
                violations=violations,
                warnings=warnings,
            )
        ],
    }


def validate_reminder_generation_semantics(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Reminder-generation Phase 2 diagnostics (audit-only).
    """
    violations: List[str] = []
    warnings: List[str] = []
    for idx, row in enumerate(rows or []):
        if not isinstance(row, dict):
            continue
        md = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        st = str(row.get("source_type") or md.get("source_type") or "").strip().lower()
        if st and st != "requirement":
            continue
        rd = md.get("requirement_display")
        if not isinstance(rd, dict) or not rd:
            violations.append(f"reminder_missing_requirement_display:row[{idx}]")

        workflow_class = str(
            md.get("workflow_class")
            or row.get("workflow_class")
            or md.get("primary_resolution_workflow")
            or ""
        ).strip().upper()
        semantic_line = str(row.get("semantic_line") or md.get("semantic_line") or "").strip().lower()
        hay = " ".join(
            [
                str(row.get("type") or ""),
                str(row.get("detail_type") or ""),
                str(row.get("semantic_line") or ""),
                str(row.get("subject") or ""),
                str(row.get("message") or ""),
            ]
        ).lower()

        if "blocking compliance" in hay:
            violations.append(f"reminder_forbidden_generic_blocking_copy:row[{idx}]")

        if workflow_class == WC_GUIDED_DECLARATION and any(x in hay for x in ("verified", "externally verified", "verification passed")):
            violations.append(f"reminder_declaration_presented_as_verified:row[{idx}]")

        if workflow_class == WC_EXTERNAL_ASSESSMENT_EVIDENCE and any(
            x in hay for x in ("operationally safe", "remediation complete", "resolved remediation")
        ):
            violations.append(f"reminder_assessment_presented_as_operationally_resolved:row[{idx}]")

        if (
            workflow_class in (CONDITION_STANDARD_ACTIVE_STANDARD, "CONDITION_STANDARD")
            and any(x in hay for x in ("upload complete", "document complete", "upload-only complete"))
        ):
            violations.append(f"reminder_condition_standard_presented_as_upload_complete:row[{idx}]")

        if workflow_class == WC_GUIDED_DECLARATION and semantic_line and "declaration" not in semantic_line:
            warnings.append(f"reminder_semantics_inconsistent_with_workflow:row[{idx}]:guided_declaration")
        if workflow_class == WC_EXTERNAL_ASSESSMENT_EVIDENCE and semantic_line and "assessment" not in semantic_line:
            warnings.append(f"reminder_semantics_inconsistent_with_workflow:row[{idx}]:external_assessment")
        if workflow_class in (CONDITION_STANDARD_ACTIVE_STANDARD, "CONDITION_STANDARD") and semantic_line and "condition" not in semantic_line:
            warnings.append(f"reminder_semantics_inconsistent_with_workflow:row[{idx}]:condition_standard")

    sev = "FAIL" if violations else ("WARN" if warnings else "OK")
    return {
        "summary": sev,
        "results": [
            _result(
                "reminder_generation_semantics_alignment",
                severity=sev,
                violations=violations,
                warnings=warnings,
            )
        ],
    }


def validate_reminder_narrative_groups(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Audit-only checks for Phase 2B grouped reminder narrative context.
    """
    violations: List[str] = []
    warnings: List[str] = []
    if not isinstance(payload, dict):
        return {
            "summary": "FAIL",
            "results": [_result("reminder_narrative_groups_alignment", severity="FAIL", violations=["invalid_payload"], warnings=[])],
        }
    groups = {
        "certificate_reminders": payload.get("certificate_reminders") or [],
        "declaration_reminders": payload.get("declaration_reminders") or [],
        "assessment_reminders": payload.get("assessment_reminders") or [],
        "condition_reminders": payload.get("condition_reminders") or [],
        "other_reminders": payload.get("other_reminders") or [],
    }
    for gk, rows in groups.items():
        if not isinstance(rows, list):
            violations.append(f"invalid_group_type:{gk}")
            continue
        for idx, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            bucket = str(row.get("workflow_semantics_bucket") or "").strip().upper()
            line = str(row.get("semantic_line") or "").strip().lower()
            hay = " ".join([str(row.get("type") or ""), str(row.get("detail_type") or ""), line]).lower()

            if "blocking compliance" in hay:
                violations.append(f"forbidden_blocking_compliance_wording:{gk}[{idx}]")
            if "verified" in hay and gk == "declaration_reminders":
                violations.append(f"declaration_framed_as_verified:{gk}[{idx}]")
            if any(x in hay for x in ("operationally safe", "remediation complete", "resolved remediation")) and gk == "assessment_reminders":
                violations.append(f"assessment_framed_as_resolved_or_safe:{gk}[{idx}]")
            if any(x in hay for x in ("upload complete", "document complete", "upload-only complete")) and gk == "condition_reminders":
                violations.append(f"condition_standard_framed_as_document_complete:{gk}[{idx}]")

            if gk == "certificate_reminders" and bucket in ("CONDITION_STANDARD", CONDITION_STANDARD_ACTIVE_STANDARD):
                violations.append(f"condition_standard_in_certificate_group:{gk}[{idx}]")
            if gk == "declaration_reminders" and bucket and bucket != WC_GUIDED_DECLARATION:
                warnings.append(f"mixed_workflow_semantics_in_group:{gk}[{idx}]:{bucket}")
            if gk == "assessment_reminders" and bucket and bucket != WC_EXTERNAL_ASSESSMENT_EVIDENCE:
                warnings.append(f"mixed_workflow_semantics_in_group:{gk}[{idx}]:{bucket}")
            if gk == "condition_reminders" and bucket and bucket not in ("CONDITION_STANDARD", CONDITION_STANDARD_ACTIVE_STANDARD):
                warnings.append(f"mixed_workflow_semantics_in_group:{gk}[{idx}]:{bucket}")
    sev = "FAIL" if violations else ("WARN" if warnings else "OK")
    return {
        "summary": sev,
        "results": [
            _result(
                "reminder_narrative_groups_alignment",
                severity=sev,
                violations=violations,
                warnings=warnings,
            )
        ],
    }


def snapshot_governance_surface_registry() -> str:
    """Stable JSON snapshot for tests (sorted keys)."""
    payload = {k: GOVERNANCE_SURFACE_REGISTRY[k] for k in sorted(GOVERNANCE_SURFACE_REGISTRY)}
    return json.dumps(payload, sort_keys=True, default=str)


def snapshot_workflow_capability_keys() -> str:
    return json.dumps(sorted(list_governance_workflow_keys()), default=str)


def validate_registry_workflow_semantics_smoke() -> Dict[str, Any]:
    """
    CI guard: registry workflow semantics module remains internally consistent
    (allowed primary workflows cover product defaults; smoke validations behave).
    """
    violations: List[str] = []
    from services.registry_workflow_semantics import (
        ALLOWED_PRIMARY_RESOLUTION_WORKFLOWS,
        validate_evidence_resolution_workflow_semantics,
    )
    from services.compliance_evidence_record_service import (
        EXTERNAL_ASSESSMENT_EVIDENCE_WORKFLOW,
        GUIDED_DECLARATION_WORKFLOW,
    )

    for required in (
        "GUIDED_EVIDENCE_RESOLUTION",
        GUIDED_DECLARATION_WORKFLOW,
        EXTERNAL_ASSESSMENT_EVIDENCE_WORKFLOW,
    ):
        if required not in ALLOWED_PRIMARY_RESOLUTION_WORKFLOWS:
            violations.append(f"missing_default_primary_workflow:{required}")

    errs_ok, _ = validate_evidence_resolution_workflow_semantics(
        {
            "allowed_evidence_modes": ["STRUCTURED_DECLARATION", "DOCUMENT_UPLOAD"],
            "primary_resolution_workflow": GUIDED_DECLARATION_WORKFLOW,
        }
    )
    if errs_ok:
        violations.append(f"valid_guided_declaration_rejected:{errs_ok}")

    bad_ext, _ = validate_evidence_resolution_workflow_semantics(
        {
            "allowed_evidence_modes": ["DOCUMENT_UPLOAD"],
            "primary_resolution_workflow": EXTERNAL_ASSESSMENT_EVIDENCE_WORKFLOW,
        }
    )
    if not bad_ext:
        violations.append("expected_external_assessment_document_only_blocked")

    sev = "FAIL" if violations else "OK"
    return {"summary": sev, "results": [_result("registry_workflow_semantics_smoke", severity=sev, violations=violations)]}


def run_phase1_ci_bundle() -> Dict[str, Any]:
    """Aggregate Phase 1 validations for CI."""
    parts = [
        validate_workflow_contract_coverage(),
        validate_surface_governance_alignment(),
        validate_document_upload_expiry_semantics_present(),
        validate_external_assessment_non_remediation_invariants(),
        validate_condition_standard_upload_only_forbidden(),
        validate_guided_declaration_moderate_score_semantics(),
        validate_no_forbidden_generic_blocking_copy_in_repo(),
        validate_registry_workflow_semantics_smoke(),
    ]
    failed = any(p.get("summary") == "FAIL" for p in parts)
    return {"overall": "FAIL" if failed else "OK", "parts": parts}
