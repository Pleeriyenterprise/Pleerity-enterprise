# Enterprise Notification System — Task Gap Analysis

This document compares the codebase to the full enterprise notification task (OTP + Billing + System Alerts + Admin Notifications + Observability). **Implemented** vs **Missing** per part.

---

## Non-negotiable rules (high level)

| Rule | Status |
|------|--------|
| All outbound email/SMS via NotificationOrchestrator | **Partial** — OTP sends via `sms_service.send_sms_via_messaging_service` directly; all other app email/SMS should go through orchestrator (some legacy paths may remain per NOTIFICATION_SEND_INVENTORY). |
| No access emails before provisioning COMPLETED | **Implemented** — Orchestrator gates on `requires_provisioned`; WELCOME_EMAIL, PASSWORD_RESET templates have `requires_provisioned: True`. |
| Stripe = billing source of truth; billing only from webhooks | **Implemented** — `stripe_webhook_service` triggers PAYMENT_FAILED, SUBSCRIPTION_CONFIRMED, SUBSCRIPTION_CANCELED via orchestrator with idempotency. |
| Server-side gating (plan_registry + subscription + entitlement) | **Implemented** — Orchestrator checks template flags and plan_registry. |
| Every send → MessageLog + AuditLog | **Implemented** for orchestrator sends; **Missing** for OTP (OTP path does not use orchestrator, so no MessageLog with template_key=OTP_CODE_SMS, no OTP_* audit events). |
| Rate limiting + throttling + failure spike alerting + health dashboard | **Partial** — See Parts 2, 7 below. |

---

## PART 1 — OTP flow (enterprise safe)

| Requirement | Implemented | Missing / notes |
|-------------|-------------|------------------|
| **Service** `backend/services/otp_service.py` | ✅ | — |
| DB-backed OTP (not in-memory) | ✅ | — |
| Hash OTP in DB (never raw) | ✅ (`code_hash` with pepper) | — |
| TTL 10 minutes | ❌ | Current default `OTP_TTL_SECONDS=300` (5 min). Task: 600. |
| Max attempts 5 | ✅ | — |
| Lockout 15 min after max attempts | ❌ | Current: lockout until `expires_at` (TTL), no separate 15-min lockout. |
| Rate limit: max 3 OTP sends per 30 min per phone | ❌ | Current: `OTP_MAX_SENDS_PER_HOUR` (5) and `OTP_RESEND_COOLDOWN_SECONDS` (60). Task: 3 per 30 min. |
| Action values: PHONE_VERIFY, SENSITIVE_ACTION | ❌ | Current: `purpose`: `verify_phone`, `step_up`. Task: `action`: PHONE_VERIFY, SENSITIVE_ACTION. |
| **Endpoints** POST /api/otp/send, POST /api/otp/verify | ❌ | Current: POST /api/sms/otp/send, /api/sms/otp/verify. Task: /api/otp/... |
| Request body `phone_number`, `action` | ❌ | Current: `phone_e164`, `purpose`. |
| **SMS routing** via NotificationOrchestrator template_key=OTP_CODE_SMS | ❌ | OTP sent via `sms_service.send_sms_via_messaging_service` directly. |
| Twilio Messaging Service SID preferred | ✅ | Used when set. |
| **Audits** OTP_SEND_REQUESTED, OTP_SENT, OTP_VERIFY_SUCCESS, OTP_VERIFY_FAILED, OTP_RATE_LIMITED, OTP_LOCKED_OUT | ❌ | No OTP_* audit actions in `AuditAction`; no audit writes in OTP flow. |
| **MessageLog** channel=SMS, template_key=OTP_CODE_SMS, metadata action/phone_hash/attempt_count | ❌ | OTP path does not write MessageLog. |
| UX: same response for send success/fail; verify generic "invalid code" | ✅ | Generic responses. |

**Summary Part 1:** OTP is implemented as a separate pipeline (DB-backed, hashed, rate-limited) but does not go through the orchestrator, does not use template OTP_CODE_SMS, and does not emit OTP_* audits or MessageLog. Route paths and body/action naming differ from task. TTL/lockout/rate window differ from spec.

---

## PART 2 — Notification orchestrator (single pipe)

