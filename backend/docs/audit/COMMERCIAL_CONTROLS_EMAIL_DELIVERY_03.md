# Commercial Controls — Postmark / email 03

**Runtime SHA:** `7c77391a5ee65f0a85372d9c462448c270b6b066`  
Queued is not treated as delivered.

## Execute with email selected

Provider acceptance is `email_result.outcome = sent` (orchestrator accepted). Delivery is `message_logs.status`.

| Control | Recipient | outcome | message_logs | Notes |
| --- | --- | --- | --- | --- |
| Grant grace period | pleerityenterprise@gmail.com | sent | `ADMIN_MANUAL` **BOUNCED** | Accepted, not delivered |
| Sponsored access | same | sent | `ADMIN_MANUAL` present | Same Gmail bounce class |
| Retention extension | same | sent | `ADMIN_MANUAL` present | |
| Recovery compensation | same | sent | `ADMIN_MANUAL` present | |
| Restrict entitlement | same | sent | `ADMIN_MANUAL` present | |
| Suspend billing (CANCELLED) | allison@yopmail.com | sent | `ADMIN_MANUAL` **DELIVERED** `4eb0a176…` at `2026-08-15T19:41:54Z` | One continuity message; correct recipient; template `ADMIN_MANUAL` |

Cancelled suspend customer copy (authoritative preview, SHA `7c77391a`):

> Temporary Professional plan access has been restored until 2026-08-15. Billing will not be collected during this period. Your underlying account remains cancelled and that status will apply again after 2026-08-15 unless otherwise changed.

Subject: `Temporary access restored on your account`. This is temporary access, not subscription reactivation.

## Execute with email unchecked

Waive onboarding fee: `send_customer_email=false`, `email_result` empty, `customer_notification_status=skipped`. No new continuity send at execute time. Prior `ADMIN_MANUAL` rows on that client are from earlier email-on actions, not this waive.

## Correlation

Idempotency key pattern `commercial_entitlement_{client_id}_{governance_id}_{action}`. `message_logs` correlate by `client_id` + `template_key=ADMIN_MANUAL` + timestamp matching execute.

## One-message rule

Each email-on execute produced one new `ADMIN_MANUAL` row (not a duplicate storm). Duplicate_ignored was not the primary path.
