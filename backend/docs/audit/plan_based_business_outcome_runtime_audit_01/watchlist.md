# Watchlist — Deterministic fixture seed closeout

Status: `PLAN_FIXTURE_GAP`

## Seed staging accounts

- [ ] **A** — ['property_count>1']
- [ ] **D** — ['property_count<5', 'not_all_satisfied']
- [ ] **E** — ['plan_mismatch:PLAN_1_SOLO!=PLAN_2_PORTFOLIO', 'property_count<5', 'not_mixed_jurisdiction']
- [ ] **G** — ['property_count>5', 'not_all_satisfied', 'unexpected_mixed_jurisdiction']
- [ ] **H** — ['not_all_satisfied']

## Verified references

- [x] Sophie Walker — Solo all-satisfied reference (Today calm after stale issue fix)
- [x] B, F, I partial fixtures

```bash
cd backend
python scripts/plan_outcome_deterministic_fixture_seed_closeout_01_execute.py
```
