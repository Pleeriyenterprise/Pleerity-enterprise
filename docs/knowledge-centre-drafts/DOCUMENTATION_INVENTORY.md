# Documentation Inventory – Knowledge Centre First-Draft Generation

**Purpose:** Discovery output and suggested article list for the Knowledge Centre. Grounded in the current codebase (routes, pages, backend). No product behaviour modified.

---

## A) Main user-facing modules/pages (from App.js and ClientPortalLayout)

| Module / Page | Route(s) | Implemented | Notes |
|---------------|----------|-------------|--------|
| Dashboard | `/dashboard` | Yes | ClientDashboard; score, trend, properties, checklist, operations KPIs (feature-gated). |
| Properties | `/properties`, `/properties/create`, `/properties/:propertyId`, `/properties/import` | Yes | PropertiesPage, PropertyCreatePage, PropertyDetailPage, BulkPropertyImportPage. |
| Compliance (Requirements) | `/requirements` | Yes | RequirementsPage; group by property/requirement, edit applicability, not required. |
| Documents / Evidence | `/documents`, `/documents/bulk-upload` | Yes | DocumentsPage, BulkUploadPage; upload, extraction, confirm details. |
| Compliance Score | `/compliance-score` | Yes | ComplianceScorePage; score, drivers, trend, methodology, PDF/CSV export (plan-gated). |
| Calendar | `/calendar` | Yes | CalendarPage. |
| Reports | `/reports` | Yes | ReportsPage. |
| Assistant | `/assistant` | Yes | AssistantPage. |
| Help Centre | `/help` | Yes | HelpPage; USER articles from `/api/client/help/*`. |
| Settings | `/settings`, `/settings/profile`, `/settings/notifications`, `/settings/billing` | Yes | ProfilePage, NotificationPreferencesPage, BillingPage. |
| Audit log | `/audit-log` | Yes | ClientAuditLogPage. |
| Tenant portal | `/tenant`, `/tenant/properties`, `/tenant/settings` | Yes | Feature-gated (tenant_portal). |
| Tenants (management) | `/tenants` | Yes | TenantManagementPage; feature-gated. |
| Integrations | `/integrations` | Yes | Feature-gated (webhooks). |
| Orders | `/orders`, `/orders/:orderId/provide-info` | Yes | ClientOrdersPage, ClientProvideInfoPage. |
| Operations – Issues | `/operations/issues`, `/operations/issues/:issueId` | Yes | Feature-gated (maintenance_workflows). |
| Operations – Work orders | `/operations/work-orders` | Yes | ClientMaintenancePage; feature-gated. |
| Operations – Contractors | `/operations/contractors` | Yes | ClientContractorsPage; feature-gated. |
| Operations – Risk signals | `/operations/risk-signals` | Yes | ClientRiskSignalsPage; feature-gated (predictive_maintenance). |
| Operations – Approvals | `/operations/approvals` | Yes | Feature-gated (invoicing). |
| Billing | `/settings/billing` | Yes | BillingPage. |
| Timeline | — | No | No dedicated “Timeline” route; calendar and score timeline exist. |
| Assets | — | No | No dedicated Assets module in client routes. |

---

## B) Admin-facing modules/pages

