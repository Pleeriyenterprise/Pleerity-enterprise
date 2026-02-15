# Full System Capability Audit vs Pricing Page

**Reference:** Pricing page screenshot (Solo / Portfolio / Professional).  
**Audit method:** Code and endpoint tracing only; no guessing.

---

## 1. Feature audit table

| Feature | Exists? | Fully working? | Endpoint(s) | Gated? | Notes |
|--------|---------|-----------------|-------------|--------|------|
| **CORE** | | | | | |
| Compliance Dashboard | Yes | Yes | `GET /api/client/dashboard` | No (all plans) | Returns client, properties, compliance_summary. Auth: client_route_guard. |
| Compliance Score | Yes | Yes | `GET /api/client/compliance-score`, `/compliance-score/trend`, `/compliance-score/explanation` | No | `services/compliance_score.py`, `compliance_trending.py`. Try/except, 500 on error. |
| Expiry Calendar | Yes | Yes | `GET /api/calendar/expiries`, `GET /api/calendar/export/ical`, `GET /api/calendar/subscription-url` | Yes | Gated by `compliance_calendar` (all plans have it). calendar.py. |
| Email Notifications | Yes | Yes | N/A (background) | N/A | Daily/monthly reminders and compliance check use `email_service` (Postmark). Jobs respect entitlement ENABLED only. |
| Document Upload | Yes | Yes | `POST /api/documents/upload` | No | Single-file upload; all plans. No plan check. properties.py + documents.py. |
| Score Trending | Yes | Yes | `GET /api/client/compliance-score/trend`, `/compliance-score/explanation` | No | compliance_trending; 90-day cap, 30-day explanation cap. |
| **AI** | | | | | |
| Basic AI Extraction | Yes | Yes | `POST /api/documents/{id}/analyze` (behavior by plan) | Implicit | Same endpoint; Solo gets basic fields only (no confidence); Portfolio+ get advanced payload. documents.py L1113–1172. |
| Advanced AI Extraction | Yes | Yes | Same | Implicit | Plan controls response shape (confidence, review_ui_available). No separate require_feature on endpoint. |
| AI Review Interface | Yes | Yes | Same + apply flow | Implicit | “review_ui_available” and “auto_apply_enabled” by plan. No explicit require_feature("extraction_review_ui"). |
| **DOCUMENTS** | | | | | |
| ZIP Bulk Upload | Yes | Yes | `POST /api/documents/zip-upload`, `POST /api/documents/bulk-upload` | Yes | zip_upload: require_feature + enforce_feature. PLAN_2+ in code. |
| **REPORTING** | | | | | |
| PDF Reports | Yes | Yes | `GET /api/reports/compliance-summary?format=pdf`, `/requirements?format=pdf`, `GET /api/reports/professional/compliance-summary`, `/professional/expiry-schedule` | Yes | reports_pdf enforced (reports.py, professional_reports). |
| CSV Export | Yes | Yes | `GET /api/reports/compliance-summary?format=csv`, `/requirements?format=csv` | Yes | reports_csv enforced. |
| Scheduled Reports | Yes | Yes | `POST /api/reports/schedules`, job `run_scheduled_reports` (hourly) | Partial | Create schedule gated (scheduled_reports). **GET /api/reports/schedules and DELETE /api/reports/schedules/{id} are NOT gated** – Solo can call. |
| **COMMUNICATION** | | | | | |
| SMS Reminders | Partial | Partial | Admin test: `POST /api/admin/billing/message` (checks sms_reminders) | Admin path only | Twilio in sms_service.py. **Daily reminder job sends email only** (_send_reminder_email); no SMS in reminder pipeline. Plan flag exists; client-facing SMS reminder flow not implemented. |
| **TENANT PORTAL** | | | | | |
| Tenant View Access | Yes | Yes | `POST /api/client/tenants/invite`, `GET /api/client/tenants`, assign/unassign, resend | Yes | tenant_portal enforced on all tenant routes (client.py). |
| **INTEGRATIONS** | | | | | |
| Webhooks | Yes | Yes | `GET/POST/PATCH/DELETE /api/webhooks`, test, enable, disable, regenerate-secret | Yes | webhooks enforce_feature (webhooks_config.py). Pro only in code. |
| API Access | Plan only | N/A | No client-facing API-key or public API | N/A | api_access in plan_registry (Pro only). No dedicated API key or external API endpoints found; flag only. |
| **ADVANCED** | | | | | |
| White-Label Reports | Yes | Yes | `GET/PUT/POST /api/client/branding`, `GET /api/client/branding/reset` | Yes | white_label_reports enforced. **Code gives Pro ✅; pricing page shows ❌ for all** – mismatch. |
| Audit Log Export | Yes | Yes | `GET /api/reports/professional/audit-log` (PDF) | Yes | audit_log_export enforced. Pro only. |

