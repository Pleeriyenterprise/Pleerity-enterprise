"""
Enterprise compliance scoring: deterministic score, event-driven recalc, persistence, audit.
Tests: calculate_property_compliance determinism, recalculate_and_persist (history + audit),
expiry rollover job, dashboard read path (stored score).
"""
import pytest
import sys
from pathlib import Path
from datetime import datetime, timezone, date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))


@pytest.fixture
def mock_db_property_single():
    """One property, 3 requirements, 2 docs (one VERIFIED)."""
    properties = [
        {"property_id": "p1", "client_id": "c1", "is_hmo": False},
    ]
    requirements = [
        {"property_id": "p1", "requirement_id": "r1", "requirement_type": "GAS_SAFETY", "status": "COMPLIANT", "due_date": (datetime.now(timezone.utc) + timedelta(days=200)).isoformat()},
        {"property_id": "p1", "requirement_id": "r2", "requirement_type": "EICR", "status": "PENDING", "due_date": (datetime.now(timezone.utc) + timedelta(days=100)).isoformat()},
        {"property_id": "p1", "requirement_id": "r3", "requirement_type": "EPC", "status": "EXPIRING_SOON", "due_date": (datetime.now(timezone.utc) + timedelta(days=14)).isoformat()},
    ]
    documents = [
        {"property_id": "p1", "requirement_id": "r1", "status": "VERIFIED"},
        {"property_id": "p1", "requirement_id": "r2", "status": "UPLOADED"},
    ]
    return properties, requirements, documents


class TestCalculatePropertyComplianceDeterminism:
    """Same DB state + same as_of_date -> same score and breakdown."""

    @pytest.mark.asyncio
    async def test_determinism_same_state_twice(self, mock_db_property_single):
        from services.compliance_scoring_service import calculate_property_compliance

        properties, requirements, documents = mock_db_property_single
        db = MagicMock()
        db.properties.find_one = AsyncMock(return_value=properties[0])
        db.requirements.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=requirements)))
        db.documents.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=documents)))

        with patch("services.compliance_scoring_service.database.get_db", return_value=db):
            result1 = await calculate_property_compliance("p1", as_of_date=date(2026, 2, 12))
            result2 = await calculate_property_compliance("p1", as_of_date=date(2026, 2, 12))
        assert result1.get("error") is None
        assert result2.get("error") is None
        assert result1["score"] == result2["score"]
        assert result1.get("breakdown") == result2.get("breakdown")

    @pytest.mark.asyncio
    async def test_returns_score_and_breakdown(self, mock_db_property_single):
        from services.compliance_scoring_service import calculate_property_compliance

        properties, requirements, documents = mock_db_property_single
        db = MagicMock()
        db.properties.find_one = AsyncMock(return_value=properties[0])
        db.requirements.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=requirements)))
        db.documents.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=documents)))

        with patch("services.compliance_scoring_service.database.get_db", return_value=db):
            result = await calculate_property_compliance("p1")
        assert "score" in result
        assert 0 <= result["score"] <= 100
        assert "breakdown" in result
        for key in ("status_score", "expiry_score", "document_score", "overdue_penalty_score", "risk_score"):
            assert key in result["breakdown"]


class TestRecalculateAndPersist:
    """recalculate_and_persist updates Property, writes history, and creates AuditLog."""

    @pytest.mark.asyncio
    async def test_persists_to_property_and_history_and_audit(self, mock_db_property_single):
        from services.compliance_scoring_service import recalculate_and_persist, REASON_DOCUMENT_UPLOADED

        properties, requirements, documents = mock_db_property_single
        db = MagicMock()
        db.properties.find_one = AsyncMock(return_value={**properties[0], "compliance_score": None, "compliance_breakdown": None})
        db.requirements.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=requirements)))
        db.documents.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=documents)))
        db.properties.update_one = AsyncMock()
        db.property_compliance_score_history.insert_one = AsyncMock()

        with patch("services.compliance_scoring_service.database.get_db", return_value=db):
            with patch("services.compliance_scoring_service.create_audit_log", new_callable=AsyncMock) as audit:
                result = await recalculate_and_persist(
                    "p1",
                    REASON_DOCUMENT_UPLOADED,
                    {"id": "u1", "role": "ROLE_CLIENT_ADMIN"},
                    {"document_id": "d1"},
                )
        assert result.get("score") is not None
        db.properties.update_one.assert_called_once()
        call = db.properties.update_one.call_args
        update_payload = call[0][1]
        assert call[0][0] == {"property_id": "p1"}
        assert "compliance_score" in update_payload.get("$set", {})
        assert "compliance_breakdown" in update_payload.get("$set", {})
        assert "compliance_last_calculated_at" in update_payload.get("$set", {})
        db.property_compliance_score_history.insert_one.assert_called_once()
        history_doc = db.property_compliance_score_history.insert_one.call_args[0][0]
        assert history_doc["property_id"] == "p1"
        assert history_doc["reason"] == REASON_DOCUMENT_UPLOADED
        audit.assert_called_once()
        assert audit.call_args[1]["resource_type"] == "property"
        assert audit.call_args[1]["resource_id"] == "p1"
        assert getattr(audit.call_args[1]["action"], "value", str(audit.call_args[1]["action"])) == "COMPLIANCE_SCORE_UPDATED"


