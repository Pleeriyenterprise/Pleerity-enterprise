"""Quote negotiation lifecycle (revision request, resubmit, approve, lineage)."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from services.work_order_pricing_constants import (
    PRICE_STATUS_APPROVED,
    PRICE_STATUS_AWAITING_QUOTE,
    PRICE_STATUS_QUOTED,
    PRICE_STATUS_REJECTED_FINAL,
    PRICE_STATUS_REVISION_REQUESTED,
    PRICING_MODE_MAINTENANCE_PREQUOTE,
)
from services.work_order_pricing_service import (
    approve_quote_for_work_order,
    derive_quote_presentation_state,
    reject_quote_final_for_work_order,
    reject_quote_for_work_order,
    request_quote_revision_for_work_order,
    serialize_pricing_snapshot,
    submit_quote_for_work_order,
)


def _wo(**overrides):
    base = {
        "work_order_id": "WO-QN-01",
        "client_id": "CL-1",
        "contractor_id": "CTR-1",
        "pricing_mode": PRICING_MODE_MAINTENANCE_PREQUOTE,
        "price_status": PRICE_STATUS_AWAITING_QUOTE,
        "quoted_price": None,
        "price_currency": "GBP",
        "quote_negotiation_history": [],
        "status": "SCHEDULED",
        "work_order_kind": "MAINTENANCE",
    }
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_submit_request_revision_resubmit_approve_lineage():
    wo_v1 = _wo()
    wo_quoted = {
        **wo_v1,
        "price_status": PRICE_STATUS_QUOTED,
        "quoted_price": 300.0,
        "quote_notes": "v1 notes",
        "quote_negotiation_history": [
            {
                "version": 1,
                "event": "submitted",
                "amount": 300.0,
                "currency": "GBP",
                "at": "2026-05-01T10:00:00+00:00",
                "actor_role": "contractor",
            }
        ],
    }
    wo_revision = {
        **wo_quoted,
        "price_status": PRICE_STATUS_REVISION_REQUESTED,
        "quote_revision_reason_code": "price_too_high",
        "quote_revision_message": "Please reduce",
        "quote_negotiation_history": wo_quoted["quote_negotiation_history"]
        + [
            {
                "version": 1,
                "event": "revision_requested",
                "amount": 300.0,
                "reason_code": "price_too_high",
                "message": "Please reduce",
                "at": "2026-05-01T11:00:00+00:00",
                "actor_role": "client",
            }
        ],
    }
    wo_resubmitted = {
        **wo_revision,
        "price_status": PRICE_STATUS_QUOTED,
        "quoted_price": 250.0,
        "quote_negotiation_history": wo_revision["quote_negotiation_history"]
        + [
            {
                "version": 2,
                "event": "resubmitted",
                "amount": 250.0,
                "currency": "GBP",
                "at": "2026-05-01T12:00:00+00:00",
                "actor_role": "contractor",
            }
        ],
    }

    wo_approved = {**wo_resubmitted, "price_status": PRICE_STATUS_APPROVED, "quote_approved_at": datetime.now(timezone.utc)}

    db = AsyncMock()
    db.work_orders.update_one = AsyncMock()
    db.contractors.find_one = AsyncMock(return_value={"email": "c@test.com", "name": "Contractor"})
    db.clients.find_one = AsyncMock(return_value={"contact_email": "l@test.com", "full_name": "Landlord"})
    db.contractor_job_tokens.insert_one = AsyncMock()

    with patch("services.work_order_pricing_service.database.get_db", return_value=db), patch(
        "services.work_order_pricing_service.create_audit_log", new_callable=AsyncMock
    ), patch(
        "services.work_order_pricing_service._fetch_wo",
        side_effect=[
            wo_v1,
            wo_quoted,
            wo_quoted,
            wo_revision,
            wo_revision,
            wo_resubmitted,
            wo_resubmitted,
            wo_approved,
        ],
    ), patch(
        "services.work_order_pricing_service._send_client_quote_review_email", new_callable=AsyncMock
    ), patch(
        "services.work_order_pricing_service._send_contractor_quote_revision_requested_email", new_callable=AsyncMock
    ), patch(
        "services.work_order_pricing_service._send_contractor_quote_approved_email", new_callable=AsyncMock
    ), patch(
        "services.invoice_service.maybe_send_contractor_invoice_ready_notification", new_callable=AsyncMock
    ):
        out1 = await submit_quote_for_work_order("WO-QN-01", "CTR-1", amount=300.0, notes="v1 notes")
        assert out1["price_status"] == PRICE_STATUS_QUOTED

        out2 = await request_quote_revision_for_work_order(
            "WO-QN-01",
            "CL-1",
            reason_code="price_too_high",
            message="Please reduce",
            actor_id="landlord",
        )
        assert out2["price_status"] == PRICE_STATUS_REVISION_REQUESTED
        assert out2.get("contractor_id") == "CTR-1"

        out3 = await submit_quote_for_work_order("WO-QN-01", "CTR-1", amount=250.0, notes="v2")
        assert out3["price_status"] == PRICE_STATUS_QUOTED
        assert out3["quoted_price"] == 250.0

        out4 = await approve_quote_for_work_order("WO-QN-01", "CL-1", actor_id="landlord")
        assert out4["price_status"] == PRICE_STATUS_APPROVED


@pytest.mark.asyncio
async def test_reject_quote_alias_requests_revision():
    wo = _wo(
        price_status=PRICE_STATUS_QUOTED,
        quoted_price=400.0,
        quote_negotiation_history=[{"version": 1, "event": "submitted", "amount": 400.0}],
    )
    wo_after = {**wo, "price_status": PRICE_STATUS_REVISION_REQUESTED, "quote_revision_reason_code": "other"}

    db = AsyncMock()
    db.work_orders.update_one = AsyncMock()
    db.contractors.find_one = AsyncMock(return_value={"email": "c@test.com"})

    with patch("services.work_order_pricing_service.database.get_db", return_value=db), patch(
        "services.work_order_pricing_service.create_audit_log", new_callable=AsyncMock
    ), patch(
        "services.work_order_pricing_service._fetch_wo", side_effect=[wo, wo_after]
    ), patch(
        "services.work_order_pricing_service._send_contractor_quote_revision_requested_email", new_callable=AsyncMock
    ):
        out = await reject_quote_for_work_order("WO-QN-01", "CL-1", reason="Too expensive", actor_id="landlord")
        assert out["price_status"] == PRICE_STATUS_REVISION_REQUESTED


@pytest.mark.asyncio
async def test_reject_final_does_not_clear_contractor():
    wo = _wo(
        price_status=PRICE_STATUS_QUOTED,
        quoted_price=500.0,
        quote_negotiation_history=[{"version": 1, "event": "submitted", "amount": 500.0}],
    )
    wo_after = {**wo, "price_status": PRICE_STATUS_REJECTED_FINAL, "contractor_id": "CTR-1"}

    db = AsyncMock()
    db.work_orders.update_one = AsyncMock()

    with patch("services.work_order_pricing_service.database.get_db", return_value=db), patch(
        "services.work_order_pricing_service.create_audit_log", new_callable=AsyncMock
    ), patch("services.work_order_pricing_service._fetch_wo", side_effect=[wo, wo_after]):
        out = await reject_quote_final_for_work_order("WO-QN-01", "CL-1", reason="Will reassign", actor_id="landlord")
        assert out["price_status"] == PRICE_STATUS_REJECTED_FINAL
        assert out.get("contractor_id") == "CTR-1"


def test_serialize_pricing_snapshot_includes_lineage():
    wo = _wo(
        price_status=PRICE_STATUS_REVISION_REQUESTED,
        quoted_price=300.0,
        quote_revision_reason_code="scope_unclear",
        quote_negotiation_history=[
            {"version": 1, "event": "submitted", "amount": 300.0, "at": datetime.now(timezone.utc)},
        ],
    )
    snap = serialize_pricing_snapshot(wo)
    assert snap["pricing_workflow"] is True
    assert snap["revision_active"] is True
    assert snap["negotiation_status_label"] == "Changes requested"
    assert snap["quote_presentation"]["key"] == "changes_requested"
    assert snap["quote_presentation"]["label"] == "Changes requested"
    assert len(snap["quote_negotiation_history"]) == 1


def test_derive_quote_presentation_state_lineage():
    awaiting = _wo()
    assert derive_quote_presentation_state(awaiting)["key"] == "quote_requested"
    quoted = _wo(
        price_status=PRICE_STATUS_QUOTED,
        quoted_price=185.0,
        quote_negotiation_history=[{"version": 1, "event": "submitted", "amount": 185.0}],
    )
    assert derive_quote_presentation_state(quoted)["label"] == "Quote submitted"
    assert derive_quote_presentation_state(quoted)["is_approved"] is False
    revision = {**quoted, "price_status": PRICE_STATUS_REVISION_REQUESTED}
    assert derive_quote_presentation_state(revision)["key"] == "changes_requested"
    revised = {
        **quoted,
        "quoted_price": 205.0,
        "quote_negotiation_history": quoted["quote_negotiation_history"]
        + [{"version": 2, "event": "resubmitted", "amount": 205.0}],
    }
    assert derive_quote_presentation_state(revised)["key"] == "revised_quote_submitted"
    approved = {**revised, "price_status": PRICE_STATUS_APPROVED}
    pres = derive_quote_presentation_state(approved)
    assert pres["key"] == "quote_approved"
    assert pres["is_approved"] is True
    assert pres["label"] == "Quote approved"
