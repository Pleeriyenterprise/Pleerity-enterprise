# SCORE-SCOPE-BACKEND-DEPLOY-CLOSEOUT-01

**Classification:** `SCORE_COUNT_SEMANTIC_DRIFT`  
**Deploy commit (expected):** `b0510957`  
**Generated:** 2026-06-07T13:26:08Z  
**Target:** Sophie Walker (`PLE-CVP-2026-000023`, `10b2ddba-e952-4484-91d1-a8f0299d0824`)

## Executive summary

Backend score-scope fix from `b0510957` is present in repository source but **not live on staging Render API** after 12 deploy polls (~6 minutes). Frontend and Today convergence remain verified; Compliance Score page and API still expose score-scoped counts (8/8) instead of registry-visible lifecycle counts (10/8 with grouping note).

## PART 1 — Backend deploy proof

| Check | Result |
|-------|--------|
| Source: `apply_registry_display_semantics` | **PASS** (repo) |
| Source: `compute_registry_display_semantic_overrides` | **PASS** (repo) |
| Source: `compliance_score.py` merge | **PASS** (repo) |
| Source: `routes/client.py` merge | **PASS** (repo) |
| Staging API health | **PASS** — 200 |
| `visible_requirement_count=10` | **FAIL** — 8 |
| `lifecycle_satisfied_count=10` | **FAIL** — 8 |
| `score_tracked_requirement_count=8` | **PASS** — 8 |
| `grouping_note` present | **FAIL** — null |
| Deploy poll (12 × 30s) | **FAIL** — no convergence |

**Artifact:** `score_scope_backend_deploy_runtime.json`

## PART 2 — Score API closeout

| Check | Result |
|-------|--------|
| Score 93/100 | **PASS** |
| Lifecycle satisfied = 10 | **FAIL** — 8 |
| Score-tracked groups = 8 | **PASS** |
| Grouping note | **FAIL** |
| No missing implication | **FAIL** — 8/8 understates registry |
| Assurance explanation | **PASS** — headline + detail present |

**Artifact:** `score_scope_api_closeout_runtime.json`

## PART 3 — Score page browser closeout

| Check | Result |
|-------|--------|
| 10 requirements satisfied on file | **FAIL** — shows 8 |
| 8 score-tracked obligation groups | **PASS** |
| Grouping note (dedupe copy) | **FAIL** |
| 93/100 + confidence explanation | **PASS** |
| 100/100 achievability path | **PASS** — optional assurance opportunities visible |

**Artifact:** `score_scope_browser_closeout_runtime.json`  
**Screenshot:** `score_scope_backend_closeout_screenshots/01_compliance_score.png`

## PART 4 — Surface parity

| Surface | Expected | Observed |
|---------|----------|----------|
| Dashboard | 10 active / 8 score-tracked | **PASS** |
| Compliance Score | 10 satisfied / 8 score-tracked + note | **FAIL** |
| Requirements | 10/10 satisfied | **PASS** |
| Properties | 2 Valid / 0 Attention | **PASS** |
| Today | No urgent action | **PASS** — urgent_count=0, Needs action 0 |

**Artifact:** `score_scope_surface_parity_runtime.json`

## PART 5 — Regression

40 backend + 9 frontend targeted tests **PASS**.

**Artifact:** `score_scope_backend_regression_runtime.json`

## Classification rationale

`SCORE_COUNT_SEMANTIC_DRIFT` — staging Render backend has not deployed `b0510957` score-scope semantics despite fix being on `main`. All non-score surfaces align; only Compliance Score API/page remain on pre-fix lifecycle counts.

Not `VERIFIED_OPERATIONALLY` — backend API and score page checks fail.  
Not `FAIL_OPERATIONAL` — Today, Requirements, Properties, Dashboard operational parity confirmed.

## Required action

Manually redeploy **`pleerity-api`** on Render from `main` (commit `b0510957` or later), then re-run:

```bash
cd backend
python scripts/score_scope_backend_deploy_closeout_01_execute.py
```

## Programme history

| Programme | Classification |
|-----------|----------------|
| TODAY-HERO-AND-SCORE-SCOPE-FINAL-CONVERGENCE-01 | PARTIAL |
| TODAY-HERO-AND-SCORE-SCOPE-POST-DEPLOY-CLOSEOUT-01 | SCORE_COUNT_SEMANTIC_DRIFT |
| SCORE-SCOPE-BACKEND-DEPLOY-CLOSEOUT-01 | SCORE_COUNT_SEMANTIC_DRIFT |
