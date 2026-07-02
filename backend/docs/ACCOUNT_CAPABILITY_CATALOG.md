# Account Capability Catalog

**Programme:** ACCOUNT-LIFECYCLE-CAPABILITY-AUTHORITY-01  
**Authority version:** `account_capability_v1`  
**Parent:** `ACCOUNT_CAPABILITY_AUTHORITY.md`

---

## Catalog conventions

| Field | Meaning |
|-------|---------|
| **ID** | Stable `CAP_*` identifier |
| **Class** | Read, Write, Administrative, Background, System, Shared, Customer |
| **Owner** | Authoritative subsystem (policy owner, not implementation) |
| **Plan key** | `plan_registry` feature_key if PLAN_GATED; `—` if lifecycle-only |
| **Legacy alias** | Deprecated keys mapping to this capability |

---

## Authentication (`CAP_AUTH_*`)

| ID | Description | Class | Owner | Dependencies | Default | Security | Audit |
|----|-------------|-------|-------|--------------|---------|----------|-------|
| `CAP_AUTH_LOGIN` | Sign in to client portal | Customer | Authentication service | Valid credentials | ALLOW when account not ARCHIVED/DELETED | Credential handling | Login events |
| `CAP_AUTH_LOGOUT` | Sign out | Customer | Authentication service | Active session | ALLOW | Session termination | Logout events |
| `CAP_AUTH_PASSWORD_RESET` | Reset forgotten password | Customer | Authentication service | Email verification | ALLOW | Token expiry | Reset requests |
| `CAP_AUTH_MFA` | Multi-factor authentication | Customer | Authentication service | MFA enrolled | ALLOW | TOTP/WebAuthn | MFA events |
| `CAP_AUTH_SESSION_RECOVERY` | Recover session after expiry | Customer | Session policy (ILP-5) | Valid refresh | ALLOW | Token rotation | Session refresh |

---

## Profile (`CAP_PROFILE_*`)

| ID | Description | Class | Owner | Plan key | Default | Security | Audit |
|----|-------------|-------|-------|----------|---------|----------|-------|
| `CAP_PROFILE_VIEW` | View profile and org settings | Read | Client settings | — | ALLOW | PII access logged | Settings view |
| `CAP_PROFILE_EDIT` | Edit profile details | Write | Client settings | — | ALLOW | PII mutation | Settings change |
| `CAP_PROFILE_JURISDICTION` | View/edit default jurisdiction | Administrative | Requirement Authority | — | ALLOW | Affects obligation set | Jurisdiction change |

---

## Subscription (`CAP_SUB_*`)

| ID | Description | Class | Owner | Plan key | Default | Security | Audit |
|----|-------------|-------|-------|----------|---------|----------|-------|
| `CAP_SUB_VIEW` | View subscription status | Read | Billing (read-only) | — | ALLOW | No payment mutation | — |
| `CAP_SUB_MANAGE` | Cancel, resume, change plan | Write | Billing API | — | Lifecycle-dependent | Stripe actions | Cancellation events |
| `CAP_SUB_RENEW` | Renew expired subscription | Write | Billing API | — | REQUIRES_RENEWAL states | Payment required | SUBSCRIPTION_STARTED |
| `CAP_SUB_UPGRADE` | Upgrade plan tier | Write | Billing API | — | PLAN_GATED | Proration | Plan change |
| `CAP_SUB_DOWNGRADE` | Downgrade plan tier | Write | Billing API | — | PLAN_GATED | Feature loss warning | Plan change |
| `CAP_SUB_CANCEL` | Request cancellation | Write | Billing API | — | ALLOW in ACTIVE/TRIAL | irreversible paths warned | CANCELLATION_* events |

---

## Billing (`CAP_BILLING_*`)