class TestExpiryRolloverJob:
    """Expiry rollover job enqueues compliance recalc for affected properties."""

    @pytest.mark.asyncio
    async def test_run_expiry_rollover_recalc_enqueues_for_affected_properties(self):
        from job_runner import run_expiry_rollover_recalc

        items = [{"property_id": "p1"}, {"property_id": "p2"}]

        class AsyncIterCursor:
            def __aiter__(self):
                return self
            def __init__(self):
                self._i = 0
            async def __anext__(self):
                if self._i >= len(items):
                    raise StopAsyncIteration
                v = items[self._i]
                self._i += 1
                return v

        db = MagicMock()
        db.requirements.find = MagicMock(return_value=AsyncIterCursor())
        db.properties.find_one = AsyncMock(side_effect=[{"client_id": "c1"}, {"client_id": "c2"}])

        with patch("job_runner.database.get_db", return_value=db):
            with patch("services.compliance_recalc_queue.enqueue_compliance_recalc", new_callable=AsyncMock, return_value=True) as enqueue:
                result = await run_expiry_rollover_recalc()
        assert enqueue.await_count == 2
        assert result.get("count") == 2
        assert "enqueued" in result.get("message", "")


class TestDashboardReadsStoredScore:
    """GET compliance-score uses stored property scores when present (no full recompute per request)."""

    @pytest.mark.asyncio
    async def test_calculate_compliance_score_uses_stored_property_scores(self):
        from services.compliance_score import calculate_compliance_score

        db = MagicMock()
        properties_with_stored = [
            {"property_id": "p1", "compliance_score": 75, "compliance_breakdown": {"status_score": 80, "expiry_score": 70, "document_score": 75, "overdue_penalty_score": 80, "risk_score": 100}, "is_hmo": False},
            {"property_id": "p2", "compliance_score": 85, "compliance_breakdown": {"status_score": 90, "expiry_score": 80, "document_score": 85, "overdue_penalty_score": 90, "risk_score": 100}, "is_hmo": False},
        ]
        db.properties.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=properties_with_stored)))
        db.requirements.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[])))

        with patch("services.compliance_score.database.get_db", return_value=db):
            result = await calculate_compliance_score("c1")
        assert result["score"] == 80
        assert "breakdown" in result
        db.properties.find.assert_called()


