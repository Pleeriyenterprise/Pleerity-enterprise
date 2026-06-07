# TODAY-HERO-AND-SCORE-SCOPE-POST-DEPLOY-CLOSEOUT-01

**Classification:** `SCORE_COUNT_SEMANTIC_DRIFT`  
**Deploy commit verified:** `b0510957`  
**Generated:** 2026-06-07T12:57:30Z  
**Target:** Sophie Walker (`PLE-CVP-2026-000023`, `10b2ddba-e952-4484-91d1-a8f0299d0824`)

## Executive summary

Post-deploy staging verification shows **Today hero convergence is operationally verified** on the Sophie Walker account, but **score scope display semantics remain on pre-fix backend behaviour**. Frontend bundle `main.239bf468.js` includes fix markers; staging API still returns score-scoped lifecycle counts (`lifecycle_satisfied_count=8`) without registry display grouping note. Compliance Score page therefore renders **8 requirements satisfied on file** instead of **10**, with legacy portfolio-average grouping copy.

## PART 1 — Deploy proof

| Check | Result |
|-------|--------|
| Frontend bundle deployed | **PASS** — score scope copy markers, urgent hero gate, no `sorted[0]` fallback |
| Backend registry lifecycle counts | **FAIL** — `lifecycle_satisfied_count=8`, `visible_requirement_count=8` |
| API grouping note | **FAIL** — `grouping_note` null |
| Score unchanged | **PASS** — 93/100 |

**Artifact:** `today_score_scope_post_deploy_runtime.json`

## PART 2 — Today final proof

| Check | Result |
|-------|--------|
| `/today` loads | **PASS** |
| Error boundary | **PASS** — none |
| `urgent_count` | **PASS** — 0 |
| Needs action | **PASS** — 0 |
| Do this next | **PASS** — absent |
| File-review assurance hero | **PASS** — not elevated |
| Calm state | **PASS** — optional in-progress (4) only |

**Artifact:** `today_final_browser_runtime.json`  
**Screenshot:** `today_score_scope_post_deploy_screenshots/01_today.png`

## PART 3 — Score scope final proof

| Check | Result |
|-------|--------|
| 10 requirements satisfied on file | **FAIL** — page shows 8 |
| 8 score-tracked obligation groups | **PASS** |
| Grouping note (dedupe / double-counting) | **FAIL** — legacy portfolio-average note only |
| Score 93/100 | **PASS** |
| No false missing implication | **PARTIAL** — 8/8 wording may imply full portfolio coverage |
| 100/100 achievability path | **PARTIAL** — assurance opportunities visible; achievability copy not detected by harness |

**Artifact:** `score_scope_final_browser_runtime.json`  
**Screenshot:** `today_score_scope_post_deploy_screenshots/03_compliance_score.png`

## PART 4 — Full surface proof

| Surface | Expected | Observed |
|---------|----------|----------|
| Today | Calm | **PASS** — Needs action 0, no hero |
| Dashboard | 10 active / 8 score-tracked | **PASS** — "10 active in Requirements", 8 score-tracked |
| Compliance Score | 10 satisfied / 8 score-tracked | **FAIL** — 8 satisfied / 8 score-tracked |
| Requirements | 10/10 | **PASS** |
| Properties | 2 Valid / 0 Attention | **PASS** |

**Artifact:** `today_score_scope_full_surface_runtime.json`  
**Screenshots:** `today_score_scope_post_deploy_screenshots/`

## PART 5 — Non-regression check

| Scenario | Result |
|----------|--------|
| Missing evidence → operational | **PASS** |
| Rejected evidence → operational | **PASS** |
| Overdue/expiring → operational | **PASS** |
| Assurance-only file-review suppressed | **PASS** |
| Assurance classified not operational | **PASS** |

**Artifact:** `today_score_scope_non_regression_post_deploy_runtime.json`

## PART 6 — Regression

40 backend + 9 frontend targeted tests **PASS**.

**Artifact:** `today_score_scope_post_deploy_regression_runtime.json`

## Classification rationale

`SCORE_COUNT_SEMANTIC_DRIFT` because:

- Today browser and API prove calm operational state (no false hero, `urgent_count=0`).
- Score page and API still expose score-scoped lifecycle count (8) instead of registry-visible satisfied count (10).
- Backend `apply_registry_display_semantics` merge not yet live on staging despite frontend deploy.

Not `VERIFIED_OPERATIONALLY` — score scope browser/API checks fail.  
Not `TODAY_UI_DRIFT` — Today convergence confirmed post-deploy.

## Next action

Redeploy backend containing `b0510957` (`reporting_semantics_v1.apply_registry_display_semantics`, `compliance_score.py`, `routes/client.py`) and re-run:

```bash
python scripts/today_hero_and_score_scope_post_deploy_closeout_01_execute.py
```

Expected post-backend-deploy: Compliance Score shows **10 requirements satisfied on file**, **Score based on 8 score-tracked obligation groups**, grouping note visible, classification `VERIFIED_OPERATIONALLY`.
