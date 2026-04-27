from __future__ import annotations

import copy

from services.compliance_registry_admin_service import (
    default_draft_shell,
    merge_partial_draft,
    plan_types_for_draft_canonical,
    validate_registry_draft,
)
from services.compliance_requirement_registry import resolve_published_entry_for_requirement
from services.published_registry_coverage_patch_specs import merge_coverage_into_published_entries
from services.registry_overlap_correction import (
    OVERLAP_SNAPSHOT_KEYS_TO_REMOVE,
    apply_registry_overlap_correction,
)


def test_overlap_correction_removes_known_duplicate_keys():
    sample = {
        "TENANCY_DEPOSIT_PROTECTION|DEFAULT": {"canonical_code": "TENANCY_DEPOSIT_PROTECTION"},
        "RIGHT_TO_RENT_CHECKS|ENGLAND": {"canonical_code": "RIGHT_TO_RENT_CHECKS"},
        "FIRE_DETECTION|DEFAULT": {"canonical_code": "FIRE_DETECTION"},
        "GAS_SAFETY|DEFAULT": {"canonical_code": "GAS_SAFETY"},
    }
    out, log = apply_registry_overlap_correction(sample)
    assert "GAS_SAFETY|DEFAULT" in out
    assert "TENANCY_DEPOSIT_PROTECTION|DEFAULT" not in out
    assert "FIRE_DETECTION|DEFAULT" not in out
    assert "RIGHT_TO_RENT_CHECKS|ENGLAND" not in out
    assert {x["registry_key"] for x in log} <= set(OVERLAP_SNAPSHOT_KEYS_TO_REMOVE)


def test_plan_types_fire_detection_has_no_slugs_smoke_heat_unifies_alarm_evidence():
    assert not plan_types_for_draft_canonical("FIRE_DETECTION")
    st = plan_types_for_draft_canonical("SMOKE_HEAT_ALARMS")
    for slug in ("smoke_alarms", "co_alarms", "smoke_heat_alarms", "fire_alarm", "fire_detection"):
        assert slug in st


def test_right_to_rent_checks_canonical_has_no_extra_slugs():
    assert not plan_types_for_draft_canonical("RIGHT_TO_RENT_CHECKS")


def _smoke_heat_shell() -> dict:
    d = default_draft_shell(canonical_code="SMOKE_HEAT_ALARMS", scope_key="DEFAULT")
    d.pop("entry_id", None)
    d.pop("status", None)
    return merge_partial_draft(
        d,
        {
            "jurisdiction": {"display_jurisdictions": ["ENGLAND", "WALES", "SCOTLAND", "NORTHERN_IRELAND"]},
            "why_it_matters_short": "Evidence that dwelling smoke, heat, and CO alarms meet applicable standards.",
        },
    )


def test_fire_alarm_and_smoke_alarm_resolve_to_smoke_heat_when_unified_row_present():
    merged, _ = merge_coverage_into_published_entries({})
    merged["SMOKE_HEAT_ALARMS|DEFAULT"] = _smoke_heat_shell()
    for k, ent in merged.items():
        assert validate_registry_draft(copy.deepcopy(ent)) == [], k

    fire = resolve_published_entry_for_requirement(
        published_registry_entries=merged,
        requirement_type="fire_alarm",
        portfolio_label="England",
        property_doc={"jurisdiction": "England"},
        enforce_conditions=True,
    )
    smoke = resolve_published_entry_for_requirement(
        published_registry_entries=merged,
        requirement_type="smoke_alarms",
        portfolio_label="England",
        property_doc={"jurisdiction": "England"},
        enforce_conditions=True,
    )
    assert fire and str(fire.get("canonical_code")).upper() == "SMOKE_HEAT_ALARMS"
    assert smoke and str(smoke.get("canonical_code")).upper() == "SMOKE_HEAT_ALARMS"
