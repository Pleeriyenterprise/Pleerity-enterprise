# Stripe-Gated Test Accounts Runbook

This runbook provisions **3 fully gated test accounts** (SOLO, PORTFOLIO, PROFESSIONAL) using the **real** flow: intake → Stripe checkout → webhook. No manual DB inserts, no admin overrides, no bypassing billing logic.

---

## STEP 1 — Pre-Check

Before creating accounts, confirm:

### 1.1 Stripe test mode

- Stripe Dashboard → ensure you are in **Test mode** (toggle top-right).
- Use **test** API keys in backend env (`STRIPE_SECRET_KEY` = `sk_test_...`).

### 1.2 Webhook endpoint active and reachable

- **Endpoint:** `POST /api/webhook/stripe` or `POST /api/webhooks/stripe`
- **Reachability:** Stripe must be able to reach your backend (e.g. ngrok for local: `ngrok http 8000`, then set Stripe webhook URL to `https://<ngrok-host>/api/webhook/stripe`).
- **Secret:** Set `STRIPE_WEBHOOK_SECRET` in env to the signing secret from Stripe Webhooks → your endpoint → Signing secret.

### 1.3 Webhook handler behaviour

The handler in `backend/services/stripe_webhook_service.py`:

- **checkout.session.completed** and **customer.subscription.created/updated**:
  - Update `db.clients`: `billing_plan`, `subscription_status`, `entitlement_status`, `entitlements_version`
  - Update `db.client_billing`: `current_plan_code`, `subscription_status`, `entitlement_status`, `entitlements_version` (incremented via `$inc`)
  - Write audit log with `action_type: "PLAN_UPDATED_FROM_STRIPE"` (and `STRIPE_EVENT_PROCESSED` for event tracking)
  - Only after webhook sets `subscription_status = ACTIVE` do features unlock

Verification:

- After a test checkout, query `db.clients` and `db.client_billing` for that `client_id`: `subscription_status` should be `ACTIVE`, `billing_plan` set, `entitlements_version` ≥ 1.
- Query `db.audit_logs` for `metadata.action_type: "PLAN_UPDATED_FROM_STRIPE"` for that client.

### 1.4 Feature gating middleware

- **Location:** `backend/middleware/feature_gating.py` — `require_feature(feature_key)`.
- Denied requests return **403** and create an audit log with `action_type: "PLAN_GATE_DENIED"`.
- Property limit enforcement: `backend/routes/properties.py` returns **403** with `PLAN_LIMIT_EXCEEDED` when at plan limit.

---

## STEP 2 — Create 3 test accounts (real flow)

Use **unique test emails**:

| Plan         | Email                      |
|-------------|-----------------------------|
| SOLO        | aigbochiev@gmail.com        |
| PORTFOLIO   | drjpane@gmail.com           |
| PROFESSIONAL| pleerityenterprise@gmail.com|

For **each** account:

### A) Intake submission

- **Endpoint:** `POST /api/intake/submit`
- **Body:** Valid `IntakeFormData` (see `backend/models/core.py`):
  - `full_name`, `email`, `client_type`, `preferred_contact`, `phone` (if SMS/BOTH)
  - `billing_plan`: `"PLAN_1_SOLO"` | `"PLAN_2_PORTFOLIO"` | `"PLAN_3_PRO"`
  - `properties`: list of at least one property (within plan limit: 1 for SOLO, up to 10 for PORTFOLIO, up to 25 for PRO)
  - `document_submission_method`, `email_upload_consent` (if EMAIL), `consent_data_processing: true`, `consent_service_boundary: true`

- **Response:** includes `client_id`. Use it for checkout.

### B) Create Stripe checkout

- **Endpoint:** `POST /api/intake/checkout?client_id=<client_id>`
- **Response:** `checkout_url` — open in browser (or use same origin for redirect).

### C) Complete Stripe test checkout

- **Card:** `4242 4242 4242 4242`
- **Expiry:** any future date (e.g. 12/34)
- **CVC:** any 3 digits (e.g. 123)

Complete payment. Stripe will send `checkout.session.completed` (and subscription events) to your webhook.

### D) Wait for webhook confirmation

- Ensure backend and webhook URL are running; wait a few seconds.
- Optionally check Stripe Dashboard → Developers → Webhooks → your endpoint → event list for successful delivery.

### E) Confirm DB state

For the `client_id`:

