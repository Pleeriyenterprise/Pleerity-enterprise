"""Regression tests for canonical score authority (utils/risk_bands.py)."""
import pytest

from utils.risk_bands import (
    RISK_BAND_HIGH_MIN,
    RISK_BAND_LOW_MIN,
    RISK_BAND_MODERATE_MIN,
    RISK_LABEL_MODERATE,
    score_authority_fields,
    score_to_band_explanation,
    score_to_grade_color_message,
    score_to_risk_level,
)


BOUNDARY_SCORES = [0, 40, 41, 59, 60, 79, 80, 89, 90, 100]

EXPECTED = {
    0: ("F", "red", "High urgency: overdue items detected", "Critical Risk", "Critical risk (0–39): Immediate action required."),
    40: ("D", "amber", "High risk - action required", "High Risk", "High risk (40–59): Action required to reduce exposure."),
    41: ("D", "amber", "High risk - action required", "High Risk", "High risk (40–59): Action required to reduce exposure."),
    59: ("D", "amber", "High risk - action required", "High Risk", "High risk (40–59): Action required to reduce exposure."),
    60: ("C", "amber", f"{RISK_LABEL_MODERATE} - action required", "Moderate Risk", f"{RISK_LABEL_MODERATE} (60–79): Action required to maintain compliance."),
    79: ("C", "amber", f"{RISK_LABEL_MODERATE} - action required", "Moderate Risk", f"{RISK_LABEL_MODERATE} (60–79): Action required to maintain compliance."),
    80: ("B", "green", "Low risk - good standing", "Low Risk", "Low risk (80–100): Good standing."),
    89: ("B", "green", "Low risk - good standing", "Low Risk", "Low risk (80–100): Good standing."),
    90: ("A", "green", "Low risk - good standing", "Low Risk", "Low risk (80–100): Good standing."),
    100: ("A", "green", "Low risk - good standing", "Low Risk", "Low risk (80–100): Good standing."),
}


@pytest.mark.parametrize("score", BOUNDARY_SCORES)
def test_score_to_grade_color_message_boundaries(score):
    grade, color, message = score_to_grade_color_message(score)
    exp_grade, exp_color, exp_message, _, _ = EXPECTED[score]
    assert grade == exp_grade
    assert color == exp_color
    assert message == exp_message


@pytest.mark.parametrize("score", BOUNDARY_SCORES)
def test_score_to_risk_level_boundaries(score):
    assert score_to_risk_level(score) == EXPECTED[score][3]


@pytest.mark.parametrize("score", BOUNDARY_SCORES)
def test_score_to_band_explanation_boundaries(score):
    assert score_to_band_explanation(score) == EXPECTED[score][4]


@pytest.mark.parametrize("score", BOUNDARY_SCORES)
def test_score_authority_fields_bundle(score):
    fields = score_authority_fields(score)
    exp_grade, exp_color, exp_message, exp_risk, exp_band = EXPECTED[score]
    assert fields["grade"] == exp_grade
    assert fields["color"] == exp_color
    assert fields["message"] == exp_message
    assert fields["risk_level"] == exp_risk
    assert fields["band_explanation"] == exp_band


def test_threshold_constants():
    assert RISK_BAND_LOW_MIN == 80
    assert RISK_BAND_MODERATE_MIN == 60
    assert RISK_BAND_HIGH_MIN == 40


def test_moderate_risk_wording_not_medium():
    _, _, message = score_to_grade_color_message(62)
    assert "Moderate risk" in message
    assert "Medium" not in message
    assert RISK_LABEL_MODERATE == "Moderate risk"
