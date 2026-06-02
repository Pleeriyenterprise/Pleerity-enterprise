# REVIEW-ASSURANCE-POST-DEPLOY-CLEANUP-01 watchlist

- [x] Post-deploy browser capture (client portal) — `screenshots/`
- [ ] Admin UI screenshots for escalation queue + document verification (API verified; UI optional)
- [ ] Persisted Mongo rows with `review_owner=org_admin` — apply `propose_stored_field_convergence` only after manual review (none found on staging probe)
- [ ] Remove `/operations/compliance-review` route once traffic at zero
