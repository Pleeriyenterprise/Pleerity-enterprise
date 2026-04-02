"""Unified client calendar timeline: requirements + work order visits."""
from datetime import datetime, timezone

from services.client_calendar_timeline_service import (
    build_ical_from_timeline_events,
    build_requirement_timeline_events,
    build_work_order_timeline_events,
    filter_timeline_events,
    summarize_events,
)
from services.maintenance_service import (
    STATUS_COMPLETED,
    WORK_ORDER_KIND_COMPLIANCE,
    WORK_ORDER_KIND_MAINTENANCE,
)
from services.work_order_schedule_constants import SCHEDULE_STATUS_CONFIRMED


def test_requirement_event_uses_effective_date_and_route():
    start = datetime(2026, 4, 1, tzinfo=timezone.utc)
    end = datetime(2026, 5, 1, tzinfo=timezone.utc)
    req = {
        "requirement_id": "r1",
        "property_id": "p1",
        "requirement_type": "GAS_SAFETY",
        "applicability": "REQUIRED",
        "confirmed_expiry_date": "2026-04-15T00:00:00+00:00",
    }
    prop_map = {"p1": {"property_id": "p1", "address_line_1": "1 Test St", "nickname": "Flat A"}}
    ev = build_requirement_timeline_events([req], prop_map, start, end)
    assert len(ev) == 1
    assert ev[0]["event_category"] == "requirement"
    assert ev[0]["date"] == "2026-04-15"
    assert ev[0]["date_source"] == "confirmed"
    assert "property_id=p1" in ev[0]["primary_route"]
    assert "requirement_id=r1" in ev[0]["primary_route"]


def test_work_order_confirmed_visit_event():
    start = datetime(2026, 4, 1, tzinfo=timezone.utc)
    end = datetime(2026, 5, 1, tzinfo=timezone.utc)
    wo = {
        "work_order_id": "w1",
        "property_id": "p1",
        "work_order_kind": WORK_ORDER_KIND_MAINTENANCE,
        "status": "ASSIGNED",
        "scheduled_at": "2026-04-20T14:30:00+00:00",
        "schedule_status": SCHEDULE_STATUS_CONFIRMED,
    }
    prop_map = {"p1": {"property_id": "p1", "address_line_1": "1 Test St"}}
    ev = build_work_order_timeline_events([wo], prop_map, start, end)
    assert len(ev) == 1
    assert ev[0]["event_type"] == "work_order_visit_confirmed"
    assert ev[0]["date"] == "2026-04-20"
    assert "work_order_id=w1" in ev[0]["primary_route"]


def test_completed_work_order_emits_single_completion_not_visit():
    start = datetime(2026, 4, 1, tzinfo=timezone.utc)
    end = datetime(2026, 5, 1, tzinfo=timezone.utc)
    wo = {
        "work_order_id": "w2",
        "property_id": "p1",
        "work_order_kind": WORK_ORDER_KIND_COMPLIANCE,
        "status": STATUS_COMPLETED,
        "completed_at": "2026-04-18T10:00:00+00:00",
        "scheduled_at": "2026-04-17T09:00:00+00:00",
        "schedule_status": SCHEDULE_STATUS_CONFIRMED,
    }
    prop_map = {"p1": {"property_id": "p1", "address_line_1": "1 Test St"}}
    ev = build_work_order_timeline_events([wo], prop_map, start, end)
    assert len(ev) == 1
    assert ev[0]["event_type"] == "compliance_job_completed"


def test_filter_categories():
    events = [
        {"event_id": "1", "event_category": "requirement"},
        {"event_id": "2", "event_category": "scheduled_job"},
    ]
    f = filter_timeline_events(events, categories={"requirement"})
    assert len(f) == 1
    assert f[0]["event_id"] == "1"


def test_summarize_events():
    s = summarize_events(
        [
            {"event_category": "requirement", "event_type": "requirement_overdue"},
            {"event_category": "requirement", "event_type": "requirement_expiring_soon"},
            {"event_category": "scheduled_job"},
        ]
    )
    assert s["total_events"] == 3
    assert s["overdue_count"] == 1
    assert s["expiring_soon_count"] == 1


def test_build_ical_uses_timeline_titles_and_dtstart_shapes():
    now = datetime(2026, 4, 2, 12, 0, 0, tzinfo=timezone.utc)
    req_ev = {
        "event_id": "evt_req_1",
        "event_type": "requirement_expiring_soon",
        "event_category": "requirement",
        "title": "Requirement expiring soon: Gas safety",
        "date": "2026-04-10",
        "datetime_utc": "2026-04-10T00:00:00+00:00",
        "status": "EXPIRING_SOON",
        "property_name": "1 Test St",
    }
    visit_ev = {
        "event_id": "evt_visit_1",
        "event_type": "work_order_visit_confirmed",
        "event_category": "scheduled_job",
        "title": "Confirmed repair visit",
        "date": "2026-04-20",
        "datetime_utc": "2026-04-20T14:30:00+00:00",
        "status": "confirmed",
        "property_name": "1 Test St",
    }
    ical = build_ical_from_timeline_events(
        [req_ev, visit_ev],
        calendar_name="Acme",
        client_ref="CRN1",
        now_utc=now,
    )
    assert "SUMMARY:Requirement expiring soon: Gas safety" in ical
    assert "DTSTART;VALUE=DATE:20260410" in ical
    assert "SUMMARY:Confirmed repair visit" in ical
    assert "DTSTART:20260420T143000Z" in ical
    assert ical.count("BEGIN:VEVENT") == 2


def test_ics_export_filter_matches_calendar_events_subset():
    """Export uses the same filter_timeline_events as /calendar/events (category slice)."""
    now = datetime(2026, 4, 2, 12, 0, 0, tzinfo=timezone.utc)
    req_ev = {
        "event_id": "evt_req_only",
        "event_type": "requirement_due",
        "event_category": "requirement",
        "title": "Requirement due: Gas safety",
        "date": "2026-04-10",
        "datetime_utc": "2026-04-10T00:00:00+00:00",
        "status": "PENDING",
        "property_name": "1 Test St",
    }
    visit_ev = {
        "event_id": "evt_visit_only",
        "event_type": "work_order_visit_confirmed",
        "event_category": "scheduled_job",
        "title": "Confirmed repair visit",
        "date": "2026-04-20",
        "datetime_utc": "2026-04-20T14:30:00+00:00",
        "status": "confirmed",
        "property_name": "1 Test St",
    }
    combined = [req_ev, visit_ev]
    only_req = filter_timeline_events(combined, categories={"requirement"}, urgent_only=False)
    ical = build_ical_from_timeline_events(
        only_req,
        calendar_name="Acme",
        client_ref="X",
        now_utc=now,
    )
    assert "Requirement due: Gas safety" in ical
    assert "Confirmed repair visit" not in ical
    assert ical.count("BEGIN:VEVENT") == 1