class TestValidateComplianceScoreEndpoint:
    """Admin validate-compliance-score: response shape, mismatch audit, fix path."""

    @pytest.mark.asyncio
    async def test_validate_match_returns_match_true_no_mismatch_audit(self):
        from routes.admin import validate_compliance_score, ValidateComplianceScoreRequest
        from models import AuditAction

        request = MagicMock()
        prop = {"property_id": "p1", "client_id": "c1", "compliance_score": 70, "compliance_breakdown": {"status_score": 70, "expiry_score": 80, "document_score": 70, "overdue_penalty_score": 80, "risk_score": 100}}
        computed = {"score": 70, "breakdown": {"status_score": 70, "expiry_score": 80, "document_score": 70, "overdue_penalty_score": 80, "risk_score": 100}}
        db = MagicMock()
        db.properties.find_one = AsyncMock(return_value=prop)

        with patch("routes.admin.admin_route_guard", new_callable=AsyncMock, return_value={"portal_user_id": "admin1"}):
            with patch("routes.admin.database.get_db", return_value=db):
                with patch("services.compliance_scoring_service.calculate_property_compliance", new_callable=AsyncMock, return_value=computed):
                    with patch("routes.admin.create_audit_log", new_callable=AsyncMock) as audit:
                        body = ValidateComplianceScoreRequest(fix=False)
                        result = await validate_compliance_score(request, "p1", body)
        assert result["property_id"] == "p1"
        assert result["stored_score"] == 70
        assert result["computed_score"] == 70
        assert result["match"] is True
        assert "diff_summary" in result
        assert result["repaired"] is False
        audit.assert_not_called()

    @pytest.mark.asyncio
    async def test_validate_mismatch_writes_mismatch_audit(self):
        from routes.admin import validate_compliance_score, ValidateComplianceScoreRequest
        from models import AuditAction

        request = MagicMock()
        prop = {"property_id": "p1", "client_id": "c1", "compliance_score": 70, "compliance_breakdown": {}}
        computed = {"score": 85, "breakdown": {"status_score": 90, "expiry_score": 80, "document_score": 85, "overdue_penalty_score": 90, "risk_score": 100}}
        db = MagicMock()
        db.properties.find_one = AsyncMock(return_value=prop)

        with patch("routes.admin.admin_route_guard", new_callable=AsyncMock, return_value={"portal_user_id": "admin1"}):
            with patch("routes.admin.database.get_db", return_value=db):
                with patch("services.compliance_scoring_service.calculate_property_compliance", new_callable=AsyncMock, return_value=computed):
                    with patch("routes.admin.create_audit_log", new_callable=AsyncMock) as audit:
                        body = ValidateComplianceScoreRequest(fix=False)
                        result = await validate_compliance_score(request, "p1", body)
        assert result["match"] is False
        assert result["stored_score"] == 70
        assert result["computed_score"] == 85
        assert result["diff_summary"]["score_delta"] == 15
        assert result["repaired"] is False
        audit.assert_called_once()
        assert getattr(audit.call_args[1]["action"], "value", str(audit.call_args[1]["action"])) == "COMPLIANCE_SCORE_MISMATCH_DETECTED"

    @pytest.mark.asyncio
    async def test_validate_mismatch_with_fix_updates_property_and_writes_repaired_audit(self):
        from routes.admin import validate_compliance_score, ValidateComplianceScoreRequest
        from models import AuditAction

        request = MagicMock()
        prop = {"property_id": "p1", "client_id": "c1", "compliance_score": 70, "compliance_breakdown": {}}
        computed = {"score": 85, "breakdown": {"status_score": 90, "expiry_score": 80, "document_score": 85, "overdue_penalty_score": 90, "risk_score": 100}, "weights_version": "v1"}
        db = MagicMock()
        db.properties.find_one = AsyncMock(return_value=prop)
        db.properties.update_one = AsyncMock()
        db.property_compliance_score_history.insert_one = AsyncMock()

        with patch("routes.admin.admin_route_guard", new_callable=AsyncMock, return_value={"portal_user_id": "admin1"}):
            with patch("routes.admin.database.get_db", return_value=db):
                with patch("services.compliance_scoring_service.calculate_property_compliance", new_callable=AsyncMock, return_value=computed):
                    with patch("routes.admin.create_audit_log", new_callable=AsyncMock) as audit:
                        body = ValidateComplianceScoreRequest(fix=True)
                        result = await validate_compliance_score(request, "p1", body)
        assert result["match"] is False
        assert result["repaired"] is True
        db.properties.update_one.assert_called_once()
        assert db.properties.update_one.call_args[0][1]["$set"]["compliance_score"] == 85
        db.property_compliance_score_history.insert_one.assert_called_once()
        history = db.property_compliance_score_history.insert_one.call_args[0][0]
        assert history["reason"] == "VALIDATOR_REPAIR"
        assert history["score"] == 85
        assert audit.await_count == 2
        actions = [getattr(c[1]["action"], "value", str(c[1]["action"])) for c in audit.call_args_list]
        assert "COMPLIANCE_SCORE_MISMATCH_DETECTED" in actions
        assert "COMPLIANCE_SCORE_REPAIRED" in actions
