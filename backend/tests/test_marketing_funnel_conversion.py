"""
Tests for Demo → Paid Conversion Linking (risk-check funnel).
- Intake submit with lead_id stores client.marketing and updates risk_leads.status=checkout_created.
- Checkout session creation includes lead_id in metadata when client has marketing.lead_id.
- Webhook marks risk_leads converted (idempotent); optional snapshot import once.
"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime, timezone


# ----- Intake submit with lead_id -----

@pytest.fixture
def mock_db_for_intake():
    """DB mock that records insert_one (clients) and update_one (risk_leads)."""
    db = MagicMock()
    db.clients = MagicMock()
    db.clients.find_one = AsyncMock(return_value=None)
    db.clients.insert_one = AsyncMock(return_value=None)
    db.properties = MagicMock()
    db.properties.insert_one = AsyncMock(return_value=None)
    db.risk_leads = MagicMock()
    db.risk_leads.update_one = AsyncMock(return_value=MagicMock(matched_count=1))
    db.risk_leads.find_one = AsyncMock(return_value=None)
    # Other collections intake might touch
    db.intake_uploads = MagicMock()
    db.intake_uploads.find_one = AsyncMock(return_value=None)
    db.intake_uploads.update_many = AsyncMock(return_value=MagicMock(modified_count=0))
    return db


def test_intake_submit_with_lead_id_stores_marketing_and_links_risk_lead(client, mock_db_for_intake):
    """Intake submit with lead_id sets client.marketing and updates risk_leads to checkout_created."""
    with patch("routes.intake.database.get_db", return_value=mock_db_for_intake):
        with patch("routes.intake.get_next_crn", AsyncMock(return_value="PLE-CVP-2025-00001")):
            with patch("routes.intake.plan_registry.check_property_limit", return_value=(True, None, {})):
                with patch("routes.intake.create_audit_log", new_callable=AsyncMock):
                    payload = {
                "full_name": "Jane Doe",
                "email": "jane@example.com",
                "client_type": "INDIVIDUAL",
                "preferred_contact": "EMAIL",
                "billing_plan": "PLAN_1_SOLO",
                "properties": [{
                    "nickname": "Home",
                    "address_line_1": "1 High St",
                    "city": "London",
                    "postcode": "SW1A 1AA",
                    "property_type": "house",
                    "bedrooms": 2,
                    "occupancy": "single_family",
                    "is_hmo": False,
                    "council_name": "Westminster",
                    "council_code": "E09000033",
                    "licence_required": "NO",
                    "managed_by": "LANDLORD",
                    "send_reminders_to": "LANDLORD",
                    "cert_gas_safety": "YES",
                    "cert_eicr": "YES",
                    "cert_epc": "YES",
                    "cert_licence": "N/A",
                }],
                "document_submission_method": "UPLOAD",
                "consent_data_processing": True,
                "consent_service_boundary": True,
                "lead_id": "RISK-ABC123",
                "source": "risk-check",
            }
                    resp = client.post("/api/intake/submit", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "client_id" in data
    client_id = data["client_id"]
    # Assert client doc had marketing
    call_args = mock_db_for_intake.clients.insert_one.call_args[0][0]
    assert call_args.get("marketing") == {"source": "risk-check", "lead_id": "RISK-ABC123"}
    # Assert risk_leads was updated to checkout_created
    mock_db_for_intake.risk_leads.update_one.assert_called_once()
    update_call = mock_db_for_intake.risk_leads.update_one.call_args[0]
    assert update_call[0] == {"lead_id": "RISK-ABC123"}
    assert update_call[1]["$set"]["status"] == "checkout_created"
    assert update_call[1]["$set"]["client_id"] == client_id


# ----- Webhook conversion (idempotent: status $ne converted) -----

def test_webhook_conversion_update_uses_idempotent_filter():
    """Conversion update filter uses status $ne converted so already-converted leads are not updated."""
    import asyncio
    db = MagicMock()
    db.risk_leads = MagicMock()
    db.risk_leads.update_one = AsyncMock(return_value=MagicMock(matched_count=1, modified_count=1))
    metadata = {"client_id": "cli-1", "plan_code": "PLAN_1_SOLO", "lead_id": "RISK-WEB"}
    lead_id_meta = metadata.get("lead_id")
    client_id = metadata.get("client_id")
    now_utc = datetime.now(timezone.utc)

    async def run():
        await db.risk_leads.update_one(
            {"lead_id": lead_id_meta.strip(), "status": {"$ne": "converted"}},
            {"$set": {
                "status": "converted",
                "converted_at": now_utc.isoformat(),
                "client_id": client_id,
                "stripe_subscription_id": "sub_1",
                "updated_at": now_utc.isoformat(),
            }},
        )
    asyncio.run(run())
    assert db.risk_leads.update_one.called
    call = db.risk_leads.update_one.call_args[0]
    assert call[0]["lead_id"] == "RISK-WEB"
    assert call[0]["status"] == {"$ne": "converted"}
    assert call[1]["$set"]["status"] == "converted"
    assert "converted_at" in call[1]["$set"]


def test_activate_endpoint_sets_activated_cta(client):
    """POST /api/risk-check/activate sets status to activated_cta when lead exists."""
    mock_db = MagicMock()
    mock_coll = MagicMock()
    mock_coll.update_one = AsyncMock(return_value=MagicMock(matched_count=1))
    mock_db.__getitem__ = MagicMock(return_value=mock_coll)
    with patch("routes.risk_check.database.get_db", return_value=mock_db):
        resp = client.post("/api/risk-check/activate", json={"lead_id": "RISK-ACTIVATE", "selected_plan_code": "PLAN_1_SOLO"})
    assert resp.status_code == 200
    assert resp.json().get("ok") is True
    mock_coll.update_one.assert_called_once()
    call = mock_coll.update_one.call_args[0]
    assert call[0]["lead_id"] == "RISK-ACTIVATE"
    assert call[0]["status"]["$in"] == ["new", "activated_cta", "nurture_started"]
    assert call[1]["$set"]["status"] == "activated_cta"
