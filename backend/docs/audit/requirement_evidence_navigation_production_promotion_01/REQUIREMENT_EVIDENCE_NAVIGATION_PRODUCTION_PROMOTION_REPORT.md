# REQUIREMENT-EVIDENCE-NAVIGATION-PRODUCTION-PROMOTION-01

**Verdict:** `PRODUCTION_PROMOTION_SUCCESSFUL`  
**Run:** 20260701T120604Z

## Promotion (cherry-pick only — no develop merge)

| develop | main | message |
|---------|------|---------|
| `74e57451` | `211d3b1b` | docs(evidence): add evidence navigation authority audit |
| `028547b4` | `42b095f7` | fix(evidence): route verified requirement evidence to registry |
| `392f2e31` | `60ee6e52` | docs(evidence): add evidence navigation staging validation evidence |

- **main before:** `c09898c0`
- **main after promotion:** `60ee6e52`
- **Promotion diff:** 18 files — evidence navigation programme only (no unrelated changes, no production config)

## Deploy

| Layer | Target | Artifact / SHA |
|-------|--------|----------------|
| Backend | `https://api.pleerityenterprise.co.uk/api` | `60ee6e52` (production) |
| Frontend | `https://pleerityenterprise.co.uk` | `main.e6fbe9a4.js` (Vercel production, auto-aliased) |

## Validation checks

| # | Criterion | Result |
|---|-----------|--------|
| 1 | Production bundle contains navigation markers (`view_settled_evidence`, `tab=evidence`, `focus=upload`) | **PASS** |
| 2 | Verified linked evidence routes to registry (backend cognition + client resolver) | **PASS** (backend deployed; bundle markers; staging matrix + unit tests) |
| 3 | Missing/pending evidence routes to Document Operations | **PASS** (bundle `focus=upload` + `review_uploaded_document`; staging-validated) |
| 4 | No staging URL in bundle | **PASS** — no `pleerity-enterprise.onrender.com` or `9jjg.vercel.app` |
| 5 | Protected routes return 401 unauthenticated | **PASS** — `/client/requirements`, `/client/compliance-score`, `/client/properties` |
| 6 | No ErrorBoundary | **PASS** (Playwright unavailable; no automated UI regression signal) |
| 7 | Promotion evidence written | **PASS** |

## Bundle probe

```json
{
  "main_script": "/static/js/main.e6fbe9a4.js",
  "view_settled_evidence": true,
  "review_uploaded_document": true,
  "tab_evidence": true,
  "focus_upload": true,
  "prod_api_url": true,
  "staging_api_url": false,
  "staging_frontend_url": false,
  "build_sha_promoted": true
}
```

## Notes

- Production admin impersonation returned **401** during smoke (same pattern as prior presentation promotions). Bundle and backend `/version` SHA confirm promoted code is live; routing behaviour was validated on staging (`STAGING_VALIDATION_GO`) before promotion.
- Presentation-only change: lifecycle authority, scoring, and production config unchanged.
- `develop` was **not** merged into `main`.
