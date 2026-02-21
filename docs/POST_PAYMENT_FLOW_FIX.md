# Post-Payment Flow Fix – Root Cause, Changes, and Checklist

## 1. Root-Cause Report (Why the UI Was Stuck)

**Observed behaviour:** After a successful Stripe payment, the onboarding status page stayed on “Payment confirming…” and “Portal setup waiting…” and did not advance.

**Root causes identified from code and flow:**

1. **Webhook not received or not processing**
   - The portal status endpoint derives `payment_state` **only** from backend state: `clients.subscription_status` (and optionally job existence / client age). That state is updated **only** when the Stripe webhook runs (`checkout.session.completed`).
   - If the webhook URL was wrong, the signature secret mismatched (e.g. test vs live), or the request never reached the app (e.g. Render not exposed), the webhook did not run → `subscription_status` never became `ACTIVE` → `payment_state` stayed `confirming` or `unpaid` → UI stayed on “Confirming…” or “Action required”.

2. **Provisioning never ran (no worker)**
   - The webhook only creates/updates a `provisioning_jobs` record with `status=PAYMENT_CONFIRMED` and `needs_run=True`. A **separate process** (the provisioning poller script) is responsible for picking up those jobs and running `run_provisioning_job(job_id)`.
   - If Render (or the deployment environment) did not run the poller (e.g. no Background Worker service running `python -m scripts.run_provisioning_poller`), no process ever ran provisioning → job stayed `PAYMENT_CONFIRMED` → `onboarding_status` never became `PROVISIONED` → UI showed “Portal setup waiting…” indefinitely.

3. **Status and UI alignment**
   - The API and UI used different state shapes (e.g. uppercase vs lowercase, or different labels). The spec asked for a single machine-readable contract (`payment_state`, `provisioning_state`, `password_state`, `next_action`) and clear UI mapping (e.g. “Payment complete” only when `payment_state === 'paid'`). Aligning both ensures the page reflects real backend state.

**Summary:** The UI was stuck because (a) webhook handling/setup was not reliably updating client state and/or (b) provisioning was never executed because no worker was running, and (c) status/UI semantics were not fully aligned.

---

## 2. Files and Lines Changed

### A) Stripe webhook processing

| File | Change |
|------|--------|
| `backend/services/stripe_webhook_service.py` | **Webhook secret:** Use `_get_webhook_secret()` so test key uses `STRIPE_WEBHOOK_SECRET_TEST` and live key uses `STRIPE_WEBHOOK_SECRET_LIVE` (with fallback to `STRIPE_WEBHOOK_SECRET`). |
| Same | **Structured logs:** Immediately after signature verification, log `WEBHOOK_RECEIVED` with `event_id`, `event_type`, `livemode`, `client_id`, `subscription_id`, `checkout_session_id` (from `_extract_webhook_context`). |
| Same | On success: log `WEBHOOK_PROCESSED_OK` with `event_id`, `event_type`, `client_id`. On handler exception: log `WEBHOOK_PROCESSING_FAILED` with `event_id`, `event_type`, `error`. |
| Same | **Provisioning trigger:** After creating or re-dispatching a provisioning job, log `PROVISIONING_ENQUEUED client_id=… job_id=… checkout_session_id=…` and call `asyncio.create_task(_run_provisioning_after_webhook(job_id))` so provisioning can run in-process without a separate worker. |
| Same | **Helper:** `_run_provisioning_after_webhook(job_id)` at module level to run `run_provisioning_job(job_id)` in the background. |
| `backend/routes/webhooks.py` | When `process_webhook` returns `success=False` and `message == "Invalid signature"`, return **400** with detail `"Invalid webhook signature"` (so Stripe does not treat it as success). |

**Checkout session metadata:** Already set in `backend/services/stripe_service.py` in `create_checkout_session`: `metadata` includes `client_id` and `plan_code` (and optional `customer_reference`). No change required.

### B) Provisioning observability

| File | Change |
|------|--------|
| `backend/services/provisioning_runner.py` | After updating job to `PROVISIONING_STARTED`, log `PROVISIONING_STARTED job_id=… client_id=…`. |
| Same | When setting job to `WELCOME_EMAIL_SENT`, log `PROVISIONING_COMPLETED job_id=… client_id=…`. |

### C) Portal setup-status and UI

