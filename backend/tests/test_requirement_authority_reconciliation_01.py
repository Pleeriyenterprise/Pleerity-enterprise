"""
REQUIREMENT-RECONCILIATION-AUTHORITY-01 regression tests.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, patch

import pytest

from services.provisioning import REQUIREMENT_GENERATION_SOURCE_DB_RULE
from services.requirement_authority_reconciliation_governance import (
    ARCHIVE_SOURCE,
    is_active_for_alias_reconciliation,
    is_authority_reconciled_superseded,
    select_canonical_requirement_row,
)
from services.requirement_authority_reconciliation_service import (
    _count_metrics,
    _group_active_duplicates,
    reconcile_requirement_authority_duplicates,
)


class _AsyncReqIter:
    def __init__(self, items: List[Dict[str, Any]]):
        self._items = list(items)

    def __aiter__(self):
        self._it = iter(self._items)
        return self

    async def __anext__(self):
        try:
            return next(self._it)
        except StopIteration as exc:
            raise StopAsyncIteration from exc

    def limit(self, _n: int):
        return self

    async def to_list(self, length: Optional[int] = None):
        items = list(self._items)
        if length is not None:
            items = items[:length]
        return items


class _FakeRequirements:
    def __init__(self, rows: List[Dict[str, Any]]):
        self.rows = {str(r["requirement_id"]): dict(r) for r in rows}
        self.updates: List[Dict[str, Any]] = []

    def find(self, query: Dict[str, Any], projection: Optional[Dict] = None):
        cid = (query or {}).get("client_id")
        out = []
        for r in self.rows.values():
            if cid and r.get("client_id") != cid:
                continue
            out.append(dict(r))
        return _AsyncReqIter(out)

    async def update_one(self, filt: Dict[str, Any], patch: Dict[str, Any]):
        rid = filt.get("requirement_id")
        row = self.rows.get(rid)
        if row and "$set" in patch:
            row.update(patch["$set"])
            self.rows[rid] = row
        self.updates.append({"filter": filt, "patch": patch})


class _FakeDB:
    def __init__(self, requirements: _FakeRequirements, properties: List[Dict], clients: List[Dict]):
        self.requirements = requirements
        self.properties = _FakeColl(properties)
        self.clients = _FakeColl(clients)


class _FakeColl:
    def __init__(self, items: List[Dict[str, Any]]):
        self.items = list(items)

    def find(self, query: Dict[str, Any], projection: Optional[Dict] = None):
        ids = set((query or {}).get("client_id", {}).get("$in") or [])
        key = "client_id"
        return _AsyncReqIter([x for x in self.items if not ids or x.get(key) in ids])


def _wales_prop(pid: str = "p1") -> Dict[str, Any]:
    return {"property_id": pid, "client_id": "c1", "jurisdiction": "Wales"}


def _occ_pair(property_id: str = "p1") -> List[Dict[str, Any]]:
    src = REQUIREMENT_GENERATION_SOURCE_DB_RULE
    return [
        {
            "requirement_id": "legacy-occ",
            "client_id": "c1",
            "property_id": property_id,
            "requirement_type": "occupation_contract",
            "requirement_code": "occupation_contract",
            "status": "PENDING",
            "applicability": "REQUIRED",
            "updated_at": "2026-01-01T00:00:00Z",
            "requirement_generation_source": src,
            "client_surface_visible": True,
        },
        {
            "requirement_id": "wales-occ",
            "client_id": "c1",
            "property_id": property_id,
            "requirement_type": "wales_occupation_contract",
            "requirement_code": "wales_occupation_contract",
            "status": "PENDING",
            "applicability": "REQUIRED",
            "updated_at": "2026-01-02T00:00:00Z",
            "requirement_generation_source": src,
            "client_surface_visible": True,
            "registry_metadata": {"action_links_published": [{"key": "k1"}]},
        },
    ]


def test_select_canonical_prefers_wales_catalog_slug():
    rows = _occ_pair()
    winner = select_canonical_requirement_row(
        rows,
        alias_family="wales_occupation_contract_alias_family",
        property_doc=_wales_prop(),
        client_doc={"client_id": "c1", "default_jurisdiction": "Wales"},
    )
    assert winner["requirement_id"] == "wales-occ"


def test_group_active_duplicates_finds_pair():
    groups = _group_active_duplicates(_occ_pair())
    assert len(groups) == 1
    assert groups[("c1", "p1", "wales_occupation_contract_alias_family")]


def test_count_metrics_duplicate_group():
    m = _count_metrics(_occ_pair())
    assert m["duplicate_active_groups"] == 1
    assert m["active_alias_family_rows"] == 2


@pytest.mark.asyncio
async def test_dry_run_does_not_write():
    reqs = _FakeRequirements(_occ_pair())
    db = _FakeDB(reqs, [_wales_prop()], [{"client_id": "c1"}])
    with patch("services.requirement_authority_reconciliation_service.database.get_db", return_value=db):
        out = await reconcile_requirement_authority_duplicates(client_id="c1", dry_run=True)
    assert out["records_to_archive"] == 1
    assert out["records_archived"] == 0
    assert len(reqs.updates) == 0
    assert out["metrics_after"]["duplicate_active_groups"] == 0


@pytest.mark.asyncio
async def test_execute_archives_loser_preserves_evidence():
    rows = _occ_pair()
    rows[0]["evidence_doc_id"] = "doc-legacy-1"
    reqs = _FakeRequirements(rows)
    db = _FakeDB(reqs, [_wales_prop()], [{"client_id": "c1"}])
    with patch("services.requirement_authority_reconciliation_service.database.get_db", return_value=db):
        with patch(
            "services.requirement_authority_reconciliation_service.create_audit_log",
            new_callable=AsyncMock,
        ) as audit:
            out = await reconcile_requirement_authority_duplicates(client_id="c1", dry_run=False)
    assert out["records_archived"] == 1
    loser = reqs.rows["legacy-occ"]
    assert loser["evidence_doc_id"] == "doc-legacy-1"
    assert is_authority_reconciled_superseded(loser)
    assert loser["registry_metadata"]["authority_reconciliation"]["canonical_requirement_id"] == "wales-occ"
    assert reqs.rows["wales-occ"]["registry_metadata"].get("authority_reconciliation") is None
    audit.assert_awaited_once()


@pytest.mark.asyncio
async def test_second_run_is_idempotent():
    rows = _occ_pair()
    reqs = _FakeRequirements(rows)
    db = _FakeDB(reqs, [_wales_prop()], [{"client_id": "c1"}])
    with patch("services.requirement_authority_reconciliation_service.database.get_db", return_value=db):
        with patch(
            "services.requirement_authority_reconciliation_service.create_audit_log",
            new_callable=AsyncMock,
        ):
            first = await reconcile_requirement_authority_duplicates(client_id="c1", dry_run=False)
            second = await reconcile_requirement_authority_duplicates(client_id="c1", dry_run=False)
    assert first["records_archived"] == 1
    assert second["records_to_archive"] == 0
    assert second["records_archived"] == 0
    assert _count_metrics(list(reqs.rows.values()))["duplicate_active_groups"] == 0


@pytest.mark.asyncio
async def test_already_superseded_rows_skipped():
    rows = _occ_pair()
    rows[0]["registry_metadata"] = {
        "lifecycle": {"status": "superseded"},
        "authority_reconciliation": {
            "archive_source": ARCHIVE_SOURCE,
            "canonical_requirement_id": "wales-occ",
        },
    }
    reqs = _FakeRequirements(rows)
    db = _FakeDB(reqs, [_wales_prop()], [{"client_id": "c1"}])
    with patch("services.requirement_authority_reconciliation_service.database.get_db", return_value=db):
        out = await reconcile_requirement_authority_duplicates(client_id="c1", dry_run=False)
    assert out["records_to_archive"] == 0


def test_deposit_alias_family_duplicate():
    rows = [
        {
            "requirement_id": "dep-a",
            "client_id": "c1",
            "property_id": "p1",
            "requirement_type": "deposit_pi",
            "status": "PENDING",
            "applicability": "REQUIRED",
            "updated_at": "2026-01-01T00:00:00Z",
        },
        {
            "requirement_id": "dep-b",
            "client_id": "c1",
            "property_id": "p1",
            "requirement_type": "tenancy_deposit_protection",
            "status": "PENDING",
            "applicability": "REQUIRED",
            "updated_at": "2026-02-01T00:00:00Z",
        },
    ]
    groups = _group_active_duplicates(rows)
    assert len(groups) == 1
    winner = select_canonical_requirement_row(rows, alias_family="tenancy_deposit_alias_family")
    assert winner["requirement_id"] == "dep-b"


@pytest.mark.asyncio
async def test_no_duplicate_dataset_zero_archives():
    rows = [
        {
            "requirement_id": "gas-1",
            "client_id": "c1",
            "property_id": "p1",
            "requirement_type": "gas_safety",
            "status": "PENDING",
            "applicability": "REQUIRED",
        }
    ]
    reqs = _FakeRequirements(rows)
    db = _FakeDB(reqs, [_wales_prop()], [{"client_id": "c1"}])
    with patch("services.requirement_authority_reconciliation_service.database.get_db", return_value=db):
        out = await reconcile_requirement_authority_duplicates(client_id="c1", dry_run=True)
    assert out["duplicate_families_found"] == 0
    assert out["records_to_archive"] == 0


@pytest.mark.asyncio
async def test_large_portfolio_many_rows_one_duplicate():
    rows = []
    for i in range(200):
        rows.append(
            {
                "requirement_id": f"req-{i}",
                "client_id": "c1",
                "property_id": f"p-{i}",
                "requirement_type": "gas_safety",
                "status": "PENDING",
                "applicability": "REQUIRED",
            }
        )
    rows.extend(_occ_pair("p-dup"))
    reqs = _FakeRequirements(rows)
    props = [_wales_prop("p-dup")] + [{"property_id": f"p-{i}", "client_id": "c1", "jurisdiction": "Wales"} for i in range(200)]
    db = _FakeDB(reqs, props, [{"client_id": "c1"}])
    with patch("services.requirement_authority_reconciliation_service.database.get_db", return_value=db):
        out = await reconcile_requirement_authority_duplicates(client_id="c1", dry_run=True)
    assert out["duplicate_families_found"] == 1
    assert out["records_to_archive"] == 1


@pytest.mark.asyncio
async def test_runtime_visible_count_unchanged_after_reconcile():
    """Archiving superseded rows must not change client runtime filter output."""
    rows = _occ_pair()
    reqs = _FakeRequirements(rows)
    db = _FakeDB(reqs, [_wales_prop()], [{"client_id": "c1"}])
    with patch("services.requirement_authority_reconciliation_service.database.get_db", return_value=db):
        with patch(
            "services.requirement_authority_reconciliation_service.create_audit_log",
            new_callable=AsyncMock,
        ):
            from services.requirement_client_runtime_surface import (
                filter_requirement_rows_for_client_runtime_surfaces,
            )

            before = await filter_requirement_rows_for_client_runtime_surfaces(
                db,
                client_id="c1",
                requirements=list(rows),
                client_doc={"client_id": "c1", "default_jurisdiction": "Wales"},
                properties=[_wales_prop()],
            )
            await reconcile_requirement_authority_duplicates(client_id="c1", dry_run=False)
            after_rows = list(reqs.rows.values())
            after = await filter_requirement_rows_for_client_runtime_surfaces(
                db,
                client_id="c1",
                requirements=after_rows,
                client_doc={"client_id": "c1", "default_jurisdiction": "Wales"},
                properties=[_wales_prop()],
            )
    assert len(before) == len(after) == 1
    assert before[0]["requirement_id"] == after[0]["requirement_id"] == "wales-occ"


def test_mixed_jurisdiction_wales_preference():
    rows = [
        {
            "requirement_id": "legacy-occ",
            "client_id": "c1",
            "property_id": "p1",
            "requirement_type": "occupation_contract",
            "status": "PENDING",
            "applicability": "REQUIRED",
            "updated_at": "2026-01-02T00:00:00Z",
        },
        {
            "requirement_id": "wales-occ",
            "client_id": "c1",
            "property_id": "p1",
            "requirement_type": "wales_occupation_contract",
            "status": "PENDING",
            "applicability": "REQUIRED",
            "updated_at": "2026-01-01T00:00:00Z",
        },
    ]
    winner = select_canonical_requirement_row(
        rows,
        alias_family="wales_occupation_contract_alias_family",
        property_doc={"property_id": "p1", "client_id": "c1", "jurisdiction": "England"},
        client_doc={"default_jurisdiction": "England"},
    )
    assert winner["requirement_id"] == "legacy-occ"
