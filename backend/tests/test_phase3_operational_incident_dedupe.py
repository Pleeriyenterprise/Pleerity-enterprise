"""Phase 3: operational incident / ops email dedupe and recurrence metadata (additive only)."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from bson import ObjectId

import services.compliance_sla_monitor as compliance_sla_monitor_mod
from services.compliance_sla_monitor import (
    DEFAULT_COMPLIANCE_RECALC_ALERT_IDEMPOTENCY_COOLDOWN_SECONDS,
    _cooldown_seconds_for_email_idempotency,
    compliance_sla_alert_email_idempotency_key,
)
from services.sla_watchdog import _touch_persistent_incident_ticks


def test_compliance_sla_email_idempotency_key_scopes_per_property_alert_severity():
    t = datetime(2026, 6, 15, 10, 30, 0, tzinfo=timezone.utc)
    k1 = compliance_sla_alert_email_idempotency_key("prop-a", "PENDING_STUCK", "WARN", t)
    k2 = compliance_sla_alert_email_idempotency_key("prop-b", "PENDING_STUCK", "WARN", t)
    assert k1 != k2
    assert "prop-a" in k1 and "PENDING_STUCK" in k1 and "WARN" in k1
    assert "hash" not in k1.lower()


def test_compliance_sla_email_idempotency_key_same_logical_send_stable_in_cooldown_window():
    t = datetime(2026, 6, 15, 10, 30, 0, tzinfo=timezone.utc)
    k = compliance_sla_alert_email_idempotency_key("prop-x", "RUNNING_STUCK", "CRIT", t)
    assert k == compliance_sla_alert_email_idempotency_key("prop-x", "RUNNING_STUCK", "CRIT", t)


def test_compliance_sla_email_idempotency_key_changes_across_cooldown_chunks():
    t0 = datetime(1970, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    cd = _cooldown_seconds_for_email_idempotency()
    chunk_a = int(t0.timestamp() // cd)
    from datetime import timedelta

    t_far = t0 + timedelta(seconds=cd * 3)
    chunk_b = int(t_far.timestamp() // cd)
    assert chunk_a != chunk_b
    ka = compliance_sla_alert_email_idempotency_key("p", "T", "WARN", t0)
    kb = compliance_sla_alert_email_idempotency_key("p", "T", "WARN", t_far)
    assert ka != kb


def test_compliance_sla_email_idempotency_valid_cooldown_chunk_matches_formula():
    t = datetime(2026, 6, 15, 10, 30, 0, tzinfo=timezone.utc)
    cd = _cooldown_seconds_for_email_idempotency()
    assert type(cd) is int and cd > 0
    expected_chunk = int(t.timestamp() // cd)
    key = compliance_sla_alert_email_idempotency_key("prop-a", "PENDING_STUCK", "WARN", t)
    assert key.endswith(f"_{expected_chunk}")


def test_compliance_sla_email_idempotency_zero_cooldown_fallback(monkeypatch, caplog):
    monkeypatch.setattr(compliance_sla_monitor_mod, "ALERT_COOLDOWN_SECONDS", 0)
    t = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    expected_chunk = int(t.timestamp() // DEFAULT_COMPLIANCE_RECALC_ALERT_IDEMPOTENCY_COOLDOWN_SECONDS)
    with caplog.at_level("WARNING"):
        key = compliance_sla_alert_email_idempotency_key("p", "T", "WARN", t)
    assert key.endswith(f"_{expected_chunk}")
    assert "Invalid COMPLIANCE_RECALC_ALERT_COOLDOWN_SECONDS" in caplog.text


def test_compliance_sla_email_idempotency_negative_cooldown_fallback(monkeypatch, caplog):
    monkeypatch.setattr(compliance_sla_monitor_mod, "ALERT_COOLDOWN_SECONDS", -5)
    t = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    expected_chunk = int(t.timestamp() // DEFAULT_COMPLIANCE_RECALC_ALERT_IDEMPOTENCY_COOLDOWN_SECONDS)
    with caplog.at_level("WARNING"):
        key = compliance_sla_alert_email_idempotency_key("p", "T", "WARN", t)
    assert key.endswith(f"_{expected_chunk}")
    assert "Invalid COMPLIANCE_RECALC_ALERT_COOLDOWN_SECONDS" in caplog.text


def test_compliance_sla_email_idempotency_non_int_cooldown_fallback(monkeypatch, caplog):
    monkeypatch.setattr(compliance_sla_monitor_mod, "ALERT_COOLDOWN_SECONDS", 3.5)
    t = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    expected_chunk = int(t.timestamp() // DEFAULT_COMPLIANCE_RECALC_ALERT_IDEMPOTENCY_COOLDOWN_SECONDS)
    with caplog.at_level("WARNING"):
        key = compliance_sla_alert_email_idempotency_key("p", "T", "WARN", t)
    assert key.endswith(f"_{expected_chunk}")
    assert "Invalid COMPLIANCE_RECALC_ALERT_COOLDOWN_SECONDS" in caplog.text


def test_compliance_sla_email_idempotency_none_cooldown_fallback(monkeypatch, caplog):
    """Simulates an invalid runtime value (e.g. bad patch); env at import is always int()."""
    monkeypatch.setattr(compliance_sla_monitor_mod, "ALERT_COOLDOWN_SECONDS", None)
    t = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    expected_chunk = int(t.timestamp() // DEFAULT_COMPLIANCE_RECALC_ALERT_IDEMPOTENCY_COOLDOWN_SECONDS)
    with caplog.at_level("WARNING"):
        key = compliance_sla_alert_email_idempotency_key("p", "T", "WARN", t)
    assert key.endswith(f"_{expected_chunk}")
    assert "Invalid COMPLIANCE_RECALC_ALERT_COOLDOWN_SECONDS" in caplog.text


@pytest.mark.asyncio
async def test_touch_persistent_incident_ticks_increments_and_sets_snapshot():
    db = MagicMock()
    db.incidents = MagicMock()
    db.incidents.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
    oid = ObjectId()
    now = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)
    await _touch_persistent_incident_ticks(
        db,
        oid,
        now,
        snapshot={"last_watchdog_tick_reason": "unit_test"},
    )
    assert db.incidents.update_one.await_count == 1
    flt, upd = db.incidents.update_one.call_args[0]
    assert flt["_id"] == oid
    assert flt["status"] == "open"
    assert upd["$inc"]["metadata.sla_watchdog_condition_ticks"] == 1
    assert upd["$set"]["metadata.last_watchdog_tick_reason"] == "unit_test"
    assert upd["$set"]["updated_at"] == now.isoformat()


@pytest.mark.asyncio
async def test_risk_regen_monitor_ticks_when_incident_already_open(monkeypatch):
    from services import risk_signal_regen_alert_monitor as mod

    oid = ObjectId()
    incidents = MagicMock()
    incidents.find_one = AsyncMock(return_value={"_id": oid})
    incidents.update_one = AsyncMock()
    db = MagicMock()
    db.incidents = incidents

    monkeypatch.setattr(mod, "database", MagicMock(get_db=lambda: db))

    async def fake_resolve():
        return 0

    async def fake_summary(_limit):
        return {
            "attention_required": True,
            "counts_by_status": {"FAILED": 2},
            "recent_dead": [],
            "recent_failed": [],
            "oldest_pending_job": {},
            "sample_limit": 5,
        }

    monkeypatch.setattr(
        "services.incident_recovery.check_and_resolve_risk_regen_queue_incidents",
        fake_resolve,
    )
    monkeypatch.setattr(mod, "get_regen_queue_summary", fake_summary)
    monkeypatch.setattr(mod, "_admin_recipients", lambda: [])

    out = await mod.run_risk_signal_regen_alert_monitor()
    assert out.get("already_open") is True
    assert incidents.update_one.await_count == 1
    _flt, upd = incidents.update_one.call_args[0]
    assert upd["$inc"]["metadata.regen_alert_monitor_ticks"] == 1
    assert upd["$set"]["metadata.counts_by_status"] == {"FAILED": 2}
