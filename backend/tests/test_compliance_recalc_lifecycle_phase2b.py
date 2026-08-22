"""Phase 2B: PARKED queue state, lifecycle restoration, presentation, invariants."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.account_background_runtime_authority import BackgroundJobDecision, BackgroundRuntimeDecision
from services.compliance_recalc_lifecycle_transition import (
    apply_lifecycle_to_client_recalc_queue,
    enqueue_or_park_compliance_recalc,
    park_claimed_ineligible_job,
    park_queue_row,
    restore_client_compliance_recalc,
    restore_parked_debt_for_eligible_clients,
    terminalize_queue_row,
)
from services.compliance_recalc_phase2b_reconciliation import (
    BUCKET_BECOME_PARKED,
    BUCKET_BECOME_TERMINAL,
    BUCKET_GENUINE_ACTIVE_FAILURE,
    BUCKET_NEED_RESTORATION,
    BUCKET_REMAIN_EXECUTABLE_PENDING,
    BUCKET_SEPARATE_INVESTIGATION,
    classify_queue_row_under_phase2b,
)
from services.compliance_recalc_queue import (
    STATUS_DEAD,
    STATUS_DONE,
    STATUS_FAILED,
    STATUS_PARKED,
    STATUS_PENDING,
    STATUS_RUNNING,
)
from services.compliance_recalc_sla_eligibility import (
    ComplianceRecalcSlaClass,
    ComplianceRecalcSlaEligibility,
)
from services.compliance_recalc_state import (
    INVARIANT_DONE_QUEUE_PENDING_TRUE,
    INVARIANT_PARKED_QUEUE_ACTIVE_PROPERTY,
    INVARIANT_PENDING_FALSE_ACTIVE_STATE,
    INVARIANT_PENDING_QUEUE_PARKED_PROPERTY,
    INVARIANT_TERMINAL_QUEUE_ACTIVE_PROPERTY,
    RECALC_STATE_ACTIVE_PENDING,
    RECALC_STATE_PARKED,
    classify_done_pending_without_outstanding_debt,
    classify_projection_invariants,
    is_recalc_active_pending,
    is_recalc_parked,
)
from services.scoring_semantics_v1 import (
    SCORE_STATUS_CALCULATING,
    SCORE_STATUS_PARTIAL,
    SCORE_STATUS_RECONCILIATION_REQUIRED,
    SCORE_STATUS_STALE,
    aggregate_persisted_portfolio_headline,
    resolve_property_score_status,
    resolve_property_score_status_message,
)


def _bg(decision: BackgroundJobDecision, lifecycle: str, allowed_reason: str = "test") -> BackgroundRuntimeDecision:
    return BackgroundRuntimeDecision(
        decision=decision,
        client_id="c1",
        job_type="compliance_recalc_queue",
        lifecycle_state=lifecycle,
        portal_mode="CLIENT",
        background_policy_key="queue_processing",
        background_policy_action=decision.value,
        reason=allowed_reason,
        runtime_version=1,
    )


def _elig(sla: ComplianceRecalcSlaClass, lifecycle: str, decision: str) -> ComplianceRecalcSlaEligibility:
    return ComplianceRecalcSlaEligibility(
        sla_class=sla,
        lifecycle_state=lifecycle,
        decision=decision,
        reason="test",
    )


def _match(doc, query):
    if not query:
        return True
    for k, v in query.items():
        if k == "$or":
            if not any(_match(doc, clause) for clause in v):
                return False
            continue
        dv = doc.get(k)
        if isinstance(v, dict):
            if "$in" in v and dv not in v["$in"]:
                return False
            if "$lte" in v and not (dv is not None and dv <= v["$lte"]):
                return False
        elif dv != v:
            return False
    return True


class _UpdResult:
    def __init__(self, matched=1, modified=1):
        self.matched_count = matched
        self.modified_count = modified


class FakeColl:
    def __init__(self, rows=None):
        self.rows = [dict(r) for r in (rows or [])]

    async def find_one(self, q, proj=None):
        for r in self.rows:
            if _match(r, q):
                return dict(r)
        return None

    async def update_one(self, q, upd):
        for r in self.rows:
            if _match(r, q):
                if "$set" in upd:
                    r.update(upd["$set"])
                if "$unset" in upd:
                    for k in upd["$unset"]:
                        r.pop(k, None)
                if "$inc" in upd:
                    for k, n in upd["$inc"].items():
                        r[k] = int(r.get(k) or 0) + n
                return _UpdResult(1, 1)
        return _UpdResult(0, 0)

    async def insert_one(self, doc):
        d = dict(doc)
        if "_id" not in d:
            d["_id"] = f"id-{len(self.rows)}"
        self.rows.append(d)
        return SimpleNamespace(inserted_id=d["_id"])

    def find(self, q=None, proj=None):
        q = q or {}
        matched = [dict(r) for r in self.rows if _match(r, q)]
        return FakeCursor(matched)


class FakeCursor:
    def __init__(self, items):
        self.items = items

    def sort(self, *a, **k):
        return self

    def limit(self, n):
        self.items = self.items[:n]
        return self

    async def to_list(self, n):
        return self.items[:n]


class FakeDB:
    def __init__(self, queue=None, props=None):
        self.compliance_recalc_queue = FakeColl(queue)
        self.properties = FakeColl(props)


# --- Invariants ---


def test_invariants_parked_queue_active_property():
    codes = classify_projection_invariants(
        queue_status=STATUS_PARKED,
        prop={"compliance_score_pending": True, "compliance_score_recalc_state": RECALC_STATE_ACTIVE_PENDING},
    )
    assert INVARIANT_PARKED_QUEUE_ACTIVE_PROPERTY in codes


def test_invariants_pending_queue_parked_property():
    codes = classify_projection_invariants(
        queue_status=STATUS_PENDING,
        prop={"compliance_score_pending": True, "compliance_score_recalc_state": RECALC_STATE_PARKED},
    )
    assert INVARIANT_PENDING_QUEUE_PARKED_PROPERTY in codes


def test_invariants_pending_false_active_state():
    codes = classify_projection_invariants(
        queue_status=STATUS_PENDING,
        prop={"compliance_score_pending": False, "compliance_score_recalc_state": RECALC_STATE_ACTIVE_PENDING},
    )
    assert INVARIANT_PENDING_FALSE_ACTIVE_STATE in codes


def test_invariants_dead_queue_active_property():
    codes = classify_projection_invariants(
        queue_status=STATUS_DEAD,
        prop={"compliance_score_pending": True, "compliance_score_recalc_state": RECALC_STATE_ACTIVE_PENDING},
    )
    assert INVARIANT_TERMINAL_QUEUE_ACTIVE_PROPERTY in codes


def test_invariants_done_pending_without_other_debt():
    prop = {"compliance_score_pending": True, "compliance_score_recalc_state": RECALC_STATE_ACTIVE_PENDING}
    assert INVARIANT_DONE_QUEUE_PENDING_TRUE in classify_done_pending_without_outstanding_debt(
        queue_statuses=["DONE"], prop=prop
    )
    assert classify_done_pending_without_outstanding_debt(
        queue_statuses=["DONE", "FAILED"], prop=prop
    ) == []


def test_legacy_pending_is_active_pending():
    prop = {"compliance_score_pending": True}
    assert is_recalc_active_pending(prop)
    assert not is_recalc_parked(prop)


# --- Presentation ---


def test_parked_with_score_is_stale_not_calculating():
    prop = {
        "compliance_score": 72,
        "compliance_score_pending": True,
        "compliance_score_recalc_state": RECALC_STATE_PARKED,
        "compliance_last_calculated_at": "2026-08-01T00:00:00+00:00",
    }
    assert resolve_property_score_status(prop) == SCORE_STATUS_STALE
    msg = resolve_property_score_status_message(prop)
    assert msg and "paused" in msg.lower()


def test_parked_without_score_is_reconciliation_required():
    prop = {
        "compliance_score": None,
        "compliance_score_pending": True,
        "compliance_score_recalc_state": RECALC_STATE_PARKED,
    }
    assert resolve_property_score_status(prop) == SCORE_STATUS_RECONCILIATION_REQUIRED


def test_mixed_portfolio_current_active_parked():
    props = [
        {"compliance_score": 80, "compliance_score_pending": False, "compliance_last_calculated_at": "2026-08-01T00:00:00+00:00"},
        {
            "compliance_score": 70,
            "compliance_score_pending": True,
            "compliance_score_recalc_state": RECALC_STATE_ACTIVE_PENDING,
            "compliance_last_calculated_at": "2026-08-01T00:00:00+00:00",
        },
        {
            "compliance_score": 60,
            "compliance_score_pending": True,
            "compliance_score_recalc_state": RECALC_STATE_PARKED,
            "compliance_last_calculated_at": "2026-08-01T00:00:00+00:00",
        },
        {"compliance_score": None, "compliance_score_pending": True, "compliance_score_recalc_state": RECALC_STATE_PARKED},
    ]
    h = aggregate_persisted_portfolio_headline(props)
    assert h["score_status"] in (SCORE_STATUS_PARTIAL, SCORE_STATUS_STALE)
    assert h["score_status"] != SCORE_STATUS_CALCULATING
    assert h["portfolio_score"] is not None
    assert "paused" in (h.get("score_status_message") or "").lower() or "processing" in (
        h.get("score_status_message") or ""
    ).lower()


def test_parked_only_portfolio_with_scores_is_not_calculating():
    props = [
        {
            "compliance_score": 55,
            "compliance_score_pending": True,
            "compliance_score_recalc_state": RECALC_STATE_PARKED,
            "compliance_last_calculated_at": "2026-08-01T00:00:00+00:00",
        }
    ]
    h = aggregate_persisted_portfolio_headline(props)
    assert h["score_status"] in (SCORE_STATUS_STALE, SCORE_STATUS_PARTIAL)
    assert h["score_status"] != SCORE_STATUS_CALCULATING


# --- Queue transitions ---


@pytest.mark.asyncio
async def test_pending_parks_on_payment_pending():
    job = {"_id": "j1", "property_id": "p1", "client_id": "c1", "status": STATUS_PENDING, "attempts": 0}
    db = FakeDB(queue=[job], props=[{"property_id": "p1", "compliance_score_pending": True}])
    outcome = await park_queue_row(db, job, _bg(BackgroundJobDecision.SKIP, "PAYMENT_PENDING"))
    assert outcome == "parked"
    assert db.compliance_recalc_queue.rows[0]["status"] == STATUS_PARKED
    assert db.properties.rows[0]["compliance_score_recalc_state"] == RECALC_STATE_PARKED
    assert db.properties.rows[0]["compliance_score_pending"] is True


@pytest.mark.asyncio
async def test_park_is_idempotent():
    job = {"_id": "j1", "property_id": "p1", "status": STATUS_PARKED}
    db = FakeDB(queue=[job], props=[{"property_id": "p1"}])
    first = await park_queue_row(db, job, _bg(BackgroundJobDecision.PAUSE, "SUSPENDED"))
    second = await park_queue_row(db, db.compliance_recalc_queue.rows[0], _bg(BackgroundJobDecision.PAUSE, "SUSPENDED"))
    assert first == "already_parked"
    assert second == "already_parked"
    assert len(db.compliance_recalc_queue.rows) == 1


@pytest.mark.asyncio
async def test_failed_parks_retaining_error():
    job = {
        "_id": "j1",
        "property_id": "p1",
        "status": STATUS_FAILED,
        "last_error": "boom",
        "attempts": 2,
    }
    db = FakeDB(queue=[job], props=[{"property_id": "p1"}])
    outcome = await park_queue_row(db, job, _bg(BackgroundJobDecision.PAUSE, "SUSPENDED"))
    assert outcome == "parked"
    row = db.compliance_recalc_queue.rows[0]
    assert row["status"] == STATUS_PARKED
    assert row["last_error"] == "boom"
    assert row["attempts"] == 2
    assert row["parked_from_status"] == STATUS_FAILED


@pytest.mark.asyncio
async def test_running_drains_on_consumer_park():
    job = {"_id": "j1", "property_id": "p1", "status": STATUS_RUNNING}
    db = FakeDB(queue=[job], props=[{"property_id": "p1"}])
    outcome = await park_queue_row(db, job, _bg(BackgroundJobDecision.PAUSE, "SUSPENDED"))
    assert outcome == "drain_running"
    assert db.compliance_recalc_queue.rows[0]["status"] == STATUS_RUNNING


@pytest.mark.asyncio
async def test_claimed_running_parks_instead_of_reschedule():
    job = {"_id": "j1", "property_id": "p1", "status": STATUS_RUNNING}
    db = FakeDB(queue=[job], props=[{"property_id": "p1"}])
    outcome = await park_claimed_ineligible_job(db, job, _bg(BackgroundJobDecision.SKIP, "PAYMENT_PENDING"))
    assert outcome == "parked"
    assert db.compliance_recalc_queue.rows[0]["status"] == STATUS_PARKED


@pytest.mark.asyncio
async def test_active_to_deleted_terminalizes_pending_and_parked():
    db = FakeDB(
        queue=[
            {"_id": "a", "property_id": "p1", "client_id": "c1", "status": STATUS_PENDING},
            {"_id": "b", "property_id": "p2", "client_id": "c1", "status": STATUS_PARKED},
        ],
        props=[
            {"property_id": "p1", "client_id": "c1", "compliance_score_pending": True},
            {"property_id": "p2", "client_id": "c1", "compliance_score_pending": True},
        ],
    )
    with patch(
        "services.compliance_recalc_lifecycle_transition.evaluate_background_runtime",
        AsyncMock(return_value=_bg(BackgroundJobDecision.TERMINATE, "ACCOUNT_DELETED")),
    ), patch(
        "services.compliance_recalc_lifecycle_transition.resolve_compliance_recalc_sla_eligibility",
        AsyncMock(return_value=_elig(ComplianceRecalcSlaClass.TERMINATED, "ACCOUNT_DELETED", "TERMINATE")),
    ):
        stats = await apply_lifecycle_to_client_recalc_queue(db, "c1")
    assert stats["terminalized"] >= 1
    assert all(r["status"] == STATUS_DEAD for r in db.compliance_recalc_queue.rows)


@pytest.mark.asyncio
async def test_restore_parked_debt_safety_net_without_lifecycle_change():
    db = FakeDB(
        queue=[{"_id": "j1", "property_id": "p1", "client_id": "c1", "status": STATUS_PARKED, "correlation_id": "x"}],
        props=[{"property_id": "p1", "client_id": "c1", "compliance_score_pending": True, "compliance_score_recalc_state": RECALC_STATE_PARKED}],
    )
    with patch(
        "services.compliance_recalc_lifecycle_transition.resolve_compliance_recalc_sla_eligibility",
        AsyncMock(return_value=_elig(ComplianceRecalcSlaClass.ACTIONABLE, "ACTIVE", "CONTINUE")),
    ), patch(
        "services.compliance_recalc_lifecycle_transition.evaluate_background_runtime",
        AsyncMock(return_value=_bg(BackgroundJobDecision.CONTINUE, "ACTIVE")),
    ):
        stats = await restore_parked_debt_for_eligible_clients(db)
    assert stats["clients_scanned"] == 1
    assert stats["clients_restored"] == 1
    assert stats["rows_restored"] == 1
    assert db.compliance_recalc_queue.rows[0]["status"] == STATUS_PENDING


@pytest.mark.asyncio
async def test_restore_parked_debt_safety_net_skips_ineligible():
    db = FakeDB(
        queue=[{"_id": "j1", "property_id": "p1", "client_id": "c1", "status": STATUS_PARKED}],
        props=[{"property_id": "p1", "client_id": "c1", "compliance_score_pending": True, "compliance_score_recalc_state": RECALC_STATE_PARKED}],
    )
    with patch(
        "services.compliance_recalc_lifecycle_transition.resolve_compliance_recalc_sla_eligibility",
        AsyncMock(return_value=_elig(ComplianceRecalcSlaClass.LIFECYCLE_SUPPRESSED, "SUSPENDED", "PAUSE")),
    ):
        stats = await restore_parked_debt_for_eligible_clients(db)
    assert stats["skipped_ineligible"] == 1
    assert stats["rows_restored"] == 0
    assert db.compliance_recalc_queue.rows[0]["status"] == STATUS_PARKED


@pytest.mark.asyncio
async def test_restore_parked_to_pending():
    db = FakeDB(
        queue=[{"_id": "j1", "property_id": "p1", "client_id": "c1", "status": STATUS_PARKED, "correlation_id": "x"}],
        props=[{"property_id": "p1", "client_id": "c1", "compliance_score_pending": True, "compliance_score_recalc_state": RECALC_STATE_PARKED}],
    )
    with patch(
        "services.compliance_recalc_lifecycle_transition.evaluate_background_runtime",
        AsyncMock(return_value=_bg(BackgroundJobDecision.CONTINUE, "ACTIVE")),
    ):
        stats = await restore_client_compliance_recalc(db, "c1")
    assert stats["restored"] == 1
    assert db.compliance_recalc_queue.rows[0]["status"] == STATUS_PENDING
    assert db.properties.rows[0]["compliance_score_recalc_state"] == RECALC_STATE_ACTIVE_PENDING


@pytest.mark.asyncio
async def test_duplicate_restore_does_not_insert_second_row():
    db = FakeDB(
        queue=[{"_id": "j1", "property_id": "p1", "client_id": "c1", "status": STATUS_PENDING}],
        props=[{"property_id": "p1", "client_id": "c1", "compliance_score_pending": True, "compliance_score_recalc_state": RECALC_STATE_PARKED}],
    )
    with patch(
        "services.compliance_recalc_lifecycle_transition.evaluate_background_runtime",
        AsyncMock(return_value=_bg(BackgroundJobDecision.CONTINUE, "ACTIVE")),
    ):
        stats = await restore_client_compliance_recalc(db, "c1")
    assert stats["restored"] == 0
    assert stats["restoration_enqueued"] == 0
    assert len(db.compliance_recalc_queue.rows) == 1


@pytest.mark.asyncio
async def test_restore_skips_dead_terminal_rows():
    db = FakeDB(
        queue=[{"_id": "j1", "property_id": "p1", "client_id": "c1", "status": STATUS_DEAD}],
        props=[{"property_id": "p1", "client_id": "c1", "compliance_score_pending": True, "compliance_score_recalc_state": RECALC_STATE_PARKED}],
    )
    with patch(
        "services.compliance_recalc_lifecycle_transition.evaluate_background_runtime",
        AsyncMock(return_value=_bg(BackgroundJobDecision.CONTINUE, "ACTIVE")),
    ):
        stats = await restore_client_compliance_recalc(db, "c1")
    assert stats["restoration_enqueued"] == 0
    assert db.compliance_recalc_queue.rows[0]["status"] == STATUS_DEAD


@pytest.mark.asyncio
async def test_mutation_while_ineligible_inserts_parked_not_pending():
    db = FakeDB(queue=[], props=[{"property_id": "p1", "client_id": "c1"}])
    with patch(
        "services.compliance_recalc_lifecycle_transition.resolve_compliance_recalc_sla_eligibility",
        AsyncMock(return_value=_elig(ComplianceRecalcSlaClass.LIFECYCLE_SUPPRESSED, "PAYMENT_PENDING", "SKIP")),
    ), patch(
        "services.compliance_recalc_lifecycle_transition.evaluate_background_runtime",
        AsyncMock(return_value=_bg(BackgroundJobDecision.SKIP, "PAYMENT_PENDING")),
    ):
        result = await enqueue_or_park_compliance_recalc(
            db,
            property_id="p1",
            client_id="c1",
            trigger_reason="DOC_UPLOADED",
            actor_type="CLIENT",
            correlation_id="DOC:p1",
        )
    assert result.parked is True
    assert result.enqueued is False
    assert db.compliance_recalc_queue.rows[0]["status"] == STATUS_PARKED
    assert db.properties.rows[0]["compliance_score_recalc_state"] == RECALC_STATE_PARKED


@pytest.mark.asyncio
async def test_lazy_backfill_repeat_does_not_duplicate_parked():
    existing = {
        "_id": "j1",
        "property_id": "p1",
        "client_id": "c1",
        "correlation_id": "LAZY_BACKFILL:p1",
        "status": STATUS_PARKED,
    }
    db = FakeDB(queue=[existing], props=[{"property_id": "p1", "client_id": "c1"}])
    with patch(
        "services.compliance_recalc_lifecycle_transition.resolve_compliance_recalc_sla_eligibility",
        AsyncMock(return_value=_elig(ComplianceRecalcSlaClass.LIFECYCLE_SUPPRESSED, "SUSPENDED", "PAUSE")),
    ), patch(
        "services.compliance_recalc_lifecycle_transition.evaluate_background_runtime",
        AsyncMock(return_value=_bg(BackgroundJobDecision.PAUSE, "SUSPENDED")),
    ):
        await enqueue_or_park_compliance_recalc(
            db,
            property_id="p1",
            client_id="c1",
            trigger_reason="LAZY_BACKFILL",
            actor_type="SYSTEM",
            correlation_id="LAZY_BACKFILL:p1",
        )
        await enqueue_or_park_compliance_recalc(
            db,
            property_id="p1",
            client_id="c1",
            trigger_reason="LAZY_BACKFILL",
            actor_type="SYSTEM",
            correlation_id="LAZY_BACKFILL:p1",
        )
    assert len(db.compliance_recalc_queue.rows) == 1
    assert db.compliance_recalc_queue.rows[0]["status"] == STATUS_PARKED


@pytest.mark.asyncio
async def test_admin_override_enqueues_and_audits():
    from services.compliance_recalc_lifecycle_transition import enqueue_compliance_recalc_admin_override

    enqueue = AsyncMock(return_value=True)
    audit = AsyncMock()
    fake_db = FakeDB(props=[{"property_id": "p1"}])
    with patch("database.database.get_db", return_value=fake_db), patch(
        "services.compliance_recalc_lifecycle_transition.evaluate_background_runtime",
        AsyncMock(return_value=_bg(BackgroundJobDecision.SKIP, "PAYMENT_PENDING")),
    ), patch(
        "services.compliance_recalc_lifecycle_transition.resolve_compliance_recalc_sla_eligibility",
        AsyncMock(return_value=_elig(ComplianceRecalcSlaClass.LIFECYCLE_SUPPRESSED, "PAYMENT_PENDING", "SKIP")),
    ), patch(
        "services.compliance_recalc_lifecycle_transition.enqueue_compliance_recalc",
        enqueue,
    ), patch(
        "utils.audit.create_audit_log",
        audit,
    ):
        await enqueue_compliance_recalc_admin_override(
            property_id="p1",
            client_id="c1",
            trigger_reason="ADMIN_MANUAL_JOB",
            actor_id="admin-1",
            correlation_id="admin:p1",
            override_reason="ops",
        )
    enqueue.assert_awaited_once()
    audit.assert_awaited()
    meta = audit.await_args.kwargs.get("metadata")
    if meta is None and audit.await_args.args:
        # positional create_audit_log(..., metadata=)
        meta = audit.await_args.kwargs.get("metadata")
    assert meta["kind"] == "compliance_recalc_admin_override"
    assert meta["would_suppress"] is True
    assert meta["lifecycle_state"] == "PAYMENT_PENDING"


# --- SLA: parked does not page ---


@pytest.mark.asyncio
async def test_sla_skips_parked_property_pending(monkeypatch):
    from datetime import datetime, timezone, timedelta
    from services import compliance_sla_monitor as mon

    mock_now = datetime(2026, 2, 12, 10, 0, tzinfo=timezone.utc)
    old = (mock_now - timedelta(hours=12)).isoformat()
    parked_prop = {
        "property_id": "p-park",
        "client_id": "c-park",
        "compliance_score_pending": True,
        "compliance_score_recalc_state": RECALC_STATE_PARKED,
        "compliance_last_calculated_at": old,
    }

    class AsyncCursor:
        def __init__(self, items):
            self._items = list(items)

        def __aiter__(self):
            return self

        async def __anext__(self):
            if not self._items:
                raise StopAsyncIteration
            return self._items.pop(0)

    db = MagicMock()
    db.compliance_recalc_queue.find = MagicMock(return_value=AsyncCursor([]))
    db.properties.find = MagicMock(return_value=AsyncCursor([parked_prop]))
    db.compliance_sla_alerts.find_one = AsyncMock(return_value=None)
    db.compliance_sla_alerts.update_one = AsyncMock()
    db.compliance_sla_alerts.find = MagicMock(
        return_value=SimpleNamespace(to_list=AsyncMock(return_value=[]))
    )

    async def _elig_fn(db_, client_id, cache=None):
        return _elig(ComplianceRecalcSlaClass.ACTIONABLE, "ACTIVE", "CONTINUE")

    with patch("database.database.get_db", return_value=db), patch(
        "services.compliance_sla_monitor.resolve_compliance_recalc_sla_eligibility",
        side_effect=_elig_fn,
    ), patch("services.compliance_sla_monitor.create_audit_log", AsyncMock()), patch(
        "services.compliance_sla_monitor.datetime"
    ) as dt:
        dt.now = MagicMock(return_value=mock_now)
        dt.side_effect = lambda *a, **k: datetime(*a, **k)
        stats = await mon.run_compliance_recalc_sla_monitor()
    assert stats["breaches"] == 0


# --- Phase 2A regression: automatic gate unchanged ---


@pytest.mark.asyncio
async def test_phase2a_automatic_gate_still_skips_ineligible():
    from services.compliance_recalc_sla_eligibility import enqueue_automatic_compliance_recalc_if_eligible

    enqueue = AsyncMock()
    with patch(
        "services.compliance_recalc_sla_eligibility.resolve_compliance_recalc_sla_eligibility",
        AsyncMock(return_value=_elig(ComplianceRecalcSlaClass.LIFECYCLE_SUPPRESSED, "PAYMENT_PENDING", "SKIP")),
    ), patch("services.compliance_recalc_queue.enqueue_compliance_recalc", enqueue):
        result = await enqueue_automatic_compliance_recalc_if_eligible(
            MagicMock(),
            property_id="p1",
            client_id="c1",
            trigger_reason="EXPIRY_JOB",
            actor_type="SYSTEM",
        )
    assert result.enqueued is False
    enqueue.assert_not_called()


# --- Dry-run buckets ---


def test_dry_run_pending_ineligible_becomes_parked():
    assert (
        classify_queue_row_under_phase2b(status="PENDING", sla_class="LIFECYCLE_SUPPRESSED")
        == BUCKET_BECOME_PARKED
    )


def test_dry_run_pending_active_remains_executable():
    assert (
        classify_queue_row_under_phase2b(status="PENDING", sla_class="ACTIONABLE")
        == BUCKET_REMAIN_EXECUTABLE_PENDING
    )


def test_dry_run_deleted_becomes_terminal():
    assert classify_queue_row_under_phase2b(status="PENDING", sla_class="TERMINATED") == BUCKET_BECOME_TERMINAL


def test_dry_run_ineligible_failed_with_date_error_parks():
    assert (
        classify_queue_row_under_phase2b(
            status="FAILED",
            sla_class="LIFECYCLE_SUPPRESSED",
            last_error="date value out of range",
        )
        == BUCKET_BECOME_PARKED
    )
    assert (
        classify_queue_row_under_phase2b(
            status="FAILED",
            sla_class="ACTIONABLE",
            last_error="date value out of range",
        )
        == BUCKET_SEPARATE_INVESTIGATION
    )


def test_dry_run_active_failed_is_genuine():
    assert (
        classify_queue_row_under_phase2b(status="FAILED", sla_class="ACTIONABLE", last_error="timeout")
        == BUCKET_GENUINE_ACTIVE_FAILURE
    )


def test_dry_run_parked_on_active_needs_restoration():
    assert classify_queue_row_under_phase2b(status="PARKED", sla_class="ACTIONABLE") == BUCKET_NEED_RESTORATION
