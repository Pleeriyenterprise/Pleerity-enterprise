# TODAY-STALE-COMPLIANCE-ISSUE-SUPPRESSION-CLOSEOUT-01

**Classification:** `VERIFIED_OPERATIONALLY`  
**Deploy commit:** `93ec5951`  
**Marker:** `TODAY-STALE-ISSUE-CLOSEOUT-20260607T185255Z`

## Summary

Stale compliance-gap bridge issues no longer surface on Today for all-satisfied users. Sophie Walker Today is **calm** (`in_progress_count=0`, `urgent_count=0`) while 5 LOW `MISSING_EVIDENCE` gaps remain in gap engine (audit-only). Partial Portfolio/Professional urgency preserved.

## Deploy proof

- Source markers: all present in repo `93ec5951`
- Staging health: 200
- Behavioral proof: Sophie `today_calm=true` on first poll attempt

## Sophie Walker recheck

| Check | Result |
|-------|--------|
| All requirements satisfied | Yes (8/8) |
| urgent_count | 0 |
| in_progress_count | 0 |
| Stale document-review titles | None |
| Browser screenshot | `sophie_today_stale_issue_closeout.png` |

## Gap reconciliation

- Gap engine: 5 open LOW `MISSING_EVIDENCE` (historical)
- Open maintenance issues (client API): 0 visible
- Today/unified in_progress: 0
- User-facing inbox suppressed; no governed cleanup required

## Non-regression

| Fixture | Urgency preserved |
|---------|-------------------|
| Sophie (all-satisfied) | Calm |
| B Solo partial | 8 unsatisfied requirements |
| F Portfolio partial | urgent_count=9 |
| I Professional partial | urgent_count=24, in_progress=81 |

## Regression

55 tests pass.
