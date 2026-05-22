"""Bounded runtime-surface legitimacy for condition_standard_pilot_ops rows."""
from __future__ import annotations

from services.condition_standard_pilot_materialisation import (
    CONDITION_STANDARD_WORKFLOW_FAMILY,
    MATERIALISATION_PROVENANCE_SOURCE,
    REQUIREMENT_GENERATION_SOURCE_CONDITION_STANDARD_PILOT,
    evaluate_condition_standard_pilot_runtime_legitimacy,
)
from services.provisioning import REQUIREMENT_GENERATION_SOURCE_DB_RULE
from services.requirement_client_runtime_surface import (
    requirement_row_passes_client_runtime_surface_gates,
)

SCOTLAND_CLIENT = "ec0b091b-105d-4b78-9711-7ab143999cef"
SCOTLAND_PROPERTY = "def23b30-efa5-41f9-a9cc-7fb69f9e9024"


def _scotland_prop(**kwargs):
    base = {
        "property_id": SCOTLAND_PROPERTY,
        "client_id": SCOTLAND_CLIENT,
        "jurisdiction": "Scotland",
        "property_type": "residential",
        "tenancy_active": True,
    }
    base.update(kwargs)
    return base


def _pilot_row(**kwargs):
    base = {
        "requirement_id": "rid-pilot-rs",
        "client_id": SCOTLAND_CLIENT,
        "property_id": SCOTLAND_PROPERTY,
        "requirement_type": "repairing_standard",
        "requirement_code": "repairing_standard",
        "requirement_generation_source": REQUIREMENT_GENERATION_SOURCE_CONDITION_STANDARD_PILOT,
        "workflow_family": CONDITION_STANDARD_WORKFLOW_FAMILY,
        "ops_verification_family": CONDITION_STANDARD_WORKFLOW_FAMILY,
        "client_surface_visible": True,
        "registry_metadata": {
            "materialisation_provenance": {
                "source": MATERIALISATION_PROVENANCE_SOURCE,
                "pilot_target": {
                    "client_id": SCOTLAND_CLIENT,
                    "property_id": SCOTLAND_PROPERTY,
                    "requirement_type": "repairing_standard",
                },
            },
        },
    }
    base.update(kwargs)
    return base


def test_pilot_repairing_standard_passes_without_planner_membership():
    prop = _scotland_prop()
    row = _pilot_row()
    assert requirement_row_passes_client_runtime_surface_gates(
        row,
        property_doc=prop,
        client_doc={"default_jurisdiction": "Scotland"},
        plan_types_lower=set(),
        published_registry_entries=None,
    )


def test_pilot_row_rejected_when_not_allowlisted_target():
    prop = _scotland_prop()
    row = _pilot_row(client_id="other-client", property_id="other-property")
    assert not requirement_row_passes_client_runtime_surface_gates(
        row,
        property_doc=prop,
        client_doc={},
        plan_types_lower=set(),
        published_registry_entries=None,
    )


def test_pilot_row_rejected_when_client_surface_hidden():
    prop = _scotland_prop()
    row = _pilot_row(client_surface_visible=False)
    assert not requirement_row_passes_client_runtime_surface_gates(
        row,
        property_doc=prop,
        client_doc={},
        plan_types_lower=set(),
        published_registry_entries=None,
    )


def test_pilot_row_rejected_without_materialisation_provenance():
    prop = _scotland_prop()
    row = _pilot_row(registry_metadata={})
    assert not requirement_row_passes_client_runtime_surface_gates(
        row,
        property_doc=prop,
        client_doc={},
        plan_types_lower=set(),
        published_registry_entries=None,
    )


def test_pilot_row_rejected_wrong_workflow_family():
    prop = _scotland_prop()
    row = _pilot_row(workflow_family="OTHER_FAMILY")
    assert not requirement_row_passes_client_runtime_surface_gates(
        row,
        property_doc=prop,
        client_doc={},
        plan_types_lower=set(),
        published_registry_entries=None,
    )


def test_db_rule_row_does_not_use_pilot_planner_bypass():
    """DB-rule rows skip planner by design; they must not inherit pilot legitimacy."""
    prop = _scotland_prop()
    row = _pilot_row(requirement_generation_source=REQUIREMENT_GENERATION_SOURCE_DB_RULE)
    _ok, reason = evaluate_condition_standard_pilot_runtime_legitimacy(row, property_doc=prop, client_doc={})
    assert not _ok
    assert "generation_source" in reason


def test_registry_row_still_requires_planner_membership():
    prop = _scotland_prop(property_id="p-other", client_id="c-other")
    row = {
        "requirement_type": "repairing_standard",
        "requirement_generation_source": "registry",
        "client_surface_visible": True,
        "property_id": "p-other",
        "client_id": "c-other",
    }
    assert not requirement_row_passes_client_runtime_surface_gates(
        row,
        property_doc=prop,
        client_doc={},
        plan_types_lower=set(),
        published_registry_entries=None,
    )
