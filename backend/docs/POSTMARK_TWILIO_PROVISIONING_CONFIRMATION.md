# Postmark + Twilio Wiring & Provisioning-Safety Confirmation

Code-based verification. All call sites checked.

---

## A) Wired paths (flow → template_key → channel → orchestrator method)

| Flow | template_key | Channel | Orchestrator path | Call site (file:line) |
|------|--------------|---------|-------------------|------------------------|
| Provisioning welcome / password setup | WELCOME_EMAIL | EMAIL | `notification_orchestrator.send` → `_send_email` | `provisioning.py:502` (`_send_password_setup_link`) |
| Admin resend password setup | WELCOME_EMAIL | EMAIL | `notification_orchestrator.send` → `_send_email` | `admin.py:1106`, `admin_billing.py:670` |
| Stripe: subscription confirmed | SUBSCRIPTION_CONFIRMED | EMAIL | `notification_orchestrator.send` → `_send_email` | `stripe_webhook_service.py:524` |
| Stripe: payment failed | PAYMENT_FAILED | EMAIL | `notification_orchestrator.send` → `_send_email` | `stripe_webhook_service.py:979` |
| Stripe: subscription canceled | SUBSCRIPTION_CANCELED | EMAIL | `notification_orchestrator.send` → `_send_email` | `stripe_webhook_service.py:786` |
| Daily compliance reminder (email) | COMPLIANCE_EXPIRY_REMINDER | EMAIL | `notification_orchestrator.send` → `_send_email` | `jobs.py:255` |
| Daily compliance reminder (SMS, Pro) | COMPLIANCE_EXPIRY_REMINDER_SMS | SMS | `notification_orchestrator.send` → `_send_sms` | `jobs.py:291` |
| Monthly digest | MONTHLY_DIGEST | EMAIL | `notification_orchestrator.send` → `_send_email` | `jobs.py:343` |
| Pending verification digest | PENDING_VERIFICATION_DIGEST | EMAIL | `notification_orchestrator.send` → `_send_email` | `jobs.py:400` |
| Scheduled reports | SCHEDULED_REPORT | EMAIL | `notification_orchestrator.send` → `_send_email` | `jobs.py:724`, `reporting.py:939` |
| Compliance SLA alert (ops) | COMPLIANCE_SLA_ALERT | EMAIL | `notification_orchestrator.send` → `_send_email` | `compliance_sla_monitor.py:57` |
| Notification failure spike (ops) | OPS_ALERT_NOTIFICATION_SPIKE | EMAIL | `notification_orchestrator.send` → `_send_email` | `notification_failure_spike_monitor.py:131` |
| Provisioning failed admin | PROVISIONING_FAILED_ADMIN | EMAIL | `notification_orchestrator.send` → `_send_email` | `provisioning_runner.py:49` |
| Stripe webhook failure admin | STRIPE_WEBHOOK_FAILURE_ADMIN | EMAIL | `notification_orchestrator.send` → `_send_email` | `webhooks.py:43` (async task) |
| OTP send (enterprise) | OTP_CODE_SMS | SMS | `notification_orchestrator.send` → `_send_sms` | `otp_service.py:202` |
| Admin manual email | ADMIN_MANUAL / WELCOME_EMAIL / etc. | EMAIL | `notification_orchestrator.send` → `_send_email` | `admin.py:1647`, `admin_billing.py:932`, etc. |
| Admin manual / test SMS | ADMIN_MANUAL_SMS | SMS | `notification_orchestrator.send` → `_send_sms` | `admin.py:1682`, `sms.py:272` (test-send) |
| Support, leads, enablement, orders, etc. | Various | EMAIL/SMS | `notification_orchestrator.send` | `support_email_service.py`, `lead_service.py`, `lead_followup_service.py`, `enablement_service.py`, `order_delivery_service.py`, `order_notification_service.py`, `documents.py`, `client.py`, `partnerships.py`, `clearform/routes/auth.py`, `scripts/resend_portal_invite.py`, etc. |

All production email and SMS sends identified above go through `notification_orchestrator.send`; the only actual Postmark call is `notification_orchestrator._send_email` (line 536). The only actual Twilio call for app/OTP SMS is `notification_orchestrator._send_sms` (lines 646–648), except for the legacy Verify path below.

---

