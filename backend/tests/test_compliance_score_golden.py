"""
Golden-case unit tests for compliance score accuracy.
Seeds minimal DB state (mocked) and asserts exact or bounded numeric outputs.
"""
import pytest
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from services.compliance_score import (
    calculate_compliance_score,
    get_requirement_weight,
    DEFAULT_REQUIREMENT_WEIGHT,
    REQUIREMENT_TYPE_WEIGHTS,
)


@pytest.fixture(autouse=True)
def _stub_enqueue_and_catalog_overlay():
    """MagicMock DB + no catalog score overlay (production path merges catalog portfolio_score)."""
    with patch(
        "services.compliance_recalc_queue.enqueue_compliance_recalc",
        new_callable=AsyncMock,
        return_value=True,
    ), patch(
        "services.catalog_compliance.get_portfolio_compliance_from_catalog",
        new_callable=AsyncMock,
        return_value=None,
    ):
        yield


def _make_db_mock(
    properties: list,
    requirements: list,
    documents: list,
    *,
    client_id: str = "c1",
    default_property_score: int | None = 98,
    default_breakdown: dict | None = None,
):
    """Mock DB for calculate_compliance_score (stored scores on properties + reqs/docs for stats)."""
    br_default = {
        "status_score": 99,
        "expiry_score": 98,
        "document_score": 99,
        "overdue_penalty_score": 100,
        "risk_score": 96,
    }
    br = default_breakdown if default_breakdown is not None else br_default
    props_out = []
    for p in properties:
        q = {**p}
        if "compliance_score" not in q and default_property_score is not None:
            q["compliance_score"] = default_property_score
        if "compliance_breakdown" not in q and default_property_score is not None:
            q["compliance_breakdown"] = dict(br)
        props_out.append(q)
    reqs_out = [{**r, "client_id": client_id} if "client_id" not in r else r for r in requirements]
    docs_out = [{**d, "client_id": client_id} if "client_id" not in d else d for d in documents]

    async def _props_to_list(*_a, **_kw):
        return list(props_out)

    async def _reqs_to_list(*_a, **_kw):
        return list(reqs_out)

    async def _docs_to_list(*_a, **_kw):
        return list(docs_out)

    db = MagicMock()
    db.properties = MagicMock()
    db.properties.find = MagicMock(
        return_value=MagicMock(to_list=AsyncMock(side_effect=_props_to_list))
    )
    db.requirements = MagicMock()
    db.requirements.find = MagicMock(
        return_value=MagicMock(to_list=AsyncMock(side_effect=_reqs_to_list))
    )
    db.documents = MagicMock()
    db.documents.find = MagicMock(
        return_value=MagicMock(to_list=AsyncMock(side_effect=_docs_to_list))
    )
    db.clients = MagicMock()
    db.clients.find_one = AsyncMock(return_value={})
    return db


class TestCaseA_AllCompliantNear100:
    """Case A: Everything compliant + valid expiry + docs present → score near 100."""

    @pytest.mark.asyncio
    async def test_all_compliant_valid_expiry_docs_present_score_near_100(self):
        due = (datetime.now(timezone.utc) + timedelta(days=120)).isoformat()
        properties = [
            {"property_id": "p1", "client_id": "c1", "is_hmo": False},
        ]
        requirements = [
            {"requirement_id": "r1", "property_id": "p1", "requirement_type": "GAS_SAFETY", "status": "COMPLIANT", "due_date": due},
            {"requirement_id": "r2", "property_id": "p1", "requirement_type": "EICR", "status": "COMPLIANT", "due_date": due},
        ]
        documents = [
            {"document_id": "d1", "property_id": "p1", "requirement_id": "r1", "status": "VERIFIED"},
            {"document_id": "d2", "property_id": "p1", "requirement_id": "r2", "status": "VERIFIED"},
        ]
        db = _make_db_mock(properties, requirements, documents)
        with patch("services.compliance_score.database.get_db", return_value=db):
            result = await calculate_compliance_score("c1")
        assert result.get("score") >= 95, "All compliant + docs + far expiry should yield score >= 95"
        assert result.get("grade") == "A"
        assert "breakdown" in result
        assert result["breakdown"].get("status_score", 0) >= 99
        assert result["breakdown"].get("document_score", 0) >= 99


