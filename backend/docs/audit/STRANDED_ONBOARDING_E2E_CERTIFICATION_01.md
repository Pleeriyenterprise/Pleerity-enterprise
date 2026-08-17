# Stranded onboarding — E2E certification 01

**Verdict:** `STRANDED_ONBOARDING_VERIFIED`

Production was not touched. Work stayed on `develop` and staging. Commercial Controls remain `COMMERCIAL_CONTROLS_VERIFIED`. Scenario C (customer-entered Stripe promotion codes) remains unsupported (`allow_promotion_codes` is unset on recovery Checkout Sessions).

## Deployment

| Item | Value |
| --- | --- |
| Implementation SHA | `7f3ba4fcc2b733e0d41ced95d5646f5cb3e41ac9` |
| Live-mode coupon 409 + atomic release | `ccd87cc3125a61b423461e73dfd19c8e6eced716` |
| Approved-promo Stripe-mode filter | `d6779809a3cd276e4bc41828d57e29e1490ebd18` |
| Unpaid release while checkout is fresh | `7b2f83fd5fd77cf8a844fcd9b897ebc43f7fff50` |
| Staging `/api/version` at recert | `7b2f83fd5fd77cf8a844fcd9b897ebc43f7fff50`, `environment=staging` |
| Staging Render | `Pleerity-enterprise` `srv-d68995vpm1nc738v1s70` `dep-da1kr1id0e5s73bg0pd0` |
| Staging frontend | `https://pleerity-enterprise-9jjg.vercel.app` bundle `main.5fcacb3c.js` |
| Production | untouched; not merged to `main` |

## Fixtures (17 Aug 2026 stamp `202608171708`)

| Journey | Email | Client |
| --- | --- | --- |
| Recovery + validated promo | `so.promo.202608171708@yopmail.com` | `718fae2d-5063-4bd6-9e4f-6f03837748e5` / `PLE-CVP-2026-000068` |
| Release + restart | `so.release.202608171708@yopmail.com` | released `40a3f8d3-…` → new `42c3152c-…` / `PLE-CVP-2026-000072` |
| Paid checkout choice | `so.paid.202608171708@yopmail.com` | `1cb4b67d-…` |
| Admin-selected promo | `so.select.202608171708@yopmail.com` | `aa036430-…` |

Staging-valid promo: private invite `STAGINGSO01` mapped to test-mode coupon `STAGINGSO01` (100% repeating 2 months, onboarding waived). Live-mode `PILOTACCESS` is omitted from approved recovery promos on staging test keys.

## Critical journey 1 — proven

1. Preserve-existing regenerate applied `STAGINGSO01`. Hosted Checkout showed **£0.00** due today, **100% off for 2 months**, onboarding waived, **no customer-entered promo control**.
2. After 30 minutes, replacement session `cs_test_a1bF7GMu…` superseded prior session `cs_test_a14AF4om…`.
3. Stripe: old session **`status=expired`**, `payment_status=unpaid`, `discounts=[{coupon:STAGINGSO01}]`, `allow_promotion_codes=null`.
4. Stripe: replacement **`status=complete`**, `payment_status=paid`, same coupon, customer `cus_V5gMT6LAZrW2zp`, subscription `sub_1U5V0HCF0O5oqdUzeaI3RtFj` **active**.
5. Postmark: continuation `ADMIN_MANUAL` **DELIVERED**, then `SUBSCRIPTION_CONFIRMED` and `WELCOME_EMAIL` **DELIVERED**.
6. Same `client_id` throughout. Onboarding **`PROVISIONED`**, subscription **`ACTIVE`**, **not** in Pending Setup. Exactly one active identity.

Playwright followed Stripe `success_url` (`/checkout/success?session_id=…`) but the staging SPA rendered the marketing homepage. Payment, webhook, provisioning, and customer emails still completed. That landing-page flake does not create a duplicate identity.

## Critical journey 2 — proven

Concurrent Release on an unpaid attempt with a still-fresh checkout: **one 200**, one `RELEASE_NOT_ALLOWED` / `already_released`. Released row `onboarding_identity_status=RELEASED_FOR_RESTART`, email vacated, **gone from Pending Setup**, `released_canonical_email` retained. Pre-release Checkout Session `cs_test_b1laUYIY…` is Stripe **`expired`**. Email `check-email` **available**. Concurrent re-register: **one 200** (`42c3152c-…` with `restarted_from_client_id=40a3f8d3-…`) and one `EMAIL_TAKEN`. Exactly one active identity for the canonical email.

## Negative paths / choices

| Path | Result |
| --- | --- |
| Release of provisioned client | `NOT_ELIGIBLE` |
| Release of `ACTIVATION_INCOMPLETE` | `MODE_CLASSIFICATION_MISMATCH` |
| Release of `DUPLICATE_RECOVERY_RISK` | `NOT_ELIGIBLE` |
| Paid checkout (no promo) | 200, Stripe **£68.00**, no customer promo field |
| Admin-selected `STAGINGSO01` | 200, Stripe **£0.00**, coupon applied, no customer promo field |
| Existing grant/bypass/waive controls | 200 |
| Pending Setup auto-drop | Released and provisioned attempts not listed; history GET-able by id |

Machine-readable: `stranded_onboarding_runtime_results_01.json`, `stranded_onboarding_runtime_recert_02.json`.
