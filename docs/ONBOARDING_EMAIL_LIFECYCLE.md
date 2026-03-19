# Onboarding / payment email lifecycle — audit & implementation plan

**Status:** **Implemented** in backend (payment → activation → dashboard-ready → 7-day sequence; activation reminders). Existing DB `email_templates` rows for `payment-receipt` are **bypassed** when the Stripe webhook sends `payment_receipt_layout: structured` (canonical code-built receipt).

**Related docs:** `docs/LANDLORD_ONBOARDING_EMAIL_SEQUENCE_AUDIT.md`, `backend/docs/POSTMARK_TWILIO_PROVISIONING_CONFIRMATION.md`, `docs/ONBOARDING_STATUS_FIELDS.md`.

---

## 1. Target lifecycle (product requirement)

| Order | Trigger (conceptual) | Purpose |
|-------|----------------------|---------|
| **Email 1** | `payment_confirmed` | Payment received; reassurance; what happens next |
| **Email 2** | `account_created_and_activation_available` | Welcome + **set password** CTA (only when token/link ready) |
| **Email 3** | `password_set_successfully` (or first login) | Dashboard **actually** usable; first steps |
| **Email 4 (optional)** | `password_not_set_after_delay` | Reminder to activate; no “dashboard ready” copy |

---

## 2. Exact root cause of wrong order today

### 2.1 Parallel paths and misleading copy

1. **`checkout.session.completed` (Stripe webhook)** — `backend/services/stripe_webhook_service.py`  
   - Enqueues / starts provisioning with `asyncio.create_task(_run_provisioning_after_webhook(job_id))` **without awaiting** completion.  
   - Then **synchronously** sends **`SUBSCRIPTION_CONFIRMED`** with subject **"Payment received - Compliance Vault Pro"** and **`portal_link`: `{base_url}/app/dashboard`** (`~603–629`).  
   - So the **payment** email can arrive **before** the portal user and password token exist, and it **points users at the dashboard** before they can log in.

2. **Provisioning runner** — `backend/services/provisioning_runner.py`  
   - After core provisioning, sends **password setup** via `provisioning_service._send_password_setup_link` (uses orchestrator **`template_key="WELCOME_EMAIL"`** — naming is confusing: it is **activation / set-password**, not a post-login welcome).  
   - On success, calls **`schedule_onboarding_sequence(client_id)`** (`~311–318`).

3. **7-day onboarding queue** — `backend/services/onboarding_sequence_service.py`  
   - **`OFFSET_HOURS = (0, 24, 48, …)`** — **Day 0 is due immediately** (`send_at = now`).  
   - **`ONBOARDING_DAY0_WELCOME`** body in `email_service._get_onboarding_content` says **“Your portal is ready”** and pushes users to **add a property** (`~68–72`).  
   - That is **semantically “dashboard/portal ready”** even though the user may **not have set a password yet**.  
   - The queue processor runs on a **schedule** (`onboarding_sequence_processing` job); delivery order vs the password email is **not guaranteed** — Postmark can deliver **Day 0 before or after** the set-password email.

### 2.2 Summary

The wrong order **(payment → “dashboard/portal ready” → set password)** is caused by:

- **Payment email** sent at end of webhook **without** waiting for activation readiness, and includes a **dashboard URL**.  
- **Day 0 onboarding** email content claiming **portal is ready** and firing at **t+0h**, **not** gated on `password_set` / first login.  
- **Race** between provisioning’s password email and the **immediate** Day 0 queue item.

This is **not** primarily caused by `APP_BASE_URL` / URL validation (those affect link bases, not ordering).

---

## 3. What is already implemented vs missing

| Area | Implemented | Missing / gap |
|------|-------------|----------------|
| Payment acknowledgement | `SUBSCRIPTION_CONFIRMED` from Stripe webhook | Not structured as a full “receipt” (amount is plan summary string; limited Stripe receipt/invoice fields); dashboard link is premature |
| Set-password send | `_send_password_setup_link` → `WELCOME_EMAIL` template_key | Template/registry name **`WELCOME_EMAIL`** collides with product language “welcome”; should be conceptually **activation** only |
| “Dashboard ready” | **`PORTAL_READY`** exists in `email_service` | **Not** wired as the milestone email after password in the provisioning path (grep shows no orchestrator sends for `PORTAL_READY` in provisioning flow) |
| Milestone after password | Password change confirmation uses “View your dashboard” | **No** dedicated “dashboard ready / first steps” email **gated** on `PASSWORD_SET_SUCCESS` or first login |
| Reminder if no password | `ONBOARDING_DAY1_SETUP_REMINDER` exists in 7-day sequence | **Not** the same as “activation reminder”: copy is generic setup, not **set-password CTA**; may **overlap** if you add Email 4 without cancelling/adjusting Day 1 |
| State tracking | `provisioning_jobs` statuses; `clients.activation_email_*`; audit `PASSWORD_SET_SUCCESS` | **No** single `onboarding_email_lifecycle` state machine with `dashboard_ready_email_sent`, etc. |
| Duplicate prevention | Orchestrator `idempotency_key`; queue item ids | Day 0 + payment + password use **different** keys — good for dedupe per channel, but **no** cross-template “don’t send dashboard-ready before password” guard |
| Receipt / invoice | Attachments supported in orchestrator (`context["attachments"]`) | **No** documented flow for generating/storing PDF receipts or signed download links for subscription checkout |
| Observability | `message_logs`, audit logs for activation | **No** single checklist of lifecycle events in one doc/query for support |
| Template unification | `build_customer_email_layout` / onboarding branch | **SUBSCRIPTION_CONFIRMED** may render from **DB `email_templates`** by alias — can **diverge** from code-built onboarding templates |

