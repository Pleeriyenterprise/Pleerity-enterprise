# Commercial Controls — Expiry / recovery 03

**Runtime SHA:** `7c77391a5ee65f0a85372d9c462448c270b6b066`

Short `entitlement_expiry_at` (~95s) was used. Manual job `POST /api/admin/jobs/run` `commercial_entitlement_expiry` with portfolio-wide confirmation succeeded (`200`).

## Suspend billing CANCELLED

Client `5db7bba1-ed9d-444e-9e0d-b7478d5b566b`.

| Phase | Canonical | Effective | Exception | Stripe | Audit |
| --- | --- | --- | --- | --- | --- |
| After execute | CANCELLED | ENABLED | active (`billing_suspension`) | `already_non_collecting`; no recreate | `commercial_granted` `19:41:57Z` |
| After expiry job | CANCELLED | CANCELLED | none | still cancelled / no recreate | `commercial_expired` `19:44:08Z` |

Job result: `expired_count: 1` for this client’s governance id `d67a3e15-…`.

## Suspend billing ACTIVE

Not expiry-certified. Pause never applied (`STRIPE_PAUSE_FAILED`). A later accidental 7-day grace on another client (stale step-up token still valid) is **not** Suspend Billing expiry proof. That grace was revoked via UI at `20:01:03Z`.

## Other duration controls

Grant grace, sponsored, retention, waive, recovery, restrict were executed then **revoked** (not waited to natural expiry). They share `process_commercial_entitlement_expiry` / `expire_stale_governance_row`. Equivalent job-path expiry was proven on the cancelled suspend fixture only.

## Recovery

Expiry unsets commercial overlay, recomputes canonical from underlying lifecycle, does not recreate Stripe subscriptions. Cancelled fixture returned to cancelled effective access.
