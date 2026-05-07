"""Governance capability matrix + audit augment (additive diagnostics only)."""
import sys
from pathlib import Path

import pytest

backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

GOVERNANCE_DOC = backend_root / "docs" / "WORKFLOW_BEHAVIOUR_GOVERNANCE.md"

_SEMANTIC_METADATA_KEYS = (
    "workflow_meaning",
    "completion_semantics",
    "risk_resolution_semantics",
    "score_confidence_semantics",
    "upload_sufficiency",
    "audit_reporting_expectation",
    "forbidden_collapses",
    "reporting_visibility",
    "reporting_narrative",
    "supports_lender_export",
    "supports_operational_risk_reporting",
    "supports_expiry_reporting",
    "supports_evidence_pack_export",
    "requires_remediation_context_in_reports",
)


def test_governance_document_exists_and_has_semantic_sections():
    text = GOVERNANCE_DOC.read_text(encoding="utf-8")
    for heading in (
        "## Workflow Semantics and Compliance Meaning",
        "## Non-Equivalence Rules",
        "## Compliance Confidence Interpretation",
        "## Lifecycle Recalculation Semantics",
        "## Forbidden Workflow Collapses",
        "## Reporting and Audit Surface Semantics",
        "## Workflow Execution & System Behaviour Semantics",
    ):
        assert heading in text


_EXECUTION_METADATA_KEYS = (
    "execution_triggers",
    "system_execution_effects",
    "may_trigger_score_recalculation",
    "may_trigger_risk_regeneration",
    "may_trigger_gap_regeneration",
    "may_trigger_attention_regeneration",
    "may_trigger_report_refresh",
    "may_append_audit_timeline",
    "completion_authority",
    "score_impact_strength",
    "supports_direct_requirement_satisfaction",
    "requires_operational_followup",
    "non_equivalence_rules",
)


def test_execution_semantics_metadata_present_and_aligned():
    from services.workflow_behaviour_governance import (
        EXECUTION_SEMANTICS_METADATA,
        list_governance_execution_keys,
        list_governance_workflow_keys,
    )

    assert list_governance_execution_keys() == list_governance_workflow_keys()
    assert frozenset(EXECUTION_SEMANTICS_METADATA.keys()) == list_governance_workflow_keys()
    for k in list_governance_workflow_keys():
        row = EXECUTION_SEMANTICS_METADATA[k]
        for field in _EXECUTION_METADATA_KEYS:
            assert field in row, f"missing {field} for {k}"
            val = row[field]
            if field == "system_execution_effects":
                assert isinstance(val, frozenset) and len(val) > 0, k
            elif field == "non_equivalence_rules":
                assert isinstance(val, frozenset) and len(val) > 0, k
            elif field.startswith("may_") or field.startswith("supports_") or field == "requires_operational_followup":
                assert isinstance(val, bool), k
            elif field in ("completion_authority", "score_impact_strength"):
                assert isinstance(val, str) and val.strip(), k
            else:
                assert isinstance(val, str) and val.strip(), k


