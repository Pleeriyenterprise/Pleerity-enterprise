"""
Today workflow residue convergence — stale suppression and lineage dedupe.

Suppresses landlord-facing inbox visibility only; does not delete audit records.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from services.compliance_expiry_policy import resolve_expiring_soon_days_for_requirement
from services.requirement_client_runtime_surface import project_requirement_row_client_runtime
from services.requirement_truth import requirement_has_active_negative_actionability
from services.risk_signal_regen_governance import ISSUE_TERMINAL_STATUSES, WO_TERMINAL_STATUSES

logger = logging.getLogger(__name__)

_SECTION_RANK = {"urgent": 0, "in_progress": 1, "upcoming": 2}
_SOURCE_RANK = {"work_order": 0, "issue": 1, "risk_signal": 2, "priority_action": 3}


def _requirement_id_from_gap_key(gap_key: str) -> Optional[str]:
    parts = [p.strip() for p in str(gap_key or "").split(":") if p.strip()]
    if len(parts) < 4:
        return None
    return parts[2] or None


def _section_rank(section: Optional[str]) -> int:
    return _SECTION_RANK.get(str(section or "").lower(), 9)


def _source_rank(source_type: Optional[str]) -> int:
    return _SOURCE_RANK.get(str(source_type or "").lower(), 5)


def lineage_dedupe_key(task: Dict[str, Any]) -> Optional[str]:
    """Stable lineage identity for operational dedupe (global, not fixture-specific)."""
    meta = task.get("metadata") if isinstance(task.get("metadata"), dict) else {}
    src = str(task.get("source_type") or "").lower()
    pid = str(task.get("property_id") or meta.get("property_id") or "").strip()

    rsid = str(meta.get("related_risk_signal_id") or "").strip()
    if rsid:
        return f"risk_signal:{rsid}"

    root = str(meta.get("operational_root_key") or meta.get("gap_key") or "").strip()
    if root.startswith("risk:"):
        return f"root:{root}"

    if src == "work_order":
        wid = str(meta.get("related_work_order_id") or task.get("source_entity_id") or "").strip()
        if wid:
            return f"work_order:{wid}"
        if root:
            return f"root:{root}"

    if src == "issue":
        iid = str(meta.get("related_issue_id") or task.get("source_entity_id") or "").strip()
        if iid:
            return f"issue:{iid}"
        if root:
            return f"root:{root}"

    if src == "risk_signal":
        sid = str(meta.get("related_risk_signal_id") or task.get("source_entity_id") or "").strip()
        if sid:
            return f"risk_signal:{sid}"

    if root and pid:
        return f"root:{pid}:{root}"
    return None


def _task_precedence_key(task: Dict[str, Any]) -> Tuple[int, int, int, str]:
    """Lower tuple wins retention in a lineage group (WO > issue > risk signal)."""
    return (
        _source_rank(task.get("source_type")),
        _section_rank(task.get("section")),
        -int(task.get("impact_score") or 0),
        str(task.get("id") or ""),
    )


def dedupe_operational_lineage_tasks(tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Collapse near-duplicate operational cards sharing risk/lineage identity.
    Preserves highest-actionability row (urgent WO > in-progress issue > risk signal).
    """
    if not tasks:
        return tasks
    groups: Dict[str, List[Dict[str, Any]]] = {}
    passthrough: List[Dict[str, Any]] = []
    for t in tasks:
        key = lineage_dedupe_key(t)
        if not key:
            passthrough.append(t)
            continue
        groups.setdefault(key, []).append(t)

    kept: List[Dict[str, Any]] = list(passthrough)
    for _key, rows in groups.items():
        if len(rows) == 1:
            kept.append(rows[0])
            continue
        best = min(rows, key=_task_precedence_key)
        kept.append(best)
        if len(rows) > 1:
            logger.info(
                "unified_tasks: deduped operational lineage group key=%s kept=%s dropped=%d",
                _key,
                best.get("id"),
                len(rows) - 1,
            )
    return kept


async def _property_requirements_recovered(
    db: Any,
    *,
    client_id: str,
    property_id: str,
    client_doc: Dict[str, Any],
    prop_doc: Dict[str, Any],
    now: datetime,
) -> bool:
    """True when no requirement on the property has active negative operational actionability."""
    try:
        rows = await db.requirements.find(
            {"client_id": client_id, "property_id": property_id},
            {"_id": 0},
        ).to_list(length=200)
    except Exception:
        return False
    if not rows:
        return True
    window_cache: Dict[str, int] = {}
    for raw in rows:
        req_row = project_requirement_row_client_runtime(raw)
        rid = str(req_row.get("requirement_id") or "")
        if rid not in window_cache:
            window_cache[rid] = resolve_expiring_soon_days_for_requirement(
                req_row, property_doc=prop_doc, client_doc=client_doc
            )
        if requirement_has_active_negative_actionability(
            req_row,
            now=now,
            expiring_window_days=window_cache[rid],
        ):
            return False
    return True


