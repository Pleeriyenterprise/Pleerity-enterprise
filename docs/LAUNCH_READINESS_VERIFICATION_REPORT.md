# Launch Readiness Verification Report

**Date:** 2026-02-12  
**Scope:** Audit only — no code changes. Verification by tracing code paths and config.  
**Constraints:** No PII in logs or report; no runtime tests run.

---

## 1) Deployment & Environment Audit

### Backend environment variables (from code/config)

| Variable | Current State | Needs Real Value | Notes |
|----------|---------------|-------------------|-------|
| **MONGO_URL** | Required (no default in `database.py`; `server.py` defaults `mongodb://localhost:27017`) | Yes | Production must use real MongoDB connection string. |
| **DB_NAME** | Required in `database.py`; default `compliance_vault_pro` in `server.py` | Yes | Set to production DB name. |
| **JWT_SECRET** | Default `your-secret-key-change-in-production` in `auth.py` | Yes | Must be strong (32+ chars); default is placeholder. |
| **JWT_ALGORITHM** | Default `HS256` | No | OK as-is. |
| **JWT_EXPIRATION_HOURS** | Default `24` | No | OK as-is. |
| **STRIPE_API_KEY** | Default `sk_test_emergent` in `admin_billing.py`, `stripe_webhook_service.py`, `stripe_service.py`, `billing.py`, `intake_draft_service.py` | Yes | Must be `sk_live_*` for production. |
| **STRIPE_WEBHOOK_SECRET** | Default `""` in `stripe_webhook_service.py` | Yes | If empty, webhook signature verification is skipped (logged warning). Production must set. |
| **STRIPE_ORDERS_WEBHOOK_SECRET** | Used in `routes/orders.py`; no default | Yes | Required for orders webhook verification. |
| **POSTMARK_SERVER_TOKEN** | No default in `email_service.py` (client is None if unset) | Yes | Required for sending email; without it emails will not send. |
| **EMAIL_SENDER** | Default `info@pleerityenterprise.co.uk` in `email_service.py`, `support_email_service.py`, `order_email_templates.py`, etc. | Depends | OK if that is the production sender; otherwise set. |
| **SUPPORT_EMAIL** | Default `info@pleerityenterprise.co.uk` in several services | Depends | Same as above. |
| **FRONTEND_URL** | Mixed: `http://localhost:3000`, `https://order-fulfillment-9.preview.emergentagent.com`, `https://pleerityenterprise.co.uk` in different files | Yes | Single production URL must be set in env; many defaults are preview/local. |
| **REACT_APP_BACKEND_URL** | Used in `order_delivery_service.py` as backend URL (misnamed env) | Yes | Frontend build-time: API base URL. |
| **BOOTSTRAP_OWNER_EMAIL** | No default in `owner_bootstrap.py`; empty = skip | Yes (for first OWNER) | Required to create/promote first OWNER at startup when BOOTSTRAP_ENABLED=true. |
| **BOOTSTRAP_OWNER_PASSWORD** | Optional; used only when creating new OWNER | Optional | One-time; can be set for initial OWNER creation. |
| **BOOTSTRAP_ENABLED** | Default `""`; must be `true` to run bootstrap | No | Set `true` only when intending to bootstrap OWNER. |
| **BREAK_GLASS_ENABLED** | Default `""`; must be `true` for break-glass endpoint to exist | No | If `true`, break-glass endpoint is active. |
| **BOOTSTRAP_SECRET** | Required when BREAK_GLASS_ENABLED=true (`auth.py`) | Yes (if break-glass on) | Shared secret for break-glass OWNER password reset. |
| **CORS_ORIGINS** | Default `*` in `server.py` (split by comma) | Yes | Production should list exact frontend origin(s), not `*`. |
| **ENVIRONMENT** | Default `development` in `server.py`; controls reload and health response | Yes | Set `production` in production. |
| **INTAKE_UPLOAD_DIR** | Default `/app/uploads/intake` in `intake_uploads.py`, `clamav_scanner.py` | Depends | Must exist and be writable; align with deployment paths. |
| **INTAKE_QUARANTINE_DIR** | Default `/app/uploads/intake_quarantine` in `clamav_scanner.py` | Depends | Must exist and be writable for ClamAV quarantine. |
| **DOCUMENT_STORAGE_PATH** | Default `/app/data/documents` in `intake_upload_migration.py` | Depends | Must exist and be writable. |
| **CLAMAV_SOCKET** | Optional; if set and path exists, use clamdscan | Optional | For ClamAV daemon; else clamscan on PATH. |
| **EMERGENT_LLM_KEY** | No default in `document_orchestrator.py` (raises if missing); default `sk-emergent-f9533226f52E25cF35` in `admin.py`, `document_analysis.py`, `assistant_service.py` | Yes | Placeholder/default in some files; production must set real key; orchestrator has no default. |
| **PROVISIONING_WORKER_ID** | Optional; default from PID + uuid | No | Optional for poller identity. |
| **SEED_ADMIN_EMAIL** / **SEED_ADMIN_PASSWORD** | Defaults `admin@pleerity.com` / `Admin123!` in `seed.py` | Yes (if seed used) | Only for seed script; not for production runtime. |
| **SEED_OWNER_EMAIL** / **SEED_OWNER_PASSWORD** | Optional in `seed.py` | Optional | Alternative to BOOTSTRAP_OWNER_* for seed. |
| **BASE_URL** | Used in `routes/calendar.py` for callback URLs | Depends | Set if calendar callbacks needed. |
| **UNSUBSCRIBE_URL** | Default `https://order-fulfillment-9.preview.emergentagent.com/unsubscribe` in `lead_followup_service.py` | Yes | Should be production frontend URL. |
| **STRIPE_SECRET_KEY** | Alternative to STRIPE_API_KEY in `setup_stripe_products.py` | Optional | Script uses STRIPE_API_KEY or this. |