| ID | Description | Class | Owner | Default | Security | Audit |
|----|-------------|-------|-------|---------|----------|-------|
| `CAP_BILLING_VIEW` | View billing dashboard | Read | Billing API | ALLOW (billing exempt routes) | PCI scope minimal | — |
| `CAP_BILLING_INVOICES` | View/download invoices | Read | Billing API | ALLOW | Financial data | Invoice access |
| `CAP_BILLING_PAYMENT_METHODS` | Manage payment methods | Write | Stripe integration | ALLOW | PCI via Stripe | Payment method change |
| `CAP_BILLING_CHECKOUT` | Complete checkout / onboarding payment | Write | Billing API | PAYMENT_REQUIRED states | Payment capture | Checkout events |

---

## Properties (`CAP_PROP_*`)

| ID | Description | Class | Owner | Plan key | Default | Security | Audit |
|----|-------------|-------|-------|----------|---------|----------|-------|
| `CAP_PROP_VIEW` | View property portfolio | Read | Property service | — | Lifecycle-dependent | Portfolio PII | Property view |
| `CAP_PROP_CREATE` | Create property | Write | Property service | — | FULL_ACCESS only | Address data | Property created |
| `CAP_PROP_EDIT` | Edit property details | Write | Property service | — | FULL_ACCESS only | Address mutation | Property updated |
| `CAP_PROP_ARCHIVE` | Archive property | Write | Property service | — | FULL_ACCESS only | Soft delete | Archive event |
| `CAP_PROP_DELETE` | Delete property | Write | Property service | — | FULL_ACCESS only | Irreversible warning | Delete event |
| `CAP_PROP_IMPORT` | Bulk import properties | Write | Property service | `document_upload_bulk_zip` | PLAN_GATED | Bulk PII | Import job |

---

## Requirements (`CAP_REQ_*`)

| ID | Description | Class | Owner | Default | Security | Audit |
|----|-------------|-------|-------|---------|----------|-------|
| `CAP_REQ_VIEW` | View requirements | Read | Requirement Authority | Lifecycle-dependent | Obligation data | — |
| `CAP_REQ_RESOLVE` | Resolve requirement with evidence | Write | Requirement Authority | FULL_ACCESS / LIMITED grace | Evidence linkage | Resolution events |
| `CAP_REQ_MARK_N_A` | Mark requirement not applicable | Write | Requirement Authority | FULL_ACCESS | Declaration audit | N/A events |
| `CAP_REQ_COMPLETE` | Mark requirement complete | Write | Lifecycle Authority (req) | FULL_ACCESS | State transition | Completion events |

---

## Documents (`CAP_DOC_*`)

| ID | Description | Class | Owner | Plan key | Default | Security | Audit |
|----|-------------|-------|-------|----------|---------|----------|-------|
| `CAP_DOC_VIEW` | View uploaded documents | Read | Evidence Authority | — | Lifecycle-dependent | Document access | View log |
| `CAP_DOC_UPLOAD` | Upload single document | Write | Evidence Authority | `document_upload_single` | PLAN_GATED | Virus scan | Upload event |
| `CAP_DOC_REPLACE` | Replace document version | Write | Evidence Authority | `document_upload_single` | PLAN_GATED | Version chain | Replace event |
| `CAP_DOC_DELETE` | Delete document | Write | Evidence Authority | — | FULL_ACCESS | Retention policy | Delete event |
| `CAP_DOC_BULK_ZIP` | Bulk ZIP upload | Write | Evidence Authority | `zip_upload` / `document_upload_bulk_zip` | PLAN_GATED | Bulk scan | Bulk job |
| `CAP_DOC_MULTI_UPLOAD` | Multi-file upload | Write | Evidence Authority | `multi_file_upload` | PLAN_GATED | — | Upload events |

---

## Evidence (`CAP_EVIDENCE_*`)

| ID | Description | Class | Owner | Default | Security | Audit |
|----|-------------|-------|-------|---------|----------|-------|
| `CAP_EVIDENCE_VIEW` | View evidence registry | Read | Evidence Authority | Lifecycle-dependent | Evidence graph | — |
| `CAP_EVIDENCE_DOWNLOAD` | Download evidence files | Shared | Evidence Authority | READ tier in recovery | Export control | Download log |
| `CAP_EVIDENCE_LINK` | Link evidence to requirements | Write | Evidence Authority | FULL_ACCESS | Graph integrity | Link events |
| `CAP_EVIDENCE_REGISTRY` | Access evidence registry API | Read | Evidence Authority | Lifecycle-dependent | — | — |

