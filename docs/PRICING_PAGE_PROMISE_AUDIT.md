# Pricing Page Promise Audit

**Live URL:** https://order-fulfillment-9.emergent.host  
**Branch:** main  
**Source of truth:** Pricing page (Solo / Portfolio / Professional) and `backend/services/plan_registry.py` FEATURE_MATRIX.

---

## 1. Feature Promise Matrix

| Pricing page promise | Feature key (plan_registry) | Backend route(s) / service | Frontend screen(s) | DB / fields | Gating rule |
|----------------------|-----------------------------|----------------------------|--------------------|-------------|-------------|
| **Core: Compliance Dashboard** | compliance_dashboard | GET /api/client/dashboard | ClientDashboard.js, /app/dashboard | clients, properties, requirements | All plans; no gate on route |
| **Core: Compliance Score** | compliance_score | GET /api/client/compliance-score, /trend, /explanation | ClientDashboard.js, ComplianceScorePage.js | requirements, compliance_snapshots | All plans; no gate |
| **Core: Expiry Calendar** | compliance_calendar | GET/POST /api/calendar/* (client calendar) | CalendarPage.js | calendar_events, requirements | plan_registry.enforce_feature("compliance_calendar") in calendar.py |
| **Core: Email Notifications** | email_notifications | GET/PUT /api/profile/notifications | NotificationPreferencesPage.js | notification_preferences | All plans; no gate |
| **Core: Document Upload** | multi_file_upload | POST /api/documents/upload, etc. | DocumentsPage.js | documents | All plans (multi_file_upload True all) |
| **Core: Score Trending** | score_trending | GET /api/client/compliance-score/trend | ClientDashboard.js (sparkline) | compliance_snapshots | All plans; no gate |
| **AI: Basic AI Extraction** | ai_extraction_basic | Document analysis in documents.py, document_analysis service | DocumentsPage (upload → extract) | documents | All plans |
| **AI: Advanced AI Extraction** | ai_extraction_advanced | Same pipeline; advanced fields/confidence | DocumentsPage | documents | Portfolio+ (plan_registry); get_features in documents |
| **AI: AI Review Interface** | extraction_review_ui | Review/approve extracted data before apply | DocumentsPage / review UI | documents | Portfolio+ |
| **Documents: ZIP Bulk Upload** | zip_upload | POST /api/documents/properties/{id}/bulk-upload (require_feature), POST /api/documents/upload-zip | BulkUploadPage.js | documents | require_feature("zip_upload"); plan_registry in upload-zip |
| **Reporting: PDF Reports** | reports_pdf | GET /api/reports/compliance-summary?format=pdf, /requirements?format=pdf, compliance-pack | ReportsPage.js | report_schedules | require_feature("reports_pdf") on PDF; plan_registry on compliance-pack |
| **Reporting: CSV Export** | reports_csv | GET /api/reports/compliance-summary?format=csv, /requirements?format=csv | ReportsPage.js | — | Fixed: gated by plan_registry.enforce_feature("reports_csv") (Portfolio+). |
| **Reporting: Scheduled Reports** | scheduled_reports | POST /api/reports/schedules, GET /api/reports/schedules | ReportsPage.js | report_schedules | plan_registry.enforce_feature("scheduled_reports") |
| **Communication: SMS Reminders** | sms_reminders | Admin message + sms; jobs send_daily_reminders (email); client SMS prefs | NotificationPreferencesPage (SMS toggle) | notification_preferences.sms_*, sms_logs | admin_billing checks sms_entitled; client SMS UI not gated by plan in backend (plan in get_plan_features) |
| **Tenant Portal: Tenant View Access** | tenant_portal | POST /api/client/tenants/invite, GET /api/client/tenants, assign, unassign, revoke, resend; GET /api/tenant/dashboard | TenantManagementPage.js, tenant dashboard | portal_users (ROLE_TENANT), tenant_assignments | Fixed: all tenant management routes gated by plan_registry.enforce_feature("tenant_portal") (Portfolio+). |
| **Integrations: Webhooks** | webhooks | POST /api/webhooks, GET /api/webhooks, GET /api/webhooks/{id} | IntegrationsPage.js | webhooks | Fixed: create, list, and get by id all gated by plan_registry.enforce_feature("webhooks") (Pro only). |
| **Integrations: API Access** | api_access | No dedicated client API-key or external API route found | BillingPage.js shows feature in plan; IntegrationsPage (webhooks) | — | **PARTIAL:** Feature in plan_registry (Pro only); no backend “API access” endpoint to gate. Either document as “future” or add read-only API key endpoint gated by api_access. |
| **Advanced: White-Label Reports** | white_label_reports | GET /api/client/reports/white-label/settings, PUT white-label | ReportsPage / white-label section | client white-label config | plan_registry.enforce_feature("white_label_reports") |
| **Advanced: Audit Log Export** | audit_log_export | GET /api/reports/audit-log/export (client) or audit log PDF | ReportsPage / admin | audit_logs | plan_registry.enforce_feature("audit_log_export") in reports.py |

---

## 2. Status per feature

| Feature | Status | Evidence / notes |
|---------|--------|-------------------|
| Compliance Dashboard | WORKING | GET /api/client/dashboard; ClientDashboard; no gate (all plans). |
| Compliance Score | WORKING | /api/client/compliance-score, /trend; ComplianceScorePage, ClientDashboard sparkline. |
| Expiry Calendar | WORKING | calendar.py enforce_feature("compliance_calendar"); CalendarPage. |
| Email Notifications | WORKING | /api/profile/notifications; NotificationPreferencesPage. |
| Document Upload | WORKING | /api/documents/*; DocumentsPage; multi_file_upload true all plans. |
| Score Trending | WORKING | /api/client/compliance-score/trend; ClientDashboard. |
| Basic AI Extraction | WORKING | document_analysis; DocumentsPage. |
| Advanced AI Extraction | WORKING | plan_registry ai_extraction_advanced; documents.py get_features_by_string. |
| AI Review Interface | WORKING | extraction_review_ui Portfolio+; review UI in flow. |
| ZIP Bulk Upload | WORKING | require_feature("zip_upload") + plan_registry in upload-zip; BulkUploadPage. |
| PDF Reports | WORKING | require_feature("reports_pdf") for PDF; compliance-pack gated. |
| CSV Export | WORKING | Gated by reports_csv (Portfolio+) on compliance-summary and requirements CSV. |
| Scheduled Reports | WORKING | enforce_feature("scheduled_reports") on POST /api/reports/schedules. |
| SMS Reminders | PARTIAL | Admin send message checks sms_entitled; client SMS prefs exist; daily reminders are email. Plan check in admin_billing. |
| Tenant View Access | WORKING | All tenant routes gated by enforce_feature("tenant_portal") (Portfolio+). |
| Webhooks | WORKING | Create, list, get by id gated by enforce_feature("webhooks") (Pro only). |
| API Access | PARTIAL | In plan_registry (Pro); no client-facing API key or external API route. |
| White-Label Reports | WORKING | enforce_feature("white_label_reports") on client white-label routes. |
| Audit Log Export | WORKING | enforce_feature("audit_log_export") on audit log PDF export. |

---

## 3. Property limits enforcement

| Plan | Max properties | Where enforced | Evidence |
|------|----------------|---------------|----------|
| Solo | 2 | backend/routes/properties.py create_property; intake validate-property-count, submit | plan_registry.get_plan(plan_code)["max_properties"]; 403 PROPERTY_LIMIT_EXCEEDED |
| Portfolio | 10 | Same | plan_registry 10 |
| Professional | 25 | Same | plan_registry 25 |

- **Bulk import:** properties.py bulk-import checks current_count + import_count vs limit.
- **Intake:** plan_registry.check_property_limit in validate-property-count and submit.
- **Stripe downgrade:** stripe_webhook_service sets over_property_limit when count > new limit.

---

## 4. Gating summary (Solo vs Portfolio vs Pro)

- **Solo (PLAN_1_SOLO):** Core (dashboard, score, calendar, email, document upload, score trending), Basic AI. No ZIP, no PDF/CSV reports, no scheduled reports, no SMS, no tenant portal, no webhooks, no API access, no white-label, no audit export.
- **Portfolio (PLAN_2_PORTFOLIO):** Solo + ZIP, PDF/CSV, scheduled reports, SMS, tenant portal, Advanced AI, AI Review. No webhooks, no API access, no white-label, no audit export.
- **Pro (PLAN_3_PRO):** Portfolio + webhooks, API access, white-label reports, audit log export.

---

## 5. Blank screen and deploy verification

- **Blank screen:** See docs/BLANK_SCREEN_DEBUG_AND_PATCHES.md. Error Boundary, 401→session expired, 403→explicit alerts, dashboard shell always renders, API URL log and build stamp added.
- **Deploy verification:** GET /api/version returns commit_sha + environment. Frontend: REACT_APP_BUILD_SHA in console and optional footer. Verify live: `curl -s https://order-fulfillment-9.emergent.host/api/version`.

---

## 6. Fixes applied (this audit)

1. **CSV Export:** Gate CSV format on GET /api/reports/compliance-summary and GET /api/reports/requirements with reports_csv (Portfolio+). Return 403 for Solo with clear message.
2. **Tenant portal:** Add plan_registry.enforce_feature("tenant_portal") to: POST /api/client/tenants/invite, GET /api/client/tenants, POST assign, DELETE unassign, DELETE revoke, POST resend-invite. Return 403 for Solo.
3. **Webhooks:** Add enforce_feature("webhooks") to GET /api/webhooks (list) and GET /api/webhooks/{id} so Pro-only is enforced on all webhook access.
4. **API Access:** Document as “Pro feature; API key / external API coming later” or add a minimal read-only API key endpoint gated by api_access (TBD).
5. **SMS Reminders:** Confirm client-facing SMS preference toggle is only shown when plan has sms_reminders (frontend can use /client/plan-features); backend already checks in admin message.

---

## 7. Routes to hit for manual verification

- **Solo:** GET /api/client/dashboard (200), GET /api/reports/compliance-summary?format=csv (should 403 after fix), GET /api/client/tenants (should 403 after fix), POST /api/webhooks (403), GET /api/webhooks (403 after fix).
- **Portfolio:** GET /api/reports/compliance-summary?format=csv (200), POST /api/client/tenants/invite (200 with body), GET /api/reports/schedules (200), POST /api/webhooks (403).
- **Pro:** POST /api/webhooks (200 with body), GET /api/webhooks (200), GET /api/client/reports/white-label/settings (200), GET /api/reports/audit-log/export (200 with params).

---

## 8. RBAC (admin vs client)

- **Admin-only:** Routes under /api/admin/* use admin_route_guard or require_admin; client routes use client_route_guard (client_id from token). Owner can bypass plan gating in require_feature (feature_gating.py).
- **Client-only:** /api/client/*, /api/reports/*, /api/documents/*, /api/calendar/*, /api/webhooks (client), /api/properties/* use client_route_guard; no admin-only data exposed.
