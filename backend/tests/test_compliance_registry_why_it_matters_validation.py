from services.compliance_registry_admin_service import default_draft_shell, validate_registry_draft


def test_missing_why_short_flagged_for_client_visible_actionable_requirement():
    doc = default_draft_shell(canonical_code="GAS_SAFETY", scope_key="DEFAULT")
    doc["why_it_matters_short"] = ""
    errs = validate_registry_draft(doc)
    assert any("why_it_matters_short is required" in e for e in errs)
    review = (doc.get("governance") or {}).get("needs_review_fields") or []
    assert "why_it_matters_short" in review


def test_system_only_can_omit_why_short():
    doc = default_draft_shell(canonical_code="GAS_SAFETY", scope_key="DEFAULT")
    doc["classification"]["requirement_type"] = "SYSTEM"
    doc["classification"]["client_surface_visible"] = False
    doc["why_it_matters_short"] = ""
    errs = validate_registry_draft(doc)
    assert not any("why_it_matters_short is required" in e for e in errs)
