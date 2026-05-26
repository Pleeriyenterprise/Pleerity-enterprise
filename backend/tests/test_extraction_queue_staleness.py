"""Extraction queue staleness enrichment and retry error code."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from services.extraction_queue_staleness import (
    STALE_DETAIL_CODE,
    STALE_QUEUE_STATUS,
    document_exists,
    enrich_extraction_queue_item,
)


@pytest.mark.asyncio
async def test_document_exists_false_when_missing():
    db = AsyncMock()
    db.documents.find_one = AsyncMock(return_value=None)
    assert await document_exists(db, "doc-missing") is False


@pytest.mark.asyncio
async def test_enrich_marks_stale_when_document_missing():
    db = AsyncMock()
    db.documents.find_one = AsyncMock(return_value=None)
    db.extracted_documents.update_one = AsyncMock()

    row = {"extraction_id": "ext1", "document_id": "doc1", "status": "FAILED"}
    out = await enrich_extraction_queue_item(db, row, auto_mark_stale=True)
    assert out["document_exists"] is False
    assert out["queue_stale"] is True
    assert out["queue_actionable"] is False
    assert out["status"] == STALE_QUEUE_STATUS
    db.extracted_documents.update_one.assert_awaited()


@pytest.mark.asyncio
async def test_enrich_actionable_when_document_present():
    db = AsyncMock()
    db.documents.find_one = AsyncMock(return_value={"_id": 1})

    row = {"extraction_id": "ext1", "document_id": "doc1", "status": "FAILED"}
    out = await enrich_extraction_queue_item(db, row, auto_mark_stale=True)
    assert out["document_exists"] is True
    assert out["queue_stale"] is False
    assert out["queue_actionable"] is True


def test_stale_detail_code_constant():
    assert STALE_DETAIL_CODE == "STALE_QUEUE_DOCUMENT_NOT_FOUND"
