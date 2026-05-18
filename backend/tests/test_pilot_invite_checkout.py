"""
Founding pilot invite checkout — validation, Stripe session discounts, webhook tagging, idempotent usage.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from server import app
from services.pilot_invite_service import (
    COL_CODES,
    COL_REDEMPTIONS,
    build_checkout_pilot_metadata,
    complete_redemption_after_provisioning,
    discount_config_from_doc,
    maybe_record_pilot_cancelled_before_paid,
    maybe_record_pilot_paid_transition,
    normalize_invite_code,
    payment_method_collection_for_pilot,
    validate_invite_for_checkout,
)
from models.pilot_invite import PilotInvitePublicError, PilotInviteCodeCreate, PilotInviteDiscountDuration


@pytest.fixture
def client():
    return TestClient(app)


def _active_invite_doc(**overrides):
    now = datetime.now(timezone.utc)
    doc = {
        "invite_code_id": "inv-test-001",
        "code": "PILOTTEST",
        "status": "active",
        "program_type": "FOUNDING_PILOT",
        "applies_to_plan_codes": ["PLAN_1_SOLO", "PLAN_2_PORTFOLIO", "PLAN_3_PRO"],
        "max_uses": 5,
        "used_count": 0,
        "expires_at": now + timedelta(days=30),
        "email_restriction": None,
        "stripe_coupon_id": "coupon_test_100",
        "stripe_promotion_code_id": None,
        "discount_mode": "coupon",
        "discount_type": "percent",
        "discount_percent": 100,
        "discount_duration": "repeating",
        "discount_duration_in_months": 2,
        "waive_onboarding_fee": True,
        "onboarding_fee_policy": "waived",
    }
    doc.update(overrides)
    return doc


@pytest.mark.asyncio
async def test_validate_invite_success():
    doc = _active_invite_doc()
    mock_db = MagicMock()
    mock_db[COL_CODES].find_one = AsyncMock(return_value=doc)
    with patch("services.pilot_invite_service.database.get_db", return_value=mock_db):
        invite_doc, resp = await validate_invite_for_checkout(
            code="pilottest",
            plan_code="PLAN_1_SOLO",
            email="pilot@example.com",
            for_checkout=True,
        )
    assert resp.valid is True
    assert resp.discount_applied is True
    assert resp.expected_transition_to_paid is True
    assert resp.discount_duration_in_months == 2
    assert resp.headline
    assert "2 months" in (resp.detail or "")
    assert invite_doc["code"] == "PILOTTEST"


@pytest.mark.asyncio
async def test_validate_invite_invalid_code():
    mock_db = MagicMock()
    mock_db[COL_CODES].find_one = AsyncMock(return_value=None)
    with patch("services.pilot_invite_service.database.get_db", return_value=mock_db):
        with pytest.raises(PilotInvitePublicError) as exc:
            await validate_invite_for_checkout(code="NOPE", plan_code="PLAN_1_SOLO")
    assert exc.value.error_code == "PILOT_INVITE_INVALID"


@pytest.mark.asyncio
async def test_validate_invite_expired():
    doc = _active_invite_doc(expires_at=datetime.now(timezone.utc) - timedelta(days=1))
    mock_db = MagicMock()
    mock_db[COL_CODES].find_one = AsyncMock(return_value=doc)
    with patch("services.pilot_invite_service.database.get_db", return_value=mock_db):
        with pytest.raises(PilotInvitePublicError) as exc:
            await validate_invite_for_checkout(code="PILOTTEST", plan_code="PLAN_1_SOLO")
    assert exc.value.error_code == "PILOT_INVITE_EXPIRED"


@pytest.mark.asyncio
async def test_validate_invite_exhausted():
    doc = _active_invite_doc(used_count=5, max_uses=5)
    mock_db = MagicMock()
    mock_db[COL_CODES].find_one = AsyncMock(return_value=doc)
    with patch("services.pilot_invite_service.database.get_db", return_value=mock_db):
        with pytest.raises(PilotInvitePublicError) as exc:
            await validate_invite_for_checkout(code="PILOTTEST", plan_code="PLAN_1_SOLO")
    assert exc.value.error_code == "PILOT_INVITE_EXHAUSTED"


@pytest.mark.asyncio
async def test_validate_invite_plan_not_eligible():
    doc = _active_invite_doc(applies_to_plan_codes=["PLAN_3_PRO"])
    mock_db = MagicMock()
    mock_db[COL_CODES].find_one = AsyncMock(return_value=doc)
    with patch("services.pilot_invite_service.database.get_db", return_value=mock_db):
        with pytest.raises(PilotInvitePublicError) as exc:
            await validate_invite_for_checkout(code="PILOTTEST", plan_code="PLAN_1_SOLO")
    assert exc.value.error_code == "PILOT_INVITE_PLAN_NOT_ELIGIBLE"


@pytest.mark.asyncio
async def test_validate_invite_email_restriction():
    doc = _active_invite_doc(email_restriction="allowed@example.com")
    mock_db = MagicMock()
    mock_db[COL_CODES].find_one = AsyncMock(return_value=doc)
    with patch("services.pilot_invite_service.database.get_db", return_value=mock_db):
        with pytest.raises(PilotInvitePublicError) as exc:
            await validate_invite_for_checkout(
                code="PILOTTEST",
                plan_code="PLAN_1_SOLO",
                email="other@example.com",
            )
    assert exc.value.error_code == "PILOT_INVITE_EMAIL_NOT_ELIGIBLE"


@pytest.mark.asyncio
async def test_complete_redemption_idempotent():
    """Second call for same checkout_session_id must not double-increment used_count."""
    state = {"redemption_status": "pending"}
    redemption = {
        "invite_code_id": "inv-test-001",
        "code": "PILOTTEST",
        "checkout_session_id": "cs_pilot_001",
        "status": "pending",
    }
    mock_redemptions = MagicMock()
    mock_codes = MagicMock()
    mock_db = MagicMock()

    def db_getitem(key):
        if key == COL_REDEMPTIONS:
            return mock_redemptions
        if key == COL_CODES:
            return mock_codes
        return MagicMock()

    mock_db.__getitem__ = MagicMock(side_effect=db_getitem)

    async def find_one_and_update_redemption(filter_doc, update, **kw):
        if filter_doc.get("status") != "pending" or state["redemption_status"] != "pending":
            return None
        state["redemption_status"] = "completed"
        redemption["status"] = "completed"
        return dict(redemption)

    async def find_one_redemption(filter_doc, projection=None):
        if filter_doc.get("status") == "completed":
            return redemption
        return None

    mock_redemptions.find_one_and_update = AsyncMock(side_effect=find_one_and_update_redemption)
    mock_redemptions.find_one = AsyncMock(side_effect=find_one_redemption)
    mock_codes.find_one_and_update = AsyncMock(return_value=_active_invite_doc(used_count=1))

    with patch("services.pilot_invite_service.database.get_db", return_value=mock_db):
        ok1 = await complete_redemption_after_provisioning(checkout_session_id="cs_pilot_001")
        ok2 = await complete_redemption_after_provisioning(checkout_session_id="cs_pilot_001")

    assert ok1 is True
    assert ok2 is True
    assert mock_codes.find_one_and_update.await_count == 1


def test_checkout_with_valid_pilot_invite_passes_discount_doc(client):
    mock_db = MagicMock()
    mock_db.clients.find_one = AsyncMock(
        return_value={
            "client_id": "test-client-pilot",
            "billing_plan": "PLAN_1_SOLO",
            "email": "pilot@example.com",
            "contact_email": None,
        }
    )
    pilot_doc = _active_invite_doc()

    with patch("routes.intake.database.get_db", return_value=mock_db):
        with patch("routes.intake.create_audit_log", new_callable=AsyncMock):
            with patch(
                "routes.intake.validate_acceptance_for_checkout",
                new_callable=AsyncMock,
                return_value=({"template_id": "t1", "template_version_id": "v1"}, None),
            ):
                with patch(
                    "routes.intake.validate_invite_for_checkout",
                    new_callable=AsyncMock,
                    return_value=(pilot_doc, MagicMock(valid=True)),
                ) as mock_validate:
                    with patch("routes.intake.stripe_service") as mock_stripe:
                        mock_stripe.create_checkout_session = AsyncMock(
                            return_value={
                                "checkout_url": "https://checkout.stripe.com/test",
                                "session_id": "cs_pilot_test",
                            }
                        )
                        mock_stripe.expire_checkout_session = AsyncMock()
                        with patch(
                            "routes.intake.mark_acceptance_checkout_started",
                            new_callable=AsyncMock,
                        ):
                            response = client.post(
                                "/api/intake/checkout",
                                params={"client_id": "test-client-pilot"},
                                headers={"origin": "https://example.com"},
                                json={
                                    "acceptance_id": "acc-pilot-1",
                                    "invite_code": "PILOTTEST",
                                },
                            )
    assert response.status_code == 200
    assert mock_validate.await_count >= 1
    call_kwargs = mock_stripe.create_checkout_session.call_args.kwargs
    assert call_kwargs.get("pilot_invite_doc") == pilot_doc


def test_checkout_without_invite_unchanged(client):
    mock_db = MagicMock()
    mock_db.clients.find_one = AsyncMock(
        return_value={
            "client_id": "test-client-paid",
            "billing_plan": "PLAN_1_SOLO",
            "email": "paid@example.com",
        }
    )
    with patch("routes.intake.database.get_db", return_value=mock_db):
        with patch("routes.intake.create_audit_log", new_callable=AsyncMock):
            with patch(
                "routes.intake.validate_acceptance_for_checkout",
                new_callable=AsyncMock,
                return_value=({"template_id": "t1", "template_version_id": "v1"}, None),
            ):
                with patch("routes.intake.stripe_service") as mock_stripe:
                    mock_stripe.create_checkout_session = AsyncMock(
                        return_value={
                            "checkout_url": "https://checkout.stripe.com/test",
                            "session_id": "cs_paid",
                        }
                    )
                    with patch(
                        "routes.intake.mark_acceptance_checkout_started",
                        new_callable=AsyncMock,
                    ):
                        response = client.post(
                            "/api/intake/checkout",
                            params={"client_id": "test-client-paid"},
                            headers={"origin": "https://example.com"},
                            json={"acceptance_id": "acc-paid-1"},
                        )
    assert response.status_code == 200
    assert mock_stripe.create_checkout_session.call_args.kwargs.get("pilot_invite_doc") is None


def test_checkout_rejects_invalid_pilot_invite(client):
    mock_db = MagicMock()
    mock_db.clients.find_one = AsyncMock(
        return_value={
            "client_id": "test-client-bad-invite",
            "billing_plan": "PLAN_1_SOLO",
            "email": "x@example.com",
        }
    )
    with patch("routes.intake.database.get_db", return_value=mock_db):
        with patch("routes.intake.create_audit_log", new_callable=AsyncMock):
            with patch(
                "routes.intake.validate_acceptance_for_checkout",
                new_callable=AsyncMock,
                return_value=({"template_id": "t1", "template_version_id": "v1"}, None),
            ):
                with patch("routes.intake.stripe_service") as mock_stripe:
                    with patch(
                        "routes.intake.validate_invite_for_checkout",
                        new_callable=AsyncMock,
                        side_effect=PilotInvitePublicError("PILOT_INVITE_INVALID", "This invite code is not valid."),
                    ):
                        response = client.post(
                            "/api/intake/checkout",
                            params={"client_id": "test-client-bad-invite"},
                            headers={"origin": "https://example.com"},
                            json={"acceptance_id": "acc-1", "invite_code": "BAD"},
                        )
    assert response.status_code == 400
    assert response.json()["detail"]["error_code"] == "PILOT_INVITE_INVALID"
    mock_stripe.create_checkout_session.assert_not_called()


def test_validate_endpoint_returns_safe_invalid_response(client):
    with patch(
        "routes.intake.validate_invite_for_checkout",
        new_callable=AsyncMock,
        side_effect=PilotInvitePublicError("PILOT_INVITE_EXPIRED", "This invite code has expired."),
    ):
        response = client.post(
            "/api/intake/pilot-invite/validate",
            json={"code": "OLD", "plan_code": "PLAN_1_SOLO", "email": "a@b.com"},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is False
    assert "expired" in body["message"].lower()


def test_normalize_invite_code():
    assert normalize_invite_code("  pilot-test  ") == "PILOT-TEST"


def test_discount_config_repeating_vs_forever():
    repeating = discount_config_from_doc(_active_invite_doc())
    assert repeating["expected_transition_to_paid"] is True
    assert repeating["discount_duration_in_months"] == 2
    forever = discount_config_from_doc(
        _active_invite_doc(discount_duration="forever", discount_duration_in_months=None)
    )
    assert forever["expected_transition_to_paid"] is False


def test_payment_method_collection_always_for_repeating():
    assert payment_method_collection_for_pilot(_active_invite_doc()) == "always"
    assert (
        payment_method_collection_for_pilot(
            _active_invite_doc(discount_duration="forever", discount_duration_in_months=None)
        )
        == "if_required"
    )


def test_checkout_metadata_includes_pilot_discount_months():
    meta = build_checkout_pilot_metadata(_active_invite_doc(), plan_code="PLAN_1_SOLO")
    assert meta["pilot_discount_months"] == "2"
    assert meta["pilot_duration_months"] == "2"
    assert meta["expected_transition_to_paid"] == "true"
    assert meta["selected_plan_code"] == "PLAN_1_SOLO"


def test_pilot_checkout_metadata_onboarding_via_resolve():
    from services.pilot_onboarding_fee import resolve_checkout_onboarding

    _, policy, onb_meta = resolve_checkout_onboarding(
        pilot_invite_doc=_active_invite_doc(),
        plan_code="PLAN_1_SOLO",
        already_paid=False,
        onboarding_price_id="price_onboard",
    )
    assert policy.value == "waived"
    assert onb_meta["onboarding_fee_waived"] == "true"


def test_pilot_invite_create_rejects_invalid_duration_combo():
    with pytest.raises(ValueError, match="duration_in_months"):
        PilotInviteCodeCreate(
            code="BAD1",
            stripe_coupon_id="c1",
            discount_duration=PilotInviteDiscountDuration.FOREVER,
            discount_duration_in_months=2,
        )


@pytest.mark.asyncio
async def test_maybe_record_pilot_paid_transition_idempotent():
    with patch(
        "services.pilot_lifecycle_service.record_stripe_paid_transition",
        new_callable=AsyncMock,
        side_effect=[True, False],
    ) as mock_record:
        ok = await maybe_record_pilot_paid_transition(
            client_id="c1",
            invoice={"id": "in_paid_1", "amount_paid": 1900},
        )
        ok2 = await maybe_record_pilot_paid_transition(
            client_id="c1",
            invoice={"id": "in_paid_2", "amount_paid": 1900},
        )
    assert ok is True
    assert ok2 is False
    assert mock_record.await_count == 2


@pytest.mark.asyncio
async def test_zero_invoice_does_not_mark_pilot_paid():
    with patch(
        "services.pilot_lifecycle_service.record_stripe_paid_transition",
        new_callable=AsyncMock,
        return_value=False,
    ) as mock_record:
        ok = await maybe_record_pilot_paid_transition(
            client_id="c1",
            invoice={"id": "in_zero", "amount_paid": 0},
        )
    assert ok is False
    mock_record.assert_awaited_once()


@pytest.mark.asyncio
async def test_maybe_record_pilot_cancelled_before_paid():
    with patch(
        "services.pilot_lifecycle_service.record_stripe_cancelled_before_paid",
        new_callable=AsyncMock,
        return_value=True,
    ) as mock_record:
        ok = await maybe_record_pilot_cancelled_before_paid(client_id="c1")
    assert ok is True
    mock_record.assert_awaited_once()
