# SCORE-RECOMMENDATION-PRESENTATION-AUTHORITY-01 — Report

**Programme:** SCORE-RECOMMENDATION-PRESENTATION-AUTHORITY-01  
**Branch:** `develop` only  
**Date:** 2026-07-01  
**Verdict:** **PRESENTATION ALIGNMENT COMPLETE**

## Objective

Improve recommendation clarity (property context, requirement identity, outcome, routing) without changing recommendation generation, ranking, scoring, or selection.

## Authority chain (unchanged)

```
compliance_scoring_v2.compute_property_score_v2
  └─ top_next_actions (per property × requirement deficit)

compliance_scoring_service persistence
  └─ compliance_top_next_actions

compliance_score.calculate_compliance_score
  └─ aggregate by impact_points DESC
  └─ partition_score_recommendations (operational / assurance)

Client surfaces consume API order only
```

## Presentation chain (new)

```
API recommendations / top_next_actions (backend order preserved)
  └─ scoreRecommendationPresentation.js
       ├─ prepareScoreRecommendationPresentation (identity + copy)
       └─ buildScoreRecommendationDisplayUnits (conditional grouping ≥4)
  └─ ScoreRecommendationPresentation.jsx (cards + expandable groups)
```

## Root cause addressed

Dashboard Quick Actions showed identical action text for distinct property×requirement deficits because `property_id` was used for routing only — not rendered. Landlords perceived duplicates.

## Before / after

| Surface | Before | After |
|---------|--------|-------|
| Dashboard Quick Actions | Title + CTA only; three EICR cards looked identical | Title, **property name**, requirement, jurisdiction, operational reason, outcome, priority, Fix now / View property |
| Compliance Score page | Plain list of action strings | Same structured cards via `ScoreRecommendationList` |
| Property Detail suggested steps | Bullet list of action text | Structured cards with property context (default property from page) |
| Reports / Digest / Command Centre | Already grouped or operational — separate authorities | Unchanged (by design) |

## Recommendation identity model

Each card presents:

| Field | Source |
|-------|--------|
| Title | `resolveQuickActionDisplayText` + governed labels |
| Property name | `buildPropertyLookup` + `getPropertyDisplayName` |
| Requirement name | `display_label` or `requirementLabel(code)` |
| Jurisdiction | Property metadata from score breakdown |
| Operational reason | Requirement status → governed copy |
| Expected outcome | API `impact` or assurance copy |
| Priority | API `priority` only |
| Primary CTA | `buildEntityRoute` (Fix now / View) |
| Secondary CTA | `resolvePropertyPath` (View property) |

Identity key: `{propertyId}|{requirement_code}|{requirementId}`

## Property context model

Lookup order: `score_breakdown_by_property` → `portfolioSummary.properties` → `dashboard.properties`.

Mandatory: property name on every card. Optional: jurisdiction, property type (`compliance_basis`).

## Grouping rules

- Default: individual cards in backend order
- Group when **4+** recommendations share `requirement_code` grouping key
- Collapsed group: requirement title + property name list + Review all
- Expanded: full cards per property, backend order preserved
- Never merge unrelated requirement types

## Routing matrix

| CTA | Operational | Assurance | Destination |
|-----|-------------|-----------|-------------|
| Fix now | Yes | No | `buildEntityRoute({ requirement_id, property_id, mode: 'upload' }, '/today')` |
| View (primary) | No | Yes | `buildEntityRoute({ ..., mode: 'view' }, '/today')` |
| View property | Both | Both | `resolvePropertyPath(property_id)` |

No navigation to empty `/today` when entity IDs are missing (`hasPrimaryCta` guard).

## Surfaces aligned

| Surface | Status |
|---------|--------|
| Dashboard Quick Actions | Updated |
| Compliance Score page (operational + assurance) | Updated |
| Property Detail suggested steps | Updated |
| Reports (executive grouping) | Unchanged — report-layer grouping |
| Monthly Digest | Unchanged — `humanize_recommendation` at assembly |
| Command Centre / Today | Unchanged — independent authorities |
| Portfolio compliance summary | No score recommendation cards in UI |

## Changed files

- `frontend/src/utils/scoreRecommendationPresentation.js` (new)
- `frontend/src/components/score/ScoreRecommendationPresentation.jsx` (new)
- `frontend/src/pages/ClientDashboard.js`
- `frontend/src/pages/ComplianceScorePage.js`
- `frontend/src/pages/PropertyDetailPage.js`
- `frontend/src/utils/scoreRecommendationPresentation.test.js` (new)
- `frontend/src/pages/ClientDashboard.scoreWidgetLabels.test.js`
- `backend/docs/COMPLIANCE_CLIENT_STATUS_AUTHORITY.md`

## Tests

- `scoreRecommendationPresentation.test.js` — order preservation, grouping threshold, property context, identity keys, operational reason
- `ClientDashboard.scoreWidgetLabels.test.js` — multi-property distinct names, assurance CTA rewrite

## Explicit non-changes

- `impact_points` ranking
- `partition_score_recommendations`
- `compliance_scoring_v2` mathematics
- Recommendation persistence
- Today operational inbox
- Backend recommendation payloads

## Acceptance criteria

| Criterion | Status |
|-----------|--------|
| Recommendation authority unchanged | ✓ |
| Ranking unchanged | ✓ |
| Scoring unchanged | ✓ |
| Recommendation identity preserved | ✓ |
| Property context immediately visible | ✓ |
| Landlords distinguish cards without opening | ✓ |
| Conditional grouping preserves actionability | ✓ |
| Today Authority independent | ✓ |
| No frontend inference | ✓ |
| No score logic changes | ✓ |

## Remaining risks

- Dashboard display cap `slice(0, 3)` unchanged — shows top 3 backend-ordered items only.
- Browser screenshots not captured in this pass (unit/integration tests only).
- Digest and Reports use separate humanization paths; terminology should be reviewed on next digest copy pass.

## Production recommendation

Validate on staging with a multi-property portfolio showing 2–3 similar requirement types (any code, not EICR-specific). Frontend-only deploy; no backend change required.
