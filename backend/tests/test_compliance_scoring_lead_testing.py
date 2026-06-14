from datetime import datetime, timezone

from services.compliance_scoring_v2 import compute_property_score_v2, _applies_if


def _scotland_prop(**overrides):
    base = {
        "property_id": "p1",
        "jurisdiction": "Scotland",
        "property_type": "flat",
        "tenancy_active": True,
        "building_age_years": 70,
        "cert_gas_safety": "YES",
        "has_gas_supply": True,
    }
    base.update(overrides)
    return base


def test_lead_testing_applies_if_scotland_age_gt_50_tenancy_active():
    assert _applies_if("LEAD_TESTING", _scotland_prop(), None) is True


def test_lead_testing_not_applicable_when_age_missing():
    assert _applies_if("LEAD_TESTING", _scotland_prop(building_age_years=None), None) is False


def test_lead_testing_not_applicable_when_age_lte_50():
    assert _applies_if("LEAD_TESTING", _scotland_prop(building_age_years=50), None) is False


def test_lead_testing_not_applicable_england():
    assert _applies_if(
        "LEAD_TESTING",
        _scotland_prop(jurisdiction="England", building_age_years=70),
        None,
    ) is False


def test_lead_testing_not_applicable_without_tenancy():
    assert _applies_if("LEAD_TESTING", _scotland_prop(tenancy_active=False), None) is False


def test_v2_lead_testing_in_breakdown_when_applicable():
    now = datetime.now(timezone.utc)
    req = [{"requirement_code": "lead_testing", "requirement_type": "lead_testing", "status": "MISSING"}]
    result = compute_property_score_v2(
        property_doc=_scotland_prop(),
        client_doc={"default_jurisdiction": "Scotland"},
        requirements=req,
        documents=[],
        open_issues_count=0,
        overdue_work_orders_count=0,
        open_risks_count=0,
        as_of=now,
    )
    lt = next(r for r in result["requirement_breakdown"] if r["requirement_code"] == "LEAD_TESTING")
    assert lt["applies_if"] is True
    assert lt["weight"] == 8.0
    assert lt["applicable_points"] == 8.0


def test_v2_lead_testing_excluded_from_denominator_when_not_applicable():
    now = datetime.now(timezone.utc)
    result = compute_property_score_v2(
        property_doc=_scotland_prop(building_age_years=30),
        client_doc={"default_jurisdiction": "Scotland"},
        requirements=[],
        documents=[],
        open_issues_count=0,
        overdue_work_orders_count=0,
        open_risks_count=0,
        as_of=now,
    )
    lt = next(r for r in result["requirement_breakdown"] if r["requirement_code"] == "LEAD_TESTING")
    assert lt["applies_if"] is False
    assert lt["applicable_points"] == 0.0
