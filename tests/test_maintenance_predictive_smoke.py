"""
Smoke tests for maintenance and predictive maintenance APIs.
Run with: pytest tests/test_maintenance_predictive_smoke.py -v
Requires backend running. Optional: set ADMIN_TOKEN and CLIENT_TOKEN env for auth tests;
without tokens only unauthenticated behaviour is asserted.
"""
import os
import pytest
import requests

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or os.environ.get("BASE_URL") or "http://localhost:8000").rstrip("/")
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "").strip()
CLIENT_TOKEN = os.environ.get("CLIENT_TOKEN", "").strip()


def _headers(token):
    return {"Authorization": f"Bearer {token}"} if token else {}


class TestMaintenancePredictiveSmoke:
    """Smoke test: maintenance and predictive endpoints respond as expected."""

    def test_admin_work_orders_unauth_returns_401(self):
        r = requests.get(f"{BASE_URL}/api/admin/ops/work-orders", timeout=10)
        assert r.status_code in (401, 403), f"Expected 401/403, got {r.status_code}"

    def test_client_maintenance_work_orders_unauth_returns_401(self):
        r = requests.get(f"{BASE_URL}/api/client/maintenance/work-orders", timeout=10)
        assert r.status_code in (401, 403), f"Expected 401/403, got {r.status_code}"

    def test_client_predictive_insights_unauth_returns_401(self):
        r = requests.get(f"{BASE_URL}/api/client/maintenance/predictive-insights", timeout=10)
        assert r.status_code in (401, 403), f"Expected 401/403, got {r.status_code}"

    @pytest.mark.skipif(not ADMIN_TOKEN, reason="ADMIN_TOKEN not set")
    def test_admin_work_orders_with_admin_token_returns_200(self):
        r = requests.get(f"{BASE_URL}/api/admin/ops/work-orders", headers=_headers(ADMIN_TOKEN), timeout=10)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:200]}"
        data = r.json()
        assert "work_orders" in data

    @pytest.mark.skipif(not ADMIN_TOKEN, reason="ADMIN_TOKEN not set")
    def test_admin_contractors_with_admin_token_returns_200(self):
        r = requests.get(f"{BASE_URL}/api/admin/ops/contractors", headers=_headers(ADMIN_TOKEN), timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert "contractors" in data

    @pytest.mark.skipif(not CLIENT_TOKEN, reason="CLIENT_TOKEN not set")
    def test_client_maintenance_work_orders_with_client_token(self):
        r = requests.get(f"{BASE_URL}/api/client/maintenance/work-orders", headers=_headers(CLIENT_TOKEN), timeout=10)
        assert r.status_code in (200, 403), f"Expected 200 or 403 (if maintenance off), got {r.status_code}"
        if r.status_code == 200:
            data = r.json()
            assert "work_orders" in data

    @pytest.mark.skipif(not CLIENT_TOKEN, reason="CLIENT_TOKEN not set")
    def test_client_predictive_insights_with_client_token(self):
        r = requests.get(f"{BASE_URL}/api/client/maintenance/predictive-insights", headers=_headers(CLIENT_TOKEN), timeout=10)
        assert r.status_code in (200, 403), f"Expected 200 or 403 (if predictive off), got {r.status_code}"
        if r.status_code == 200:
            data = r.json()
            assert "client_id" in data
            assert "properties" in data
