# Watchlist — Governed staging fixture seeding

Status: `FIXTURE_SEEDING_GAP`

## Completed

- [x] **A** — Sophie Walker exact Solo fixture (`10b2ddba-e952-4484-91d1-a8f0299d0824`); 1 active England property; 8/8 satisfied; Today calm

## Fixture gaps

- [ ] **D** — `80f83edd-ba12-41ed-929a-bbaf8c696a23`; 5 England properties provisioned; 3/28 satisfied; document-only requirements need governed mongo seed
- [ ] **E** — `6bcc43c0-16f4-46a5-adf4-26693a0919d0`; 8 mixed props; 23/41 satisfied; needs satisfaction pass
- [ ] **G** — `f68d4f4b-8007-43c6-84cb-a20c4ab69891`; 1 Wales prop; needs 3-5 props + satisfaction
- [ ] **H** — `6fd5ac4c-3fd4-4112-ade7-156977deb49f`; 7 mixed props; needs bulk satisfaction
- [ ] Provide `STAGING_MONGO_URL` (or `--mongo-url-file`) for document-authority governed satisfaction on document-only requirements

## Re-run

```bash
cd backend
python scripts/plan_outcome_governed_staging_fixture_seeding_01_execute.py --confirm-write --mongo-url-file docs/audit/phase2c_commercial_entitlement_governance_01/.staging_mongo_url
python scripts/plan_outcome_fixture_seeding_and_closeout_01_execute.py
```
