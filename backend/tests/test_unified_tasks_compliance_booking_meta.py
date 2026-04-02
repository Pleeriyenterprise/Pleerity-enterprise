"""Unified task DTO: compliance execution booking metadata for Today / Command Centre."""

from datetime import datetime, timezone

from services.priority_actions import (
    ACTION_CERT_EXPIRING_SOON,
    ACTION_MISSING_DOCUMENT,
    ACTION_OVERDUE_COMPLIANCE,
)
from services.unified_tasks_service import _action_to_task, _compliance_execution_booking_meta


def test_compliance_booking_meta_gas_safety_eligible():
    a = {
        "action_type": ACTION_OVERDUE_COMPLIANCE,
        "title": "Overdue",
        "related_property_id": "p1",
        "related_requirement_id": "req-1",
        "requirement_code": "gas_safety",
        "priority": 10,
        "severity": "high",
    }
    meta = _compliance_execution_booking_meta(ACTION_OVERDUE_COMPLIANCE, a)
    assert meta is not None
    assert meta["eligible"] is True
    assert meta["property_id"] == "p1"
    assert meta["linked_property_requirement_id"] == "req-1"
    assert meta["requirement_code"] == "gas_safety"
    assert meta["compliance_purpose"] == "inspection"
    assert meta["compliance_generated_from"] == "requirement"


def test_compliance_booking_meta_unknown_code_not_eligible():
    a = {
        "action_type": ACTION_MISSING_DOCUMENT,
        "related_property_id": "p1",
        "related_requirement_id": "req-1",
        "requirement_code": "deposit_pi",
    }
    meta = _compliance_execution_booking_meta(ACTION_MISSING_DOCUMENT, a)
    assert meta is not None
    assert meta["eligible"] is False


def test_action_to_task_includes_booking_in_metadata():
    a = {
        "action_type": ACTION_CERT_EXPIRING_SOON,
        "title": "Due soon",
        "description": "x",
        "priority": 5,
        "severity": "medium",
        "related_property_id": "p9",
        "related_requirement_id": "req-z",
        "requirement_code": "eicr",
    }
    now = datetime.now(timezone.utc)
    t = _action_to_task(a, {"p9": "9 Test St"}, now)
    assert "compliance_execution_booking" in t["metadata"]
    assert t["metadata"]["compliance_execution_booking"]["eligible"] is True
    assert t["metadata"]["compliance_execution_booking"]["compliance_purpose"] == "renewal"


def test_pending_approval_has_billing_domain():
    from services.priority_actions import ACTION_PENDING_APPROVAL

    a = {
        "action_type": ACTION_PENDING_APPROVAL,
        "title": "Pending",
        "description": "inv",
        "priority": 5,
        "severity": "medium",
        "related_invoice_id": "inv-1",
        "related_property_id": "p1",
    }
    now = datetime.now(timezone.utc)
    t = _action_to_task(a, {"p1": "1 Main"}, now)
    assert t["metadata"].get("domain") == "billing"
    assert t["metadata"].get("billing_milestone_type") == "pending_invoice_approval"
    assert "billing" in t["filter_tags"]
