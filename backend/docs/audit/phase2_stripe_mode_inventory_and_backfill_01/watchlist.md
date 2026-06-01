# Phase 2 watchlist — Stripe mode inventory & backfill

- Run `phase2_stripe_mode_inventory_closeout.py` against **production** Mongo when credentials available; save `production_drift_inventory.json`.
- Deploy Phase 2 backend to staging; re-run inventory via admin API for API-path proof.
- Execute authoritative backfill on staging (`POST stripe-mode-backfill` with `dry_run=false`) only after admin review of dry-run output.
- Monitor `stripe_mode_backfill_audit` and `stripe_mode_inventory_metrics` collections post-deploy.
- Reconcile any remaining `legacy_caller_count > 0` from `legacy_stripe_caller_audit.json`.
- Clients with `LEGACY_TEST_SUBSCRIPTION` or `REGENERATE_CHECKOUT_REQUIRED` need manual checkout regeneration — no auto-migration.
