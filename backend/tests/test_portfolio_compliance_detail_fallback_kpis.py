"""Regression tests for portfolio compliance-detail fallback KPI aggregation."""

from services.requirement_satisfaction_service import row_counts_as_missing_evidence


def _accumulate_fallback_kpis(requirements):
    """Mirror portfolio.py fallback path: KPIs from each enriched requirement row."""
    kpis = {"overdue": 0, "expiring_30": 0, "missing": 0, "compliant": 0, "status_valid": 0}
    for r_raw in requirements:
        s = str(r_raw.get("status") or "PENDING").upper()
        if s in ("COMPLIANT", "VALID"):
            kpis["status_valid"] += 1
        if s in ("OVERDUE", "EXPIRED"):
            kpis["overdue"] += 1
        elif s in ("PENDING", "MISSING"):
            if row_counts_as_missing_evidence(r_raw):
                kpis["missing"] += 1
            else:
                kpis["compliant"] += 1
        else:
            kpis["compliant"] += 1
    return kpis


def test_fallback_kpi_evaluates_each_requirement_not_stale_loop_variable():
    requirements = [
        {
            "requirement_id": "r1",
            "status": "PENDING",
            "requirement_satisfied": True,
            "missing_required_document": False,
        },
        {"requirement_id": "r2", "status": "PENDING"},
    ]
    assert _accumulate_fallback_kpis(requirements) == {
        "overdue": 0,
        "expiring_30": 0,
        "missing": 1,
        "compliant": 1,
        "status_valid": 0,
    }

    # Bug pattern: inner loop over matrix reuses last outer `r_raw` for every item.
    stale = requirements[-1]
    wrong = {"missing": 0, "compliant": 0}
    for _ in requirements:
        if row_counts_as_missing_evidence(stale):
            wrong["missing"] += 1
        else:
            wrong["compliant"] += 1
    assert wrong == {"missing": 2, "compliant": 0}


def test_fallback_kpi_status_valid_counts_compliant_status_only():
    requirements = [
        {"requirement_id": "r1", "status": "PENDING"},
        {"requirement_id": "r2", "status": "COMPLIANT", "requirement_satisfied": True},
    ]
    assert _accumulate_fallback_kpis(requirements) == {
        "overdue": 0,
        "expiring_30": 0,
        "missing": 1,
        "compliant": 1,
        "status_valid": 1,
    }
