"""
REQUIREMENT-AUTHORITY-ONBOARDING-DRIFT-AUDIT-01 regression tests.

Proves:
- Wales occupation alias family dedupes legacy ``occupation_contract`` vs ``wales_occupation_contract``.
- Provisioning skips legacy DB ``occupation_contract`` when planner already has Wales catalog slug.
- Electrical risk signals do not fire on PENDING/MISSING EICR alone (calendar-confirmed only).
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.provisioning import ProvisioningService, REQUIREMENT_GENERATION_SOURCE_DB_RULE
from services.requirement_client_runtime_surface import filter_requirement_rows_for_client_runtime_surfaces
from services.risk_signal_service import _rule_electrical


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
    def __init__(self, props):
        self._props = props

    async def find_one(self, *_a, **_k):
        return {"client_id": "c1", "default_jurisdiction": "Wales"}

    def find(self, *_a, **_k):
        return _AsyncPropIter(self._props)


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
async def test_wales_occupation_contract_alias_family_dedupes_duplicate_slugs():
    props = [_wales_residential()]
    rows = [
        {
            "requirement_id": "occ-legacy",
            "client_id": "c1",
            "property_id": "p-wales",
            "requirement_type": "occupation_contract",
            "requirement_code": "occupation_contract",
            "jurisdiction": "Wales",
            "applicability": "REQUIRED",
            "status": "PENDING",
            "client_surface_visible": True,
            "requirement_generation_source": REQUIREMENT_GENERATION_SOURCE_DB_RULE,
            "updated_at": "2026-01-01T00:00:00Z",
        },
        {
            "requirement_id": "occ-wales",
            "client_id": "c1",
            "property_id": "p-wales",
            "requirement_type": "wales_occupation_contract",
            "requirement_code": "wales_occupation_contract",
            "jurisdiction": "Wales",
            "applicability": "REQUIRED",
            "status": "PENDING",
            "client_surface_visible": True,
            "requirement_generation_source": REQUIREMENT_GENERATION_SOURCE_DB_RULE,
            "updated_at": "2026-01-02T00:00:00Z",
            "registry_metadata": {"action_links_published": [{"key": "k1"}]},
        },
    ]
    db = _FakeDB(props)
    out = await filter_requirement_rows_for_client_runtime_surfaces(
        db,
        client_id="c1",
        requirements=rows,
        client_doc={"default_jurisdiction": "Wales"},
        properties=props,
        published_registry_entries=None,
    )
    ids = {r["requirement_id"] for r in out}
    assert len(ids) == 1
    assert "occ-wales" in ids
    assert "occ-legacy" not in ids


@pytest.mark.asyncio
async def test_provisioning_skips_db_occupation_contract_when_wales_catalog_planned():
    svc = ProvisioningService()
    created: list[str] = []

    async def capture_create(_client_id, _property_id, requirement_type, *_a, **_kw):
        created.append(requirement_type)

    svc._create_requirement_if_not_exists = capture_create  # type: ignore[method-assign]

    rules = [
        {
            "rule_type": "occupation_contract",
            "name": "Occupation Contract",
            "frequency_days": 365,
            "warning_days": 30,
            "governed": False,
        }
    ]
    prop = _wales_residential()
    await svc._apply_db_rules(
        rules,
        "c1",
        "p-wales",
        "residential",
        prop,
        {"default_jurisdiction": "Wales"},
        planned_registry_types={"wales_occupation_contract", "gas_safety"},
    )
    assert created == []


@pytest.mark.asyncio
async def test_electrical_risk_does_not_fire_on_pending_eicr_only():
    requirements = [
        {
            "requirement_id": "eicr-1",
            "requirement_code": "eicr",
            "requirement_type": "eicr",
            "status": "PENDING",
        }
    ]
    out = await _rule_electrical(
        MagicMock(),
        "p1",
        "c1",
        {},
        [],
        [],
        [],
        requirements,
    )
    assert out == []


@pytest.mark.asyncio
async def test_electrical_risk_fires_on_overdue_eicr():
    requirements = [
        {
            "requirement_id": "eicr-1",
            "requirement_code": "eicr",
            "requirement_type": "eicr",
            "status": "OVERDUE",
        }
    ]
    out = await _rule_electrical(
        MagicMock(),
        "p1",
        "c1",
        {},
        [],
        [],
        [],
        requirements,
    )
    assert len(out) == 1
    assert out[0]["risk_type"] == "Electrical Risk"
    assert any("calendar-confirmed" in r.lower() for r in out[0]["reasons"])


@pytest.mark.asyncio
async def test_portal_setup_status_exposes_tracked_attention_semantics():
    from routes.portal import _portal_requirement_count_semantics

    mock_db = MagicMock()

    async def req_to_list(_limit):
        return [
            {
                "requirement_id": "doc-1",
                "client_id": "c1",
                "property_id": "p-wales",
                "requirement_type": "gas_safety",
                "compliance_requirement_class": "DOCUMENT",
                "client_surface_visible": True,
                "applicability": "REQUIRED",
                "status": "PENDING",
            },
            {
                "requirement_id": "obl-1",
                "client_id": "c1",
                "property_id": "p-wales",
                "requirement_type": "wales_occupation_contract",
                "compliance_requirement_class": "OBLIGATION",
                "client_surface_visible": True,
                "applicability": "REQUIRED",
                "status": "PENDING",
            },
        ]

    async def prop_to_list(_limit):
        return [_wales_residential()]

    mock_db.requirements.find.return_value.to_list = req_to_list
    mock_db.properties.find.return_value.to_list = prop_to_list

    with patch(
        "services.requirement_client_runtime_surface.filter_requirement_rows_for_client_runtime_surfaces",
        new=AsyncMock(side_effect=lambda _db, **kw: kw["requirements"]),
    ):
        with patch(
            "services.requirement_truth.enrich_requirements_for_client",
            new=AsyncMock(side_effect=lambda _db, _cid, rows: (rows, {})),
        ):
            out = await _portal_requirement_count_semantics(
                mock_db,
                "c1",
                {"client_id": "c1"},
                ["p-wales"],
            )

    assert out["requirements_runtime_visible_count"] == 2
    assert out["requirements_tracked_attention_count"] == 1
    assert out["requirements_count_semantics"] == "tracked_attention_document_job_excludes_obligation"
