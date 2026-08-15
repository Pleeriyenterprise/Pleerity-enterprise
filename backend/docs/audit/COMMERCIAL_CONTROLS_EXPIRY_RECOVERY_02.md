# Commercial Controls — Expiry / recovery 02

**Runtime status:** **UNVERIFIED** in this exercise (no backdated staging fixture run).

## Implemented

`expire_stale_governance_row`:

- marks governance `expired`
- unsets commercial overlay fields
- recomputes `canonical_entitlement_state` from underlying billing
- resumes Stripe collection only if previously paused and still billable
- invalidates runtime contract cache
- emits `commercial_expired`

Cancelled path (code): overlay `ENABLED` + restored plan → expiry → canonical/effective `CANCELLED` again; Stripe not recreated.

Prior Phase 2C staging expiry closeout (2026-06-01) is **not** reused as proof of this overlay/pause behaviour.
