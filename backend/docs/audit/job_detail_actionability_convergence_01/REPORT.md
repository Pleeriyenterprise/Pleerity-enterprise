# Job detail actionability & progress convergence — REPORT

**Audit ID:** `JOB-DETAIL-ACTIONABILITY-AND-PROGRESS-CONVERGENCE-01`  
**Classification:** `PARTIAL` (unit/regression verified; staging browser not captured this run)

## Summary

Client job detail CTAs and progress narrative were drifting: the hero always scrolled to Visit while the Contractor section opened the assign modal; progress could show “Contractor assigned” without `contractor_id`; Cancel appeared for any non-terminal status.

This change converges hero and Contractor assign flows through `jobDetailPrimaryAction.js`, gates Cancel on `next_actions.cancel`, aligns `progress_contract_v1` assignment with `contractor_id`, and adds frontend drift correction for stale payloads.

## Root causes

| Issue | Cause |
|-------|--------|
| Hero assign misfire | `onPrimaryClick` hardcoded `visitSectionRef.scrollIntoView` |
| Progress drift | `_assigned()` treated non-OPEN status as assigned without `contractor_id` |
| Early Cancel | UI gated only on raw `status ∉ terminal` |

## Fixes

### Frontend

- **`jobDetailPrimaryAction.js`** — shared resolver for hero + contractor assign; entitlement gates; visit scroll routing; cancel visibility helper.
- **`ClientJobDetailPage.js`** — hero uses resolver; entitlement upgrade Alert; Cancel in bottom “Job options” card gated on `next_actions`.
- **`jobWorkflowUi.js`** — `alignProgressTrackerWithContractorFacts` corrects assigned step without `contractor_id`.

### Backend

- **`progress_contract_service._assigned`** — requires `contractor_id`.
- **`_assigned_step_label`** — “Awaiting contractor assignment” when assignment step current without facts.
- **`compliance_workflow_service._append_lifecycle_cancel`** — emits `cancel` in `next_actions` for non-terminal jobs.

## Verification

- Frontend: 11 tests (`jobDetailPrimaryAction`, `jobWorkflowUi.progressAlignment`).
- Backend: new progress + cancel governance tests; maintenance canonical updated for lifecycle cancel append.

## Artifacts

All JSON runtime artifacts and `watchlist.md` live in this directory.

## Post-deploy

Capture staging browser proof on `/operations/jobs/:id` for scenarios A–E to upgrade classification to `VERIFIED_OPERATIONALLY`.
