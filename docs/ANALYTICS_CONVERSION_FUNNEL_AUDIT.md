# Admin Analytics Dashboard (Conversion Funnel) — Audit

## Purpose

Check the codebase against the task requirements for an **admin Analytics dashboard** tracking conversion end-to-end (Checklist Lead → Paid → Provisioned → Activated → First Value). Identify what is implemented, what is missing, and any conflicts. **Do not implement** in this step.

---

## 1. Task Requirements (Summary)

| Area | Requirement |
|------|-------------|
| **NON-NEGOTIABLES** | Do NOT change provisioning rules (Stripe webhooks + runner only). Analytics must be passive: log events and aggregate; no business logic changes. |
| **Backend** | Collection `analytics_events` (ts, event, lead_id, client_id, customer_reference, email, source, plan_code, properties_count, stripe_session_id, stripe_subscription_id, metadata). Service: `log_event`, idempotency for key events (e.g. payment_succeeded by stripe event id), `first_doc_uploaded` once per client_id. |
| **Instrumentation** | lead_captured, intake_submitted, checkout_started, payment_succeeded (dedupe), provisioning_started/completed/failed, activation_email_sent / email_failed, password_set, doc_uploaded + first_doc_uploaded once. |
| **Admin API** | GET /overview (KPIs, conversion rates, median times, leads by source, failures), GET /funnel, GET /failures. Query params: from, to, source, plan. RBAC owner/admin. |
| **First Value (MVP)** | first_value = first_doc_uploaded (at least one document uploaded after activation). |
| **Frontend** | Route /admin/analytics. Filters (date, source, plan). KPI cards, funnel table, median time-to-complete, sources table, failures panel. No legal advice; operational analytics only. |
| **Tests** | payment_succeeded dedupe, overview aggregation from seeded events, admin RBAC enforced. |
| **Docs** | docs/ANALYTICS_DASHBOARD.md (metrics definitions, First Value). |

---

## 2. What Exists Today

### 2.1 Backend analytics (order/revenue, not event-based)

| Item | Location | Notes |
|------|----------|--------|
| **Analytics routes** | `backend/routes/analytics.py` | Prefix `/api/admin/analytics`. No `analytics_events` collection. |
| **Data source** | Same file | Uses `orders`, `intake_drafts`, `clients`, `leads` collections directly (aggregations and counts), not an event log. |
| **Endpoints** | `GET /summary`, `/revenue/daily`, `/services`, `/sla-performance`, `/customers`, `/conversion-funnel`, `/addons`, `/v2/summary`, `/v2/trends`, `/v2/breakdown` | Contract: `period` (e.g. 30d), optional custom `start_date`/`end_date`. No `from`/`to`/`source`/`plan` as in task. |
| **Conversion funnel (current)** | `analytics.py` ~356–305 | Stages: "Drafts Created" → "Payment Started" (converted drafts) → "Payment Completed" (paid orders) → "Order Completed". **Not** Lead → Intake → Checkout → Paid → Provisioned → Activated → First Value. |
| **Auth** | `admin_route_guard` on all analytics routes | No explicit `require_owner_or_admin`; guard allows admin/owner by default. Task asks RBAC owner/admin — current guard is sufficient if it restricts to admin roles. |

### 2.2 Frontend

| Item | Location | Notes |
|------|----------|--------|
| **Admin Analytics** | `frontend/src/pages/AdminAnalyticsDashboard.js` | Route `/admin/analytics` (in App.js ~388). Nav: UnifiedAdminLayout → Analytics (BarChart3). |
| **UI** | Same file | Period selector (today, 7d, 30d, 90d, ytd, all), custom date range, compare toggle. StatCards: Revenue, Paid Orders, AOV, New Clients, Leads. Revenue breakdown by dimension (service, status, day, hour). Service performance, **Conversion Funnel** (draft-based), SLA, add-ons, customers, order status breakdown. |
| **Gaps vs task** | — | No source/plan filters. No KPI row: Leads Captured, Intakes Submitted, Checkout Started, Payments Succeeded, Provisioned, Activation Email Sent, Password Set, First Value. No funnel by event stages. No median time-to-complete. No “Leads by source” table. No Failures panel (checkout_failed, email_failed, provisioning_failed). No tabs Overview / Funnel / Speed / Sources / Failures. |

