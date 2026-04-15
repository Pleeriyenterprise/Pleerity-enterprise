"""Governed rule applicability predicates (no Mongo)."""
from datetime import datetime, timezone

from services.compliance_governed_rules_service import property_matches_governed_applicability
from services.compliance_rules_registry import (
    db_requirement_rule_applies_to_property,
    governed_requirement_rule_covers_property,
    governed_requirement_rule_effective_for_runtime,
)


def test_governed_applicability_wildcard():
    assert property_matches_governed_applicability({"is_hmo": True}, None) is True
    assert property_matches_governed_applicability({"is_hmo": True}, {}) is True


def test_governed_applicability_is_hmo():
    assert property_matches_governed_applicability({"is_hmo": True}, {"is_hmo": True}) is True
    assert property_matches_governed_applicability({"is_hmo": True}, {"is_hmo": False}) is False


def test_governed_applicability_local_authority():
    prop = {"local_authority": "london"}
    assert property_matches_governed_applicability(prop, {"local_authority_in": ["LONDON"]}) is True
    assert property_matches_governed_applicability(prop, {"local_authority_in": ["MANCHESTER"]}) is False


def test_db_rule_applies_includes_governed_predicate():
    rule = {
        "jurisdictions": None,
        "governed_applicability": {"is_hmo": True},
    }
    prop = {"property_type": "house", "is_hmo": True}
    assert db_requirement_rule_applies_to_property(rule, prop, "England", "ENGLAND_WALES") is True
    prop2 = {"property_type": "house", "is_hmo": False}
    assert db_requirement_rule_applies_to_property(rule, prop2, "England", "ENGLAND_WALES") is False


def test_governed_effective_window_active():
    now = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
    rule = {
        "governed": True,
        "is_active": True,
        "governed_effective_from": "2026-01-01T00:00:00+00:00",
        "governed_effective_to": "2026-12-31T23:59:59+00:00",
    }
    assert governed_requirement_rule_effective_for_runtime(rule, now=now) is True


def test_governed_effective_before_start():
    now = datetime(2025, 6, 1, tzinfo=timezone.utc)
    rule = {"governed": True, "is_active": True, "governed_effective_from": "2026-01-01T00:00:00Z"}
    assert governed_requirement_rule_effective_for_runtime(rule, now=now) is False


def test_governed_inactive_row():
    rule = {"governed": True, "is_active": False}
    assert governed_requirement_rule_effective_for_runtime(rule) is False


def test_governed_deprecated_row():
    rule = {"governed": True, "is_active": True, "governed_deprecated": True}
    assert governed_requirement_rule_effective_for_runtime(rule) is False


def test_governed_covers_respects_effective_window():
    now = datetime(2025, 6, 1, tzinfo=timezone.utc)
    rule = {
        "governed": True,
        "is_active": True,
        "governed_effective_from": "2026-01-01T00:00:00Z",
        "jurisdictions": None,
        "applicable_to": "ALL",
    }
    prop = {"property_type": "house", "is_hmo": False, "jurisdiction": "England"}
    assert governed_requirement_rule_covers_property(rule, "HOUSE", prop, {}, now=now) is False
