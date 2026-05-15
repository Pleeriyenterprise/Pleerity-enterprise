"""Unit tests for intake plan recommendation (risk lead → intake prefill)."""

import pytest

from services.intake_plan_recommendation import (
    build_intake_plan_recommendation_from_risk_lead,
    parse_risk_lead_property_count,
    recommend_plan_from_property_count_only,
)


@pytest.mark.parametrize(
    "raw,expected",
    [
        (None, None),
        ("", None),
        ("x", None),
        (0, None),
        (101, None),
        (1, 1),
        ("2", 2),
        (3, 3),
        ("10.0", 10),
        (11, 11),
        (100, 100),
    ],
)
def test_parse_risk_lead_property_count(raw, expected):
    assert parse_risk_lead_property_count(raw) == expected


@pytest.mark.parametrize(
    "n,code",
    [
        (1, "PLAN_1_SOLO"),
        (2, "PLAN_1_SOLO"),
        (3, "PLAN_2_PORTFOLIO"),
        (10, "PLAN_2_PORTFOLIO"),
        (11, "PLAN_3_PRO"),
        (25, "PLAN_3_PRO"),
        (99, "PLAN_3_PRO"),
    ],
)
def test_recommend_plan_from_property_count_only(n, code):
    assert recommend_plan_from_property_count_only(n) == code


def test_build_from_risk_lead_missing_count():
    out = build_intake_plan_recommendation_from_risk_lead({"property_count": None})
    assert out["recommended_plan_code"] is None
    assert out["recommendation_basis"] is None


def test_build_from_risk_lead_valid():
    out = build_intake_plan_recommendation_from_risk_lead({"property_count": 5})
    assert out["recommended_plan_code"] == "PLAN_2_PORTFOLIO"
    assert out["recommendation_basis"] == "property_count"
    assert out["recommendation_property_count"] == 5
