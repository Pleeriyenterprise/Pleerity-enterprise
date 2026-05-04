"""
Mixed-jurisdiction portfolio: canonical runtime filter must stay property-scoped and
jurisdiction-scoped. Dedupe must never collapse rows across properties or merge legally
distinct jurisdiction variants.

Dashboard / Requirements / Today / Command Centre all consume the same filtered requirement
rows at the data layer; we validate aggregation invariants that those surfaces rely on.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Dict, List
from unittest.mock import AsyncMock, patch

import pytest

from services.compliance_requirement_registry import REQUIREMENT_GENERATION_SOURCE_REGISTRY
from services.provisioning import REQUIREMENT_GENERATION_SOURCE_DB_RULE
from services.requirement_client_runtime_surface import filter_requirement_rows_for_client_runtime_surfaces
from services.requirement_truth import enrich_requirements_for_client


class _AsyncPropIter:
    def __init__(self, items: List[Dict[str, Any]]):
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
    """Minimal stub: ``clients.find_one`` + optional ``properties.find``."""

    def __init__(self, client_doc: Dict[str, Any], props: List[Dict[str, Any]]):
        self._client = dict(client_doc)
        self._props = list(props)

    async def find_one(self, *_a, **_k):
        return dict(self._client)

    def find(self, *_a, **_k):
        return _AsyncPropIter(self._props)


class _EnrichFakeClients:
    def __init__(self, client_id: str):
        self._client_id = client_id

    async def find_one(self, query: Dict[str, Any], projection=None):
        if query.get("client_id") == self._client_id:
            return {"client_id": self._client_id, "default_jurisdiction": "England"}
        return None


class _EnrichFakeProperties:
    def __init__(self, props_by_id: Dict[str, Dict[str, Any]]):
        self._props = props_by_id

    def find(self, query: Dict[str, Any], projection=None):
        pids = (query.get("property_id") or {}).get("$in") or []
        items = [self._props[pid] for pid in pids if pid in self._props]
        return _AsyncPropIter(items)


class _EnrichFakeDB:
    """DB stub for ``enrich_requirements_for_client`` matching ``db.clients`` / ``db.properties``."""

    def __init__(self, client_id: str, props: List[Dict[str, Any]]):
        props_by_id = {p["property_id"]: dict(p) for p in props}
        self.clients = _EnrichFakeClients(client_id)
        self.properties = _EnrichFakeProperties(props_by_id)


def _prop(
    *,
    pid: str,
    client_id: str,
    jurisdiction: str,
) -> Dict[str, Any]:
    return {
        "property_id": pid,
        "client_id": client_id,
        "jurisdiction": jurisdiction,
        "property_type": "residential",
        "tenancy_active": True,
        "has_gas_supply": True,
        "deposit_taken": True,
        "furnished": False,
        "is_hmo": False,
    }


def _db_row(
    *,
    rid: str,
    client_id: str,
    pid: str,
    rtype: str,
    source: str = REQUIREMENT_GENERATION_SOURCE_DB_RULE,
    jurisdiction: str = "",
    status: str = "PENDING",
    updated_at: str = "2026-01-01T00:00:00Z",
    extra: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    row: Dict[str, Any] = {
        "requirement_id": rid,
        "client_id": client_id,
        "property_id": pid,
        "requirement_type": rtype,
        "requirement_code": rtype,
        "jurisdiction": jurisdiction,
        "applicability": "REQUIRED",
        "status": status,
        "client_surface_visible": True,
        "requirement_generation_source": source,
        "updated_at": updated_at,
    }
    if extra:
        row.update(extra)
    return row


def _visible(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [r for r in rows if r.get("client_surface_visible") is not False]


def _dashboard_style_aggregate(filtered: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Same grouping shape as ``GET /api/client/dashboard`` requirement handling."""
    vis = _visible(filtered)
    by_pid: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in vis:
        pid = r.get("property_id")
        if pid:
            by_pid[str(pid)].append(r)
    return {
        "total_requirements": len(vis),
        "by_property": {k: len(v) for k, v in by_pid.items()},
        "by_property_rows": dict(by_pid),
    }


def _assert_no_cross_property_dedupe(filtered: List[Dict[str, Any]], *, expect_per_code: Dict[str, int]):
    """``expect_per_code``: canonical_code -> expected count across portfolio (may be >1 across props)."""
    canon_by_pid: Dict[str, Counter[str]] = defaultdict(Counter)
    for r in filtered:
        pid = str(r.get("property_id") or "")
        cc = str(r.get("canonical_code") or "").strip().lower()
        if pid and cc:
            canon_by_pid[pid][cc] += 1
    total = Counter()
    for ctr in canon_by_pid.values():
        total += ctr
    for code, n in expect_per_code.items():
        assert total[code] == n, (code, dict(total), expect_per_code)


