# Stranded onboarding — production smoke 03

Programme: `CHECKOUT-SUCCESS-ROUTE-FIX-AND-STRANDED-ONBOARDING-PRODUCTION-PROMOTION-03`

Does not recertify SO-01. Does not reopen Commercial Controls. No live customer Stripe charge was created.

Related: `CHECKOUT_SUCCESS_ROUTE_ROOT_CAUSE_03.md`, `CHECKOUT_SUCCESS_ROUTE_RUNTIME_VALIDATION_03.md`, `STRANDED_ONBOARDING_FOCUSED_REGRESSION_03.md`, `STRANDED_ONBOARDING_PRODUCTION_PROMOTION_03.md`, `STRANDED_ONBOARDING_E2E_CERTIFICATION_01.md`.

Machine-readable: `backend/docs/audit/checkout_success_03/production_smoke_03.json`.

## Checkout success route

Direct production URLs (Playwright, no payment):

| Path | Result |
| --- | --- |
| `https://pleerityenterprise.co.uk/checkout/success` | Success page `checkout-success-missing-session`. No `hero-cta-primary`. URL unchanged. |
| `…/checkout/success?session_id=cs_test_safe_reference_0001` | Success page `checkout-success-invalid-session`. Session id shown on the page and kept in the URL. Not the marketing homepage. |
| `…/checkout/success?session_id=not-a-session` | Same invalid-session page. Session id preserved. Not homepage. |

Expected console/network: `GET /api/portal/setup-status?session_id=cs_test_safe_reference_0001` returns **404** (unknown reference). The page stays on the continuation experience.

Screenshots: `backend/docs/audit/checkout_success_03/screenshots/prod_route_*.png`.

A real production Stripe Checkout was **not** completed (no customer billing mutation). Staging already proved Stripe → `/checkout/success?session_id=…` → continuation page on `583c4f9a`.

## Deployment integrity

| Check | Result |
| --- | --- |
| Production SHA | `1fcb5fbcdf99ded01a45fe2fcf1123587efd117d` |
| `/api/version` environment | `production` |
| `/api/health` | `healthy`, readiness `ready`, scheduler `heartbeat_fresh` at smoke (`2026-08-18T15:04:08Z`) |
| Homepage `/`, `/login`, `/login/admin` | 200 |
| Bundle | `main.b993e884.js` |
| API host | `https://api.pleerityenterprise.co.uk` |
| Staging onrender host in bundle | absent |
| `pk_live` in bundle | present |
| `allow_promotion_codes` in bundle | absent |

`pk_test` also appears as a string in the production bundle (same Stripe account test publishable key). Backend boot log is `STRIPE_MODE=live`. This fingerprint is not introduced by the checkout-success component; it is recorded, not treated as a customer-route defect.

## Pending Setup / recovery UI

Production admin login was **not** exercised (no `PROD_ADMIN_*` in this session; same stance as `PRODUCTION_PROMOTION_SMOKE_07.md`).

Deployment integrity for the recovery panel:

| Marker in `main.b993e884.js` | Present |
| --- | --- |
| `release_and_restart` | yes |
| `preserve_existing` | yes |
| `apply_selected` | yes |
| customer-entered Stripe promo field (`allow_promotion_codes`) | **no** |

Release-and-restart eligibility remains server-governed. Staging smoke already showed a provisioned/activation-incomplete row rejected with `MODE_CLASSIFICATION_MISMATCH`.

## Promo recovery (production UI fingerprint)

| Control | Production bundle |
| --- | --- |
| Apply existing promo (`preserve_existing`) | present |
| Normal paid checkout | unchanged path; present in recovery copy |
| Approved promo selection (`apply_selected`) | present |
| Customer-entered Stripe promotion-code field | **disabled** (`allow_promotion_codes` absent) |

## Commercial Controls

Not reopened. Preserve `COMMERCIAL_CONTROLS_VERIFIED`.

## Authentication

| Check | Result |
| --- | --- |
| Public login routes | 200 |
| Production operator session | **NOT_EXERCISED** |
| Staging admin against production | not used |

## Observation

| Item | Value |
| --- | --- |
| Start | `2026-08-18T14:52:00Z` |
| Close | `2026-08-18T15:38:00Z` (~46 minutes) |
| Scheduler | `heartbeat_fresh` at close (`15:36:41Z`) |
| Mongo / readiness | `ready`, `degraded=false` |
| Frontend routing | no regression; bundle still `main.b993e884.js`; `/checkout/success?session_id=cs_test_safe_reference_0001` still 200 on the success route |
| Auth | no 401/403 spike |
| HTTP 5xx after `14:52Z` | none |
| Cutover-only | one **502** at `14:51Z` while instance count was 0 |
| Smoke-attributed | 404×3 unknown `session_id`; 400×1 malformed `session_id` |
| Stripe webhook errors | none observed in app logs `15:05Z`–`15:38Z` |
| Postmark regression | none observed in that window |
| Duplicate onboarding creation | none observed |
| P0/P1 attributable to promotion | none |

## Final verdict

```text
STRANDED_ONBOARDING_PRODUCTION_DEPLOYMENT_SUCCESSFUL_WITH_CONDITIONS
```

Non-blocking: staging `9jjg` Git Production-on-main alias hygiene. Customer production is on project `pleerity-enterprise`.
