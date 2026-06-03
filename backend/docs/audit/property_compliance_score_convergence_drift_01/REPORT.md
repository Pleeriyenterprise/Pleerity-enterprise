# PROPERTY-COMPLIANCE-SCORE-CONVERGENCE-DRIFT-01

Verified at: 2026-06-03T20:45:08.204612+00:00

## Problem
Requirement surfaces converged (Operating, Compliance, Documents) but score/risk cognition remained inconsistent:
55/100 Elevated risk alongside "No open gaps" and stale "Upload and verify" quick actions.

## Root cause
Three competing read models: persisted v2 score (NEEDS_REVIEW at 0.5), catalog gap KPIs (converged), and dashboard gap line (KPI-only).

## Fix
1. **Scoring engine** — satisfaction-aware assurance fractions; documentation bucket includes satisfied obligations
2. **Enrichment** — `enrich_requirements_for_client` before score compute
3. **Cognition service** — `score_cognition_line` / `score_risk_explanation` on portfolio API
4. **Dashboard** — prefer cognition line; assurance quick-action copy

## Classification
PARTIAL — code convergence complete; browser proof pending post-deploy recalc.

## Tests
Backend: PASS
