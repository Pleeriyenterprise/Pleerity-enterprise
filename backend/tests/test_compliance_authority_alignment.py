"""
Authority alignment: headline score vs catalog alternate view; stats projection consistency hooks.
"""
from __future__ import annotations

import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))


@pytest.fixture(autouse=True)
def _stub_enqueue_and_lazy_backfill():
    with patch(
        "services.compliance_recalc_queue.enqueue_compliance_recalc",
        new_callable=AsyncMock,
        return_value=True,
    ):
        yield


def _make_db_mock(properties: list, requirements: list, documents: list, *, client_id: str = "c1"):
    from services.provisioning import REQUIREMENT_GENERATION_SOURCE_DB_RULE

    br_default = {
        "status_score": 99,
        "expiry_score": 98,
        "document_score": 99,
        "overdue_penalty_score": 100,
        "risk_score": 96,
    }
    props_out = []
    for p in properties:
        q = {**p}
        if "compliance_score" not in q:
            q["compliance_score"] = 88
        if "compliance_breakdown" not in q:
            q["compliance_breakdown"] = dict(br_default)
        props_out.append(q)
    reqs_out = []
    for r in requirements:
        q = {**r, "client_id": client_id} if "client_id" not in r else dict(r)
        if "requirement_generation_source" not in q:
            q["requirement_generation_source"] = REQUIREMENT_GENERATION_SOURCE_DB_RULE
        reqs_out.append(q)

    async def _props(*_a, **_k):
        return list(props_out)

    async def _reqs(*_a, **_k):
        return list(reqs_out)

    async def _docs(*_a, **_k):
        return list(documents)

    db = MagicMock()
    db.properties = MagicMock()
    db.properties.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(side_effect=_props)))
    async def _prop_find_one(query, projection=None):
        for p in props_out:
            if all(p.get(k) == v for k, v in (query or {}).items()):
                return dict(p)
        return None
    db.properties.find_one = AsyncMock(side_effect=_prop_find_one)
    db.requirements = MagicMock()
    db.requirements.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(side_effect=_reqs)))
    db.documents = MagicMock()
    db.documents.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(side_effect=_docs)))
    db.clients = MagicMock()
    db.clients.find_one = AsyncMock(return_value={})
    return db


@pytest.mark.asyncio
async def test_catalog_portfolio_view_does_not_replace_headline_score():
    """Headline score stays persisted average; catalog matrix is exposed only under catalog_portfolio_view."""
    from services.compliance_score import calculate_compliance_score

    due = (datetime.now(timezone.utc) + timedelta(days=120)).isoformat()
    properties = [{"property_id": "p1", "client_id": "c1", "is_hmo": False, "compliance_score": 88}]
    requirements = [
        {
            "requirement_id": "r1",
            "property_id": "p1",
            "requirement_type": "EPC",
            "status": "COMPLIANT",
            "due_date": due,
            "client_surface_visible": True,
        },
    ]
    documents = [{"document_id": "d1", "property_id": "p1", "requirement_id": "r1", "status": "VERIFIED"}]
    db = _make_db_mock(properties, requirements, documents)

    async def _catalog(_client_id: str):
        return {
            "portfolio_score": 12,
            "risk_level": "Critical Risk",
            "portfolio_risk_level": "Critical Risk",
            "updated_at": "2026-01-15T00:00:00+00:00",
        }

    _eff = {
        "base_portfolio_risk_state": "Low Risk",
        "effective_portfolio_risk_state": "Low Risk",
        "risk_override_reasons": [],
        "critical_property_count": 0,
        "high_risk_gap_count": 0,
        "unknown_or_stale_property_count": 0,
        "attention_required": False,
        "critical_property_escalation": False,
        "suppress_positive_headline": False,
    }
    _override_bundle = {
        "legacy_override_output": _eff,
        "policy_override_output": _eff,
        "effective_override_output": _eff,
    }

    with patch("services.compliance_score.database.get_db", return_value=db), patch(
        "services.catalog_compliance.get_portfolio_compliance_from_catalog",
        new_callable=AsyncMock,
        side_effect=_catalog,
    ), patch(
        "services.compliance_gap_sync.aggregate_gap_counts_for_client",
        new_callable=AsyncMock,
        return_value={"by_kind": {}, "by_severity": {}, "total_open": 0, "policy": {}},
    ), patch(
        "services.compliance_score.build_portfolio_override_outputs",
        new_callable=AsyncMock,
        return_value=_override_bundle,
    ):
        result = await calculate_compliance_score("c1")

    assert result.get("score") == 88
    view = result.get("catalog_portfolio_view") or {}
    assert view.get("score_authority") == "non_authoritative_requirement_matrix"
    assert view.get("portfolio_score") == 12
    assert view.get("risk_level") == "Critical Risk"


