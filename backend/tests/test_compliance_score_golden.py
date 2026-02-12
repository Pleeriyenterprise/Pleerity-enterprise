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


def _make_db_mock(properties: list, requirements: list, documents: list):
    """Build a mock db with find().to_list() returning the given data."""
    db = MagicMock()
    db.properties = MagicMock()
    db.properties.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=properties)))
    db.requirements = MagicMock()
    db.requirements.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=requirements)))
    db.documents = MagicMock()
    db.documents.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=documents)))
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
        properties = [{"property_id": "p1", "client_id": "c1", "is_hmo": False}]
        requirements = [
            {"requirement_id": "r1", "property_id": "p1", "requirement_type": "GAS_SAFETY", "status": "OVERDUE", "due_date": past},
            {"requirement_id": "r2", "property_id": "p1", "requirement_type": "EPC", "status": "COMPLIANT", "due_date": future},
        ]
        documents = [
            {"document_id": "d1", "property_id": "p1", "requirement_id": "r2", "status": "VERIFIED"},
        ]
        db = _make_db_mock(properties, requirements, documents)
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
        db = _make_db_mock(properties, requirements, documents)
        with patch("services.compliance_score.database.get_db", return_value=db):
            result = await calculate_compliance_score("c1")
        # Status score = 100 (all compliant), expiry = 100, doc_score = 0, overdue = 100, risk = 100
        # 0.35*100 + 0.25*100 + 0.15*0 + 0.15*100 + 0.10*100 = 35+25+0+15+10 = 85
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
        db = _make_db_mock(properties, [], [])
        with patch("services.compliance_score.database.get_db", return_value=db):
            result = await calculate_compliance_score("c1")
        assert result.get("score") == 100
        assert result.get("message") == "No requirements to evaluate"
        assert result.get("grade") == "A"