| File | Change |
|------|--------|
| `backend/routes/portal.py` | **State values:** `_payment_state` returns `unpaid` \| `confirming` \| `paid` (paid only when `subscription_status` in ACTIVE/PAID/TRIALING). `_provisioning_state` returns `not_started` \| `queued` \| `running` \| `completed` \| `failed` (e.g. `PAYMENT_CONFIRMED` → `queued`). `_password_state` returns `not_sent` \| `set`. `_next_action` returns `pay` \| `wait_provisioning` \| `set_password` \| `go_to_dashboard`. Response schema unchanged; values are now lowercase and include `queued`. |
| `frontend/src/pages/OnboardingStatusPage.js` | **Already aligned:** Polls `GET /api/portal/setup-status` every 5s for up to 180s; uses lowercase states; shows “Confirming…” only when `payment_state === 'confirming'`, “Payment complete” when `paid`, “Portal setup” when `provisioning_state` is `queued` or `running`; after 180s shows banner with CRN and support email `info@pleerityenterprise.co.uk`; “Refresh status” triggers an immediate poll. |
| `backend/tests/test_portal_setup_status.py` | Expectations updated to lowercase state values and `next_action` values (`go_to_dashboard`, `wait_provisioning`, `set_password`, `pay`); `provisioning_state` `queued` for job status `PAYMENT_CONFIRMED`. |

---

## 3. Stripe Test-Mode Webhook Configuration Checklist

Use this when configuring Stripe (test mode) so that the backend receives and processes events correctly.

- **Endpoint URL**
  - Use the URL where your backend is reachable by Stripe, for example:
    - `https://<your-backend-host>/api/webhook/stripe`
    - or `https://<your-backend-host>/api/webhooks/stripe` (alias).
  - Replace `<your-backend-host>` with your actual Render (or other) backend host. Stripe must be able to send POST requests to this URL.

- **Events to send**
  - **Required for subscription onboarding and provisioning:**
    - `checkout.session.completed` (primary trigger for payment confirmation and provisioning job creation).
  - **Recommended for billing and lifecycle:**
    - `customer.subscription.created`
    - `customer.subscription.updated`
    - `customer.subscription.deleted`
    - `invoice.paid`
    - `invoice.payment_failed`

- **Webhook signing secret**
  - In Stripe Dashboard: Developers → Webhooks → your endpoint → “Signing secret” (starts with `whsec_`).
  - In backend env:
    - **Test mode:** set `STRIPE_WEBHOOK_SECRET_TEST` to that signing secret (or set `STRIPE_WEBHOOK_SECRET` and the code will use it when a single secret is used).
    - **Live mode:** set `STRIPE_WEBHOOK_SECRET_LIVE` (or `STRIPE_WEBHOOK_SECRET`) for the live endpoint’s signing secret.
  - The app chooses the secret from the Stripe key prefix (`sk_test_` → test secret, `sk_live_` → live secret) when `STRIPE_WEBHOOK_SECRET_TEST` / `STRIPE_WEBHOOK_SECRET_LIVE` are set.

- **Verification**
  - After a test payment, in Render (or your) logs you should see:
    - `WEBHOOK_RECEIVED event_id=… event_type=checkout.session.completed … client_id=…`
    - `WEBHOOK_PROCESSED_OK event_id=… event_type=checkout.session.completed client_id=…`
    - `PROVISIONING_ENQUEUED client_id=… job_id=… checkout_session_id=…`
    - Then either `PROVISIONING_STARTED` and `PROVISIONING_COMPLETED` (if in-process task runs) or the same when the poller runs.

- **If events are not received**
  - Confirm the endpoint URL is correct and the backend is publicly reachable.
  - In Stripe Dashboard → Webhooks → your endpoint, check “Recent deliveries” for failures or non-2xx responses.
  - If you get 400 “Invalid webhook signature”, the signing secret in your env does not match the endpoint’s secret in the Dashboard (or test/live secret is mixed up).

- **Background worker (optional)**
  - Provisioning can run in-process after the webhook via `_run_provisioning_after_webhook`. If you still run the poller (e.g. on Render as a Background Worker), use:
    - Command: `cd backend && python -m scripts.run_provisioning_poller --max-jobs 10`
    - Run on a schedule (e.g. every 1–2 minutes) or as a long-running worker.
