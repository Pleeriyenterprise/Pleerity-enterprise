"""
Unit tests for Compliance Score v1 (evidence-based, no legal verdicts).
- Status factor mapping
- Renormalization when gas not applicable
- Critical missing forces Critical even if score high
- Portfolio weighted average and worst-risk rule
"""
import pytest
from services.compliance_scoring import (
    status_factor,
    compute_property_score,
    portfolio_score_and_risk,
    _applicable_weights,
    _risk_level_from_breakdown,
)


class TestStatusFactorMapping:
    """S(r): Valid 1.0, Expiring soon 0.7, Overdue 0.25, Missing 0.0, Needs review 0.5."""

    def test_valid_over_30_days(self):
        assert status_factor("COMPLIANT", 60, True, False) == 1.0
        assert status_factor("VALID", 31, True, False) == 1.0

    def test_expiring_soon_0_to_30(self):
        assert status_factor("EXPIRING_SOON", 30, True, False) == 0.7
        assert status_factor("COMPLIANT", 15, True, False) == 0.7
        assert status_factor("EXPIRING_SOON", 1, True, False) == 0.7

    def test_overdue(self):
        assert status_factor("OVERDUE", -1, True, False) == 0.25
        assert status_factor("EXPIRED", 0, True, False) == 0.25
        assert status_factor("COMPLIANT", 0, True, False) == 0.25

    def test_missing_evidence(self):
        assert status_factor("PENDING", None, False, False) == 0.0
        assert status_factor("PENDING", 10, False, False) == 0.0
        assert status_factor("MISSING", None, False, False) == 0.0

    def test_needs_review(self):
        assert status_factor("PENDING", 60, True, True) == 0.5
        assert status_factor("COMPLIANT", 90, True, True) == 0.5


class TestRenormalizationWhenGasNotApplicable:
    """Gas excluded when cert_gas_safety != 'YES'; remaining weights renormalize to 100 (catalog-based)."""

    def test_applicable_weights_with_gas(self):
        prop = {"cert_gas_safety": "YES", "licence_required": "NO"}
        w = _applicable_weights(prop)
        assert "GAS_SAFETY_CERT" in w
        assert w["GAS_SAFETY_CERT"] == 30
        assert "EICR_CERT" in w
        assert "EPC_CERT" in w
        assert "PROPERTY_LICENCE" not in w

    def test_applicable_weights_without_gas(self):
        prop = {"cert_gas_safety": "NO", "licence_required": ""}
        w = _applicable_weights(prop)
        assert "GAS_SAFETY_CERT" not in w
        assert "EICR_CERT" in w
        assert "EPC_CERT" in w

    def test_score_computed_only_from_applicable(self):
        # cert_gas_safety=NO => no gas; tenancy_active=True => EICR, EPC, TENANCY_AGREEMENT, HOW_TO_RENT applicable
        prop = {
            "property_id": "p1",
            "cert_gas_safety": "NO",
            "licence_required": "NO",
            "is_hmo": False,
            "tenancy_active": True,
        }
        requirements = [
            {"requirement_id": "r1", "requirement_type": "EICR", "status": "COMPLIANT", "due_date": "2026-12-31T00:00:00Z"},
            {"requirement_id": "r2", "requirement_type": "EPC", "status": "COMPLIANT", "due_date": "2026-12-31T00:00:00Z"},
            {"requirement_id": "r3", "requirement_type": "TENANCY_AGREEMENT", "status": "COMPLIANT", "due_date": "2026-12-31T00:00:00Z"},
            {"requirement_id": "r4", "requirement_type": "HOW_TO_RENT", "status": "COMPLIANT", "due_date": "2026-12-31T00:00:00Z"},
        ]
        # Document-status pipeline expects expiry_date on doc for expiring types; use future date for VALID
        future_expiry = "2026-12-31T00:00:00Z"
        documents = [
            {"requirement_id": "r1", "status": "VERIFIED", "expiry_date": future_expiry},
            {"requirement_id": "r2", "status": "VERIFIED", "expiry_date": future_expiry},
            {"requirement_id": "r3", "status": "VERIFIED"},
            {"requirement_id": "r4", "status": "VERIFIED"},
        ]
        result = compute_property_score(prop, requirements, documents)
        assert result["score_0_100"] == 100
        assert result["risk_level"] == "Low risk"
        keys_in_breakdown = {r["requirement_key"] for r in result["breakdown"]}
        assert "GAS_SAFETY_CERT" not in keys_in_breakdown
        assert "EICR_CERT" in keys_in_breakdown
        assert "EPC_CERT" in keys_in_breakdown


