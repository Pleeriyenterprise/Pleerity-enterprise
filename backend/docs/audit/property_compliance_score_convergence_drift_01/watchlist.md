# Watchlist — PROPERTY-COMPLIANCE-SCORE-CONVERGENCE-DRIFT-01

## Post-deploy
- [ ] Run admin compliance score repair / enqueue recalc for affected client portfolio
- [ ] Verify Cooper Close: score_cognition_line explains assurance confidence (not bare "No open gaps")
- [ ] Verify Ali Cave: missing_count=1 aligns with where-to-focus line
- [ ] Confirm quick actions no longer say "Upload and verify" for satisfied/platform-review rows

## Residual risk
- Persisted scores remain stale until recalc worker processes queue (`compliance_score_pending`)
- Portfolio headline score unchanged until per-property recalc completes

## Regression monitors
- Requirement lifecycle convergence tests
- Property page attention convergence (missing doc KPIs)
- Escalation queue / Command Centre / Today surfaces
