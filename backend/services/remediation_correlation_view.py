"""
Stream C — internal remediation correlation read-model (v1).

Read-only, property-scoped joins across compliance_gaps, maintenance_issues,
work_orders, risk_signals, audit_logs, property_compliance_score_history, score_change_log.

Gated by FEATURE_REMEDIATION_CORRELATION_VIEW_V1. Not a source of truth.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Literal, Optional, Tuple

FEATURE_ENV = "FEATURE_REMEDIATION_CORRELATION_VIEW_V1"

DISCLAIMER = (
    "Read-only correlation for support investigation. "
    "Not a source of truth for compliance posture, billing, or legal outcome."
)

CAP_AUDIT_LOGS = 50
CAP_SCORE_HISTORY = 20
CAP_SCORE_CHANGE_LOG = 20
CAP_LINKED_ISSUES = 10
CAP_LINKED_WORK_ORDERS = 10

ENTRY_KINDS = frozenset({"gap_key", "issue_id", "work_order_id", "risk_signal_id"})

SourceSystem = Literal["gap", "maintenance_issue", "work_order", "risk_signal"]

# Work order terminal statuses (maintenance_service)
_WO_TERMINAL = frozenset({"COMPLETED", "VERIFIED", "CLOSED", "CANCELLED"})
# Issue terminal (maintenance_issues_service)
_ISSUE_TERMINAL = frozenset({"resolved", "closed", "cancelled"})


def is_remediation_correlation_view_v1_enabled() -> bool:
    return os.getenv(FEATURE_ENV, "").strip().lower() in ("1", "true", "yes")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_as_of(raw: Optional[str]) -> datetime:
    if not raw or not str(raw).strip():
        return _utc_now()
    s = str(raw).strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        raise ValueError("Invalid as_of datetime")


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _window(as_of: datetime, radius_days: int) -> Tuple[str, str]:
    r = max(1, min(int(radius_days), 31))
    start = as_of - timedelta(days=r)
    end = as_of + timedelta(days=r)
    return _iso(start), _iso(end)


def _remediation_key(source_system: SourceSystem, value: str) -> str:
    v = (value or "").strip()
    if source_system == "gap":
        return v
    if source_system == "risk_signal":
        return f"risk:{v}"
    if source_system == "work_order":
        return f"wo:{v}"
    return f"issue:{v}"


def _strip_id(doc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not doc:
        return None
    return {k: v for k, v in doc.items() if k != "_id"}


def _issue_operational_closed(status: Optional[str]) -> bool:
    return (status or "").strip().lower() in _ISSUE_TERMINAL


def _wo_operational_closed(status: Optional[str]) -> bool:
    return (status or "").strip().upper() in _WO_TERMINAL


def _risk_operational_closed(status: Optional[str]) -> bool:
    s = (status or "").strip().lower()
    return s in ("resolved", "acknowledged")


def _gap_compliance_closed(status: Optional[str]) -> bool:
    return (status or "").strip().lower() == "resolved"


def _primary_snapshot_gap(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "gap_key": row.get("gap_key"),
        "status": row.get("status"),
        "gap_kind": row.get("gap_kind"),
        "severity": row.get("severity"),
        "requirement_id": row.get("requirement_id"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
        "resolved_at": row.get("resolved_at"),
        "resolved_reason": row.get("resolved_reason"),
    }


def _primary_snapshot_issue(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "issue_id": row.get("issue_id"),
        "status": row.get("status"),
        "operational_root_key": row.get("operational_root_key"),
        "created_from": row.get("created_from"),
        "risk_signal_id": row.get("risk_signal_id"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


def _primary_snapshot_wo(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "work_order_id": row.get("work_order_id"),
        "status": row.get("status"),
        "issue_id": row.get("issue_id"),
        "risk_signal_id": row.get("risk_signal_id"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


def _primary_snapshot_risk(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "signal_id": row.get("signal_id"),
        "status": row.get("status"),
        "risk_type": row.get("risk_type"),
        "signal_category": row.get("signal_category"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


async def _fetch_gap(db, client_id: str, property_id: str, gap_key: str) -> Optional[Dict[str, Any]]:
    doc = await db.compliance_gaps.find_one(
        {"client_id": client_id, "property_id": property_id, "gap_key": gap_key},
        {"_id": 0},
    )
    return _strip_id(doc)


async def _fetch_issue(db, client_id: str, property_id: str, issue_id: str) -> Optional[Dict[str, Any]]:
    doc = await db.maintenance_issues.find_one(
        {"client_id": client_id, "property_id": property_id, "issue_id": issue_id},
        {"_id": 0},
    )
    return _strip_id(doc)


async def _fetch_wo(db, client_id: str, property_id: str, work_order_id: str) -> Optional[Dict[str, Any]]:
    doc = await db.work_orders.find_one(
        {"client_id": client_id, "property_id": property_id, "work_order_id": work_order_id},
        {"_id": 0},
    )
    return _strip_id(doc)


async def _fetch_risk(db, client_id: str, property_id: str, signal_id: str) -> Optional[Dict[str, Any]]:
    doc = await db.risk_signals.find_one(
        {"client_id": client_id, "property_id": property_id, "signal_id": signal_id},
        {"_id": 0},
    )
    return _strip_id(doc)


async def _issues_for_gap_key(
    db, client_id: str, property_id: str, gap_key: str, cap: int
) -> Tuple[List[Dict[str, Any]], bool]:
    cur = (
        db.maintenance_issues.find(
            {"client_id": client_id, "property_id": property_id, "operational_root_key": gap_key},
            {"_id": 0, "issue_id": 1, "status": 1, "operational_root_key": 1, "created_at": 1},
        )
        .sort("updated_at", -1)
        .limit(cap + 1)
    )
    rows = await cur.to_list(length=cap + 1)
    truncated = len(rows) > cap
    return [_strip_id(r) or r for r in rows[:cap]], truncated


async def _wos_for_issue_ids(
    db, client_id: str, property_id: str, issue_ids: List[str], cap: int
) -> Tuple[List[Dict[str, Any]], bool]:
    if not issue_ids:
        return [], False
    cur = (
        db.work_orders.find(
            {"client_id": client_id, "property_id": property_id, "issue_id": {"$in": issue_ids}},
            {"_id": 0, "work_order_id": 1, "status": 1, "issue_id": 1, "risk_signal_id": 1, "created_at": 1},
        )
        .sort("updated_at", -1)
        .limit(cap + 1)
    )
    rows = await cur.to_list(length=cap + 1)
    truncated = len(rows) > cap
    return [_strip_id(r) or r for r in rows[:cap]], truncated


async def _wos_for_risk_signal(
    db, client_id: str, property_id: str, signal_id: str, cap: int
) -> Tuple[List[Dict[str, Any]], bool]:
    cur = (
        db.work_orders.find(
            {"client_id": client_id, "property_id": property_id, "risk_signal_id": signal_id},
            {"_id": 0, "work_order_id": 1, "status": 1, "issue_id": 1, "risk_signal_id": 1, "created_at": 1},
        )
        .sort("updated_at", -1)
        .limit(cap + 1)
    )
    rows = await cur.to_list(length=cap + 1)
    truncated = len(rows) > cap
    return [_strip_id(r) or r for r in rows[:cap]], truncated


async def _wos_for_single_issue(
    db, client_id: str, property_id: str, issue_id: str, cap: int
) -> Tuple[List[Dict[str, Any]], bool]:
    return await _wos_for_issue_ids(db, client_id, property_id, [issue_id], cap)


def _audit_or_clauses(linked: Dict[str, Any]) -> List[Dict[str, Any]]:
    clauses: List[Dict[str, Any]] = []
    if linked.get("gap_key"):
        gk = str(linked["gap_key"])
        clauses.append({"resource_id": gk})
        clauses.append({"metadata.gap_key": gk})
    if linked.get("issue_id"):
        iid = str(linked["issue_id"])
        clauses.append({"resource_id": iid})
        clauses.append({"metadata.issue_id": iid})
    if linked.get("work_order_id"):
        wid = str(linked["work_order_id"])
        clauses.append({"resource_id": wid})
        clauses.append({"metadata.work_order_id": wid})
    if linked.get("signal_id"):
        sid = str(linked["signal_id"])
        clauses.append({"resource_id": sid})
        clauses.append({"metadata.signal_id": sid})
    rid = linked.get("requirement_id")
    if rid:
        clauses.append({"metadata.requirement_id": str(rid)})
    seen = set()
    out: List[Dict[str, Any]] = []
    for c in clauses:
        key = repr(sorted(c.items()))
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
    return out


async def _load_audits(
    db, client_id: str, win_start: str, win_end: str, or_clauses: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], bool]:
    if not or_clauses:
        return [], False
    q: Dict[str, Any] = {
        "client_id": client_id,
        "timestamp": {"$gte": win_start, "$lte": win_end},
        "$or": or_clauses,
    }
    cur = db.audit_logs.find(q, {"_id": 0}).sort("timestamp", -1).limit(CAP_AUDIT_LOGS + 1)
    rows = await cur.to_list(length=CAP_AUDIT_LOGS + 1)
    truncated = len(rows) > CAP_AUDIT_LOGS
    return [_strip_id(r) or r for r in rows[:CAP_AUDIT_LOGS]], truncated


async def _load_score_history(
    db, client_id: str, property_id: str, win_start: str, win_end: str
) -> Tuple[List[Dict[str, Any]], bool]:
    q = {
        "client_id": client_id,
        "property_id": property_id,
        "created_at": {"$gte": win_start, "$lte": win_end},
    }
    cur = (
        db.property_compliance_score_history.find(q, {"_id": 0})
        .sort("created_at", -1)
        .limit(CAP_SCORE_HISTORY + 1)
    )
    rows = await cur.to_list(length=CAP_SCORE_HISTORY + 1)
    truncated = len(rows) > CAP_SCORE_HISTORY
    return [_strip_id(r) or r for r in rows[:CAP_SCORE_HISTORY]], truncated


def _score_change_log_implies_mapping_advisory(rows: List[Dict[str, Any]]) -> bool:
    """
    True when score_change_log rows carry requirement-level mapping signals worth flagging.

    Not triggered merely because rows exist in the window (empty or absent changed_requirements
    does not qualify).
    """
    for row in rows:
        if not isinstance(row, dict):
            continue
        cr = row.get("changed_requirements")
        if cr is None:
            continue
        if not isinstance(cr, list):
            return True
        if len(cr) == 0:
            continue
        for item in cr:
            if not isinstance(item, dict):
                return True
            rk = item.get("requirement_key")
            if rk is None or str(rk).strip() == "":
                return True
        return True
    return False


async def _load_score_change_log(
    db, client_id: str, property_id: str, win_start: str, win_end: str
) -> Tuple[List[Dict[str, Any]], bool]:
    q = {
        "client_id": client_id,
        "property_id": property_id,
        "created_at": {"$gte": win_start, "$lte": win_end},
    }
    cur = (
        db.score_change_log.find(q, {"_id": 0}).sort("created_at", -1).limit(CAP_SCORE_CHANGE_LOG + 1)
    )
    rows = await cur.to_list(length=CAP_SCORE_CHANGE_LOG + 1)
    truncated = len(rows) > CAP_SCORE_CHANGE_LOG
    return [_strip_id(r) or r for r in rows[:CAP_SCORE_CHANGE_LOG]], truncated


def _closure_row(
    source_system: SourceSystem,
    primary: Dict[str, Any],
    linked_gap: Optional[Dict[str, Any]],
    diagnostic_flags: List[str],
) -> Dict[str, Any]:
    compliance = False
    operational = False
    if source_system == "gap":
        compliance = _gap_compliance_closed(primary.get("status"))
        operational = False
    elif source_system == "maintenance_issue":
        compliance = bool(linked_gap and _gap_compliance_closed(linked_gap.get("status")))
        operational = _issue_operational_closed(primary.get("status"))
    elif source_system == "work_order":
        compliance = bool(linked_gap and _gap_compliance_closed(linked_gap.get("status")))
        operational = _wo_operational_closed(primary.get("status"))
    elif source_system == "risk_signal":
        compliance = False
        operational = _risk_operational_closed(primary.get("status"))

    diagnostic_lane = bool(diagnostic_flags)
    return {
        "compliance": compliance,
        "operational": operational,
        "inbox_visibility": False,
        "diagnostic": diagnostic_lane,
    }


async def build_remediation_correlation_view(
    db,
    *,
    client_id: str,
    property_id: str,
    entry_kind: str,
    entry_value: str,
    as_of_raw: Optional[str] = None,
    window_half_days: int = 14,
) -> Dict[str, Any]:
    """
    Build full JSON response for POST remediation-correlation-view.
    Raises ValueError for invalid input; LookupError when anchor row is missing.
    """
    client_id = (client_id or "").strip()
    property_id = (property_id or "").strip()
    entry_value = (entry_value or "").strip()
    entry_kind = (entry_kind or "").strip()

    if not client_id or not property_id or not entry_value:
        raise ValueError("client_id, property_id, and entry.value are required")
    if entry_kind not in ENTRY_KINDS:
        raise ValueError(f"entry.kind must be one of: {', '.join(sorted(ENTRY_KINDS))}")

    as_of = _parse_as_of(as_of_raw)
    win_start, win_end = _window(as_of, window_half_days)

    truncation = {
        "audits_truncated": False,
        "property_compliance_score_history_truncated": False,
        "score_change_log_truncated": False,
        "linked_issues_truncated": False,
        "linked_work_orders_truncated": False,
    }
    diagnostic_flags: List[str] = []

    linked_entities: Dict[str, Any] = {
        "client_id": client_id,
        "property_id": property_id,
    }
    primary: Dict[str, Any] = {}
    source_system: SourceSystem = "gap"
    linked_gap_doc: Optional[Dict[str, Any]] = None
    issues_slice: List[Dict[str, Any]] = []
    wos_slice: List[Dict[str, Any]] = []

    if entry_kind == "gap_key":
        row = await _fetch_gap(db, client_id, property_id, entry_value)
        if not row:
            raise LookupError("anchor_not_found")
        source_system = "gap"
        primary = row
        linked_entities["gap_key"] = row.get("gap_key")
        linked_entities["requirement_id"] = row.get("requirement_id")
        gk = str(row.get("gap_key") or "")
        issues_slice, it = await _issues_for_gap_key(db, client_id, property_id, gk, CAP_LINKED_ISSUES)
        truncation["linked_issues_truncated"] = it
        iids = [str(i.get("issue_id")) for i in issues_slice if i.get("issue_id")]
        linked_entities["issue_ids"] = iids
        wos_slice, wt = await _wos_for_issue_ids(db, client_id, property_id, iids, CAP_LINKED_WORK_ORDERS)
        truncation["linked_work_orders_truncated"] = wt
        linked_entities["work_order_ids"] = [str(w.get("work_order_id")) for w in wos_slice if w.get("work_order_id")]
        linked_gap_doc = row

    elif entry_kind == "issue_id":
        row = await _fetch_issue(db, client_id, property_id, entry_value)
        if not row:
            raise LookupError("anchor_not_found")
        source_system = "maintenance_issue"
        primary = row
        linked_entities["issue_id"] = row.get("issue_id")
        ork = (row.get("operational_root_key") or "").strip()
        if ork:
            linked_entities["operational_root_key"] = ork
            linked_entities["gap_key"] = ork
            linked_gap_doc = await _fetch_gap(db, client_id, property_id, ork)
            if not linked_gap_doc:
                diagnostic_flags.append("bridge_gap_missing")
            else:
                linked_entities["requirement_id"] = linked_gap_doc.get("requirement_id")
        wos_slice, wt = await _wos_for_single_issue(
            db, client_id, property_id, str(row.get("issue_id")), CAP_LINKED_WORK_ORDERS
        )
        truncation["linked_work_orders_truncated"] = wt
        linked_entities["work_order_ids"] = [str(w.get("work_order_id")) for w in wos_slice if w.get("work_order_id")]

    elif entry_kind == "work_order_id":
        row = await _fetch_wo(db, client_id, property_id, entry_value)
        if not row:
            raise LookupError("anchor_not_found")
        source_system = "work_order"
        primary = row
        linked_entities["work_order_id"] = row.get("work_order_id")
        linked_entities["issue_id"] = row.get("issue_id")
        linked_entities["risk_signal_id"] = row.get("risk_signal_id")
        iid = (row.get("issue_id") or "").strip()
        if iid:
            iss = await _fetch_issue(db, client_id, property_id, iid)
            if iss:
                ork = (iss.get("operational_root_key") or "").strip()
                if ork:
                    linked_entities["operational_root_key"] = ork
                    linked_entities["gap_key"] = ork
                    linked_gap_doc = await _fetch_gap(db, client_id, property_id, ork)
                    if linked_gap_doc:
                        linked_entities["requirement_id"] = linked_gap_doc.get("requirement_id")
                    else:
                        diagnostic_flags.append("bridge_gap_missing")

    else:  # risk_signal_id
        row = await _fetch_risk(db, client_id, property_id, entry_value)
        if not row:
            raise LookupError("anchor_not_found")
        source_system = "risk_signal"
        primary = row
        linked_entities["signal_id"] = row.get("signal_id")
        diagnostic_flags.append("risk_signal_regen_possible")
        sid = str(row.get("signal_id") or "")
        wos_slice, wt = await _wos_for_risk_signal(db, client_id, property_id, sid, CAP_LINKED_WORK_ORDERS)
        truncation["linked_work_orders_truncated"] = wt
        linked_entities["work_order_ids"] = [str(w.get("work_order_id")) for w in wos_slice if w.get("work_order_id")]

    remediation_key = _remediation_key(source_system, entry_value)

    if source_system == "gap":
        snap = _primary_snapshot_gap(primary)
    elif source_system == "maintenance_issue":
        snap = _primary_snapshot_issue(primary)
    elif source_system == "work_order":
        snap = _primary_snapshot_wo(primary)
    else:
        snap = _primary_snapshot_risk(primary)

    or_clauses = _audit_or_clauses(linked_entities)
    audits, at = await _load_audits(db, client_id, win_start, win_end, or_clauses)
    truncation["audits_truncated"] = at

    hist, ht = await _load_score_history(db, client_id, property_id, win_start, win_end)
    truncation["property_compliance_score_history_truncated"] = ht

    scl, st = await _load_score_change_log(db, client_id, property_id, win_start, win_end)
    truncation["score_change_log_truncated"] = st

    if _score_change_log_implies_mapping_advisory(scl):
        diagnostic_flags.append("score_change_log_present_mapping_advisory")

    diagnostic_flags = sorted(set(diagnostic_flags))
    closure_semantics = _closure_row(source_system, primary, linked_gap_doc, diagnostic_flags)

    correlation_row = {
        "remediation_key": remediation_key,
        "source_system": source_system,
        "linked_entities": linked_entities,
        "closure_semantics": closure_semantics,
        "diagnostic_flags": diagnostic_flags,
        "primary_snapshot": snap,
        "linked_issues": issues_slice,
        "linked_work_orders": wos_slice,
    }

    return {
        "non_authoritative": True,
        "client_id": client_id,
        "property_id": property_id,
        "entry": {"kind": entry_kind, "value": entry_value},
        "as_of": _iso(as_of),
        "window": {"start": win_start, "end": win_end},
        "disclaimer": DISCLAIMER,
        "truncation": truncation,
        "rows": [correlation_row],
        "supporting_reads": {
            "audit_logs": audits,
            "property_compliance_score_history": hist,
            "score_change_log": scl,
        },
    }
