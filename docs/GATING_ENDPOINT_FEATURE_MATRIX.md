# Gating: Endpoint → FeatureKey Map (Pricing Page Aligned)

**Source of truth:** `backend/services/plan_registry.py` (FEATURE_MATRIX).  
Stripe webhooks are the only updater of `billing_plan`, `subscription_status`, `entitlements_version`.

**Definition of Done (per feature):** Working UI + backend endpoint(s) + real persistence + server-side FeatureKey enforcement (403 + PLAN_GATE_DENIED audit on deny). No UI-only toggles. Proof required: allowed tier succeeds, blocked tier returns 403 with upgrade_required.

---

## Tiers (authoritative)

| Tier | Cap | Features |
|------|-----|----------|
| **SOLO** | 2 properties | Core + Basic AI only |
| **PORTFOLIO** | 10 properties | SOLO + zip_upload, reports_pdf, scheduled_reports |
| **PROFESSIONAL** | 25 properties | PORTFOLIO + ai_extraction_advanced, ai_review_interface, reports_csv, sms_reminders, tenant_portal, webhooks, white_label_reports, audit_log_export |

**API Access:** Removed (not implemented). No feature key, no UI, no routes.

---

## Endpoint → FeatureKey → Allowed Tiers

| Method | Route | FeatureKey | Allowed Tiers |
|--------|-------|------------|---------------|
| POST | /api/documents/upload | document_upload_single | SOLO, PORTFOLIO, PROFESSIONAL |
| POST | /api/documents/bulk-upload | zip_upload | PORTFOLIO, PROFESSIONAL |
| POST | /api/documents/zip-upload | zip_upload | PORTFOLIO, PROFESSIONAL |
| POST | /api/documents/analyze/{id} (return_advanced=false) | ai_extraction_basic | SOLO, PORTFOLIO, PROFESSIONAL |
| POST | /api/documents/analyze/{id} (return_advanced=true) | ai_extraction_advanced | PROFESSIONAL only |
| POST | /api/documents/{id}/apply-extraction | ai_review_interface | PROFESSIONAL only |
| POST | /api/documents/{id}/reject-extraction | ai_review_interface | PROFESSIONAL only |
| GET | /api/documents/{id}/extraction | (same as apply – view for review) | PROFESSIONAL when review UI |
| GET | /api/reports/available | (list only) | All (content gated per report) |
| GET | /api/reports/compliance-summary?format=pdf | reports_pdf | PORTFOLIO, PROFESSIONAL |
| GET | /api/reports/compliance-summary?format=csv | reports_csv | PROFESSIONAL only |
| GET | /api/reports/requirements?format=pdf | reports_pdf | PORTFOLIO, PROFESSIONAL |
| GET | /api/reports/requirements?format=csv | reports_csv | PROFESSIONAL only |
| POST | /api/reports/schedules | scheduled_reports | PORTFOLIO, PROFESSIONAL |
| GET | /api/reports/schedules | scheduled_reports | PORTFOLIO, PROFESSIONAL |
| DELETE | /api/reports/schedules/{id} | scheduled_reports | PORTFOLIO, PROFESSIONAL |
| PATCH | /api/reports/schedules/{id}/toggle | scheduled_reports | PORTFOLIO, PROFESSIONAL |
| GET | /api/reports/professional/compliance-summary | reports_pdf | PORTFOLIO, PROFESSIONAL |
| GET | /api/reports/professional/expiry-schedule | reports_pdf | PORTFOLIO, PROFESSIONAL |
| GET | /api/reports/professional/audit-log | audit_log_export | PROFESSIONAL only |
| GET | /api/client/compliance-pack/{property_id}/download | reports_pdf | PORTFOLIO, PROFESSIONAL |
| GET | /api/client/branding | white_label_reports (read with upgrade_required in body) | All (write gated) |
| PUT | /api/client/branding | white_label_reports | PROFESSIONAL only |
| POST | /api/client/branding/reset | white_label_reports | PROFESSIONAL only |
| POST | /api/client/tenants/invite | tenant_portal | PROFESSIONAL only |
| GET | /api/client/tenants | tenant_portal | PROFESSIONAL only |
| POST | /api/client/tenants/{id}/assign-property | tenant_portal | PROFESSIONAL only |
| DELETE | /api/client/tenants/{id}/unassign-property/{property_id} | tenant_portal | PROFESSIONAL only |
| DELETE | /api/client/tenants/{id} | tenant_portal | PROFESSIONAL only |
| POST | /api/client/tenants/{id}/resend-invite | tenant_portal | PROFESSIONAL only |
| GET | /api/webhooks | webhooks | PROFESSIONAL only |
| POST | /api/webhooks | webhooks | PROFESSIONAL only |
| GET | /api/webhooks/events | webhooks | PROFESSIONAL only |
| GET | /api/webhooks/stats | webhooks | PROFESSIONAL only |
| GET | /api/webhooks/{id} | webhooks | PROFESSIONAL only |
| PATCH | /api/webhooks/{id} | webhooks | PROFESSIONAL only |
| DELETE | /api/webhooks/{id} | webhooks | PROFESSIONAL only |
| POST | /api/webhooks/{id}/test | webhooks | PROFESSIONAL only |
| POST | /api/webhooks/{id}/enable | webhooks | PROFESSIONAL only |
| POST | /api/webhooks/{id}/disable | webhooks | PROFESSIONAL only |
| POST | /api/webhooks/{id}/regenerate-secret | webhooks | PROFESSIONAL only |
| GET | /api/calendar/expiries | compliance_calendar / expiry_calendar | SOLO, PORTFOLIO, PROFESSIONAL |
| GET | /api/calendar/upcoming | compliance_calendar | SOLO, PORTFOLIO, PROFESSIONAL |
| GET | /api/calendar/export.ics | compliance_calendar | SOLO, PORTFOLIO, PROFESSIONAL |
| GET | /api/calendar/subscription-url | compliance_calendar | SOLO, PORTFOLIO, PROFESSIONAL |
| GET | /api/client/dashboard | compliance_dashboard | SOLO, PORTFOLIO, PROFESSIONAL |
| GET | /api/client/compliance-score | compliance_score | SOLO, PORTFOLIO, PROFESSIONAL |
| GET | /api/client/compliance-score/trend | score_trending | SOLO, PORTFOLIO, PROFESSIONAL |