## B) Remaining direct provider calls

### Postmark

| Location | Classification | Notes |
|----------|----------------|------|
| `notification_orchestrator.py:72–73, 536` | **Single pipe** | PostmarkClient init and `_postmark_client.emails.send` — only production send path. |
| `email_service.py:32, 78, 103` | **Allowed (dead)** | `EmailService.send_email()` raises `_raise_send_deprecated()` at line 43 before any send. No production caller reaches `.emails.send`. |

**Conclusion:** All live email goes through the orchestrator. No migration needed for Postmark.

### Twilio / SMS

| Location | Classification | Notes |
|----------|----------------|------|
| `notification_orchestrator.py:81–82, 646–648` | **Single pipe** | Twilio Client init and `_twilio_client.messages.create` — used for all orchestrator SMS (OTP_CODE_SMS, COMPLIANCE_EXPIRY_REMINDER_SMS, ADMIN_MANUAL_SMS, etc.). |
| `sms_service.py:28, 70, 112` | **Legacy – deprecated (410)** | `POST /api/sms/send-otp` and `/api/sms/verify-otp` return **410 Gone** with `LEGACY_OTP_ENDPOINT_DEPRECATED`; callers must use **POST /api/otp/send** and **POST /api/otp/verify**. No production code calls `sms_service.send_otp` or `verify_otp`; OTP is fully orchestrator-based. |

**Conclusion:** All app/enterprise SMS (including OTP) goes through the orchestrator. Legacy `/api/sms/send-otp` and `/api/sms/verify-otp` return 410 Gone; the only OTP API in use is **POST /api/otp/send** and **POST /api/otp/verify** (orchestrator-only).

---

## C) Provisioning rule enforcement

| Check | Status | Evidence |
|-------|--------|----------|
| WELCOME_EMAIL requires PROVISIONED | **Enforced** | `database.py` seed: `WELCOME_EMAIL` has `requires_provisioned: True`. Orchestrator `_apply_gating` (line 350) blocks when `onboarding_status != "PROVISIONED"`. |
| PASSWORD_RESET requires PROVISIONED | **Enforced** | Seed: `PASSWORD_RESET` has `requires_provisioned: True`; same gating. |
| Provisioning runner sends welcome only after PROVISIONING_COMPLETED | **Enforced** | `provisioning_runner.py`: welcome email is sent only after job status is set to `PROVISIONING_COMPLETED` (lines 237–248) and after `provisioning_service._send_password_setup_link`. In `provisioning.py`, `run_provisioning_core` sets `onboarding_status` to `PROVISIONED` (line 174) before the runner sends the link. So client is PROVISIONED when WELCOME_EMAIL is sent. |
| Admin resend returns 403 ACCOUNT_NOT_READY when not PROVISIONED | **Enforced** | `admin.py:1054–1058`: if `client.get("onboarding_status") != "PROVISIONED"` → `HTTPException(403, ACCOUNT_NOT_READY)`. `admin_billing.py:662–666`: same check before calling orchestrator. |

---

## D) Runtime env dependency checklist (Postmark + Twilio)

Required for **sending** in production (orchestrator only):

| Env var | Read in code | If missing |
|---------|----------------|------------|
| **POSTMARK_SERVER_TOKEN** | `notification_orchestrator.py:69` | `_postmark_client` is None; `_send_email` sets MessageLog to `BLOCKED_PROVIDER_NOT_CONFIGURED`, writes audit, returns blocked — no crash. |
| **EMAIL_SENDER** | `notification_orchestrator.py:21` | Default `info@pleerityenterprise.co.uk`. |
| **SMS_ENABLED** | `notification_orchestrator.py:75, 611` | Treated as false; SMS path blocks with `BLOCKED_PROVIDER_NOT_CONFIGURED`, audit — no crash. |
| **TWILIO_ACCOUNT_SID** | `notification_orchestrator.py:76` | With SMS_ENABLED=true, `_twilio_client` stays None; SMS blocked, audit — no crash. |
| **TWILIO_AUTH_TOKEN** | `notification_orchestrator.py:77` | Same as SID. |
| **TWILIO_PHONE_NUMBER** or **TWILIO_MESSAGING_SERVICE_SID** | `notification_orchestrator.py:623–625` | Both missing → MessageLog `BLOCKED_PROVIDER_NOT_CONFIGURED`, audit — no crash. |

