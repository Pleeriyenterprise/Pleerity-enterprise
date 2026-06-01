"""Phase 3 onboarding continuation token and landing tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from models import OnboardingStatus, PasswordStatus
from services.onboarding_continuation_service import (
    OnboardingContinuationError,
    derive_customer_next_step,
    expire_old_continuation_tokens,
)
from services.onboarding_recovery_execution_service import (
    MODE_RESUME_ONBOARDING,
    validate_mode_for_classification,
)
from services.onboarding_recovery_service import (
    CLASS_PAYMENT_ABANDONED,
    derive_executable_modes,
    derive_recovery_strategy,
)


def test_derive_customer_next_step_unpaid():
    step = derive_customer_next_step(
        {"onboarding_status": OnboardingStatus.INTAKE_PENDING.value, "subscription_status": None},
        None,
    )
    assert step == "complete_payment"


def test_derive_customer_next_step_activation():
    step = derive_customer_next_step(
        {
            "onboarding_status": OnboardingStatus.PROVISIONED.value,
            "subscription_status": "active",
            "stripe_subscription_id": "sub_1",
        },
        {"password_status": PasswordStatus.NOT_SET.value},
        paid_or_active=True,
    )
    assert step == "set_password"


def test_resume_mode_allowed_for_payment_abandoned():
    validate_mode_for_classification(MODE_RESUME_ONBOARDING, "PAYMENT_ABANDONED")


def test_executable_modes_include_resume_for_abandoned():
    strategy = derive_recovery_strategy(CLASS_PAYMENT_ABANDONED, {})
    modes = derive_executable_modes(CLASS_PAYMENT_ABANDONED, strategy, {"eligible": True})
    assert MODE_RESUME_ONBOARDING in modes


@pytest.mark.asyncio
async def test_create_and_resolve_continuation_token():
    from auth import hash_token
    from services.onboarding_continuation_service import (
        build_continuation_landing_context,
        create_secure_continuation_link,
    )

    raw = "a" * 32 + "b" * 16
    client = {
        "client_id": "c-cont",
        "customer_reference": "PLE-CVP-2026-000010",
        "full_name": "Jane Doe",
        "email": "jane@example.com",
        "billing_plan": "PLAN_1_SOLO",
        "onboarding_status": OnboardingStatus.INTAKE_PENDING.value,
    }
    token_doc = {
        "continuation_token_id": "tok-1",
        "token_hash": hash_token(raw),
        "client_id": "c-cont",
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
        "revoked_at": None,
    }

    tokens_col = MagicMock()
    tokens_col.insert_one = AsyncMock()
    tokens_col.update_many = AsyncMock(return_value=MagicMock(modified_count=0))
    tokens_col.update_one = AsyncMock()
    tokens_col.find_one = AsyncMock(return_value=token_doc)

    mock_db = MagicMock()
    mock_db.clients.find_one = AsyncMock(return_value=client)
    mock_db.clients.update_one = AsyncMock()
    mock_db.portal_users.find_one = AsyncMock(return_value=None)
    mock_db.properties.count_documents = AsyncMock(return_value=2)
    mock_db.__getitem__ = lambda _db, key: tokens_col if key == "onboarding_continuation_tokens" else MagicMock()

    with patch("services.onboarding_continuation_service.database.get_db", return_value=mock_db):
        with patch("auth.generate_secure_token", return_value=raw):
            with patch("utils.app_urls.get_app_base_url", return_value="https://app.example.com"):
                link = await create_secure_continuation_link(
                    client_id="c-cont",
                    classification=CLASS_PAYMENT_ABANDONED,
                    created_by="test",
                )
        assert "onboarding/continue?token=" in link["continuation_url"]

        ctx = await build_continuation_landing_context(raw)
    assert ctx["valid"] is True
    assert ctx["properties_count"] == 2
    assert ctx["next_step"] == "complete_payment"
    assert "saved" in ctx["welcome_message"].lower()


@pytest.mark.asyncio
async def test_expired_token_rejected():
    from auth import hash_token
    from services.onboarding_continuation_service import build_continuation_landing_context

    raw = "c" * 48
    expired = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    tokens_col = MagicMock()
    tokens_col.find_one = AsyncMock(
        return_value={
            "continuation_token_id": "x",
            "token_hash": hash_token(raw),
            "client_id": "c1",
            "expires_at": expired,
            "revoked_at": None,
        }
    )
    mock_db = MagicMock()
    mock_db.__getitem__ = lambda _db, key: tokens_col if key == "onboarding_continuation_tokens" else MagicMock()

    with patch("services.onboarding_continuation_service.database.get_db", return_value=mock_db):
        with pytest.raises(OnboardingContinuationError) as exc:
            await build_continuation_landing_context(raw)
    assert exc.value.code == "TOKEN_EXPIRED"


@pytest.mark.asyncio
async def test_execute_resume_onboarding_delivers_continuation_url():
    from services.onboarding_recovery_execution_service import execute_resume_onboarding

    client = {
        "client_id": "c-resume",
        "email": "resume@yopmail.com",
        "customer_reference": "PLE-CVP-2026-000099",
        "billing_plan": "PLAN_1_SOLO",
        "onboarding_status": OnboardingStatus.INTAKE_PENDING.value,
        "subscription_status": "PENDING",
    }
    signals = {"client": client, "billing": None}

    tokens_col = MagicMock()
    tokens_col.insert_one = AsyncMock()
    tokens_col.update_many = AsyncMock(return_value=MagicMock(modified_count=0))
    mock_db = MagicMock()
    mock_db.clients.find_one = AsyncMock(return_value=client)
    mock_db.clients.update_one = AsyncMock()
    mock_db.properties.count_documents = AsyncMock(return_value=1)
    mock_db.__getitem__ = lambda _db, key: tokens_col if key == "onboarding_continuation_tokens" else MagicMock()

    with patch("services.onboarding_continuation_service.database.get_db", return_value=mock_db):
        with patch("services.onboarding_recovery_execution_service.database.get_db", return_value=mock_db):
            with patch("auth.generate_secure_token", return_value="d" * 48):
                with patch("utils.app_urls.get_app_base_url", return_value="https://app.example.com"):
                    result = await execute_resume_onboarding(
                        client_id="c-resume",
                        signals=signals,
                        classification="PAYMENT_ABANDONED",
                        reason="test resume onboarding",
                        actor={"id": "admin-1"},
                        send_customer_email=False,
                        apply_recovery_waiver=False,
                    )
    assert result["mode"] == "resume_onboarding"
    assert "onboarding/continue?token=" in result["continuation_url"]
    assert result["continuation_delivered"] is True


@pytest.mark.asyncio
async def test_expire_old_tokens():
    tokens_col = MagicMock()
    tokens_col.update_many = AsyncMock(return_value=MagicMock(modified_count=2))
    mock_db = MagicMock()
    mock_db.__getitem__ = lambda _db, key: tokens_col if key == "onboarding_continuation_tokens" else MagicMock()

    with patch("services.onboarding_continuation_service.database.get_db", return_value=mock_db):
        n = await expire_old_continuation_tokens("c1")
    assert n == 2
