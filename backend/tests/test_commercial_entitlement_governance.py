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
    _lifecycle_action_warnings,
    _derive_executable_actions,
    resolve_authoritative_plan_code,
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
    assert access["effective_entitlement_state"] == "ENABLED"
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


def test_suspend_billing_on_cancelled_preserves_canonical_and_restores_effective_access():
    signals = {
        "client": {
            "billing_lifecycle_state": "cancelled",
            "subscription_status": "CANCELED",
            "billing_plan": "PLAN_3_PRO",
        },
        "billing": {
            "billing_lifecycle_state": "cancelled",
            "subscription_status": "CANCELED",
            "current_plan_code": "PLAN_3_PRO",
        },
        "active_governance": _governance(
            entitlement_state=STATE_BILLING_SUSPENDED,
            exception_type="billing_suspension",
            access_policy=ACCESS_FULL,
            restored_plan_code="PLAN_3_PRO",
        ),
    }
    access = derive_customer_access_state(signals)
    assert access["canonical_entitlement_state"] == "CANCELLED"
    assert access["underlying_canonical_entitlement_state"] == "CANCELLED"
    assert access["effective_entitlement_state"] == "ENABLED"
    assert access["restored_plan_code"] == "PLAN_3_PRO"
    assert access["access_policy"] == ACCESS_FULL


def test_impact_preview_operator_copy_describes_stripe_pause_for_active():
    preview = derive_customer_impact_preview(
        action=ACTION_SUSPEND_BILLING,
        duration_days=14,
        entitlement_expiry_at=None,
        sponsor_reference=None,
        access_policy=ACCESS_FULL,
        customer_note=None,
        underlying_canonical="ENABLED",
        restored_plan_code="PLAN_2_PORTFOLIO",
        stripe_pause_mode="pause_collection",
    )
    assert "pause_collection" in preview["stripe_impact"]
    assert "paused" in preview["billing_impact"].lower()
    assert "reactivated" not in preview["customer_impact"].lower()


def test_impact_preview_cancelled_does_not_claim_subscription_reactivated():
    preview = derive_customer_impact_preview(
        action=ACTION_SUSPEND_BILLING,
        duration_days=14,
        entitlement_expiry_at=None,
        sponsor_reference=None,
        access_policy=ACCESS_FULL,
        customer_note=None,
        underlying_canonical="CANCELLED",
        restored_plan_code="PLAN_3_PRO",
        stripe_pause_mode="already_non_collecting",
    )
    assert "remains cancelled" in preview["customer_impact"].lower()
    assert "not be created" in preview["billing_impact"].lower() or "non-collecting" in preview["billing_impact"].lower()
    assert "Professional" in preview["customer_impact"] or "PLAN_3_PRO" in preview["access_impact"]


def test_lifecycle_warnings_for_cancelled_without_blocking_actions():
    signals = {
        "found": True,
        "client": {"billing_lifecycle_state": "cancelled", "subscription_status": "CANCELED"},
        "billing": {"billing_lifecycle_state": "cancelled", "subscription_status": "CANCELED"},
    }
    warnings = _lifecycle_action_warnings(signals, None)
    actions = _derive_executable_actions(signals, None)
    assert "suspend_billing" in actions
    assert "suspend_billing" in warnings
    assert "cancelled" in warnings["suspend_billing"].lower()


def test_lifecycle_warnings_empty_when_active_exception():
    signals = {
        "client": {"billing_lifecycle_state": "active", "subscription_status": "ACTIVE"},
        "billing": {},
    }
    warnings = _lifecycle_action_warnings(signals, _governance())
    assert warnings == {}


def test_validate_transition_blocks_revoke_without_active():
    with pytest.raises(CommercialEntitlementExecutionError) as exc:
        validate_transition("resume_billing", has_active=False)
    assert exc.value.code == "NO_ACTIVE_EXCEPTION"


def test_duration_cap_grace_rejects_over_max():
    from services.commercial_entitlement_service import EXCEPTION_GRACE_EXTENSION

    ok, err = validate_entitlement_authority(
        exception_type=EXCEPTION_GRACE_EXTENSION,
        duration_days=31,
        sponsor_reference=None,
        entitlement_expiry_at=None,
    )
    assert not ok
    assert "30" in (err or "")


@pytest.mark.asyncio
async def test_persist_governance_duplicate_key_maps_to_active_exception():
    from pymongo.errors import DuplicateKeyError
    from services.commercial_entitlement_execution_service import _persist_governance_row

    gov = MagicMock()
    gov.insert_one = AsyncMock(side_effect=DuplicateKeyError("E11000"))
    db = MagicMock()
    db.__getitem__.return_value = gov
    with patch("services.commercial_entitlement_execution_service.database") as mock_db:
        mock_db.get_db.return_value = db
        with pytest.raises(CommercialEntitlementExecutionError) as exc:
            await _persist_governance_row(
                client_id="c1",
                exception_type="billing_suspension",
                entitlement_state=STATE_BILLING_SUSPENDED,
                reason="Help required for billing review",
                scope="account",
                actor={"id": "a1", "email": "a@example.com"},
                origin="test",
                duration_days=14,
                entitlement_expiry_at=None,
                entitlement_review_at=None,
                entitlement_review_required=False,
                sponsor_reference=None,
                access_policy=ACCESS_FULL,
                supersedes_governance_id=None,
                send_customer_email=False,
            )
    assert exc.value.code == "ACTIVE_EXCEPTION_EXISTS"


def test_resolve_authoritative_plan_code_precedence_and_no_solo_default():
    empty = resolve_authoritative_plan_code({"client": {}, "billing": {}})
    assert empty == (None, None)
    unknown = resolve_authoritative_plan_code({"client": {"billing_plan": "ENTERPRISE_UNLIMITED"}, "billing": {}})
    assert unknown == (None, None)
    billed = resolve_authoritative_plan_code(
        {
            "client": {"billing_plan": "PLAN_1_SOLO"},
            "billing": {"current_plan_code": "PLAN_3_PRO"},
        }
    )
    assert billed == ("PLAN_3_PRO", "client_billing.current_plan_code")
    alias = resolve_authoritative_plan_code({"client": {"selected_plan": "Professional"}, "billing": {}})
    assert alias[0] == "PLAN_3_PRO"


def test_waive_onboarding_does_not_overlay_cancelled_access():
    signals = {
        "client": {"billing_lifecycle_state": "cancelled", "subscription_status": "CANCELED"},
        "billing": {"billing_lifecycle_state": "cancelled", "subscription_status": "CANCELED"},
        "active_governance": _governance(
            entitlement_state="WAIVED",
            exception_type="onboarding_waiver",
            access_policy=ACCESS_FULL,
        ),
    }
    access = derive_customer_access_state(signals)
    assert access["canonical_entitlement_state"] == "CANCELLED"
    assert access["effective_entitlement_state"] == "CANCELLED"