@pytest.mark.asyncio
async def test_stats_overdue_matches_portal_projection_counts():
    """stats.overdue uses same portal projection as compute_client_portal_requirement_stats."""
    from services.compliance_score import calculate_compliance_score
    from services.requirement_client_runtime_surface import (
        compute_client_portal_requirement_stats,
        project_requirement_row_client_runtime,
        client_portal_surface_visible_row,
    )

    past = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
    properties = [{"property_id": "p1", "client_id": "c1", "is_hmo": False, "compliance_score": 70}]
    requirements = [
        {
            "requirement_id": "r1",
            "property_id": "p1",
            "requirement_type": "EPC",
            "status": "EXPIRED",
            "due_date": past,
            "client_surface_visible": True,
        },
        {
            "requirement_id": "r2",
            "property_id": "p1",
            "requirement_type": "GAS_SAFETY",
            "status": "COMPLIANT",
            "due_date": (datetime.now(timezone.utc) + timedelta(days=200)).isoformat(),
            "client_surface_visible": True,
        },
    ]
    documents = []
    db = _make_db_mock(properties, requirements, documents)

    _eff = {
        "base_portfolio_risk_state": "Low Risk",
        "effective_portfolio_risk_state": "Low Risk",
        "risk_override_reasons": [],
        "critical_property_count": 0,
        "high_risk_gap_count": 0,
        "unknown_or_stale_property_count": 0,
        "attention_required": False,
        "critical_property_escalation": False,
        "suppress_positive_headline": False,
    }
    _override_bundle = {
        "legacy_override_output": _eff,
        "policy_override_output": _eff,
        "effective_override_output": _eff,
    }

    with patch("services.compliance_score.database.get_db", return_value=db), patch(
        "services.catalog_compliance.get_portfolio_compliance_from_catalog",
        new_callable=AsyncMock,
        return_value=None,
    ), patch(
        "services.compliance_gap_sync.aggregate_gap_counts_for_client",
        new_callable=AsyncMock,
        return_value={"by_kind": {}, "by_severity": {}, "total_open": 0, "policy": {}},
    ), patch(
        "services.compliance_score.build_portfolio_override_outputs",
        new_callable=AsyncMock,
        return_value=_override_bundle,
    ):
        result = await calculate_compliance_score("c1")

    proj = [project_requirement_row_client_runtime(dict(r)) for r in requirements]
    portal = [r for r in proj if client_portal_surface_visible_row(r)]
    expected = compute_client_portal_requirement_stats(portal)
    assert result.get("stats", {}).get("overdue") == expected["overdue"]
    assert result.get("stats", {}).get("total_requirements") == expected["total_requirements"]


