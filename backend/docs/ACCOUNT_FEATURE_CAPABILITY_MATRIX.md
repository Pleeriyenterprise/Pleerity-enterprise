# Account Feature Capability Matrix

**Programme:** ACCOUNT-LIFECYCLE-CAPABILITY-AUTHORITY-01  
**Authority version:** `account_capability_v1`  
**Parent:** `ACCOUNT_CAPABILITY_CATALOG.md`

Maps **product features** (UI surfaces, plan features) to **capabilities**. No feature may bypass capability authority.

---

## Plan features (`plan_registry.FEATURE_MATRIX`)

| Feature key | Capability ID(s) | Notes |
|-------------|------------------|-------|
| `compliance_dashboard` | `CAP_DASHBOARD_VIEW` | |
| `compliance_score` | `CAP_SCORE_VIEW`, `CAP_SCORE_EXPLAIN` | |
| `compliance_calendar` | `CAP_CALENDAR_VIEW` | |
| `expiry_calendar` | `CAP_CALENDAR_VIEW` | Legacy alias |
| `email_notifications` | `CAP_NOTIF_EMAIL` | |
| `document_upload_single` | `CAP_DOC_UPLOAD` | |
| `multi_file_upload` | `CAP_DOC_MULTI_UPLOAD` | |
| `score_trending` | `CAP_SCORE_TREND` | |
| `ai_extraction_basic` | `CAP_AI_EXTRACTION_BASIC` | |
| `ai_extraction_advanced` | `CAP_AI_EXTRACTION_ADVANCED` | |
| `extraction_review_ui` | `CAP_AI_REVIEW` | |
| `ai_review_interface` | `CAP_AI_REVIEW` | Legacy alias |
| `document_upload_bulk_zip` | `CAP_DOC_BULK_ZIP` | |
| `zip_upload` | `CAP_DOC_BULK_ZIP` | Legacy alias |
| `reports_pdf` | `CAP_REPORT_GENERATE_PDF`, `CAP_REPORT_DOWNLOAD` | |
| `reports_csv` | `CAP_REPORT_GENERATE_CSV`, `CAP_EXPORT_CSV` | |
| `scheduled_reports` | `CAP_REPORT_SCHEDULE`, `CAP_BG_SCHEDULED_REPORTS` | |
| `sms_reminders` | `CAP_NOTIF_SMS` | |
| `tenant_portal` | `CAP_TENANT_PORTAL`, `CAP_TENANT_MANAGE` | |
| `tenant_portal_access` | `CAP_TENANT_PORTAL` | Legacy alias |
| `webhooks` | `CAP_INTEGRATION_WEBHOOKS`, `CAP_INTEGRATION_READ_API` | |
| `white_label_reports` | `CAP_BRANDING_WHITE_LABEL`, `CAP_BRANDING_EDIT` | |
| `audit_log_export` | `CAP_AUDIT_LOG_EXPORT`, `CAP_REPORT_AUDIT_PACK` | |

---

## Ops module features (`/client/entitlements` flags)

| Feature flag | Capability ID(s) | Owner |
|--------------|------------------|-------|
| `maintenance_workflows` | `CAP_OPS_ISSUES_VIEW`, `CAP_OPS_MAINTENANCE` | Ops compliance module |
| `predictive_maintenance` | `CAP_OPS_PREDICTIVE`, `CAP_RISK_VIEW` | Predictive service |
| `contractor_network` | `CAP_OPS_CONTRACTORS` | Contractor service |
| `compliance_engine` | `CAP_OPS_APPROVALS`, `CAP_OPS_COMPLIANCE_REVIEW`, `CAP_REQ_RESOLVE` | Compliance engine |

---

## UI feature → capability

| UI feature / page | Primary capabilities |
|-------------------|---------------------|
| Property Dashboard | `CAP_DASHBOARD_VIEW`, `CAP_PROP_VIEW` |
| Property Editing | `CAP_PROP_EDIT` |
| Property Create | `CAP_PROP_CREATE` |
| Bulk Property Import | `CAP_PROP_IMPORT` |
| Requirements Page | `CAP_REQ_VIEW`, `CAP_REQ_RESOLVE` |
| Documents Page | `CAP_DOC_VIEW`, `CAP_DOC_UPLOAD` |
| Bulk Upload | `CAP_DOC_BULK_ZIP` |
| Evidence Upload | `CAP_DOC_UPLOAD`, `CAP_EVIDENCE_LINK` |
| Audit Pack | `CAP_REPORT_AUDIT_PACK` |
| Reports catalog | `CAP_REPORT_VIEW` |
| PDF report generation | `CAP_REPORT_GENERATE_PDF` |
| CSV report generation | `CAP_REPORT_GENERATE_CSV` |
| Scheduled reports UI | `CAP_REPORT_SCHEDULE` |
| Compliance Score page | `CAP_SCORE_VIEW`, `CAP_SCORE_EXPLAIN`, `CAP_SCORE_TREND` |
| Today workspace | `CAP_TODAY_VIEW`, `CAP_TODAY_ACT` |
| Command Centre | `CAP_CMD_CTR_VIEW` |
| Work Queue | `CAP_WORK_QUEUE_VIEW` |
| Billing / subscription | `CAP_BILLING_VIEW`, `CAP_SUB_MANAGE` |
| Notification preferences | `CAP_NOTIF_PREFS` |
| Integrations / webhooks | `CAP_INTEGRATION_WEBHOOKS` |
| Tenant management | `CAP_TENANT_MANAGE` |
| AI Assistant | `CAP_AI_ASSISTANT` |
| Help / Knowledge | `CAP_KNOWLEDGE_CENTRE`, `CAP_SUPPORT_ACCESS` |
| Branding settings | `CAP_BRANDING_EDIT` |
| Audit log page | `CAP_AUDIT_LOG_VIEW` |
| Operations: Issues | `CAP_OPS_ISSUES_VIEW` |
| Operations: Maintenance | `CAP_OPS_MAINTENANCE` |
| Operations: Contractors | `CAP_OPS_CONTRACTORS` |
| Operations: Risk signals | `CAP_OPS_PREDICTIVE` |
| Operations: Rent | `CAP_OPS_RENT` |
| Operations: Approvals | `CAP_OPS_APPROVALS` |
| Calendar | `CAP_CALENDAR_VIEW` |
| Ledger export | `CAP_LEDGER_EXPORT` |
| Subscription renewal CTA | `CAP_SUB_RENEW` |
| Plan upgrade prompt | `CAP_SUB_UPGRADE` |
| Account data export | `CAP_DATA_EXPORT` |

---

## Frontend consumption pattern (target)

```
effective = capabilityResolver(CAP_*, lifecycle, portal_mode)
if effective === PLAN_GATED:
    show = planRegistry.hasFeature(mapped_feature_key)
else:
    show = effective === ALLOW || effective === READ
```

**Current:** `hasFeature(feature_key)` only — **FEATURE_MAPPING_GAP** (ACA-001, ACA-003).

---

## EntitlementProtectedRoute mapping

| Route | Current `requiredFeature` | Required capabilities |
|-------|-------------------------|----------------------|
| `/integrations` | `webhooks` | `CAP_INTEGRATION_WEBHOOKS` |
| Tenant routes | `tenant_portal` | `CAP_TENANT_PORTAL` |

Target: `requiredCapabilities={['CAP_INTEGRATION_WEBHOOKS']}` with lifecycle check first.

---

**Outcome:** `ACCOUNT_FEATURE_CAPABILITY_MATRIX_COMPLETE`