**SMS:** No single “endpoint” for client-initiated SMS; daily reminder job enforces `sms_reminders` (Professional only) and logs to `sms_logs`. Admin test-send: `POST /api/admin/billing/test-notification` with `channels: ["sms"]` – respects plan.

**Email notifications:** Event-based emails (e.g. expiring soon) logged to `message_logs`; no plan gate (all tiers have email_notifications).

---

## Audit events

| Action | When |
|--------|------|
| **PLAN_GATE_DENIED** | 403 on gated endpoint: feature_key, endpoint, method, reason, client_id (documents, reports, webhooks, client tenant/branding). |
| **PLAN_UPDATED_FROM_STRIPE** | Webhook handler (checkout + subscription change). |
| **STRIPE_EVENT_PROCESSED** | Same. |
| **PLAN_CHANGE_REQUESTED** | User starts checkout/upgrade (`POST /api/billing/checkout`, `POST /api/intake/checkout`). |
| **PLAN_LIMIT_EXCEEDED** | Property create / bulk create when at plan cap. |

---

## Intake rule (reminder)

During intake, **property cap enforcement must return the user to plan selection (“Change plan”)**, not trigger Stripe upgrade mid-intake. Backend returns error (e.g. 400 with `plan_limit_exceeded` / `current_limit`) from `POST /api/intake/submit` and `GET/POST /api/intake/validate-property-count`; frontend must show “Change plan” and redirect to plan step, not open checkout.

---

## Feature audit vs Definition of Done (no “complete” without proof)

Per pricing-card feature, MVP must have: working UI entry point, working backend endpoint(s), real persistence, server-side FeatureKey enforcement (403 + PLAN_GATE_DENIED), and proof (allowed tier succeeds, blocked tier 403 + audit log).