---

## 2. Property caps

| Cap | Enforced? | Where | Audit on deny |
|-----|-----------|--------|----------------|
| SOLO: 2 | Yes | properties.py create + bulk; intake submit (check_property_limit) | PLAN_LIMIT_EXCEEDED |
| PORTFOLIO: 10 | Yes | Same | Same |
| PROFESSIONAL: 25 | Yes | Same | Same |

Source: plan_registry.get_property_limit(plan_code) → 2, 10, 25.

---

## 3. Stripe / plan gating vs pricing page

- **Source of truth:** Plan and subscription status are updated **only** in Stripe webhook handlers (checkout.session.completed, customer.subscription.*, invoice.paid/payment_failed). Idempotency via stripe_events. No local plan change on “Upgrade” click; checkout/portal only.
- **Matrix mismatch (code vs pricing page):**
  - **Pricing:** Advanced AI, AI Review, CSV Export, SMS, Tenant Portal = **Pro only**. Webhooks = **Pro only**. API = **Pro only**. White-Label = **all ❌**.
  - **Code (plan_registry):** Portfolio has ai_extraction_advanced, extraction_review_ui, reports_csv, sms_reminders, tenant_portal. Pro has webhooks, api_access, white_label_reports, audit_log_export. So: **Portfolio in code has more than pricing (CSV, SMS, tenant portal, advanced AI); White-Label is Pro in code but pricing says none.**

---

## 4. Missing or partial implementations

| Item | Status |
|------|--------|
| **SMS Reminders** | Plan flag and admin test message only. Daily reminder job does not send SMS; email only. No client-triggered SMS reminder path. |
| **API Access** | No client-facing API key or public API; plan key exists only. |
| **GET /api/reports/schedules** | Not gated; should require scheduled_reports. |
| **DELETE /api/reports/schedules/{schedule_id}** | Not gated; should require scheduled_reports. |

---

## 5. Implemented but not on pricing page (or different)

- **multi_file_upload** – In code for all plans; pricing lists “Document Upload” (single). No conflict.
- **white_label_reports** – Code: Pro ✅. Pricing: ❌ for all plans.

---

## 6. Endpoints requiring stricter or added gating

| Endpoint | Current | Required |
|----------|---------|----------|
| `GET /api/reports/schedules` | No plan check | Gate with scheduled_reports (Portfolio+). |
| `DELETE /api/reports/schedules/{schedule_id}` | No plan check | Gate with scheduled_reports. |
| `POST /api/documents/{id}/analyze` | Plan used only for response shape | If pricing is Pro-only for Advanced AI: add explicit deny for non-Pro (403 + PLAN_GATE_DENIED) when requesting advanced/review; or keep current (Portfolio+ get advanced in code). |

---

## 7. Background job architecture

