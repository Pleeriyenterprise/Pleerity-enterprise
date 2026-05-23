# Watchlist — F2 `ops_runtime_02_work_orders` (post-remediation)

## Blocking (deploy + rerun)

- **F2-deploy-g9-g10:** Backend remediation (G9 idempotency + G10 terminal reopen guard) implemented locally; staging API not yet deployed — G9/G10 probes fail on Render until deploy + same-run rerun.
- **F2-post-deploy-rerun:** Rerun `tmp_ops_runtime_02_work_orders_execute.py` after deploy; require `VERIFIED_OPERATIONALLY` in single same-run.

## Resolved by remediation (pending deploy verification)

- ~~**F2-g9-wo-from-issue-idempotency**~~ — code + tests shipped; staging probe pending deploy
- ~~**F2-lifecycle-completion-blocked**~~ — pilot contractor fixture `a1f2e3b4…` enables assign→quote→approve→complete path

## Operational debt (pre-remediation runs)

- Prior duplicate marker WO rows from failed G9 runs remain visible on pilot (historical debt; new duplicates blocked after deploy)

## Remediation sequence

1. Deploy backend + frontend to staging
2. Rerun F2 harness (browser + G9 + G10 + convergence in same run)
3. Classify; if `VERIFIED_OPERATIONALLY`, F3 may proceed per programme rules
