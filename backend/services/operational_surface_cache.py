"""
Short-TTL in-process cache for expensive operational read models (unified tasks).

Disclosed via freshness metadata on responses (cache_hit, cached_at, cache_ttl_seconds).
Not used for mutations or authority outcomes.
"""
from __future__ import annotations

import time
from typing import Any, Dict, Optional, Tuple

_DEFAULT_TTL_SECONDS = 45

_store: Dict[str, Dict[str, Any]] = {}


def unified_tasks_cache_key(
    client_id: str,
    property_id_filter: Optional[str],
    portal_user_id: Optional[str],
    raw_limit: int,
) -> str:
    return f"unified:{client_id}:{property_id_filter or ''}:{portal_user_id or ''}:{int(raw_limit)}"


def get_cached_unified_tasks(key: str) -> Optional[Dict[str, Any]]:
    row = _store.get(key)
    if not row:
        return None
    age = time.monotonic() - float(row.get("stored_at_mono") or 0)
    ttl = float(row.get("ttl_seconds") or _DEFAULT_TTL_SECONDS)
    if age > ttl:
        _store.pop(key, None)
        return None
    return row


def set_cached_unified_tasks(
    key: str,
    payload: Dict[str, Any],
    *,
    ttl_seconds: int = _DEFAULT_TTL_SECONDS,
) -> None:
    _store[key] = {
        "payload": payload,
        "cached_at": time.time(),
        "stored_at_mono": time.monotonic(),
        "ttl_seconds": ttl_seconds,
    }


def invalidate_unified_tasks_for_client(client_id: str) -> None:
    prefix = f"unified:{client_id}:"
    for k in list(_store.keys()):
        if k.startswith(prefix):
            _store.pop(k, None)
