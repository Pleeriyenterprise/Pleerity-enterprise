"""Rent Operations Phase 1 — unit and integration tests."""
import uuid
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from models.rent_operations import RentLedgerStatus
from services.rent_ledger_service import recalculate_rent_ledger_status, recalculate_and_persist_ledger


class TestRentStatusDerivation:
    def test_paid_when_fully_received(self):
        status, days, outstanding = recalculate_rent_ledger_status(
            120000, 120000, "2026-01-01", as_of=date(2026, 1, 15)
        )
        assert status == RentLedgerStatus.PAID.value
        assert outstanding == 0
        assert days == 0

    def test_partially_paid(self):
        status, days, outstanding = recalculate_rent_ledger_status(
            120000, 70000, "2026-05-20", as_of=date(2026, 5, 25)
        )
        assert status == RentLedgerStatus.PARTIALLY_PAID.value
        assert outstanding == 50000
        assert days >= 1

    def test_overdue_unpaid(self):
        status, days, outstanding = recalculate_rent_ledger_status(
            120000, 0, "2026-05-01", as_of=date(2026, 5, 10)
        )
        assert status == RentLedgerStatus.OVERDUE.value
        assert days == 9
        assert outstanding == 120000

    def test_severely_overdue(self):
        status, days, outstanding = recalculate_rent_ledger_status(
            120000, 0, "2026-04-01", as_of=date(2026, 5, 20)
        )
        assert status == RentLedgerStatus.SEVERELY_OVERDUE.value
        assert days >= 14

    def test_due_today(self):
        today = date(2026, 5, 1)
        status, days, outstanding = recalculate_rent_ledger_status(
            120000, 0, today.isoformat(), as_of=today
        )
        assert status == RentLedgerStatus.DUE_TODAY.value

    def test_upcoming(self):
        status, _, outstanding = recalculate_rent_ledger_status(
            120000, 0, "2026-06-01", as_of=date(2026, 5, 1)
        )
        assert status == RentLedgerStatus.UPCOMING.value
        assert outstanding == 120000

    def test_waived(self):
        status, _, _ = recalculate_rent_ledger_status(
            120000, 0, "2026-01-01", waived_at="2026-01-02T00:00:00Z", as_of=date(2026, 2, 1)
        )
        assert status == RentLedgerStatus.WAIVED.value

    def test_disputed(self):
        status, _, _ = recalculate_rent_ledger_status(
            120000, 50000, "2026-01-01", disputed_at="2026-01-02T00:00:00Z", as_of=date(2026, 2, 1)
        )
        assert status == RentLedgerStatus.DISPUTED.value


@pytest.mark.asyncio
async def test_recalculate_and_persist_ledger():
    ledger_id = "rlp_test123"
    client_id = "c_test"
    mock_db = MagicMock()
    periods_coll = MagicMock()
    periods_coll.find_one = AsyncMock(
        return_value={
            "ledger_id": ledger_id,
            "client_id": client_id,
            "expected_amount_minor": 100000,
            "due_date": "2026-01-01",
            "waived_at": None,
            "disputed_at": None,
        }
    )
    periods_coll.update_one = AsyncMock()
    mock_db.__getitem__ = MagicMock(side_effect=lambda k: periods_coll if k == "rent_ledger_periods" else MagicMock())
    mock_db.rent_payments = MagicMock()
    payments_cursor = MagicMock()
    payments_cursor.to_list = AsyncMock(return_value=[{"amount_minor": 60000}])
    mock_db.rent_payments.find = MagicMock(return_value=payments_cursor)

    with patch("services.rent_ledger_service.database.get_db", return_value=mock_db), patch(
        "services.rent_ledger_service.create_audit_log", new_callable=AsyncMock
    ):
        doc = await recalculate_and_persist_ledger(ledger_id, client_id)
    assert doc["status"] == RentLedgerStatus.PARTIALLY_PAID.value
    assert doc["received_amount_minor"] == 60000
    assert doc["outstanding_balance_minor"] == 40000
    assert doc["is_overdue"] is True


