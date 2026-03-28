"""
Ensure customer order emails resolve branding and pass client_id into the orchestrator.
"""
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))


@pytest.mark.asyncio
async def test_send_client_info_request_passes_branding_and_client_id():
    """Admin order info request: resolve_order_email_branding → build(..., branding=) → send(client_id=)."""
    from routes import admin_orders

    order = {
        "client_id": "cli_wl_1",
        "customer": {"email": "cust@example.com", "full_name": "Bob"},
        "service_name": "Test Service",
    }
    branding = {
        "header_bg": "#111111",
        "accent": "#00aa00",
        "company_name": "Acme Co",
        "tagline": "We test",
        "support_email": "support@acme.com",
    }
    payload = {
        "request_notes": "Please upload X",
        "requested_fields": ["field_a"],
        "requested_at": "ts1",
    }

    with patch(
        "services.branding_resolver_service.resolve_order_email_branding",
        new_callable=AsyncMock,
        return_value=branding,
    ) as resolve_mock:
        with patch(
            "services.order_email_templates.build_client_input_required_email",
            return_value={"subject": "Subj", "html": "<p>html</p>", "text": "plain"},
        ) as build_mock:
            with patch(
                "services.notification_orchestrator.notification_orchestrator"
            ) as orch_mod:
                orch_mod.send = AsyncMock(
                    return_value=MagicMock(outcome="sent")
                )
                with patch(
                    "services.order_view_token.generate_order_provide_info_token",
                    return_value="tok123",
                ):
                    with patch(
                        "utils.app_urls.get_app_base_url",
                        return_value="https://app.example",
                    ):
                        ok = await admin_orders._send_client_info_request_email(
                            order, "ord-999", payload
                        )

    assert ok is True
    resolve_mock.assert_awaited_once_with("cli_wl_1")
    build_mock.assert_called_once()
    assert build_mock.call_args.kwargs.get("branding") == branding
    orch_mod.send.assert_awaited_once()
    send_kw = orch_mod.send.call_args.kwargs
    assert send_kw.get("client_id") == "cli_wl_1"
    assert send_kw.get("template_key") == "ORDER_INFO_REQUEST"
