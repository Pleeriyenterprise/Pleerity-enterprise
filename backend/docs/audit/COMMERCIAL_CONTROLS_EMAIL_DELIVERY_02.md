# Commercial Controls — Email delivery 02

**Runtime status:** **UNVERIFIED**

Staging execute with `send_customer_email=true` was not run. Operator login did not succeed (401 stale credentials after lock expiry).

Code path (not a substitute for Postmark proof):

- Continuity send isolated (25s timeout)
- Idempotency key `commercial_entitlement_{client_id}_{governance_id}_{action}`
- Suspend billing subject/body generated from committed preview (cancelled vs active)
- Checkbox off → `customer_notification_status=skipped`

`queued` is not treated as delivered.
