# REVIEW-ASSURANCE-POST-DEPLOY-CLEANUP-01 watchlist

- [ ] Re-run browser capture if Playwright unavailable in CI runner
- [ ] Persisted Mongo rows with `review_owner=org_admin` — apply `propose_stored_field_convergence` only after manual review
- [ ] Remove `/operations/compliance-review` route once traffic at zero
- [ ] Admin panel spot-check document verification after deploy
