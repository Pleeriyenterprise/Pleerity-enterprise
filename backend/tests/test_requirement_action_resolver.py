from services.requirement_action_resolver import (
    enrich_take_action_envelope_for_client,
    resolve_take_action_envelope,
    resolve_take_action_for_priority_action,
)


def test_resolver_includes_registry_why_it_matters():
    requirement = {
        "requirement_id": "r1",
        "property_id": "p1",
        "requirement_type": "gas_safety",
        "requirement_code": "gas_safety",
        "compliance_requirement_class": "DOCUMENT",
        "registry_metadata": {
            "why_it_matters_short_published": "Gas checks reduce safety risk and support legal compliance.",
            "why_it_matters_long_published": "Longer detail text.",
        },
    }
    out = resolve_take_action_envelope(requirement, property_id="p1", property_jurisdiction="England")
    assert out.get("why_it_matters_short", "").startswith("Gas checks reduce safety risk")
    assert out.get("why_it_matters_long") == "Longer detail text."


def test_priority_action_projection_includes_why_it_matters():
    row = {
        "related_property_id": "p1",
        "related_requirement_id": "r1",
        "requirement_code": "gas_safety",
        "jurisdiction": "England",
    }
    eng = {
        "compliance_requirement_class": "DOCUMENT",
        "registry_metadata": {"why_it_matters_short_published": "Short why"},
    }
    out = resolve_take_action_for_priority_action(row, compliance_engine=eng)
    assert out.get("why_it_matters_short") == "Short why"


def test_envelope_guided_primary_when_multiple_evidence_modes():
    requirement = {
        "requirement_id": "r1",
        "property_id": "p1",
        "requirement_type": "smoke_heat_alarms",
        "requirement_code": "smoke_heat_alarms",
        "compliance_requirement_class": "DOCUMENT",
    }
    out = resolve_take_action_envelope(requirement, property_id="p1", property_jurisdiction="England")
    pri = out["take_action"]["primary"]
    assert pri.get("kind") == "guided_evidence_resolution"
    assert pri.get("label") == "Add compliance evidence"
    assert pri.get("route") in (None, "")
    assert out["take_action"].get("secondary") in (None, {})


def test_envelope_guided_label_registry_override():
    requirement = {
        "requirement_id": "r1",
        "property_id": "p1",
        "requirement_type": "smoke_heat_alarms",
        "requirement_code": "smoke_heat_alarms",
        "compliance_requirement_class": "DOCUMENT",
        "registry_metadata": {
            "evidence_resolution": {
                "allowed_evidence_modes": [
                    "DOCUMENT_UPLOAD",
                    "STRUCTURED_DECLARATION",
                    "CONTRACTOR_CONFIRMATION",
                ],
                "guided_primary_cta_label": "Resolve requirement",
            },
        },
    }
    out = resolve_take_action_envelope(requirement, property_id="p1", property_jurisdiction="England")
    assert out["take_action"]["primary"].get("label") == "Resolve requirement"


def test_envelope_single_structured_direct_action():
    requirement = {
        "requirement_id": "r1",
        "property_id": "p1",
        "requirement_type": "custom_evidence_row",
        "compliance_requirement_class": "DOCUMENT",
        "registry_metadata": {
            "evidence_resolution": {
                "allowed_evidence_modes": ["STRUCTURED_DECLARATION"],
                "primary_resolution_workflow": "DIRECT_EVIDENCE_ACTION",
            },
        },
    }
    out = resolve_take_action_envelope(requirement, property_id="p1", property_jurisdiction="England")
    pri = out["take_action"]["primary"]
    assert pri.get("kind") == "direct_evidence_action"
    assert pri.get("evidence_mode") == "STRUCTURED_DECLARATION"
    assert "declaration" in pri.get("label", "").lower()


