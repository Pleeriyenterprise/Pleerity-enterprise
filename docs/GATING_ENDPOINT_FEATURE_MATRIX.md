# Gating: Endpoints and Feature Keys (Pricing Page Aligned)

**Source of truth:** `backend/services/plan_registry.py` (FEATURE_MATRIX + MINIMUM_PLAN_FOR_FEATURE).  
Stripe webhooks are the only updater of `billing_plan`, `subscription_status`, `entitlements_version`.

---

## Tiers (authoritative)

- **SOLO (cap 2):** Core + Basic AI only.
- **PORTFOLIO (cap 10):** SOLO + `document_upload_bulk_zip` (zip_upload), `reports_pdf`, `scheduled_reports`.
- **PROFESSIONAL (cap 25):** PORTFOLIO + `ai_extraction_advanced`, `ai_review_interface`, `reports_csv`, `sms_reminders`, `tenant_portal_access` (tenant_portal), `webhooks`, `white_label_reports`, `audit_log_export`.

**API Access:** Removed (not implemented). No feature key, no UI, no routes.

---

## Endpoints and feature key

| Endpoint(s) | Feature key | Notes |
|-------------|-------------|--------|
| `POST /api/documents/bulk-upload`, `POST /api/documents/zip-upload` | zip_upload / document_upload_bulk_zip | require_feature / enforce_feature |
| `GET /api/reports/compliance-summary` (format=pdf) | reports_pdf | enforce_feature |
| `GET /api/reports/compliance-summary` (format=csv) | reports_csv | enforce_feature |
| `GET /api/reports/requirements` (pdf/csv) | reports_pdf / reports_csv | enforce_feature |
| `POST /api/reports/schedules` | scheduled_reports | enforce_feature |
| `GET /api/reports/schedules` | scheduled_reports | enforce_feature (added) |
| `DELETE /api/reports/schedules/{id}` | scheduled_reports | enforce_feature (added) |
| `GET /api/reports/professional/*` (PDFs) | reports_pdf | enforce_feature |
| `GET /api/reports/professional/audit-log` | audit_log_export | enforce_feature |
| `POST /api/documents/analyze/{id}` with return_advanced=True | ai_extraction_advanced | 403 + PLAN_GATE_DENIED if not entitled |
| `POST /api/documents/{id}/apply-extraction` | ai_review_interface | enforce_feature, 403 if not Pro |
| `GET/POST/PATCH/DELETE /api/webhooks*` | webhooks | enforce_feature |
| `GET/PUT/POST /api/client/branding*` | white_label_reports | enforce_feature |
| `POST /api/client/tenants/invite`, `GET /api/client/tenants`, assign/unassign, resend | tenant_portal / tenant_portal_access | enforce_feature |
| `GET /api/calendar/export/ical`, `GET /api/calendar/subscription-url` | compliance_calendar | enforce_feature (all plans) |

---

## Audit events

- **PLAN_GATE_DENIED:** feature_key, endpoint, method, reason, client_id (middleware + reports + documents).
- **PLAN_UPDATED_FROM_STRIPE:** webhook handler (checkout + subscription change).
- **STRIPE_EVENT_PROCESSED:** same.
- **PLAN_CHANGE_REQUESTED:** when user starts checkout/upgrade (`POST /api/billing/checkout`, intake `POST /api/intake/checkout`).
- **PLAN_LIMIT_EXCEEDED:** property create / bulk create when at plan cap.

---

## SMS reminders (Professional only)

- **Daily reminder job:** After sending email, if `enforce_feature(client_id, "sms_reminders")` passes and notification_preferences.sms_enabled + sms_phone_number and Twilio configured, sends one SMS per client per day (throttled via sms_logs). Failures are per-client and do not crash the job.
- **Logging:** sms_service writes to `sms_logs`; job logs warnings on send failure.
