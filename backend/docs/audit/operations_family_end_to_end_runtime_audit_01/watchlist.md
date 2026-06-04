# Operations watchlist (post invoice closeout)

## Resolved (2026-06-04 closeout)

- [x] INVOICING enabled on Wales HMO pilot via governed `PATCH /api/admin/ops/clients/{id}/feature-flags`.
- [x] Contractor submit → landlord approve → mark paid proven (contractor portal state + PATCH mutations).
- [x] Edge cases: pre-completion blocked, duplicate blocked, needs_info path, permission boundaries.

## Deploy follow-up

- [ ] Deploy `approval_service._invoice_for_api` serialization fix to staging/production so `GET /client/approvals` returns 200 (currently 500 after successful mutations).
- [ ] Re-run `operations_family_invoice_closeout_01_execute.py` after deploy to confirm landlord approvals API JSON (remove `STAGING_APPROVALS_GET_500_UNTIL_DEPLOY` flag).

## Optional hygiene

- [ ] Revert INVOICING manual override on pilot if staging policy requires plan-default only.
- [ ] Clean up marker invoices/work orders from closeout runs if portfolio noise is undesirable.
## Resilience audit watchlist (OPERATIONS-RESILIENCE-AND-CONCURRENCY-AUDIT-01)

- [x] Concurrent assign, accept-after-decline, evidence/close race, invoice/reassign race, rent idempotency key (staging).
- [x] WO-from-issue idempotency, duplicate accept, duplicate invoice (≤ approved quote), duplicate evidence append.
- [x] Risk regen queue summary, reminder/notification governance (code + unit tests).
- [x] Cross-surface convergence and bounded staging read latency.
- [x] Risk churn does not increase duplicate stable keys on pilot.
- [x] Retry-after-timeout accept recovery.
- [x] Security under decline/stale WO; scalability bounded list reads.
- [x] Regression suites (idempotency, queue, webhooks, rent, approval serialization).

## Optional follow-up

- [ ] Extend concurrent landlord invoice approve/mark-paid race with two landlord sessions.
- [ ] Reconcile pre-existing duplicate risk stable keys on Wales pilot (5 types) via governed regen/cleanup if product requires zero duplicates.
