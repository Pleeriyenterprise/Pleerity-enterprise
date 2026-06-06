# Rent operations landlord-tenant watchlist

- Classification: `PARTIAL`
- Fresh event run tag: `20260606T151019Z`

## Fresh event checklist
- [x] fixture
- [ ] due_delivery
- [ ] overdue_delivery
- [x] dedupe
- [x] payment_suppression
- [ ] partial_payment_copy
- [x] tenant_targeting
- [x] regression

## Remaining
- [ ] **Apply `RENT_REMINDERS_LIVE_SEND=true` on Render `pleerity-api` service** (render.yaml alone does not update existing services)
- [ ] Re-run `python backend/rent_reminder_fresh_event_proof_01_execute.py` with new marker after env active
- [ ] Expect fresh events `delivery_status=sent` and `RENT_REMINDER` message_logs to `f7-ops-wales@yopmail.com`
- [ ] Tenant in-app notification surface when enabled
- [ ] SMS proof only with configured safe test number
