"""Phase 2C commercial entitlement governance — unit tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.commercial_entitlement_execution_service import (
    CommercialEntitlementExecutionError,
    derive_customer_impact_preview,
    prevent_duplicate_active_exception,
    validate_transition,
    ACTION_GRANT_GRACE,
    ACTION_SUSPEND_BILLING,
)
from services.commercial_entitlement_expiry_service import enforce_review_requirements
from services.commercial_entitlement_notification_service import build_commercial_continuity_email_html
from services.commercial_entitlement_service import (
    EXCEPTION_SPONSORED_ACCESS,
    STATE_GRACE_PERIOD,
    STATE_BILLING_SUSPENDED,
    derive_customer_access_state,
    derive_effective_access_reason,
    validate_entitlement_authority,
    detect_entitlement_drift,
    ACCESS_FULL,
    ACCESS_SUSPENDED,
)
from services.commercial_entitlement_stripe_convergence_service import prevent_duplicate_subscription_risk


def _governance(**kwargs):
    base = {
        "governance_id": "gov-1",
        "entitlement_state": STATE_GRACE_PERIOD,
        "exception_type": "grace_extension",
        "entitlement_expiry_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
        "access_policy": ACCESS_FULL,
    }
    base.update(kwargs)
    return base


def test_derive_effective_access_reason_grace():
    reason = derive_effective_access_reason(_governance())
    assert "Grace period until" in (reason or "")


def test_derive_customer_access_state_preserves_continuity_on_billing_suspend():
    signals = {
        "client": {"billing_lifecycle_state": "active", "subscription_status": "ACTIVE"},
        "billing": {"billing_lifecycle_state": "active", "subscription_status": "ACTIVE"},
        "active_governance": _governance(
            entitlement_state=STATE_BILLING_SUSPENDED,
            exception_type="billing_suspension",
        ),
    }
    access = derive_customer_access_state(signals)
    assert access["canonical_entitlement_state"] == "ENABLED"
    assert access["access_policy"] == ACCESS_FULL


def test_derive_customer_access_state_restricted_suspends():
    signals = {
        "client": {"billing_lifecycle_state": "active", "subscription_status": "ACTIVE"},
        "billing": {},
        "active_governance": _governance(
            entitlement_state="RESTRICTED",
            access_policy=ACCESS_SUSPENDED,
        ),
    }
    access = derive_customer_access_state(signals)
    assert access["canonical_entitlement_state"] == "SUSPENDED"


def test_validate_sponsored_requires_sponsor_and_expiry():
    ok, err = validate_entitlement_authority(
        exception_type=EXCEPTION_SPONSORED_ACCESS,
        duration_days=30,
        sponsor_reference="",
        entitlement_expiry_at=None,
    )
    assert not ok
    assert "Sponsor" in (err or "")


def test_validate_sponsored_ok_with_duration():
    ok, err = validate_entitlement_authority(
        exception_type=EXCEPTION_SPONSORED_ACCESS,
        duration_days=30,
        sponsor_reference="ACME-PILOT",
        entitlement_expiry_at=None,
    )
    assert ok
    assert err is None


def test_validate_transition_blocks_duplicate_active():
    with pytest.raises(CommercialEntitlementExecutionError) as exc:
        validate_transition(ACTION_GRANT_GRACE, has_active=True)
    assert exc.value.code == "ACTIVE_EXCEPTION_EXISTS"


def test_impact_preview_customer_safe_copy():
    preview = derive_customer_impact_preview(
        action=ACTION_SUSPEND_BILLING,
        duration_days=14,
        entitlement_expiry_at=None,
        sponsor_reference=None,
        access_policy=ACCESS_FULL,
        customer_note=None,
    )
    assert "Billing" in preview["customer_impact"]
    assert "compliance" in preview["operational_continuity"].lower()
    assert "Stripe" not in preview["customer_impact"]


def test_impact_preview_no_stripe_jargon_in_customer_line():
    preview = derive_customer_impact_preview(
        action=ACTION_GRANT_GRACE,
        duration_days=7,
        entitlement_expiry_at=datetime.now(timezone.utc) + timedelta(days=7),
        sponsor_reference=None,
        access_policy=ACCESS_FULL,
        customer_note=None,
    )
    assert "stripe" not in preview["customer_impact"].lower()
    assert "override" not in preview["customer_impact"].lower()


def test_notification_html_avoids_technical_billing_jargon():
    html = build_commercial_continuity_email_html(
        body_line="Your access has been temporarily extended while we resolve your account issue.",
        effective_access_reason="Grace period until 2026-06-10",
        expiry_label="2026-06-10",
    )
    assert "pause_collection" not in html.lower()
    assert "stripe" not in html.lower()


def test_enforce_review_sponsored_without_dates():
    ok, err = enforce_review_requirements({"exception_type": EXCEPTION_SPONSORED_ACCESS})
    assert not ok


@pytest.mark.asyncio
async def test_prevent_duplicate_active_exception():
    with patch(
        "services.commercial_entitlement_execution_service.get_active_governance",
        new_callable=AsyncMock,
        return_value={"governance_id": "x"},
    ):
        with pytest.raises(CommercialEntitlementExecutionError) as exc:
            await prevent_duplicate_active_exception("client-1")
        assert exc.value.code == "ACTIVE_EXCEPTION_EXISTS"


@pytest.mark.asyncio
async def test_detect_entitlement_drift_expired_governance():
    expired = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    with patch(
        "services.commercial_entitlement_service.load_client_billing_signals",
        new_callable=AsyncMock,
        return_value={
            "found": True,
            "client": {"canonical_entitlement_state": "ENABLED"},
            "billing": {"canonical_entitlement_state": "ENABLED"},
        },
    ), patch(
        "services.commercial_entitlement_service.get_active_governance",
        new_callable=AsyncMock,
        return_value=_governance(entitlement_expiry_at=expired),
    ):
        drift = await detect_entitlement_drift("client-1")
        assert drift["drift_detected"] is True
        assert drift["governance_expired"] is True


@pytest.mark.asyncio
async def test_prevent_duplicate_subscription_risk():
    db = MagicMock()
    db.client_billing.find_one = AsyncMock(
        return_value={
            "stripe_subscription_id": "sub_a",
            "stripe_subscription_ids": ["sub_b"],
        }
    )
    with patch("services.commercial_entitlement_stripe_convergence_service.database") as mock_db:
        mock_db.get_db.return_value = db
        result = await prevent_duplicate_subscription_risk("client-1")
    assert result["duplicate_risk"] is True
    assert len(result["subscription_ids"]) == 2
