# SCORE-SCOPE-DEPLOYMENT-AND-CODEPATH-DIAGNOSTIC-01

**Classification:** `INPUT_SCOPE_DRIFT`  
**Generated:** 2026-06-07T14:29:14Z  
**Target:** Sophie Walker (`PLE-CVP-2026-000023`)

## Executive summary

Render **is** deployed with post-`b0510957` code (`/api/version` commit `9fe393b0`). Root cause is **not** deployment mismatch. `apply_registry_display_semantics` was called in `calculate_compliance_score`, but received **score-scoped enriched rows (8)** from a partial `client_row` Mongo projection while dashboard/requirements use the **full client document (10 rows)**. Registry display overrides never saw the 2 excluded Willow Grove requirements (`epc`, `fire_alarm`).

**Fix applied:** load `registry_enriched` via full-client filter solely for `apply_registry_display_semantics`; score-scoped `portal_reqs` pipeline unchanged (score formula untouched).

## PART 1 — Deployment identity

| Check | Result |
|-------|--------|
| `/api/version` commit | `9fe393b0` (includes b0510957) |
| `/api/health` commit SHA | **Not exposed** (observability gap on health only) |
| Service | `pleerity-api` on Render |

**Ruled out:** `DEPLOYMENT_MISMATCH`

## PART 2 — API route trace

Compliance Score page → `GET /client/compliance-score` → `calculate_compliance_score`. Same route (not bypass). Dashboard uses `GET /client/dashboard` with full client doc for semantics.

## PART 3 — Codepath probe

| Surface | visible | lifecycle | score_tracked | grouping_note |
|---------|---------|-----------|---------------|---------------|
| Staging compliance-score API | 8 | 8 | 8 | null |
| Dashboard API | 10 | 10 | 10 | — |
| Requirements full API | 10 | 10 | 10 | null |
| **Post-fix simulation** | **10** | **10** | **8** | **present** |

Collapse point: `filter_requirement_rows_for_client_runtime_surfaces(..., client_doc=partial_client_row)` in `calculate_compliance_score`.

## PART 4 — Data scope trace

10 visible registry rows; 2 excluded from score-scoped portal projection (Willow Grove `epc` + `fire_alarm`) due to partial client context in planner filter. Both remain lifecycle-satisfied and visible on Requirements page.

## PART 5 — Root cause

**`INPUT_SCOPE_DRIFT`** — correct code deployed, wrong input scope to display semantics merge.

## PART 6 — Minimal fix

`compliance_score.py`: separate `registry_enriched` load with full client doc for `apply_registry_display_semantics` only.

## PART 7 — Verification

Local simulation on staging Requirements full data: **PASS** (10/10/8 + grouping note). Staging live API: **pending redeploy**.

## PART 8 — Regression

41 backend targeted tests **PASS** (including new registry/score-tracked preservation test).

## Next step

Redeploy Render backend and re-run:

```bash
python scripts/score_scope_backend_deploy_closeout_01_execute.py
```

Expected: `VERIFIED_OPERATIONALLY`
