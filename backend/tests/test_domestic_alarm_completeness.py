"""Evidence completeness hints for unified domestic alarm requirement (visibility layer only)."""

from services.compliance_evidence_record_service import (
    EVIDENCE_MODE_DOCUMENT_UPLOAD,
    EVIDENCE_MODE_INSPECTION_CHECKLIST,
    EVIDENCE_MODE_STRUCTURED_DECLARATION,
)
from services.requirement_evidence_completeness import evaluate_domestic_alarm_completeness
from services.requirement_truth import EVIDENCE_MISSING, enrich_requirement_dict
from services.requirement_workflow_audit import apply_workflow_reference_audit


def _smoke_checklist_ok():
    return {
        "evidence_mode": EVIDENCE_MODE_INSPECTION_CHECKLIST,
        "evidence_record_id": "cer_1",
        "evidence_payload": {
            "checklist_answers": {"alarm_present": "PASS", "alarm_tested": "PASS"},
            "inspection_date": "2026-01-01",
            "responsible_person": "Tester",
        },
    }


def _co_declaration_ok():
    return {
        "evidence_mode": EVIDENCE_MODE_STRUCTURED_DECLARATION,
        "evidence_record_id": "cer_2",
        "evidence_payload": {"declaration_statement": "x", "structured_fields": {"note": "carbon monoxide alarm checked"}},
    }


def test_co_required_smoke_only_is_incomplete():
    req = {"requirement_type": "smoke_heat_alarms", "requirement_id": "r1"}
    prop = {"has_fuel_burning_appliance": True}
    out = evaluate_domestic_alarm_completeness(req, prop, [_smoke_checklist_ok()])
    assert out["evaluated"] is True
    assert out["is_complete"] is False
    assert out["co_alarm_required"] is True
    assert any(m["key"] == "co_alarm" for m in out["missing_components"])


def test_co_not_required_smoke_document_is_complete():
    req = {"requirement_type": "smoke_heat_alarms"}
    out = evaluate_domestic_alarm_completeness(
        req,
        {},
        [{"evidence_mode": EVIDENCE_MODE_DOCUMENT_UPLOAD, "evidence_payload": {}, "evidence_record_id": "d1"}],
    )
    assert out["is_complete"] is True
    assert out["summary_label"] == "Complete"


def test_smoke_and_co_records_complete():
    req = {"requirement_type": "smoke_heat_alarms"}
    prop = {"has_fuel_burning_appliance": True}
    out = evaluate_domestic_alarm_completeness(req, prop, [_smoke_checklist_ok(), _co_declaration_ok()])
    assert out["is_complete"] is True


def test_registry_metadata_co_required():
    req = {
        "requirement_type": "smoke_heat_alarms",
        "registry_metadata": {"co_alarm_required": True},
    }
    out = evaluate_domestic_alarm_completeness(req, {}, [_smoke_checklist_ok()])
    assert out["co_alarm_required"] is True
    assert out["is_complete"] is False


def test_alias_codes_evaluate_same_as_canonical():
    base_recs = [{"evidence_mode": EVIDENCE_MODE_DOCUMENT_UPLOAD, "evidence_payload": {}, "evidence_record_id": "x"}]
    a = evaluate_domestic_alarm_completeness({"requirement_type": "fire_alarm"}, {}, base_recs)
    b = evaluate_domestic_alarm_completeness({"requirement_type": "smoke_heat_alarms"}, {}, base_recs)
    assert a["evaluated"] and b["evaluated"]
    assert a["is_complete"] == b["is_complete"]


def test_enrich_client_payload_is_safe_subset():
    out = enrich_requirement_dict(
        {
            "requirement_type": "smoke_heat_alarms",
            "requirement_id": "r1",
            "property_id": "p1",
            "status": "PENDING",
            "applicability": "REQUIRED",
            "expiry_source": "NONE",
        },
        EVIDENCE_MISSING,
        audience="client",
        published_registry_entries=None,
        property_doc=None,
        compliance_evidence_records=[],
    )
    ec = out.get("evidence_completeness") or {}
    assert "required_components" not in ec
    assert "completeness_reason" not in ec
    assert ec.get("evaluated") is True


def test_enrich_admin_includes_full_completeness():
    out = enrich_requirement_dict(
        {
            "requirement_type": "smoke_alarms",
            "requirement_id": "r1",
            "status": "PENDING",
            "applicability": "REQUIRED",
            "expiry_source": "NONE",
        },
        EVIDENCE_MISSING,
        audience="admin",
        published_registry_entries=None,
        property_doc=None,
        compliance_evidence_records=[],
    )
    ec = out.get("evidence_completeness") or {}
    assert ec.get("required_components")


def test_audit_incomplete_unified_flag_when_status_satisfied():
    out = {
        "requirement_code": "smoke_heat_alarms",
        "requirement_type": "smoke_heat_alarms",
        "status": "COMPLIANT",
        "workflow_class": "GUIDED_EVIDENCE_RESOLUTION",
        "action_type": "DOCUMENT",
        "allowed_evidence_modes": ["DOCUMENT_UPLOAD", "STRUCTURED_DECLARATION"],
        "take_action": {"primary": {"intent": "guided_evidence_resolution", "kind": "guided_evidence_resolution"}},
        "evidence_completeness": {
            "evaluated": True,
            "is_complete": False,
            "completeness_reason": "co_alarm_evidence_required_but_missing",
            "required_components": [],
            "missing_components": [{"key": "co_alarm"}],
        },
    }
    apply_workflow_reference_audit(out, published_entry=None)
    ids = {f.get("id") for f in out.get("workflow_mismatch_flags") or []}
    assert "INCOMPLETE_UNIFIED_REQUIREMENT" in ids


def test_scoring_resolver_contract_untouched_by_completeness():
    out = enrich_requirement_dict(
        {
            "requirement_type": "smoke_heat_alarms",
            "requirement_id": "r1",
            "property_id": "p1",
            "compliance_requirement_class": "DOCUMENT",
            "status": "PENDING",
            "applicability": "REQUIRED",
            "expiry_source": "NONE",
        },
        EVIDENCE_MISSING,
        audience="client",
        compliance_evidence_records=[],
    )
    assert out.get("take_action") is not None
    assert out.get("workflow_class") is not None
