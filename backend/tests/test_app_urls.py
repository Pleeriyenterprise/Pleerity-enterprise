"""Canonical APP_BASE_URL / API_BASE_URL resolution."""
import os
import pytest
from unittest.mock import patch


def test_app_base_url_prefers_app_base_url():
    from utils.app_urls import get_app_base_url

    with patch.dict(
        os.environ,
        {
            "APP_BASE_URL": "https://app.canonical.example",
            "FRONTEND_PUBLIC_URL": "https://other.example.com",
            "FRONTEND_URL": "https://third.example.com",
        },
        clear=False,
    ):
        assert get_app_base_url(for_email_links=True) == "https://app.canonical.example"


def test_api_base_url_prefers_api_base_url():
    from utils.app_urls import get_api_base_url

    with patch.dict(
        os.environ,
        {
            "API_BASE_URL": "https://api.canonical.example",
            "BACKEND_URL": "https://legacy-backend.example",
        },
        clear=False,
    ):
        assert get_api_base_url() == "https://api.canonical.example"


def test_validate_fails_on_conflicting_app_origins():
    from utils.app_urls import validate_url_configuration

    with patch.dict(
        os.environ,
        {
            "ENVIRONMENT": "production",
            "FRONTEND_URL": "https://a.example.com",
            "FRONTEND_PUBLIC_URL": "https://b.example.com",
            "PYTEST_RUNNING": "",
            "SKIP_URL_VALIDATION": "",
        },
        clear=False,
    ):
        with pytest.raises(RuntimeError, match="multiple distinct app origins"):
            validate_url_configuration()


def test_validate_allows_http_and_https_same_host():
    """Legacy vars often mix schemes; same host must not abort startup."""
    from utils.app_urls import validate_url_configuration

    with patch.dict(
        os.environ,
        {
            "ENVIRONMENT": "production",
            "APP_BASE_URL": "https://pleerityenterprise.co.uk",
            "FRONTEND_URL": "http://pleerityenterprise.co.uk",
            "FRONTEND_PUBLIC_URL": "https://pleerityenterprise.co.uk",
            "PYTEST_RUNNING": "",
            "SKIP_URL_VALIDATION": "",
        },
        clear=False,
    ):
        validate_url_configuration()


def test_validate_on_render_logs_and_continues_on_conflict():
    """On RENDER=true, conflicting origins must not raise so the service can bind to PORT."""
    from utils.app_urls import validate_url_configuration

    with patch.dict(
        os.environ,
        {
            "ENVIRONMENT": "production",
            "RENDER": "true",
            "FRONTEND_URL": "https://a.example.com",
            "FRONTEND_PUBLIC_URL": "https://b.example.com",
            "PYTEST_RUNNING": "",
            "SKIP_URL_VALIDATION": "",
        },
        clear=False,
    ):
        validate_url_configuration()
        # Must not raise; on Render we log CRITICAL and continue
