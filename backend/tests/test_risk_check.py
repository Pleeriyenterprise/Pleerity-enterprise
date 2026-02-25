"""
API tests for /api/risk-check (preview, report). No provisioning, no Stripe.
Report tests mock DB when PYTEST_RUNNING (no MongoDB in test env).
"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock


VALID_PREVIEW_BODY = {
    "property_count": 2,
    "any_hmo": False,
    "gas_status": "Valid",
    "eicr_status": "Expired",
    "tracking_method": "Manual reminders",
}

VALID_REPORT_BODY = {
    **VALID_PREVIEW_BODY,
    "first_name": "Test",
    "email": "test-risk@example.com",
}


def _mock_db():
    """Fake DB so report endpoint can run without MongoDB."""
    m = MagicMock()
    m.__getitem__ = MagicMock(return_value=m)
    m.insert_one = AsyncMock(return_value=None)
    m.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
    m.find_one = AsyncMock(return_value=None)
    return m


def test_preview_returns_200_with_band_and_recommended_plan(client):
    """Preview returns 200 and includes risk_band and recommended_plan_code."""
    response = client.post("/api/risk-check/preview", json=VALID_PREVIEW_BODY)
    assert response.status_code == 200
    data = response.json()
    assert "risk_band" in data
    assert data["risk_band"] in ("LOW", "MODERATE", "HIGH")
    assert "recommended_plan_code" in data
    assert data["recommended_plan_code"] in ("PLAN_1_SOLO", "PLAN_2_PORTFOLIO", "PLAN_3_PRO")
    assert "blurred_score_hint" in data
    assert "flags_count" in data


def test_preview_recommended_plan_by_property_count(client):
    """recommended_plan_code: 1–2 -> SOLO, 3–10 -> PORTFOLIO, 11+ -> PRO."""
    r1 = client.post("/api/risk-check/preview", json={**VALID_PREVIEW_BODY, "property_count": 1})
    assert r1.status_code == 200
    assert r1.json()["recommended_plan_code"] == "PLAN_1_SOLO"
    r2 = client.post("/api/risk-check/preview", json={**VALID_PREVIEW_BODY, "property_count": 5})
    assert r2.status_code == 200
    assert r2.json()["recommended_plan_code"] == "PLAN_2_PORTFOLIO"
    r3 = client.post("/api/risk-check/preview", json={**VALID_PREVIEW_BODY, "property_count": 15})
    assert r3.status_code == 200
    assert r3.json()["recommended_plan_code"] == "PLAN_3_PRO"


def test_preview_missing_required_returns_422(client):
    """Missing required fields returns 422."""
    response = client.post("/api/risk-check/preview", json={"property_count": 1})
    assert response.status_code == 422


@patch("routes.risk_check.database.get_db")
@patch("routes.risk_check._send_risk_report_email", new_callable=AsyncMock, return_value=True)
def test_report_returns_200_and_lead_id(mock_send, mock_get_db, client):
    """Report returns 200 and includes lead_id; email send is invoked. Mock DB when None."""
    mock_get_db.return_value = _mock_db()
    response = client.post("/api/risk-check/report", json=VALID_REPORT_BODY)
    assert response.status_code == 200
    data = response.json()
    assert "lead_id" in data
    assert data["lead_id"].startswith("RISK-")
    assert data.get("recommended_plan_code") in ("PLAN_1_SOLO", "PLAN_2_PORTFOLIO", "PLAN_3_PRO")
    assert "score" in data
    assert "risk_band" in data
    mock_send.assert_called_once()
    call_args = mock_send.call_args[0][0]
    assert call_args.get("email") == "test-risk@example.com"
    assert call_args.get("first_name") == "Test"


def test_report_missing_required_returns_422(client):
    """Report with missing first_name or email returns 422."""
    r1 = client.post("/api/risk-check/report", json={**VALID_REPORT_BODY, "first_name": ""})
    assert r1.status_code == 422
    # Missing email field entirely
    r2 = client.post("/api/risk-check/report", json={**VALID_PREVIEW_BODY, "first_name": "A"})
    assert r2.status_code == 422


@patch("routes.risk_check.database.get_db")
def test_score_in_valid_range(mock_get_db, client):
    """Report score is in 0–100. Mock DB for report."""
    mock_get_db.return_value = _mock_db()
    with patch("routes.risk_check._send_risk_report_email", new_callable=AsyncMock, return_value=True):
        r2 = client.post("/api/risk-check/report", json=VALID_REPORT_BODY)
    assert r2.status_code == 200
    assert 0 <= r2.json()["score"] <= 100


@patch("routes.risk_check.database.get_db")
@patch("routes.risk_check._send_risk_report_email", new_callable=AsyncMock, return_value=True)
def test_report_does_not_create_client(mock_send, mock_get_db, client):
    """Report creates/updates lead only; no Client creation (writes go to risk_leads only)."""
    mock_get_db.return_value = _mock_db()
    # find_one returns None => new lead => insert_one called
    client.post("/api/risk-check/report", json=VALID_REPORT_BODY)
    mock_get_db.return_value.insert_one.assert_called_once()


@patch("routes.risk_check.database.get_db")
def test_lead_from_token_returns_200_with_sanitized_payload(mock_get_db, client):
    """GET lead-from-token returns 200 and intake-relevant fields only (no score/exposure)."""
    db_mock = MagicMock()
    fake_lead = {
        "lead_id": "RISK-ABC123",
        "email": "lead@example.com",
        "first_name": "Jane",
        "property_count": 3,
        "any_hmo": True,
        "gas_status": "Valid",
        "eicr_status": "Expired",
        "tracking_method": "Manual reminders",
        "computed_score": 45,
        "risk_band": "HIGH",
        "exposure_range_label": "High exposure",
    }
    coll_mock = MagicMock()
    coll_mock.find_one = AsyncMock(return_value=fake_lead)
    db_mock.__getitem__ = MagicMock(return_value=coll_mock)
    mock_get_db.return_value = db_mock
    with patch("utils.risk_lead_token.verify_lead_token", return_value="RISK-ABC123"):
        response = client.get("/api/risk-check/lead-from-token", params={"lead_token": "valid-token"})
    assert response.status_code == 200
    data = response.json()
    assert data["lead_id"] == "RISK-ABC123"
    assert data["email"] == "lead@example.com"
    assert data["first_name"] == "Jane"
    assert data["property_count"] == 3
    assert data["any_hmo"] is True
    assert "computed_score" not in data
    assert "risk_band" not in data
    assert "exposure_range_label" not in data


def test_lead_from_token_missing_token_returns_400(client):
    """GET lead-from-token without lead_token returns 400."""
    response = client.get("/api/risk-check/lead-from-token")
    assert response.status_code in (400, 422)


@patch("utils.risk_lead_token.verify_lead_token", return_value=None)
def test_lead_from_token_expired_or_invalid_returns_401(mock_verify, client):
    """GET lead-from-token with invalid/expired token returns 401."""
    response = client.get("/api/risk-check/lead-from-token", params={"lead_token": "bad-token"})
    assert response.status_code == 401
