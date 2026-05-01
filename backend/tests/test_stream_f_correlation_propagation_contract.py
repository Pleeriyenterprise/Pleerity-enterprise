"""
Stream F Phase 2 — contract: correlation_id in recalculate_and_persist context
reaches score ledger + COMPLIANCE_SCORE_UPDATED audit metadata (existing design).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_recalculate_and_persist_forwards_correlation_id_to_ledger_and_audit() -> None:
    """Guarantees context['correlation_id'] is not dropped before log_score_change / create_audit_log."""
    from models import AuditAction
    from services.compliance_scoring_service import recalculate_and_persist

    db = MagicMock()
    db.properties.find_one = AsyncMock(
        return_value={
            "property_id": "p1",
            "client_id": "c1",
            "compliance_score": 50,
            "compliance_breakdown": {},
            "score_breakdown": [],
        }
    )
    db.properties.update_one = AsyncMock()
    db.property_compliance_score_history.insert_one = AsyncMock()
    db.score_change_log.insert_one = AsyncMock()

    computed = {
        "score": 55,
        "breakdown": {
            "status_score": 55,
            "expiry_score": 80,
            "document_score": 70,
            "overdue_penalty_score": 80,
            "risk_score": 100,
        },
        "weights_version": "v1",
        "score_breakdown": [],
    }

    corr = "STREAM_F_CONTRACT:p1:test"

    with patch("services.compliance_scoring_service.database") as db_mod:
        db_mod.get_db.return_value = db
        with patch(
            "services.compliance_scoring_service.calculate_property_compliance",
            new_callable=AsyncMock,
            return_value=computed,
        ):
            with patch("services.score_ledger_service.log_score_change", new_callable=AsyncMock) as ledger:
                with patch("utils.audit.create_audit_log", new_callable=AsyncMock) as audit:
                    with patch(
                        "services.risk_signal_regen_queue.enqueue_risk_signal_regen",
                        new_callable=AsyncMock,
                    ):
                        await recalculate_and_persist(
                            "p1",
                            "TEST_REASON_STREAM_F",
                            {"id": "u1", "role": "ADMIN"},
                            context={"correlation_id": corr, "skip_risk_regen_enqueue": True},
                        )

    ledger.assert_awaited_once()
    assert ledger.await_args.kwargs.get("correlation_id") == corr

    audit.assert_awaited_once()
    assert audit.await_args.kwargs.get("action") == AuditAction.COMPLIANCE_SCORE_UPDATED
    meta = audit.await_args.kwargs.get("metadata") or {}
    assert meta.get("correlation_id") == corr
    assert meta.get("reason") == "TEST_REASON_STREAM_F"

    db.property_compliance_score_history.insert_one.assert_awaited_once()
    hist_doc = db.property_compliance_score_history.insert_one.await_args.args[0]
    assert hist_doc.get("correlation_id") == corr

    db.score_change_log.insert_one.assert_awaited_once()
    change_doc = db.score_change_log.insert_one.await_args.args[0]
    assert change_doc.get("correlation_id") == corr


@pytest.mark.asyncio
async def test_recalculate_and_persist_omits_correlation_id_on_history_when_context_has_none() -> None:
    """F2-A: do not add correlation_id to Mongo inserts when caller did not supply a non-empty id."""
    from services.compliance_scoring_service import recalculate_and_persist

    db = MagicMock()
    db.properties.find_one = AsyncMock(
        return_value={
            "property_id": "p1",
            "client_id": "c1",
            "compliance_score": 50,
            "compliance_breakdown": {},
            "score_breakdown": [],
        }
    )
    db.properties.update_one = AsyncMock()
    db.property_compliance_score_history.insert_one = AsyncMock()
    db.score_change_log.insert_one = AsyncMock()

    computed = {
        "score": 55,
        "breakdown": {
            "status_score": 55,
            "expiry_score": 80,
            "document_score": 70,
            "overdue_penalty_score": 80,
            "risk_score": 100,
        },
        "weights_version": "v1",
        "score_breakdown": [],
    }

    with patch("services.compliance_scoring_service.database") as db_mod:
        db_mod.get_db.return_value = db
        with patch(
            "services.compliance_scoring_service.calculate_property_compliance",
            new_callable=AsyncMock,
            return_value=computed,
        ):
            with patch("services.score_ledger_service.log_score_change", new_callable=AsyncMock) as ledger:
                with patch("utils.audit.create_audit_log", new_callable=AsyncMock):
                    with patch(
                        "services.risk_signal_regen_queue.enqueue_risk_signal_regen",
                        new_callable=AsyncMock,
                    ):
                        await recalculate_and_persist(
                            "p1",
                            "TEST_REASON_STREAM_F_NO_CID",
                            {"id": "u1", "role": "ADMIN"},
                            context={"skip_risk_regen_enqueue": True},
                        )

    hist_doc = db.property_compliance_score_history.insert_one.await_args.args[0]
    change_doc = db.score_change_log.insert_one.await_args.args[0]
    assert "correlation_id" not in hist_doc
    assert "correlation_id" not in change_doc
    assert ledger.await_args.kwargs.get("correlation_id") is None


@pytest.mark.asyncio
async def test_recalculate_and_persist_does_not_persist_blank_correlation_id() -> None:
    """Whitespace-only correlation_id is treated as absent for history / change_log (no new field)."""
    from services.compliance_scoring_service import recalculate_and_persist

    db = MagicMock()
    db.properties.find_one = AsyncMock(
        return_value={
            "property_id": "p1",
            "client_id": "c1",
            "compliance_score": 50,
            "compliance_breakdown": {},
            "score_breakdown": [],
        }
    )
    db.properties.update_one = AsyncMock()
    db.property_compliance_score_history.insert_one = AsyncMock()
    db.score_change_log.insert_one = AsyncMock()

    computed = {
        "score": 55,
        "breakdown": {
            "status_score": 55,
            "expiry_score": 80,
            "document_score": 70,
            "overdue_penalty_score": 80,
            "risk_score": 100,
        },
        "weights_version": "v1",
        "score_breakdown": [],
    }

    with patch("services.compliance_scoring_service.database") as db_mod:
        db_mod.get_db.return_value = db
        with patch(
            "services.compliance_scoring_service.calculate_property_compliance",
            new_callable=AsyncMock,
            return_value=computed,
        ):
            with patch("services.score_ledger_service.log_score_change", new_callable=AsyncMock):
                with patch("utils.audit.create_audit_log", new_callable=AsyncMock):
                    with patch(
                        "services.risk_signal_regen_queue.enqueue_risk_signal_regen",
                        new_callable=AsyncMock,
                    ):
                        await recalculate_and_persist(
                            "p1",
                            "TEST_REASON_BLANK_CID",
                            {"id": "u1", "role": "ADMIN"},
                            context={
                                "correlation_id": "   ",
                                "skip_risk_regen_enqueue": True,
                            },
                        )

    hist_doc = db.property_compliance_score_history.insert_one.await_args.args[0]
    change_doc = db.score_change_log.insert_one.await_args.args[0]
    assert "correlation_id" not in hist_doc
    assert "correlation_id" not in change_doc
