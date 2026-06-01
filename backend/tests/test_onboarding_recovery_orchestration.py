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
    CLASS_EXPIRED_CHECKOUT,
    CLASS_FIRST_TIME_RESTRICTION_COLLISION,
    CLASS_PAYMENT_ABANDONED,
    CLASS_PROMO_REDEMPTION_FAILED,
    CLASS_RECOVERY_ALREADY_ACTIVE,
    CLASS_UNKNOWN_RECOVERY_STATE,
    MODE_REGENERATE_PAYMENT,
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
            },
            indicators={"stranded_onboarding": True},
        )
    )
    assert classification == CLASS_PAYMENT_ABANDONED


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
    assert assessment["classification"] == CLASS_PAYMENT_ABANDONED
    assert assessment["strategy"]["recommended_mode"] == MODE_REGENERATE_PAYMENT
    assert assessment["execution_available"] is True
    assert MODE_REGENERATE_PAYMENT in assessment["strategy"]["executable_modes"]
    assert "blockage_summary" in assessment["recommendation"]
