"""
Regression: deliberately poisoned requirement rows must not pass the shared runtime surface filter.

Surfaces that consume ``filter_requirement_rows_for_client_runtime_surfaces`` (or
``requirement_row_eligible_on_client_runtime_surfaces``) include client dashboard,
property requirements lists, reminders, monthly digest assembly, evidence readiness /
reporting exports, compliance pack, assistant + retrieval snapshots, calendar, ROI, etc.
"""
from __future__ import annotations

import pytest

from services.provisioning import REQUIREMENT_GENERATION_SOURCE_DB_RULE
from services.requirement_client_runtime_surface import filter_requirement_rows_for_client_runtime_surfaces


class _AsyncPropIter:
    def __init__(self, items):
        self._items = list(items)

    def __aiter__(self):
        self._i = iter(self._items)
        return self

    async def __anext__(self):
        try:
            return next(self._i)
        except StopIteration as e:
            raise StopAsyncIteration from e


class _FakeDB:
    """Minimal db stub: ``clients.find_one`` + ``properties.find`` async iteration."""

    def __init__(self, props):
        self._props = props

    async def find_one(self, *_a, **_k):
        return {"client_id": "c1", "default_jurisdiction": "England"}

    def find(self, *_a, **_k):
        return _AsyncPropIter(self._props)


def _england_residential(pid: str = "p-eng"):
    return {
        "property_id": pid,
        "client_id": "c1",
        "jurisdiction": "England",
        "property_type": "residential",
        "tenancy_active": True,
        "has_gas_supply": True,
        "deposit_taken": True,
        "furnished": False,
        "is_hmo": False,
    }


def _wales_residential(pid: str = "p-wales"):
    return {
        "property_id": pid,
        "client_id": "c1",
        "jurisdiction": "Wales",
        "property_type": "residential",
        "tenancy_active": True,
        "has_gas_supply": True,
        "deposit_taken": True,
        "furnished": False,
        "is_hmo": False,
    }


@pytest.mark.asyncio
async def test_injected_leak_rows_removed_by_shared_surface_filter():
    """
    Inserts (as if from Mongo) four poison rows + valid gas rows; only valid in-plan rows remain.
    Same filter backs dashboard, lists, digest, reminders, exports, compliance pack, assistant paths.
    """
    props = [_england_residential("p-eng"), _wales_residential("p-wales")]
    poisoned = [
        # Wales-only statutory row materialised against England property (wrong explicit jurisdiction)
        {
            "requirement_id": "leak-wales-contract-on-eng",
            "client_id": "c1",
            "property_id": "p-eng",
            "requirement_type": "wales_occupation_contract",
            "jurisdiction": "Wales",
            "applicability": "REQUIRED",
            "status": "PENDING",
            "client_surface_visible": True,
            "requirement_generation_source": REQUIREMENT_GENERATION_SOURCE_DB_RULE,
        },
        # England-only row on Wales property
        {
            "requirement_id": "leak-rtr-on-wales",
            "client_id": "c1",
            "property_id": "p-wales",
            "requirement_type": "right_to_rent",
            "jurisdiction": "England",
            "applicability": "REQUIRED",
            "status": "PENDING",
            "client_surface_visible": True,
            "requirement_generation_source": REQUIREMENT_GENERATION_SOURCE_DB_RULE,
        },
        # Draft-only materialisation flag (never published snapshot)
        {
            "requirement_id": "leak-draft-gas",
            "client_id": "c1",
            "property_id": "p-eng",
            "requirement_type": "gas_safety",
            "jurisdiction": "England",
            "applicability": "REQUIRED",
            "status": "PENDING",
            "client_surface_visible": True,
            "requirement_generation_source": REQUIREMENT_GENERATION_SOURCE_DB_RULE,
            "registry_metadata": {"draft_only_materialization": True},
        },
        # Archived registry metadata on row
        {
            "requirement_id": "leak-archived-gas",
            "client_id": "c1",
            "property_id": "p-eng",
            "requirement_type": "gas_safety",
            "jurisdiction": "England",
            "applicability": "REQUIRED",
            "status": "PENDING",
            "client_surface_visible": True,
            "requirement_generation_source": REQUIREMENT_GENERATION_SOURCE_DB_RULE,
            "registry_metadata": {"lifecycle": {"status": "archived"}},
        },
        # Valid rows (one per property)
        {
            "requirement_id": "ok-gas-eng",
            "client_id": "c1",
            "property_id": "p-eng",
            "requirement_type": "gas_safety",
            "jurisdiction": "England",
            "applicability": "REQUIRED",
            "status": "PENDING",
            "client_surface_visible": True,
            "requirement_generation_source": REQUIREMENT_GENERATION_SOURCE_DB_RULE,
        },
        {
            "requirement_id": "ok-gas-wales",
            "client_id": "c1",
            "property_id": "p-wales",
            "requirement_type": "gas_safety",
            "jurisdiction": "Wales",
            "applicability": "REQUIRED",
            "status": "PENDING",
            "client_surface_visible": True,
            "requirement_generation_source": REQUIREMENT_GENERATION_SOURCE_DB_RULE,
        },
    ]
    db = _FakeDB(props)
    out = await filter_requirement_rows_for_client_runtime_surfaces(
        db,
        client_id="c1",
        requirements=poisoned,
        client_doc={"default_jurisdiction": "England"},
        properties=props,
        published_registry_entries=None,
    )
    ids = {r["requirement_id"] for r in out}
    assert ids == {"ok-gas-eng", "ok-gas-wales"}
    for bid in (
        "leak-wales-contract-on-eng",
        "leak-rtr-on-wales",
        "leak-draft-gas",
        "leak-archived-gas",
    ):
        assert bid not in ids


