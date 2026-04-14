"""Compliance requirement engine: priority stream + enrichment metadata."""
from services.compliance_requirement_engine import (
    requirement_row_in_client_priority_stream,
    resolve_engine_payload_from_code,
    resolve_engine_payload_from_requirement_row,
    VISIBILITY_INFORMATIONAL,
)


def test_how_to_rent_informational_excluded_from_priority_streams():
    row = {"requirement_type": "how_to_rent", "requirement_code": "how_to_rent"}
    for kind in ("overdue", "expiring", "missing"):
        ok, payload = requirement_row_in_client_priority_stream(row, kind=kind)
        assert ok is False
        assert payload["engine_client_visibility"] == VISIBILITY_INFORMATIONAL


def test_gas_safety_included_in_overdue_stream():
    row = {"requirement_type": "gas_safety", "requirement_code": "gas_safety"}
    ok, _ = requirement_row_in_client_priority_stream(row, kind="overdue")
    assert ok is True


def test_missing_skipped_when_no_document_required():
    row = {"requirement_type": "how_to_rent", "requirement_code": "how_to_rent"}
    ok, _ = requirement_row_in_client_priority_stream(row, kind="missing")
    assert ok is False


def test_resolve_from_code_returns_fulfillment():
    p = resolve_engine_payload_from_code("gas_safety")
    assert p["fulfillment_mode"] == "document"
    assert p["requires_document_evidence"] is True


def test_row_event_based_override():
    row = {
        "requirement_type": "gas_safety",
        "requirement_code": "gas_safety",
        "engine_event_based": True,
    }
    ok, _ = requirement_row_in_client_priority_stream(row, kind="overdue")
    assert ok is False
    payload = resolve_engine_payload_from_requirement_row(row)
    assert payload["requirement_category"] == "event_based"


def test_row_client_surface_visible_persists_over_engine_default():
    row = {
        "requirement_type": "gas_safety",
        "requirement_code": "gas_safety",
        "client_surface_visible": False,
        "requires_document": True,
        "requires_job": False,
    }
    out = resolve_engine_payload_from_requirement_row(row)
    assert out["client_surface_visible"] is False
    assert out["requires_document"] is True
    assert out["requires_job"] is False
