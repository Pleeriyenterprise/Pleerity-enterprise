"""Phase 2A: lifecycle-aware automatic compliance recalc enqueue prevention."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.compliance_recalc_sla_eligibility import (
    AutomaticEnqueueAttempt,
    ComplianceRecalcSlaClass,
    ComplianceRecalcSlaEligibility,
    enqueue_automatic_compliance_recalc_if_eligible,
)


def _elig(sla_class, lifecycle, decision="CONTINUE"):
    return ComplianceRecalcSlaEligibility(
        sla_class=sla_class,
        lifecycle_state=lifecycle,
        decision=decision,
        reason=f"test_{lifecycle}",
    )


ACTIONABLE = _elig(ComplianceRecalcSlaClass.ACTIONABLE, "ACTIVE", "CONTINUE")
TRIAL = _elig(ComplianceRecalcSlaClass.ACTIONABLE, "TRIAL", "CONTINUE")
GRACE = _elig(ComplianceRecalcSlaClass.ACTIONABLE, "GRACE_PERIOD", "CONTINUE")
PAYMENT_PENDING = _elig(ComplianceRecalcSlaClass.LIFECYCLE_SUPPRESSED, "PAYMENT_PENDING", "SKIP")
SUSPENDED = _elig(ComplianceRecalcSlaClass.LIFECYCLE_SUPPRESSED, "SUSPENDED", "PAUSE")
CANCELLED = _elig(ComplianceRecalcSlaClass.LIFECYCLE_SUPPRESSED, "CANCELLED_IMMEDIATE", "PAUSE")
DELETED = _elig(ComplianceRecalcSlaClass.TERMINATED, "ACCOUNT_DELETED", "TERMINATE")
ARCHIVED = _elig(ComplianceRecalcSlaClass.TERMINATED, "ARCHIVED", "TERMINATE")
UNKNOWN = _elig(ComplianceRecalcSlaClass.UNKNOWN_SAFE_SKIP, "UNKNOWN", "SKIP")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "eligibility,expect_enqueue,expect_outcome",
    [
        (ACTIONABLE, True, "enqueued"),
        (TRIAL, True, "enqueued"),
        (GRACE, True, "enqueued"),
        (PAYMENT_PENDING, False, "lifecycle_suppressed"),
        (SUSPENDED, False, "lifecycle_suppressed"),
        (CANCELLED, False, "lifecycle_suppressed"),
        (DELETED, False, "terminal_skipped"),
        (ARCHIVED, False, "terminal_skipped"),
        (UNKNOWN, False, "unknown_safe_skip"),
    ],
)
async def test_automatic_enqueue_gate_matrix(eligibility, expect_enqueue, expect_outcome):
    enqueue = AsyncMock(return_value=True)
    async def _resolve(db, client_id, cache=None):
        return eligibility

    with patch(
        "services.compliance_recalc_sla_eligibility.resolve_compliance_recalc_sla_eligibility",
        side_effect=_resolve,
    ):
        with patch(
            "services.compliance_recalc_queue.enqueue_compliance_recalc",
            enqueue,
        ):
            result = await enqueue_automatic_compliance_recalc_if_eligible(
                MagicMock(),
                property_id="p1",
                client_id="c1",
                trigger_reason="SCHEDULED_PROPERTY_BATCH",
                actor_type="SYSTEM",
            )
    assert result.outcome == expect_outcome
    assert result.enqueued is (expect_enqueue and expect_outcome == "enqueued")
    if expect_enqueue:
        enqueue.assert_awaited_once()
    else:
        enqueue.assert_not_called()


@pytest.mark.asyncio
async def test_ineligible_does_not_rewrite_existing_queue_row():
    enqueue = AsyncMock()
    async def _resolve(db, client_id, cache=None):
        return PAYMENT_PENDING

    with patch(
        "services.compliance_recalc_sla_eligibility.resolve_compliance_recalc_sla_eligibility",
        side_effect=_resolve,
    ):
        with patch("services.compliance_recalc_queue.enqueue_compliance_recalc", enqueue):
            result = await enqueue_automatic_compliance_recalc_if_eligible(
                MagicMock(),
                property_id="p-existing",
                client_id="c-pay",
                trigger_reason="EXPIRY_JOB",
                actor_type="SYSTEM",
            )
    assert result.enqueued is False
    enqueue.assert_not_called()


@pytest.mark.asyncio
async def test_recovery_payment_pending_to_active_allows_new_enqueue():
    state = {"elig": PAYMENT_PENDING}

    async def _resolve(db, client_id, cache=None):
        return state["elig"]

    enqueue = AsyncMock(return_value=True)
    with patch(
        "services.compliance_recalc_sla_eligibility.resolve_compliance_recalc_sla_eligibility",
        side_effect=_resolve,
    ):
        with patch("services.compliance_recalc_queue.enqueue_compliance_recalc", enqueue):
            first = await enqueue_automatic_compliance_recalc_if_eligible(
                MagicMock(),
                property_id="p1",
                client_id="c1",
                trigger_reason="SCHEDULED_PROPERTY_BATCH",
                actor_type="SYSTEM",
            )
            state["elig"] = ACTIONABLE
            second = await enqueue_automatic_compliance_recalc_if_eligible(
                MagicMock(),
                property_id="p1",
                client_id="c1",
                trigger_reason="SCHEDULED_PROPERTY_BATCH",
                actor_type="SYSTEM",
            )
    assert first.outcome == "lifecycle_suppressed"
    assert second.outcome == "enqueued"
    assert enqueue.await_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("start", [SUSPENDED, UNKNOWN])
async def test_recovery_suspended_and_unknown_to_active(start):
    state = {"elig": start}

    async def _resolve(db, client_id, cache=None):
        return state["elig"]

    enqueue = AsyncMock(return_value=True)
    with patch(
        "services.compliance_recalc_sla_eligibility.resolve_compliance_recalc_sla_eligibility",
        side_effect=_resolve,
    ):
        with patch("services.compliance_recalc_queue.enqueue_compliance_recalc", enqueue):
            blocked = await enqueue_automatic_compliance_recalc_if_eligible(
                MagicMock(),
                property_id="p1",
                client_id="c1",
                trigger_reason="EXPIRY_JOB",
                actor_type="SYSTEM",
            )
            state["elig"] = ACTIONABLE
            allowed = await enqueue_automatic_compliance_recalc_if_eligible(
                MagicMock(),
                property_id="p1",
                client_id="c1",
                trigger_reason="EXPIRY_JOB",
                actor_type="SYSTEM",
            )
    assert blocked.enqueued is False
    assert allowed.enqueued is True
    assert enqueue.await_count == 1


@pytest.mark.asyncio
async def test_eligible_duplicate_is_deduplicated_not_suppressed():
    enqueue = AsyncMock(return_value=False)

    async def _resolve(db, client_id, cache=None):
        return ACTIONABLE

    with patch(
        "services.compliance_recalc_sla_eligibility.resolve_compliance_recalc_sla_eligibility",
        side_effect=_resolve,
    ):
        with patch("services.compliance_recalc_queue.enqueue_compliance_recalc", enqueue):
            result = await enqueue_automatic_compliance_recalc_if_eligible(
                MagicMock(),
                property_id="p1",
                client_id="c1",
                trigger_reason="SCHEDULED_PROPERTY_BATCH",
                actor_type="SYSTEM",
            )
    assert result.outcome == "deduplicated"
    assert result.enqueued is False
    enqueue.assert_awaited_once()


class _AsyncListCursor:
    def __init__(self, items):
        self._items = list(items)

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._items:
            raise StopAsyncIteration
        return self._items.pop(0)


@pytest.mark.asyncio
async def test_scheduled_batch_skips_ineligible_and_continues_neighbours():
    from job_runner import run_compliance_recalc_enqueue_property

    props = [
        {"property_id": "p-pay", "client_id": "c-pay"},
        {"property_id": "p-act", "client_id": "c-act"},
    ]

    async def _resolve(db, client_id, cache=None):
        return PAYMENT_PENDING if client_id == "c-pay" else ACTIONABLE

    enqueue = AsyncMock(return_value=True)
    db = MagicMock()
    db.properties.count_documents = AsyncMock(return_value=2)

    with patch("database.database.get_db", return_value=db):
        with patch("job_runner._fetch_properties_batch_round_robin", new_callable=AsyncMock, return_value=props):
            with patch(
                "services.compliance_recalc_sla_eligibility.resolve_compliance_recalc_sla_eligibility",
                side_effect=_resolve,
            ):
                with patch("services.compliance_recalc_queue.enqueue_compliance_recalc", enqueue):
                    result = await run_compliance_recalc_enqueue_property()

    assert result["count"] == 1
    om = result["outcome_metrics"]
    assert om["scanned"] == 2
    assert om["enqueued"] == 1
    assert om["lifecycle_suppressed"] == 1
    assert om["eligible"] == 1
    assert enqueue.await_count == 1
    assert enqueue.await_args.kwargs["property_id"] == "p-act"


@pytest.mark.asyncio
async def test_scheduled_batch_one_error_does_not_abort_batch():
    from job_runner import run_compliance_recalc_enqueue_property

    props = [
        {"property_id": "p-bad", "client_id": "c-bad"},
        {"property_id": "p-ok", "client_id": "c-ok"},
    ]

    async def _resolve(db, client_id, cache=None):
        if client_id == "c-bad":
            raise RuntimeError("boom")
        return ACTIONABLE

    enqueue = AsyncMock(return_value=True)
    db = MagicMock()
    db.properties.count_documents = AsyncMock(return_value=2)

    with patch("database.database.get_db", return_value=db):
        with patch("job_runner._fetch_properties_batch_round_robin", new_callable=AsyncMock, return_value=props):
            with patch(
                "services.compliance_recalc_sla_eligibility.resolve_compliance_recalc_sla_eligibility",
                side_effect=_resolve,
            ):
                with patch("services.compliance_recalc_queue.enqueue_compliance_recalc", enqueue):
                    result = await run_compliance_recalc_enqueue_property()

    assert result["count"] == 1
    assert result["outcome_metrics"]["errors"] == 1
    enqueue.assert_awaited_once()


@pytest.mark.asyncio
async def test_expiry_skips_ineligible_and_does_not_mutate_requirement_facts():
    from job_runner import run_expiry_rollover_recalc

    items = [{"property_id": "p1"}]
    db = MagicMock()
    db.requirements.find = MagicMock(return_value=_AsyncListCursor(items))
    db.properties.find_one = AsyncMock(return_value={"client_id": "c-pay"})
    db.requirements.update_one = AsyncMock()
    enqueue = AsyncMock()

    async def _resolve(db, client_id, cache=None):
        return PAYMENT_PENDING

    with patch("database.database.get_db", return_value=db):
        with patch(
            "services.compliance_recalc_sla_eligibility.resolve_compliance_recalc_sla_eligibility",
            side_effect=_resolve,
        ):
            with patch("services.compliance_recalc_queue.enqueue_compliance_recalc", enqueue):
                result = await run_expiry_rollover_recalc()

    assert result["count"] == 0
    assert result["outcome_metrics"]["lifecycle_suppressed"] == 1
    enqueue.assert_not_called()
    db.requirements.update_one.assert_not_called()


@pytest.mark.asyncio
async def test_admin_manual_enqueue_bypasses_automatic_gate():
    from job_runner import run_compliance_recalc_enqueue_property

    db = MagicMock()
    db.properties.find_one = AsyncMock(return_value={"client_id": "c-pay"})
    enqueue = AsyncMock(return_value=True)
    resolve = AsyncMock(return_value=PAYMENT_PENDING)

    with patch("database.database.get_db", return_value=db):
        with patch(
            "services.compliance_recalc_lifecycle_transition.enqueue_compliance_recalc_admin_override",
            enqueue,
        ):
            with patch(
                "services.compliance_recalc_sla_eligibility.resolve_compliance_recalc_sla_eligibility",
                resolve,
            ):
                result = await run_compliance_recalc_enqueue_property(property_id="p1")

    assert result["count"] == 1
    enqueue.assert_awaited_once()
    resolve.assert_not_called()
