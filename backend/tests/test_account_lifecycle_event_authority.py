"""Tests for ILP-9 Account Lifecycle Event Authority."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.account_lifecycle_event_authority import (
    EVENTS_COLLECTION,
    SCHEMA_VERSION,
    LifecycleEventAuthority,
    LifecycleEventCategory,
    LifecycleEventPayload,
    LifecycleEventType,
    detect_runtime_contract_events,
    publish_lifecycle_event,
    register_lifecycle_event_consumer,
)
from services.account_lifecycle_runtime_contract import (
    build_runtime_contract,
    invalidate_runtime_cache_for_client,
    peek_cached_runtime_contract,
    runtime_contract_to_dict,
)

NOW = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)


def _client(**overrides):
    base = {"client_id": "c-evt-1", "billing_plan": "PLAN_2_PORTFOLIO"}
    base.update(overrides)
    return base


def _billing(**overrides):
    base = {
        "client_id": "c-evt-1",
        "subscription_status": "ACTIVE",
        "billing_lifecycle_state": "active",
    }
    base.update(overrides)
    return base


def _contract(client=None, billing=None):
    return runtime_contract_to_dict(
        build_runtime_contract(client=client or _client(), billing=billing or _billing(), now=NOW)
    )


class _FakeEventsCollection:
    def __init__(self):
        self.docs: list = []

    async def find_one(self, query, projection=None):
        for doc in reversed(self.docs):
            if doc.get("idempotency_key") == query.get("idempotency_key"):
                out = {"event_id": doc.get("event_id")}
                if projection:
                    out = {k: v for k, v in out.items() if k in projection or "_id" in projection}
                return out
        return None

    async def insert_one(self, doc):
        self.docs.append(dict(doc))


class _FakeDb:
    def __init__(self):
        self._collections = {EVENTS_COLLECTION: _FakeEventsCollection()}

    def __getitem__(self, name):
        if name not in self._collections:
            self._collections[name] = _FakeEventsCollection()
        return self._collections[name]


def test_payload_schema_required_fields():
    payload = LifecycleEventPayload(
        event_type=LifecycleEventType.RUNTIME_CONTRACT_CHANGED.value,
        client_id="c-evt-1",
        lifecycle_state="ACTIVE",
        portal_mode="FULL_ACCESS",
        runtime_version=3,
        event_category=LifecycleEventCategory.RUNTIME.value,
    )
    doc = payload.to_document()
    for field in (
        "event_id",
        "event_type",
        "event_category",
        "client_id",
        "schema_version",
        "policy_version",
        "correlation_id",
        "occurred_at",
        "created_at",
    ):
        assert field in doc, field
    assert doc["schema_version"] == SCHEMA_VERSION


def test_detect_lifecycle_state_transition_active_to_grace():
    prev = _contract(billing={"subscription_status": "ACTIVE", "billing_lifecycle_state": "active"})
    curr = _contract(
        billing={
            "subscription_status": "PAST_DUE",
            "billing_lifecycle_state": "grace_period",
            "grace_period_end": datetime(2026, 6, 20, tzinfo=timezone.utc),
        }
    )
    events = detect_runtime_contract_events(prev, curr, trigger="test")
    types = {e.event_type for e in events}
    assert LifecycleEventType.GRACE_PERIOD_STARTED.value in types
    assert LifecycleEventType.LIFECYCLE_STATE_CHANGED.value in types


def test_detect_portal_mode_change():
    prev = _contract(billing={"subscription_status": "ACTIVE", "billing_lifecycle_state": "active"})
    curr = _contract(billing={"subscription_status": "CANCELED", "billing_lifecycle_state": "cancelled"})
    events = detect_runtime_contract_events(prev, curr, trigger="test")
    types = {e.event_type for e in events}
    assert LifecycleEventType.PORTAL_MODE_CHANGED.value in types
    assert LifecycleEventType.LIFECYCLE_STATE_CHANGED.value in types


def test_detect_capabilities_change_event():
    prev = _contract()
    curr = dict(_contract())
    curr["capabilities"] = dict(curr["capabilities"])
    curr["capabilities"]["CAP_REPORT_GENERATE_PDF"] = "DENY"
    events = detect_runtime_contract_events(prev, curr, trigger="test")
    types = {e.event_type for e in events}
    assert LifecycleEventType.CAPABILITIES_CHANGED.value in types


def test_detect_runtime_version_bump_emits_session_and_runtime_events():
    prev = _contract()
    curr = dict(_contract())
    curr["runtime_version"] = int(prev["runtime_version"]) + 1
    events = detect_runtime_contract_events(prev, curr, trigger="test")
    types = {e.event_type for e in events}
    assert LifecycleEventType.RUNTIME_CONTRACT_CHANGED.value in types
    assert LifecycleEventType.SESSION_RUNTIME_CHANGED.value in types


def test_detect_no_events_when_empty_client():
    events = detect_runtime_contract_events(None, {"client_id": ""})
    assert events == []


@pytest.mark.asyncio
async def test_publish_idempotent_duplicate_skipped():
    db = _FakeDb()
    payload = LifecycleEventPayload(
        event_type=LifecycleEventType.RUNTIME_CONTRACT_CHANGED.value,
        client_id="c-evt-1",
        idempotency_key="c-evt-1:RuntimeContractChanged:1:2",
        event_category=LifecycleEventCategory.RUNTIME.value,
    )
    first = await publish_lifecycle_event(db, payload)
    second = await publish_lifecycle_event(db, payload)
    assert first["duplicate"] is False
    assert second["duplicate"] is True
    assert len(db[EVENTS_COLLECTION].docs) == 1


@pytest.mark.asyncio
async def test_publish_dispatches_registered_consumer():
    db = _FakeDb()
    seen = []

    async def handler(doc):
        seen.append(doc.get("event_type"))

    register_lifecycle_event_consumer(LifecycleEventCategory.RUNTIME, handler)
    payload = LifecycleEventPayload(
        event_type=LifecycleEventType.PORTAL_MODE_CHANGED.value,
        client_id="c-evt-1",
        idempotency_key=f"unique-{len(seen)}-portal",
        event_category=LifecycleEventCategory.RUNTIME.value,
    )
    with patch(
        "services.account_lifecycle_event_authority._audit_lifecycle_event",
        new=AsyncMock(),
    ):
        await LifecycleEventAuthority(db).publish(payload)
    assert LifecycleEventType.PORTAL_MODE_CHANGED.value in seen


@pytest.mark.asyncio
async def test_builtin_consumer_invalidates_runtime_cache():
    from services import account_lifecycle_event_authority as mod

    client_id = "cache-inv-1"
    contract = _contract(client={"client_id": client_id})
    from services.account_lifecycle_runtime_contract import _runtime_cache
    import time

    _runtime_cache[client_id] = (time.time(), contract["runtime_version"], contract)
    assert peek_cached_runtime_contract(client_id) is not None
    await mod._consumer_runtime_cache_invalidation({"client_id": client_id})
    assert peek_cached_runtime_contract(client_id) is None


def test_invalidate_runtime_cache_for_client_helper():
    client_id = "cache-inv-2"
    contract = _contract(client={"client_id": client_id})
    from services.account_lifecycle_runtime_contract import _runtime_cache
    import time

    _runtime_cache[client_id] = (time.time(), contract["runtime_version"], contract)
    invalidate_runtime_cache_for_client(client_id)
    assert peek_cached_runtime_contract(client_id) is None
