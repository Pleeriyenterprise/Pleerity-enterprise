"""Shared query fragments for portal_users soft-delete (archive) scope."""

from typing import Any, Dict


def active_portal_user_filter() -> Dict[str, Any]:
    """Documents that are not soft-deleted (missing is_deleted or not True)."""
    return {"is_deleted": {"$ne": True}}


def merge_active_portal_user(query: Dict[str, Any]) -> Dict[str, Any]:
    """AND the given query with the active-user constraint."""
    merged = dict(query)
    merged.update(active_portal_user_filter())
    return merged
