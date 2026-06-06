# Rent operations landlord-tenant watchlist

- Classification: `PARTIAL`
- Post-deploy run tag: `20260606T143514Z`

## Post-deploy checklist
- [x] env_proof (commit `1dfcc85a` deployed; job 200; rate limit cleared)
- [ ] due_delivery
- [ ] overdue_delivery
- [x] idempotency
- [x] tenant_delivery
- [x] regression

## Remaining
- [ ] Pilot ledger with **missing** due/overdue reminder event (live send only fires on newly created events; pre-live `manual` events are not upgraded)
- [ ] `RENT_REMINDER` message_logs with `status=sent` to `f7-ops-wales@yopmail.com`
- [ ] Reminder events with `delivery_status=sent` (not `manual`)
- [ ] Re-run `rent_reminder_live_delivery_post_deploy_proof_01_execute.py` when a new due_soon/due_today/overdue threshold crosses on an un-evented period
- [ ] Tenant in-app notification surface when enabled
- [ ] SMS proof only with configured safe test number