### DOCUMENTS

| Feature | Backend gate | Persistence | Status / gap |
|---------|--------------|-------------|--------------|
| **document_upload_single** (DOCUMENT_UPLOAD_SINGLE) | No gate (all plans) | Documents stored, listed per property | Implemented; verify E2E. |
| **zip_upload** (DOCUMENT_UPLOAD_BULK_ZIP) | enforce_feature zip_upload on bulk-upload + zip-upload | ZIP extracted, docs stored; “Unsorted” / tag-to-property | Implemented; confirm “Unsorted” + tag flow exists. |

### REPORTING

| Feature | Backend gate | Persistence | Status / gap |
|---------|--------------|-------------|--------------|
| **reports_pdf** (PDF_REPORTS) | enforce_feature reports_pdf | PDF generated (template); metadata/streaming | Implemented; confirm file/metadata stored where required. |
| **reports_csv** (CSV_EXPORT) | enforce_feature reports_csv | CSV export real data | Implemented; confirm no fake data. |
| **scheduled_reports** (SCHEDULED_REPORTS) | enforce_feature scheduled_reports on create/list/delete/toggle | Schedule in DB; runner `run_scheduled_reports` | Implemented; confirm runner produces stored file + metadata. |

### AI

| Feature | Backend gate | Persistence | Status / gap |
|---------|--------------|-------------|--------------|
| **ai_extraction_basic** | No gate (all plans) | Extraction on document record | Implemented; verify doc type + expiry. |
| **ai_extraction_advanced** | 403 when return_advanced=True without entitlement | Stored on document | Implemented; verify materially more fields (e.g. confidence). |
| **ai_review_interface** | enforce_feature ai_review_interface on apply-extraction / reject-extraction | Accept updates canonical fields | Implemented; verify deterministic update. |

### COMMUNICATION

| Feature | Backend gate | Persistence | Status / gap |
|---------|--------------|-------------|--------------|
| **email_notifications** | All plans | message_logs | Implemented; verify at least one event-based email (e.g. expiring soon). |
| **sms_reminders** | Professional only in job | sms_logs (or unified MessageLog channel=sms) | Job gated; verify one real event-based SMS via Twilio and single logging path. |

### TENANT PORTAL

| Feature | Backend gate | Persistence | Status / gap |
|---------|--------------|-------------|--------------|
| **tenant_portal** (TENANT_PORTAL_ACCESS) | enforce_feature tenant_portal on invite/list/assign/unassign/revoke/resend | Tenant users + assignments; time-limited/revocable access | Implemented; verify tenant viewer limited to assigned property (token or login, no permanent public link). |

### AUDIT EXPORT

| Feature | Backend gate | Persistence | Status / gap |
|---------|--------------|-------------|--------------|
| **audit_log_export** (AUDIT_LOG_EXPORT) | enforce_feature audit_log_export on GET /api/reports/professional/audit-log | Downloadable PDF/CSV | Implemented; confirm server-side gate + downloadable. |

### CORE (verify only)

| Feature | Backend gate | Status |
|---------|--------------|--------|
| compliance_dashboard | All plans | GET /api/client/dashboard |
| compliance_score | All plans | GET /api/client/compliance-score (+ trend, explanation) |
| expiry_calendar / compliance_calendar | All plans | GET /api/calendar/* |
| score_trending | All plans | GET /api/client/compliance-score/trend |

---

## Proof required before marking “complete”

- **3 Stripe-backed test accounts** created via real checkout/provisioning: SOLO, PORTFOLIO, PROFESSIONAL.
- **For each previously missing/partial feature:**
  - Screenshot/video of **allowed tier success**.
  - **Blocked tier:** 403 response body (with upgrade_required / feature).
  - **AuditLog:** corresponding PLAN_GATE_DENIED (or equivalent) entry.
- **Commit and push** all doc/code changes.

Nothing may be marked “complete” until the above proof is provided and the endpoint→FeatureKey map (this document) is updated and stored in the repo.
