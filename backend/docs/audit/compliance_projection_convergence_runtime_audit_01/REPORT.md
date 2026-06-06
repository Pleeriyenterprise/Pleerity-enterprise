# COMPLIANCE-ASSURANCE-ACTIONABILITY-CONVERGENCE-01

**Classification:** `PARTIAL` (code complete; staging API deploy pending)  
**Prior closeout:** `SCORE_DRIFT` from post-deploy closeout  
**Target reference:** Sophie Walker (`PLE-CVP-2026-000023`)

## Summary

Implemented global separation of **assurance-confidence opportunities** from **operational actionability** across Today, score recommendations, dashboard summary, and client UI. Local validation and regression pass. Staging API probe (pre-deploy) still returns legacy `recommendations` without `assurance_opportunities` / `score_confidence`; browser Today no longer shows “Do this next” for the target account.

## Changes

| Area | Fix |
|------|-----|
| `assurance_actionability_service.py` | Central classifier; partitions score actions; Today issue suppression |
| `today_projection_service.py` | `today_task_is_actionable` uses assurance gate |
| `compliance_score.py` | `recommendations` vs `assurance_opportunities`; `score_confidence`; stats semantics |
| `routes/client.py` dashboard | Enrich + `is_requirement_satisfied` for compliance_summary |
| `todayExecutionWorkspace.js` | No assurance hero; operational bucket filter |
| `portalRequirementAttention.js` | `filterInboxTasksForOperationalActionability` |
| `ComplianceScorePage.js` | Confidence copy; optional assurance section |
| `ClientDashboard.js` | Renders `assurance_opportunities` as optional |

## Part results

| Part | Result |
|------|--------|
| 1 Inventory | `assurance_actionability_inventory_runtime.json` |
| 2 Today convergence | API urgent=0 ✓; browser no Do this next ✓ (see screenshots) |
| 3 Quick actions | Code ✓; staging API still 4 legacy HIGH cards ✗ |
| 4 Score counts | Code adds lifecycle/score-tracked labels; staging pre-deploy |
| 5 Score confidence copy | Code ✓; `score_confidence` absent on staging API until deploy |
| 6 Global validation | All scenarios pass locally |
| 7 Browser proof | `assurance_browser_runtime.json` + screenshots |
| 8 Regression | 60 tests pass |
| 9 Classification | `PARTIAL` |

## Post-deploy verification

After deploy, re-run:

`python scripts/compliance_assurance_actionability_convergence_01_execute.py`

Expect: `assurance_opportunities` > 0, `recommendations` operational-only empty, `score_confidence.detail` present, dashboard `satisfied_requirements` = 10.
