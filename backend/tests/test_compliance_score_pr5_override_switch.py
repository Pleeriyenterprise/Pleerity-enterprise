from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_calculate_score_maps_top_level_override_from_effective_output():
    db = MagicMock()
    db.properties.find.return_value = MagicMock(to_list=AsyncMock(return_value=[]))
    db.clients.find_one = AsyncMock(return_value={})

    override_outputs = {
        "legacy_override_output": {
            "effective_portfolio_risk_state": "High Risk",
            "risk_override_reasons": ["UNRESOLVED_HIGH_RISK_GAP"],
            "critical_property_count": 0,
            "high_risk_gap_count": 1,
            "unknown_or_stale_property_count": 0,
            "attention_required": True,
            "critical_property_escalation": False,
            "suppress_positive_headline": True,
            "base_portfolio_risk_state": "Low Risk",
        },
        "policy_override_output": {
            "effective_portfolio_risk_state": "Critical Risk",
            "risk_override_reasons": ["UNRESOLVED_CRITICAL_MANDATORY_BREACH"],
            "critical_property_count": 0,
            "high_risk_gap_count": 1,
            "unknown_or_stale_property_count": 0,
            "attention_required": True,
            "critical_property_escalation": True,
            "suppress_positive_headline": True,
            "base_portfolio_risk_state": "Low Risk",
        },
        "effective_override_output": {
            "effective_portfolio_risk_state": "Moderate Risk",
            "risk_override_reasons": ["ATTENTION_ONLY_GAP"],
            "critical_property_count": 0,
            "high_risk_gap_count": 0,
            "unknown_or_stale_property_count": 1,
            "attention_required": True,
            "critical_property_escalation": False,
            "suppress_positive_headline": True,
            "base_portfolio_risk_state": "Low Risk",
        },
    }
    with patch("services.compliance_score.database.get_db", return_value=db), patch(
        "services.compliance_score.build_portfolio_override_outputs",
        new=AsyncMock(return_value=override_outputs),
    ):
        from services.compliance_score import calculate_compliance_score

        out = await calculate_compliance_score("c1")

    assert out["risk_level"] == "Moderate Risk"
    assert out["portfolio_risk_level"] == "Moderate Risk"
    assert out["risk_override_reasons"] == ["ATTENTION_ONLY_GAP"]
    assert out["legacy_override_output"]["effective_portfolio_risk_state"] == "High Risk"
    assert out["policy_override_output"]["effective_portfolio_risk_state"] == "Critical Risk"
    assert out["effective_override_output"]["effective_portfolio_risk_state"] == "Moderate Risk"
