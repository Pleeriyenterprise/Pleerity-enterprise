"""Tests for assignment eligibility recovery guidance."""
from services.assignment_eligibility_recovery import build_assignment_eligibility_recovery


def test_recovery_primary_blocker_coverage():
    diag = {
        "visible_in_directory": 16,
        "excluded_not_assignment_ready": 5,
        "excluded_location_postcode": 10,
        "excluded_execution_capability": 1,
        "excluded_property_scope": 0,
        "excluded_maintenance_trade": 0,
        "excluded_service_region_jurisdiction": 0,
        "excluded_wrong_client_scope": 0,
        "eligible": 0,
    }
    out = build_assignment_eligibility_recovery(
        diag, job_jurisdiction="England", property_postcode="B1 1AA", eligible=0
    )
    assert out["primary_blocker"] == "update_coverage"
    keys = [a["key"] for a in out["recovery_actions"]]
    assert "update_coverage" in keys
    assert "complete_setup" in keys
    assert "edit_trade_capability" in keys
    assert "add_contractor" in keys


def test_recovery_names_existing_contractor_out_of_coverage():
    diag = {
        "visible_in_directory": 2,
        "excluded_not_assignment_ready": 0,
        "excluded_location_postcode": 1,
        "excluded_execution_capability": 0,
        "excluded_property_scope": 0,
        "excluded_maintenance_trade": 0,
        "excluded_service_region_jurisdiction": 0,
        "excluded_wrong_client_scope": 0,
        "eligible": 0,
    }
    out = build_assignment_eligibility_recovery(
        diag,
        job_jurisdiction="England",
        property_postcode="EN10 6AF",
        eligible=0,
        exclusion_samples={
            "excluded_location_postcode": [{"contractor_id": "c1", "name": "Hartley Plumbing Ltd"}],
        },
    )
    coverage = next(a for a in out["recovery_actions"] if a["key"] == "update_coverage")
    assert "Hartley Plumbing Ltd already exists but does not currently cover this postcode" in coverage["detail"]


def test_email_duplicate_message_explains_coverage_gap():
    from services.contractor_service import email_duplicate_assignment_message

    msg = email_duplicate_assignment_message(
        {
            "company_name": "Hartley Plumbing Ltd",
            "client_id": "cl-1",
            "coverage_area": ["B1"],
            "areas_served": ["B1"],
        },
        client_id="cl-1",
        property_postcode="EN10 6AF",
        property_jurisdiction="England",
    )
    assert "Hartley Plumbing Ltd already exists but does not currently cover this postcode" in msg
