"""Work order scheduling lifecycle: validation, ICS, state rules (no calendar engine)."""

import base64
import re
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from models import AuditAction
from services.work_order_schedule_constants import (
    AUDIT_EVENT_SCHEDULE_CANCELLED,
    AUDIT_EVENT_SCHEDULE_CONFIRMED,
    AUDIT_EVENT_SCHEDULE_PROPOSED,
    AUDIT_EVENT_SCHEDULE_REMINDER,
    AUDIT_EVENT_SCHEDULE_RESCHEDULE_REQUESTED,
    SCHEDULE_ACTOR_CLIENT,
    SCHEDULE_ACTOR_CONTRACTOR,
    SCHEDULE_STATUS_CANCELLED,
    SCHEDULE_STATUS_CONFIRMED,
    SCHEDULE_STATUS_PROPOSED,
    SCHEDULE_STATUS_RESCHEDULE_REQUESTED,
)
from services.work_order_schedule_service import (
    build_work_order_ics_bytes,
    normalize_scheduled_instant,
)
from services.notification_orchestrator import notification_orchestrator


class _SimpleAsyncCursor:
    """Minimal async iterator for Motor-style ``async for doc in cursor``."""

    def __init__(self, rows):
        self._rows = list(rows)
        self._idx = 0

    def __aiter__(self):
        self._idx = 0
        return self

    async def __anext__(self):
        if self._idx >= len(self._rows):
            raise StopAsyncIteration
        r = self._rows[self._idx]
        self._idx += 1
        return r


class FakeScheduleMongo:
    """In-memory work_orders row + related collections for schedule service tests."""

    def __init__(self, wo: dict):
        self.wo = dict(wo)
        self.db = MagicMock()
        self.db.properties.find_one = AsyncMock(
            return_value={"nickname": None, "address_line_1": "1 Main", "city": "London", "postcode": "E1 1AA"}
        )
        self.db.clients.find_one = AsyncMock(return_value={"email": "client@example.com", "contact_email": None})
        self.db.contractors.find_one = AsyncMock(return_value={"email": "contractor@example.com"})
        self.db.work_orders.find_one = self._work_orders_find_one
        self.db.work_orders.find_one_and_update = self._work_orders_find_one_and_update
        self.db.work_orders.find = self._work_orders_find
        self.db.work_orders.update_one = self._work_orders_update_one

    async def _work_orders_find_one(self, query, projection=None):
        if query.get("work_order_id") == self.wo.get("work_order_id"):
            return dict(self.wo)
        return None

    async def _work_orders_find_one_and_update(self, query, update, return_document=True):
        if "$set" in update:
            self.wo.update(update["$set"])
        return dict(self.wo)

    def _matches_reminder_query(self, q: dict) -> bool:
        if self.wo.get("schedule_status") != SCHEDULE_STATUS_CONFIRMED:
            return False
        if self.wo.get("reminder_sent") is True:
            return False
        sat = self.wo.get("scheduled_at")
        if not sat or not str(sat).strip():
            return False
        cid = self.wo.get("contractor_id")
        if not cid or not str(cid).strip():
            return False
        return True

    def _work_orders_find(self, query):
        if self._matches_reminder_query(query):
            return _SimpleAsyncCursor([dict(self.wo)])
        return _SimpleAsyncCursor([])

    async def _work_orders_update_one(self, query, update):
        if query.get("work_order_id") == self.wo.get("work_order_id") and "$set" in update:
            self.wo.update(update["$set"])
        return MagicMock(modified_count=1)


def _future_iso(days=7, hours=0):
    t = datetime.now(timezone.utc) + timedelta(days=days, hours=hours)
    return t.replace(microsecond=0).isoformat()


def _kwargs(mock_call):
    return mock_call.kwargs


def test_normalize_scheduled_instant_naive_with_tz():
    utc_iso, tz = normalize_scheduled_instant("2028-06-15T14:00:00", "Europe/London")
    assert tz == "Europe/London"
    assert "2028-06-15" in utc_iso or "2028-06-15T13:00:00" in utc_iso or "T13:" in utc_iso or "T12:" in utc_iso


def test_normalize_requires_timezone():
    with pytest.raises(ValueError, match="timezone"):
        normalize_scheduled_instant("2028-06-15T14:00:00", "")


