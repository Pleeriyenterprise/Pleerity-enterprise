# Email Delivery Reliability Audit

Audit of password setup, payment received, and digest email flows: triggers, failure handling, user impact, and admin recovery. No code changes—findings and prioritized fix list only.

---

## 1. Password setup emails

### 1.1 What triggers them

| Trigger | Location | Path |
|--------|----------|------|
| Provisioning (direct) | After `provision_client_portal_core()` succeeds | `provisioning.py`: `_send_password_setup_link()` → `email_service.send_password_setup_email()` |
| Provisioning (job) | After job reaches PROVISIONING_COMPLETED, before WELCOME_EMAIL_SENT | `provisioning_runner.py`: `run_provisioning_job()` → `provisioning_service._send_password_setup_link()` |
| Job email retry | Poller picks job with status PROVISIONING_COMPLETED (email failed earlier) | `provisioning_runner.py`: same block, reuses `_send_password_setup_link()` |
| Admin resend | POST `/api/admin/clients/{client_id}/resend-password-setup` or `/api/admin/billing/clients/{client_id}/resend-setup` | `admin.py` / `admin_billing.py`: new token, then `email_service.send_password_setup_email()` |
| Job resend | POST `/api/admin/provisioning-jobs/{job_id}/resend-invite` (job must be PROVISIONING_COMPLETED) | `admin.py`: calls `run_provisioning_job(job_id)` which performs email-only retry |
| Script | `scripts/resend_portal_invite.py` | Direct call to `email_service.send_password_setup_email()` |

### 1.2 What happens on failure

- **Email service** (`email_service.send_email`): On exception, sets `message_log.status = "failed"`, `message_log.error_message`, logs with `logger.error`, persists to `message_logs`, creates audit `EMAIL_FAILED` with metadata (recipient, template, status, error). **Does not re-raise**; returns the `MessageLog`.
- **Direct provisioning** (`provisioning.py`): Catches exception from `_send_password_setup_link`, sets `client.last_invite_error`, creates audit `PORTAL_INVITE_EMAIL_FAILED`, returns success with message "Provisioning successful but invite email failed; use resend invite to retry".
- **Job runner** (`provisioning_runner.py`): On exception, sets `job.last_error` and `client.last_invite_error`, **does not** set job to FAILED; leaves status as PROVISIONING_COMPLETED so the poller can retry the email step.

### 1.3 Retry

- **Automatic:** Only in the **job flow**. When the provisioning poller runs and finds a job in PROVISIONING_COMPLETED, it performs an email-only retry (same `_send_password_setup_link`). No retry in the direct provisioning path or in admin resend.
- **Manual:** Admin resend endpoints and script; job resend-invite endpoint.

### 1.4 Can failures strand a user?

- **Job flow:** No. Job stays PROVISIONING_COMPLETED and is retried by the poller; admin can also use resend-invite.
- **Direct provisioning (no job):** Yes. If the invite email fails, the user has no link until an admin uses resend-password-setup or the script.

### 1.5 Admin actions to resend/recover

- **POST** `/api/admin/clients/{client_id}/resend-password-setup` (rate-limited 3/hour per client).
- **POST** `/api/admin/billing/clients/{client_id}/resend-setup`.
- **POST** `/api/admin/provisioning-jobs/{job_id}/resend-invite` (only when job status is PROVISIONING_COMPLETED).
- **GET** `/api/admin/clients/{client_id}/password-setup-link?generate_new=false|true` — view or generate link (no email sent).
- **Script:** `resend_portal_invite.py`.

**Gap:** Resend endpoints do not check the return value of `send_password_setup_email()` (which does not raise on failure). If the send fails, the API still returns success ("Password setup link resent"), so the admin may believe the email was sent when it was not.

---

## 2. Payment received emails

### 2.1 What triggers them

| Trigger | Location |
|--------|----------|
| Provisioning job | Only in **provisioning_runner.py**, immediately after the password setup email is sent successfully. Same try block: first `_send_password_setup_link()`, then `email_service.send_payment_received_email()`. |

Not sent from Stripe webhooks. Sent only as part of the job flow after welcome email succeeds.

### 2.2 What happens on failure

- Wrapped in its own try/except: `logger.warning(f"Job {job_id}: payment received email failed: {e}")`. No re-raise; job is still considered successful (status set to WELCOME_EMAIL_SENT).
- Under the hood, `send_email()` still writes to `message_logs` and creates `EMAIL_SENT` or `EMAIL_FAILED` audit, but the runner does not act on failure.

### 2.3 Retry

- None. No automatic or admin-triggered retry for payment received emails.

### 2.4 Can failures strand a user?

- No. The user has already received the password setup email and can log in. They simply do not get the payment confirmation email.

