"""
Tests for OWNER + ADMIN governance and zero-stranding recovery.
- OWNER bypasses billing/plan gating; ADMIN does not bypass client plan gating.
- Plan gating enforced for normal clients.
- Last OWNER cannot be removed (deactivate OWNER returns 403).
- Break-glass writes audit log and forces logout (session_version incremented).
"""
import pytest
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from models import UserRole, UserStatus, AuditAction


class TestOwnerBypassesPlanGating:
    """OWNER bypasses billing/plan gating in require_feature."""

    @pytest.mark.asyncio
    async def test_owner_bypasses_feature_gate(self):
        from middleware.feature_gating import require_feature

        async def handler(request):
            return "ok"

        request = MagicMock()
        request.state = MagicMock()
        request.state.user = {
            "portal_user_id": "owner-1",
            "client_id": None,
            "role": UserRole.ROLE_OWNER.value,
        }
        request.url = MagicMock(path="/api/test")
        request.method = "GET"

        wrapped = require_feature("zip_upload")(handler)
        result = await wrapped(request)
        assert result == "ok"


class TestAdminDoesNotBypassPlanGating:
    """ADMIN does not bypass client plan gating (client_id required, plan checked)."""

    @pytest.mark.asyncio
    async def test_admin_with_client_id_gated_by_plan(self):
        from middleware.feature_gating import require_feature
        from fastapi import HTTPException

        async def handler(request):
            return "ok"

        request = MagicMock()
        request.state = MagicMock()
        request.state.user = {
            "portal_user_id": "admin-1",
            "client_id": "client-123",
            "role": UserRole.ROLE_ADMIN.value,
        }
        request.url = MagicMock(path="/api/test")
        request.method = "GET"

        db = MagicMock()
        db.clients = MagicMock()
        db.clients.find_one = AsyncMock(return_value={
            "billing_plan": "PLAN_1_SOLO",
            "subscription_status": "ACTIVE",
        })

        with patch("middleware.feature_gating.database.get_db", return_value=db), \
             patch("services.plan_registry.plan_registry") as pr:
            pr.resolve_plan_code.return_value = MagicMock(value="PLAN_1_SOLO")
            pr.get_features.return_value = {"zip_upload": False}
            pr.get_plan.return_value = {"name": "Solo"}

            with patch("middleware.feature_gating.create_audit_log", new_callable=AsyncMock):
                wrapped = require_feature("zip_upload")(handler)
                with pytest.raises(HTTPException) as exc:
                    await wrapped(request)
                assert exc.value.status_code == 403


class TestLastOwnerCannotBeRemoved:
    """Deactivate OWNER returns 403; last OWNER cannot be removed."""

    @pytest.mark.asyncio
    async def test_deactivate_owner_returns_403(self):
        from routes.admin import deactivate_admin
        from fastapi import Request, HTTPException

        request = MagicMock()
        request.headers = {"Authorization": "Bearer fake"}
        # Authenticated as ADMIN trying to deactivate an OWNER
        with patch("routes.admin.admin_route_guard", new_callable=AsyncMock) as guard:
            guard.return_value = {
                "portal_user_id": "admin-1",
                "email": "admin@test.com",
                "role": UserRole.ROLE_ADMIN.value,
            }
            db = MagicMock()
            db.portal_users = MagicMock()
            db.portal_users.find_one = AsyncMock(return_value={
                "portal_user_id": "owner-1",
                "role": UserRole.ROLE_OWNER.value,
                "status": UserStatus.ACTIVE.value,
                "auth_email": "owner@test.com",
            })

            with patch("routes.admin.database.get_db", return_value=db), \
                 patch("routes.admin.create_audit_log", new_callable=AsyncMock):
                with pytest.raises(HTTPException) as exc:
                    await deactivate_admin(request, "owner-1")
                assert exc.value.status_code == 403
                assert "OWNER" in exc.value.detail


class TestBreakGlassAuditAndForceLogout:
    """Break-glass writes BREAK_GLASS_OWNER_USED and increments session_version."""

    @pytest.mark.asyncio
    async def test_break_glass_writes_audit_and_increments_session_version(self):
        import os
        from routes.auth import break_glass_reset_owner_password
        from fastapi import Request

        request = MagicMock()
        request.headers = {
            "Content-Type": "application/json",
            "X-Break-Glass-Secret": "secret123",
        }
        request.json = AsyncMock(return_value={"new_password": "NewSecure1!"})

        with patch.dict(os.environ, {"BREAK_GLASS_ENABLED": "true", "BOOTSTRAP_SECRET": "secret123"}, clear=False):
            db = MagicMock()
            db.portal_users = MagicMock()
            db.portal_users.find_one = AsyncMock(return_value={
                "portal_user_id": "owner-1",
                "auth_email": "owner@test.com",
            })
            db.portal_users.update_one = AsyncMock(return_value=MagicMock(modified_count=1))

            audit_logs = []
            async def capture_audit(*args, **kwargs):
                audit_logs.append(kwargs.get("action") or (args[0] if args else None))

            with patch("routes.auth.database.get_db", return_value=db), \
                 patch("routes.auth.create_audit_log", new_callable=AsyncMock, side_effect=capture_audit), \
                 patch("routes.auth.hash_password", return_value="hashed"):
                result = await break_glass_reset_owner_password(request)
                assert result.get("message") and "invalidated" in result.get("message", "")
                update_call = db.portal_users.update_one.call_args
                assert update_call is not None
                set_part = update_call[1].get("$set", {})
                inc_part = update_call[1].get("$inc", {})
                assert "password_hash" in set_part
                assert inc_part.get("session_version") == 1
                assert any(
                    (getattr(a, "value", None) == AuditAction.BREAK_GLASS_OWNER_USED.value or a == AuditAction.BREAK_GLASS_OWNER_USED)
                    for a in audit_logs
                )


class TestPlanGatingEnforcedForNormalClients:
    """Normal client (ROLE_CLIENT/ROLE_CLIENT_ADMIN) is subject to plan gating."""

    @pytest.mark.asyncio
    async def test_client_without_feature_gets_403(self):
        from middleware.feature_gating import require_feature
        from fastapi import HTTPException

        async def handler(request):
            return "ok"

        request = MagicMock()
        request.state = MagicMock()
        request.state.user = {
            "portal_user_id": "user-1",
            "client_id": "client-456",
            "role": "ROLE_CLIENT_ADMIN",
        }
        request.url = MagicMock(path="/api/test")
        request.method = "GET"

        db = MagicMock()
        db.clients = MagicMock()
        db.clients.find_one = AsyncMock(return_value={
            "billing_plan": "PLAN_1_SOLO",
            "subscription_status": "ACTIVE",
        })

        with patch("middleware.feature_gating.database.get_db", return_value=db), \
             patch("services.plan_registry.plan_registry") as pr, \
             patch("middleware.feature_gating.create_audit_log", new_callable=AsyncMock):
            pr.resolve_plan_code.return_value = MagicMock(value="PLAN_1_SOLO")
            pr.get_features.return_value = {"zip_upload": False}
            pr.get_plan.return_value = {"name": "Solo"}
            wrapped = require_feature("zip_upload")(handler)
            with pytest.raises(HTTPException) as exc:
                await wrapped(request)
            assert exc.value.status_code == 403
