"""Phase 1 hardening tests: V2 backfill + response field exposure."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class _FakeCursor:
    def __init__(self, rows: List[Dict[str, Any]]):
        self._rows = rows
        self._limit = None

    def limit(self, n: int):
        self._limit = n
        return self

    async def to_list(self, n: int):
        use_n = self._limit if self._limit is not None else n
        return deepcopy(self._rows[:use_n])


class _FakeDocumentsCollection:
    def __init__(self, rows: List[Dict[str, Any]]):
        self.rows = deepcopy(rows)
        self.update_calls = 0

    def find(self, _q, _proj):
        return _FakeCursor(self.rows)

    async def update_one(self, filt, update):
        self.update_calls += 1
        did = filt.get("document_id")
        for row in self.rows:
            if row.get("document_id") == did:
                row.update((update or {}).get("$set") or {})
                break
        return MagicMock(modified_count=1)


class _FakeDb:
    def __init__(self, rows: List[Dict[str, Any]]):
        self.documents = _FakeDocumentsCollection(rows)


@pytest.mark.asyncio
async def test_backfill_is_idempotent():
    from services.evidence_review_backfill import scan_evidence_review_backfill

    db = _FakeDb(
        [
            {"document_id": "d1", "status": "VERIFIED"},
            {"document_id": "d2", "status": "UPLOADED"},
        ]
    )
    first = await scan_evidence_review_backfill(db, limit=100, dry_run=False, force=False)
    second = await scan_evidence_review_backfill(db, limit=100, dry_run=False, force=False)
    assert first["updated"] == 2
    assert second["updated"] == 0
    assert db.documents.update_calls == 2


def test_legacy_verified_maps_to_accepted_unverified():
    from services.evidence_review_backfill import compute_v2_backfill_patch

    patch = compute_v2_backfill_patch({"status": "VERIFIED"}, force=False)
    assert patch["evidence_review_state"] == "ACCEPTED_UNVERIFIED"
    assert patch["assurance_tier"] == "HUMAN_ACCEPTED"


@pytest.mark.asyncio
async def test_dry_run_does_not_modify_documents():
    from services.evidence_review_backfill import scan_evidence_review_backfill

    db = _FakeDb([{"document_id": "d1", "status": "UPLOADED"}])
    result = await scan_evidence_review_backfill(db, limit=100, dry_run=True, force=False)
    assert result["planned_updates"] == 1
    assert result["updated"] == 0
    assert db.documents.update_calls == 0


def test_forced_mode_overwrites_only_when_explicit():
    from services.evidence_review_backfill import compute_v2_backfill_patch

    doc = {
        "document_id": "d1",
        "status": "VERIFIED",
        "evidence_review_state": "REJECTED",
        "assurance_tier": "REJECTED",
    }
    no_force = compute_v2_backfill_patch(doc, force=False)
    force = compute_v2_backfill_patch(doc, force=True)
    assert no_force == {}
    assert force["evidence_review_state"] == "ACCEPTED_UNVERIFIED"
    assert force["assurance_tier"] == "HUMAN_ACCEPTED"


@pytest.mark.asyncio
async def test_admin_backfill_endpoint_dry_run_contract():
    from fastapi import Request
    from routes.admin import AdminEvidenceReviewBackfillBody, admin_backfill_evidence_review_v2

    req = MagicMock(spec=Request)
    req.state = MagicMock()
    req.state.user = {"portal_user_id": "admin-1", "role": "ROLE_ADMIN"}

    db = MagicMock()
    body = AdminEvidenceReviewBackfillBody(limit=200, dry_run=True, force=False)
    service_result = {
        "dry_run": True,
        "force": False,
        "limit": 200,
        "scanned": 3,
        "planned_updates": 2,
        "updated": 0,
        "counts_by_legacy_status": {"VERIFIED": 1},
        "counts_by_mapped_state": {"ACCEPTED_UNVERIFIED": 1},
        "preview": [],
    }
    with (
        patch("routes.admin.admin_route_guard", new_callable=AsyncMock),
        patch("routes.admin.database.get_db", return_value=db),
        patch("services.evidence_review_backfill.scan_evidence_review_backfill", new_callable=AsyncMock, return_value=service_result),
        patch("routes.admin.create_audit_log", new_callable=AsyncMock),
    ):
        out = await admin_backfill_evidence_review_v2(req, body)
    assert out["dry_run"] is True
    assert out["planned_updates"] == 2
    assert "counts_by_legacy_status" in out
    assert "counts_by_mapped_state" in out


@pytest.mark.asyncio
async def test_api_response_includes_v2_fields():
    from fastapi import Request
    from routes.documents import list_documents

    req = MagicMock(spec=Request)
    req.state = MagicMock()
    req.state.user = {"client_id": "c1", "portal_user_id": "u1", "role": "ROLE_CLIENT"}
    sample = [
        {
            "document_id": "d-legacy",
            "client_id": "c1",
            "status": "VERIFIED",
            "uploaded_at": "2026-01-01T00:00:00+00:00",
        }
    ]
    cursor = MagicMock()
    cursor.sort = MagicMock(return_value=cursor)
    cursor.to_list = AsyncMock(return_value=sample)
    db = MagicMock()
    db.documents.find = MagicMock(return_value=cursor)

    with (
        patch("routes.documents.client_route_guard", new_callable=AsyncMock, return_value=req.state.user),
        patch("routes.documents.database.get_db", return_value=db),
    ):
        out = await list_documents(req)

    doc = out["documents"][0]
    assert doc["evidence_review_state"] == "ACCEPTED_UNVERIFIED"
    assert doc["assurance_tier"] == "HUMAN_ACCEPTED"
    for key in (
        "latest_validation_snapshot",
        "review_required",
        "review_decision_at",
        "review_decision_by",
        "external_verification_method",
        "external_verification_reference",
    ):
        assert key in doc


@pytest.mark.asyncio
async def test_admin_pending_verification_includes_v2_fields():
    from fastapi import Request
    from routes.admin import list_pending_verification_documents

    req = MagicMock(spec=Request)
    req.state = MagicMock()
    req.state.user = {"portal_user_id": "admin-1", "role": "ROLE_ADMIN"}

    sample_docs = [
        {
            "document_id": "doc-1",
            "client_id": "client-a",
            "property_id": "prop-1",
            "requirement_id": "req-1",
            "status": "VERIFIED",
            "uploaded_at": "2025-02-10T10:00:00+00:00",
        }
    ]
    cursor = MagicMock()
    cursor.sort = MagicMock(return_value=cursor)
    cursor.skip = MagicMock(return_value=cursor)
    cursor.limit = MagicMock(return_value=cursor)
    cursor.to_list = AsyncMock(return_value=sample_docs)
    clients_cursor = MagicMock()
    clients_cursor.to_list = AsyncMock(return_value=[])
    req_cursor = MagicMock()
    req_cursor.to_list = AsyncMock(return_value=[])

    db = MagicMock()
    db.documents.count_documents = AsyncMock(return_value=1)
    db.documents.find = MagicMock(return_value=cursor)
    db.clients.find = MagicMock(return_value=clients_cursor)
    db.requirements.find = MagicMock(return_value=req_cursor)

    with (
        patch("routes.admin.admin_route_guard", new_callable=AsyncMock),
        patch("routes.admin.database.get_db", return_value=db),
    ):
        out = await list_pending_verification_documents(req, hours=0, client_id=None, limit=50, skip=0)

    row = out["documents"][0]
    assert row["evidence_review_state"] == "ACCEPTED_UNVERIFIED"
    assert row["assurance_tier"] == "HUMAN_ACCEPTED"
    assert "latest_validation_snapshot" in row

