# COMPLIANCE-ASSURANCE-ACTIONABILITY-POST-DEPLOY-CLOSEOUT-01

**Classification:** `PARTIAL` (API/deploy verified; Today browser error boundary; count semantics scope gap)  
**Deploy commit:** `28743ee3`  
**Target:** Sophie Walker (`PLE-CVP-2026-000023`)  
**Generated:** 2026-06-06T23:25:33Z

## Executive summary

Staging has deployed `28743ee3`. The assurance/actionability API model is live: `score_confidence`, `assurance_opportunities`, zero operational `recommendations`, and dashboard `satisfied_requirements: 10`. Properties and Requirements surfaces converge. **Today API** is calm (`urgent=0`). **Today browser** hit `CVP_ErrorBoundary` on `/today` during impersonated session (screenshot). **Count semantics:** requirements API shows 10/10 satisfied; score stats `lifecycle_satisfied_count` remains 8 within score-tracked scope (alias-family dedup).

## Part results

| Part | Result | Notes |
|------|--------|-------|
| 1 Deploy proof | **PASS** | API fields present; bundle `193d3a8d` has assurance markers |
| 2 Sophie snapshot | **PASS** | 10 visible, 10 satisfied, 2 GREEN, 93/100, 0 operational recs |
| 3 Today API | **PASS** | urgent=0 |
| 3 Today browser | **FAIL** | Error boundary on `/today` route |
| 4 Dashboard quick actions | **PASS** | 0 operational; 2 OPTIONAL assurance (Legionella) |
| 5 Score page API | **PASS** | `score_confidence` headline + detail present |
| 6 Count semantics | **PARTIAL** | Dashboard 10/10 satisfied; stats lifecycle=8 (score-tracked scope) |
| 7 Non-regression | **PASS** | Local scenarios pass |
| 8 Browser proof | **PARTIAL** | Dashboard, score, requirements, properties OK; Today error |
| 9 Regression | **PASS** | 60 tests |

## Key API evidence (Sophie Walker)

- `recommendations`: `[]`
- `assurance_opportunities`: 2 × Legionella (`priority: info`, `action_kind: ASSURANCE_CONFIDENCE_OPPORTUNITY`)
- `score_confidence.headline`: "Your requirements are satisfied."
- `score_confidence.detail`: explains sub-100 as assurance confidence
- `dashboard.compliance_summary`: `satisfied_requirements: 10`, `total_requirements: 10`

## Screenshots

`assurance_post_deploy_screenshots/` — Today shows error boundary; Properties 2 Valid / 0 Attention needed.
