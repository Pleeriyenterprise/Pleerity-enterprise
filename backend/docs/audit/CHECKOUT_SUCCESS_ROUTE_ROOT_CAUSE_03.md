# Checkout success route — root cause 03

Programme: `CHECKOUT-SUCCESS-ROUTE-FIX-AND-STRANDED-ONBOARDING-PRODUCTION-PROMOTION-03`

Related authority: `STRANDED_ONBOARDING_VERIFIED` on `7b2f83fd5fd77cf8a844fcd9b897ebc43f7fff50` (evidence `b3c2d76b`). See `STRANDED_ONBOARDING_E2E_CERTIFICATION_01.md`.

This note does not recertify recovery, promo policy, or email-release.

## Classification

```text
SUCCESS_COMPONENT_DEFECT
```

Contributing factor (not the primary class): `QUERY_HANDLING_DEFECT` — `session_id` was read and then unused.

Ruled out:

| Class | Why not |
| --- | --- |
| `MISSING_ROUTE` | `App.js` already registered `/checkout/success`. |
| `ROUTER_ORDER_DEFECT` | The success route sits with other public onboarding routes, before the `*` → `/` fallback. |
| `SPA_REWRITE_DEFECT` | Vercel SPA fallback served `index.html`; the React route ran. |
| `AUTH_GUARD_DEFECT` | The route was not wrapped in `ProtectedRoute`. |
| `OTHER_VERIFIED_CAUSE` | Not required. |

## Path after Stripe Checkout

1. Recovery or intake checkout is created with `checkout_redirect_urls()` in `backend/services/stripe_service.py`.
2. For non-plan-change journeys, Stripe `success_url` is:

   `{frontend_origin}/checkout/success?session_id={CHECKOUT_SESSION_ID}`

3. Stripe hosted Checkout completes and redirects the customer browser to that URL.
4. The SPA loads. React Router matches `/checkout/success`.
5. **Before this fix**, `CheckoutSuccessRedirect` in `frontend/src/App.js` ran:

   - If `localStorage.pending_client_id` existed (set by the intake wizard in the same browser), redirect to `/onboarding-status?client_id=…`.
   - Else `window.location.href = '/'` — the marketing homepage.

6. Recovery checkout is started by an admin (or a continuation email) in a **different** browser than the original intake. The paying customer therefore has **no** `pending_client_id`. The success URL is correct; the landing page is not.

Certified SO-01 Playwright run observed this exact sequence: Stripe `success_url` contained `/checkout/success?session_id=…`, then the SPA rendered the marketing homepage. Payment, webhook, provisioning, and Postmark still completed. See `STRANDED_ONBOARDING_E2E_CERTIFICATION_01.md`.

## Why `session_id` was insufficient

The component parsed `session_id` from `window.location.search` and never used it. There was no public lookup from Stripe Checkout session → onboarding continuation. `/api/portal/setup-status` accepted only JWT or `client_id`.

## Correct experience (implemented)

After a successful Stripe Checkout, `/checkout/success?session_id=…` must remain a success/continuation page:

- communicate that checkout completed;
- continue onboarding without asking the customer to register again;
- show a waiting state while provisioning is still pending;
- show email / sign-in continuation when provisioning is complete;
- never promise dashboard access before `next_action` says the portal is ready;
- preserve `session_id` on the page for lookup.

## Fix (smallest)

Frontend: replace `CheckoutSuccessRedirect` with `frontend/src/pages/CheckoutSuccessPage.js`. The route path is unchanged. The component never assigns `window.location` to `/`.

Backend: `GET /api/portal/setup-status` accepts optional `session_id` (Stripe Checkout id `cs_…`), rate-limited like `client_id`, resolved via `checkout_sessions.session_id` then `clients.latest_checkout_session_id`. No Stripe live call. Existing `client_id` behaviour is unchanged.

Not changed: public routes, portal login, admin routes, onboarding routes other than this success handler, Stripe Checkout creation, promo policy, `allow_promotion_codes`, email-release, recovery engine, API host configuration.
