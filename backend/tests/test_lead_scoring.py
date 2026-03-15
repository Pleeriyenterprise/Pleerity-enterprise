"""
Unit tests for lead scoring (lead_scoring.py).
"""
import pytest
from services.lead_scoring import (
    calculate_lead_score_from_signals,
    stage_from_lead_score,
    should_update_stage,
    HOT_LEAD_SCORE_THRESHOLD,
)
from services.lead_models import LeadSourcePlatform, LeadServiceInterest, LeadIntentScore, LeadStage, LeadStatus


def test_stage_from_lead_score_bands():
    """Stage bands: 0-19 NEW, 20-39 QUALIFIED, 40-59 NURTURING, 60+ SALES_READY."""
    assert stage_from_lead_score(0) == "NEW"
    assert stage_from_lead_score(19) == "NEW"
    assert stage_from_lead_score(20) == "QUALIFIED"
    assert stage_from_lead_score(39) == "QUALIFIED"
    assert stage_from_lead_score(40) == "NURTURING"
    assert stage_from_lead_score(59) == "NURTURING"
    assert stage_from_lead_score(60) == "SALES_READY"
    assert stage_from_lead_score(100) == "SALES_READY"


def test_calculate_score_intent_only():
    """Base score from intent_score only."""
    assert calculate_lead_score_from_signals(intent_score=LeadIntentScore.HIGH.value) >= 40
    assert calculate_lead_score_from_signals(intent_score=LeadIntentScore.MEDIUM.value) >= 25
    assert calculate_lead_score_from_signals(intent_score=LeadIntentScore.LOW.value) >= 10


def test_calculate_score_compliance_risk_check():
    """COMPLIANCE_RISK_CHECK adds +20."""
    base = calculate_lead_score_from_signals(intent_score=LeadIntentScore.LOW.value)
    with_check = calculate_lead_score_from_signals(
        source_platform=LeadSourcePlatform.COMPLIANCE_RISK_CHECK.value,
        intent_score=LeadIntentScore.LOW.value,
    )
    assert with_check >= base + 20


def test_calculate_score_risk_level():
    """HIGH risk adds +30, MODERATE +20."""
    base = calculate_lead_score_from_signals(intent_score=LeadIntentScore.LOW.value)
    high_risk = calculate_lead_score_from_signals(
        intent_score=LeadIntentScore.LOW.value,
        risk_level="HIGH",
    )
    mod_risk = calculate_lead_score_from_signals(
        intent_score=LeadIntentScore.LOW.value,
        risk_level="MODERATE",
    )
    assert high_risk >= base + 30
    assert mod_risk >= base + 20


def test_calculate_score_portfolio_size():
    """Portfolio size 2-5 adds +15, 1 adds +5."""
    base = calculate_lead_score_from_signals(intent_score=LeadIntentScore.LOW.value)
    with_portfolio_2_5 = calculate_lead_score_from_signals(
        intent_score=LeadIntentScore.LOW.value,
        portfolio_size=3,
    )
    with_portfolio_1 = calculate_lead_score_from_signals(
        intent_score=LeadIntentScore.LOW.value,
        portfolio_size=1,
    )
    assert with_portfolio_2_5 >= base + 15
    assert with_portfolio_1 >= base + 5


def test_calculate_score_capped_at_100():
    """Score is capped at 100."""
    score = calculate_lead_score_from_signals(
        intent_score=LeadIntentScore.HIGH.value,
        source_platform=LeadSourcePlatform.COMPLIANCE_RISK_CHECK.value,
        risk_level="HIGH",
        portfolio_size=5,
        service_interest=LeadServiceInterest.AUTOMATION.value,
        tags=["consultation_request", "nurture_cta_clicked"],
    )
    assert 0 <= score <= 100


def test_recalculate_lead_score_signals_integration():
    """Score from signals matches expected range for a typical risk-check lead."""
    score = calculate_lead_score_from_signals(
        source_platform=LeadSourcePlatform.COMPLIANCE_RISK_CHECK.value,
        service_interest=LeadServiceInterest.CVP.value,
        intent_score=LeadIntentScore.MEDIUM.value,
        risk_level="HIGH",
        portfolio_size=2,
        tags=[],
    )
    assert 0 <= score <= 100
    suggested = stage_from_lead_score(score)
    assert suggested in ("NEW", "QUALIFIED", "NURTURING", "SALES_READY")


def test_should_update_stage_never_overwrite_converted():
    """Do not update stage when lead is already WON or CONVERTED."""
    assert should_update_stage({"stage": LeadStage.WON.value, "status": "ACTIVE"}, "QUALIFIED") is False
    assert should_update_stage({"stage": "NEW", "status": LeadStatus.CONVERTED.value}, "QUALIFIED") is False
    assert should_update_stage({"stage": LeadStage.LOST.value, "status": "ACTIVE"}, "QUALIFIED") is False
    assert should_update_stage({"stage": "NEW", "status": "ACTIVE"}, "QUALIFIED") is True


def test_hot_lead_threshold():
    """Hot lead alert threshold is 80."""
    assert HOT_LEAD_SCORE_THRESHOLD == 80


def test_negative_signal_unsubscribe():
    """Marketing unsubscribe reduces score."""
    base = calculate_lead_score_from_signals(intent_score=LeadIntentScore.LOW.value)
    with_opt_out = calculate_lead_score_from_signals(
        intent_score=LeadIntentScore.LOW.value,
        followup_status="OPTED_OUT",
    )
    assert with_opt_out <= base - 10
