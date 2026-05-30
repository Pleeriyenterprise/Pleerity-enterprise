"""Contractor invite / activation onboarding state derivation."""
from services.contractor_service import (
    ONBOARDING_ACTIVATION_PENDING,
    ONBOARDING_ACTIVE,
    ONBOARDING_DIRECTORY_CREATED,
    ONBOARDING_DISABLED,
    ONBOARDING_JOB_INVITE_SENT,
    ONBOARDING_PORTAL_INVITE_SENT,
    derive_contractor_onboarding_state,
    enrich_contractor_onboarding_view,
    portal_access_is_activated,
)


def test_directory_created_when_no_invites():
    c = {"status": "approved", "portal_access_status": "not_invited"}
    assert derive_contractor_onboarding_state(c) == ONBOARDING_DIRECTORY_CREATED


def test_job_invite_sent_overrides_not_invited():
    c = {
        "status": "approved",
        "portal_access_status": "not_invited",
        "job_invite_sent_at": "2026-05-28T12:00:00+00:00",
    }
    assert derive_contractor_onboarding_state(c) == ONBOARDING_JOB_INVITE_SENT


def test_portal_invite_sent_when_portal_invite_timestamp():
    c = {
        "status": "approved",
        "portal_access_status": "not_invited",
        "job_invite_sent_at": "2026-05-28T12:00:00+00:00",
        "portal_invite_sent_at": "2026-05-28T12:01:00+00:00",
    }
    assert derive_contractor_onboarding_state(c) == ONBOARDING_PORTAL_INVITE_SENT


def test_activation_pending_on_invite_pending_portal():
    c = {
        "status": "approved",
        "portal_access_status": "invite_pending",
        "portal_invite_sent_at": "2026-05-28T12:01:00+00:00",
    }
    assert derive_contractor_onboarding_state(c) == ONBOARDING_ACTIVATION_PENDING


def test_active_when_lifecycle_and_portal_enabled():
    c = {
        "status": "active",
        "portal_access_status": "enabled",
        "activated_at": "2026-05-28T13:00:00+00:00",
    }
    assert derive_contractor_onboarding_state(c) == ONBOARDING_ACTIVE
    assert portal_access_is_activated(c)


def test_disabled_portal_wins():
    c = {
        "status": "active",
        "portal_access_status": "disabled",
        "job_invite_sent_at": "2026-05-28T12:00:00+00:00",
    }
    assert derive_contractor_onboarding_state(c) == ONBOARDING_DISABLED


def test_enrich_adds_labels():
    c = {"status": "approved", "portal_access_status": "not_invited", "job_invite_sent_at": "2026-05-28T12:00:00+00:00"}
    out = enrich_contractor_onboarding_view(c)
    assert out["onboarding_state"] == ONBOARDING_JOB_INVITE_SENT
    assert out["onboarding_state_label"] == "Job invite sent"
    assert out["portal_activation_required"] is True
