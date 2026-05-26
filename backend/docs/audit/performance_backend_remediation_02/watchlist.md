# Post-deploy watchlist (2026-05-26)

- Deploy rent/items fix (`flat_items_included` gate in `merge_rent_into_today_payload`) and re-verify Today `items_len=0` default.
- Slim Today `tasks.*` enriched DTOs to meet <200KB (largest remaining payload gap).
- Command Centre: profile remaining ~28s (compliance_score + unified build); target <15s.
- Documents: linkage deferred but list path still ~22s — profile Mongo + operational projection loop.
- Requirements: unchanged ~22s browser primary; consider pagination/field projection.
- Property detail: add/verify `data-testid=property-detail-page` for browser probe; compliance-detail path is fast (~4s API).
- Set `GIT_COMMIT_SHA` on Render for `/api/version` deploy continuity checks.
- Re-run `tmp_performance_remediation_02_post_deploy_verify.py` after next deploy for VERIFIED_OPERATIONALLY upgrade.
