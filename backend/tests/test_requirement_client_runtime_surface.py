"""
Runtime surface filter: planner + jurisdiction + visibility gates for client-facing requirement rows.
"""
from __future__ import annotations

from services.compliance_requirement_registry import build_requirement_plan_for_property
from services.provisioning import REQUIREMENT_GENERATION_SOURCE_DB_RULE
from services.requirement_client_runtime_surface import (
    CLIENT_RUNTIME_REQUIREMENT_SURFACE_INVARIANT,
    requirement_row_passes_client_runtime_surface_gates,
)


def _wales_prop(**kwargs):
    base = {
        "property_id": "p-wales",
        "client_id": "c1",
        "jurisdiction": "Wales",
        "property_type": "residential",
        "tenancy_active": True,
        "has_gas_supply": True,
        "deposit_taken": True,
        "furnished": False,
        "is_hmo": False,
    }
    base.update(kwargs)
    return base


def _england_prop(**kwargs):
    base = {
        "property_id": "p-eng",
        "client_id": "c1",
        "jurisdiction": "England",
        "property_type": "residential",
        "tenancy_active": True,
        "has_gas_supply": True,
        "deposit_taken": True,
        "furnished": False,
        "is_hmo": False,
    }
    base.update(kwargs)
    return base


def _scotland_prop(**kwargs):
    base = {
        "property_id": "p-sct",
        "client_id": "c1",
        "jurisdiction": "Scotland",
        "property_type": "residential",
        "tenancy_active": True,
        "has_gas_supply": True,
        "deposit_taken": True,
        "furnished": False,
        "is_hmo": False,
    }
    base.update(kwargs)
    return base


def _client_wales():
    return {"default_jurisdiction": "Wales"}


def _plan_types(prop, client_doc, published=None):
    return {
        str(x.requirement_type or "").strip().lower()
        for x in build_requirement_plan_for_property(prop, client_doc, published_registry_entries=published)
    }


def test_invariant_string_documents_policy():
    assert "planner" in CLIENT_RUNTIME_REQUIREMENT_SURFACE_INVARIANT.lower()
    assert "jurisdiction" in CLIENT_RUNTIME_REQUIREMENT_SURFACE_INVARIANT.lower()
    assert "draft" in CLIENT_RUNTIME_REQUIREMENT_SURFACE_INVARIANT.lower()


def test_wales_property_filters_england_right_to_rent_row():
    prop = _wales_prop()
    client = _client_wales()
    pt = _plan_types(prop, client)
    row = {
        "property_id": prop["property_id"],
        "requirement_id": "r1",
        "requirement_type": "right_to_rent",
        "jurisdiction": "England",
        "applicability": "REQUIRED",
        "status": "PENDING",
        "client_surface_visible": True,
        "requirement_generation_source": "catalog_registry",
    }
    assert "right_to_rent" not in pt
    assert not requirement_row_passes_client_runtime_surface_gates(
        row,
        property_doc=prop,
        client_doc=client,
        plan_types_lower=pt,
        published_registry_entries=None,
    )


def test_wales_property_filters_right_to_rent_even_if_row_jurisdiction_blank():
    prop = _wales_prop()
    client = _client_wales()
    pt = _plan_types(prop, client)
    row = {
        "property_id": prop["property_id"],
        "requirement_id": "r2",
        "requirement_type": "right_to_rent",
        "jurisdiction": "",
        "applicability": "REQUIRED",
        "status": "PENDING",
        "client_surface_visible": True,
        "requirement_generation_source": "catalog_registry",
    }
    assert not requirement_row_passes_client_runtime_surface_gates(
        row,
        property_doc=prop,
        client_doc=client,
        plan_types_lower=pt,
        published_registry_entries=None,
    )


def test_scotland_property_filters_wales_occupation_contract_row():
    prop = _scotland_prop()
    client = {"default_jurisdiction": "Scotland"}
    pt = _plan_types(prop, client)
    row = {
        "property_id": prop["property_id"],
        "requirement_id": "r3",
        "requirement_type": "wales_occupation_contract",
        "jurisdiction": "Wales",
        "applicability": "REQUIRED",
        "status": "PENDING",
        "client_surface_visible": True,
        "requirement_generation_source": "catalog_registry",
    }
    assert "wales_occupation_contract" not in pt
    assert not requirement_row_passes_client_runtime_surface_gates(
        row,
        property_doc=prop,
        client_doc=client,
        plan_types_lower=pt,
        published_registry_entries=None,
    )