def _assert_attribution(filtered: List[Dict[str, Any]], props_by_id: Dict[str, Dict[str, Any]]):
    for r in filtered:
        pid = str(r.get("property_id") or "")
        prop = props_by_id.get(pid) or {}
        exp = (prop.get("jurisdiction") or "").strip()
        pj = str(r.get("property_jurisdiction") or "").strip()
        assert pj == exp, (r.get("requirement_id"), pj, exp)
        assert str(r.get("jurisdiction_source") or "") == "property_explicit"


@pytest.mark.asyncio
async def test_mixed_england_scotland_portfolio_no_cross_property_or_jurisdiction_leakage():
    client_id = "mix-es"
    p_eng = "p-eng-es"
    p_sct = "p-sct-es"
    props = [_prop(pid=p_eng, client_id=client_id, jurisdiction="England"), _prop(pid=p_sct, client_id=client_id, jurisdiction="Scotland")]
    props_by_id = {p["property_id"]: p for p in props}
    client_doc = {"client_id": client_id, "default_jurisdiction": "England"}
    rows = [
        # Same canonical obligation on two properties — must remain two rows.
        _db_row(rid="g-eng", client_id=client_id, pid=p_eng, rtype="gas_safety", jurisdiction="England"),
        _db_row(rid="g-sct", client_id=client_id, pid=p_sct, rtype="gas_safety", jurisdiction="Scotland"),
        # Alias family per property: two rows each -> one winner per property after dedupe.
        _db_row(rid="fa-eng", client_id=client_id, pid=p_eng, rtype="fire_alarm", jurisdiction="England", updated_at="2026-01-01T00:00:00Z"),
        _db_row(
            rid="fd-eng",
            client_id=client_id,
            pid=p_eng,
            rtype="fire_detection",
            jurisdiction="England",
            updated_at="2026-01-02T00:00:00Z",
            extra={"registry_metadata": {"action_links_published": [{"k": 1}]}},
        ),
        _db_row(rid="fa-sct", client_id=client_id, pid=p_sct, rtype="fire_alarm", jurisdiction="Scotland"),
        _db_row(rid="fd-sct", client_id=client_id, pid=p_sct, rtype="fire_detection", jurisdiction="Scotland", updated_at="2026-01-02T00:00:00Z"),
        # Jurisdiction leak attempt: England-only slug on Scotland property (catalog planner excludes).
        _db_row(
            rid="rtr-sct",
            client_id=client_id,
            pid=p_sct,
            rtype="right_to_rent",
            jurisdiction="England",
            source=REQUIREMENT_GENERATION_SOURCE_REGISTRY,
        ),
    ]
    db = _FakeDB(client_doc, props)
    out = await filter_requirement_rows_for_client_runtime_surfaces(
        db,
        client_id=client_id,
        requirements=rows,
        client_doc=client_doc,
        properties=props,
        published_registry_entries=None,
    )
    ids = {r["requirement_id"] for r in out}
    assert "g-eng" in ids and "g-sct" in ids
    assert "rtr-sct" not in ids
    # One fire alias winner per property.
    assert sum(1 for r in out if r["property_id"] == p_eng and str(r.get("canonical_code")) == "smoke_heat_alarms") == 1
    assert sum(1 for r in out if r["property_id"] == p_sct and str(r.get("canonical_code")) == "smoke_heat_alarms") == 1
    assert "fa-eng" not in ids and "fd-eng" in ids  # winner has published enrichment on England
    _assert_attribution(out, props_by_id)
    _assert_no_cross_property_dedupe(out, expect_per_code={"gas_safety": 2, "smoke_heat_alarms": 2})
    agg = _dashboard_style_aggregate(out)
    assert agg["total_requirements"] == len(out)
    assert agg["by_property"][p_eng] + agg["by_property"][p_sct] == agg["total_requirements"]


