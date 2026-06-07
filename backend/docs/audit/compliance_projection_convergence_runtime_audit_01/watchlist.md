# Watchlist — Today hero + score scope post-deploy closeout

## Open blocker

- **Backend deploy pending for score scope semantics** — Staging frontend (`main.239bf468.js`) includes fix markers from `b0510957`, but `/api/client/compliance-score` still returns `lifecycle_satisfied_count=8` and no registry grouping note. Compliance Score page renders **8 requirements satisfied on file** while Requirements registry shows **10/10**.

## Verified post-deploy

- Today hero convergence on Sophie Walker staging account: `urgent_count=0`, Needs action 0, no Do this next, no file-review assurance elevation.
- Dashboard: 10 active requirements / 8 score-tracked obligations.
- Properties: 2 Valid / 0 Attention needed.
- Score remains 93/100 (assurance weighting unchanged).
- Targeted regression: 40 backend + 9 frontend tests pass.
- Non-regression scenarios pass (missing/rejected/overdue operational; assurance-only suppressed).

## Re-run after backend deploy

```bash
cd backend
python scripts/today_hero_and_score_scope_post_deploy_closeout_01_execute.py
```

## Expected final state (VERIFIED_OPERATIONALLY)

- Today calm (no false Needs action / Do this next).
- Compliance Score: **10 requirements satisfied on file**, **Score based on 8 score-tracked obligation groups**, grouping note visible.
- API: `lifecycle_satisfied_count >= 10`, `score_tracked_requirement_count == 8`, `grouping_note` populated.

## Classification history

| Programme | Classification |
|-----------|----------------|
| TODAY-HERO-AND-SCORE-SCOPE-FINAL-CONVERGENCE-01 | PARTIAL (pre-deploy) |
| TODAY-HERO-AND-SCORE-SCOPE-POST-DEPLOY-CLOSEOUT-01 | SCORE_COUNT_SEMANTIC_DRIFT |