### 2.3 Collections and services

| Item | Status |
|------|--------|
| **analytics_events** | ❌ Not present. No code inserts into this collection. |
| **analytics_service.py** | ❌ Not present. No `log_event` or idempotency/dedupe layer. |
| **docs/ANALYTICS_DASHBOARD.md** | ❌ Not present. |

### 2.4 Tests

| Item | Location | Notes |
|------|----------|--------|
| **Analytics API tests** | `backend/tests/test_analytics_schema_features.py` | Tests existing endpoints: summary, services, conversion-funnel, sla-performance, customers, addons; 401 without auth. **No** tests for analytics_events, payment_succeeded dedupe, or new overview/funnel/failures. |

---

## 3. Instrumentation Points (File:Line References)

Task requires logging at these points. **None of these currently call any analytics event logger** (no such logger exists).

| Event | Where to log | File:Line (approximate) |
|-------|----------------|--------------------------|
| **lead_captured** | After successful `create_lead` (all capture endpoints). Include `source` = source_platform. | `backend/routes/leads.py`: after create_lead in each of: capture_chatbot_lead ~136, capture_contact_form_lead ~179, capture_compliance_checklist_lead ~222, capture_document_service_lead ~258, capture_whatsapp_lead ~302. |
| **intake_submitted** | After client + properties created in submit_intake. Include plan_code, properties_count, lead_id if linked, client_id. | `backend/routes/intake.py`: submit_intake ~620; after client insert (client_id and customer_reference available). Need to resolve lead_id from email if desired. |
| **checkout_started** | When Stripe checkout session is created and returned to client. Include stripe_session_id, client_id. | `backend/routes/intake.py`: create_checkout ~1049 (CVP intake flow); after session created, before return. Also `backend/services/stripe_service.py` create_checkout_session ~36 (used by intake and others); or `backend/routes/intake_wizard.py` create_checkout_session call ~492. Prefer single point: intake create_checkout and stripe_service both possible; intake has client_id in path. |
| **payment_succeeded** | After successful handling of checkout.session.completed or invoice.paid. **Dedupe by stripe event id** (idempotency). Include subscription_id. | `backend/services/stripe_webhook_service.py`: _handle_checkout_completed ~225 and/or _handle_subscription_checkout ~335; after DB updates, before return. Also _handle_invoice_paid ~930. Must use event["id"] as dedupe key. |
| **provisioning_started** | When runner begins processing a job. | `backend/services/provisioning_runner.py`: _run_provisioning_job_locked ~149; when status set to PROVISIONING_STARTED (~213). |
| **provisioning_completed** | When job reaches PROVISIONING_COMPLETED. | Same file: when status set to PROVISIONING_COMPLETED (~247). |
| **provisioning_failed** | When job fails (status FAILED). | Same file: in except path that sets status to FAILED and last_error. |
| **activation_email_sent** | When WELCOME_EMAIL send succeeds. | `backend/services/notification_orchestrator.py`: after successful send in _send_email (or in provisioning_runner/provisioning when they call _send_password_setup_link and get success). Orchestrator is single place for “sent”; provisioning_runner ~166, ~271. |
| **email_failed** | When send fails (exception or outcome failed/blocked). | Same: in orchestrator _send_email exception path and/or when result.outcome not in (sent, duplicate_ignored). |
| **password_set** | After successful password set via token. | `backend/routes/auth.py`: set_password ~182; after portal_users update and token invalidation, before return 200. |
| **doc_uploaded** | On every successful document upload (client or admin). | `backend/routes/documents.py`: upload_document ~681 (POST /upload) after insert; admin_upload_document ~806 after insert. Bulk/zip uploads: bulk_upload_documents ~188, upload_zip_archive ~379 — optional to log per-doc or once per batch. |
| **first_doc_uploaded** | Once per client_id: only if no prior analytics_events event first_doc_uploaded for that client_id. | Same upload paths; call analytics_service helper that checks before insert. |

