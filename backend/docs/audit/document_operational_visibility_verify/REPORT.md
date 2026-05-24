# Document operational visibility — staged verification

**Run:** `20260524T224107Z`  
**Pilot:** `6fd5ac4c-3fd4-4112-ade7-156977deb49f` / `d35a58ae-3c81-491c-9694-1d021dd3b8ad`  
**Implementation commit:** `531f0e74`  
**Classification:** `BLOCKED`

## Summary

Backend visibility governance deployed and API-coherent on staging. **Frontend bundle not updated** (`/static/js/main.457d1533.js` — no `filter-queue-view`, no “Document operations” title). Browser operational proof blocked per deploy-continuity gate.

## Checkpoint matrix

| Checkpoint | API | Browser | Overall |
|------------|-----|---------|---------|
| Deploy continuity | visibility projections 21/21 | bundle stale | **FAIL** |
| Operations queue | 13 attention / 8 settled-out-of-queue | flat inventory (22 rows) | **FAIL** |
| Property registry | 6 sections truthful | no Evidence Registry UI | **FAIL** |
| Reconciliation | intentional-unlink transition OK | CTA not in stale UI | **FAIL** |
| Expiry resurfacing | 4 docs EXPIRY_RESURFACE | n/a | **PASS** |
| Historical governance | no authority violations | n/a | **PASS** |
| Cross-surface | 401 (harness token drift) | n/a | **FAIL** |
| G9 / G10 | pass | n/a | **PASS** |
| Convergence | stable (attention count) | n/a | **PASS** |

## Re-run gate

1. Deploy frontend containing commit `531f0e74` to `pleerityenterprise.co.uk`
2. Confirm bundle contains `filter-queue-view` or `Document operations`
3. Re-run `backend/tmp_document_operational_visibility_execute.py`
4. Fix reconciliation probe: seed without `document_type=Other` (Other → immediate INTENTIONALLY_UNLINKED)

## G6

VERIFY-02 G6 calendar remains unblocked from G5 (`VERIFIED_OPERATIONALLY`). This visibility programme is **BLOCKED** independently until frontend deploy + browser rerun.
