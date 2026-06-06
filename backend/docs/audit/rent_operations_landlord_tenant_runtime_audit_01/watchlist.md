# Rent operations landlord-tenant watchlist

- Classification: `RENT_REMINDER_GAP`
- Run tag: `20260606T115547Z`

## Checklist
- [x] setup
- [x] tracking_setup
- [x] status_logic
- [x] payments
- [x] tenant
- [x] reminders
- [x] arrears_risk
- [x] cross_surface
- [x] mobile
- [x] audit_trail
- [x] permissions
- [x] edge_resilience
- [x] regression

## Gaps / follow-up
- [ ] Tenant portal rent due surface (not implemented — by design today)
- [ ] RENT_REMINDERS_LIVE_SEND on staging for automatic email/SMS proof
- [ ] Real-device Safari bottom-bar overlap on enable-tracking modal
- [ ] Timezone boundary tests around midnight UTC due dates
- [ ] Prove live due/overdue reminder delivery when RENT_REMINDERS_LIVE_SEND enabled
