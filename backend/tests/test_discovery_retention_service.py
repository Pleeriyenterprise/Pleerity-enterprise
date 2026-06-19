"""
Stage T — DiscoveryRetentionService tests.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from services.discovery.discovery_models import (
    DiscoveryErasureStatus,
    DiscoveryReviewStatus,
)
from services.discovery.discovery_models import is_frozen_audit_event
from services.discovery.discovery_retention_policy import (
    POLICY_CATEGORY_IMPORTED,
    POLICY_CATEGORY_REJECTED,
)
from services.discovery.discovery_retention_service import DiscoveryRetentionService

NOW = datetime(2026, 6, 30, 12, 0, 0, tzinfo=timezone.utc)
LEAD_SERVICE = Path(__file__).resolve().parents[1] / "services" / "lead_service.py"


def _prospect(**overrides):
    base = {
        "prospect_id": "PROSP-T-1",
        "campaign_id": "DCAMP-T",
        "created_at": (NOW - timedelta(days=400)).isoformat().replace("+00:00", "Z"),
        "review_status": DiscoveryReviewStatus.REJECTED.value,
        "erasure_status": DiscoveryErasureStatus.ACTIVE.value,
        "legal_hold": False,
    }
    base.update(overrides)
    return base


def test_validate_retention_policy():
    errors = DiscoveryRetentionService.validate_retention_policy()
    assert errors == []


def test_retention_expiry_calculation():
    prospect = _prospect()
    expiry = DiscoveryRetentionService.determine_retention_expiry(
        prospect, evaluated_at=NOW
    )
    assert expiry is not None
    assert expiry <= NOW


def test_retention_status_expired_for_old_rejected():
    result = DiscoveryRetentionService.evaluate_retention_status(
        _prospect(), evaluated_at=NOW
    )
    assert result.category == POLICY_CATEGORY_REJECTED
    assert result.retention_expiry_reached is True
    assert result.status == "expired"


def test_retention_status_indefinite_for_imported():
    result = DiscoveryRetentionService.evaluate_retention_status(
        _prospect(
            review_status=DiscoveryReviewStatus.IMPORTED.value,
            imported_lead_id="LEAD-1",
        ),
        evaluated_at=NOW,
    )
    assert result.category == POLICY_CATEGORY_IMPORTED
    assert result.retention_expiry_reached is False
    assert result.status == "indefinite"


def test_retention_summary():
    summary = DiscoveryRetentionService.build_retention_summary(
        _prospect(), evaluated_at=NOW
    )
    assert "Retention Category:" in summary
    assert "Retention Expiry:" in summary


def test_purge_eligible_old_rejected():
    purge = DiscoveryRetentionService.determine_purge_eligibility(
        _prospect(), evaluated_at=NOW
    )
    assert purge.retention_expiry_reached is True
    assert purge.eligible is True
    assert purge.blocking_reasons == []


def test_purge_blocked_by_legal_hold():
    purge = DiscoveryRetentionService.determine_purge_eligibility(
        _prospect(legal_hold=True), evaluated_at=NOW
    )
    assert purge.eligible is False
    assert any("legal_hold" in r for r in purge.blocking_reasons)


def test_purge_blocked_active_review():
    purge = DiscoveryRetentionService.determine_purge_eligibility(
        _prospect(review_status=DiscoveryReviewStatus.NEEDS_REVIEW.value),
        evaluated_at=NOW,
    )
    assert purge.eligible is False
    assert any("active review" in r for r in purge.blocking_reasons)


def test_lifecycle_audit_events_frozen():
    for event in (
        "ERASURE_REQUESTED",
        "ERASURE_EXECUTED",
        "LEGAL_HOLD_APPLIED",
        "RETENTION_EXPIRY_REACHED",
        "PURGE_ELIGIBLE",
        "PURGE_BLOCKED",
    ):
        assert is_frozen_audit_event(event), event


def test_no_leadservice_changes():
    assert "DiscoveryRetentionService" not in LEAD_SERVICE.read_text(encoding="utf-8")