def test_governance_helpers_execution_contracts():
    from services.workflow_behaviour_governance import (
        COMPLETION_AUTHORITY_MAY_DIRECT_SATISFY,
        COMPLETION_AUTHORITY_MUST_NOT_UPLOAD_ONLY,
        CONDITION_STANDARD_ACTIVE_STANDARD,
        SCORE_IMPACT_STRENGTH_CONDITIONAL,
        SCORE_IMPACT_STRENGTH_DISTRIBUTED_OPERATIONAL,
        SCORE_IMPACT_STRENGTH_HIGH_DIRECT,
        SCORE_IMPACT_STRENGTH_MODERATE_CONTEXTUAL,
        WC_DOCUMENT_UPLOAD,
        WC_EXTERNAL_ASSESSMENT_EVIDENCE,
        WC_GUIDED_DECLARATION,
        workflow_completion_authority,
        workflow_may_append_audit_timeline,
        workflow_may_directly_satisfy_requirement,
        workflow_may_trigger_score_recalculation,
        workflow_non_equivalence_rules,
        workflow_requires_gap_regeneration,
        workflow_requires_operational_followup,
        workflow_score_impact_strength,
        workflow_supports_expiry_tracking,
    )

    assert workflow_may_directly_satisfy_requirement(WC_DOCUMENT_UPLOAD) is True
    assert workflow_supports_expiry_tracking(WC_DOCUMENT_UPLOAD) is True
    assert workflow_may_trigger_score_recalculation(WC_DOCUMENT_UPLOAD) is True
    assert workflow_requires_gap_regeneration(WC_DOCUMENT_UPLOAD) is True
    assert workflow_requires_operational_followup(WC_DOCUMENT_UPLOAD) is False
    assert workflow_completion_authority(WC_DOCUMENT_UPLOAD) == COMPLETION_AUTHORITY_MAY_DIRECT_SATISFY
    assert workflow_score_impact_strength(WC_DOCUMENT_UPLOAD) == SCORE_IMPACT_STRENGTH_HIGH_DIRECT
    assert len(workflow_non_equivalence_rules(WC_DOCUMENT_UPLOAD)) >= 1

    assert workflow_may_directly_satisfy_requirement(WC_GUIDED_DECLARATION) is True
    assert workflow_score_impact_strength(WC_GUIDED_DECLARATION) == SCORE_IMPACT_STRENGTH_MODERATE_CONTEXTUAL
    assert workflow_requires_operational_followup(WC_EXTERNAL_ASSESSMENT_EVIDENCE) is True
    assert workflow_score_impact_strength(WC_EXTERNAL_ASSESSMENT_EVIDENCE) == SCORE_IMPACT_STRENGTH_CONDITIONAL

    assert workflow_may_directly_satisfy_requirement(CONDITION_STANDARD_ACTIVE_STANDARD) is False
    assert workflow_completion_authority(CONDITION_STANDARD_ACTIVE_STANDARD) == COMPLETION_AUTHORITY_MUST_NOT_UPLOAD_ONLY
    assert workflow_score_impact_strength(CONDITION_STANDARD_ACTIVE_STANDARD) == SCORE_IMPACT_STRENGTH_DISTRIBUTED_OPERATIONAL

    assert workflow_may_append_audit_timeline(WC_GUIDED_DECLARATION) is True


def test_semantic_metadata_present_for_all_governance_workflow_keys():
    from services.workflow_behaviour_governance import (
        WORKFLOW_SEMANTIC_METADATA,
        list_governance_workflow_keys,
    )

    keys = list_governance_workflow_keys()
    assert keys == frozenset(WORKFLOW_SEMANTIC_METADATA.keys())
    for k in keys:
        row = WORKFLOW_SEMANTIC_METADATA[k]
        for field in _SEMANTIC_METADATA_KEYS:
            assert field in row, f"missing {field} for {k}"
            val = row[field]
            if field == "forbidden_collapses":
                assert isinstance(val, frozenset) and len(val) > 0, k
            elif field == "reporting_visibility":
                assert isinstance(val, frozenset) and len(val) > 0, k
            elif field.startswith("supports_") or field == "requires_remediation_context_in_reports":
                assert isinstance(val, bool), k
            else:
                assert isinstance(val, str) and val.strip(), k


def test_external_assessment_non_equivalence_excludes_remediation_completion():
    from services.workflow_behaviour_governance import WC_EXTERNAL_ASSESSMENT_EVIDENCE, workflow_non_equivalence_rules

    rules = workflow_non_equivalence_rules(WC_EXTERNAL_ASSESSMENT_EVIDENCE)
    assert "assessment_complete_not_remediation_complete" in rules


