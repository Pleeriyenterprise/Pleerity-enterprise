"""Tests for superseding AI extraction confirmation after admin evidence decisions."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from services.evidence_extraction_supersession import (
    ADMIN_DECISION_ACCEPTED,
    ADMIN_DECISION_REJECTED,
    build_extraction_supersession_patch,
    supersede_extraction_confirmation_for_admin_decision,
)


def test_build_extraction_supersession_patch_accepted():
    patch = build_extraction_supersession_patch(
        decision=ADMIN_DECISION_ACCEPTED,
        actor_id="adm1",
        now_iso="2026-05-16T12:00:00+00:00",
        existing_ai_extraction={"status": "completed", "review_status": "PENDING", "data": {"x": 1}},
    )
    assert patch["extraction_status"] == "CONFIRMED"
    assert patch["extraction_confirmation_superseded"] is True
    assert patch["ai_extraction"]["review_status"] == "approved"
    assert patch["ai_extraction"]["superseded_by_admin_decision"] == ADMIN_DECISION_ACCEPTED
    assert patch["extraction_confirmation_superseded_by"] == "adm1"


def test_build_extraction_supersession_patch_rejected():
    patch = build_extraction_supersession_patch(
        decision=ADMIN_DECISION_REJECTED,
        actor_id=None,
        now_iso="2026-05-16T12:00:00+00:00",
    )
    assert patch["extraction_status"] == "REJECTED"
    assert patch["ai_extraction"]["review_status"] == "rejected"
    assert "extraction_confirmation_superseded_by" not in patch


@pytest.mark.asyncio
async def test_supersede_updates_document_and_extracted_documents_queue():
    mock_db = MagicMock()
    mock_db.documents.find_one = AsyncMock(
        return_value={
            "document_id": "doc-1",
            "extraction_id": "ext-1",
            "extraction_status": "NEEDS_REVIEW",
            "ai_extraction": {"status": "completed", "review_status": "PENDING"},
        }
    )
    mock_db.documents.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
    mock_db.extracted_documents.update_one = AsyncMock(return_value=MagicMock(modified_count=1))

    ok = await supersede_extraction_confirmation_for_admin_decision(
        mock_db,
        document_id="doc-1",
        decision=ADMIN_DECISION_ACCEPTED,
        actor_id="adm1",
    )

    assert ok is True
    mock_db.documents.update_one.assert_awaited_once()
    set_payload = mock_db.documents.update_one.await_args.args[1]["$set"]
    assert set_payload["extraction_confirmation_superseded"] is True
    assert set_payload["ai_extraction"]["review_status"] == "approved"
    mock_db.extracted_documents.update_one.assert_awaited_once()
    queue_set = mock_db.extracted_documents.update_one.await_args.args[1]["$set"]
    assert queue_set["status"] == "CONFIRMED"


@pytest.mark.asyncio
async def test_supersede_returns_false_when_document_missing():
    mock_db = MagicMock()
    mock_db.documents.find_one = AsyncMock(return_value=None)

    ok = await supersede_extraction_confirmation_for_admin_decision(
        mock_db,
        document_id="missing",
        decision=ADMIN_DECISION_ACCEPTED,
    )

    assert ok is False
    mock_db.documents.update_one.assert_not_called()
