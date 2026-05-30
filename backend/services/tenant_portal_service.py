"""
Tenant portal onboarding state, invite truth, and API view enrichment.

Mirrors contractor invite/activation authority model for landlord + tenant surfaces.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# Derived onboarding states (authoritative labels for UI)
TENANT_RECORD_CREATED = "tenant_record_created"
TENANT_INVITE_SENT = "tenant_invite_sent"
ACTIVATION_PENDING = "activation_pending"
EMAIL_VERIFIED = "email_verified"
LANDLORD_APPROVAL_PENDING = "landlord_approval_pending"
LINKED_TO_TENANCY = "linked_to_tenancy"
TENANT_ACTIVE = "active"
MOVED_OUT = "moved_out"
ACCESS_REVOKED = "access_revoked"

ONBOARDING_STATE_LABELS = {
    TENANT_RECORD_CREATED: "Not invited",
    TENANT_INVITE_SENT: "Invite sent",
    ACTIVATION_PENDING: "Activation pending",
    EMAIL_VERIFIED: "Email verified",
    LANDLORD_APPROVAL_PENDING: "Approval pending",
    LINKED_TO_TENANCY: "Linked",
    TENANT_ACTIVE: "Active",
    MOVED_OUT: "Moved out",
    ACCESS_REVOKED: "Access revoked",
}

PORTAL_STATUS_INVITED = "INVITED"
PORTAL_STATUS_ACTIVE = "ACTIVE"
PORTAL_STATUS_DISABLED = "DISABLED"
PASSWORD_NOT_SET = "NOT_SET"
PASSWORD_SET = "SET"


def derive_tenant_onboarding_state(
    tenant: Dict[str, Any],
    *,
    assigned_property_count: int = 0,
    moved_out: bool = False,
) -> str:
    """Derive canonical tenant onboarding state from portal_users + assignment context."""
    status = (tenant.get("status") or "").strip().upper()
    pw = (tenant.get("password_status") or "").strip().upper()
    invite_sent = bool(tenant.get("portal_invite_sent_at"))

    if status == PORTAL_STATUS_DISABLED:
        return ACCESS_REVOKED
    if moved_out:
        return MOVED_OUT
    if status == PORTAL_STATUS_ACTIVE and pw == PASSWORD_SET:
        if assigned_property_count > 0:
            return LINKED_TO_TENANCY
        return TENANT_ACTIVE
    if invite_sent and pw == PASSWORD_NOT_SET:
        return ACTIVATION_PENDING
    if invite_sent:
        return TENANT_INVITE_SENT
    if status == PORTAL_STATUS_INVITED:
        return TENANT_RECORD_CREATED
    return TENANT_RECORD_CREATED


def enrich_tenant_portal_view(
    tenant: Dict[str, Any],
    *,
    assigned_property_count: Optional[int] = None,
) -> Dict[str, Any]:
    """Add derived onboarding fields for landlord/admin list responses."""
    out = dict(tenant)
    count = assigned_property_count
    if count is None:
        count = len(out.get("assigned_properties") or [])
    state = derive_tenant_onboarding_state(out, assigned_property_count=count)
    out["onboarding_state"] = state
    out["onboarding_state_label"] = ONBOARDING_STATE_LABELS.get(state, state)
    out["portal_activation_pending"] = state in (
        TENANT_INVITE_SENT,
        ACTIVATION_PENDING,
        TENANT_RECORD_CREATED,
    )
    out["linked_to_tenancy"] = count > 0 and state in (LINKED_TO_TENANCY, TENANT_ACTIVE)
    return out


def portal_activity_label(tenant: Dict[str, Any]) -> str:
    """Property occupancy panel label aligned with onboarding truth."""
    state = derive_tenant_onboarding_state(
        tenant,
        assigned_property_count=len(tenant.get("assigned_properties") or []),
    )
    if state in (TENANT_INVITE_SENT, ACTIVATION_PENDING, TENANT_RECORD_CREATED):
        return "pending_invite"
    if state in (TENANT_ACTIVE, LINKED_TO_TENANCY, EMAIL_VERIFIED):
        return "active"
    if state == ACCESS_REVOKED:
        return "revoked"
    return "invited"


async def record_tenant_portal_invite_sent(
    db,
    portal_user_id: str,
    *,
    resend: bool = False,
) -> None:
    """Persist invite email truth after successful delivery."""
    now_iso = datetime.now(timezone.utc).isoformat()
    patch: Dict[str, Any] = {
        "portal_invite_sent_at": now_iso,
        "updated_at": now_iso,
    }
    if not resend:
        patch.setdefault("status", PORTAL_STATUS_INVITED)
        patch.setdefault("password_status", PASSWORD_NOT_SET)
    await db.portal_users.update_one(
        {"portal_user_id": portal_user_id},
        {"$set": patch},
    )


async def revoke_unused_tenant_invite_tokens(db, portal_user_id: str) -> None:
    """Revoke sibling unused tenant invite tokens before issuing a new one."""
    now_iso = datetime.now(timezone.utc).isoformat()
    await db.password_tokens.update_many(
        {
            "portal_user_id": portal_user_id,
            "purpose": "tenant_invite",
            "used": {"$ne": True},
            "revoked_at": None,
        },
        {"$set": {"revoked_at": now_iso, "revoked_reason": "invite_replaced"}},
    )


def build_tenant_invite_url(base_url: str, raw_token: str) -> str:
    base = base_url.rstrip("/")
    return f"{base}/set-password?token={raw_token}&portal=tenant"
