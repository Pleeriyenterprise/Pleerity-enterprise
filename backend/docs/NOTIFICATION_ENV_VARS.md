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
| | `sms_service.py:22` | Legacy SMS from number. | Used only when SMS sent via sms_service (OTP path). |
| **TWILIO_MESSAGING_SERVICE_SID** | `sms_service.py:23,119` | Twilio Messaging Service for OTP (no direct From). | OTP send uses `send_sms_via_messaging_service`; if missing, OTP not sent but generic success still returned. |
| **OTP_PEPPER** | `otp_service.py:24,56,62,187` | SHA256 pepper for OTP and phone-hash (never store raw OTP). | Required for send/verify; if missing, send returns generic success without sending; verify returns generic fail. |
| **OTP_TTL_SECONDS** | `otp_service.py:25` | OTP validity window. | Default 300. |
| **OTP_MAX_ATTEMPTS** | `otp_service.py:26` | Max verify attempts per OTP. | Default 5. |
| **OTP_RESEND_COOLDOWN_SECONDS** | `otp_service.py:27` | Min seconds between send per (phone, purpose). | Default 60. |
| **OTP_MAX_SENDS_PER_HOUR** | `otp_service.py:28` | Max OTP sends per (phone_hash, purpose) in a 1-hour window. | Default 5. |
| **STEP_UP_TOKEN_TTL_SECONDS** | `otp_service.py:29` | Step-up token validity (5–10 min typical). | Default 300. |
| **OPS_ALERT_EMAIL** | `compliance_sla_monitor.py:22,49,60` | Recipient for compliance SLA alert emails. | If empty: warning logged, `_send_alert_email` returns False — no crash, alert not sent. |
| **BASE_URL** | `calendar.py:429` | Fallback for request base URL. | Defaults to `request.base_url.scheme + "://" + request.base_url.netloc` — safe. |
| **POSTMARK_WEBHOOK_TOKEN** | `webhooks.py` | Webhook auth: must match `X-Postmark-Token` header when set. | If env set and header missing/wrong: 401, no DB update. If env not set: no token check (backward compat). |

## Postmark webhook auth

- **Endpoint:** `POST /api/webhooks/postmark`
- **Env:** `POSTMARK_WEBHOOK_TOKEN` (or `POSTMARK_WEBHOOK_SECRET` if already used).
- **Header:** `X-Postmark-Token` — when `POSTMARK_WEBHOOK_TOKEN` is set, request must send this header with the same value.
- **On mismatch or missing token (when env set):** return `401 Unauthorized`, do not update `message_logs`.
