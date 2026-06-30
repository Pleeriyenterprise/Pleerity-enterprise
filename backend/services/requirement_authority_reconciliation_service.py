"""
Archive superseded alias-duplicate requirement rows (REQUIREMENT-RECONCILIATION-AUTHORITY-01).

Never deletes documents — sets registry lifecycle to superseded with authority_reconciliation metadata.
"""
from __future__ import annotations

import logging
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from database import database
from models import AuditAction, UserRole
from services.requirement_authority_reconciliation_governance import (
    ARCHIVE_REASON,
    ARCHIVE_SOURCE,
    PROGRAMME,
    build_supersede_registry_metadata,
    duplicate_group_key,
    is_active_for_alias_reconciliation,
    is_authority_reconciled_superseded,
    select_canonical_requirement_row,
)
from utils.audit import create_audit_log

logger = logging.getLogger(__name__)


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _count_metrics(rows: List[Dict[str, Any]]) -> Dict[str, int]:
    active_alias = 0
    archived = 0
    duplicate_groups = 0
    by_group: Dict[Tuple[str, str, str], int] = defaultdict(int)
    for row in rows:
        if is_authority_reconciled_superseded(row):
            archived += 1
        key = duplicate_group_key(row)
        if not key:
            continue
        if is_active_for_alias_reconciliation(row):
            active_alias += 1
            by_group[key] += 1
    duplicate_groups = sum(1 for c in by_group.values() if c > 1)
    return {
        "total_rows": len(rows),
        "active_alias_family_rows": active_alias,
        "authority_superseded_rows": archived,
        "duplicate_active_groups": duplicate_groups,
    }