### 2.5 Admin actions to resend/recover

- **None.** There is no admin endpoint or script to resend the payment received email.

---

## 3. Payment failed emails (invoice.payment_failed)

### 3.1 What triggers them

- **Stripe webhook** `invoice.payment_failed`: `stripe_webhook_service._handle_invoice_payment_failed` → `email_service.send_payment_failed_email()`.

### 3.2 What happens on failure

- try/except around the send: `logger.error(f"Failed to send payment failed email: {e}")`. Webhook processing continues; subscription/entitlement state is still updated. No retry.

### 3.3 Retry

- None. Stripe may send the event again (webhook retries), but the handler is idempotent by event id; if the event was already processed, the email is not sent again.

### 3.4 Can failures strand a user?

- No. User can still use the portal; they just don’t get an email telling them payment failed. Risk is delayed awareness and possible service restriction (e.g. entitlement LIMITED) without clear notice.

### 3.5 Admin actions to resend/recover

- **None.** No admin action to resend the payment failed email.

---

## 4. Digest emails

### 4.1 Monthly compliance digest

**Trigger:** Scheduled job (e.g. 1st of month), `JobScheduler.send_monthly_digests()` → for each client `_send_digest_email(client, digest_content)`.

**Implementation:** `_send_digest_email()` **does not call `email_service.send_email()`**. It only:

1. Fires `fire_digest_sent()` webhook.
2. Inserts a raw document into `audit_logs` with `action: "DIGEST_SENT"` and metadata.

So **monthly digest emails are not sent through the application’s email service** (e.g. Postmark). The job still increments `digest_count` and writes to `digest_logs` as if sent. Comment in code: "In production, this would use the monthly-digest template."

**Failure / retry / strand:** N/A for “email delivery” because no email is sent. Webhook or audit insert failures are caught and logged.

**Admin recovery:** No resend; no real send in the first place.

### 4.2 Pending verification digest (admin)

**Trigger:** Scheduled job (e.g. daily 09:30 UTC), `JobScheduler.send_pending_verification_digest()` → for each OWNER/ADMIN `email_service.send_email(PENDING_VERIFICATION_DIGEST, ...)`.

**On failure:** Per-recipient try/except: `logger.warning(...)`, loop continues. One audit log at end with `recipient_count` (only successful sends). Failed recipients are not retried.

**Retry:** None automatic. Next run is the next day.

**Strand:** An admin could miss that day’s digest if their send failed; no way to “resend” that run.

**Admin recovery:** None. No endpoint to re-send the pending verification digest for a given date.

---

## 5. Cross-cutting: email service and logging

- **All sends** through `email_service.send_email()`:
  - Are logged to **`message_logs`** (status `sent` or `failed`, `error_message` if failed).
  - Trigger an **audit log** (`EMAIL_SENT` or `EMAIL_FAILED`) with recipient, template, status, postmark_id, error.
- **No application-level retry** (no backoff, no queue). Callers either retry themselves (e.g. job poller for password setup) or do not.

---

## 6. Prioritized fix list

| Priority | Issue | Recommendation |
|----------|--------|----------------|
| **P0** | Monthly digest does not send email | Implement actual send in `_send_digest_email()` using `email_service.send_email()` with `EmailTemplateAlias.MONTHLY_DIGEST` (or equivalent) and the computed digest content. Remove or update the "would use" comment. |
| **P0** | Admin resend reports success when email fails | After `send_password_setup_email()` in resend endpoints, check returned `MessageLog.status` (or have `send_email` raise on failure). Return 5xx or clear error to the admin if status is `"failed"`. |
| **P1** | Payment received email: no retry, no admin resend | Option A: Add a small retry (e.g. one immediate retry) in the runner on failure. Option B: Add admin-only “Resend payment confirmation” for a client (idempotent, e.g. last 24h). Option C: Both. |
| **P1** | Payment failed email: no retry, no admin resend | Consider idempotent retry (e.g. by invoice id) or admin “Resend payment failed notice” for a client when entitlement is LIMITED and last event was payment_failed. |
| **P2** | Pending verification digest: failed recipient not retried | Option A: Retry failed recipients once before moving on. Option B: Record failed recipients in audit metadata and/or a small table for manual or scripted resend. |
| **P2** | Direct provisioning path: no automatic retry for invite email | Document that “resend invite” is required, or introduce a delayed job (e.g. “send invite” job) that is retried by the same poller when provisioning is done without a checkout job. |
| **P3** | No central “email delivery” dashboard | Use existing `message_logs` (and optional aggregation) to expose failed count, last failure time, and link to resend actions where they exist. |

---

*Audit performed from codebase only; no runtime or Postmark configuration reviewed.*
