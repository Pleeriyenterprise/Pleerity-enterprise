# SCORE-AUTHORITY-ALIGNMENT-01 — Alignment Report

**Programme:** SCORE-AUTHORITY-ALIGNMENT-01  
**Branch:** `develop` only  
**Date:** 2026-06-30  
**Verdict:** **ALIGNMENT COMPLETE**

## Objective

Establish one canonical Score Authority — backend owns score bands, grade, colour, risk wording, and band explanation; frontend presents API authority only.

## Pre-alignment drift (from SCORE-PRESENTATION-AUTHORITY-AUDIT-01)

| Drift | Location | Issue |
|-------|----------|-------|
| Duplicate thresholds | `ClientDashboard.scoreToGradeColorMessage` | Local 80/60/40 inference |
| Duplicate thresholds | `riskLabel.js` | `getRiskBandExplanationFromScore`, `riskLevelToGradeColorMessage` |
| Duplicate thresholds | `ComplianceScorePage.js` | Property row colour from `score >= 80/40` |
| Chart bands | `ScoreTrendChart.js` | Inline `RISK_BANDS` (display-only but duplicated constants) |
| Per-property thresholds | `compliance_scoring_service.py` L151 | 90/70/50 cut-offs vs `risk_bands` 80/60/40 |
| Terminology | Frontend `formatRiskLabel` | "Medium risk" vs backend "Moderate risk" |

## Canonical authority

**Module:** `backend/utils/risk_bands.py`

| Threshold | Value |
|-----------|-------|
| Low (A/B) | ≥ 80 |
| Moderate (C) | ≥ 60 |
| High (D) | ≥ 40 |
| Critical (F) | < 40 |
| Grade A | ≥ 90 within Low band |

**Governed phrase:** **Moderate risk** (not Medium risk).

## Implementation summary

### Backend

1. Extended `risk_bands.py` with `score_to_band_explanation`, `risk_level_to_band_explanation`, `score_authority_fields`, `attach_score_authority_fields`.
2. Aligned `compliance_scoring_service` per-property `risk_level` to `score_to_risk_level`; authoritative read path derives `risk_level` from persisted score.
3. Added `band_explanation` to compliance score API, property scoring payloads, portfolio summary, and property compliance-detail.
4. Enriched `property_breakdown` rows with grade/colour/message/risk_level/band_explanation from `score_authority_fields`.

### Frontend

1. Removed `scoreToGradeColorMessage` from `ClientDashboard.js`.
2. Rewrote `riskLabel.js` — API pass-through only; no score-based threshold inference.
3. Added `scoreAuthorityConstants.js` for chart/static copy (display mirror, no inference).
4. `ComplianceScorePage` property rows use API `color` only.
5. `ScoreTrendChart` imports chart bands from constants module.

### Governance

- `backend/docs/COMPLIANCE_CLIENT_STATUS_AUTHORITY.md` — new **Score authority** section.

### Tests

- `backend/tests/test_risk_bands_score_authority.py` — boundary scores 0, 40, 41, 59, 60, 79, 80, 89, 90, 100.
- `frontend/src/utils/riskLabel.test.js`
- `frontend/src/utils/scoreAuthorityConstants.test.js`

## Consumer verification

| Surface | Authority source | Local threshold calc removed? |
|---------|------------------|-------------------------------|
| Dashboard score card | `GET /client/compliance-score` + portfolio summary API fields | ✓ |
| Portfolio summary table | API `risk_level`, property row presentation fields | ✓ |
| Property Detail | API `risk_level`, `formatRiskLabel` (label normalisation only) | ✓ |
| Compliance Score page | API grade/colour/message/band_explanation; property `color` | ✓ |
| Score trend chart | Display constants mirror only | ✓ (no grade inference) |
| Reports / Digest / Command Centre | Already used backend `score_to_risk_level` | ✓ (unchanged) |
| Admin | Displays stored/API risk_level | ✓ (unchanged) |
| Exports | Persisted score + backend labels on write | ✓ |

## Explicit non-changes

- Score mathematics (`compliance_scoring_v2`) unchanged.
- Weighting unchanged.
- RAOD unaffected.
- Today authority unaffected.
- Presentation authority (requirement lifecycle) unaffected.
- Production / `main` not touched.

## Acceptance checklist

- [x] Backend owns thresholds.
- [x] Frontend owns presentation only.
- [x] Property and portfolio thresholds match (`80/60/40`).
- [x] Risk wording harmonised (**Moderate risk**).
- [x] No duplicate threshold logic in client score presentation paths.
- [x] Existing score mathematics unchanged.
- [x] Regression tests added.

## Residual notes

- `scoreAuthorityConstants.js` mirrors backend thresholds for chart shading and static copy only — documented as non-authoritative display mirror.
- Legacy persisted `Property.risk_level` values with old 90/70/50 wording are superseded on read when score is present (authoritative derivation from score).
- Contractor/lead scoring modules (`explanation_engine`, `risk_lead_email_service`) use unrelated score domains — out of scope.
