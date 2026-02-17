# OTP Task Requirements – Gap Analysis

## Implemented (current codebase)

| Requirement | Status | Notes |
|-------------|--------|--------|
| POST /api/otp/send, POST /api/otp/verify | Done | Only OTP API; /api/sms/otp/* and legacy send-otp/verify-otp removed |
| purpose verify_phone \| step_up | Done | Validated in Pydantic |
| Twilio Messaging Service SID only | Done | send_sms_via_messaging_service |
| 6-digit OTP, TTL (expires_at) | Done | OTP_TTL_SECONDS |
| OTP_RESEND_COOLDOWN_SECONDS, OTP_MAX_ATTEMPTS | Done | Cooldown and attempts enforced |
| Generic responses (no enumeration) | Done | Same message for send; generic fail for verify |
| Log hashed phone only | Done | _phone_hash_for_log |
| verify_phone → update notification_preferences (sms_phone_verified) | Done | update_many by sms_phone_number |
| otp_codes collection + index | Done | Unique (phone_e164, purpose); expires_at |
| Env vars in NOTIFICATION_ENV_VARS.md | Done | OTP_*, TWILIO_MESSAGING_SERVICE_SID |
| Basic unit tests | Done | test_otp_flow.py |

## Gaps to implement

| Requirement | Gap | Action |
|-------------|-----|--------|
| Request JSON field name | Task: `phone_e164`; code: `phone_number` | Use `phone_e164` in request body and Pydantic models |
| Send response | Task: 200 `{ "status": "sent" }`; code: `{ "success", "message" }` | Return `{ "status": "sent" }` |
| Verify success response | Task: 200 `{ "status": "verified" }` or `{ "status": "verified", "step_up_token": "..." }`; code: `{ "success", "message" }` | Return status + optional step_up_token |
| Verify fail response | Task: 400 `{ "detail": "Invalid or expired code" }`; code: 200 with success false | Return HTTP 400 with detail |
| Code hash format | Task: sha256(code + ":" + OTP_PEPPER); code: sha256(OTP_PEPPER + raw_otp) | Change to code + ":" + OTP_PEPPER |
| Store phone_hash in DB (not raw phone) | Code stores phone_e164 | Store phone_hash only; unique index (phone_hash, purpose); use request phone for SMS and user update |
| OTP_MAX_SENDS_PER_HOUR | Not implemented | Add send_count, send_window_start; reject send if send_count >= max in window |
| Lockout until expires_at | Code deletes on max_attempts | Do not delete; reject verify until record expires |
| DB fields | Task: code_hash, send_count, send_window_start, verified_at | Add/rename and use |
| User update verify_phone | Task: user.phone_e164, phone_verified, phone_verified_at | Keep notification_preferences; add client.phone / portal_user if schema has it |
| Step-up token on verify | Not implemented | On success purpose=step_up: create step_up_tokens, return step_up_token; verify endpoint must be authenticated for step_up |
| step_up_tokens collection | Not implemented | Create; index token_hash; one-time use |
| X-Step-Up-Token dependency | Not implemented | Dependency that validates header, consumes token |
| SMS body templates | Task: different text for verify_phone vs step_up | Use two templates |
| Tests | Task: cooldown, attempts lockout, step_up token, generic | Add/expand tests |
