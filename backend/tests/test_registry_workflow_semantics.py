"""Published-registry workflow semantics (Phase 3)."""
import sys
from pathlib import Path

backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))


def test_validate_evidence_resolution_rejects_bad_primary_workflow():
    from services.registry_workflow_semantics import validate_evidence_resolution_workflow_semantics

    errs, _ = validate_evidence_resolution_workflow_semantics(
        {"allowed_evidence_modes": ["DOCUMENT_UPLOAD"], "primary_resolution_workflow": "NOT_A_REAL_WORKFLOW"}
    )
    assert any("primary_resolution_workflow invalid" in e for e in errs)


def test_validate_evidence_resolution_requires_structured_for_guided_declaration():
    from services.registry_workflow_semantics import validate_evidence_resolution_workflow_semantics

    errs, _ = validate_evidence_resolution_workflow_semantics(
        {
            "allowed_evidence_modes": ["DOCUMENT_UPLOAD"],
            "primary_resolution_workflow": "GUIDED_DECLARATION",
        }
    )
    assert errs


def test_validate_evidence_resolution_blocks_external_assessment_document_only():
    from services.registry_workflow_semantics import validate_evidence_resolution_workflow_semantics

    errs, _ = validate_evidence_resolution_workflow_semantics(
        {
            "allowed_evidence_modes": ["DOCUMENT_UPLOAD"],
            "primary_resolution_workflow": "EXTERNAL_ASSESSMENT_EVIDENCE",
        }
    )
    assert errs


def test_registry_draft_accepts_guided_declaration_primary():
    from services.compliance_registry_admin_service import default_draft_shell, validate_registry_draft

    d = default_draft_shell(canonical_code="RIGHT_TO_RENT", scope_key="DEFAULT")
    d["evidence_resolution"] = {
        "allowed_evidence_modes": ["STRUCTURED_DECLARATION", "DOCUMENT_UPLOAD"],
        "primary_resolution_workflow": "GUIDED_DECLARATION",
    }
    errs = validate_registry_draft(d)
    assert not any("primary_resolution_workflow invalid" in e for e in errs)


def test_enrich_multi_mode_guided_uses_multi_evidence_workflow_class():
    from services.requirement_action_resolver import enrich_take_action_envelope_for_client, resolve_take_action_envelope

    req = {
        "requirement_id": "r1",
        "property_id": "p1",
        "requirement_type": "smoke_heat_alarms",
        "requirement_code": "smoke_heat_alarms",
        "compliance_requirement_class": "DOCUMENT",
        "registry_metadata": {},
    }
    env = resolve_take_action_envelope(req, property_id="p1", property_jurisdiction="England")
    rich = enrich_take_action_envelope_for_client(env, req)
    assert rich.get("workflow_class") == "MULTI_EVIDENCE"


def test_normalize_evidence_resolution_passes_through_client_workflow_class():
    from services.compliance_evidence_record_service import normalize_evidence_resolution_dict

    out = normalize_evidence_resolution_dict(
        {
            "allowed_evidence_modes": ["DOCUMENT_UPLOAD", "STRUCTURED_DECLARATION"],
            "primary_resolution_workflow": "GUIDED_EVIDENCE_RESOLUTION",
            "client_workflow_class": "MULTI_EVIDENCE",
        }
    )
    assert out.get("client_workflow_class") == "MULTI_EVIDENCE"