### Frontend environment variables

| Variable | Current State | Needs Real Value | Notes |
|----------|---------------|-------------------|-------|
| **REACT_APP_BACKEND_URL** | Used in `api/client.js` and many pages as API base | Yes | Must be production API URL at build time. |
| **REACT_APP_TAWKTO_PROPERTY_ID** / **REACT_APP_TAWKTO_WIDGET_ID** | Default `YOUR_PROPERTY_ID` / `YOUR_WIDGET_ID` in `TawkToWidget.js` | Yes (if using Tawk) | Placeholders; replace or leave unset to disable. |
| **NODE_ENV** | Set by build (development/production) | No | Build tooling sets. |

### Stripe LIVE keys & webhook secret usage

- **STRIPE_API_KEY:** Used as `stripe.api_key` in multiple modules (admin_billing, stripe_webhook_service, stripe_service, billing, intake_draft_service, clearform routes). Default is `sk_test_emergent`. For production, set to `sk_live_*`.
- **STRIPE_WEBHOOK_SECRET:** In `stripe_webhook_service.py`, when set, `stripe.Webhook.construct_event(payload, signature, STRIPE_WEBHOOK_SECRET)` is used; when unset, signature verification is skipped and a warning is logged. Production must set the webhook signing secret from Stripe Dashboard (live endpoint).
- **STRIPE_ORDERS_WEBHOOK_SECRET:** Used in `routes/orders.py` for orders webhook; if not set, verification is skipped. Production must set for orders webhook.

### Email provider production keys

- **POSTMARK_SERVER_TOKEN:** Only env for Postmark. If not set, email client is not initialized and emails will not send. No fallback.

### BOOTSTRAP_OWNER_EMAIL usage

- **owner_bootstrap.py:** Reads `BOOTSTRAP_OWNER_EMAIL`; if empty, returns "skipped". Used when `BOOTSTRAP_ENABLED=true` at server startup and in seed when `BOOTSTRAP_OWNER_EMAIL` is set. Creates or promotes exactly one OWNER. No default email in code.

### BREAK_GLASS_ENABLED / BOOTSTRAP_SECRET

- **auth.py:** Break-glass endpoint exists only when `BREAK_GLASS_ENABLED` is `true`. If enabled, `BOOTSTRAP_SECRET` must be set; otherwise returns 503. Secret compared to `X-Break-Glass-Secret` or Bearer token. Audit log `BREAK_GLASS_OWNER_USED` written on use (success or invalid_secret/no_owner).

### ClamAV / intake upload directories

- **INTAKE_UPLOAD_DIR:** Default `/app/uploads/intake`; used in `intake_uploads.py` and `clamav_scanner.py`. Created with `mkdir(parents=True, exist_ok=True)` in intake_uploads.
- **INTAKE_QUARANTINE_DIR:** Default `/app/uploads/intake_quarantine`; used in `clamav_scanner.py` for quarantined files. Must be writable.
- **CLAMAV_SOCKET:** Optional; if set and path exists, clamdscan is used; else clamscan on PATH. See `docs/INTAKE_UPLOADS_CLAMAV.md`.

### TODO / CHANGE_ME / example.com / localhost references

