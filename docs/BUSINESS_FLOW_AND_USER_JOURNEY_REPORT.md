# Compliance Vault Pro — Business Flow & Full User Journey Report

**Document purpose:** End-to-end description of the business flow from intake (including intake fields), provisioning, through to final delivery; features and services; what triggers what; and hosting.

**Audience:** Product, operations, and technical stakeholders.

---

## Table of Contents

1. [What the Business Is About](#1-what-the-business-is-about)
2. [Full User Journey (High Level)](#2-full-user-journey-high-level)
3. [Intake Flow in Detail](#3-intake-flow-in-detail)
4. [Provisioning Flow](#4-provisioning-flow)
5. [Final Delivery (Orders & Reports)](#5-final-delivery-orders--reports)
6. [Features & Services (What Exists)](#6-features--services-what-exists)
7. [What Triggers What](#7-what-triggers-what-triggers--dependencies)
8. [Background Jobs (Scheduled)](#8-background-jobs-scheduled)
9. [Hosting & Deployment](#9-hosting--deployment)
10. [Summary Diagram](#10-summary-diagram-flow)
11. [Key Database Collections](#11-key-database-collections)
12. [Related Documentation](#12-related-documentation)

---

## 1. What the Business Is About

**Compliance Vault Pro (CVP)** is a SaaS platform for **UK landlords, letting agents, and property companies** to:

- **Track compliance** across property portfolios (gas safety, EICR, EPC, licences, etc.).
- **Store and manage documents** (certificates, evidence) with optional AI extraction and confirmation.
- **Receive reminders and digests** (email/SMS) for expiring or overdue requirements.
- **View compliance scores and risk levels** (property- and portfolio-level), with score change history and audit.
- **Order professional services** (e.g. document packs, reports) with workflow states and final delivery (email/postal).
- **Generate reports** (PDF/CSV/Excel), including scheduled report delivery.

**Primary conversion funnel:** Public site → **Risk Check** (`/risk-check`) → **Intake** → **Stripe Checkout** → **Provisioning** → **Client Portal**. The main CTA across marketing is `/risk-check`.

---

## 2. Full User Journey (High Level)

| Stage | Description | Key endpoints / routes |
|-------|-------------|------------------------|
| **1. Discovery** | User lands on marketing site (Homepage, CVP page, FAQ, etc.). | `/`, `/compliance-vault-pro`, `/risk-check` |
| **2. Risk Check (pre-intake)** | User enters property count, HMO flag; gets risk band + report; can submit email for full report and “Activate Monitoring” (CTA to intake with plan + lead_id). | `POST /api/risk-check/preview`, `POST /api/risk-check/report`, `POST /api/risk-check/activate`; frontend: `/risk-check` |
| **3. Intake** | 5-step wizard: Your Details, Select Plan, Properties, Preferences, Review. Optional document uploads (staged). Submit creates **client + properties** (no entitlement yet). | `POST /api/intake/submit`; frontend: `/intake/start` |
| **4. Checkout** | Frontend calls create-checkout; user redirects to Stripe. Payment completes → Stripe sends `checkout.session.completed` webhook. | `POST /api/intake/checkout?client_id=...`; Stripe hosted page |
| **5. Post-payment (Stripe webhook)** | Backend sets subscription_status, billing_plan, entitlement_status; creates **provisioning job** (and optionally runs it in-process). | `POST /api/webhooks/stripe`; `stripe_webhook_service` |
| **6. Provisioning** | Job runner/poller: generate requirements per property, enqueue compliance recalc, create portal user, migrate intake uploads to vault, send **password-setup email**. Client status → `PROVISIONED`. | `provisioning_service.provision_client_portal_core` (+ migrate + invite); `provisioning_runner` / poller |
| **7. Password setup & first login** | User clicks link in email (token, 60 min, single-use), sets password, is redirected to portal. | `GET /api/portal/set-password?token=...`; frontend `/set-password`; then login |
| **8. Client portal (ongoing)** | Dashboard (score, trend, portfolio), Properties, Requirements, Documents, Calendar, Reports, Audit & Change History, Billing, Settings. | `/app/dashboard`, `/app/properties`, `/app/documents`, `/app/audit-log`, etc. |
| **9. Final delivery (orders)** | Orders in state **FINALISING** with approved document version are processed by **order_delivery_processing** job: send delivery email with document links, transition to **COMPLETED** (or DELIVERY_FAILED). Optional postal delivery for printed copies. | `order_delivery_service.process_finalising_orders`; `POST /api/admin/orders/{id}/deliver` (manual); client: order status + download links |

---

## 3. Intake Flow in Detail

### 3.1 Intake steps (frontend)

| Step | Name | Content |
|------|------|--------|
| 1 | Your Details | Full name, email, phone, company name (if company/agent), client type, preferred contact (Email/SMS/Both), consents (data processing, service boundary, email upload if method=EMAIL). |
| 2 | Select Plan | Billing plan: Solo (2 props), Portfolio (10), Pro (25). Plan limits enforced in UI and at submit. |
| 3 | Properties | Add properties up to plan cap. Per-property fields below. Upgrade prompt only changes selected plan (no entitlement until payment). |
| 4 | Preferences | Document submission method (Upload here / Email later); optional staged uploads (stored by intake_session_id). |
| 5 | Review | Summary: your details, plan, property count and list, preferences, staged upload filenames. Then “Proceed to Payment” → submit → create checkout → redirect to Stripe. |

### 3.2 Intake fields (stored on client)

- **Client:** `full_name`, `email`, `phone`, `company_name`, `client_type`, `preferred_contact`, `billing_plan`, `document_submission_method`, `email_upload_consent`, `intake_session_id`, `consent_data_processing`, `consent_service_boundary`, `customer_reference` (CRN assigned at submit). Optional: `marketing.lead_id`, `marketing.source` (e.g. risk-check).

### 3.3 Intake fields (stored per property)

- **Address:** `address_line_1`, `address_line_2`, `city`, `postcode`, `council_name` / `council_code` (normalized to `local_authority`).
- **Property attributes:** `property_type` (House, Flat, Bungalow, etc.), `bedrooms`, `occupancy` (Single Family, Multi Family, Student Let, etc.), `is_hmo`, `has_gas_supply` (default true).
- **Licence:** `licence_required` (Yes/No/Unsure), `licence_type` (Selective, Additional, Mandatory HMO), `licence_status` (Applied, Pending, etc.), `hmo_license_required` (derived from is_hmo + licence_required).
- **Certificates (declared):** `cert_gas_safety`, `cert_eicr`, `cert_epc`, `cert_licence` (Yes/No/Unsure). Drive **requirement applicability** (e.g. Gas Safety only if cert_gas_safety == "YES").
- **Reminders:** `managed_by`, `send_reminders_to`, `agent_name`, `agent_email`, `agent_phone`.

These fields are used by **requirement_catalog** and **compliance_scoring** (applicability and multipliers). Intake submit creates **client + properties**; **no entitlement or portal access** until payment and provisioning.

### 3.4 Intake API behaviour

- **Property limit:** Enforced at `POST /api/intake/submit` via `plan_registry.check_property_limit`. Over limit → **403** `PROPERTY_LIMIT_EXCEEDED`.
- **Checkout:** `POST /api/intake/checkout?client_id=...` creates Stripe session; returns `checkout_url`. Frontend redirects only if `checkout_url` present; handles `CHECKOUT_FAILED`, `CHECKOUT_URL_MISSING`.
- **Intake uploads:** Optional. Stored in `intake_uploads` by `intake_session_id`. After provisioning, **intake_upload_migration** copies CLEAN uploads into the document vault and links to client/properties.

### 3.5 Intake API endpoints (reference)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/api/intake/submit` | Submit completed 5-step wizard; creates client + properties (no entitlement). |
| `POST` | `/api/intake/checkout?client_id=...` | Create Stripe Checkout session; returns `checkout_url` for redirect. |
| `GET` | `/api/intake/onboarding-status/{client_id}` | Get onboarding progress (INTAKE_PENDING, PROVISIONING, PROVISIONED, FAILED). |
| `GET` | `/api/intake/councils` | Search UK councils (for property address). |
| `POST` | `/api/intake/upload-document` | Upload document during intake (staged; keyed by `intake_session_id`). |
| `GET` | `/api/intake/plans` | Get available billing plans with property limits. |
| `POST` | `/api/intake/validate-property-count` | Validate property count against plan limit before submit. |

---

## 4. Provisioning Flow

### 4.1 Trigger

- **Stripe** `checkout.session.completed` (mode=subscription) → webhook sets subscription/billing/entitlement and creates a **provisioning job** (`provisioning_jobs` collection) with `status=PAYMENT_CONFIRMED`, `needs_run=True`. Optionally the webhook starts provisioning in-process via `_run_provisioning_after_webhook(job_id)`; otherwise a **provisioning poller** (e.g. `run_provisioning_poller.py`) picks up jobs.

### 4.2 Provisioning steps (core)

1. **Client check:** Client exists; if already `onboarding_status == PROVISIONED`, return “Already provisioned”.
2. **Subscription (production):** If `ENVIRONMENT=production`, require `subscription_status == ACTIVE`.
3. **Status:** Set client `onboarding_status = PROVISIONING`, `provisioning_status = IN_PROGRESS`.
4. **Requirements:** For each property, `_generate_requirements(client_id, property_id)` — uses DB rules or fallback (e.g. gas_safety, eicr, epc, HMO rules, location rules).
5. **Property compliance:** `_update_property_compliance(property_id)` (legacy/backfill).
6. **Compliance recalc queue:** For each property, `enqueue_compliance_recalc(TRIGGER_PROVISIONING, ACTOR_SYSTEM)`. The **compliance_recalc_worker** job will run `recalculate_and_persist` and write score history + ledger.
7. **Portal user:** If no existing client-admin portal user, create one (`ROLE_CLIENT_ADMIN`, INVITED, password NOT_SET, must_set_password=True).
8. **Status:** Set client `onboarding_status = PROVISIONED`, `provisioning_status = COMPLETED`.
9. **Enablement:** Emit `PROVISIONING_COMPLETED` enablement event (if enabled).
10. **Post-core (full provisioning):** Migrate intake uploads to vault; send **password setup email** (link with token). Activation link uses `FRONTEND_PUBLIC_URL` / `PUBLIC_APP_URL`.

### 4.3 Onboarding status values

- **INTAKE_PENDING** — After intake submit; before payment (or payment not yet processed).
- **PROVISIONING** — Provisioning job running.
- **PROVISIONED** — Portal user created; client can set password and log in.
- **FAILED** — Provisioning failed (e.g. `_fail_provisioning`).

Portal access (middleware, routes) requires `onboarding_status == PROVISIONED`.

### 4.4 Provisioning poller (optional)

If the Stripe webhook does **not** run provisioning in-process, a separate process can poll for jobs:

- **Script:** `backend/scripts/run_provisioning_poller.py`
- **Behaviour:** Polls `provisioning_jobs` for `status=PAYMENT_CONFIRMED` and `needs_run=True`; runs `provision_client_portal` (core + migrate uploads + password-setup email) and marks job complete.
- **When to use:** When the webhook is configured to only create the job (e.g. to avoid long webhook response time); ensure exactly one poller instance runs (e.g. dedicated Render worker or cron).

---

## 5. Final Delivery (Orders & Reports)

### 5.1 Order delivery

- **Orders** have states (e.g. DRAFT → SUBMITTED → … → **FINALISING** → COMPLETED or DELIVERY_FAILED).
- **Order delivery processing** (scheduled job, every 5 min): finds orders in **FINALISING** with `version_locked`, `approved_document_version` set; for each, sends **delivery email** (document links) and transitions to **COMPLETED** (or DELIVERY_FAILED on send failure).
- **Manual:** Admin can trigger `POST /api/admin/orders/{order_id}/deliver` or batch `POST /api/admin/orders/batch/process-delivery`.
- **Postal:** Orders with `requires_postal_delivery` (e.g. printed copy add-on) have postal address and status; admin can record delivery.

### 5.2 Reports and scheduled delivery

- **Reports:** Client and admin can generate PDF/CSV/Excel (e.g. compliance summary, evidence readiness). **Scheduled reports** job runs periodically and sends reports by email (scheduled report delivery).
- **Digests:** **Monthly digest** and **pending verification digest** jobs send summary emails to clients.

---

## 6. Features & Services (What Exists)

### 6.1 Client-facing

- **Dashboard:** Compliance score (portfolio/property), risk level, score trend, portfolio summary, next actions.
- **Properties:** List/add/edit properties; property-level requirements and documents.
- **Requirements:** Requirement catalog driven by property attributes (from intake); status, due dates, evidence.
- **Documents:** Upload, AI extraction, confirm/reject; linked to requirements.
- **Calendar:** Requirement due dates and expiry view.
- **Reports:** Generate and download reports; scheduled report delivery (plan-dependent).
- **Audit & Change History:** Score History (ledger of score changes) + Activity Log (audit timeline).
- **Billing:** Plan, payment method, invoices (Stripe).
- **Orders:** Place and track orders (e.g. document packs); view delivery status and download links.

### 6.2 Admin

- **Dashboard:** System overview, clients by onboarding/subscription, recent activity.
- **Clients:** List, detail, edit, resend invite, provisioning status.
- **Properties & requirements:** Per-client property and requirement management.
- **Documents:** Pending verification, bulk actions.
- **Orders:** List, detail, approve, deliver, retry delivery, postal delivery status.
- **Observability:** System Health, Automation Control Centre (job runs, run now), Incidents (ack/resolve), score events/ledger.
- **Audit logs, email delivery (message_logs), leads (risk-check, checklist), analytics, billing, support (canned responses, knowledge base), prompts, reporting, CMS, etc.**

### 6.3 Public / marketing

- **Risk Check:** Preview, report, activate (CTA to intake with plan + lead_id).
- **Intake:** 5-step wizard; checkout redirect to Stripe.
- **Onboarding status:** `GET /api/intake/onboarding-status/{client_id}` for post-checkout status.

---

## 7. What Triggers What (Triggers & Dependencies)

### 7.1 Compliance score & ledger

- **Score recalculation** is done only via **recalculate_and_persist** (no route does its own scoring). It is invoked by the **compliance_recalc_worker** job, which processes the **compliance_recalc_queue**.
- **Enqueue recalc** is triggered by:
  - **Provisioning** (per property, TRIGGER_PROVISIONING).
  - **Document upload** (client or admin): TRIGGER_DOC_UPLOADED / TRIGGER_ADMIN_UPLOAD.
  - **Document delete:** TRIGGER_DOC_DELETED / TRIGGER_ADMIN_DELETE.
  - **Document status change:** TRIGGER_DOC_STATUS_CHANGED.
  - **AI confirm (certificate details):** TRIGGER_AI_APPLIED.
  - **Property create/update:** TRIGGER_PROPERTY_CREATED, TRIGGER_PROPERTY_UPDATED.
  - **Expiry rollover job:** TRIGGER_EXPIRY_JOB (daily job enqueues recalc for properties with due_date in window).
  - **Lazy backfill:** When `calculate_compliance_score` finds properties with no score, it enqueues TRIGGER_LAZY_BACKFILL.
- Each **recalculate_and_persist** updates property score, writes **property_compliance_score_history**, **score_change_log**, **score_ledger_events** (Audit & Change History), and audit log. **Admin “Validate compliance score” with Fix** also writes to **score_ledger_events**.

### 7.2 Notifications

- **Notification orchestrator** sends templates (e.g. daily reminder, monthly digest, subscription confirmed, order delivered) based on **message_templates**, **notification_preferences**, and **entitlements**. Blocked if client not PROVISIONED (unless template allows).
- **Postmark** is used for email; delivery/bounce/spam webhooks update **message_logs**.
- **In-app notifications** (e.g. incident created for admins) via enablement/in-app delivery.

### 7.3 Orders

- **Order creation:** Intake draft → Stripe payment (mode=payment, type=order_intake) → webhook converts draft to order and starts workflow.
- **Order delivery:** Scheduled job **order_delivery_processing** processes FINALISING orders; **ORDER_DELIVERED** template and transition to COMPLETED. Manual deliver/retry via admin API.

### 7.4 Risk-check funnel

- **Risk-check report** creates/updates **risk_leads** (email, lead_id, status, snapshot). **Activate** sets status to activated_cta and redirects to intake with plan + lead_id + from=risk-check.
- **Intake submit** links client to lead (marketing.lead_id, marketing.source); **checkout.session.completed** marks lead **converted** and can store **initial_risk_snapshot** on client.

---

## 8. Background Jobs (Scheduled)

All run via **APScheduler** (AsyncIOScheduler) with **MongoDB job store** (when configured). If scheduler fails to start, the API still runs without jobs.

| Job ID | Schedule | Purpose |
|--------|----------|--------|
| daily_reminders | 08:00 UTC | Send daily reminder emails (expiring/overdue). |
| pending_verification_digest | 09:00 UTC | Pending verification document digest. |
| monthly_digests | 1st, 10:00 UTC | Monthly compliance digest. |
| compliance_status_check | 18:00 UTC | Compliance status change alerts. |
| scheduled_reports | Every hour | Scheduled report generation and delivery. |
| compliance_score_snapshots | 02:00 UTC | Capture portfolio score snapshots (trend). |
| expiry_rollover_recalc | 00:10 UTC | Enqueue compliance recalc for expiry window. |
| compliance_recalc_worker | Every 15s | Process compliance_recalc_queue → recalculate_and_persist. |
| compliance_recalc_sla_monitor | Every 5 min | Monitor recalc queue SLA. |
| notification_failure_spike_monitor | Every 5 min | Monitor notification failure spikes. |
| sla_watchdog | Every 10 min | Job-run SLA (incidents if critical jobs miss window). |
| notification_retry_worker | Every minute | Retry deferred notifications. |
| order_delivery_processing | Every 5 min | Process FINALISING orders → deliver email, COMPLETED. |
| sla_monitoring | Every 15 min | Workflow SLA (e.g. WF9). |
| stuck_order_detection | Every 30 min | Detect stuck orders. |
| queued_order_processing | Every 10 min | Process queued orders. |
| abandoned_intake_detection | Every 15 min | Abandoned intake handling. |
| lead_followup_processing | Every 15 min | Lead follow-up. |
| pending_payment_lifecycle | 03:00 UTC | Abandoned/archived payment lifecycle. |
| lead_sla_check | Hourly | Lead SLA breach. |
| checklist_nurture_processing | 09:00 UTC | Checklist lead nurture. |
| risk_lead_nurture_processing | 09:15 UTC | Risk-check lead nurture (steps 2–5). |

**Provisioning** is triggered by Stripe webhook (in-process or via separate **provisioning poller** script), not by the main scheduler.

---

## 9. Hosting & Deployment

### 9.1 Stack

- **Frontend:** React (Create React App); built and served as static assets.
- **Backend:** FastAPI (Python), async; single process (recommended one worker for scheduler).
- **Database:** MongoDB (e.g. **MongoDB Atlas**).
- **Payments:** Stripe (test/live via key prefix).
- **Email:** Postmark (transactional + webhooks for delivery/bounce).

### 9.2 Hosting (as per README and docs)

- **Frontend:** **Vercel** (CI/CD from repo; env vars at build time, e.g. `REACT_APP_BACKEND_URL`).
- **Backend:** **Render** (service runs the FastAPI app; env vars in Render dashboard; scheduler runs in the same process).
- **Database:** **MongoDB Atlas** (connection string via `MONGO_URL`, `DB_NAME`).

### 9.3 Important environment variables

**Backend (Render / .env):**

- `MONGO_URL`, `DB_NAME` — MongoDB.
- `STRIPE_SECRET_KEY` or `STRIPE_API_KEY` — Stripe secret key.
- `STRIPE_WEBHOOK_SECRET` (or `STRIPE_WEBHOOK_SECRET_TEST` / `STRIPE_WEBHOOK_SECRET_LIVE`) — Webhook verification.
- `FRONTEND_PUBLIC_URL` or `PUBLIC_APP_URL` — Frontend base URL for activation/set-password links (must be production URL in production).
- `ENVIRONMENT=production` — Reject localhost and enforce subscription for provisioning.
- `CORS_ORIGINS` — Allowed frontend origins (e.g. Vercel URL).
- Postmark: `POSTMARK_API_KEY`, `POSTMARK_WEBHOOK_TOKEN` (for delivery webhooks).

**Frontend (Vercel):**

- `REACT_APP_BACKEND_URL` — Backend API base URL (e.g. Render service URL). Set at build time; rebuild after change.

If activation links point to localhost or wrong domain, set `FRONTEND_PUBLIC_URL` (or `PUBLIC_APP_URL`) on the backend and redeploy; set `REACT_APP_BACKEND_URL` on the frontend and redeploy.

### 9.4 Operational notes

- **Scheduler:** Runs inside the backend process. If the backend spins down (e.g. Render free tier sleep), no cron runs until the next request. For reliable jobs, keep one backend instance always on or use an external cron that hits “run job now” endpoints.
- **Single worker:** Multiple uvicorn workers each have their own scheduler; use one worker for the API if you want a single job runner.

---

## 10. Summary Diagram (Flow)

```
[Public] Risk Check → (optional) Activate → Intake 5 steps → Submit
    → Client + Properties created (INTAKE_PENDING)
    → Checkout → Stripe payment
    → Webhook: subscription_status, billing, entitlement, provisioning_job
    → Provisioning: requirements, recalc queue, portal user, migrate uploads, invite email
    → PROVISIONED → User sets password → Login
    → Client portal: Dashboard, Properties, Documents, Reports, Audit, Orders, …
    → Orders: FINALISING → order_delivery_processing → delivery email → COMPLETED
```

---

## 11. Key Database Collections

| Collection | Purpose |
|------------|---------|
| `clients` | Client profile, onboarding_status, subscription_status, billing_plan, stripe_customer_id. |
| `properties` | Property details (from intake); compliance_score, compliance_breakdown, requirements. |
| `portal_users` | Portal logins; client_id, role, auth_email, password_status, must_set_password. |
| `requirements` | Per-property requirements (from catalog/rules); due_date, status, evidence. |
| `documents` | Uploaded evidence; linked to client/property/requirement; extraction status. |
| `intake_uploads` | Staged intake documents (intake_session_id); migrated to vault after provisioning. |
| `provisioning_jobs` | Post-payment jobs; status PAYMENT_CONFIRMED → PROVISIONING_COMPLETED. |
| `compliance_recalc_queue` | Pending compliance recalc jobs; worker runs recalculate_and_persist. |
| `score_ledger_events` | Score change history (Audit & Change History); before/after, trigger, drivers. |
| `property_compliance_score_history` | Per-property score snapshots over time. |
| `orders` | Client/admin orders; workflow states through to COMPLETED / DELIVERY_FAILED. |
| `message_logs` | Email/SMS delivery log (Postmark webhooks). |
| `risk_leads` | Risk-check funnel leads; status, converted flag. |
| `job_runs` | Observability: background job execution log. |
| `incidents` | Observability: open/acknowledged/resolved incidents (e.g. SLA breach). |

---

## 12. Related Documentation

- **README.md** — Setup, env vars, deployment (Vercel + Render), activation links.
- **docs/BACKGROUND_AUTOMATIONS_AND_JOBS.md** — Job scheduler, single-worker note.
- **docs/POST_PAYMENT_FLOW_FIX.md** — Provisioning poller and PAYMENT_CONFIRMED → PROVISIONED flow.
- **docs/INTAKE_FLOW_AUDIT.md** — Intake validation and checkout behaviour.
- **docs/RESTORE_SERVICES.md** — Catalogue/CMS restore on deploy.

---

*Report generated from codebase and existing docs (intake, provisioning, stripe webhook, job_runner, server, order_delivery_service, README).*
