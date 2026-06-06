# Rent operations landlord-tenant watchlist

- Classification: `PARTIAL`
- Live-send final run tag: `20260606T154220Z`

## Live-send final checklist
- [ ] env_proof
- [ ] due_live_send
- [ ] overdue_live_send
- [x] dedupe
- [x] payment_suppression
- [x] regression

## Remaining — Render env (use **code** variable names)
- [ ] `RENT_REMINDERS_LIVE_SEND=true`
- [ ] `RENT_REMINDERS_LIVE_SEND_CLIENT_ALLOWLIST=6fd5ac4c-3fd4-4112-ade7-156977deb49f` (not `RENT_REMINDERS_LIVE_CLIENT_ALLOWLIST`)
- [ ] `RENT_REMINDERS_SAFE_RECIPIENT_DOMAINS=yopmail.com` (not `RENT_REMINDERS_SAFE_EMAIL_DOMAINS`)
- [ ] `SMS_ENABLED` unset or `false` (not `RENT_REMINDERS_SMS_ENABLED`)
- [ ] Redeploy/restart `pleerity-api` on Render
- [ ] Re-run `python backend/rent_reminder_live_send_env_final_proof_01_execute.py`
- [ ] Expect `delivery_status=sent` + `RENT_REMINDER` message_logs to `f7-ops-wales@yopmail.com`
- [ ] Tenant in-app notification surface when enabled
- [ ] SMS proof only with configured safe test number
