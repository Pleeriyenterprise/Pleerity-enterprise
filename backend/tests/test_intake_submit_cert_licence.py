"""
POST /api/intake/submit accepts both cert_licence (primary) and cert_lincence (typo alias).
OpenAPI schema shows cert_licence. Includes test for exact production payload (200 + client_id + next_step).

Run from repo root: python -m pytest backend/tests/test_intake_submit_cert_licence.py -v
From backend dir: PYTHONPATH=. python -m pytest tests/test_intake_submit_cert_licence.py -v
(requires: pip install -r backend/requirements.txt)
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from server import app


def _make_db():
    db = MagicMock()
    db.clients.find_one = AsyncMock(return_value=None)
    db.clients.insert_one = AsyncMock()
    db.properties.insert_one = AsyncMock()
    db.documents.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[])))
    db.documents.update_one = AsyncMock()
    return db


def _minimal_intake_payload(property_overrides=None, email=None):
    base = {
        "full_name": "Test User",
        "email": email or "test_cert_licence@example.com",
        "client_type": "INDIVIDUAL",
        "company_name": None,
        "preferred_contact": "EMAIL",
        "phone": None,
        "billing_plan": "PLAN_1_SOLO",
        "document_submission_method": "UPLOAD",
        "email_upload_consent": False,
        "consent_data_processing": True,
        "consent_service_boundary": True,
        "properties": [
            {
                "nickname": "Prop",
                "postcode": "SW1A 1AA",
                "address_line_1": "10 Street",
                "address_line_2": "",
                "city": "London",
                "property_type": "house",
                "is_hmo": False,
                "bedrooms": 2,
                "occupancy": "single_family",
                "council_name": None,
                "council_code": None,
                "licence_required": "NO",
                "licence_type": None,
                "licence_status": None,
                "managed_by": "LANDLORD",
                "send_reminders_to": "LANDLORD",
                "agent_name": None,
                "agent_email": None,
                "agent_phone": None,
                "cert_gas_safety": "YES",
                "cert_eicr": "YES",
                "cert_epc": "YES",
            }
        ],
    }
    if property_overrides:
        base["properties"][0].update(property_overrides)
    return base


@pytest.fixture
def client():
    return TestClient(app)


def test_submit_accepts_cert_licence_returns_200(client):
    """POST /api/intake/submit with properties[].cert_licence (primary name) returns 200."""
    payload = _minimal_intake_payload({"cert_licence": "YES"}, email="test_cert_licence_primary@example.com")
    with patch("routes.intake.database.get_db", return_value=_make_db()):
        with patch("routes.intake.create_audit_log", new_callable=AsyncMock):
            with patch("routes.intake.get_next_crn", new_callable=AsyncMock, return_value="PLE-CVP-2026-000001"):
                response = client.post("/api/intake/submit", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "client_id" in data
    assert data.get("next_step") == "checkout"
    assert data.get("customer_reference") == "PLE-CVP-2026-000001"


def test_submit_accepts_cert_lincence_typo_returns_200(client):
    """POST /api/intake/submit with properties[].cert_lincence (typo alias) returns 200 for backward compatibility."""
    payload = _minimal_intake_payload({"cert_lincence": "YES"}, email="test_cert_lincence_alias@example.com")
    with patch("routes.intake.database.get_db", return_value=_make_db()):
        with patch("routes.intake.create_audit_log", new_callable=AsyncMock):
            with patch("routes.intake.get_next_crn", new_callable=AsyncMock, return_value="PLE-CVP-2026-000002"):
                response = client.post("/api/intake/submit", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "client_id" in data
    assert data.get("next_step") == "checkout"
    assert data.get("customer_reference") == "PLE-CVP-2026-000002"


# Exact production payload that previously caused 500 SUBMIT_FAILED (integer validation).
# council_code "S12000029" and bedrooms 1 must be accepted; response must be 200.
PRODUCTION_PAYLOAD = {
    "full_name": "dxzdz",
    "email": "drjpane@gmail.com",
    "client_type": "INDIVIDUAL",
    "company_name": "",
    "preferred_contact": "EMAIL",
    "phone": "",
    "billing_plan": "PLAN_1_SOLO",
    "properties": [
        {
            "nickname": "Verdant",
            "postcode": "G73 4BA",
            "address_line_1": "261 main street",
            "address_line_2": "Main Street",
            "city": "Rutherglen",
            "property_type": "house",
            "is_hmo": False,
            "bedrooms": 1,
            "occupancy": "single_family",
            "council_name": "",
            "council_code": "S12000029",
            "licence_required": "",
            "licence_type": "",
            "licence_status": "",
            "managed_by": "LANDLORD",
            "send_reminders_to": "LANDLORD",
            "agent_name": "",
            "agent_email": "",
            "agent_phone": "",
            "cert_gas_safety": "YES",
            "cert_eicr": "NO",
            "cert_epc": "YES",
            "cert_licence": "",
        }
    ],
    "document_submission_method": "EMAIL",
    "email_upload_consent": True,
    "consent_data_processing": True,
    "consent_service_boundary": True,
    "intake_session_id": "fb8f1747-a399-4c19-84f6-5aa0f02ddbc1",
}


def test_submit_exact_production_payload_returns_200(client):
    """POST /api/intake/submit with exact production payload returns 200 with client_id and next_step checkout."""
    import copy
    payload = copy.deepcopy(PRODUCTION_PAYLOAD)
    payload["email"] = "test_production_payload@example.com"
    with patch("routes.intake.database.get_db", return_value=_make_db()):
        with patch("routes.intake.create_audit_log", new_callable=AsyncMock):
            with patch("routes.intake.get_next_crn", new_callable=AsyncMock, return_value="PLE-CVP-2026-000003"):
                response = client.post("/api/intake/submit", json=payload)
    assert response.status_code == 200, response.text
    data = response.json()
    assert "client_id" in data
    assert data.get("next_step") == "checkout"
    assert data.get("customer_reference") == "PLE-CVP-2026-000003"


def test_submit_sets_customer_reference_before_insert(client):
    """customer_reference is set before client insert and returned in response (never null)."""
    payload = _minimal_intake_payload(email="test_crn_insert@example.com")
    mock_db = _make_db()
    with patch("routes.intake.database.get_db", return_value=mock_db):
        with patch("routes.intake.create_audit_log", new_callable=AsyncMock):
            with patch("routes.intake.get_next_crn", new_callable=AsyncMock, return_value="PLE-CVP-2026-000099"):
                response = client.post("/api/intake/submit", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data.get("customer_reference") == "PLE-CVP-2026-000099"
    # Client document inserted must contain customer_reference
    insert_calls = mock_db.clients.insert_one.call_args_list
    assert len(insert_calls) >= 1
    inserted_doc = insert_calls[0][0][0]
    assert inserted_doc.get("customer_reference") == "PLE-CVP-2026-000099"
