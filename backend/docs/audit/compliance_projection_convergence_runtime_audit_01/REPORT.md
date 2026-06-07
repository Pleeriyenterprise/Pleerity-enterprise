# TODAY-UI-AND-SCORE-COUNT-SEMANTICS-CLOSEOUT-01

**Classification:** `TODAY_UI_DRIFT` (code fix landed; staging frontend not yet deployed)  
**Generated:** 2026-06-07T11:44:10Z

## Executive summary

Root-caused and fixed the Today page crash (`ReferenceError: filterInboxTasksForOperationalActionability is not defined` in `portalRequirementAttention.js`). Clarified score count semantics: `lifecycle_satisfied_count` now counts all visible satisfied requirements; `score_tracked_requirement_count` remains grouped scoring scope with `grouping_note` when visible count exceeds score-tracked groups.

Staging browser still hits `CVP_ErrorBoundary` on `/today` until the frontend bundle containing the fix deploys. Backend semantics fields (`visible_requirement_count`, updated `lifecycle_satisfied_count`, `grouping_note`) require backend deploy. API Today is calm (`urgent=0`). Regression: 36 backend + frontend tests pass.

## Part results

| Part | Result | Notes |
|------|--------|-------|
| 1 Today root cause | **PASS** | Missing export in `portalRequirementAttention.js` |
| 2 Today UI fix | **PASS** | `isTaskAssuranceOnly` + `filterInboxTasksForOperationalActionability` added |
| 3 Today browser | **FAIL** | Staging bundle still crashes; API urgent=0 |
| 4 Score count root cause | **PASS** | `lifecycle_satisfied_count` used tracked-attention filter (8) vs visible registry (10) |
| 5 Score count clarity | **PASS** | `METRIC_VISIBLE`, `METRIC_LIFECYCLE_SATISFIED`, `grouping_note` in API/UI |
| 6 Regression | **PASS** | 36 backend + portalRequirementAttention frontend tests |
| 7 Browser closeout | **PARTIAL** | Requirements 10/10; score confidence visible; Today error boundary |

## Fixes shipped

- `frontend/src/utils/portalRequirementAttention.js` — assurance filter exports
- `frontend/src/utils/portalRequirementAttention.test.js` — render safety tests
- `backend/services/reporting_semantics_v1.py` — visible/lifecycle metrics + grouping note
- `backend/services/compliance_score.py` — lifecycle_satisfied from visible satisfied
- `backend/services/assurance_actionability_service.py` — score_confidence grouping copy
- `frontend/src/pages/ComplianceScorePage.js` — separated satisfied vs score-tracked labels
- `frontend/src/utils/reportingSemanticsLabels.js` — clarified tooltips

## Score count semantics (Sophie Walker)

| Surface | Count | Authority |
|---------|-------|-----------|
| Requirements page | 10 visible / 10 satisfied | Full visible registry |
| Dashboard compliance_summary | 10 / 10 | Lifecycle satisfied (visible) |
| Score stats (pre-deploy) | lifecycle=8, score_tracked=8 | Score projection / alias grouping |
| Post-deploy expected | lifecycle=10, score_tracked=8, grouping_note | Visible vs grouped scoring scope |