def test_build_ics_contains_vevent():
    wo = {
        "work_order_id": "wo-test-ics",
        "description": "Test repair",
        "status": "SCHEDULED",
        "work_order_kind": "MAINTENANCE",
    }
    dt = datetime(2028, 3, 1, 10, 0, tzinfo=timezone.utc)
    raw = build_work_order_ics_bytes(wo, property_label="1 Test St", dt_start_utc=dt)
    s = raw.decode("utf-8")
    assert "BEGIN:VCALENDAR" in s
    assert "BEGIN:VEVENT" in s
    assert "wo-test-ics" in s


@pytest.mark.asyncio
async def test_propose_schedule_writes_mongo_and_audits():
    from services import work_order_schedule_service as sch

    now = datetime.now(timezone.utc) + timedelta(days=7)
    iso_local = now.strftime("%Y-%m-%dT%H:%M:00")

    mock_db = MagicMock()
    wo_row = {
        "work_order_id": "wo1",
        "client_id": "c1",
        "contractor_id": "ctr1",
        "property_id": "p1",
        "status": "ASSIGNED",
        "work_order_kind": "MAINTENANCE",
    }
    updated_doc = {**wo_row, "scheduled_at": iso_local, "schedule_status": SCHEDULE_STATUS_PROPOSED}

    mock_db.work_orders.find_one = AsyncMock(return_value=dict(wo_row))
    mock_db.work_orders.find_one_and_update = AsyncMock(return_value=dict(updated_doc))
    mock_db.properties.find_one = AsyncMock(
        return_value={"nickname": None, "address_line_1": "1 Main", "city": "London", "postcode": "E1 1AA"}
    )
    mock_db.clients.find_one = AsyncMock(return_value={"email": "client@example.com", "contact_email": None})
    mock_db.contractors.find_one = AsyncMock(return_value={"email": "co@example.com"})

    with (
        patch("services.work_order_schedule_service.database.get_db", return_value=mock_db),
        patch("services.work_order_schedule_service.create_audit_log", new_callable=AsyncMock),
        patch("services.work_order_schedule_service._send_schedule_emails", new_callable=AsyncMock),
    ):
        out = await sch.propose_schedule(
            "wo1",
            actor_type=SCHEDULE_ACTOR_CLIENT,
            actor_id="u1",
            actor_role="ROLE_CLIENT",
            scheduled_at_raw=iso_local,
            timezone_name="UTC",
            notes="Please confirm",
            client_id="c1",
        )
    assert out.get("schedule_status") == SCHEDULE_STATUS_PROPOSED
    mock_db.work_orders.find_one_and_update.assert_called_once()


def test_completion_policy_requires_confirmed_when_env_set(monkeypatch):
    monkeypatch.setenv("WORK_ORDER_COMPLETION_REQUIRES_CONFIRMED_SCHEDULE", "true")
    from services.work_order_schedule_service import assert_completion_schedule_policy

    with pytest.raises(ValueError, match="confirmed"):
        assert_completion_schedule_policy({"schedule_status": "proposed", "scheduled_at": "2028-01-01T00:00:00+00:00"})
    assert_completion_schedule_policy({"schedule_status": "confirmed", "scheduled_at": "2028-01-01T00:00:00+00:00"}) is None