@pytest.mark.asyncio
async def test_payment_allocation_oldest_first():
    from services import rent_payment_service

    client_id = "c_alloc"
    property_id = "p_alloc"
    mock_db = MagicMock()

    ledgers = [
        {
            "ledger_id": "rlp_may",
            "client_id": client_id,
            "property_id": property_id,
            "period_key": "2026-05",
            "outstanding_balance_minor": 100000,
            "status": RentLedgerStatus.OVERDUE.value,
            "due_date": "2026-05-01",
            "currency": "GBP",
        },
        {
            "ledger_id": "rlp_jun",
            "client_id": client_id,
            "property_id": property_id,
            "period_key": "2026-06",
            "outstanding_balance_minor": 100000,
            "status": RentLedgerStatus.UPCOMING.value,
            "due_date": "2026-06-01",
            "currency": "GBP",
        },
    ]

    async def _find_one(query, *args, **kwargs):
        if query.get("property_id") == property_id:
            return {"property_id": property_id, "client_id": client_id}
        lid = query.get("ledger_id")
        for l in ledgers:
            if l["ledger_id"] == lid:
                return dict(l)
        return None

    sort_mock = MagicMock()
    sort_mock.to_list = AsyncMock(return_value=ledgers)
    find_cursor = MagicMock()
    find_cursor.sort = MagicMock(return_value=sort_mock)
    mock_db.properties.find_one = AsyncMock(side_effect=_find_one)
    mock_db.rent_ledger_periods = MagicMock()
    mock_db.rent_ledger_periods.find_one = AsyncMock(side_effect=_find_one)
    mock_db.rent_ledger_periods.find = MagicMock(return_value=find_cursor)
    mock_db.rent_payments = MagicMock()
    mock_db.rent_payments.insert_one = AsyncMock()

    with patch("services.rent_payment_service.database.get_db", return_value=mock_db), patch(
        "services.rent_payment_service.rent_ledger_service.recalculate_and_persist_ledger",
        new_callable=AsyncMock,
        side_effect=lambda lid, cid, *a, **k: next(
            (dict(l, outstanding_balance_minor=100000 if l["ledger_id"] == "rlp_may" else 50000)
             for l in ledgers if l["ledger_id"] == lid),
            None,
        ),
    ), patch(
        "services.rent_payment_service._recalc_ledgers", new_callable=AsyncMock
    ), patch("services.rent_payment_service.create_audit_log", new_callable=AsyncMock), patch(
        "services.rent_payment_service.tenancy_authority.get_tenancy",
        new_callable=AsyncMock,
        return_value={"tenancy_id": "pty_alloc", "property_id": property_id, "client_id": client_id},
    ):
        result = await rent_payment_service.record_payment(
            client_id,
            {
                "amount_minor": 150000,
                "payment_date": "2026-06-15",
                "property_id": property_id,
                "tenancy_id": "pty_alloc",
            },
        )

    assert len(result["allocations"]) == 2
    assert result["allocations"][0]["ledger_id"] == "rlp_may"
    assert result["allocations"][0]["amount_minor"] == 100000
    assert result["allocations"][1]["amount_minor"] == 50000


@pytest.mark.asyncio
async def test_reminder_idempotency():
    from services import rent_reminder_service

    reminder_key = rent_reminder_service.build_reminder_key("due_today", "rlp_1", "2026-05")
    assert reminder_key == "RENT_DUE_TODAY_rlp_1_2026-05"

    mock_db = MagicMock()
    mock_db.rent_ledger_periods = MagicMock()
    mock_db.rent_ledger_periods.find_one = AsyncMock(
        return_value={
            "ledger_id": "rlp_1",
            "client_id": "c1",
            "property_id": "p1",
            "period_key": "2026-05",
        }
    )
    reminders_coll = MagicMock()
    reminders_coll.find_one = AsyncMock(return_value={"reminder_key": reminder_key})
    reminders_coll.insert_one = AsyncMock()
    mock_db.__getitem__ = MagicMock(
        side_effect=lambda k: (
            mock_db.rent_ledger_periods
            if k == "rent_ledger_periods"
            else reminders_coll
            if k == "rent_reminder_events"
            else MagicMock()
        )
    )

    with patch("services.rent_reminder_service.database.get_db", return_value=mock_db), patch(
        "services.rent_reminder_service.create_audit_log", new_callable=AsyncMock
    ):
        existing = await rent_reminder_service.mark_reminder_sent(
            "rlp_1",
            "c1",
            {"reminder_type": "due_today", "channel": "email"},
        )
    assert existing["reminder_key"] == reminder_key
    reminders_coll.insert_one.assert_not_called()


