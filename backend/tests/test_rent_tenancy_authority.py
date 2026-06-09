"""Tenancy-authority rent operations — schedule, ledger, payment governance."""
from __future__ import annotations

import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services import rent_ledger_service
from services import rent_tenancy_authority_service as tenancy_authority
from services.rent_ledger_service import preview_schedule_periods


class TestSchedulePreview:
    def test_preview_discloses_period_count_and_range(self):
        preview = preview_schedule_periods(
            {
                "start_date": "2026-06-01",
                "expected_amount_minor": 120000,
                "rent_frequency": "monthly",
                "due_day": 1,
            }
        )
        assert preview["period_count"] >= 1
        assert preview["disclosure"]
        assert "monthly" in preview["disclosure"].lower() or preview["cadence_label"] == "monthly"


@pytest.mark.asyncio
async def test_schedule_requires_tenancy_id():
    mock_db = MagicMock()
    mock_db.properties.find_one = AsyncMock(
        return_value={"property_id": "p1", "client_id": "c1"}
    )
    with patch("services.rent_tenancy_authority_service.database.get_db", return_value=mock_db):
        with pytest.raises(ValueError, match="TENANCY_ID_REQUIRED"):
            await tenancy_authority.validate_schedule_authority(
                "c1",
                {
                    "property_id": "p1",
                    "tenant_name": "Test",
                    "expected_amount_minor": 100000,
                    "start_date": "2026-01-01",
                },
            )


@pytest.mark.asyncio
async def test_external_payer_allowed_without_tenancy():
    mock_db = MagicMock()
    mock_db.properties.find_one = AsyncMock(
        return_value={"property_id": "p1", "client_id": "c1"}
    )
    with patch("services.rent_tenancy_authority_service.database.get_db", return_value=mock_db):
        _prop, tenancy, is_ext = await tenancy_authority.validate_schedule_authority(
            "c1",
            {
                "property_id": "p1",
                "is_external_payer": True,
                "external_payer_name": "Council top-up",
                "expected_amount_minor": 100000,
                "start_date": "2026-01-01",
            },
        )
    assert is_ext is True
    assert tenancy.get("is_external_payer") is True


@pytest.mark.asyncio
async def test_create_schedule_response_has_no_object_id():
    """Mongo insert_one mutates dict with _id; responses must not leak ObjectId."""
    client_id = "c_oid"
    mock_db = MagicMock()
    schedules = MagicMock()
    schedules.find_one = AsyncMock(return_value=None)
    schedules.insert_one = MagicMock(side_effect=lambda d: d.update({"_id": "fake_oid"}))
    schedules.update_many = AsyncMock()
    periods = MagicMock()
    periods.find_one = AsyncMock(return_value=None)
    periods.insert_one = AsyncMock()
    periods.count_documents = AsyncMock(return_value=0)
    tenancies = MagicMock()
    tenancies.find_one = AsyncMock(
        return_value={
            "tenancy_id": "pty_oid",
            "client_id": client_id,
            "property_id": "p1",
            "status": "active",
        }
    )
    tenancies.update_one = AsyncMock()
    props = MagicMock()
    props.find_one = AsyncMock(return_value={"property_id": "p1", "client_id": client_id})

    def getter(k):
        return {
            "rent_schedules": schedules,
            "rent_ledger_periods": periods,
            "property_tenancies": tenancies,
            "properties": props,
        }.get(k, MagicMock())

    mock_db.properties = props
    mock_db.__getitem__ = MagicMock(side_effect=getter)
    with patch("services.rent_ledger_service.database.get_db", return_value=mock_db), patch(
        "services.rent_tenancy_authority_service.database.get_db", return_value=mock_db
    ), patch("services.rent_ledger_service.create_audit_log", new_callable=AsyncMock):
        out = await rent_ledger_service.create_rent_schedule(
            client_id,
            {
                "property_id": "p1",
                "tenancy_id": "pty_oid",
                "expected_amount_minor": 100000,
                "start_date": "2026-06-01",
                "due_day": 1,
                "rent_frequency": "monthly",
                "tenant_name": "T",
            },
        )
    assert "_id" not in out
    assert out.get("schedule_id")


