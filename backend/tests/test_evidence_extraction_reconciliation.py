"""Historical extraction supersession reconciliation."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from services.evidence_extraction_reconciliation import (
    build_reconciliation_patch,
    reconcile_document_extraction_supersession,
    scan_extraction_supersession_reconciliation,
)


def test_build_reconciliation_patch_includes_metadata():
    doc = {
        "ai_extraction": {"status": "completed", "review_status": "PENDING", "data": {"k": "v"}},
    }
    patch = build_reconciliation_patch(
        doc,
        decision="accepted",
        actor_id="adm1",
        now_iso="2026-05-16T12:00:00+00:00",
        reconciliation_reason="historical_evidence_review_supersedes_extraction",
        reconciliation_batch_id="batch-1",
    )
    assert patch["extraction_confirmation_superseded"] is True
    assert patch["extraction_reconciliation_at"] == "2026-05-16T12:00:00+00:00"
    assert patch["extraction_reconciliation_by"] == "adm1"
    assert patch["extraction_reconciliation_batch_id"] == "batch-1"
    assert patch["ai_extraction"]["data"] == {"k": "v"}


@pytest.mark.asyncio
async def test_reconcile_historical_verified_document():
    doc = {
        "document_id": "doc-hist-1",
        "status": "VERIFIED",
        "evidence_review_state": "ACCEPTED_UNVERIFIED",
        "extraction_status": "NEEDS_REVIEW",
        "ai_extraction": {"status": "completed", "review_status": "PENDING", "data": {"x": 1}},
    }
    mock_db = MagicMock()
    mock_db.documents.find_one = AsyncMock(return_value=dict(doc))
    mock_db.documents.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
    mock_db.extracted_documents.update_one = AsyncMock()

    out = await reconcile_document_extraction_supersession(
        mock_db,
        document_id="doc-hist-1",
        actor_id="adm1",
        dry_run=False,
    )
    assert out["status"] == "updated"
    assert out["decision"] == "accepted"
    mock_db.documents.update_one.assert_awaited_once()


@pytest.mark.asyncio
async def test_reconcile_idempotent_skip_when_aligned():
    doc = {
        "document_id": "doc-hist-2",
        "status": "VERIFIED",
        "evidence_review_state": "ACCEPTED_UNVERIFIED",
        "extraction_status": "CONFIRMED",
        "extraction_confirmation_superseded": True,
        "ai_extraction": {"review_status": "approved", "superseded_by_admin_decision": "accepted"},
    }
    mock_db = MagicMock()
    mock_db.documents.find_one = AsyncMock(return_value=dict(doc))

    out = await reconcile_document_extraction_supersession(
        mock_db,
        document_id="doc-hist-2",
        actor_id="adm1",
        dry_run=False,
    )
    assert out["status"] == "skipped"
    mock_db.documents.update_one.assert_not_called()


@pytest.mark.asyncio
async def test_scan_dry_run_counts_needs_reconciliation():
    rows = [
        {
            "document_id": "d1",
            "status": "VERIFIED",
            "evidence_review_state": "ACCEPTED_UNVERIFIED",
            "extraction_status": "NEEDS_REVIEW",
            "ai_extraction": {"review_status": "PENDING", "status": "completed", "data": {}},
        },
        {
            "document_id": "d2",
            "status": "UPLOADED",
            "evidence_review_state": "UPLOADED",
            "extraction_status": "NEEDS_REVIEW",
            "ai_extraction": {"review_status": "PENDING", "status": "completed", "data": {}},
        },
    ]
    mock_db = MagicMock()
    mock_db.documents.find = MagicMock(
        return_value=MagicMock(
            limit=MagicMock(
                return_value=MagicMock(to_list=AsyncMock(return_value=rows))
            )
        )
    )

    result = await scan_extraction_supersession_reconciliation(mock_db, limit=10, dry_run=True)
    assert result["scanned"] == 2
    assert result["needs_reconciliation"] == 1
    assert result["updated"] == 0
