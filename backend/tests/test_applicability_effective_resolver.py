"""PR5: applicability read resolver."""
from __future__ import annotations

from services.applicability_effective_resolver import has_provenance_storage, resolve_applicability_read_model
from services.applicability_provenance_constants import OPERATOR_OVERRIDE, PIPELINE


def test_resolve_read_model_operator_effective():
    row = {
        "pipeline_applicability_state": "UNKNOWN",
        "effective_applicability_state": "REQUIRED",
        "applicability_resolution_source": OPERATOR_OVERRIDE,
        "applicability_state": "REQUIRED",
    }
    out = resolve_applicability_read_model(row)
    assert out["pipeline_applicability_state"] == "UNKNOWN"
    assert out["effective_applicability_state"] == "REQUIRED"
    assert out["applicability_resolution_source"] == OPERATOR_OVERRIDE
    assert out["has_provenance_storage"] is True


def test_has_provenance_nested_only():
    row = {
        "applicability_provenance": {
            "pipeline_applicability_state": "REQUIRED",
            "effective_applicability_state": "REQUIRED",
            "applicability_resolution_source": PIPELINE,
        }
    }
    assert has_provenance_storage(row) is True


def test_legacy_row_no_provenance():
    row = {"applicability_state": "REQUIRED"}
    out = resolve_applicability_read_model(row)
    assert out["has_provenance_storage"] is False
    assert out["effective_applicability_state"] == "REQUIRED"
    assert out["pipeline_applicability_state"] == "REQUIRED"
