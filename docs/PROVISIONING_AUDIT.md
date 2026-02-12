# Provisioning Flow Audit (No Behaviour Changes)

**Scope:** CVP subscription provisioning triggered by Stripe `checkout.session.completed`, plus idempotency, failure handling, email timing, and IntakeUploads migration hook.

---

## 1. End-to-end provisioning flow

### 1.1 Trigger conditions

- **Primary trigger:** Stripe webhook `checkout.session.completed` with `mode == "subscription"` (CVP subscription checkout).
- **Handler:** `StripeWebhookService._handle_checkout_completed` → `_handle_subscription_checkout`.
- **Preconditions for provisioning:**
  - `metadata.client_id` present (required; otherwise handler raises).
  - Subscription fetched from Stripe; `plan_code` resolved from subscription line items via `plan_registry.get_plan_from_subscription_price_id(price_id)`.
  - `entitlement_status == EntitlementStatus.ENABLED` (derived from `plan_registry.get_entitlement_status_from_subscription(subscription_status)`; typically `active` or `trialing` → ENABLED).
  - Client fetched; **`client.onboarding_status != "PROVISIONED"`**. If already PROVISIONED, provisioning is **not** called (only billing/client updates run).

**Other triggers (manual):**

- **Admin:** `admin.py` – manual “provision” action (e.g. after manual approval) calls `provisioning_service.provision_client_portal(client_id)`.
- **Admin billing:** `admin_billing.py` (two call sites) – e.g. after activating subscription or similar; same call.

### 1.2 Webhook-level idempotency

- **Event idempotency:** Before processing, the service looks up `stripe_events` by `event_id`.
  - If `status == "PROCESSED"`: handler is **not** run; returns “Already processed”.
  - If event exists with `FAILED` or `PROCESSING`: record is **overwritten** with `status: "PROCESSING"` and the handler **is run again** (retry path).
  - If event does not exist: insert with `PROCESSING`, then run handler.
- After **successful** handler run: event is updated to `status: "PROCESSED"`, `processed_at`, `related_client_id`, `related_subscription_id`.
- If handler **throws**: event is updated to `status: "FAILED"`, `error`, `processed_at`; webhook still returns 200 (Stripe will not retry for that event id unless reconfigured).

### 1.3 Ordering of actions (subscription checkout handler)

1. **Billing & client (always):**
   - Upsert `client_billing` (stripe customer/subscription, plan_code, entitlement_status, etc.).
   - Update `clients` (subscription_status, billing_plan, stripe_*, entitlement_status).
2. **Provisioning (only if entitlement_status == ENABLED and onboarding_status != PROVISIONED):**
   - `provisioning_service.provision_client_portal(client_id)` (see below).
3. **Payment-received email (only if entitlement ENABLED):**
   - `email_service.send_payment_received_email(...)` (recipient from `client.contact_email` or `metadata.email`; client_name from `client.contact_name` or “Valued Customer”). Sent **after** provisioning is attempted (success or failure).
4. **Audit:** `STRIPE_EVENT_PROCESSED` with plan_code, subscription_status, entitlement_status, `provisioning_triggered` (bool).

### 1.4 Ordering inside `provision_client_portal`

1. **Preconditions:** Client exists; `onboarding_status` in `[INTAKE_PENDING, PROVISIONING]`; in production, `subscription_status == ACTIVE` (in dev, PENDING allowed).
2. **STEP 1:** Set `clients.onboarding_status = PROVISIONING`; audit `PROVISIONING_STARTED`.
3. **STEP 2:** Load properties; if none → `_fail_provisioning` (set FAILED), return.
4. **STEP 3:** For each property, `_generate_requirements(client_id, property_id)`.
5. **STEP 4:** For each property, `_update_property_compliance(property_id)`.
6. **STEP 5:** Create PortalUser if none exists (by `client_id` + role CLIENT_ADMIN); idempotent (find one, else insert). Uses `client["email"]` as `auth_email`, `client["full_name"]` not stored on PortalUser.
7. **STEP 6:** Set `clients.onboarding_status = PROVISIONED`; audit `PROVISIONING_COMPLETE` with `portal_user_id`.
8. **Enablement:** Emit `PROVISIONING_COMPLETED` (swallowed on exception).
9. **STEP 7:** IntakeUploads migration: `migrate_intake_uploads_to_vault(client_id)` (swallowed on exception).
10. **STEP 8:** `_send_password_setup_link(client_id, user_id, client["email"], client["full_name"])` – creates password token, sends password-setup email. **No try/except** – if this throws, the whole `provision_client_portal` fails.