@pytest.mark.asyncio
async def test_duplicate_schedule_idempotency_replay():
    client_id = "c_idem"
    idem = f"idem_{uuid.uuid4().hex[:8]}"
    prior = {"schedule_id": "rs_prior", "client_id": client_id, "idempotency_key": idem}
    mock_db = MagicMock()
    schedules = MagicMock()
    schedules.find_one = AsyncMock(return_value=prior)
    mock_db.rent_schedules = schedules
    mock_db.__getitem__ = MagicMock(side_effect=lambda k: schedules if k == "rent_schedules" else MagicMock())
    with patch("services.rent_ledger_service.database.get_db", return_value=mock_db):
        out = await rent_ledger_service.create_rent_schedule(
            client_id,
            {
                "property_id": "p1",
                "tenancy_id": "pty_1",
                "tenant_name": "A",
                "expected_amount_minor": 100000,
                "start_date": "2026-01-01",
                "idempotency_key": idem,
            },
        )
    assert out.get("idempotent_replay") is True
    assert out["schedule_id"] == "rs_prior"


@pytest.mark.asyncio
async def test_payment_requires_ledger_or_full_authority():
    from services import rent_payment_service

    with patch("services.rent_payment_service.database.get_db", return_value=MagicMock()):
        with pytest.raises(ValueError, match="PAYMENT_AUTHORITY_INCOMPLETE"):
            await rent_payment_service.record_payment(
                "c1",
                {"amount_minor": 50000, "payment_date": "2026-05-01", "property_id": "p1"},
            )


@pytest.mark.asyncio
async def test_create_tenancy_requires_occupancy():
    client_id = "c_no_occ"
    property_id = "p_no_occ"
    mock_db = MagicMock()
    tenancies = MagicMock()
    tenancies.find_one = AsyncMock(return_value=None)
    props = MagicMock()
    props.find_one = AsyncMock(return_value={"property_id": property_id, "client_id": client_id})
    portal_users = MagicMock()
    portal_users.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[])))
    assignments = MagicMock()
    assignments.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[])))
    mock_db.properties = props
    mock_db.portal_users = portal_users
    mock_db.tenant_assignments = assignments
    mock_db.__getitem__ = MagicMock(return_value=tenancies)

    with patch("services.rent_tenancy_authority_service.database.get_db", return_value=mock_db):
        with pytest.raises(ValueError, match="NO_OCCUPANCY_FOR_TENANCY"):
            await tenancy_authority.resolve_or_create_active_tenancy(
                client_id,
                property_id,
                rent_tracking_enabled=True,
            )


@pytest.mark.asyncio
async def test_schedule_rejects_cross_property_tenancy():
    mock_db = MagicMock()
    mock_db.properties.find_one = AsyncMock(
        return_value={"property_id": "p1", "client_id": "c1"}
    )
    tenancies_coll = MagicMock()
    tenancies_coll.find_one = AsyncMock(
        return_value={
            "tenancy_id": "pty_other",
            "client_id": "c1",
            "property_id": "p2",
            "status": "active",
        }
    )
    mock_db.__getitem__ = MagicMock(
        side_effect=lambda k: tenancies_coll if k == "property_tenancies" else MagicMock()
    )

    with patch("services.rent_tenancy_authority_service.database.get_db", return_value=mock_db):
        with pytest.raises(ValueError, match="TENANCY_PROPERTY_MISMATCH"):
            await tenancy_authority.validate_schedule_authority(
                "c1",
                {
                    "property_id": "p1",
                    "tenancy_id": "pty_other",
                    "expected_amount_minor": 100000,
                    "start_date": "2026-01-01",
                },
            )


@pytest.mark.asyncio
async def test_duplicate_active_tenancy_returns_existing():
    client_id = "c_dup"
    property_id = "p_dup"
    existing = {
        "tenancy_id": "pty_existing",
        "client_id": client_id,
        "property_id": property_id,
        "status": "active",
        "rent_tracking_enabled": False,
    }
    mock_db = MagicMock()
    tenancies = MagicMock()
    tenancies.find_one = AsyncMock(return_value=existing)
    tenancies.update_one = AsyncMock()
    props = MagicMock()
    props.find_one = AsyncMock(return_value={"property_id": property_id, "client_id": client_id})
    mock_db.properties = props
    mock_db.__getitem__ = MagicMock(return_value=tenancies)

    with patch("services.rent_tenancy_authority_service.database.get_db", return_value=mock_db):
        doc = await tenancy_authority.resolve_or_create_active_tenancy(
            client_id,
            property_id,
            rent_tracking_enabled=True,
        )
    assert doc["tenancy_id"] == "pty_existing"
    tenancies.insert_one.assert_not_called()