def test_envelope_guided_metadata_incomplete_no_upload_primary():
    """Multi-mode policy without property/requirement ids must not silently use document upload as primary."""
    requirement = {
        "requirement_id": None,
        "property_id": None,
        "requirement_type": "smoke_heat_alarms",
        "requirement_code": "smoke_heat_alarms",
        "compliance_requirement_class": "DOCUMENT",
    }
    out = resolve_take_action_envelope(requirement, property_id=None, property_jurisdiction="England")
    pri = out["take_action"]["primary"]
    assert pri.get("handler") == "guided_evidence_unavailable"
    assert pri.get("kind") == "guided_evidence_resolution"
    assert pri.get("route") in (None, "")
    assert pri.get("intent") == "guided_evidence_unavailable"


def test_how_to_rent_uses_guided_evidence_not_view_guidance_only():
    from services.compliance_evidence_record_service import TENANT_DELIVERY_WORKFLOW

    requirement = {
        "requirement_id": "r1",
        "property_id": "p1",
        "requirement_type": "how_to_rent",
        "requirement_code": "how_to_rent",
        "compliance_requirement_class": "OBLIGATION",
        "engine_informational": True,
    }
    out = resolve_take_action_envelope(requirement, property_id="p1", property_jurisdiction="England")
    assert out["action_type"] == "DOCUMENT"
    pri = out["take_action"]["primary"]
    assert pri.get("kind") == "guided_evidence_resolution"
    assert pri.get("label") == "Record How to Rent delivery"
    sec = (out["take_action"] or {}).get("secondary") or {}
    assert sec.get("label") == "Upload delivery proof"
    rich = enrich_take_action_envelope_for_client(out, requirement)
    assert rich.get("workflow_class") == TENANT_DELIVERY_WORKFLOW


def test_right_to_rent_guided_declaration_envelope_and_alias_checks():
    from services.compliance_evidence_record_service import GUIDED_DECLARATION_WORKFLOW

    for rtype, rcode in (("right_to_rent", "right_to_rent"), ("right_to_rent_checks", "right_to_rent_checks")):
        requirement = {
            "requirement_id": "r1",
            "property_id": "p1",
            "requirement_type": rtype,
            "requirement_code": rcode,
            "compliance_requirement_class": "OBLIGATION",
            "engine_informational": True,
        }
        out = resolve_take_action_envelope(requirement, property_id="p1", property_jurisdiction="England")
        assert out["action_type"] == "DOCUMENT"
        pri = out["take_action"]["primary"]
        assert pri.get("kind") == "guided_evidence_resolution"
        assert pri.get("label") == "Record Right to Rent check"
        sec = (out["take_action"] or {}).get("secondary") or {}
        assert sec.get("label") == "Upload supporting evidence"
        rich = enrich_take_action_envelope_for_client(out, requirement)
        assert rich.get("workflow_class") == GUIDED_DECLARATION_WORKFLOW


def test_deposit_pi_guided_declaration_envelope_secondary_upload_label():
    from services.compliance_evidence_record_service import GUIDED_DECLARATION_WORKFLOW

    for rtype, rcode in (
        ("deposit_pi", "deposit_pi"),
        ("deposit_prescribed_info", "deposit_prescribed_info"),
        ("tenancy_deposit_protection", "tenancy_deposit_protection"),
    ):
        requirement = {
            "requirement_id": "r1",
            "property_id": "p1",
            "requirement_type": rtype,
            "requirement_code": rcode,
            "compliance_requirement_class": "OBLIGATION",
            "engine_informational": True,
        }
        out = resolve_take_action_envelope(requirement, property_id="p1", property_jurisdiction="England")
        assert out["action_type"] == "DOCUMENT"
        pri = out["take_action"]["primary"]
        assert pri.get("kind") == "guided_evidence_resolution"
        assert pri.get("label") == "Record deposit compliance"
        sec = (out["take_action"] or {}).get("secondary") or {}
        assert sec.get("label") == "Upload deposit evidence"
        rich = enrich_take_action_envelope_for_client(out, requirement)
        assert rich.get("workflow_class") == GUIDED_DECLARATION_WORKFLOW


