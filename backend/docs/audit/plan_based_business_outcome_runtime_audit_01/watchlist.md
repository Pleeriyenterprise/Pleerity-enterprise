# Watchlist — Mongo-backed fixture satisfaction

Status: `MONGO_SAFETY_GAP`

- [ ] Copy staging Atlas URI to `docs/audit/phase2c_commercial_entitlement_governance_01/.staging_mongo_url` (gitignored)
- [ ] **D** — ['not_all_satisfied']
- [ ] **E** — ['not_all_satisfied']
- [ ] **G** — ['property_count<3', 'not_all_satisfied']
- [ ] **H** — ['not_all_satisfied']

## Re-run

```bash
cd backend
python scripts/plan_outcome_mongo_backed_fixture_satisfaction_closeout_01_execute.py --dry-run
python scripts/plan_outcome_mongo_backed_fixture_satisfaction_closeout_01_execute.py --confirm-write --mongo-url-file docs/audit/phase2c_commercial_entitlement_governance_01/.staging_mongo_url
```
