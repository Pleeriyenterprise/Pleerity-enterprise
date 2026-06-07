# TODAY-UI-AND-SCORE-COUNT-POST-DEPLOY-CLOSEOUT-01

**Classification:** `PARTIAL` (primary: `TODAY_UI_DRIFT`; secondary: `SCORE_COUNT_SEMANTIC_DRIFT`)  
**Deploy commit:** `0b8582ca`  
**Generated:** 2026-06-07T12:04:38Z

## Executive summary

Post-deploy staging verification after `0b8582ca`. The Today page **no longer crashes** (no `CVP_ErrorBoundary`). Frontend deploy confirmed via score-page copy markers (`score-tracked obligation groups`, bundle `776a71bb`). Backend deploy confirmed via `visible_requirement_count` field.

**Remaining drift:**

1. **Today API/browser divergence** — API `urgent_count=0` but browser shows "Do this next" hero and "Needs action: 1" (file-review task at Brixton Hill).
2. **Score count semantics** — Requirements page and Dashboard show **10 active** requirements; Compliance Score API/page shows **8/8** with no `grouping_note` because score pipeline `portal_reqs` scope is 8 rows (alias dedupe), not 10 visible registry rows.

## Part results

| Part | Result | Notes |
|------|--------|-------|
| 1 Deploy proof | **PARTIAL** | Frontend + backend fields deployed; lifecycle=8 not 10; grouping_note absent |
| 2 Today page | **FAIL** | No crash; API urgent=0; browser Do this next + Needs action 1 |
| 3 Score count semantics | **FAIL** | Score page 8 satisfied / 8 groups; Requirements 10/10; no grouping note |
| 4 Browser proof | **PARTIAL** | Screenshots captured; Dashboard 10 active vs 8 score-tracked visible |
| 5 Regression | **PASS** | 47 backend + frontend tests |

## Key evidence (Sophie Walker)

| Surface | Value |
|---------|-------|
| Today API urgent | 0 |
| Today browser | Do this next visible; Needs action 1 |
| Dashboard | 93/100; 0 urgent; 10 active in Requirements; 8 score-tracked obligations |
| Compliance Score | 8 requirements satisfied; 8 score-tracked groups; 93 explained as assurance gap |
| Requirements | 10/10 satisfied |
| Properties | 2 Valid; 0 Attention needed |

## Screenshots

`today_score_post_deploy_screenshots/` — Today, Dashboard, Compliance Score, Requirements, Properties.