def test_forbidden_collapses_tokens_are_documented_normative():
    """Spot-check: umbrella semantic-collapse diagnostics align with governance vocabulary."""
    from services.workflow_behaviour_governance import WORKFLOW_SEMANTIC_METADATA

    union = set()
    for row in WORKFLOW_SEMANTIC_METADATA.values():
        union |= set(row["forbidden_collapses"])
    assert len(union) >= 4


def test_governance_augment_assessment_treated_as_remediation_flag():
    from services.compliance_evidence_record_service import EVIDENCE_MODE_DOCUMENT_UPLOAD
    from services.requirement_workflow_audit import WC_EXTERNAL_ASSESSMENT_EVIDENCE, compute_workflow_mismatch_flags

    enriched = {
        "requirement_code": "legionella",
        "workflow_class": WC_EXTERNAL_ASSESSMENT_EVIDENCE,
        "action_type": "DOCUMENT",
        "status": "VALID",
        "allowed_evidence_modes": ["STRUCTURED_DECLARATION", EVIDENCE_MODE_DOCUMENT_UPLOAD],
        "take_action": {"primary": {"intent": "upload_evidence", "kind": "navigate", "label": "Upload report"}},
    }
    flags = compute_workflow_mismatch_flags(
        enriched,
        reference_class=WC_EXTERNAL_ASSESSMENT_EVIDENCE,
        reference_source="decision_record_fallback",
    )
    ids = {f.get("id") for f in flags}
    assert "ASSESSMENT_TREATED_AS_REMEDIATION" in ids
    assert "ASSESSMENT_PRESENTED_AS_REMEDIATED" in ids
    assert "ASSESSMENT_REPORTED_AS_REMEDIATED" in ids
    assert "WORKFLOW_COMPLETION_SEMANTIC_DRIFT" in ids
    assert "WORKFLOW_REPORTING_SEMANTIC_DRIFT" in ids
    assert "WORKFLOW_SEMANTIC_COLLAPSE_RISK" in ids


def test_governance_augment_condition_standard_document_equivalence_flag():
    from services.compliance_evidence_record_service import EVIDENCE_MODE_DOCUMENT_UPLOAD
    from services.requirement_workflow_audit import WC_GUIDANCE_ONLY, compute_workflow_mismatch_flags

    enriched = {
        "requirement_code": "fitness_for_human_habitation",
        "requirement_type": "fitness_for_human_habitation",
        "jurisdiction": "England",
        "status": "COMPLIANT",
        "workflow_class": "GUIDANCE_ONLY",
        "action_type": "OBLIGATION",
        "allowed_evidence_modes": [EVIDENCE_MODE_DOCUMENT_UPLOAD],
        "take_action": {"primary": {"intent": "view_guidance", "kind": "navigate"}},
        "active_standard_status_summary": {"state": "unknown", "signal_counts": {}, "read_only": True},
    }
    flags = compute_workflow_mismatch_flags(
        enriched,
        reference_class=WC_GUIDANCE_ONLY,
        reference_source="decision_record_fallback",
    )
    ids = {f.get("id") for f in flags}
    assert "CONDITION_STANDARD_DOCUMENT_EQUIVALENCE" in ids
    assert "CONDITION_STANDARD_PRESENTED_AS_UPLOAD_COMPLETE" in ids
    assert "CONDITION_STANDARD_REPORTED_AS_DOCUMENT_COMPLIANT" in ids
    assert "WORKFLOW_COMPLETION_SEMANTIC_DRIFT" in ids
    assert "WORKFLOW_REPORTING_SEMANTIC_DRIFT" in ids
    assert "WORKFLOW_SEMANTIC_COLLAPSE_RISK" in ids


