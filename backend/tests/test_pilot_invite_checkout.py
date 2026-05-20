"""
Founding pilot invite checkout — validation, Stripe session discounts, webhook tagging, idempotent usage.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict
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


def _async_empty_cursor():
    """Empty async iterator for Mongo find() mocks."""

    class _Cursor:
        def sort(self, *args, **kwargs):
            return self

        def limit(self, *args, **kwargs):
            return self

        async def to_list(self, length=None):
            return []

        def __aiter__(self):
            return self

        async def __anext__(self):
            raise StopAsyncIteration

    return _Cursor()


def _fake_db_for_invite(doc, *, redemption_count=0, client_row=None):
    fdb: Dict[str, Any] = {}
    fdb[COL_CODES] = MagicMock()
    fdb[COL_CODES].find_one = AsyncMock(return_value=doc)
    fdb[COL_REDEMPTIONS] = MagicMock()
    fdb[COL_REDEMPTIONS].count_documents = AsyncMock(return_value=redemption_count)
    fdb[COL_REDEMPTIONS].update_many = AsyncMock(return_value=MagicMock(modified_count=0))
    fdb["pilot_redemption_eligibility_overrides"] = MagicMock()
    fdb["pilot_redemption_eligibility_overrides"].find = MagicMock(return_value=_async_empty_cursor())
    fdb["pilot_invite_validation_attempts"] = MagicMock()
    fdb["pilot_invite_validation_attempts"].insert_one = AsyncMock()
    fdb["clients"] = MagicMock()
    fdb["clients"].find_one = AsyncMock(return_value=client_row)
    fdb["clients"].find = MagicMock(return_value=_async_empty_cursor())
    return fdb


@pytest.mark.asyncio
async def test_validate_invite_success():
    doc = _active_invite_doc()
    fdb = _fake_db_for_invite(doc)
    with patch("services.pilot_invite_service.database.get_db", return_value=fdb):
        with patch("utils.audit.create_audit_log", new_callable=AsyncMock):
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
    fdb = _fake_db_for_invite(None)
    fdb[COL_CODES].find_one = AsyncMock(return_value=None)
    with patch("services.pilot_invite_service.database.get_db", return_value=fdb):
        with patch("utils.audit.create_audit_log", new_callable=AsyncMock):
            with pytest.raises(PilotInvitePublicError) as exc:
                await validate_invite_for_checkout(code="NOPE", plan_code="PLAN_1_SOLO")
    assert exc.value.error_code == "PILOT_INVITE_INVALID"


@pytest.mark.asyncio
async def test_validate_invite_expired():
    doc = _active_invite_doc(expires_at=datetime.now(timezone.utc) - timedelta(days=1))
    fdb = _fake_db_for_invite(doc)
    with patch("services.pilot_invite_service.database.get_db", return_value=fdb):
        with patch("utils.audit.create_audit_log", new_callable=AsyncMock):
            with pytest.raises(PilotInvitePublicError) as exc:
                await validate_invite_for_checkout(code="PILOTTEST", plan_code="PLAN_1_SOLO")
    assert exc.value.error_code == "PILOT_INVITE_EXPIRED"


@pytest.mark.asyncio
async def test_validate_invite_exhausted():
    doc = _active_invite_doc(used_count=5, max_uses=5)
    fdb = _fake_db_for_invite(doc)
    with patch("services.pilot_invite_service.database.get_db", return_value=fdb):
        with patch("utils.audit.create_audit_log", new_callable=AsyncMock):
            with pytest.raises(PilotInvitePublicError) as exc:
                await validate_invite_for_checkout(code="PILOTTEST", plan_code="PLAN_1_SOLO")
    assert exc.value.error_code == "PILOT_INVITE_EXHAUSTED"


@pytest.mark.asyncio
async def test_validate_invite_plan_not_eligible():
    doc = _active_invite_doc(applies_to_plan_codes=["PLAN_3_PRO"])
    fdb = _fake_db_for_invite(doc)
    with patch("services.pilot_invite_service.database.get_db", return_value=fdb):
        with patch("utils.audit.create_audit_log", new_callable=AsyncMock):
            with pytest.raises(PilotInvitePublicError) as exc:
                await validate_invite_for_checkout(code="PILOTTEST", plan_code="PLAN_1_SOLO")
    assert exc.value.error_code == "PILOT_INVITE_PLAN_NOT_ELIGIBLE"


@pytest.mark.asyncio
async def test_validate_invite_email_restriction():
    doc = _active_invite_doc(email_restriction="allowed@example.com")
    fdb = _fake_db_for_invite(doc)
    with patch("services.pilot_invite_service.database.get_db", return_value=fdb):
        with patch("utils.audit.create_audit_log", new_callable=AsyncMock):
            with pytest.raises(PilotInvitePublicError) as exc:
                await validate_invite_for_checkout(
                    code="PILOTTEST",
                    plan_code="PLAN_1_SOLO",
                    email="other@example.com",
                )
    assert exc.value.error_code == "PILOT_INVITE_EMAIL_NOT_ELIGIBLE"


@pytest.mark.asyncio
async def test_public_promo_manual_entry_requires_is_publicly_enterable():
    doc = _active_invite_doc(
        code_type="public_promo",
        public_entry_enabled=True,
        campaign_status="active",
        is_publicly_enterable=False,
    )
    fdb = _fake_db_for_invite(doc)
    with patch("services.pilot_invite_service.database.get_db", return_value=fdb):
        with patch("utils.audit.create_audit_log", new_callable=AsyncMock):
            with pytest.raises(PilotInvitePublicError) as exc:
                await validate_invite_for_checkout(
                    code="PILOTTEST",
                    plan_code="PLAN_1_SOLO",
                    email="a@b.com",
                    entry_channel="manual",
                )
    assert exc.value.error_code == "PILOT_INVITE_PUBLIC_ENTRY_DISABLED"


@pytest.mark.asyncio
async def test_public_promo_link_skips_is_publicly_enterable():
    doc = _active_invite_doc(
        code_type="public_promo",
        public_entry_enabled=True,
        campaign_status="active",
        is_publicly_enterable=False,
    )
    fdb = _fake_db_for_invite(doc)
    with patch("services.pilot_invite_service.database.get_db", return_value=fdb):
        with patch("utils.audit.create_audit_log", new_callable=AsyncMock):
            _, resp = await validate_invite_for_checkout(
                code="PILOTTEST",
                plan_code="PLAN_1_SOLO",
                email="a@b.com",
                for_checkout=True,
                entry_channel="link",
            )
    assert resp.valid is True


@pytest.mark.asyncio
async def test_public_promo_public_entry_master_disabled():
    doc = _active_invite_doc(
        code_type="public_promo",
        public_entry_enabled=False,
        campaign_status="active",
        is_publicly_enterable=True,
    )
    fdb = _fake_db_for_invite(doc)
    with patch("services.pilot_invite_service.database.get_db", return_value=fdb):
        with patch("utils.audit.create_audit_log", new_callable=AsyncMock):
            with pytest.raises(PilotInvitePublicError) as exc:
                await validate_invite_for_checkout(
                    code="PILOTTEST",
                    plan_code="PLAN_1_SOLO",
                    entry_channel="link",
                )
    assert exc.value.error_code == "PILOT_INVITE_PUBLIC_ENTRY_DISABLED"


@pytest.mark.asyncio
async def test_one_redemption_per_email_blocks():
    doc = _active_invite_doc(
        code_type="public_promo",
        public_entry_enabled=True,
        campaign_status="active",
        is_publicly_enterable=True,
        one_redemption_per_email=True,
    )
    fdb = _fake_db_for_invite(doc, redemption_count=1)
    with patch("services.pilot_invite_service.database.get_db", return_value=fdb):
        with patch("utils.audit.create_audit_log", new_callable=AsyncMock):
            with pytest.raises(PilotInvitePublicError) as exc:
                await validate_invite_for_checkout(
                    code="PILOTTEST",
                    plan_code="PLAN_1_SOLO",
                    email="used@example.com",
                    entry_channel="manual",
                )
    assert exc.value.error_code == "PILOT_INVITE_ALREADY_REDEEMED_EMAIL"


@pytest.mark.asyncio
async def test_private_invite_ignores_public_governance():
    doc = _active_invite_doc(
        code_type="private_invite",
        public_entry_enabled=False,
        campaign_status="not_applicable",
        is_publicly_enterable=False,
    )
    fdb = _fake_db_for_invite(doc)
    with patch("services.pilot_invite_service.database.get_db", return_value=fdb):
        with patch("utils.audit.create_audit_log", new_callable=AsyncMock):
            _, resp = await validate_invite_for_checkout(
                code="PILOTTEST",
                plan_code="PLAN_1_SOLO",
                email="x@y.com",
                for_checkout=True,
                entry_channel="manual",
            )
    assert resp.valid is True


@pytest.mark.asyncio
async def test_internal_test_manual_entry_blocked_but_link_allowed():
    doc = _active_invite_doc(
        code_type="internal_test",
        campaign_state="active",
        launch_visibility="internal",
        analytics_family="internal_test",
        public_entry_enabled=False,
        is_publicly_enterable=False,
    )
    fdb = _fake_db_for_invite(doc)
    with patch("services.pilot_invite_service.database.get_db", return_value=fdb):
        with patch("utils.audit.create_audit_log", new_callable=AsyncMock):
            with pytest.raises(PilotInvitePublicError) as exc:
                await validate_invite_for_checkout(
                    code="PILOTTEST",
                    plan_code="PLAN_1_SOLO",
                    email="internal@example.com",
                    entry_channel="manual",
                )
            _, resp = await validate_invite_for_checkout(
                code="PILOTTEST",
                plan_code="PLAN_1_SOLO",
                email="internal@example.com",
                for_checkout=True,
                entry_channel="link",
            )
    assert exc.value.error_code == "PILOT_INVITE_PUBLIC_ENTRY_DISABLED"
    assert resp.valid is True
    assert resp.code_type == "internal_test"


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
        st_filt = filter_doc.get("status")
        pending_ok = st_filt == "pending" or (
            isinstance(st_filt, dict) and "pending" in (st_filt.get("$in") or [])
        )
        if not pending_ok or state["redemption_status"] != "pending":
            return None
        state["redemption_status"] = "redeemed"
        redemption["status"] = "redeemed"
        return dict(redemption)

    async def find_one_redemption(filter_doc, projection=None):
        st = filter_doc.get("status")
        if st == "completed" or (isinstance(st, dict) and st.get("$in")):
            return redemption
        return None

    mock_redemptions.find_one_and_update = AsyncMock(side_effect=find_one_and_update_redemption)
    mock_redemptions.find_one = AsyncMock(side_effect=find_one_redemption)
    mock_codes.find_one_and_update = AsyncMock(return_value=_active_invite_doc(used_count=1))

    with patch("services.pilot_invite_service.database.get_db", return_value=mock_db):
        with patch("utils.audit.create_audit_log", new_callable=AsyncMock):
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