| Requirement | Implemented | Missing / notes |
|-------------|-------------|------------------|
| Single path for all sends | ✅ | Except OTP (see Part 1). |
| POSTMARK_MESSAGE_STREAM default "outbound" | ✅ | `notification_orchestrator.py`. |
| EMAIL_REPLY_TO applied to all email | ✅ | — |
| **Global outbound throttling** | ❌ | No `notification_outbound_limits` collection; no per_minute_email_limit / per_minute_sms_limit. |
| Token-bucket or rolling window throttle | ❌ | — |
| On throttle: MessageLog status=DEFERRED_THROTTLED + enqueue retry | ❌ | No DEFERRED_THROTTLED; retry queue exists for transient failures only. |
| **Per-client rate** 1 per template_key per client per window | Partial | Orchestrator has 24h SMS throttle (1 per 24h per template per client). Task: configurable `rate_limit_window_seconds` per template (e.g. 24h reminders, 10m OTP). No `rate_limit_window_seconds` in template seed. |
| **Retry policy** Email 3 (30s, 2m, 10m), SMS 2 (1m) | ✅ | `EMAIL_BACKOFFS`, `SMS_BACKOFFS`, retry queue. |
| Retry only transient (no 4xx/hard) | ✅ | `_is_transient_error`. |
| **Failure spike detection** (last 15 min, WARN/CRIT thresholds) | ❌ | Not implemented. |
| Job `run_notification_failure_spike_monitor` every 5 min | ❌ | — |
| Ops email on spike via template OPS_ALERT_NOTIFICATION_SPIKE | ❌ | No template; no job. |

**Summary Part 2:** Reply-to and stream are done. Global per-minute throttling, DEFERRED_THROTTLED, and failure-spike monitor job + OPS alert are missing. Per-template rate window is only partially aligned (fixed 24h for SMS, no DB field).

---

## PART 3 — Billing notifications (Stripe-triggered only)

| Requirement | Implemented | Missing / notes |
|-------------|-------------|------------------|
| invoice.payment_failed → PAYMENT_FAILED email | ✅ | `stripe_webhook_service._handle_payment_failed` → orchestrator. |
| invoice.paid / checkout completed → SUBSCRIPTION_CONFIRMED | ✅ | `_handle_invoice_paid`, checkout flow → orchestrator. |
| customer.subscription.deleted → SUBSCRIPTION_CANCELED | ✅ | `_handle_subscription_deleted` → orchestrator (idempotency_key). |
| Idempotency by event_id + template_key | ✅ | — |
| Billing emails allowed pre-provisioning | ✅ | Templates have requires_provisioned=False. |
| MessageLog + AuditLog for billing | ✅ | Via orchestrator. |

**Summary Part 3:** Fully implemented.

---

## PART 4 — System alerts (compliance)

| Requirement | Implemented | Missing / notes |
|-------------|-------------|------------------|
| Compliance expiry reminders (daily job, 7/14/30 days) | Partial | Job and templates exist; need to confirm configurable 7/14/30 and that email uses COMPLIANCE_EXPIRY_REMINDER. |
| Email always (COMPLIANCE_EXPIRY_REMINDER) | ✅ | Template and usage in jobs. |
| SMS only if plan_registry sms_reminders + sms_enabled + phone | Partial | Template COMPLIANCE_EXPIRY_REMINDER_SMS with plan_required_feature_key sms_reminders; call site must use orchestrator and gating. |
| Compliance SLA alerts use orchestrator COMPLIANCE_SLA_ALERT | ✅ | `compliance_sla_monitor._send_alert_email` → orchestrator. |
| Ops alerts to OPS_ALERT_EMAIL | ✅ | Context recipient = OPS_ALERT_EMAIL. |

**Summary Part 4:** Largely implemented; confirm job uses orchestrator for both email and SMS and configurable expiry windows.

---

## PART 5 — Admin notifications

| Requirement | Implemented | Missing / notes |
|-------------|-------------|------------------|
| Template PROVISIONING_FAILED_ADMIN | ❌ | Not in `_seed_notification_templates`. |
| Template STRIPE_WEBHOOK_FAILURE_ADMIN | ❌ | Not in seed. |
| Template NOTIFICATION_SPIKE_ALERT_ADMIN | ❌ | Not in seed. Task also names OPS_ALERT_NOTIFICATION_SPIKE for spike. |
| Admin notifications to OPS_ALERT_EMAIL or ADMIN_ALERT_EMAILS | Partial | OPS_ALERT_EMAIL used by compliance SLA; no ADMIN_ALERT_EMAILS (comma-separated) or wiring for the three admin templates above. |
| Never to client | ✅ | Admin templates would use client_id=None, recipient from env. |

