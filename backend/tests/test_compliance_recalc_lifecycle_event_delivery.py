"""Phase 2B: real lifecycle event delivery into compliance recalc restore/park."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from services.account_lifecycle_event_authority import (
    EVENTS_COLLECTION,
    LifecycleEventType,
    detect_runtime_contract_events,
    publish_runtime_contract_transition,
)
from services.account_lifecycle_runtime_contract import (
    build_runtime_contract,
    publish_runtime_contract_after_mutation,
    runtime_contract_to_dict,
)
from services.account_background_runtime_authority import BackgroundJobDecision
from services.compliance_recalc_lifecycle_transition import register_compliance_recalc_lifecycle_consumers
from services.compliance_recalc_queue import STATUS_PARKED, STATUS_PENDING
from services.compliance_recalc_sla_eligibility import ComplianceRecalcSlaClass
from services.compliance_recalc_state import RECALC_STATE_ACTIVE_PENDING, RECALC_STATE_PARKED
from tests.test_compliance_recalc_lifecycle_phase2b import FakeDB, _bg, _elig

NOW = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)


def _client(**overrides):
    base = {"client_id": "c-evt-2b", "billing_plan": "PLAN_3_PRO"}
    base.update(overrides)
    return base


def _contract(*, client=None, billing=None):
    return runtime_contract_to_dict(
        build_runtime_contract(client=client or _client(), billing=billing, now=NOW)
    )


class _EventsColl:
    def __init__(self):
        self.docs = []

    async def find_one(self, query, projection=None):
        for doc in reversed(self.docs):
            if doc.get("idempotency_key") == query.get("idempotency_key"):
                return {"event_id": doc.get("event_id")}
        return None

    async def insert_one(self, doc):
        self.docs.append(dict(doc))


class CombinedDB(FakeDB):
    def __init__(self, queue=None, props=None):
        super().__init__(queue=queue, props=props)
        self._events = _EventsColl()

    def __getitem__(self, name):
        if name == EVENTS_COLLECTION:
            return self._events
        if name == "compliance_recalc_queue":
            return self.compliance_recalc_queue
        if name == "properties":
            return self.properties
        return _EventsColl()


def _parked_db():
    return CombinedDB(
        queue=[
            {
                "_id": "j1",
                "property_id": "p1",
                "client_id": "c-evt-2b",
                "status": STATUS_PARKED,
                "correlation_id": "x",
            }
        ],
        props=[
            {
                "property_id": "p1",
                "client_id": "c-evt-2b",
                "compliance_score_pending": True,
                "compliance_score_recalc_state": RECALC_STATE_PARKED,
            }
        ],
    )


def test_detect_payment_pending_to_active_emits_lifecycle_events():
    prev = _contract(
        client=_client(lifecycle_status="pending_payment"),
        billing=None,
    )
    curr = _contract(
        billing={"subscription_status": "ACTIVE", "billing_lifecycle_state": "active"},
    )
    assert prev["lifecycle_state"] == "PAYMENT_PENDING"
    assert curr["lifecycle_state"] == "ACTIVE"
    types = {e.event_type for e in detect_runtime_contract_events(prev, curr, trigger="stripe_invoice_paid")}
    assert LifecycleEventType.LIFECYCLE_STATE_CHANGED.value in types
    assert LifecycleEventType.ACCOUNT_ACTIVATED.value in types
    assert LifecycleEventType.RUNTIME_CONTRACT_CHANGED.value in types


def test_detect_suspended_to_active_emits_lifecycle_state_changed():
    prev = _contract(
        client=_client(client_lifecycle_status="SUSPENDED"),
        billing={"subscription_status": "ACTIVE", "billing_lifecycle_state": "active"},
    )
    curr = _contract(
        billing={"subscription_status": "ACTIVE", "billing_lifecycle_state": "active"},
    )
    assert prev["lifecycle_state"] == "SUSPENDED"
    assert curr["lifecycle_state"] == "ACTIVE"
    types = {e.event_type for e in detect_runtime_contract_events(prev, curr, trigger="admin_resume_client_org")}
    assert LifecycleEventType.LIFECYCLE_STATE_CHANGED.value in types


def test_detect_unknown_to_active_emits_account_activated():
    prev = _contract(
        billing={"subscription_status": "ACTIVE", "billing_lifecycle_state": "cancelled"},
    )
    curr = _contract(
        billing={"subscription_status": "ACTIVE", "billing_lifecycle_state": "active"},
    )
    assert prev["lifecycle_state"] == "UNKNOWN"
    assert curr["lifecycle_state"] == "ACTIVE"
    types = {e.event_type for e in detect_runtime_contract_events(prev, curr, trigger="runtime_contract_resolve")}
    assert LifecycleEventType.ACCOUNT_ACTIVATED.value in types
    assert LifecycleEventType.LIFECYCLE_STATE_CHANGED.value in types


@pytest.mark.asyncio
async def test_publish_payment_recovery_restores_parked_via_consumer():
    register_compliance_recalc_lifecycle_consumers()
    db = _parked_db()
    prev = _contract(client=_client(lifecycle_status="pending_payment"), billing=None)
    curr = _contract(billing={"subscription_status": "ACTIVE", "billing_lifecycle_state": "active"})
    with patch("database.database.get_db", return_value=db), patch(
        "services.compliance_recalc_lifecycle_transition.evaluate_background_runtime",
        AsyncMock(return_value=_bg(BackgroundJobDecision.CONTINUE, "ACTIVE")),
    ), patch(
        "services.compliance_recalc_lifecycle_transition.resolve_compliance_recalc_sla_eligibility",
        AsyncMock(return_value=_elig(ComplianceRecalcSlaClass.ACTIONABLE, "ACTIVE", "CONTINUE")),
    ), patch(
        "utils.audit.create_audit_log",
        AsyncMock(),
    ):
        results = await publish_runtime_contract_transition(
            db, prev, curr, trigger="stripe_invoice_paid"
        )
    assert any(r.get("status") == "published" for r in results)
    assert db.compliance_recalc_queue.rows[0]["status"] == STATUS_PENDING
    assert db.properties.rows[0]["compliance_score_recalc_state"] == RECALC_STATE_ACTIVE_PENDING


@pytest.mark.asyncio
async def test_publish_admin_resume_restores_parked_via_consumer():
    register_compliance_recalc_lifecycle_consumers()
    db = _parked_db()
    prev = _contract(
        client=_client(client_lifecycle_status="SUSPENDED"),
        billing={"subscription_status": "ACTIVE", "billing_lifecycle_state": "active"},
    )
    curr = _contract(billing={"subscription_status": "ACTIVE", "billing_lifecycle_state": "active"})
    with patch("database.database.get_db", return_value=db), patch(
        "services.compliance_recalc_lifecycle_transition.evaluate_background_runtime",
        AsyncMock(return_value=_bg(BackgroundJobDecision.CONTINUE, "ACTIVE")),
    ), patch(
        "services.compliance_recalc_lifecycle_transition.resolve_compliance_recalc_sla_eligibility",
        AsyncMock(return_value=_elig(ComplianceRecalcSlaClass.ACTIONABLE, "ACTIVE", "CONTINUE")),
    ), patch(
        "utils.audit.create_audit_log",
        AsyncMock(),
    ):
        await publish_runtime_contract_transition(db, prev, curr, trigger="admin_resume_client_org")
    assert db.compliance_recalc_queue.rows[0]["status"] == STATUS_PENDING


@pytest.mark.asyncio
async def test_publish_unknown_to_active_restores_parked_via_consumer():
    register_compliance_recalc_lifecycle_consumers()
    db = _parked_db()
    prev = _contract(billing={"subscription_status": "ACTIVE", "billing_lifecycle_state": "cancelled"})
    curr = _contract(billing={"subscription_status": "ACTIVE", "billing_lifecycle_state": "active"})
    with patch("database.database.get_db", return_value=db), patch(
        "services.compliance_recalc_lifecycle_transition.evaluate_background_runtime",
        AsyncMock(return_value=_bg(BackgroundJobDecision.CONTINUE, "ACTIVE")),
    ), patch(
        "services.compliance_recalc_lifecycle_transition.resolve_compliance_recalc_sla_eligibility",
        AsyncMock(return_value=_elig(ComplianceRecalcSlaClass.ACTIONABLE, "ACTIVE", "CONTINUE")),
    ), patch(
        "utils.audit.create_audit_log",
        AsyncMock(),
    ):
        await publish_runtime_contract_transition(db, prev, curr, trigger="runtime_contract_resolve")
    assert db.compliance_recalc_queue.rows[0]["status"] == STATUS_PENDING


@pytest.mark.asyncio
async def test_duplicate_transition_publish_is_idempotent():
    register_compliance_recalc_lifecycle_consumers()
    db = _parked_db()
    prev = _contract(client=_client(lifecycle_status="pending_payment"), billing=None)
    curr = _contract(billing={"subscription_status": "ACTIVE", "billing_lifecycle_state": "active"})
    with patch("database.database.get_db", return_value=db), patch(
        "services.compliance_recalc_lifecycle_transition.evaluate_background_runtime",
        AsyncMock(return_value=_bg(BackgroundJobDecision.CONTINUE, "ACTIVE")),
    ), patch(
        "services.compliance_recalc_lifecycle_transition.resolve_compliance_recalc_sla_eligibility",
        AsyncMock(return_value=_elig(ComplianceRecalcSlaClass.ACTIONABLE, "ACTIVE", "CONTINUE")),
    ), patch(
        "utils.audit.create_audit_log",
        AsyncMock(),
    ):
        first = await publish_runtime_contract_transition(db, prev, curr, trigger="stripe_invoice_paid")
        second = await publish_runtime_contract_transition(db, prev, curr, trigger="stripe_invoice_paid")
    assert any(r.get("status") == "published" for r in first)
    assert all(r.get("duplicate") or r.get("status") == "duplicate" for r in second)
    assert len([r for r in db.compliance_recalc_queue.rows if r["status"] == STATUS_PENDING]) == 1
    assert len(db.compliance_recalc_queue.rows) == 1


@pytest.mark.asyncio
async def test_publish_runtime_contract_after_mutation_uses_pre_snapshot():
    db = CombinedDB()
    prev = _contract(client=_client(lifecycle_status="pending_payment"), billing=None)
    curr = _contract(billing={"subscription_status": "ACTIVE", "billing_lifecycle_state": "active"})
    with patch(
        "services.account_lifecycle_runtime_contract.resolve_runtime_contract_for_client",
        AsyncMock(return_value=curr),
    ), patch(
        "services.account_lifecycle_event_authority.publish_runtime_contract_transition",
        AsyncMock(return_value=[{"status": "published"}]),
    ) as pub:
        out = await publish_runtime_contract_after_mutation(
            db, "c-evt-2b", prev, trigger="stripe_invoice_paid"
        )
    pub.assert_awaited_once()
    args, kwargs = pub.await_args
    assert args[1] is prev
    assert args[2] == curr
    assert kwargs.get("trigger") == "stripe_invoice_paid"
    assert out == [{"status": "published"}]


def test_billing_recovery_and_admin_resume_paths_emit_after_mutation():
    import inspect

    from services.client_lifecycle_service import resume_client_org, suspend_client_org
    from services.stripe_webhook_service import StripeWebhookService

    invoice_src = inspect.getsource(StripeWebhookService._handle_invoice_paid)
    assert "snapshot_runtime_contract" in invoice_src
    assert "publish_runtime_contract_after_mutation" in invoice_src
    assert "stripe_invoice_paid" in invoice_src
    resume_src = inspect.getsource(resume_client_org)
    assert "publish_runtime_contract_after_mutation" in resume_src
    assert "admin_resume_client_org" in resume_src
    suspend_src = inspect.getsource(suspend_client_org)
    assert "admin_suspend_client_org" in suspend_src
