"""
Guards contractor assignment email: only after client confirm (or allow_direct), never on recommendation alone.
Uses mocked DB + notification_orchestrator (no Mongo, no real sends).
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from database import database as db_singleton
from services.work_order_assignment_constants import (
    ASSIGNMENT_ROUTING_ASSIGNED,
    ASSIGNMENT_ROUTING_PENDING_CLIENT_CONFIRMATION,
    ASSIGNMENT_ROUTING_UNASSIGNED,
)
from services import maintenance_service


def _mock_db_for_generate():
    db = MagicMock()
    wo = {
        "work_order_id": "wo-r1",
        "client_id": "cli-1",
        "property_id": "prop-1",
        "status": "OPEN",
        "description": "Leak under sink",
        "contractor_id": None,
        "severity": "medium",
        "sla_breached_at": None,
        "sla_breach_risk_at": None,
    }
    db.work_orders.find_one = AsyncMock(return_value=dict(wo))
    db.work_orders.update_one = AsyncMock()
    db.properties.find_one = AsyncMock(
        return_value={"address_line_1": "1 Test St", "city": "London", "postcode": "SW1A 1AA"}
    )
    cur = MagicMock()
    cur.to_list = AsyncMock(return_value=[{"auth_email": "owner@test.com", "portal_user_id": "pu-1"}])
    db.portal_users.find = MagicMock(return_value=cur)
    return db, wo


def _mock_db_for_confirm_and_assign():
    db = MagicMock()
    pending_wo = {
        "work_order_id": "wo-c1",
        "client_id": "cli-1",
        "property_id": "prop-1",
        "status": "OPEN",
        "description": "Electrical fault",
        "contractor_id": None,
        "requires_client_assignment_confirmation": True,
        "assignment_routing_state": ASSIGNMENT_ROUTING_PENDING_CLIENT_CONFIRMATION,
        "recommended_contractor_id": "ctr-rec-1",
        "sla_complete_by": "2030-01-01T00:00:00+00:00",
    }
    assigned_wo = {
        **pending_wo,
        "contractor_id": "ctr-rec-1",
        "status": "ASSIGNED",
        "assigned_at": "2030-01-02T00:00:00+00:00",
        "assignment_routing_state": "ASSIGNED",
        "recommended_contractor_id": None,
    }

    find_one_calls = []

    async def find_one_side_effect(*args, **kwargs):
        find_one_calls.append((args, kwargs))
        n = len(find_one_calls)
        # routing _load_wo_client
        if n == 1:
            return dict(pending_wo)
        # maintenance prev_snapshot
        if n == 2:
            return {
                "status": pending_wo["status"],
                "client_id": pending_wo["client_id"],
                "property_id": pending_wo["property_id"],
                "requires_client_assignment_confirmation": True,
            }
        # maintenance existing status check (OPEN -> ASSIGNED)
        if n == 3:
            return {"status": "OPEN"}
        return None

    db.work_orders.find_one = AsyncMock(side_effect=find_one_side_effect)
    db.work_orders.find_one_and_update = AsyncMock(return_value=dict(assigned_wo))
    db.work_orders.update_one = AsyncMock()
    db.contractor_assignments.insert_one = AsyncMock()
    db.contractor_job_tokens.insert_one = AsyncMock()
    db.contractors.find_one = AsyncMock(return_value={"email": "contractor@test.com"})
    db.properties.find_one = AsyncMock(
        return_value={"address_line_1": "9 High St", "city": "Manchester", "postcode": "M1 1AA"}
    )
    return db, find_one_calls


def test_generate_recommendation_sends_no_contractor_assigned_email():
    from services import work_order_contractor_routing_service as routing

    async def _run():
        mock_db, _ = _mock_db_for_generate()
        send_mock = AsyncMock(return_value={"ok": True})

        ranked = {
            "contractors": [
                {
                    "contractor_id": "ctr-1",
                    "name": "Acme Repairs",
                    "company_name": "Acme Ltd",
                    "reasons": ["trade match", "area"],
                }
            ],
            "routing": {"assignment_urgency": "normal", "routing_messages": []},
        }

        with (
            patch.object(db_singleton, "get_db", return_value=mock_db),
            patch(
                "services.work_order_contractor_routing_service.contractor_service.recommend_contractors_for_work_order",
                new_callable=AsyncMock,
                return_value=ranked,
            ),
            patch(
                "services.notification_orchestrator.notification_orchestrator.send",
                send_mock,
            ),
            patch(
                "services.order_service.create_in_app_notification",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "services.work_order_contractor_routing_service.create_audit_log",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            return await routing.generate_and_notify_recommendation(
                "wo-r1", "cli-1", actor_portal_user_id="pu-1"
            ), send_mock

    out, send_mock = asyncio.run(_run())

    assert out.get("ok") is True
    assert out.get("recommended_contractor_id") == "ctr-1"
    assert send_mock.await_count >= 1
    for c in send_mock.await_args_list:
        kwargs = c.kwargs
        assert kwargs.get("template_key") != "CONTRACTOR_ASSIGNED"
        assert kwargs.get("event_type") != "CONTRACTOR_ASSIGNED"


def test_confirm_recommendation_sends_contractor_assigned_email():
    from services import work_order_contractor_routing_service as routing

    async def _run():
        mock_db, _ = _mock_db_for_confirm_and_assign()
        send_mock = AsyncMock(return_value={"ok": True})

        with (
            patch.object(db_singleton, "get_db", return_value=mock_db),
            patch(
                "services.contractor_service.validate_contractor_for_work_order_assignment",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "services.notification_orchestrator.notification_orchestrator.send",
                send_mock,
            ),
            patch("utils.audit.create_audit_log", new_callable=AsyncMock, return_value=None),
            patch(
                "services.work_order_contractor_routing_service.create_audit_log",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch("services.webhook_service.fire_work_order_status_changed", new_callable=AsyncMock),
            patch("auth.generate_secure_token", return_value="fixed-test-token-32chars-min____"),
            patch("utils.public_app_url.get_frontend_base_url", return_value="https://app.example.com"),
        ):
            out = await routing.confirm_recommended_contractor(
                "wo-c1", "cli-1", actor_portal_user_id="pu-1"
            )
        return out, send_mock

    out, send_mock = asyncio.run(_run())

    assert out.get("ok") is True
    assign_sends = [
        c
        for c in send_mock.await_args_list
        if c.kwargs.get("template_key") == "CONTRACTOR_ASSIGNED"
    ]
    assert len(assign_sends) == 1
    assert assign_sends[0].kwargs.get("idempotency_key") == "contractor_assign_wo-c1_ctr-rec-1"
    assert assign_sends[0].kwargs.get("context", {}).get("recipient") == "contractor@test.com"


def test_update_work_order_blocks_contractor_without_allow_direct_when_confirmation_required():
    async def _run():
        mock_db = MagicMock()
        mock_db.work_orders.find_one = AsyncMock(
            return_value={
                "status": "OPEN",
                "client_id": "cli-1",
                "property_id": "prop-1",
                "requires_client_assignment_confirmation": True,
            }
        )

        with (
            patch.object(db_singleton, "get_db", return_value=mock_db),
            patch(
                "services.contractor_service.validate_contractor_for_work_order_assignment",
                new_callable=AsyncMock,
            ) as val_mock,
        ):
            with pytest.raises(ValueError, match="client confirmation"):
                await maintenance_service.update_work_order(
                    "wo-x1",
                    contractor_id="ctr-1",
                    assigned_by="user@test.com",
                )
        return val_mock

    val_mock = asyncio.run(_run())
    val_mock.assert_not_called()


def test_update_work_order_allows_assign_when_allow_direct_true():
    async def _run():
        mock_db = MagicMock()
        assigned = {
            "work_order_id": "wo-x2",
            "status": "ASSIGNED",
            "client_id": "cli-1",
            "property_id": "prop-1",
            "contractor_id": "ctr-1",
            "description": "Job",
            "sla_complete_by": None,
        }

        async def find_one_filter(*args, **kwargs):
            proj = kwargs.get("projection") or (args[1] if len(args) > 1 else None)
            if proj == {"status": 1}:
                return {"status": "OPEN"}
            return {
                "status": "OPEN",
                "client_id": "cli-1",
                "property_id": "prop-1",
                "requires_client_assignment_confirmation": True,
            }

        mock_db.work_orders.find_one = AsyncMock(side_effect=find_one_filter)
        mock_db.work_orders.find_one_and_update = AsyncMock(return_value=dict(assigned))
        mock_db.contractor_assignments.insert_one = AsyncMock()
        mock_db.contractor_job_tokens.insert_one = AsyncMock()
        mock_db.contractors.find_one = AsyncMock(return_value={"email": "c@example.com"})
        mock_db.properties.find_one = AsyncMock(return_value=None)

        send_mock = AsyncMock(return_value={"ok": True})

        with (
            patch.object(db_singleton, "get_db", return_value=mock_db),
            patch(
                "services.contractor_service.validate_contractor_for_work_order_assignment",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "services.notification_orchestrator.notification_orchestrator.send",
                send_mock,
            ),
            patch("utils.audit.create_audit_log", new_callable=AsyncMock, return_value=None),
            patch("services.webhook_service.fire_work_order_status_changed", new_callable=AsyncMock),
            patch("auth.generate_secure_token", return_value="tok-fixed________________________"),
            patch("utils.public_app_url.get_frontend_base_url", return_value="https://app.example.com"),
        ):
            doc = await maintenance_service.update_work_order(
                "wo-x2",
                contractor_id="ctr-1",
                assigned_by="admin@test.com",
                allow_direct_contractor_assignment=True,
            )
        return doc, send_mock

    doc, send_mock = asyncio.run(_run())

    assert doc.get("contractor_id") == "ctr-1"
    assert any(
        c.kwargs.get("template_key") == "CONTRACTOR_ASSIGNED" for c in send_mock.await_args_list
    )


def test_update_work_order_sends_quote_required_email_when_price_awaiting_quote():
    async def _run():
        mock_db = MagicMock()
        assigned = {
            "work_order_id": "wo-quote-1",
            "status": "ASSIGNED",
            "client_id": "cli-1",
            "property_id": "prop-1",
            "contractor_id": "ctr-q",
            "description": "Quoted repair",
            "work_order_kind": "MAINTENANCE",
            "price_status": "AWAITING_QUOTE",
            "jurisdiction": "England",
            "sla_complete_by": None,
        }

        async def find_one_filter(*args, **kwargs):
            proj = kwargs.get("projection") or (args[1] if len(args) > 1 else None)
            if proj == {"status": 1}:
                return {"status": "OPEN"}
            return {
                "status": "OPEN",
                "client_id": "cli-1",
                "property_id": "prop-1",
                "requires_client_assignment_confirmation": True,
            }

        mock_db.work_orders.find_one = AsyncMock(side_effect=find_one_filter)
        mock_db.work_orders.find_one_and_update = AsyncMock(return_value=dict(assigned))
        mock_db.contractor_assignments.insert_one = AsyncMock()
        mock_db.contractor_job_tokens.insert_one = AsyncMock()
        mock_db.contractors.find_one = AsyncMock(
            return_value={"email": "q@example.com", "name": "Pat Contractor", "company_name": "PC Ltd"}
        )
        mock_db.properties.find_one = AsyncMock(
            return_value={"address_line_1": "9 Quote St", "city": "York", "postcode": "YO1 1AA"}
        )

        send_mock = AsyncMock(return_value={"ok": True})

        with (
            patch.object(db_singleton, "get_db", return_value=mock_db),
            patch(
                "services.contractor_service.validate_contractor_for_work_order_assignment",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "services.notification_orchestrator.notification_orchestrator.send",
                send_mock,
            ),
            patch("utils.audit.create_audit_log", new_callable=AsyncMock, return_value=None),
            patch("services.webhook_service.fire_work_order_status_changed", new_callable=AsyncMock),
            patch(
                "services.maintenance_service.generate_secure_token",
                return_value="quote-tok-32chars-minimum______",
            ),
            patch("utils.public_app_url.get_frontend_base_url", return_value="https://app.example.com"),
        ):
            await maintenance_service.update_work_order(
                "wo-quote-1",
                contractor_id="ctr-q",
                assigned_by="admin@test.com",
                allow_direct_contractor_assignment=True,
            )
        return send_mock

    send_mock = asyncio.run(_run())

    quote_sends = [
        c
        for c in send_mock.await_args_list
        if c.kwargs.get("template_key") == "CONTRACTOR_JOB_ASSIGNMENT_QUOTE_REQUIRED"
    ]
    assert len(quote_sends) == 1
    assert quote_sends[0].kwargs.get("idempotency_key") == "contractor_quote_required:wo-quote-1:ctr-q"
    ctx = quote_sends[0].kwargs.get("context") or {}
    assert ctx.get("recipient") == "q@example.com"
    assert ctx.get("job_kind") == "MAINTENANCE"
    assert ctx.get("jurisdiction") == "England"
    assert ctx.get("contractor_name") == "Pat Contractor"
    assert "https://app.example.com/job?token=quote-tok-32chars-minimum______" == str(ctx.get("secure_job_link") or "")
    assert not any(c.kwargs.get("template_key") == "CONTRACTOR_ASSIGNED" for c in send_mock.await_args_list)


def test_scenario_c_chained_request_contractor_then_confirm_assigns_and_notifies():
    """
    Scenario C (enterprise): request recommendation updates routing state; confirm assigns contractor
    and emits CONTRACTOR_ASSIGNED. Uses a mutable in-memory work order document (no real Mongo).
    """
    from services import work_order_contractor_routing_service as routing

    woid = "wo-scenario-c"
    wo_live = {
        "work_order_id": woid,
        "client_id": "cli-1",
        "property_id": "prop-1",
        "status": "OPEN",
        "description": "Scenario C maintenance job",
        "contractor_id": None,
        "requires_client_assignment_confirmation": True,
        "work_order_kind": "MAINTENANCE",
        "assignment_routing_state": ASSIGNMENT_ROUTING_UNASSIGNED,
        "evidence_keys": [],
        "sla_breached_at": None,
        "sla_breach_risk_at": None,
        "severity": "medium",
    }

    async def find_one(*args, **kwargs):
        filt = args[0] if args else {}
        if filt.get("work_order_id") != woid:
            return None
        proj = args[1] if len(args) > 1 else None
        if proj and isinstance(proj, dict):
            return {k: wo_live.get(k) for k, v in proj.items() if k != "_id" and v}
        return dict(wo_live)

    async def update_one(filt, update, *_a, **_kw):
        if filt.get("work_order_id") != woid:
            return None
        if "$set" in update:
            wo_live.update(update["$set"])
        return {"modified_count": 1}

    async def find_one_and_update(filt, update, **_kwargs):
        if filt.get("work_order_id") != woid:
            return None
        if "$set" in update:
            wo_live.update(update["$set"])
        if "$addToSet" in update:
            keys = (update["$addToSet"] or {}).get("evidence_keys", {})
            if isinstance(keys, dict) and "$each" in keys:
                for k in keys["$each"]:
                    if k and k not in wo_live.setdefault("evidence_keys", []):
                        wo_live["evidence_keys"].append(k)
        out = dict(wo_live)
        out.pop("_id", None)
        return out

    async def _run():
        mock_db = MagicMock()
        mock_db.work_orders.find_one = AsyncMock(side_effect=find_one)
        mock_db.work_orders.update_one = AsyncMock(side_effect=update_one)
        mock_db.work_orders.find_one_and_update = AsyncMock(side_effect=find_one_and_update)
        mock_db.contractor_assignments.insert_one = AsyncMock()
        mock_db.contractor_job_tokens.insert_one = AsyncMock()
        mock_db.contractors.find_one = AsyncMock(return_value={"email": "contractor-scen-c@test.com"})
        mock_db.properties.find_one = AsyncMock(
            return_value={"address_line_1": "1 Chain Rd", "city": "Leeds", "postcode": "LS1 1AA"}
        )
        cur = MagicMock()
        cur.to_list = AsyncMock(return_value=[{"auth_email": "owner@test.com", "portal_user_id": "pu-scen-c"}])
        mock_db.portal_users.find = MagicMock(return_value=cur)

        ranked = {
            "contractors": [
                {
                    "contractor_id": "ctr-scen-c",
                    "name": "Scenario C Ltd",
                    "company_name": "Scenario C Ltd",
                    "reasons": ["Eligible for work order"],
                }
            ],
            "routing": {"assignment_urgency": "normal", "routing_messages": []},
        }
        send_mock = AsyncMock(return_value={"ok": True})

        with (
            patch.object(db_singleton, "get_db", return_value=mock_db),
            patch(
                "services.work_order_contractor_routing_service.contractor_service.recommend_contractors_for_work_order",
                new_callable=AsyncMock,
                return_value=ranked,
            ),
            patch(
                "services.contractor_service.validate_contractor_for_work_order_assignment",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch("services.notification_orchestrator.notification_orchestrator.send", send_mock),
            patch("utils.audit.create_audit_log", new_callable=AsyncMock, return_value=None),
            patch(
                "services.work_order_contractor_routing_service.create_audit_log",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch("services.order_service.create_in_app_notification", new_callable=AsyncMock, return_value=None),
            patch("services.webhook_service.fire_work_order_status_changed", new_callable=AsyncMock),
            patch("auth.generate_secure_token", return_value="scen-c-token-32chars-min___________"),
            patch("utils.public_app_url.get_frontend_base_url", return_value="https://app.example.com"),
        ):
            gen_out = await routing.generate_and_notify_recommendation(
                woid, "cli-1", actor_portal_user_id="pu-scen-c"
            )
            assert gen_out.get("ok") is True
            assert wo_live.get("assignment_routing_state") == ASSIGNMENT_ROUTING_PENDING_CLIENT_CONFIRMATION
            assert wo_live.get("recommended_contractor_id") == "ctr-scen-c"

            pre_confirm_sends = len(send_mock.await_args_list)

            conf_out = await routing.confirm_recommended_contractor(
                woid, "cli-1", actor_portal_user_id="pu-scen-c"
            )
            assert conf_out.get("ok") is True
            assert wo_live.get("contractor_id") == "ctr-scen-c"
            assert wo_live.get("assignment_routing_state") == ASSIGNMENT_ROUTING_ASSIGNED

        assign_sends = [
            c
            for c in send_mock.await_args_list
            if c.kwargs.get("template_key") == "CONTRACTOR_ASSIGNED"
        ]
        assert len(assign_sends) == 1
        assert assign_sends[0].kwargs.get("context", {}).get("recipient") == "contractor-scen-c@test.com"
        assert pre_confirm_sends >= 1
        assert len(send_mock.await_args_list) > pre_confirm_sends

    asyncio.run(_run())