**Summary Part 5:** Admin templates and ADMIN_ALERT_EMAILS list not present; triggers (where to call these templates) not wired.

---

## PART 6 — Template governance

| Requirement | Implemented | Missing / notes |
|-------------|-------------|------------------|
| WELCOME_EMAIL, PASSWORD_RESET (provisioning-gated) | ✅ | In seed, requires_provisioned=True. |
| SUBSCRIPTION_CONFIRMED, PAYMENT_FAILED, COMPLIANCE_EXPIRY_REMINDER | ✅ | In seed. |
| OPS_ALERT_NOTIFICATION_SPIKE (admin) | ❌ | Not in seed. |
| PROVISIONING_FAILED_ADMIN, STRIPE_WEBHOOK_FAILURE_ADMIN | ❌ | Not in seed. |
| OTP_CODE_SMS (client SMS) | ❌ | Not in seed. |
| COMPLIANCE_EXPIRY_SMS (Pro) | Partial | COMPLIANCE_EXPIRY_REMINDER_SMS exists with plan_required_feature_key sms_reminders. |
| OPS_ALERT_SMS (optional, default off) | ❌ | Not in seed. |
| Template fields: rate_limit_window_seconds | ❌ | Not in seed schema. |
| **docs/NOTIFICATION_TEMPLATE_MATRIX.md** | ❌ | File does not exist. |

**Summary Part 6:** Several admin/OTP templates and rate_limit_window_seconds missing; NOTIFICATION_TEMPLATE_MATRIX.md not added.

---

## PART 7 — Admin "Notification Health Dashboard" (observability)

| Requirement | Implemented | Missing / notes |
|-------------|-------------|------------------|
| GET /api/admin/notification-health/summary?window_minutes=60 | ❌ | Not implemented. Task: sent/failed counts per channel, top_failed_templates, top_failure_reasons, throttled_count. |
| GET /api/admin/notification-health/timeseries?window_minutes=240&bucket_minutes=15 | ❌ | Not implemented. |
| GET /api/admin/notification-health/recent?limit=100 | ❌ | Not implemented. Task: last message_logs with status, template_key, recipient, error, timestamps. |
| Admin tab "Notification Health" | ✅ | UI exists at `/admin/notification-health` using existing message-logs API. |
| Backend GET /api/admin/message-logs and /message-logs/{id} | ✅ | Implemented; different from task’s summary/timeseries/recent shapes. |

**Summary Part 7:** Dedicated notification-health summary, timeseries, and recent endpoints per task spec are missing. UI and message-logs APIs exist but do not fulfill the specified aggregate/time-series contract.

---

## PART 8 — Required env vars (document + defaults)

| Requirement | Implemented | Missing / notes |
|-------------|-------------|------------------|
| NOTIFICATION_ENV_VARS.md with file/line and defaults | ✅ | Exists. |
| POSTMARK_*, EMAIL_SENDER, EMAIL_REPLY_TO, POSTMARK_MESSAGE_STREAM, POSTMARK_WEBHOOK_TOKEN | ✅ | Documented. |
| TWILIO_*, SMS_ENABLED, OPS_ALERT_EMAIL | ✅ | Documented. |
| ADMIN_ALERT_EMAILS (optional, comma-separated) | ❌ | Not documented. |
| NOTIFICATION_EMAIL_PER_MINUTE_LIMIT (default 60) | ❌ | Not documented (no global throttle yet). |
| NOTIFICATION_SMS_PER_MINUTE_LIMIT (default 30) | ❌ | Not documented. |
| OTP_TTL_SECONDS (default 600) | Partial | Documented default 300; task wants 600. |
| OTP_SEND_RATE_LIMIT (3 per 30m) | ❌ | Current: OTP_MAX_SENDS_PER_HOUR (5); task: 3 per 30 min. Not documented as per task. |

**Summary Part 8:** Core vars documented; optional admin/throttle/OTP vars and task defaults need to be added.

---

## PART 9 — Tests (mandatory)

