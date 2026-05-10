"""L-009c: propagation_notice on Evidence Review V2 lifecycle endpoints (after authority + recalc fanout)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request

from database import database as db_singleton
from services.client_propagation_notice import (
    NOTICE_AUTHORITY_SYNC_DEFERRED,
    NOTICE_RECALC_ENQUEUE_DEFERRED,
)


@pytest.mark.asyncio
async def test_start_evidence_review_propagation_notice_when_authority_deferred():
    from routes.evidence_review import ReviewNotesBody, start_evidence_review

    doc = {
        "document_id": "d-lc-1",
        "client_id": "c1",
        "property_id": "p1",
        "requirement_id": "r1",
        "evidence_review_state": "NEEDS_INFORMATION",
    }
    mock_db = MagicMock()
    mock_db.documents.find_one = AsyncMock(return_value=doc)

    async def auth_mutate(*_a, **kwargs):
        fo = kwargs.get("transition_fanout")
        if isinstance(fo, dict):
            fo["rst_core_backbone_activation"] = {
                "permitted": False,
                "activation_reason": "unit_test",
            }

    request = MagicMock(spec=Request)
    body = ReviewNotesBody(notes="starting", correlation_id="corr-start-1")
    admin_user = {"portal_user_id": "adm1"}

    with (
        patch("routes.evidence_review.is_feature_evidence_review_v2", return_value=True),
        patch("routes.evidence_review.admin_route_guard", new_callable=AsyncMock, return_value=admin_user),
        patch.object(db_singleton, "get_db", return_value=mock_db),
        patch("routes.evidence_review.transition_review_fields", new_callable=AsyncMock),
        patch(
            "routes.evidence_review.authority_sync_with_transition_observability",
            new_callable=AsyncMock,
            side_effect=auth_mutate,
        ),
    ):
        out = await start_evidence_review(request, "d-lc-1", body)

    assert out.get("message") == "Review started"
    assert (out.get("propagation_notice") or {}).get("code") == NOTICE_AUTHORITY_SYNC_DEFERRED


@pytest.mark.asyncio
async def test_reject_evidence_review_propagation_notice_after_recalc_fanout():
    """Notice is built after _sync_prop_recalc so enqueue-side backbone skip is visible."""
    from routes.evidence_review import RejectBody, reject_evidence_review

    doc = {
        "document_id": "d-lc-2",
        "client_id": "c1",
        "property_id": "p1",
        "requirement_id": "r1",
    }
    mock_db = MagicMock()
    mock_db.documents.find_one = AsyncMock(return_value=doc)

    async def auth_ok(*_a, **kwargs):
        fo = kwargs.get("transition_fanout")
        if isinstance(fo, dict):
            fo["rst_core_backbone_activation"] = {"permitted": True}
            fo["transition_id"] = "t-test-reject"

    async def enqueue_mutate(transition_fanout, **_kwargs):
        if isinstance(transition_fanout, dict):
            transition_fanout.setdefault("downstream_trigger_targets", []).append(
                {
                    "downstream_target": "compliance_recalc_queue.enqueue_compliance_recalc",
                    "propagation_stage": "post_review_reject:rst_core_backbone_blocked_skip_enqueue",
                }
            )

    request = MagicMock(spec=Request)
    body = RejectBody(notes="rejecting for unit test", correlation_id="corr-rej-1")
    admin_user = {"portal_user_id": "adm1"}

    with (
        patch("routes.evidence_review.is_feature_evidence_review_v2", return_value=True),
        patch("routes.evidence_review.admin_route_guard", new_callable=AsyncMock, return_value=admin_user),
        patch.object(db_singleton, "get_db", return_value=mock_db),
        patch("routes.evidence_review.transition_review_fields", new_callable=AsyncMock),
        patch(
            "routes.evidence_review.authority_sync_with_transition_observability",
            new_callable=AsyncMock,
            side_effect=auth_ok,
        ),
        patch("routes.evidence_review.provisioning_service._update_property_compliance", new_callable=AsyncMock),
        patch(
            "routes.evidence_review.enqueue_compliance_recalc_with_fanout",
            new_callable=AsyncMock,
            side_effect=enqueue_mutate,
        ),
    ):
        out = await reject_evidence_review(request, "d-lc-2", body)

    assert out.get("message") == "Evidence rejected"
    assert (out.get("propagation_notice") or {}).get("code") == NOTICE_RECALC_ENQUEUE_DEFERRED
