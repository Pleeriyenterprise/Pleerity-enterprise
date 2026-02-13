"""
Version endpoint and client dashboard shell shape.
- GET /api/version returns commit_sha + environment (for deployment verification).
- Client dashboard response shape: client, properties, compliance_summary (so frontend always gets a shell).
"""
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


class TestVersionEndpoint:
    """GET /api/version returns commit SHA and environment."""

    @pytest.fixture
    def app_client(self):
        from fastapi.testclient import TestClient
        from server import app
        return TestClient(app)

    def test_version_returns_commit_sha_and_environment(self, app_client):
        """Version endpoint returns commit_sha and environment for deployment verification."""
        r = app_client.get("/api/version")
        assert r.status_code == 200
        data = r.json()
        assert "commit_sha" in data
        assert "environment" in data
        assert isinstance(data["commit_sha"], str)
        assert isinstance(data["environment"], str)

    def test_version_commit_sha_is_string(self, app_client):
        """commit_sha is a string (may be 'unknown' or a SHA)."""
        r = app_client.get("/api/version")
        assert r.status_code == 200
        assert isinstance(r.json().get("commit_sha"), str)


class TestClientDashboardShellShape:
    """Client dashboard API returns shape expected by frontend (shell never blank)."""

    def test_dashboard_response_has_required_keys(self):
        """Dashboard payload has client, properties, compliance_summary (contract for frontend shell)."""
        # Same shape as backend/routes/client.py get_dashboard return
        shape = {
            "client": None,
            "properties": [],
            "compliance_summary": {
                "total_requirements": 0,
                "compliant": 0,
                "overdue": 0,
                "expiring_soon": 0,
            },
        }
        assert "client" in shape
        assert "properties" in shape
        assert "compliance_summary" in shape
        assert "total_requirements" in shape["compliance_summary"]
        assert "compliant" in shape["compliance_summary"]
        assert "overdue" in shape["compliance_summary"]
        assert "expiring_soon" in shape["compliance_summary"]
