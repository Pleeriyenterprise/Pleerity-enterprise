# Customer communication — production conditions 04

Programme: `CUSTOMER-COMMUNICATION-PRODUCTION-PROMOTION-GATE-04`

These do not hide a live customer-truth defect.

## Carried from staging Closure 03 (accepted)

1. Stripe event resend is not available through the Stripe MCP OpenAPI used for certification. Unsigned POSTs return `400 Invalid webhook signature`. Event-id idempotency remains in code.
2. Cancel-at-period-end *deletion* customer email was not waited through on staging. Immediate `customer.subscription.deleted` access-date authority was proven.
3. P2 `resolve_greeting` NameError on some DB-template finalize paths remains. Focused orchestrator tests still fail 4 cases. Promoted billing emails are code-built and do not use that path.

## Production-window conditions

1. **Frontend not promoted** — no frontend diff. Bundle remains `main.b993e884.js`.
2. **Billing webhooks not naturally exercised** in the initial post-deploy window. Staging 03 remains the runtime proof.
3. **Contractor assignment not exercised** on production (no internal fixture). Staging 03 remains the runtime proof.
4. **Stripe live MCP** could not list live webhook endpoints (`No account found` for livemode). Production route was proven by unsigned POST → 400 signature. Boot log: `STRIPE_MODE=live`.
5. **Mongo Atlas / Sentry MCP** unauthenticated in this session. Health + Render logs used instead. No Mongo growth anomaly observed from API health/memory.
6. **Transient recycle P1** `Scheduler heartbeat stale` (`6a856036eb413d81cff75bf4`) at `07:50:14Z`, with an internal operator alert email. Heartbeat recovered `07:51`/`07:53`. Same governed-startup pattern as prior production promotions. Not a customer communication defect.
7. **First-cron send counts not retrieved.** Render MCP became unavailable after ~08:01Z, so 09:00 `daily_reminders` and 09:15 `subscription_lifecycle` log lines were not captured in this session. Scheduler heartbeat remained fresh through 09:27Z. Not treated as a measured amplification defect.
8. **Frontend JS asset 404** when fetching `https://pleerityenterprise.co.uk/static/js/main.b993e884.js` directly (homepage HTML still references that bundle and returns 200). Same fingerprint as the pre-promotion SPA; frontend was not deployed.

## P2/P3 backlog (not reopened)

* `resolve_greeting` DB-template NameError
* tenant RAG terminology
* support acknowledgement copy
* dead notification keys
* event-registry drift
* emoji subject polish
* COMPLIANCE_ALERT same-day overlap
* remaining onboarding Day 2+ content polish
* any stale inventory documentation
