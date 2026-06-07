# Score scope convergence — operational verification complete

**Classification:** `VERIFIED_OPERATIONALLY`  
**Final fix commit:** `0dbe58a1`  
**Generated:** 2026-06-07T15:09:22Z  
**Target:** Sophie Walker (`PLE-CVP-2026-000023`)

## Executive summary

Score scope semantic drift is **operationally verified** on staging after `0dbe58a1`. Compliance Score API and browser now show **10 requirements satisfied on file**, **8 score-tracked obligation groups**, grouping note visible, score **93/100** unchanged. Today, Requirements, Properties, and Dashboard remain aligned.

## Root cause chain

1. **`b0510957`** — Added `apply_registry_display_semantics` but compliance-score used score-scoped counts only.
2. **`fefa72bd`** — Loaded full client doc for registry filter, but still passed truncated property projection → filter returned 8 rows.
3. **`0dbe58a1`** — Registry display filter now uses **full property documents** (dashboard/Requirements parity); score-scoped `portal_reqs` unchanged.

## Post-`0dbe58a1` verification

| Check | Result |
|-------|--------|
| API visible / lifecycle / score_tracked | **10 / 10 / 8** |
| grouping_note | **Present** |
| Compliance Score browser | **10 satisfied / 8 score-tracked / note visible** |
| Today calm | **PASS** |
| Requirements 10/10 | **PASS** |
| Properties 2 Valid / 0 Attention | **PASS** |
| Regression | **41 tests PASS** |

## Programme history

| Programme | Classification |
|-----------|----------------|
| TODAY-HERO-AND-SCORE-SCOPE-POST-DEPLOY-CLOSEOUT-01 | SCORE_COUNT_SEMANTIC_DRIFT |
| SCORE-SCOPE-BACKEND-DEPLOY-CLOSEOUT-01 | SCORE_COUNT_SEMANTIC_DRIFT → **VERIFIED_OPERATIONALLY** |
| SCORE-SCOPE-DEPLOYMENT-AND-CODEPATH-DIAGNOSTIC-01 | INPUT_SCOPE_DRIFT (fixed) |