**“Already provisioned” detection:**

- At the **start** of `provision_client_portal`: if `onboarding_status` is **not** in `[INTAKE_PENDING, PROVISIONING]` (e.g. PROVISIONED or FAILED), the method returns `(True, "Already provisioned")` and does nothing else.
- So: PROVISIONED → skip. FAILED → also skip (no automatic retry from this method).

---

## 2. Idempotency

### 2.1 Webhook fires twice (same event_id)

- **First run:** Event inserted/updated to PROCESSING, handler runs, event updated to PROCESSED (or FAILED if error).
- **Second run:** Event found with status PROCESSED → handler **not** run; return “Already processed”. So **no double provisioning** for the same Stripe event.

### 2.2 Webhook fires twice (different event_ids for same checkout)

- Stripe normally sends one `checkout.session.completed` per checkout; event_id is unique per event. So “same checkout, two events” would be two different event_ids (e.g. retries with new ids). Then:
  - First event: runs handler, client becomes PROVISIONED, event PROCESSED.
  - Second event: handler runs again; client already PROVISIONED → `provision_client_portal` is still **called** (webhook doesn’t check PROVISIONED), but inside `provision_client_portal` the precondition fails (`onboarding_status != PROVISIONED`) so it returns “Already provisioned” and does nothing. So **safe**.

### 2.3 Provisioning partially failed

- **Failure before STEP 6:** e.g. STEP 2 (no properties), STEP 3/4 (requirement/compliance error), or STEP 5 (portal user insert error). Exception caught in `provision_client_portal` → `_fail_provisioning(client_id, reason)` → `onboarding_status = FAILED`. Client is left in FAILED; no PortalUser if failure was before STEP 5; no PROVISIONED.
- **Failure at STEP 8 (password email):** STEP 6 has already run, so `onboarding_status` was set to PROVISIONED. Then `_send_password_setup_link` throws → exception caught → `_fail_provisioning` runs → **overwrites** PROVISIONED to FAILED. Result: PortalUser exists, requirements/compliance/dashboard and intake migration (STEP 7) are done, but client record says FAILED and user never got the password email. **Recovery:** Admin would need to re-trigger provisioning; but `provision_client_portal` treats FAILED as “already provisioned” and returns without doing anything, so **password email is never re-sent** and there is no built-in path to “resend password setup only.”

---

## 3. Failure points and recovery paths

| Failure point | Client state | PortalUser | Recovery path |
|---------------|-------------|------------|----------------|
| No properties (STEP 2) | FAILED | No | Add properties, then **manual** provision (admin/admin_billing) – works because status is FAILED and precondition allows only INTAKE_PENDING/PROVISIONING; FAILED will currently **not** be retried (returns “Already provisioned”). So actually **admin manual provision** is called with client in FAILED; precondition rejects FAILED → no retry. **Gap.** |
| Requirement/compliance error (STEP 3/4) | FAILED | No | Fix data/rules; manual provision – same gap as above (FAILED not re-entered). |
| Portal user create (STEP 5) | FAILED | No | Retry manual provision – same. |
| Intake migration (STEP 7) | N/A (inside try/except) | Yes | Migration failure is logged; client still PROVISIONED. **Recovery:** `scripts/retry_intake_upload_migration.py` by client_id. |
| Password email (STEP 8) | FAILED (overwrites PROVISIONED) | Yes | Portal is usable but client shows FAILED; user has no password email. **No automatic or one-click recovery:** calling `provision_client_portal` again does nothing (FAILED treated as already provisioned). Would need either a “resend password setup” admin action or a special path to re-run only STEP 8 / allow provisioning to run again when FAILED. |

**Webhook handler exception:** If *any* part of `_handle_subscription_checkout` throws (e.g. Stripe API call, DB error), the event is marked FAILED; Stripe gets 200 so it won’t retry the same event. Client may be mid-update (billing updated but provisioning not started, or provisioning started and client PROVISIONING/FAILED). No automatic retry; support would rely on manual reprovision or fixing data and manual trigger.

---

## 4. Email timing

### 4.1 Password setup email

- **When:** Sent in **STEP 8**, after: PortalUser exists (STEP 5), onboarding_status set to PROVISIONED (STEP 6), enablement event (optional), IntakeUploads migration (STEP 7).
- **Ordering:** So password setup email is sent only after the portal user exists and the dashboard is fully set up (properties, requirements, compliance, migration). **Correct.**

