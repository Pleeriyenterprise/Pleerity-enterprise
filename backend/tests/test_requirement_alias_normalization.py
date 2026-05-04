"""Phase-1 low-risk requirement code alias normalization (registry authority only)."""
import sys
from pathlib import Path

import pytest

backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))


def test_normalize_three_documented_aliases():
    from services.requirement_code_registry import normalize_requirement_code

    assert normalize_requirement_code("gas_safety_certificate") == "gas_safety"
    assert normalize_requirement_code("fire_alarm") == "smoke_heat_alarms"
    assert normalize_requirement_code("right_to_rent_checks") == "right_to_rent"


def test_engine_spec_fire_alarm_equals_fire_detection():
    from services.compliance_requirement_engine import resolve_engine_payload_from_requirement_row

    d = resolve_engine_payload_from_requirement_row({"requirement_type": "fire_detection"})
    a = resolve_engine_payload_from_requirement_row({"requirement_type": "fire_alarm"})
    assert d.get("compliance_requirement_class") == a.get("compliance_requirement_class")


def test_effective_evidence_right_to_rent_checks_matches_right_to_rent():
    from services.compliance_evidence_record_service import effective_evidence_resolution

    r = {"requirement_type": "right_to_rent", "registry_metadata": {}}
    c = {"requirement_type": "right_to_rent_checks", "registry_metadata": {}}
    assert effective_evidence_resolution(r) == effective_evidence_resolution(c)


def test_enrich_client_display_label_alias_matches_canonical():
    from services.requirement_truth import EVIDENCE_MISSING, enrich_requirement_dict

    common = {"status": "PENDING", "applicability": "REQUIRED", "expiry_source": "NONE"}
    gas = enrich_requirement_dict({**common, "requirement_type": "gas_safety"}, EVIDENCE_MISSING, audience="client")
    cert = enrich_requirement_dict({**common, "requirement_type": "gas_safety_certificate"}, EVIDENCE_MISSING, audience="client")
    assert gas["display_label"] == cert["display_label"]
    assert cert.get("canonical_requirement_code") == "gas_safety"


def test_enrich_take_action_primary_matches_canonical_gas_rows():
    from services.requirement_truth import EVIDENCE_MISSING, enrich_requirement_dict

    common = {
        "property_id": "prop-a",
        "status": "PENDING",
        "applicability": "REQUIRED",
        "expiry_source": "NONE",
    }
    a = enrich_requirement_dict({**common, "requirement_type": "gas_safety"}, EVIDENCE_MISSING, audience="client")
    b = enrich_requirement_dict({**common, "requirement_type": "gas_safety_certificate"}, EVIDENCE_MISSING, audience="client")
    assert (a.get("take_action") or {}).get("primary") == (b.get("take_action") or {}).get("primary")


def test_unrelated_requirement_unchanged_normalization():
    from services.requirement_code_registry import normalize_requirement_code

    assert normalize_requirement_code("eicr") == "eicr"


def test_client_enrichment_has_no_workflow_audit_payload_keys():
    from services.requirement_workflow_audit import WORKFLOW_DIAGNOSTIC_PAYLOAD_KEYS
    from services.requirement_truth import EVIDENCE_MISSING, enrich_requirement_dict

    r = enrich_requirement_dict(
        {"requirement_type": "eicr", "status": "PENDING", "applicability": "REQUIRED", "expiry_source": "NONE"},
        EVIDENCE_MISSING,
        audience="client",
    )
    for k in WORKFLOW_DIAGNOSTIC_PAYLOAD_KEYS:
        assert k not in r


def test_admin_enrichment_exposes_stored_and_canonical_when_alias():
    from services.requirement_truth import EVIDENCE_MISSING, enrich_requirement_dict

    r = enrich_requirement_dict(
        {
            "requirement_type": "gas_safety_certificate",
            "requirement_code": "gas_safety_certificate",
            "status": "PENDING",
            "applicability": "REQUIRED",
            "expiry_source": "NONE",
        },
        EVIDENCE_MISSING,
        audience="admin",
        published_registry_entries=None,
    )
    assert r.get("requirement_code_stored") == "gas_safety_certificate"
    assert r.get("canonical_requirement_code") == "gas_safety"
