"""Phase 1 onboarding recovery orchestration — classification and assessment tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from models import OnboardingStatus, PasswordStatus
from services.onboarding_recovery_execution_service import (
    OnboardingRecoveryExecutionError,
    validate_mode_for_classification,
)
from services.onboarding_recovery_service import (
    CLASS_ACTIVATION_INCOMPLETE,
    CLASS_EMAIL_RESERVED_NO_CHECKOUT,
    CLASS_EXPIRED_CHECKOUT,
    CLASS_FIRST_TIME_RESTRICTION_COLLISION,
    CLASS_PAYMENT_ABANDONED,
    CLASS_PROMO_REDEMPTION_FAILED,
    CLASS_RECOVERY_ALREADY_ACTIVE,
    CLASS_UNKNOWN_RECOVERY_STATE,
    MODE_REGENERATE_PAYMENT,
    MODE_RELEASE_AND_RESTART,
    MODE_RESEND_ACTIVATION,
    build_onboarding_recovery_assessment,
    classify_recovery_state,
    derive_executable_modes,
    derive_execution_availability,
    derive_recovery_recommendation_copy,
    derive_recovery_strategy,
    validate_recovery_eligibility,
)


def _signals(
    *,
    stranded=True,
    client=None,
    indicators=None,
    redemptions=None,
    portal_user=None,
    billing=None,
    subscription_drift=False,
):
    return {
        "is_stranded": stranded,
        "client": client or {},
        "indicators": indicators or {},
        "redemptions": redemptions or [],
        "portal_user": portal_user,
        "billing": billing,
        "subscription_drift": subscription_drift,
    }


def test_classify_payment_abandoned():
    classification = classify_recovery_state(
        _signals(
            client={
                "customer_reference": "PLE-CVP-2026-000001",
                "onboarding_status": OnboardingStatus.INTAKE_PENDING.value,
                "lifecycle_status": "pending_payment",
                "latest_checkout_url": "https://checkout.stripe.com/c",
                "latest_checkout_session_id": "cs_x",
                "checkout_link_sent_at": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
            },
            indicators={"stranded_onboarding": True},
        )
    )
    assert classification == CLASS_EXPIRED_CHECKOUT


def test_classify_email_reserved_no_checkout():
    classification = classify_recovery_state(
        _signals(
            client={
                "email": "stranded@example.com",
                "onboarding_status": OnboardingStatus.INTAKE_PENDING.value,
            },
            indicators={"stranded_onboarding": True},
        )
    )
    assert classification == CLASS_EMAIL_RESERVED_NO_CHECKOUT


def test_classify_expired_checkout():
    old = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    classification = classify_recovery_state(
        _signals(
            client={
                "customer_reference": "PLE-CVP-2026-000001",
                "onboarding_status": OnboardingStatus.INTAKE_PENDING.value,
                "latest_checkout_url": "https://checkout.stripe.com/old",
                "latest_checkout_session_id": "cs_old",
                "checkout_link_sent_at": old,
            },
            indicators={"stranded_onboarding": True},
        )
    )
    assert classification == CLASS_EXPIRED_CHECKOUT


def test_classify_recovery_already_active():
    fresh = datetime.now(timezone.utc).isoformat()
    classification = classify_recovery_state(
        _signals(
            client={
                "onboarding_status": OnboardingStatus.INTAKE_PENDING.value,
                "latest_checkout_url": "https://checkout.stripe.com/new",
                "latest_checkout_session_id": "cs_new",
                "checkout_link_sent_at": fresh,
            },
            indicators={"stranded_onboarding": True},
        )
    )
    assert classification == CLASS_RECOVERY_ALREADY_ACTIVE


def test_classify_promo_redemption_failed():
    classification = classify_recovery_state(
        _signals(
            client={"onboarding_status": OnboardingStatus.INTAKE_PENDING.value},
            indicators={"stranded_onboarding": True, "payment_failed": True},
            redemptions=[{"status": "payment_failed", "created_at": "2026-05-01T12:00:00Z"}],
        )
    )
    assert classification == CLASS_PROMO_REDEMPTION_FAILED


def test_classify_first_time_restriction_collision():
    classification = classify_recovery_state(
        _signals(
            client={"onboarding_status": OnboardingStatus.INTAKE_PENDING.value},
            indicators={"stranded_onboarding": True, "retry_blocked": True, "override_active": False},
        )
    )
    assert classification == CLASS_FIRST_TIME_RESTRICTION_COLLISION


def test_classify_activation_incomplete():
    classification = classify_recovery_state(
        _signals(
            client={
                "onboarding_status": OnboardingStatus.PROVISIONED.value,
                "subscription_status": "active",
                "stripe_subscription_id": "sub_123",
            },
            portal_user={"password_status": PasswordStatus.NOT_SET.value},
            indicators={"stranded_onboarding": True},
        )
    )
    assert classification == CLASS_ACTIVATION_INCOMPLETE


def test_not_stranded_returns_none():
    assert classify_recovery_state(_signals(stranded=False)) is None


def test_strategy_recommends_regenerate_payment_for_abandoned():
    strategy = derive_recovery_strategy(CLASS_PAYMENT_ABANDONED, _signals())
    assert strategy["recommended_mode"] == MODE_REGENERATE_PAYMENT
    assert strategy["phase"] == 2


def test_executable_modes_when_eligible():
    strategy = derive_recovery_strategy(CLASS_PAYMENT_ABANDONED, _signals())
    eligibility = {"eligible": True, "reason": None}
    modes = derive_executable_modes(CLASS_PAYMENT_ABANDONED, strategy, eligibility)
    assert MODE_REGENERATE_PAYMENT in modes
    available, phase = derive_execution_availability(CLASS_PAYMENT_ABANDONED, strategy, eligibility)
    assert available is True
    assert phase == 2


def test_validate_mode_for_classification_rejects_mismatch():
    with pytest.raises(OnboardingRecoveryExecutionError) as exc:
        validate_mode_for_classification(MODE_RESEND_ACTIVATION, CLASS_PAYMENT_ABANDONED)
    assert exc.value.code == "MODE_CLASSIFICATION_MISMATCH"


def test_strategy_recommends_activation_resend():
    strategy = derive_recovery_strategy(CLASS_ACTIVATION_INCOMPLETE, _signals())
    assert strategy["recommended_mode"] == MODE_RESEND_ACTIVATION


def test_recommendation_copy_is_customer_safe():
    copy = derive_recovery_recommendation_copy(
        CLASS_PAYMENT_ABANDONED,
        _signals(client={"customer_reference": "PLE-CVP-2026-000099"}),
        derive_recovery_strategy(CLASS_PAYMENT_ABANDONED, _signals()),
    )
    text = " ".join(copy.values()).lower()
    assert "stripe" not in text
    assert "override" not in text
    assert "provisioning" not in text
    assert "ple-cvp-2026-000099" in copy["blockage_summary"].lower()


def test_recovery_already_active_not_eligible():
    eligibility = validate_recovery_eligibility(CLASS_RECOVERY_ALREADY_ACTIVE, _signals())
    assert eligibility["eligible"] is False


@pytest.mark.asyncio
async def test_build_assessment_integrates_promo_context():
    mock_client = {
        "client_id": "c1",
        "email": "pending@example.com",
        "customer_reference": "PLE-CVP-2026-000001",
        "onboarding_status": OnboardingStatus.INTAKE_PENDING.value,
        "lifecycle_status": "pending_payment",
        "subscription_status": None,
    }
    mock_db = MagicMock()
    mock_db.clients.find_one = AsyncMock(return_value=mock_client)
    mock_db.client_billing.find_one = AsyncMock(return_value=None)
    mock_db.portal_users.find_one = AsyncMock(return_value=None)
    mock_db.provisioning_jobs.find = MagicMock(
        return_value=MagicMock(
            sort=MagicMock(
                return_value=MagicMock(limit=MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[]))))
            )
        )
    )
    promo_context = {
        "indicators": {"stranded_onboarding": True, "payment_failed": False},
        "redemptions": [],
        "waiver_history": [],
    }
    obs_payload = {
        "found": True,
        "client_id": "c1",
        "completion": {"status": "no_governed_recovery", "message": "—"},
        "events": [],
        "delivery": {},
    }
    with patch("services.onboarding_recovery_service.database.get_db", return_value=mock_db):
        with patch(
            "services.onboarding_recovery_service.get_account_promo_recovery_context",
            new=AsyncMock(return_value=promo_context),
        ):
            with patch(
                "services.onboarding_recovery_observability_service.get_client_onboarding_recovery_observability",
                new=AsyncMock(return_value=obs_payload),
            ):
                assessment = await build_onboarding_recovery_assessment("c1")
    assert assessment["found"] is True
    assert assessment["classification"] == CLASS_EMAIL_RESERVED_NO_CHECKOUT
    assert assessment["strategy"]["recommended_mode"] == MODE_RELEASE_AND_RESTART
    assert assessment["execution_available"] is True
    assert MODE_RELEASE_AND_RESTART in assessment["strategy"]["executable_modes"]
    assert assessment["diagnostic"]["last_successful_stage"]
    assert assessment["diagnostic"]["email_identity_state"] == "ACTIVE_OR_VALID_ONBOARDING_IDENTITY"
    assert assessment["promo_recovery"]["customer_entered_promo_supported"] is False
    assert "blockage_summary" in assessment["recommendation"]


@pytest.mark.asyncio
async def test_client_email_taken_ignores_released_identity():
    from utils.client_email import client_email_taken

    db = MagicMock()
    db.clients.find_one = AsyncMock(
        side_effect=[
            {"_id": "x", "onboarding_identity_status": "RELEASED_FOR_RESTART"},
            None,
        ]
    )
    db.portal_users.find_one = AsyncMock(return_value=None)
    assert await client_email_taken(db, "user@example.com") is False


@pytest.mark.asyncio
async def test_release_rejected_when_paid():
    from services.onboarding_recovery_execution_service import (
        execute_release_and_restart,
        OnboardingRecoveryExecutionError,
    )

    signals = _signals(
        client={
            "client_id": "c1",
            "email": "paid@example.com",
            "onboarding_status": OnboardingStatus.INTAKE_PENDING.value,
            "subscription_status": "active",
            "stripe_subscription_id": "sub_1",
        }
    )
    with pytest.raises(OnboardingRecoveryExecutionError) as exc:
        await execute_release_and_restart(
            client_id="c1",
            signals=signals,
            classification=CLASS_EMAIL_RESERVED_NO_CHECKOUT,
            reason="Customer asked to restart signup.",
            actor={"portal_user_id": "admin1", "role": "ROLE_ADMIN"},
        )
    assert exc.value.code == "RELEASE_NOT_ALLOWED"


@pytest.mark.asyncio
async def test_release_and_restart_vacates_email():
    from services.onboarding_recovery_execution_service import execute_release_and_restart

    mock_db = MagicMock()
    mock_db.clients.find_one_and_update = AsyncMock(
        return_value={"client_id": "c1", "email": "stranded@example.com"}
    )
    mock_db.clients.update_one = AsyncMock()
    mock_db.clients.find_one = AsyncMock(return_value={"recovery_attempt_count": 0})
    mock_db.portal_users.update_one = AsyncMock()
    signals = _signals(
        client={
            "client_id": "c1",
            "email": "stranded@example.com",
            "onboarding_status": OnboardingStatus.INTAKE_PENDING.value,
        }
    )
    with patch("services.onboarding_recovery_execution_service.database.get_db", return_value=mock_db):
        with patch(
            "services.stripe_service.stripe_service.expire_checkout_session",
            new=AsyncMock(),
        ):
            with patch(
                "services.onboarding_continuation_service.expire_old_continuation_tokens",
                new=AsyncMock(return_value=1),
            ):
                with patch(
                    "services.onboarding_recovery_execution_service.create_audit_log",
                    new=AsyncMock(),
                ):
                    result = await execute_release_and_restart(
                        client_id="c1",
                        signals=signals,
                        classification=CLASS_EMAIL_RESERVED_NO_CHECKOUT,
                        reason="Abandoned unpaid signup, restart allowed.",
                        actor={"portal_user_id": "admin1", "email": "ops@example.com", "role": "ROLE_ADMIN"},
                    )
    assert result["completion_status"] == "RESTART_RELEASE_COMPLETE"
    assert result["released_canonical_email"] == "stranded@example.com"
    assert result["email_reservation_released"] is True
    set_payload = mock_db.clients.find_one_and_update.await_args.args[1]["$set"]
    assert set_payload["onboarding_identity_status"] == "RELEASED_FOR_RESTART"
    assert set_payload["email"] == "released.c1@released.invalid"


@pytest.mark.asyncio
async def test_release_second_call_rejected_already_released():
    from services.onboarding_recovery_execution_service import (
        execute_release_and_restart,
        OnboardingRecoveryExecutionError,
    )

    mock_db = MagicMock()
    mock_db.clients.find_one_and_update = AsyncMock(return_value=None)
    signals = _signals(
        client={
            "client_id": "c1",
            "email": "stranded@example.com",
            "onboarding_status": OnboardingStatus.INTAKE_PENDING.value,
        }
    )
    with patch("services.onboarding_recovery_execution_service.database.get_db", return_value=mock_db):
        with patch(
            "services.stripe_service.stripe_service.expire_checkout_session",
            new=AsyncMock(),
        ):
            with patch(
                "services.onboarding_continuation_service.expire_old_continuation_tokens",
                new=AsyncMock(return_value=0),
            ):
                with pytest.raises(OnboardingRecoveryExecutionError) as exc:
                    await execute_release_and_restart(
                        client_id="c1",
                        signals=signals,
                        classification=CLASS_EMAIL_RESERVED_NO_CHECKOUT,
                        reason="Abandoned unpaid signup, restart allowed.",
                        actor={"portal_user_id": "admin1", "role": "ROLE_ADMIN"},
                    )
    assert exc.value.code == "RELEASE_NOT_ALLOWED"
    assert "already_released" in exc.value.message


@pytest.mark.asyncio
async def test_regenerate_maps_live_coupon_on_test_mode_to_conflict():
    from services.onboarding_recovery_execution_service import (
        execute_regenerate_payment,
        OnboardingRecoveryExecutionError,
    )

    signals = _signals(
        client={
            "client_id": "c1",
            "email": "promo@example.com",
            "onboarding_status": OnboardingStatus.INTAKE_PENDING.value,
            "billing_plan": "PLAN_1_SOLO",
        }
    )
    mock_db = MagicMock()
    with patch("services.onboarding_recovery_execution_service.database.get_db", return_value=mock_db):
        with patch(
            "services.onboarding_recovery_execution_service.resolve_pilot_invite_for_client",
            new=AsyncMock(return_value={"code": "PILOTACCESS", "stripe_coupon_id": "85x6smtg"}),
        ):
            with patch(
                "services.stripe_service.stripe_service.expire_checkout_session",
                new=AsyncMock(),
            ):
                with patch(
                    "services.stripe_service.stripe_service.create_checkout_session",
                    new=AsyncMock(
                        side_effect=ValueError(
                            "No such coupon: '85x6smtg'; a similar object exists in live mode, but a test mode key was used to make this request."
                        )
                    ),
                ):
                    with pytest.raises(OnboardingRecoveryExecutionError) as exc:
                        await execute_regenerate_payment(
                            client_id="c1",
                            signals=signals,
                            classification=CLASS_EMAIL_RESERVED_NO_CHECKOUT,
                            reason="Recovery checkout with existing promo.",
                            actor={"portal_user_id": "admin1", "role": "ROLE_ADMIN"},
                            origin_url="https://example.test",
                            send_customer_email=False,
                            preserve_promo_eligibility=True,
                            apply_recovery_waiver=False,
                            promo_decision="preserve_existing",
                        )
    assert exc.value.code == "STRIPE_PROMO_MODE_MISMATCH"
    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_list_approved_recovery_promos_skips_incompatible_stripe_mode():
    from services.onboarding_recovery_execution_service import list_approved_recovery_promos

    rows = [
        {
            "code": "PILOTACCESS",
            "campaign_name": "Live coupon",
            "effective_status": "active",
            "remaining_uses": 10,
            "discount_percent": 100,
            "discount_duration": "repeating",
            "discount_duration_in_months": 2,
            "applies_to_plan_codes": ["PLAN_1_SOLO"],
            "stripe_coupon_id": "85x6smtg",
        },
        {
            "code": "STAGINGSO01",
            "campaign_name": "Staging cert",
            "effective_status": "active",
            "remaining_uses": 8,
            "discount_percent": 100,
            "discount_duration": "repeating",
            "discount_duration_in_months": 2,
            "applies_to_plan_codes": ["PLAN_1_SOLO"],
            "stripe_coupon_id": "STAGINGSO01",
        },
        {
            "code": "NOPAYLOAD",
            "effective_status": "active",
            "remaining_uses": 5,
            "discount_percent": 100,
            "stripe_coupon_id": None,
        },
    ]

    async def _preview(fields):
        cid = fields.get("stripe_coupon_id")
        if cid == "STAGINGSO01":
            return {"valid": True}
        return {"valid": False, "message": "live mode mismatch"}

    with patch(
        "services.pilot_invite_service.list_invite_codes",
        new=AsyncMock(return_value=rows),
    ):
        with patch(
            "services.pilot_invite_service.preview_stripe_coupon_validation",
            new=AsyncMock(side_effect=_preview),
        ):
            out = await list_approved_recovery_promos()
    assert [p["code"] for p in out] == ["STAGINGSO01"]
