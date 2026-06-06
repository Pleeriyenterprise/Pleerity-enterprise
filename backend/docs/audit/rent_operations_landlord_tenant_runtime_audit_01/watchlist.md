# Rent operations landlord-tenant watchlist

- Classification: `PARTIAL` (closeout)
- Prior audit: `RENT_REMINDER_GAP`
- Closeout run tag: `20260606T123538Z`

## Closeout checklist
- [x] setup
- [ ] due_delivery
- [ ] overdue_delivery
- [x] suppression
- [x] partial_payment
- [x] audit_delivery
- [x] tenant_visibility
- [ ] retry
- [x] regression

## Code delivered (pending deploy proof)
- [x] Safe live send: client allowlist + yopmail domain guard
- [x] Tenant recipient resolution from tenancy assignments
- [x] RENT_REMINDER notification template seed
- [x] render.yaml staging env flags

## Remaining
- [ ] Deploy to staging and re-run closeout harness after admin job rate limit clears
- [ ] Verify `RENT_REMINDER` message_logs with status `sent` to `f7-ops-wales@yopmail.com`
- [ ] Tenant portal in-app notification surface when enabled
- [ ] SMS proof only with configured safe test number
- [ ] Real-device Safari bottom-bar overlap on enable-tracking modal
