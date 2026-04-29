from services.compliance_registry_admin_service import default_draft_shell, validate_registry_draft


def _base():
    d = default_draft_shell(canonical_code="GAS_SAFETY")
    d["classification"]["criticality"] = "HIGH"
    d["jurisdiction"]["display_jurisdictions"] = ["ENGLAND"]
    d["why_it_matters_short"] = "Statutory gas safety compliance for this property."
    return d


def test_rejects_empty_allowed_modes():
    d = _base()
    d["evidence_resolution"] = {"allowed_evidence_modes": []}
    errs = validate_registry_draft(d)
    assert any("allowed_evidence_modes" in e for e in errs)


def test_rejects_legacy_workflow_without_document_upload_mode():
    d = _base()
    d["evidence_resolution"] = {
        "allowed_evidence_modes": ["STRUCTURED_DECLARATION"],
        "primary_resolution_workflow": "LEGACY_DOCUMENT_UPLOAD",
    }
    errs = validate_registry_draft(d)
    assert any("LEGACY_DOCUMENT_UPLOAD requires DOCUMENT_UPLOAD" in e for e in errs)


def test_rejects_unsupported_upload_type():
    d = _base()
    d["evidence_resolution"] = {
        "allowed_evidence_modes": ["DOCUMENT_UPLOAD", "STRUCTURED_DECLARATION"],
        "primary_resolution_workflow": "GUIDED_EVIDENCE_RESOLUTION",
        "allowed_upload_types": ["text/plain"],
    }
    errs = validate_registry_draft(d)
    assert any("allowed_upload_types" in e for e in errs)


def test_high_criticality_low_confidence_sets_review_warning_not_block():
    d = _base()
    d["evidence_resolution"] = {
        "allowed_evidence_modes": ["DOCUMENT_UPLOAD", "STRUCTURED_DECLARATION"],
        "primary_resolution_workflow": "GUIDED_EVIDENCE_RESOLUTION",
        "allow_low_non_document_satisfaction": True,
    }
    errs = validate_registry_draft(d)
    assert not errs
    assert "evidence_resolution.low_confidence_critical_warning" in (
        d.get("governance", {}).get("needs_review_fields") or []
    )


def test_supporting_upload_required_allows_non_document_only_policy():
    d = _base()
    d["evidence_resolution"] = {
        "allowed_evidence_modes": ["STRUCTURED_DECLARATION"],
        "primary_resolution_workflow": "DIRECT_EVIDENCE_ACTION",
        "supporting_upload_required": True,
    }
    errs = validate_registry_draft(d)
    assert not errs


def test_supporting_upload_required_rejects_document_only_policy():
    d = _base()
    d["evidence_resolution"] = {
        "allowed_evidence_modes": ["DOCUMENT_UPLOAD"],
        "primary_resolution_workflow": "LEGACY_DOCUMENT_UPLOAD",
        "supporting_upload_required": True,
    }
    errs = validate_registry_draft(d)
    assert any("supporting_upload_required requires at least one non-document mode" in e for e in errs)
