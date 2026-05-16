"""Canonical requirement action fan-out after guided evidence mutations."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.requirement_action_orchestration import (
    enrich_single_requirement_for_client,
    propagate_requirement_evidence_outcome,
)


@pytest.mark.asyncio
async def test_propagate_requirement_evidence_outcome_returns_enriched_requirement():
    db = MagicMock()
    enriched_row = {
        "requirement_id": "r1",
        "client_lifecycle_state": "SATISFIED_UNVERIFIED",
        "client_lifecycle_label": "Evidence recorded",
    }

    with patch(
        "services.requirement_action_orchestration.authority_sync_with_transition_observability",
        new_callable=AsyncMock,
    ) as sync_mock:
        with patch(
            "services.requirement_action_orchestration.enqueue_compliance_recalc_with_fanout",
            new_callable=AsyncMock,
        ) as enq_mock:
            with patch(
                "services.requirement_action_orchestration.enrich_single_requirement_for_client",
                new_callable=AsyncMock,
                return_value=enriched_row,
            ):
                out = await propagate_requirement_evidence_outcome(
                    db,
                    requirement_id="r1",
                    property_id="p1",
                    client_id="c1",
                    actor_user_id="u1",
                    correlation_base="TEST:guided",
                    transition_origin="test.propagate",
                )

    sync_mock.assert_awaited_once()
    enq_mock.assert_awaited_once()
    assert out["ok"] is True
    assert out["workflow_complete"] is True
    assert out["authority_synced"] is True
    assert out["requirement"]["client_lifecycle_state"] == "SATISFIED_UNVERIFIED"


@pytest.mark.asyncio
async def test_propagate_partial_when_authority_sync_fails():
    db = MagicMock()
    with patch(
        "services.requirement_action_orchestration.authority_sync_with_transition_observability",
        new_callable=AsyncMock,
        side_effect=RuntimeError("sync failed"),
    ):
        with patch(
            "services.requirement_action_orchestration.enqueue_compliance_recalc_with_fanout",
            new_callable=AsyncMock,
        ) as enq_mock:
            with patch(
                "services.requirement_action_orchestration.enrich_single_requirement_for_client",
                new_callable=AsyncMock,
                return_value=None,
            ):
                out = await propagate_requirement_evidence_outcome(
                    db,
                    requirement_id="r1",
                    property_id="p1",
                    client_id="c1",
                    actor_user_id="u1",
                    correlation_base="TEST:fail",
                    transition_origin="test.propagate_fail",
                )

    enq_mock.assert_not_awaited()
    assert out["workflow_complete"] is False
    assert out["authority_synced"] is False
    assert "could not be refreshed" in out["message"].lower()


@pytest.mark.asyncio
async def test_enrich_single_requirement_for_client_delegates():
    db = MagicMock()
    db.requirements.find_one = AsyncMock(return_value={"requirement_id": "r9", "client_id": "c9"})
    with patch(
        "services.requirement_action_orchestration.enrich_requirements_for_client",
        new_callable=AsyncMock,
        return_value=([{"requirement_id": "r9", "client_lifecycle_state": "VERIFIED"}], {}),
    ):
        row = await enrich_single_requirement_for_client(db, client_id="c9", requirement_id="r9")
    assert row["client_lifecycle_state"] == "VERIFIED"