- **TODO (in code):** `server.py` ~215 (send notification to admin); `lead_followup_service.py` ~600 (business hours mode); `lead_service.py` ~470 (notify admin), ~769 (avg_time_to_contact); `admin_orders.py` ~387, ~459, ~1211 (trigger jobs / resend email); `team.py` ~373 (send invite email); `clearform` (invitation email, usage tracking); `clearform/routes/audit.py` ~200 (verify document ownership). None are placeholder env vars; all are implementation notes.
- **example.com:** Used only in tests and script examples (`re_enable_admin_by_email.py`, `resend_portal_invite.py`, test files, `intake_schema_registry.py` placeholders for schema UI). No production config.
- **localhost:** Defaults in `server.py` (MONGO_URL, DB_NAME), `admin.py` (FRONTEND_URL for resend link), `provisioning.py`, `provisioning_runner.py`, `resend_portal_invite.py`, `billing.py` (host header), `clearform` routes (FRONTEND_URL). Production must override via env.
- **Preview / test URLs:** Multiple files default FRONTEND_URL or links to `https://order-fulfillment-9.preview.emergentagent.com` or `https://pleerityenterprise.co.uk`. Production must set FRONTEND_URL and any UNSUBSCRIBE_URL / link bases.
- **EMERGENT_LLM_KEY:** Hardcoded default `sk-emergent-f9533226f52E25cF35` in `admin.py` (line 2822), `document_analysis.py`, `assistant_service.py`. Production must set real key and must not rely on this default.

---

## 2) Deployment Source of Truth

- **Where the system is expected to be deployed:** The repo contains `.emergent/emergent.yml` (Emergent job/image metadata). PRODUCTION_DEPLOYMENT.md and multiple defaults reference a preview URL (`order-fulfillment-9.preview.emergentagent.com`). Deployment is expected on **Emergent** (or similar) for production; local is for development.
- **Cursor:** Cursor is a development tool only; it is not the deployment mechanism. No deploy pipeline is driven by Cursor.
- **GitHub sync:** `.github/workflows/backend-tests.yml` runs backend tests on push/PR to `main`. There is no workflow that deploys to Emergent in this repo; whether "pushing to GitHub" syncs to Emergent depends on Emergent’s own integration (e.g. GitHub as source, separate deploy step). The repo does not define that pipeline.

**Deliverable — Clear statement:**  
**“Deploy from the configured Emergent pipeline (or CI/CD that builds from the GitHub repo), not from Cursor. Cursor is for development only. Confirm with Emergent/platform docs whether pushing to GitHub is sufficient to trigger deployment or if a separate deploy step is required.”**

---

## 3) Frontend Access & Validation

- **Production frontend URL:** Not defined in repo. It should be the same value as **FRONTEND_URL** used by the backend (e.g. `https://pleerityenterprise.co.uk` or the chosen production domain). Backend uses FRONTEND_URL for links in emails and redirects.
- **CORS:** Backend uses `allow_origins=os.environ.get('CORS_ORIGINS', '*').split(',')`. Default `*` is not production-safe. Production should set **CORS_ORIGINS** to the exact frontend origin(s) (e.g. `https://your-frontend-domain.com`).
- **Auth:** Frontend uses **Bearer token in `Authorization` header** (`localStorage.getItem('auth_token')` in `api/client.js`). No auth cookies in the audited flow. Same-origin or CORS with credentials is sufficient if API and frontend share a domain or CORS is restricted to the frontend origin.
- **API base URL:** Frontend uses **REACT_APP_BACKEND_URL** at build time. Production build must be built with `REACT_APP_BACKEND_URL` set to the production API URL (e.g. `https://api.pleerityenterprise.co.uk` or the actual backend URL). No runtime override unless another mechanism exists outside the audited files.
- **Blocking frontend access after deploy:** If CORS_ORIGINS is too restrictive or wrong, browsers will block API calls. If REACT_APP_BACKEND_URL is wrong or missing, API requests go to the wrong host or fail. No other frontend “blocker” identified in config.

**Deliverable — Where the frontend should be accessed after deploy:**  
**The frontend should be accessed at the production frontend URL (the same value as FRONTEND_URL used by the backend). That URL must be set in Emergent/build config and must match the origin listed in backend CORS_ORIGINS. The frontend build must be produced with REACT_APP_BACKEND_URL pointing at the production API base URL.**

---

## 4) End-to-End System Readiness Audit (Code Paths Only)

