"""
Tests for risk lead email service: Activate Monitoring CTA URL uses app origin and optional lead_token.
"""
import os
import pytest
from unittest.mock import patch


def test_activate_url_contains_intake_start():
    """Lead email CTA must contain /intake/start; uses get_public_app_url (app origin)."""
    from services.risk_lead_email_service import _activate_url

    with patch("utils.public_app_url.get_public_app_url", return_value="https://app.example.com"):
        url = _activate_url({})
        assert url == "https://app.example.com/intake/start"


def test_activate_url_with_token_appends_lead_token():
    """When activation_token is provided, URL includes ?lead_token= for intake prefill."""
    from services.risk_lead_email_service import _activate_url

    with patch("utils.public_app_url.get_public_app_url", return_value="https://app.example.com"):
        url = _activate_url({}, "signed-token-xyz")
        assert url == "https://app.example.com/intake/start?lead_token=signed-token-xyz"


def test_activate_url_fallback_contains_intake_start():
    """When get_public_app_url raises (e.g. missing env), fallback yields URL containing /intake/start."""
    from services.risk_lead_email_service import _activate_url

    with patch("utils.public_app_url.get_public_app_url", side_effect=ValueError("missing")):
        with patch.dict(os.environ, {"FRONTEND_URL": "https://app.example.com"}, clear=False):
            url = _activate_url({})
            assert "/intake/start" in url


def test_step1_email_body_contains_intake_start_link():
    """Step 1 nurture email body must contain Activate Monitoring link with /intake/start."""
    from services.risk_lead_email_service import _body_step1

    with patch("services.risk_lead_email_service._activate_url", return_value="https://example.com/intake/start"):
        body = _body_step1({"first_name": "Test", "computed_score": 70, "risk_band": "MODERATE"})
        assert "/intake/start" in body
        assert "Activate Monitoring" in body
        assert "https://example.com/intake/start" in body


def test_step1_email_body_with_token_includes_lead_token_in_link():
    """Step 1 with activation_token passes token to URL so link has lead_token param."""
    from services.risk_lead_email_service import _body_step1

    with patch("services.risk_lead_email_service._activate_url", return_value="https://example.com/intake/start?lead_token=abc"):
        body = _body_step1({"first_name": "Test", "computed_score": 70, "risk_band": "MODERATE"}, "abc")
        assert "lead_token=abc" in body
