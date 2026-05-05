from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from services.requirement_read_model_guard import (
    filter_rows_to_canonical_requirement_ids,
    get_canonical_requirement_ids_for_property,
    get_canonical_requirement_ids_map_for_properties,
)


class _FakeCollection:
    def __init__(self, items):
        self._items = [dict(x) for x in items]

    async def find_one(self, query, projection=None):
        for d in self._items:
            if all(d.get(k) == v for k, v in query.items()):
                return dict(d)
        return None

    def find(self, query, projection=None):
        class _Cur:
            def __init__(self, rows):
                self._rows = rows

            async def to_list(self, length=0):
                return [dict(x) for x in self._rows]

        rows = []
        for d in self._items:
            ok = True
            for k, v in query.items():
                if d.get(k) != v:
                    ok = False
                    break
            if ok:
                rows.append(d)
        return _Cur(rows)


class _FakeDB:
    def __init__(self):
        self.clients = _FakeCollection([{"client_id": "c1", "default_jurisdiction": "England"}])
        self.properties = _FakeCollection([{"client_id": "c1", "property_id": "p1", "jurisdiction": "England"}])
        self.requirements = _FakeCollection(
            [
                {"client_id": "c1", "property_id": "p1", "requirement_id": "r1"},
                {"client_id": "c1", "property_id": "p1", "requirement_id": "r2"},
            ]
        )


class _MotorLikeDatabaseNoBool(_FakeDB):
    """Mimics PyMongo/Motor: truth-value testing is forbidden on Database objects."""

    def __bool__(self):
        raise NotImplementedError(
            "Database objects do not implement truth value testing or bool(). "
            "Please compare with None instead."
        )


@pytest.mark.asyncio
async def test_get_canonical_requirement_ids_for_property_returns_filtered_ids():
    db = _FakeDB()
    filtered = [
        {"requirement_id": "r1"},
        {"requirement_id": "r2"},
    ]
    with patch(
        "services.requirement_read_model_guard.filter_requirement_rows_for_client_runtime_surfaces",
        new=AsyncMock(return_value=filtered),
    ):
        out = await get_canonical_requirement_ids_for_property("c1", "p1", db=db)
    assert out == {"r1", "r2"}


@pytest.mark.asyncio
async def test_get_canonical_requirement_ids_does_not_truth_test_db_passed_motor_like():
    """Passing a db handle must not use `if db` / `db or` — Motor Database forbids bool()."""
    db = _MotorLikeDatabaseNoBool()
    filtered = [
        {"requirement_id": "r1"},
        {"requirement_id": "r2"},
    ]
    with patch(
        "services.requirement_read_model_guard.filter_requirement_rows_for_client_runtime_surfaces",
        new=AsyncMock(return_value=filtered),
    ):
        out = await get_canonical_requirement_ids_for_property("c1", "p1", db=db)
    assert out == {"r1", "r2"}


@pytest.mark.asyncio
async def test_get_canonical_requirement_ids_map_for_properties_does_not_truth_test_db():
    db = _MotorLikeDatabaseNoBool()
    filtered = [{"requirement_id": "r1"}]
    with patch(
        "services.requirement_read_model_guard.filter_requirement_rows_for_client_runtime_surfaces",
        new=AsyncMock(return_value=filtered),
    ):
        out = await get_canonical_requirement_ids_map_for_properties(
            "c1",
            {"p1"},
            db=db,
        )
    assert out == {"p1": {"r1"}}


def test_filter_rows_to_canonical_requirement_ids_drops_missing_and_noncanonical_rows():
    rows = [
        {"requirement_id": "r1", "requirement_code": "gas_safety"},
        {"requirement_id": "r2", "requirement_code": "right_to_rent"},
        {"requirement_id": "", "requirement_code": "eicr"},
    ]
    kept, dropped = filter_rows_to_canonical_requirement_ids(rows, {"r1"})
    assert [r["requirement_id"] for r in kept] == ["r1"]
    assert len(dropped) == 2
    assert all(d.get("reason") == "missing_or_noncanonical_requirement_id" for d in dropped)