def test_governance_augment_declaration_presented_as_verified_proof():
    from services.compliance_evidence_record_service import EVIDENCE_MODE_DOCUMENT_UPLOAD
    from services.requirement_workflow_audit import WC_GUIDED_DECLARATION, compute_workflow_mismatch_flags

    enriched = {
        "requirement_code": "deposit_pi",
        "workflow_class": "GUIDED_DECLARATION",
        "action_type": "DOCUMENT",
        "allowed_evidence_modes": ["STRUCTURED_DECLARATION", EVIDENCE_MODE_DOCUMENT_UPLOAD],
        "take_action": {
            "primary": {
                "intent": "guided_evidence_resolution",
                "kind": "guided_evidence_resolution",
                "label": "Statutory verification checklist",
            }
        },
    }
    flags = compute_workflow_mismatch_flags(
        enriched,
        reference_class=WC_GUIDED_DECLARATION,
        reference_source="decision_record_fallback",
    )
    ids = {f.get("id") for f in flags}
    assert "DECLARATION_PRESENTED_AS_VERIFIED_PROOF" in ids
    assert "DECLARATION_PRESENTED_AS_EXTERNALLY_VERIFIED" in ids
    assert "DECLARATION_REPORTED_AS_EXTERNALLY_VERIFIED" in ids
    assert "WORKFLOW_COMPLETION_SEMANTIC_DRIFT" in ids
    assert "WORKFLOW_REPORTING_SEMANTIC_DRIFT" in ids


def test_document_workflow_missing_expiry_semantics_flag():
    from services.compliance_evidence_record_service import EVIDENCE_MODE_DOCUMENT_UPLOAD
    from services.requirement_workflow_audit import WC_DOCUMENT_UPLOAD, compute_workflow_mismatch_flags

    enriched = {
        "requirement_code": "gas_safety",
        "workflow_class": "LEGACY_DOCUMENT_UPLOAD",
        "action_type": "DOCUMENT",
        "status": "VALID",
        "allowed_evidence_modes": [EVIDENCE_MODE_DOCUMENT_UPLOAD],
        "take_action": {"primary": {"intent": "upload_evidence", "kind": "navigate", "label": "Upload certificate"}},
    }
    flags = compute_workflow_mismatch_flags(
        enriched,
        reference_class=WC_DOCUMENT_UPLOAD,
        reference_source="decision_record_fallback",
    )
    ids = {f.get("id") for f in flags}
    assert "DOCUMENT_WORKFLOW_MISSING_EXPIRY_SEMANTICS" in ids
    assert "WORKFLOW_SCORE_SEMANTIC_DRIFT" in ids


def test_document_upload_supports_primary_upload_and_may_satisfy():
    from services.workflow_behaviour_governance import (
        WC_DOCUMENT_UPLOAD,
        get_workflow_capabilities,
        workflow_may_directly_satisfy_requirement,
        workflow_supports_primary_document_upload,
    )

    c = get_workflow_capabilities(WC_DOCUMENT_UPLOAD)
    assert c["supports_document_upload_as_primary"] is True
    assert workflow_supports_primary_document_upload(WC_DOCUMENT_UPLOAD) is True
    assert workflow_may_directly_satisfy_requirement(WC_DOCUMENT_UPLOAD) is True


def test_guided_declaration_requires_structured_no_upload_primary():
    from services.workflow_behaviour_governance import (
        WC_GUIDED_DECLARATION,
        get_workflow_capabilities,
        workflow_requires_structured_payload,
        workflow_supports_primary_document_upload,
    )

    c = get_workflow_capabilities(WC_GUIDED_DECLARATION)
    assert c["requires_structured_payload"] is True
    assert c["supports_document_upload_as_primary"] is False
    assert workflow_requires_structured_payload(WC_GUIDED_DECLARATION) is True
    assert workflow_supports_primary_document_upload(WC_GUIDED_DECLARATION) is False


def test_tenant_delivery_structured_supporting_only():
    from services.workflow_behaviour_governance import (
        WC_TENANT_DELIVERY,
        get_workflow_capabilities,
    )

    c = get_workflow_capabilities(WC_TENANT_DELIVERY)
    assert c["requires_structured_payload"] is True
    assert c["supports_document_upload_as_primary"] is False
    assert c["supports_document_upload_as_supporting"] is True


