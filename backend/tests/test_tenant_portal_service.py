"""Tests for tenant portal onboarding state model."""
from services.tenant_portal_service import (
    ACTIVATION_PENDING,
    LINKED_TO_TENANCY,
    TENANT_ACTIVE,
    TENANT_INVITE_SENT,
    derive_tenant_onboarding_state,
    enrich_tenant_portal_view,
)


def test_activation_pending_when_invite_sent_not_activated():
    tenant = {
        "status": "INVITED",
        "password_status": "NOT_SET",
        "portal_invite_sent_at": "2026-05-30T12:00:00+00:00",
    }
    assert derive_tenant_onboarding_state(tenant) == ACTIVATION_PENDING


def test_linked_when_active_with_properties():
    tenant = {
        "status": "ACTIVE",
        "password_status": "SET",
        "portal_invite_sent_at": "2026-05-30T12:00:00+00:00",
    }
    assert derive_tenant_onboarding_state(tenant, assigned_property_count=1) == LINKED_TO_TENANCY


def test_enrich_adds_label():
    tenant = {
        "status": "INVITED",
        "password_status": "NOT_SET",
        "portal_invite_sent_at": "2026-05-30T12:00:00+00:00",
        "assigned_properties": [],
    }
    out = enrich_tenant_portal_view(tenant)
    assert out["onboarding_state"] == ACTIVATION_PENDING
    assert out["onboarding_state_label"] == "Activation pending"
    assert out["portal_activation_pending"] is True


def test_active_without_invite_timestamp_still_active():
    tenant = {"status": "ACTIVE", "password_status": "SET"}
    assert derive_tenant_onboarding_state(tenant) == TENANT_ACTIVE


def test_record_created_without_invite_timestamp():
    tenant = {"status": "INVITED", "password_status": "NOT_SET"}
    from services.tenant_portal_service import TENANT_RECORD_CREATED

    assert derive_tenant_onboarding_state(tenant) == TENANT_RECORD_CREATED
