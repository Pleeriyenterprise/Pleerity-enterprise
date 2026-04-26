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

    with patch("services.compliance_score.database.get_db", return_value=db), patch(
        "services.catalog_compliance.get_portfolio_compliance_from_catalog",
        new_callable=AsyncMock,
        side_effect=_catalog,
    ):
        result = await calculate_compliance_score("c1")

    assert result.get("score") == 88
    view = result.get("catalog_portfolio_view") or {}
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

    with patch("services.compliance_score.database.get_db", return_value=db), patch(
        "services.catalog_compliance.get_portfolio_compliance_from_catalog",
        new_callable=AsyncMock,
        return_value=None,
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
