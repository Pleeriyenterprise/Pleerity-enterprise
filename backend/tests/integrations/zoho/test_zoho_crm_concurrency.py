"""CRM concurrency hardening — queue claim and external-key integrity."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pymongo.errors import DuplicateKeyError

from services.integrations.zoho.sync_store import ZohoSyncStore


@pytest.mark.asyncio
async def test_claim_pending_queue_atomic_find_one_and_update():
    store = ZohoSyncStore()
    doc1 = {
        "queue_id": "ZQ-1",
        "integration": "crm",
        "operation": "lead.created",
        "payload": {"lead_id": "L1"},
        "status": "processing",
        "claim_id": "WQ-TEST",
    }
    mock_coll = MagicMock()
    mock_coll.find_one_and_update = AsyncMock(side_effect=[doc1, None])
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_coll)

    with patch("services.integrations.zoho.sync_store.database.get_db", return_value=mock_db):
        claimed = await store.claim_pending_queue("crm", limit=5, worker_id="WQ-TEST")

    assert len(claimed) == 1
    assert claimed[0]["queue_id"] == "ZQ-1"
    assert mock_coll.find_one_and_update.await_count == 2
    call_kwargs = mock_coll.find_one_and_update.await_args_list[0]
    update = call_kwargs.args[1]
    assert update["$set"]["status"] == "processing"
    assert update["$set"]["claim_id"] == "WQ-TEST"
    assert "lease_expires_at" in update["$set"]


@pytest.mark.asyncio
async def test_store_external_key_first_writer_wins_on_duplicate():
    store = ZohoSyncStore()
    mock_coll = MagicMock()
    mock_coll.insert_one = AsyncMock(side_effect=DuplicateKeyError("dup"))
    mock_coll.find_one = AsyncMock(
        side_effect=[
            None,  # get_external_key before insert
            None,  # get_pleerity_id_for_zoho
            {"zoho_id": "Z-WIN"},  # re-read after DuplicateKeyError
        ]
    )
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_coll)

    with patch("services.integrations.zoho.sync_store.database.get_db", return_value=mock_db):
        bound = await store.store_external_key("crm", "LEAD-A", "Z-NEW")

    assert bound == "Z-WIN"


@pytest.mark.asyncio
async def test_store_external_key_immutable_existing():
    store = ZohoSyncStore()
    mock_coll = MagicMock()
    mock_coll.find_one = AsyncMock(return_value={"zoho_id": "Z-EXIST"})
    mock_coll.insert_one = AsyncMock()
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_coll)

    with patch("services.integrations.zoho.sync_store.database.get_db", return_value=mock_db):
        bound = await store.store_external_key("crm", "LEAD-A", "Z-OTHER")

    assert bound == "Z-EXIST"
    mock_coll.insert_one.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_queue_uses_claim_not_fetch():
    from services.integrations.zoho.service import ZohoIntegrationService
    from services.integrations.zoho.types import SyncResult, SyncStatus

    svc = ZohoIntegrationService()
    item = {
        "queue_id": "ZQ-9",
        "integration": "crm",
        "operation": "upsert_lead",
        "payload": {"lead_id": "L9"},
        "status": "processing",
        "claim_id": "WQ-1",
    }
    ok = SyncResult(
        success=True,
        sync_id="ZSYNC-9",
        integration="crm",
        operation="upsert_lead",
        status=SyncStatus.SUCCESS,
        message="ok",
        external_id="Z1",
    )
    with (
        patch(
            "services.integrations.zoho.service.zoho_sync_store.claim_pending_queue",
            new_callable=AsyncMock,
            return_value=[item],
        ) as claim,
        patch(
            "services.integrations.zoho.service.zoho_sync_store.fetch_pending_queue",
            new_callable=AsyncMock,
        ) as fetch,
        patch.object(svc, "run_sync", new_callable=AsyncMock, return_value=ok),
        patch(
            "services.integrations.zoho.service.zoho_sync_store.mark_queue_done",
            new_callable=AsyncMock,
        ) as done,
    ):
        out = await svc.process_queue("crm", limit=10)

    claim.assert_awaited()
    fetch.assert_not_awaited()
    done.assert_awaited_with("ZQ-9")
    assert out["processed"] == 1
    assert out["claimed"] == 1
    assert out["worker_id"]