@pytest.mark.asyncio
async def test_property_compliance_stats_use_portal_projection_counts():
    from services.compliance_scoring_service import calculate_property_compliance
    from services.provisioning import REQUIREMENT_GENERATION_SOURCE_DB_RULE

    now = datetime.now(timezone.utc)
    db = MagicMock()
    db.properties.find_one = AsyncMock(
        return_value={
            "property_id": "p1",
            "client_id": "c1",
            "jurisdiction": "England",
            "is_hmo": False,
        }
    )
    reqs = [
        {
            "requirement_id": "r1",
            "property_id": "p1",
            "requirement_type": "EPC",
            "status": "EXPIRED",
            "due_date": (now - timedelta(days=7)).isoformat(),
            "client_surface_visible": True,
            "requirement_generation_source": REQUIREMENT_GENERATION_SOURCE_DB_RULE,
        },
        {
            "requirement_id": "r2",
            "property_id": "p1",
            "requirement_type": "GAS_SAFETY",
            "status": "PENDING",
            "due_date": (now + timedelta(days=20)).isoformat(),
            "client_surface_visible": True,
            "requirement_generation_source": REQUIREMENT_GENERATION_SOURCE_DB_RULE,
        },
        {
            "requirement_id": "r3",
            "property_id": "p1",
            "requirement_type": "EICR",
            "status": "COMPLIANT",
            "due_date": (now + timedelta(days=120)).isoformat(),
            "client_surface_visible": True,
            "requirement_generation_source": REQUIREMENT_GENERATION_SOURCE_DB_RULE,
        },
    ]
    db.requirements.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=reqs)))
    db.documents.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[])))
    db.clients.find_one = AsyncMock(return_value={"default_jurisdiction": "England"})
    db.maintenance_issues.count_documents = AsyncMock(return_value=0)
    db.work_orders.count_documents = AsyncMock(return_value=0)
    db.risk_signals.count_documents = AsyncMock(return_value=0)

    with patch("services.compliance_scoring_service.database.get_db", return_value=db), patch(
        "services.compliance_scoring_service.compute_property_score_v2",
        return_value={
            "score_0_100": 64,
            "requirement_breakdown": [],
            "bucket_breakdown": {},
            "earned_points": 64.0,
            "applicable_points": 100.0,
            "top_deficits": [],
            "top_next_actions": [],
            "jurisdiction": "ENGLAND_WALES",
        },
    ):
        out = await calculate_property_compliance("p1")

    st = out.get("stats") or {}
    assert st.get("total_requirements") == 3
    assert st.get("overdue") == 1
    assert st.get("pending") == 1
    assert st.get("missing_evidence") == 1
    assert st.get("compliant") == 1


@pytest.mark.asyncio
async def test_score_drivers_filtered_to_canonical_subset_and_score_unchanged():
    from services.compliance_score import calculate_compliance_score

    now = datetime.now(timezone.utc)
    due = (now + timedelta(days=180)).isoformat()
    properties = [{"property_id": "p1", "client_id": "c1", "is_hmo": False, "compliance_score": 80}]
    requirements = [
        {
            "requirement_id": "r-valid",
            "property_id": "p1",
            "requirement_type": "EICR",
            "status": "COMPLIANT",
            "due_date": due,
            "client_surface_visible": True,
        },
        {
            "requirement_id": "r-expired",
            "property_id": "p1",
            "requirement_type": "GAS_SAFETY",
            "status": "EXPIRED",
            "due_date": (now - timedelta(days=3)).isoformat(),
            "client_surface_visible": True,
        },
        {
            "requirement_id": "r-orphan",
            "property_id": "p1",
            "requirement_type": "EPC",
            "status": "EXPIRED",
            "due_date": (now - timedelta(days=2)).isoformat(),
            "client_surface_visible": True,
        },
    ]
    db = _make_db_mock(properties, requirements, [])
    _eff = {
        "base_portfolio_risk_state": "Low Risk",
        "effective_portfolio_risk_state": "Low Risk",
        "risk_override_reasons": [],
        "critical_property_count": 0,
        "high_risk_gap_count": 0,
        "unknown_or_stale_property_count": 0,
        "attention_required": False,
        "critical_property_escalation": False,
        "suppress_positive_headline": False,
    }
    _override_bundle = {
        "legacy_override_output": _eff,
        "policy_override_output": _eff,
        "effective_override_output": _eff,
    }

    with patch("services.compliance_score.database.get_db", return_value=db), patch(
        "services.catalog_compliance.get_portfolio_compliance_from_catalog",
        new_callable=AsyncMock,
        return_value=None,
    ), patch(
        "services.compliance_gap_sync.aggregate_gap_counts_for_client",
        new_callable=AsyncMock,
        return_value={"by_kind": {}, "by_severity": {}, "total_open": 0, "policy": {}},
    ), patch(
        "services.compliance_score.build_portfolio_override_outputs",
        new_callable=AsyncMock,
        return_value=_override_bundle,
    ), patch(
        "services.compliance_score.get_canonical_requirement_ids_map_for_properties",
        new_callable=AsyncMock,
        return_value={"p1": {"r-valid", "r-expired"}},
    ):
        result = await calculate_compliance_score("c1")

    assert result.get("score") == 80
    drivers = result.get("drivers") or []
    ids = {(d.get("property_id"), d.get("requirement_id")) for d in drivers}
    assert ("p1", "r-expired") in ids
    assert ("p1", "r-valid") not in ids
    assert ("p1", "r-orphan") not in ids