- **clients:** `subscription_status == "ACTIVE"`, `billing_plan` = chosen plan, `entitlements_version` ≥ 1.
- **client_billing:** same; `entitlements_version` incremented.

### F) Confirm correct plan

- SOLO → `billing_plan: "PLAN_1_SOLO"`
- PORTFOLIO → `billing_plan: "PLAN_2_PORTFOLIO"`
- PROFESSIONAL → `billing_plan: "PLAN_3_PRO"`

---

## STEP 3 — Seed sample data (post-activation only)

After `subscription_status == ACTIVE` and provisioning has run (user can log in):

### SOLO (max 2 properties)

- Create 2 properties via `POST /api/properties/create` (authenticated).
- Attempt 3rd property → must return **403** and audit `PLAN_LIMIT_EXCEEDED`.

### PORTFOLIO (max 10 properties)

- Create 10 properties.
- Attempt 11th → **403** (plan limit exceeded).

### PROFESSIONAL (max 25 properties)

- Create 25 properties.
- Attempt 26th → **403**.

---

## STEP 4 — Feature validation

Use the **plan_registry** feature matrix (`backend/services/plan_registry.py`):

| Feature            | SOLO | PORTFOLIO | PROFESSIONAL |
|---------------------|------|-----------|--------------|
| zip_upload          | 403  | allowed   | allowed      |
| reports_pdf         | 403  | allowed   | allowed      |
| reports_csv         | 403  | allowed   | allowed      |
| scheduled_reports   | 403  | allowed   | allowed      |
| webhooks            | 403  | 403       | allowed      |
| api_access          | 403  | 403       | allowed      |

- **SOLO:** Call zip_upload, PDF/CSV reports, scheduled reports, Advanced AI (if gated), API/Webhooks → expect **403** and audit `PLAN_GATE_DENIED`.
- **PORTFOLIO:** Bulk ZIP and scheduled reports allowed; Webhooks/API → **403**.
- **PROFESSIONAL:** All features allowed per matrix.

For each denied attempt: response **403**, audit log `PLAN_GATE_DENIED`, UI must not crash.

**Gated endpoints (examples):**

- Bulk ZIP: `POST /api/documents/upload-zip` (or equivalent) — gated by `zip_upload`
- PDF reports: reports routes gated by `reports_pdf`
- Scheduled reports: gated by `scheduled_reports`
- Webhooks: `GET/POST /api/webhooks` — gated by `webhooks`

---

## STEP 5 — Credentials (safe handling)

- **Do not** insert users directly into MongoDB; do not manually set `billing_plan` or `subscription_status`.
- Passwords are set via the **password-setup flow** (link sent after provisioning). For each test account:
  1. Generate a **secure random password** (e.g. 16+ chars, alphanumeric + symbols).
  2. Use the setup link from the welcome/password-set email to set that password (or admin “resend invite” if available).
  3. Store credentials in a **secure store** (e.g. password manager), not in server logs or repo.

Deliver to stakeholders:

- Email  
- Password (via secure channel)  
- Plan  
- subscription_status  
- entitlements_version  

**Do not log passwords in server logs.**

---

## STEP 6 — Verification output

Provide:

1. **Proof webhook processed**
   - Stripe event ID (from Stripe Dashboard or logs).
   - DB: `clients` and `client_billing` updated; `entitlements_version` incremented.
   - Audit: `PLAN_UPDATED_FROM_STRIPE` present for each account.

2. **List of endpoints tested for gating**
   - Property create (limit and over-limit).
   - zip_upload, reports_pdf, scheduled_reports, webhooks (and any other gated endpoints used).

3. **Confirmation**
   - No manual overrides: no direct MongoDB writes for `billing_plan` / `subscription_status`; no admin-only bypass used. Stripe and webhook are the source of truth.

---

## Verification script

After the 3 accounts are created and active, you can run:

```bash
cd backend
python scripts/verify_gated_test_accounts.py --emails aigbochiev@gmail.com,drjpane@gmail.com,pleerityenterprise@gmail.com
```

Options:

- `--emails` or `--client-ids`: identify the three test accounts.
- Script checks: `subscription_status`, `billing_plan`, `entitlements_version`; optionally property limits and gated endpoints (requires auth tokens or env with test user credentials). See script docstring for details.

---

## Commit

Use commit message:

```
test(seeding): provision 3 Stripe-backed gated test accounts
```
