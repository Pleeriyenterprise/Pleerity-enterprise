"""Trust-language governance — drift prevention and authority enforcement."""
import re

import pytest

from services.trust_language_governance import (
    ASSISTANT_TRUST_LANGUAGE_RULES,
    FORBIDDEN_ENGINEERING_TERMS,
    build_score_trend_explanation,
    operational_score_key_reasons,
    validate_customer_copy,
)
from services.scoring_explanation_copy import KB_COMPLIANCE_SCORE_EXPLAINED
from services import assistant_prompt


def test_forbidden_engineering_terms_detected():
    assert validate_customer_copy("The scoring engine uses bucket emphasis")
    assert any(v["category"] == "FORBIDDEN_ENGINEERING_LANGUAGE" for v in validate_customer_copy("status score 80%"))


def test_false_precision_detected():
    assert validate_customer_copy("Your score improved by 15 points")


def test_kb_copy_passes_governance():
    violations = validate_customer_copy(KB_COMPLIANCE_SCORE_EXPLAINED, allow_vague=True)
    assert not violations, violations


def test_operational_key_reasons_no_internal_labels():
    reasons = operational_score_key_reasons(
        {"status_score": 70, "expiry_score": 80, "document_score": 65, "overdue_penalty_score": 90}
    )
    joined = " ".join(reasons).lower()
    assert "status score" not in joined
    assert "document score" not in joined
    assert len(reasons) >= 2


def test_trend_explanation_causal_not_points():
    text = build_score_trend_explanation(
        compare_days=7,
        score_change=5,
        change_summaries=["2 overdue item(s) resolved"],
    )
    assert "points" not in text.lower()
    assert "overdue" in text.lower()
    assert "improved" in text.lower()


def test_assistant_prompt_includes_trust_rules():
    assert "TRUST-LANGUAGE GOVERNANCE" in assistant_prompt.ASSISTANT_SYSTEM_PROMPT
    assert ASSISTANT_TRUST_LANGUAGE_RULES.strip() in assistant_prompt.ASSISTANT_SYSTEM_PROMPT


def test_compliance_trending_module_source_governed():
    from pathlib import Path

    src = Path(__file__).resolve().parents[1] / "services" / "compliance_trending.py"
    text = src.read_text(encoding="utf-8")
    assert "build_score_trend_explanation" in text
    assert not re.search(r"by\s+\{abs\(score_change\)\}\s+points", text)
