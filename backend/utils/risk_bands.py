"""
Single source of truth for compliance score bands and presentation labels.
Used by: portfolio compliance-summary, client compliance-score, property scoring, digests, reports.

Do not duplicate thresholds elsewhere. Frontend must consume API grade/color/message/band_explanation only.
Do not change Stripe/provisioning/auth; this is display/calculation only.
"""
from typing import Any, Dict, Optional

# Bands: Low >= LOW_MIN, Moderate >= MODERATE_MIN, High >= HIGH_MIN, Critical < HIGH_MIN
RISK_BAND_LOW_MIN = 80
RISK_BAND_MODERATE_MIN = 60
RISK_BAND_HIGH_MIN = 40

# Governed risk wording — use "Moderate risk" (not "Medium risk") everywhere.
RISK_LABEL_LOW = "Low risk"
RISK_LABEL_MODERATE = "Moderate risk"
RISK_LABEL_HIGH = "High risk"
RISK_LABEL_CRITICAL = "Critical risk"

RISK_LEVEL_LOW = "Low Risk"
RISK_LEVEL_MODERATE = "Moderate Risk"
RISK_LEVEL_HIGH = "High Risk"
RISK_LEVEL_CRITICAL = "Critical Risk"


def _coerce_score(score: int) -> int:
    try:
        return max(0, min(100, int(round(float(score)))))
    except (TypeError, ValueError):
        return 0


def score_to_risk_level(score: int) -> str:
    """Map 0-100 score to risk level label. Used by portfolio and any UI showing risk."""
    score = _coerce_score(score)
    if score >= RISK_BAND_LOW_MIN:
        return RISK_LEVEL_LOW
    if score >= RISK_BAND_MODERATE_MIN:
        return RISK_LEVEL_MODERATE
    if score >= RISK_BAND_HIGH_MIN:
        return RISK_LEVEL_HIGH
    return RISK_LEVEL_CRITICAL


def score_to_grade_color_message(score: int) -> tuple:
    """Map 0-100 score to (grade, color, message) for client compliance score response."""
    score = _coerce_score(score)
    if score >= RISK_BAND_LOW_MIN:
        grade = "A" if score >= 90 else "B"
        return (grade, "green", f"{RISK_LABEL_LOW} - good standing")
    if score >= RISK_BAND_MODERATE_MIN:
        return ("C", "amber", f"{RISK_LABEL_MODERATE} - action required")
    if score >= RISK_BAND_HIGH_MIN:
        return ("D", "amber", f"{RISK_LABEL_HIGH} - action required")
    return ("F", "red", "High urgency: overdue items detected")


def risk_level_to_grade_color_message(risk_level: str, score: Optional[int] = None) -> tuple:
    """Map backend risk_level string to (grade, color, message).

    When risk_level is Low Risk and score is provided, grade A/B is derived from score (90+ → A).
    """
    if not risk_level or not isinstance(risk_level, str):
        return ("—", "gray", "")
    s = risk_level.strip()
    if s == RISK_LEVEL_LOW:
        if score is not None:
            return score_to_grade_color_message(_coerce_score(score))
        return ("B", "green", f"{RISK_LABEL_LOW} - good standing")
    if s == RISK_LEVEL_MODERATE:
        return ("C", "amber", f"{RISK_LABEL_MODERATE} - action required")
    if s == RISK_LEVEL_HIGH:
        return ("D", "amber", f"{RISK_LABEL_HIGH} - action required")
    if s == RISK_LEVEL_CRITICAL:
        return ("F", "red", "High urgency: overdue items detected")
    return ("—", "gray", s)


def score_to_band_explanation(score: int) -> str:
    """Inline band explanation for display under grade."""
    score = _coerce_score(score)
    if score >= RISK_BAND_LOW_MIN:
        return f"{RISK_LABEL_LOW} (80–100): Good standing."
    if score >= RISK_BAND_MODERATE_MIN:
        return f"{RISK_LABEL_MODERATE} (60–79): Action required to maintain compliance."
    if score >= RISK_BAND_HIGH_MIN:
        return f"{RISK_LABEL_HIGH} (40–59): Action required to reduce exposure."
    return f"{RISK_LABEL_CRITICAL} (0–39): Immediate action required."


def risk_level_to_band_explanation(risk_level: str) -> str:
    """Band explanation from canonical risk_level string."""
    if not risk_level or not isinstance(risk_level, str):
        return ""
    s = risk_level.strip()
    if s == RISK_LEVEL_LOW:
        return f"{RISK_LABEL_LOW} (80–100): Good standing."
    if s == RISK_LEVEL_MODERATE:
        return f"{RISK_LABEL_MODERATE} (60–79): Action required to maintain compliance."
    if s == RISK_LEVEL_HIGH:
        return f"{RISK_LABEL_HIGH} (40–59): Action required to reduce exposure."
    if s == RISK_LEVEL_CRITICAL:
        return f"{RISK_LABEL_CRITICAL} (0–39): Immediate action required."
    return ""


def score_authority_fields(score: int) -> Dict[str, Any]:
    """Canonical presentation bundle for a numeric score."""
    score = _coerce_score(score)
    grade, color, message = score_to_grade_color_message(score)
    return {
        "grade": grade,
        "color": color,
        "message": message,
        "risk_level": score_to_risk_level(score),
        "band_explanation": score_to_band_explanation(score),
    }


def attach_score_authority_fields(payload: Dict[str, Any], score: Optional[int]) -> Dict[str, Any]:
    """Merge score authority presentation fields into an API payload when score is numeric."""
    if score is None:
        return payload
    try:
        fields = score_authority_fields(int(round(float(score))))
    except (TypeError, ValueError):
        return payload
    merged = dict(payload)
    merged.update(fields)
    return merged
