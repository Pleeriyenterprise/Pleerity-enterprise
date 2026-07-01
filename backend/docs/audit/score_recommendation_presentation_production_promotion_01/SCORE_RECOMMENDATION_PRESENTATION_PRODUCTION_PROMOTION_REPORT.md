# SCORE-RECOMMENDATION-PRESENTATION-PRODUCTION-PROMOTION-01

- **Run tag:** 20260701T105000Z
- **Verdict:** `PRODUCTION_PROMOTION_SUCCESSFUL`

## Promotion

| | SHA | Message |
|---|-----|---------|
| main before | `cc77efdc` | score authority production promotion evidence |
| cherry-pick 1 | `b43cebc5` → `a0c43f32` | fix(score): improve recommendation presentation authority |
| cherry-pick 2 | `9daa2a78` → `272c2cc1` | docs(score): add recommendation presentation staging validation evidence |
| main after | `272c2cc1` | |

**Promotion diff:** 12 files only — no unrelated commits.

## Deploy

| Target | URL | Artefact |
|--------|-----|----------|
| Backend (Render production) | `https://api.pleerityenterprise.co.uk/api` | `272c2cc1` |
| Frontend (Vercel production) | `https://pleerityenterprise.co.uk` | `main.feee4114.js` |

`npx vercel deploy --prod` with `REACT_APP_BACKEND_URL=https://api.pleerityenterprise.co.uk`. Aliased to `pleerityenterprise.co.uk`.

## Smoke checks

| Check | Result |
|-------|--------|
| promotion_diff_clean | PASS |
| production_backend_sha | PASS |
| production_frontend_bundle | PASS |
| bundle_presentation_markers (`data-recommendation-identity`) | PASS |
| bundle_grouping_copy (`properties require attention`) | PASS |
| bundle_view_property_cta | PASS |
| prod_api_url_present | PASS |
| no_staging_api_url | PASS |
| no_staging_frontend_url | PASS |
| regression_unauth_protected | PASS |
| presentation_only_no_score_maths_change | PASS |
| staging_validation_reference | PASS |

## Authenticated probes

Admin and client production login returned **401** in the promotion runner (same constraint as SCORE-AUTHORITY-PRODUCTION-PROMOTION-01). Unauthenticated protected endpoints return **401** as expected.

Presentation behaviour validated via:

1. **Production bundle markers** — presentation layer deployed with prod API URL.
2. **Staging reference** — `STAGING_VALIDATION_GO` at `b43cebc5` with authenticated browser walkthrough on OPS pilot `6fd5ac4c`:
   - Dashboard Quick Actions show property names without opening cards
   - 5× EICR grouped on Compliance Score with expandable Review all
   - Today and Command Centre unchanged
   - API recommendation order, ranking, and score unchanged

## Recommendation

Recommendation presentation authority is live on production. Presentation-only promotion; recommendation generation, ranking, scoring, and `impact_points` unchanged.

## Rollback

Revert cherry-picks `a0c43f32` and `272c2cc1` on `main` and redeploy prior frontend bundle if regression detected.
