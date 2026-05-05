"""
Canonical requirement read-model guard helpers.

Single source for validating requirement_id membership against materialised requirement rows
visible on client runtime surfaces for a property/client scope.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

from database import database
from services.requirement_client_runtime_surface import filter_requirement_rows_for_client_runtime_surfaces


async def get_canonical_requirement_ids_for_property(
    client_id: str,
    property_id: str,
    *,
    db: Optional[Any] = None,
) -> Set[str]:
    """
    Return canonical visible requirement_ids for one property/client pair.

    Canonical here means: materialised requirement rows that survive runtime-surface filtering
    (jurisdiction, planner visibility, registry/runtime gates, alias-family collapse, etc).
    """
    cid = str(client_id or "").strip()
    pid = str(property_id or "").strip()
    if not cid or not pid:
        return set()
    dbh = db or database.get_db()

    prop = await dbh.properties.find_one(
        {"client_id": cid, "property_id": pid},
        {"_id": 0},
    )
    if not isinstance(prop, dict):
        return set()

    client_doc = (
        await dbh.clients.find_one(
            {"client_id": cid},
            {"_id": 0, "client_id": 1, "default_jurisdiction": 1},
        )
        or {}
    )
    raw_reqs = await dbh.requirements.find(
        {"client_id": cid, "property_id": pid},
        {"_id": 0},
    ).to_list(length=5000)
    filtered = await filter_requirement_rows_for_client_runtime_surfaces(
        dbh,
        client_id=cid,
        requirements=list(raw_reqs or []),
        client_doc=client_doc,
        properties=[prop],
    )
    out: Set[str] = set()
    for r in filtered:
        rid = str((r or {}).get("requirement_id") or "").strip()
        if rid:
            out.add(rid)
    return out


async def get_canonical_requirement_ids_map_for_properties(
    client_id: str,
    property_ids: Set[str],
    *,
    db: Optional[Any] = None,
) -> Dict[str, Set[str]]:
    """
    Batched convenience wrapper for multiple properties.
    """
    out: Dict[str, Set[str]] = {}
    dbh = db or database.get_db()
    for pid in {str(x or "").strip() for x in (property_ids or set()) if str(x or "").strip()}:
        out[pid] = await get_canonical_requirement_ids_for_property(client_id, pid, db=dbh)
    return out


def filter_rows_to_canonical_requirement_ids(
    rows: List[Dict[str, Any]],
    canonical_requirement_ids: Set[str],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Keep only rows with requirement_id in canonical_requirement_ids.

    Returns:
      - filtered rows
      - dropped-row diagnostics payloads (source/requirement identifiers only)
    """
    out: List[Dict[str, Any]] = []
    dropped: List[Dict[str, Any]] = []
    canon = {str(x).strip() for x in (canonical_requirement_ids or set()) if str(x).strip()}
    for r in rows or []:
        row = r or {}
        rid = str(row.get("requirement_id") or "").strip()
        if rid and rid in canon:
            out.append(row)
            continue
        dropped.append(
            {
                "requirement_id": rid or None,
                "requirement_code": row.get("requirement_code") or row.get("canonical_code") or None,
                "requirement_type": row.get("requirement_type") or None,
                "source": row.get("source") or None,
                "reason": "missing_or_noncanonical_requirement_id",
            }
        )
    return out, dropped
