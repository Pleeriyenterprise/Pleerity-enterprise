"""Presentation-only requirement_display contract (canonical naming, CTAs from take_action)."""
from __future__ import annotations

from presentation.requirement_display_contract import (
    build_requirement_display,
    compact_display_for_requirement_row,
)


def test_build_display_right_to_rent_canonical_copy():
    row = {
        "requirement_type": "right_to_rent",
        "take_action": {
            "primary": {"label": "Complete declaration", "kind": "guided_evidence_resolution"},
            "secondary": None,
        },
    }
    d = build_requirement_display(row, audience="client")
    assert d["canonical_name"] == "Right to Rent Checks"
    assert d["short_name"] == "Right to Rent"
    assert d["primary_cta_label"] == "Complete declaration"
    assert "compliance" not in d["canonical_name"].lower()


def test_hmo_licence_variants_share_display():
    base_ta = {"primary": {"label": "Primary CTA", "kind": "view_requirement"}, "secondary": None}
    a = build_requirement_display({"requirement_type": "hmo_license", "take_action": base_ta})
    b = build_requirement_display({"requirement_type": "property_licence", "take_action": base_ta})
    c = build_requirement_display({"requirement_type": "selective_license", "take_action": base_ta})
    assert a["canonical_name"] == b["canonical_name"] == c["canonical_name"]
    assert a["canonical_name"] == "HMO / Selective / Additional Licensing"
    assert a["short_name"] == "HMO Licensing"


def test_wales_occupation_contract_display_is_canonical():
    ta = {"primary": {"label": "Record delivery", "kind": "guided_evidence_resolution"}, "secondary": None}
    a = build_requirement_display({"requirement_type": "occupation_contract", "take_action": ta})
    b = build_requirement_display({"requirement_type": "wales_occupation_contract", "take_action": ta})
    assert a["canonical_name"] == "Occupation Contract (Wales)"
    assert b["canonical_name"] == "Occupation Contract (Wales)"
    assert a["short_name"] == b["short_name"] == "Occupation Contract"


def test_scotland_landlord_registration_display_is_consistent():
    d = build_requirement_display(
        {
            "requirement_type": "scotland_landlord_registration",
            "take_action": {"primary": {"label": "Review registration", "kind": "view_requirement"}, "secondary": None},
        }
    )
    assert d["canonical_name"] == "Landlord Registration (Scotland)"
    assert d["short_name"] == "Scottish Landlord Registration"


def test_hmo_fire_description_not_in_title():
    row = {
        "requirement_type": "hmo_fire_risk_evidence",
        "take_action": {"primary": {"label": "Upload", "kind": "upload_document"}, "secondary": None},
    }
    d = build_requirement_display(row, audience="client")
    assert d["canonical_name"] == "HMO Fire Safety Management"
    assert "Log book" not in d["canonical_name"]
    assert "Log book" in d["description"]


def test_compact_display_prefers_requirement_display_short():
    enriched = {
        "requirement_display": {
            "canonical_name": "Right to Rent Checks",
            "short_name": "Right to Rent",
            "description": "",
            "category_label": "Tenancy",
            "primary_cta_label": "X",
            "secondary_cta_label": None,
        }
    }
    assert compact_display_for_requirement_row(enriched, "right_to_rent") == "Right to Rent"


def test_compact_display_falls_back_without_payload():
    assert "Gas" in compact_display_for_requirement_row(None, "gas_safety")
