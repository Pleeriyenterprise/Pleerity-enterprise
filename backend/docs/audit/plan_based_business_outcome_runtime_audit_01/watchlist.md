# Watchlist — Today stale compliance issue suppression

## Status: VERIFIED_OPERATIONALLY

### Completed

- [x] Deploy `93ec5951` stale issue suppression to staging
- [x] Sophie Walker Today calm (`in_progress_count=0`)
- [x] Partial F/I urgency preserved
- [x] Browser proof captured

### Remaining (prior programme)

- [ ] Seed all-satisfied fixtures A, D, E, G, H
- [ ] Optional: governed backfill to resolve 5 LOW `MISSING_EVIDENCE` gap-engine rows for Sophie (audit retention only)

## Re-run

```bash
cd backend
python scripts/today_stale_compliance_issue_suppression_closeout_01_execute.py
```