Optional / defaults: `POSTMARK_MESSAGE_STREAM` (default `outbound`), `EMAIL_REPLY_TO`, `OPS_ALERT_EMAIL`, `ADMIN_ALERT_EMAILS`, `OTP_PEPPER`, per-minute limits, etc. — see `backend/docs/NOTIFICATION_ENV_VARS.md`.

---

## E) Remaining work / gaps (from code + gap doc)

| Item | Status | Notes |
|------|--------|------|
| OTP through orchestrator + OTP_* audits + MessageLog | **DONE** | `otp_service` calls `notification_orchestrator.send("OTP_CODE_SMS", ...)`; audits OTP_SEND_REQUESTED, OTP_SENT, OTP_VERIFY_*, OTP_RATE_LIMITED, OTP_LOCKED_OUT; MessageLog via orchestrator. |
| Global throttling + DEFERRED_THROTTLED + retry enqueue | **DONE** | `_check_global_throttle` in orchestrator; per-minute limits; DEFERRED_THROTTLED + `notification_retry_queue`. |
| Failure spike monitor + OPS_ALERT_NOTIFICATION_SPIKE | **DONE** | `run_notification_failure_spike_monitor` in job_runner; sends via orchestrator; template seeded. |
| Notification health endpoints (summary / timeseries / recent) | **DONE** | `GET /api/admin/notification-health/summary`, `timeseries`, `recent` in `admin.py`. |
| Admin templates + triggers (PROVISIONING_FAILED_ADMIN, STRIPE_WEBHOOK_FAILURE_ADMIN) | **DONE** | Templates seeded; provisioning_runner and webhooks.py wire them. |
| NOTIFICATION_TEMPLATE_MATRIX.md + env doc | **DONE** | `backend/docs/NOTIFICATION_TEMPLATE_MATRIX.md` and NOTIFICATION_ENV_VARS.md updated. |
| Mandatory tests (OTP rate limit, lockout, throttling, spike, health, plan gate) | **DONE** | `test_otp_flow.py`, `test_enterprise_notification.py` cover these. |
| Legacy `/api/sms/send-otp` and verify-otp | **DONE** | Return 410 Gone; canonical OTP is /api/otp/send and /api/otp/verify (orchestrator-only). |
| Per-template `rate_limit_window_seconds` in DB | **PARTIAL** | Not in template seed; orchestrator uses fixed 24h for SMS reminder throttle and env-based OTP window. Optional enhancement. |
| ENTERPRISE_NOTIFICATION_TASK_GAP_ANALYSIS.md | **OUTDATED** | Doc still says “OTP sent via sms_service directly” and “Missing” for several items; implementation is done. Update doc to match current code. |

TODOs in repo (unrelated to notifications): `lead_service.py:470` (notify admin), `lead_followup_service.py:587` (business hours), `admin_orders.py:387, 459, 1215`, `team.py:373`, `clearform` TODOs — none of these block Postmark/Twilio or provisioning safety.

---

## F) Provisioning flow end-to-end

- Stripe webhook / checkout sets provisioning job; runner runs core (`provisioning_service.run_provisioning_core`), which creates portal user and sets `onboarding_status = PROVISIONED`.
- Runner then sends welcome email via `_send_password_setup_link` → `notification_orchestrator.send("WELCOME_EMAIL", ...)`. Template gating would block if client were not PROVISIONED; by then the client is already PROVISIONED.
- Admin resend endpoints check `onboarding_status == "PROVISIONED"` and return 403 otherwise; they use the same orchestrator path.

**Conclusion:** Provisioning flow is consistent and provisioning-safe: welcome/password-setup only after PROVISIONED; admin resend enforces 403 when not PROVISIONED.

---

## G) One-sentence conclusion

**SAFE FOR E2E TESTING? YES.** All production email and SMS (including OTP) go through NotificationOrchestrator. Legacy `/api/sms/send-otp` and `/api/sms/verify-otp` return 410 Gone; the only OTP API is **POST /api/otp/send** and **POST /api/otp/verify**. WELCOME_EMAIL/PASSWORD_RESET are gated on PROVISIONED; admin resend returns 403 when not PROVISIONED; missing Postmark/Twilio env blocks sends with audit and no crash.
