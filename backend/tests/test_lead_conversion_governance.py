"""Governed lead conversion status transitions."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.lead_models import LeadStage, LeadStatus
from services.lead_service import (
    LeadConversionError,
    LeadService,
    _lead_conversion_block_code,
)


def test_block_code_active_new_is_convertible():
    assert _lead_conversion_block_code({"status": LeadStatus.ACTIVE.value, "stage": LeadStage.NEW.value}) is None


def test_block_code_lost_rejected():
    assert _lead_conversion_block_code({"status": LeadStatus.LOST.value, "stage": LeadStage.LOST.value}) == "LEAD_NOT_CONVERTIBLE"


def test_block_code_converted_rejected():
    assert _lead_conversion_block_code(
        {"status": LeadStatus.CONVERTED.value, "stage": LeadStage.WON.value, "client_id": "cid-1"}
    ) == "LEAD_ALREADY_CONVERTED"


def test_block_code_merged_rejected():
    assert _lead_conversion_block_code({"status": LeadStatus.MERGED.value, "stage": LeadStage.INACTIVE.value}) == "LEAD_NOT_CONVERTIBLE"


class _FakeDB:
    def __init__(self, lead_find_results):
        self.leads = MagicMock()
        self.leads.find_one = AsyncMock(side_effect=lead_find_results)
        self.leads.update_one = AsyncMock()
        self.clients = MagicMock()
        self.clients.update_one = AsyncMock()
        self.lead_audit_logs = MagicMock()
        self.lead_audit_logs.insert_one = AsyncMock()

    def __getitem__(self, key: str):
        return getattr(self, key)


def _mock_db(lead_find_results):
    db = _FakeDB(lead_find_results)
    return db, db.leads, db.clients, db.lead_audit_logs


@pytest.mark.asyncio
async def test_convert_lost_raises_without_mutation():
    db, leads, clients, audit = _mock_db(
        [
            {
                "lead_id": "LEAD-LOST",
                "status": LeadStatus.LOST.value,
                "stage": LeadStage.LOST.value,
                "lead_status": "lost",
            }
        ]
    )

    with patch("services.lead_service.database.get_db", return_value=db):
        with pytest.raises(LeadConversionError) as exc:
            await LeadService.convert_lead("LEAD-LOST", "cid-1", "admin@test.com")
    assert exc.value.code == "LEAD_NOT_CONVERTIBLE"
    leads.update_one.assert_not_called()
    clients.update_one.assert_not_called()
    audit.insert_one.assert_called_once()


@pytest.mark.asyncio
async def test_convert_already_converted_raises_without_mutation():
    db, leads, clients, audit = _mock_db(
        [
            {
                "lead_id": "LEAD-WON",
                "status": LeadStatus.CONVERTED.value,
                "stage": LeadStage.WON.value,
                "lead_status": "converted",
                "client_id": "cid-existing",
            }
        ]
    )

    with patch("services.lead_service.database.get_db", return_value=db):
        with pytest.raises(LeadConversionError) as exc:
            await LeadService.convert_lead("LEAD-WON", "cid-other", "admin@test.com")
    assert exc.value.code == "LEAD_ALREADY_CONVERTED"
    leads.update_one.assert_not_called()
    clients.update_one.assert_not_called()


@pytest.mark.asyncio
async def test_convert_active_lead_succeeds():
    db, leads, clients, audit = _mock_db(
        [
            {
                "lead_id": "LEAD-OK",
                "status": LeadStatus.ACTIVE.value,
                "stage": LeadStage.QUALIFIED.value,
                "lead_status": "qualified",
                "created_at": "2026-06-01T10:00:00+00:00",
                "source_platform": "WEB_CHAT",
            },
            {
                "lead_id": "LEAD-OK",
                "status": LeadStatus.CONVERTED.value,
                "client_id": "cid-1",
            },
        ]
    )

    with patch("services.lead_service.database.get_db", return_value=db):
        with patch("services.lead_automation_service.apply_conversion_attribution", AsyncMock(return_value={})):
            with patch("services.lead_automation_service.record_event", AsyncMock()):
                result = await LeadService.convert_lead("LEAD-OK", "cid-1", "admin@test.com")
    assert result is not None
    leads.update_one.assert_called_once()
    clients.update_one.assert_called_once()