def test_registration_tracking_structured_supporting_only():
    from services.workflow_behaviour_governance import (
        WC_REGISTRATION_TRACKING,
        get_workflow_capabilities,
    )

    c = get_workflow_capabilities(WC_REGISTRATION_TRACKING)
    assert c["requires_structured_payload"] is True
    assert c["supports_document_upload_as_primary"] is False


def test_external_assessment_conditional_remediation_open():
    from services.workflow_behaviour_governance import (
        SCORE_MODEL_ASSESSMENT_CONDITIONAL,
        WC_EXTERNAL_ASSESSMENT_EVIDENCE,
        get_workflow_capabilities,
    )

    c = get_workflow_capabilities(WC_EXTERNAL_ASSESSMENT_EVIDENCE)
    assert c["score_impact_model"] == SCORE_MODEL_ASSESSMENT_CONDITIONAL
    assert c["may_leave_remediation_open"] is True
    assert c["supports_document_upload_as_primary"] is False


def test_condition_standard_not_document_only_completion():
    from services.workflow_behaviour_governance import (
        CONDITION_STANDARD_ACTIVE_STANDARD,
        SCORE_MODEL_OPERATIONAL_CONVERGENCE,
        get_workflow_capabilities,
        workflow_document_only_is_governance_violation,
    )

    c = get_workflow_capabilities(CONDITION_STANDARD_ACTIVE_STANDARD)
    assert c["must_not_complete_from_document_only"] is True
    assert c["score_impact_model"] == SCORE_MODEL_OPERATIONAL_CONVERGENCE
    assert workflow_document_only_is_governance_violation(CONDITION_STANDARD_ACTIVE_STANDARD) is True


def test_multi_evidence_must_not_collapse_document_only():
    from services.workflow_behaviour_governance import (
        WC_MULTI_EVIDENCE,
        get_workflow_capabilities,
        workflow_document_only_is_governance_violation,
    )

    c = get_workflow_capabilities(WC_MULTI_EVIDENCE)
    assert c["must_not_complete_from_document_only"] is True
    assert workflow_document_only_is_governance_violation(WC_MULTI_EVIDENCE) is True


def test_condition_standard_doc_only_policy_no_upload_primary_no_high_cta_flag():
    """Document-only evidence policy with guidance/resolver-safe primary must not emit upload-primary CTA drift."""
    from services.compliance_evidence_record_service import EVIDENCE_MODE_DOCUMENT_UPLOAD
    from services.requirement_workflow_audit import WC_GUIDANCE_ONLY, compute_workflow_mismatch_flags

    enriched = {
        "requirement_code": "fitness_for_human_habitation",
        "requirement_type": "fitness_for_human_habitation",
        "jurisdiction": "England",
        "workflow_class": "GUIDANCE_ONLY",
        "action_type": "OBLIGATION",
        "allowed_evidence_modes": [EVIDENCE_MODE_DOCUMENT_UPLOAD],
        "take_action": {
            "primary": {
                "intent": "view_guidance",
                "kind": "navigate",
                "label": "Manage related issues",
            }
        },
    }
    flags = compute_workflow_mismatch_flags(
        enriched,
        reference_class=WC_GUIDANCE_ONLY,
        reference_source="decision_record_fallback",
    )
    assert not any(f.get("id") == "CONDITION_STANDARD_DOCUMENT_UPLOAD_PRIMARY" for f in flags)