---

## 4. Conflicting instructions & safest approach

### 4.1 Conflict: new 4-email lifecycle vs existing 7-day sequence

- **Existing:** 8 queued emails (`ONBOARDING_DAY0` … `DAY7`) triggered at **`WELCOME_EMAIL_SENT`** (actually: right after password-setup email succeeds).  
- **Requested:** Distinct **activation reminder** (Email 4) and **dashboard-ready** only after password.

**Risk:** Implementing Email 4 as a new job **without** adjusting Day 0/Day 1 produces **duplicate** “complete setup” messaging.

**Recommendation (professional / safest):**

1. Treat **Emails 1–3** as the **strict lifecycle gate** (payment → activation → dashboard milestone).  
2. **Reschedule or rewrite Day 0**: do **not** send “portal is ready” until **`password_set` or first successful login** (or **remove Day 0** and fold milestone into Email 3).  
3. Map **Email 4** to **either** a dedicated `ACTIVATION_REMINDER` template **or** repurpose **`ONBOARDING_DAY1_SETUP_REMINDER`** with copy/CTA strictly **set-password** (and **skip** if password already set).  
4. Document **one** owner for “reminder” logic to avoid two systems sending similar emails.

### 4.2 Conflict: trigger dashboard-ready on `password_set` vs `first_login`

- **Password set** is **synchronous** with the activation API and is **already audited** (`PASSWORD_SET_SUCCESS`).  
- **First login** can differ if you ever allow **SSO** or magic links later; today portal is password-centric.

**Recommendation:** Prefer **`PASSWORD_SET_SUCCESS`** (or portal_user `password_status == SET`) as the **authoritative** trigger for Email 3, with **optional** fallback to first `USER_LOGIN_SUCCESS` only if product requires “first login” for legal/UX reasons. Document the choice in code comments.

### 4.3 Receipt: PDF attachment vs signed link

- **Attachments:** Orchestrator already supports Postmark attachments; risk is **generation failure** blocking send, **size**, and **no central store** for re-download unless you add storage.  
- **Signed link:** Fits existing **portal + documents** patterns better: generate **short-lived or revocable** URL, store receipt metadata on `client_billing` or `orders`, serve from authenticated or token route.

**Recommendation:** **Phase 1 — receipt link** in payment email (even if link goes to a simple “billing” page placeholder); **Phase 2 — optional PDF** once storage and idempotent generation exist. **Do not** block email send on PDF generation in Phase 1.

---

## 5. Corrected trigger sequence (proposed)

1. **`payment_confirmed`**  
   - Send **Email 1** (`SUBSCRIPTION_CONFIRMED` or renamed `PAYMENT_RECEIPT`).  
   - **Remove or replace** premature `portal_link` to dashboard with **neutral** “next you’ll receive an email to activate your account” (or link only to **marketing**/help, not `/app/dashboard`).

2. **`activation_link_ready`** (after portal user + token persisted)  
   - Send **Email 2** (keep orchestrator path; consider renaming template_key / alias to **`CLIENT_ACTIVATION`** in DB for clarity — **migration** of `notification_templates` + `email_templates` required).

3. **`password_set_success`**  
   - Send **Email 3** (use **`PORTAL_READY`** or new alias **`DASHBOARD_READY_FIRST_STEPS`** with milestone copy).  
   - **Do not** send based on `provisioning_jobs` alone.

4. **`password_not_set_after_delay`**  
   - Send **Email 4**; gate on `password_status != SET` and **suppress** if Email 2 never succeeded (optional: different copy for “payment without activation email”).

5. **7-day sequence**  
   - Start **after** Email 3 **or** after first login — **not** immediately after Email 2. Alternatively keep start after Email 2 but **change Day 0** to non–“portal ready” content (e.g. product education only).

---

## 6. Files likely to change in a future implementation