---

## Reports (`CAP_REPORT_*`)

| ID | Description | Class | Owner | Plan key | Default | Security | Audit |
|----|-------------|-------|-------|----------|---------|----------|-------|
| `CAP_REPORT_VIEW` | View report catalog and history | Read | Report Presentation Authority | — | Lifecycle-dependent | — | — |
| `CAP_REPORT_GENERATE_PDF` | Generate PDF reports | Write | Report Presentation Authority | `reports_pdf` | PLAN_GATED | Generation cost | Report job |
| `CAP_REPORT_GENERATE_CSV` | Generate CSV reports | Write | Report Presentation Authority | `reports_csv` | PLAN_GATED | — | Report job |
| `CAP_REPORT_DOWNLOAD` | Download generated reports | Shared | Report Presentation Authority | READ tier | Export | Download log |
| `CAP_REPORT_SHARE` | Share report via link | Write | Report service | `reports_pdf` | PLAN_GATED | Token expiry | Share event |
| `CAP_REPORT_SCHEDULE` | Schedule recurring reports | Administrative | Report scheduler | `scheduled_reports` | PLAN_GATED | — | Schedule CRUD |
| `CAP_REPORT_AUDIT_PACK` | Generate audit evidence pack | Write | Report Presentation Authority | `audit_log_export` | PLAN_GATED | Sensitive bundle | Pack job |

---

## Compliance (`CAP_COMPLIANCE_*` / `CAP_SCORE_*` / `CAP_RISK_*`)

| ID | Description | Class | Owner | Plan key | Default |
|----|-------------|-------|-------|----------|---------|
| `CAP_SCORE_VIEW` | View compliance score | Read | Score Authority | `compliance_score` | Lifecycle-dependent |
| `CAP_SCORE_EXPLAIN` | View score explanation | Read | Score Authority | `compliance_score` | Lifecycle-dependent |
| `CAP_SCORE_TREND` | View score trends | Read | Score Authority | `score_trending` | PLAN_GATED |
| `CAP_SCORE_SNAPSHOT` | Trigger score snapshot | Write | Score Authority | `compliance_score` | FULL_ACCESS |
| `CAP_RISK_VIEW` | View risk signals | Read | Risk engine | `predictive_maintenance` | PLAN_GATED + ops flag |
| `CAP_RISK_ANALYSIS` | Run risk analysis | Background | Risk engine | `predictive_maintenance` | CAP_BG_RISK_RECALC |
| `CAP_COMPLIANCE_MONITOR` | Compliance monitoring active | Background | Compliance monitoring | — | CAP_BG_COMPLIANCE_CHECK |
| `CAP_COMPLIANCE_ACTIVITY` | View compliance activity feed | Read | Command Centre Authority | `compliance_dashboard` | Lifecycle-dependent |
| `CAP_DASHBOARD_VIEW` | View compliance dashboard | Read | Command Centre Authority | `compliance_dashboard` | Lifecycle-dependent |
| `CAP_CALENDAR_VIEW` | View compliance/expiry calendar | Read | Navigation Authority | `compliance_calendar` | PLAN_GATED |

---

## Today & Command Centre (`CAP_TODAY_*`, `CAP_CMD_*`)

| ID | Description | Class | Owner | Default |
|----|-------------|-------|-------|---------|
| `CAP_TODAY_VIEW` | View Today workspace | Read | Today Authority | FULL_ACCESS portal modes |
| `CAP_TODAY_ACT` | Act on Today tasks | Write | Today Authority | FULL_ACCESS |
| `CAP_CMD_CTR_VIEW` | View Command Centre | Read | Command Centre Authority | FULL_ACCESS |
| `CAP_WORK_QUEUE_VIEW` | View work queue | Read | Today Authority | FULL_ACCESS |
| `CAP_LEDGER_VIEW` | View compliance ledger | Read | Compliance service | Lifecycle-dependent |
| `CAP_LEDGER_EXPORT` | Export ledger CSV | Shared | Compliance service | `reports_csv` PLAN_GATED |

