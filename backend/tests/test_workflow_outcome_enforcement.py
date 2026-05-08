from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from models import RequirementStatus
from services.compliance_evidence_record_service import EVIDENCE_MODE_DOCUMENT_UPLOAD, effective_evidence_resolution
from services.requirement_workflow_audit import (
    WC_DOCUMENT_UPLOAD,
    WC_EXTERNAL_ASSESSMENT_EVIDENCE,
    WC_GUIDED_DECLARATION,
    WC_MULTI_EVIDENCE,
    WC_REGISTRATION_TRACKING,
    WC_TENANT_DELIVERY,
    apply_workflow_reference_audit,
)
from services.requirement_evidence_authority import EA_VERIFIED_EXPIRED, preview_authority
from services.workflow_behaviour_governance import (
    CONDITION_STANDARD_ACTIVE_STANDARD,
    get_workflow_capabilities,
    workflow_non_equivalence_rules,
)
from tests.helpers.workflow_outcome_harness import (
    CONDITION_STANDARD_FITNESS,
    CONDITION_STANDARD_REPAIRING,
    DOCUMENT_UPLOAD_GAS,
    EXTERNAL_ASSESSMENT_LEAD,
    EXTERNAL_ASSESSMENT_LEGIONELLA,
    GUIDED_DECLARATION_DEPOSIT_PI,
    GUIDED_DECLARATION_TENANCY,
    MULTI_EVIDENCE_SMOKE_HEAT,
    REGISTRATION_TRACKING_LANDLORD,
    REGISTRATION_TRACKING_RENT_SMART_WALES,
    TENANT_DELIVERY_HOW_TO_RENT,
    apply_phase2_scenario_defaults,
    build_property_a_partial_multi_evidence_record,
    build_property_a_verified_document,
    build_property_a_verified_document_no_expiry,
    build_property_a_evidence_record,
    build_property_a_structured_record_for_registration_or_delivery,
    build_property_a_upload_only_record,
    build_two_property_requirements,
    enrich_requirement_projection,
    preview_requirement_authority_with_scoped_records,
    preview_requirement_authority_with_scoped_records_and_property_context,
    representative_phase2_workflow_scenarios,
    reminder_state_key_for_requirement,
    representative_workflow_scenarios,
    resolver_projection,
    scoped_records_for_requirement,
    workflow_mismatch_ids,
)


@pytest.mark.parametrize("scenario", representative_workflow_scenarios(), ids=lambda s: s.key)
def test_property_scope_isolation_for_representative_workflows(scenario):
    req_a, req_b = build_two_property_requirements(scenario)
    evidence_a = build_property_a_evidence_record(scenario, req_a)
    all_records = [evidence_a]

    scoped_a = scoped_records_for_requirement(all_records, req_a)
    scoped_b = scoped_records_for_requirement(all_records, req_b)
    assert len(scoped_a) == 1
    assert scoped_b == []

    preview_a = preview_requirement_authority_with_scoped_records(req_a, all_records)
    preview_b = preview_requirement_authority_with_scoped_records(req_b, all_records)

    assert preview_b["mirror"]["status"] != RequirementStatus.COMPLIANT.value
    assert preview_a["evidence_authority"].get("authoritative_property_id") == req_a["property_id"]
    assert preview_a["evidence_authority"].get("primary_evidence_record_id") == evidence_a["evidence_record_id"]

    key_a = reminder_state_key_for_requirement(req_a)
    key_b = reminder_state_key_for_requirement(req_b)
    assert key_a["client_id"] == key_b["client_id"]
    assert key_a["requirement_code"] == key_b["requirement_code"]
    assert key_a["property_id"] != key_b["property_id"]
    assert key_a["target_ref"] != key_b["target_ref"]


@pytest.mark.parametrize("scenario", representative_workflow_scenarios(), ids=lambda s: s.key)
def test_user_outcome_projection_matches_governance_workflow_and_take_action(scenario):
    req_a, req_b = build_two_property_requirements(scenario)
    evidence_a = build_property_a_evidence_record(scenario, req_a)
    all_records = [evidence_a]

    preview_a = preview_requirement_authority_with_scoped_records(req_a, all_records)
    preview_b = preview_requirement_authority_with_scoped_records(req_b, all_records)
    proj_a = enrich_requirement_projection(req_a, preview_a, all_records, audience="client")
    proj_b = enrich_requirement_projection(req_b, preview_b, all_records, audience="client")

    ta_a = resolver_projection(req_a)
    ta_b = resolver_projection(req_b)

    expected_classes = {scenario.expected_workflow_class}
    if scenario.expected_workflow_class == WC_DOCUMENT_UPLOAD:
        expected_classes.add("LEGACY_DOCUMENT_UPLOAD")
    assert str(ta_a.get("workflow_class") or "").upper() in expected_classes
    assert str(ta_b.get("workflow_class") or "").upper() in expected_classes
    assert isinstance(ta_a.get("take_action"), dict)
    assert isinstance(ta_b.get("take_action"), dict)
    assert isinstance(proj_a.get("requirement_display"), dict)
    assert isinstance(proj_b.get("requirement_display"), dict)
    assert proj_a["requirement_display"].get("canonical_name")
    assert proj_b["requirement_display"].get("short_name")


