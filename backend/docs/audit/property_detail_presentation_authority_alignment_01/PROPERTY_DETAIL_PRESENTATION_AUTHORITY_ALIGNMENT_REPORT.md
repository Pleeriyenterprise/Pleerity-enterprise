# PROPERTY-DETAIL-PRESENTATION-AUTHORITY-ALIGNMENT-01

**Branch:** `develop` only · **Production:** not touched · **Authority:** unchanged (presentation only)

---

## Summary

Property Detail now communicates two governed requirement metrics with Dashboard-aligned terminology:

| Before | After | API field | Authority |
|--------|-------|-----------|-----------|
| **Valid** | **Valid for scoring** | `kpis.status_valid` | Projected `COMPLIANT` / `VALID` |
| *(not shown)* | **Requirements satisfied** | `kpis.lifecycle_satisfied_count` | `is_requirement_satisfied()` |

Misleading copy (“Counts follow the requirements table below — one list, same definitions”) replaced with explicit dual-metric explanation.

---

## Before / after (conceptual)

### Before
- Operating hub: Overdue · Expiring · Missing documents · **Valid (2)**
- Compliance card: implied counters match table definitions
- User sees 7 “Valid” table rows but **Valid: 2** — unexplained

### After
- Operating hub: Overdue · Expiring · Missing documents · **Requirements satisfied (7)** · **Valid for scoring (2)**
- Compliance card: explains both measures and that they may legitimately differ
- VALID filter unchanged (still COMPLIANT/VALID rows only); label now **Valid for scoring**

---

## Label mapping

| UI surface | Label source | Tooltip source |
|------------|--------------|----------------|
| Operating hub — satisfied tile | `REPORTING_SEMANTICS_LABELS.lifecycle_satisfied_count.label` | same `.tooltip` |
| Operating hub — scoring tile | `REPORTING_SEMANTICS_LABELS.compliant_requirement_count.label` | same `.tooltip` |
| Compliance tab — filter button | `compliant_requirement_count.label` | same `.tooltip` |
| Compliance card — explanation | `PROPERTY_DETAIL_COMPLIANCE_KPI_EXPLANATION` | — |

Shared helper: `frontend/src/utils/propertyDetailComplianceKpiPresentation.js`

---

## Authority mapping

| Metric | Backend computation | Changed? |
|--------|---------------------|----------|
| `status_valid` | `catalog_compliance.py` — status ∈ {COMPLIANT, VALID} | **No** |
| `lifecycle_satisfied_count` | `is_requirement_satisfied(row)` per matrix row | **Added to API** (existing authority) |
| Property score | Catalog weighted matrix | **No** |
| Table status chips | `complianceObligationStatusLabel` + lifecycle badges | **No** |
| VALID filter | COMPLIANT/VALID projected status | **No** |

---

## API mapping

**Endpoint:** `GET /api/portfolio/properties/{property_id}/compliance-detail`

```json
{
  "kpis": {
    "overdue": 0,
    "expiring_30": 0,
    "missing": 0,
    "compliant": 5,
    "status_valid": 2,
    "lifecycle_satisfied_count": 7
  }
}
```

Frontend consumes via `propertyDetailComplianceKpiCountsFromApi()` — **no React-side counting**.

---

## Changed files

| File | Change |
|------|--------|
| `backend/services/catalog_compliance.py` | Expose `lifecycle_satisfied_count` in KPIs |
| `backend/routes/portfolio.py` | Fallback path: same field |
| `backend/docs/COMPLIANCE_CLIENT_STATUS_AUTHORITY.md` | Surface matrix row for Property Detail dual KPIs |
| `frontend/src/utils/propertyDetailComplianceKpiPresentation.js` | **New** — labels, copy, API mapping |
| `frontend/src/utils/reportingSemanticsLabels.js` | Lifecycle tooltip aligned with declarations |
| `frontend/src/pages/PropertyDetailPage.js` | Labels, copy, API-only counts |
| `frontend/src/components/property/PropertyOperatingHub.jsx` | Five-tile KPI strip |
| `backend/tests/test_catalog_compliance_kpi_status_valid.py` | Lifecycle satisfied regression |
| `frontend/src/utils/propertyDetailComplianceKpiPresentation.test.js` | **New** |
| `frontend/src/pages/PropertyDetailPage.validKpiParity.test.js` | Updated labels |
| `frontend/src/pages/PropertyDetailPage.presentationAuthority.test.js` | **New** — multi-scenario |

---

## Tests

- Backend: 4 passed (`test_catalog_compliance_kpi_status_valid.py`)
- Frontend: 12 passed (presentation + parity)

Scenarios covered: mixed document/declaration, document-only, declaration-only, mixed satisfied/overdue, all satisfied, Operating hub tiles.

---

## Remaining risks

| Risk | Level | Mitigation |
|------|-------|------------|
| Legacy clients without `lifecycle_satisfied_count` | Low | UI shows `—` until API deployed |
| Portfolio summary aggregation | Low | `lifecycle_satisfied_count` rolled up in `get_portfolio_compliance_from_catalog` |
| User expects satisfied tile to filter table | Low | Tile opens Compliance tab (all rows); tooltips explain |

---

## Production recommendation

Deploy backend + frontend together on `develop` staging first. No KPI semantics change — safe to promote after smoke on Property Detail Operating + Compliance tabs. Label-only risk is negligible; new API field is additive.

---

## Acceptance criteria

| Criterion | Status |
|-----------|--------|
| "Valid" replaced by governed wording | ✓ |
| "Requirements satisfied" from lifecycle authority | ✓ |
| No KPI semantics change for `status_valid` | ✓ |
| No score semantics change | ✓ |
| No frontend inference for satisfied count | ✓ |
| Dashboard terminology parity | ✓ |
| User can understand 7 vs 2 | ✓ |

**Evidence:** [PROPERTY_DETAIL_PRESENTATION_AUTHORITY_ALIGNMENT_EVIDENCE.json](./PROPERTY_DETAIL_PRESENTATION_AUTHORITY_ALIGNMENT_EVIDENCE.json)