Failure events (for failures panel):

| Event | Where to log |
|-------|----------------|
| **checkout_failed** | When checkout session creation fails or webhook returns error; store error_code, request_id in metadata. e.g. `routes/intake.py` create_checkout except; stripe webhook handler on failure path. |
| **email_failed** | See above (activation_email_sent failure path). |
| **provisioning_failed** | See provisioning_runner status FAILED path; store status + reason in metadata. |

---

## 4. Conflicts and Design Choices

### 4.1 Existing funnel vs new funnel

- **Current:** Conversion funnel is draft-based (Drafts Created → Payment Started → Payment Completed → Order Completed) and is used by the existing dashboard.
- **Task:** Funnel is event-based: Lead Captured → Intake Submitted → Checkout Started → Paid → Provisioned → Activation Email Sent → Password Set → First Value.
- **Conflict:** Different definitions and data sources.
- **Recommendation:** **Add** new endpoints and event-based logic **without removing** existing analytics. Keep `/conversion-funnel` and existing summary for order/revenue; add new `/overview`, `/funnel`, `/failures` that read from `analytics_events`. Frontend can show a new “Conversion funnel (lead to first value)” section or tab that uses the new API; existing “Conversion Funnel” can remain as “Order funnel” or be renamed for clarity.

### 4.2 CVP vs document-pack intake

- CVP subscription flow: `intake.py` submit_intake (creates client) → create_checkout (intake or intake_wizard) → Stripe checkout.session.completed → provisioning job.
- Document packs / other intakes may use different paths (e.g. intake_wizard create_checkout_session, orders).
- **Recommendation:** Instrument all paths that create checkout sessions and that trigger provisioning. At minimum: (1) lead capture (all sources), (2) intake submit_intake (intake.py), (3) create_checkout in intake.py and/or stripe_service, (4) Stripe webhook checkout.session.completed + invoice.paid, (5) provisioning_runner start/complete/fail, (6) activation email send/fail, (7) auth set_password, (8) documents upload + first_doc_uploaded. If intake_wizard is the main CVP path, ensure both intake.py and intake_wizard checkout creation are covered so “checkout_started” is not missed.

### 4.3 First Value definition

- Task (MVP): First Value = at least one document uploaded to a property (first_doc_uploaded).
- Optional extensions (report generated, dashboard view) can be added later.
- **Recommendation:** Implement MVP only: first_value = existence of event first_doc_uploaded for client_id. No change to provisioning or business logic.

### 4.4 RBAC

- Task: “RBAC owner/admin”.
- Current analytics routes use `admin_route_guard` only. Other admin routes sometimes use `require_owner_or_admin` for sensitive actions.
- **Recommendation:** Use the same pattern as other admin analytics: keep `admin_route_guard`. If the project explicitly restricts analytics to owner/admin, add `dependencies=[Depends(require_owner_or_admin)]` to the new analytics endpoints.

---

## 5. What Is Missing (Checklist)