async def _load_requirements(
    db,
    *,
    client_id: Optional[str] = None,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    q: Dict[str, Any] = {}
    if client_id:
        q["client_id"] = client_id
    cursor = db.requirements.find(q, {"_id": 0})
    if limit:
        cursor = cursor.limit(limit)
    return await cursor.to_list(limit or 100000)


async def _load_property_client_maps(
    db, client_ids: Set[str]
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    props: Dict[str, Dict[str, Any]] = {}
    clients: Dict[str, Dict[str, Any]] = {}
    if not client_ids:
        return props, clients
    async for p in db.properties.find({"client_id": {"$in": list(client_ids)}}, {"_id": 0}):
        props[p["property_id"]] = p
    async for c in db.clients.find({"client_id": {"$in": list(client_ids)}}, {"_id": 0}):
        clients[c["client_id"]] = c
    return props, clients


def _group_active_duplicates(rows: List[Dict[str, Any]]) -> Dict[Tuple[str, str, str], List[Dict[str, Any]]]:
    groups: Dict[Tuple[str, str, str], List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = duplicate_group_key(row)
        if not key:
            continue
        groups[key].append(row)
    return {k: v for k, v in groups.items() if sum(1 for r in v if is_active_for_alias_reconciliation(r)) > 1}


async def reconcile_requirement_authority_duplicates(
    *,
    client_id: Optional[str] = None,
    dry_run: bool = True,
    reconciled_by: str = "system:requirement_authority_reconciliation",
    limit: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Detect alias-family duplicate active requirements and supersede non-canonical rows.

    Idempotent: already-superseded rows and canonical winners are never modified again.
    """
    t0 = time.perf_counter()
    db = database.get_db()
    rows_before = await _load_requirements(db, client_id=client_id, limit=limit)
    metrics_before = _count_metrics(rows_before)

    client_ids = {str(r.get("client_id")) for r in rows_before if r.get("client_id")}
    props_by_id, clients_by_id = await _load_property_client_maps(db, client_ids)

    duplicate_groups = _group_active_duplicates(rows_before)
    archived_actions: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []
    canonical_selections: List[Dict[str, Any]] = []

    for (cid, pid, fam), group_rows in sorted(duplicate_groups.items()):
        prop = props_by_id.get(pid)
        client_doc = clients_by_id.get(cid)
        winner = select_canonical_requirement_row(
            group_rows, alias_family=fam, property_doc=prop, client_doc=client_doc
        )
        if not winner:
            skipped.append(
                {
                    "client_id": cid,
                    "property_id": pid,
                    "alias_family": fam,
                    "reason": "no_active_canonical_candidate",
                }
            )
            continue
        win_id = str(winner.get("requirement_id") or "")
        canonical_selections.append(
            {
                "client_id": cid,
                "property_id": pid,
                "alias_family": fam,
                "canonical_requirement_id": win_id,
                "canonical_requirement_type": winner.get("requirement_type"),
                "candidate_ids": [str(r.get("requirement_id")) for r in group_rows],
            }
        )
        for row in group_rows:
            rid = str(row.get("requirement_id") or "")
            if rid == win_id:
                continue
            if not is_active_for_alias_reconciliation(row):
                skipped.append(
                    {
                        "requirement_id": rid,
                        "reason": "not_active_for_reconciliation",
                    }
                )
                continue
            if is_authority_reconciled_superseded(row):
                skipped.append({"requirement_id": rid, "reason": "already_superseded"})
                continue
            now_iso = _utc_iso()
            new_meta = build_supersede_registry_metadata(
                row,
                canonical_row=winner,
                alias_family=fam,
                reconciled_at=now_iso,
                reconciled_by=reconciled_by,
            )
            action = {
                "requirement_id": rid,
                "client_id": cid,
                "property_id": pid,
                "alias_family": fam,
                "canonical_requirement_id": win_id,
                "archive_reason": ARCHIVE_REASON,
                "archive_source": ARCHIVE_SOURCE,
                "previous_requirement_type": row.get("requirement_type"),
                "previous_status": row.get("status"),
                "previous_lifecycle": (new_meta.get("authority_reconciliation") or {}).get(
                    "previous_lifecycle"
                ),
                "evidence_doc_id_preserved": row.get("evidence_doc_id"),
                "dry_run": dry_run,
            }
            archived_actions.append(action)
            if dry_run:
                continue
            before = dict(row)
            await db.requirements.update_one(
                {"requirement_id": rid},
                {"$set": {"registry_metadata": new_meta, "updated_at": now_iso}},
            )
            after = {**before, "registry_metadata": new_meta, "updated_at": now_iso}
            await create_audit_log(
                action=AuditAction.REQUIREMENTS_EVALUATED,
                actor_role=UserRole.ROLE_ADMIN,
                actor_id=reconciled_by,
                client_id=cid,
                resource_type="requirement",
                resource_id=rid,
                before_state={
                    "requirement_id": rid,
                    "requirement_type": before.get("requirement_type"),
                    "status": before.get("status"),
                    "registry_metadata": before.get("registry_metadata"),
                    "evidence_doc_id": before.get("evidence_doc_id"),
                },
                after_state={
                    "requirement_id": rid,
                    "requirement_type": after.get("requirement_type"),
                    "status": after.get("status"),
                    "registry_metadata": new_meta,
                    "evidence_doc_id": after.get("evidence_doc_id"),
                },
                metadata={
                    "programme": PROGRAMME,
                    "archive_reason": ARCHIVE_REASON,
                    "canonical_requirement_id": win_id,
                    "alias_family": fam,
                    "previous_lifecycle": action.get("previous_lifecycle"),
                    "new_lifecycle": "superseded",
                },
                reason_code="AUTHORITY_ALIAS_RECONCILE",
            )

    rows_after = rows_before
    if not dry_run and archived_actions:
        rows_after = await _load_requirements(db, client_id=client_id, limit=limit)
    metrics_after = _count_metrics(rows_after if not dry_run else _simulate_after(rows_before, archived_actions))

    elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
    return {
        "programme": PROGRAMME,
        "dry_run": dry_run,
        "client_id": client_id,
        "reconciled_by": reconciled_by,
        "duration_ms": elapsed_ms,
        "metrics_before": metrics_before,
        "metrics_after": metrics_after,
        "duplicate_families_found": len(duplicate_groups),
        "records_to_archive": len(archived_actions),
        "records_archived": 0 if dry_run else len(archived_actions),
        "records_skipped": len(skipped),
        "canonical_selections": canonical_selections,
        "archive_actions": archived_actions,
        "skipped": skipped[:100],
    }


def _simulate_after(
    rows: List[Dict[str, Any]], actions: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Dry-run after metrics: apply supersede metadata in memory only."""
    by_id = {str(r.get("requirement_id")): dict(r) for r in rows}
    now_iso = _utc_iso()
    for act in actions:
        rid = act["requirement_id"]
        row = by_id.get(rid)
        if not row:
            continue
        winner = by_id.get(act["canonical_requirement_id"]) or {"requirement_id": act["canonical_requirement_id"]}
        meta = build_supersede_registry_metadata(
            row,
            canonical_row=winner,
            alias_family=act["alias_family"],
            reconciled_at=now_iso,
            reconciled_by="dry_run",
        )
        row["registry_metadata"] = meta
        by_id[rid] = row
    return list(by_id.values())
