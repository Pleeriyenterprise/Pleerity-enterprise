"""PR2: applicability_resolution_audit append-only writer."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from services.applicability_provenance_constants import OPERATOR_OVERRIDE, PIPELINE, RECONCILIATION_LOCK
from services.applicability_resolution_audit import (
    COLLECTION_NAME,
    append_applicability_resolution_audit,
    build_applicability_resolution_audit_document,
)


def _base_kwargs():
    return dict(
        client_id="c1",
        property_id="p1",
        requirement_id="r1",
        event_type="PR2_UNIT_TEST_APPEND",
        pipeline_applicability_state="UNKNOWN",
        effective_applicability_state="UNKNOWN",
        applicability_resolution_source=PIPELINE,
        actor={"type": "system", "id": "pytest"},
    )


def test_build_document_has_required_fields() -> None:
    doc = build_applicability_resolution_audit_document(**_base_kwargs())
    for k in (
        "event_id",
        "created_at",
        "client_id",
        "property_id",
        "requirement_id",
        "event_type",
        "pipeline_applicability_state",
        "effective_applicability_state",
        "applicability_resolution_source",
        "actor",
    ):
        assert k in doc
    assert doc["client_id"] == "c1"
    assert doc["property_id"] == "p1"
    assert doc["pipeline_applicability_state"] == "UNKNOWN"
    assert doc["effective_applicability_state"] == "UNKNOWN"
    assert doc["applicability_resolution_source"] == PIPELINE
    assert doc["actor"]["type"] == "system"


def test_property_id_nullable() -> None:
    kw = _base_kwargs()
    kw["property_id"] = None
    doc = build_applicability_resolution_audit_document(**kw)
    assert doc["property_id"] is None


def test_rejects_reserved_resolution_source() -> None:
    kw = _base_kwargs()
    kw["applicability_resolution_source"] = RECONCILIATION_LOCK
    with pytest.raises(ValueError):
        build_applicability_resolution_audit_document(**kw)


def test_rejects_invalid_actor() -> None:
    kw = _base_kwargs()
    kw["actor"] = {"type": "invalid"}
    with pytest.raises(ValueError):
        build_applicability_resolution_audit_document(**kw)


def test_operator_override_source_allowed() -> None:
    kw = _base_kwargs()
    kw.update(
        pipeline_applicability_state="UNKNOWN",
        effective_applicability_state="REQUIRED",
        applicability_resolution_source=OPERATOR_OVERRIDE,
    )
    doc = build_applicability_resolution_audit_document(**kw)
    assert doc["applicability_resolution_source"] == OPERATOR_OVERRIDE


@pytest.mark.asyncio
async def test_append_only_insert_one() -> None:
    coll = MagicMock()
    coll.insert_one = AsyncMock(return_value=MagicMock(inserted_id="oid1"))
    db = MagicMock()
    setattr(db, COLLECTION_NAME, coll)

    eid = await append_applicability_resolution_audit(db, **_base_kwargs())
    assert eid
    coll.insert_one.assert_awaited_once()
    args, _kwargs = coll.insert_one.await_args
    inserted = args[0]
    assert inserted["client_id"] == "c1"
    assert inserted["requirement_id"] == "r1"


@pytest.mark.asyncio
async def test_append_returns_event_id() -> None:
    coll = MagicMock()
    coll.insert_one = AsyncMock(return_value=MagicMock(inserted_id="x"))
    db = MagicMock()
    setattr(db, COLLECTION_NAME, coll)
    fixed = "00000000-0000-4000-8000-000000000001"
    eid = await append_applicability_resolution_audit(
        db,
        **_base_kwargs(),
        event_id=fixed,
    )
    assert eid == fixed


def test_stable_created_at_optional() -> None:
    ts = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    doc = build_applicability_resolution_audit_document(**_base_kwargs(), created_at=ts)
    assert doc["created_at"] == ts