@pytest.mark.asyncio
async def test_score_drivers_missing_id_requires_property_and_unique_code_match():
    from services.compliance_score import calculate_compliance_score

    now = datetime.now(timezone.utc)
    properties = [{"property_id": "p1", "client_id": "c1", "is_hmo": False, "compliance_score": 75}]
    requirements = [
        {
            "requirement_id": "r-gas",
            "property_id": "p1",
            "requirement_type": "gas_safety",
            "status": "EXPIRED",
            "due_date": (now - timedelta(days=1)).isoformat(),
            "client_surface_visible": True,
        },
        {
            "requirement_id": "",
            "property_id": "p1",
            "requirement_type": "gas_safety_certificate",
            "status": "EXPIRED",
            "due_date": (now - timedelta(days=2)).isoformat(),
            "client_surface_visible": True,
        },
        {
            "requirement_id": "",
            "property_id": "",
            "requirement_type": "gas_safety_certificate",
            "status": "EXPIRED",
            "due_date": (now - timedelta(days=2)).isoformat(),
            "client_surface_visible": True,
        },
    ]
    db = _make_db_mock(properties, requirements, [])
    _eff = {
        "base_portfolio_risk_state": "Low Risk",
        "effective_portfolio_risk_state": "Low Risk",
        "risk_override_reasons": [],
        "critical_property_count": 0,
        "high_risk_gap_count": 0,
        "unknown_or_stale_property_count": 0,
        "attention_required": False,
        "critical_property_escalation": False,
        "suppress_positive_headline": False,
    }
    _override_bundle = {
        "legacy_override_output": _eff,
        "policy_override_output": _eff,
        "effective_override_output": _eff,
    }

    with patch("services.compliance_score.database.get_db", return_value=db), patch(
        "services.catalog_compliance.get_portfolio_compliance_from_catalog",
        new_callable=AsyncMock,
        return_value=None,
    ), patch(
        "services.compliance_gap_sync.aggregate_gap_counts_for_client",
        new_callable=AsyncMock,
        return_value={"by_kind": {}, "by_severity": {}, "total_open": 0, "policy": {}},
    ), patch(
        "services.compliance_score.build_portfolio_override_outputs",
        new_callable=AsyncMock,
        return_value=_override_bundle,
    ), patch(
        "services.compliance_score.get_canonical_requirement_ids_map_for_properties",
        new_callable=AsyncMock,
        return_value={"p1": {"r-gas"}},
    ):
        result = await calculate_compliance_score("c1")

    drivers = result.get("drivers") or []
    ids = [(d.get("property_id"), d.get("requirement_id")) for d in drivers]
    assert ("p1", "r-gas") in ids
    assert all(d.get("property_id") for d in drivers)


