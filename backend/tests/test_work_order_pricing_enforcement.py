"""Unit tests for quote gating (no database)."""
import pytest

from services import maintenance_service as ms
from services.work_order_pricing_constants import (
    PRICE_STATUS_APPROVED,
    PRICE_STATUS_AWAITING_QUOTE,
    PRICING_MODE_COMPLIANCE_FIXED_QUOTE,
    PRICING_MODE_MAINTENANCE_INSPECTION_REQUIRED,
    PRICING_MODE_MAINTENANCE_PREQUOTE,
)
from services.work_order_pricing_service import (
    assert_may_transition_to_completed,
    assert_may_transition_to_in_progress,
    contractor_may_offer_complete_job,
    contractor_may_offer_start_job,
    pricing_workflow_applies,
)


def test_pricing_workflow_absent_legacy():
    wo = {"status": ms.STATUS_SCHEDULED, "work_order_kind": "MAINTENANCE"}
    assert not pricing_workflow_applies(wo)


def test_compliance_blocks_in_progress_without_approval():
    wo = {
        "pricing_mode": PRICING_MODE_COMPLIANCE_FIXED_QUOTE,
        "price_status": PRICE_STATUS_AWAITING_QUOTE,
        "work_order_kind": "COMPLIANCE",
    }
    with pytest.raises(ValueError, match="approved quote"):
        assert_may_transition_to_in_progress(wo)


def test_compliance_allows_in_progress_when_approved():
    wo = {
        "pricing_mode": PRICING_MODE_COMPLIANCE_FIXED_QUOTE,
        "price_status": PRICE_STATUS_APPROVED,
        "quoted_price": 100.0,
        "work_order_kind": "COMPLIANCE",
    }
    assert_may_transition_to_in_progress(wo)


def test_inspection_maintenance_allows_in_progress_before_inspection_done():
    wo = {
        "pricing_mode": PRICING_MODE_MAINTENANCE_INSPECTION_REQUIRED,
        "price_status": PRICE_STATUS_AWAITING_QUOTE,
        "work_order_kind": "MAINTENANCE",
        "inspection_completed_at": None,
    }
    assert_may_transition_to_in_progress(wo)
    assert contractor_may_offer_start_job(wo)


def test_inspection_maintenance_blocks_in_progress_after_inspection_without_quote():
    wo = {
        "pricing_mode": PRICING_MODE_MAINTENANCE_INSPECTION_REQUIRED,
        "price_status": PRICE_STATUS_AWAITING_QUOTE,
        "work_order_kind": "MAINTENANCE",
        "inspection_completed_at": "2026-01-01T12:00:00+00:00",
    }
    with pytest.raises(ValueError, match="approved quote"):
        assert_may_transition_to_in_progress(wo)
    assert not contractor_may_offer_start_job(wo)


def test_prequote_maintenance_blocks_complete_without_approval():
    wo = {
        "pricing_mode": PRICING_MODE_MAINTENANCE_PREQUOTE,
        "price_status": PRICE_STATUS_AWAITING_QUOTE,
        "work_order_kind": "MAINTENANCE",
    }
    with pytest.raises(ValueError, match="approved quote"):
        assert_may_transition_to_completed(wo)
    assert not contractor_may_offer_complete_job(wo)
