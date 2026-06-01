# Watchlist — Phase 2C Commercial Entitlement Closeout

- **Expiry transition proof:** Re-run closeout with `STAGING_MONGO_URL` (or local `.env` pointing at staging) and `--use-db-expiry` to backdate `entitlement_expiry_at`, then confirm `commercial_expired` audit event and `has_active_exception=false`.
- **Scheduler cron:** Deploy commit including `server.py` `commercial_entitlement_expiry` daily schedule (04:10 UTC); staging scheduler sample did not yet list this job id pre-deploy.
- **VERIFIED_OPERATIONALLY:** Blocked only on full expiry transition proof; API harness, browser, deploy SHA, duplicate prevention, customer copy, and job manual-run all passed at closeout.
- **Optional:** Migrate legacy pilot waiver buttons to Commercial Controls when ops sign off.
