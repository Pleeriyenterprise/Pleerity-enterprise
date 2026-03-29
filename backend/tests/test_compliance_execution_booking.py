"""Compliance execution: requirement normalization, capability gate, recommendation scoring."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from database import database as db_singleton
from services.compliance_contractor_capability import contractor_qualifies_for_requirement
from services.contractor_recommendation import recommend_contractors, _is_compliance_work_order
from services.contractor_service import contractor_passes_work_order_execution_gate
from services.requirement_code_registry import normalize_requirement_code, normalize_requirement_code_strict
from services.work_order_execution_constants import (
    WORK_ORDER_KIND_COMPLIANCE,
    WORK_ORDER_KIND_MAINTENANCE,
)


def test_normalize_requirement_code_maps_legacy():
    assert normalize_requirement_code("GAS_SAFETY") == "gas_safety"
    assert normalize_requirement_code("cp12") == "gas_safety"
    assert normalize_requirement_code("fire_alarm") == "fire_detection"
    assert normalize_requirement_code("EICR") == "eicr"


def test_normalize_strict_rejects_unknown():
    canon, err = normalize_requirement_code_strict("not_a_real_requirement_xyz")
    assert canon is None
    assert err is not None


def test_contractor_passes_compliance_gate():
    wo_c = {"work_order_kind": WORK_ORDER_KIND_COMPLIANCE, "requirement_code": "gas_safety"}
    c_ok = {
        "execution_capabilities": "both",
        "supported_requirement_codes": ["gas_safety"],
        "trade_types": ["heating"],
        "credentials": [],
    }
    assert contractor_passes_work_order_execution_gate(c_ok, wo_c) is True
    c_maint_only = {"execution_capabilities": "maintenance", "trade_types": ["heating"]}
    assert contractor_passes_work_order_execution_gate(c_maint_only, wo_c) is False


def test_compliance_only_excluded_from_maintenance_recommendation_pool():
    wo_m = {"work_order_kind": WORK_ORDER_KIND_MAINTENANCE, "category": "plumbing", "recommended_contractor_type": "plumber"}
    c_comp_only = {
        "contractor_id": "x1",
        "status": "active",
        "trade_types": ["plumbing"],
        "credentials": [],
        "execution_capabilities": "compliance",
    }
    prop = {"postcode": "M1 1AA"}
    r = recommend_contractors(wo_m, prop, [c_comp_only], eligible_only=False)
    assert r["total"] == 0


def test_compliance_work_order_scoring_uses_requirement_match():
    wo_c = {
        "work_order_kind": WORK_ORDER_KIND_COMPLIANCE,
        "requirement_code": "eicr",
        "work_order_id": "wo-c",
    }
    c1 = {
        "contractor_id": "e1",
        "status": "active",
        "trade_types": ["electrical"],
        "credentials": ["eicr"],
        "execution_capabilities": "compliance",
        "supported_requirement_codes": ["eicr"],
        "verified_execution_capabilities": "compliance",
        "verified_supported_requirement_codes": ["eicr"],
    }
    prop = {"postcode": "SW1A 1AA"}
    r = recommend_contractors(wo_c, prop, [c1], eligible_only=False)
    assert r["total"] == 1
    top = r["contractors"][0]
    assert top["score_breakdown"].get("compliance_requirement_match", 0) > 0
    assert top["score_breakdown"].get("trade_match") == 0


def test_is_compliance_work_order():
    assert _is_compliance_work_order({"work_order_kind": "COMPLIANCE"}) is True
    assert _is_compliance_work_order({"work_order_kind": "MAINTENANCE"}) is False


def test_contractor_qualifies_via_credentials():
    c = {"supported_requirement_codes": [], "trade_types": ["electrical"], "credentials": ["niceic", "eicr"]}
    assert contractor_qualifies_for_requirement(c, "eicr") is True


def test_create_compliance_booking_service_mocked():
    from services import compliance_booking_service as cbs

    async def _run():
        mock_db = MagicMock()
        mock_db.properties.find_one = AsyncMock(return_value={"_id": 1})
        mock_db.requirements.find_one = AsyncMock(
            return_value={"requirement_code": "gas_safety", "requirement_type": "gas_safety"}
        )
        mock_db.requirements_catalog.find_one = AsyncMock(return_value={"title": "Gas Safety"})
        inserted = {}

        async def fake_create(**kwargs):
            inserted.update(kwargs)
            return {
                "work_order_id": "wo-test",
                "work_order_kind": kwargs.get("work_order_kind"),
                "requirement_code": kwargs.get("requirement_code"),
                "client_id": kwargs.get("client_id"),
            }

        with (
            patch.object(db_singleton, "get_db", return_value=mock_db),
            patch("services.compliance_booking_service.create_audit_log", new_callable=AsyncMock),
            patch("services.compliance_booking_service.maintenance_service.create_work_order", side_effect=fake_create),
        ):
            await cbs.create_compliance_execution_work_order(
                client_id="cli1",
                property_id="p1",
                requirement_code_raw="cp12",
                compliance_purpose="inspection",
                compliance_generated_from="manual",
                actor_portal_user_id="u1",
                linked_property_requirement_id="req-row-1",
            )
        return inserted

    kwargs = asyncio.run(_run())
    assert kwargs.get("work_order_kind") == WORK_ORDER_KIND_COMPLIANCE
    assert kwargs.get("requirement_code") == "gas_safety"
    assert kwargs.get("use_triage") is False


def test_list_work_orders_applies_work_order_kind_filter():
    """Optional work_order_kind narrows the Mongo query to MAINTENANCE or COMPLIANCE."""

    async def _run():
        from services import maintenance_service as ms

        mock_cursor = MagicMock()
        mock_cursor.sort = MagicMock(return_value=mock_cursor)
        mock_cursor.skip = MagicMock(return_value=mock_cursor)
        mock_cursor.limit = MagicMock(return_value=mock_cursor)
        mock_cursor.to_list = AsyncMock(return_value=[])

        mock_db = MagicMock()
        mock_db.work_orders.find = MagicMock(return_value=mock_cursor)
        mock_db.work_orders.count_documents = AsyncMock(return_value=0)

        with patch.object(db_singleton, "get_db", return_value=mock_db):
            await ms.list_work_orders(client_id="c1", work_order_kind="compliance")

        mock_db.work_orders.find.assert_called_once()
        q = mock_db.work_orders.find.call_args[0][0]
        assert q.get("client_id") == "c1"
        assert q.get("work_order_kind") == WORK_ORDER_KIND_COMPLIANCE

    asyncio.run(_run())
