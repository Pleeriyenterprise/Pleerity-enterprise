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