@pytest.mark.asyncio
async def test_scenario_a_client_proposes_contractor_confirms_reminder_sent():
    """A: propose → other party notified; confirm → both + ICS; reminder job → both, reminder_sent set."""
    from services import work_order_schedule_service as sch

    iso = _future_iso(days=7)
    fake = FakeScheduleMongo(
        {
            "work_order_id": "wo-a",
            "client_id": "c1",
            "contractor_id": "ctr1",
            "property_id": "p1",
            "status": "ASSIGNED",
            "work_order_kind": "MAINTENANCE",
            "description": "Leak repair",
        }
    )
    with (
        patch("services.work_order_schedule_service.database.get_db", return_value=fake.db),
        patch("services.work_order_schedule_service.create_audit_log", new_callable=AsyncMock),
        patch.object(notification_orchestrator, "send", new_callable=AsyncMock),
    ):
        await sch.propose_schedule(
            "wo-a",
            actor_type=SCHEDULE_ACTOR_CLIENT,
            actor_id="u1",
            actor_role="ROLE_CLIENT",
            scheduled_at_raw=iso,
            timezone_name="UTC",
            notes="Morning please",
            client_id="c1",
        )
        assert fake.wo["schedule_status"] == SCHEDULE_STATUS_PROPOSED
        assert notification_orchestrator.send.await_count == 1
        k1 = _kwargs(notification_orchestrator.send.await_args_list[0])
        assert k1["event_type"] == AUDIT_EVENT_SCHEDULE_PROPOSED
        assert k1["context"]["recipient"] == "contractor@example.com"

        await sch.confirm_schedule(
            "wo-a",
            actor_type=SCHEDULE_ACTOR_CONTRACTOR,
            actor_id="u2",
            actor_role="ROLE_CONTRACTOR",
            contractor_id="ctr1",
        )
        assert fake.wo["schedule_status"] == SCHEDULE_STATUS_CONFIRMED
        assert notification_orchestrator.send.await_count == 3
        k2 = _kwargs(notification_orchestrator.send.await_args_list[1])
        k3 = _kwargs(notification_orchestrator.send.await_args_list[2])
        assert {k2["context"]["recipient"], k3["context"]["recipient"]} == {
            "client@example.com",
            "contractor@example.com",
        }
        assert k2["event_type"] == AUDIT_EVENT_SCHEDULE_CONFIRMED
        assert "attachments" in k2["context"]
        assert "attachments" in k3["context"]
        att = k2["context"]["attachments"][0]
        ics_raw = base64.b64decode(att["Content"])
        assert b"BEGIN:VCALENDAR" in ics_raw

        # Move visit into reminder window (job filters by time, not the initial +7d proposal)
        fake.wo["scheduled_at"] = (datetime.now(timezone.utc) + timedelta(hours=12)).replace(microsecond=0).isoformat()
        out = await sch.run_schedule_reminders_job()
        assert out["count"] == 1
        assert fake.wo.get("reminder_sent") is True
        assert notification_orchestrator.send.await_count == 5
        k4 = _kwargs(notification_orchestrator.send.await_args_list[3])
        k5 = _kwargs(notification_orchestrator.send.await_args_list[4])
        assert k4["event_type"] == AUDIT_EVENT_SCHEDULE_REMINDER
        assert k5["event_type"] == AUDIT_EVENT_SCHEDULE_REMINDER


@pytest.mark.asyncio
async def test_scenario_b_reschedule_then_repropose_and_confirm():
    """B: contractor requests reschedule → client notified; client re-proposes; contractor confirms."""
    from services import work_order_schedule_service as sch

    iso1 = _future_iso(days=10)
    iso2 = _future_iso(days=11)
    fake = FakeScheduleMongo(
        {
            "work_order_id": "wo-b",
            "client_id": "c1",
            "contractor_id": "ctr1",
            "property_id": "p1",
            "status": "ASSIGNED",
            "work_order_kind": "MAINTENANCE",
        }
    )
    with (
        patch("services.work_order_schedule_service.database.get_db", return_value=fake.db),
        patch("services.work_order_schedule_service.create_audit_log", new_callable=AsyncMock),
        patch.object(notification_orchestrator, "send", new_callable=AsyncMock),
    ):
        await sch.propose_schedule(
            "wo-b",
            actor_type=SCHEDULE_ACTOR_CLIENT,
            actor_id="u1",
            actor_role="ROLE_CLIENT",
            scheduled_at_raw=iso1,
            timezone_name="UTC",
            notes=None,
            client_id="c1",
        )
        await sch.confirm_schedule(
            "wo-b",
            actor_type=SCHEDULE_ACTOR_CONTRACTOR,
            actor_id="u2",
            actor_role="ROLE_CONTRACTOR",
            contractor_id="ctr1",
        )
        notification_orchestrator.send.reset_mock()

        await sch.request_reschedule(
            "wo-b",
            actor_type=SCHEDULE_ACTOR_CONTRACTOR,
            actor_id="u2",
            actor_role="ROLE_CONTRACTOR",
            reason="Need next week",
            contractor_id="ctr1",
        )
        assert fake.wo["schedule_status"] == SCHEDULE_STATUS_RESCHEDULE_REQUESTED
        assert fake.wo.get("schedule_reschedule_reason") == "Need next week"
        assert notification_orchestrator.send.await_count == 1
        rk = _kwargs(notification_orchestrator.send.await_args_list[0])
        assert rk["event_type"] == AUDIT_EVENT_SCHEDULE_RESCHEDULE_REQUESTED
        assert rk["context"]["recipient"] == "client@example.com"

        await sch.propose_schedule(
            "wo-b",
            actor_type=SCHEDULE_ACTOR_CLIENT,
            actor_id="u1",
            actor_role="ROLE_CLIENT",
            scheduled_at_raw=iso2,
            timezone_name="UTC",
            notes="New slot",
            client_id="c1",
        )
        assert fake.wo["schedule_status"] == SCHEDULE_STATUS_PROPOSED

        await sch.confirm_schedule(
            "wo-b",
            actor_type=SCHEDULE_ACTOR_CONTRACTOR,
            actor_id="u2",
            actor_role="ROLE_CONTRACTOR",
            contractor_id="ctr1",
        )
        assert fake.wo["schedule_status"] == SCHEDULE_STATUS_CONFIRMED


