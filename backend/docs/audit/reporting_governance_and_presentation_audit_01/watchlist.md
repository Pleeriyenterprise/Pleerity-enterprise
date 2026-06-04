# Watchlist — reporting governance (2026-06-04)

## Primary: REPORT_TRUTH_DRIFT

### Operational (dangerous)

- [ ] Staging proof: dashboard 43 vs compliance CSV 49 vs requirements tracked 47 requirements (same session)
- [ ] Dashboard `compliant` uses portal stats bucket; Requirements page uses lifecycle VERIFIED — compliant 1 vs 0
- [ ] Evidence Readiness `GET /reports/{id}/download` regenerates live data — challenge/audit risk
- [ ] Compliance summary CSV `compliance_status` from DB property field vs live dashboard RAG
- [ ] Scheduled report CSV may be generated before async score recalc completes
- [ ] Legacy `POST /client/evidence-pack/jobs` ZIP must not be sold as regulator-ready

### Cosmetic

- [ ] jsPDF compliance PDF vs ReportLab professional PDF — typography and metadata parity

### Strong paths (no change required for audit)

- Governed audit evidence pack v2 (`compliance_audit_evidence_pack_service`, manifest + SHA-256)
- Score drivers CSV `# export_snapshot_generated_at` / `SCORING_SEMANTICS_EXPORT_V1` contract
- Export rate limits (`_enforce_report_export_rate`)

### Not in scope as report

- Evidence reminders — email-only (`COMPLIANCE_EXPIRY_REMINDER`), no export surface

### Related audits

- `dashboard_score_widget_semantic_convergence_01` — COUNT_CONVERGENCE_DRIFT
- `portfolio_score_aggregation_audit_01` — persisted mean headline verified