---

## Notifications (`CAP_NOTIF_*`)

| ID | Description | Class | Owner | Plan key | Default |
|----|-------------|-------|-------|----------|---------|
| `CAP_NOTIF_EMAIL` | Receive email reminders | Background | Communication Authority | `email_notifications` | CAP_BG_REMINDERS |
| `CAP_NOTIF_SMS` | Receive SMS reminders | Background | Communication Authority | `sms_reminders` | PLAN_GATED |
| `CAP_NOTIF_PORTAL` | Portal notifications | Customer | Notification service | — | Lifecycle-dependent |
| `CAP_NOTIF_PREFS` | Manage notification preferences | Administrative | Notification service | — | ALLOW except DELETED |

---

## Exports (`CAP_EXPORT_*`)

| ID | Description | Class | Owner | Maps from |
|----|-------------|-------|-------|-----------|
| `CAP_EXPORT_CSV` | CSV data export | Shared | Export service | `reports_csv`, ledger |
| `CAP_EXPORT_PDF` | PDF export | Shared | Report Presentation Authority | `reports_pdf` |
| `CAP_EXPORT_ZIP` | ZIP bulk export | Shared | Document service | `zip_upload` |
| `CAP_EXPORT_API` | Read API / webhooks data export | Shared | Integration service | `webhooks` |
| `CAP_DATA_EXPORT` | Account data export (lifecycle recovery) | Shared | Support/recovery | BILLING_RECOVERY tier |

---

## AI (`CAP_AI_*`)

| ID | Description | Class | Owner | Plan key |
|----|-------------|-------|-------|----------|
| `CAP_AI_ASSISTANT` | AI assistant chat | Customer | AI service | — (future plan gate) |
| `CAP_AI_EXTRACTION_BASIC` | Basic document extraction | Background | AI extraction | `ai_extraction_basic` |
| `CAP_AI_EXTRACTION_ADVANCED` | Advanced extraction | Background | AI extraction | `ai_extraction_advanced` |
| `CAP_AI_REVIEW` | Extraction review UI | Write | AI review | `extraction_review_ui` / `ai_review_interface` |
| `CAP_KNOWLEDGE_CENTRE` | Help/knowledge base | Read | Support content | — |

---

## Operations (`CAP_OPS_*`)

| ID | Description | Class | Owner | Plan key / ops flag |
|----|-------------|-------|-------|---------------------|
| `CAP_OPS_ISSUES_VIEW` | View maintenance issues | Read | Maintenance service | `maintenance_workflows` |
| `CAP_OPS_MAINTENANCE` | Manage work orders | Write | Maintenance service | `maintenance_workflows` |
| `CAP_OPS_CONTRACTORS` | Contractor network | Write | Contractor service | `contractor_network` |
| `CAP_OPS_PREDICTIVE` | Predictive maintenance insights | Read | Predictive service | `predictive_maintenance` |
| `CAP_OPS_RENT` | Rent operations | Write | Rent operations | — |
| `CAP_OPS_APPROVALS` | Approvals workflow | Write | Approvals service | `compliance_engine` |
| `CAP_OPS_COMPLIANCE_REVIEW` | Org compliance review | Write | Compliance review | `compliance_engine` |

---

## Tenants (`CAP_TENANT_*`)

| ID | Description | Class | Owner | Plan key |
|----|-------------|-------|-------|----------|
| `CAP_TENANT_PORTAL` | Tenant portal access | Customer | Tenant portal service | `tenant_portal` / `tenant_portal_access` |
| `CAP_TENANT_MANAGE` | Invite/manage tenants | Administrative | Tenant service | `tenant_portal` |
| `CAP_TENANT_MESSAGES` | Tenant messaging | Write | Tenant service | `tenant_portal` |

---

## Integrations (`CAP_INTEGRATION_*`)