| Module / Page | Route(s) | Implemented | Notes |
|---------------|----------|-------------|--------|
| Admin Dashboard | `/admin/dashboard` | Yes | Tabs: Clients, Rules, Templates, Email delivery, etc. |
| Analytics | `/admin/analytics`, `/admin/analytics/executive` | Yes | Owner/admin-only. |
| Reporting | `/admin/reporting` | Yes | AdminReportingPage. |
| Lead Management | `/admin/leads` | Yes | |
| Risk Check Leads | `/admin/risk-leads` | Yes | |
| Talent Pool | `/admin/talent-pool` | Yes | |
| Partnership Enquiries | `/admin/partnership-enquiries` | Yes | |
| Contact Enquiries | `/admin/inbox/enquiries` | Yes | |
| Clients (tab) | `/admin/dashboard` (tabTarget: clients) | Yes | |
| Orders Pipeline | `/admin/orders` | Yes | |
| Service Catalogue | `/admin/services` | Yes | |
| Intake Schema | `/admin/intake-schema` | Yes | |
| Pricing & Billing | `/admin/billing` | Yes | |
| Pending Payments | `/admin/billing` (tab) | Yes | |
| Ops Overview | `/admin/ops` | Yes | |
| Ops Compliance | `/admin/ops/compliance` | Yes | Placeholder page (AdminOpsPlaceholderPage). |
| Ops Maintenance | `/admin/ops/maintenance` | Yes | AdminOpsMaintenancePage. |
| Ops Contractors | `/admin/ops/contractors` | Yes | |
| Ops Risk & Insights | `/admin/ops/risk` | Yes | Placeholder. |
| Ops Audit & Logs | `/admin/ops/audit` | Yes | Placeholder. |
| Feature Controls | `/admin/ops/feature-controls` | Yes | AdminOpsFeatureControlsPage. |
| ClearForm (users, documents, orgs, types, audit) | `/admin/clearform/*` | Yes | Separate product. |
| Site Builder | `/admin/site-builder` | Yes | |
| Knowledge Centre | `/admin/knowledge-base` | Yes | AdminKnowledgeBasePage; CRUD, categories, PDF export. |
| Blog / Insights | `/admin/blog` | Yes | |
| FAQ Management | `/admin/content/faqs` | Yes | |
| Canned Responses | `/admin/support/responses` | Yes | |
| Legal Pages | `/admin/settings/legal` | Yes | |
| Newsletter | `/admin/marketing/newsletter` | Yes | |
| Support Dashboard | `/admin/support` | Yes | |
| Postal Tracking | `/admin/postal-tracking` | Yes | |
| Team Permissions | `/admin/team` | Yes | |
| Prompt Manager | `/admin/prompts` | Yes | |
| Enablement Engine | `/admin/enablement` | Yes | |
| Privacy & Consent | `/admin/privacy/consent` | Yes | |
| Notification Health | `/admin/notification-health` | Yes | |
| System Health | `/admin/system-health` | Yes | |
| Automation Centre | `/admin/automation` | Yes | Jobs, Run Now, incidents. |
| Incidents | `/admin/incidents` | Yes | |
| Organisations | — | No | ClearForm has organizations; no main-platform “Organisations” admin. |
| Users (platform) | — | Partial | Team Permissions; no single “Users” list page. |
| Feature Flags | Partial | Feature Controls (Ops); entitlements/plan features drive client nav. |
| Jobs / Automation Health | Yes | Automation Centre + System Health. |
| Email / Notification Health | Yes | Notification Health page + Email delivery tab. |
| Audit Logs | Yes | Client audit log; Ops Audit (placeholder); ClearForm audit. |

---

## C) Core workflows (from codebase)

| Workflow | Implemented | Where |
|----------|-------------|--------|
| Signup / Login | Yes | PortalSelectorPage, ClientLoginPage, AdminLoginPage; `/login`, `/login/client`, `/login/admin`; set-password, forgot-password. |
| Onboarding | Yes | IntakePage (`/intake/start`), OnboardingStatusPage; checkout success redirect; provisioning. |
| Property creation | Yes | PropertyCreatePage; `POST /api/properties/create`; plan limit enforced. |
| Evidence upload | Yes | DocumentsPage; upload → extraction (async) → Confirm details modal; `POST /api/documents/upload`. |
| Compliance score update | Yes | Recalc jobs; `GET /api/client/compliance-score`, trend, timeline APIs. |
| Reminder scheduling | Yes | `daily_reminders` job (e.g. 09:00 UTC); notification preferences (daily_reminder_enabled, expiry_reminders). |
| Compliance pack generation | Yes | Backend compliance_pack service; client/tenant routes; PDF generation. Needs verification for full user-facing flow. |
| Work order flow | Yes | Client maintenance page; admin ops maintenance; feature-gated. |
| Contractor assignment | Yes | Client contractors page; admin ops contractors; feature-gated. |
| Provisioning (post-payment) | Yes | portal/setup-status, resend-activation; provisioning_runner. |
| Feature flags / entitlements | Yes | EntitlementsContext, hasFeature, plan_registry; client nav and export gating. |

---

## Suggested articles per module (for Knowledge Centre)

### Priority 1 — User-critical (USER audience)