@pytest.mark.parametrize("scenario", representative_workflow_scenarios(), ids=lambda s: s.key)
def test_system_outcome_projection_is_property_scoped_with_audit_facing_metadata(scenario):
    req_a, req_b = build_two_property_requirements(scenario)
    evidence_a = build_property_a_evidence_record(scenario, req_a)
    all_records = [evidence_a]

    preview_a = preview_requirement_authority_with_scoped_records(req_a, all_records)
    preview_b = preview_requirement_authority_with_scoped_records(req_b, all_records)

    admin_a = enrich_requirement_projection(req_a, preview_a, all_records, audience="admin")
    admin_b = enrich_requirement_projection(req_b, preview_b, all_records, audience="admin")

    # Report/export builders are intentionally not invoked here to avoid brittle integration tests;
    # audit-facing metadata on enriched rows is deterministic and sufficient for this Phase 1 harness.
    assert "workflow_class_reference" in admin_a
    assert "workflow_mismatch_flags" in admin_a
    assert "workflow_class_reference" in admin_b
    assert "workflow_mismatch_flags" in admin_b

    assert preview_b["mirror"]["status"] != RequirementStatus.COMPLIANT.value
    assert preview_a["evidence_authority"].get("authoritative_property_id") == req_a["property_id"]


def test_non_equivalence_guided_declaration_not_represented_as_externally_verified():
    scenario = GUIDED_DECLARATION_TENANCY
    req_a, _ = build_two_property_requirements(scenario)
    evidence_a = build_property_a_evidence_record(scenario, req_a)
    all_records = [evidence_a]
    preview_a = preview_requirement_authority_with_scoped_records(req_a, all_records)
    admin_a = enrich_requirement_projection(req_a, preview_a, all_records, audience="admin")
    mismatch_ids = workflow_mismatch_ids(admin_a, scenario.expected_workflow_class)

    assert "DECLARATION_PRESENTED_AS_EXTERNALLY_VERIFIED" not in mismatch_ids
    take_action_label = str(
        ((resolver_projection(req_a).get("take_action") or {}).get("primary") or {}).get("label") or ""
    ).lower()
    assert "verify" not in take_action_label


def test_non_equivalence_external_assessment_not_represented_as_resolved_or_safe_and_actions_visible():
    scenario = EXTERNAL_ASSESSMENT_LEGIONELLA
    req_a, _ = build_two_property_requirements(scenario)
    evidence_a = build_property_a_evidence_record(scenario, req_a)
    all_records = [evidence_a]
    preview_a = preview_requirement_authority_with_scoped_records(req_a, all_records)
    admin_a = enrich_requirement_projection(req_a, preview_a, all_records, audience="admin")
    mismatch_ids = workflow_mismatch_ids(admin_a, scenario.expected_workflow_class)

    forbidden = {
        "ASSESSMENT_PRESENTED_AS_REMEDIATION_COMPLETE",
        "EXTERNAL_ASSESSMENT_EVIDENCE:operationally_safe_or_resolved",
    }
    assert not forbidden.intersection(set(mismatch_ids))
    assert (
        evidence_a.get("evidence_payload", {})
        .get("structured_fields", {})
        .get("actions_required", {})
        .get("answer")
        is True
    )


def test_governance_capability_contract_assertions_for_phase1_workflows():
    caps_doc = get_workflow_capabilities(WC_DOCUMENT_UPLOAD)
    caps_decl = get_workflow_capabilities(WC_GUIDED_DECLARATION)
    caps_assess = get_workflow_capabilities(WC_EXTERNAL_ASSESSMENT_EVIDENCE)

    assert caps_doc.get("supports_document_upload_as_primary") is True
    assert caps_doc.get("supports_expiry_tracking") is True

    assert caps_decl.get("requires_structured_payload") is True

    assert caps_assess.get("requires_structured_payload") is True
    assert caps_assess.get("supports_follow_up") is True
    assert caps_assess.get("may_leave_remediation_open") is True

    decl_rules = workflow_non_equivalence_rules(WC_GUIDED_DECLARATION)
    assess_rules = workflow_non_equivalence_rules(WC_EXTERNAL_ASSESSMENT_EVIDENCE)
    assert any("declaration_not_external" in rule for rule in decl_rules)
    assert "assessment_complete_not_remediation_complete" in assess_rules


@pytest.mark.parametrize("scenario", representative_phase2_workflow_scenarios(), ids=lambda s: s.key)
def test_phase2_property_scope_isolation_and_reminder_state_keys(scenario):
    req_a, req_b = build_two_property_requirements(scenario)
    req_a = apply_phase2_scenario_defaults(scenario, req_a)
    req_b = apply_phase2_scenario_defaults(scenario, req_b)
    evidence_a = build_property_a_upload_only_record(scenario, req_a)
    all_records = [evidence_a]

    scoped_a = scoped_records_for_requirement(all_records, req_a)
    scoped_b = scoped_records_for_requirement(all_records, req_b)
    assert len(scoped_a) == 1
    assert scoped_b == []

    preview_a = preview_requirement_authority_with_scoped_records(req_a, all_records)
    preview_b = preview_requirement_authority_with_scoped_records(req_b, all_records)
    assert preview_b["mirror"]["status"] != RequirementStatus.COMPLIANT.value
    assert preview_a["evidence_authority"].get("authoritative_property_id") == req_a["property_id"]

    key_a = reminder_state_key_for_requirement(req_a)
    key_b = reminder_state_key_for_requirement(req_b)
    assert key_a["client_id"] == key_b["client_id"]
    assert key_a["requirement_code"] == key_b["requirement_code"]
    assert key_a["property_id"] != key_b["property_id"]
    assert key_a["target_ref"] != key_b["target_ref"]