@pytest.mark.asyncio
async def test_true_alias_family_rows_are_deduped_with_precedence_and_legal_distinct_rows_remain():
    props = [_england_residential("p-eng")]
    rows = [
        # Same fire-detection obligation represented by legacy alias rows.
        {
            "requirement_id": "fire-a",
            "client_id": "c1",
            "property_id": "p-eng",
            "requirement_type": "fire_alarm",
            "requirement_code": "fire_alarm",
            "jurisdiction": "England",
            "applicability": "REQUIRED",
            "status": "PENDING",
            "client_surface_visible": True,
            "requirement_generation_source": REQUIREMENT_GENERATION_SOURCE_DB_RULE,
            "updated_at": "2026-01-01T00:00:00Z",
            "registry_metadata": {"action_links_published": [{"key": "k1"}]},
        },
        {
            "requirement_id": "fire-b",
            "client_id": "c1",
            "property_id": "p-eng",
            "requirement_type": "fire_detection",
            "requirement_code": "fire_detection",
            "jurisdiction": "England",
            "applicability": "REQUIRED",
            "status": "PENDING",
            "client_surface_visible": True,
            "requirement_generation_source": REQUIREMENT_GENERATION_SOURCE_DB_RULE,
            "updated_at": "2026-01-02T00:00:00Z",
        },
        # Legally distinct obligations must remain separate.
        {
            "requirement_id": "em-light",
            "client_id": "c1",
            "property_id": "p-eng",
            "requirement_type": "emergency_lighting",
            "requirement_code": "emergency_lighting",
            "jurisdiction": "England",
            "applicability": "REQUIRED",
            "status": "PENDING",
            "client_surface_visible": True,
            "requirement_generation_source": REQUIREMENT_GENERATION_SOURCE_DB_RULE,
            "updated_at": "2026-01-03T00:00:00Z",
        },
        {
            "requirement_id": "ext",
            "client_id": "c1",
            "property_id": "p-eng",
            "requirement_type": "fire_extinguisher",
            "requirement_code": "fire_extinguisher",
            "jurisdiction": "England",
            "applicability": "REQUIRED",
            "status": "PENDING",
            "client_surface_visible": True,
            "requirement_generation_source": REQUIREMENT_GENERATION_SOURCE_DB_RULE,
            "updated_at": "2026-01-04T00:00:00Z",
        },
    ]
    db = _FakeDB(props)
    out = await filter_requirement_rows_for_client_runtime_surfaces(
        db,
        client_id="c1",
        requirements=rows,
        client_doc={"default_jurisdiction": "England"},
        properties=props,
        published_registry_entries=None,
    )
    ids = {r["requirement_id"] for r in out}
    # Published-enriched fire alias row wins within family.
    assert "fire-a" in ids
    assert "fire-b" not in ids
    # Distinct obligations remain.
    assert "em-light" in ids
    assert "ext" in ids
    for r in out:
        assert r.get("canonical_code")
        assert r.get("source") in {"baseline", "published", "both"}
        assert r.get("property_jurisdiction") == "England"


@pytest.mark.asyncio
async def test_smoke_alarms_and_fire_alarm_alias_family_collapses_to_one_row():
    props = [_england_residential("p-eng")]
    rows = [
        {
            "requirement_id": "sm-a",
            "client_id": "c1",
            "property_id": "p-eng",
            "requirement_type": "smoke_alarms",
            "requirement_code": "smoke_alarms",
            "jurisdiction": "England",
            "applicability": "REQUIRED",
            "status": "PENDING",
            "client_surface_visible": True,
            "requirement_generation_source": REQUIREMENT_GENERATION_SOURCE_DB_RULE,
            "updated_at": "2026-01-01T00:00:00Z",
        },
        {
            "requirement_id": "fa-b",
            "client_id": "c1",
            "property_id": "p-eng",
            "requirement_type": "fire_alarm",
            "requirement_code": "fire_alarm",
            "jurisdiction": "England",
            "applicability": "REQUIRED",
            "status": "PENDING",
            "client_surface_visible": True,
            "requirement_generation_source": REQUIREMENT_GENERATION_SOURCE_DB_RULE,
            "updated_at": "2026-01-02T00:00:00Z",
        },
    ]
    db = _FakeDB(props)
    out = await filter_requirement_rows_for_client_runtime_surfaces(
        db,
        client_id="c1",
        requirements=rows,
        client_doc={"default_jurisdiction": "England"},
        properties=props,
        published_registry_entries=None,
    )
    ids = {r["requirement_id"] for r in out}
    assert len(ids) == 1
    assert ids == {"fa-b"}
