"""
Zoho field mapping registry — Pleerity fields to Zoho API fields.

Pleerity lead_id is always the external key in Zoho CRM (custom field Pleerity_Lead_ID).
"""
from __future__ import annotations

from typing import Any, Dict, List

# CRM: outbound only — fields Pleerity may push to Zoho Leads module
CRM_LEAD_OUTBOUND_FIELDS: List[str] = [
    "lead_id",
    "email",
    "first_name",
    "last_name",
    "phone",
    "stage",
    "lead_score",
    "status",
    "source_platform",
    "service_interest",
    "created_at",
    "updated_at",
    "client_id",
]

CRM_FIELD_MAP: Dict[str, str] = {
    "lead_id": "Pleerity_Lead_ID",
    "email": "Email",
    "first_name": "First_Name",
    "last_name": "Last_Name",
    "phone": "Phone",
    "stage": "Lead_Status",
    "lead_score": "Lead_Score",
    "status": "Pleerity_Status",
    "source_platform": "Lead_Source",
    "service_interest": "Pleerity_Service_Interest",
    "created_at": "Pleerity_Created_At",
    "updated_at": "Pleerity_Updated_At",
    "client_id": "Pleerity_Client_ID",
}

# Fields Zoho must NEVER write back to Pleerity (authority fields)
CRM_AUTHORITY_FIELDS_BLOCKED_FROM_INBOUND: frozenset = frozenset(
    {
        "lead_id",
        "email",
        "stage",
        "status",
        "client_id",
        "lead_score",
        "converted_at",
    }
)

# Analytics export — aggregated metrics only (no row-level PII)
ANALYTICS_EXPORT_METRICS: List[str] = [
    "period_start",
    "period_end",
    "leads_created_count",
    "leads_converted_count",
    "total_leads_count",
    "conversion_rate_pct",
    "active_subscriptions_count",
    "mrr_summary_gbp",
    "churn_count",
    "new_subscriptions_count",
    "support_tickets_open_count",
    "support_tickets_closed_count",
    "export_type",
    "payload_version",
]

# Campaigns — minimal audience fields
CAMPAIGNS_AUDIENCE_FIELDS: List[str] = ["email", "marketing_consent", "subscribed_at", "source"]

# Books — finance export line items (Stripe summary, not customer SoR)
BOOKS_EXPORT_LINE_TYPES: List[str] = [
    "stripe_payout",
    "stripe_fee",
    "subscription_revenue_summary",
    "refund_summary",
]

# Sign — allowed document categories for webhook processing
SIGN_ALLOWED_CATEGORIES: frozenset = frozenset(
    {"vendor", "partnership", "employment", "nda", "b2b_agreement", "internal"}
)

SIGN_FORBIDDEN_CATEGORIES: frozenset = frozenset(
    {"subscription_clickwrap", "compliance_evidence", "customer_agreement", "requirement_evidence"}
)

# WorkDrive — internal folder categories only
WORKDRIVE_ALLOWED_CATEGORIES: frozenset = frozenset(
    {"internal", "vendor", "hr", "governance", "b2b_signed", "finance"}
)

WORKDRIVE_FORBIDDEN_CATEGORIES: frozenset = frozenset(
    {"compliance_evidence", "customer_vault", "requirement_evidence", "property_evidence"}
)


def map_lead_to_zoho_crm(lead: Dict[str, Any]) -> Dict[str, Any]:
    """Map Pleerity lead document to Zoho CRM API payload (PII-minimised)."""
    payload: Dict[str, Any] = {}
    for pleerity_key, zoho_key in CRM_FIELD_MAP.items():
        val = lead.get(pleerity_key)
        if val is not None and val != "":
            payload[zoho_key] = val
    if lead.get("lead_id"):
        payload["Pleerity_Lead_ID"] = lead["lead_id"]
    return payload


def validate_inbound_crm_fields(fields: Dict[str, Any]) -> List[str]:
    """Return list of blocked authority fields present in inbound payload."""
    blocked = []
    for key in fields:
        norm = key.lower().replace(" ", "_")
        if norm in CRM_AUTHORITY_FIELDS_BLOCKED_FROM_INBOUND or key in CRM_AUTHORITY_FIELDS_BLOCKED_FROM_INBOUND:
            blocked.append(key)
        if key in CRM_FIELD_MAP.values():
            blocked.append(key)
    return blocked
