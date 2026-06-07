# Watchlist — Score scope backend deploy closeout

## Open blocker (critical)

- **Render backend not deployed with `b0510957` score-scope semantics** — After 12 API polls (~6 min), staging `/api/client/compliance-score` still returns:
  - `visible_requirement_count=8` (expected 10)
  - `lifecycle_satisfied_count=8` (expected 10)
  - `grouping_note=null` (expected dedupe note)
- **Action:** Manually redeploy **`pleerity-api`** on Render from `main` (≥ `b0510957`).

## Verified (unchanged post-deploy)

- Today calm: `urgent_count=0`, Needs action 0, no Do this next.
- Dashboard: 10 active in Requirements / 8 score-tracked obligations.
- Requirements: 10/10 satisfied.
- Properties: 2 Valid / 0 Attention needed.
- Score: 93/100 with assurance confidence explanation.
- Targeted regression: 40 backend + 9 frontend tests pass.

## Re-run after Render redeploy

```bash
cd backend
python scripts/score_scope_backend_deploy_closeout_01_execute.py
```

Optional longer poll:

```bash
SCORE_SCOPE_DEPLOY_POLL_ATTEMPTS=40 SCORE_SCOPE_DEPLOY_POLL_SECONDS=30 python scripts/score_scope_backend_deploy_closeout_01_execute.py
```

## Expected final state (VERIFIED_OPERATIONALLY)

- API: `visible_requirement_count=10`, `lifecycle_satisfied_count=10`, `score_tracked_requirement_count=8`, `grouping_note` populated.
- Compliance Score page: **10 requirements satisfied on file**, **Score based on 8 score-tracked obligation groups**, grouping note visible.
- All surface parity checks pass.

## Classification history

| Programme | Classification |
|-----------|----------------|
| TODAY-HERO-AND-SCORE-SCOPE-POST-DEPLOY-CLOSEOUT-01 | SCORE_COUNT_SEMANTIC_DRIFT |
| SCORE-SCOPE-BACKEND-DEPLOY-CLOSEOUT-01 | SCORE_COUNT_SEMANTIC_DRIFT |
