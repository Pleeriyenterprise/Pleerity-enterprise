"""Unit tests for risk-check scoring (demo only; not legal advice)."""
import pytest
from services.risk_check_scoring import (
    compute_risk_check_result,
    simulated_property_breakdown,
    RISK_CHECK_BAND_LOW_MIN,
    RISK_CHECK_BAND_MODERATE_MIN,
)


def test_score_full_penalty_high_band():
    """Expired gas + expired EICR + HMO + no tracking → low score, HIGH band."""
    r = compute_risk_check_result(
        property_count=2,
        any_hmo=True,
        gas_status="expired",
        eicr_status="expired",
        tracking_method="none",
    )
    assert r["score"] <= 49
    assert r["risk_band"] == "HIGH"
    assert "missed renewals" in (r["exposure_range_label"] or "").lower() or "documentation" in (r["exposure_range_label"] or "").lower()
    assert len(r["flags"]) >= 3


def test_score_valid_all_low_band():
    """Valid gas, valid EICR, no HMO, automated → high score, LOW band."""
    r = compute_risk_check_result(
        property_count=1,
        any_hmo=False,
        gas_status="valid",
        eicr_status="valid",
        tracking_method="automated",
    )
    assert r["score"] == 100
    assert r["risk_band"] == "LOW"
    assert len(r["flags"]) <= 1  # maybe portfolio visibility for multi


def test_score_moderate_band():
    """Mix of issues → score in 50–74, MODERATE."""
    r = compute_risk_check_result(
        property_count=1,
        any_hmo=False,
        gas_status="unknown",
        eicr_status="unknown",
        tracking_method="manual",
    )
    assert 50 <= r["score"] <= 74
    assert r["risk_band"] == "MODERATE"


def test_score_clamped_0_100():
    """Score never goes below 0 or above 100."""
    r = compute_risk_check_result(
        property_count=10,
        any_hmo=True,
        gas_status="expired",
        eicr_status="expired",
        tracking_method="none",
    )
    assert 0 <= r["score"] <= 100


def test_flags_structure():
    """Each flag has title, description, recommended_next_step."""
    r = compute_risk_check_result(
        property_count=1,
        any_hmo=True,
        gas_status="expired",
        eicr_status="valid",
        tracking_method="manual",
    )
    for f in r["flags"]:
        assert "title" in f
        assert "description" in f
        assert "recommended_next_step" in f


def test_simulated_property_breakdown_single():
    """Single property returns one row with same score."""
    rows = simulated_property_breakdown(1, 64, "valid", "expired", "manual")
    assert len(rows) == 1
    assert rows[0]["score"] == 64
    assert "Property 1" in rows[0]["label"]


def test_simulated_property_breakdown_multi():
    """Multiple properties return N rows with scores near base."""
    rows = simulated_property_breakdown(3, 64, "valid", "unknown", "spreadsheet")
    assert len(rows) == 3
    for i, row in enumerate(rows):
        assert f"Property {i + 1}" in row["label"]
        assert 0 <= row["score"] <= 100
