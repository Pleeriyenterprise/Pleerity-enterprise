"""Contractor evidence validation and unified decline assignment behaviour."""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from services import maintenance_service as ms
from services import contractor_evidence_service as ces


def test_validate_evidence_empty():
    with pytest.raises(ValueError, match="Empty"):
        ces.validate_evidence_file(filename="a.pdf", content=b"")


def test_validate_evidence_too_large():
    with pytest.raises(ValueError, match="too large"):
        ces.validate_evidence_file(filename="a.pdf", content=b"x" * (ces.MAX_BYTES + 1))


def test_validate_evidence_bad_ext():
    with pytest.raises(ValueError, match="Unsupported"):
        ces.validate_evidence_file(filename="a.exe", content=b"ok")


def test_validate_evidence_ok():
    assert ces.validate_evidence_file(filename="x.PDF", content=b"data") == ".pdf"


def test_resolve_contractor_evidence_file_ok(tmp_path):
    rel = "c1/contractor_evidence/wo1/abc.pdf"
    dest = tmp_path.joinpath(*rel.split("/"))
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(b"%PDF-1.1")

    async def _run():
        with patch.object(ces, "DOCUMENT_STORAGE_PATH", tmp_path):
            return await ces.resolve_contractor_evidence_file(
                work_order_id="wo1",
                wo_client_id="c1",
                evidence_keys=[rel],
                storage_key=rel,
            )

    path, media, name = asyncio.run(_run())
    assert name == "abc.pdf"
    assert media == "application/pdf"
    assert path.is_file()


def test_resolve_contractor_evidence_not_on_work_order(tmp_path):
    async def _run():
        with patch.object(ces, "DOCUMENT_STORAGE_PATH", tmp_path):
            await ces.resolve_contractor_evidence_file(
                work_order_id="wo1",
                wo_client_id="c1",
                evidence_keys=[],
                storage_key="c1/contractor_evidence/wo1/x.pdf",
            )

    with pytest.raises(LookupError):
        asyncio.run(_run())


def test_contractor_decline_assignment_updates_and_revokes():
    mock_db = MagicMock()
    mock_db.work_orders.find_one = AsyncMock(
        return_value={
            "work_order_id": "wo1",
            "contractor_id": "c1",
            "client_id": "cl1",
            "status": "ASSIGNED",
        }
    )
    updated = {
        "work_order_id": "wo1",
        "contractor_id": None,
        "client_id": "cl1",
        "status": ms.STATUS_OPEN,
        "_id": "x",
    }
    mock_db.work_orders.find_one_and_update = AsyncMock(return_value=updated)
    mock_db.contractor_job_tokens.update_many = AsyncMock()

    async def _run():
        with patch("services.maintenance_service.database.get_db", return_value=mock_db):
            with patch(
                "services.work_order_contractor_routing_service.invalidate_pending_routing_for_work_order",
                new_callable=AsyncMock,
            ) as inv:
                with patch(
                    "services.webhook_service.fire_work_order_status_changed",
                    new_callable=AsyncMock,
                ) as wh:
                    out = await ms.contractor_decline_assignment("wo1", "c1")
        return out, inv, wh

    out, inv, wh = asyncio.run(_run())
    assert out is not None
    assert out["contractor_id"] is None
    mock_db.contractor_job_tokens.update_many.assert_awaited()
    inv.assert_awaited()
    wh.assert_awaited()


def test_contractor_decline_not_assigned():
    mock_db = MagicMock()
    mock_db.work_orders.find_one = AsyncMock(return_value=None)

    async def _run():
        with patch("services.maintenance_service.database.get_db", return_value=mock_db):
            return await ms.contractor_decline_assignment("wo1", "c1")

    assert asyncio.run(_run()) is None
