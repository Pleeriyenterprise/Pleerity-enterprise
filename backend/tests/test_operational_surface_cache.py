"""Operational surface cache — dedupe unified tasks within TTL."""

import pytest

from services import operational_surface_cache as osc
from services.unified_tasks_service import digest_from_unified_tasks_full


def test_unified_tasks_cache_key_stable():
    k1 = osc.unified_tasks_cache_key("c1", None, "pu1", 60)
    k2 = osc.unified_tasks_cache_key("c1", None, "pu1", 60)
    assert k1 == k2
    assert k1 != osc.unified_tasks_cache_key("c2", None, "pu1", 60)


def test_cache_set_get_and_expire(monkeypatch):
    osc._store.clear()
    osc.set_cached_unified_tasks("k", {"summary": {"urgent_count": 1}}, ttl_seconds=60)
    hit = osc.get_cached_unified_tasks("k")
    assert hit is not None
    assert hit["payload"]["summary"]["urgent_count"] == 1

    monkeypatch.setattr(
        "services.operational_surface_cache.time.monotonic",
        lambda: hit["stored_at_mono"] + 120,
    )
    assert osc.get_cached_unified_tasks("k") is None


def test_digest_from_full_without_rebuild():
    full = {
        "summary": {"urgent_count": 3},
        "freshness": {"tasks_refreshed_at": "2026-01-01T00:00:00Z"},
        "activity_feed": [{"id": "a"}, {"id": "b"}],
    }
    d = digest_from_unified_tasks_full(full, activity_limit=1)
    assert d["summary"]["urgent_count"] == 3
    assert len(d["activity_feed"]) == 1
