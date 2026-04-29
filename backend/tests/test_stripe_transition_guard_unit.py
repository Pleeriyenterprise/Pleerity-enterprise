from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict
from unittest.mock import patch

import pytest

from services.stripe_webhook_service import stripe_webhook_service


@dataclass
class _UpdateResult:
    modified_count: int


def _get_path(doc: Dict[str, Any], dotted: str) -> Any:
    cur: Any = doc
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def _set_path(doc: Dict[str, Any], dotted: str, value: Any) -> None:
    cur: Dict[str, Any] = doc
    parts = dotted.split(".")
    for part in parts[:-1]:
        nxt = cur.get(part)
        if not isinstance(nxt, dict):
            nxt = {}
            cur[part] = nxt
        cur = nxt
    cur[parts[-1]] = value


class _FakeClientBillingCollection:
    def __init__(self) -> None:
        self._docs: Dict[str, Dict[str, Any]] = {}

    def seed(self, client_id: str) -> None:
        self._docs[client_id] = {"client_id": client_id, "transition_guards": {}}

    async def find_one(self, query: Dict[str, Any], projection: Dict[str, Any] | None = None) -> Dict[str, Any] | None:
        client_id = query.get("client_id")
        doc = self._docs.get(client_id)
        if doc is None:
            return None
        return deepcopy(doc)

    async def update_one(self, query: Dict[str, Any], update: Dict[str, Any]) -> _UpdateResult:
        client_id = query.get("client_id")
        doc = self._docs.get(client_id)
        if doc is None:
            return _UpdateResult(modified_count=0)

        for key, expected in query.items():
            if key == "client_id":
                continue
            if isinstance(expected, dict) and "$exists" in expected:
                exists = _get_path(doc, key) is not None
                if exists != bool(expected["$exists"]):
                    return _UpdateResult(modified_count=0)
                continue
            actual = _get_path(doc, key)
            if actual != expected:
                return _UpdateResult(modified_count=0)

        to_set = update.get("$set", {})
        for dotted, value in to_set.items():
            _set_path(doc, dotted, deepcopy(value))
        return _UpdateResult(modified_count=1)


class _FakeDb:
    def __init__(self) -> None:
        self.client_billing = _FakeClientBillingCollection()


def _evt(event_id: str, created_dt: datetime) -> Dict[str, Any]:
    return {
        "id": event_id,
        "type": "customer.subscription.updated",
        "created": int(created_dt.timestamp()),
    }


def _sub(price_ids: list[str]) -> Dict[str, Any]:
    return {
        "id": "sub_unit_123",
        "status": "active",
        "current_period_end": 1893456000,
        "items": {"data": [{"price": {"id": pid}} for pid in price_ids]},
    }


def test_subscription_transition_key_includes_price_fingerprint() -> None:
    key = stripe_webhook_service._subscription_transition_key(_sub(["price_z", "price_a", "price_a"]))
    assert key.startswith("sub_change:sub_unit_123:active:1893456000:")
    assert key.endswith("price_a|price_z")


def test_same_status_period_different_price_produces_different_key() -> None:
    key_a = stripe_webhook_service._subscription_transition_key(_sub(["price_plan_a"]))
    key_b = stripe_webhook_service._subscription_transition_key(_sub(["price_plan_b"]))
    assert key_a != key_b


@pytest.mark.asyncio
async def test_first_atomic_claim_succeeds() -> None:
    db = _FakeDb()
    db.client_billing.seed("client_unit_1")
    now = datetime.now(timezone.utc)
    with patch("services.stripe_webhook_service.database.get_db", return_value=db):
        result = await stripe_webhook_service._claim_transition_guard(
            client_id="client_unit_1",
            transition_key="sub_change:sub_unit_123:active:period:price_plan_a",
            event=_evt("evt_unit_1", now),
            skip_if_seen=True,
        )
    assert result["claimed"] is True


@pytest.mark.asyncio
async def test_duplicate_claim_loses() -> None:
    db = _FakeDb()
    db.client_billing.seed("client_unit_2")
    now = datetime.now(timezone.utc)
    with patch("services.stripe_webhook_service.database.get_db", return_value=db):
        first = await stripe_webhook_service._claim_transition_guard(
            client_id="client_unit_2",
            transition_key="sub_change:sub_unit_123:active:period:price_plan_a",
            event=_evt("evt_unit_2", now),
            skip_if_seen=True,
        )
        duplicate = await stripe_webhook_service._claim_transition_guard(
            client_id="client_unit_2",
            transition_key="sub_change:sub_unit_123:active:period:price_plan_a",
            event=_evt("evt_unit_2", now),
            skip_if_seen=True,
        )
    assert first["claimed"] is True
    assert duplicate["claimed"] is False
    assert duplicate["reason"] == "same_event_id"


@pytest.mark.asyncio
async def test_newer_cas_update_wins() -> None:
    db = _FakeDb()
    db.client_billing.seed("client_unit_3")
    now = datetime.now(timezone.utc)
    newer = now + timedelta(minutes=5)
    with patch("services.stripe_webhook_service.database.get_db", return_value=db):
        first = await stripe_webhook_service._claim_transition_guard(
            client_id="client_unit_3",
            transition_key="sub_change:sub_unit_123:active:period:price_plan_a",
            event=_evt("evt_unit_3_first", now),
            skip_if_seen=True,
        )
        second = await stripe_webhook_service._claim_transition_guard(
            client_id="client_unit_3",
            transition_key="sub_change:sub_unit_123:active:period:price_plan_a",
            event=_evt("evt_unit_3_newer", newer),
            skip_if_seen=True,
        )
    assert first["claimed"] is True
    assert second["claimed"] is True
    assert second["reason"] == "claimed_newer_event"


@pytest.mark.asyncio
async def test_stale_older_event_loses() -> None:
    db = _FakeDb()
    db.client_billing.seed("client_unit_4")
    now = datetime.now(timezone.utc)
    older = now - timedelta(minutes=5)
    with patch("services.stripe_webhook_service.database.get_db", return_value=db):
        first = await stripe_webhook_service._claim_transition_guard(
            client_id="client_unit_4",
            transition_key="sub_change:sub_unit_123:active:period:price_plan_a",
            event=_evt("evt_unit_4_first", now),
            skip_if_seen=True,
        )
        stale = await stripe_webhook_service._claim_transition_guard(
            client_id="client_unit_4",
            transition_key="sub_change:sub_unit_123:active:period:price_plan_a",
            event=_evt("evt_unit_4_older", older),
            skip_if_seen=True,
        )
    assert first["claimed"] is True
    assert stale["claimed"] is False
    assert stale["reason"] == "older_event"
