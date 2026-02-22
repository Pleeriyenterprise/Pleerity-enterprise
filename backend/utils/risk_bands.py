"""
Single source of truth for compliance risk bands and labels.
Used by: portfolio compliance-summary, client compliance-score.
Ensures score-based risk level and messaging never conflict across the app.
Do not change Stripe/provisioning/auth; this is display/calculation only.
"""
# Bands: Low >= LOW_MIN, Moderate >= MODERATE_MIN, High >= HIGH_MIN, Critical < HIGH_MIN
RISK_BAND_LOW_MIN = 80
RISK_BAND_MODERATE_MIN = 60
RISK_BAND_HIGH_MIN = 40


def score_to_risk_level(score: int) -> str:
    """Map 0-100 score to risk level label. Used by portfolio and any UI showing risk."""
    if score >= RISK_BAND_LOW_MIN:
        return "Low Risk"
    if score >= RISK_BAND_MODERATE_MIN:
        return "Moderate Risk"
    if score >= RISK_BAND_HIGH_MIN:
        return "High Risk"
    return "Critical Risk"


def score_to_grade_color_message(score: int) -> tuple:
    """Map 0-100 score to (grade, color, message) for client compliance score response."""
    if score >= RISK_BAND_LOW_MIN:
        grade = "A" if score >= 90 else "B"
        return (grade, "green", "Low risk - good standing")
    if score >= RISK_BAND_MODERATE_MIN:
        return ("C", "amber", "Moderate risk - action required")
    if score >= RISK_BAND_HIGH_MIN:
        return ("D", "amber", "High risk - action required")
    return ("F", "red", "Critical risk - immediate action needed")