async def _property_has_meaningful_open_workflows(
    db: Any,
    *,
    client_id: str,
    property_id: str,
) -> bool:
    """Non-terminal work orders or non-stale open issues on the property."""
    try:
        wo_n = await db.work_orders.count_documents(
            {
                "client_id": client_id,
                "property_id": property_id,
                "status": {"$nin": list(WO_TERMINAL_STATUSES)},
            }
        )
        if wo_n > 0:
            return True
        issue_n = await db.maintenance_issues.count_documents(
            {
                "client_id": client_id,
                "property_id": property_id,
                "status": {"$nin": list(ISSUE_TERMINAL_STATUSES)},
            }
        )
        return issue_n > 0
    except Exception:
        return True


async def issue_is_stale_operational_residue(
    db: Any,
    *,
    client_id: str,
    issue: Dict[str, Any],
    client_doc: Optional[Dict[str, Any]] = None,
    prop_doc: Optional[Dict[str, Any]] = None,
    now: Optional[datetime] = None,
) -> bool:
    """
    Open issue that should not alarm the landlord inbox (compliance recovered, no meaningful WO).
  Does not mutate the issue document.
    """
    if not issue:
        return False
    status = str(issue.get("status") or "").lower()
    if status in ISSUE_TERMINAL_STATUSES:
        return True

    property_id = str(issue.get("property_id") or "").strip()
    if not property_id:
        return False

    now = now or datetime.now(timezone.utc)
    client_doc = client_doc if isinstance(client_doc, dict) else {}
    prop_doc = prop_doc if isinstance(prop_doc, dict) else {}

    risk_sid = str(issue.get("risk_signal_id") or "").strip()
    trig = str(issue.get("triggering_rule") or "").lower()
    created_from = str(issue.get("created_from") or "").lower()
    gap_key = str(issue.get("operational_root_key") or "").strip()
    is_gap_bridge = bool(gap_key) or "compliance_gap" in trig or created_from in ("compliance", "system")
    is_risk_linked = bool(risk_sid) or gap_key.startswith("risk:")

    if not is_gap_bridge and not is_risk_linked:
        return False

    if not await _property_requirements_recovered(
        db,
        client_id=client_id,
        property_id=property_id,
        client_doc=client_doc,
        prop_doc=prop_doc,
        now=now,
    ):
        return False

    # Gap-bridge: also require satisfied requirement when gap_key parses.
    if is_gap_bridge and gap_key and not gap_key.startswith("risk:"):
        rid = _requirement_id_from_gap_key(gap_key)
        if rid:
            from services.requirement_satisfaction_service import is_requirement_satisfied

            try:
                raw = await db.requirements.find_one(
                    {"client_id": client_id, "requirement_id": rid},
                    {"_id": 0},
                )
            except Exception:
                raw = None
            if isinstance(raw, dict):
                req_row = project_requirement_row_client_runtime(raw)
                if not is_requirement_satisfied(req_row):
                    return False

    # Linked non-terminal WO means real operational work remains.
    linked_wo = str(issue.get("linked_work_order_id") or issue.get("work_order_id") or "").strip()
    if linked_wo:
        try:
            wo = await db.work_orders.find_one(
                {"client_id": client_id, "work_order_id": linked_wo},
                {"_id": 0, "status": 1},
            )
        except Exception:
            wo = None
        if isinstance(wo, dict) and str(wo.get("status") or "").upper() not in WO_TERMINAL_STATUSES:
            return False

    if risk_sid:
        try:
            wo = await db.work_orders.find_one(
                {
                    "client_id": client_id,
                    "risk_signal_id": risk_sid,
                    "status": {"$nin": list(WO_TERMINAL_STATUSES)},
                },
                {"_id": 0, "work_order_id": 1},
            )
        except Exception:
            wo = None
        if wo:
            return False

    return True


