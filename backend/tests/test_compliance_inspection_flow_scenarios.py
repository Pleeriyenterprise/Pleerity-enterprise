"""
End-to-end compliance inspection scenarios (A–E) with mocked persistence.

A: Risk signal → COMPLIANCE work order; recommendation → pending confirmation; confirm assigns.
B: Alternate contractor chosen only via confirm-alternate (assignment after client choice).
C: Personal contractor path tags compliance capability + requirement code for routing.
D: Operational completion without evidence does not set resolve_linked_compliance_risks.
E: Log inspection issue creates a maintenance issue (Inspection: prefix), not a compliance WO.

Scenario D duplicates the invariant tested in test_operational_action_alignment (kept here for traceability).
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from database import database as db_singleton
from services import maintenance_issues_service as mis
from services import maintenance_service
from services import risk_signal_service
from services import work_order_contractor_routing_service as wcrs
from services.work_order_assignment_constants import ASSIGNMENT_ROUTING_PENDING_CLIENT_CONFIRMATION
from services.work_order_execution_constants import (
    COMPLIANCE_BOOKING_PENDING_CLIENT_CONFIRMATION,
    WORK_ORDER_KIND_COMPLIANCE,
)


async def test_scenario_a_arrange_compliance_from_risk_signal_uses_booking_service():
    sig = {
        "signal_id": "sig-gas",
        "client_id": "c1",
        "property_id": "p1",
        "risk_type": "gas_safety",
    }
    booking = AsyncMock(
        return_value={
            "work_order_id": "wo-compliance-1",
            "work_order_kind": WORK_ORDER_KIND_COMPLIANCE,
            "requirement_code": "gas_safety",
        }
    )
    with (
        patch.object(risk_signal_service, "get_risk_signal_by_id", new_callable=AsyncMock, return_value=sig),
        patch("services.compliance_booking_service.create_compliance_execution_work_order", booking),
    ):
        out = await risk_signal_service.arrange_compliance_inspection_from_risk_signal(
            "sig-gas",
            "c1",
            "cp12",
            "req-row-gas",
            reporter_id="u1",
            compliance_purpose="inspection",
        )
    assert out["work_order_id"] == "wo-compliance-1"
    booking.assert_awaited_once()
    kwargs = booking.await_args.kwargs
    assert kwargs.get("risk_signal_id") == "sig-gas"
    assert kwargs.get("compliance_generated_from") == "risk_signal"
    assert kwargs.get("requirement_code_raw") == "cp12"


async def test_scenario_a_compliance_recommendation_sets_booking_pending_confirmation():
    wo = {
        "work_order_id": "wo1",
        "client_id": "c1",
        "contractor_id": None,
        "status": "OPEN",
        "work_order_kind": WORK_ORDER_KIND_COMPLIANCE,
    }
    mock_db = MagicMock()
    mock_db.work_orders.update_one = AsyncMock()
    ranked = {"contractors": [{"contractor_id": "gas-safe-1", "reasons": ["Gas Safe registered"]}], "routing": {}}
    with (
        patch.object(wcrs, "_load_wo_client", new_callable=AsyncMock, return_value=wo),
        patch.object(db_singleton, "get_db", return_value=mock_db),
        patch.object(wcrs.contractor_service, "recommend_contractors_for_work_order", new_callable=AsyncMock, return_value=ranked),
        patch.object(wcrs, "_notify_client_recommendation_pending", new_callable=AsyncMock),
        patch("services.work_order_contractor_routing_service.create_audit_log", new_callable=AsyncMock),
    ):
        await wcrs.generate_and_notify_recommendation("wo1", "c1", actor_portal_user_id="u1")
    mock_db.work_orders.update_one.assert_awaited()
    set_doc = mock_db.work_orders.update_one.call_args[0][1]["$set"]
    assert set_doc.get("compliance_booking_status") == COMPLIANCE_BOOKING_PENDING_CLIENT_CONFIRMATION
    assert set_doc.get("recommended_contractor_id") == "gas-safe-1"
    assert set_doc.get("contractor_id") is None


async def test_scenario_a_confirm_recommended_assigns_contractor_after_client_confirmation():
    wo = {
        "work_order_id": "wo1",
        "client_id": "c1",
        "assignment_routing_state": ASSIGNMENT_ROUTING_PENDING_CLIENT_CONFIRMATION,
        "recommended_contractor_id": "rec-gas",
        "contractor_id": None,
    }
    with (
        patch.object(wcrs, "_load_wo_client", new_callable=AsyncMock, return_value=wo),
        patch.object(maintenance_service, "update_work_order", new_callable=AsyncMock, return_value={"ok": True}) as upd,
        patch("services.work_order_contractor_routing_service.create_audit_log", new_callable=AsyncMock),
    ):
        await wcrs.confirm_recommended_contractor("wo1", "c1", actor_portal_user_id="u1")
    upd.assert_awaited_once()
    assert upd.await_args.kwargs.get("contractor_id") == "rec-gas"
    assert upd.await_args.kwargs.get("allow_direct_contractor_assignment") is True


async def test_scenario_b_confirm_alternate_assigns_chosen_contractor():
    wo = {
        "work_order_id": "wo-eicr",
        "client_id": "c1",
        "contractor_id": None,
        "assignment_routing_state": ASSIGNMENT_ROUTING_PENDING_CLIENT_CONFIRMATION,
        "work_order_kind": WORK_ORDER_KIND_COMPLIANCE,
        "status": "OPEN",
    }
    with (
        patch.object(wcrs, "_load_wo_client", new_callable=AsyncMock, return_value=wo),
        patch.object(maintenance_service, "update_work_order", new_callable=AsyncMock, return_value={}) as upd,
        patch("services.work_order_contractor_routing_service.create_audit_log", new_callable=AsyncMock),
    ):
        await wcrs.confirm_alternate_contractor(
            "wo-eicr", "c1", "electrician-alt-2", actor_portal_user_id="u1"
        )
    assert upd.await_args.kwargs.get("contractor_id") == "electrician-alt-2"
    assert upd.await_args.kwargs.get("allow_direct_contractor_assignment") is True


async def test_scenario_c_personal_contractor_for_compliance_gets_execution_tags():
    wo = {
        "work_order_id": "wo-p",
        "client_id": "c1",
        "contractor_id": None,
        "work_order_kind": WORK_ORDER_KIND_COMPLIANCE,
        "requirement_code": "gas_safety",
        "status": "OPEN",
    }
    cc_mock = AsyncMock(return_value={"contractor_id": "ctr-personal", "email": "bob@example.com"})
    with (
        patch.object(wcrs, "_load_wo_client", new_callable=AsyncMock, return_value=wo),
        patch("services.contractor_service.create_contractor_client_supplied_personal", cc_mock),
        patch.object(maintenance_service, "update_work_order", new_callable=AsyncMock, return_value={}),
        patch("services.work_order_contractor_routing_service.create_audit_log", new_callable=AsyncMock),
    ):
        await wcrs.add_personal_contractor_and_assign(
            "wo-p",
            "c1",
            name="Bob Tester",
            email="bob@example.com",
            phone=None,
            trade_types=["heating"],
            actor_portal_user_id="u1",
        )
    cc_mock.assert_awaited_once()
    k = cc_mock.await_args.kwargs
    assert k.get("execution_capabilities") == "compliance"
    assert k.get("supported_requirement_codes") == ["gas_safety"]


def test_scenario_d_operational_complete_without_evidence_skips_risk_resolution():
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
                "requirement_code": "eicr",
            }
        )
        completed = {
            "work_order_id": "wo-d",
            "status": "COMPLETED",
            "client_id": "c1",
            "property_id": "p1",
            "work_order_kind": "COMPLIANCE",
            "requirement_code": "eicr",
            "evidence_keys": [],
            "contractor_id": None,
            "issue_id": None,
            "asset_id": None,
            "description": "EICR job",
            "completed_at": "2026-01-01T00:00:00+00:00",
        }
        mock_db.work_orders.find_one_and_update = AsyncMock(return_value=dict(completed))
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
            await maintenance_service.update_work_order("wo-d", status="COMPLETED")
        wo_completed = [
            c.args[0]
            for c in apply_mock.call_args_list
            if c.args and isinstance(c.args[0], dict) and c.args[0].get("event_type") == "work_order_completed"
        ]
        assert len(wo_completed) == 1
        meta = wo_completed[0].get("metadata") or {}
        assert meta.get("resolve_linked_compliance_risks") is False
        assert meta.get("compliance_proof_submitted") is False

    asyncio.run(_run())


async def test_scenario_e_log_inspection_issue_creates_maintenance_issue_not_compliance_wo():
    sig = {
        "signal_id": "s-maint",
        "client_id": "c1",
        "property_id": "p9",
        "risk_type": "boiler_noise",
        "recommended_action": "Book inspection",
    }
    issue_ret = {"issue_id": "iss-maint-1"}
    create_issue_mock = AsyncMock(return_value=issue_ret)
    with (
        patch.object(risk_signal_service, "get_risk_signal_by_id", new_callable=AsyncMock, return_value=sig),
        patch.object(mis, "create_issue", create_issue_mock),
        patch("services.risk_signal_service.create_audit_log", new_callable=AsyncMock),
    ):
        out = await risk_signal_service.create_inspection_issue_from_risk_signal("s-maint", "c1")
    assert out["issue_id"] == "iss-maint-1"
    create_issue_mock.assert_awaited_once()
    desc = create_issue_mock.await_args.kwargs.get("description") or ""
    assert desc.startswith("Inspection:")
    assert "boiler_noise" in desc or "Book inspection" in desc


def test_document_verify_sets_compliance_work_order_proof_verified_flag():
    async def _run():
        from routes.documents import _set_compliance_work_order_proof_verified
        from services.work_order_execution_constants import COMPLIANCE_PROOF_VERIFIED

        mock_db = MagicMock()
        mock_db.work_orders.update_one = AsyncMock()
        await _set_compliance_work_order_proof_verified(mock_db, "wo-linked")
        mock_db.work_orders.update_one.assert_awaited_once()
        flt = mock_db.work_orders.update_one.call_args[0][0]
        assert flt["work_order_id"] == "wo-linked"
        assert flt["work_order_kind"] == "COMPLIANCE"
        assert mock_db.work_orders.update_one.call_args[0][1]["$set"]["compliance_proof_status"] == COMPLIANCE_PROOF_VERIFIED

    asyncio.run(_run())


async def test_reconcile_proof_not_submitted_after_doc_removed_when_no_evidence_remains():
    from routes.documents import _reconcile_compliance_work_order_proof_after_document_removed
    from services.work_order_execution_constants import COMPLIANCE_PROOF_NOT_SUBMITTED

    mock_db = MagicMock()
    mock_db.work_orders.find_one = AsyncMock(
        side_effect=[
            {"work_order_id": "wo1"},
            {"evidence_keys": []},
        ]
    )
    mock_db.work_orders.update_one = AsyncMock()
    mock_db.documents.count_documents = AsyncMock(return_value=0)
    await _reconcile_compliance_work_order_proof_after_document_removed(mock_db, "d1", "wo1")
    final = mock_db.work_orders.update_one.call_args_list[-1][0][1]["$set"]["compliance_proof_status"]
    assert final == COMPLIANCE_PROOF_NOT_SUBMITTED


async def test_reconcile_proof_submitted_when_non_document_evidence_remains():
    from routes.documents import _reconcile_compliance_work_order_proof_after_document_removed
    from services.work_order_execution_constants import COMPLIANCE_PROOF_SUBMITTED

    mock_db = MagicMock()
    mock_db.work_orders.find_one = AsyncMock(
        side_effect=[
            {"work_order_id": "wo1"},
            {"evidence_keys": ["contractor_evidence/wo1/a.pdf"]},
        ]
    )
    mock_db.work_orders.update_one = AsyncMock()
    mock_db.documents.count_documents = AsyncMock(return_value=0)
    await _reconcile_compliance_work_order_proof_after_document_removed(mock_db, "d1", "wo1")
    final = mock_db.work_orders.update_one.call_args_list[-1][0][1]["$set"]["compliance_proof_status"]
    assert final == COMPLIANCE_PROOF_SUBMITTED


async def test_reconcile_proof_stays_verified_when_other_verified_document_remains():
    from routes.documents import _reconcile_compliance_work_order_proof_after_document_removed
    from services.work_order_execution_constants import COMPLIANCE_PROOF_VERIFIED

    mock_db = MagicMock()
    mock_db.work_orders.find_one = AsyncMock(
        side_effect=[
            {"work_order_id": "wo1"},
            {"evidence_keys": ["document:d-other"]},
        ]
    )
    mock_db.work_orders.update_one = AsyncMock()
    mock_db.documents.count_documents = AsyncMock(return_value=1)
    await _reconcile_compliance_work_order_proof_after_document_removed(mock_db, "d1", "wo1")
    final = mock_db.work_orders.update_one.call_args_list[-1][0][1]["$set"]["compliance_proof_status"]
    assert final == COMPLIANCE_PROOF_VERIFIED
