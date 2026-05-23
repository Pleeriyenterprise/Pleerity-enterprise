# Watchlist — F2 `ops_runtime_02_work_orders`

## Resolved (post-deploy `20260523T152330Z`)

- G9 issue→WO idempotency — **PASS** on deployed staging
- Lifecycle completion path — **PASS** (fixture contractor + quote gates)
- G10 terminal reopen — **PASS** (400 on client PATCH)
- Convergence — **PASS** (WO `COMPLETED` stable after 60s)

## Residual (non-blocking)

- **Historical marker WO rows:** pre-remediation duplicate WOs remain visible on pilot (`marker_wo_rows: 2` includes prior-run debt; G9 probe for current issue shows single row)
- **Render GIT_COMMIT_SHA:** `/api/version` returns `unknown`; use behavioral smoke + bundle for deploy proof until CI env wired

## Programme

- F3 (`ops_runtime_03_contractor`) **may proceed** per programme execution order
