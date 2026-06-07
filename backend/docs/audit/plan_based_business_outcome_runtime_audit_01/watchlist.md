# Watchlist — Plan outcome seeding closeout

## Status: PLAN_FIXTURE_GAP

### Seed staging accounts (all-satisfied matrix)

- [ ] **A** Solo 1 property, 1 jurisdiction, all satisfied, Today calm
- [ ] **D** Portfolio 5 properties, same jurisdiction, all satisfied
- [ ] **E** Portfolio 5–10 mixed jurisdictions, all satisfied
- [ ] **G** Professional 3–5 properties, same jurisdiction, all satisfied
- [ ] **H** Professional 5–10 mixed jurisdictions, all satisfied

### Deploy + verify code fix

- [ ] Deploy `_suppress_stale_compliance_issue_tasks` + Today filter-before-compact
- [ ] Re-probe Sophie Walker — expect `in_progress_count=0` when requirements satisfied

### Verified partial fixtures (regression)

- [x] **B** Solo partial — `616258a5-51a6-4def-aa00-baa1598b2557`
- [x] **F** Portfolio partial mixed — `6bcc43c0-16f4-46a5-adf4-26693a0919d0`
- [x] **I** Professional partial mixed — `6fd5ac4c-3fd4-4112-ade7-156977deb49f`

### Count semantics follow-up

- [ ] Dashboard copy: ensure visible registry vs score-tracked labels on large portfolios (F, I)

## Re-run

```bash
cd backend
python scripts/plan_outcome_fixture_seeding_and_closeout_01_execute.py
```