| # | Item | Status |
|---|------|--------|
| 1 | Collection `analytics_events` with schema (ts, event, lead_id, client_id, customer_reference, email, source, plan_code, properties_count, stripe_session_id, stripe_subscription_id, metadata) | ❌ |
| 2 | `backend/services/analytics_service.py`: log_event(event_name, payload), idempotency for payment_succeeded (e.g. stripe_event_id), helper for first_doc_uploaded (once per client_id) | ❌ |
| 3 | Instrumentation: lead_captured (leads.py), intake_submitted (intake.py), checkout_started (intake/intake_wizard/stripe_service), payment_succeeded (stripe_webhook_service, dedupe), provisioning_started/completed/failed (provisioning_runner), activation_email_sent/email_failed (orchestrator/provisioning), password_set (auth.py), doc_uploaded + first_doc_uploaded (documents.py) | ❌ |
| 4 | Failure events: checkout_failed, email_failed, provisioning_failed with error_code/request_id/metadata | ❌ |
| 5 | GET /api/admin/analytics/overview?from=&to=&source=&plan= (KPIs, conversion rates, median times, leads by source, failures counts) | ❌ |
| 6 | GET /api/admin/analytics/funnel?from=&to=&source=&plan= (stage counts, step conversion, drop-off) | ❌ |
| 7 | GET /api/admin/analytics/failures?from=&to=&type=checkout\|email\|provisioning (recent failures with request_id/stripe ids, metadata) | ❌ |
| 8 | First Value computed as “any analytics_events event first_doc_uploaded for client_id” | ❌ |
| 9 | Frontend: filters (date range, source, plan), KPI cards row (leads, intake_submitted, checkout_started, paid, provisioned, activation_email_sent, password_set, first_value), funnel table, median time row, sources table, failures panel; optional tabs Overview / Funnel / Speed / Sources / Failures | ❌ |
| 10 | Backend tests: payment_succeeded dedupe on repeated webhook; overview aggregation from seeded analytics_events; admin RBAC (401 without auth / 403 if role not owner/admin if applied) | ❌ |
| 11 | docs/ANALYTICS_DASHBOARD.md (metrics definitions, First Value) | ❌ |

---

## 6. File Touch List (When Implementing)

- **New:** `backend/services/analytics_service.py`, `docs/ANALYTICS_DASHBOARD.md`.
- **New collection:** `analytics_events` (create index on event, ts, client_id, lead_id, idempotency key if used).
- **Backend instrumentation:** `routes/leads.py` (multiple capture endpoints), `routes/intake.py` (submit_intake, create_checkout), `services/stripe_webhook_service.py` (checkout completed, invoice.paid), `services/provisioning_runner.py` (start/complete/fail), `services/notification_orchestrator.py` or provisioning (activation send/fail), `routes/auth.py` (set_password), `routes/documents.py` (upload_document, admin_upload_document; first_doc_uploaded helper).
- **Backend API:** `routes/analytics.py` (add GET /overview, /funnel, /failures with from/to/source/plan; optional require_owner_or_admin).
- **Frontend:** `frontend/src/pages/AdminAnalyticsDashboard.js` (or new component/tabs): filters, KPI cards from overview, funnel from /funnel, median times, sources table, failures panel; call new endpoints.
- **Tests:** New or extend `backend/tests/test_analytics_schema_features.py` (or new test file): dedupe, overview aggregation, RBAC.

---

## 7. Summary

| Area | Implemented | Action |
|------|-------------|--------|
| analytics_events collection | ❌ | Add collection + indexes; schema as specified. |
| analytics_service.py | ❌ | Add service with log_event, idempotency for payment_succeeded, first_doc_uploaded once per client. |
| Event instrumentation | ❌ | Add log_event calls at all listed file:line points; no change to business logic. |
| GET /overview, /funnel, /failures | ❌ | Add endpoints; query analytics_events; support from, to, source, plan. |
| First Value | ❌ | Define as presence of first_doc_uploaded for client_id in analytics_events. |
| Frontend funnel / KPIs / failures | ❌ | Add or extend dashboard: filters, KPI row, funnel table, median times, sources, failures. |
| Tests | Partial | Existing tests cover current endpoints; add tests for dedupe, overview, RBAC. |
| docs/ANALYTICS_DASHBOARD.md | ❌ | Add doc with metrics definitions and First Value. |
| Existing analytics | ✅ | Keep; do not remove or replace existing order/revenue funnel and summary. |

No conflicting instructions that block implementation. Safest approach: add `analytics_events` and `analytics_service`, instrument existing flows passively, add new admin endpoints and UI sections that read from events, and keep all current analytics behavior unchanged.