@pytest.mark.asyncio
async def test_compliance_score_unchanged_after_rent_ops():
    """Rent/expense mutations must not invoke compliance scoring."""
    from services import property_expense_service

    client_id = f"c_iso_{uuid.uuid4().hex[:8]}"
    property_id = f"p_iso_{uuid.uuid4().hex[:8]}"
    expenses_coll = MagicMock()
    expenses_coll.insert_one = AsyncMock()
    mock_db = MagicMock()
    mock_db.properties = MagicMock()
    mock_db.properties.find_one = AsyncMock(return_value={"property_id": property_id, "client_id": client_id})
    mock_db.__getitem__ = MagicMock(
        side_effect=lambda k: expenses_coll if k == "property_expenses" else MagicMock()
    )

    with patch("services.property_expense_service.database.get_db", return_value=mock_db), patch(
        "services.property_expense_service.create_audit_log", new_callable=AsyncMock
    ), patch(
        "services.compliance_scoring_service.recalculate_and_persist", new_callable=AsyncMock
    ) as mock_recalc:
        await property_expense_service.create_expense(
            client_id,
            {
                "property_id": property_id,
                "category": "REPAIRS",
                "amount_minor": 50000,
                "expense_date": date.today().isoformat(),
                "compliance_related": True,
                "requirement_id": "req_test",
            },
        )
    mock_recalc.assert_not_called()


@pytest.mark.asyncio
async def test_sum_rent_collected_by_payment_date():
    from services.rent_ledger_service import sum_rent_collected_by_payment_date

    mock_db = MagicMock()
    mock_db.rent_payments = MagicMock()
    mock_db.rent_payments.aggregate = MagicMock(
        return_value=MagicMock(to_list=AsyncMock(return_value=[{"total": 75000}]))
    )
    with patch("services.rent_ledger_service.database.get_db", return_value=mock_db):
        total = await sum_rent_collected_by_payment_date("c1", "2026-05-01", "2026-05-31", property_id="p1")
    assert total == 75000
    pipeline = mock_db.rent_payments.aggregate.call_args[0][0]
    assert pipeline[0]["$match"]["payment_date"] == {"$gte": "2026-05-01", "$lte": "2026-05-31"}
    assert pipeline[0]["$match"]["property_id"] == "p1"


@pytest.mark.asyncio
async def test_sum_rent_collected_cross_property_isolation():
    from services.rent_ledger_service import sum_rent_collected_by_payment_date

    mock_db = MagicMock()
    mock_db.rent_payments = MagicMock()
    mock_db.rent_payments.aggregate = MagicMock(
        return_value=MagicMock(to_list=AsyncMock(return_value=[]))
    )
    with patch("services.rent_ledger_service.database.get_db", return_value=mock_db):
        await sum_rent_collected_by_payment_date("c1", "2026-05-01", "2026-05-31")
    match = mock_db.rent_payments.aggregate.call_args[0][0][0]["$match"]
    assert "property_id" not in match
    assert match["client_id"] == "c1"


@pytest.mark.asyncio
async def test_list_ledgers_overdue_only():
    from services import rent_ledger_service

    mock_db = MagicMock()
    periods = MagicMock()
    periods.count_documents = AsyncMock(return_value=0)
    cursor = MagicMock()
    cursor.sort = MagicMock(return_value=cursor)
    cursor.skip = MagicMock(return_value=cursor)
    cursor.limit = MagicMock(return_value=cursor)
    cursor.to_list = AsyncMock(return_value=[])
    periods.find = MagicMock(return_value=cursor)
    mock_db.__getitem__ = MagicMock(side_effect=lambda k: periods if k == "rent_ledger_periods" else MagicMock())

    with patch("services.rent_ledger_service.database.get_db", return_value=mock_db):
        await rent_ledger_service.list_ledgers("c1", overdue_only=True)
    query = periods.count_documents.call_args[0][0]
    assert query["is_overdue"] is True


@pytest.mark.asyncio
async def test_list_ledgers_attention_only_matches_arrears_criteria():
    from models.rent_operations import RentLedgerStatus
    from services import rent_ledger_service

    mock_db = MagicMock()
    periods = MagicMock()
    periods.count_documents = AsyncMock(return_value=0)
    cursor = MagicMock()
    cursor.sort = MagicMock(return_value=cursor)
    cursor.skip = MagicMock(return_value=cursor)
    cursor.limit = MagicMock(return_value=cursor)
    cursor.to_list = AsyncMock(return_value=[])
    periods.find = MagicMock(return_value=cursor)
    mock_db.__getitem__ = MagicMock(side_effect=lambda k: periods if k == "rent_ledger_periods" else MagicMock())

    with patch("services.rent_ledger_service.database.get_db", return_value=mock_db):
        await rent_ledger_service.list_ledgers("c1", attention_only=True)
    query = periods.count_documents.call_args[0][0]
    assert query["$or"] == [
        {"is_overdue": True},
        {"status": RentLedgerStatus.DUE_TODAY.value},
        {"status": RentLedgerStatus.DISPUTED.value},
        {"status": RentLedgerStatus.PARTIALLY_PAID.value},
    ]


