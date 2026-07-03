#!/usr/bin/env python3
"""Read-only drift diagnostic: catalog vs runtime resolver vs compatibility mappings (ILP-4)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from services.account_capability_enforcement import runtime_resolved_capability_ids  # noqa: E402
from services.capability_compatibility import FEATURE_KEY_TO_CAPABILITIES  # noqa: E402

# Governed catalog inventory (ACCOUNT_CAPABILITY_CATALOG.md) — static for Phase 0–1.
CATALOG_CAPABILITY_IDS = sorted(
    {
        "CAP_AUTH_LOGIN",
        "CAP_AUTH_LOGOUT",
        "CAP_AUTH_PASSWORD_RESET",
        "CAP_AUTH_MFA",
        "CAP_AUTH_SESSION_RECOVERY",
        "CAP_PROFILE_VIEW",
        "CAP_PROFILE_EDIT",
        "CAP_PROFILE_JURISDICTION",
        "CAP_SUB_VIEW",
        "CAP_SUB_MANAGE",
        "CAP_SUB_RENEW",
        "CAP_SUB_UPGRADE",
        "CAP_SUB_DOWNGRADE",
        "CAP_SUB_CANCEL",
        "CAP_BILLING_VIEW",
        "CAP_BILLING_INVOICES",
        "CAP_BILLING_PAYMENT_METHODS",
        "CAP_BILLING_CHECKOUT",
        "CAP_PROP_VIEW",
        "CAP_PROP_CREATE",
        "CAP_PROP_EDIT",
        "CAP_PROP_ARCHIVE",
        "CAP_PROP_DELETE",
        "CAP_PROP_IMPORT",
        "CAP_REQ_VIEW",
        "CAP_REQ_RESOLVE",
        "CAP_REQ_MARK_N_A",
        "CAP_REQ_COMPLETE",
        "CAP_DOC_VIEW",
        "CAP_DOC_UPLOAD",
        "CAP_DOC_REPLACE",
        "CAP_DOC_DELETE",
        "CAP_DOC_BULK_ZIP",
        "CAP_DOC_MULTI_UPLOAD",
        "CAP_EVIDENCE_VIEW",
        "CAP_EVIDENCE_DOWNLOAD",
        "CAP_EVIDENCE_LINK",
        "CAP_EVIDENCE_REGISTRY",
        "CAP_REPORT_VIEW",
        "CAP_REPORT_GENERATE_PDF",
        "CAP_REPORT_GENERATE_CSV",
        "CAP_REPORT_DOWNLOAD",
        "CAP_REPORT_SHARE",
        "CAP_REPORT_SCHEDULE",
        "CAP_REPORT_AUDIT_PACK",
        "CAP_SCORE_VIEW",
        "CAP_SCORE_EXPLAIN",
        "CAP_SCORE_TREND",
        "CAP_SCORE_SNAPSHOT",
        "CAP_RISK_VIEW",
        "CAP_RISK_ANALYSIS",
        "CAP_COMPLIANCE_MONITOR",
        "CAP_COMPLIANCE_ACTIVITY",
        "CAP_DASHBOARD_VIEW",
        "CAP_CALENDAR_VIEW",
        "CAP_TODAY_VIEW",
        "CAP_TODAY_ACT",
        "CAP_CMD_CTR_VIEW",
        "CAP_WORK_QUEUE_VIEW",
        "CAP_LEDGER_VIEW",
        "CAP_LEDGER_EXPORT",
        "CAP_NOTIF_EMAIL",
        "CAP_NOTIF_SMS",
        "CAP_NOTIF_PORTAL",
        "CAP_NOTIF_PREFS",
        "CAP_EXPORT_CSV",
        "CAP_EXPORT_PDF",
        "CAP_EXPORT_ZIP",
        "CAP_EXPORT_API",
        "CAP_DATA_EXPORT",
        "CAP_AI_ASSISTANT",
        "CAP_AI_EXTRACTION_BASIC",
        "CAP_AI_EXTRACTION_ADVANCED",
        "CAP_AI_REVIEW",
        "CAP_KNOWLEDGE_CENTRE",
        "CAP_OPS_ISSUES_VIEW",
        "CAP_OPS_MAINTENANCE",
        "CAP_OPS_CONTRACTORS",
        "CAP_OPS_PREDICTIVE",
        "CAP_OPS_RENT",
        "CAP_OPS_APPROVALS",
        "CAP_OPS_COMPLIANCE_REVIEW",
        "CAP_TENANT_PORTAL",
        "CAP_TENANT_MANAGE",
        "CAP_TENANT_MESSAGES",
        "CAP_INTEGRATION_WEBHOOKS",
        "CAP_INTEGRATION_READ_API",
        "CAP_BRANDING_VIEW",
        "CAP_BRANDING_EDIT",
        "CAP_BRANDING_WHITE_LABEL",
        "CAP_SUPPORT_ACCESS",
        "CAP_SUPPORT_REQUEST",
        "CAP_ACCOUNT_RECOVERY",
        "CAP_AUDIT_LOG_VIEW",
        "CAP_AUDIT_LOG_EXPORT",
        "CAP_BG_REMINDERS",
        "CAP_BG_DIGEST",
        "CAP_BG_SCHEDULED_REPORTS",
        "CAP_BG_COMPLIANCE_CHECK",
        "CAP_BG_SCORE_RECALC",
        "CAP_BG_RISK_RECALC",
        "CAP_BG_LIFECYCLE_SYNC",
        "CAP_BG_RENEWAL_REMINDERS",
        "CAP_BG_VERIFICATION_DIGEST",
    }
)


def main() -> int:
    runtime = runtime_resolved_capability_ids()
    catalog = set(CATALOG_CAPABILITY_IDS)
    missing_runtime = sorted(catalog - runtime)
    extra_runtime = sorted(runtime - catalog)
    payload = {
        "catalog_count": len(catalog),
        "runtime_resolver_count": len(runtime),
        "compatibility_feature_mappings": len(FEATURE_KEY_TO_CAPABILITIES),
        "missing_from_runtime": missing_runtime,
        "missing_from_runtime_count": len(missing_runtime),
        "runtime_not_in_catalog": extra_runtime,
    }
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