- **Runner:** `job_runner.py` defines one async function per job (e.g. run_daily_reminders, run_scheduled_reports). `JOB_RUNNERS` maps scheduler id → function.
- **Scheduler:** `server.py` adds jobs with `scheduler.add_job(run_*, CronTrigger(...), id="...", replace_existing=True)`. Each job has a distinct id (e.g. daily_reminders, scheduled_reports, compliance_check_morning).
- **Manual run:** `POST /api/admin/jobs/run` with body `{ "job": "<id>" }` calls `JOB_RUNNERS[job_id]()`. Response is `{ "success", "job", "message" }` – **one message per job** (suitable for one toast per run).
- **Execution:** Each runner runs independently; no single “run all” for these. Jobs iterate clients/context internally (e.g. send_daily_reminders loops clients with ENABLED entitlement).
- **Conclusion:** Jobs are triggered individually; unique toast per job; no unintended global “run everything” in one call.

---

## 8. Email / SMS correspondence architecture

| Aspect | Email | SMS |
|--------|--------|-----|
| **Provider** | Postmark (`postmarker.core.PostmarkClient`). `POSTMARK_SERVER_TOKEN`, `EMAIL_SENDER`. | Twilio (`twilio.rest.Client`). `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`, optional `TWILIO_VERIFY_SERVICE_SID`. |
| **Config** | email_service.py; dev mode logs only if token unset. | sms_service.py; `SMS_ENABLED` env; is_enabled() = SMS_ENABLED and is_configured(). |
| **Logging** | MessageLog (DB); postmark_message_id, status, sent_at, error_message. | sms_logs collection: message_sid, to_number, status, client_id, created_at. |
| **Retry** | No explicit retry in email_service; caller can retry. Jobs log and continue on per-client failure. | No retry in sms_service.send_sms. |
| **Rate limiting** | Not implemented in code (Postmark account limits apply). | Not implemented in code. |
| **Templates** | Database email_templates (alias, html_body, text_body, subject) + placeholder replacement; fallback built-in in email_service. | No template system; raw message string. |

---

## 9. Clear statement

**System is not fully aligned with the pricing page.** Gaps:

1. **Matrix alignment:** Code gives Portfolio more than the pricing page (CSV export, SMS reminders, Tenant portal, Advanced AI + AI Review). Pricing page restricts these to Professional. White-Label is Pro in code but pricing shows ❌ for all.
2. **SMS Reminders:** Promised for Pro; only plan flag and admin test message exist. Daily reminder job does not send SMS.
3. **API Access:** Promised for Pro; no client API key or public API implementation, only plan flag.
4. **Scheduled reports:** Create is gated; list and delete schedules are not – Solo can call list/delete (should 403).
5. **Advanced AI / Review:** Enforced only via response shape (same endpoint); no explicit 403 for non-Pro if you align to “Pro only” for advanced/review.

---

## 10. Proposed implementation plan (audit-first; no changes yet)

1. **Align plan_registry FEATURE_MATRIX (and MINIMUM_PLAN_FOR_FEATURE) with pricing page:**  
   - CSV, SMS, Tenant portal, Advanced AI, AI Review → Pro only.  
   - Webhooks, API Access → Pro only (already).  
   - White-Label → all ❌ (disable for Pro in matrix).

2. **Gate scheduled-report list/delete:**  
   - Add enforce_feature(user["client_id"], "scheduled_reports") to GET /api/reports/schedules and DELETE /api/reports/schedules/{schedule_id}. Return 403 with PLAN_GATE_DENIED when not entitled.

3. **SMS Reminders (product decision):**  
   - Either implement SMS in daily reminder job (when client has sms_reminders and SMS enabled + configured), or document “SMS Reminders” as coming soon and keep email-only reminders.

4. **API Access:**  
   - Either add a client API key flow and document it, or keep as “plan flag only” and document that external API is roadmap.

5. **Optional:** Add explicit require_feature("ai_extraction_advanced") or equivalent on a dedicated “advanced analyze” path if you want Pro-only advanced extraction with a clear 403; otherwise keep single endpoint with response shape by plan.

6. **Runbook / tests:** Update STRIPE_GATED_TEST_ACCOUNTS_RUNBOOK and any plan-gating tests to use the new matrix; re-verify SOLO/PORTFOLIO/PRO behavior and property caps.

No code changes have been made in this audit; the above is the proposed plan after the audit.
