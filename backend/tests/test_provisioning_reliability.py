"""
Tests for provisioning reliability: FAILED retry, email failure isolation, resend invite.

- (a) Email failure in STEP 8 does not set onboarding_status to FAILED when PortalUser exists.
- (b) Client in FAILED state can be retried (provision_client_portal succeeds).
- (c) Resend invite (script) works for existing PortalUser.
"""
import pytest
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

pytestmark = pytest.mark.asyncio

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
os.chdir(BACKEND_DIR)

CLIENT_ID = "test-client-123"
PORTAL_USER_ID = "portal-user-456"
PROPERTY_ID = "prop-789"


def _make_mock_db(
    client_status="PROVISIONING",
    has_portal_user=True,
    has_properties=True,
):
    """Build a mock DB that returns client, optional portal_user, and properties."""
    client = {
        "client_id": CLIENT_ID,
        "email": "client@example.com",
        "full_name": "Test Client",
        "onboarding_status": client_status,
        "subscription_status": "ACTIVE",
        "billing_plan": "PLAN_1",
    }
    properties = [{"client_id": CLIENT_ID, "property_id": PROPERTY_ID}] if has_properties else []
    portal_user = (
        {"client_id": CLIENT_ID, "portal_user_id": PORTAL_USER_ID, "role": "ROLE_CLIENT_ADMIN"}
        if has_portal_user
        else None
    )

    db = MagicMock()
    db.clients = MagicMock()
    db.clients.find_one = AsyncMock(side_effect=[
        client,  # first call: get client
    ])
    db.clients.update_one = AsyncMock()
    db.clients.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=properties)))

    db.properties = MagicMock()
    db.properties.find_one = AsyncMock(return_value={"property_id": PROPERTY_ID, "property_type": "residential"})
    db.properties.update_one = AsyncMock()

    db.portal_users = MagicMock()
    db.portal_users.find_one = AsyncMock(return_value=portal_user)
    db.portal_users.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=properties)))
    db.portal_users.insert_one = AsyncMock()

    db.requirement_rules = MagicMock()
    db.requirement_rules.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[])))
    db.requirements = MagicMock()
    db.requirements.find_one = AsyncMock(return_value=None)
    db.requirements.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[])))
    db.requirements.insert_one = AsyncMock()
    db.requirements.update_one = AsyncMock()

    db.password_tokens = MagicMock()
    db.password_tokens.insert_one = AsyncMock()
    db.password_tokens.update_many = AsyncMock()

    return db, client


class TestProvisioningEmailFailureIsolation:
    """(a) Email failure in STEP 8 must not set FAILED; client stays PROVISIONED; last_invite_error set."""

    @pytest.mark.asyncio
    async def test_email_failure_does_not_set_failed(self):
        from services.provisioning import provisioning_service
        from models import OnboardingStatus, AuditAction

        db, _ = _make_mock_db(client_status="PROVISIONING", has_portal_user=True, has_properties=True)

        with patch("services.provisioning.database.get_db", return_value=db), \
             patch("services.provisioning.create_audit_log", new_callable=AsyncMock) as mock_audit:
            with patch.object(
                provisioning_service,
                "_send_password_setup_link",
                side_effect=Exception("SMTP error"),
            ):
                success, message = await provisioning_service.provision_client_portal(CLIENT_ID)

        assert success is True
        assert "invite email failed" in message or "resend" in message.lower()
        # Client must have been set to PROVISIONED (STEP 6) and then last_invite_error set (STEP 8 catch)
        updates = [c for c in db.clients.update_one.call_args_list if c[0][0] == {"client_id": CLIENT_ID}]
        set_payloads = [c[1].get("$set", {}) for c in updates]
        assert any(s.get("onboarding_status") == OnboardingStatus.PROVISIONED.value for s in set_payloads)
        assert any("last_invite_error" in s for s in set_payloads)
        assert not any(s.get("onboarding_status") == OnboardingStatus.FAILED.value for s in set_payloads)
        fail_calls = [c for c in mock_audit.call_args_list if c[1].get("action") == AuditAction.PORTAL_INVITE_EMAIL_FAILED]
        assert len(fail_calls) >= 1
        meta = fail_calls[0][1].get("metadata", {})
        assert "error" in meta and "portal_user_id" in meta


class TestProvisioningFailedRetry:
    """(b) FAILED clients can be retried; provisioning runs and can succeed."""

    @pytest.mark.asyncio
    async def test_failed_client_not_treated_as_already_provisioned(self):
        from services.provisioning import provisioning_service
        from models import OnboardingStatus

        db, client = _make_mock_db(client_status="FAILED", has_portal_user=True, has_properties=True)

        with patch("services.provisioning.database.get_db", return_value=db), \
             patch("services.provisioning.create_audit_log", new_callable=AsyncMock):
            with patch.object(
                provisioning_service,
                "_send_password_setup_link",
                new_callable=AsyncMock,
            ):
                success, message = await provisioning_service.provision_client_portal(CLIENT_ID)

        # Should have run provisioning (not returned "Already provisioned")
        assert message != "Already provisioned"
        # Should have set PROVISIONING then PROVISIONED
        updates = [c[1].get("$set", {}) for c in db.clients.update_one.call_args_list]
        assert any(s.get("onboarding_status") == OnboardingStatus.PROVISIONING.value for s in updates)
        assert any(s.get("onboarding_status") == OnboardingStatus.PROVISIONED.value for s in updates)


class TestResendInvite:
    """(c) Resend invite works for existing PortalUser (script path)."""

    @pytest.mark.asyncio
    async def test_resend_invite_script_sends_for_existing_portal_user(self):
        from scripts.resend_portal_invite import resend_invite

        db = MagicMock()
        client = {"client_id": CLIENT_ID, "email": "client@example.com", "full_name": "Test Client"}
        portal_user = {"portal_user_id": PORTAL_USER_ID}
        db.clients = MagicMock()
        db.clients.find_one = AsyncMock(return_value=client)
        db.portal_users = MagicMock()
        db.portal_users.find_one = AsyncMock(return_value=portal_user)
        db.password_tokens = MagicMock()
        db.password_tokens.update_many = AsyncMock()
        db.password_tokens.insert_one = AsyncMock()

        with patch("scripts.resend_portal_invite.database.get_db", return_value=db), \
             patch("scripts.resend_portal_invite.create_audit_log", new_callable=AsyncMock) as mock_audit:
            with patch("services.email_service.email_service.send_password_setup_email", new_callable=AsyncMock) as mock_send:
                result = await resend_invite("client@example.com")

        assert result is True
        mock_send.assert_called_once()
        call_kw = mock_send.call_args[1]
        assert call_kw["recipient"] == "client@example.com"
        assert call_kw["client_id"] == CLIENT_ID
        mock_audit.assert_called_once()
        assert mock_audit.call_args[1]["action"].value == "PORTAL_INVITE_RESENT"
        assert mock_audit.call_args[1]["client_id"] == CLIENT_ID
