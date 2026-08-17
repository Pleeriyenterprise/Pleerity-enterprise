"""
Account Lifecycle Runtime Contract (ILP-2).

Pure read-only assembly of the governed AccountLifecycleRuntimeContract from:
ILP-1 lifecycle resolver, ALPA, APMA, ACA, and runtime schema.

Does not mutate data, enforce access, or wire into middleware/jobs/frontend.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import Any, Dict, FrozenSet, List, Mapping, Optional, Tuple

from services.account_lifecycle_state_resolver import (
    POLICY_VERSION as LIFECYCLE_POLICY_VERSION,
    RESOLVER_VERSION,
    LifecycleStateResolution,
    resolve_account_lifecycle_state,
)
from services.plan_registry import plan_registry
from services.billing_period_utils import normalize_stored_period_end_for_api
from services.billing_scheduled_cancellation_authority import (
    is_stale_scheduled_cancellation_mirror,
    reconcile_stale_scheduled_cancellation_if_needed,
)

logger = logging.getLogger(__name__)

CONTRACT_VERSION = "1.0.0"
RUNTIME_BUILD_ID = "ilp2_lifecycle_runtime_contract_v1"
CAPABILITY_AUTHORITY_VERSION = "account_capability_v1"
PORTAL_MODE_AUTHORITY_VERSION = "account_lifecycle_policy_v1"

CACHE_TTL_SECONDS = 30
_runtime_cache: Dict[str, Tuple[float, int, Mapping[str, Any]]] = {}

GRANT_ALLOW = "ALLOW"
GRANT_READ = "READ"
GRANT_DENY = "DENY"
GRANT_HIDDEN = "HIDDEN"
GRANT_PLAN_GATED = "PLAN_GATED"
GRANT_LIMITED = "LIMITED"

_GRANT_PERMISSIVENESS = {
    GRANT_HIDDEN: 0,
    GRANT_DENY: 1,
    GRANT_LIMITED: 2,
    GRANT_PLAN_GATED: 3,
    GRANT_READ: 4,
    GRANT_ALLOW: 5,
}

_LIFECYCLE_COLUMNS = (
    "ACTIVE",
    "TRIAL",
    "TRIAL_EXPIRED",
    "PAYMENT_PENDING",
    "PAYMENT_FAILED",
    "GRACE_PERIOD",
    "CANCELLATION_SCHEDULED",
    "CANCELLED_IMMEDIATE",
    "SUBSCRIPTION_EXPIRED",
    "READ_ONLY",
    "SUSPENDED",
    "ARCHIVED",
    "ACCOUNT_DELETED",
    "UNKNOWN",
    "LEGACY",
)

# Governed base grants (ACCOUNT_CAPABILITY_MATRIX.md — core customer capabilities).
_BASE_CAPABILITY_MATRIX: Dict[str, Tuple[str, ...]] = {
    "CAP_AUTH_LOGIN": ("A", "A", "A", "A", "A", "A", "A", "A", "A", "A", "A", "D", "D", "A", "A"),
    "CAP_PROFILE_VIEW": ("A", "A", "R", "L", "A", "A", "A", "R", "R", "R", "D", "D", "D", "A", "R"),
    "CAP_PROFILE_EDIT": ("A", "A", "D", "L", "A", "L", "A", "D", "D", "D", "D", "D", "D", "D", "D"),
    "CAP_PROFILE_JURISDICTION": ("A", "A", "D", "L", "A", "L", "A", "D", "D", "D", "D", "D", "D", "D", "D"),
    "CAP_CALENDAR_VIEW": ("P", "P", "D", "D", "P", "L", "P", "D", "D", "D", "D", "D", "D", "D", "D"),
    "CAP_PROP_VIEW": ("A", "A", "R", "L", "A", "A", "A", "R", "R", "R", "D", "D", "D", "D", "R"),
    "CAP_PROP_CREATE": ("A", "A", "D", "L", "A", "L", "A", "D", "D", "D", "D", "D", "D", "D", "D"),
    "CAP_PROP_EDIT": ("A", "A", "D", "L", "A", "L", "A", "D", "D", "D", "D", "D", "D", "D", "D"),
    "CAP_PROP_ARCHIVE": ("A", "A", "D", "L", "A", "L", "A", "D", "D", "D", "D", "D", "D", "D", "D"),
    "CAP_PROP_DELETE": ("A", "A", "D", "L", "A", "L", "A", "D", "D", "D", "D", "D", "D", "D", "D"),
    "CAP_PROP_IMPORT": ("P", "P", "D", "L", "P", "L", "P", "D", "D", "D", "D", "D", "D", "D", "D"),
    "CAP_REQ_VIEW": ("A", "A", "R", "L", "A", "A", "A", "R", "R", "R", "D", "D", "D", "D", "R"),
    "CAP_REQ_RESOLVE": ("A", "A", "D", "L", "A", "L", "A", "D", "D", "D", "D", "D", "D", "D", "D"),
    "CAP_REQ_MARK_N_A": ("A", "A", "D", "L", "A", "L", "A", "D", "D", "D", "D", "D", "D", "D", "D"),
    "CAP_REQ_COMPLETE": ("A", "A", "D", "L", "A", "L", "A", "D", "D", "D", "D", "D", "D", "D", "D"),
    "CAP_DOC_VIEW": ("A", "A", "R", "L", "A", "A", "A", "R", "R", "R", "D", "D", "D", "D", "R"),
    "CAP_DOC_UPLOAD": ("P", "P", "D", "L", "P", "L", "P", "D", "D", "D", "D", "D", "D", "D", "D"),
    "CAP_EVIDENCE_VIEW": ("A", "A", "R", "L", "A", "A", "A", "R", "R", "R", "D", "D", "D", "D", "R"),
    "CAP_EVIDENCE_DOWNLOAD": ("A", "A", "R", "D", "A", "A", "A", "R", "R", "R", "D", "D", "D", "D", "R"),
    "CAP_REPORT_VIEW": ("A", "A", "R", "D", "A", "A", "A", "R", "R", "R", "D", "D", "D", "D", "R"),
    "CAP_REPORT_GENERATE_PDF": ("P", "P", "D", "D", "P", "L", "P", "D", "D", "D", "D", "D", "D", "D", "D"),
    "CAP_REPORT_DOWNLOAD": ("A", "A", "R", "D", "A", "A", "A", "R", "R", "R", "D", "D", "D", "D", "R"),
    "CAP_REPORT_SCHEDULE": ("P", "P", "D", "D", "P", "P", "P", "D", "D", "D", "D", "D", "D", "D", "D"),
    "CAP_REPORT_GENERATE_CSV": ("P", "P", "D", "D", "P", "L", "P", "D", "D", "D", "D", "D", "D", "D", "D"),
    "CAP_AUDIT_LOG_EXPORT": ("P", "P", "D", "D", "P", "L", "P", "D", "D", "D", "D", "D", "D", "D", "D"),
    "CAP_REPORT_AUDIT_PACK": ("P", "P", "D", "D", "P", "L", "P", "D", "D", "D", "D", "D", "D", "D", "D"),
    "CAP_DOC_BULK_ZIP": ("P", "P", "D", "L", "P", "L", "P", "D", "D", "D", "D", "D", "D", "D", "D"),
    "CAP_AI_EXTRACTION_ADVANCED": ("P", "P", "D", "D", "P", "L", "P", "D", "D", "D", "D", "D", "D", "D", "D"),
    "CAP_DASHBOARD_VIEW": ("A", "A", "D", "D", "A", "A", "A", "D", "D", "R", "D", "D", "D", "D", "R"),
    "CAP_TODAY_VIEW": ("A", "A", "D", "D", "A", "A", "A", "D", "D", "D", "D", "D", "D", "D", "D"),
    "CAP_TODAY_ACT": ("A", "A", "D", "D", "A", "L", "A", "D", "D", "D", "D", "D", "D", "D", "D"),
    "CAP_CMD_CTR_VIEW": ("A", "A", "D", "D", "A", "A", "A", "D", "D", "R", "D", "D", "D", "D", "R"),
    "CAP_LEDGER_VIEW": ("A", "A", "R", "D", "A", "A", "A", "R", "R", "R", "D", "D", "D", "D", "R"),
    "CAP_LEDGER_EXPORT": ("P", "P", "D", "D", "P", "L", "P", "D", "D", "D", "D", "D", "D", "D", "D"),
    "CAP_SCORE_VIEW": ("A", "A", "R", "D", "A", "A", "A", "R", "R", "R", "D", "D", "D", "D", "R"),
    "CAP_SCORE_EXPLAIN": ("P", "P", "R", "D", "P", "A", "A", "R", "R", "R", "D", "D", "D", "D", "R"),
    "CAP_SCORE_TREND": ("P", "P", "D", "D", "P", "A", "A", "R", "R", "R", "D", "D", "D", "D", "R"),
    "CAP_SCORE_SNAPSHOT": ("A", "A", "D", "D", "A", "L", "A", "D", "D", "D", "D", "D", "D", "D", "D"),
    "CAP_COMPLIANCE_ACTIVITY": ("P", "P", "D", "D", "P", "A", "A", "R", "R", "R", "D", "D", "D", "D", "R"),
    "CAP_BILLING_VIEW": ("A", "A", "A", "A", "A", "A", "A", "A", "A", "A", "A", "D", "D", "A", "A"),
    "CAP_BILLING_CHECKOUT": ("A", "A", "A", "A", "A", "A", "A", "A", "A", "A", "A", "D", "D", "A", "A"),
    "CAP_BILLING_INVOICES": ("A", "A", "A", "A", "A", "A", "A", "A", "A", "A", "A", "D", "D", "A", "A"),
    "CAP_BILLING_PAYMENT_METHODS": ("A", "A", "A", "A", "A", "A", "A", "A", "A", "A", "A", "D", "D", "A", "A"),
    "CAP_SUB_VIEW": ("A", "A", "A", "A", "A", "A", "A", "A", "A", "A", "A", "D", "D", "A", "A"),
    "CAP_SUB_MANAGE": ("A", "A", "A", "A", "A", "A", "A", "A", "A", "A", "A", "D", "D", "A", "A"),
    "CAP_SUB_CANCEL": ("A", "A", "A", "A", "A", "A", "A", "A", "A", "A", "A", "D", "D", "A", "A"),
    "CAP_SUB_RENEW": ("N", "N", "A", "A", "N", "N", "A", "A", "A", "A", "A", "D", "D", "A", "A"),
    "CAP_DATA_EXPORT": ("A", "A", "R", "D", "A", "A", "A", "R", "R", "R", "D", "D", "D", "D", "R"),
    "CAP_SUPPORT_ACCESS": ("A", "A", "A", "A", "A", "A", "A", "A", "A", "A", "A", "A", "D", "A", "A"),
    "CAP_SUPPORT_REQUEST": ("A", "A", "A", "A", "A", "A", "A", "A", "A", "A", "A", "A", "D", "A", "A"),
    "CAP_KNOWLEDGE_CENTRE": ("A", "A", "A", "A", "A", "A", "A", "A", "A", "A", "A", "A", "D", "A", "A"),
    "CAP_NOTIF_EMAIL": ("A", "A", "D", "D", "A", "A", "A", "D", "D", "D", "D", "D", "D", "D", "D"),
    "CAP_NOTIF_SMS": ("P", "P", "D", "D", "P", "P", "P", "D", "D", "D", "D", "D", "D", "D", "D"),
    "CAP_AI_ASSISTANT": ("P", "P", "D", "D", "P", "L", "P", "D", "D", "D", "D", "D", "D", "D", "D"),
    "CAP_OPS_MAINTENANCE": ("P", "P", "D", "D", "P", "L", "P", "D", "D", "D", "D", "D", "D", "D", "D"),
    "CAP_OPS_ISSUES_VIEW": ("P", "P", "D", "D", "P", "L", "P", "D", "D", "D", "D", "D", "D", "D", "D"),
    "CAP_OPS_CONTRACTORS": ("P", "P", "D", "D", "P", "L", "P", "D", "D", "D", "D", "D", "D", "D", "D"),
    "CAP_OPS_PREDICTIVE": ("P", "P", "D", "D", "P", "L", "P", "D", "D", "D", "D", "D", "D", "D", "D"),
    "CAP_RISK_VIEW": ("P", "P", "D", "D", "P", "L", "P", "D", "D", "D", "D", "D", "D", "D", "D"),
    "CAP_OPS_RENT": ("P", "P", "D", "D", "P", "L", "P", "D", "D", "D", "D", "D", "D", "D", "D"),
    "CAP_OPS_APPROVALS": ("P", "P", "D", "D", "P", "L", "P", "D", "D", "D", "D", "D", "D", "D", "D"),
    "CAP_OPS_COMPLIANCE_REVIEW": ("P", "P", "D", "D", "P", "L", "P", "D", "D", "D", "D", "D", "D", "D", "D"),
    "CAP_TENANT_PORTAL": ("P", "P", "D", "D", "P", "L", "P", "D", "D", "D", "D", "D", "D", "D", "D"),
    "CAP_TENANT_MANAGE": ("P", "P", "D", "D", "P", "L", "P", "D", "D", "D", "D", "D", "D", "D", "D"),
    "CAP_TENANT_MESSAGES": ("P", "P", "D", "D", "P", "L", "P", "D", "D", "D", "D", "D", "D", "D", "D"),
    "CAP_BRANDING_VIEW": ("A", "A", "R", "L", "A", "A", "A", "R", "R", "R", "D", "D", "D", "D", "R"),
    "CAP_BRANDING_EDIT": ("P", "P", "D", "D", "P", "L", "P", "D", "D", "D", "D", "D", "D", "D", "D"),
    "CAP_BRANDING_WHITE_LABEL": ("P", "P", "D", "D", "P", "L", "P", "D", "D", "D", "D", "D", "D", "D", "D"),
    "CAP_INTEGRATION_WEBHOOKS": ("P", "P", "D", "D", "P", "L", "P", "D", "D", "D", "D", "D", "D", "D", "D"),
    "CAP_INTEGRATION_READ_API": ("P", "P", "D", "D", "P", "L", "P", "D", "D", "D", "D", "D", "D", "D", "D"),
    "CAP_EXPORT_API": ("P", "P", "D", "D", "P", "L", "P", "D", "D", "D", "D", "D", "D", "D", "D"),
}

_CAP_PLAN_KEYS: Dict[str, str] = {
    "CAP_DOC_UPLOAD": "document_upload_single",
    "CAP_DOC_BULK_ZIP": "zip_upload",
    "CAP_PROP_IMPORT": "document_upload_bulk_zip",
    "CAP_REPORT_GENERATE_PDF": "reports_pdf",
    "CAP_REPORT_GENERATE_CSV": "reports_csv",
    "CAP_REPORT_SCHEDULE": "scheduled_reports",
    "CAP_AUDIT_LOG_EXPORT": "audit_log_export",
    "CAP_REPORT_AUDIT_PACK": "audit_log_export",
    "CAP_NOTIF_SMS": "sms_reminders",
    "CAP_AI_ASSISTANT": "ai_assistant",
    "CAP_CALENDAR_VIEW": "compliance_calendar",
    "CAP_AI_EXTRACTION_ADVANCED": "ai_extraction_advanced",
    "CAP_OPS_MAINTENANCE": "maintenance_workflows",
    "CAP_OPS_ISSUES_VIEW": "maintenance_workflows",
    "CAP_OPS_CONTRACTORS": "contractor_network",
    "CAP_OPS_PREDICTIVE": "predictive_maintenance",
    "CAP_RISK_VIEW": "predictive_maintenance",
    "CAP_OPS_RENT": "rent_operations",
    "CAP_OPS_APPROVALS": "compliance_engine",
    "CAP_OPS_COMPLIANCE_REVIEW": "compliance_engine",
    "CAP_TENANT_PORTAL": "tenant_portal",
    "CAP_TENANT_MANAGE": "tenant_portal",
    "CAP_TENANT_MESSAGES": "tenant_portal",
    "CAP_BRANDING_EDIT": "white_label_reports",
    "CAP_BRANDING_WHITE_LABEL": "white_label_reports",
    "CAP_SCORE_EXPLAIN": "compliance_score",
    "CAP_SCORE_TREND": "score_trending",
    "CAP_SCORE_SNAPSHOT": "compliance_score",
    "CAP_COMPLIANCE_ACTIVITY": "compliance_dashboard",
    "CAP_DASHBOARD_VIEW": "compliance_dashboard",
    "CAP_CMD_CTR_VIEW": "compliance_dashboard",
    "CAP_LEDGER_EXPORT": "reports_csv",
    "CAP_INTEGRATION_WEBHOOKS": "webhooks",
    "CAP_INTEGRATION_READ_API": "webhooks",
    "CAP_EXPORT_API": "webhooks",
}

_LIFECYCLE_TO_PORTAL_MODE: Dict[str, str] = {
    "ACTIVE": "FULL_ACCESS",
    "TRIAL": "FULL_ACCESS",
    "TRIAL_EXPIRED": "PAYMENT_REQUIRED",
    "PAYMENT_PENDING": "PAYMENT_REQUIRED",
    "PAYMENT_FAILED": "FULL_ACCESS",
    "GRACE_PERIOD": "GRACE",
    "CANCELLATION_SCHEDULED": "FULL_ACCESS",
    "CANCELLED_IMMEDIATE": "BILLING_RECOVERY",
    "SUBSCRIPTION_EXPIRED": "BILLING_RECOVERY",
    "READ_ONLY": "READ_ONLY",
    "SUSPENDED": "SUSPENDED",
    "ARCHIVED": "ARCHIVED",
    "ACCOUNT_DELETED": "ACCOUNT_DELETED",
    "UNKNOWN": "BILLING_RECOVERY",
    "LEGACY": "READ_ONLY",
}

# Portal mode may only restrict grants (APMA + portal capability matrix).
_PORTAL_CAP_CEILINGS: Dict[str, Dict[str, str]] = {
    "BILLING_RECOVERY": {
        "CAP_PROP_CREATE": GRANT_DENY,
        "CAP_PROP_EDIT": GRANT_DENY,
        "CAP_PROP_ARCHIVE": GRANT_DENY,
        "CAP_PROP_DELETE": GRANT_DENY,
        "CAP_PROP_IMPORT": GRANT_DENY,
        "CAP_REQ_RESOLVE": GRANT_DENY,
        "CAP_REQ_MARK_N_A": GRANT_DENY,
        "CAP_REQ_COMPLETE": GRANT_DENY,
        "CAP_DOC_UPLOAD": GRANT_DENY,
        "CAP_DOC_BULK_ZIP": GRANT_DENY,
        "CAP_TODAY_VIEW": GRANT_DENY,
        "CAP_TODAY_ACT": GRANT_DENY,
        "CAP_DASHBOARD_VIEW": GRANT_DENY,
        "CAP_CMD_CTR_VIEW": GRANT_DENY,
        "CAP_REPORT_GENERATE_PDF": GRANT_DENY,
        "CAP_REPORT_GENERATE_CSV": GRANT_DENY,
        "CAP_AUDIT_LOG_EXPORT": GRANT_DENY,
        "CAP_REPORT_AUDIT_PACK": GRANT_DENY,
        "CAP_AI_EXTRACTION_ADVANCED": GRANT_DENY,
        "CAP_AI_ASSISTANT": GRANT_DENY,
        "CAP_PROP_VIEW": GRANT_READ,
        "CAP_REQ_VIEW": GRANT_READ,
        "CAP_DOC_VIEW": GRANT_READ,
        "CAP_REPORT_VIEW": GRANT_READ,
        "CAP_EVIDENCE_VIEW": GRANT_READ,
        "CAP_EVIDENCE_DOWNLOAD": GRANT_READ,
        "CAP_DATA_EXPORT": GRANT_READ,
        "CAP_SCORE_VIEW": GRANT_READ,
        "CAP_SCORE_EXPLAIN": GRANT_READ,
        "CAP_SCORE_TREND": GRANT_READ,
        "CAP_COMPLIANCE_ACTIVITY": GRANT_READ,
        "CAP_LEDGER_VIEW": GRANT_READ,
        "CAP_LEDGER_EXPORT": GRANT_DENY,
        "CAP_BRANDING_VIEW": GRANT_READ,
        "CAP_BRANDING_EDIT": GRANT_DENY,
        "CAP_TENANT_MANAGE": GRANT_DENY,
        "CAP_TENANT_MESSAGES": GRANT_DENY,
        "CAP_TENANT_PORTAL": GRANT_DENY,
        "CAP_OPS_MAINTENANCE": GRANT_DENY,
        "CAP_OPS_CONTRACTORS": GRANT_DENY,
        "CAP_OPS_PREDICTIVE": GRANT_DENY,
        "CAP_OPS_RENT": GRANT_DENY,
        "CAP_OPS_APPROVALS": GRANT_DENY,
        "CAP_OPS_COMPLIANCE_REVIEW": GRANT_DENY,
        "CAP_PROFILE_EDIT": GRANT_DENY,
        "CAP_PROFILE_JURISDICTION": GRANT_DENY,
        "CAP_CALENDAR_VIEW": GRANT_DENY,
        "CAP_INTEGRATION_WEBHOOKS": GRANT_DENY,
        "CAP_INTEGRATION_READ_API": GRANT_DENY,
        "CAP_EXPORT_API": GRANT_DENY,
    },
    "PAYMENT_REQUIRED": {
        "CAP_PROP_VIEW": GRANT_DENY,
        "CAP_REQ_VIEW": GRANT_DENY,
        "CAP_DOC_VIEW": GRANT_DENY,
        "CAP_REPORT_VIEW": GRANT_DENY,
        "CAP_TODAY_VIEW": GRANT_DENY,
        "CAP_DASHBOARD_VIEW": GRANT_DENY,
        "CAP_CMD_CTR_VIEW": GRANT_DENY,
        "CAP_PROP_CREATE": GRANT_DENY,
        "CAP_PROP_EDIT": GRANT_DENY,
        "CAP_PROP_ARCHIVE": GRANT_DENY,
        "CAP_PROP_DELETE": GRANT_DENY,
        "CAP_PROP_IMPORT": GRANT_DENY,
        "CAP_REQ_RESOLVE": GRANT_DENY,
        "CAP_REQ_MARK_N_A": GRANT_DENY,
        "CAP_REQ_COMPLETE": GRANT_DENY,
        "CAP_DOC_UPLOAD": GRANT_DENY,
    },
    "READ_ONLY": {
        "CAP_PROP_CREATE": GRANT_DENY,
        "CAP_PROP_EDIT": GRANT_DENY,
        "CAP_PROP_ARCHIVE": GRANT_DENY,
        "CAP_PROP_DELETE": GRANT_DENY,
        "CAP_PROP_IMPORT": GRANT_DENY,
        "CAP_REQ_RESOLVE": GRANT_DENY,
        "CAP_REQ_MARK_N_A": GRANT_DENY,
        "CAP_REQ_COMPLETE": GRANT_DENY,
        "CAP_DOC_UPLOAD": GRANT_DENY,
        "CAP_REPORT_GENERATE_PDF": GRANT_DENY,
        "CAP_REPORT_GENERATE_CSV": GRANT_DENY,
        "CAP_AUDIT_LOG_EXPORT": GRANT_DENY,
        "CAP_REPORT_AUDIT_PACK": GRANT_DENY,
        "CAP_DOC_BULK_ZIP": GRANT_DENY,
        "CAP_AI_EXTRACTION_ADVANCED": GRANT_DENY,
        "CAP_TODAY_ACT": GRANT_DENY,
        "CAP_PROFILE_EDIT": GRANT_DENY,
        "CAP_PROP_VIEW": GRANT_READ,
        "CAP_REQ_VIEW": GRANT_READ,
        "CAP_DOC_VIEW": GRANT_READ,
        "CAP_REPORT_VIEW": GRANT_READ,
        "CAP_EVIDENCE_VIEW": GRANT_READ,
        "CAP_EVIDENCE_DOWNLOAD": GRANT_READ,
        "CAP_DATA_EXPORT": GRANT_READ,
        "CAP_SCORE_VIEW": GRANT_READ,
        "CAP_SCORE_EXPLAIN": GRANT_READ,
        "CAP_SCORE_TREND": GRANT_READ,
        "CAP_COMPLIANCE_ACTIVITY": GRANT_READ,
        "CAP_LEDGER_VIEW": GRANT_READ,
        "CAP_LEDGER_EXPORT": GRANT_DENY,
        "CAP_BRANDING_VIEW": GRANT_READ,
        "CAP_BRANDING_EDIT": GRANT_DENY,
        "CAP_TENANT_MANAGE": GRANT_DENY,
        "CAP_TENANT_MESSAGES": GRANT_DENY,
        "CAP_TENANT_PORTAL": GRANT_DENY,
        "CAP_OPS_MAINTENANCE": GRANT_DENY,
        "CAP_OPS_CONTRACTORS": GRANT_DENY,
        "CAP_OPS_PREDICTIVE": GRANT_DENY,
        "CAP_OPS_RENT": GRANT_DENY,
        "CAP_OPS_APPROVALS": GRANT_DENY,
        "CAP_OPS_COMPLIANCE_REVIEW": GRANT_DENY,
        "CAP_INTEGRATION_WEBHOOKS": GRANT_DENY,
        "CAP_INTEGRATION_READ_API": GRANT_DENY,
        "CAP_EXPORT_API": GRANT_DENY,
        "CAP_DASHBOARD_VIEW": GRANT_READ,
        "CAP_CMD_CTR_VIEW": GRANT_READ,
    },
    "SUSPENDED": {
        "CAP_PROP_VIEW": GRANT_DENY,
        "CAP_REQ_VIEW": GRANT_DENY,
        "CAP_DOC_VIEW": GRANT_DENY,
        "CAP_REPORT_VIEW": GRANT_DENY,
        "CAP_EVIDENCE_VIEW": GRANT_DENY,
        "CAP_EVIDENCE_DOWNLOAD": GRANT_DENY,
        "CAP_REPORT_DOWNLOAD": GRANT_DENY,
        "CAP_TODAY_VIEW": GRANT_DENY,
        "CAP_DASHBOARD_VIEW": GRANT_DENY,
        "CAP_CMD_CTR_VIEW": GRANT_DENY,
        "CAP_PROP_CREATE": GRANT_DENY,
        "CAP_PROP_EDIT": GRANT_DENY,
        "CAP_PROP_ARCHIVE": GRANT_DENY,
        "CAP_PROP_DELETE": GRANT_DENY,
        "CAP_PROP_IMPORT": GRANT_DENY,
        "CAP_REQ_RESOLVE": GRANT_DENY,
        "CAP_REQ_MARK_N_A": GRANT_DENY,
        "CAP_REQ_COMPLETE": GRANT_DENY,
        "CAP_DOC_UPLOAD": GRANT_DENY,
        "CAP_DOC_BULK_ZIP": GRANT_DENY,
        "CAP_PROFILE_EDIT": GRANT_DENY,
        "CAP_PROFILE_JURISDICTION": GRANT_DENY,
        "CAP_CALENDAR_VIEW": GRANT_DENY,
        "CAP_REPORT_GENERATE_PDF": GRANT_DENY,
        "CAP_REPORT_GENERATE_CSV": GRANT_DENY,
        "CAP_REPORT_SCHEDULE": GRANT_DENY,
        "CAP_AUDIT_LOG_EXPORT": GRANT_DENY,
        "CAP_REPORT_AUDIT_PACK": GRANT_DENY,
        "CAP_AI_EXTRACTION_ADVANCED": GRANT_DENY,
        "CAP_AI_ASSISTANT": GRANT_DENY,
        "CAP_INTEGRATION_WEBHOOKS": GRANT_DENY,
        "CAP_INTEGRATION_READ_API": GRANT_DENY,
        "CAP_EXPORT_API": GRANT_DENY,
        "CAP_SCORE_VIEW": GRANT_DENY,
        "CAP_SCORE_EXPLAIN": GRANT_DENY,
        "CAP_SCORE_TREND": GRANT_DENY,
        "CAP_SCORE_SNAPSHOT": GRANT_DENY,
        "CAP_COMPLIANCE_ACTIVITY": GRANT_DENY,
        "CAP_LEDGER_VIEW": GRANT_DENY,
        "CAP_LEDGER_EXPORT": GRANT_DENY,
        "CAP_BRANDING_VIEW": GRANT_DENY,
        "CAP_BRANDING_EDIT": GRANT_DENY,
        "CAP_BRANDING_WHITE_LABEL": GRANT_DENY,
        "CAP_TENANT_MANAGE": GRANT_DENY,
        "CAP_TENANT_MESSAGES": GRANT_DENY,
        "CAP_TENANT_PORTAL": GRANT_DENY,
        "CAP_OPS_MAINTENANCE": GRANT_DENY,
        "CAP_OPS_CONTRACTORS": GRANT_DENY,
        "CAP_OPS_PREDICTIVE": GRANT_DENY,
        "CAP_OPS_RENT": GRANT_DENY,
        "CAP_OPS_APPROVALS": GRANT_DENY,
        "CAP_OPS_COMPLIANCE_REVIEW": GRANT_DENY,
        "CAP_PROFILE_JURISDICTION": GRANT_DENY,
        "CAP_CALENDAR_VIEW": GRANT_DENY,
    },
    "ARCHIVED": {
        "CAP_PROP_VIEW": GRANT_DENY,
        "CAP_REQ_VIEW": GRANT_DENY,
        "CAP_DOC_VIEW": GRANT_DENY,
        "CAP_REPORT_VIEW": GRANT_DENY,
        "CAP_BILLING_VIEW": GRANT_DENY,
        "CAP_BILLING_CHECKOUT": GRANT_DENY,
        "CAP_BILLING_INVOICES": GRANT_DENY,
        "CAP_BILLING_PAYMENT_METHODS": GRANT_DENY,
        "CAP_SUB_MANAGE": GRANT_DENY,
        "CAP_SUB_CANCEL": GRANT_DENY,
        "CAP_PROFILE_EDIT": GRANT_DENY,
    },
    "ACCOUNT_DELETED": {
        "CAP_AUTH_LOGIN": GRANT_DENY,
        "CAP_PROP_VIEW": GRANT_DENY,
        "CAP_REQ_VIEW": GRANT_DENY,
        "CAP_BILLING_VIEW": GRANT_DENY,
        "CAP_BILLING_CHECKOUT": GRANT_DENY,
        "CAP_BILLING_INVOICES": GRANT_DENY,
        "CAP_BILLING_PAYMENT_METHODS": GRANT_DENY,
        "CAP_SUB_MANAGE": GRANT_DENY,
        "CAP_SUB_CANCEL": GRANT_DENY,
        "CAP_PROFILE_VIEW": GRANT_DENY,
    },
    "GRACE": {},
    "FULL_ACCESS": {},
}


class PortalMode(str, Enum):
    FULL_ACCESS = "FULL_ACCESS"
    READ_ONLY = "READ_ONLY"
    BILLING_RECOVERY = "BILLING_RECOVERY"
    PAYMENT_REQUIRED = "PAYMENT_REQUIRED"
    GRACE = "GRACE"
    SUSPENDED = "SUSPENDED"
    ARCHIVED = "ARCHIVED"
    ACCOUNT_DELETED = "ACCOUNT_DELETED"


def _utc_now(now: Optional[datetime] = None) -> datetime:
    if now is None:
        return datetime.now(timezone.utc)
    if now.tzinfo is None:
        return now.replace(tzinfo=timezone.utc)
    return now


def _code_to_grant(code: str) -> str:
    return {
        "A": GRANT_ALLOW,
        "R": GRANT_READ,
        "D": GRANT_DENY,
        "H": GRANT_HIDDEN,
        "P": GRANT_PLAN_GATED,
        "L": GRANT_LIMITED,
        "N": GRANT_HIDDEN,
    }.get(code, GRANT_HIDDEN)


def _restrict_grant(current: str, ceiling: str) -> str:
    if _GRANT_PERMISSIVENESS[ceiling] < _GRANT_PERMISSIVENESS[current]:
        return ceiling
    return current


def _lifecycle_index(lifecycle_state: str) -> int:
    try:
        return _LIFECYCLE_COLUMNS.index(lifecycle_state)
    except ValueError:
        return _LIFECYCLE_COLUMNS.index("UNKNOWN")


def resolve_portal_mode(
    lifecycle_state: str,
    *,
    read_only_retention: bool = False,
) -> str:
    if lifecycle_state == "SUBSCRIPTION_EXPIRED" and read_only_retention:
        return PortalMode.READ_ONLY.value
    if lifecycle_state == "PAYMENT_FAILED":
        return PortalMode.FULL_ACCESS.value
    return _LIFECYCLE_TO_PORTAL_MODE.get(lifecycle_state, PortalMode.BILLING_RECOVERY.value)


def _base_capability_grants(lifecycle_state: str) -> Dict[str, str]:
    idx = _lifecycle_index(lifecycle_state)
    grants: Dict[str, str] = {}
    for cap_id, row in _BASE_CAPABILITY_MATRIX.items():
        grants[cap_id] = _code_to_grant(row[idx])
    return grants


def _apply_portal_overlay(portal_mode: str, grants: Dict[str, str]) -> Dict[str, str]:
    ceilings = _PORTAL_CAP_CEILINGS.get(portal_mode, {})
    if not ceilings:
        return dict(grants)
    out = dict(grants)
    for cap_id, ceiling in ceilings.items():
        if cap_id in out:
            out[cap_id] = _restrict_grant(out[cap_id], ceiling)
    return out


def _resolve_plan_gated(grants: Dict[str, str], plan_features: Dict[str, bool]) -> Dict[str, str]:
    resolved: Dict[str, str] = {}
    for cap_id, grant in grants.items():
        if grant != GRANT_PLAN_GATED:
            resolved[cap_id] = grant
            continue
        feature_key = _CAP_PLAN_KEYS.get(cap_id)
        if feature_key and plan_features.get(feature_key):
            resolved[cap_id] = GRANT_ALLOW
        else:
            resolved[cap_id] = GRANT_DENY
    return resolved


def resolve_capabilities(
    lifecycle_state: str,
    portal_mode: str,
    plan_features: Dict[str, bool],
) -> Dict[str, str]:
    grants = _base_capability_grants(lifecycle_state)
    grants = _apply_portal_overlay(portal_mode, grants)
    return _resolve_plan_gated(grants, plan_features)


def resolve_background_policy(lifecycle_state: str) -> Dict[str, str]:
    terminal = lifecycle_state in (
        "CANCELLED_IMMEDIATE",
        "SUBSCRIPTION_EXPIRED",
        "READ_ONLY",
        "SUSPENDED",
        "ARCHIVED",
        "ACCOUNT_DELETED",
        "UNKNOWN",
    )
    grace = lifecycle_state == "GRACE_PERIOD"
    payment_pending = lifecycle_state in ("PAYMENT_PENDING", "TRIAL_EXPIRED", "LEGACY")
    if lifecycle_state == "ACCOUNT_DELETED":
        return {
            "reminders": "TERMINATE",
            "digest": "TERMINATE",
            "scheduled_reports": "TERMINATE",
            "compliance_monitoring": "TERMINATE",
            "score_recalculation": "TERMINATE",
            "risk_recalculation": "TERMINATE",
            "queue_processing": "TERMINATE",
        }
    if lifecycle_state == "ARCHIVED":
        return {
            "reminders": "TERMINATE",
            "digest": "TERMINATE",
            "scheduled_reports": "TERMINATE",
            "compliance_monitoring": "TERMINATE",
            "score_recalculation": "TERMINATE",
            "risk_recalculation": "TERMINATE",
            "queue_processing": "TERMINATE",
        }
    if terminal:
        return {
            "reminders": "PAUSE",
            "digest": "PAUSE",
            "scheduled_reports": "REVOKE",
            "compliance_monitoring": "PAUSE",
            "score_recalculation": "PAUSE",
            "risk_recalculation": "PAUSE",
            "queue_processing": "DRAIN_PAUSE",
        }
    if grace:
        return {
            "reminders": "CONTINUE",
            "digest": "CONTINUE",
            "scheduled_reports": "CONTINUE",
            "compliance_monitoring": "CONTINUE",
            "score_recalculation": "CONTINUE",
            "risk_recalculation": "CONTINUE",
            "queue_processing": "CONTINUE",
        }
    if payment_pending:
        return {
            "reminders": "PAUSE",
            "digest": "PAUSE",
            "scheduled_reports": "PAUSE",
            "compliance_monitoring": "PAUSE",
            "score_recalculation": "PAUSE",
            "risk_recalculation": "PAUSE",
            "queue_processing": "PAUSE",
        }
    return {
        "reminders": "CONTINUE",
        "digest": "CONTINUE",
        "scheduled_reports": "CONTINUE",
        "compliance_monitoring": "CONTINUE",
        "score_recalculation": "CONTINUE",
        "risk_recalculation": "CONTINUE",
        "queue_processing": "CONTINUE",
    }


def resolve_communication_policy(lifecycle_state: str, portal_mode: str) -> Dict[str, Any]:
    billing_only = portal_mode in ("BILLING_RECOVERY", "PAYMENT_REQUIRED", "SUSPENDED")
    archived = lifecycle_state in ("ARCHIVED", "ACCOUNT_DELETED")
    return {
        "email_operational": not billing_only and not archived,
        "email_billing": not archived,
        "sms": lifecycle_state in ("ACTIVE", "TRIAL", "GRACE_PERIOD", "CANCELLATION_SCHEDULED"),
        "portal_notifications": not billing_only and not archived,
        "template_family": {
            "FULL_ACCESS": "operational",
            "GRACE": "payment_grace",
            "BILLING_RECOVERY": "subscription_ended",
            "PAYMENT_REQUIRED": "payment_required",
            "READ_ONLY": "read_only",
            "SUSPENDED": "suspended",
            "ARCHIVED": "archived",
            "ACCOUNT_DELETED": "deleted",
        }.get(portal_mode, "operational"),
    }


def resolve_session_policy(
    lifecycle_state: str,
    *,
    entitlements_version: Optional[int] = None,
) -> Dict[str, Any]:
    terminal = lifecycle_state in ("ARCHIVED", "ACCOUNT_DELETED")
    return {
        "jwt_valid": not terminal,
        "force_reauth": lifecycle_state == "ACCOUNT_DELETED",
        "session_version_bump_recommended": lifecycle_state in (
            "CANCELLED_IMMEDIATE",
            "SUBSCRIPTION_EXPIRED",
            "SUSPENDED",
            "ARCHIVED",
            "ACCOUNT_DELETED",
        ),
        "entitlements_version": int(entitlements_version or 1),
    }


def resolve_retention_policy(
    lifecycle_state: str,
    facts: Dict[str, Any],
) -> Dict[str, Any]:
    tier = "STANDARD"
    if facts.get("read_only_retention") or facts.get("account_lifecycle_read_only"):
        tier = "READ_ONLY_WINDOW"
    elif lifecycle_state in ("ARCHIVED",):
        tier = "PURGE_ELIGIBLE"
    elif lifecycle_state == "READ_ONLY":
        tier = "READ_ONLY_WINDOW"
    retention_tier = str(facts.get("retention_tier") or "").upper()
    if retention_tier in ("READ_ONLY", "READ_ONLY_WINDOW"):
        tier = "READ_ONLY_WINDOW"
    return {
        "tier": tier,
        "data_export_allowed": lifecycle_state not in ("ACCOUNT_DELETED", "ARCHIVED"),
        "purge_eligible_at": facts.get("purged_at"),
    }


def resolve_reactivation_policy(lifecycle_state: str, portal_mode: str) -> Dict[str, Any]:
    eligible_states = {
        "CANCELLED_IMMEDIATE": (True, ["R-005_immediately_cancelled_restored"], "EVERYTHING"),
        "SUBSCRIPTION_EXPIRED": (True, ["R-006_subscription_expired_restored"], "EVERYTHING"),
        "READ_ONLY": (True, ["R-007_read_only_restored"], "EVERYTHING"),
        "SUSPENDED": (True, ["R-008_suspension_lifted"], "SELECTIVE"),
        "GRACE_PERIOD": (True, ["R-002_payment_recovered_grace"], "EVERYTHING"),
        "TRIAL_EXPIRED": (True, ["R-003_trial_converted"], "EVERYTHING"),
        "PAYMENT_PENDING": (True, ["R-004_checkout_completed"], "EVERYTHING"),
        "UNKNOWN": (False, [], "MANUAL_REVIEW"),
        "ARCHIVED": (False, [], "MANUAL_REVIEW"),
        "ACCOUNT_DELETED": (False, [], "MANUAL_REVIEW"),
    }
    eligible, paths, scope = eligible_states.get(
        lifecycle_state, (False, [], "MANUAL_REVIEW")
    )
    if portal_mode == PortalMode.BILLING_RECOVERY.value and lifecycle_state in (
        "CANCELLED_IMMEDIATE",
        "SUBSCRIPTION_EXPIRED",
    ):
        eligible = True
    return {
        "eligible": eligible,
        "paths": paths,
        "restoration_scope": scope,
    }


def resolve_polling_policy(portal_mode: str) -> Dict[str, Any]:
    disabled_modes = {
        PortalMode.BILLING_RECOVERY.value,
        PortalMode.PAYMENT_REQUIRED.value,
        PortalMode.SUSPENDED.value,
        PortalMode.ARCHIVED.value,
        PortalMode.ACCOUNT_DELETED.value,
        PortalMode.READ_ONLY.value,
    }
    enabled = portal_mode not in disabled_modes
    return {
        "enabled": enabled,
        "reason": "lifecycle_terminal" if not enabled else "operational",
        "circuit_breaker_after_denies": 2,
    }


def resolve_navigation_policy(portal_mode: str) -> Dict[str, Any]:
    policies = {
        PortalMode.FULL_ACCESS.value: {
            "landing_route": "/today",
            "locked_routes": [],
            "read_only_routes": [],
            "hidden_routes": [],
        },
        PortalMode.GRACE.value: {
            "landing_route": "/today",
            "locked_routes": [],
            "read_only_routes": [],
            "hidden_routes": [],
        },
        PortalMode.BILLING_RECOVERY.value: {
            "landing_route": "/settings/billing",
            "locked_routes": ["/today", "/dashboard", "/command-center", "/properties/create"],
            "read_only_routes": ["/properties", "/requirements", "/reports"],
            "hidden_routes": ["/operations"],
        },
        PortalMode.PAYMENT_REQUIRED.value: {
            "landing_route": "/settings/billing",
            "locked_routes": ["/today", "/dashboard", "/command-center", "/properties"],
            "read_only_routes": [],
            "hidden_routes": ["/operations", "/reports"],
        },
        PortalMode.READ_ONLY.value: {
            "landing_route": "/properties",
            "locked_routes": ["/properties/create"],
            "read_only_routes": ["/properties", "/requirements", "/reports", "/documents"],
            "hidden_routes": ["/operations"],
        },
        PortalMode.SUSPENDED.value: {
            "landing_route": "/settings/billing",
            "locked_routes": ["/today", "/dashboard", "/command-center", "/properties"],
            "read_only_routes": [],
            "hidden_routes": ["/operations", "/reports"],
        },
        PortalMode.ARCHIVED.value: {
            "landing_route": "/support",
            "locked_routes": ["/today", "/dashboard", "/properties", "/requirements"],
            "read_only_routes": [],
            "hidden_routes": ["/operations", "/reports", "/settings/billing"],
        },
        PortalMode.ACCOUNT_DELETED.value: {
            "landing_route": "/support",
            "locked_routes": ["/"],
            "read_only_routes": [],
            "hidden_routes": ["/operations"],
        },
    }
    return dict(policies.get(portal_mode, policies[PortalMode.BILLING_RECOVERY.value]))


def _customer_experience_for_mode(
    portal_mode: str,
    lifecycle_state: str,
    facts: Dict[str, Any],
    *,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    now = _utc_now(now)
    period_end = facts.get("current_period_end")
    period_end_dt = normalize_stored_period_end_for_api(period_end)
    stale_scheduled = is_stale_scheduled_cancellation_mirror(facts, now=now)
    grace_end = facts.get("grace_period_ends_at")
    templates = {
        PortalMode.FULL_ACCESS.value: {
            "heading": "",
            "explanation": "",
            "reason": "",
            "current_state_label": {
                "TRIAL": "Trial",
                "CANCELLATION_SCHEDULED": "Cancellation scheduled",
                "PAYMENT_FAILED": "Payment issue",
            }.get(lifecycle_state, "Active"),
            "available_features": ["dashboard", "properties", "requirements", "reports", "today", "billing"],
            "unavailable_features": [],
            "primary_cta": {"label": "Continue", "route": "/today"},
            "secondary_cta": None,
            "recovery_guidance": "",
            "support_guidance": "Standard help is available from the support centre.",
            "expected_next_step": "Continue work",
        },
        PortalMode.GRACE.value: {
            "heading": "Payment required",
            "explanation": "We couldn't process your latest payment. Update your payment method to avoid interruption.",
            "reason": "Your account is in a grace period.",
            "current_state_label": "Grace period",
            "available_features": ["properties", "requirements", "reports", "billing"],
            "unavailable_features": [],
            "primary_cta": {"label": "Update payment method", "route": "/settings/billing"},
            "secondary_cta": {"label": "View invoice", "route": "/settings/billing"},
            "recovery_guidance": f"Pay outstanding balance before {grace_end or 'the grace deadline'}.",
            "support_guidance": "Contact support if you believe this is an error.",
            "expected_next_step": "Payment updated — return to normal access",
        },
        PortalMode.BILLING_RECOVERY.value: {
            "heading": "Your subscription has ended",
            "explanation": "Your compliance data is preserved. Resubscribe to restore full access.",
            "reason": "Subscription cancelled" if lifecycle_state == "CANCELLED_IMMEDIATE" else "Billing period ended",
            "current_state_label": "Inactive subscription",
            "available_features": ["billing", "profile", "support", "data_export"],
            "unavailable_features": ["dashboard", "properties", "requirements", "reports", "today"],
            "primary_cta": {"label": "Resubscribe", "route": "/settings/billing"},
            "secondary_cta": {"label": "Export my data", "route": "/settings/billing?tab=export"},
            "recovery_guidance": "Choose a plan to reactivate your account.",
            "support_guidance": "Our team can help with billing questions.",
            "expected_next_step": "Complete resubscription",
        },
        PortalMode.PAYMENT_REQUIRED.value: {
            "heading": "Complete your setup" if lifecycle_state == "PAYMENT_PENDING" else "Your trial has ended",
            "explanation": "Subscribe to continue using Compliance Vault Pro.",
            "reason": "Payment required",
            "current_state_label": "Setup incomplete" if lifecycle_state == "PAYMENT_PENDING" else "Trial expired",
            "available_features": ["billing", "onboarding", "support"],
            "unavailable_features": ["dashboard", "properties", "requirements", "reports", "today"],
            "primary_cta": {"label": "Choose a plan", "route": "/settings/billing"},
            "secondary_cta": {"label": "Contact support", "route": "/support"},
            "recovery_guidance": "Select a plan and enter payment details.",
            "support_guidance": "We can help you choose the right plan.",
            "expected_next_step": "Checkout success — full access restored",
        },
        PortalMode.READ_ONLY.value: {
            "heading": "View-only access",
            "explanation": "You can view and export your data. Subscribe to make changes.",
            "reason": "Subscription lapsed — read-only retention period",
            "current_state_label": "Read-only",
            "available_features": ["properties", "requirements", "reports", "export", "billing"],
            "unavailable_features": ["edit", "upload", "new reports"],
            "primary_cta": {"label": "Subscribe to edit", "route": "/settings/billing"},
            "secondary_cta": {"label": "Export data", "route": "/settings/billing?tab=export"},
            "recovery_guidance": "Renew your subscription to restore editing.",
            "support_guidance": "Standard support is available.",
            "expected_next_step": "Subscription renewed — full access",
        },
        PortalMode.SUSPENDED.value: {
            "heading": "Account suspended",
            "explanation": "Your account access has been restricted.",
            "reason": "Outstanding payment after grace period." if lifecycle_state == "SUSPENDED" else "Administrative suspension.",
            "current_state_label": "Suspended",
            "available_features": ["support", "billing"],
            "unavailable_features": ["dashboard", "properties", "requirements", "reports", "today"],
            "primary_cta": {"label": "Resolve payment", "route": "/settings/billing"},
            "secondary_cta": {"label": "Contact support", "route": "/support"},
            "recovery_guidance": "Resolve payment in Billing to restore full access.",
            "support_guidance": "",
            "expected_next_step": "Reinstatement — full access",
        },
        PortalMode.ARCHIVED.value: {
            "heading": "Account archived",
            "explanation": "This account has been closed. Contact support if you need assistance.",
            "reason": "Account archived",
            "current_state_label": "Archived",
            "available_features": ["support"],
            "unavailable_features": ["dashboard", "properties", "billing", "reports"],
            "primary_cta": {"label": "Contact support", "route": "/support"},
            "secondary_cta": None,
            "recovery_guidance": "Restoration requires support review.",
            "support_guidance": "Contact support for archive enquiries.",
            "expected_next_step": "Support review",
        },
        PortalMode.ACCOUNT_DELETED.value: {
            "heading": "Account removed",
            "explanation": "This account has been permanently deleted.",
            "reason": "Account deleted",
            "current_state_label": "Deleted",
            "available_features": [],
            "unavailable_features": ["all"],
            "primary_cta": {"label": "Contact support", "route": "/support"},
            "secondary_cta": None,
            "recovery_guidance": "",
            "support_guidance": "Contact support for data enquiries.",
            "expected_next_step": "N/A",
        },
    }
    cx = dict(templates.get(portal_mode, templates[PortalMode.BILLING_RECOVERY.value]))
    if lifecycle_state == "CANCELLATION_SCHEDULED" and portal_mode == PortalMode.FULL_ACCESS.value:
        if stale_scheduled:
            cx["heading"] = "Updating your subscription status"
            cx["explanation"] = (
                "Your subscription status is being updated. This usually completes within a few minutes."
            )
            cx["reason"] = "We are synchronising your billing status with Stripe."
            cx["primary_cta"] = {"label": "Keep subscription", "action": "resume_subscription"}
            cx["secondary_cta"] = {"label": "View billing", "route": "/settings/billing"}
            cx["expected_next_step"] = "Status refresh — full access or recovery guidance"
        else:
            cx["heading"] = "Cancellation scheduled"
            if period_end_dt and period_end_dt >= now:
                cx["explanation"] = f"You have full access until {period_end_dt.strftime('%Y-%m-%d %H:%M UTC')}."
            else:
                cx["explanation"] = "You have full access until the end of your billing period."
            cx["primary_cta"] = {"label": "Keep subscription", "action": "resume_subscription"}
            cx["secondary_cta"] = {"label": "View billing", "route": "/settings/billing"}
    return cx


def _load_plan_context(client: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    plan_str = (client or {}).get("billing_plan") or "PLAN_1_SOLO"
    plan_code = plan_registry.resolve_plan_code(plan_str)
    features = plan_registry.get_features(plan_code)
    plan_name = str(plan_code.value if hasattr(plan_code, "value") else plan_code)
    max_properties = None
    try:
        plan_def = plan_registry.get_plan(plan_code)
        plan_name = plan_def.get("name") or plan_name
        max_properties = plan_def.get("max_properties")
    except Exception:
        logger.debug("plan_registry.get_plan unavailable; using plan_code label only", exc_info=True)
    ops_modules = {
        "maintenance_workflows": bool(features.get("maintenance_workflows")),
        "predictive_maintenance": bool(features.get("predictive_maintenance")),
        "rent_operations": bool(features.get("rent_operations")),
    }
    return {
        "plan_code": plan_code.value if hasattr(plan_code, "value") else str(plan_code),
        "plan_name": plan_name,
        "max_properties": max_properties,
        "plan_features": {k: bool(v) for k, v in features.items()},
        "ops_modules": ops_modules,
    }


def _fact_snapshot_hash(source_facts: Dict[str, Any]) -> str:
    payload = json.dumps(source_facts, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def _compute_runtime_version(material: Dict[str, Any]) -> int:
    payload = json.dumps(material, sort_keys=True, default=str)
    digest = int(hashlib.sha256(payload.encode()).hexdigest()[:12], 16)
    return max(1, digest % 2_000_000_000)


def _freeze_mapping(data: Dict[str, Any]) -> Mapping[str, Any]:
    frozen: Dict[str, Any] = {}
    for key, value in data.items():
        if isinstance(value, dict):
            frozen[key] = MappingProxyType(dict(value))
        elif isinstance(value, list):
            frozen[key] = tuple(value)
        else:
            frozen[key] = value
    return MappingProxyType(frozen)


def build_runtime_contract(
    *,
    client: Optional[Dict[str, Any]] = None,
    billing: Optional[Dict[str, Any]] = None,
    now: Optional[datetime] = None,
    entitlements_version: Optional[int] = None,
    include_audit: bool = False,
) -> Mapping[str, Any]:
    """
    Build immutable runtime contract from fact snapshots.

    Does not write to database or mutate inputs.
    """
    started = time.perf_counter()
    now = _utc_now(now)
    client_id = (client or {}).get("client_id") or (billing or {}).get("client_id") or ""

    resolution: LifecycleStateResolution = resolve_account_lifecycle_state(
        client=client, billing=billing, now=now
    )
    lifecycle_state = resolution.account_lifecycle_state
    facts = resolution.source_facts
    read_only = bool(facts.get("read_only_retention") or facts.get("account_lifecycle_read_only"))
    portal_mode = resolve_portal_mode(lifecycle_state, read_only_retention=read_only)

    plan = _load_plan_context(client)
    capabilities = resolve_capabilities(lifecycle_state, portal_mode, plan["plan_features"])
    background_policy = resolve_background_policy(lifecycle_state)
    communication_policy = resolve_communication_policy(lifecycle_state, portal_mode)
    session_policy = resolve_session_policy(lifecycle_state, entitlements_version=entitlements_version)
    retention_policy = resolve_retention_policy(lifecycle_state, facts)
    reactivation_policy = resolve_reactivation_policy(lifecycle_state, portal_mode)
    polling_policy = resolve_polling_policy(portal_mode)
    navigation_policy = resolve_navigation_policy(portal_mode)
    customer_experience = _customer_experience_for_mode(portal_mode, lifecycle_state, facts, now=now)

    commercial_exception = None
    try:
        from services.commercial_entitlement_service import (
            commercial_continuity_overlay_active,
            commercial_restored_plan_code,
        )

        if commercial_continuity_overlay_active(client, billing):
            restored = commercial_restored_plan_code(client, billing)
            overlay_client = dict(client or {})
            if restored:
                overlay_client["billing_plan"] = restored
            plan = _load_plan_context(overlay_client)
            portal_mode = PortalMode.FULL_ACCESS.value
            capabilities = resolve_capabilities("ACTIVE", portal_mode, plan["plan_features"])
            background_policy = resolve_background_policy("ACTIVE")
            communication_policy = resolve_communication_policy("ACTIVE", portal_mode)
            session_policy = resolve_session_policy("ACTIVE", entitlements_version=entitlements_version)
            customer_experience = _customer_experience_for_mode(portal_mode, "ACTIVE", facts, now=now)
            commercial_exception = {
                "active": True,
                "effective_entitlement_state": "ENABLED",
                "restored_plan_code": restored,
                "underlying_lifecycle_state": lifecycle_state,
                "portal_mode_override": portal_mode,
                "governance_id": (client or {}).get("commercial_governance_id"),
                "governance_state": (client or {}).get("commercial_governance_state"),
            }
    except Exception:
        logger.debug("commercial continuity overlay skipped client_id=%s", client_id, exc_info=True)

    lifecycle_context = {
        "state_label": customer_experience.get("current_state_label") or lifecycle_state,
        "state_reason": resolution.reason,
        "period_end": facts.get("current_period_end"),
        "grace_end": facts.get("grace_period_ends_at"),
        "last_event_id": None,
        "last_event_type": None,
        "transition_pending": is_stale_scheduled_cancellation_mirror(facts, now=now),
        "commercial_overlay_active": bool(commercial_exception),
    }

    material = {
        "lifecycle_state": lifecycle_state,
        "portal_mode": portal_mode,
        "capabilities": capabilities,
        "plan_code": plan["plan_code"],
        "background_policy": background_policy,
        "communication_policy": communication_policy,
        "session_policy": {
            "force_reauth": session_policy["force_reauth"],
            "jwt_valid": session_policy["jwt_valid"],
        },
        "reactivation_policy": reactivation_policy,
        "navigation_policy": navigation_policy,
        "commercial_overlay": bool(commercial_exception),
        "restored_plan_code": (commercial_exception or {}).get("restored_plan_code") if commercial_exception else None,
    }
    runtime_version = _compute_runtime_version(material)
    elapsed_ms = round((time.perf_counter() - started) * 1000, 3)

    contract: Dict[str, Any] = {
        "contract_version": CONTRACT_VERSION,
        "runtime_version": runtime_version,
        "client_id": client_id,
        "resolved_at": now.isoformat(),
        "policy_pins": {
            "lifecycle_policy": LIFECYCLE_POLICY_VERSION,
            "capability_authority": CAPABILITY_AUTHORITY_VERSION,
            "portal_mode_authority": PORTAL_MODE_AUTHORITY_VERSION,
        },
        "lifecycle_state": lifecycle_state,
        "portal_mode": portal_mode,
        "lifecycle_context": lifecycle_context,
        "capabilities": capabilities,
        "plan": plan,
        "customer_experience": customer_experience,
        "background_policy": background_policy,
        "communication_policy": communication_policy,
        "session_policy": session_policy,
        "retention_policy": retention_policy,
        "reactivation_policy": reactivation_policy,
        "polling_policy": polling_policy,
        "navigation_policy": navigation_policy,
        "warnings": list(resolution.warnings),
        "source_facts": facts,
        "commercial_exception": commercial_exception,
        "resolver_metadata": {
            "policy_version": resolution.policy_version,
            "resolver_version": resolution.resolver_version,
            "confidence": resolution.confidence,
            "reason": resolution.reason,
            "generation_timestamp": now.isoformat(),
            "runtime_build_id": RUNTIME_BUILD_ID,
        },
    }
    if include_audit:
        contract["audit"] = {
            "resolver_build_id": RUNTIME_BUILD_ID,
            "fact_snapshot_hash": _fact_snapshot_hash(facts),
            "resolution_ms": elapsed_ms,
        }
    return _freeze_mapping(contract)


def runtime_contract_to_dict(contract: Mapping[str, Any]) -> Dict[str, Any]:
    """Deep plain dict for JSON serialization."""

    def _deep(value: Any) -> Any:
        if isinstance(value, Mapping):
            return {str(k): _deep(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [_deep(v) for v in value]
        return value

    return json.loads(json.dumps(_deep(contract), default=str))


async def load_client_and_billing(db, client_id: str):
    from services.account_lifecycle_state_resolver import load_client_and_billing as _load

    return await _load(db, client_id)


async def resolve_runtime_contract_for_client(
    db,
    client_id: str,
    *,
    now: Optional[datetime] = None,
    use_cache: bool = True,
    include_audit: bool = False,
    emit_events: bool = True,
) -> Mapping[str, Any]:
    client, billing = await load_client_and_billing(db, client_id)
    entitlements_version = None
    if client:
        entitlements_version = client.get("entitlements_version")
    now = _utc_now(now)
    if client_id and billing:
        billing, _reconciled = await reconcile_stale_scheduled_cancellation_if_needed(
            client_id,
            billing,
            now=now,
            event_source="runtime_contract_stale_scheduled_cancellation",
        )
    contract = build_runtime_contract(
        client={**(client or {}), "client_id": client_id} if client_id else client,
        billing=billing,
        now=now,
        entitlements_version=entitlements_version,
        include_audit=include_audit,
    )
    previous = peek_cached_runtime_contract(client_id) if client_id and use_cache else None
    if emit_events and client_id and previous is not None:
        try:
            from services.account_lifecycle_event_authority import publish_runtime_contract_transition

            await publish_runtime_contract_transition(
                db,
                previous,
                contract,
                trigger="runtime_contract_resolve",
            )
        except Exception as exc:
            logger.debug("lifecycle_event_publish_skipped client_id=%s error=%s", client_id, exc)
    if use_cache and client_id:
        _runtime_cache[client_id] = (time.time(), contract["runtime_version"], contract)
    return contract


def get_cached_runtime_contract(client_id: str, runtime_version: int) -> Optional[Mapping[str, Any]]:
    entry = _runtime_cache.get(client_id)
    if not entry:
        return None
    cached_at, cached_version, contract = entry
    if time.time() - cached_at > CACHE_TTL_SECONDS:
        return None
    if cached_version != runtime_version:
        return None
    return contract


def peek_cached_runtime_contract(client_id: str) -> Optional[Mapping[str, Any]]:
    """Return cached contract if within TTL (for lifecycle event transition detection)."""
    entry = _runtime_cache.get(client_id)
    if not entry:
        return None
    cached_at, _, contract = entry
    if time.time() - cached_at > CACHE_TTL_SECONDS:
        return None
    return contract


def invalidate_runtime_cache_for_client(client_id: str) -> None:
    _runtime_cache.pop(client_id, None)


def compare_runtime_with_legacy(
    contract: Mapping[str, Any],
) -> Dict[str, Any]:
    """Read-only drift diagnostic vs legacy stored bands."""
    facts = contract.get("source_facts") or {}
    drift: List[str] = []
    canonical = str(facts.get("canonical_entitlement_state") or "").upper()
    billing_lc = str(facts.get("billing_lifecycle_state") or "").lower()
    entitlement = str(facts.get("entitlement_status") or "").upper()
    lifecycle = contract.get("lifecycle_state")
    portal = contract.get("portal_mode")

    implied_canonical = {
        "ACTIVE": "ENABLED",
        "TRIAL": "ENABLED",
        "CANCELLATION_SCHEDULED": "ENABLED",
        "PAYMENT_FAILED": "ENABLED",
        "GRACE_PERIOD": "GRACE",
        "CANCELLED_IMMEDIATE": "CANCELLED",
        "SUBSCRIPTION_EXPIRED": "SUSPENDED",
        "TRIAL_EXPIRED": "SUSPENDED",
        "SUSPENDED": "SUSPENDED",
        "READ_ONLY": "SUSPENDED",
    }.get(lifecycle)
    if canonical and implied_canonical and canonical != implied_canonical:
        drift.append(f"canonical_mismatch:stored={canonical}:implied={implied_canonical}")

    if lifecycle == "ACTIVE" and portal not in ("FULL_ACCESS", "GRACE"):
        drift.append(f"portal_mode_unexpected_for_active:{portal}")
    if lifecycle in ("CANCELLED_IMMEDIATE", "SUBSCRIPTION_EXPIRED") and portal not in (
        "BILLING_RECOVERY",
        "READ_ONLY",
    ):
        drift.append(f"portal_mode_unexpected_for_cancelled:{portal}")

    caps = dict(contract.get("capabilities") or {})
    if lifecycle == "ACTIVE" and caps.get("CAP_PROP_VIEW") == GRANT_DENY:
        drift.append("capability_drift:ACTIVE_denies_CAP_PROP_VIEW")

    return {
        "lifecycle_state": lifecycle,
        "portal_mode": portal,
        "canonical_entitlement_state": canonical or None,
        "billing_lifecycle_state": billing_lc or None,
        "entitlement_status": entitlement or None,
        "runtime_version": contract.get("runtime_version"),
        "drift_flags": drift,
        "warnings": list(contract.get("warnings") or []),
    }
