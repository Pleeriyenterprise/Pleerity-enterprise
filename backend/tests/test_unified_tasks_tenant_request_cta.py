"""Stream D B3: tenant_request unified tasks — metadata.take_action enrich + mismatch logging."""
from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.unified_tasks_service import _tenant_request_tasks


def _chain_tenant_rows(rows):
    chain = MagicMock()
    chain.sort.return_value = chain
    chain.limit.return_value = chain
    chain.to_list = AsyncMock(return_value=rows)
    return chain


@pytest.mark.asyncio
async def test_tenant_request_attaches_metadata_take_action_when_requirement_found(caplog):
    tr_row = {
        "request_id": "tr-1",
        "property_id": "p1",
        "status": "PENDING",
        "requirement_id": "r1",
        "requirement_code": "gas_safety",
        "created_at": None,
        "updated_at": None,
    }
    req_doc = {
        "requirement_id": "r1",
        "property_id": "p1",
        "client_id": "c1",
        "requirement_code": "gas_safety",
        "requirement_type": "gas_safety",
        "compliance_requirement_class": "DOCUMENT",
        "jurisdiction": "England",
    }
    mock_db = MagicMock()
    mock_db.tenant_requests.find.return_value = _chain_tenant_rows([tr_row])
    mock_db.requirements.find_one = AsyncMock(return_value=req_doc)

    with patch("services.unified_tasks_service.database.get_db", return_value=mock_db), patch(
        "services.unified_tasks_service._load_property_labels", new_callable=AsyncMock
    ) as _lbl:
        _lbl.return_value = {"p1": "Test property"}
        with caplog.at_level(logging.WARNING):
            tasks = await _tenant_request_tasks("c1", None, 20)
    assert len(tasks) == 1
    ta = tasks[0]["metadata"].get("take_action")
    assert isinstance(ta, dict)
    assert ta.get("primary")
    assert tasks[0]["primary_action_label"] == "Upload document"
    assert "/documents" in (tasks[0]["primary_action_url"] or "")
    assert not [r for r in caplog.records if "tenant_request unified task" in r.getMessage()]


@pytest.mark.asyncio
async def test_tenant_request_mismatch_warning_when_canonical_guided(caplog):
    tr_row = {
        "request_id": "tr-2",
        "property_id": "p1",
        "status": "PENDING",
        "requirement_id": "r1",
        "requirement_code": "smoke_heat_alarms",
        "created_at": None,
        "updated_at": None,
    }
    req_doc = {
        "requirement_id": "r1",
        "property_id": "p1",
        "client_id": "c1",
        "requirement_code": "smoke_heat_alarms",
        "requirement_type": "smoke_heat_alarms",
        "compliance_requirement_class": "DOCUMENT",
        "jurisdiction": "England",
    }
    mock_db = MagicMock()
    mock_db.tenant_requests.find.return_value = _chain_tenant_rows([tr_row])
    mock_db.requirements.find_one = AsyncMock(return_value=req_doc)

    with patch("services.unified_tasks_service.database.get_db", return_value=mock_db), patch(
        "services.unified_tasks_service._load_property_labels", new_callable=AsyncMock
    ) as _lbl:
        _lbl.return_value = {"p1": "Test property"}
        with caplog.at_level(logging.WARNING):
            tasks = await _tenant_request_tasks("c1", None, 20)
    assert len(tasks) == 1
    assert tasks[0]["metadata"].get("take_action")
    warns = [r for r in caplog.records if r.levelno == logging.WARNING and "tenant_request unified task" in r.getMessage()]
    assert warns, "expected mismatch warning for guided canonical vs hardcoded upload CTA"
    assert "guided_evidence_resolution" in (warns[0].getMessage() or "")
    assert getattr(warns[0], "op", None) == "tenant_request_cta"
    assert getattr(warns[0], "event", None) == "compliance_fanout"


@pytest.mark.asyncio
async def test_tenant_request_no_metadata_enrich_without_requirement_id():
    tr_row = {
        "request_id": "tr-3",
        "property_id": "p1",
        "status": "PENDING",
        "requirement_id": None,
        "requirement_code": None,
        "created_at": None,
        "updated_at": None,
    }
    mock_db = MagicMock()
    mock_db.tenant_requests.find.return_value = _chain_tenant_rows([tr_row])
    mock_db.requirements.find_one = AsyncMock()

    with patch("services.unified_tasks_service.database.get_db", return_value=mock_db), patch(
        "services.unified_tasks_service._load_property_labels", new_callable=AsyncMock
    ) as _lbl:
        _lbl.return_value = {"p1": "Test property"}
        tasks = await _tenant_request_tasks("c1", None, 20)
    assert len(tasks) == 1
    assert "take_action" not in tasks[0]["metadata"]
    mock_db.requirements.find_one.assert_not_called()


@pytest.mark.asyncio
async def test_tenant_request_no_take_action_when_requirement_missing():
    tr_row = {
        "request_id": "tr-4",
        "property_id": "p1",
        "status": "PENDING",
        "requirement_id": "r-missing",
        "requirement_code": "gas_safety",
        "created_at": None,
        "updated_at": None,
    }
    mock_db = MagicMock()
    mock_db.tenant_requests.find.return_value = _chain_tenant_rows([tr_row])
    mock_db.requirements.find_one = AsyncMock(return_value=None)

    with patch("services.unified_tasks_service.database.get_db", return_value=mock_db), patch(
        "services.unified_tasks_service._load_property_labels", new_callable=AsyncMock
    ) as _lbl:
        _lbl.return_value = {"p1": "Test property"}
        tasks = await _tenant_request_tasks("c1", None, 20)
    assert len(tasks) == 1
    assert "take_action" not in tasks[0]["metadata"]
    assert tasks[0]["primary_action_url"].startswith("/documents")