| # | Title | Slug | Category (category_id) | Module |
|---|--------|------|--------------------------|--------|
| 1 | Getting Started | getting-started | getting-started | Dashboard |
| 2 | How to Add a Property | adding-a-property | adding-properties | Properties |
| 3 | How to Upload a Gas Safety Certificate (and other evidence) | uploading-evidence | documents-uploads | Evidence |
| 4 | Understanding Your Compliance Score | compliance-score-explained | compliance-score | Compliance Score |
| 5 | Dashboard Guide | dashboard-guide | dashboard-guide | Dashboard |
| 6 | How Reminder Alerts Work | reminders-and-alerts | reminders | Reminders |
| 7 | How to View and Download Compliance Packs | compliance-packs-download | compliance-packs | Reports / Compliance |

*Note: `uploading-evidence`, `adding-a-property`, `compliance-score-explained`, `reminders-and-alerts` may already exist as published seed articles; use distinct slugs for new drafts if importing (e.g. `getting-started`, `dashboard-guide`, `compliance-packs-download`) or create as drafts with same slugs only where intent is to replace.*

### Priority 2 — Staff-critical (STAFF or ADMIN audience)

| # | Title | Slug | Category (category_id) | Module |
|---|--------|------|--------------------------|--------|
| 8 | Admin Console Overview | admin-console-overview | admin-console | Admin |
| 9 | Reviewing Onboarding Status | onboarding-status-review | provisioning | Provisioning |
| 10 | How Provisioning Works | how-provisioning-works | provisioning | Provisioning |
| 11 | How to Diagnose Missing Obligations | diagnose-missing-obligations | compliance-engine | Compliance |
| 12 | How Evidence Confirmation Affects Scoring | evidence-confirmation-scoring | compliance-engine | Compliance |
| 13 | How to Monitor Reminder Jobs | monitor-reminder-jobs | job-monitoring | Automation |
| 14 | How to Review Email Failures | review-email-failures | support-procedures | Support |
| 15 | How Feature Flags Affect Access | feature-flags-access | feature-flags | Feature Controls |

### Priority 3 — Operational playbooks (ADMIN / STAFF)

| # | Title | Slug | Category (category_id) | Module |
|---|--------|------|--------------------------|--------|
| 16 | Failed Provisioning Recovery | playbook-failed-provisioning | operations-playbooks | Provisioning |
| 17 | Reminder Failure Response | playbook-reminder-failure | operations-playbooks | Automation |
| 18 | Evidence Upload Troubleshooting | playbook-evidence-upload | support-procedures | Evidence |
| 19 | Login Failure Investigation | playbook-login-failure | support-procedures | Auth |
| 20 | Compliance Pack Generation Support | playbook-compliance-pack | support-procedures | Compliance |
| 21 | Feature Flag Rollout Procedure | playbook-feature-rollout | feature-flags | Feature Controls |

### User help (additional)

| # | Title | Slug | Category | Module |
|---|--------|------|----------|--------|
| 22 | Billing & Plans | billing-and-plans | billing-subscriptions | Billing |
| 23 | Troubleshooting Login Issues | troubleshooting-login | troubleshooting | Auth |
| 24 | How to View Property Alerts | property-alerts | adding-properties | Properties |

### Release note template

| # | Title | Slug | Category | Notes |
|---|--------|------|----------|--------|
| 25 | Release note (template) | release-note-template | release-notes | article_type: release_notes; template only. |

---

## Relationship to existing content

- **Training manuals:** `docs/training/` contains full training manuals (admin + client) for trainers. Knowledge Centre articles are shorter, Help Centre–oriented, and stored in `kb_articles` when imported. They complement rather than replace the training docs.
- **Seed KB articles:** `backend/scripts/seed_kb_articles.py` creates four **published** USER articles (uploading-evidence, adding-a-property, compliance-score-explained, reminders-and-alerts). New drafts from this inventory use **status = draft** and do not auto-publish. Use distinct slugs for new drafts where the seed already uses that slug, or import as drafts with same slug only if the workflow is “replace seed with reviewed draft.”
- **Conflict / safest option:** Do not overwrite existing published seed articles. Create new draft articles with the slugs above; for overlapping topics (e.g. “Understanding Your Compliance Score”), either use the same slug and leave seed as-is and create a separate draft “Understanding Your Compliance Score (revised)” with slug `compliance-score-explained-v2`, or create drafts only for articles that do not yet exist (getting-started, dashboard-guide, billing-and-plans, troubleshooting-login, all staff/playbook articles). **Recommended:** Generate drafts for all suggested titles with **status = draft**; use slugs as in the table; if slug already exists in KB, import script should skip or create with a -v2 suffix.
