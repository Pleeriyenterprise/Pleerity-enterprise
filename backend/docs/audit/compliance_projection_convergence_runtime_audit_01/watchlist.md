# Watchlist — Score scope convergence

## Status: VERIFIED_OPERATIONALLY

Staging verified post-`0dbe58a1` (2026-06-07):

- Compliance Score API: visible=10, lifecycle=10, score_tracked=8, grouping note present
- Browser: “10 requirements satisfied on file”, “8 score-tracked obligation groups”, grouping note visible
- Today calm (urgent_count=0, Needs action 0)
- Requirements 10/10, Properties 2 Valid / 0 Attention, Dashboard 10 active / 8 score-tracked
- Regression: 41 targeted tests pass

## Fix commits (for reference)

| Commit | Change |
|--------|--------|
| `b0510957` | `apply_registry_display_semantics` at compliance-score API |
| `fefa72bd` | Full client doc for registry display filter |
| `0dbe58a1` | Full property docs for registry display filter |

## No open blockers

Score scope semantic drift closed for Sophie Walker staging account.

## Re-run harness (if needed)

```bash
cd backend
python scripts/score_scope_backend_deploy_closeout_01_execute.py
```
