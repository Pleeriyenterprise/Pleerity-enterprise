# Watchlist — Plan-based business outcome

## Status: PLAN_FIXTURE_GAP

### Staging fixture gaps (seed or identify)

- [ ] **A** Solo 1 property, 1 jurisdiction, all satisfied, Today calm
- [ ] **D** Portfolio 5 properties, same jurisdiction, all satisfied
- [ ] **E** Portfolio 5–10 mixed jurisdictions, all satisfied
- [ ] **G** Professional 3–5 properties, same jurisdiction, all satisfied
- [ ] **H** Professional 5–10 mixed jurisdictions, all satisfied

### Verified fixtures (use for regression)

- [x] **B** Solo partial — `616258a5-51a6-4def-aa00-baa1598b2557` (David Harrison)
- [x] **C** Solo property limit — local max 2
- [x] **F** Portfolio partial mixed — `6bcc43c0-16f4-46a5-adf4-26693a0919d0` (David Miller)
- [x] **I** Professional partial mixed — `6fd5ac4c-3fd4-4112-ade7-156977deb49f` (Nancy)

### Reference (not exact fixture)

- [x] Sophie Walker `10b2ddba…` — Solo all-satisfied reference; **Today in_progress=4** needs investigation

### Follow-up

- [ ] Investigate why all-satisfied Sophie Walker shows Today in_progress=4 with urgent_count=0
- [ ] Seed Portfolio 5-property all-satisfied account for scenario D/E
- [ ] Seed Professional all-satisfied account for G/H

## Re-run

```bash
cd backend
python scripts/plan_based_business_outcome_fixture_closeout_01_execute.py
python scripts/plan_fixture_browser_capture_01.py
```
