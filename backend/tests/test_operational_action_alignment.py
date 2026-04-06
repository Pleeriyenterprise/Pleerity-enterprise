"""
Enterprise operational alignment: compliance completion evidence gate, issue closure rules,
and compliance completion outcome hook (mocked).
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from database import database as db_singleton
from services import maintenance_issues_service as mis
from services import maintenance_service


def test_compliance_work_order_completion_without_evidence_raises():
    """Completion proof is required for compliance jobs; persist is blocked until evidence exists."""

    async def _run():
        mock_db = MagicMock()
        mock_db.work_orders.find_one = AsyncMock(
            return_value={
                "status": "IN_PROGRESS",
                "client_id": "c1",
                "property_id": "p1",
                "requires_client_assignment_confirmation": False,
                "work_order_kind": "COMPLIANCE",
                "evidence_keys": [],
                "requirement_code": "gas_safety",
            }
        )
        mock_db.work_orders.find_one_and_update = AsyncMock()
        apply_mock = AsyncMock(return_value={"ok": True})
        with (
            patch.object(db_singleton, "get_db", return_value=mock_db),
            patch("services.compliance_outcome_engine.apply_action_outcome", apply_mock),
            patch("utils.audit.create_audit_log", AsyncMock()),
            patch("services.webhook_service.fire_work_order_status_changed", AsyncMock()),
            patch(
                "services.work_order_contractor_routing_service.invalidate_pending_routing_for_work_order",
                AsyncMock(),
            ),
        ):
            with pytest.raises(ValueError, match="Completion proof is required"):
                await maintenance_service.update_work_order("wo-c", status="COMPLETED")
        mock_db.work_orders.find_one_and_update.assert_not_called()
        apply_mock.assert_not_awaited()

    asyncio.run(_run())


def test_compliance_work_order_completion_triggers_outcome_with_evidence_append():
    async def _run():
        mock_db = MagicMock()

        mock_db.work_orders.find_one = AsyncMock(
            return_value={
                "status": "IN_PROGRESS",
                "client_id": "c1",
                "property_id": "p1",
                "requires_client_assignment_confirmation": False,
                "work_order_kind": "COMPLIANCE",
                "evidence_keys": [],
            }
        )
        completed_doc = {
            "work_order_id": "wo-c",
            "status": "COMPLETED",
            "client_id": "c1",
            "property_id": "p1",
            "work_order_kind": "COMPLIANCE",
            "requirement_code": "gas_safety",
            "evidence_keys": ["contractor_evidence/wo-c/x.pdf"],
            "contractor_id": "ctr1",
            "issue_id": None,
            "asset_id": None,
            "description": "Compliance job",
            "completed_at": "2026-01-01T00:00:00+00:00",
        }
        mock_db.work_orders.find_one_and_update = AsyncMock(return_value=dict(completed_doc))
        apply_mock = AsyncMock(return_value={"ok": True})
        with (
            patch.object(db_singleton, "get_db", return_value=mock_db),
            patch("services.compliance_outcome_engine.apply_action_outcome", apply_mock),
            patch("utils.audit.create_audit_log", AsyncMock()),
            patch("services.webhook_service.fire_work_order_status_changed", AsyncMock()),
            patch(
                "services.work_order_contractor_routing_service.invalidate_pending_routing_for_work_order",
                AsyncMock(),
            ),
            patch("services.maintenance_service._update_contractor_performance_on_completion", AsyncMock()),
        ):
            await maintenance_service.update_work_order(
                "wo-c",
                status="COMPLETED",
                evidence_keys_append=["contractor_evidence/wo-c/x.pdf"],
            )
        apply_mock.assert_awaited()
        wo_completed = [
            c.args[0]
            for c in apply_mock.call_args_list
            if c.args and isinstance(c.args[0], dict) and c.args[0].get("event_type") == "work_order_completed"
        ]
        assert len(wo_completed) == 1
        call_kw = wo_completed[0]
        assert call_kw.get("requirement_type") == "gas_safety"
        assert (call_kw.get("metadata") or {}).get("resolve_linked_compliance_risks") is True

    asyncio.run(_run())


def test_compliance_work_order_assignment_sets_awaiting_contractor_response():
    async def _run():
        from services.work_order_execution_constants import COMPLIANCE_BOOKING_AWAITING_CONTRACTOR_RESPONSE

        mock_db = MagicMock()
        mock_db.work_orders.find_one = AsyncMock(
            return_value={
                "status": "OPEN",
                "client_id": "c1",
                "property_id": "p1",
                "requires_client_assignment_confirmation": False,
                "work_order_kind": "COMPLIANCE",
                "evidence_keys": [],
                "description": "Compliance job",
            }
        )
        upd_doc_holder: dict = {}

        async def do_update(_filt, upd, **_kw):
            upd_doc_holder["doc"] = upd
            return {
                "work_order_id": "wo-a",
                "client_id": "c1",
                "property_id": "p1",
                "contractor_id": "ctr1",
                "work_order_kind": "COMPLIANCE",
                "status": "ASSIGNED",
                "description": "Compliance job",
                **(upd.get("$set") or {}),
            }

        mock_db.work_orders.find_one_and_update = AsyncMock(side_effect=do_update)
        mock_db.contractor_assignments.insert_one = AsyncMock()
        mock_db.contractor_job_tokens.insert_one = AsyncMock()
        mock_db.contractors.find_one = AsyncMock(return_value=None)
        with (
            patch.object(db_singleton, "get_db", return_value=mock_db),
            patch("services.contractor_service.validate_contractor_for_work_order_assignment", AsyncMock()),
            patch("utils.audit.create_audit_log", AsyncMock()),
            patch("services.webhook_service.fire_work_order_status_changed", AsyncMock()),
            patch(
                "services.work_order_contractor_routing_service.invalidate_pending_routing_for_work_order",
                AsyncMock(),
            ),
        ):
            await maintenance_service.update_work_order(
                "wo-a",
                contractor_id="ctr1",
                assigned_by="admin",
                allow_direct_contractor_assignment=True,
            )
        assert (
            upd_doc_holder["doc"]["$set"]["compliance_booking_status"]
            == COMPLIANCE_BOOKING_AWAITING_CONTRACTOR_RESPONSE
        )

    asyncio.run(_run())


def test_compliance_work_order_scheduled_at_sets_booking_scheduled():
    async def _run():
        from services.work_order_execution_constants import COMPLIANCE_BOOKING_SCHEDULED

        mock_db = MagicMock()
        mock_db.work_orders.find_one = AsyncMock(
            return_value={
                "status": "ASSIGNED",
                "client_id": "c1",
                "property_id": "p1",
                "requires_client_assignment_confirmation": False,
                "work_order_kind": "COMPLIANCE",
                "evidence_keys": [],
                "compliance_booking_status": "AWAITING_CONTRACTOR_RESPONSE",
            }
        )
        upd_doc_holder: dict = {}

        async def do_update(_filt, upd, **_kw):
            upd_doc_holder["doc"] = upd
            return {"work_order_id": "wo-s", **(upd.get("$set") or {})}

        mock_db.work_orders.find_one_and_update = AsyncMock(side_effect=do_update)
        with (
            patch.object(db_singleton, "get_db", return_value=mock_db),
            patch("utils.audit.create_audit_log", AsyncMock()),
            patch("services.webhook_service.fire_work_order_status_changed", AsyncMock()),
            patch(
                "services.work_order_contractor_routing_service.invalidate_pending_routing_for_work_order",
                AsyncMock(),
            ),
        ):
            await maintenance_service.update_work_order(
                "wo-s",
                scheduled_at="2026-06-15T14:00:00+00:00",
            )
        assert upd_doc_holder["doc"]["$set"]["compliance_booking_status"] == COMPLIANCE_BOOKING_SCHEDULED
        assert upd_doc_holder["doc"]["$set"]["scheduled_at"] == "2026-06-15T14:00:00+00:00"

    asyncio.run(_run())


def test_issue_close_requires_resolution_note_without_completed_work_order():
    async def _run():
        mock_db = MagicMock()
        mock_db.maintenance_issues.find_one = AsyncMock(
            return_value={
                "issue_id": "iss1",
                "client_id": "c1",
                "property_id": "p1",
                "status": "open",
            }
        )
        mock_db.work_orders.find_one = AsyncMock(return_value=None)
        with patch.object(db_singleton, "get_db", return_value=mock_db):
            with pytest.raises(ValueError, match="resolution note"):
                await mis.update_issue(
                    "iss1",
                    client_id="c1",
                    status="closed",
                    updated_by_id="u1",
                    closed_by="client",
                )

    asyncio.run(_run())
