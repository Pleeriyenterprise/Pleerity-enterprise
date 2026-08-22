"""Negative authorisation: a contractor must not access another landlord's job."""
from fastapi import HTTPException

from routes.contractor_portal import _ensure_assigned_to_me


def test_contractor_denied_other_landlord_job_is_403():
    other_landlord_job = {
        "work_order_id": "wo-other-landlord",
        "client_id": "landlord-b",
        "contractor_id": "ctr-assigned-to-b",
        "status": "ASSIGNED",
    }
    try:
        _ensure_assigned_to_me(other_landlord_job, "ctr-for-landlord-a")
        raise AssertionError("expected authorised denial")
    except HTTPException as exc:
        assert exc.status_code == 403
        assert "authorised" in str(exc.detail).lower() or "not authorised" in str(exc.detail).lower()


def test_assigned_contractor_is_allowed():
    wo = {
        "work_order_id": "wo-mine",
        "client_id": "landlord-a",
        "contractor_id": "ctr-for-landlord-a",
    }
    _ensure_assigned_to_me(wo, "ctr-for-landlord-a")