@pytest.mark.parametrize(
    "scenario,expected_flag",
    [
        (CONDITION_STANDARD_FITNESS, "CONDITION_STANDARD_DOCUMENT_UPLOAD_PRIMARY"),
        (CONDITION_STANDARD_REPAIRING, "CONDITION_STANDARD_DOCUMENT_UPLOAD_PRIMARY"),
        (TENANT_DELIVERY_HOW_TO_RENT, "TENANT_DELIVERY_DOCUMENT_ONLY"),
        (REGISTRATION_TRACKING_LANDLORD, "REGISTRATION_TRACKING_DOCUMENT_ONLY"),
    ],
    ids=[
        CONDITION_STANDARD_FITNESS.key,
        CONDITION_STANDARD_REPAIRING.key,
        TENANT_DELIVERY_HOW_TO_RENT.key,
        REGISTRATION_TRACKING_LANDLORD.key,
    ],
)
def test_phase2_upload_only_non_equivalence_flags_are_enforced(scenario, expected_flag):
    req_a, _ = build_two_property_requirements(scenario)
    req_a = apply_phase2_scenario_defaults(scenario, req_a)
    admin_a = enrich_requirement_projection(
        req_a,
        preview_requirement_authority_with_scoped_records(req_a, []),
        [],
        audience="admin",
    )
    if scenario.expected_workflow_class in (WC_TENANT_DELIVERY, WC_REGISTRATION_TRACKING):
        admin_a["allowed_evidence_modes"] = [EVIDENCE_MODE_DOCUMENT_UPLOAD]
    if expected_flag == "CONDITION_STANDARD_DOCUMENT_UPLOAD_PRIMARY":
        ta = dict(admin_a.get("take_action") or {})
        pri = dict((ta.get("primary") or {}))
        pri["intent"] = "upload_evidence"
        pri["kind"] = "navigate"
        pri["label"] = "Upload certificate"
        ta["primary"] = pri
        admin_a["take_action"] = ta
        admin_a["allowed_evidence_modes"] = [EVIDENCE_MODE_DOCUMENT_UPLOAD]
    mismatch_ids = workflow_mismatch_ids(admin_a, scenario.expected_workflow_class)
    assert expected_flag in mismatch_ids


def test_condition_standard_operational_signals_and_audit_metadata_are_visible():
    for scenario in (CONDITION_STANDARD_FITNESS, CONDITION_STANDARD_REPAIRING):
        req_a, _ = build_two_property_requirements(scenario)
        req_a = apply_phase2_scenario_defaults(scenario, req_a)
        preview_a = preview_requirement_authority_with_scoped_records(req_a, [])
        admin_a = enrich_requirement_projection(req_a, preview_a, [], audience="admin")
        client_ta = resolver_projection(req_a)
        mismatch_ids = workflow_mismatch_ids(admin_a, scenario.expected_workflow_class)

        # Operational-convergence internals are intentionally not orchestrated in this harness.
        # We assert deterministic governance-facing signals and drift flags instead.
        assert "workflow_class_reference" in admin_a
        assert "workflow_mismatch_flags" in admin_a
        assert admin_a.get("workflow_class_reference") == "GUIDANCE_ONLY"
        assert "CONDITION_STANDARD_DOCUMENT_UPLOAD_PRIMARY" not in mismatch_ids
        assert str(client_ta.get("workflow_class") or "").upper() == "GUIDANCE_ONLY"
        primary = ((client_ta.get("take_action") or {}).get("primary") or {})
        assert str(primary.get("intent") or "").lower() == "view_guidance"
        assert "issue" in str(primary.get("label") or "").lower()


def test_multi_evidence_partial_component_remains_incomplete_and_action_needed():
    scenario = MULTI_EVIDENCE_SMOKE_HEAT
    req_a, req_b = build_two_property_requirements(scenario)
    req_a = apply_phase2_scenario_defaults(scenario, req_a)
    req_b = apply_phase2_scenario_defaults(scenario, req_b)
    partial_record = build_property_a_partial_multi_evidence_record(req_a)
    all_records = [partial_record]

    preview_a = preview_requirement_authority_with_scoped_records(req_a, all_records)
    preview_b = preview_requirement_authority_with_scoped_records(req_b, all_records)
    client_ta_a = resolver_projection(req_a)
    admin_a = enrich_requirement_projection(req_a, preview_a, all_records, audience="admin")

    assert preview_b["mirror"]["status"] != RequirementStatus.COMPLIANT.value
    assert admin_a.get("workflow_class_reference") == WC_MULTI_EVIDENCE
    assert str(client_ta_a.get("workflow_class") or "").upper() == "MULTI_EVIDENCE"
    assert str(((client_ta_a.get("take_action") or {}).get("primary") or {}).get("intent") or "").lower() in (
        "guided_evidence_resolution",
        "upload_evidence",
    )
    synthetic = dict(admin_a)
    synthetic["status"] = RequirementStatus.COMPLIANT.value
    synthetic["evidence_completeness"] = {
        "evaluated": True,
        "is_complete": False,
        "completeness_reason": "partial components missing",
    }
    apply_workflow_reference_audit(synthetic, published_entry=None)
    assert "INCOMPLETE_UNIFIED_REQUIREMENT" in {
        str(flag.get("id") or "") for flag in (synthetic.get("workflow_mismatch_flags") or [])
    }


