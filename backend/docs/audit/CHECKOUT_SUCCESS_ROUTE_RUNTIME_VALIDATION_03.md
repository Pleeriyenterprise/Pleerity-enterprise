# Checkout success route — staging runtime validation 03

Programme: `CHECKOUT-SUCCESS-ROUTE-FIX-AND-STRANDED-ONBOARDING-PRODUCTION-PROMOTION-03`

Related: `CHECKOUT_SUCCESS_ROUTE_ROOT_CAUSE_03.md`, `STRANDED_ONBOARDING_E2E_CERTIFICATION_01.md` (`STRANDED_ONBOARDING_VERIFIED`).

## Staging deployment

| Item | Value |
| --- | --- |
| Application SHA | `583c4f9a90e78fb83baf3c9f60b57bf17c9ab5b2` |
| Branch | `develop` (not merged to `main` at time of this proof) |
| Staging API | `https://pleerity-enterprise.onrender.com` |
| `/api/version` | `commit_sha=583c4f9a…`, `environment=staging` |
| Render service | `Pleerity-enterprise` `srv-d68995vpm1nc738v1s70` deploy `dep-da26g3gae00c73c7mp4g` **live** |
| Staging frontend project | `pleerity-enterprise-9jjg` |
| Preview | `https://pleerity-enterprise-9jjg-pybmokp1a-victory-aigbochies-projects.vercel.app` `dpl_HEda8CLTXLqb4QMmNUL2zepoGKjT` **Preview** (not `--prod`) |
| Alias | `https://pleerity-enterprise-9jjg.vercel.app` → that preview |
| Bundle | `static/js/main.677c2b2d.js` |
| API host in bundle | `https://pleerity-enterprise.onrender.com` |
| Production API host in bundle | absent |
| Production Render | unchanged (`b6b7ddf5`, service `srv-d8m59gmgvqtc73cmbu6g`) |

Route fingerprint: bundle contains `checkout-success-page`, `checkout-success-missing-session`, `Checkout complete`, `preserve_existing`, `release_and_restart`.

## Direct route proof (Playwright, no payment)

| Path | Result |
| --- | --- |
| `/checkout/success` | Success page `checkout-success-missing-session`. No `hero-cta-primary`. URL unchanged. |
| `/checkout/success?session_id=cs_test_abcdefghijklmnopqrstuv` | Success page `checkout-success-invalid-session`. Session id preserved in URL and on page. No homepage. |
| `/checkout/success?session_id=not-a-session` | Same invalid-session page. No homepage. |

Screenshots: `backend/docs/audit/checkout_success_03/screenshots/route_*.png`.

## Real Stripe test checkout

Fixture: `so.success.202608181435@yopmail.com` / `f44b8fd0-571e-418c-be75-3e6bec76a42b` / `PLE-CVP-2026-000074`.

1. Public intake submit 200.
2. Admin recovery `regenerate_payment` with `promo_decision=apply_selected`, invite `STAGINGSO01` 200. Continuation email `ADMIN_MANUAL` **DELIVERED**.
3. Stripe Checkout: **£0.00** due today, 100% off for 2 months, **customer-entered promo UI count = 0**.
4. Test card completed. Final URL:

   `https://pleerity-enterprise-9jjg.vercel.app/checkout/success?session_id=cs_test_a1wgVR4vNn3aJle59Y2xNpvzrvABi6ECLR3LP5IhiF3S3nHy90M6uNwXhh`

5. Rendered copy: “Checkout complete” / “Your payment has been received. We are continuing your account setup.” Session id shown. **Not** the marketing homepage.
6. `GET /api/portal/setup-status?session_id=cs_test_a1wgVR4v…` → 200, same `client_id`, `payment_state=paid`, `provisioning_status=COMPLETED`, `next_action=set_password`.
7. Client `PROVISIONED`, subscription `ACTIVE`, left Pending Setup. Postmark `SUBSCRIPTION_CONFIRMED` and `WELCOME_EMAIL` **DELIVERED**.
8. Release of this provisioned/activation-incomplete row **blocked** (`400` `MODE_CLASSIFICATION_MISMATCH`).

Machine-readable: `backend/docs/audit/checkout_success_03/runtime_03.json`.

## Verdict for this phase

```text
GO_FOR_STRANDED_ONBOARDING_PRODUCTION_PROMOTION
```
