# Stranded onboarding — E2E certification 01

**Verdict:** `STRANDED_ONBOARDING_INCOMPLETE`

Production was not touched. Work stayed on `develop` and staging.

## Deployment

| Item | Value |
| --- | --- |
| Implementation SHA | `7f3ba4fcc2b733e0d41ced95d5646f5cb3e41ac9` |
| Remediation SHA (live) | `ccd87cc3125a61b423461e73dfd19c8e6eced716` |
| Staging `/api/version` | `ccd87cc3…`, `environment=staging` |
| Staging Render | `Pleerity-enterprise` `srv-d68995vpm1nc738v1s70` `dep-da1jbnbncjis739grq90` |
| Staging frontend | `https://pleerity-enterprise-9jjg.vercel.app` bundle `main.5fcacb3c.js` |
| Production | untouched |

Remediation on `ccd87cc3`: live-mode Stripe coupons on test-mode checkout return governed `409 STRIPE_PROMO_MODE_MISMATCH` instead of HTTP 500; Release uses atomic `find_one_and_update` so a second concurrent release cannot both succeed.

## What runtime-proved

- Staging health recovered to `healthy` / `heartbeat_fresh` on `ccd87cc3`.
- Dedicated yopmail fixtures created via public `/intake/submit`.
- **Normal paid recovery checkout** created Stripe session `cs_test_b1jZQrXm…`; hosted Checkout showed **£68.00** (onboarding £49 + Solo £19) with **no customer-entered promotion-code control**.
- Grant promo exception, bypass first-time, and waive-onboarding eligibility overrides returned 200 and recorded.
- Release guards rejected provisioned / paid / `ACTIVATION_INCOMPLETE` / `DUPLICATE_RECOVERY_RISK` clients (`NOT_ELIGIBLE` or `MODE_CLASSIFICATION_MISMATCH`).
- First certification pass: unpaid reserved email became available after Release; concurrent re-registration produced **exactly one** 200 and one `EMAIL_TAKEN`; new identity carried `restarted_from_client_id`; released attempt left Pending Setup automatically.
- First pass also showed a race: two concurrent Releases both returned 200 (same client). That is the defect `ccd87cc3` serialises. Re-proof of the race was interrupted by an SSL error on the follow-up `/intake/submit`.

## What is not runtime-proven

- Recovery checkout with a **staging-valid** promo: the only approved code returned by staging is `PILOTACCESS`, whose Stripe coupon `85x6smtg` exists in **live** mode. Staging correctly refuses it (`409`). No test-mode coupon is in the approved list, so preserve/select promo Checkout, discounted amount, Postmark continuation, customer payment, webhook, and auto-exit from Pending Setup after **paid** recovery were **not** completed.
- Customer completing payment and provisioning on the replacement session.
- Postmark delivery of the continuation email (send was not reached on the promo path; paid path used `send_customer_email=false`).
- Admin CCP Playwright: token injection landed on the client Today shell, not Promo & Recovery Controls. Bundle markers for the new UI **are** present in `main.5fcacb3c.js`.

Machine-readable: `stranded_onboarding_runtime_results_01.json`.

| Recovery case | Diagnosis | Admin action | API | DB | Stripe | Promo | Email | Identity | Customer continuation | Verdict |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Expired checkout/no promo | `EXPIRED_CHECKOUT` / paid regenerate | regenerate + `none` | PASS | PASS | session created; £68 shown | none; customer field absent | not sent in this run | unchanged | checkout opened; payment not completed | INCOMPLETE |
| Expired checkout/validated promo | preserve / `PILOTACCESS` | regenerate + `preserve_existing` | 409 governed | n/a | live coupon blocked in test | server-refused | n/a | unchanged | not proven | INCOMPLETE |
| Email reserved/no payment | `EMAIL_RESERVED_NO_CHECKOUT` | release_and_restart | PASS (first pass) | vacated email | n/a | n/a | not sent | new id + `restarted_from` | re-register 1-of-2 | INCOMPLETE (race re-proof pending) |
| Paid/provisioning pending | `PARTIAL_PROVISIONING` / duplicate risk | release rejected | PASS | n/a | n/a | n/a | n/a | protected | n/a | PASS (guard) |
| Password setup pending | `ACTIVATION_INCOMPLETE` | release rejected | PASS | n/a | n/a | n/a | n/a | no release | n/a | PASS (guard) |
| Promo exception | apply_selected `PILOTACCESS` | regenerate | 409 | n/a | live coupon | approved list has no test coupon | n/a | unchanged | not proven | INCOMPLETE |
| Customer-entered promo | n/a | n/a | unused | n/a | no promo-code UI on paid Checkout | n/a | n/a | n/a | n/a | PASS (disabled) |

Customer-entered Stripe promo codes remain out of scope (Scenario C).