| Test | Implemented | Missing / notes |
|------|-------------|------------------|
| 1) OTP send rate limit → OTP_RATE_LIMITED audit, no send | ❌ | No OTP_* audits; rate limit logic exists but audit not. |
| 2) OTP verify wrong code → attempts increment, lock after 5 | ✅ | test_otp_flow covers verify failure and lockout. |
| 3) Provisioning-gated email blocked pre-PROVISIONED (WELCOME_EMAIL) | Partial | test_notification_orchestrator has provisioning-gate tests; explicit "WELCOME_EMAIL blocked pre-PROVISIONED" test can be added. |
| 4) Pro SMS allowed, Solo SMS denied for COMPLIANCE_EXPIRY_SMS | ❌ | No test for plan gate on COMPLIANCE_EXPIRY_REMINDER_SMS. |
| 5) Global throttling defers and enqueues retry | ❌ | Global throttling not implemented. |
| 6) Failure spike monitor triggers OPS alert when threshold exceeded | ❌ | No failure spike job or test. |
| 7) Health dashboard endpoints return correct aggregate counts (mock DB) | ❌ | No notification-health/summary (or timeseries/recent) endpoints or tests. |

**Summary Part 9:** Some OTP and orchestrator tests exist; the seven task-mandated tests are not all present (especially rate-limit audit, plan gate SMS, throttling, spike, health aggregates).

---

## Summary table

| Part | Implemented | Missing |
|------|-------------|--------|
| 1 OTP | Service, DB, hash, cooldown, lockout, step-up, generic UX | Orchestrator path (OTP_CODE_SMS), OTP_* audits, MessageLog, task route/body/action names, TTL 10m, lockout 15m, rate 3/30m |
| 2 Orchestrator | Single pipe, reply-to, stream, retry, per-client SMS 24h | Global throttling, DEFERRED_THROTTLED, failure spike job + OPS_ALERT_NOTIFICATION_SPIKE, per-template rate_limit_window_seconds |
| 3 Billing | ✅ Full | — |
| 4 System alerts | ✅ Mostly | Confirm configurable expiry windows; SMS via orchestrator + gating |
| 5 Admin notifications | COMPLIANCE_SLA_ALERT to ops | PROVISIONING_FAILED_ADMIN, STRIPE_WEBHOOK_FAILURE_ADMIN, NOTIFICATION_SPIKE_ALERT_ADMIN templates + triggers, ADMIN_ALERT_EMAILS |
| 6 Template governance | Most client templates | OTP_CODE_SMS, OPS_ALERT_*, admin templates, rate_limit_window_seconds, NOTIFICATION_TEMPLATE_MATRIX.md |
| 7 Health dashboard | message-logs API + UI | GET /api/admin/notification-health/summary, /timeseries, /recent with task response shapes |
| 8 Env vars | Core vars doc | ADMIN_ALERT_EMAILS, NOTIFICATION_*_PER_MINUTE_LIMIT, OTP_SEND_RATE_LIMIT (3/30m), OTP_TTL 600 |
| 9 Tests | Some OTP + orchestrator tests | All 7 task-mandated tests (rate-limit audit, plan gate SMS, throttling, spike, health aggregates) |

---

## Recommended implementation order

1. **OTP via orchestrator** — Add OTP_CODE_SMS template; route OTP send through orchestrator; add OTP_* audit actions and write audits + MessageLog in OTP flow; optionally align route path/body/action with task.
2. **Templates + matrix** — Seed OPS_ALERT_NOTIFICATION_SPIKE, PROVISIONING_FAILED_ADMIN, STRIPE_WEBHOOK_FAILURE_ADMIN, OTP_CODE_SMS; add rate_limit_window_seconds where needed; add docs/NOTIFICATION_TEMPLATE_MATRIX.md.
3. **Global throttling** — notification_outbound_limits (or env), per-minute caps, DEFERRED_THROTTLED + retry enqueue.
4. **Failure spike job** — run_notification_failure_spike_monitor every 5 min; WARN/CRIT thresholds; send OPS email via OPS_ALERT_NOTIFICATION_SPIKE.
5. **Notification health API** — GET notification-health/summary, /timeseries, /recent; then wire UI if desired.
6. **Admin triggers** — Wire PROVISIONING_FAILED_ADMIN, STRIPE_WEBHOOK_FAILURE_ADMIN (and spike admin) to appropriate call sites; ADMIN_ALERT_EMAILS.
7. **Env doc** — Update NOTIFICATION_ENV_VARS.md with Part 8 list and defaults.
8. **Tests** — Add the 7 mandatory tests (and fix any that fail after changes).
