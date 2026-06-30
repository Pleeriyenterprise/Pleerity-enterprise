# PROPERTY-DETAIL-PRESENTATION-AUTHORITY-ALIGNMENT-01-STAGING-VALIDATION

**Verdict:** `STAGING_VALIDATION_GO`
**Run:** 20260630T224033Z
**Staging SHA:** 6c3d219049b0124fe21260ec93e16354803eff2c

## Checks

- local_catalog_kpi_pytest: **PASS**
- staging_backend_deployed: **PASS**
- staging_frontend_deployed: **PASS**
- api_lifecycle_satisfied_field: **PASS**
- api_status_valid_unchanged: **PASS**
- api_dual_kpi_numeric: **PASS**
- frontend_valid_for_scoring_copy: **PASS**
- frontend_requirements_satisfied_copy: **PASS**

## compliance-detail probe

```json
{
  "status": 200,
  "kpis": {
    "overdue": 0,
    "expiring_30": 0,
    "missing": 3,
    "compliant": 5,
    "status_valid": 3,
    "lifecycle_satisfied_count": 3
  },
  "matrix_len": 8
}
```