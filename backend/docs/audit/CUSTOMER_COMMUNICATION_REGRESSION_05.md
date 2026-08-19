# Communication regression 05

## Focused Cleanup 05 + P0/P1 suite (local)

Primary command included orchestrator, presentation, reminder idempotency, remediation 02, billing webhooks, onboarding governance, billing period, billing phase B, reminder truth/governance.

| Metric | Value |
| --- | --- |
| PASSED | 86 (first focused run) / 132 when monthly digest + extra suites included before excluding pre-existing digest copy tests |
| FAILED (cleanup/P0/P1 required) | 0 |
| SKIPPED | 22 (integration / live-service skips in those files) |
| PRE_EXISTING_FAILURES | `tests/test_monthly_digest_email_copy.py` — 2 failed (`missing evidence` phrase in digest body; `governance and operational review` copy). **Not caused by Cleanup 05 diffs.** Not in Gate 04 promotion-critical list. MONTHLY_DIGEST renderer was not modified. |
| NEW_FAILURES | 0 on the required communication suites |

The four Gate 04 orchestrator failures (`resolve_greeting`) now **pass**.

## Mandatory invariants (unit / prior staging 02–03)

| Invariant | Result |
| --- | --- |
| Scottish landlord registration reminder — that requirement only | PASS (remediation 02 tests) |
| HMO fire-safety reminder — that requirement only | PASS |
| Two eligible requirements → two messages | PASS |
| Second scheduler run → no duplicate | PASS (idempotency tests; staging 02) |
| PAYMENT_FAILED meaningful | PASS |
| SUBSCRIPTION_CANCELED access timing | PASS |
| Renewal 7d/3d subject/body timing | PASS |
| CONTRACTOR_ASSIGNED usable | PASS (unit) |
| Onboarding no completed-milestone instruction | PASS Day 0/1; Day 2+ adapted |
| MONTHLY_DIGEST remains aggregate | PASS (not rewritten) |
