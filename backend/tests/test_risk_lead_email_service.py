"""
Tests for risk lead email service: CTA URL, operational snapshot layout, and admin-manual document bypass.
"""
import os
import pytest
from unittest.mock import patch, AsyncMock, MagicMock


def test_activate_url_contains_intake_start():
    """Lead email CTA must contain /intake/start; uses get_public_app_url (app origin)."""
    from services.risk_lead_email_service import _activate_url

    with patch("utils.app_urls.get_app_base_url", return_value="https://app.example.com"):
        url = _activate_url({})
        assert url == "https://app.example.com/intake/start"


def test_activate_url_with_token_appends_lead_token():
    """When activation_token is provided, URL includes ?lead_token= for intake prefill."""
    from services.risk_lead_email_service import _activate_url

    with patch("utils.app_urls.get_app_base_url", return_value="https://app.example.com"):
        url = _activate_url({}, "signed-token-xyz")
        assert url == "https://app.example.com/intake/start?lead_token=signed-token-xyz"


def test_activate_url_uses_env_when_no_patch():
    """_activate_url resolves app base from env chain."""
    from services.risk_lead_email_service import _activate_url

    with patch.dict(
        os.environ,
        {
            "APP_BASE_URL": "",
            "FRONTEND_PUBLIC_URL": "",
            "PUBLIC_APP_URL": "",
            "FRONTEND_URL": "https://app.example.com",
            "PORTAL_BASE_URL": "",
        },
        clear=False,
    ):
        url = _activate_url({})
        assert url == "https://app.example.com/intake/start"


def test_step1_email_body_contains_intake_start_link():
    """Step 1 nurture email body must contain monitoring CTA with /intake/start."""
    from services.risk_lead_email_service import _body_step1

    with patch("services.risk_lead_email_service._activate_url", return_value="https://example.com/intake/start"):
        body = _body_step1({"first_name": "Test", "computed_score": 70, "risk_band": "MODERATE"})
        assert "/intake/start" in body
        assert "Start Compliance Monitoring" in body
        assert "https://example.com/intake/start" in body
        assert "Moderate Risk" in body
        assert "Assessment generated:" in body
        assert "information currently available from your risk check responses" in body
        assert body.count("Hello ") == 1
        assert "Activate Compliance Monitoring" not in body


def test_step1_email_body_with_token_includes_lead_token_in_link():
    """Step 1 with activation_token passes token to URL so link has lead_token param."""
    from services.risk_lead_email_service import _body_step1

    with patch("services.risk_lead_email_service._activate_url", return_value="https://example.com/intake/start?lead_token=abc"):
        body = _body_step1({"first_name": "Test", "computed_score": 70, "risk_band": "MODERATE"}, "abc")
        assert "lead_token=abc" in body


def test_step1_omits_risk_level_when_score_invalid():
    from services.risk_lead_email_service import _body_step1

    with patch("services.risk_lead_email_service._activate_url", return_value="https://example.com/intake/start"):
        body = _body_step1({"first_name": "Test", "computed_score": "N/A"})
        assert "High Risk" not in body
        assert "Compliance score unavailable" in body


@pytest.mark.asyncio
async def test_admin_manual_full_html_message_bypasses_db_template():
    """Full <html> message must not be merged into admin-manual DB wrapper (no double shell)."""
    from services.notification_orchestrator import notification_orchestrator

    db = MagicMock()
    db.email_templates.find_one = AsyncMock(
        return_value={
            "subject": "WRONG SUBJECT",
            "html_body": "<p>OUTER {{message}}</p>",
            "text_body": "OUTER",
        }
    )
    with patch("services.notification_orchestrator.database.get_db", return_value=db):
        with patch(
            "services.branding_resolver_service.merge_email_branding_context",
            new_callable=AsyncMock,
        ):
            full = "<html><body><p>Hello David,</p></body></html>"
            html, text, subj = await notification_orchestrator._render_email(
                db,
                "admin-manual",
                {
                    "message": full,
                    "subject": "Your Compliance Risk Snapshot",
                },
                "default subject",
                None,
            )
    assert html.strip() == full
    assert "OUTER" not in html
    assert subj == "Your Compliance Risk Snapshot"
    assert "David" in text or "Hello" in text
