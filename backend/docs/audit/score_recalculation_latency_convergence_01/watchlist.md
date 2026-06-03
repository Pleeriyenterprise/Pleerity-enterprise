# Watchlist — SCORE-RECALCULATION-LATENCY-CONVERGENCE-01

## Post-deploy verification
- [ ] Submit declaration → property shows Updating… / calculating (not stale Elevated risk)
- [ ] Verify document → pending state → score converges within worker SLA
- [ ] Portfolio with 1 pending property shows partial + pending note

## Monitor
- [ ] compliance_recalc_queue backlog depth
- [ ] Properties with compliance_score_pending=true > 10 minutes (stuck marker)
- [ ] activation gate deferrals without propagation_notice

## Residual
- Outcome engine sync recalc vs async queue mixed semantics (documented, not unified)
