"""Controlled vocabulary normalisation and validation for registry drafts."""
from __future__ import annotations

from copy import deepcopy

from services.compliance_registry_admin_service import validate_registry_draft
from services.compliance_registry_controlled_vocab import (
    normalise_action_link_kind,
    normalise_registry_draft_for_storage,
)
from services.requirement_action_links_admin_service import normalize_admin_action_link_item


def test_normalise_category_compliance_to_regulatory():
    doc = {
        "identity": {"category": "compliance", "name": "X"},
        "classification": {"requirement_type": "SYSTEM", "criticality": "LOW", "client_surface_visible": False},
        "jurisdiction": {"display_jurisdictions": []},
        "action_behaviour": {},
        "action_links": [],
    }
    w = normalise_registry_draft_for_storage(doc)
    assert doc["identity"]["category"] == "REGULATORY"
    assert any("category" in x for x in w)


def test_normalise_jurisdiction_england_token():
    doc = {
        "identity": {"category": "SAFETY", "name": "X"},
        "classification": {"requirement_type": "SYSTEM", "criticality": "LOW", "client_surface_visible": False},
        "jurisdiction": {"display_jurisdictions": ["England", "Scotland"]},
        "action_behaviour": {},
        "action_links": [],
    }
    normalise_registry_draft_for_storage(doc)
    assert doc["jurisdiction"]["display_jurisdictions"] == ["ENGLAND", "SCOTLAND"]


def test_validate_rejects_unknown_category():
    doc = {
        "canonical_code": "GAS_SAFETY",
        "scope_key": "DEFAULT",
        "identity": {"category": "NOT_A_REAL_CATEGORY", "name": "Y"},
        "classification": {
            "requirement_type": "SYSTEM",
            "criticality": "LOW",
            "client_surface_visible": False,
        },
        "jurisdiction": {"display_jurisdictions": []},
        "conditions": {"logic": "ALL", "rules": []},
        "action_behaviour": {"primary_action_mode": "hidden"},
        "action_links": [],
        "governance": {"needs_review_fields": []},
    }
    errs = validate_registry_draft(deepcopy(doc))
    assert any("identity.category" in e for e in errs)


def test_normalise_action_link_kind_guidance_to_official():
    k, w = normalise_action_link_kind("guidance")
    assert k == "official"
    assert w


def test_normalize_admin_action_link_rejects_unknown_kind():
    raw = {
        "key": "k1",
        "label": "L",
        "url": "https://example.com",
        "kind": "made_up_kind",
        "jurisdictions": ["ENGLAND"],
        "priority": 10,
    }
    item, err = normalize_admin_action_link_item(raw, generate_key_if_missing=False)
    assert item is None
    assert err and "kind" in err.lower()
