"""
Governance: operational-outcome family map must stay aligned with scheduler registry + JOB_RUNNERS.

New production job ids must update ``REGISTRY_JOB_OUTCOME_FAMILY`` (and usually ``INTENTIONAL_PLATFORM_OTHER_JOB_IDS``
if they remain in platform_other) or CI fails — prevents silent drift into platform_other.
"""
from services.control_centre_outcome_aggregation import (
    INTENTIONAL_PLATFORM_OTHER_JOB_IDS,
    OUTCOME_FAMILY_GOVERNANCE,
    OUTCOME_FAMILY_ORDER,
    REGISTRY_JOB_OUTCOME_FAMILY,
    outcome_family_for_job_name,
)
from services.job_schedule_registry import get_registry_by_id
from job_runner import JOB_RUNNERS


def _valid_family_keys() -> set:
    return {t[0] for t in OUTCOME_FAMILY_ORDER}


def test_registry_and_runners_exactly_match_explicit_family_map():
    required = set(get_registry_by_id()) | set(JOB_RUNNERS.keys())
    explicit = set(REGISTRY_JOB_OUTCOME_FAMILY.keys())
    assert explicit == required, (
        f"REGISTRY_JOB_OUTCOME_FAMILY keys must equal registry ∪ JOB_RUNNERS.\n"
        f"Missing from map: {sorted(required - explicit)}\n"
        f"Stale extra keys in map: {sorted(explicit - required)}"
    )


def test_every_explicit_family_value_is_valid():
    valid = _valid_family_keys()
    bad = {k: v for k, v in REGISTRY_JOB_OUTCOME_FAMILY.items() if v not in valid}
    assert not bad, f"Invalid family keys: {bad}"


def test_platform_other_only_for_intentional_allowlist():
    po_jobs = {jid for jid, fam in REGISTRY_JOB_OUTCOME_FAMILY.items() if fam == "platform_other"}
    assert po_jobs == set(INTENTIONAL_PLATFORM_OTHER_JOB_IDS), (
        f"platform_other jobs must match INTENTIONAL_PLATFORM_OTHER_JOB_IDS exactly.\n"
        f"dict: {sorted(po_jobs)}\nallowlist: {sorted(INTENTIONAL_PLATFORM_OTHER_JOB_IDS)}"
    )


def test_new_production_job_cannot_silently_use_platform_other_outside_allowlist():
    """If someone maps a canonical id to platform_other without updating the allowlist, fail."""
    for jid, fam in REGISTRY_JOB_OUTCOME_FAMILY.items():
        if fam == "platform_other":
            assert jid in INTENTIONAL_PLATFORM_OTHER_JOB_IDS, (
                f"{jid} is platform_other but not in INTENTIONAL_PLATFORM_OTHER_JOB_IDS — "
                "add rationale and allowlist entry, or assign a concrete family."
            )


def test_unknown_runtime_job_name_falls_back_without_crash():
    assert outcome_family_for_job_name("definitely_not_a_production_job_xyz") == "platform_other"
    assert outcome_family_for_job_name("") == "platform_other"
    assert outcome_family_for_job_name("  subscription_lifecycle  ") == "billing_and_subscription_jobs"


def test_family_map_stable_ordering_for_review():
    """Non-functional guard: explicit map stays alphabetically sorted (easier diff review)."""
    keys = list(REGISTRY_JOB_OUTCOME_FAMILY.keys())
    assert keys == sorted(keys), "Keep REGISTRY_JOB_OUTCOME_FAMILY keys alphabetically sorted."


def test_governance_notes_cover_every_family_key():
    family_keys = {t[0] for t in OUTCOME_FAMILY_ORDER}
    assert set(OUTCOME_FAMILY_GOVERNANCE.keys()) == family_keys
    for fk, meta in OUTCOME_FAMILY_GOVERNANCE.items():
        assert meta.get("belongs"), f"{fk} missing 'belongs'"
        assert meta.get("represents"), f"{fk} missing 'represents'"
        assert meta.get("excludes"), f"{fk} missing 'excludes'"