def test_tenant_delivery_and_registration_tracking_are_record_led_not_certificate_style():
    for scenario, expected_class in (
        (TENANT_DELIVERY_HOW_TO_RENT, WC_TENANT_DELIVERY),
        (REGISTRATION_TRACKING_LANDLORD, WC_REGISTRATION_TRACKING),
    ):
        req_a, req_b = build_two_property_requirements(scenario)
        req_a = apply_phase2_scenario_defaults(scenario, req_a)
        req_b = apply_phase2_scenario_defaults(scenario, req_b)
        upload_only = build_property_a_upload_only_record(scenario, req_a)
        structured = build_property_a_structured_record_for_registration_or_delivery(scenario, req_a)

        preview_upload_a = preview_requirement_authority_with_scoped_records(req_a, [upload_only])
        preview_structured_a = preview_requirement_authority_with_scoped_records(req_a, [structured])
        preview_structured_b = preview_requirement_authority_with_scoped_records(req_b, [structured])
        admin_a = enrich_requirement_projection(req_a, preview_upload_a, [upload_only], audience="admin")
        ta_a = resolver_projection(req_a)
        rules = workflow_non_equivalence_rules(expected_class)

        assert preview_upload_a["mirror"]["status"] != RequirementStatus.COMPLIANT.value
        if expected_class == WC_REGISTRATION_TRACKING:
            assert preview_structured_a["mirror"]["status"] != RequirementStatus.COMPLIANT.value
            assert (
                preview_structured_a["evidence_authority"].get("state_reason")
                == "registration_tracking_regulator_confirmation_not_verified"
            )
        elif expected_class == WC_TENANT_DELIVERY:
            assert preview_structured_a["mirror"]["status"] != RequirementStatus.COMPLIANT.value
            assert (
                preview_structured_a["evidence_authority"].get("state_reason")
                == "tenant_delivery_tenant_confirmation_not_verified"
            )
        assert preview_structured_b["mirror"]["status"] != RequirementStatus.COMPLIANT.value
        assert admin_a.get("workflow_class_reference") == expected_class
        assert str(ta_a.get("workflow_class") or "").upper() == expected_class
        assert str(((ta_a.get("take_action") or {}).get("primary") or {}).get("intent") or "").lower() == (
            "guided_evidence_resolution"
        )
        if expected_class == WC_TENANT_DELIVERY:
            assert "upload_not_sole_proof_of_service" in rules
        if expected_class == WC_REGISTRATION_TRACKING:
            assert "registration_record_not_regulator_live_confirmation" in rules


def test_phase2_governance_capability_assertions():
    caps_condition = get_workflow_capabilities(CONDITION_STANDARD_ACTIVE_STANDARD)
    caps_multi = get_workflow_capabilities(WC_MULTI_EVIDENCE)
    caps_delivery = get_workflow_capabilities(WC_TENANT_DELIVERY)
    caps_registration = get_workflow_capabilities(WC_REGISTRATION_TRACKING)

    assert caps_condition.get("supports_follow_up") is True
    assert caps_condition.get("may_leave_remediation_open") is True
    assert caps_condition.get("must_not_complete_from_document_only") is True
    assert str(caps_condition.get("score_impact_model") or "").lower() == "operational_convergence"

    assert caps_multi.get("must_not_complete_from_document_only") is True
    assert str(caps_multi.get("score_impact_model") or "").lower() == "multi_component"
    assert caps_multi.get("requires_structured_payload") is False

    assert caps_delivery.get("requires_structured_payload") is True
    assert caps_delivery.get("must_not_complete_from_document_only") is True

    assert caps_registration.get("requires_structured_payload") is True
    assert caps_registration.get("must_not_complete_from_document_only") is True


