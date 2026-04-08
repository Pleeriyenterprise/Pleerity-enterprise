"""Contractor proof-required email when job enters IN_PROGRESS / AWAITING_PARTS without evidence."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from database import database as db_singleton
from services import maintenance_service as ms
from services.work_order_execution_constants import WORK_ORDER_KIND_COMPLIANCE


@pytest.mark.asyncio
async def test_in_progress_compliance_sends_proof_required_email():
    work_order_id = "wo-pr-1"
    client_id = "cli-pr"
    contractor_id = "ctr-pr"
    prev = {
        "work_order_id": work_order_id,
        "client_id": client_id,
        "property_id": "prop-pr",
        "contractor_id": contractor_id,
        "status": "SCHEDULED",
        "work_order_kind": WORK_ORDER_KIND_COMPLIANCE,
        "description": "Gas safety",
        "evidence_keys": [],
        "requirement_code": "GAS",
    }
    after = {**prev, "status": "IN_PROGRESS", "updated_at": "2026-04-02T12:00:00+00:00"}

    mock_db = MagicMock()
    mock_db.work_orders.find_one = AsyncMock(side_effect=[dict(prev), dict(prev)])
    mock_db.work_orders.find_one_and_update = AsyncMock(return_value=dict(after))
    mock_db.properties.find_one = AsyncMock(
        return_value={"address_line_1": "1 Proof St", "city": "Leeds", "postcode": "LS1 1AA"}
    )
    mock_db.contractors.find_one = AsyncMock(
        return_value={"email": "c@example.com", "name": "FixIt Ltd", "company_name": "FixIt Ltd"}
    )
    mock_db.contractor_job_tokens.insert_one = AsyncMock(return_value=None)

    send_mock = AsyncMock(return_value=MagicMock(outcome="sent"))

    with (
        patch.object(db_singleton, "get_db", return_value=mock_db),
        patch("services.work_order_pricing_service.assert_may_transition_to_in_progress"),
        patch("utils.public_app_url.get_frontend_base_url", return_value="https://app.example.com"),
        patch("services.maintenance_service.generate_secure_token", return_value="proof-tok-32chars-minimum________"),
        patch("services.notification_orchestrator.notification_orchestrator.send", send_mock),
    ):
        out = await ms.update_work_order(work_order_id, status=ms.STATUS_IN_PROGRESS)

    assert out and out.get("status") == "IN_PROGRESS"
    assert send_mock.await_count == 1
    kw = send_mock.await_args.kwargs
    assert kw.get("template_key") == "CONTRACTOR_PROOF_REQUIRED"
    assert kw.get("event_type") == "CONTRACTOR_PROOF_REQUIRED"
    assert kw.get("idempotency_key") == f"contractor_proof_required:{work_order_id}:IN_PROGRESS"
    ctx = kw.get("context") or {}
    assert ctx.get("recipient") == "c@example.com"
    assert ctx.get("completion_proof_required") is True
    assert ctx.get("completion_proof_satisfied") is False
    assert ctx.get("is_compliance") is True
    assert ctx.get("proof_type_hint") == "certificate"
    assert ctx.get("secure_job_link") == "https://app.example.com/job?token=proof-tok-32chars-minimum________"


@pytest.mark.asyncio
async def test_in_progress_skips_when_evidence_already_present():
    work_order_id = "wo-pr-2"
    client_id = "cli-pr"
    contractor_id = "ctr-pr"
    prev = {
        "work_order_id": work_order_id,
        "client_id": client_id,
        "property_id": "prop-pr",
        "contractor_id": contractor_id,
        "status": "SCHEDULED",
        "work_order_kind": WORK_ORDER_KIND_COMPLIANCE,
        "description": "Gas safety",
        "evidence_keys": ["vault:key1"],
    }
    after = {**prev, "status": "IN_PROGRESS"}

    mock_db = MagicMock()
    mock_db.work_orders.find_one = AsyncMock(side_effect=[dict(prev), dict(prev)])
    mock_db.work_orders.find_one_and_update = AsyncMock(return_value=dict(after))

    send_mock = AsyncMock(return_value=MagicMock(outcome="sent"))

    with (
        patch.object(db_singleton, "get_db", return_value=mock_db),
        patch("services.work_order_pricing_service.assert_may_transition_to_in_progress"),
        patch("services.notification_orchestrator.notification_orchestrator.send", send_mock),
    ):
        await ms.update_work_order(work_order_id, status=ms.STATUS_IN_PROGRESS)

    send_mock.assert_not_called()


@pytest.mark.asyncio
async def test_awaiting_parts_uses_distinct_idempotency_key():
    work_order_id = "wo-pr-3"
    client_id = "cli-pr"
    contractor_id = "ctr-pr"
    prev = {
        "work_order_id": work_order_id,
        "client_id": client_id,
        "property_id": "prop-pr",
        "contractor_id": contractor_id,
        "status": "IN_PROGRESS",
        "work_order_kind": WORK_ORDER_KIND_COMPLIANCE,
        "description": "Gas safety",
        "evidence_keys": [],
    }
    after = {**prev, "status": "AWAITING_PARTS"}

    mock_db = MagicMock()
    mock_db.work_orders.find_one = AsyncMock(return_value=dict(prev))
    mock_db.work_orders.find_one_and_update = AsyncMock(return_value=dict(after))
    mock_db.properties.find_one = AsyncMock(return_value=None)
    mock_db.contractors.find_one = AsyncMock(return_value={"email": "c@example.com", "name": "A"})
    mock_db.contractor_job_tokens.insert_one = AsyncMock(return_value=None)

    send_mock = AsyncMock(return_value=MagicMock(outcome="sent"))

    with (
        patch.object(db_singleton, "get_db", return_value=mock_db),
        patch("utils.public_app_url.get_frontend_base_url", return_value="https://app.example.com"),
        patch("services.maintenance_service.generate_secure_token", return_value="tok________________________________"),
        patch("services.notification_orchestrator.notification_orchestrator.send", send_mock),
    ):
        await ms.update_work_order(work_order_id, status=ms.STATUS_AWAITING_PARTS)

    assert send_mock.await_count == 1
    assert send_mock.await_args.kwargs.get("idempotency_key") == f"contractor_proof_required:{work_order_id}:AWAITING_PARTS"
