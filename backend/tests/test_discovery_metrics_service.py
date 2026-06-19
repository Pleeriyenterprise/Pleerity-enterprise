"""
Stage S — DiscoveryMetricsService tests.

Measurement and ROI foundations only — no CRM, LeadService, routes, or UI.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import pytest

from services.discovery.discovery_metrics_service import (
    DiscoveryMetricsService,
    DiscoveryMetricsValidationError,
    MetricsCostInputs,
)
from services.discovery.discovery_models import (
    DiscoveryDuplicateStatus,
    DiscoveryErasureStatus,
    DiscoveryProviderId,
    DiscoveryReviewStatus,
)

DISCOVERY_ROOT = Path(__file__).resolve().parents[1] / "services" / "discovery"
LEAD_SERVICE_FILE = Path(__file__).resolve().parents[1] / "services" / "lead_service.py"
GENERATED_AT = datetime(2026, 6, 25, 12, 0, 0, tzinfo=timezone.utc)
CAMPAIGN_ID = "DCAMP-TEST-01"
COSTS = MetricsCostInputs(
    campaign_cost=252.0,
    provider_cost=0.0,
    manual_review_cost=0.0,
    currency="GBP",
)


def _prospect(
    prospect_id: str,
    *,
    provider: str = DiscoveryProviderId.CSV.value,
    review_status: str = DiscoveryReviewStatus.NEEDS_REVIEW.value,
    duplicate_status: str = DiscoveryDuplicateStatus.NONE.value,
    platform_quality_score: int = 78,
    review_priority: int = 60,
    imported_lead_id: str | None = None,
    erasure_status: str = DiscoveryErasureStatus.ACTIVE.value,
    risk_flags: List[str] | None = None,
) -> Dict[str, Any]:
    return {
        "prospect_id": prospect_id,
        "campaign_id": CAMPAIGN_ID,
        "discovery_run_id": "DRUN-TEST",
        "provider": provider,
        "review_status": review_status,
        "duplicate_status": duplicate_status,
        "platform_quality_score": platform_quality_score,
        "review_priority": review_priority,
        "imported_lead_id": imported_lead_id,
        "erasure_status": erasure_status,
        "risk_flags": risk_flags or [],
        "created_at": "2026-06-01T10:00:00Z",
    }


def _audit(
    event_type: str,
    *,
    prospect_id: str = "PROSP-1",
    actor_id: str = "reviewer-1",
    failure_code: str | None = None,
    blocking_reasons: List[str] | None = None,
    action: str | None = None,
    created_at: str = "2026-06-02T10:00:00Z",
) -> Dict[str, Any]:
    details: Dict[str, Any] = {}
    if failure_code:
        details["failure_code"] = failure_code
    if blocking_reasons:
        details["blocking_reasons"] = blocking_reasons
    if action:
        details["audit_context"] = {"action": action}
    return {
        "event_type": event_type,
        "prospect_id": prospect_id,
        "actor_id": actor_id,
        "created_at": created_at,
        "details": details,
    }


def _sample_prospects() -> List[Dict[str, Any]]:
    return [
        _prospect("PROSP-1", review_status=DiscoveryReviewStatus.IMPORTED.value, imported_lead_id="LEAD-1"),
        _prospect("PROSP-2", review_status=DiscoveryReviewStatus.APPROVED.value),
        _prospect("PROSP-3", review_status=DiscoveryReviewStatus.REJECTED.value),
        _prospect(
            "PROSP-4",
            review_status=DiscoveryReviewStatus.DUPLICATE_DETECTED.value,
            duplicate_status=DiscoveryDuplicateStatus.CONFIRMED.value,
        ),
        _prospect("PROSP-5", review_status=DiscoveryReviewStatus.NEEDS_REVIEW.value),
        _prospect(
            "PROSP-6",
            provider=DiscoveryProviderId.MANUAL.value,
            review_status=DiscoveryReviewStatus.IMPORTED.value,
            imported_lead_id="LEAD-2",
            platform_quality_score=90,
        ),
        _prospect(
            "PROSP-7",
            review_status=DiscoveryReviewStatus.NEEDS_REVIEW.value,
            erasure_status=DiscoveryErasureStatus.ERASED.value,
            risk_flags=["suppression_list_match"],
        ),
    ]


def _sample_audits() -> List[Dict[str, Any]]:
    return [
        _audit("PROSPECT_APPROVED", prospect_id="PROSP-2"),
        _audit("PROSPECT_REJECTED", prospect_id="PROSP-3"),
        _audit("PROSPECT_REVIEWED", prospect_id="PROSP-5", action="request_changes"),
        _audit("DUPLICATE_OVERRIDDEN", prospect_id="PROSP-4", actor_id="reviewer-2"),
        _audit("IMPORT_REQUESTED", prospect_id="PROSP-1"),
        _audit("IMPORT_REQUESTED", prospect_id="PROSP-6"),
        _audit("PROSPECT_IMPORTED", prospect_id="PROSP-1"),
        _audit("PROSPECT_IMPORTED", prospect_id="PROSP-6"),
        _audit(
            "IMPORT_BLOCKED",
            prospect_id="PROSP-8",
            failure_code="CRM_DUPLICATE",
        ),
        _audit("SUPPRESSION_MATCH", prospect_id="PROSP-7"),
        _audit("CONSENT_VALIDATION_FAILED", prospect_id="PROSP-9"),
        _audit("IMPORT_FAILED", prospect_id="PROSP-10"),
    ]


# --- Validation ---


def test_validate_metrics_inputs_ok():
    errors = DiscoveryMetricsService.validate_metrics_inputs(
        prospects=_sample_prospects(),
        audit_logs=_sample_audits(),
        costs=COSTS,
    )
    assert errors == []


def test_validate_metrics_inputs_rejects_negative_cost():
    errors = DiscoveryMetricsService.validate_metrics_inputs(
        prospects=_sample_prospects(),
        audit_logs=_sample_audits(),
        costs=MetricsCostInputs(campaign_cost=-1.0),
    )
    assert any("campaign_cost" in e for e in errors)


# --- Campaign metrics ---


def test_campaign_metrics():
    prospects = _sample_prospects()
    metrics = DiscoveryMetricsService.calculate_campaign_metrics(
        prospects, campaign_id=CAMPAIGN_ID
    )
    assert metrics.prospects_created == 7
    assert metrics.approved >= 3
    assert metrics.imported == 2
    assert metrics.rejected == 1


def test_campaign_funnel():
    funnel = DiscoveryMetricsService.calculate_campaign_funnel(
        _sample_prospects(), campaign_id=CAMPAIGN_ID
    )
    assert funnel.prospects_created == 7
    assert funnel.imported == 2
    assert funnel.lead_created == 2
    assert funnel.conversion_to_imported_pct == pytest.approx(28.57, abs=0.01)


def test_campaign_roi_calculation():
    roi = DiscoveryMetricsService.calculate_campaign_roi(
        campaign_id=CAMPAIGN_ID,
        campaign_cost=252.0,
        imported_leads_count=60,
        currency="GBP",
    )
    assert roi.cost_per_imported_lead == pytest.approx(4.2)


# --- Provider metrics ---


def test_provider_metrics_csv():
    prospects = _sample_prospects()
    audits = _sample_audits()
    metrics = DiscoveryMetricsService.calculate_provider_metrics(
        prospects, audits, provider=DiscoveryProviderId.CSV.value
    )
    assert metrics.prospects_discovered == 6
    assert metrics.prospects_imported == 1
    assert metrics.duplicate_rate > 0
    assert metrics.suppression_rate > 0


def test_provider_metrics_manual():
    metrics = DiscoveryMetricsService.calculate_provider_metrics(
        _sample_prospects(), _sample_audits(), provider=DiscoveryProviderId.MANUAL.value
    )
    assert metrics.prospects_discovered == 1
    assert metrics.prospects_imported == 1


def test_provider_comparison_uses_identical_model():
    prospects = _sample_prospects()
    audits = _sample_audits()
    csv = DiscoveryMetricsService.calculate_provider_metrics(
        prospects, audits, provider=DiscoveryProviderId.CSV.value
    ).to_dict()
    manual = DiscoveryMetricsService.calculate_provider_metrics(
        prospects, audits, provider=DiscoveryProviderId.MANUAL.value
    ).to_dict()
    assert set(csv.keys()) == set(manual.keys())


def test_provider_quality_average():
    metrics = DiscoveryMetricsService.calculate_provider_metrics(
        _sample_prospects(), _sample_audits(), provider=DiscoveryProviderId.CSV.value
    )
    score = DiscoveryMetricsService.calculate_provider_quality(metrics)
    assert 0 <= score <= 100


def test_provider_cost_efficiency():
    metrics = DiscoveryMetricsService.calculate_provider_metrics(
        _sample_prospects(), _sample_audits(), provider=DiscoveryProviderId.CSV.value
    )
    costs = DiscoveryMetricsService.calculate_provider_cost_efficiency(metrics, COSTS)
    assert costs.cost_per_prospect == pytest.approx(42.0)
    assert costs.cost_per_imported == pytest.approx(252.0)


def test_duplicate_rate_and_quality_averages():
    metrics = DiscoveryMetricsService.calculate_provider_metrics(
        _sample_prospects(), _sample_audits(), provider=DiscoveryProviderId.CSV.value
    )
    assert metrics.average_quality_score > 0
    assert metrics.average_review_priority > 0
    assert metrics.duplicate_rate > 0


def test_suppression_rate():
    metrics = DiscoveryMetricsService.calculate_provider_metrics(
        _sample_prospects(), _sample_audits(), provider=DiscoveryProviderId.CSV.value
    )
    assert metrics.suppression_rate > 0


# --- Review metrics ---


def test_review_metrics():
    review = DiscoveryMetricsService.calculate_review_metrics(
        _sample_prospects(), _sample_audits()
    )
    assert review.approval_rate > 0
    assert review.rejection_rate > 0
    assert review.request_changes_rate > 0
    assert review.duplicate_override_rate > 0
    assert len(review.reviewer_performance) >= 2


def test_review_cycle_time():
    hours = DiscoveryMetricsService.calculate_review_cycle_time(
        _sample_prospects(), _sample_audits()
    )
    assert hours == pytest.approx(24.0)


def test_reviewer_performance_attribution():
    reviewers = DiscoveryMetricsService.calculate_reviewer_performance(_sample_audits())
    by_id = {r.reviewer_id: r for r in reviewers}
    assert by_id["reviewer-1"].approvals >= 1
    assert by_id["reviewer-2"].duplicate_overrides == 1


# --- Import metrics ---


def test_import_metrics():
    metrics = DiscoveryMetricsService.calculate_import_metrics(_sample_audits())
    assert metrics.import_attempts == 2
    assert metrics.import_success == 2
    assert metrics.import_blocked == 1
    assert metrics.import_failed == 1
    assert metrics.duplicate_blocked == 1
    assert metrics.suppression_blocked >= 1
    assert metrics.compliance_blocked >= 1


def test_import_conversion():
    metrics = DiscoveryMetricsService.calculate_import_metrics(_sample_audits())
    conversion = DiscoveryMetricsService.calculate_import_conversion(metrics)
    assert conversion == 100.0


# --- Snapshot and summary ---


def test_metrics_snapshot_generation():
    snapshot = DiscoveryMetricsService.build_metrics_snapshot(
        prospects=_sample_prospects(),
        audit_logs=_sample_audits(),
        campaign_id=CAMPAIGN_ID,
        costs=COSTS,
        generated_at=GENERATED_AT,
    )
    assert snapshot["generated_at"] == "2026-06-25T12:00:00Z"
    assert DiscoveryProviderId.CSV.value in snapshot["provider_metrics"]
    assert DiscoveryProviderId.APOLLO.value in snapshot["provider_metrics"]
    assert snapshot["campaign_metrics"] is not None
    assert snapshot["review_metrics"] is not None
    assert snapshot["import_metrics"] is not None


def test_metrics_snapshot_is_deterministic():
    kwargs = dict(
        prospects=_sample_prospects(),
        audit_logs=_sample_audits(),
        campaign_id=CAMPAIGN_ID,
        costs=COSTS,
        generated_at=GENERATED_AT,
    )
    first = DiscoveryMetricsService.build_metrics_snapshot(**kwargs)
    second = DiscoveryMetricsService.build_metrics_snapshot(**kwargs)
    assert first == second


def test_metrics_summary_generation():
    snapshot = DiscoveryMetricsService.build_metrics_snapshot(
        prospects=_sample_prospects(),
        audit_logs=_sample_audits(),
        campaign_id=CAMPAIGN_ID,
        costs=COSTS,
        generated_at=GENERATED_AT,
    )
    summary = DiscoveryMetricsService.build_metrics_summary(
        snapshot, provider=DiscoveryProviderId.CSV.value
    )
    assert "Provider: CSV" in summary
    assert "Prospects:" in summary
    assert "Approved:" in summary
    assert "Imported:" in summary
    assert "Duplicate Rate:" in summary
    assert "Average Quality:" in summary
    assert "Cost Per Import:" in summary


def test_metrics_snapshot_invalid_inputs_raise():
    with pytest.raises(DiscoveryMetricsValidationError):
        DiscoveryMetricsService.build_metrics_snapshot(
            prospects=[{"missing": "fields"}],
            audit_logs=[],
        )


# --- Scope guards ---


def test_no_leadservice_changes():
    text = LEAD_SERVICE_FILE.read_text(encoding="utf-8")
    assert "DiscoveryMetricsService" not in text


def test_no_provider_integrations_in_metrics_service():
    text = (DISCOVERY_ROOT / "discovery_metrics_service.py").read_text(encoding="utf-8")
    assert "csv_import_provider" not in text
    assert "discovery_provider_registry" not in text
    assert not re.search(r"https?://", text)


def test_no_routes_in_metrics_service():
    text = (DISCOVERY_ROOT / "discovery_metrics_service.py").read_text(encoding="utf-8")
    assert "APIRouter" not in text
    assert "FastAPI" not in text


def test_no_notifications_in_metrics_service():
    text = (DISCOVERY_ROOT / "discovery_metrics_service.py").read_text(encoding="utf-8")
    assert "send_notification" not in text.lower()
    assert "notification_service" not in text.lower()


def test_no_ui_in_metrics_service():
    text = (DISCOVERY_ROOT / "discovery_metrics_service.py").read_text(encoding="utf-8")
    assert "dashboard" not in text.lower()
    assert "react" not in text.lower()
