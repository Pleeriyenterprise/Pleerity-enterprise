"""Today projection: urgency band, action titles, business_actions cap, dedupe, actionable filter."""

from datetime import datetime, timezone, timedelta

import pytest

from services.today_projection_service import (
    build_business_actions_for_task,
    cap_and_order_business_actions,
    dedupe_tasks_by_requirement,
    derive_today_urgency,
    enrich_task_bucket,
    today_action_oriented_title,
    today_task_is_actionable,
)


def test_derive_today_urgency_overdue_days():
    now = datetime(2026, 4, 2, 12, 0, 0, tzinfo=timezone.utc)
    assert derive_today_urgency({"overdue_days": 3}, now) == "overdue"


def test_derive_today_urgency_due_soon():
    now = datetime(2026, 4, 2, 12, 0, 0, tzinfo=timezone.utc)
    due = (now + timedelta(days=3)).isoformat()
    assert derive_today_urgency({"due_date": due, "overdue_days": None}, now) == "due_soon"


def test_derive_today_urgency_on_track_far_future():
    now = datetime(2026, 4, 2, 12, 0, 0, tzinfo=timezone.utc)
    due = (now + timedelta(days=30)).isoformat()
    assert derive_today_urgency({"due_date": due, "overdue_days": None}, now) == "on_track"


def test_derive_today_urgency_critical_without_due_not_auto_due_soon():
    """High/critical urgency_level alone must not force due_soon (QA: avoid over-classification)."""
    now = datetime(2026, 4, 2, 12, 0, 0, tzinfo=timezone.utc)
    task = {
        "urgency_level": "critical",
        "overdue_days": None,
        "due_date": None,
        "metadata": {"action_type": "risk_signal"},
    }
    assert derive_today_urgency(task, now) == "on_track"


def test_derive_today_urgency_work_order_breach_without_due_is_due_soon():
    from services.client_priority_stream import ACTION_WORK_ORDER_BREACHED

    now = datetime(2026, 4, 2, 12, 0, 0, tzinfo=timezone.utc)
    task = {
        "urgency_level": "critical",
        "overdue_days": None,
        "due_date": None,
        "metadata": {"action_type": ACTION_WORK_ORDER_BREACHED},
    }
    assert derive_today_urgency(task, now) == "due_soon"


def test_cap_business_actions_max_two_and_primary():
    acts = [
        {"id": "view_requirement", "label": "View"},
        {"id": "upload_certificate", "label": "Upload"},
        {"id": "create_compliance_work_order", "label": "Create job", "requirement_id": "r1"},
    ]
    capped = cap_and_order_business_actions(acts, max_actions=2)
    assert len(capped) == 2
    assert capped[0]["id"] == "create_compliance_work_order"
    assert capped[0].get("primary") is True
    assert capped[1].get("primary") is False


def test_today_inbox_title_from_labels_for_work_order():
    task = {
        "source_type": "work_order",
        "source_entity_id": "wo1",
        "metadata": {},
        "title": "Job",
    }
    title, flag = today_action_oriented_title(task)
    assert flag is True
    assert title == "Keep this job moving forward"


def test_requirement_action_title_uses_phrase():
    task = {
        "source_type": "requirement",
        "source_entity_id": "req-1",
        "metadata": {"requirement_code": "gas_safety", "action_type": "missing_document"},
        "title": "Gas safety missing",
    }
    title, flag = today_action_oriented_title(task)
    assert flag is True
    assert title
    assert "gas" in title.lower() or "certificate" in title.lower() or "upload" in title.lower() or "renew" in title.lower()


def test_dedupe_keeps_higher_impact():
    a = {
        "id": "requirement:r1",
        "source_type": "requirement",
        "property_id": "p1",
        "source_entity_id": "r1",
        "impact_score": 10,
        "title": "A",
    }
    b = {
        "id": "tenant_request:tr1",
        "source_type": "tenant_request",
        "property_id": "p1",
        "requirement_id": "r1",
        "impact_score": 50,
        "title": "B",
    }
    out = dedupe_tasks_by_requirement([a, b])
    assert len(out) == 1
    assert out[0]["impact_score"] == 50


def test_enrich_open_bucket_drops_non_actionable():
    now = datetime.now(timezone.utc)
    bad = {
        "id": "orphan:x",
        "source_type": "priority_action",
        "title": "Noise",
        "section": "upcoming",
        "impact_score": 5,
        "metadata": {},
    }
    good = {
        "id": "work_order:wo1",
        "source_type": "work_order",
        "source_entity_id": "wo1",
        "title": "Job",
        "section": "upcoming",
        "impact_score": 40,
        "metadata": {"action_type": "open_work_order"},
    }
    bucket = enrich_task_bucket([bad, good], now, filter_non_actionable=True)
    assert len(bucket) == 1
    assert bucket[0]["id"] == "work_order:wo1"


def test_today_task_is_actionable_with_primary_url_only():
    t = {"business_actions": [], "primary_action_url": "/dashboard"}
    assert today_task_is_actionable(t) is True


def test_build_business_actions_issue_has_create_before_view():
    task = {
        "source_type": "issue",
        "source_entity_id": "iss1",
        "property_id": "p1",
        "metadata": {},
    }
    raw = build_business_actions_for_task(task)
    capped = cap_and_order_business_actions(raw, 2)
    assert capped[0]["id"] == "create_maintenance_job"
    assert capped[0].get("primary") is True
