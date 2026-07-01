# SCORE-RECOMMENDATION-PRESENTATION-AUTHORITY-01 — Staging Validation

**Programme:** SCORE-RECOMMENDATION-PRESENTATION-AUTHORITY-01-STAGING-VALIDATION  
**Verdict:** `STAGING_VALIDATION_GO`  
**Run:** 20260701T102800Z  
**Branch:** `develop`  
**Commit:** `b43cebc5`

## Deploy

| Target | URL | Artefact |
|--------|-----|----------|
| Backend (Render staging) | `https://pleerity-enterprise.onrender.com/api` | `b43cebc5` |
| Frontend (Vercel alias) | `https://pleerity-enterprise-9jjg.vercel.app` | `main.7c01727a.js` |

Frontend deployed via `npx vercel deploy` and aliased to staging. Bundle contains `b43cebc5`, `data-recommendation-identity`, grouped copy (`properties require attention`), and `View property`.

## Cohort

OPS pilot client `6fd5ac4c-3fd4-4112-ade7-156977deb49f` — 7 properties, **5 operational EICR recommendations** across distinct properties plus 2 assurance opportunities.

## Checks

| Check | Result |
|-------|--------|
| Local frontend tests (13) | PASS |
| Staging backend reachable | PASS |
| Staging frontend bundle | PASS |
| API recommendations reachable | PASS |
| Multi-property similar recommendations | PASS |
| Browser property context visible | PASS |
| Dashboard display cap (3 cards) | PASS |
| Compliance Score 5×EICR grouped | PASS |
| Group expandable (Review all) | PASS |
| Today unchanged | PASS |
| Command Centre unchanged | PASS |
| API order / ranking / score unchanged | PASS |

## Browser walkthrough summary

### Dashboard Quick Actions

- **3 cards** shown (backend-ordered top 3; cap unchanged).
- Identical EICR action text **distinguishable by property name** without opening cards (e.g. Altrincham Townhouse, Leamington Spa Victorian).
- Each card shows requirement, operational reason, expected outcome, priority, Fix now, View property.

### Compliance Score page

- **5 EICR recommendations grouped** as one expandable unit: “5 properties require attention”.
- **Review all** expands to individual property cards preserving identity.
- Assurance section shows separate cards (not merged with operational group).

### Today / Command Centre

- No score Quick Action cards on Today (operational authority independent).
- Command Centre loads without score recommendation presentation regression.

## API authority (unchanged)

- 5 operational recommendations, same `EICR` code, distinct `property_id` values, `priority: high`, `impact: +15 points`.
- Order preserved by `impact_points` backend ranking.
- Portfolio score **40** unchanged by presentation deploy.
- No recommendations suppressed, deduplicated, or re-ranked by frontend.

## Acceptance

All programme acceptance criteria met. Landlords can immediately distinguish similar recommendations by property context; recommendation authority remains identical to backend payloads.

## Remaining risks

- Property Detail `top_next_actions` empty for probed property `d35a58ae` — presentation component wired; data-dependent.
- Automated probes should use `quick-action-N-property` testids, not suffix `-property` (matches View property button).
