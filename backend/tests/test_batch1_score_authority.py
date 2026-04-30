"""Batch 1: persisted score authority, reconciliation enqueue, JOB CTA wording."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from services.compliance_scoring_service import (
    REASON_SCORE_READ_REPAIR,
    _merge_live_compliance_with_persisted_headline,
    get_authoritative_property_compliance_for_client,
)
from services.compliance_score_reconciliation_service import enqueue_reconciliation_for_properties
from services.requirement_action_resolver import (
    INTENT_COORDINATE_INSPECTION_EVIDENCE,
    job_primary_label,
    resolve_take_action_envelope,
)


def test_merge_overwrites_headline_with_property_store():
    live = {
        "score": 50,
        "grade": "D",
        "risk_level": "High risk",
        "bucket_breakdown": {"legal_core": {"percent": 40}},
        "score_breakdown": [],
    }
    prop = {
        "compliance_score": 72,
        "risk_level": "Moderate risk",
        "compliance_bucket_breakdown": {"legal_core": {"percent": 70}},
        "score_breakdown": [{"requirement_key": "GAS_SAFETY", "status": "PENDING"}],
        "compliance_earned_points": 10,
        "compliance_applicable_points": 20,
        "compliance_top_deficits": [],
        "compliance_top_next_actions": [],
        "scoring_jurisdiction_bucket": "ENGLAND_WALES",
        "compliance_breakdown": {"status_score": 70, "expiry_score": 70, "document_score": 70, "overdue_penalty_score": 70, "risk_score": 70},
        "compliance_version": "v2_jurisdictional",
        "compliance_last_calculated_at": "2026-01-01T00:00:00+00:00",
    }
    out = _merge_live_compliance_with_persisted_headline(live, prop)
    assert out["authoritative"]["score"] == 72
    assert out["authoritative"]["score_authority"] == "persisted_headline"
    assert out["authoritative"]["bucket_breakdown"]["legal_core"]["percent"] == 70
    assert out["authoritative"]["score_breakdown"][0]["requirement_key"] == "GAS_SAFETY"


@pytest.mark.asyncio
async def test_get_authoritative_repairs_missing_score_once():
    prop_before = {
        "property_id": "p1",
        "client_id": "c1",
        "compliance_score": None,
    }
    prop_after = {**prop_before, "compliance_score": 80, "compliance_breakdown": {"status_score": 80}}

    db = MagicMock()
    db.properties.find_one = AsyncMock(side_effect=[prop_before, prop_after])

    live_payload = {
        "score": 80,
        "grade": "B",
        "color": "green",
        "risk_level": "Low risk",
        "score_breakdown": [],
        "bucket_breakdown": {},
        "breakdown": {},
        "stats": {"total_requirements": 0},
        "weights_version": "v2_jurisdictional",
    }

    with patch("services.compliance_scoring_service.database.get_db", return_value=db), patch(
        "services.compliance_scoring_service.recalculate_and_persist", new_callable=AsyncMock
    ) as mock_recalc, patch(
        "services.compliance_scoring_service.calculate_property_compliance", new_callable=AsyncMock
    ) as mock_live:
        mock_live.return_value = live_payload
        out = await get_authoritative_property_compliance_for_client("p1", "c1")
        mock_recalc.assert_called_once()
        assert mock_recalc.call_args[0][0] == "p1"
        assert mock_recalc.call_args[0][1] == REASON_SCORE_READ_REPAIR
        assert out.get("authoritative", {}).get("score_authority") == "persisted_headline"
        assert out["authoritative"]["score"] == 80


@pytest.mark.asyncio
async def test_reconciliation_enqueue_idempotent():
    rows = [
        {"property_id": "p1", "client_id": "c1"},
        {"property_id": "p2", "client_id": "c1"},
    ]

    class FakeFind:
        def __init__(self, items):
            self._items = items

        def limit(self, n):
            return self

        def __aiter__(self):
            self._i = 0
            return self

        async def __anext__(self):
            if self._i >= len(self._items):
                raise StopAsyncIteration
            x = self._items[self._i]
            self._i += 1
            return x

    class FakeProps:
        def find(self, filt, proj=None):
            return FakeFind(rows)

    class FakeDb:
        properties = FakeProps()

    calls = []

    async def fake_enqueue(**kw):
        calls.append(kw)
        return True

    with patch("services.compliance_score_reconciliation_service.database.get_db", return_value=FakeDb()), patch(
        "services.compliance_score_reconciliation_service.enqueue_compliance_recalc", side_effect=fake_enqueue
    ):
        r = await enqueue_reconciliation_for_properties(client_id="c1")
        assert r["enqueued"] == 2
        assert len(calls) == 2
        assert calls[0]["correlation_id"].startswith("RECONCILIATION_BATCH:")


def test_job_primary_label_no_book_phrase():
    s = job_primary_label({"requirement_code": "gas_safety", "display_label": ""})
    assert "Book" not in s
    assert "Coordinate" in s


def test_resolve_job_envelope_intent():
    env = resolve_take_action_envelope(
        {
            "requirement_id": "r1",
            "property_id": "p1",
            "requirement_code": "eicr",
            "compliance_requirement_class": "JOB",
            "engine_fulfillment_mode": "job",
        }
    )
    assert env["take_action"]["primary"]["intent"] == INTENT_COORDINATE_INSPECTION_EVIDENCE
