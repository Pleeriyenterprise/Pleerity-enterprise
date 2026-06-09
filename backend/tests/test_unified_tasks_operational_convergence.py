"""Unified tasks operational residue convergence — suppression and lineage dedupe."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services import unified_tasks_operational_convergence as conv
from services.risk_signal_service import RISK_TYPE_COMPLIANCE_CHURN


def _issue_task(issue_id: str, *, risk_signal_id: str = "", gap_key: str = "", property_id: str = "p1"):
    meta = {
        "related_issue_id": issue_id,
        "action_type": "open_operational_issue",
    }
    if risk_signal_id:
        meta["related_risk_signal_id"] = risk_signal_id
    if gap_key:
        meta["operational_root_key"] = gap_key
        meta["gap_key"] = gap_key
        meta["issue_created_from"] = "compliance"
        meta["issue_triggering_rule"] = "compliance_gap:MISSING_EVIDENCE"
    return {
        "id": f"issue:{issue_id}",
        "source_type": "issue",
        "source_entity_id": issue_id,
        "property_id": property_id,
        "section": "in_progress",
        "impact_score": 45,
        "metadata": meta,
    }


def _wo_task(wo_id: str, *, risk_signal_id: str = "", property_id: str = "p1"):
    return {
        "id": f"work_order:{wo_id}",
        "source_type": "work_order",
        "source_entity_id": wo_id,
        "property_id": property_id,
        "section": "in_progress",
        "impact_score": 80,
        "metadata": {
            "related_work_order_id": wo_id,
            "related_risk_signal_id": risk_signal_id,
            "action_type": "open_work_order",
        },
    }


def _risk_task(signal_id: str, property_id: str = "p1"):
    return {
        "id": f"risk_signal:{signal_id}",
        "source_type": "risk_signal",
        "source_entity_id": signal_id,
        "property_id": property_id,
        "section": "urgent",
        "impact_score": 70,
        "metadata": {"related_risk_signal_id": signal_id, "action_type": "risk_signal"},
    }


def test_lineage_dedupe_key_risk_signal():
    t = _risk_task("rs_abc")
    assert conv.lineage_dedupe_key(t) == "risk_signal:rs_abc"


def test_dedupe_keeps_work_order_over_issue_for_same_risk_signal():
    rs = "rs_churn"
    issue = _issue_task("iss_1", risk_signal_id=rs)
    wo = _wo_task("wo_1", risk_signal_id=rs)
    risk = _risk_task(rs)
    out = conv.dedupe_operational_lineage_tasks([issue, risk, wo])
    assert len(out) == 1
    assert out[0]["source_type"] == "work_order"


def test_dedupe_collapses_duplicate_risk_linked_issues():
    a = _issue_task("iss_a", risk_signal_id="rs_dup")
    b = _issue_task("iss_b", risk_signal_id="rs_dup")
    out = conv.dedupe_operational_lineage_tasks([a, b])
    assert len(out) == 1


@pytest.mark.asyncio
async def test_suppress_stale_risk_linked_issue_when_compliance_recovered():
    client_id = "c1"
    property_id = "p1"
    issue_id = "iss_stale"
    tasks = [_issue_task(issue_id, risk_signal_id="rs_1", property_id=property_id)]

    db = MagicMock()
    db.maintenance_issues.find = MagicMock(
        return_value=MagicMock(
            to_list=AsyncMock(
                return_value=[
                    {
                        "issue_id": issue_id,
                        "property_id": property_id,
                        "risk_signal_id": "rs_1",
                        "status": "open",
                        "description": f"{RISK_TYPE_COMPLIANCE_CHURN}: follow up",
                    }
                ]
            )
        )
    )
    db.clients.find_one = AsyncMock(return_value={"default_jurisdiction": "england"})
    db.properties.find = MagicMock(
        return_value=MagicMock(
            to_list=AsyncMock(
                return_value=[
                    {
                        "property_id": property_id,
                        "jurisdiction": "england",
                    }
                ]
            )
        )
    )
    db.requirements.find = MagicMock(
        return_value=MagicMock(
            to_list=AsyncMock(
                return_value=[
                    {
                        "requirement_id": "req_1",
                        "property_id": property_id,
                        "client_id": client_id,
                        "status": "COMPLIANT",
                        "semantic_state": "SATISFIED",
                    }
                ]
            )
        )
    )
    db.work_orders.find_one = AsyncMock(return_value=None)

    with patch(
        "services.unified_tasks_operational_convergence.project_requirement_row_client_runtime",
        side_effect=lambda r: {**r, "requirement_id": r.get("requirement_id"), "property_id": property_id},
    ), patch(
        "services.unified_tasks_operational_convergence.requirement_has_active_negative_actionability",
        return_value=False,
    ), patch(
        "services.requirement_satisfaction_service.is_requirement_satisfied",
        return_value=True,
    ):
        out = await conv.suppress_stale_operational_residue_tasks(
            client_id=client_id,
            tasks=tasks,
            db=db,
        )
    assert out == []


@pytest.mark.asyncio
async def test_compliance_churn_rule_decays_when_obligations_recovered():
    from services.risk_signal_service import _rule_compliance_churn

    mock_db = MagicMock()
    mock_db.work_orders.count_documents = AsyncMock(return_value=0)
    mock_db.maintenance_issues.count_documents = AsyncMock(return_value=0)
    metrics = {
        "max_bad_transitions_single_key": 4,
        "obligation_keys_with_repeat_bad": 2,
        "recovery_cycles": 1,
        "negative_activity_events": 0,
    }
    with patch("services.risk_signal_service._temporal_churn_metrics", new_callable=AsyncMock, return_value=metrics):
        recovered = await _rule_compliance_churn(
            mock_db, "p1", "c1", [{"status": "COMPLIANT", "requirement_id": "r1"}]
        )
        still_active = await _rule_compliance_churn(
            mock_db,
            "p1",
            "c1",
            [{"status": "MISSING", "requirement_id": "r2"}],
        )
    assert recovered == []
    assert still_active


def test_customer_language_risk_issue_summary():
    from services.customer_operational_language_service import derive_customer_safe_issue_summary

    summary = derive_customer_safe_issue_summary(
        {
            "risk_signal_id": "rs_1",
            "description": "Compliance Churn Risk: Upload missing evidence",
        }
    )
    assert summary == "Compliance follow-up still unresolved"
    assert "Compliance Churn Risk" not in summary