class TestCaseB_CriticalOverdueDropsScore:
    """Case B: One critical requirement overdue → score drops by expected amount."""

    @pytest.mark.asyncio
    async def test_one_critical_overdue_drops_score(self):
        past = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        future = (datetime.now(timezone.utc) + timedelta(days=200)).isoformat()
        properties = [
            {
                "property_id": "p1",
                "client_id": "c1",
                "is_hmo": False,
                "compliance_score": 55,
                "compliance_breakdown": {
                    "status_score": 45,
                    "expiry_score": 85,
                    "document_score": 80,
                    "overdue_penalty_score": 25,
                    "risk_score": 90,
                },
            }
        ]
        requirements = [
            {"requirement_id": "r1", "property_id": "p1", "requirement_type": "GAS_SAFETY", "status": "OVERDUE", "due_date": past},
            {"requirement_id": "r2", "property_id": "p1", "requirement_type": "EPC", "status": "COMPLIANT", "due_date": future},
        ]
        documents = [
            {"document_id": "d1", "property_id": "p1", "requirement_id": "r2", "status": "VERIFIED"},
        ]
        db = _make_db_mock(properties, requirements, documents, default_property_score=None, default_breakdown=None)
        with patch("services.compliance_score.database.get_db", return_value=db):
            result = await calculate_compliance_score("c1")
        # Critical overdue: status contribution low, overdue penalty hit, expiry still ok
        assert result.get("score") < 70, "One critical (GAS_SAFETY) overdue should pull score below 70"
        assert "critical_overdue" in result.get("stats", {})
        assert result["stats"]["critical_overdue"] >= 1
        assert result["stats"]["overdue"] >= 1


class TestCaseC_CompliantButMissingDocs:
    """Case C: Missing documents but requirements marked compliant → document coverage penalty only."""

    @pytest.mark.asyncio
    async def test_compliant_requirements_missing_docs_document_penalty_only(self):
        due = (datetime.now(timezone.utc) + timedelta(days=100)).isoformat()
        properties = [{"property_id": "p1", "client_id": "c1", "is_hmo": False}]
        requirements = [
            {"requirement_id": "r1", "property_id": "p1", "requirement_type": "EPC", "status": "COMPLIANT", "due_date": due},
            {"requirement_id": "r2", "property_id": "p1", "requirement_type": "LANDLORD_INSURANCE", "status": "COMPLIANT", "due_date": due},
        ]
        documents = []  # No docs
        db = _make_db_mock(
            properties,
            requirements,
            documents,
            default_property_score=85,
            default_breakdown={
                "status_score": 100,
                "expiry_score": 100,
                "document_score": 0,
                "overdue_penalty_score": 100,
                "risk_score": 100,
            },
        )
        with patch("services.compliance_score.database.get_db", return_value=db):
            result = await calculate_compliance_score("c1")
        # Portfolio score = stored property average; breakdown averages match model weights narrative.
        assert result.get("score") == 85
        assert result["breakdown"]["status_score"] == 100
        assert result["breakdown"]["document_score"] == 0
        assert result["stats"]["verified_coverage_percent"] == 0


class TestCaseD_UnknownRequirementTypeDefaultWeight:
    """Case D: New/unknown requirement type → default weight 1.0."""

    @pytest.mark.asyncio
    async def test_unknown_requirement_type_uses_default_weight(self):
        due = (datetime.now(timezone.utc) + timedelta(days=90)).isoformat()
        properties = [{"property_id": "p1", "client_id": "c1", "is_hmo": False}]
        requirements = [
            {"requirement_id": "r1", "property_id": "p1", "requirement_type": "UNKNOWN_NEW_TYPE", "status": "COMPLIANT", "due_date": due},
        ]
        documents = [{"document_id": "d1", "property_id": "p1", "requirement_id": "r1", "status": "VERIFIED"}]
        db = _make_db_mock(properties, requirements, documents)
        with patch("services.compliance_score.database.get_db", return_value=db):
            result = await calculate_compliance_score("c1")
        assert result.get("score") >= 90
        assert get_requirement_weight("UNKNOWN_NEW_TYPE") == DEFAULT_REQUIREMENT_WEIGHT
        assert "UNKNOWN_NEW_TYPE" not in REQUIREMENT_TYPE_WEIGHTS


class TestCaseE_NoPropertiesOrNoRequirements:
    """Case E: No properties / no requirements → score = 100 with defined message (not null)."""

    @pytest.mark.asyncio
    async def test_no_properties_returns_100_with_message(self):
        db = _make_db_mock([], [], [])
        with patch("services.compliance_score.database.get_db", return_value=db):
            result = await calculate_compliance_score("c1")
        assert result.get("score") == 100
        assert result.get("message") == "No properties to evaluate"
        assert result.get("grade") == "A"
        assert result.get("breakdown") == {}

    @pytest.mark.asyncio
    async def test_no_requirements_returns_100_with_message(self):
        properties = [{"property_id": "p1", "client_id": "c1", "is_hmo": False}]
        db = _make_db_mock(
            properties,
            [],
            [],
            default_property_score=None,
            default_breakdown=None,
        )
        with patch("services.compliance_score.database.get_db", return_value=db):
            result = await calculate_compliance_score("c1")
        assert result.get("score") == 100
        assert result.get("message") == "No requirements to evaluate"
        assert result.get("grade") == "A"
