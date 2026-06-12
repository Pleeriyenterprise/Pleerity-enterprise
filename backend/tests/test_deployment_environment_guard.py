"""Deployment tier guardrails."""
import os
from unittest.mock import patch

import pytest

from utils.deployment_environment_guard import (
    DeploymentEnvironmentError,
    resolve_deployment_tier,
    validate_deployment_environment,
)


def test_resolve_tier_explicit():
    with patch.dict(os.environ, {"DEPLOYMENT_TIER": "staging"}, clear=False):
        assert resolve_deployment_tier() == "staging"
    with patch.dict(os.environ, {"DEPLOYMENT_TIER": "production"}, clear=False):
        assert resolve_deployment_tier() == "production"


def test_resolve_tier_from_db_name():
    with patch.dict(os.environ, {"DB_NAME": "pleerity_staging", "DEPLOYMENT_TIER": ""}, clear=False):
        assert resolve_deployment_tier() == "staging"
    with patch.dict(os.environ, {"DB_NAME": "pleerity_production", "DEPLOYMENT_TIER": ""}, clear=False):
        assert resolve_deployment_tier() == "production"


def test_legacy_combined_stack_staging_db_overrides_env_production():
    """Legacy Render: production URLs + live Stripe + pleerity_staging until tier migration."""
    env = {
        "DEPLOYMENT_TIER": "",
        "ENVIRONMENT": "production",
        "DB_NAME": "pleerity_staging",
        "STRIPE_MODE": "live",
        "APP_BASE_URL": "https://pleerityenterprise.co.uk",
        "API_BASE_URL": "https://api.pleerityenterprise.co.uk",
        "JWT_SECRET": "secure-staging-secret",
        "PYTEST_RUNNING": "",
        "SKIP_DEPLOYMENT_GUARD": "",
    }
    with patch.dict(os.environ, env, clear=False):
        assert resolve_deployment_tier() == "staging"
        assert validate_deployment_environment() == "staging"


def test_production_refuses_staging_db():
    env = {
        "DEPLOYMENT_TIER": "production",
        "ENVIRONMENT": "production",
        "DB_NAME": "pleerity_staging",
        "STRIPE_MODE": "live",
        "JWT_SECRET": "secure-random-production-secret",
        "APP_BASE_URL": "https://pleerityenterprise.co.uk",
        "API_BASE_URL": "https://api.pleerityenterprise.co.uk",
        "PYTEST_RUNNING": "",
        "SKIP_DEPLOYMENT_GUARD": "",
    }
    with patch.dict(os.environ, env, clear=False):
        with pytest.raises(DeploymentEnvironmentError, match="staging database"):
            validate_deployment_environment()


def test_production_refuses_test_stripe_mode():
    env = {
        "DEPLOYMENT_TIER": "production",
        "DB_NAME": "pleerity_production",
        "STRIPE_MODE": "test",
        "JWT_SECRET": "secure-random-production-secret",
        "APP_BASE_URL": "https://pleerityenterprise.co.uk",
        "API_BASE_URL": "https://api.pleerityenterprise.co.uk",
        "PYTEST_RUNNING": "",
        "SKIP_DEPLOYMENT_GUARD": "",
    }
    with patch.dict(os.environ, env, clear=False):
        with pytest.raises(DeploymentEnvironmentError, match="STRIPE_MODE=live"):
            validate_deployment_environment()


def test_production_refuses_staging_api_url():
    env = {
        "DEPLOYMENT_TIER": "production",
        "DB_NAME": "pleerity_production",
        "STRIPE_MODE": "live",
        "JWT_SECRET": "secure-random-production-secret",
        "APP_BASE_URL": "https://pleerityenterprise.co.uk",
        "API_BASE_URL": "https://pleerity-enterprise.onrender.com",
        "PYTEST_RUNNING": "",
        "SKIP_DEPLOYMENT_GUARD": "",
    }
    with patch.dict(os.environ, env, clear=False):
        with pytest.raises(DeploymentEnvironmentError, match="staging/dev host"):
            validate_deployment_environment()


