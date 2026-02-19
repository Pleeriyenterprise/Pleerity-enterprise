"""
Tests for GET /api/intake/plans.

- Plans endpoint must NOT hard-fail (500) when Stripe env vars are missing
- Stripe mode mismatch in checkout returns 400 with error_code, not generic 500
"""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from server import app


@pytest.fixture
def client():
    return TestClient(app)


def test_intake_plans_returns_200_when_stripe_env_missing(client):
    """
    GET /api/intake/plans must return 200 with plans when STRIPE_TEST_PRICE_* is not set.
    Previously raised 500; fix allows plan display while checkout still fails with 400.
    """
    from services.plan_registry import StripeModeMismatchError

    with patch("services.plan_registry.get_stripe_price_mappings") as mock_get:
        mock_get.side_effect = StripeModeMismatchError(
            "Stripe key is test mode but STRIPE_TEST_PRICE_PLAN_1_SOLO_MONTHLY is not set",
            missing_var="STRIPE_TEST_PRICE_PLAN_1_SOLO_MONTHLY",
            stripe_mode="test",
        )
        response = client.get("/api/intake/plans")

    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    data = response.json()
    assert "plans" in data
    plans = data["plans"]
    assert len(plans) >= 1
    assert any(p.get("plan_id") == "PLAN_1_SOLO" for p in plans)
    assert any(p.get("max_properties") == 2 for p in plans)


def test_intake_plans_returns_200_with_plans_when_stripe_configured(client):
    """GET /api/intake/plans returns 200 with plan list when Stripe env is properly set."""
    with patch("services.plan_registry.get_stripe_price_mappings") as mock_get:
        mock_get.return_value = {
            "mappings": {
                "PLAN_1_SOLO": {"subscription_price_id": "price_xxx", "onboarding_price_id": "price_yyy"},
                "PLAN_2_PORTFOLIO": {"subscription_price_id": "price_a", "onboarding_price_id": "price_b"},
                "PLAN_3_PRO": {"subscription_price_id": "price_p", "onboarding_price_id": "price_q"},
            },
            "subscription_price_to_plan": {},
            "onboarding_price_to_plan": {},
        }
        response = client.get("/api/intake/plans")

    assert response.status_code == 200
    data = response.json()
    assert "plans" in data
    assert len(data["plans"]) == 3
