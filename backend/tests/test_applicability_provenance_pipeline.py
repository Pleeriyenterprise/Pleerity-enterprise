"""PR3: applicability provenance pipeline merge + audit gating."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from services.applicability_provenance_constants import OPERATOR_OVERRIDE, PIPELINE
from services.applicability_provenance_pipeline import (
    applicability_provenance_signature,
    merge_provenance_into_requirement_patch,
    maybe_audit_applicability_transition,
)


def test_merge_sets_legacy_applicability_state_to_effective() -> None:
    prov = merge_provenance_into_requirement_patch({}, "REQUIRED")
    assert prov["pipeline_applicability_state"] == "REQUIRED"
    assert prov["effective_applicability_state"] == "REQUIRED"
    assert prov["applicability_state"] == "REQUIRED"


def test_merge_respects_operator_override() -> None:
    existing = {
        "applicability_provenance": {
            "operator_override": {"active": True, "applicability_state": "NOT_REQUIRED"},
            "pipeline_applicability_state": "UNKNOWN",
        },
        "operator_override_active": True,
    }
    prov = merge_provenance_into_requirement_patch(existing, "REQUIRED")
    assert prov["pipeline_applicability_state"] == "REQUIRED"
    assert prov["effective_applicability_state"] == "NOT_REQUIRED"
    assert prov["applicability_resolution_source"] == OPERATOR_OVERRIDE
    assert prov["applicability_state"] == "NOT_REQUIRED"


@pytest.mark.asyncio
async def test_maybe_audit_skips_when_unchanged() -> None:
    db = MagicMock()
    db.applicability_resolution_audit = MagicMock(insert_one=AsyncMock())
    before = {
        "pipeline_applicability_state": "UNKNOWN",
        "effective_applicability_state": "UNKNOWN",
        "applicability_resolution_source": PIPELINE,
    }
    after = merge_provenance_into_requirement_patch(before, "UNKNOWN")
    await maybe_audit_applicability_transition(
        db,
        client_id="c1",
        property_id="p1",
        requirement_id="r1",
        before=before,
        after_patch=after,
        event_type="TEST",
        actor={"type": "system", "id": "pytest"},
    )
    db.applicability_resolution_audit.insert_one.assert_not_awaited()


@pytest.mark.asyncio
async def test_maybe_audit_on_pipeline_change() -> None:
    db = MagicMock()
    db.applicability_resolution_audit = MagicMock(insert_one=AsyncMock())
    before = {"applicability_state": "UNKNOWN"}
    after = merge_provenance_into_requirement_patch(before, "REQUIRED")
    await maybe_audit_applicability_transition(
        db,
        client_id="c1",
        property_id="p1",
        requirement_id="r1",
        before=before,
        after_patch=after,
        event_type="TEST",
        actor={"type": "system", "id": "pytest"},
    )
    db.applicability_resolution_audit.insert_one.assert_awaited_once()


def test_applicability_provenance_signature_stable() -> None:
    row = {
        "pipeline_applicability_state": "UNKNOWN",
        "effective_applicability_state": "UNKNOWN",
        "applicability_resolution_source": PIPELINE,
        "operator_override_active": False,
    }
    assert applicability_provenance_signature(row) == ("UNKNOWN", "UNKNOWN", PIPELINE, False)