@pytest.mark.asyncio
async def test_mixed_england_wales_portfolio_no_cross_jurisdiction_leakage():
    client_id = "mix-ew"
    p_eng = "p-eng-ew"
    p_wal = "p-wal-ew"
    props = [_prop(pid=p_eng, client_id=client_id, jurisdiction="England"), _prop(pid=p_wal, client_id=client_id, jurisdiction="Wales")]
    props_by_id = {p["property_id"]: p for p in props}
    client_doc = {"client_id": client_id, "default_jurisdiction": "England"}
    rows = [
        _db_row(rid="gas-eng", client_id=client_id, pid=p_eng, rtype="gas_safety", jurisdiction="England"),
        _db_row(rid="gas-wal", client_id=client_id, pid=p_wal, rtype="gas_safety", jurisdiction="Wales"),
        # Wales-only statutory on Wales property (must appear only there when planner emits it).
        _db_row(
            rid="oc-wal",
            client_id=client_id,
            pid=p_wal,
            rtype="wales_occupation_contract",
            jurisdiction="Wales",
            source=REQUIREMENT_GENERATION_SOURCE_REGISTRY,
        ),
        # Leak: Wales occupation contract row tied to England property — must drop.
        _db_row(
            rid="oc-leak-eng",
            client_id=client_id,
            pid=p_eng,
            rtype="wales_occupation_contract",
            jurisdiction="Wales",
            source=REQUIREMENT_GENERATION_SOURCE_REGISTRY,
        ),
    ]
    db = _FakeDB(client_doc, props)
    out = await filter_requirement_rows_for_client_runtime_surfaces(
        db,
        client_id=client_id,
        requirements=rows,
        client_doc=client_doc,
        properties=props,
        published_registry_entries=None,
    )
    ids = {r["requirement_id"] for r in out}
    assert "gas-eng" in ids and "gas-wal" in ids
    assert "oc-leak-eng" not in ids
    if "oc-wal" in ids:
        assert all(r.get("property_id") != p_eng for r in out if r["requirement_id"] == "oc-wal")
    _assert_attribution(out, props_by_id)
    agg = _dashboard_style_aggregate(out)
    assert agg["total_requirements"] == len(out)


@pytest.mark.asyncio
async def test_mixed_scotland_ni_portfolio_legally_distinct_registration_not_merged():
    client_id = "mix-sn"
    p_sct = "p-sct-sn"
    p_ni = "p-ni-sn"
    props = [_prop(pid=p_sct, client_id=client_id, jurisdiction="Scotland"), _prop(pid=p_ni, client_id=client_id, jurisdiction="Northern Ireland")]
    props_by_id = {p["property_id"]: p for p in props}
    client_doc = {"client_id": client_id, "default_jurisdiction": "Scotland"}
    rows = [
        _db_row(
            rid="lr-sct",
            client_id=client_id,
            pid=p_sct,
            rtype="scotland_landlord_registration",
            jurisdiction="Scotland",
            source=REQUIREMENT_GENERATION_SOURCE_DB_RULE,
        ),
        _db_row(
            rid="lr-ni",
            client_id=client_id,
            pid=p_ni,
            rtype="landlord_registration_ni",
            jurisdiction="Northern Ireland",
            source=REQUIREMENT_GENERATION_SOURCE_DB_RULE,
        ),
        # Same English label family but legally distinct codes — both must survive.
        _db_row(rid="gas-sct", client_id=client_id, pid=p_sct, rtype="gas_safety", jurisdiction="Scotland"),
        _db_row(rid="gas-ni", client_id=client_id, pid=p_ni, rtype="gas_safety", jurisdiction="Northern Ireland"),
        # Leak: NI registration slug on Scotland property — excluded when catalog-governed.
        _db_row(
            rid="ni-on-sct",
            client_id=client_id,
            pid=p_sct,
            rtype="landlord_registration_ni",
            jurisdiction="Northern Ireland",
            source=REQUIREMENT_GENERATION_SOURCE_REGISTRY,
        ),
    ]
    db = _FakeDB(client_doc, props)
    out = await filter_requirement_rows_for_client_runtime_surfaces(
        db,
        client_id=client_id,
        requirements=rows,
        client_doc=client_doc,
        properties=props,
        published_registry_entries=None,
    )
    ids = {r["requirement_id"] for r in out}
    assert "lr-sct" in ids and "lr-ni" in ids
    assert "gas-sct" in ids and "gas-ni" in ids
    assert "ni-on-sct" not in ids
    codes_sct = {str(r.get("canonical_code")) for r in out if r["property_id"] == p_sct}
    codes_ni = {str(r.get("canonical_code")) for r in out if r["property_id"] == p_ni}
    assert "scotland_landlord_registration" in codes_sct
    assert "landlord_registration_ni" in codes_ni
    assert "landlord_registration_ni" not in codes_sct
    _assert_attribution(out, props_by_id)
    _assert_no_cross_property_dedupe(out, expect_per_code={"gas_safety": 2})
    agg = _dashboard_style_aggregate(out)
    assert agg["total_requirements"] == len(out)
    assert set(agg["by_property"].keys()) == {p_sct, p_ni}


