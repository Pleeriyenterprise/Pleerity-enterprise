"""Scenario tests for SLA-aware contractor routing (pure scoring)."""
from datetime import datetime, timezone, timedelta

from services.contractor_recommendation import (
    compute_assignment_routing_meta,
    recommend_contractors,
)


def test_scenario_a_electrical_postcode_filters_ranking():
    wo = {
        "work_order_id": "wo-a",
        "category": "electrical",
        "recommended_contractor_type": "electrician",
        "severity": "medium",
    }
    prop = {"postcode": "SW1A 1AA", "region": "London"}
    c_elig = [
        {
            "contractor_id": "e1",
            "trade_types": ["electrical"],
            "status": "active",
            "vetted": True,
            "credentials": [],
            "areas_served": ["SW1A"],
            "region": "London",
        },
        {
            "contractor_id": "e2",
            "trade_types": ["electrical"],
            "status": "active",
            "vetted": True,
            "credentials": [],
            "areas_served": ["EH1"],
            "region": "Edinburgh",
        },
    ]
    r = recommend_contractors(wo, prop, c_elig, eligible_only=True, client_id_for_preference="client-1")
    assert r["total"] == 2
    assert r["contractors"][0]["contractor_id"] == "e1"
    assert any("electrical" in x.lower() for x in r["contractors"][0]["reasons"])


def test_scenario_b_workload_deprioritises_busy_contractor():
    wo = {
        "work_order_id": "wo-b",
        "category": "plumbing",
        "recommended_contractor_type": "plumber",
        "severity": "low",
    }
    contractors = [
        {
            "contractor_id": "p1",
            "trade_types": ["plumbing"],
            "status": "active",
            "vetted": True,
            "credentials": [],
            "areas_served": [],
        },
        {
            "contractor_id": "p2",
            "trade_types": ["plumbing"],
            "status": "active",
            "vetted": True,
            "credentials": [],
            "areas_served": [],
        },
    ]
    wl = {"p1": 0, "p2": 11}
    r = recommend_contractors(wo, None, contractors, workload_map=wl, eligible_only=True)
    assert r["contractors"][0]["contractor_id"] == "p1"
    assert r["contractors"][0]["open_assigned_jobs"] == 0


def test_scenario_c_near_sla_marks_urgent_routing():
    soon = (datetime.now(timezone.utc) + timedelta(hours=6)).isoformat()
    wo = {
        "work_order_id": "wo-c",
        "category": "general",
        "recommended_contractor_type": "general",
        "severity": "medium",
        "sla_complete_by": soon,
    }
    meta = compute_assignment_routing_meta(wo, now_utc=datetime.now(timezone.utc))
    assert meta["assignment_urgency"] in ("high", "critical")


def test_scenario_d_suspended_excluded_by_legacy_filter():
    wo = {"work_order_id": "wo-d", "category": "general", "recommended_contractor_type": "general"}
    contractors = [
        {"contractor_id": "x1", "trade_types": ["general"], "status": "suspended", "vetted": True, "credentials": [], "areas_served": []},
    ]
    r = recommend_contractors(wo, None, contractors, eligible_only=False)
    assert r["total"] == 0
    assert r["routing"]["no_eligible_contractors"]
