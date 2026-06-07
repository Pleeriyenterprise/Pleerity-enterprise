# TODAY-HERO-AND-SCORE-SCOPE-FINAL-CONVERGENCE-01

**Classification:** `PARTIAL` (fixes committed; staging deploy pending)  
**Generated:** 2026-06-07T12:29:18Z

## Executive summary

Fixed Today hero elevation and score scope display semantics in code. Root causes documented; local regression passes (40 backend + 9 frontend tests). Staging browser still shows pre-fix behaviour until deploy.

## Root causes

1. **Today hero:** `pickPrimaryExecutionTask` included `in_progress` tasks and fell back to `sorted[0]`, elevating file-review issue tasks when API `urgent_count=0`.
2. **Score scope:** Compliance Score API used score-scoped `portal_reqs` counts (8) for lifecycle satisfied display; Requirements registry shows 10 visible satisfied rows.

## Fixes shipped

- **Today:** Hero gated on API urgent lane; removed fallback elevation; metadata-based assurance classification for file-review issues.
- **Score:** `apply_registry_display_semantics` merges enriched registry visible counts; UI copy separates lifecycle satisfied vs score-tracked groups.

## Staging status (pre-deploy snapshot)

| Check | Result |
|-------|--------|
| Today API urgent | 0 |
| Today browser Do this next | Still present (old bundle) |
| Score API lifecycle | 8 (expected 10 post-deploy) |
| Requirements visible | 10 |
| Local regression | PASS |

## Re-run after deploy

`python scripts/today_hero_and_score_scope_final_convergence_01_execute.py`