@pytest.mark.asyncio
async def test_score_drivers_ambiguous_and_cross_property_aliases_excluded_or_scoped():
    from services.compliance_score import calculate_compliance_score

    now = datetime.now(timezone.utc)
    properties = [
        {"property_id": "p1", "client_id": "c1", "is_hmo": False, "compliance_score": 70},
        {"property_id": "p2", "client_id": "c1", "is_hmo": False, "compliance_score": 70},
    ]
    requirements = [
        {
            "requirement_id": "r1a",
            "property_id": "p1",
            "requirement_type": "smoke_heat_alarms",
            "status": "EXPIRED",
            "due_date": (now - timedelta(days=4)).isoformat(),
            "client_surface_visible": True,
        },
        {
            "requirement_id": "r1b",
            "property_id": "p1",
            "requirement_type": "smoke_alarms",
            "status": "EXPIRED",
            "due_date": (now - timedelta(days=4)).isoformat(),
            "client_surface_visible": True,
        },
        {
            "requirement_id": "",
            "property_id": "p1",
            "requirement_type": "co_alarms",
            "status": "EXPIRED",
            "due_date": (now - timedelta(days=4)).isoformat(),
            "client_surface_visible": True,
        },
        {
            "requirement_id": "r2",
            "property_id": "p2",
            "requirement_type": "gas_safety",
            "status": "EXPIRED",
            "due_date": (now - timedelta(days=2)).isoformat(),
            "client_surface_visible": True,
        },
        {
            "requirement_id": "",
            "property_id": "p2",
            "requirement_type": "gas_safety_certificate",
            "status": "EXPIRED",
            "due_date": (now - timedelta(days=2)).isoformat(),
            "client_surface_visible": True,
        },
    ]
    db = _make_db_mock(properties, requirements, [])
    _eff = {
        "base_portfolio_risk_state": "Moderate Risk",
        "effective_portfolio_risk_state": "Moderate Risk",
        "risk_override_reasons": [],
        "critical_property_count": 0,
        "high_risk_gap_count": 0,
        "unknown_or_stale_property_count": 0,
        "attention_required": False,
        "critical_property_escalation": False,
        "suppress_positive_headline": False,
    }
    _override_bundle = {
        "legacy_override_output": _eff,
        "policy_override_output": _eff,
        "effective_override_output": _eff,
    }

    with patch("services.compliance_score.database.get_db", return_value=db), patch(
        "services.catalog_compliance.get_portfolio_compliance_from_catalog",
        new_callable=AsyncMock,
        return_value=None,
    ), patch(
        "services.compliance_gap_sync.aggregate_gap_counts_for_client",
        new_callable=AsyncMock,
        return_value={"by_kind": {}, "by_severity": {}, "total_open": 0, "policy": {}},
    ), patch(
        "services.compliance_score.build_portfolio_override_outputs",
        new_callable=AsyncMock,
        return_value=_override_bundle,
    ), patch(
        "services.compliance_score.get_canonical_requirement_ids_map_for_properties",
        new_callable=AsyncMock,
        return_value={"p1": {"r1a", "r1b"}, "p2": {"r2"}},
    ):
        result = await calculate_compliance_score("c1")

    drivers = result.get("drivers") or []
    keys = {(d.get("property_id"), d.get("requirement_id")) for d in drivers}
    # p1 missing-id alias maps to multiple canonical rows -> excluded
    assert ("p1", "r1a") in keys or ("p1", "r1b") in keys
    # p2 missing-id alias maps to the unique p2 canonical row; must not cross-match to p1
    assert ("p2", "r2") in keys
    assert sum(1 for d in drivers if d.get("property_id") == "p2" and d.get("requirement_id") == "r2") == 1
    assert all(k[0] in {"p1", "p2"} for k in keys)