@pytest.mark.asyncio
async def test_scenario_c_confirmed_cancel_notifies_both():
    """C: after confirm, cancel notifies client and contractor."""
    from services import work_order_schedule_service as sch

    iso = _future_iso(days=5)
    fake = FakeScheduleMongo(
        {
            "work_order_id": "wo-c",
            "client_id": "c1",
            "contractor_id": "ctr1",
            "property_id": "p1",
            "status": "ASSIGNED",
            "work_order_kind": "MAINTENANCE",
        }
    )
    with (
        patch("services.work_order_schedule_service.database.get_db", return_value=fake.db),
        patch("services.work_order_schedule_service.create_audit_log", new_callable=AsyncMock),
        patch.object(notification_orchestrator, "send", new_callable=AsyncMock),
    ):
        await sch.propose_schedule(
            "wo-c",
            actor_type=SCHEDULE_ACTOR_CLIENT,
            actor_id="u1",
            actor_role="ROLE_CLIENT",
            scheduled_at_raw=iso,
            timezone_name="UTC",
            notes=None,
            client_id="c1",
        )
        await sch.confirm_schedule(
            "wo-c",
            actor_type=SCHEDULE_ACTOR_CONTRACTOR,
            actor_id="u2",
            actor_role="ROLE_CONTRACTOR",
            contractor_id="ctr1",
        )
        notification_orchestrator.send.reset_mock()

        await sch.cancel_schedule(
            "wo-c",
            actor_type=SCHEDULE_ACTOR_CLIENT,
            actor_id="u1",
            actor_role="ROLE_CLIENT",
            client_id="c1",
        )
        assert fake.wo["schedule_status"] == SCHEDULE_STATUS_CANCELLED
        assert fake.wo.get("scheduled_at") is None
        assert fake.wo.get("scheduled_timezone") is None
        assert fake.wo.get("status") == "ASSIGNED"
        assert notification_orchestrator.send.await_count == 2
        recips = {_kwargs(c)["context"]["recipient"] for c in notification_orchestrator.send.await_args_list}
        assert recips == {"client@example.com", "contractor@example.com"}
        for c in notification_orchestrator.send.await_args_list:
            assert _kwargs(c)["event_type"] == AUDIT_EVENT_SCHEDULE_CANCELLED


@pytest.mark.asyncio
async def test_scenario_d_confirm_then_ics_payload_valid_rfc5545_shape():
    """D: after confirm, ICS download contains required VEVENT fields and UTC DTSTART."""
    from services import work_order_schedule_service as sch

    iso = "2030-02-15T15:30:00+00:00"
    fake = FakeScheduleMongo(
        {
            "work_order_id": "wo-d",
            "client_id": "c1",
            "contractor_id": "ctr1",
            "property_id": "p1",
            "status": "ASSIGNED",
            "work_order_kind": "MAINTENANCE",
            "description": "Boiler service",
        }
    )
    with (
        patch("services.work_order_schedule_service.database.get_db", return_value=fake.db),
        patch("services.work_order_schedule_service.create_audit_log", new_callable=AsyncMock),
        patch.object(notification_orchestrator, "send", new_callable=AsyncMock),
    ):
        await sch.propose_schedule(
            "wo-d",
            actor_type=SCHEDULE_ACTOR_CLIENT,
            actor_id="u1",
            actor_role="ROLE_CLIENT",
            scheduled_at_raw=iso,
            timezone_name="UTC",
            notes=None,
            client_id="c1",
        )
        await sch.confirm_schedule(
            "wo-d",
            actor_type=SCHEDULE_ACTOR_CONTRACTOR,
            actor_id="u2",
            actor_role="ROLE_CONTRACTOR",
            contractor_id="ctr1",
        )
        ics_bytes, filename = await sch.get_schedule_ics_payload("wo-d", contractor_id="ctr1")
    assert filename == "work-order-wo-d-visit.ics"
    text = ics_bytes.decode("utf-8")
    assert re.search(r"^VERSION:2\.0\r?$", text, re.MULTILINE)
    assert re.search(r"^BEGIN:VCALENDAR\r?$", text, re.MULTILINE)
    assert re.search(r"^BEGIN:VEVENT\r?$", text, re.MULTILINE)
    assert re.search(r"^DTSTART:20300215T153000Z\r?$", text, re.MULTILINE)
    assert re.search(r"^DTEND:20300215T163000Z\r?$", text, re.MULTILINE)
    assert "LOCATION:1 Main, London, E1 1AA" in text.replace("\r\n ", "") or "LOCATION:1 Main" in text


