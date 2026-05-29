"""Trust-safe scoring explanation copy (PDF/KB/email/timeline)."""
from services.scoring_explanation_copy import (
    email_score_delta_line,
    score_change_narrative,
    KB_COMPLIANCE_SCORE_EXPLAINED,
    ASSISTANT_HOW_SCORING_WORKS,
)
from services.trust_language_governance import (
    FORBIDDEN_ENGINEERING_TERMS,
    validate_customer_copy,
)


def test_score_change_narrative_directional_not_points():
    assert "point" not in score_change_narrative(5).lower()
    assert "point" not in score_change_narrative(-3).lower()
    assert "improved" in score_change_narrative(5).lower()
    assert "decreased" in score_change_narrative(-3).lower()


def test_email_score_delta_line_directional():
    assert "point" not in email_score_delta_line(4).lower()
    assert "improved" in email_score_delta_line(4).lower()


def test_kb_and_assistant_copy_no_engineering_leaks():
    for blob in (KB_COMPLIANCE_SCORE_EXPLAINED, ASSISTANT_HOW_SCORING_WORKS):
        violations = validate_customer_copy(blob, allow_vague=True)
        assert not violations, violations
