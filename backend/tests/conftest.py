"""
Pytest configuration and shared test helpers for backend tests.
"""
import os

# Skip heavy server startup (MongoDB, scheduler) when running under pytest.
os.environ.setdefault("PYTEST_RUNNING", "1")

# Default MongoDB for integration tests (intake, checkout, packs). Override in CI. REF-PRODTEST-MONGO-DEFAULTS
_mongo_default = "mongodb://127.0.0.1:27017/?serverSelectionTimeoutMS=5000"
if not os.environ.get("MONGO_URL"):
    os.environ["MONGO_URL"] = _mongo_default
elif "serverSelectionTimeoutMS" not in os.environ.get("MONGO_URL", ""):
    _u = os.environ["MONGO_URL"].rstrip("/")
    os.environ["MONGO_URL"] = _u + ("&" if "?" in _u else "?") + "serverSelectionTimeoutMS=5000"
os.environ.setdefault("DB_NAME", "compliance_vault_pro_test")

# Synthetic Stripe price IDs so plan_registry.get_plan() / upgrade paths work in CI
# without real secrets. Real values can override via env. REF-PRODTEST-STRIPE-DEFAULTS
_STRIPE_TEST_DEFAULTS = {
    "STRIPE_TEST_PRICE_PLAN_1_SOLO_MONTHLY": "price_test_plan1_solo_monthly",
    "STRIPE_TEST_PRICE_PLAN_1_SOLO_ONBOARDING": "price_test_plan1_solo_onboarding",
    "STRIPE_TEST_PRICE_PLAN_2_PORTFOLIO_MONTHLY": "price_test_plan2_portfolio_monthly",
    "STRIPE_TEST_PRICE_PLAN_2_PORTFOLIO_ONBOARDING": "price_test_plan2_portfolio_onboarding",
    "STRIPE_TEST_PRICE_PLAN_3_PRO_MONTHLY": "price_test_plan3_pro_monthly",
    "STRIPE_TEST_PRICE_PLAN_3_PRO_ONBOARDING": "price_test_plan3_pro_onboarding",
}
for _k, _v in _STRIPE_TEST_DEFAULTS.items():
    os.environ.setdefault(_k, _v)
os.environ.setdefault("STRIPE_MODE", "test")
os.environ.setdefault("STRIPE_SECRET_KEY_TEST", "sk_test_pytest_dummy_not_for_production")

# OTP unit tests require a pepper at import-time of services.otp_service (via app import). Not a production secret.
os.environ.setdefault(
    "OTP_PEPPER",
    "pytest-otp-pepper-not-for-production-use-32chars!",
)

import pytest


@pytest.fixture(autouse=True)
def _lifecycle_tier_env_baseline(request, monkeypatch):
    """
    Lifecycle flag tests assume unknown deployment tier unless they set DEPLOYMENT_TIER.
    Clear tier-related env at each test start to avoid order/shell pollution.
    """
    mod_name = getattr(request.node, "module", None)
    mod_basename = getattr(mod_name, "__name__", "").rpartition(".")[-1]
    if not mod_basename.startswith("test_lifecycle"):
        return
    for key in (
        "DEPLOYMENT_TIER",
        "LIFECYCLE_AWARE_CONFIRM_PREVIEW_OVERRIDE",
        "LIFECYCLE_AWARE_EXTRACTION_PREVIEW_OVERRIDE",
        "LIFECYCLE_AWARE_SCORING_PREVIEW_OVERRIDE",
        "LIFECYCLE_AWARE_REMINDER_PREVIEW_OVERRIDE",
    ):
        monkeypatch.delenv(key, raising=False)


# CMS, blog, experimental tooling, internal analytics only (Phase 5.3). Not landlord core flows.
# REF-PRODTEST-QUARANTINE-001 — set PYTEST_RUN_QUARANTINED=1 to collect/run these modules.
QUARANTINE_REF = "REF-PRODTEST-QUARANTINE-001"
QUARANTINED_TEST_MODULES = frozenset(
    {
        "test_cms_site_builder",
        "test_team_cms_sharing",
        "test_blog_api",
        "test_enablement_engine",
        "test_prompt_manager",
        "test_prompt_manager_bridge_analytics",
        "test_clearform_templates_phase_d",
        "test_clearform_api",
        "test_new_features_iter50",
        "test_support_system",
        "test_clearform_organizations",
        "test_clearform_admin_pricing",
        "test_new_features_iter45",
        "test_clearform_p0_features",
        "test_clearform_phase_c",
        "test_analytics_schema_features",
        "test_automation_registry_alignment",
        "test_template_renderer",
        "test_lead_management_iter51",
    }
)


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "quarantine_legacy: excluded by default; see REF-PRODTEST-QUARANTINE-001 in conftest.py",
    )
    config.addinivalue_line(
        "markers",
        "integration: requires MongoDB (and optionally other local services); skips when unreachable",
    )


def pytest_collection_modifyitems(config, items):
    if os.getenv("PYTEST_RUN_QUARANTINED", "").strip().lower() in ("1", "true", "yes"):
        return
    reason = (
        f"QUARANTINE {QUARANTINE_REF}: CMS/blog/experimental/ClearForm/analytics; "
        "set PYTEST_RUN_QUARANTINED=1 to run."
    )
    skip_legacy = pytest.mark.skip(reason=reason)
    for item in items:
        mod = getattr(item, "module", None)
        if mod is None:
            continue
        short = getattr(mod, "__name__", "").rpartition(".")[-1]
        if short in QUARANTINED_TEST_MODULES:
            item.add_marker(skip_legacy)


# Base URL for HTTP requests in tests. Always includes scheme for CI (requests requires full URL).
# Used only by tests that call a live server; TestClient-based tests use the client fixture instead.
BASE_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")

# Shared TestClient: session-scoped so lifespan runs once (MongoDB stays up for integration tests).
from fastapi.testclient import TestClient
from server import app


@pytest.fixture
def client():
    """TestClient for in-process HTTP tests. Context manager ensures lifespan (Mongo + seeds) runs."""
    with TestClient(app) as c:
        yield c