| ID | Description | Class | Owner | Plan key |
|----|-------------|-------|-------|----------|
| `CAP_INTEGRATION_WEBHOOKS` | Configure webhooks | Administrative | Integration service | `webhooks` |
| `CAP_INTEGRATION_READ_API` | Client read API keys | Administrative | Integration service | `webhooks` |

---

## Branding (`CAP_BRANDING_*`)

| ID | Description | Class | Owner | Plan key |
|----|-------------|-------|-------|----------|
| `CAP_BRANDING_VIEW` | View branding settings | Read | Branding service | `white_label_reports` |
| `CAP_BRANDING_EDIT` | Edit branding/logo | Write | Branding service | `white_label_reports` |
| `CAP_BRANDING_WHITE_LABEL` | White-label reports | Shared | Report Presentation Authority | `white_label_reports` |

---

## Support (`CAP_SUPPORT_*`)

| ID | Description | Class | Owner | Default |
|----|-------------|-------|-------|---------|
| `CAP_SUPPORT_ACCESS` | Access help/support | Customer | Support service | ALLOW all non-DELETED |
| `CAP_SUPPORT_REQUEST` | Submit support request | Customer | Support service | ALLOW |
| `CAP_ACCOUNT_RECOVERY` | Billing/account recovery flows | Customer | Billing + ALPA | BILLING_RECOVERY modes |
| `CAP_AUDIT_LOG_VIEW` | View client audit log | Read | Audit service | Lifecycle-dependent |
| `CAP_AUDIT_LOG_EXPORT` | Export audit log | Shared | Audit service | `audit_log_export` |

---

## Background (`CAP_BG_*`)

| ID | Description | Class | Owner | Triggers |
|----|-------------|-------|-------|----------|
| `CAP_BG_REMINDERS` | Daily compliance reminders | Background | Reminder engine | ACTIVE, TRIAL, GRACE, CANCELLATION_SCHEDULED |
| `CAP_BG_DIGEST` | Monthly digest | Background | Digest job | Same as reminders |
| `CAP_BG_SCHEDULED_REPORTS` | Scheduled report delivery | Background | Report scheduler | ACTIVE + `scheduled_reports` |
| `CAP_BG_COMPLIANCE_CHECK` | Compliance status monitoring | Background | Compliance job | ACTIVE, TRIAL, GRACE |
| `CAP_BG_SCORE_RECALC` | Score recalculation | Background | Score Authority | ACTIVE, TRIAL, GRACE |
| `CAP_BG_RISK_RECALC` | Risk recalculation | Background | Risk engine | ACTIVE + predictive flag |
| `CAP_BG_LIFECYCLE_SYNC` | Subscription lifecycle sync | System | subscription_lifecycle_service | Stripe webhooks |
| `CAP_BG_RENEWAL_REMINDERS` | Subscription renewal reminders | Background | Lifecycle job | CANCELLATION_SCHEDULED, ACTIVE |
| `CAP_BG_VERIFICATION_DIGEST` | Pending verification digest | Background | Admin/compliance job | ACTIVE |

---

## Legacy alias compatibility table

| Legacy `feature_key` | Capability ID |
|---------------------|---------------|
| `zip_upload` | `CAP_DOC_BULK_ZIP` |
| `document_upload_bulk_zip` | `CAP_DOC_BULK_ZIP` |
| `tenant_portal_access` | `CAP_TENANT_PORTAL` |
| `ai_review_interface` | `CAP_AI_REVIEW` |
| `compliance_calendar` | `CAP_CALENDAR_VIEW` |
| `expiry_calendar` | `CAP_CALENDAR_VIEW` |
| `compliance_dashboard` | `CAP_DASHBOARD_VIEW` |
| `maintenance_workflows` | `CAP_OPS_MAINTENANCE` |
| `predictive_maintenance` | `CAP_OPS_PREDICTIVE` |
| `contractor_network` | `CAP_OPS_CONTRACTORS` |
| `compliance_engine` | `CAP_OPS_APPROVALS` |

---

**Outcome:** `ACCOUNT_CAPABILITY_CATALOG_COMPLETE`
