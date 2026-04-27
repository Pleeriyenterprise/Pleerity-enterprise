"""Domestic alarm evidence unified under SMOKE_HEAT_ALARMS; FIRE_DETECTION not client-eligible."""
from __future__ import annotations

import copy

from services.compliance_registry_admin_service import (
    default_draft_shell,
    merge_partial_draft,
    plan_types_for_draft_canonical,
    validate_registry_draft,
)
from services.compliance_requirement_registry import (
    published_registry_entry_eligible_for_runtime,
    resolve_published_entry_for_requirement,
)
from services.published_registry_coverage_patch_specs import (
    SMOKE_HEAT_ALARMS_UNIFIED_CLIENT_PATCH,
    _RUNTIME_SANITY_PATCH,
    merge_coverage_into_published_entries,
)


def _smoke_published_row() -> dict:
    shell = default_draft_shell(canonical_code="SMOKE_HEAT_ALARMS", scope_key="DEFAULT")
    shell.pop("entry_id", None)
    shell.pop("status", None)
    m = merge_partial_draft(shell, _RUNTIME_SANITY_PATCH)
    return merge_partial_draft(m, SMOKE_HEAT_ALARMS_UNIFIED_CLIENT_PATCH)


def _fire_detection_row() -> dict:
    return {
        "canonical_code": "FIRE_DETECTION",
        "scope_key": "DEFAULT",
        "jurisdiction": {"display_jurisdictions": ["ENGLAND"]},
        "identity": {"name": "Legacy", "category": "FIRE"},
        "classification": {"requirement_type": "DOCUMENT", "client_surface_visible": True},
        "conditions": {"logic": "ALL", "rules": []},
        "action_behaviour": {"primary_action_mode": "upload_document"},
        "why_it_matters_short": "x" * 50,
    }


def test_plan_types_fire_detection_has_no_planner_slugs():
    assert plan_types_for_draft_canonical("FIRE_DETECTION") == frozenset()


def test_plan_types_smoke_heat_maps_all_alarm_slugs():
    st = plan_types_for_draft_canonical("SMOKE_HEAT_ALARMS")
    for slug in ("smoke_alarms", "co_alarms", "smoke_heat_alarms", "fire_alarm", "fire_detection"):
        assert slug in st


def test_published_fire_detection_entry_not_runtime_eligible():
    assert not published_registry_entry_eligible_for_runtime(_fire_detection_row())


def test_all_alarm_slugs_resolve_to_smoke_heat_when_only_that_row_published():
    sh = _smoke_published_row()
    assert validate_registry_draft(copy.deepcopy(sh)) == []
    pub = {"SMOKE_HEAT_ALARMS|DEFAULT": sh}
    prop = {"jurisdiction": "England", "tenancy_active": True}
    for rt in ("fire_alarm", "fire_detection", "smoke_alarms", "co_alarms", "smoke_heat_alarms"):
        pe = resolve_published_entry_for_requirement(
            published_registry_entries=pub,
            requirement_type=rt,
            portfolio_label="England",
            property_doc=prop,
            enforce_conditions=True,
        )
        assert pe is not None
        assert str(pe.get("canonical_code")).upper() == "SMOKE_HEAT_ALARMS"


def test_fire_detection_snapshot_row_does_not_win_over_smoke_for_fire_alarm_slug():
    sh = _smoke_published_row()
    fd = _fire_detection_row()
    pub = {"SMOKE_HEAT_ALARMS|DEFAULT": sh, "FIRE_DETECTION|DEFAULT": fd}
    pe = resolve_published_entry_for_requirement(
        published_registry_entries=pub,
        requirement_type="fire_alarm",
        portfolio_label="England",
        property_doc={"jurisdiction": "England"},
        enforce_conditions=True,
    )
    assert pe is not None
    assert str(pe.get("canonical_code")).upper() == "SMOKE_HEAT_ALARMS"


def test_hmo_fire_and_fra_remain_distinct_from_smoke_aliases():
    merged, _ = merge_coverage_into_published_entries({})
    merged["SMOKE_HEAT_ALARMS|DEFAULT"] = _smoke_published_row()
    for k, ent in merged.items():
        assert validate_registry_draft(copy.deepcopy(ent)) == [], k
    hmo = resolve_published_entry_for_requirement(
        published_registry_entries=merged,
        requirement_type="hmo_fire_risk",
        portfolio_label="England",
        property_doc={"jurisdiction": "England", "is_hmo": True},
        enforce_conditions=True,
    )
    assert hmo and str(hmo.get("canonical_code")).upper() == "HMO_FIRE_RISK"
    fra = resolve_published_entry_for_requirement(
        published_registry_entries=merged,
        requirement_type="fire_risk_assessment",
        portfolio_label="England",
        property_doc={"jurisdiction": "England", "is_hmo": True},
        enforce_conditions=True,
    )
    assert fra and str(fra.get("canonical_code")).upper() == "FIRE_RISK_ASSESSMENT"
