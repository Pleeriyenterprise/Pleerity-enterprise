"""Keep frontend and backend domain_labels.json identical (single source of truth)."""
import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def api_client():
    os.environ.setdefault("PYTEST_RUNNING", "1")
    from server import app

    return TestClient(app)


def test_domain_labels_json_matches_frontend_mirror():
    backend_path = Path(__file__).resolve().parent.parent / "presentation" / "domain_labels.json"
    frontend_path = (
        Path(__file__).resolve().parent.parent.parent
        / "frontend"
        / "src"
        / "domain"
        / "domain_labels.json"
    )
    assert backend_path.is_file(), f"Missing {backend_path}"
    assert frontend_path.is_file(), f"Missing {frontend_path}"
    with open(backend_path, encoding="utf-8") as f:
        a = json.load(f)
    with open(frontend_path, encoding="utf-8") as f:
        b = json.load(f)
    assert a == b


def test_public_presentation_domain_labels_matches_canonical(api_client):
    backend_path = Path(__file__).resolve().parent.parent / "presentation" / "domain_labels.json"
    with open(backend_path, encoding="utf-8") as f:
        expected = json.load(f)
    r = api_client.get("/api/public/presentation/domain-labels")
    assert r.status_code == 200
    assert r.json() == expected


def test_label_service_enriches_risk_signal():
    from presentation.label_service import enrich_risk_signal

    s = {
        "risk_type": "SLA Breach Risk",
        "recommended_action": "Legacy stored text",
    }
    enrich_risk_signal(s)
    assert s.get("risk_type_label_client") == "Response time exceeded"
    assert s.get("recommended_action_client")
    assert "risk_type_label_admin" in s
