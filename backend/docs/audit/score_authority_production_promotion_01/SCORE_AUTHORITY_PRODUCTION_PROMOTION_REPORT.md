# SCORE-AUTHORITY-PRODUCTION-PROMOTION-01

- **Run tag:** 20260701T093743Z
- **Verdict:** `PRODUCTION_PROMOTION_SUCCESSFUL`

## Promotion

- develop @ `0931c9ba`
- main before: `91ffa3f3`
- main after: `71350447` (cherry-picks `6855f297`, `0931c9ba`)

## Smoke checks

- production_backend_sha: PASS
- production_frontend_bundle: PASS
- bundle_no_legacy_threshold_fn: PASS
- bundle_no_old_explanation_fn: PASS
- bundle_has_band_explanation: PASS
- bundle_moderate_risk_wording: PASS
- no_staging_api_url: PASS
- no_staging_frontend_url: PASS
- prod_api_url_present: PASS
- requirement_authority_preserved: PASS
- presentation_authority_preserved: PASS
- regression_unauth_protected: PASS
- dashboard_compliance_score_authority: PASS
- portfolio_summary_authority: PASS
- property_detail_authority: PASS
- score_maths_unchanged: PASS

## Recommendation

Score Authority programme complete on production. Monitor portfolio override messages separately from band authority.
