"""REGISTRATION_TRACKING workflow for landlord registration–style requirements."""
import sys
from pathlib import Path

import pytest

backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))


_REG_SLUGS = (
    "landlord_registration",
    "scotland_landlord_registration",
    "landlord_registration_ni",
    "rent_smart_wales",
)


@pytest.mark.parametrize("slug", _REG_SLUGS)
def test_effective_evidence_resolution_is_registration_tracking(slug):
    from services.compliance_evidence_record_service import (
        EVIDENCE_MODE_DOCUMENT_UPLOAD,
        EVIDENCE_MODE_STRUCTURED_DECLARATION,
        REGISTRATION_TRACKING_WORKFLOW,
        effective_evidence_resolution,
    )

    pol = effective_evidence_resolution(
        {"requirement_type": slug, "requirement_code": slug, "property_id": "p1", "requirement_id": "r1"}
    )
    assert pol["primary_resolution_workflow"] == REGISTRATION_TRACKING_WORKFLOW
    assert set(pol["allowed_evidence_modes"]) == {
        EVIDENCE_MODE_STRUCTURED_DECLARATION,
        EVIDENCE_MODE_DOCUMENT_UPLOAD,
    }
    assert pol.get("checklist_schema_by_mode", {}).get(EVIDENCE_MODE_STRUCTURED_DECLARATION)


@pytest.mark.parametrize("slug", _REG_SLUGS)
def test_workflow_class_reference_fallback_registration_tracking(slug):
    from services.requirement_workflow_audit import WC_REGISTRATION_TRACKING, resolve_workflow_class_reference

    ref, src = resolve_workflow_class_reference(slug, published_entry=None)
    assert ref == WC_REGISTRATION_TRACKING
    assert src == "decision_record_fallback"


@pytest.mark.parametrize("slug", _REG_SLUGS)
def test_resolver_primary_and_secondary_registration_ctas(slug):
    from services.compliance_evidence_record_service import REGISTRATION_TRACKING_WORKFLOW
    from services.requirement_action_resolver import enrich_take_action_envelope_for_client, resolve_take_action_envelope

    req = {
        "requirement_code": slug,
        "requirement_type": slug,
        "property_id": "p1",
        "requirement_id": "r1",
        "compliance_requirement_class": "DOCUMENT",
        "requires_document": True,
        "jurisdiction": "England",
    }
    env = resolve_take_action_envelope(req, property_id="p1", property_jurisdiction="England")
    ta = env["take_action"]
    assert ta["primary"]["label"] == "Record registration details"
    assert ta["primary"]["kind"] == "guided_evidence_resolution"
    sec = ta.get("secondary")
    assert sec is not None
    assert sec["label"] == "Upload registration evidence"
    assert "documents" in (sec.get("route") or "")

    merged = enrich_take_action_envelope_for_client(env, req)
    assert merged["workflow_class"] == REGISTRATION_TRACKING_WORKFLOW


def test_resolver_document_only_legacy_override():
    """Published/registry DOCUMENT_upload-only policy keeps certificate path (fallback behaviour)."""
    from services.requirement_action_resolver import resolve_take_action_envelope

    slug = "landlord_registration"
    req = {
        "requirement_code": slug,
        "requirement_type": slug,
        "property_id": "p1",
        "requirement_id": "r1",
        "compliance_requirement_class": "DOCUMENT",
        "requires_document": True,
        "registry_metadata": {
            "evidence_resolution": {"allowed_evidence_modes": ["DOCUMENT_UPLOAD"]},
        },
    }
    env = resolve_take_action_envelope(req, property_id="p1")
    ta = env["take_action"]
    assert ta["primary"]["intent"] == "upload_evidence"
    assert ta.get("secondary") is None


def test_audit_registration_document_only_flag():
    from services.compliance_evidence_record_service import EVIDENCE_MODE_DOCUMENT_UPLOAD
    from services.requirement_workflow_audit import (
        WC_REGISTRATION_TRACKING,
        compute_workflow_mismatch_flags,
    )

    enriched = {
        "requirement_code": "landlord_registration",
        "workflow_class": "LEGACY_DOCUMENT_UPLOAD",
        "action_type": "DOCUMENT",
        "allowed_evidence_modes": [EVIDENCE_MODE_DOCUMENT_UPLOAD],
        "take_action": {"primary": {"intent": "upload_evidence", "kind": "navigate"}},
    }
    flags = compute_workflow_mismatch_flags(
        enriched,
        reference_class=WC_REGISTRATION_TRACKING,
        reference_source="decision_record_fallback",
    )
    assert any(f.get("id") == "REGISTRATION_TRACKING_DOCUMENT_ONLY" for f in flags)


def test_enrich_client_has_registration_workflow_no_audit_leak():
    from services.requirement_truth import EVIDENCE_MISSING, enrich_requirement_dict
    from services.requirement_workflow_audit import WORKFLOW_DIAGNOSTIC_PAYLOAD_KEYS

    r = enrich_requirement_dict(
        {
            "requirement_type": "rent_smart_wales",
            "requirement_code": "rent_smart_wales",
            "property_id": "p1",
            "requirement_id": "r1",
            "due_date": "2026-04-01T00:00:00+00:00",
            "expiry_source": "NONE",
            "status": "PENDING",
            "applicability": "REQUIRED",
            "jurisdiction": "Wales",
        },
        EVIDENCE_MISSING,
        audience="client",
        published_registry_entries=None,
    )
    assert r.get("workflow_class") == "REGISTRATION_TRACKING"
    for k in WORKFLOW_DIAGNOSTIC_PAYLOAD_KEYS:
        assert k not in r


def test_enrich_admin_workflow_reference_registration():
    from services.requirement_truth import EVIDENCE_MISSING, enrich_requirement_dict
    from services.requirement_workflow_audit import WC_REGISTRATION_TRACKING

    r = enrich_requirement_dict(
        {
            "requirement_type": "scotland_landlord_registration",
            "property_id": "p1",
            "requirement_id": "r1",
            "due_date": "2026-04-01T00:00:00+00:00",
            "expiry_source": "NONE",
            "status": "PENDING",
            "applicability": "REQUIRED",
            "jurisdiction": "Scotland",
        },
        EVIDENCE_MISSING,
        audience="admin",
        published_registry_entries=None,
    )
    assert r.get("workflow_class_reference") == WC_REGISTRATION_TRACKING
    assert not any(f.get("id") == "REGISTRATION_TRACKING_DOCUMENT_ONLY" for f in (r.get("workflow_mismatch_flags") or []))
