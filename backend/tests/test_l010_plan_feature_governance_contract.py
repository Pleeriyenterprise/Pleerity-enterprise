"""L-010e: plan feature keys — matrix, metadata, grace sets, literals, notification seed cross-check."""

from __future__ import annotations

from notification_template_seed_definitions import (
    ADMIN_CLIENT_COMMUNICATION_NOTIFICATION_SEED_DEFINITIONS,
    CORE_NOTIFICATION_TEMPLATE_SEED_DEFINITIONS,
)
from plan_feature_governance_audit import (
    PRODUCTION_ENFORCE_FEATURE_KEY_LITERALS,
    PRODUCTION_REQUIRE_FEATURE_KEY_LITERALS,
)
from services.plan_registry import (
    FEATURES_BLOCKED_DURING_GRACE_PERIOD,
    FEATURE_METADATA,
    LIMITED_RECOVERY_FEATURES,
    MINIMUM_PLAN_FOR_FEATURE,
    PlanCode,
    all_feature_matrix_keys,
    plan_registry,
)


def test_feature_metadata_matches_matrix_keys():
    matrix = all_feature_matrix_keys()
    meta = frozenset(FEATURE_METADATA.keys())
    assert meta == matrix, (
        f"FEATURE_METADATA keys must match FEATURE_MATRIX keys; "
        f"only_in_matrix={sorted(matrix - meta)} only_in_meta={sorted(meta - matrix)}"
    )


def test_grace_and_limited_recovery_feature_sets_are_registered():
    matrix = all_feature_matrix_keys()
    bad_grace = sorted(FEATURES_BLOCKED_DURING_GRACE_PERIOD - matrix)
    bad_lim = sorted(LIMITED_RECOVERY_FEATURES - matrix)
    assert not bad_grace, f"FEATURES_BLOCKED_DURING_GRACE_PERIOD has unknown keys: {bad_grace}"
    assert not bad_lim, f"LIMITED_RECOVERY_FEATURES has unknown keys: {bad_lim}"


def test_minimum_plan_for_feature_keys_are_registered():
    matrix = all_feature_matrix_keys()
    bad = sorted(set(MINIMUM_PLAN_FOR_FEATURE.keys()) - matrix)
    assert not bad, f"MINIMUM_PLAN_FOR_FEATURE references unknown keys: {bad}"


def test_production_enforce_and_require_literals_are_registered():
    matrix = all_feature_matrix_keys()
    bad_e = sorted(PRODUCTION_ENFORCE_FEATURE_KEY_LITERALS - matrix)
    bad_r = sorted(PRODUCTION_REQUIRE_FEATURE_KEY_LITERALS - matrix)
    assert not bad_e, f"enforce_feature literals not in FEATURE_MATRIX: {bad_e}"
    assert not bad_r, f"require_feature literals not in FEATURE_MATRIX: {bad_r}"


def test_notification_seed_plan_required_feature_keys_are_registered():
    matrix = all_feature_matrix_keys()
    seen: set[str] = set()
    for row in CORE_NOTIFICATION_TEMPLATE_SEED_DEFINITIONS + ADMIN_CLIENT_COMMUNICATION_NOTIFICATION_SEED_DEFINITIONS:
        pk = row.get("plan_required_feature_key")
        if pk:
            seen.add(str(pk))
    bad = sorted(seen - matrix)
    assert not bad, f"notification seed plan_required_feature_key not in FEATURE_MATRIX: {bad}"


def test_feature_matrix_rows_have_identical_key_sets():
    keys_ref = frozenset(plan_registry.get_features(PlanCode.PLAN_3_PRO).keys())
    for code in (PlanCode.PLAN_1_SOLO, PlanCode.PLAN_2_PORTFOLIO, PlanCode.PLAN_3_PRO):
        k = frozenset(plan_registry.get_features(code).keys())
        assert k == keys_ref, (
            f"FEATURE_MATRIX key drift for {code}: only_in_ref={sorted(keys_ref - k)} "
            f"only_in_plan={sorted(k - keys_ref)}"
        )
