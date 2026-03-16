"""
Unit tests for the Explanation Engine (explainability layer).
"""
import pytest
from services.explanation_engine import (
    explain_risk_signal,
    explain_compliance_alert,
    explain_contractor_score,
    explain_compliance_score,
)


class TestExplainRiskSignal:
    """Risk signal explanations include why_it_matters and recommended_action_text."""

    def test_output_shape(self):
        out = explain_risk_signal({"risk_type": "Boiler Failure Risk"})
        assert "explanation_text" in out
        assert "why_it_matters" in out
        assert "recommended_action_text" in out

    def test_boiler_failure_includes_context(self):
        out = explain_risk_signal({
            "risk_type": "Boiler Failure Risk",
            "reasons": ["Boiler is 14 years old", "Two issues in last 12 months"],
        })
        assert "12 years" in out["why_it_matters"] or "Boiler" in out["why_it_matters"]
        assert "14 years" in out["why_it_matters"] or "Two issues" in out["why_it_matters"]

    def test_uses_signal_recommended_action_when_present(self):
        out = explain_risk_signal({
            "risk_type": "Boiler Failure Risk",
            "recommended_action": "Schedule an inspection to reduce the risk of emergency repair.",
        })
        assert "Schedule an inspection" in out["recommended_action_text"]

    def test_fallback_recommended_action(self):
        out = explain_risk_signal({"risk_type": "Unknown Type"})
        assert out["recommended_action_text"]
        assert "Review" in out["recommended_action_text"] or "suggested" in out["recommended_action_text"].lower()

    def test_damp_risk_has_context(self):
        out = explain_risk_signal({"risk_type": "Damp / Moisture Risk"})
        assert "damp" in out["why_it_matters"].lower() or "moisture" in out["why_it_matters"].lower()

    def test_certificate_expiry_soon(self):
        out = explain_risk_signal({"risk_type": "Certificate Expiry Soon", "reasons": ["Gas cert in 21 days"]})
        assert "expir" in out["why_it_matters"].lower() or "certificate" in out["why_it_matters"].lower()


class TestExplainComplianceAlert:
    """Compliance alert explanations include legal context and recommended action."""

    def test_output_shape(self):
        out = explain_compliance_alert({"requirement_code": "gas_safety", "status": "EXPIRING_SOON"})
        assert "explanation_text" in out
        assert "why_it_matters" in out
        assert "recommended_action_text" in out

    def test_gas_safety_expiring_soon(self):
        out = explain_compliance_alert({"requirement_code": "gas_safety", "status": "EXPIRING_SOON"})
        assert "Gas Safe" in out["why_it_matters"] or "annual" in out["why_it_matters"].lower()
        assert "Gas Safe" in out["recommended_action_text"] or "inspection" in out["recommended_action_text"].lower()

    def test_eicr_overdue(self):
        out = explain_compliance_alert({"requirement_code": "eicr", "status": "OVERDUE"})
        assert "EICR" in out["why_it_matters"] or "Electrical" in out["why_it_matters"]
        assert "Upload" in out["recommended_action_text"] or "evidence" in out["recommended_action_text"].lower()

    def test_generic_requirement_has_fallback(self):
        out = explain_compliance_alert({"requirement_code": "other_thing", "status": "PENDING"})
        assert out["why_it_matters"]
        assert out["recommended_action_text"]


class TestExplainContractorScore:
    """Contractor score explanations describe calculation and usage guidance."""

    def test_output_shape(self):
        out = explain_contractor_score({"reliability_score": 0.72})
        assert "explanation_text" in out
        assert "why_it_matters" in out
        assert "recommended_action_text" in out

    def test_no_score_yet(self):
        out = explain_contractor_score({"contractor_id": "c1", "name": "Acme"})
        assert "does not have a score" in out["explanation_text"] or "score" in out["explanation_text"].lower()
        assert "Assign" in out["recommended_action_text"]

    def test_high_score_usage_guidance(self):
        out = explain_contractor_score({"reliability_score": 0.9, "performance_score": 88})
        assert "85" in out["recommended_action_text"] or "urgent" in out["recommended_action_text"].lower() or "Well suited" in out["recommended_action_text"]

    def test_low_score_usage_guidance(self):
        out = explain_contractor_score({"reliability_score": 0.4})
        assert "reassign" in out["recommended_action_text"].lower() or "higher" in out["recommended_action_text"].lower()


class TestExplainComplianceScore:
    """Portfolio compliance score explanation."""

    def test_output_shape(self):
        out = explain_compliance_score("client-1")
        assert "explanation_text" in out
        assert "why_it_matters" in out
        assert "recommended_action_text" in out

    def test_no_score_data_returns_generic(self):
        out = explain_compliance_score("client-1", None)
        assert "score" in out["explanation_text"].lower() or "portfolio" in out["explanation_text"].lower()

    def test_with_score_data(self):
        out = explain_compliance_score("client-1", {"score": 78, "breakdown": {}})
        assert "78" in out["explanation_text"]
        assert "overdue" in out["why_it_matters"].lower() or "expiring" in out["why_it_matters"].lower()
