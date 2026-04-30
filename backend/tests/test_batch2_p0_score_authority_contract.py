"""Batch 2: P0 scoring authority — contract tests (no conflicting headline scores)."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))


@pytest.fixture(autouse=True)
def _stub_enqueue():
    with patch(
        "services.compliance_recalc_queue.enqueue_compliance_recalc",
        new_callable=AsyncMock,
        return_value=True,
    ):
        yield


def test_aggregate_persisted_headline_never_fakes_100_when_missing():
    from services.compliance_score import aggregate_persisted_portfolio_headline

    assert aggregate_persisted_portfolio_headline([])["score_status"] == "unavailable"
    assert aggregate_persisted_portfolio_headline([])["portfolio_score"] is None

    rows = [
        {"property_id": "p1", "compliance_score": None, "compliance_score_pending": True},
        {"property_id": "p2", "compliance_score": None, "compliance_score_pending": False},
    ]
    out = aggregate_persisted_portfolio_headline(rows)
    assert out["portfolio_score"] is None
    assert out["score_status"] == "calculating"

    rows2 = [{"property_id": "p1", "compliance_score": None, "compliance_score_pending": False}]
    assert aggregate_persisted_portfolio_headline(rows2)["score_status"] == "reconciliation_required"

    mixed = [
        {"property_id": "p1", "compliance_score": 80, "compliance_score_pending": False},
        {"property_id": "p2", "compliance_score": None, "compliance_score_pending": False},
    ]
    out_m = aggregate_persisted_portfolio_headline(mixed)
    assert out_m["portfolio_score"] == 80
    assert out_m["score_status"] == "partial"


@pytest.mark.asyncio
async def test_portfolio_compliance_summary_headline_not_catalog_matrix():
    """Main portfolio_score must match persisted aggregate, not catalog matrix."""
    from routes.portfolio import get_compliance_summary
    from starlette.requests import Request

    headline = {
        "portfolio_score": 77,
        "risk_level": "Moderate Risk",
        "portfolio_risk_level": "Moderate Risk",
        "score_status": "ok",
        "score_status_message": None,
        "properties": [{"property_id": "p1", "client_id": "c1", "compliance_score": 77, "risk_level": "Moderate Risk"}],
        "properties_by_id": {
            "p1": {"property_id": "p1", "compliance_score": 77, "risk_level": "Moderate Risk", "compliance_score_pending": False},
        },
    }
    catalog = {
        "portfolio_score": 12,
        "risk_level": "Critical Risk",
        "portfolio_risk_level": "Critical Risk",
        "updated_at": "2026-01-01T00:00:00+00:00",
        "kpis": {"overdue": 1, "expiring_30": 0, "missing": 0, "compliant": 0},
        "properties": [
            {
                "property_id": "p1",
                "name": "A",
                "score": 12,
                "risk_level": "Critical Risk",
                "overdue_count": 1,
                "expiring_30_count": 0,
                "missing_count": 0,
            }
        ],
    }

    async def _guard(_req: Request):
        return {"client_id": "c1"}

    with patch("routes.portfolio.client_route_guard", _guard), patch(
        "routes.portfolio.get_persisted_portfolio_headline_for_summary",
        new_callable=AsyncMock,
        return_value=headline,
    ), patch(
        "routes.portfolio.get_portfolio_compliance_from_catalog",
        new_callable=AsyncMock,
        return_value=catalog,
    ):
        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "method": "GET",
            "path": "/",
            "raw_path": b"/",
            "root_path": "",
            "scheme": "http",
            "query_string": b"",
            "headers": [],
            "client": ("127.0.0.1", 123),
            "server": ("test", 80),
        }
        body = await get_compliance_summary(Request(scope))

    assert body["portfolio_score"] == 77
    assert body["portfolio_score"] != catalog["portfolio_score"]
    assert body["properties"][0]["score"] == 77
    assert body["properties"][0]["preview_matrix_score"] == 12
    preview = body.get("catalog_matrix_portfolio_preview") or {}
    assert preview.get("score_authority") == "non_authoritative_requirement_matrix"
    assert preview.get("portfolio_score") == 12


def test_merge_explanation_splits_authoritative_and_preview():
    from services.compliance_scoring_service import _merge_live_compliance_with_persisted_headline

    live = {
        "score": 40,
        "grade": "D",
        "effective_jurisdiction_label": "England",
        "stats": {"total_requirements": 3},
    }
    prop = {
        "property_id": "p1",
        "compliance_score": 88,
        "risk_level": "Moderate Risk",
        "compliance_bucket_breakdown": {"legal_core": {"percent": 70}},
        "score_breakdown": [],
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
    assert out["explanation_contract_version"] == "batch2_authoritative_split_v1"
    assert out["authoritative"]["score"] == 88
    assert out["authoritative"]["score_authority"] == "persisted_headline"
    assert out["operational_preview"]["live_engine_snapshot"]["score"] == 40
    assert out["operational_preview"]["score_authority"] == "operational_preview_only"


@pytest.mark.asyncio
async def test_property_compliance_detail_score_is_persisted_not_matrix():
    from database import database as db_singleton
    from routes.portfolio import get_property_compliance_detail_route
    from starlette.requests import Request

    db = MagicMock()
    db.properties.find_one = AsyncMock(
        side_effect=[
            {
                "property_id": "p1",
                "nickname": "N",
                "address_line_1": "1 Main",
                "compliance_score": 91,
                "risk_level": "Low Risk",
                "compliance_last_calculated_at": None,
                "jurisdiction": "England",
                "compliance_score_pending": False,
            },
            {"jurisdiction": "England"},
        ]
    )
    db.clients = MagicMock()
    db.clients.find_one = AsyncMock(return_value={"default_jurisdiction": "England"})
    db.score_change_log = MagicMock()
    db.score_change_log.find_one = AsyncMock(return_value=None)

    detail = {
        "property_id": "p1",
        "property_name": "N",
        "matrix": [],
        "property_score": 40,
        "risk_index": 0.0,
        "risk_level": "High Risk",
        "kpis": {},
    }

    async def _guard(_req: Request):
        return {"client_id": "c1"}

    with patch("routes.portfolio.client_route_guard", _guard), patch.object(
        db_singleton,
        "get_db",
        return_value=db,
    ), patch(
        "routes.portfolio.get_property_compliance_detail",
        new_callable=AsyncMock,
        return_value=detail,
    ):
        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "method": "GET",
            "path": "/",
            "raw_path": b"/",
            "root_path": "",
            "scheme": "http",
            "query_string": b"",
            "headers": [],
            "client": ("127.0.0.1", 123),
            "server": ("test", 80),
        }
        body = await get_property_compliance_detail_route(Request(scope), "p1")

    assert body["score"] == 91
    assert body["preview_matrix_score"] == 40
    assert body["risk_level"] == "Low Risk"