@pytest.mark.asyncio
async def test_score_drivers_empty_when_property_has_no_canonical_requirements():
    from services.compliance_score import calculate_compliance_score

    now = datetime.now(timezone.utc)
    properties = [{"property_id": "eng-1", "client_id": "c1", "is_hmo": False, "compliance_score": 66}]
    requirements = [
        {
            "requirement_id": "wales-occupation-contract",
            "property_id": "eng-1",
            "requirement_type": "wales_occupation_contract",
            "status": "EXPIRED",
            "due_date": (now - timedelta(days=5)).isoformat(),
            "client_surface_visible": True,
        }
    ]
    db = _make_db_mock(properties, requirements, [])
    _eff = {
        "base_portfolio_risk_state": "High Risk",
        "effective_portfolio_risk_state": "High Risk",
        "risk_override_reasons": [],
        "critical_property_count": 0,
        "high_risk_gap_count": 0,
        "unknown_or_stale_property_count": 0,
        "attention_required": True,
        "critical_property_escalation": False,
        "suppress_positive_headline": False,
    }
    _override_bundle = {
        "legacy_override_output": _eff,
        "policy_override_output": _eff,
        "effective_override_output": _eff,
    }
    with patch("services.compliance_score.database.get_db", return_value=db), patch(
        "services.catalog_compliance.get_portfolio_compliance_from_catalog",
        new_callable=AsyncMock,
        return_value=None,
    ), patch(
        "services.compliance_gap_sync.aggregate_gap_counts_for_client",
        new_callable=AsyncMock,
        return_value={"by_kind": {}, "by_severity": {}, "total_open": 0, "policy": {}},
    ), patch(
        "services.compliance_score.build_portfolio_override_outputs",
        new_callable=AsyncMock,
        return_value=_override_bundle,
    ), patch(
        "services.compliance_score.get_canonical_requirement_ids_map_for_properties",
        new_callable=AsyncMock,
        return_value={"eng-1": set()},
    ):
        result = await calculate_compliance_score("c1")
    assert result.get("score") == 66
    assert result.get("drivers") == []


@pytest.mark.asyncio
async def test_score_drivers_due_window_reappears_but_future_due_hidden():
    from services.compliance_score import calculate_compliance_score

    now = datetime.now(timezone.utc)
    properties = [{"property_id": "p1", "client_id": "c1", "is_hmo": False, "compliance_score": 81}]
    requirements = [
        {
            "requirement_id": "r-future",
            "property_id": "p1",
            "requirement_type": "gas_safety",
            "status": "VALID",
            "due_date": (now + timedelta(days=120)).isoformat(),
            "evidence_state": "VERIFIED",
            "client_surface_visible": True,
        },
        {
            "requirement_id": "r-due",
            "property_id": "p1",
            "requirement_type": "gas_safety",
            "status": "VALID",
            "due_date": (now + timedelta(days=5)).isoformat(),
            "evidence_state": "VERIFIED",
            "client_surface_visible": True,
        },
    ]
    db = _make_db_mock(properties, requirements, [])
    _eff = {
        "base_portfolio_risk_state": "Low Risk",
        "effective_portfolio_risk_state": "Low Risk",
        "risk_override_reasons": [],
        "critical_property_count": 0,
        "high_risk_gap_count": 0,
        "unknown_or_stale_property_count": 0,
        "attention_required": False,
        "critical_property_escalation": False,
        "suppress_positive_headline": False,
    }
    _override_bundle = {
        "legacy_override_output": _eff,
        "policy_override_output": _eff,
        "effective_override_output": _eff,
    }
    with patch("services.compliance_score.database.get_db", return_value=db), patch(
        "services.catalog_compliance.get_portfolio_compliance_from_catalog",
        new_callable=AsyncMock,
        return_value=None,
    ), patch(
        "services.compliance_gap_sync.aggregate_gap_counts_for_client",
        new_callable=AsyncMock,
        return_value={"by_kind": {}, "by_severity": {}, "total_open": 0, "policy": {}},
    ), patch(
        "services.compliance_score.build_portfolio_override_outputs",
        new_callable=AsyncMock,
        return_value=_override_bundle,
    ), patch(
        "services.compliance_score.get_canonical_requirement_ids_map_for_properties",
        new_callable=AsyncMock,
        return_value={"p1": {"r-future", "r-due"}},
    ), patch(
        "services.compliance_score.resolve_expiring_soon_days_for_requirement",
        return_value=30,
    ):
        result = await calculate_compliance_score("c1")
    assert result.get("score") == 81
    ids = {(d.get("property_id"), d.get("requirement_id")) for d in (result.get("drivers") or [])}
    assert ("p1", "r-due") in ids
    assert ("p1", "r-future") not in ids
