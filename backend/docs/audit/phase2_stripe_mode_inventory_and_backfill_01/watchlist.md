# Stripe mode governance watchlist

## Phase 3 — CLIENT_REMEDIATION_REQUIRED

### Per-client backlog (33)

- [ ] Each client: review `client_remediation_worklist.json` row
- [ ] Default action: **REGENERATE_CHECKOUT_REQUIRED** (no webhook/checkout mode evidence)
- [ ] Use **admin-set-mode** only after manual Stripe dashboard verification (`remediation_policy.json`)
- [ ] Do **not** bulk assign live/test from deployment mode

### Orphaned checkouts (50)

- [ ] All classified `requires_regeneration` — pending sessions missing `stripe_mode`
- [ ] Regenerate or expire via operational process — **no auto-delete**

### Deploy

- [ ] Deploy Phase 3: `stripe_mode_client_remediation_service.py`, `admin_verified` source, MODE_UNVERIFIED unset on authoritative write
- [ ] Re-run `phase3_stripe_mode_client_remediation_closeout.py --test-admin-set-mode` after deploy

### Production gate

- [ ] `PRODUCTION_MONGO_URL` → re-run closeout with `--production-mongo-url`

### Verification

- [ ] One admin-set-mode + one regenerated checkout + one still-unverified upgrade/downgrade retest
- [ ] Target `authoritative_mode_coverage` > 0 after remediation batch

## Harness

```bash
cd backend
python scripts/phase3_stripe_mode_client_remediation_closeout.py \
  --mongo-url "$MONGO_URL" --db-name pleerity_staging \
  --test-admin-set-mode
```
