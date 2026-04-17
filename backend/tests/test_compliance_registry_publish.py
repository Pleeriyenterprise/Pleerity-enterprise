"""Publish queue helpers and planner merge from published registry snapshot."""
from __future__ import annotations

import pytest

from services.compliance_registry_publish_service import _snapshot_entries_from_drafts
from services.compliance_requirement_registry import build_requirement_plan_for_property


def test_snapshot_rejects_duplicate_canonical_scope():
    docs = [
        {"entry_id": "a", "canonical_code": "GAS_SAFETY", "scope_key": "DEFAULT"},
        {"entry_id": "b", "canonical_code": "GAS_SAFETY", "scope_key": "DEFAULT"},
    ]
    with pytest.raises(ValueError, match="duplicate_publish_key"):
        _snapshot_entries_from_drafts(docs)


def test_build_plan_applies_published_overlay_to_gas_safety():
    prop = {
        "property_id": "p1",
        "client_id": "c1",
        "jurisdiction": "England",
        "property_type": "residential",
        "has_gas_supply": True,
    }
    client = {"default_jurisdiction": "England"}
    pub = {
        "GAS_SAFETY|DEFAULT": {
            "canonical_code": "GAS_SAFETY",
            "scope_key": "DEFAULT",
            "jurisdiction": {"display_jurisdictions": ["England", "Wales", "Scotland", "Northern Ireland"]},
            "identity": {"name": "Published gas label"},
            "classification": {"requirement_type": "DOCUMENT"},
            "frequency": {"frequency_days": 365, "reminder_lead_days": 30},
            "why_it_matters_short": "Short explanation",
            "why_it_matters_long": "Long explanation",
            "why_it_matters_by_jurisdiction": {"SCOTLAND": {"short": "Scotland short"}},
        }
    }
    plan = build_requirement_plan_for_property(prop, client, published_registry_entries=pub)
    g = next((x for x in plan if x.requirement_type == "gas_safety"), None)
    assert g is not None
    assert g.description == "Published gas label"
    assert g.why_it_matters_short == "Short explanation"
    assert g.why_it_matters_long == "Long explanation"
