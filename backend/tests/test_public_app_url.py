"""Tests for get_public_app_url (activation link base URL)."""
import os
import pytest
from unittest.mock import patch


def test_get_frontend_base_url_uses_frontend_public_url():
    """Generated activation link base must start with FRONTEND_PUBLIC_URL when set."""
    from utils.public_app_url import get_frontend_base_url

    with patch.dict(
        os.environ,
        {
            "FRONTEND_PUBLIC_URL": "https://pleerityenterprise.co.uk",
            "PUBLIC_APP_URL": "https://other.example.com",
        },
        clear=False,
    ):
        base = get_frontend_base_url()
    assert base.startswith("https://pleerityenterprise.co.uk")
    assert "other.example.com" not in base
    assert base.rstrip("/") == base
    # Simulated link format
    link = f"{base}/set-password?token=***"
    assert link.startswith("https://pleerityenterprise.co.uk")


def test_get_public_app_url_prefers_frontend_public_url():
    """When FRONTEND_PUBLIC_URL is set, activation link base uses it (single source of truth for emails)."""
    from utils.public_app_url import get_public_app_url

    with patch.dict(
        os.environ,
        {
            "FRONTEND_PUBLIC_URL": "https://pleerityenterprise.co.uk",
            "PUBLIC_APP_URL": "https://other.example.com",
        },
        clear=False,
    ):
        url = get_public_app_url(for_email_links=True)
    assert url.startswith("https://pleerityenterprise.co.uk")
    assert "other.example.com" not in url
    assert url.rstrip("/") == url


def test_get_public_app_url_uses_public_app_url_when_set():
    """When PUBLIC_APP_URL is set, returned URL contains that domain (no localhost)."""
    from utils.public_app_url import get_public_app_url

    with patch.dict(os.environ, {"PUBLIC_APP_URL": "https://app.example.com"}, clear=False):
        url = get_public_app_url(for_email_links=False)
    assert "app.example.com" in url
    assert "localhost" not in url
    assert url.rstrip("/") == url


def test_get_public_app_url_strips_trailing_slash():
    """Returned URL has no trailing slash."""
    from utils.public_app_url import get_public_app_url

    with patch.dict(os.environ, {"PUBLIC_APP_URL": "https://app.example.com/"}, clear=False):
        url = get_public_app_url(for_email_links=False)
    assert url == "https://app.example.com"


def test_get_public_app_url_uses_canonical_when_missing():
    """When for_email_links=True and no URL set, returns canonical domain (no Vercel default)."""
    from utils.public_app_url import get_public_app_url

    with patch.dict(os.environ, {"PUBLIC_APP_URL": "", "FRONTEND_PUBLIC_URL": "", "FRONTEND_URL": ""}, clear=False):
        url = get_public_app_url(for_email_links=True)
    assert url == "https://pleerityenterprise.co.uk"
    assert "vercel.app" not in url
