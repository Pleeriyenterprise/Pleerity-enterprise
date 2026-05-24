"""VERIFY-02 G1 — Today attention authority ranking tests."""
from __future__ import annotations

from services.client_priority_stream import (
    ACTION_OPEN_ISSUE,
    ACTION_PENDING_APPROVAL,
    ACTION_RISK_SIGNAL,
    ACTION_OPEN_WORK_ORDER,
)
from services.ops_runtime_verify_02.attention_authority_service import AttentionAuthorityService
from services.today_attention_ranking import (
    ATTENTION_PRECEDENCE,
    attention_class_for_task,
    today_attention_sort_key,
)
from services import unified_tasks_service as uts


def _items_for_harness_eval(tasks: list) -> list:
    """Mirror G1 harness active-item extraction."""
    out = []
    pos = 0
    for t in tasks:
        cls = attention_class_for_task(t)
        out.append(
            {
                "id": t["id"],
                "class": cls,
                "urgency_rank": 1,
                "position": pos,
                "section": t.get("section"),
                "source_type": t.get("source_type"),
            }
        )
        pos += 1
    return out


def _assert_no_precedence_violations(tasks: list) -> None:
    items = _items_for_harness_eval(tasks)
    result = AttentionAuthorityService().evaluate_order(items)
    assert not result["precedence_violations"], result["precedence_violations"]


def test_risk_signal_outranks_work_order_when_both_urgent():
    risk = {
        "id": "risk_signal:rs1",
        "source_type": "risk_signal",
        "section": "urgent",
        "urgency_level": "high",
        "impact_score": 10,
        "metadata": {"action_type": ACTION_RISK_SIGNAL, "severity": "high"},
    }
    wo = {
        "id": "work_order:wo1",
        "source_type": "work_order",
        "section": "urgent",
        "urgency_level": "critical",
        "impact_score": 80,
        "metadata": {"action_type": ACTION_OPEN_WORK_ORDER},
    }
    sorted_tasks = uts._sort_tasks([wo, risk])
    assert [t["id"] for t in sorted_tasks] == ["risk_signal:rs1", "work_order:wo1"]
    _assert_no_precedence_violations(sorted_tasks)


def test_risk_signal_outranks_requirement_when_both_upcoming():
    risk = {
        "id": "risk_signal:rs2",
        "source_type": "risk_signal",
        "section": "upcoming",
        "urgency_level": "medium",
        "impact_score": 5,
        "metadata": {"action_type": ACTION_RISK_SIGNAL, "severity": "medium"},
    }
    req = {
        "id": "requirement:r1",
        "source_type": "requirement",
        "section": "upcoming",
        "urgency_level": "medium",
        "impact_score": 40,
        "metadata": {"action_type": "missing_document"},
    }
    sorted_tasks = uts._sort_tasks([req, risk])
    assert sorted_tasks[0]["id"] == "risk_signal:rs2"
    _assert_no_precedence_violations(sorted_tasks)


def test_issue_outranks_approval_when_both_in_progress():
    approval = {
        "id": "approval:a1",
        "source_type": "approval",
        "section": "in_progress",
        "urgency": "due_soon",
        "urgency_level": "medium",
        "impact_score": 30,
        "metadata": {"action_type": ACTION_PENDING_APPROVAL},
    }
    issue = {
        "id": "issue:i1",
        "source_type": "issue",
        "section": "in_progress",
        "urgency": "on_track",
        "urgency_level": "medium",
        "impact_score": 5,
        "metadata": {"action_type": ACTION_OPEN_ISSUE},
    }
    sorted_tasks = uts._sort_tasks([approval, issue])
    assert sorted_tasks[0]["id"] == "issue:i1"
    _assert_no_precedence_violations(sorted_tasks)


def test_sort_key_is_deterministic_with_stable_tiebreaker():
    a = {
        "id": "work_order:aaa",
        "source_type": "work_order",
        "section": "urgent",
        "title": "Job A",
        "impact_score": 50,
        "metadata": {"action_type": ACTION_OPEN_WORK_ORDER},
    }
    b = {
        "id": "work_order:bbb",
        "source_type": "work_order",
        "section": "urgent",
        "title": "Job A",
        "impact_score": 50,
        "metadata": {"action_type": ACTION_OPEN_WORK_ORDER},
    }
    assert today_attention_sort_key(a) < today_attention_sort_key(b)


def test_active_risk_signal_section_is_urgent():
    section = uts._section_for_action(uts.ACTION_RISK_SIGNAL, "medium", None)
    assert section == "urgent"


def test_cross_section_urgent_work_order_before_upcoming_risk_resolved_by_risk_in_urgent():
    """Regression: WO in urgent must not precede active risk relegated to upcoming."""
    risk = {
        "id": "risk_signal:rs_x",
        "source_type": "risk_signal",
        "section": "urgent",
        "urgency_level": "medium",
        "impact_score": 5,
        "metadata": {"action_type": ACTION_RISK_SIGNAL, "severity": "medium"},
    }
    wo = {
        "id": "work_order:wo_x",
        "source_type": "work_order",
        "section": "urgent",
        "urgency_level": "critical",
        "impact_score": 90,
        "metadata": {"action_type": ACTION_OPEN_WORK_ORDER},
    }
    flat = uts._sort_tasks([wo, risk])
    _assert_no_precedence_violations(flat)


def test_attention_class_matches_precedence_constants():
    assert ATTENTION_PRECEDENCE["active_risk"] < ATTENTION_PRECEDENCE["open_operational_debt"]
    assert ATTENTION_PRECEDENCE["open_operational_debt"] < ATTENTION_PRECEDENCE["time_bound_reminder"]
    assert attention_class_for_task({"source_type": "risk_signal", "metadata": {"action_type": ACTION_RISK_SIGNAL}}) == "active_risk"
