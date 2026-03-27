"""
Forgot-password must send the reset email to the portal user's auth_email first,
so it matches the inbox the user checks after submitting the form.
"""
import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))


def test_forgot_password_orchestrator_recipient_prefers_portal_auth_email():
    async def _run():
        from services.notification_orchestrator import NotificationResult
        import routes.auth as auth_routes

        portal_user = {
            "portal_user_id": "pu-forgot-1",
            "auth_email": "login@client.example.com",
            "role": "ROLE_CLIENT_ADMIN",
            "client_id": "cli-forgot-1",
        }
        client_doc = {
            "client_id": "cli-forgot-1",
            "onboarding_status": "PROVISIONED",
            "email": "billing@other.example.com",
            "contact_email": "accounts@other.example.com",
            "full_name": "Acme Ltd",
        }

        mock_db = MagicMock()
        mock_db.portal_users.find_one = AsyncMock(return_value=portal_user)
        mock_db.clients.find_one = AsyncMock(return_value=client_doc)
        mock_db.password_tokens.update_many = AsyncMock()
        mock_db.password_tokens.insert_one = AsyncMock()

        mock_request = MagicMock()
        mock_request.headers.get = MagicMock(return_value=None)
        mock_request.client = MagicMock()
        mock_request.client.host = "127.0.0.1"

        orch_send = AsyncMock(
            return_value=NotificationResult(outcome="sent", message_id="msg-forgot-test")
        )

        with patch.object(auth_routes.database, "get_db", return_value=mock_db):
            with patch.object(
                auth_routes.rate_limiter,
                "check_rate_limit",
                new_callable=AsyncMock,
                return_value=(True, None),
            ):
                with patch.object(auth_routes, "create_audit_log", new_callable=AsyncMock):
                    with patch(
                        "services.notification_orchestrator.notification_orchestrator.send",
                        orch_send,
                    ):
                        with patch(
                            "utils.public_app_url.get_frontend_base_url",
                            return_value="https://app.example.com",
                        ):
                            from models import ForgotPasswordRequest

                            await auth_routes.forgot_password(
                                mock_request,
                                ForgotPasswordRequest(email="login@client.example.com"),
                            )

        orch_send.assert_called_once()
        ctx = orch_send.call_args[1]["context"]
        assert ctx["recipient"] == "login@client.example.com"
        assert "setup_link" in ctx
        assert ctx["setup_link"].startswith("https://app.example.com/set-password?token=")

    asyncio.run(_run())
