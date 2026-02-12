# Launch Readiness — Current Code on GitHub (main)

**Repo (GitHub remote):** `https://github.com/Pleeriyenterprise/Pleerity-enterprise.git`  
**Branch audited:** `main`  
**Commit SHA (origin/main):** `0caf30dcb79437ee06beb7f97ccfef57a69b24c9`

**Note:** Branch `main` exists on GitHub (`remotes/origin/main`). Audit was performed on the workspace at the above SHA.

---

## 1) Placeholder Hunt (hard requirement)

Every placeholder/default/dev value that must be replaced for production. **Production-safe value type** = what to set (no actual secrets in this doc).

### Backend env vars

| File path | Variable / key | Current default/value | Production-safe value type |
|-----------|----------------|------------------------|----------------------------|
| backend/database.py | MONGO_URL | (required, no default) | Production MongoDB connection string |
| backend/database.py | DB_NAME | (required, no default) | Production DB name |
| backend/server.py | MONGO_URL | mongodb://localhost:27017 | Production MongoDB connection string |
| backend/server.py | DB_NAME | compliance_vault_pro | Production DB name |
| backend/server.py | CORS_ORIGINS | * | Comma-separated list of allowed origins (e.g. https://your-frontend.com) |
| backend/server.py | ENVIRONMENT | development | Set to `production` |
| backend/auth.py | JWT_SECRET | your-secret-key-change-in-production | Strong random secret (32+ chars) |
| backend/auth.py | JWT_ALGORITHM | HS256 | Keep or override |
| backend/auth.py | JWT_EXPIRATION_HOURS | 24 | Keep or override |
| backend/services/document_access_token.py | JWT_SECRET | default-secret-change-in-production | Same as auth JWT_SECRET |
| backend/routes/auth.py | BREAK_GLASS_ENABLED | (any non-"true" = disabled) | Set `true` only if break-glass desired |
| backend/routes/auth.py | BOOTSTRAP_SECRET | "" | Strong secret when BREAK_GLASS_ENABLED=true |
| backend/server.py | BOOTSTRAP_ENABLED | "" | Set `true` only when bootstrapping OWNER |
| backend/services/owner_bootstrap.py | BOOTSTRAP_OWNER_EMAIL | "" | Email for first OWNER (required to create/promote) |
| backend/services/owner_bootstrap.py | BOOTSTRAP_OWNER_PASSWORD | "" | Optional one-time password for new OWNER |
| backend/seed.py | SEED_ADMIN_EMAIL | admin@pleerity.com | Override for seed script only |
| backend/seed.py | SEED_ADMIN_PASSWORD | Admin123! | Override for seed script only |
| backend/seed.py | SEED_OWNER_EMAIL / SEED_OWNER_PASSWORD | "" / Owner123! | Optional seed path |
| backend/routes/admin_billing.py | STRIPE_API_KEY | sk_test_emergent | Stripe live secret key (sk_live_*) |
| backend/services/stripe_webhook_service.py | STRIPE_API_KEY | sk_test_emergent | Stripe live secret key |
| backend/services/stripe_webhook_service.py | STRIPE_WEBHOOK_SECRET | "" | Stripe webhook signing secret (live endpoint) |
| backend/services/stripe_service.py | STRIPE_API_KEY | sk_test_emergent | Stripe live secret key |
| backend/routes/billing.py | STRIPE_API_KEY | sk_test_emergent | Stripe live secret key |
| backend/services/intake_draft_service.py | STRIPE_API_KEY | sk_test_emergent | Stripe live secret key |
| backend/routes/orders.py | STRIPE_SECRET_KEY | (no default) | Stripe secret key for orders API |
| backend/routes/orders.py | STRIPE_ORDERS_WEBHOOK_SECRET | (no default) | Orders webhook signing secret |
| backend/scripts/setup_stripe_products.py | STRIPE_SECRET_KEY / STRIPE_API_KEY | (script) | Set for script runs |
| backend/services/email_service.py | POSTMARK_SERVER_TOKEN | (none; client None if unset) | Postmark server token |
| backend/services/email_service.py | EMAIL_SENDER | info@pleerityenterprise.co.uk | Verified sender identity |
| backend/services/support_email_service.py | POSTMARK_SERVER_TOKEN | (none) | Same as above |
| backend/services/support_email_service.py | EMAIL_SENDER / SUPPORT_EMAIL | info@pleerityenterprise.co.uk | Support/sender address |
| backend/services/order_email_templates.py | SUPPORT_EMAIL / FRONTEND_URL | info@pleerityenterprise.co.uk / https://pleerity.com | Production values |
| backend/services/lead_followup_service.py | ADMIN_DASHBOARD_URL | https://order-fulfillment-9.preview.emergentagent.com/admin/leads | Production frontend admin URL |
| backend/services/lead_followup_service.py | UNSUBSCRIBE_URL | https://order-fulfillment-9.preview.emergentagent.com/unsubscribe | Production frontend unsubscribe URL |
| backend/services/lead_service.py | ADMIN_DASHBOARD_URL | https://order-fulfillment-9.preview.emergentagent.com/admin/leads | Same |
| backend/services/lead_followup_service.py | ADMIN_NOTIFICATION_EMAILS | admin@pleerity.com | Comma-separated admin emails |
| backend/services/lead_service.py | ADMIN_NOTIFICATION_EMAILS | admin@pleerity.com | Same |
| backend/services/kit_integration.py | KIT_API_KEY | 1nG0QycdXFwymTr1oLiuUA | Real KIT API key or remove use |
| backend/services/document_orchestrator.py | EMERGENT_LLM_KEY | (no default; raises if missing) | Production LLM API key |
| backend/services/prompt_service.py | EMERGENT_LLM_KEY | (no default; raises if missing) | Same |
| backend/routes/admin.py | EMERGENT_LLM_KEY | sk-emergent-f9533226f52E25cF35 | Production key (remove hardcoded default) |
| backend/services/document_analysis.py | EMERGENT_LLM_KEY | sk-emergent-f9533226f52E25cF35 | Same |
| backend/services/assistant_service.py | EMERGENT_LLM_KEY | sk-emergent-f9533226f52E25cF35 | Same |
| backend/services/support_chatbot.py | EMERGENT_LLM_KEY | (optional; fallback response if unset) | Set for real LLM |
| backend/services/lead_ai_service.py | EMERGENT_LLM_KEY | (none) | Set for lead AI |
| backend/routes/intake_uploads.py | INTAKE_UPLOAD_DIR | /app/uploads/intake | Writable path for intake uploads |
| backend/services/clamav_scanner.py | INTAKE_UPLOAD_DIR | /app/uploads/intake | Same as above |
| backend/services/clamav_scanner.py | INTAKE_QUARANTINE_DIR | /app/uploads/intake_quarantine | Writable quarantine path |
| backend/services/clamav_scanner.py | CLAMAV_SOCKET | "" | Optional; path to clamd socket |
| backend/services/intake_upload_migration.py | DOCUMENT_STORAGE_PATH | /app/data/documents | Writable document storage path |
| backend/routes/calendar.py | BASE_URL | (request.base_url) | Set if calendar callbacks need fixed URL |
| backend/routes/reporting.py | PUBLIC_URL | "" | Set if report sharing uses public base URL |
| backend/routes/marketing.py | ENVIRONMENT | preview | Set to production for production behaviour |
| backend/clearform/routes/webhooks.py | STRIPE_WEBHOOK_SECRET | (none) | ClearForm Stripe webhook secret if used |

### FRONTEND_URL (backend) — multiple files, must be single production value

| File path | Default used when FRONTEND_URL unset | Production-safe value type |
|-----------|--------------------------------------|----------------------------|
| backend/routes/admin.py | http://localhost:3000 (line 706) | Production frontend base URL |
| backend/routes/admin.py | https://order-fulfillment-9.preview.emergentagent.com (1900, 2207, 2478) | Same |
| backend/routes/admin_billing.py | https://order-fulfillment-9.preview.emergentagent.com | Same |
| backend/routes/documents.py | https://compliance-vault-pro.pleerity.com | Same |
| backend/services/jobs.py | https://order-fulfillment-9.preview.emergentagent.com | Same |
| backend/services/email_service.py | https://pleerityenterprise.co.uk (1098) | Same |
| backend/services/provisioning_runner.py | http://localhost:3000 | Same |
| backend/services/provisioning.py | http://localhost:3000 | Same |
| backend/services/stripe_webhook_service.py | https://order-fulfillment-9.preview.emergentagent.com | Same |
| backend/services/support_email_service.py | https://pleerity.com | Same |
| backend/services/order_delivery_service.py | https://order-fulfillment-9.preview.emergentagent.com | Same |
| backend/services/order_delivery_service.py | REACT_APP_BACKEND_URL default https://order-fulfillment-9.preview.emergentagent.com | Backend base URL (misnamed env) |
| backend/services/intake_draft_service.py | https://pleerity.com | Same as FRONTEND_URL |
| backend/services/lead_followup_service.py | (hardcoded preview URLs in template strings) | Set ADMIN_DASHBOARD_URL + UNSUBSCRIBE_URL |
| backend/routes/intake.py | origin or http://localhost:3000 | N/A (request origin fallback) |
| backend/scripts/resend_portal_invite.py | http://localhost:3000 | Set when running script |
| backend/clearform/routes/subscriptions.py, credits.py | http://localhost:3000 | Same as FRONTEND_URL |
| backend/routes/admin_orders.py | https://pleerity.com (528); "" (702) | Same |
| backend/routes/client_orders.py | https://pleerity.com | Same |
| backend/routes/intake_wizard.py | https://pleerity.com | Same |
| backend/services/owner_bootstrap.py | "" | Same |

### Frontend env vars

| File path | Variable / key | Current default/value | Production-safe value type |
|-----------|----------------|------------------------|----------------------------|
| frontend/src/api/client.js | REACT_APP_BACKEND_URL | (none at runtime; build-time only) | Production API base URL (e.g. https://api.yourdomain.com) |
| frontend/src/components/TawkToWidget.js | REACT_APP_TAWKTO_PROPERTY_ID | YOUR_PROPERTY_ID | Real Tawk property ID or leave unset to disable |
| frontend/src/components/TawkToWidget.js | REACT_APP_TAWKTO_WIDGET_ID | YOUR_WIDGET_ID | Real Tawk widget ID or leave unset |

### Hard-coded preview URLs, localhost, sk_test, example.com, YOUR_*

| File path | Current value | Production action |
|-----------|---------------|-------------------|
| backend/routes/admin.py | http://localhost:3000 | Set FRONTEND_URL in env |
| backend/routes/admin.py | https://order-fulfillment-9.preview.emergentagent.com | Set FRONTEND_URL |
| backend/routes/admin.py | sk-emergent-f9533226f52E25cF35 | Set EMERGENT_LLM_KEY; do not rely on default |
| backend/server.py | mongodb://localhost:27017 | Set MONGO_URL |
| backend/services/provisioning_runner.py | http://localhost:3000 | Set FRONTEND_URL |
| backend/services/provisioning.py | http://localhost:3000 | Set FRONTEND_URL |
| backend/scripts/resend_portal_invite.py | http://localhost:3000 | Set FRONTEND_URL when running |
| backend/routes/intake.py | http://localhost:3000 (origin fallback) | N/A (request origin) |
| backend/clearform/routes/subscriptions.py, credits.py | http://localhost:3000 | Set FRONTEND_URL |
| backend/services/lead_followup_service.py | https://order-fulfillment-9.preview.emergentagent.com (in template links) | Set ADMIN_DASHBOARD_URL, UNSUBSCRIBE_URL |
| backend/services/lead_service.py | https://order-fulfillment-9.preview.emergentagent.com/admin/leads | Set ADMIN_DASHBOARD_URL |
| backend/services/order_delivery_service.py | https://order-fulfillment-9.preview.emergentagent.com (FRONTEND_URL, BACKEND_URL) | Set both in env |
| frontend/src/components/TawkToWidget.js | YOUR_PROPERTY_ID, YOUR_WIDGET_ID | Set or leave unset (widget disabled) |
| README.md | MONGO_URL=mongodb://localhost:27017, STRIPE_API_KEY=sk_test_emergent, FRONTEND_URL=http://localhost:3000, REACT_APP_BACKEND_URL=https://order-fulfillment-9.preview.emergentagent.com | Doc only; use production values in real .env |
| Test files (backend/tests, tests/) | example.com, order-fulfillment-9.preview.emergentagent.com, sk_test | Test fixtures only; no change for prod |

---

## 2) Deployment Truth

- **Where deployment happens (from repo):**  
  The repo contains **`.emergent/emergent.yml`** (Emergent job/image metadata: `env_image_name`, `job_id`, `created_at`). There is **no other deploy config** (no Dockerfile in the listed tree, no Heroku/Vercel config). **Conclusion:** Deployment is expected to happen via **Emergent** (or a pipeline that uses this repo and the Emergent image).

- **Auto-triggered by GitHub push or manual:**  
  **Unknown.** The only workflow under `.github/workflows` is **`backend-tests.yml`**, which runs backend tests on push/PR to `main`. It does **not** trigger a deploy. There is no workflow that calls Emergent or pushes an image. So:
  - **Deploy is not auto-triggered by GitHub push** from this repo’s workflows.
  - Whether Emergent auto-deploys on push (e.g. via Emergent’s own GitHub integration) **cannot be verified from the repo**.

**What you must check in Emergent UI:**  
(1) Is this repo connected to an Emergent project/app?  
(2) Is the deploy trigger “on push to main”, “manual”, or something else?  
(3) Which branch and path does Emergent build from?

---

## 3) Frontend Access

- **URL that should load the frontend after deploy:**  
  The **same URL as the value of `FRONTEND_URL`** configured in the backend for that environment. The repo does not define this; you set it in Emergent (or your env). Example: `https://your-app.emergentagent.com` or `https://pleerityenterprise.co.uk`. All backend links (password setup, emails, redirects) use `FRONTEND_URL`, so backend and frontend must agree on this value.

- **API base URL the frontend will call:**  
  The frontend uses **`process.env.REACT_APP_BACKEND_URL`** (see `frontend/src/api/client.js` and every page that calls the API). This is **baked in at build time** (Create React App / React env). There is no runtime override in the audited code.

- **Where it is set:**  
  Set **`REACT_APP_BACKEND_URL`** in the environment used when running the frontend build (e.g. in Emergent’s build settings or in the shell before `npm run build` / `yarn build`). Example: `REACT_APP_BACKEND_URL=https://api.yourdomain.com` (no trailing slash; the code appends `/api`).

- **Required CORS_ORIGINS for that setup:**  
  Backend uses `allow_origins=os.environ.get('CORS_ORIGINS', '*').split(',')` in `backend/server.py`. For production, set **CORS_ORIGINS** to the exact origin of the frontend that will load in the browser. Example: if the frontend is at `https://app.yourdomain.com`, set `CORS_ORIGINS=https://app.yourdomain.com`. Multiple origins: comma-separated, no spaces (e.g. `https://app.yourdomain.com,https://admin.yourdomain.com`). **Do not use `*` in production.**

---

## 4) End-to-End Test Plan (Manual Staging Run)

Run on **staging** with staging Stripe, Postmark, and DB. Use a test client email you can access.

| Step | Action | What to check (admin endpoints / DB) | “Good” looks like |
|------|--------|-------------------------------------|--------------------|
| 1. Intake (upload + email option) | Submit intake with 1 property; choose document submission method (e.g. email). Optionally upload a file in intake if the flow allows. | `GET /api/intake/onboarding-status/{client_id}` (after you have client_id from admin or DB). | `onboarding_status: INTAKE_PENDING` or similar; client and properties exist. |
| 2. Payment | Complete Stripe Checkout (test card 4242…) for the created client. | `GET /api/admin/billing/clients` or DB: `clients.subscription_status`, `client_billing`. Webhook: `stripe_events` has `checkout.session.completed` with `status: PROCESSED`. | `subscription_status: ACTIVE`, entitlement set; `provisioning_jobs` has a job with `status: PAYMENT_CONFIRMED` and `needs_run: true`. |
| 3. Provisioning job | (Automatic via webhook.) | DB: `provisioning_jobs` for that `client_id`: `status` = PAYMENT_CONFIRMED, `needs_run` = true. | Job exists and is runnable. |
| 4. Poller | Run: `cd backend && python -m scripts.run_provisioning_poller --max-jobs 10`. | Same job: `status` progresses to WELCOME_EMAIL_SENT; `portal_users` has entry for client; `clients.onboarding_status` = PROVISIONED. | Job status WELCOME_EMAIL_SENT; portal_user exists; client PROVISIONED. |
| 5. Invite email | Check inbox (and Postmark activity). | `GET /api/admin/email-delivery?status=failed&template_alias=password-setup` (optional). `message_logs` for template password-setup, status sent. | Password setup email received; no failed row for that client in email-delivery. |
| 6. First login | Open link from email → set password → log in to portal. | `POST /api/auth/set-password`, then `POST /api/auth/login` (or portal login). | 200; redirect to /app/dashboard; token in localStorage. |
| 7. Upload doc | As client, upload a document to a requirement. | `POST /api/documents/upload`; DB: `documents` has new doc, status UPLOADED; `requirements` updated (e.g. due_date). | 200; document and requirement updated. |
| 8. Verify doc | As admin, verify the document. | `POST /api/documents/verify/{document_id}` (admin). DB: `documents.status` = VERIFIED; `requirements.status` = COMPLIANT; `properties.compliance_status` updated. | 200; statuses updated; compliance score reflects on next fetch. |
| 9. Compliance score update | As client, open dashboard or call compliance score. | `GET /api/client/compliance-score`. | 200; score and breakdown consistent with verified docs and requirements. |
| 10. Document generation | (If using order/document pack flow.) Create order, pay, trigger generation; or use admin generate. | `GET /api/admin/orders/{order_id}` or orchestration_executions; order status and document_versions. | Order reaches expected status; documents generated and stored. |
| 11. Resend password | As admin, open Email delivery, filter status=failed, template=password-setup; click Resend for a row with client_id; or call resend endpoint. | `POST /api/admin/clients/{client_id}/resend-password-setup`. `message_logs` new sent row; audit PORTAL_INVITE_RESENT. | 200; new password email sent; no 502. |
| 12. Break-glass | Only if BREAK_GLASS_ENABLED=true and BOOTSTRAP_SECRET set. `POST /api/auth/break-glass-reset-owner-password` with header `X-Break-Glass-Secret: <BOOTSTRAP_SECRET>` and body `{"new_password": "NewSecurePassword!"}`. | Audit log: BREAK_GLASS_OWNER_USED, outcome success. Owner can log in with new password. | 200; owner password changed; sessions invalidated. |

**Admin endpoints summary for each stage:**  
- After intake: use admin client list or DB to get `client_id`.  
- After payment: `GET /api/admin/billing/clients`, DB `stripe_events`, `provisioning_jobs`.  
- After poller: DB `provisioning_jobs`, `portal_users`, `clients.onboarding_status`.  
- Email: `GET /api/admin/email-delivery` (optional), DB `message_logs`.  
- Documents/verify: `POST /api/documents/verify/{document_id}` (admin).  
- Compliance: `GET /api/client/compliance-score` (as client).  
- Resend: `POST /api/admin/clients/{client_id}/resend-password-setup`.  
- Break-glass: `POST /api/auth/break-glass-reset-owner-password`.

---

## 5) Conflicts Check (no speculation)

### a) Plan gating: plan_registry vs legacy

- **Evidence:**  
  - **plan_registry** is the single source of truth used by: `backend/middleware/feature_gating.py` (reads `billing_plan`, uses `plan_registry.resolve_plan_code` and `plan_registry.get_features`), and by routes in `documents.py`, `reports.py`, `client.py`, `calendar.py`, `webhooks_config.py` via `plan_registry.enforce_feature(...)`.  
  - **plan_gating** (`backend/services/plan_gating.py`): File is marked DEPRECATED; uses `BillingPlan.PLAN_1/PLAN_2_5/PLAN_6_15` and limits 1/5/15. **No route in the repo calls `plan_gating_service.enforce_feature`**; only `plan_registry.enforce_feature` is used in routes.  
  - **feature_entitlement** (`backend/services/feature_entitlement.py`): Uses same legacy `BillingPlan` and `PLAN_FEATURE_MATRIX` (1/5/15). **No route in the repo calls `feature_entitlement_service.enforce_feature`**; only `plan_registry.enforce_feature` is used.

- **Conflict:** No **runtime** conflict: all gated routes use plan_registry. Legacy code (plan_gating, feature_entitlement) is dead for enforcement. **Risk:** If someone later calls `plan_gating_service` or `feature_entitlement_service` without migrating to plan_registry, limits and features would be wrong (1/5/15 vs 2/10/25).

### b) Provisioning runner vs poller

- **Evidence:**  
  - **Webhook** (`backend/services/stripe_webhook_service.py`): On `checkout.session.completed` (subscription), creates/updates a row in `provisioning_jobs` with status PAYMENT_CONFIRMED and sets `needs_run=True`. It does **not** run the provisioning job itself.  
  - **Poller** (`backend/scripts/run_provisioning_poller.py`): Finds jobs with `needs_run=True` and lock not held (or expired), then calls `run_provisioning_job(job_id)`.  
  - **Runner** (`backend/services/provisioning_runner.py`): `run_provisioning_job(job_id)` acquires a job-level lock, runs `provisioning_service.provision_client_portal(client_id)`, then migrates intake uploads and sends password email; updates job to WELCOME_EMAIL_SENT.

- **Conflict:** None. Webhook only persists state; poller is the only process that runs jobs. Runner is invoked only by the poller (or by a manual script that calls `run_provisioning_job`). Lock in runner prevents two processes from running the same job.

### c) Email resend paths

- **Evidence:**  
  - **Route 1:** `backend/routes/admin.py`: `POST /api/admin/clients/{client_id}/resend-password-setup` → `resend_password_setup(request, client_id)`.  
  - **Route 2:** `backend/routes/admin_billing.py`: `POST /api/admin/billing/clients/{client_id}/resend-setup` → `resend_password_setup(request, client_id)` (same function name, different module).

- **Conflict:** Two **different URLs** expose resend: `/api/admin/clients/{id}/resend-password-setup` and `/api/admin/billing/clients/{id}/resend-setup`. Both require admin auth. Implementation may differ (admin.py vs admin_billing.py); the UI “Email delivery” Resend button calls the first (adminAPI.resendPasswordSetup in client.js → `/admin/clients/${id}/resend-password-setup`). No **logic** conflict identified; only dual entry points. Prefer one canonical endpoint for operations and docs.

### d) Document generation idempotency and failure records

- **Evidence:**  
  - **Stripe webhooks:** `backend/services/stripe_webhook_service.py`: By `event_id`, looks up `stripe_events`. If `status == "PROCESSED"`, returns “Already processed” and does not run handler again. Inserts/updates record with status PROCESSING, then PROCESSED or error. **Idempotent** per event_id.  
  - **Document orchestration:** `backend/services/document_orchestrator.py`: Uses `_compute_idempotency_key(...)`, stores in `orchestration_executions` with `idempotency_key`. On retry with same key, can skip or fail with “Previous run failed; use force=true to retry”. Failure records written with `idempotency_key` and status so retries are controlled.

- **Conflict:** None. Stripe events are idempotent by event_id; document runs are keyed by idempotency_key and failure is recorded so duplicate runs don’t silently overwrite.

---

**End of report. No code was changed.**