@pytest.mark.parametrize(
    "scenario",
    [CONDITION_STANDARD_FITNESS, CONDITION_STANDARD_REPAIRING],
    ids=lambda s: s.key,
)
def test_runtime_hardening_condition_standard_upload_only_never_projects_compliant_when_operationally_unresolved(scenario):
    req_a, req_b = build_two_property_requirements(scenario)
    req_a = apply_phase2_scenario_defaults(scenario, req_a)
    req_b = apply_phase2_scenario_defaults(scenario, req_b)
    req_a["active_standard_status_summary"] = {
        "state": "active_issues_present",
        "signal_counts": {
            "open_issues": 2,
            "open_work_orders": 1,
            "open_risk_signals": 1,
            "open_compliance_gaps": 1,
        },
        "read_only": True,
    }
    req_b["active_standard_status_summary"] = {
        "state": "active_issues_present",
        "signal_counts": {
            "open_issues": 1,
            "open_work_orders": 0,
            "open_risk_signals": 0,
            "open_compliance_gaps": 1,
        },
        "read_only": True,
    }
    verified_doc_a = build_property_a_verified_document(req_a)

    preview_a = preview_authority(req_a, [verified_doc_a], evidence_records=[])
    preview_b = preview_authority(req_b, [verified_doc_a], evidence_records=[])
    client_a = enrich_requirement_projection(req_a, preview_a, [], audience="client")
    admin_a = enrich_requirement_projection(req_a, preview_a, [], audience="admin")
    reminder_key_a = reminder_state_key_for_requirement(req_a)
    reminder_key_b = reminder_state_key_for_requirement(req_b)

    assert preview_a["mirror"]["status"] != RequirementStatus.COMPLIANT.value
    assert preview_b["mirror"]["status"] != RequirementStatus.COMPLIANT.value
    assert preview_a["evidence_authority"].get("effective_verified_document_id") == verified_doc_a["document_id"]
    assert preview_a["evidence_authority"].get("state_reason") == "operational_followup_required_condition_standard"
    assert preview_a["evidence_authority"].get("semantic_state") == "OPERATIONALLY_OPEN"

    lowered = " ".join(
        [
            str(client_a.get("status_label") or ""),
            str(client_a.get("evidence_badge_label") or ""),
            str(client_a.get("date_label") or ""),
            str(client_a.get("date_explanation_helper") or ""),
        ]
    ).lower()
    for forbidden in ("safe", "remediated", "resolved", "verified", "compliant"):
        assert forbidden not in lowered
    assert "review" in lowered or "follow-up" in lowered or "supporting evidence" in lowered

    # Heavy report/export builders are intentionally not invoked here.
    # Deterministic audit-facing metadata on enriched rows is asserted instead.
    assert admin_a.get("workflow_class_reference") == "GUIDANCE_ONLY"
    assert isinstance(admin_a.get("workflow_mismatch_flags"), list)
    assert reminder_key_a["property_id"] != reminder_key_b["property_id"]
    assert reminder_key_a["target_ref"] != reminder_key_b["target_ref"]


def test_runtime_hardening_multi_evidence_partial_components_block_compliant_projection_and_wording():
    scenario = MULTI_EVIDENCE_SMOKE_HEAT
    req_a, req_b = build_two_property_requirements(scenario)
    req_a = apply_phase2_scenario_defaults(scenario, req_a)
    req_b = apply_phase2_scenario_defaults(scenario, req_b)
    req_a["registry_metadata"] = {"evidence_resolution": {"co_alarm_required": True}}
    req_b["registry_metadata"] = {"evidence_resolution": {"co_alarm_required": True}}
    partial_record = build_property_a_partial_multi_evidence_record(req_a)
    all_records = [partial_record]
    property_ctx = {"has_fuel_burning_appliance": True}

    preview_a = preview_requirement_authority_with_scoped_records_and_property_context(req_a, all_records, property_ctx)
    preview_b = preview_requirement_authority_with_scoped_records_and_property_context(req_b, all_records, property_ctx)
    client_a = enrich_requirement_projection(req_a, preview_a, all_records, audience="client")
    admin_a = enrich_requirement_projection(req_a, preview_a, all_records, audience="admin")
    reminder_key_a = reminder_state_key_for_requirement(req_a)
    reminder_key_b = reminder_state_key_for_requirement(req_b)

    assert preview_a["mirror"]["status"] != RequirementStatus.COMPLIANT.value
    assert preview_b["mirror"]["status"] != RequirementStatus.COMPLIANT.value
    assert preview_a["evidence_authority"].get("state_reason") == "multi_evidence_components_incomplete"
    assert preview_a["evidence_authority"].get("semantic_state") == "PARTIALLY_COMPLETE"
    comp = preview_a["evidence_authority"].get("evidence_completeness") or {}
    assert comp.get("evaluated") is True
    assert comp.get("is_complete") is False
    assert int(len(comp.get("missing_components") or [])) > 0
    assert admin_a.get("workflow_class_reference") == WC_MULTI_EVIDENCE
    assert isinstance(admin_a.get("workflow_mismatch_flags"), list)
    synthetic = dict(admin_a)
    synthetic["status"] = RequirementStatus.COMPLIANT.value
    synthetic["evidence_completeness"] = {
        "evaluated": True,
        "is_complete": False,
        "completeness_reason": "partial components missing",
    }
    apply_workflow_reference_audit(synthetic, published_entry=None)
    assert "INCOMPLETE_UNIFIED_REQUIREMENT" in {
        str(flag.get("id") or "") for flag in (synthetic.get("workflow_mismatch_flags") or [])
    }

    lowered = " ".join(
        [
            str(client_a.get("status_label") or ""),
            str(client_a.get("evidence_badge_label") or ""),
            str((client_a.get("evidence_completeness") or {}).get("summary_label") or ""),
        ]
    ).lower()
    assert "incomplete" in lowered or "required" in lowered or "partial" in lowered
    for forbidden_phrase in (" evidence complete", "fully complete", "compliant", "verified", "resolved"):
        assert forbidden_phrase not in lowered

    assert reminder_key_a["property_id"] != reminder_key_b["property_id"]
    assert reminder_key_a["target_ref"] != reminder_key_b["target_ref"]


