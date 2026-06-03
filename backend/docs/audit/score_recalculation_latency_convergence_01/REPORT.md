# Score recalculation latency — audit + post-deploy closeout

## Programmes
1. **SCORE-RECALCULATION-LATENCY-CONVERGENCE-01** @ `0a184409` — code convergence
2. **SCORE-RECALCULATION-LATENCY-POST-DEPLOY-CLOSEOUT-01** — staging operational proof

## Post-deploy closeout summary

| Check | Result |
|-------|--------|
| Deploy verified | YES — frontend markers + API health |
| Regression tests | PASS |
| Pending visible after trigger | NO — REQUEUE_DRIFT |
| Stale Elevated risk during pending | N/A (no pending observed) |
| Worker convergence | Not observed |
| Browser screenshots | YES |
| Classification | **PARTIAL** |

## Root cause (closeout)
`POST /properties/{id}/requirements/sync` uses fixed correlation `REQUIREMENTS_SYNC:{property_id}`. When the queue row is already **DONE**, duplicate suppression on staging build `0a184409` did not regenerate the job or set `compliance_score_pending`. Admin recalc trigger unavailable (401 — staging admin credentials not in environment).

## Remediation (local, pending deploy)
Regenerate DONE duplicate queue rows to PENDING and set `compliance_score_pending=true` (`regenerated_from_done_duplicate`).

## Re-run instructions
```bash
export STAGING_ADMIN_PASSWORD=...
python backend/scripts/score_recalculation_latency_post_deploy_closeout_01.py
```

Expected after fix deploy: pending within seconds, convergence <2 min, classification **VERIFIED_OPERATIONALLY**.
