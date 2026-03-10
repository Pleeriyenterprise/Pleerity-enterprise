"""
Tests for the rule-based Contractor Recommendation Engine (pure helper).
"""
import pytest
from services.contractor_recommendation import recommend_contractors
from services.contractor_recommendation_config import DEFAULT_WEIGHTS


class TestContractorRecommendationRanking:
    """Correct ranking for trade + credential + region matches."""

    def test_trade_match_ranks_higher(self):
        wo = {"work_order_id": "wo-1", "category": "plumbing", "recommended_contractor_type": "plumber"}
        property_doc = None
        contractors = [
            {"contractor_id": "c1", "trade_types": ["electrical"], "status": "active", "credentials": [], "vetted": False, "areas_served": []},
            {"contractor_id": "c2", "trade_types": ["plumbing", "heating"], "status": "active", "credentials": [], "vetted": False, "areas_served": []},
        ]
        result = recommend_contractors(wo, property_doc, contractors, performance_map={})
        assert result["total"] == 1
        assert result["contractors"][0]["contractor_id"] == "c2"
        assert any(r.startswith("Matches trade") for r in (result["contractors"][0]["reasons"] or []))

    def test_credential_match_adds_score(self):
        wo = {"work_order_id": "wo-1", "category": "heating", "recommended_contractor_type": "gas_safe"}
        property_doc = None
        contractors = [
            {"contractor_id": "c1", "trade_types": ["heating"], "status": "active", "credentials": ["gas_safe"], "vetted": True, "areas_served": []},
            {"contractor_id": "c2", "trade_types": ["heating"], "status": "active", "credentials": [], "vetted": False, "areas_served": []},
        ]
        result = recommend_contractors(wo, property_doc, contractors, performance_map={})
        assert result["total"] >= 1
        if result["total"] == 2:
            assert result["contractors"][0]["contractor_id"] == "c1"
            assert result["contractors"][0]["score"] > result["contractors"][1]["score"]

    def test_region_match_adds_score(self):
        wo = {"work_order_id": "wo-1", "category": "general", "recommended_contractor_type": "general"}
        property_doc = {"postcode": "G1 2AB", "region": "Glasgow"}
        contractors = [
            {"contractor_id": "c1", "trade_types": ["general"], "status": "active", "credentials": [], "vetted": False, "areas_served": ["G1"], "region": "Glasgow"},
            {"contractor_id": "c2", "trade_types": ["general"], "status": "active", "credentials": [], "vetted": False, "areas_served": ["EH1"], "region": "Edinburgh"},
        ]
        result = recommend_contractors(wo, property_doc, contractors, performance_map={})
        assert result["total"] == 1
        assert result["contractors"][0]["contractor_id"] == "c1"


class TestContractorRecommendationExclusions:
    """Exclusion rules work."""

    def test_suspended_excluded(self):
        wo = {"work_order_id": "wo-1", "category": "general", "recommended_contractor_type": "general"}
        contractors = [
            {"contractor_id": "c1", "trade_types": ["general"], "status": "suspended", "credentials": [], "vetted": False, "areas_served": []},
        ]
        result = recommend_contractors(wo, None, contractors, performance_map={})
        assert result["total"] == 0

    def test_wrong_trade_excluded(self):
        wo = {"work_order_id": "wo-1", "category": "plumbing", "recommended_contractor_type": "plumber"}
        contractors = [
            {"contractor_id": "c1", "trade_types": ["electrical"], "status": "active", "credentials": [], "vetted": False, "areas_served": []},
        ]
        result = recommend_contractors(wo, None, contractors, performance_map={})
        assert result["total"] == 0

    def test_gas_safe_without_credential_excluded(self):
        wo = {"work_order_id": "wo-1", "category": "heating", "recommended_contractor_type": "gas_safe"}
        contractors = [
            {"contractor_id": "c1", "trade_types": ["heating"], "status": "active", "credentials": [], "vetted": False, "areas_served": []},
        ]
        result = recommend_contractors(wo, None, contractors, performance_map={})
        assert result["total"] == 0

    def test_gas_safe_with_credential_included(self):
        wo = {"work_order_id": "wo-1", "category": "heating", "recommended_contractor_type": "gas_safe"}
        contractors = [
            {"contractor_id": "c1", "trade_types": ["heating"], "status": "active", "credentials": ["gas_safe"], "vetted": True, "areas_served": []},
        ]
        result = recommend_contractors(wo, None, contractors, performance_map={})
        assert result["total"] == 1


class TestContractorRecommendationOutput:
    """Output shape: score, rank, recommendation_label, reasons."""

    def test_output_has_required_fields(self):
        wo = {"work_order_id": "wo-1", "category": "general", "recommended_contractor_type": "general"}
        contractors = [
            {"contractor_id": "c1", "trade_types": ["general"], "status": "active", "credentials": [], "vetted": True, "areas_served": []},
        ]
        result = recommend_contractors(wo, None, contractors, performance_map={})
        assert "contractors" in result
        assert "total" in result
        assert "no_strong_match" in result
        assert result["work_order_id"] == "wo-1"
        if result["contractors"]:
            c = result["contractors"][0]
            assert "contractor_id" in c
            assert "score" in c
            assert "rank" in c
            assert "recommendation_label" in c
            assert "reasons" in c
            assert "benchmark_fit" in c

    def test_no_strong_match_when_empty(self):
        wo = {"work_order_id": "wo-1", "category": "plumbing", "recommended_contractor_type": "plumber"}
        contractors = [
            {"contractor_id": "c1", "trade_types": ["electrical"], "status": "active", "credentials": [], "vetted": False, "areas_served": []},
        ]
        result = recommend_contractors(wo, None, contractors, performance_map={})
        assert result["no_strong_match"] is True
        assert result["total"] == 0