async def suppress_stale_operational_residue_tasks(
    *,
    client_id: str,
    tasks: List[Dict[str, Any]],
    db: Any,
) -> List[Dict[str, Any]]:
    """
    Drop gap-bridge and risk-linked operational residue from unified tasks when compliance
    has recovered and no meaningful open workflow progression exists.
    """
    if not tasks:
        return tasks

    now = datetime.now(timezone.utc)
    issue_indices: List[int] = []
    issue_ids: List[str] = []
    risk_indices: List[int] = []
    risk_ids: List[str] = []
    property_ids: Set[str] = set()

    for i, t in enumerate(tasks):
        pid = str(t.get("property_id") or (t.get("metadata") or {}).get("property_id") or "").strip()
        if pid:
            property_ids.add(pid)
        src = str(t.get("source_type") or "").lower()
        meta = t.get("metadata") if isinstance(t.get("metadata"), dict) else {}
        if src == "issue":
            issue_indices.append(i)
            iid = str(meta.get("related_issue_id") or t.get("source_entity_id") or "").strip()
            if iid:
                issue_ids.append(iid)
        elif src == "risk_signal":
            risk_indices.append(i)
            sid = str(meta.get("related_risk_signal_id") or t.get("source_entity_id") or "").strip()
            if sid:
                risk_ids.append(sid)

    if not issue_indices and not risk_indices:
        return tasks

    issues_by_id: Dict[str, Dict[str, Any]] = {}
    if issue_ids:
        try:
            rows = await db.maintenance_issues.find(
                {"client_id": client_id, "issue_id": {"$in": list(set(issue_ids))}},
                {"_id": 0},
            ).to_list(length=max(1, len(set(issue_ids)) * 2))
            issues_by_id = {str(r.get("issue_id") or ""): r for r in rows if r.get("issue_id")}
        except Exception as exc:
            logger.debug("convergence: issue load skipped: %s", exc)

    client_doc: Dict[str, Any] = {}
    prop_by_id: Dict[str, Dict[str, Any]] = {}
    try:
        client_doc = await db.clients.find_one({"client_id": client_id}, {"_id": 0, "default_jurisdiction": 1}) or {}
        if property_ids:
            props = await db.properties.find(
                {"client_id": client_id, "property_id": {"$in": list(property_ids)}},
                {"_id": 0, "property_id": 1, "jurisdiction": 1, "tenancy_active": 1, "furnished": 1, "is_hmo": 1},
            ).to_list(length=max(1, len(property_ids) * 2))
            prop_by_id = {
                str(p.get("property_id") or "").strip(): p
                for p in props
                if str(p.get("property_id") or "").strip()
            }
    except Exception as exc:
        logger.debug("convergence: client/property load skipped: %s", exc)

    drop: Set[int] = set()
    for i in issue_indices:
        t = tasks[i]
        meta = t.get("metadata") if isinstance(t.get("metadata"), dict) else {}
        iid = str(meta.get("related_issue_id") or t.get("source_entity_id") or "").strip()
        iss = issues_by_id.get(iid) or {}
        pid = str(t.get("property_id") or iss.get("property_id") or "").strip()
        if await issue_is_stale_operational_residue(
            db,
            client_id=client_id,
            issue=iss if iss else {
                "property_id": pid,
                "triggering_rule": meta.get("issue_triggering_rule"),
                "created_from": meta.get("issue_created_from"),
                "operational_root_key": meta.get("operational_root_key") or meta.get("gap_key"),
                "status": "open",
            },
            client_doc=client_doc,
            prop_doc=prop_by_id.get(pid) if pid else None,
            now=now,
        ):
            drop.add(i)
            logger.info(
                "unified_tasks: suppressed stale operational issue task id=%s property=%s",
                t.get("id"),
                pid,
            )

    recovered_by_property: Dict[str, bool] = {}
    for i in risk_indices:
        t = tasks[i]
        meta = t.get("metadata") if isinstance(t.get("metadata"), dict) else {}
        pid = str(t.get("property_id") or meta.get("property_id") or "").strip()
        if not pid:
            continue
        if pid not in recovered_by_property:
            recovered_by_property[pid] = await _property_requirements_recovered(
                db,
                client_id=client_id,
                property_id=pid,
                client_doc=client_doc,
                prop_doc=prop_by_id.get(pid) or {},
                now=now,
            )
        if not recovered_by_property[pid]:
            continue
        sid = str(meta.get("related_risk_signal_id") or t.get("source_entity_id") or "").strip()
        if sid:
            try:
                open_issue = await db.maintenance_issues.find_one(
                    {
                        "client_id": client_id,
                        "risk_signal_id": sid,
                        "status": {"$nin": list(ISSUE_TERMINAL_STATUSES)},
                    },
                    {"_id": 0, "issue_id": 1},
                )
            except Exception:
                open_issue = None
            if open_issue:
                continue
            try:
                open_wo = await db.work_orders.find_one(
                    {
                        "client_id": client_id,
                        "risk_signal_id": sid,
                        "status": {"$nin": list(WO_TERMINAL_STATUSES)},
                    },
                    {"_id": 0, "work_order_id": 1},
                )
            except Exception:
                open_wo = None
            if open_wo:
                continue
        if not await _property_has_meaningful_open_workflows(db, client_id=client_id, property_id=pid):
            drop.add(i)
            logger.info(
                "unified_tasks: suppressed stale risk signal task id=%s property=%s",
                t.get("id"),
                pid,
            )

    if not drop:
        return tasks
    return [t for i, t in enumerate(tasks) if i not in drop]
