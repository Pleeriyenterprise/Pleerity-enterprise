# Watchlist — Score scope deployment + codepath diagnostic

## Root cause (resolved in code)

**INPUT_SCOPE_DRIFT** — `calculate_compliance_score` passed score-scoped `enriched_portal` (8 rows from partial `client_row` filter) into `apply_registry_display_semantics` instead of full-registry enriched rows (10). Dashboard/requirements already used full client doc.

## Fix shipped (pending Render redeploy)

- `compliance_score.py`: load `registry_enriched` with full client doc for display semantics merge only
- Score-scoped `portal_reqs` unchanged → `score_tracked_requirement_count` stays 8
- Expected after deploy: visible=10, lifecycle=10, score_tracked=8, grouping note populated

## Deploy proof reference

- Staging `/api/version`: `9fe393b0` (includes b0510957) — deployment was **not** the blocker
- `/api/health` lacks commit SHA (minor observability gap; use `/api/version`)

## Re-run after redeploy

```bash
cd backend
python scripts/score_scope_backend_deploy_closeout_01_execute.py
```

## Classification history

| Programme | Classification |
|-----------|----------------|
| SCORE-SCOPE-BACKEND-DEPLOY-CLOSEOUT-01 | SCORE_COUNT_SEMANTIC_DRIFT |
| SCORE-SCOPE-DEPLOYMENT-AND-CODEPATH-DIAGNOSTIC-01 | INPUT_SCOPE_DRIFT (fix applied; staging pending) |
