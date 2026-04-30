"""Tests for applicability provenance selector (PR1)."""
from __future__ import annotations

import pytest

from services.applicability_provenance_constants import (
    OPERATOR_OVERRIDE,
    PIPELINE,
    RECONCILIATION_LOCK,
    RESERVED_RESOLUTION_SOURCES,
    SYSTEM_FALLBACK,
    validate_resolution_source_for_persist,
)
from services.applicability_provenance_selector import (
    build_applicability_provenance_document,
    build_provenance_mongo_set,
    provenance_flat_fields_in_sync,
    select_effective_applicability,
)


@pytest.mark.parametrize(
    "pipeline,ov_active,ov_state,expect_eff,expect_src",
    [
        ("UNKNOWN", False, None, "UNKNOWN", PIPELINE),
        ("REQUIRED", False, None, "REQUIRED", PIPELINE),
        ("NOT_REQUIRED", False, None, "NOT_REQUIRED", PIPELINE),
        ("UNKNOWN", True, "REQUIRED", "REQUIRED", OPERATOR_OVERRIDE),
        ("REQUIRED", True, "NOT_REQUIRED", "NOT_REQUIRED", OPERATOR_OVERRIDE),
        ("UNKNOWN", True, "UNKNOWN", "UNKNOWN", PIPELINE),
        ("UNKNOWN", True, None, "UNKNOWN", PIPELINE),
        ("invalid", False, None, "UNKNOWN", PIPELINE),
    ],
)
def test_select_effective_applicability(
    pipeline: str, ov_active: bool, ov_state, expect_eff: str, expect_src: str
) -> None:
    eff, src = select_effective_applicability(
        pipeline_applicability_state=pipeline,
        operator_override_active=ov_active,
        operator_override_applicability_state=ov_state,
    )
    assert eff == expect_eff
    assert src == expect_src
    assert src not in RESERVED_RESOLUTION_SOURCES


def test_validate_resolution_source_v1_only() -> None:
    assert validate_resolution_source_for_persist(PIPELINE)[0] is True
    assert validate_resolution_source_for_persist(OPERATOR_OVERRIDE)[0] is True
    ok, _ = validate_resolution_source_for_persist(RECONCILIATION_LOCK)
    assert ok is False
    ok, _ = validate_resolution_source_for_persist(SYSTEM_FALLBACK)
    assert ok is False


def test_build_provenance_mongo_set_rejects_reserved_source() -> None:
    with pytest.raises(ValueError):
        build_applicability_provenance_document(
            pipeline_applicability_state="UNKNOWN",
            effective_applicability_state="UNKNOWN",
            applicability_resolution_source=RECONCILIATION_LOCK,
            operator_override_active=False,
        )


def test_build_provenance_mongo_set_nested_and_flat_match() -> None:
    patch = build_provenance_mongo_set(
        pipeline_applicability_state="REQUIRED",
        operator_override_active=False,
    )
    assert patch["pipeline_applicability_state"] == patch["applicability_provenance"]["pipeline_applicability_state"]
    assert patch["effective_applicability_state"] == patch["applicability_provenance"]["effective_applicability_state"]
    assert patch["applicability_resolution_source"] == patch["applicability_provenance"][
        "applicability_resolution_source"
    ]
    assert patch["operator_override_active"] is False
    assert patch["applicability_provenance"]["operator_override"]["active"] is False


def test_provenance_flat_fields_in_sync() -> None:
    doc = {
        "pipeline_applicability_state": "UNKNOWN",
        "effective_applicability_state": "UNKNOWN",
        "applicability_resolution_source": PIPELINE,
        "operator_override_active": False,
        "applicability_provenance": {
            "pipeline_applicability_state": "UNKNOWN",
            "effective_applicability_state": "UNKNOWN",
            "applicability_resolution_source": PIPELINE,
            "operator_override": {"active": False, "applicability_state": None},
        },
    }
    assert provenance_flat_fields_in_sync(doc) is True
    doc["effective_applicability_state"] = "REQUIRED"
    assert provenance_flat_fields_in_sync(doc) is False