@pytest.mark.parametrize(
    "scenario",
    [EXTERNAL_ASSESSMENT_LEGIONELLA, EXTERNAL_ASSESSMENT_LEAD],
    ids=lambda s: s.key,
)
def test_runtime_hardening_external_assessment_blocks_compliant_when_follow_up_unresolved(scenario):
    req_a, req_b = build_two_property_requirements(scenario)
    if scenario.requirement_code == "lead_testing":
        req_a["jurisdiction"] = "Scotland"
        req_b["jurisdiction"] = "Scotland"
    evidence_a = build_property_a_evidence_record(scenario, req_a)
    all_records = [evidence_a]

    preview_a = preview_requirement_authority_with_scoped_records(req_a, all_records)
    preview_b = preview_requirement_authority_with_scoped_records(req_b, all_records)
    client_a = enrich_requirement_projection(req_a, preview_a, all_records, audience="client")
    admin_a = enrich_requirement_projection(req_a, preview_a, all_records, audience="admin")

    assert preview_a["mirror"]["status"] != RequirementStatus.COMPLIANT.value
    assert preview_b["mirror"]["status"] != RequirementStatus.COMPLIANT.value
    assert preview_a["evidence_authority"].get("state_reason") == "external_assessment_remediation_or_followup_unresolved"
    assert preview_a["evidence_authority"].get("semantic_state") == "ASSESSMENT_FOLLOWUP_REQUIRED"
    assert preview_a["evidence_authority"].get("primary_evidence_record_id") == evidence_a["evidence_record_id"]

    lowered = " ".join(
        [str(client_a.get("status_label") or ""), str(client_a.get("evidence_badge_label") or "")]
    ).lower()
    assert "follow-up" in lowered or "remediation" in lowered
    for phrase in ("operationally safe", "remediated", "compliant", "verified"):
        assert phrase not in lowered

    assert admin_a.get("workflow_class_reference") == WC_EXTERNAL_ASSESSMENT_EVIDENCE
    assert isinstance(admin_a.get("workflow_mismatch_flags"), list)

    assert reminder_state_key_for_requirement(req_a)["property_id"] != reminder_state_key_for_requirement(req_b)[
        "property_id"
    ]


@pytest.mark.parametrize(
    "scenario",
    [GUIDED_DECLARATION_TENANCY, GUIDED_DECLARATION_DEPOSIT_PI],
    ids=lambda s: s.key,
)
def test_runtime_hardening_guided_declaration_blocks_certificate_style_projection(scenario):
    """
    Phase 4: structured declarations must not project certificate / external verification semantics.
    Harness uses policy-shaped structured rows only; completeness engines may add further gates elsewhere.
    """
    req_a, req_b = build_two_property_requirements(scenario)
    evidence_a = build_property_a_evidence_record(scenario, req_a)
    all_records = [evidence_a]

    preview_a = preview_requirement_authority_with_scoped_records(req_a, all_records)
    preview_b = preview_requirement_authority_with_scoped_records(req_b, all_records)
    client_a = enrich_requirement_projection(req_a, preview_a, all_records, audience="client")
    admin_a = enrich_requirement_projection(req_a, preview_a, all_records, audience="admin")

    assert preview_a["mirror"]["status"] != RequirementStatus.COMPLIANT.value
    assert preview_b["mirror"]["status"] != RequirementStatus.COMPLIANT.value
    assert preview_a["evidence_authority"].get("state_reason") == "guided_declaration_not_independently_verified"
    assert preview_a["evidence_authority"].get("semantic_state") == "DECLARATION_RECORDED"
    assert preview_a["evidence_authority"].get("primary_evidence_record_id") == evidence_a["evidence_record_id"]
    assert scoped_records_for_requirement(all_records, req_a)[0].get("evidence_record_id") == evidence_a["evidence_record_id"]

    lowered = " ".join(
        [str(client_a.get("status_label") or ""), str(client_a.get("evidence_badge_label") or "")]
    ).lower()
    assert "declaration recorded" in lowered
    collapsed = lowered.replace("not externally verified", "")
    for phrase in ("externally verified", "certified", "independently confirmed", "legally validated", "compliant"):
        assert phrase not in collapsed
    assert "verified" not in collapsed

    assert admin_a.get("workflow_class_reference") == WC_GUIDED_DECLARATION
    assert isinstance(admin_a.get("workflow_mismatch_flags"), list)

    assert reminder_state_key_for_requirement(req_a)["property_id"] != reminder_state_key_for_requirement(req_b)[
        "property_id"
    ]


def test_runtime_hardening_guided_declaration_supporting_document_does_not_project_compliant():
    """Supporting uploads remain secondary; document-only must not collapse to compliant mirror."""
    scenario = GUIDED_DECLARATION_TENANCY
    req_a, _ = build_two_property_requirements(scenario)
    verified = build_property_a_verified_document(req_a)
    policy = effective_evidence_resolution(req_a)
    preview_doc = preview_authority(req_a, [verified], evidence_records=[], evidence_policy=policy)
    client_doc = enrich_requirement_projection(req_a, preview_doc, [], audience="client")

    assert preview_doc["mirror"]["status"] != RequirementStatus.COMPLIANT.value
    assert preview_doc["evidence_authority"].get("state_reason") == "guided_declaration_not_independently_verified"
    lowered = " ".join(
        [str(client_doc.get("status_label") or ""), str(client_doc.get("evidence_badge_label") or "")]
    ).lower()
    # No structured rows: client copy stays default; still must not claim external verification in badge.
    assert "externally verified" not in lowered