### 4.2 If password setup email sending fails

- **Behaviour:** `_send_password_setup_link` is not in a try/except inside provisioning. So the exception propagates → `provision_client_portal`’s except runs → `_fail_provisioning(client_id, str(e))` → client set to **FAILED**.
- **Consequence:** Portal is actually ready (PortalUser, requirements, compliance, possibly migrated intake uploads), but the client is marked FAILED and the user never receives the setup link. Re-running provisioning (e.g. from admin) does nothing because FAILED is treated as “already provisioned.” **Risk.**

### 4.3 Payment received email

- Sent by the **webhook handler** after `provision_client_portal` returns (success or failure). Uses `client.contact_email` or `metadata.email`. If the client document has only `email` (e.g. intake-created) and no `contact_email`, the fallback `metadata.get("email", "")` is used – **provided** the checkout metadata included it. Otherwise recipient could be empty. Minor inconsistency: intake Client model has `email` / `full_name`; webhook and some jobs use `contact_email` / `contact_name`.

---

## 5. Safe hook for IntakeUploads → vault migration

- **Current hook:** Inside `provision_client_portal`, **STEP 7**, after STEP 6 (PROVISIONED) and before STEP 8 (password email).
  - Calls `migrate_intake_uploads_to_vault(client_id)`.
  - Wrapped in try/except; migration errors are logged and do not fail provisioning.
- **Safety:** Migration runs only after the client is marked PROVISIONED and the portal user exists; it is idempotent (only CLEAN, not already migrated). So the hook is in a **safe** place: dashboard and user are ready; migration is best-effort and does not block provisioning success.
- **Manual retry:** `backend/scripts/retry_intake_upload_migration.py` runs the same migration by `client_id` for support when provisioning succeeded later or migration failed during STEP 7.

---

## 6. Risks and inconsistencies (summary)

1. **FAILED clients never re-enter provisioning:** Precondition only allows `INTAKE_PENDING` or `PROVISIONING`. So if client is FAILED (e.g. no properties, or password email failed), calling `provision_client_portal` again returns “Already provisioned” and does nothing. No automatic or single-call recovery for FAILED.
2. **Password email failure marks client FAILED and is unrecoverable via provisioning:** STEP 8 failure overwrites PROVISIONED to FAILED; portal is actually ready but user has no setup link; re-calling provisioning does not resend the email.
3. **Payment received email sent even when provisioning failed:** User may get “your portal is ready” while onboarding_status is FAILED and they have no access (e.g. no properties).
4. **Client email/name fields:** Provisioning uses `client["email"]` and `client["full_name"]`; webhook payment email uses `contact_email` / `contact_name`. Intake-created clients may only have `email`/`full_name`; if `contact_email` is not set, fallback to `metadata.email` is used. Inconsistent field usage.
5. **Enablement event uses `client.get("plan_code")`:** Client model has `billing_plan`; `plan_code` may be missing on intake-created clients (only `billing_plan` set). May result in None passed to enablement.

---

## 7. Recommended tweaks (minimal; do NOT implement yet)

1. **Allow re-entry for FAILED when manually provisioning:** In `provision_client_portal`, allow `onboarding_status == FAILED` in the precondition when called from an explicit “retry” path (e.g. admin), or add a separate “retry failed provisioning” that clears FAILED to PROVISIONING and re-runs. Alternatively, treat FAILED as “can retry” and only treat PROVISIONED as “already provisioned.”
2. **Isolate password email from full failure:** Wrap STEP 8 in try/except: on failure, log and optionally set a flag (e.g. `password_email_pending`) or leave status PROVISIONED, and do not call `_fail_provisioning`. Add an admin or support action “Resend password setup email” that only sends the setup link for an existing PortalUser.
3. **Send payment received email only when provisioning succeeded:** Move or gate the payment-received email so it is sent only when `provisioning_triggered and success` (or when client is PROVISIONED after the call), to avoid “portal ready” when the user is actually FAILED.
4. **Normalise client contact fields:** Ensure intake and any client creation set `contact_email`/`contact_name` from `email`/`full_name` if not already set, and/or have the webhook use `client.get("contact_email") or client.get("email")` (and same for name) so payment emails always have a recipient.
5. **Enablement plan_code:** Use `client.get("billing_plan") or client.get("plan_code")` when emitting PROVISIONING_COMPLETED so plan is always passed when available.

---

**Document version:** 1.0 (audit only; no code changes).
