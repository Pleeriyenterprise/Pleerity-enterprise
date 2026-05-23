# Operations — Rent Operations (Phase 1)

## Product boundary

**In scope:** Operational rent tracking, arrears awareness, manual payment capture, property expense logging, operational financial summaries, advisory risk signals.

**Out of scope:** Accounting, bookkeeping, VAT/tax, payroll, bank feeds, reconciliation, double-entry, payment processing, tenant banking portal.

Rent Operations does **not** feed the compliance score or mutate requirement authority.

## Navigation

- **Operations → Rent Operations** (`/operations/rent`)
- **Expenses** tab inside Rent Operations (deep link: `/operations/expenses` → `/operations/rent?tab=expenses`)

## API routes (client)

| Method | Path |
|--------|------|
| GET | `/api/client/operations/rent/summary` |
| GET/POST | `/api/client/operations/rent/schedules` |
| GET/PATCH | `/api/client/operations/rent/ledgers` |
| GET | `/api/client/operations/rent/ledgers/{ledger_id}` |
| POST | `/api/client/operations/rent/payments` |
| POST | `/api/client/operations/rent/ledgers/{ledger_id}/payments` |
| POST | `/api/client/operations/rent/ledgers/{ledger_id}/reminders/mark-sent` |
| GET/POST/PATCH/DELETE | `/api/client/operations/expenses` |
| GET | `/api/client/operations/expenses/summary` |
| GET | `/api/client/properties/{property_id}/financial-snapshot` |

Gated by feature flag `RENT_OPERATIONS` (entitlement key: `rent_operations`).

## Collections

- `rent_schedules` — landlord rent setup (generates periods)
- `rent_ledger_periods` — one row per rent period
- `rent_payments` — append-only payment records
- `rent_reminder_events` — idempotent reminder tracking
- `property_expenses` — property-linked expenses (soft delete)

## Money

All amounts stored as **integer minor units** (pence), default currency `GBP`.

## Scheduled job

`rent_operations_daily_job` — daily recalc, future period generation, reminder events, advisory risk signals.

Live reminder send requires `RENT_REMINDERS_LIVE_SEND=true` and notification templates; default is tracked/manual send.

## Deferred (Phase 2+)

Bank feeds, reconciliation, Stripe rent collection, tenant payment portal, first-class tenancy entity, accounting statements, compliance score integration.
