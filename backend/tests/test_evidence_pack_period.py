"""Evidence pack export period parsing and validation."""
import pytest

from services.evidence_pack_service import parse_export_period


def test_parse_period_none():
    assert parse_export_period(None, None) is None
    assert parse_export_period("", "  ") is None


def test_parse_period_requires_both():
    with pytest.raises(ValueError, match="Both period_start"):
        parse_export_period("2024-01-01", None)
    with pytest.raises(ValueError, match="Both period_start"):
        parse_export_period(None, "2024-01-31")


def test_parse_period_order_and_max_span():
    with pytest.raises(ValueError, match="on or after"):
        parse_export_period("2024-02-01", "2024-01-01")
    with pytest.raises(ValueError, match="366"):
        parse_export_period("2023-01-01", "2024-02-01")


def test_parse_period_ok():
    lo, hi_excl = parse_export_period("2024-06-01", "2024-06-30")
    assert lo.isoformat().startswith("2024-06-01")
    assert (hi_excl - lo).days == 30
