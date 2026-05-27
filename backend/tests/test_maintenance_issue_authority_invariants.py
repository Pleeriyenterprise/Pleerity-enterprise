"""
INV-IS-002: issue closure timestamps and canonical path.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from services.maintenance_issues_service import STATUS_CLOSED, update_issue


@pytest.mark.asyncio
async def test_update_issue_closed_sets_closed_at_inv_is_002():
    mock_db = MagicMock()
    issue = {
        "issue_id": "iss1",
        "client_id": "c1",
        "status": "in_progress",
        "description": "Leak",
        "property_id": "p1",
    }
    wo = {"status": "VERIFIED"}

    with patch("services.maintenance_issues_service.database.get_db", return_value=mock_db):
        with patch("services.maintenance_issues_service.get_issue", new_callable=AsyncMock) as get_issue:
            get_issue.side_effect = [
                issue,
                {**issue, "status": STATUS_CLOSED, "closed_at": "2026-05-27T12:00:00+00:00"},
            ]
            mock_db.work_orders.find_one = AsyncMock(return_value=wo)
            mock_db.maintenance_issues.update_one = AsyncMock()
            with patch("utils.audit.create_audit_log", new_callable=AsyncMock):
                with patch(
                    "services.compliance_outcome_engine.apply_action_outcome",
                    new_callable=AsyncMock,
                    return_value={},
                ):
                    out = await update_issue(
                        "iss1",
                        "c1",
                        status=STATUS_CLOSED,
                        closed_by="admin@test",
                        updated_by_id="admin@test",
                    )

    assert out is not None
    set_doc = mock_db.maintenance_issues.update_one.await_args[0][1]["$set"]
    assert set_doc["status"] == STATUS_CLOSED
    assert set_doc.get("closed_at")
    assert set_doc.get("closed_by") == "admin@test"


@pytest.mark.asyncio
async def test_update_issue_close_without_wo_or_note_raises_inv_is_001():
    mock_db = MagicMock()
    issue = {"issue_id": "iss2", "client_id": "c1", "status": "open", "description": "x", "property_id": "p1"}

    with patch("services.maintenance_issues_service.database.get_db", return_value=mock_db):
        with patch("services.maintenance_issues_service.get_issue", new_callable=AsyncMock, return_value=issue):
            mock_db.work_orders.find_one = AsyncMock(return_value=None)
            with pytest.raises(ValueError, match="resolution note"):
                await update_issue("iss2", "c1", status=STATUS_CLOSED)