def test_production_refuses_default_jwt():
    env = {
        "DEPLOYMENT_TIER": "production",
        "DB_NAME": "pleerity_production",
        "STRIPE_MODE": "live",
        "JWT_SECRET": "your-secret-key-change-in-production",
        "APP_BASE_URL": "https://pleerityenterprise.co.uk",
        "API_BASE_URL": "https://api.pleerityenterprise.co.uk",
        "PYTEST_RUNNING": "",
        "SKIP_DEPLOYMENT_GUARD": "",
    }
    with patch.dict(os.environ, env, clear=False):
        with pytest.raises(DeploymentEnvironmentError, match="JWT_SECRET"):
            validate_deployment_environment()


def test_production_passes_valid_config():
    env = {
        "DEPLOYMENT_TIER": "production",
        "DB_NAME": "pleerity_production",
        "STRIPE_MODE": "live",
        "JWT_SECRET": "secure-random-production-secret",
        "APP_BASE_URL": "https://pleerityenterprise.co.uk",
        "API_BASE_URL": "https://api.pleerityenterprise.co.uk",
        "PYTEST_RUNNING": "",
        "SKIP_DEPLOYMENT_GUARD": "",
    }
    with patch.dict(os.environ, env, clear=False):
        assert validate_deployment_environment() == "production"


def test_staging_refuses_live_stripe():
    env = {
        "DEPLOYMENT_TIER": "staging",
        "DB_NAME": "pleerity_staging",
        "STRIPE_MODE": "live",
        "APP_BASE_URL": "https://staging.pleerityenterprise.co.uk",
        "API_BASE_URL": "https://pleerity-enterprise.onrender.com",
        "PYTEST_RUNNING": "",
        "SKIP_DEPLOYMENT_GUARD": "",
    }
    with patch.dict(os.environ, env, clear=False):
        with pytest.raises(DeploymentEnvironmentError, match="STRIPE_MODE=live"):
            validate_deployment_environment()


def test_staging_refuses_production_db():
    env = {
        "DEPLOYMENT_TIER": "staging",
        "DB_NAME": "pleerity_production",
        "STRIPE_MODE": "test",
        "APP_BASE_URL": "https://staging.pleerityenterprise.co.uk",
        "API_BASE_URL": "https://pleerity-enterprise.onrender.com",
        "PYTEST_RUNNING": "",
        "SKIP_DEPLOYMENT_GUARD": "",
    }
    with patch.dict(os.environ, env, clear=False):
        with pytest.raises(DeploymentEnvironmentError, match="production database"):
            validate_deployment_environment()


def test_staging_refuses_production_frontend_url():
    env = {
        "DEPLOYMENT_TIER": "staging",
        "DB_NAME": "pleerity_staging",
        "STRIPE_MODE": "test",
        "APP_BASE_URL": "https://pleerityenterprise.co.uk",
        "API_BASE_URL": "https://pleerity-enterprise.onrender.com",
        "PYTEST_RUNNING": "",
        "SKIP_DEPLOYMENT_GUARD": "",
    }
    with patch.dict(os.environ, env, clear=False):
        with pytest.raises(DeploymentEnvironmentError, match="production frontend"):
            validate_deployment_environment()


def test_staging_passes_valid_config():
    env = {
        "DEPLOYMENT_TIER": "staging",
        "DB_NAME": "pleerity_staging",
        "STRIPE_MODE": "test",
        "APP_BASE_URL": "https://staging.pleerityenterprise.co.uk",
        "API_BASE_URL": "https://pleerity-enterprise.onrender.com",
        "PYTEST_RUNNING": "",
        "SKIP_DEPLOYMENT_GUARD": "",
    }
    with patch.dict(os.environ, env, clear=False):
        assert validate_deployment_environment() == "staging"