@pytest.mark.asyncio
async def test_get_rent_summary_arrears_uses_attention_criteria():
    from models.rent_operations import RentLedgerStatus
    from services import rent_ledger_service

    mock_db = MagicMock()
    periods = MagicMock()
    periods.count_documents = AsyncMock(return_value=0)

    def _agg_cursor(_pipeline):
        cursor = MagicMock()
        cursor.to_list = AsyncMock(return_value=[])
        return cursor

    periods.aggregate = MagicMock(side_effect=_agg_cursor)
    mock_db.__getitem__ = MagicMock(side_effect=lambda k: periods if k == "rent_ledger_periods" else MagicMock())

    with patch("services.rent_ledger_service.database.get_db", return_value=mock_db), patch(
        "services.rent_ledger_service.sum_rent_collected_by_payment_date",
        new_callable=AsyncMock,
        return_value=0,
    ):
        await rent_ledger_service.get_rent_summary("c1")

    arrears_match = periods.aggregate.call_args_list[0][0][0][0]["$match"]
    assert arrears_match["$or"] == [
        {"is_overdue": True},
        {"status": RentLedgerStatus.DUE_TODAY.value},
        {"status": RentLedgerStatus.DISPUTED.value},
        {"status": RentLedgerStatus.PARTIALLY_PAID.value},
    ]
    assert "outstanding_balance_minor" not in arrears_match


@pytest.mark.asyncio
async def test_period_generation_duplicate_key_is_idempotent():
    from pymongo.errors import DuplicateKeyError
    from services import rent_ledger_service

    schedule = {
        "schedule_id": "rs1",
        "client_id": "c1",
        "property_id": "p1",
        "tenant_name": "T",
        "expected_amount_minor": 100000,
        "due_day": 1,
        "start_date": "2026-05-01",
        "rent_frequency": "monthly",
        "currency": "GBP",
    }
    mock_db = MagicMock()
    mock_db.rent_ledger_periods = MagicMock()
    mock_db.rent_ledger_periods.insert_one = AsyncMock(side_effect=DuplicateKeyError("dup"))
    mock_db.rent_ledger_periods.find_one = AsyncMock(return_value=None)
    mock_db.__getitem__ = MagicMock(side_effect=lambda k: mock_db.rent_ledger_periods)

    with patch("services.rent_ledger_service.database.get_db", return_value=mock_db), patch(
        "services.rent_ledger_service._generate_periods_for_schedule",
        return_value=[
            {
                "period_key": "2026-05",
                "due_date": "2026-05-01",
                "expected_amount_minor": 100000,
                "currency": "GBP",
                "rent_frequency": "monthly",
            }
        ],
    ), patch("services.rent_ledger_service.create_audit_log", new_callable=AsyncMock):
        created = await rent_ledger_service.ensure_future_periods_for_schedule(schedule)
    assert created == 0


@pytest.mark.asyncio
async def test_derive_is_overdue_partial_paid():
    from services.rent_ledger_service import derive_is_overdue

    assert derive_is_overdue(115000, "2026-04-01", as_of=date(2026, 5, 20)) is True
    assert derive_is_overdue(0, "2026-04-01", as_of=date(2026, 5, 20)) is False


@pytest.mark.asyncio
async def test_recalculate_all_active_ledgers_batch_audit_only():
    from models import AuditAction
    from services import rent_ledger_service

    periods_coll = MagicMock()
    periods_coll.find = MagicMock(
        return_value=MagicMock(
            to_list=AsyncMock(return_value=[{"ledger_id": "r1", "status": "UPCOMING"}])
        )
    )
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(side_effect=lambda k: periods_coll if k == "rent_ledger_periods" else MagicMock())

    with patch("services.rent_ledger_service.database.get_db", return_value=mock_db), patch(
        "services.rent_ledger_service.recalculate_and_persist_ledger",
        new_callable=AsyncMock,
        return_value={"ledger_id": "r1", "status": "OVERDUE"},
    ), patch(
        "services.rent_ledger_service.create_audit_log", new_callable=AsyncMock
    ) as audit:
        result = await rent_ledger_service.recalculate_all_active_ledgers("c1", write_audit=False)
    assert result["ledgers_processed"] == 1
    assert audit.call_count == 1
    assert audit.call_args.kwargs["action"] == AuditAction.RENT_STATUS_RECALCULATED_BATCH