| # | Area | Result | Evidence / Notes |
|---|------|--------|------------------|
| 1 | Intake → Payment → Provisioning → Portal login | PASS (with caveats) | Intake creates client; Stripe checkout; webhook updates billing and entitlement; provisioning creates PortalUser and sends password-setup email; poller must run to process jobs. If poller not run, jobs stay PAYMENT_CONFIRMED and client may not get access. |
| 2 | Plan gating (no feature leakage) | NEEDS ATTENTION | PRODUCTION_SYSTEM_AUDIT_REPORT.md: three gating systems (plan_registry, plan_gating, feature_entitlement); middleware uses `plan_code` but DB has `billing_plan`; legacy plan_gating/feature_entitlement use 1/5/15 limits. Risk of wrong caps and feature leakage/denial until unified on plan_registry and billing_plan. |
| 3 | Document generation (no raw intake leakage) | PASS | DOC_GENERATION_AUDIT.md: intake passed as structured snapshot; prompt template controls injection (e.g. `{{INPUT_DATA_JSON}}`); rendering uses structured_output + snapshot. Risk only if a template is authored that dumps raw JSON with no structure. |
| 4 | Compliance score correctness and update triggers | PASS (with known gaps) | COMPLIANCE_SCORE_AND_REQUIREMENT_UPDATE_AUDIT.md: single production scorer `calculate_compliance_score`; upload triggers requirement update and property compliance (where implemented); verify triggers property compliance; score recomputed on GET compliance-score; snapshots and status checks run via scheduled jobs. |
| 5 | Email delivery + resend flows | PASS | Email via Postmark (POSTMARK_SERVER_TOKEN); message_logs and audit for skipped; Admin Email delivery UI and resend-password-setup exist; resend returns 502 on send failure with error_code EMAIL_SEND_FAILED. |
| 6 | OWNER / ADMIN governance safety | NEEDS ATTENTION | Break-glass and bootstrap documented; self-deactivation blocked. No “last admin” safeguard; last admin can be deactivated by another admin (PRODUCTION_SYSTEM_AUDIT_REPORT.md). |

---

## 5) Automation & Jobs

### In-process scheduler (server.py)

| Job | Schedule | Purpose |
|-----|----------|---------|
| Daily reminders | 09:00 UTC | Compliance reminders (entitlement ENABLED only). |
| Pending verification digest | 09:30 UTC | Digest of docs awaiting verification (counts only). |
| Monthly digest | 1st of month, 10:00 UTC | Monthly compliance digest. |
| Compliance status check | 08:00, 18:00 UTC | Property compliance_status sync; degradation alerts. |
| Scheduled reports | Every hour | Process due reports. |
| Compliance score snapshots | 02:00 UTC | Write to compliance_score_history. |
| Order delivery processing | Every 5 min | Deliver orders in FINALISING. |
| SLA monitoring | Every 15 min | SLA warnings/breach notifications. |
| Stuck order detection | Every 30 min | Detect stuck FINALISING orders. |

### External / cron (must be run separately)

| Worker / Script | Frequency | Purpose | If not running |
|-----------------|------------|---------|----------------|
| **Provisioning poller** | Every 1–2 min (e.g. `*/2 * * * *`) | Processes `provisioning_jobs` with `needs_run=True`; creates portal user and sends password email after payment. | New paying clients never get portal access; jobs stay PAYMENT_CONFIRMED. |
| **Optional: daily/monthly jobs** | If not using in-process scheduler | Same as daily reminders and monthly digest. | Reminders/digests not sent; compliance snapshots and status checks may not run if server has no scheduler. |

**Deliverable — Required cron / worker list:**

- **Provisioning poller (required):**  
  `*/2 * * * * cd /app/backend && python -m scripts.run_provisioning_poller --max-jobs 10`  
  (or equivalent path and schedule). Env must include MONGO_URL, DB_NAME, and any required for runner (e.g. email, Stripe).
- **In-process jobs:** Assumed to run inside the backend process (APScheduler + MongoDB job store). If the backend runs as a single process, all scheduled jobs above run there; no separate cron needed for them. If backend is scaled or jobs are offloaded, equivalent cron entries for daily reminders, monthly digest, compliance snapshots, compliance status check, scheduled reports, order delivery, SLA, stuck orders must be provided elsewhere.

---

## 6) Conflicts & Risks

### Conflicting or inconsistent logic

- **Plan gating:** Three systems (plan_registry, plan_gating, feature_entitlement) and wrong client field (`plan_code` vs `billing_plan`) cause inconsistent property limits and feature access (see PRODUCTION_SYSTEM_AUDIT_REPORT.md).
- **FRONTEND_URL / REACT_APP_BACKEND_URL:** Multiple different defaults (localhost, preview URL, pleerityenterprise.co.uk). Risk of emails/links pointing to wrong environment if env not set consistently.
- **STRIPE_WEBHOOK_SECRET empty:** Webhook handler accepts events without signature verification when secret is not set; safe only for dev.