def test_wales_occupation_contract_guided_declaration_ctas():
    from services.compliance_evidence_record_service import GUIDED_DECLARATION_WORKFLOW

    for rtype, rcode in (("wales_occupation_contract", "wales_occupation_contract"), ("occupation_contract", "occupation_contract")):
        requirement = {
            "requirement_id": "r1",
            "property_id": "p1",
            "jurisdiction": "Wales",
            "requirement_type": rtype,
            "requirement_code": rcode,
            "compliance_requirement_class": "OBLIGATION",
            "engine_informational": True,
        }
        out = resolve_take_action_envelope(requirement, property_id="p1", property_jurisdiction="Wales")
        assert out["action_type"] == "DOCUMENT"
        pri = out["take_action"]["primary"]
        assert pri.get("kind") == "guided_evidence_resolution"
        assert pri.get("label") == "Record Wales occupation contract"
        sec = (out["take_action"] or {}).get("secondary") or {}
        assert sec.get("label") == "Upload occupation contract"
        rich = enrich_take_action_envelope_for_client(out, requirement)
        assert rich.get("workflow_class") == GUIDED_DECLARATION_WORKFLOW


def test_tenancy_agreement_guided_declaration_ctas():
    from services.compliance_evidence_record_service import GUIDED_DECLARATION_WORKFLOW

    requirement = {
        "requirement_id": "r1",
        "property_id": "p1",
        "requirement_type": "tenancy_agreement",
        "requirement_code": "tenancy_agreement",
        "compliance_requirement_class": "OBLIGATION",
        "engine_informational": True,
    }
    out = resolve_take_action_envelope(requirement, property_id="p1", property_jurisdiction="England")
    assert out["action_type"] == "DOCUMENT"
    pri = out["take_action"]["primary"]
    assert pri.get("kind") == "guided_evidence_resolution"
    assert pri.get("label") == "Record tenancy agreement"
    sec = (out["take_action"] or {}).get("secondary") or {}
    assert sec.get("label") == "Upload signed agreement"
    rich = enrich_take_action_envelope_for_client(out, requirement)
    assert rich.get("workflow_class") == GUIDED_DECLARATION_WORKFLOW


def test_occupation_contract_non_wales_does_not_force_guided_evidence():
    requirement = {
        "requirement_id": "r1",
        "property_id": "p1",
        "jurisdiction": "England",
        "requirement_type": "occupation_contract",
        "requirement_code": "occupation_contract",
        "compliance_requirement_class": "OBLIGATION",
        "engine_informational": True,
    }
    out = resolve_take_action_envelope(requirement, property_id="p1", property_jurisdiction="England")
    assert out["action_type"] == "OBLIGATION"
    pri = out["take_action"]["primary"]
    assert pri.get("intent") == "view_guidance"


def test_legionella_external_assessment_guided_ctas():
    requirement = {
        "requirement_id": "r1",
        "property_id": "p1",
        "requirement_type": "legionella",
        "requirement_code": "legionella",
        "compliance_requirement_class": "DOCUMENT",
    }
    out = resolve_take_action_envelope(requirement, property_id="p1", property_jurisdiction="England")
    assert out["action_type"] == "DOCUMENT"
    pri = out["take_action"]["primary"]
    assert pri.get("kind") == "guided_evidence_resolution"
    assert pri.get("label") == "Record Legionella risk assessment"
    sec = (out["take_action"] or {}).get("secondary") or {}
    assert sec.get("label") == "Upload assessment report"

    rich = enrich_take_action_envelope_for_client(out, requirement)
    assert rich.get("workflow_class") == "EXTERNAL_ASSESSMENT_EVIDENCE"


def test_lead_testing_external_assessment_guided_ctas():
    requirement = {
        "requirement_id": "r-lead-1",
        "property_id": "p1",
        "requirement_type": "lead_testing",
        "requirement_code": "lead_testing",
        "jurisdiction": "Scotland",
        "compliance_requirement_class": "DOCUMENT",
    }
    out = resolve_take_action_envelope(requirement, property_id="p1", property_jurisdiction="Scotland")
    assert out["action_type"] == "DOCUMENT"
    pri = out["take_action"]["primary"]
    assert pri.get("kind") == "guided_evidence_resolution"
    assert pri.get("label") == "Record lead risk assessment"
    sec = (out["take_action"] or {}).get("secondary") or {}
    assert sec.get("label") == "Upload test report"

    rich = enrich_take_action_envelope_for_client(out, requirement)
    assert rich.get("workflow_class") == "EXTERNAL_ASSESSMENT_EVIDENCE"


