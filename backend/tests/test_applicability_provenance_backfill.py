"""Tests for applicability provenance backfill helpers (PR1)."""
from __future__ import annotations

import pytest

from services.applicability_provenance_constants import PIPELINE
from services.applicability_provenance_backfill import (
    build_backfill_set_for_document,
    logical_provenance_matches_document,
    summarize_backfill_eligibility,
)
from services.applicability_provenance_selector import build_provenance_mongo_set


def test_build_backfill_set_from_legacy_applicability_state() -> None:
    doc = {"applicability_state": "REQUIRED", "status": "ACTIVE"}
    patch = build_backfill_set_for_document(doc)
    assert patch is not None
    assert patch["pipeline_applicability_state"] == "REQUIRED"
    assert patch["effective_applicability_state"] == "REQUIRED"
    assert patch["applicability_resolution_source"] == PIPELINE


def test_build_backfill_skips_when_operator_override_active_nested() -> None:
    doc = {
        "applicability_state": "UNKNOWN",
        "applicability_provenance": {
            "operator_override": {"active": True, "applicability_state": "REQUIRED"},
            "pipeline_applicability_state": "UNKNOWN",
        },
    }
    assert build_backfill_set_for_document(doc) is None


def test_build_backfill_skips_when_operator_override_active_flat() -> None:
    doc = {"applicability_state": "UNKNOWN", "operator_override_active": True}
    assert build_backfill_set_for_document(doc) is None


def test_summarize_skip_already_aligned() -> None:
    doc = {"applicability_state": "NOT_REQUIRED", "status": "NOT_REQUIRED"}
    patch = build_backfill_set_for_document(doc)
    assert patch is not None
    doc.update(patch)
    assert summarize_backfill_eligibility(doc, force_refresh_from_legacy=False) == "skip_already_aligned"


def test_summarize_update_when_missing_provenance() -> None:
    doc = {"applicability_state": "UNKNOWN"}
    assert summarize_backfill_eligibility(doc, force_refresh_from_legacy=False) == "update"


def test_logical_provenance_matches_document_operator_branch() -> None:
    patch = build_provenance_mongo_set(
        pipeline_applicability_state="UNKNOWN",
        operator_override_active=True,
        operator_override_applicability_state="REQUIRED",
    )
    doc = dict(patch)
    assert logical_provenance_matches_document(doc, patch) is True


def test_force_refresh_when_pipeline_diverges() -> None:
    doc = {
        "applicability_state": "REQUIRED",
        "applicability_provenance": {
            "pipeline_applicability_state": "UNKNOWN",
            "effective_applicability_state": "UNKNOWN",
            "applicability_resolution_source": PIPELINE,
            "operator_override": {"active": False, "applicability_state": None},
        },
        "pipeline_applicability_state": "UNKNOWN",
        "effective_applicability_state": "UNKNOWN",
        "applicability_resolution_source": PIPELINE,
        "operator_override_active": False,
    }
    assert summarize_backfill_eligibility(doc, force_refresh_from_legacy=True) == "update"


@pytest.mark.asyncio
async def test_run_backfill_dry_run_mock_db() -> None:
    from services.applicability_provenance_backfill import run_applicability_provenance_backfill

    class FakeCursor:
        def __init__(self, docs: list) -> None:
            self._docs = docs

        def sort(self, *_args, **_kwargs):  # noqa: ANN001
            return self

        def __aiter__(self):
            self._i = 0
            return self

        async def __anext__(self):
            if self._i >= len(self._docs):
                raise StopAsyncIteration
            d = self._docs[self._i]
            self._i += 1
            return d

    class FakeReq:
        def __init__(self, docs: list) -> None:
            self.docs = docs
            self.updates: list = []

        def find(self, _flt):  # noqa: ANN001
            return FakeCursor(self.docs)

        async def update_one(self, q, upd):  # noqa: ANN001
            self.updates.append((q, upd))

    class FakeDb:
        def __init__(self, docs: list) -> None:
            self.requirements = FakeReq(docs)

    docs = [
        {"requirement_id": "r1", "client_id": "c1", "applicability_state": "UNKNOWN"},
        {
            "requirement_id": "r2",
            "client_id": "c1",
            "applicability_state": "REQUIRED",
            "applicability_provenance": {"operator_override": {"active": True, "applicability_state": "REQUIRED"}},
            "operator_override_active": True,
        },
    ]
    db = FakeDb(docs)
    stats = await run_applicability_provenance_backfill(db, dry_run=True, limit=10)
    assert stats["examined"] == 2
    assert stats["updated"] == 1
    assert stats["skipped_operator_override_active"] == 1
    assert len(db.requirements.updates) == 0
