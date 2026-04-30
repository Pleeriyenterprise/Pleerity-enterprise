"""
Internal applicability resolution queue: high-impact requirements whose **pipeline**
applicability is UNKNOWN (pipeline quality), with **effective** + **source** for runtime view.

Tenant-scoped only. No operator mutations here (use PR4 ops endpoint).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from services.applicability_effective_resolver import has_provenance_storage, resolve_applicability_read_model
from services.applicability_operator_actions import OPERATOR_COMMANDS, REVOKE_OVERRIDE
from services.applicability_operator_resolution_reasons import APPLICABILITY_OPERATOR_REASON_CODES
from services.hiua_operational_uncertainty import derive_hiua_signal_for_open_gap

# High-impact obligation codes (normalized lowercase). Queue membership also uses mandatory+HIGH/CRITICAL.
HIGH_IMPACT_REQUIREMENT_CODES: Set[str] = {
    "gas_safety",
    "eicr",
    "smoke_alarm",
    "co_alarm",
    "hmo_license",
    "hmo_licence",
    "fire_risk_assessment",
}

MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 50

# Cap gap documents loaded for HIUA counting per queue page (tenant + requirement_id $in page).
MAX_GAP_DOCS_FOR_QUEUE_HIUA_EVAL = 2000

# Priority band model (P0 highest): HIUA-eligible open gaps first, then mandatory impact + open gaps, etc.
_PRIORITY_BAND_ORDER = ("P0", "P1", "P2", "P3")

# First matching root cause wins for recommended_next_action (ops ordering, not alphabetical).
# Operator POST body commands, in stable queue response order (subset of OPERATOR_COMMANDS).
_QUEUE_OPERATOR_MARK_COMMANDS_ORDER: Tuple[str, ...] = (
    "MARK_REQUIRED",
    "MARK_NOT_REQUIRED",
    "MARK_NEEDS_REVIEW",
)

_ROOT_CAUSE_TO_RECOMMENDED_ACTION: Tuple[Tuple[str, str], ...] = (
    ("PROVENANCE_NOT_INITIALISED", "Run applicability provenance initialisation / PR1 backfill for the tenant."),
    ("MISSING_JURISDICTION", "Set or verify requirement jurisdiction."),
    ("PROPERTY_CONTEXT_UNAVAILABLE", "Ensure the property record exists and is readable for this requirement."),
    ("PROPERTY_JURISDICTION_MISSING", "Set property jurisdiction on the property record."),
    ("PROPERTY_TYPE_MISSING", "Set property_type on the property record."),
    ("REGISTRY_METADATA_MISSING", "Repair registry metadata / published registry linkage on the requirement."),
)


def build_queue_mongo_filter(*, client_id: str) -> Dict[str, Any]:
    """
    Rows where **pipeline** applicability is UNKNOWN and impact is high:
    - known high-impact codes, OR
    - mandatory with HIGH/CRITICAL policy criticality.
    """
    cid = str(client_id or "").strip()
    codes = sorted(HIGH_IMPACT_REQUIREMENT_CODES)
    return {
        "client_id": cid,
        "pipeline_applicability_state": "UNKNOWN",
        "$or": [
            {"requirement_code_normalized": {"$in": codes}},
            {"requirement_type": {"$in": codes}},
            {
                "$and": [
                    {"is_mandatory": True},
                    {"policy_criticality": {"$in": ["HIGH", "CRITICAL"]}},
                ]
            },
        ],
    }


def classify_applicability_unknown_root_causes(
    requirement_row: Dict[str, Any],
    property_doc: Optional[Dict[str, Any]] = None,
) -> List[str]:
    """
    Deterministic diagnostics only (no inference). Ordered stable list, de-duplicated.
    """
    req = requirement_row if isinstance(requirement_row, dict) else {}
    codes: List[str] = []

    if not has_provenance_storage(req):
        codes.append("PROVENANCE_NOT_INITIALISED")

    if not str(req.get("jurisdiction") or "").strip():
        codes.append("MISSING_JURISDICTION")

    pid = str(req.get("property_id") or "").strip()
    if pid and property_doc is None:
        codes.append("PROPERTY_CONTEXT_UNAVAILABLE")

    if isinstance(property_doc, dict):
        pj = str(
            property_doc.get("jurisdiction")
            or property_doc.get("property_jurisdiction")
            or property_doc.get("scoring_jurisdiction")
            or ""
        ).strip()
        if not pj:
            codes.append("PROPERTY_JURISDICTION_MISSING")
        if not str(property_doc.get("property_type") or "").strip():
            codes.append("PROPERTY_TYPE_MISSING")

    meta = req.get("registry_metadata")
    if not isinstance(meta, dict) or not meta:
        codes.append("REGISTRY_METADATA_MISSING")

    # Stable order for UI/tests
    return sorted(set(codes))


def build_applicability_queue_operator_action_wiring(*, operator_override_active: bool) -> Dict[str, Any]:
    """
    Read-only wiring for PR4 ``POST .../applicability-operator`` from a queue row.
    Reflects ``OPERATOR_COMMANDS`` only — no new execute paths.
    """
    reason_options = sorted(APPLICABILITY_OPERATOR_REASON_CODES)
    actions: List[Dict[str, Any]] = []
    for cmd in _QUEUE_OPERATOR_MARK_COMMANDS_ORDER:
        if cmd not in OPERATOR_COMMANDS:
            continue
        actions.append(
            {
                "command": cmd,
                "available": True,
                "requires_resolution_reason_code": True,
                "resolution_reason_code_options": list(reason_options),
            }
        )
    if REVOKE_OVERRIDE in OPERATOR_COMMANDS:
        actions.append(
            {
                "command": REVOKE_OVERRIDE,
                "available": bool(operator_override_active),
                "requires_resolution_reason_code": True,
                "resolution_reason_code_options": list(reason_options),
            }
        )
    return {
        "applicability_operator_method": "POST",
        "applicability_operator_path_template": (
            "/api/admin/ops/clients/{client_id}/requirements/{requirement_id}/applicability-operator"
        ),
        "actions": actions,
    }


def recommended_next_action_from_root_causes(root_cause_codes: List[str]) -> str:
    """Deterministic ops guidance from classifier codes only (no new predicates)."""
    codes_set = set(root_cause_codes or [])
    for code, action in _ROOT_CAUSE_TO_RECOMMENDED_ACTION:
        if code in codes_set:
            return action
    return "Review pipeline applicability inputs, property context, and registry linkage."


def compute_priority_band(
    *,
    hiua_open_gap_count: int,
    open_gap_count: int,
    is_mandatory: bool,
    policy_criticality: Any,
) -> str:
    """
    P0: at least one HIUA-eligible open gap (existing derive_hiua_signal_for_open_gap, unchanged).
    P1: open gaps on mandatory HIGH/CRITICAL requirements.
    P2: any other open gaps.
    P3: no open gaps (still in queue due to pipeline UNKNOWN / diagnostics).
    """
    pc = str(policy_criticality or "").strip().upper()
    if int(hiua_open_gap_count or 0) > 0:
        return "P0"
    og = int(open_gap_count or 0)
    if og > 0 and bool(is_mandatory) and pc in ("HIGH", "CRITICAL"):
        return "P1"
    if og > 0:
        return "P2"
    return "P3"


def _parse_iso_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    s = str(value).strip()
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (TypeError, ValueError):
        return None


def _requirement_last_updated_at(req: Dict[str, Any]) -> Optional[datetime]:
    candidates: List[Any] = [
        req.get("updated_at"),
        req.get("created_at"),
    ]
    nested = req.get("applicability_provenance") if isinstance(req.get("applicability_provenance"), dict) else {}
    candidates.extend(
        [
            nested.get("pipeline_updated_at"),
            nested.get("effective_updated_at"),
        ]
    )
    ov = nested.get("operator_override") if isinstance(nested.get("operator_override"), dict) else {}
    candidates.append(ov.get("updated_at"))

    best: Optional[datetime] = None
    for c in candidates:
        dt = _parse_iso_datetime(c)
        if dt is None:
            continue
        if best is None or dt > best:
            best = dt
    return best


def _serialize_queue_item(
    req: Dict[str, Any],
    *,
    property_doc: Optional[Dict[str, Any]],
    operational: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    read = resolve_applicability_read_model(req)
    nested = req.get("applicability_provenance") if isinstance(req.get("applicability_provenance"), dict) else {}
    ov = nested.get("operator_override") if isinstance(nested.get("operator_override"), dict) else {}
    root_cause_codes = classify_applicability_unknown_root_causes(req, property_doc)
    evn = req.get("evidence_state_normalized")
    ev_raw = req.get("evidence_state")
    evidence_state = str(evn).strip() if evn is not None and str(evn).strip() else (str(ev_raw).strip() if ev_raw else "")

    last_dt = _requirement_last_updated_at(req)
    last_iso = last_dt.isoformat().replace("+00:00", "Z") if last_dt else None
    now = datetime.now(timezone.utc)
    age_seconds: Optional[int] = None
    if last_dt is not None:
        age_seconds = max(0, int((now - last_dt).total_seconds()))

    op = operational if isinstance(operational, dict) else {}
    open_gap_count = int(op.get("open_gap_count") or 0)
    hiua_open_gap_count = int(op.get("hiua_open_gap_count") or 0)
    priority_band = compute_priority_band(
        hiua_open_gap_count=hiua_open_gap_count,
        open_gap_count=open_gap_count,
        is_mandatory=bool(req.get("is_mandatory")),
        policy_criticality=req.get("policy_criticality"),
    )
    override_active = bool(req.get("operator_override_active") or ov.get("active"))

    return {
        "client_id": req.get("client_id"),
        "property_id": req.get("property_id"),
        "requirement_id": req.get("requirement_id"),
        "requirement_type": req.get("requirement_type"),
        "requirement_code_normalized": req.get("requirement_code_normalized"),
        "jurisdiction": req.get("jurisdiction"),
        "pipeline_applicability_state": read["pipeline_applicability_state"],
        "effective_applicability_state": read["effective_applicability_state"],
        "applicability_resolution_source": read["applicability_resolution_source"],
        "is_mandatory": bool(req.get("is_mandatory")),
        "policy_criticality": req.get("policy_criticality"),
        "status": req.get("status"),
        "evidence_state_normalized": req.get("evidence_state_normalized"),
        "evidence_state": evidence_state or None,
        "operator_override_active": override_active,
        "root_cause_codes": root_cause_codes,
        "priority_band": priority_band,
        "open_gap_count": open_gap_count,
        "hiua_active": hiua_open_gap_count > 0,
        "hiua_open_gap_count": hiua_open_gap_count,
        "last_updated_at": last_iso,
        "age_seconds": age_seconds,
        "recommended_next_action": recommended_next_action_from_root_causes(root_cause_codes),
        "operator_action_wiring": build_applicability_queue_operator_action_wiring(
            operator_override_active=override_active
        ),
    }


_GAP_PROJECTION_HIUA = {
    "_id": 0,
    "gap_key": 1,
    "gap_kind": 1,
    "status": 1,
    "property_id": 1,
    "requirement_id": 1,
    "requirement_code": 1,
    "requirement_code_normalized": 1,
    "requirement_type": 1,
    "applicability_state": 1,
    "pipeline_applicability_state": 1,
    "effective_applicability_state": 1,
    "applicability_resolution_source": 1,
    "applicability_provenance": 1,
    "is_mandatory": 1,
    "policy_criticality": 1,
    "evidence_authority": 1,
    "authority_snapshot": 1,
    "critical_mandatory_breach": 1,
    "high_risk_gap": 1,
    "days_to_expiry": 1,
    "evidence_state_normalized": 1,
}


async def _open_gap_counts_by_requirement(
    db: Any,
    *,
    client_id: str,
    requirement_ids: List[str],
) -> Dict[str, int]:
    if not requirement_ids:
        return {}
    pipeline: List[Dict[str, Any]] = [
        {
            "$match": {
                "client_id": client_id,
                "requirement_id": {"$in": requirement_ids},
                "status": "open",
            }
        },
        {"$group": {"_id": "$requirement_id", "n": {"$sum": 1}}},
    ]
    out: Dict[str, int] = {}
    cur = db.compliance_gaps.aggregate(pipeline)
    async for doc in cur:
        rid = str(doc.get("_id") or "").strip()
        if not rid:
            continue
        try:
            out[rid] = int(doc.get("n") or 0)
        except (TypeError, ValueError):
            out[rid] = 0
    return out


async def _hiua_open_gap_counts_by_requirement(
    db: Any,
    *,
    client_id: str,
    requirement_ids: List[str],
) -> Tuple[Dict[str, int], bool]:
    """
    Count open gaps per requirement where derive_hiua_signal_for_open_gap is true.
    Returns (counts, truncated) if more than MAX_GAP_DOCS_FOR_QUEUE_HIUA_EVAL documents matched.
    """
    if not requirement_ids:
        return {}, False
    lim = max(1, MAX_GAP_DOCS_FOR_QUEUE_HIUA_EVAL)
    cur = db.compliance_gaps.find(
        {"client_id": client_id, "requirement_id": {"$in": requirement_ids}, "status": "open"},
        _GAP_PROJECTION_HIUA,
    ).limit(lim + 1)
    fn = getattr(cur, "to_list", None)
    if callable(fn):
        rows: List[Dict[str, Any]] = await fn(lim + 1)
    else:
        rows = []
        async for doc in cur:
            rows.append(doc)
            if len(rows) > lim:
                break
    truncated = len(rows) > lim
    rows = rows[:lim]
    counts: Dict[str, int] = {}
    for g in rows:
        if not derive_hiua_signal_for_open_gap(g):
            continue
        rid = str(g.get("requirement_id") or "").strip()
        if not rid:
            continue
        counts[rid] = counts.get(rid, 0) + 1
    return counts, truncated


async def list_applicability_resolution_queue_page(
    db: Any,
    *,
    client_id: str,
    limit: int = DEFAULT_PAGE_SIZE,
    after_requirement_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Paginated queue (requirement_id ascending). Fetches property docs for the page in one query.
    """
    cid = str(client_id or "").strip()
    lim = min(max(int(limit or DEFAULT_PAGE_SIZE), 1), MAX_PAGE_SIZE)
    flt = build_queue_mongo_filter(client_id=cid)
    if after_requirement_id and str(after_requirement_id).strip():
        rid = str(after_requirement_id).strip()
        flt = {"$and": [flt, {"requirement_id": {"$gt": rid}}]}

    cur = db.requirements.find(flt, {"_id": 0}).sort("requirement_id", 1).limit(lim + 1)
    rows: List[Dict[str, Any]] = await cur.to_list(lim + 1)
    has_more = len(rows) > lim
    page = rows[:lim]

    prop_ids = sorted({str(r.get("property_id") or "").strip() for r in page if r.get("property_id")})
    props: Dict[str, Dict[str, Any]] = {}
    if prop_ids:
        pc = db.properties.find(
            {"client_id": cid, "property_id": {"$in": prop_ids}},
            {"_id": 0},
        )
        async for p in pc:
            pid = str(p.get("property_id") or "").strip()
            if pid:
                props[pid] = p

    req_ids = [str(r.get("requirement_id") or "").strip() for r in page]
    req_ids = [x for x in req_ids if x]
    gap_counts = await _open_gap_counts_by_requirement(db, client_id=cid, requirement_ids=req_ids)
    hiua_counts, hiua_truncated = await _hiua_open_gap_counts_by_requirement(db, client_id=cid, requirement_ids=req_ids)

    items: List[Dict[str, Any]] = []
    for r in page:
        rid = str(r.get("requirement_id") or "").strip()
        items.append(
            _serialize_queue_item(
                r,
                property_doc=props.get(str(r.get("property_id") or "")),
                operational={
                    "open_gap_count": gap_counts.get(rid, 0),
                    "hiua_open_gap_count": hiua_counts.get(rid, 0),
                },
            )
        )

    next_cursor: Optional[str] = None
    if has_more and page:
        next_cursor = str(page[-1].get("requirement_id") or "")

    return {
        "client_id": cid,
        "items": items,
        "has_more": has_more,
        "next_cursor": next_cursor,
        "page_size": len(items),
        "queue_operational_scan_truncated": bool(hiua_truncated),
        "priority_band_order": list(_PRIORITY_BAND_ORDER),
    }


__all__ = [
    "HIGH_IMPACT_REQUIREMENT_CODES",
    "MAX_GAP_DOCS_FOR_QUEUE_HIUA_EVAL",
    "build_applicability_queue_operator_action_wiring",
    "build_queue_mongo_filter",
    "classify_applicability_unknown_root_causes",
    "compute_priority_band",
    "list_applicability_resolution_queue_page",
    "recommended_next_action_from_root_causes",
]
