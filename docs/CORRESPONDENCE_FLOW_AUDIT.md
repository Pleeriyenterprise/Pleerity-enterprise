# Correspondence / Email Flow Inventory (Audit)

**Date:** 2026-02  
**Scope:** Backend email and correspondence flows triggered by jobs, webhooks, and admin actions.

---

## 1. Email service and templates

- **Service:** `backend/services/email_service.py` – `EmailService` uses Postmark (`POSTMARK_SERVER_TOKEN`). Templates can be DB-driven (`email_templates` collection, alias + `html_body`/`text_body`/`subject`) or built-in (`_build_html_body` / `_build_text_body` by `EmailTemplateAlias`).
- **Template aliases:** `backend/models/core.py` – `EmailTemplateAlias` enum: PASSWORD_SETUP, PORTAL_READY, MONTHLY_DIGEST, ADMIN_MANUAL, REMINDER, COMPLIANCE_ALERT, TENANT_INVITE, SCHEDULED_REPORT, ADMIN_INVITE, AI_EXTRACTION_APPLIED, PAYMENT_RECEIVED, PAYMENT_FAILED, RENEWAL_REMINDER, SUBSCRIPTION_CANCELED, ORDER_DELIVERED, PENDING_VERIFICATION_DIGEST, CLEARFORM_WELCOME, etc.
- **Storage:** `message_logs` (or equivalent) for send status; audit logs where applicable.

---

## 2. Scheduled / job-triggered flows

| Flow | Trigger | Entry point | Template(s) | Notes |
|------|--------|-------------|-------------|--------|
| Daily reminders | Cron (e.g. 09:00 UTC) | `job_runner.run_daily_reminders()` → `JobScheduler.send_daily_reminders()` | REMINDER | Expiry reminders for requirements. |
| Monthly digest | Cron (1st of month) | `job_runner.run_monthly_digests()` → `JobScheduler.send_monthly_digests()` | MONTHLY_DIGEST | Counts-only digest to client/owner. |
| Pending verification digest | Cron (e.g. 09:30 UTC) | `JobScheduler.send_pending_verification_digest()` | PENDING_VERIFICATION_DIGEST | Daily digest of docs awaiting verification (counts only). |
| Compliance status change alerts | Cron (08:00, 18:00 UTC) | `job_runner.run_compliance_status_check()` → `JobScheduler.check_compliance_status_changes()` | COMPLIANCE_ALERT | On property compliance status change. |
| Scheduled reports | Hourly | `job_runner.run_scheduled_reports()` → `send_scheduled_reports()` | SCHEDULED_REPORT | Per-client report schedule. |
| Renewal reminders | Daily job | `JobScheduler` renewal job | RENEWAL_REMINDER | 7 days before subscription renewal. |

---

## 3. Event / webhook-triggered flows

| Flow | Trigger | Entry point | Template(s) | Notes |
|------|--------|-------------|-------------|--------|
| Payment received | Stripe `checkout.session.completed` | `stripe_webhook_service._handle_subscription_checkout`; provisioning runner | PAYMENT_RECEIVED | After payment confirmation; before/with provisioning. |
| Payment failed | Stripe `invoice.payment_failed` | `stripe_webhook_service._handle_payment_failed` | PAYMENT_FAILED | admin_billing.py also sends. |
| Subscription canceled | Stripe `customer.subscription.deleted` | `stripe_webhook_service._handle_subscription_deleted` | SUBSCRIPTION_CANCELED | Cancellation confirmation. |
| Order delivered | Order delivery pipeline | `order_delivery_service` | ORDER_DELIVERED | When order moves to delivered. |

---

## 4. Admin / provisioning flows

| Flow | Trigger | Entry point | Template(s) | Notes |
|------|--------|-------------|-------------|--------|
| Password setup | Admin resend / provisioning | `admin.resend_password_setup`, `provisioning._send_password_setup_link`, `provisioning_runner` | PASSWORD_SETUP | Portal invite link. |
| Portal ready | After provisioning | `provisioning` / email_service | PORTAL_READY | Post-provisioning welcome. |
| Admin manual message | Admin sends message to client | `admin` message endpoint | ADMIN_MANUAL | Custom admin-to-client. |
| Admin invite | Admin invites (client/admin) | `admin_invite_client`, admin invite flows | ADMIN_INVITE | Invitation email. |
| AI extraction applied | Document AI extraction | `documents.send_ai_extraction_email` | AI_EXTRACTION_APPLIED | Notify when extraction applied. |

---

## 5. Other flows

| Flow | Trigger | Entry point | Template(s) | Notes |
|------|--------|-------------|-------------|--------|
| Tenant invite | Client invites tenant | `client` tenant invite | TENANT_INVITE | Tenant portal invite. |
| ClearForm welcome | ClearForm auth/signup | `clearform/routes/auth` | CLEARFORM_WELCOME | ClearForm-specific. |
| Custom notification | Admin action | `admin_orders.send_custom_notification` | Custom | One-off notifications. |

---

## 6. API / routes involved

- **Templates CRUD:** `routes/templates.py` – manage `email_templates` (alias, subject, html_body, text_body).
- **Email delivery log (admin):** `admin_billing` or admin email-delivery endpoint – list recent sends.
- **Postmark:** All sending via `email_service` → Postmark client; no send when `POSTMARK_SERVER_TOKEN` unset (logged only).

---

## 7. Manual test checklist (after changes)

- [ ] Admin → Lead Management → open page, click **New Lead** → Create Lead dialog opens; no "Something went wrong"; filters and create form render.
- [ ] Admin → Prompt Manager → **New Prompt** → Service Code and Document Type dropdowns show options (or "No services configured yet" when empty).
- [ ] Admin → Prompt Manager → **Seed defaults** (when no prompts) → list refreshes with seeded templates.
- [ ] Admin Dashboard → Overview and Pending verification load without crashing; refresh works.
- [ ] Send a test reminder/digest (Jobs tab → Run Now for daily/monthly) → toast shows job-specific message.
