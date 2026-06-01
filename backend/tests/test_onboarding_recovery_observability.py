"""Phase 4 onboarding recovery observability tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from models import OnboardingStatus, PasswordStatus
from services.onboarding_recovery_observability_service import (
    derive_recovery_completion_status,
    EVENT_RECOVERY_EXECUTED,
    record_onboarding_recovery_event,
)


def test_completion_activation_complete():
    completion = derive_recovery_completion_status(
        {"onboarding_status": OnboardingStatus.PROVISIONED.value, "subscription_status": "active"},
        {"password_status": PasswordStatus.SET.value},
    )
    assert completion["status"] == "activation_complete"


def test_completion_awaiting_payment():
    completion = derive_recovery_completion_status(
        {
            "onboarding_status": OnboardingStatus.INTAKE_PENDING.value,
            "continuation_delivered_at": "2026-05-01T12:00:00+00:00",
        },
        None,
    )
    assert completion["status"] == "continuation_delivered_awaiting_action"


@pytest.mark.asyncio
async def test_record_recovery_event_writes_audit():
    audit_col = MagicMock()
    audit_col.insert_one = AsyncMock()
    metrics_col = MagicMock()
    metrics_col.update_one = AsyncMock()

    mock_db = MagicMock()

    mock_db.__getitem__ = lambda _db, key: (
        audit_col
        if key == "onboarding_recovery_audit"
        else metrics_col
        if key == "onboarding_recovery_metrics"
        else MagicMock()
    )

    with patch("services.onboarding_recovery_observability_service.database.get_db", return_value=mock_db):
        with patch("services.onboarding_recovery_observability_service.create_audit_log", new=AsyncMock()):
            event_id = await record_onboarding_recovery_event(
                event_type=EVENT_RECOVERY_EXECUTED,
                client_id="c1",
                mode="resume_onboarding",
                classification="PAYMENT_ABANDONED",
                actor_id="admin-1",
                continuation_delivered=True,
                email_sent=True,
            )
    assert event_id
    audit_col.insert_one.assert_called_once()
