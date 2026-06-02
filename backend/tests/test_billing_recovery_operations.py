"""Phase 4 — billing recovery state machine, orchestration, bulk safety."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.billing_recovery_state_machine import (
    STATE_CHECKOUT_REGENERATED,
    STATE_CUSTOMER_PENDING,
    STATE_MODE_UNVERIFIED,
    STATE_RECOVERY_RESOLVED,
    BillingRecoveryTransitionError,
    can_transition,
    initial_recovery_state,
    transition_recovery_state,
)
from services.billing_recovery_service import (
    BULK_MAX_BATCH,
    bulk_resend_continuation,
)


def test_initial_state_mode_unverified():
    assert initial_recovery_state(verification_status="MODE_UNVERIFIED") == STATE_MODE_UNVERIFIED


def test_initial_state_recovery_required():
    assert initial_recovery_state(verification_status=None) == "RECOVERY_REQUIRED"


def test_transition_idempotent():
    new_state, record = transition_recovery_state(
        STATE_MODE_UNVERIFIED,
        STATE_MODE_UNVERIFIED,
        action="noop",
        actor_id="admin@test",
    )
    assert new_state == STATE_MODE_UNVERIFIED
    assert record["idempotent"] is True


def test_transition_allowed_path():
    new_state, record = transition_recovery_state(
        STATE_MODE_UNVERIFIED,
        "RECOVERY_REQUIRED",
        action="open",
        actor_id="admin@test",
    )
    assert new_state == "RECOVERY_REQUIRED"
    assert record["idempotent"] is False


def test_transition_forbidden():
    with pytest.raises(BillingRecoveryTransitionError):
        transition_recovery_state(
            STATE_RECOVERY_RESOLVED,
            STATE_MODE_UNVERIFIED,
            action="illegal",
            actor_id="admin@test",
        )


def test_checkout_regenerated_to_customer_pending():
    assert can_transition(STATE_CHECKOUT_REGENERATED, STATE_CUSTOMER_PENDING)


@pytest.mark.asyncio
async def test_bulk_resend_preview():
    mock_db = MagicMock()
    mock_db.billing_recovery_audit.insert_one = AsyncMock()
    mock_db.billing_recovery_metrics.update_one = AsyncMock()
    with patch("services.billing_recovery_service.database.get_db", return_value=mock_db):
        with patch("services.billing_recovery_service.create_audit_log", new=AsyncMock()):
            result = await bulk_resend_continuation(
                ["c1", "c2"],
                actor_id="admin@test",
                preview=True,
            )
    assert result["preview"] is True
    assert len(result["results"]) == 2
    assert result["results"][0]["preview"] is True


@pytest.mark.asyncio
async def test_bulk_resend_batch_limit():
    ids = [f"c{i}" for i in range(BULK_MAX_BATCH + 1)]
    with pytest.raises(ValueError, match="Batch limit"):
        await bulk_resend_continuation(ids, actor_id="admin@test", preview=True)


@pytest.mark.asyncio
async def test_regenerate_supersedes_pending_checkouts():
    from services.billing_recovery_service import regenerate_checkout_for_recovery

    mock_db = MagicMock()
    mock_db.checkout_sessions.update_many = AsyncMock(return_value=MagicMock(modified_count=2))
    mock_db.billing_recovery_cases.find_one = AsyncMock(
        return_value={
            "client_id": "c1",
            "recovery_state": STATE_MODE_UNVERIFIED,
            "remediation_code": "MODE_UNVERIFIED",
            "operational_risk": "high",
            "recommended_action": "REGENERATE_CHECKOUT_REQUIRED",
        }
    )
    mock_db.billing_recovery_cases.update_one = AsyncMock()
    mock_db.billing_recovery_cases.insert_one = AsyncMock()
    mock_db.billing_recovery_audit.insert_one = AsyncMock()
    mock_db.billing_recovery_metrics.update_one = AsyncMock()
    mock_db.client_billing.find_one = AsyncMock(return_value={"client_id": "c1"})
    mock_db.clients.find_one = AsyncMock(return_value={"client_id": "c1", "email": "a@b.com"})
    mock_db.stripe_events.find_one = AsyncMock(return_value=None)
    mock_db.checkout_sessions.find_one = AsyncMock(return_value=None)

    mock_stripe = MagicMock()
    mock_stripe.create_upgrade_session = AsyncMock(
        return_value={"session_id": "cs_test", "checkout_url": "https://checkout.example"}
    )

    with patch("services.billing_recovery_service.database.get_db", return_value=mock_db):
        with patch("services.billing_recovery_service.create_audit_log", new=AsyncMock()):
            with patch("services.billing_recovery_service.resolve_stripe_context", new=AsyncMock()):
                with patch(
                    "services.billing_recovery_service._get_or_create_case",
                    new=AsyncMock(return_value={"client_id": "c1", "recovery_state": STATE_MODE_UNVERIFIED}),
                ):
                    with patch("services.stripe_service.StripeService", return_value=mock_stripe):
                        with patch(
                            "services.billing_recovery_service.transition_case",
                            new=AsyncMock(side_effect=lambda cid, **kw: {"recovery_state": kw["target_state"]}),
                        ):
                            result = await regenerate_checkout_for_recovery(
                                "c1",
                                plan_code="PLAN_2_PORTFOLIO",
                                actor_id="admin@test",
                                origin_url="https://app.example/admin/billing",
                                send_email=False,
                            )
    mock_db.checkout_sessions.update_many.assert_awaited()
    assert result["checkout"]["session_id"] == "cs_test"


@pytest.mark.asyncio
async def test_regenerate_prepares_state_before_stripe_side_effects():
    from services.billing_recovery_service import regenerate_checkout_for_recovery

    mock_db = MagicMock()
    mock_db.checkout_sessions.update_many = AsyncMock(return_value=MagicMock(modified_count=1))
    mock_db.billing_recovery_cases.find_one = AsyncMock(
        return_value={
            "client_id": "c1",
            "recovery_state": STATE_MODE_UNVERIFIED,
            "remediation_code": "MODE_UNVERIFIED",
            "operational_risk": "high",
            "recommended_action": "REGENERATE_CHECKOUT_REQUIRED",
        }
    )
    mock_db.billing_recovery_cases.update_one = AsyncMock()
    mock_db.billing_recovery_cases.insert_one = AsyncMock()
    mock_db.billing_recovery_audit.insert_one = AsyncMock()
    mock_db.billing_recovery_metrics.update_one = AsyncMock()
    mock_db.client_billing.find_one = AsyncMock(return_value={"client_id": "c1"})
    mock_db.clients.find_one = AsyncMock(return_value={"client_id": "c1", "email": "a@b.com"})
    mock_db.stripe_events.find_one = AsyncMock(return_value=None)
    mock_db.checkout_sessions.find_one = AsyncMock(return_value=None)

    mock_stripe = MagicMock()
    mock_stripe.create_upgrade_session = AsyncMock(
        return_value={"session_id": "cs_test", "checkout_url": "https://checkout.example"}
    )

    call_states = []

    async def _fake_transition_case(client_id, **kw):
        call_states.append(kw["target_state"])
        return {"recovery_state": kw["target_state"]}

    with patch("services.billing_recovery_service.database.get_db", return_value=mock_db):
        with patch("services.billing_recovery_service.create_audit_log", new=AsyncMock()):
            with patch("services.billing_recovery_service.resolve_stripe_context", new=AsyncMock()):
                with patch(
                    "services.billing_recovery_service._get_or_create_case",
                    new=AsyncMock(return_value={"client_id": "c1", "recovery_state": STATE_MODE_UNVERIFIED}),
                ):
                    with patch("services.stripe_service.StripeService", return_value=mock_stripe):
                        with patch(
                            "services.billing_recovery_service.transition_case",
                            new=AsyncMock(side_effect=_fake_transition_case),
                        ):
                            await regenerate_checkout_for_recovery(
                                "c1",
                                plan_code="PLAN_2_PORTFOLIO",
                                actor_id="admin@test",
                                origin_url="https://app.example/admin/billing",
                                send_email=False,
                            )

    assert call_states[0] == "RECOVERY_REQUIRED"
    assert call_states[1] == STATE_CHECKOUT_REGENERATED
    assert call_states[2] == STATE_CUSTOMER_PENDING


@pytest.mark.asyncio
async def test_continuation_email_rate_limit_blocks_at_three():
    from services.billing_recovery_service import _send_continuation_email

    mock_db = MagicMock()
    mock_db.clients.find_one = AsyncMock(return_value={"client_id": "c1", "email": "client@example.com"})
    mock_audit_collection = MagicMock()
    mock_audit_collection.count_documents = AsyncMock(return_value=3)
    mock_db.__getitem__.return_value = mock_audit_collection

    with patch("services.billing_recovery_service.database.get_db", return_value=mock_db):
        with patch("services.notification_orchestrator.notification_orchestrator.send", new=AsyncMock()) as send_mock:
            result = await _send_continuation_email(
                "c1",
                "https://checkout.example",
                actor_id="admin@test",
            )

    assert result["sent"] is False
    assert result["reason"] == "rate_limited"
    send_mock.assert_not_called()