@pytest.mark.asyncio
async def test_daily_job_continues_after_client_failure():
    from services import rent_operations_daily_job

    async def _side_effect(cid):
        if cid == "bad":
            raise RuntimeError("boom")
        return {"skipped": False}

    with patch(
        "services.rent_operations_daily_job.database.get_db",
        return_value=MagicMock(
            clients=MagicMock(
                find=MagicMock(
                    return_value=MagicMock(
                        to_list=AsyncMock(
                            return_value=[{"client_id": "ok"}, {"client_id": "bad"}]
                        )
                    )
                )
            )
        ),
    ), patch(
        "services.rent_operations_daily_job.run_rent_operations_daily_for_client",
        new_callable=AsyncMock,
        side_effect=_side_effect,
    ):
        out = await rent_operations_daily_job.run_rent_operations_daily_job()
    assert out["outcome_metrics"]["clients_failed"] == 1
    assert out["outcome_metrics"]["processed"] == 1


@pytest.mark.asyncio
async def test_get_ledger_returns_none_for_wrong_client():
    """Service layer must not return another client's ledger."""
    from services import rent_ledger_service

    mock_db = MagicMock()
    mock_db.rent_ledger_periods = MagicMock()
    mock_db.rent_ledger_periods.find_one = AsyncMock(return_value=None)
    mock_db.__getitem__ = MagicMock(side_effect=lambda k: mock_db.rent_ledger_periods)

    with patch("services.rent_ledger_service.database.get_db", return_value=mock_db):
        doc = await rent_ledger_service.get_ledger("rlp_other", "c_a_iso")
    assert doc is None


def test_live_send_client_allowlist(monkeypatch):
    from services import rent_reminder_service

    monkeypatch.setenv("RENT_REMINDERS_LIVE_SEND", "true")
    monkeypatch.setenv("RENT_REMINDERS_LIVE_SEND_CLIENT_ALLOWLIST", "client-a,client-b")
    assert rent_reminder_service._live_send_enabled_for_client("client-a") is True
    assert rent_reminder_service._live_send_enabled_for_client("client-c") is False


def test_safe_recipient_domain_guard(monkeypatch):
    from services import rent_reminder_service

    monkeypatch.delenv("RENT_REMINDERS_PRODUCTION_MODE", raising=False)
    monkeypatch.setenv("RENT_REMINDERS_SAFE_RECIPIENT_DOMAINS", "yopmail.com")
    assert rent_reminder_service.recipient_allowed_for_live_send("f7-ops-wales@yopmail.com") is True
    assert rent_reminder_service.recipient_allowed_for_live_send("tenant@example.com") is False


def test_production_mode_allows_all_clients_and_domains(monkeypatch):
    from services import rent_reminder_service

    monkeypatch.setenv("RENT_REMINDERS_LIVE_SEND", "true")
    monkeypatch.setenv("RENT_REMINDERS_PRODUCTION_MODE", "true")
    monkeypatch.setenv("RENT_REMINDERS_LIVE_SEND_CLIENT_ALLOWLIST", "other-client-only")
    monkeypatch.delenv("RENT_REMINDERS_SAFE_RECIPIENT_DOMAINS", raising=False)

    assert rent_reminder_service._live_send_enabled_for_client("any-client") is True
    assert rent_reminder_service.recipient_allowed_for_live_send("tenant@gmail.com") is True

    cfg = rent_reminder_service.get_live_send_config()
    assert cfg["production_mode"] is True
    assert cfg["client_allowlist_enforced"] is False
    assert cfg["safe_recipient_domains_enforced"] is False


def test_staging_default_blocks_non_yopmail_when_domains_unset(monkeypatch):
    from services import rent_reminder_service

    monkeypatch.delenv("RENT_REMINDERS_PRODUCTION_MODE", raising=False)
    monkeypatch.delenv("RENT_REMINDERS_SAFE_RECIPIENT_DOMAINS", raising=False)

    assert rent_reminder_service.recipient_allowed_for_live_send("f7-ops-wales@yopmail.com") is True
    assert rent_reminder_service.recipient_allowed_for_live_send("tenant@gmail.com") is False


def test_partial_payment_message_notes_remaining_balance():
    from services import rent_reminder_service

    msg = rent_reminder_service.build_reminder_message(
        {
            "tenant_name": "Alex",
            "due_date": "2026-06-01",
            "expected_amount_minor": 120000,
            "outstanding_balance_minor": 45000,
            "status": "PARTIALLY_PAID",
        },
        "overdue_3d",
    )
    assert "partial payment" in msg.lower()
    assert "£450.00" in msg
    assert "£1,200.00" not in msg