@pytest.mark.parametrize(
    "scenario",
    [REGISTRATION_TRACKING_LANDLORD, REGISTRATION_TRACKING_RENT_SMART_WALES],
    ids=lambda s: s.key,
)
def test_runtime_hardening_registration_tracking_blocks_authority_style_projection(scenario):
    """
    Phase 5: registration records must not project regulator/government confirmation or licensed semantics.
    Harness uses policy-shaped structured rows; live register confirmation is not modelled here.
    """
    req_a, req_b = build_two_property_requirements(scenario)
    req_a = apply_phase2_scenario_defaults(scenario, req_a)
    req_b = apply_phase2_scenario_defaults(scenario, req_b)
    evidence_a = build_property_a_evidence_record(scenario, req_a)
    all_records = [evidence_a]

    preview_a = preview_requirement_authority_with_scoped_records(req_a, all_records)
    preview_b = preview_requirement_authority_with_scoped_records(req_b, all_records)
    client_a = enrich_requirement_projection(req_a, preview_a, all_records, audience="client")
    admin_a = enrich_requirement_projection(req_a, preview_a, all_records, audience="admin")

    assert preview_a["mirror"]["status"] != RequirementStatus.COMPLIANT.value
    assert preview_b["mirror"]["status"] != RequirementStatus.COMPLIANT.value
    assert preview_a["evidence_authority"].get("state_reason") == "registration_tracking_regulator_confirmation_not_verified"
    assert preview_a["evidence_authority"].get("semantic_state") == "REGISTRATION_RECORDED"
    assert preview_a["evidence_authority"].get("primary_evidence_record_id") == evidence_a["evidence_record_id"]
    assert scoped_records_for_requirement(all_records, req_a)[0].get("evidence_record_id") == evidence_a["evidence_record_id"]

    lowered = " ".join(
        [str(client_a.get("status_label") or ""), str(client_a.get("evidence_badge_label") or "")]
    ).lower()
    assert "registration details recorded" in lowered
    assert "authority confirmation not verified externally" in lowered
    for phrase in (
        "government verified",
        "regulator approved",
        "licensed by",
        "authority verified",
        "compliant",
        "officially approved",
        "externally validated",
    ):
        assert phrase not in lowered

    assert admin_a.get("workflow_class_reference") == WC_REGISTRATION_TRACKING
    assert isinstance(admin_a.get("workflow_mismatch_flags"), list)

    assert reminder_state_key_for_requirement(req_a)["property_id"] != reminder_state_key_for_requirement(req_b)[
        "property_id"
    ]


def test_runtime_hardening_registration_tracking_supporting_document_does_not_project_compliant():
    scenario = REGISTRATION_TRACKING_LANDLORD
    req_a, _ = build_two_property_requirements(scenario)
    req_a = apply_phase2_scenario_defaults(scenario, req_a)
    verified = build_property_a_verified_document(req_a)
    policy = effective_evidence_resolution(req_a)
    preview_doc = preview_authority(req_a, [verified], evidence_records=[], evidence_policy=policy)
    client_doc = enrich_requirement_projection(req_a, preview_doc, [], audience="client")

    assert preview_doc["mirror"]["status"] != RequirementStatus.COMPLIANT.value
    assert preview_doc["evidence_authority"].get("state_reason") == "registration_tracking_regulator_confirmation_not_verified"
    lowered = " ".join(
        [str(client_doc.get("status_label") or ""), str(client_doc.get("evidence_badge_label") or "")]
    ).lower()
    assert "government verified" not in lowered
    assert "regulator approved" not in lowered


def test_runtime_hardening_tenant_delivery_blocks_confirmation_style_projection():
    """
    Phase 6: delivery records must not project tenant-confirmed / legally proven served semantics.
    """
    scenario = TENANT_DELIVERY_HOW_TO_RENT
    req_a, req_b = build_two_property_requirements(scenario)
    req_a = apply_phase2_scenario_defaults(scenario, req_a)
    req_b = apply_phase2_scenario_defaults(scenario, req_b)
    evidence_a = build_property_a_evidence_record(scenario, req_a)
    all_records = [evidence_a]

    preview_a = preview_requirement_authority_with_scoped_records(req_a, all_records)
    preview_b = preview_requirement_authority_with_scoped_records(req_b, all_records)
    client_a = enrich_requirement_projection(req_a, preview_a, all_records, audience="client")
    admin_a = enrich_requirement_projection(req_a, preview_a, all_records, audience="admin")

    assert preview_a["mirror"]["status"] != RequirementStatus.COMPLIANT.value
    assert preview_b["mirror"]["status"] != RequirementStatus.COMPLIANT.value
    assert preview_a["evidence_authority"].get("state_reason") == "tenant_delivery_tenant_confirmation_not_verified"
    assert preview_a["evidence_authority"].get("semantic_state") == "TENANT_DELIVERY_RECORDED"
    assert preview_a["evidence_authority"].get("primary_evidence_record_id") == evidence_a["evidence_record_id"]
    assert scoped_records_for_requirement(all_records, req_a)[0].get("evidence_record_id") == evidence_a["evidence_record_id"]

    lowered = " ".join(
        [str(client_a.get("status_label") or ""), str(client_a.get("evidence_badge_label") or "")]
    ).lower()
    assert "delivery recorded" in lowered
    assert "tenant receipt not independently confirmed" in lowered
    for phrase in (
        "tenant confirmed",
        "legally proven",
        "acknowledged served",
        "externally verified",
        "compliant",
    ):
        assert phrase not in lowered

    assert admin_a.get("workflow_class_reference") == WC_TENANT_DELIVERY
    assert isinstance(admin_a.get("workflow_mismatch_flags"), list)

    assert reminder_state_key_for_requirement(req_a)["property_id"] != reminder_state_key_for_requirement(req_b)[
        "property_id"
    ]


