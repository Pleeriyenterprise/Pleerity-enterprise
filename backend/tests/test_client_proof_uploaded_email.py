"""Client email when contractor appends new work order evidence keys."""
import hashlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from database import database as db_singleton
from services import maintenance_service as ms
from services.work_order_execution_constants import WORK_ORDER_KIND_COMPLIANCE


@pytest.mark.asyncio
async def test_evidence_append_sends_client_proof_uploaded():
    work_order_id = "wo-cpu-1"
    client_id = "cli-cpu"
    contractor_id = "ctr-cpu"
    prev = {
        "work_order_id": work_order_id,
        "client_id": client_id,
        "property_id": "prop-cpu",
        "contractor_id": contractor_id,
        "status": "IN_PROGRESS",
        "work_order_kind": WORK_ORDER_KIND_COMPLIANCE,
        "description": "Gas check",
        "evidence_keys": [],
        "requirement_code": "gas",
    }
    new_key = "vault:proof-abc"
    after = {**prev, "evidence_keys": [new_key], "updated_at": "2026-04-02T16:00:00+00:00"}

    mock_db = MagicMock()
    mock_db.work_orders.find_one = AsyncMock(return_value=dict(prev))
    mock_db.work_orders.find_one_and_update = AsyncMock(return_value=dict(after))
    mock_db.clients.find_one = AsyncMock(
        return_value={
            "contact_email": "client@example.com",
            "full_name": "Acme Ltd",
            "customer_reference": "REF-1",
        }
    )
    mock_db.properties.find_one = AsyncMock(
        return_value={"address_line_1": "1 Lane", "city": "Leeds", "postcode": "LS1 1AA"}
    )
    mock_db.contractors.find_one = AsyncMock(return_value={"name": "Gas Co", "company_name": "Gas Co Ltd"})

    send_mock = AsyncMock(return_value=MagicMock(outcome="sent"))
    peid = hashlib.sha256(new_key.encode("utf-8")).hexdigest()[:32]

    with (
        patch.object(db_singleton, "get_db", return_value=mock_db),
        patch("utils.public_app_url.get_frontend_base_url", return_value="https://app.example.com"),
        patch("services.notification_orchestrator.notification_orchestrator.send", send_mock),
    ):
        await ms.update_work_order(work_order_id, evidence_keys_append=[new_key])

    assert send_mock.await_count == 1
    kw = send_mock.await_args.kwargs
    assert kw.get("template_key") == "CLIENT_PROOF_UPLOADED"
    assert kw.get("event_type") == "CLIENT_PROOF_UPLOADED"
    assert kw.get("idempotency_key") == f"client_proof_uploaded:{work_order_id}:{peid}"
    ctx = kw.get("context") or {}
    assert ctx.get("recipient") == "client@example.com"
    assert ctx.get("is_compliance") is True
    assert ctx.get("client_job_link") == f"https://app.example.com/operations/jobs/{work_order_id}"
    assert "validation" in (ctx.get("compliance_outcome_hint") or "").lower()


@pytest.mark.asyncio
async def test_evidence_append_skips_when_keys_already_present():
    work_order_id = "wo-cpu-2"
    key = "vault:existing"
    prev = {
        "work_order_id": work_order_id,
        "client_id": "cli-cpu",
        "property_id": "prop-cpu",
        "contractor_id": "ctr-cpu",
        "status": "COMPLETED",
        "work_order_kind": "MAINTENANCE",
        "description": "Fix tap",
        "evidence_keys": [key],
    }
    after = dict(prev)

    mock_db = MagicMock()
    mock_db.work_orders.find_one = AsyncMock(return_value=dict(prev))
    mock_db.work_orders.find_one_and_update = AsyncMock(return_value=dict(after))
    send_mock = AsyncMock(return_value=MagicMock(outcome="sent"))

    with (
        patch.object(db_singleton, "get_db", return_value=mock_db),
        patch("services.notification_orchestrator.notification_orchestrator.send", send_mock),
    ):
        await ms.update_work_order(work_order_id, evidence_keys_append=[key])

    send_mock.assert_not_called()
