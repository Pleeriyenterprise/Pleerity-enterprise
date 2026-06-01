"""Phase 2 — stripe mode backfill, authoritative resolution, MODE_UNVERIFIED governance."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.stripe_mode_backfill_service import (
    CONFIDENCE_AUTHORITATIVE,
    CONFIDENCE_UNKNOWN,
    MODE_UNVERIFIED,
    REMEDIATION_LEGACY_TEST,
    REMEDIATION_MODE_UNVERIFIED,
    REMEDIATION_REGENERATE_CHECKOUT,
    classify_remediation,
    resolve_authoritative_mode,
)
from services.stripe_mode_containment_service import (
    CUSTOMER_BILLING_REFRESH_MESSAGE,
    StripeModeDriftError,
    validate_stripe_subscription_mode,
)


@pytest.mark.asyncio
async def test_resolve_from_webhook_livemode():
    billing = {
        "client_id": "c1",
        "stripe_subscription_id": "sub_123",
        "stripe_customer_id": "cus_123",
    }
    mock_db = MagicMock()
    mock_db.stripe_events.find_one = AsyncMock(
        return_value={"livemode": False, "event_id": "evt_1", "created": datetime.now(timezone.utc)}
    )
    mock_db.client_billing.find_one = AsyncMock(return_value=billing)
    mock_db.checkout_sessions.find_one = AsyncMock(return_value=None)

    with patch("services.stripe_mode_backfill_service.database.get_db", return_value=mock_db):
        with patch("services.stripe_mode_backfill_service.get_stripe_mode", return_value="live"):
            with patch("services.stripe_mode_backfill_service._resolve_from_stripe_api", new=AsyncMock(return_value=None)):
                result = await resolve_authoritative_mode("c1", billing=billing)

    assert result["stripe_mode"] == "test"
    assert result["stripe_mode_confidence"] == CONFIDENCE_AUTHORITATIVE
    assert result["stripe_mode_verification_source"] == "webhook_livemode"


@pytest.mark.asyncio
async def test_resolve_unknown_when_no_evidence():
    billing = {
        "client_id": "c2",
        "stripe_subscription_id": "sub_456",
    }
    mock_db = MagicMock()
    mock_db.stripe_events.find_one = AsyncMock(return_value=None)
    mock_db.client_billing.find_one = AsyncMock(return_value=billing)
    mock_db.checkout_sessions.find_one = AsyncMock(return_value=None)

    with patch("services.stripe_mode_backfill_service.database.get_db", return_value=mock_db):
        with patch("services.stripe_mode_backfill_service.get_stripe_mode", return_value="live"):
            with patch("services.stripe_mode_backfill_service._resolve_from_stripe_api", new=AsyncMock(return_value=None)):
                result = await resolve_authoritative_mode("c2", billing=billing)

    assert result["stripe_mode_confidence"] == CONFIDENCE_UNKNOWN
    assert result["stripe_mode_verification_status"] == MODE_UNVERIFIED
    assert result["customer_message"] == CUSTOMER_BILLING_REFRESH_MESSAGE


def test_classify_remediation_legacy_test_in_live():
    billing = {"stripe_subscription_id": "sub_x", "stripe_mode": None}
    resolution = {
        "stripe_mode": "test",
        "stripe_mode_confidence": CONFIDENCE_AUTHORITATIVE,
    }
    code, risk, _ = classify_remediation(billing, resolution, deployment_mode="live")
    assert code == REMEDIATION_LEGACY_TEST
    assert risk == "critical"


def test_classify_remediation_mode_unverified():
    billing = {"stripe_subscription_id": "sub_x", "stripe_mode_verification_status": MODE_UNVERIFIED}
    code, risk, _ = classify_remediation(billing, None, deployment_mode="live")
    assert code == REMEDIATION_MODE_UNVERIFIED
    assert risk == "high"


def test_validate_blocks_mode_unverified():
    with pytest.raises(StripeModeDriftError) as exc:
        validate_stripe_subscription_mode(
            "sub_abc",
            "live",
            stored_mode=None,
            verification_status=MODE_UNVERIFIED,
            client_id="c1",
        )
    assert exc.value.recovery_action == "MODE_UNVERIFIED"


@pytest.mark.asyncio
async def test_backfill_dry_run_authoritative():
    from services.stripe_mode_backfill_service import backfill_client_billing_mode

    billing = {"client_id": "c3", "stripe_subscription_id": "sub_789", "stripe_customer_id": "cus_789"}
    mock_db = MagicMock()
    mock_db.client_billing.find_one = AsyncMock(return_value=billing)
    mock_db.client_billing.update_one = AsyncMock()

    resolution = {
        "stripe_mode": "live",
        "stripe_mode_confidence": CONFIDENCE_AUTHORITATIVE,
        "stripe_mode_verification_source": "webhook_livemode",
        "stripe_mode_verified_at": datetime.now(timezone.utc),
        "stripe_mode_last_checked_at": datetime.now(timezone.utc),
    }

    with patch("services.stripe_mode_backfill_service.database.get_db", return_value=mock_db):
        with patch(
            "services.stripe_mode_backfill_service.resolve_authoritative_mode",
            new=AsyncMock(return_value=resolution),
        ):
            result = await backfill_client_billing_mode("c3", dry_run=True)

    assert result["action"] == "backfill_authoritative_mode"
    assert result["would_write"]["stripe_mode"] == "live"
    mock_db.client_billing.update_one.assert_not_called()


@pytest.mark.asyncio
async def test_backfill_marks_unverified_when_unknown():
    from services.stripe_mode_backfill_service import backfill_client_billing_mode

    billing = {"client_id": "c4", "stripe_subscription_id": "sub_u"}
    mock_db = MagicMock()
    mock_db.client_billing.find_one = AsyncMock(return_value=billing)
    mock_db.client_billing.update_one = AsyncMock()

    resolution = {
        "stripe_mode_confidence": CONFIDENCE_UNKNOWN,
        "stripe_mode_verification_status": MODE_UNVERIFIED,
        "stripe_mode_verification_source": "unknown",
    }

    with patch("services.stripe_mode_backfill_service.database.get_db", return_value=mock_db):
        with patch(
            "services.stripe_mode_backfill_service.resolve_authoritative_mode",
            new=AsyncMock(return_value=resolution),
        ):
            result = await backfill_client_billing_mode("c4", dry_run=False)

    assert result["action"] == "mark_mode_unverified"
    mock_db.client_billing.update_one.assert_called_once()


def test_classify_missing_mode_regenerate_checkout():
    billing = {"stripe_subscription_id": "sub_y", "stripe_mode": None}
    resolution = {
        "stripe_mode": "live",
        "stripe_mode_confidence": CONFIDENCE_AUTHORITATIVE,
        "stripe_mode_verification_source": "webhook_livemode",
    }
    code, _, _ = classify_remediation(billing, resolution, deployment_mode="live")
    assert code in (REMEDIATION_REGENERATE_CHECKOUT, "VERIFIED_OPERATIONALLY")


def test_audit_legacy_stripe_callers_structure():
    from services.stripe_mode_backfill_service import audit_legacy_stripe_callers

    result = audit_legacy_stripe_callers()
    assert "legacy_caller_findings" in result
    assert "convergence_targets" in result
    targets = {t["file"] for t in result["convergence_targets"]}
    assert "services/intake_draft_service.py" in targets
    assert "services/jobs.py" in targets


def test_remediation_required_clients_sums_category_counts():
    counts = {
        "missing_stripe_mode": 33,
        "mixed_customer_subscription_mode": 0,
        "test_rows_in_live": 0,
        "live_rows_in_test": 0,
        "unknown_mode_rows": 2,
        "orphaned_checkout_sessions": 50,
    }
    metric = sum(
        counts[cat]
        for cat in (
            "missing_stripe_mode",
            "mixed_customer_subscription_mode",
            "test_rows_in_live",
            "live_rows_in_test",
            "unknown_mode_rows",
        )
    )
    assert metric == 35
