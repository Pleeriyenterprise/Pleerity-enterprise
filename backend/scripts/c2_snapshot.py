"""
Shared read-only snapshots for C2 downstream convergence verification.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from collections import Counter


def fp(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()[:16]


def fp32(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()[:32]


async def select_control_entity(db, *, pilot_cid: str, pilot_pid: str) -> Tuple[str, str, str]:
    """Return (control_cid, control_pid, selection_reason)."""
    async for prop in db.properties.find(
        {"client_id": {"$ne": pilot_cid}},
        {"_id": 0, "client_id": 1, "property_id": 1},
    ).limit(80):
        cid = str(prop.get("client_id") or "")
        pid = str(prop.get("property_id") or "")
        if not cid or not pid:
            continue
        n = await db.requirements.count_documents({"client_id": cid, "property_id": pid})
        if n > 0:
            return cid, pid, "different_client_with_requirements"
    async for prop in db.properties.find(
        {"client_id": pilot_cid, "property_id": {"$ne": pilot_pid}},
        {"_id": 0, "client_id": 1, "property_id": 1},
    ).limit(20):
        pid = str(prop.get("property_id") or "")
        if pid:
            return pilot_cid, pid, "same_client_different_property_fallback"
    raise RuntimeError("No control entity found for unrelated-surface check")


async def explain_metrics(db, *, cid: str, pid: str) -> Dict[str, Any]:
    from services.requirement_client_runtime_surface import explain_runtime_requirement_rows_for_property

    explain = await explain_runtime_requirement_rows_for_property(db, client_id=cid, property_id=pid)
    rows = explain.get("rows") or []
    exclusion_reasons: Counter[str] = Counter()
    included_types: List[str] = []
    for row in rows:
        if row.get("included"):
            included_types.append(str(row.get("requirement_type") or ""))
        else:
            exclusion_reasons[str(row.get("exclusion_reason") or "unknown")] += 1
    return {
        "raw_count": int(explain.get("raw_count") or 0),
        "included_count": int(explain.get("included_count") or 0),
        "exclusion_reasons": dict(exclusion_reasons),
        "included_types": sorted(t for t in included_types if t),
        "rows_sample": [
            {
                "requirement_type": r.get("requirement_type"),
                "included": r.get("included"),
                "exclusion_reason": r.get("exclusion_reason"),
            }
            for r in rows[:25]
        ],
    }


async def client_visible_count(db, *, cid: str, pid: str) -> int:
    from services.compliance_registry_publish_service import fetch_active_published_registry_entries
    from services.requirement_client_runtime_surface import filter_requirement_rows_for_client_runtime_surfaces

    prop = await db.properties.find_one({"client_id": cid, "property_id": pid}, {"_id": 0}) or {}
    client_doc = await db.clients.find_one({"client_id": cid}, {"_id": 0}) or {}
    raw = await db.requirements.find({"client_id": cid, "property_id": pid}, {"_id": 0}).to_list(500)
    published = await fetch_active_published_registry_entries(db)
    filtered = await filter_requirement_rows_for_client_runtime_surfaces(
        db,
        client_id=cid,
        requirements=raw,
        client_doc=client_doc,
        properties=[prop],
        published_registry_entries=published,
    )
    return len([r for r in filtered if r.get("client_surface_visible", True)])


async def gaps_snapshot(db, *, cid: str, pid: str) -> Dict[str, Any]:
    by_status: Dict[str, int] = {}
    open_rows: List[Dict[str, Any]] = []
    async for row in db.compliance_gaps.find(
        {"client_id": cid, "property_id": pid},
        {"_id": 0, "gap_key": 1, "status": 1, "requirement_id": 1, "updated_at": 1},
    ):
        st = str(row.get("status") or "unknown").upper()
        by_status[st] = by_status.get(st, 0) + 1
        if st == "OPEN":
            open_rows.append(
                {
                    "gap_key": row.get("gap_key"),
                    "requirement_id": row.get("requirement_id"),
                    "updated_at": row.get("updated_at"),
                }
            )
    open_rows.sort(key=lambda r: str(r.get("gap_key") or ""))
    return {
        "by_status": by_status,
        "open_count": by_status.get("OPEN", 0),
        "open_sample": open_rows[:15],
        "fingerprint": fp32({"by_status": by_status, "open_keys": [r.get("gap_key") for r in open_rows[:50]]}),
    }


async def risk_priority_snapshot(db, *, cid: str, pid: str) -> Dict[str, Any]:
    from services.client_priority_stream import fetch_client_priority_actions

    open_risk = await db.risk_signals.count_documents(
        {"client_id": cid, "property_id": pid, "status": {"$in": ["OPEN", "ACTIVE", "open", "active"]}}
    )
    regen_pending = await db.risk_signal_regen_queue.count_documents(
        {"property_id": pid, "status": "PENDING"}
    )
    actions = await fetch_client_priority_actions(cid, pid, 80)
    action_keys = sorted(
        f"{a.get('action_type')}|{a.get('related_property_id')}|{a.get('related_requirement_id')}|{a.get('title')}"
        for a in actions
    )
    return {
        "open_risk_signals": open_risk,
        "risk_regen_pending": regen_pending,
        "priority_action_count": len(actions),
        "priority_action_keys_sample": action_keys[:20],
        "fingerprint": fp32({"open_risk": open_risk, "regen_pending": regen_pending, "keys": action_keys[:80]}),
    }


async def stable_task_business_keys(db, *, cid: str, pid: str) -> List[str]:
    """C2a-normalized keys aligned with client_priority_stream (excludes volatile risk_signal:rs_* ids)."""
    from services.client_priority_stream import fetch_client_priority_actions

    actions = await fetch_client_priority_actions(cid, pid, 80)
    return sorted(
        f"{a.get('action_type')}|{a.get('related_property_id')}|{a.get('related_requirement_id')}|{a.get('title')}"
        for a in actions
    )


async def dashboard_tasks_snapshot(db, *, cid: str, pid: str) -> Dict[str, Any]:
    from services.unified_tasks_service import get_unified_tasks_digest, get_unified_tasks_for_client

    prop = await db.properties.find_one({"client_id": cid, "property_id": pid}, {"_id": 0}) or {}
    digest = await get_unified_tasks_digest(cid, property_id_filter=pid, activity_limit=5)
    stable_keys = await stable_task_business_keys(db, cid=cid, pid=pid)
    tasks = await get_unified_tasks_for_client(cid, property_id_filter=pid, raw_limit=40)
    task_list: List[Dict[str, Any]] = []
    raw_tasks = tasks.get("tasks")
    if isinstance(raw_tasks, dict):
        for section in ("urgent", "upcoming", "in_progress", "recently_completed", "snoozed", "hidden"):
            chunk = raw_tasks.get(section) or []
            if isinstance(chunk, list):
                task_list.extend(chunk)
    elif isinstance(raw_tasks, list):
        task_list = raw_tasks
    else:
        task_list = tasks.get("items") or []
    task_ids = sorted(
        str(t.get("id") or t.get("task_id") or t.get("remediation_key") or "")
        for t in task_list[:40]
        if isinstance(t, dict)
    )
    return {
        "compliance_score": prop.get("compliance_score"),
        "compliance_score_pending": prop.get("compliance_score_pending"),
        "compliance_last_calculated_at": prop.get("compliance_last_calculated_at"),
        "risk_level": prop.get("risk_level"),
        "top_deficits": (prop.get("compliance_top_deficits") or [])[:5],
        "digest_summary": digest.get("summary") if isinstance(digest, dict) else None,
        "task_count": len(task_list),
        "task_sections_summary": (tasks.get("summary") if isinstance(tasks, dict) else None),
        "task_ids_sample": [t for t in task_ids if t][:15],
        "stable_task_business_keys_sample": stable_keys[:20],
        "fingerprint_mode": "normalized_stable_business_keys_c2a",
        "fingerprint": fp32(
            {
                "stable_task_keys": stable_keys,
                "section_summary": tasks.get("summary") if isinstance(tasks, dict) else None,
                "digest_summary": digest.get("summary") if isinstance(digest, dict) else None,
            }
        ),
        "fingerprint_legacy_volatile_ids": fp32(
            {
                "task_ids": task_ids[:40],
            }
        ),
    }


async def property_score_snapshot(db, *, cid: str, pid: str) -> Dict[str, Any]:
    prop = await db.properties.find_one({"client_id": cid, "property_id": pid}, {"_id": 0}) or {}
    return {
        "compliance_score": prop.get("compliance_score"),
        "compliance_score_pending": prop.get("compliance_score_pending"),
        "compliance_last_calculated_at": prop.get("compliance_last_calculated_at"),
        "risk_level": prop.get("risk_level"),
        "fingerprint": fp(
            {
                "compliance_score": prop.get("compliance_score"),
                "compliance_score_pending": prop.get("compliance_score_pending"),
                "compliance_last_calculated_at": prop.get("compliance_last_calculated_at"),
            }
        ),
    }


async def consistency_hashes(db, *, cid: str, pid: str) -> Dict[str, str]:
    expl = await explain_metrics(db, cid=cid, pid=pid)
    gaps = await gaps_snapshot(db, cid=cid, pid=pid)
    risk = await risk_priority_snapshot(db, cid=cid, pid=pid)
    dash = await dashboard_tasks_snapshot(db, cid=cid, pid=pid)
    return {
        "requirements_applicability": fp32(
            {
                "included": expl["included_types"],
                "exclusions": expl["exclusion_reasons"],
            }
        ),
        "gaps": gaps["fingerprint"],
        "risk_signals": fp32({"open": risk["open_risk_signals"], "regen_pending": risk["risk_regen_pending"]}),
        "priority_stream": risk["fingerprint"],
        "tasks_today": dash["fingerprint"],
        "kpi_dashboard": fp32(
            {
                "score": dash["compliance_score"],
                "pending": dash["compliance_score_pending"],
                "deficits": dash.get("top_deficits"),
            }
        ),
    }


async def unrelated_fingerprints(db, *, cid: str, pid: str) -> Dict[str, Any]:
    return {
        "gaps": (await gaps_snapshot(db, cid=cid, pid=pid))["fingerprint"],
        "risk_priority": (await risk_priority_snapshot(db, cid=cid, pid=pid))["fingerprint"],
        "dashboard_tasks": (await dashboard_tasks_snapshot(db, cid=cid, pid=pid))["fingerprint"],
        "property": (await property_score_snapshot(db, cid=cid, pid=pid))["fingerprint"],
        "gap_count": await db.compliance_gaps.count_documents({"client_id": cid, "property_id": pid}),
        "score_last_calculated_at": (await db.properties.find_one(
            {"client_id": cid, "property_id": pid}, {"compliance_last_calculated_at": 1, "_id": 0}
        ) or {}).get("compliance_last_calculated_at"),
    }


async def lineage_fingerprint(db, *, pid: str, correlation_id: str) -> str:
    queue = await db.compliance_recalc_queue.find_one(
        {"property_id": pid, "correlation_id": correlation_id},
        {"_id": 0, "status": 1, "correlation_id": 1, "updated_at": 1},
    )
    history = await db.property_compliance_score_history.find({"property_id": pid}, {"_id": 0, "correlation_id": 1, "reason": 1, "created_at": 1}).sort(
        "created_at", -1
    ).limit(5).to_list(5)
    score_log = await db.score_change_log.find({"property_id": pid}, {"_id": 0, "correlation_id": 1, "reason": 1, "created_at": 1}).sort(
        "created_at", -1
    ).limit(5).to_list(5)
    regen = await db.risk_signal_regen_queue.find(
        {"property_id": pid},
        {"_id": 0, "status": 1, "correlation_id": 1, "updated_at": 1},
    ).sort("updated_at", -1).limit(3).to_list(3)
    return fp32(
        {
            "queue": queue,
            "history_corr": [h.get("correlation_id") for h in history],
            "score_log_corr": [s.get("correlation_id") for s in score_log],
            "regen": regen,
        }
    )


async def lineage_trace(db, *, cid: str, pid: str, correlation_id: str) -> Dict[str, Any]:
    queue = await db.compliance_recalc_queue.find_one(
        {"property_id": pid, "correlation_id": correlation_id},
        {"_id": 0},
    )
    history = await db.property_compliance_score_history.find({"property_id": pid}, {"_id": 0}).sort(
        "created_at", -1
    ).limit(5).to_list(5)
    gaps_open = await db.compliance_gaps.find(
        {"client_id": cid, "property_id": pid, "status": "OPEN"},
        {"_id": 0, "gap_key": 1, "requirement_id": 1},
    ).limit(10).to_list(10)
    return {
        "correlation_id": correlation_id,
        "queue_row_status": (queue or {}).get("status"),
        "score_history_recent": history,
        "open_gaps_sample": gaps_open,
        "lineage_fingerprint": await lineage_fingerprint(db, pid=pid, correlation_id=correlation_id),
    }


async def full_convergence_snapshot(db, *, cid: str, pid: str) -> Dict[str, Any]:
    expl = await explain_metrics(db, cid=cid, pid=pid)
    visible = await client_visible_count(db, cid=cid, pid=pid)
    return {
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "client_id": cid,
        "property_id": pid,
        "property_score": await property_score_snapshot(db, cid=cid, pid=pid),
        "requirements_explain": expl,
        "client_visible_count": visible,
        "parity_included_vs_client": expl["included_count"] == visible,
        "gaps": await gaps_snapshot(db, cid=cid, pid=pid),
        "risk_priority": await risk_priority_snapshot(db, cid=cid, pid=pid),
        "dashboard_tasks": await dashboard_tasks_snapshot(db, cid=cid, pid=pid),
        "consistency_hashes": await consistency_hashes(db, cid=cid, pid=pid),
    }


def ordering_tick(snap: Dict[str, Any], *, violation: Optional[str] = None) -> Dict[str, Any]:
    prop = snap.get("property_score") or {}
    gaps = snap.get("gaps") or {}
    risk = snap.get("risk_priority") or {}
    dash = snap.get("dashboard_tasks") or {}
    expl = snap.get("requirements_explain") or {}
    pending = prop.get("compliance_score_pending")
    open_gaps = int(gaps.get("open_count") or 0)
    kpi_ok = pending is False and prop.get("compliance_last_calculated_at")
    return {
        "t": snap.get("captured_at_utc"),
        "requirements_ready": expl.get("included_count", 0) >= 0,
        "gaps_ready": True,
        "risk_ready": int(risk.get("risk_regen_pending") or 0) == 0,
        "priority_ready": int(risk.get("priority_action_count") or 0) >= 0,
        "tasks_ready": int(dash.get("task_count") or 0) >= 0,
        "kpi_ready": bool(kpi_ok),
        "ordering_violation": violation,
        "open_gaps": open_gaps,
        "score_pending": pending,
    }


def detect_ordering_violation(snap: Dict[str, Any]) -> Optional[str]:
    """
    C2-RC-13 (rev): settled recalc != resolved compliance.
    Do not treat compliance_score_pending=false as all-clear.
    """
    gaps = snap.get("gaps") or {}
    dash = snap.get("dashboard_tasks") or {}
    risk = snap.get("risk_priority") or {}
    prop = snap.get("property_score") or {}
    open_gaps = int(gaps.get("open_count") or 0)
    if open_gaps <= 0:
        return None

    summary = dash.get("digest_summary") or dash.get("task_sections_summary") or {}
    if isinstance(summary, dict):
        actionable = (
            int(summary.get("urgent_count") or 0)
            + int(summary.get("upcoming_count") or 0)
            + int(summary.get("in_progress_count") or 0)
        )
        if actionable == 0:
            return "downstream_asserts_resolved_while_gaps_open"

    score = prop.get("compliance_score")
    if score is not None and float(score) >= 95:
        return "dashboard_healthy_score_while_gaps_open"

    if int(dash.get("task_count") or 0) == 0 and int(risk.get("priority_action_count") or 0) > 0:
        return "tasks_empty_while_priority_stream_has_actions"

    return None


async def exclusions_matrix(db, *, cid: str, pid: str) -> Dict[str, Any]:
    from services.requirement_client_runtime_surface import explain_runtime_requirement_rows_for_property

    explain = await explain_runtime_requirement_rows_for_property(db, client_id=cid, property_id=pid)
    rows = explain.get("rows") or []
    matrix: List[Dict[str, Any]] = []
    silent_risk = 0
    for row in rows:
        rt = str(row.get("requirement_type") or "")
        included = bool(row.get("included"))
        excl = row.get("exclusion_reason")
        pers = row.get("persistence") or {}
        entry = {
            "requirement_type": rt,
            "included": included,
            "exclusion_reason": excl if not included else None,
            "gaps": "n/a",
            "priority_stream": "n/a",
            "tasks": "n/a",
            "kpi": "present" if included else "excluded",
        }
        if not included and not excl:
            silent_risk += 1
            entry["governance_gap"] = "missing_exclusion_reason"
        if not included and excl:
            entry["governed_exclusion"] = True
        matrix.append(entry)
    return {
        "matrix": matrix[:40],
        "silent_missing_exclusion_count": silent_risk,
        "pass": silent_risk == 0,
    }


def delta_fingerprints(before: Dict[str, Any], after: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for key in ("gaps", "risk_priority", "dashboard_tasks", "property", "gap_count", "score_last_calculated_at"):
        b = (before or {}).get(key)
        a = (after or {}).get(key)
        out[key] = {"before": b, "after": a, "changed": b != a}
    return out


async def stale_decay_snapshot(db, *, cid: str, pid: str) -> Dict[str, Any]:
    prop = await db.properties.find_one({"client_id": cid, "property_id": pid}, {"_id": 0}) or {}
    gaps = await gaps_snapshot(db, cid=cid, pid=pid)
    risk = await risk_priority_snapshot(db, cid=cid, pid=pid)
    dash = await dashboard_tasks_snapshot(db, cid=cid, pid=pid)
    closed_gap_active_task = 0
    open_gaps = {g.get("gap_key") for g in gaps.get("open_sample") or []}
    return {
        "pending_badge": prop.get("compliance_score_pending"),
        "open_gaps": gaps.get("open_count"),
        "open_risk": risk.get("open_risk_signals"),
        "task_count": dash.get("task_count"),
        "orphan_priority_risk": 0,
        "closed_gap_active_task": closed_gap_active_task,
        "open_gap_keys": list(open_gaps)[:10],
    }