def test_document_only_governance_respects_allowed_primary_cta_condition_standard():
    """Legacy document-only modes with allowed primary (view guidance) must not raise document-only umbrella HIGH."""
    from services.compliance_evidence_record_service import EVIDENCE_MODE_DOCUMENT_UPLOAD
    from services.workflow_behaviour_governance import CONDITION_STANDARD_ACTIVE_STANDARD, governance_augment_mismatch_flags

    enriched = {
        "requirement_code": "fitness_for_human_habitation",
        "requirement_type": "fitness_for_human_habitation",
        "workflow_class": "GUIDANCE_ONLY",
        "action_type": "OBLIGATION",
        "allowed_evidence_modes": [EVIDENCE_MODE_DOCUMENT_UPLOAD],
        "take_action": {
            "primary": {"intent": "view_guidance", "kind": "navigate", "label": "Manage related issues"},
        },
    }
    flags = governance_augment_mismatch_flags(
        enriched,
        reference_class=CONDITION_STANDARD_ACTIVE_STANDARD,
        existing_flag_ids=frozenset(),
    )
    assert not any(f.get("id") == "WORKFLOW_DOCUMENT_ONLY_GOVERNANCE_VIOLATION" for f in flags)


def test_document_only_governance_flag_on_tenant_delivery():
    from services.compliance_evidence_record_service import EVIDENCE_MODE_DOCUMENT_UPLOAD
    from services.requirement_workflow_audit import WC_TENANT_DELIVERY, compute_workflow_mismatch_flags

    enriched = {
        "requirement_code": "how_to_rent",
        "workflow_class": "LEGACY_DOCUMENT_UPLOAD",
        "action_type": "DOCUMENT",
        "allowed_evidence_modes": [EVIDENCE_MODE_DOCUMENT_UPLOAD],
        "take_action": {"primary": {"intent": "upload_evidence", "kind": "navigate"}},
    }
    flags = compute_workflow_mismatch_flags(
        enriched,
        reference_class=WC_TENANT_DELIVERY,
        reference_source="decision_record_fallback",
    )
    ids = {f.get("id") for f in flags}
    assert "WORKFLOW_DOCUMENT_ONLY_GOVERNANCE_VIOLATION" in ids
    assert "WORKFLOW_SEMANTIC_COLLAPSE_RISK" in ids


def test_condition_standard_document_completion_governance_flag():
    from services.requirement_workflow_audit import WC_GUIDANCE_ONLY, compute_workflow_mismatch_flags

    enriched = {
        "requirement_code": "repairing_standard",
        "requirement_type": "repairing_standard",
        "jurisdiction": "Scotland",
        "status": "COMPLIANT",
        "workflow_class": "GUIDANCE_ONLY",
        "action_type": "OBLIGATION",
        "allowed_evidence_modes": ["DOCUMENT_UPLOAD"],
        "take_action": {"primary": {"intent": "view_guidance", "kind": "navigate"}},
        "active_standard_status_summary": {"state": "unknown", "signal_counts": {}, "read_only": True},
    }
    flags = compute_workflow_mismatch_flags(
        enriched,
        reference_class=WC_GUIDANCE_ONLY,
        reference_source="decision_record_fallback",
    )
    ids = {f.get("id") for f in flags}
    assert "CONDITION_STANDARD_DOCUMENT_COMPLETION_VIOLATION" in ids


def test_certificate_workflow_without_document_mode_flag():
    from services.requirement_workflow_audit import WC_DOCUMENT_UPLOAD, compute_workflow_mismatch_flags

    enriched = {
        "requirement_code": "gas_safety",
        "workflow_class": "LEGACY_DOCUMENT_UPLOAD",
        "action_type": "DOCUMENT",
        "allowed_evidence_modes": ["STRUCTURED_DECLARATION"],
        "take_action": {"primary": {"intent": "guided_evidence_resolution", "kind": "guided_evidence_resolution"}},
    }
    flags = compute_workflow_mismatch_flags(
        enriched,
        reference_class=WC_DOCUMENT_UPLOAD,
        reference_source="decision_record_fallback",
    )
    ids = {f.get("id") for f in flags}
    assert "CERTIFICATE_WORKFLOW_WITHOUT_DOCUMENT_MODE" in ids


