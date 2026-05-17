"""C2 §9 contract tests (mocked — no staging Mongo required)."""
from __future__ import annotations

import hashlib
import json
from unittest.mock import AsyncMock, patch

import pytest

from scripts.c2_snapshot import detect_ordering_violation, fp32


def test_cross_surface_hash_stable_on_identical_payload():
    payload = {"a": 1, "b": [2, 3]}
    assert fp32(payload) == fp32(payload)


def test_temporal_ordering_settled_recalc_not_violation():
    """pending=false + open gaps + score 52 is settled recalc, not C2-RC-13."""
    snap = {
        "property_score": {"compliance_score_pending": False, "compliance_score": 52},
        "gaps": {"open_count": 5},
        "requirements_explain": {"included_count": 8},
        "dashboard_tasks": {
            "task_count": 7,
            "digest_summary": {"urgent_count": 1, "upcoming_count": 4, "in_progress_count": 2},
        },
        "risk_priority": {"priority_action_count": 7},
    }
    assert detect_ordering_violation(snap) is None


def test_temporal_ordering_downstream_asserts_resolved_while_gaps_open():
    snap = {
        "property_score": {"compliance_score_pending": False, "compliance_score": 52},
        "gaps": {"open_count": 3},
        "dashboard_tasks": {
            "task_count": 0,
            "digest_summary": {"urgent_count": 0, "upcoming_count": 0, "in_progress_count": 0},
        },
        "risk_priority": {"priority_action_count": 0},
    }
    assert detect_ordering_violation(snap) == "downstream_asserts_resolved_while_gaps_open"


def test_replay_lineage_fingerprint_equality():
    a = fp32({"corr": "REQUIREMENTS_SYNC:pid", "status": "DONE"})
    b = fp32({"corr": "REQUIREMENTS_SYNC:pid", "status": "DONE"})
    assert a == b


def test_unrelated_surface_non_mutation_delta_zero():
    from scripts.c2_snapshot import delta_fingerprints

    before = {"gaps": "abc", "property": "x"}
    after = {"gaps": "abc", "property": "x"}
    delta = delta_fingerprints(before, after)
    assert all(not v.get("changed") for v in delta.values() if isinstance(v, dict))


@pytest.mark.asyncio
async def test_downstream_exclusion_requires_reason():
    from scripts.c2_snapshot import exclusions_matrix

    explain_rows = {
        "rows": [
            {"requirement_type": "eicr", "included": True},
            {
                "requirement_type": "hidden",
                "included": False,
                "exclusion_reason": "not_required_row",
                "persistence": {},
            },
        ],
        "raw_count": 2,
        "included_count": 1,
    }
    with patch(
        "services.requirement_client_runtime_surface.explain_runtime_requirement_rows_for_property",
        new=AsyncMock(return_value=explain_rows),
    ):
        out = await exclusions_matrix(None, cid="c", pid="p")
    assert out["pass"] is True


@pytest.mark.asyncio
async def test_c2_m1_sync_enqueue_suppressed_on_duplicate():
    from scripts.c1_staging_verification import _c1_m1_sync

    class _Res:
        enqueued = False
        duplicate_suppression_reason = "duplicate_pending"
        regeneration_requeued = False

    with patch(
        "services.requirement_materialization_service.materialize_requirements_for_property",
        new=AsyncMock(return_value={"upserted": 0}),
    ), patch(
        "services.provisioning.provisioning_service"
    ) as prov, patch(
        "services.compliance_recalc_queue.enqueue_compliance_recalc",
        new=AsyncMock(return_value=_Res()),
    ):
        prov._update_property_compliance = AsyncMock()
        out = await _c1_m1_sync(None, cid="c", pid="p")
    assert out["enqueue"]["enqueued"] is False