| File | Role |
|------|------|
| `backend/services/stripe_webhook_service.py` | Payment email content, ordering vs provisioning, receipt fields |
| `backend/services/provisioning_runner.py` | When to call `schedule_onboarding_sequence`; optional lifecycle flags |
| `backend/services/onboarding_sequence_service.py` | Offsets, gating on password_set, Day 0 copy |
| `backend/services/provisioning.py` | `_send_password_setup_link` template_key / context |
| `backend/routes/auth.py` (or password-setup route) | Fire Email 3 on successful password set |
| `backend/services/email_service.py` | Copy, greetings, unified layout branches |
| `backend/services/notification_orchestrator.py` | Only if new gating or render path needed |
| `backend/database.py` (seeds) | `notification_templates` / `email_templates` rows |
| New small module (optional) | `onboarding_email_lifecycle.py` — central state + idempotency keys |

---

## 7. Duplicate / contradictory send prevention (proposed)

Store on `clients` or a dedicated `onboarding_lifecycle` subdocument:

- `payment_email_sent_at`  
- `activation_email_sent_at`  
- `dashboard_ready_email_sent_at`  
- `activation_reminder_sent_at` (and optional `activation_reminder_final_at`)  
- `password_set_at` (may already be inferable from `portal_users`)

Enforce: **Email 3** only if `password_set_at` set and `dashboard_ready_email_sent_at` unset.  
Enforce: **Email 4** only if activation sent, password not set, reminder not yet sent, and delay elapsed.

---

## 8. Observability (proposed)

Extend audit / structured logs (or `message_logs` queries) for:

- `ONBOARDING_LIFECYCLE_PAYMENT_EMAIL`  
- `ONBOARDING_LIFECYCLE_ACTIVATION_EMAIL`  
- `ONBOARDING_LIFECYCLE_DASHBOARD_READY_EMAIL`  
- `ONBOARDING_LIFECYCLE_ACTIVATION_REMINDER`  
- `ONBOARDING_LIFECYCLE_RECEIPT_GENERATED` (if applicable)

---

## 9. Template unification (proposed)

- Ensure **`SUBSCRIPTION_CONFIRMED`** uses the same **customer layout** pipeline as onboarding (or consciously document why it uses a different Postmark/DB template).  
- Standardise **greeting**: one helper `format_email_greeting(full_name, email)` → “Hello {first_name}” / “Hello” fallback — fix **“Hi ,”** by never passing empty `client_name`.  
- Single **footer** (support email, company name, preferences link policy) via `build_customer_email_layout`.

---

## 10. Deliverables checklist (implementation)

- [x] Root cause addressed: payment email no longer links to dashboard before activation; Day 0 queue starts **after** password set.  
- [x] Email 3 (`DASHBOARD_READY`) trigger: **`PASSWORD_SET_SUCCESS`** path in `auth.set_password` → `send_dashboard_ready_and_start_sequence`.  
- [x] Receipt: **structured HTML/text** in-app (no PDF attachment); no durable download URL yet (see limitations).  
- [x] `payment-receipt` + `portal-ready` (milestone) + `activation-reminder` use **code-built** layout when flags set (`notification_orchestrator._render_email`).  
- [x] Activation reminders: job `activation_reminder_processing` every 6h; env `ACTIVATION_REMINDER_HOURS_FIRST` (default 24), `ACTIVATION_REMINDER_HOURS_FINAL` (default 72).  
- [x] Client fields (ISO timestamps): `onboarding_payment_confirmation_email_sent_at`, `onboarding_dashboard_ready_email_sent_at`, `onboarding_activation_reminder_sent_at`, `onboarding_activation_reminder_final_sent_at`.  
- [x] Audit: `ONBOARDING_PAYMENT_CONFIRMATION_EMAIL_SENT`, `ONBOARDING_DASHBOARD_READY_EMAIL_SENT`, `ONBOARDING_ACTIVATION_REMINDER_SENT`.

### Key files

| Area | File |
|------|------|
| Payment email | `backend/services/stripe_webhook_service.py` |
| Receipt layout | `backend/services/email_service.py` (`PAYMENT_RECEIPT`), `notification_orchestrator.py` |
| Sequence start | `backend/services/onboarding_lifecycle_service.py` |
| After password | `backend/routes/auth.py` |
| No sequence at provision | `backend/services/provisioning_runner.py` |
| Reminder send + token | `backend/services/provisioning.py` (`send_activation_reminder_email`) |
| Templates seed | `backend/database.py` (`DASHBOARD_READY`, `ACTIVATION_REMINDER`) |
| Scheduler | `backend/server.py`, `backend/job_runner.py` |

### Limitations / follow-up

- **PDF receipt / signed download URL** not implemented; Stripe Customer Portal or a dedicated `/api/billing/receipt` can be added later.  
- **DB `email_templates` for `payment-receipt`**: ignored for subscription checkout when `payment_receipt_layout=structured` is sent.  
- **Admin invite** password flow does not send `DASHBOARD_READY` (client_id `ADMIN_INVITE` skipped).

---

*Last updated: implementation pass (lifecycle service, webhook, auth, provisioning, orchestrator, jobs).*