def test_england_property_filters_scotland_landlord_registration_row():
    prop = _england_prop()
    client = {"default_jurisdiction": "England"}
    pt = _plan_types(prop, client)
    row = {
        "property_id": prop["property_id"],
        "requirement_id": "r4",
        "requirement_type": "scotland_landlord_registration",
        "jurisdiction": "Scotland",
        "applicability": "REQUIRED",
        "status": "PENDING",
        "client_surface_visible": True,
        "requirement_generation_source": "catalog_registry",
    }
    assert "scotland_landlord_registration" not in pt
    assert not requirement_row_passes_client_runtime_surface_gates(
        row,
        property_doc=prop,
        client_doc=client,
        plan_types_lower=pt,
        published_registry_entries=None,
    )


def test_draft_or_orphan_catalog_row_not_in_planner_excluded():
    prop = _england_prop()
    client = {"default_jurisdiction": "England"}
    pt = _plan_types(prop, client)
    row = {
        "property_id": prop["property_id"],
        "requirement_id": "orphan",
        "requirement_type": "rent_smart_wales",
        "jurisdiction": "England",
        "applicability": "REQUIRED",
        "status": "PENDING",
        "client_surface_visible": True,
        "requirement_generation_source": "catalog_registry",
    }
    assert "rent_smart_wales" not in pt
    assert not requirement_row_passes_client_runtime_surface_gates(
        row,
        property_doc=prop,
        client_doc=client,
        plan_types_lower=pt,
        published_registry_entries=None,
    )


def test_requirement_rules_row_not_subject_to_planner_membership():
    prop = _wales_prop()
    client = _client_wales()
    pt = _plan_types(prop, client)
    row = {
        "property_id": prop["property_id"],
        "requirement_id": "gov",
        "requirement_type": "custom_governed_only_type",
        "jurisdiction": "Wales",
        "applicability": "REQUIRED",
        "status": "PENDING",
        "client_surface_visible": True,
        "requirement_generation_source": REQUIREMENT_GENERATION_SOURCE_DB_RULE,
    }
    assert "custom_governed_only_type" not in pt
    assert requirement_row_passes_client_runtime_surface_gates(
        row,
        property_doc=prop,
        client_doc=client,
        plan_types_lower=pt,
        published_registry_entries=None,
    )


def test_requirement_rules_row_still_rejects_explicit_wrong_jurisdiction():
    prop = _wales_prop()
    client = _client_wales()
    pt = _plan_types(prop, client)
    row = {
        "property_id": prop["property_id"],
        "requirement_id": "gov2",
        "requirement_type": "custom_governed_only_type",
        "jurisdiction": "England",
        "applicability": "REQUIRED",
        "status": "PENDING",
        "client_surface_visible": True,
        "requirement_generation_source": REQUIREMENT_GENERATION_SOURCE_DB_RULE,
    }
    assert not requirement_row_passes_client_runtime_surface_gates(
        row,
        property_doc=prop,
        client_doc=client,
        plan_types_lower=pt,
        published_registry_entries=None,
    )


def test_draft_only_registry_metadata_excluded():
    prop = _england_prop()
    client = {"default_jurisdiction": "England"}
    pt = _plan_types(prop, client)
    base = {
        "property_id": prop["property_id"],
        "requirement_id": "draft-gas",
        "requirement_type": "gas_safety",
        "jurisdiction": "England",
        "applicability": "REQUIRED",
        "status": "PENDING",
        "client_surface_visible": True,
        "requirement_generation_source": "catalog_registry",
        "registry_metadata": {"draft_only_materialization": True},
    }
    assert not requirement_row_passes_client_runtime_surface_gates(
        base,
        property_doc=prop,
        client_doc=client,
        plan_types_lower=pt,
        published_registry_entries=None,
    )