def test_runtime_hardening_tenant_delivery_supporting_document_does_not_project_compliant():
    scenario = TENANT_DELIVERY_HOW_TO_RENT
    req_a, _ = build_two_property_requirements(scenario)
    req_a = apply_phase2_scenario_defaults(scenario, req_a)
    verified = build_property_a_verified_document(req_a)
    policy = effective_evidence_resolution(req_a)
    preview_doc = preview_authority(req_a, [verified], evidence_records=[], evidence_policy=policy)
    client_doc = enrich_requirement_projection(req_a, preview_doc, [], audience="client")

    assert preview_doc["mirror"]["status"] != RequirementStatus.COMPLIANT.value
    assert preview_doc["evidence_authority"].get("state_reason") == "tenant_delivery_tenant_confirmation_not_verified"
    lowered = " ".join(
        [str(client_doc.get("status_label") or ""), str(client_doc.get("evidence_badge_label") or "")]
    ).lower()
    assert "tenant confirmed" not in lowered
    assert "legally proven" not in lowered


def test_runtime_hardening_document_upload_missing_expiry_blocks_compliant_and_client_copy():
    """Phase 7: verified certificate without authoritative expiry must not project compliant/current."""
    scenario = DOCUMENT_UPLOAD_GAS
    req_a, req_b = build_two_property_requirements(scenario)
    doc_no_exp = build_property_a_verified_document_no_expiry(req_a)
    policy = effective_evidence_resolution(req_a)
    preview_a = preview_authority(req_a, [doc_no_exp], evidence_records=[], evidence_policy=policy)
    preview_b = preview_authority(req_b, [doc_no_exp], evidence_records=[], evidence_policy=policy)
    client_a = enrich_requirement_projection(req_a, preview_a, [], audience="client")
    admin_a = enrich_requirement_projection(req_a, preview_a, [], audience="admin")

    assert preview_a["mirror"]["status"] != RequirementStatus.COMPLIANT.value
    assert preview_a["evidence_authority"].get("state_reason") == "document_upload_missing_required_expiry_semantics"
    assert preview_a["evidence_authority"].get("semantic_state") == "EXPIRY_REVIEW_REQUIRED"
    assert preview_b["mirror"]["status"] != RequirementStatus.COMPLIANT.value

    lowered = " ".join(
        [str(client_a.get("status_label") or ""), str(client_a.get("evidence_badge_label") or "")]
    ).lower()
    assert "expiry review required" in lowered or "certificate on file" in lowered
    for phrase in ("compliant", "verified", "accepted", "in-force", "satisfactory", "current certificate"):
        assert phrase not in lowered

    assert admin_a.get("workflow_class_reference") == WC_DOCUMENT_UPLOAD
    assert isinstance(admin_a.get("workflow_mismatch_flags"), list)
    assert reminder_state_key_for_requirement(req_a)["property_id"] != reminder_state_key_for_requirement(req_b)[
        "property_id"
    ]


def test_runtime_hardening_document_upload_expired_not_compliant():
    scenario = DOCUMENT_UPLOAD_GAS
    req_a, _ = build_two_property_requirements(scenario)
    past = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
    doc = {**build_property_a_verified_document(req_a), "expiry_date": past}
    policy = effective_evidence_resolution(req_a)
    preview = preview_authority(req_a, [doc], evidence_records=[], evidence_policy=policy)
    assert preview["evidence_authority"]["state"] == EA_VERIFIED_EXPIRED
    assert preview["mirror"]["status"] == RequirementStatus.OVERDUE.value


def test_runtime_hardening_document_upload_verified_with_future_expiry_can_project_compliant():
    scenario = DOCUMENT_UPLOAD_GAS
    req_a, _ = build_two_property_requirements(scenario)
    doc = build_property_a_verified_document(req_a)
    policy = effective_evidence_resolution(req_a)
    preview = preview_authority(req_a, [doc], evidence_records=[], evidence_policy=policy)
    assert preview["evidence_authority"]["state"] == "VERIFIED_CURRENT"
    assert preview["mirror"]["status"] in (
        RequirementStatus.COMPLIANT.value,
        RequirementStatus.EXPIRING_SOON.value,
    )
