"""Controlled vocabulary normalisation and validation for registry drafts."""
from __future__ import annotations

from copy import deepcopy

from services.compliance_registry_admin_service import merge_partial_draft, validate_registry_draft
from services.compliance_registry_controlled_vocab import (
    controlled_field_options_payload,
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


def test_merge_partial_draft_applies_action_links_list():
    """Regression: action_links is a list on PATCH; must not be dropped (was gated on isinstance dict)."""
    existing = {
        "canonical_code": "GAS_SAFETY",
        "scope_key": "DEFAULT",
        "identity": {"name": "Gas", "category": "SAFETY"},
        "classification": {"requirement_type": "DOCUMENT", "criticality": "HIGH", "client_surface_visible": True},
        "jurisdiction": {"display_jurisdictions": ["ENGLAND", "WALES", "SCOTLAND", "NORTHERN_IRELAND"]},
        "conditions": {"logic": "ALL", "rules": []},
        "frequency": {"frequency_days": 365, "reminder_lead_days": 30},
        "action_behaviour": {"primary_action_mode": "upload_document"},
        "action_links": [{"key": "old", "label": "Old", "url": "https://a.example", "kind": "official", "jurisdictions": ["ENGLAND"], "priority": 1}],
        "why_it_matters_short": "Statutory gas safety compliance for this property.",
        "governance": {"needs_review_fields": []},
    }
    patch = {
        "action_links": [
            {
                "key": "gov",
                "label": "Gov",
                "url": "https://gov.example/",
                "kind": "official",
                "jurisdictions": ["ENGLAND"],
                "priority": 10,
            }
        ]
    }
    merged = merge_partial_draft(existing, patch)
    assert len(merged["action_links"]) == 1
    assert merged["action_links"][0]["key"] == "gov"


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


def test_controlled_options_include_evidence_resolution_controls():
    payload = controlled_field_options_payload()
    assert "evidence_modes" in payload
    assert "evidence_resolution_workflows" in payload
    assert "client_workflow_classes" in payload
    assert any(x["value"] == "MULTI_EVIDENCE" for x in payload["client_workflow_classes"])
    assert any(x["value"] == "MULTI_EVIDENCE" for x in payload["client_workflow_classes"])
    assert any(x["value"] == "DOCUMENT_UPLOAD" for x in payload["evidence_modes"])
