# Rent Operations Tenancy Authority — Watchlist

## Post-deploy runtime (required for VERIFIED_OPERATIONALLY)

- [ ] Staging browser: create tenancy → enable rent tracking → confirm preview disclosure → no duplicate periods on retry
- [ ] Record payment from ledger row only; verify unallocated overpayment appears in operational view
- [ ] Move-out tenancy: confirm schedule inactive and daily job skips future materialisation
- [ ] Multi-property landlord: property filter isolates ledgers and payments

## Backend latency (unchanged)

- [ ] Today/Command Centre rent attention still subject to backend payload size — separate performance workstream

## Data migration

- [ ] Legacy schedules without `tenancy_id` remain readable; new schedules require tenancy. Optional backfill script for historical rows.

## Future (out of scope)

- [ ] UI to allocate `rent_unallocated_payments` to ledger periods
- [ ] Tenant portal read-only rent balance (no payment recording)
