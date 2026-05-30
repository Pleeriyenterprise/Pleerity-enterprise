"""Tests for Phase 2A operational recovery orchestration."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from services.operational_recovery_service import (
    classify_recovery_state,
    generate_recovery_actions,
    generate_recovery_guidance,
    suppress_invalid_recovery_guidance,
)
from services.recovery_guardrails import (
    assert_recovery_convergence,
    assert_recovery_guidance_safe,
    is_authority_safe_recovery_action,
)
from services.recovery_intelligence_service import enrich_recovery_intelligence
from services.workflow_timer_service import work_order_stall_context


def test_authority_safe_recovery_actions():
    assert is_authority_safe_recovery_action("review_quote")
    assert is_authority_safe_recovery_action("open_job")
    assert not is_authority_safe_recovery_action("approve_quote")
    assert not is_authority_safe_recovery_action("assign_contractor")
    assert not is_authority_safe_recovery_action("verify_evidence")


def test_recovery_guidance_human_readable():
    g = generate_recovery_guidance(
        "CONTRACTOR_NON_RESPONSE",
        waiting_on_party="contractor",
        age_hours=30,
        entity_label="Boiler repair",
        entity_id="wo1",
    )
    assert "contractor" in g["recovery_summary"].lower()
    assert "workflow" not in g["recovery_summary"].lower()
    assert "escalation" not in g["recovery_explanation"].lower()
    assert g["authority_safe"] is True
    assert_recovery_guidance_safe(g)


def test_classify_contractor_non_response():
    now = datetime.now(timezone.utc)
    wo = {
        "work_order_id": "wo1",
        "status": "ASSIGNED",
        "price_status": "AWAITING_QUOTE",
        "awaiting_quote_since": (now - timedelta(hours=30)).isoformat(),
        "contractor_id": "ctr1",
    }
    stall = work_order_stall_context(wo)
    rtype = classify_recovery_state("work_order", wo, stall=stall)
    assert rtype == "CONTRACTOR_NON_RESPONSE"


def test_classify_quote_negotiation_loop():
    wo = {
        "work_order_id": "wo2",
        "status": "ASSIGNED",
        "price_status": "REVISION_REQUESTED",
        "awaiting_contractor_quote_revision_since": datetime.now(timezone.utc).isoformat(),
        "quote_negotiation_history": [
            {"event": "revision_requested"},
            {"event": "revision_requested"},
            {"event": "revision_requested"},
        ],
    }
    stall = work_order_stall_context(wo)
    rtype = classify_recovery_state("work_order", wo, stall=stall)
    assert rtype == "QUOTE_NEGOTIATION_LOOP"


def test_classify_visit_reschedule_loop():
    wo = {
        "work_order_id": "wo3",
        "status": "SCHEDULED",
        "schedule_status": "reschedule_requested",
        "awaiting_visit_reschedule_since": datetime.now(timezone.utc).isoformat(),
        "reschedule_count": 3,
    }
    stall = work_order_stall_context(wo)
    rtype = classify_recovery_state("work_order", wo, stall=stall)
    assert rtype == "VISIT_RESCHEDULE_LOOP"


def test_classify_abandonment_risk():
    now = datetime.now(timezone.utc)
    wo = {
        "work_order_id": "wo4",
        "status": "ASSIGNED",
        "price_status": "AWAITING_QUOTE",
        "awaiting_quote_since": (now - timedelta(hours=80)).isoformat(),
        "contractor_id": "ctr1",
    }
    stall = work_order_stall_context(wo)
    rtype = classify_recovery_state("work_order", wo, stall=stall, nudge_count=3)
    assert rtype == "WORK_ORDER_ABANDONMENT_RISK"


def test_classify_evidence_rejection_loop():
    req = {"requirement_id": "r1", "status": "OVERDUE"}
    rtype = classify_recovery_state("requirement", req, evidence_rejection_count=3)
    assert rtype == "EVIDENCE_REJECTION_LOOP"


def test_suppress_terminal_entity():
    g = generate_recovery_guidance(
        "WAITING_ON_CONTRACTOR_ACTION",
        waiting_on_party="contractor",
        age_hours=10,
        entity_id="wo5",
    )
    out = suppress_invalid_recovery_guidance(g, entity_terminal=True)
    assert out["suppressed"] is True
    assert out["suppression_state"] == "entity_terminal"


def test_recovery_actions_all_safe():
    actions = generate_recovery_actions(
        "QUOTE_NEGOTIATION_LOOP",
        waiting_on_party="landlord",
        entity_type="work_order",
        entity_id="wo6",
    )
    for a in actions:
        assert is_authority_safe_recovery_action(a["action_id"])


def test_intelligence_coarse_confidence_only():
    g = generate_recovery_guidance(
        "VISIT_RESCHEDULE_LOOP",
        waiting_on_party="contractor",
        age_hours=80,
        repetition_count=3,
        entity_id="wo7",
    )
    enriched = enrich_recovery_intelligence(g, nudge_count=2, has_safe_action=True)
    assert enriched["recovery_confidence"] in ("LOW", "MODERATE", "HIGH")
    assert enriched["recovery_likelihood"] in ("LOW", "MODERATE", "HIGH")
    assert "instability_signals" in enriched


def test_recovery_convergence_no_false_calm():
    assert_recovery_convergence(
        {
            "today": {
                "recovery_disclosure": {"has_recovery_attention": True, "blocked_count": 1},
                "waiting_on_summary": "contractor",
            },
            "command_centre": {
                "waiting_on_summary": "contractor",
                "blocked_count": 1,
            },
        }
    )


def test_recovery_convergence_rejects_false_calm():
    with pytest.raises(ValueError):
        assert_recovery_convergence(
            {
                "today": {
                    "recovery_disclosure": {"has_recovery_attention": True, "blocked_count": 0},
                    "stalled_reason": "This job cannot currently move forward because no next step is available.",
                },
            }
        )
