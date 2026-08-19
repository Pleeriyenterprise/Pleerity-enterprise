# Customer communication — production smoke 04

Programme: `CUSTOMER-COMMUNICATION-PRODUCTION-PROMOTION-GATE-04`

Does not recertify staging runtime. Does not fail a real customer payment, cancel a real subscription, or move a real renewal date.

Related: `CUSTOMER_COMMUNICATION_P0_P1_CLOSURE_03.md`, `CUSTOMER_COMMUNICATION_STAGING_RUNTIME_CERTIFICATION_02.md`.

## Deployment integrity

| Check | Result |
| --- | --- |
| Production SHA | `626f35de80ca71dd03b4782552126213cab414b4` |
| `/api/version` environment | `production` |
| `/api/health` after recycle | `healthy`, readiness `ready`, scheduler `heartbeat_fresh` (`last_heartbeat_at=2026-08-19T07:53:02Z`) |
| Homepage `/`, `/login`, `/login/admin` | 200 |
| Frontend bundle | `main.b993e884.js` (unchanged; frontend not promoted) |
| Stripe webhook route | live (`POST` unsigned → 400 signature) |
| Error-level app logs since deploy start | none through `07:55Z` |

## Code integrity on promoted SHA

Confirmed in merge tree `626f35de` (contains `0097b85f`):

| Contract | Evidence |
| --- | --- |
| One requirement → one reminder email | `jobs.py`: “One independently governed email per eligible requirement”; loop `for item in overdue_requirements + expiring_requirements` |
| Per-requirement idempotency | `daily_compliance_reminder_item_idempotency_key(..., requirement_id=...)` |
| Requirement-specific CTA | `client_portal_requirement_item_url` when `first_item` present; `single_requirement_reminder: True` |
| Basil invoice subscription id | `subscription_id_from_stripe_invoice_dict` used in payment-failed and invoice-paid handlers |
| Cancellation recipient fallback | `resolve_client_notification_email`: `contact_email or email` |
| Renewal windows | scheduler job `subscription_lifecycle` at 09:15 UTC registered on the new instance |
| Contractor assignment | staging-proven path unchanged; eligibility guards not weakened in this merge |

## Path smoke (no customer mutation)

| Domain | Production exercise | Result |
| --- | --- | --- |
| Compliance reminders | Code + job registration; no real-customer fixture send | PASS (code/job). 09:00 cron send counts NOT_RETRIEVED (Render MCP). |
| PAYMENT_FAILED | Webhook route live; no manufactured failure | NOT_EXERCISED naturally. Staging 03 preserved. |
| SUBSCRIPTION_CANCELED | Resolver in promoted SHA; no real cancel | NOT_EXERCISED naturally. Staging 03 preserved. |
| Renewal 7d / 3d | Job registered; no renewal-date mutation | NOT_EXERCISED naturally before 09:15 UTC. Staging 03 preserved. |
| CONTRACTOR_ASSIGNED | No internal production fixture used | NOT_EXERCISED. Staging 03 preserved. |
| Onboarding state copy | Code in SHA; no Day-2 mutation | PASS (code). Runtime 02 preserved. |
| Monthly digest | Regression suite passed; remains aggregate | PASS (regression). |
| Notification preferences | Regression suite passed | PASS (regression). |

## Non-regression (public / deployment)

| Domain | Result |
| --- | --- |
| Authentication public routes | PASS (`/login`, `/login/admin` 200) |
| Production operator session | **NOT_EXERCISED** (no production admin login in this gate) |
| Commercial Controls | Not reopened; preserve `COMMERCIAL_CONTROLS_VERIFIED` |
| Stranded Onboarding | Not reopened; preserve `STRANDED_ONBOARDING_VERIFIED` |
| Customer portal routes | Public SPA 200; authenticated portal **NOT_EXERCISED** |

## Billing webhooks in the initial window

```text
NOT_NATURALLY_EXERCISED_IN_PRODUCTION_WINDOW
```

No `invoice.payment_failed` / cancellation / renewal customer emails were manufactured. Render request logs for `/api/webhooks/stripe` were empty in `07:41Z`–`07:56Z`. This does not invalidate staging certification.
