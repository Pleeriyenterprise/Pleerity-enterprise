from services.requirement_action_resolver import resolve_take_action_envelope, resolve_take_action_for_priority_action


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
    sec = out["take_action"].get("secondary") or {}
    assert sec.get("route") and "/documents" in sec["route"]


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

