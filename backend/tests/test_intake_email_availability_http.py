"""HTTP tests for intake email availability (check-email) and duplicate enforcement on submit."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from pymongo.errors import DuplicateKeyError

from server import app
from utils.client_email import INTAKE_EMAIL_ALREADY_EXISTS_MESSAGE


@pytest.fixture
def client():
    return TestClient(app)


_INTAKE_SUBMIT_MIN = {
    "full_name": "A User",
    "email": "new@example.com",
    "client_type": "INDIVIDUAL",
    "preferred_contact": "EMAIL",
    "billing_plan": "PLAN_1_SOLO",
    "properties": [
        {
            "nickname": "Home",
            "postcode": "SW1A 1AA",
            "address_line_1": "10 Downing St",
            "city": "London",
            "property_type": "house",
            "jurisdiction": "England",
            "is_hmo": False,
            "tenancy_active": False,
            "deposit_taken": False,
            "has_communal_areas": False,
            "managed_by": "LANDLORD",
            "send_reminders_to": "LANDLORD",
            "cert_gas_safety": "YES",
            "cert_eicr": "YES",
            "cert_epc": "YES",
            "cert_licence": "N/A",
        }
    ],
    "document_submission_method": "UPLOAD",
    "consent_data_processing": True,
    "consent_service_boundary": True,
}


def test_check_email_available_returns_normalized_and_ok(client):
    with patch("routes.intake.rate_limiter.check_rate_limit", new_callable=AsyncMock) as rl:
        rl.return_value = (True, None)
        with patch("routes.intake.client_email_taken", new_callable=AsyncMock) as taken:
            taken.return_value = False
            r = client.post("/api/intake/check-email", json={"email": "  User@Example.COM "})
    assert r.status_code == 200
    d = r.json()
    assert d["available"] is True
    assert d["normalized_email"] == "user@example.com"
    assert d["reason_code"] == "OK"


def test_check_email_taken_matches_canonical_request(client):
    with patch("routes.intake.rate_limiter.check_rate_limit", new_callable=AsyncMock) as rl:
        rl.return_value = (True, None)
        with patch("routes.intake.client_email_taken", new_callable=AsyncMock) as taken:
            taken.return_value = True
            r = client.post("/api/intake/check-email", json={"email": "USER@EXAMPLE.COM"})
    assert r.status_code == 200
    d = r.json()
    assert d["available"] is False
    assert d["normalized_email"] == "user@example.com"
    assert d["reason_code"] == "EMAIL_TAKEN"


def test_submit_rejects_duplicate_before_crn_allocation(client):
    with patch("routes.intake.client_email_taken", new_callable=AsyncMock) as taken:
        taken.return_value = True
        with patch("routes.intake.get_next_crn", new_callable=AsyncMock) as crn:
            with patch("routes.intake.plan_registry.check_property_limit", return_value=(True, None, {})):
                r = client.post("/api/intake/submit", json=_INTAKE_SUBMIT_MIN)
    assert r.status_code == 400
    assert r.json()["detail"] == INTAKE_EMAIL_ALREADY_EXISTS_MESSAGE
    crn.assert_not_called()


def test_submit_duplicate_key_on_email_maps_to_same_message(client):
    dup = DuplicateKeyError(
        'E11000 duplicate key error collection: test.clients index: email_1 dup key: { email: "new@example.com" }',
        11000,
        {
            "code": 11000,
            "errmsg": 'E11000 duplicate key error collection: test.clients index: email_1 dup key: { email: "new@example.com" }',
            "keyPattern": {"email": 1},
        },
    )
    mock_db = MagicMock()
    mock_db.clients.insert_one = AsyncMock(side_effect=dup)
    mock_db.risk_leads = MagicMock()
    mock_db.risk_leads.update_one = AsyncMock()

    with patch("routes.intake.database.get_db", return_value=mock_db):
        with patch("routes.intake.client_email_taken", new_callable=AsyncMock) as taken:
            taken.return_value = False
            with patch("routes.intake.get_next_crn", AsyncMock(return_value="PLE-CVP-2026-00001")):
                with patch("routes.intake.plan_registry.check_property_limit", return_value=(True, None, {})):
                    with patch("routes.intake.create_audit_log", new_callable=AsyncMock):
                        r = client.post("/api/intake/submit", json=_INTAKE_SUBMIT_MIN)
    assert r.status_code == 400
    assert r.json()["detail"] == INTAKE_EMAIL_ALREADY_EXISTS_MESSAGE
