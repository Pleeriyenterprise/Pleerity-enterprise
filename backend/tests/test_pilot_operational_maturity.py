"""Pilot operational maturity — separated domains, health, anomalies, template governance."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from models.pilot_lifecycle import PilotStatus
from models.pilot_operational import PilotAnomalyCode, PilotGovernanceStatus
from services.agreement_template_governance import (
    AgreementTemplateGovernanceError,
    assert_agreement_template_publishable,
    validate_agreement_template_for_publish,
)
from services.pilot_conversion_risk import compute_conversion_risk_flags
from services.pilot_lifecycle_domains import (
    build_lifecycle_domains_snapshot,
    detect_domain_inconsistencies,
    derive_pilot_billing_status,
    derive_pilot_entitlement_status,
    derive_pilot_governance_status,
)
from services.pilot_operational_health import compute_pilot_health


def _client(**kw):
    base = {
        "client_id": "c1",
        "pilot_status": PilotStatus.ACTIVE.value,
        "pilot_program_type": "FOUNDING_PILOT",
        "pilot_started_at": datetime.now(timezone.utc) - timedelta(days=30),
        "pilot_expires_at": datetime.now(timezone.utc) + timedelta(days=10),
        "onboarding_status": "PROVISIONED",
        "pilot_stripe_payment_method_collected": True,
    }
    base.update(kw)
    return base


def test_governance_status_maps_converted():
    c = _client(pilot_status=PilotStatus.CONVERTED_TO_PAID.value)
    assert derive_pilot_governance_status(c) == PilotGovernanceStatus.CONVERTED.value


def test_billing_status_from_stripe():
    c = _client()
    billing = {"subscription_status": "trialing"}
    assert derive_pilot_billing_status(c, billing) == "trialing"
    billing2 = {"subscription_status": "active"}
    assert derive_pilot_billing_status(c, billing2) == "active"


def test_entitlement_comped_enabled():
    c = _client(pilot_status=PilotStatus.COMPED.value)
    assert derive_pilot_entitlement_status(c, {}) == "enabled"


def test_detect_expired_pilot_active_sub():
    c = _client(pilot_status=PilotStatus.EXPIRED.value, pilot_governance_status="expired")
    billing = {"subscription_status": "active"}
    issues = detect_domain_inconsistencies(c, billing)
    codes = [i["code"] for i in issues]
    assert PilotAnomalyCode.EXPIRED_PILOT_ACTIVE_PAID_SUB.value in codes


def test_conversion_risk_missing_pm():
    c = _client(
        pilot_stripe_payment_method_collected=False,
        pilot_expected_first_paid_invoice_at=datetime.now(timezone.utc) + timedelta(days=5),
    )
    risk = compute_conversion_risk_flags(c, billing={"subscription_status": "trialing"})
    assert risk["missing_payment_method"] is True
    assert risk["approaching_paid_transition"] is True


def test_health_scoring_conversion_ready():
    c = _client()
    health = compute_pilot_health(
        c,
        billing={"subscription_status": "trialing"},
        document_count=2,
        has_recent_activity=True,
    )
    assert health["pilot_health_score"] >= 60
    assert health["pilot_health_band"] in ("healthy", "conversion_ready", "at_risk")


def test_agreement_template_governance_blocks_missing_pilot_line():
    blocks = [
        {
            "key": "plan_fees",
            "enabled": True,
            "content": "{{monthly_fee}} {{onboarding_fee_line}} recurring subscription charges apply.",
        }
    ]
    valid, issues = validate_agreement_template_for_publish(blocks)
    assert not valid
    assert any("pilot_offer_line" in i for i in issues)


def test_agreement_template_governance_passes_complete_blocks():
    from services.agreement_seed import DEFAULT_BLOCKS

    valid, issues = validate_agreement_template_for_publish(DEFAULT_BLOCKS)
    assert valid, issues
    assert_agreement_template_publishable(DEFAULT_BLOCKS)


def test_agreement_template_governance_raises():
    with pytest.raises(AgreementTemplateGovernanceError):
        assert_agreement_template_publishable(
            [{"key": "plan_fees", "enabled": True, "content": "No placeholders"}]
        )


@pytest.mark.asyncio
async def test_sync_lifecycle_domains_persists():
    from services.pilot_lifecycle_domains import sync_lifecycle_domains_to_client

    client = _client()
    billing = {"subscription_status": "trialing", "canonical_entitlement_state": "ENABLED"}
    mock_db = MagicMock()
    mock_db.clients.find_one = AsyncMock(return_value=client)
    mock_db.client_billing.find_one = AsyncMock(return_value=billing)
    mock_db.clients.update_one = AsyncMock()
    with patch("database.database.get_db", return_value=mock_db):
        domains = await sync_lifecycle_domains_to_client("c1", client=client, billing=billing)
    assert domains["pilot_governance_status"] == "active"
    assert domains["pilot_billing_status"] == "trialing"
    mock_db.clients.update_one.assert_awaited()


@pytest.mark.asyncio
async def test_build_pilot_ops_summary():
    from services.pilot_lifecycle_service import build_pilot_ops_summary

    c = _client(pilot_health_score=80, pilot_health_band="healthy")
    ops = build_pilot_ops_summary(c, {"subscription_status": "trialing"})
    assert ops["lifecycle_domains"]["pilot_governance_status"] == "active"
    assert "conversion_readiness" in ops
    assert ops["payment_method_collected"] is True


def test_lifecycle_domains_snapshot_separated():
    c = _client(pilot_status=PilotStatus.EXTENDED.value)
    snap = build_lifecycle_domains_snapshot(c, {"subscription_status": "past_due"})
    assert snap["pilot_governance_status"] == "extended"
    assert snap["pilot_billing_status"] == "past_due"