### Behaviour that could silently fail in production

- **No POSTMARK_SERVER_TOKEN:** Emails simply do not send; client may never get password link.
- **Provisioning poller not run:** Payment is recorded and job created, but portal is never provisioned; client sees “paid” but has no login.
- **STRIPE_WEBHOOK_SECRET not set:** Forged webhooks could be accepted.
- **EMERGENT_LLM_KEY missing:** Document orchestrator and prompt_service raise; assistant/document_analysis may use a hardcoded default in some paths (review needed for production).

### Launch Risk List (ranked)

| Priority | Risk | Mitigation |
|----------|------|------------|
| **P0** | Provisioning poller not running → clients pay but get no access | Run poller on cron every 1–2 min; monitor job completion and alert on backlog. |
| **P0** | STRIPE_WEBHOOK_SECRET or STRIPE_API_KEY not set for live → payments or webhooks insecure/wrong | Set live Stripe key and webhook secret; verify endpoint in Stripe Dashboard. |
| **P0** | POSTMARK_SERVER_TOKEN not set → no emails | Set token; verify send with a test. |
| **P0** | JWT_SECRET left default → session compromise | Set strong JWT_SECRET (32+ chars). |
| **P1** | CORS_ORIGINS=* in production → CSRF/origin abuse | Set CORS_ORIGINS to exact frontend origin(s). |
| **P1** | Plan gating inconsistencies → wrong limits / feature leakage or denial | Resolve plan_registry vs plan_gating/feature_entitlement and use billing_plan in middleware (see PRODUCTION_SYSTEM_AUDIT_REPORT.md). |
| **P1** | Last admin deactivated → no admin access | Add “at least one admin” check or document recovery (break-glass + DB/script). |
| **P2** | FRONTEND_URL / REACT_APP_BACKEND_URL wrong → broken links or API calls | Set both consistently for production build and backend env. |
| **P2** | EMERGENT_LLM_KEY default/placeholder in some services → wrong or failing LLM calls | Set EMERGENT_LLM_KEY everywhere; remove hardcoded defaults for production. |
| **P2** | Rate limiting in-memory → not shared across instances | PRODUCTION_DEPLOYMENT.md notes production should use Redis for rate limiting. |

---

## 7) Operational Runbooks (Confirm or Flag Missing)

| Runbook | Exists? | Where / Notes |
|---------|---------|----------------|
| Client paid but no access | Partially | PRODUCTION_DEPLOYMENT.md “Provisioning fails” and PROVISIONING_JOBS_POLLER.md describe flow and poller; no dedicated “client paid, no access” runbook (steps: check provisioning_jobs, run poller, resend password, etc.). **Flag: needs runbook.** |
| Email failed | Partially | PRODUCTION_DEPLOYMENT.md “Emails not sending” (Postmark, templates, message_logs). Admin Email delivery UI + resend for password-setup. **Flag: formal “email failed” runbook (diagnosis + resend) recommended.** |
| Document generation failed | Partially | DOC_GENERATION_FAILURE_VERIFICATION.md and DOC_GENERATION_AUDIT.md describe pipeline; no step-by-step operator runbook. **Flag: needs runbook.** |
| Compliance score dispute | No | No runbook found. **Flag: needs runbook (how to verify calculation, requirement status, property compliance, snapshots).** |
| Owner/admin lockout | Partially | Break-glass endpoint and BOOTSTRAP_SECRET documented in code/auth; PRODUCTION_SYSTEM_AUDIT_REPORT mentions recovery. **Flag: short runbook (break-glass + “last admin” recovery) recommended.** |

**Deliverable — Runbooks to add (do not create in this audit):**

1. **Client paid but no access** — Check provisioning_jobs status; run poller if needed; verify email sent; resend password-setup from Admin if required.  
2. **Email failed** — Check POSTMARK_SERVER_TOKEN and message_logs; use Admin Email delivery to filter failed and resend (password-setup only); escalate to Postmark if needed.  
3. **Document generation failed** — Use DOC_GENERATION_AUDIT/FAILURE_VERIFICATION; check orchestration_executions and order status; retry or manual generate/regenerate steps.  
4. **Compliance score dispute** — How to verify requirements, property compliance, and score calculation (compliance_score.py and COMPLIANCE_SCORE_AND_REQUIREMENT_UPDATE_AUDIT).  
5. **Owner/admin lockout** — Break-glass procedure (BREAK_GLASS_ENABLED, BOOTSTRAP_SECRET); recovery of last admin (DB/script) if implemented or documented.

---

**End of report. No code or config was changed.**
