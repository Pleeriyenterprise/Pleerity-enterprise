"""
Central gate for *client-facing* requirement rows on runtime surfaces (reminders, digests,
exports, dashboards, notifications, calendar, unified tasks, etc.).

INVARIANT — all client-facing requirement output must pass through published runtime
eligibility + jurisdiction + condition filtering aligned with ``build_requirement_plan_for_property``
(planner truth for catalog-backed rows), plus row-level NOT_REQUIRED / visibility / hidden-action /
archived-metadata gates. Prefer ``filter_requirement_rows_for_client_runtime_surfaces`` (async, DB-aware)
or call ``requirement_row_passes_client_runtime_surface_gates`` after you have loaded published entries
and per-property plan type sets.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from services.compliance_registry_publish_service import fetch_active_published_registry_entries
from services.compliance_requirement_registry import (
    REQUIREMENT_GENERATION_SOURCE_REGISTRY,
    build_requirement_plan_for_property,
)
from services.compliance_rules_registry import (
    canonicalize_uk_portfolio_label,
    portfolio_jurisdiction_label,
)
from services.provisioning import REQUIREMENT_GENERATION_SOURCE_DB_RULE


CLIENT_RUNTIME_REQUIREMENT_SURFACE_INVARIANT = (
    "All client-facing requirement output must pass through published runtime eligibility + "
    "jurisdiction + condition filtering (shared planner for catalog-backed rows), excluding "
    "NOT_REQUIRED, non-visible, hidden-primary-action, archived metadata, draft-only registry rows, "
    "and wrong-jurisdiction rows."
)


def _status_upper(val: Optional[str]) -> str:
    return (val or "").strip().upper()


def _norm_requirement_type(row: Dict[str, Any]) -> str:
    return (
        str(row.get("requirement_type") or row.get("requirement_code") or row.get("code") or "")
        .strip()
        .lower()
    )


def _generation_source(row: Dict[str, Any]) -> str:
    return str(row.get("requirement_generation_source") or "").strip()


def _needs_catalog_planner_membership(row: Dict[str, Any]) -> bool:
    src = _generation_source(row)
    if src == REQUIREMENT_GENERATION_SOURCE_DB_RULE:
        return False
    if src in ("", REQUIREMENT_GENERATION_SOURCE_REGISTRY):
        return True
    # Unknown / legacy sources: fail closed to planner membership when property-backed
    return True


def _primary_action_hidden(row: Dict[str, Any]) -> bool:
    meta = row.get("registry_metadata")
    if not isinstance(meta, dict):
        return False
    return str(meta.get("primary_action_mode") or "").strip().lower() == "hidden"


def _registry_metadata_archived(row: Dict[str, Any]) -> bool:
    meta = row.get("registry_metadata")
    if not isinstance(meta, dict):
        return False
    life = meta.get("lifecycle") if isinstance(meta.get("lifecycle"), dict) else {}
    st = str(life.get("status") or meta.get("lifecycle_status") or "").strip().lower()
    return st in ("archived", "superseded", "disabled", "withdrawn")


def _registry_draft_or_unpublished_materialization(row: Dict[str, Any]) -> bool:
    """Rows materialised only from unpublished / draft registry must never surface to clients."""
    meta = row.get("registry_metadata") if isinstance(row.get("registry_metadata"), dict) else {}
    if meta.get("draft_only_materialization") is True:
        return True
    rps = str(meta.get("registry_publish_state") or "").strip().lower()
    return rps in ("draft", "draft_only", "unpublished")


def _explicit_row_jurisdiction_mismatches_property(
    row: Dict[str, Any],
    property_doc: Dict[str, Any],
    client_doc: Optional[Dict[str, Any]],
) -> bool:
    """
    True when the row carries an explicit UK portfolio label that disagrees with the
    property's resolved portfolio label (stale / cross-region materialised rows).
    """
    raw = row.get("jurisdiction")
    if not raw or not str(raw).strip():
        return False
    row_label = canonicalize_uk_portfolio_label(str(raw).strip())
    if not row_label:
        return False
    prop_label = portfolio_jurisdiction_label(property_doc, client_doc or {})
    prop_canon = canonicalize_uk_portfolio_label(prop_label) or prop_label
    return bool(row_label and prop_canon and row_label != prop_canon)


def requirement_row_passes_client_runtime_surface_gates(
    row: Dict[str, Any],
    *,
    property_doc: Dict[str, Any],
    client_doc: Optional[Dict[str, Any]],
    plan_types_lower: Set[str],
    published_registry_entries: Optional[Dict[str, Any]],
) -> bool:
    """
    Pure predicate: caller supplies property doc, client doc, and precomputed planner types
    for that property (from ``build_requirement_plan_for_property`` with the same published snapshot).
    """
    if _status_upper(row.get("applicability")) == "NOT_REQUIRED" or _status_upper(row.get("status")) == "NOT_REQUIRED":
        return False
    if row.get("client_surface_visible") is False:
        return False
    if _primary_action_hidden(row):
        return False
    if _registry_metadata_archived(row):
        return False
    if _registry_draft_or_unpublished_materialization(row):
        return False
    if _explicit_row_jurisdiction_mismatches_property(row, property_doc, client_doc):
        return False

    rtype = _norm_requirement_type(row)
    if not rtype:
        return False

    if _needs_catalog_planner_membership(row):
        if rtype not in plan_types_lower:
            return False

    return True


def _property_plan_types_lower(
    property_doc: Dict[str, Any],
    client_doc: Optional[Dict[str, Any]],
    published_registry_entries: Optional[Dict[str, Any]],
) -> Set[str]:
    plan = build_requirement_plan_for_property(
        property_doc,
        client_doc,
        published_registry_entries=published_registry_entries,
    )
    return {str(x.requirement_type or "").strip().lower() for x in plan if str(x.requirement_type or "").strip()}


async def filter_requirement_rows_for_client_runtime_surfaces(
    db,
    *,
    client_id: str,
    requirements: List[Dict[str, Any]],
    client_doc: Optional[Dict[str, Any]] = None,
    properties: Optional[List[Dict[str, Any]]] = None,
    published_registry_entries: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Async safe wrapper: loads published snapshot once, resolves property docs, filters rows.
    """
    if not requirements:
        return []

    if published_registry_entries is None:
        try:
            published_registry_entries = await fetch_active_published_registry_entries(db)
        except TypeError:
            # Tests may pass a stub ``db`` without awaitable collection accessors; planner still runs.
            published_registry_entries = None

    if client_doc is None:
        client_doc = await db.clients.find_one({"client_id": client_id}, {"_id": 0}) or {}

    # Prefer authoritative DB property docs for planner membership + conditions; caller-supplied
    # ``properties`` is a fallback when tests or offline callers omit Mongo reads.
    prop_by_id: Dict[str, Dict[str, Any]] = {}
    if properties:
        for p in properties:
            pid = p.get("property_id")
            if pid:
                prop_by_id[str(pid)] = dict(p)

    req_pids = sorted({str(r.get("property_id")) for r in requirements if r.get("property_id")})
    if req_pids:
        missing = [pid for pid in req_pids if str(pid) not in prop_by_id]
        if missing:
            cur = db.properties.find(
                {"client_id": client_id, "property_id": {"$in": missing}},
                {"_id": 0},
            )
            async for p in cur:
                pid = p.get("property_id")
                if pid:
                    prop_by_id[str(pid)] = p

    plan_cache: Dict[str, Set[str]] = {}

    def plan_for(pid: str) -> Set[str]:
        if pid in plan_cache:
            return plan_cache[pid]
        prop = prop_by_id.get(pid) or {}
        types_lower = _property_plan_types_lower(prop, client_doc, published_registry_entries)
        plan_cache[pid] = types_lower
        return types_lower

    out: List[Dict[str, Any]] = []
    for row in requirements:
        pid = row.get("property_id")
        if not pid:
            continue
        prop = prop_by_id.get(str(pid))
        if not prop:
            continue
        pt = plan_for(str(pid))
        if requirement_row_passes_client_runtime_surface_gates(
            row,
            property_doc=prop,
            client_doc=client_doc,
            plan_types_lower=pt,
            published_registry_entries=published_registry_entries,
        ):
            out.append(row)
    return out


async def requirement_row_eligible_on_client_runtime_surfaces(
    db,
    *,
    client_id: str,
    row: Dict[str, Any],
    client_doc: Optional[Dict[str, Any]] = None,
    property_doc: Optional[Dict[str, Any]] = None,
    published_registry_entries: Optional[Dict[str, Any]] = None,
) -> bool:
    """Single-row convenience for explanation routes and spot checks."""
    pid = row.get("property_id")
    if not pid:
        return False
    prop = property_doc
    if prop is None:
        prop = await db.properties.find_one(
            {"client_id": client_id, "property_id": pid},
            {"_id": 0},
        )
    if not prop:
        return False
    filtered = await filter_requirement_rows_for_client_runtime_surfaces(
        db,
        client_id=client_id,
        requirements=[row],
        client_doc=client_doc,
        properties=[prop],
        published_registry_entries=published_registry_entries,
    )
    return len(filtered) == 1


__all__ = (
    "CLIENT_RUNTIME_REQUIREMENT_SURFACE_INVARIANT",
    "filter_requirement_rows_for_client_runtime_surfaces",
    "requirement_row_passes_client_runtime_surface_gates",
    "requirement_row_eligible_on_client_runtime_surfaces",
)