def test_not_required_hidden_archived_surface_gates():
    prop = _england_prop()
    client = {"default_jurisdiction": "England"}
    pt = _plan_types(prop, client)
    gas = next(iter([t for t in pt if t == "gas_safety"]), None)
    assert gas == "gas_safety"

    base = {
        "property_id": prop["property_id"],
        "requirement_id": "g",
        "requirement_type": "gas_safety",
        "jurisdiction": "England",
        "requirement_generation_source": "catalog_registry",
    }

    assert not requirement_row_passes_client_runtime_surface_gates(
        {**base, "applicability": "NOT_REQUIRED", "status": "PENDING", "client_surface_visible": True},
        property_doc=prop,
        client_doc=client,
        plan_types_lower=pt,
        published_registry_entries=None,
    )
    assert not requirement_row_passes_client_runtime_surface_gates(
        {**base, "applicability": "REQUIRED", "status": "NOT_REQUIRED", "client_surface_visible": True},
        property_doc=prop,
        client_doc=client,
        plan_types_lower=pt,
        published_registry_entries=None,
    )
    assert not requirement_row_passes_client_runtime_surface_gates(
        {**base, "applicability": "REQUIRED", "status": "PENDING", "client_surface_visible": False},
        property_doc=prop,
        client_doc=client,
        plan_types_lower=pt,
        published_registry_entries=None,
    )
    assert not requirement_row_passes_client_runtime_surface_gates(
        {
            **base,
            "applicability": "REQUIRED",
            "status": "PENDING",
            "client_surface_visible": True,
            "registry_metadata": {"primary_action_mode": "hidden"},
        },
        property_doc=prop,
        client_doc=client,
        plan_types_lower=pt,
        published_registry_entries=None,
    )
    assert not requirement_row_passes_client_runtime_surface_gates(
        {
            **base,
            "applicability": "REQUIRED",
            "status": "PENDING",
            "client_surface_visible": True,
            "registry_metadata": {"lifecycle": {"status": "archived"}},
        },
        property_doc=prop,
        client_doc=client,
        plan_types_lower=pt,
        published_registry_entries=None,
    )


def test_project_requirement_row_uses_legacy_status_without_authority():
    """Projection must match compliance_score: authority absent → legacy ``status`` (e.g. EXPIRED)."""
    from services.requirement_client_runtime_surface import project_requirement_row_client_runtime

    row = {
        "requirement_id": "r-exp",
        "property_id": "p1",
        "requirement_type": "EPC",
        "status": "EXPIRED",
        "due_date": "2020-01-01T00:00:00+00:00",
    }
    out = project_requirement_row_client_runtime(row)
    assert (out.get("status") or "").upper() == "EXPIRED"


def test_compute_client_portal_requirement_stats_buckets():
    from services.requirement_client_runtime_surface import compute_client_portal_requirement_stats

    rows = [
        {"status": "COMPLIANT"},
        {"status": "VALID"},
        {"status": "PENDING"},
        {"status": "MISSING"},
        {"status": "EXPIRING_SOON"},
        {"status": "OVERDUE"},
        {"status": "EXPIRED"},
    ]
    c = compute_client_portal_requirement_stats(rows)
    assert c["total_requirements"] == 7
    assert c["compliant"] == 2
    assert c["pending"] == 1
    assert c["missing_evidence"] == 2
    assert c["expiring_soon"] == 1
    assert c["overdue"] == 2


def test_client_portal_surface_visible_excludes_hidden_overdue_from_portal_slice():
    from services.requirement_client_runtime_surface import (
        client_portal_surface_visible_row,
        project_requirement_row_client_runtime,
    )

    rows = [
        project_requirement_row_client_runtime(
            {"requirement_id": "a", "property_id": "p1", "status": "OVERDUE", "client_surface_visible": True}
        ),
        project_requirement_row_client_runtime(
            {"requirement_id": "b", "property_id": "p1", "status": "OVERDUE", "client_surface_visible": False}
        ),
    ]
    portal = [r for r in rows if client_portal_surface_visible_row(r)]
    overdue = sum(1 for r in portal if (r.get("status") or "") in ("OVERDUE", "EXPIRED"))
    assert len(portal) == 1
    assert overdue == 1