@pytest.mark.asyncio
async def test_mixed_portfolio_today_command_centre_style_slice_preserves_property_attribution():
    """
    Today / Command Centre consume filtered requirement rows in bulk then attach property labels.
    Ensure a portfolio-wide filter pass never drops or merges rows across properties.
    """
    client_id = "mix-tc"
    p_a = "p-a"
    p_b = "p-b"
    props = [
        _prop(pid=p_a, client_id=client_id, jurisdiction="England"),
        _prop(pid=p_b, client_id=client_id, jurisdiction="Wales"),
    ]
    props_by_id = {p["property_id"]: p for p in props}
    client_doc = {"client_id": client_id, "default_jurisdiction": "England"}
    rows = [
        _db_row(rid="a1", client_id=client_id, pid=p_a, rtype="eicr", jurisdiction="England"),
        _db_row(rid="b1", client_id=client_id, pid=p_b, rtype="eicr", jurisdiction="Wales"),
        _db_row(rid="a2", client_id=client_id, pid=p_a, rtype="legionella", jurisdiction="England"),
        _db_row(rid="b2", client_id=client_id, pid=p_b, rtype="legionella", jurisdiction="Wales"),
    ]
    db = _FakeDB(client_doc, props)
    out = await filter_requirement_rows_for_client_runtime_surfaces(
        db,
        client_id=client_id,
        requirements=rows,
        client_doc=client_doc,
        properties=props,
        published_registry_entries=None,
    )
    assert len(out) == 4
    by_pid = defaultdict(list)
    for r in out:
        by_pid[str(r["property_id"])].append(r)
    assert len(by_pid[p_a]) == 2 and len(by_pid[p_b]) == 2
    _assert_attribution(out, props_by_id)
    # Same canonical_code on two properties — four rows, not collapsed to two.
    assert sum(1 for r in out if str(r.get("canonical_code")) == "eicr") == 2
    assert sum(1 for r in out if str(r.get("canonical_code")) == "legionella") == 2


@pytest.mark.asyncio
async def test_mixed_portfolio_enrich_uses_per_property_document_for_resolver():
    """
    ``enrich_requirements_for_client`` must pass the correct full ``property_doc`` for each
    row so published CTA / why_it_matters / action-link resolution stays jurisdiction-scoped.
    """
    client_id = "mix-enrich"
    p_eng = "p-en-e"
    p_wal = "p-wa-e"
    props = [_prop(pid=p_eng, client_id=client_id, jurisdiction="England"), _prop(pid=p_wal, client_id=client_id, jurisdiction="Wales")]
    reqs = [
        _db_row(rid="r1", client_id=client_id, pid=p_eng, rtype="gas_safety", jurisdiction="England"),
        _db_row(rid="r2", client_id=client_id, pid=p_wal, rtype="gas_safety", jurisdiction="Wales"),
    ]
    captured: List[tuple] = []

    def _capture_enrich(req, live_ev, **kwargs):
        pd = kwargs.get("property_doc") or {}
        captured.append((str(req.get("property_id")), str(pd.get("jurisdiction") or "")))
        out = dict(req)
        out["why_it_matters_short"] = f"why-{pd.get('jurisdiction')}"
        out["take_action"] = {"primary": {"action_type": "view", "label": f"cta-{pd.get('jurisdiction')}", "url": "/"}}
        out["action_links"] = [{"label": f"link-{pd.get('jurisdiction')}"}]
        return out

    db = _EnrichFakeDB(client_id, props)
    with (
        patch("services.requirement_truth.fetch_active_published_registry_entries", new_callable=AsyncMock, return_value={}),
        patch("services.requirement_truth.load_evidence_state_by_requirement_id", new_callable=AsyncMock, return_value={}),
        patch("services.requirement_truth.enrich_requirement_dict", side_effect=_capture_enrich),
    ):
        enriched, _ = await enrich_requirements_for_client(db, client_id, reqs)
    assert captured == [(p_eng, "England"), (p_wal, "Wales")]
    by_pid = {r["property_id"]: r for r in enriched}
    assert by_pid[p_eng]["why_it_matters_short"] == "why-England"
    assert by_pid[p_wal]["why_it_matters_short"] == "why-Wales"
    assert by_pid[p_eng]["take_action"]["primary"]["label"] == "cta-England"
    assert by_pid[p_wal]["take_action"]["primary"]["label"] == "cta-Wales"
    assert by_pid[p_eng]["action_links"][0]["label"] == "link-England"
    assert by_pid[p_wal]["action_links"][0]["label"] == "link-Wales"
