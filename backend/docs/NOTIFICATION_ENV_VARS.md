# Notification & Webhook Environment Variables

Verified call sites and safe behavior when missing.

| Env Var | File:Line | What it controls | When missing / safe behavior |
|---------|-----------|-------------------|------------------------------|
| **POSTMARK_SERVER_TOKEN** | `notification_orchestrator.py:62` | Postmark API client for sending email. | `_postmark_client` is None; `_send_email` sets MessageLog status to `BLOCKED_PROVIDER_NOT_CONFIGURED`, writes audit, returns blocked — no crash. |
| | `email_service.py:27` | Legacy EmailService Postmark client. | `self.client = None`; send paths are quarantined (raise). |
| | `lead_service.py:819`, `lead_followup_service.py:28,640` | Legacy checks before sending (now migrated to orchestrator). | Skip/early return; no crash. |
| **POSTMARK_MESSAGE_STREAM** | `notification_orchestrator.py:22` (read), `notification_orchestrator.py:_send_email` (applied) | Postmark `MessageStream` for every orchestrator email send. | Default `"outbound"`; passed as payload field `MessageStream` on all sends. |
| **EMAIL_SENDER** | `notification_orchestrator.py:21` | Default `From` for all orchestrator email. | Default `info@pleerityenterprise.co.uk` — safe. |
| | `email_service.py:14` | Legacy default From. | Same default. |
| | `order_email_templates.py:12` | SUPPORT_EMAIL fallback. | Same default. |
| **EMAIL_REPLY_TO** | `notification_orchestrator.py:23` (read), `notification_orchestrator.py:_send_email` (applied) | Postmark `ReplyTo` for every orchestrator email send (including attachments). | Optional; if set and non-empty, payload field `ReplyTo` is set. |
| **SMS_ENABLED** | `notification_orchestrator.py:69,545` | Whether Twilio client is used and SMS sends allowed. | Treated as false; SMS path sets `BLOCKED_PROVIDER_NOT_CONFIGURED` — no crash. |
| **TWILIO_ACCOUNT_SID** | `notification_orchestrator.py:70` | Twilio client init. | With SMS_ENABLED=true but SID missing, `_twilio_client` stays None; SMS sends blocked with audit — safe. |
| **TWILIO_AUTH_TOKEN** | `notification_orchestrator.py:71` | Twilio client init. | Same as SID. |
| **TWILIO_PHONE_NUMBER** | `notification_orchestrator.py:557` | From number for SMS. | MessageLog set to `BLOCKED_PROVIDER_NOT_CONFIGURED`, audit written — no crash. |
| | `sms_service.py:22` | SMS from number when not using Messaging Service. | Used when SMS sent via sms_service (e.g. compliance alerts). OTP is via orchestrator only. |
| **TWILIO_MESSAGING_SERVICE_SID** | `notification_orchestrator.py:_send_sms`, `sms_service.py` | Twilio Messaging Service for SMS (OTP and other); preferred over TWILIO_PHONE_NUMBER when set. | If missing and TWILIO_PHONE_NUMBER missing: SMS blocked with BLOCKED_PROVIDER_NOT_CONFIGURED. |
| **OTP_PEPPER** | `otp_service.py:24,56,62,187` | SHA256 pepper for OTP and phone-hash (never store raw OTP). | Required for send/verify; if missing, send returns generic success without sending; verify returns generic fail. |
| **OTP_TTL_SECONDS** | `otp_service.py` | OTP validity window. | Default 600 (10 min). |
| **OTP_MAX_ATTEMPTS** | `otp_service.py` | Max verify attempts per OTP. | Default 5. |
| **OTP_LOCKOUT_SECONDS** | `otp_service.py` | Lockout duration after max failed verify attempts. | Default 900 (15 min). |
| **OTP_SEND_LIMIT_WINDOW_SECONDS** | `otp_service.py` | Rate-limit window for OTP sends per (phone, purpose). | Default 1800 (30 min). |
| **OTP_MAX_SENDS_PER_WINDOW** | `otp_service.py` | Max OTP sends per window per (phone_hash, purpose). | Default 3. |
| **OTP_RESEND_COOLDOWN_SECONDS** | `otp_service.py` | Min seconds between send per (phone, purpose). | Default 60. |
| **STEP_UP_TOKEN_TTL_SECONDS** | `otp_service.py` | Step-up token validity (5–10 min typical). | Default 300. |
| **OPS_ALERT_EMAIL** | `compliance_sla_monitor.py`, `notification_failure_spike_monitor.py`, `provisioning_runner.py`, `webhooks.py` | Recipient for ops/admin alert emails when ADMIN_ALERT_EMAILS not set. | If empty: warning logged, alerts not sent. |
| **ADMIN_ALERT_EMAILS** | `notification_failure_spike_monitor.py`, `provisioning_runner.py`, `webhooks.py` | Optional comma-separated list for admin alerts (provisioning failed, Stripe webhook failure, notification spike). | If unset, fallback to OPS_ALERT_EMAIL. |
| **NOTIFICATION_EMAIL_PER_MINUTE_LIMIT** | `notification_orchestrator.py` | Global outbound email throttle (per minute). | Default 60. |
| **NOTIFICATION_SMS_PER_MINUTE_LIMIT** | `notification_orchestrator.py` | Global outbound SMS throttle (per minute). | Default 30. |
| **NOTIFICATION_FAIL_WARN_THRESHOLD** | `notification_failure_spike_monitor.py` | Failure count in 15 min to trigger WARN spike alert. | Default 10. |
| **NOTIFICATION_FAIL_CRIT_THRESHOLD** | `notification_failure_spike_monitor.py` | Failure count in 15 min to trigger CRIT spike alert. | Default 25. |
| **NOTIFICATION_SPIKE_COOLDOWN_SECONDS** | `notification_failure_spike_monitor.py` | Min seconds between spike alert emails. | Default 3600. |
| **BASE_URL** | `calendar.py:429` | Fallback for request base URL. | Defaults to `request.base_url.scheme + "://" + request.base_url.netloc` — safe. |
| **POSTMARK_WEBHOOK_TOKEN** | `webhooks.py` | Webhook auth: must match `X-Postmark-Token` header when set. | If env set and header missing/wrong: 401, no DB update. If env not set: no token check (backward compat). |

## Postmark webhook auth

- **Endpoint:** `POST /api/webhooks/postmark`
- **Env:** `POSTMARK_WEBHOOK_TOKEN` (or `POSTMARK_WEBHOOK_SECRET` if already used).
- **Header:** `X-Postmark-Token` — when `POSTMARK_WEBHOOK_TOKEN` is set, request must send this header with the same value.
- **On mismatch or missing token (when env set):** return `401 Unauthorized`, do not update `message_logs`.
