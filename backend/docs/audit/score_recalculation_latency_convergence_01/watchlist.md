# Watchlist — score recalculation latency

## Post-deploy closeout (2026-06-03) — PARTIAL

### Verified on staging
- [x] Frontend bundle includes score cognition / Updating / pending copy (`main.75e503d8.js`)
- [x] API returns `score_cognition_line` per property (blocker-accurate)
- [x] Regression suites pass locally
- [x] Browser dashboard screenshots captured (before / pending / converged)

### Not verified on staging (blockers)
- [ ] `compliance_score_pending=true` immediately after trigger — **REQUEUE_DRIFT** on DONE duplicate correlation
- [ ] Worker convergence latency measurement
- [ ] Pending-state “Updating…” visible in browser (no pending flag observed)

### Fix pending deploy
- [ ] Ship `regenerated_from_done_duplicate` queue handling (local fix after closeout)
- [ ] Re-run `python scripts/score_recalculation_latency_post_deploy_closeout_01.py`
- [ ] Provide `STAGING_ADMIN_PASSWORD` for admin recalc trigger (preferred over requirements/sync)

### Monitor
- [ ] `compliance_score_pending` stuck >10 minutes
- [ ] Queue backlog / worker SLA