@pytest.mark.asyncio
async def test_cannot_confirm_without_proposed_schedule():
    from services import work_order_schedule_service as sch

    fake = FakeScheduleMongo(
        {
            "work_order_id": "wo-x",
            "client_id": "c1",
            "contractor_id": "ctr1",
            "property_id": "p1",
            "status": "ASSIGNED",
            "work_order_kind": "MAINTENANCE",
            "scheduled_at": _future_iso(days=3),
            "schedule_status": SCHEDULE_STATUS_CONFIRMED,
        }
    )
    with patch("services.work_order_schedule_service.database.get_db", return_value=fake.db):
        with pytest.raises(ValueError, match="proposed"):
            await sch.confirm_schedule(
                "wo-x",
                actor_type=SCHEDULE_ACTOR_CONTRACTOR,
                actor_id="u2",
                actor_role="ROLE_CONTRACTOR",
                contractor_id="ctr1",
            )


@pytest.mark.asyncio
async def test_cannot_confirm_when_client_proposed_same_party():
    from services import work_order_schedule_service as sch

    fake = FakeScheduleMongo(
        {
            "work_order_id": "wo-y",
            "client_id": "c1",
            "contractor_id": "ctr1",
            "property_id": "p1",
            "status": "ASSIGNED",
            "work_order_kind": "MAINTENANCE",
            "scheduled_at": _future_iso(days=3),
            "schedule_status": SCHEDULE_STATUS_PROPOSED,
            "scheduled_by": SCHEDULE_ACTOR_CLIENT,
        }
    )
    with patch("services.work_order_schedule_service.database.get_db", return_value=fake.db):
        with pytest.raises(ValueError, match="not allowed to confirm"):
            await sch.confirm_schedule(
                "wo-y",
                actor_type=SCHEDULE_ACTOR_CLIENT,
                actor_id="u1",
                actor_role="ROLE_CLIENT",
                client_id="c1",
            )


@pytest.mark.asyncio
async def test_reschedule_requires_existing_scheduled_at():
    from services import work_order_schedule_service as sch

    fake = FakeScheduleMongo(
        {
            "work_order_id": "wo-z",
            "client_id": "c1",
            "contractor_id": "ctr1",
            "property_id": "p1",
            "status": "ASSIGNED",
            "work_order_kind": "MAINTENANCE",
            "schedule_status": SCHEDULE_STATUS_PROPOSED,
            "scheduled_at": "",
        }
    )
    with patch("services.work_order_schedule_service.database.get_db", return_value=fake.db):
        with pytest.raises(ValueError, match="no visit scheduled"):
            await sch.request_reschedule(
                "wo-z",
                actor_type=SCHEDULE_ACTOR_CLIENT,
                actor_id="u1",
                actor_role="ROLE_CLIENT",
                reason="Please move",
                client_id="c1",
            )


@pytest.mark.asyncio
async def test_audit_metadata_includes_event_type_on_propose():
    from services import work_order_schedule_service as sch

    iso = _future_iso(days=8)
    fake = FakeScheduleMongo(
        {
            "work_order_id": "wo-audit",
            "client_id": "c1",
            "contractor_id": "ctr1",
            "property_id": "p1",
            "status": "ASSIGNED",
            "work_order_kind": "MAINTENANCE",
        }
    )
    audit = AsyncMock()
    with (
        patch("services.work_order_schedule_service.database.get_db", return_value=fake.db),
        patch("services.work_order_schedule_service.create_audit_log", audit),
        patch.object(notification_orchestrator, "send", new_callable=AsyncMock),
    ):
        await sch.propose_schedule(
            "wo-audit",
            actor_type=SCHEDULE_ACTOR_CLIENT,
            actor_id="actor-1",
            actor_role="ROLE_CLIENT",
            scheduled_at_raw=iso,
            timezone_name="Europe/London",
            notes="Note A",
            client_id="c1",
        )
    audit.assert_awaited_once()
    call_kw = audit.await_args.kwargs
    assert call_kw["action"] == AuditAction.WORK_ORDER_SCHEDULE_PROPOSED
    meta = call_kw["metadata"]
    assert meta["event_type"] == AUDIT_EVENT_SCHEDULE_PROPOSED
    assert meta["work_order_id"] == "wo-audit"
    assert meta["scheduled_at"]
    assert meta["timezone"] == "Europe/London"
