"""Bounded review-state alignment: document verify → linked DOCUMENT_UPLOAD CER."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.compliance_evidence_record_service import (
    EVIDENCE_MODE_DOCUMENT_UPLOAD,
    VERIFICATION_PENDING,
    VERIFICATION_VERIFIED,
    align_linked_document_upload_cer_on_document_verified,
)


@pytest.mark.asyncio
async def test_align_linked_cer_pending_to_verified():
    existing = {
        "evidence_record_id": "cer_doc_1",
        "client_id": "c1",
        "requirement_id": "r1",
        "evidence_mode": EVIDENCE_MODE_DOCUMENT_UPLOAD,
        "verification_status": VERIFICATION_PENDING,
        "linked_document_ids": ["doc-1"],
    }

    class _Cursor:
        def __init__(self, rows):
            self._rows = list(rows)

        def __aiter__(self):
            self._it = iter(self._rows)
            return self

        async def __anext__(self):
            try:
                return next(self._it)
            except StopIteration:
                raise StopAsyncIteration

    mock_coll = MagicMock()
    mock_coll.find = MagicMock(return_value=_Cursor([existing]))
    mock_coll.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
    mock_db = MagicMock()
    mock_db.compliance_evidence_records = mock_coll

    mock_coll.find_one = AsyncMock(return_value=existing)

    with (
        patch("services.compliance_evidence_record_service._evidence_coll", return_value=mock_coll),
        patch(
            "services.compliance_evidence_record_service.assign_confidence_for_new_record",
            return_value="HIGH",
        ),
    ):
        out = await align_linked_document_upload_cer_on_document_verified(
            mock_db,
            client_id="c1",
            requirement_id="r1",
            document_id="doc-1",
            actor_user_id="admin-1",
        )

    assert len(out) == 1
    assert out[0]["verification_status"] == VERIFICATION_VERIFIED
    mock_coll.update_one.assert_awaited()


@pytest.mark.asyncio
async def test_align_skips_already_verified_cer():
    class _Cursor:
        def __aiter__(self):
            return self

        async def __anext__(self):
            raise StopAsyncIteration

    mock_coll = MagicMock()
    mock_coll.find = MagicMock(return_value=_Cursor())
    mock_db = MagicMock()
    mock_db.compliance_evidence_records = mock_coll

    with patch("services.compliance_evidence_record_service._evidence_coll", return_value=mock_coll):
        out = await align_linked_document_upload_cer_on_document_verified(
            mock_db,
            client_id="c1",
            requirement_id="r1",
            document_id="doc-1",
            actor_user_id="admin-1",
        )

    assert out == []
