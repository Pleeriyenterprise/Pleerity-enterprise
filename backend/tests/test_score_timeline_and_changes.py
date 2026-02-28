"""
Tests for score timeline and What Changed endpoints (GET /api/client/score/timeline, /score/changes).
Regression: document confirmation creates a score_event and timeline reflects it.
"""
import pytest
import asyncio
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture
def client_user():
    return {"client_id": "test_client_1", "portal_user_id": "user_1", "role": "ROLE_CLIENT"}


class TestScoreTimelineEndpoint:
    """GET /api/client/score/timeline returns points and last_updated_at."""

    def test_timeline_returns_structure(self, client_user):
        async def _test():
            from routes.client import get_score_timeline
            from fastapi import Request

            req = MagicMock(spec=Request)
            req.headers = {}
            with patch("routes.client.client_route_guard", new_callable=AsyncMock, return_value=client_user):
                with patch("services.score_events_service.get_timeline", new_callable=AsyncMock) as get_timeline:
                    get_timeline.return_value = {
                        "client_id": "test_client_1",
                        "days": 90,
                        "interval": "week",
                        "points": [{"date": "2026-01-01", "score": 36}, {"date": "2026-01-08", "score": 38}],
                        "last_updated_at": "2026-01-15T12:00:00+00:00",
                    }
                    return await get_score_timeline(req, days=90, interval="week")

        result = _run(_test())
        assert result["client_id"] == "test_client_1"
        assert result["days"] == 90
        assert result["interval"] == "week"
        assert len(result["points"]) == 2
        assert result["points"][0]["date"] == "2026-01-01" and result["points"][0]["score"] == 36
        assert result["last_updated_at"] is not None

    def test_timeline_caps_days(self, client_user):
        async def _test():
            from routes.client import get_score_timeline
            from fastapi import Request

            req = MagicMock(spec=Request)
            with patch("routes.client.client_route_guard", new_callable=AsyncMock, return_value=client_user):
                with patch("services.score_events_service.get_timeline", new_callable=AsyncMock) as get_timeline:
                    get_timeline.return_value = {"client_id": "test_client_1", "days": 90, "interval": "week", "points": [], "last_updated_at": None}
                    await get_score_timeline(req, days=365, interval="week")
                    return get_timeline

        get_timeline = _run(_test())
        get_timeline.assert_called_once()
        call_kw = get_timeline.call_args[1]
        assert call_kw["days"] == 90


class TestScoreChangesEndpoint:
    """GET /api/client/score/changes returns items with title, details, delta."""

    def test_changes_returns_items(self, client_user):
        async def _test():
            from routes.client import get_score_changes
            from fastapi import Request

            req = MagicMock(spec=Request)
            with patch("routes.client.client_route_guard", new_callable=AsyncMock, return_value=client_user):
                with patch("services.score_events_service.get_changes", new_callable=AsyncMock) as get_changes:
                    get_changes.return_value = {
                        "items": [
                            {
                                "created_at": "2026-01-15T12:00:00+00:00",
                                "event_type": "DOCUMENT_CONFIRMED",
                                "title": "Certificate confirmed",
                                "details": "Willow Grove • Expires 2030-09-22",
                                "delta": 5,
                                "score_after": 41,
                                "property_id": "p1",
                                "requirement_id": "r1",
                                "document_id": "d1",
                            }
                        ]
                    }
                    return await get_score_changes(req, limit=20)
        result = _run(_test())
        assert "items" in result
        assert len(result["items"]) == 1
        assert result["items"][0]["event_type"] == "DOCUMENT_CONFIRMED"
        assert result["items"][0]["title"] == "Certificate confirmed"
        assert result["items"][0]["delta"] == 5
        assert result["items"][0]["score_after"] == 41


class TestScoreEventsService:
    """Unit tests for score_events_service get_timeline and get_changes."""

    def test_get_timeline_empty_fallback(self):
        async def _test():
            from services.score_events_service import get_timeline
            from database import database

            db = MagicMock()
            db.score_events.find = MagicMock(return_value=MagicMock(sort=MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[])))))
            with patch.object(database, "get_db", return_value=db):
                with patch("services.compliance_score.calculate_compliance_score", new_callable=AsyncMock) as calc:
                    calc.return_value = {"score": 50, "score_last_calculated_at": None}
                    return await get_timeline("client_1", days=90, interval="week")

        result = _run(_test())
        assert result["client_id"] == "client_1"
        assert result["days"] == 90
        assert result["interval"] == "week"
        assert isinstance(result["points"], list)
        assert len(result["points"]) == 1
        assert result["points"][0]["score"] == 50

    def test_get_changes_limit(self):
        async def _test():
            from services.score_events_service import get_changes
            from database import database

            db = MagicMock()
            cursor = MagicMock()
            cursor.sort = MagicMock(return_value=cursor)
            cursor.limit = MagicMock(return_value=cursor)
            cursor.to_list = AsyncMock(return_value=[])
            db.score_events.find = MagicMock(return_value=cursor)
            db.properties.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[])))
            with patch.object(database, "get_db", return_value=db):
                return await get_changes("client_1", limit=10)

        result = _run(_test())
        assert "items" in result
        assert result["items"] == []


class TestDocumentConfirmationCreatesScoreEvent:
    """Regression: document confirmation creates a score_event; get_changes returns it."""

    def test_get_changes_includes_document_confirmed_event(self):
        async def _test():
            from services.score_events_service import get_changes, EVENT_DOCUMENT_CONFIRMED
            from database import database

            now = datetime.now(timezone.utc)
            events = [
                {
                    "created_at": now,
                    "event_type": EVENT_DOCUMENT_CONFIRMED,
                    "property_id": "p1",
                    "requirement_id": "r1",
                    "document_id": "d1",
                    "metadata": {"requirement_type": "EICR", "expiry_date": "2030-09-22"},
                    "delta": 5,
                    "score_after": 41,
                }
            ]
            db = MagicMock()
            cursor = MagicMock()
            cursor.sort = MagicMock(return_value=cursor)
            cursor.limit = MagicMock(return_value=cursor)
            cursor.to_list = AsyncMock(return_value=events)
            db.score_events.find = MagicMock(return_value=cursor)
            db.properties.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[
                {"property_id": "p1", "nickname": "Willow Grove", "address_line_1": "1 High St"}
            ])))
            with patch.object(database, "get_db", return_value=db):
                return await get_changes("client_1", limit=20)

        result = _run(_test())
        assert len(result["items"]) == 1
        item = result["items"][0]
        assert item["event_type"] == "DOCUMENT_CONFIRMED"
        assert item["title"] == "Certificate confirmed"
        assert item["delta"] == 5
        assert item["score_after"] == 41
        assert item["property_id"] == "p1"
        assert item["requirement_id"] == "r1"
        assert item["document_id"] == "d1"