def test_enrich_adds_workflow_class_and_guidance_target():
    requirement = {
        "requirement_id": "r1",
        "property_id": "p1",
        "requirement_type": "generic_ob",
        "requirement_code": "generic_ob",
        "compliance_requirement_class": "OBLIGATION",
    }
    env = resolve_take_action_envelope(requirement, property_id="p1")
    rich = enrich_take_action_envelope_for_client(env, requirement)
    assert rich.get("workflow_class") == "GUIDANCE_ONLY"
    assert rich.get("guidance_target", {}).get("hash") == "compliance"


def test_active_condition_standard_cta_is_not_upload_primary():
    requirement = {
        "requirement_id": "r-active-1",
        "property_id": "p1",
        "requirement_type": "fitness_for_human_habitation",
        "requirement_code": "fitness_for_human_habitation",
        "compliance_requirement_class": "OBLIGATION",
        "engine_informational": True,
    }
    out = resolve_take_action_envelope(requirement, property_id="p1", property_jurisdiction="England")
    pri = out["take_action"]["primary"]
    assert pri.get("label") == "Manage related issues"
    assert "/operations/issues" in str(pri.get("route") or "")
    assert "upload" not in str(pri.get("label") or "").lower()
    sec = (out["take_action"] or {}).get("secondary") or {}
    assert "work-orders" in str(sec.get("route") or "")
    rich = enrich_take_action_envelope_for_client(out, requirement)
    assert rich.get("workflow_class") == "GUIDANCE_ONLY"


def test_active_condition_standard_repairing_standard_no_upload_primary():
    requirement = {
        "requirement_id": "r-active-2",
        "property_id": "p2",
        "jurisdiction": "Scotland",
        "requirement_type": "repairing_standard",
        "requirement_code": "repairing_standard",
        "compliance_requirement_class": "OBLIGATION",
        "engine_informational": True,
    }
    out = resolve_take_action_envelope(requirement, property_id="p2", property_jurisdiction="Scotland")
    pri = out["take_action"]["primary"]
    assert "upload" not in str(pri.get("label") or "").lower()
    assert "/operations/issues" in str(pri.get("route") or "")


def test_hmo_fire_single_primary_guided_no_secondary():
    requirement = {
        "requirement_id": "r1",
        "property_id": "p1",
        "requirement_type": "hmo_fire_risk",
        "requirement_code": "hmo_fire_risk",
        "compliance_requirement_class": "DOCUMENT",
    }
    out = resolve_take_action_envelope(requirement, property_id="p1", property_jurisdiction="England")
    assert out["take_action"]["primary"].get("kind") == "guided_evidence_resolution"
    assert out["take_action"].get("secondary") in (None, {})


def test_envelope_document_only_when_single_document_mode():
    requirement = {
        "requirement_id": "r1",
        "property_id": "p1",
        "requirement_type": "gas_safety",
        "requirement_code": "gas_safety",
        "compliance_requirement_class": "DOCUMENT",
    }
    out = resolve_take_action_envelope(requirement, property_id="p1", property_jurisdiction="England")
    pri = out["take_action"]["primary"]
    assert pri.get("kind") == "navigate"
    assert "/documents" in (pri.get("route") or "")
    assert "Gas" in pri.get("label") or "gas" in pri.get("label", "").lower()
    assert out["take_action"].get("secondary") in (None, {})


def test_client_surface_visible_false_suppresses_take_action():
    requirement = {
        "requirement_id": "r1",
        "property_id": "p1",
        "requirement_type": "gas_safety",
        "compliance_requirement_class": "DOCUMENT",
        "client_surface_visible": False,
    }
    out = resolve_take_action_envelope(requirement, property_id="p1")
    assert out["take_action"].get("suppressed") is True