def test_guided_declaration_without_structured_payload_flag():
    from services.compliance_evidence_record_service import EVIDENCE_MODE_DOCUMENT_UPLOAD
    from services.requirement_workflow_audit import WC_GUIDED_DECLARATION, compute_workflow_mismatch_flags

    enriched = {
        "requirement_code": "deposit_pi",
        "workflow_class": "GUIDED_DECLARATION",
        "action_type": "DOCUMENT",
        "allowed_evidence_modes": [EVIDENCE_MODE_DOCUMENT_UPLOAD],
        "take_action": {"primary": {"intent": "guided_evidence_resolution", "kind": "guided_evidence_resolution"}},
    }
    flags = compute_workflow_mismatch_flags(
        enriched,
        reference_class=WC_GUIDED_DECLARATION,
        reference_source="decision_record_fallback",
    )
    ids = {f.get("id") for f in flags}
    assert "GUIDED_DECLARATION_WITHOUT_STRUCTURED_PAYLOAD" in ids


def test_assessment_completed_with_unresolved_actions_flag():
    from services.requirement_evidence_completeness import requirement_status_appears_satisfied_top_level
    from services.requirement_workflow_audit import WC_EXTERNAL_ASSESSMENT_EVIDENCE, compute_workflow_mismatch_flags

    enriched = {
        "requirement_code": "legionella",
        "workflow_class": WC_EXTERNAL_ASSESSMENT_EVIDENCE,
        "action_type": "DOCUMENT",
        "status": "VALID",
        "allowed_evidence_modes": ["STRUCTURED_DECLARATION", "DOCUMENT_UPLOAD"],
        "take_action": {"primary": {"intent": "guided_evidence_resolution", "kind": "guided_evidence_resolution"}},
        "evidence_completeness": {
            "evaluated": True,
            "is_complete": False,
            "completeness_reason": "missing_follow_up",
        },
    }
    assert requirement_status_appears_satisfied_top_level(enriched)
    flags = compute_workflow_mismatch_flags(
        enriched,
        reference_class=WC_EXTERNAL_ASSESSMENT_EVIDENCE,
        reference_source="decision_record_fallback",
    )
    ids = {f.get("id") for f in flags}
    assert "ASSESSMENT_COMPLETED_WITH_UNRESOLVED_ACTIONS" in ids
    assert "ASSESSMENT_REPORTED_AS_REMEDIATED" in ids
    assert "WORKFLOW_COMPLETION_SEMANTIC_DRIFT" in ids
    assert "WORKFLOW_SCORE_SEMANTIC_DRIFT" in ids
    assert "WORKFLOW_REPORTING_SEMANTIC_DRIFT" in ids


def test_primary_cta_governance_violation_condition_upload():
    from services.compliance_evidence_record_service import EVIDENCE_MODE_DOCUMENT_UPLOAD
    from services.requirement_workflow_audit import WC_GUIDANCE_ONLY, compute_workflow_mismatch_flags

    enriched = {
        "requirement_code": "fitness_for_human_habitation",
        "requirement_type": "fitness_for_human_habitation",
        "jurisdiction": "England",
        "workflow_class": "LEGACY_DOCUMENT_UPLOAD",
        "action_type": "DOCUMENT",
        "allowed_evidence_modes": [EVIDENCE_MODE_DOCUMENT_UPLOAD],
        "take_action": {"primary": {"intent": "upload_evidence", "kind": "navigate", "label": "Upload certificate"}},
    }
    flags = compute_workflow_mismatch_flags(
        enriched,
        reference_class=WC_GUIDANCE_ONLY,
        reference_source="decision_record_fallback",
    )
    ids = {f.get("id") for f in flags}
    assert "WORKFLOW_PRIMARY_CTA_GOVERNANCE_VIOLATION" in ids
