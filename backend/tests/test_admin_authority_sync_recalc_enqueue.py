"""Stream B straggler: admin routes enqueue recalc after standalone sync_requirement_evidence_authority."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from routes import admin as admin_routes


@pytest.mark.asyncio
async def test_enqueue_skipped_when_property_or_client_missing():
    enq = AsyncMock(return_value=True)
    with patch("services.compliance_recalc_queue.enqueue_compliance_recalc", enq):
        await admin_routes._enqueue_recalc_after_standalone_authority_sync(
            property_id="",
            client_id="c1",
            portal_user_id="u1",
            correlation_id="X:1",
        )
        await admin_routes._enqueue_recalc_after_standalone_authority_sync(
            property_id="p1",
            client_id="",
            portal_user_id="u1",
            correlation_id="X:2",
        )
    enq.assert_not_called()


@pytest.mark.asyncio
async def test_admin_unlink_requirement_enqueues_after_authority_sync():
    user = {"portal_user_id": "adm1", "client_id": "cliX"}
    doc = {
        "document_id": "d1",
        "client_id": "c1",
        "property_id": "p1",
        "requirement_id": "r_old",
    }
    db = MagicMock()
    db.documents.find_one = AsyncMock(return_value=doc)
    db.documents.update_one = AsyncMock()

    enq = AsyncMock(return_value=True)
    sync = AsyncMock()
    audit = AsyncMock()

    with patch.object(admin_routes.database, "get_db", return_value=db):
        with patch.object(admin_routes, "admin_route_guard", AsyncMock(return_value=user)):
            with patch(
                "services.requirement_evidence_authority.sync_requirement_evidence_authority",
                sync,
            ):
                with patch("services.compliance_recalc_queue.enqueue_compliance_recalc", enq):
                    with patch.object(admin_routes, "create_audit_log", audit):
                        out = await admin_routes.admin_unlink_document_requirement(
                            request=MagicMock(),
                            document_id="d1",
                        )

    assert out["message"] == "Requirement unlinked"
    sync.assert_awaited_once()
    enq.assert_awaited_once()
    kw = enq.await_args.kwargs
    assert kw["property_id"] == "p1"
    assert kw["client_id"] == "c1"
    assert kw["correlation_id"] == "AUTHORITY_SYNC:ADMIN_UNLINK_REQUIREMENT:d1"
