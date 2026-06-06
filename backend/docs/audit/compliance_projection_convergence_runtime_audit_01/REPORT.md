# COMPLIANCE-PROJECTION-CONVERGENCE-RUNTIME-AUDIT-01

**Classification:** PARTIAL
**Generated:** 2026-06-06T21:50:45.294983+00:00

## Summary

Converged operational projections across Today inbox, compliance score stats, property health RAG, dashboard quick actions, and scheduled compliance status jobs.

## Fixes

1. **Property health** — `GET /client/properties` now computes live RAG via `property_compliance_status_service` (enriched requirements). Scheduled job aligned.
2. **Today / inbox** — `requirement_has_active_negative_actionability` limited to `OPERATIONAL_INBOX_ATTENTION_REASONS`; assurance-only review suppressed when obligation recorded on file.
3. **Score stats** — `stats.compliant` / `stats.satisfied` use `is_requirement_satisfied` (includes declaration/recorded-on-file paths).
4. **Quick actions** — Recommendations from `compliance_top_next_actions` filtered when requirement no longer has operational negative actionability.
5. **Dashboard** — `/client/dashboard` compliance summary uses `compute_client_portal_requirement_stats` on enriched rows.

## Regression

`projection_regression_runtime.json`: exit_code=0

## Staging

See `projection_browser_runtime.json`.
