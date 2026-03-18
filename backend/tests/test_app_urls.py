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
