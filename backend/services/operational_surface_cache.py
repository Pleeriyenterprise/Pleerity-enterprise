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
    surface_profile: str = "full",
) -> str:
    prof = str(surface_profile or "full").strip().lower()
    return f"unified:{client_id}:{property_id_filter or ''}:{portal_user_id or ''}:{int(raw_limit)}:{prof}"


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


def compliance_score_cache_key(client_id: str) -> str:
    return f"compliance_score:{client_id}"


def get_cached_compliance_score(key: str) -> Optional[Dict[str, Any]]:
    return get_cached_unified_tasks(key)


def set_cached_compliance_score(
    key: str,
    payload: Dict[str, Any],
    *,
    ttl_seconds: int = _DEFAULT_TTL_SECONDS,
) -> None:
    set_cached_unified_tasks(key, payload, ttl_seconds=ttl_seconds)


def command_center_primary_cache_key(client_id: str, property_id_filter: Optional[str]) -> str:
    return f"cc_primary:{client_id}:{property_id_filter or ''}"


def get_cached_command_center_primary(key: str) -> Optional[Dict[str, Any]]:
    return get_cached_unified_tasks(key)


def set_cached_command_center_primary(
    key: str,
    payload: Dict[str, Any],
    *,
    ttl_seconds: int = 45,
) -> None:
    set_cached_unified_tasks(key, payload, ttl_seconds=ttl_seconds)


def invalidate_command_center_primary_for_client(client_id: str) -> None:
    prefix = f"cc_primary:{client_id}:"
    for k in list(_store.keys()):
        if k.startswith(prefix):
            _store.pop(k, None)


def invalidate_compliance_score_for_client(client_id: str) -> None:
    _store.pop(compliance_score_cache_key(client_id), None)


def invalidate_operational_intelligence_sections_for_client(client_id: str) -> None:
    prefix = f"oi_section:{client_id}:"
    for k in list(_store.keys()):
        if k.startswith(prefix):
            _store.pop(k, None)


def invalidate_client_operational_surfaces(client_id: str) -> None:
    """Fan-out cache bust for Today/CC/dashboard/score/admin read models."""
    invalidate_unified_tasks_for_client(client_id)
    invalidate_command_center_primary_for_client(client_id)
    invalidate_compliance_score_for_client(client_id)
    invalidate_operational_intelligence_sections_for_client(client_id)


def operational_intelligence_section_cache_key(
    client_id: str,
    property_id_filter: Optional[str],
    section_name: str,
) -> str:
    section = str(section_name or "").strip().lower()
    return f"oi_section:{client_id}:{property_id_filter or ''}:{section}"


def get_cached_operational_intelligence_section(key: str) -> Optional[Dict[str, Any]]:
    return get_cached_unified_tasks(key)


def set_cached_operational_intelligence_section(
    key: str,
    payload: Dict[str, Any],
    *,
    ttl_seconds: int = 120,
) -> None:
    set_cached_unified_tasks(key, payload, ttl_seconds=ttl_seconds)


def _summary_counts_from_cached_payload(cached: Dict[str, Any]) -> Optional[Tuple[int, int]]:
    summ = (cached.get("payload") or {}).get("summary") or {}
    urgent = summ.get("urgent_count")
    upcoming = summ.get("upcoming_count")
    if urgent is None or upcoming is None:
        return None
    return int(urgent), int(upcoming)


def peek_cached_unified_tasks_summary_counts(
    client_id: str,
    *,
    property_id_filter: Optional[str] = None,
    portal_user_id: Optional[str] = None,
    preferred_raw_limits: Tuple[int, ...] = (60, 120),
    surface_profile: str = "full",
) -> Optional[Dict[str, Any]]:
    """
    Return urgent/upcoming counts from a TTL-valid unified tasks cache entry without rebuilding.
    """
    prof = str(surface_profile or "full").strip().lower()
    for raw_limit in preferred_raw_limits:
        key = unified_tasks_cache_key(client_id, property_id_filter, portal_user_id, raw_limit, prof)
        cached = get_cached_unified_tasks(key)
        if not cached:
            continue
        counts = _summary_counts_from_cached_payload(cached)
        if counts is None:
            continue
        urgent, upcoming = counts
        return {
            "urgent_count": urgent,
            "upcoming_count": upcoming,
            "cache_key": key,
        }

    prefix = f"unified:{client_id}:"
    suffix = f":{prof}"
    for key in list(_store.keys()):
        if not key.startswith(prefix) or not key.endswith(suffix):
            continue
        cached = get_cached_unified_tasks(key)
        if not cached:
            continue
        counts = _summary_counts_from_cached_payload(cached)
        if counts is None:
            continue
        urgent, upcoming = counts
        return {
            "urgent_count": urgent,
            "upcoming_count": upcoming,
            "cache_key": key,
        }
    return None


def peek_cached_command_center_summary_counts(
    client_id: str,
    *,
    property_id_filter: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Return urgent/upcoming from cached CC primary tasks_digest_summary when both are present."""
    key = command_center_primary_cache_key(client_id, property_id_filter)
    cached = get_cached_command_center_primary(key)
    if not cached:
        return None
    tds = (cached.get("payload") or {}).get("tasks_digest_summary") or {}
    urgent = tds.get("urgent_count")
    upcoming = tds.get("upcoming_count")
    if urgent is None or upcoming is None:
        return None
    return {
        "urgent_count": int(urgent),
        "upcoming_count": int(upcoming),
        "cache_key": key,
    }
