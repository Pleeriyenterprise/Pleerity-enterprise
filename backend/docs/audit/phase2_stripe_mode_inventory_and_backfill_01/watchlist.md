# Phase 2 remediation closeout watchlist

## Blocking VERIFIED_OPERATIONALLY

- [ ] **Production inventory** — run `phase2_stripe_mode_remediation_closeout.py --production-mongo-url $PROD_URL`
- [ ] **33 staging clients** — missing authoritative `stripe_mode`; classified `MODE_UNVERIFIED` / `ADMIN_SET_MODE_REQUIRED`
- [ ] **Authoritative backfill** — 0 verified writes on execute; 1 row showed API dry-run resolution — investigate webhook/checkout evidence for that client
- [ ] **50 orphaned checkout sessions** — regenerate checkout in deployment mode where still pending

## Post-remediation verification

- [ ] Re-test upgrade/downgrade on at least one admin-remediated client (live authoritative row)
- [ ] Confirm new `stripe_events` rows include `environment_source` and `event_verification_status`
- [ ] Re-run inventory; target `authoritative_mode_coverage` > 0

## Operational notes

- Staging API deploy at `76731d1b` — Phase 2 endpoints live
- Backfill execute safely marked 32 rows `MODE_UNVERIFIED` (no subscription mutation)
- Do not use ID-prefix inference for mode
- Use `POST .../admin-set-mode` only with explicit admin verification

## Harness

```bash
cd backend
python scripts/phase2_stripe_mode_remediation_closeout.py \
  --mongo-url "$MONGO_URL" --db-name pleerity_staging \
  --execute-backfill
```
