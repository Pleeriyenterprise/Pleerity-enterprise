"""
Typed payload shapes for unified customer emails.

Renderers should accept plain dicts at runtime (Mongo/orchestrator context); these types
document the expected fields for scheduled digest and future strict validation.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict


class ComplianceBreakdown(TypedDict, total=False):
    green: int
    amber: int
    red: int


class RequirementsBreakdown(TypedDict, total=False):
    compliant: int
    overdue: int
    expiring_soon: int
    pending: int


class ReportSummaryPayload(TypedDict, total=False):
    total_properties: int
    compliance_rate: int
    compliance_breakdown: ComplianceBreakdown
    requirements_breakdown: RequirementsBreakdown


class PropertySnapshotRow(TypedDict, total=False):
    address: str
    compliance_status: str
    overdue: Optional[int]


class ScheduledReportEmailPayload(TypedDict, total=False):
    """Context for SCHEDULED_REPORT / unified scheduled digest."""

    client_name: str
    customer_reference: str
    frequency: str
    report_type: str
    generated_date: str
    portal_link: str
    report_summary: ReportSummaryPayload
    properties_snapshot: List[PropertySnapshotRow]
    report_rows: List[Dict[str, Any]]
    email_render_engine: str
    _email_branding: Dict[str, Any]


class AlertEmailPayload(TypedDict, total=False):
    recipient_name: str
    property_name: str
    previous_status: str
    current_status: str
    reason_summary: str
    primary_cta_url: str


class ReminderEmailPayload(TypedDict, total=False):
    recipient_name: str
    property_name: str
    requirement_name: str
    due_date: str
    urgency_label: str
    days_remaining: int
    primary_cta_url: str


class EngagementEmailPayload(TypedDict, total=False):
    recipient_name: str
    behavioural_context: str
    benefit_statement: str
    primary_cta_url: str