class TestCriticalMissingForcesCritical:
    """Any critical (Gas, EICR, Licence when required) missing => Critical risk even if score high (catalog keys)."""

    def test_critical_missing_forces_critical(self):
        applicable = {"GAS_SAFETY_CERT": 30, "EICR_CERT": 25, "EPC_CERT": 15, "TENANCY_AGREEMENT": 10}
        breakdown = [
            {"requirement_key": "EICR_CERT", "status": "COMPLIANT", "status_factor": 1.0},
            {"requirement_key": "EPC_CERT", "status": "COMPLIANT", "status_factor": 1.0},
            {"requirement_key": "TENANCY_AGREEMENT", "status": "COMPLIANT", "status_factor": 1.0},
            {"requirement_key": "GAS_SAFETY_CERT", "status": "MISSING_EVIDENCE", "status_factor": 0.0},
        ]
        risk = _risk_level_from_breakdown(85, breakdown, applicable)
        assert risk == "Critical risk"

    def test_critical_overdue_forces_high(self):
        applicable = {"GAS_SAFETY_CERT": 30, "EICR_CERT": 25, "EPC_CERT": 15}
        breakdown = [
            {"requirement_key": "GAS_SAFETY_CERT", "status": "EXPIRED", "status_factor": 0.1},
            {"requirement_key": "EICR_CERT", "status": "COMPLIANT", "status_factor": 1.0},
            {"requirement_key": "EPC_CERT", "status": "COMPLIANT", "status_factor": 1.0},
        ]
        risk = _risk_level_from_breakdown(75, breakdown, applicable)
        assert risk == "High risk"

    def test_score_under_40_forces_critical(self):
        applicable = {"EICR_CERT": 25, "EPC_CERT": 15}
        breakdown = [
            {"requirement_key": "EICR_CERT", "status": "EXPIRED", "status_factor": 0.1},
            {"requirement_key": "EPC_CERT", "status": "MISSING_EVIDENCE", "status_factor": 0.0},
        ]
        risk = _risk_level_from_breakdown(35, breakdown, applicable)
        assert risk == "Critical risk"


class TestPortfolioWeightedAverageAndWorstRisk:
    """E(p) = 1 + 0.5*HMO + 0.2*(bedrooms>=4) + 0.2*(occupancy!=single_family); weighted avg; worst risk."""

    def test_portfolio_weighted_average(self):
        properties_with_scores = [
            {"compliance_score": 80, "risk_level": "Low risk", "is_hmo": False, "bedrooms": 2, "occupancy": "single_family"},
            {"compliance_score": 40, "risk_level": "High risk", "is_hmo": True, "bedrooms": 5, "occupancy": "multi_family"},
        ]
        e1 = 1.0
        e2 = 1.0 + 0.5 + 0.2 + 0.2
        expected_score = round((80 * e1 + 40 * e2) / (e1 + e2))
        result = portfolio_score_and_risk(properties_with_scores)
        assert result["portfolio_score"] == expected_score

    def test_portfolio_worst_risk(self):
        properties_with_scores = [
            {"compliance_score": 90, "risk_level": "Low risk"},
            {"compliance_score": 70, "risk_level": "Medium risk"},
            {"compliance_score": 50, "risk_level": "Critical risk"},
        ]
        result = portfolio_score_and_risk(properties_with_scores)
        assert result["portfolio_risk_level"] == "Critical risk"

    def test_portfolio_single_property(self):
        result = portfolio_score_and_risk([
            {"compliance_score": 85, "risk_level": "Low risk", "is_hmo": False},
        ])
        assert result["portfolio_score"] == 85
        assert result["portfolio_risk_level"] == "Low risk"

    def test_portfolio_empty(self):
        result = portfolio_score_and_risk([])
        assert result["portfolio_score"] == 100
        assert result["portfolio_risk_level"] == "Low risk"