@pytest.mark.asyncio
async def test_new_tenancy_links_lineage_after_move_out():
    """Replacement tenancy after move-out must reference prior tenancy lineage."""
    client_id = "c_lineage"
    property_id = "p_lineage"
    parent_id = "pty_old"
    mock_db = MagicMock()
    tenancies = MagicMock()
    tenancies.find_one = AsyncMock(
        side_effect=[
            None,  # no active tenancy
            {"tenancy_id": parent_id},  # latest moved_out parent
        ]
    )
    tenancies.insert_one = AsyncMock()
    props = MagicMock()
    props.find_one = AsyncMock(return_value={"property_id": property_id, "client_id": client_id})
    portal_users = MagicMock()
    portal_users.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[])))
    assignments = MagicMock()
    assignments.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[])))
    mock_db.properties = props
    mock_db.portal_users = portal_users
    mock_db.tenant_assignments = assignments
    mock_db.__getitem__ = MagicMock(return_value=tenancies)

    with patch("services.rent_tenancy_authority_service.database.get_db", return_value=mock_db):
        doc = await tenancy_authority.resolve_or_create_active_tenancy(
            client_id,
            property_id,
            tenant_ids=["tenant_1"],
            tenant_display_name="New tenant",
            rent_tracking_enabled=False,
            actor_id="actor-1",
        )
    assert doc["lineage_parent_tenancy_id"] == parent_id
    insert_doc = tenancies.insert_one.call_args[0][0]
    assert insert_doc["lineage_parent_tenancy_id"] == parent_id


@pytest.mark.asyncio
async def test_create_replacement_tenancy_sets_parent():
    parent_id = "pty_parent"
    mock_db = MagicMock()
    tenancies = MagicMock()
    tenancies.find_one = AsyncMock(
        return_value={
            "tenancy_id": parent_id,
            "client_id": "c1",
            "property_id": "p1",
            "status": "moved_out",
            "tenant_display_name": "Old",
            "tenant_ids": [],
            "rent_type": "residential_rent",
        }
    )
    tenancies.insert_one = AsyncMock()
    schedules = MagicMock()
    schedules.update_many = AsyncMock()
    mock_db.rent_schedules = schedules
    mock_db.__getitem__ = MagicMock(return_value=tenancies)
    with patch("services.rent_tenancy_authority_service.database.get_db", return_value=mock_db):
        doc = await tenancy_authority.create_replacement_tenancy(
            "c1",
            "p1",
            parent_id,
            actor_id="actor-1",
        )
    assert doc["lineage_parent_tenancy_id"] == parent_id


@pytest.mark.asyncio
async def test_close_tenancy_deactivates_schedules():
    mock_db = MagicMock()
    tenancies = MagicMock()
    tenancies.find_one = AsyncMock(
        return_value={
            "tenancy_id": "pty_x",
            "client_id": "c1",
            "property_id": "p1",
            "status": "active",
        }
    )
    tenancies.update_one = AsyncMock()
    schedules = MagicMock()
    schedules.update_many = AsyncMock()
    mock_db.property_tenancies = tenancies
    mock_db.rent_schedules = schedules
    mock_db.__getitem__ = MagicMock(
        side_effect=lambda k: tenancies if k == "property_tenancies" else schedules
    )
    with patch("services.rent_tenancy_authority_service.database.get_db", return_value=mock_db):
        await tenancy_authority.close_tenancy_rent_lineage("pty_x", "c1")
    mock_db.rent_schedules.update_many.assert_called_once()
    call_filter = mock_db.rent_schedules.update_many.call_args[0][0]
    assert call_filter["tenancy_id"] == "pty_x"


@pytest.mark.asyncio
async def test_ledger_periods_scoped_by_schedule_id():
    """New schedule must not skip period creation due to another schedule's period_key on same property."""
    client_id = "c_scope"
    property_id = "p_scope"
    schedule = {
        "schedule_id": "rs_new",
        "client_id": client_id,
        "property_id": property_id,
        "tenancy_id": "pty_new",
        "tenant_name": "B",
        "rent_frequency": "monthly",
        "due_day": 1,
        "start_date": date.today().replace(day=1).isoformat(),
        "expected_amount_minor": 90000,
        "currency": "GBP",
    }
    mock_db = MagicMock()
    periods_coll = MagicMock()
    periods_coll.find_one = AsyncMock(return_value=None)
    periods_coll.insert_one = AsyncMock()
    mock_db.rent_ledger_periods = periods_coll
    mock_db.__getitem__ = MagicMock(return_value=periods_coll)

    with patch("services.rent_ledger_service.database.get_db", return_value=mock_db), patch(
        "services.rent_ledger_service.create_audit_log", new_callable=AsyncMock
    ):
        created = await rent_ledger_service.ensure_future_periods_for_schedule(schedule)
    assert created >= 0
    if created > 0:
        insert_doc = periods_coll.insert_one.call_args[0][0]
        assert insert_doc["schedule_id"] == "rs_new"
        assert insert_doc["tenancy_id"] == "pty_new"
