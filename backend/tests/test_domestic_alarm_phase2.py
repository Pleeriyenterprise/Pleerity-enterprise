"""Phase 2 domestic smoke / heat / CO alignment: registry canon, workflow MULTI_EVIDENCE, scoring FIRE_DETECTION."""

from services.compliance_scoring_v2 import compute_property_score_v2, normalize_requirement_code as scoring_normalize
from services.requirement_action_resolver import resolve_take_action_envelope
from services.requirement_code_registry import normalize_requirement_code as registry_normalize
from services.requirement_workflow_audit import WC_MULTI_EVIDENCE, resolve_workflow_class_reference


def test_registry_aliases_normalize_to_smoke_heat_alarms():
    for raw in ("fire_alarm", "fire_detection", "smoke_alarms", "co_alarms", "smoke_heat_alarms"):
        assert registry_normalize(raw) == "smoke_heat_alarms"


def test_scoring_bucket_remains_fire_detection_for_family():
    for raw in ("fire_alarm", "fire_detection", "smoke_alarms", "co_alarms", "smoke_heat_alarms"):
        assert scoring_normalize(raw) == "FIRE_DETECTION"


def test_emergency_lighting_scoring_alias_unchanged():
    assert scoring_normalize("emergency_lighting") == "FIRE_DETECTION"


def test_workflow_reference_multievidence_for_all_domestic_slugs():
    for code in ("smoke_alarms", "co_alarms", "fire_detection", "fire_alarm", "smoke_heat_alarms"):
        ref, src = resolve_workflow_class_reference(code, published_entry=None)
        assert ref == WC_MULTI_EVIDENCE
        assert src == "decision_record_fallback"


def test_resolver_guided_primary_matches_across_registry_aliases():
    base = {
        "requirement_id": "r-domestic",
        "property_id": "p-domestic",
        "compliance_requirement_class": "DOCUMENT",
    }
    codes = ("smoke_alarms", "co_alarms", "fire_detection", "fire_alarm", "smoke_heat_alarms")
    labels = []
    for c in codes:
        out = resolve_take_action_envelope({**base, "requirement_type": c, "requirement_code": c}, property_id="p-domestic")
        pri = (out.get("take_action") or {}).get("primary") or {}
        assert pri.get("kind") == "guided_evidence_resolution"
        labels.append(pri.get("label"))
    assert len(set(labels)) == 1
    assert labels[0] == "Add compliance evidence"


def test_compute_property_score_v2_same_breakdown_for_alias_and_canonical():
    property_doc = {
        "jurisdiction": "England",
        "property_id": "p-domestic",
        "has_gas_supply": False,
        "property_type": "RESIDENTIAL",
    }
    client_doc = {"default_jurisdiction": "England"}
    z = (0, 0, 0)
    a = compute_property_score_v2(
        property_doc=property_doc,
        client_doc=client_doc,
        requirements=[{"requirement_code": "smoke_alarms", "requirement_type": "smoke_alarms"}],
        documents=[],
        open_issues_count=z[0],
        overdue_work_orders_count=z[1],
        open_risks_count=z[2],
    )
    b = compute_property_score_v2(
        property_doc=property_doc,
        client_doc=client_doc,
        requirements=[{"requirement_code": "smoke_heat_alarms", "requirement_type": "smoke_heat_alarms"}],
        documents=[],
        open_issues_count=z[0],
        overdue_work_orders_count=z[1],
        open_risks_count=z[2],
    )
    da = next(r for r in a["requirement_breakdown"] if r["requirement_code"] == "FIRE_DETECTION")
    db = next(r for r in b["requirement_breakdown"] if r["requirement_code"] == "FIRE_DETECTION")
    assert da["status"] == db["status"]
    assert da["earned_points"] == db["earned_points"]
