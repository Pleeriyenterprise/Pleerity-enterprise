"""
Rule-based Contractor Recommendation Engine (pure logic, no I/O).
Scores and ranks contractors for a work order. Explainable, configurable weights.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from services.compliance_contractor_capability import (
    compliance_match_reasons_verified,
    contractor_verified_qualifies_for_requirement,
    parse_execution_capabilities,
    parse_verified_execution_capabilities,
)
from services.contractor_recommendation_config import (
    DEFAULT_WEIGHTS,
    MIN_SCORE_STRONG_MATCH,
    REQUIRED_CREDENTIALS_BY_TYPE,
    VERIFICATION_REQUIRED_TYPES,
    POSTCODE_PREFIX_LEN,
    REWORK_RATE_MAX_PENALTY,
    HISTORICAL_BREACH_PENALTY_PER_EVENT,
    HISTORICAL_BREACH_PENALTY_CAP,
    WORKLOAD_OPEN_JOBS_REFERENCE,
)
from services.work_order_execution_constants import (
    EXECUTION_CAPABILITY_COMPLIANCE,
    EXECUTION_CAPABILITY_MAINTENANCE,
    WORK_ORDER_KIND_COMPLIANCE,
)

# Trade keys by recommended_contractor_type (align with contractor_service.RECOMMENDED_TYPE_TO_TRADES)
TYPE_TO_TRADES: Dict[str, List[str]] = {
    "gas_safe": ["heating", "gas", "gas_safe", "boiler"],
    "plumber": ["plumbing", "plumber"],
    "electrician": ["electrical", "electrician"],
    "damp_inspection": ["damp", "inspection", "damp_inspection"],
    "general": ["general", "handyman"],
}


def _normalize(s: Optional[str]) -> str:
    return (s or "").strip().lower()


def _parse_wo_dt(val: Any) -> Optional[datetime]:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val if val.tzinfo else val.replace(tzinfo=timezone.utc)
    try:
        return datetime.fromisoformat(str(val).replace("Z", "+00:00"))
    except Exception:
        return None


def compute_assignment_routing_meta(
    work_order: Dict[str, Any],
    *,
    now_utc: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    SLA-aware routing context for assignment UIs (no I/O).
    assignment_urgency: critical | high | normal
    sla_routing_state: breached | at_risk | approaching_deadline | deadline_passed | on_track
    """
    now = now_utc or datetime.now(timezone.utc)
    breached = bool(work_order.get("sla_breached_at"))
    at_risk = bool(work_order.get("sla_breach_risk_at"))
    severity = (work_order.get("severity") or "").strip().lower()
    complete_by = _parse_wo_dt(work_order.get("sla_complete_by"))
    hours_to_complete: Optional[float] = None
    overdue_complete = False
    if complete_by:
        hours_to_complete = round((complete_by - now).total_seconds() / 3600.0, 2)
        overdue_complete = hours_to_complete < 0

    if breached or overdue_complete:
        level = "critical"
        sla_state = "breached" if breached else "deadline_passed"
    elif at_risk or severity in ("urgent", "high") or (hours_to_complete is not None and hours_to_complete <= 24):
        level = "high"
        if at_risk:
            sla_state = "at_risk"
        elif hours_to_complete is not None and hours_to_complete <= 24:
            sla_state = "approaching_deadline"
        else:
            sla_state = "priority_elevated"
    else:
        level = "normal"
        sla_state = "on_track"

    if level == "critical":
        routing_messages = [
            "SLA breached or completion deadline has passed — assign the top eligible contractor without delay."
        ]
    elif level == "high":
        routing_messages = [
            "Elevated urgency (priority or SLA risk) — review ranked contractors immediately."
        ]
    else:
        routing_messages = ["Standard routing — system recommends; operations confirms assignment."]

    return {
        "assignment_urgency": level,
        "sla_routing_state": sla_state,
        "hours_to_sla_complete": hours_to_complete,
        "severity": severity or None,
        "flags": {
            "sla_breached": breached,
            "sla_breach_risk": at_risk,
            "completion_overdue": overdue_complete,
        },
        "routing_messages": routing_messages,
    }


def _adjust_weights_for_urgency(base: Dict[str, int], assignment_urgency: str) -> Dict[str, int]:
    w = dict(base)
    if assignment_urgency == "critical":
        w["trade_match"] = w.get("trade_match", 26) + 4
        w["workload_capacity"] = w.get("workload_capacity", 10) + 5
        w["performance_score"] = w.get("performance_score", 16) + 4
    elif assignment_urgency == "high":
        w["workload_capacity"] = w.get("workload_capacity", 10) + 3
        w["performance_score"] = w.get("performance_score", 16) + 2
    return w


def _trade_match(wo: Dict[str, Any], c: Dict[str, Any], weights: Dict[str, int]) -> Tuple[int, List[str]]:
    """Trade match: 0 or full weight. Reasons if match."""
    rec_type = _normalize(wo.get("recommended_contractor_type") or "general")
    category = _normalize(wo.get("category") or "general")
    trade_keys = list(set(TYPE_TO_TRADES.get(rec_type, ["general"]) + [category]))
    trades = [_normalize(t) for t in (c.get("trade_types") or [])]
    match = any(t in trade_keys for t in trades) or "general" in trades
    if not match:
        return 0, []
    label = (wo.get("category") or wo.get("recommended_contractor_type") or "job").strip()
    if label:
        label_title = label.replace("_", " ").title()
        reason = f"{label_title} trade match"
    else:
        reason = "Trade match for this job"
    return weights.get("trade_match", 26), [reason]


def _region_match(wo: Dict[str, Any], property_doc: Optional[Dict[str, Any]], c: Dict[str, Any], weights: Dict[str, int]) -> Tuple[int, List[str]]:
    """Region / service area match vs property (postcode prefix, outward code, region)."""
    raw_pc = (property_doc.get("postcode") or "").strip().upper() if property_doc else ""
    pc_compact = _normalize(raw_pc.replace(" ", ""))
    outward = ""
    if raw_pc:
        parts = raw_pc.split()
        outward = parts[0].upper() if parts else raw_pc[:4].upper()
    region_wo = _normalize(property_doc.get("region") or "") if property_doc else ""
    areas = [_normalize(a) for a in (c.get("areas_served") or [])]
    coverage = [_normalize(a) for a in (c.get("coverage_area") or [])]
    area_pool = list({*areas, *coverage})
    contractor_region = _normalize(c.get("region") or "")
    reg_pc = _normalize((c.get("registration_postcode") or "").replace(" ", ""))
    w_reg = weights.get("region_match", 12)

    def _exact_postcode_hit() -> bool:
        if not pc_compact:
            return False
        for a in area_pool + ([reg_pc] if reg_pc else []):
            if not a:
                continue
            if a.replace(" ", "") == pc_compact:
                return True
        return False

    def _prefix_hit() -> bool:
        if not outward:
            return False
        for a in area_pool + ([reg_pc] if reg_pc else []):
            if not a:
                continue
            au = a.upper().replace(" ", "")
            if outward in au or au in outward or (len(outward) >= 2 and au.startswith(outward[:2])):
                return True
        if contractor_region and outward and outward[:2] in contractor_region.upper():
            return True
        return False

    if not raw_pc and not region_wo and not area_pool and not contractor_region and not reg_pc:
        return w_reg, ["Service area: national / unspecified (eligible)"]

    if _exact_postcode_hit():
        return w_reg, [f"Exact postcode match ({raw_pc})"]
    if _prefix_hit():
        return w_reg, [f"Same postcode area as property ({outward or raw_pc})"]
    if region_wo and (region_wo in area_pool or region_wo == contractor_region):
        return w_reg, [f"Same region as property ({region_wo})"]
    if not area_pool and not contractor_region and not reg_pc:
        return max(1, w_reg // 2), ["Broad service area (no postcode filter on contractor)"]
    return 0, []


def _credential_match(wo: Dict[str, Any], c: Dict[str, Any], weights: Dict[str, int]) -> Tuple[int, List[str]]:
    """Credential match: has required credential for job type; or vetted when verification required."""
    rec_type = _normalize(wo.get("recommended_contractor_type") or "general")
    required = REQUIRED_CREDENTIALS_BY_TYPE.get(rec_type, [])
    creds = [_normalize(x) for x in (c.get("credentials") or [])]
    vetted = bool(c.get("vetted"))
    if not required:
        if vetted:
            return weights.get("credential_match", 20), ["Vetted"]
        return weights.get("credential_match", 20) // 2, []
    for r in required:
        if any(r in cr or cr in r for cr in creds):
            return weights.get("credential_match", 20), [f"Credential: {r}"]
    if rec_type in VERIFICATION_REQUIRED_TYPES and vetted:
        return weights.get("credential_match", 20) // 2, ["Vetted (verification required type)"]
    return 0, []


def _performance_score(c: Dict[str, Any], weights: Dict[str, int]) -> Tuple[int, List[str]]:
    """Overall contractor intelligence score (0-100) from contractor doc. Higher = more points."""
    score = c.get("performance_score")
    if score is None:
        return 0, []
    try:
        val = float(score)
        if val <= 0:
            return 0, []
        pct = min(1.0, max(0.0, val / 100.0))
        w = weights.get("performance_score", 25) or 0
        points = int(w * pct)
        return points, [f"Performance score {val:.0f}/100"] if points else (0, [])
    except (TypeError, ValueError):
        return 0, []


def _sla_score(perf: Tuple[int, int], c: Dict[str, Any], weights: Dict[str, int]) -> Tuple[int, List[str]]:
    """SLA: from contractor_performance (jobs_on_time, jobs_completed) or contractor.sla_compliance_rate."""
    jobs, on_time = perf
    rate = c.get("sla_compliance_rate")
    if rate is not None and isinstance(rate, (int, float)):
        pct = min(1.0, max(0.0, float(rate) if rate <= 1 else rate / 100))
    elif jobs and jobs > 0:
        pct = on_time / jobs
    else:
        return 0, []
    points = int((weights.get("sla_performance", 10) or 0) * pct)
    return points, [f"{int(pct * 100)}% SLA compliance"] if points else (0, [])


def _rating_score(c: Dict[str, Any], weights: Dict[str, int]) -> Tuple[int, List[str]]:
    """Rating 1-5 -> scale to weight."""
    r = c.get("rating_average")
    if r is None:
        return 0, []
    try:
        val = float(r)
        if val <= 0:
            return 0, []
        pct = min(1.0, (val - 1) / 4)  # 1->0, 5->1
        points = int((weights.get("rating", 10) or 0) * pct)
        return points, [f"Rating {val:.1f}/5"] if points else (0, [])
    except (TypeError, ValueError):
        return 0, []


def _rework_score(c: Dict[str, Any], weights: Dict[str, int]) -> Tuple[int, List[str]]:
    """Lower rework_rate is better. 0% -> full points; >= REWORK_RATE_MAX_PENALTY -> 0."""
    r = c.get("rework_rate")
    if r is None:
        return weights.get("rework_rate", 5), []
    try:
        val = float(r) if r <= 1 else float(r) / 100
        if val >= REWORK_RATE_MAX_PENALTY:
            return 0, []
        pct = 1.0 - (val / REWORK_RATE_MAX_PENALTY)
        points = int((weights.get("rework_rate", 5) or 0) * pct)
        return points, ["Low rework rate"] if points else (0, [])
    except (TypeError, ValueError):
        return weights.get("rework_rate", 5), []


def _workload_capacity_score(open_jobs: int, weights: Dict[str, int]) -> Tuple[int, List[str]]:
    """Fewer open assigned jobs => higher score (deprioritise overload)."""
    w = weights.get("workload_capacity", 10)
    oj = max(0, int(open_jobs))
    ref = max(1, WORKLOAD_OPEN_JOBS_REFERENCE)
    frac = max(0.0, 1.0 - (oj / ref))
    points = int(w * frac)
    if oj == 0:
        reasons = ["Low current workload"]
    elif oj <= 3:
        reasons = [f"Moderate workload ({oj} open jobs)"]
    else:
        reasons = [f"Heavier workload ({oj} open jobs)"]
    return points, reasons


def _client_preference_score(c: Dict[str, Any], client_id: Optional[str], weights: Dict[str, int]) -> Tuple[int, List[str]]:
    """Bonus when contractor is explicitly linked to the client org."""
    if not client_id:
        return 0, []
    cid = (c.get("client_id") or "").strip()
    if not cid or cid != str(client_id).strip():
        return 0, []
    pts = weights.get("client_preference", 8)
    return pts, ["Preferred / linked to your organisation"]


def _historical_breach_penalty(breach_count: int) -> Tuple[int, List[str]]:
    """Subtract points for past SLA breaches (does not exclude)."""
    n = max(0, int(breach_count))
    if n <= 0:
        return 0, []
    pen = min(HISTORICAL_BREACH_PENALTY_CAP, n * HISTORICAL_BREACH_PENALTY_PER_EVENT)
    return -pen, [f"Past SLA breaches on completed jobs: {n}"]


def _price_fit(wo: Dict[str, Any], _c: Dict[str, Any], _price_books: Optional[List[Dict[str, Any]]], weights: Dict[str, int]) -> Tuple[int, List[str], Optional[str]]:
    """Price fit from price_books if available; else 0 and benchmark_fit null. When price_books exist and WO has category, return label only (no invented prices)."""
    if not _price_books:
        return 0, [], None
    category = wo.get("category") or wo.get("recommended_contractor_type")
    if not (category and str(category).strip()):
        return 0, [], None
    return 0, ["Benchmark available"], "Benchmark available"


def _is_compliance_work_order(wo: Dict[str, Any]) -> bool:
    return (wo.get("work_order_kind") or "").strip().upper() == WORK_ORDER_KIND_COMPLIANCE


def _compliance_requirement_match_score(
    wo: Dict[str, Any], c: Dict[str, Any], weights: Dict[str, int]
) -> Tuple[int, List[str]]:
    """Primary score driver for compliance execution work orders."""
    code = (wo.get("requirement_code") or "").strip().lower()
    if not code:
        return 0, []
    if not contractor_verified_qualifies_for_requirement(c, code):
        return 0, []
    w = weights.get("compliance_requirement_match", 40)
    reasons = compliance_match_reasons_verified(c, code) or [f"Verified capability for compliance requirement {code}"]
    return w, reasons


def _should_exclude_compliance(
    wo: Dict[str, Any], property_doc: Optional[Dict[str, Any]], c: Dict[str, Any]
) -> Optional[str]:
    status = (c.get("status") or "").strip().lower()
    if status == "suspended":
        return "Suspended"
    if status and status != "active":
        return "Inactive"
    caps = parse_verified_execution_capabilities(c)
    if EXECUTION_CAPABILITY_COMPLIANCE not in caps:
        return "Contractor is not enabled for compliance execution work"
    code = (wo.get("requirement_code") or "").strip().lower()
    if code and not contractor_verified_qualifies_for_requirement(c, code):
        return "Contractor does not meet this compliance requirement (verified codes)"
    trades = [_normalize(t) for t in (c.get("trade_types") or [])]
    if not trades:
        return "No trade types"
    postcode = (property_doc or {}).get("postcode") or ""
    postcode_norm = _normalize(postcode.replace(" ", ""))[:POSTCODE_PREFIX_LEN]
    if postcode_norm:
        areas = [_normalize(a) for a in (c.get("areas_served") or [])]
        region = _normalize(c.get("region") or "")
        if areas or region:
            if not any(postcode_norm in a or a in postcode_norm for a in areas) and postcode_norm not in region and (
                not region or region not in postcode_norm
            ):
                return "Region mismatch"
    return None


def _should_exclude(wo: Dict[str, Any], property_doc: Optional[Dict[str, Any]], c: Dict[str, Any]) -> Optional[str]:
    """Return exclusion reason or None if contractor is eligible."""
    if _is_compliance_work_order(wo):
        return _should_exclude_compliance(wo, property_doc, c)
    status = (c.get("status") or "").strip().lower()
    if status == "suspended":
        return "Suspended"
    if status and status != "active":
        return "Inactive"
    caps_m = parse_execution_capabilities(c)
    if caps_m == {EXECUTION_CAPABILITY_COMPLIANCE}:
        return "Contractor is compliance-only; not used for maintenance repair routing"
    if EXECUTION_CAPABILITY_MAINTENANCE not in caps_m:
        return "Contractor is not enabled for maintenance execution work"
    rec_type = _normalize(wo.get("recommended_contractor_type") or "general")
    trade_keys = list(set(TYPE_TO_TRADES.get(rec_type, ["general"]) + [_normalize(wo.get("category") or "general")]))
    trades = [_normalize(t) for t in (c.get("trade_types") or [])]
    if not trades:
        return "No trade types"
    if not any(t in trade_keys for t in trades) and "general" not in trades:
        return "Wrong trade"
    required_creds = REQUIRED_CREDENTIALS_BY_TYPE.get(rec_type, [])
    if required_creds:
        creds = [_normalize(x) for x in (c.get("credentials") or [])]
        has_cred = any(any(r in cr or cr in r for cr in creds) for r in required_creds)
        if not has_cred and rec_type in VERIFICATION_REQUIRED_TYPES and not c.get("vetted"):
            return "Missing required credential / not verified"
        if not has_cred and not c.get("vetted") and required_creds:
            return "Missing required credential"
    postcode = (property_doc or {}).get("postcode") or ""
    postcode_norm = _normalize(postcode.replace(" ", ""))[:POSTCODE_PREFIX_LEN]
    if postcode_norm:
        areas = [_normalize(a) for a in (c.get("areas_served") or [])]
        region = _normalize(c.get("region") or "")
        if areas or region:
            if not any(postcode_norm in a or a in postcode_norm for a in areas) and postcode_norm not in region and (not region or region not in postcode_norm):
                return "Region mismatch"
    return None


def recommend_contractors(
    work_order: Dict[str, Any],
    property_doc: Optional[Dict[str, Any]],
    contractors: List[Dict[str, Any]],
    performance_map: Optional[Dict[str, Tuple[int, int]]] = None,
    price_books: Optional[List[Dict[str, Any]]] = None,
    weights: Optional[Dict[str, int]] = None,
    min_strong_match: Optional[int] = None,
    *,
    workload_map: Optional[Dict[str, int]] = None,
    breach_count_map: Optional[Dict[str, int]] = None,
    client_id_for_preference: Optional[str] = None,
    routing_meta: Optional[Dict[str, Any]] = None,
    assignment_policy: Optional[Dict[str, Any]] = None,
    eligible_only: bool = False,
) -> Dict[str, Any]:
    """
    Pure recommendation: filter, score, rank. No I/O.
    performance_map: contractor_id -> (jobs_completed, jobs_on_time).
    When eligible_only=True, callers must pre-filter to assignable contractors (skips legacy _should_exclude).
    Returns routing + score_breakdown per contractor for operational transparency.
    """
    base_w = dict(weights or DEFAULT_WEIGHTS)
    meta = routing_meta or compute_assignment_routing_meta(work_order)
    w = _adjust_weights_for_urgency(base_w, str(meta.get("assignment_urgency") or "normal"))
    perf = performance_map or {}
    wl = workload_map or {}
    br = breach_count_map or {}
    min_strong = min_strong_match if min_strong_match is not None else MIN_SCORE_STRONG_MATCH
    out: List[Dict[str, Any]] = []
    seen: set = set()
    for c in contractors:
        cid = c.get("contractor_id")
        if not cid or cid in seen:
            continue
        seen.add(cid)
        if not eligible_only:
            exclude = _should_exclude(work_order, property_doc, c)
            if exclude:
                continue
        reasons: List[str] = []
        breakdown: Dict[str, int] = {}
        is_comp = _is_compliance_work_order(work_order)
        cq_score = 0
        if is_comp:
            cq_score, cq_reasons = _compliance_requirement_match_score(work_order, c, w)
            reasons.extend(cq_reasons)
            breakdown["compliance_requirement_match"] = cq_score
            t_score, t_reasons = 0, []
            breakdown["trade_match"] = 0
        else:
            breakdown["compliance_requirement_match"] = 0
            t_score, t_reasons = _trade_match(work_order, c, w)
            reasons.extend(t_reasons)
            breakdown["trade_match"] = t_score
        r_score, r_reasons = _region_match(work_order, property_doc, c, w)
        reasons.extend(r_reasons)
        breakdown["location_service_area"] = r_score
        cr_score, cr_reasons = _credential_match(work_order, c, w)
        reasons.extend(cr_reasons)
        cr_eff = cr_score if not is_comp else int(cr_score * 0.6)
        breakdown["credentials_vetting"] = cr_eff
        ps_score, ps_reasons = _performance_score(c, w)
        reasons.extend(ps_reasons)
        breakdown["performance_score"] = ps_score
        s_score, s_reasons = _sla_score(perf.get(cid, (0, 0)), c, w)
        reasons.extend(s_reasons)
        breakdown["sla_track_record"] = s_score
        rt_score, rt_reasons = _rating_score(c, w)
        reasons.extend(rt_reasons)
        breakdown["rating"] = rt_score
        rw_score, rw_reasons = _rework_score(c, w)
        reasons.extend(rw_reasons)
        breakdown["rework_rate"] = rw_score
        p_score, p_reasons, benchmark_fit = _price_fit(work_order, c, price_books, w)
        reasons.extend(p_reasons)
        breakdown["price_benchmark"] = p_score
        open_jobs = int(wl.get(cid, 0))
        j_done, j_on = perf.get(cid, (0, 0))
        wl_score, wl_reasons = _workload_capacity_score(open_jobs, w)
        reasons.extend(wl_reasons)
        breakdown["workload_capacity"] = wl_score
        cp_score, cp_reasons = _client_preference_score(c, client_id_for_preference, w)
        reasons.extend(cp_reasons)
        breakdown["client_preference"] = cp_score
        hb_pen, hb_reasons = _historical_breach_penalty(br.get(cid, 0))
        reasons.extend(hb_reasons)
        breakdown["historical_sla_breaches"] = hb_pen
        if client_id_for_preference and j_done >= 5:
            reasons.append(f"Strong completion history ({j_done} jobs with your organisation)")
        total = (
            cq_score
            + t_score
            + r_score
            + cr_eff
            + ps_score
            + s_score
            + rt_score
            + rw_score
            + p_score
            + wl_score
            + cp_score
            + hb_pen
        )
        out.append({
            "contractor_id": cid,
            "score": total,
            "score_breakdown": breakdown,
            "open_assigned_jobs": open_jobs,
            "historical_sla_breach_jobs": int(br.get(cid, 0)),
            "jobs_completed_recorded": int(j_done),
            "jobs_on_time_recorded": int(j_on),
            "reasons": reasons,
            "benchmark_fit": benchmark_fit,
            "name": c.get("name") or c.get("company_name"),
            "company_name": c.get("company_name"),
            "trade_types": c.get("trade_types"),
            "vetted": c.get("vetted"),
            "rating_average": c.get("rating_average"),
            "sla_compliance_rate": c.get("sla_compliance_rate"),
            "region": c.get("region"),
            "credentials": c.get("credentials"),
            "performance_score": c.get("performance_score"),
            "reliability_score": c.get("reliability_score"),
            "completed_jobs": c.get("completed_jobs"),
            "assigned_jobs": c.get("assigned_jobs"),
        })
    out.sort(key=lambda x: -x["score"])
    for i, item in enumerate(out, 1):
        item["rank"] = i
        if i == 1 and item["score"] >= min_strong:
            item["recommendation_label"] = "Best match"
        elif i == 1:
            item["recommendation_label"] = "Best available"
        elif i == 2 and item["score"] >= min_strong:
            item["recommendation_label"] = "Strong alternative"
        else:
            item["recommendation_label"] = "Available"
    top_score = out[0]["score"] if out else 0
    no_strong_match = not out or top_score < min_strong
    policy = assignment_policy or {}
    routing_block = {
        **meta,
        "no_eligible_contractors": len(out) == 0,
        "no_strong_match": no_strong_match,
        "policy": {
            "admin_confirms_assignment": policy.get("admin_confirms_assignment_default", True),
            "auto_assign_enabled": bool(policy.get("auto_assign_enabled")),
            "auto_assign_categories": policy.get("auto_assign_categories") or [],
        },
        "weights_effective": w,
    }
    if routing_block["no_eligible_contractors"]:
        routing_block["routing_messages"] = list(meta.get("routing_messages") or []) + [
            "No eligible contractors match this job (trade, area, portal activation, and vetting)."
        ]
    elif no_strong_match and out:
        routing_block["routing_messages"] = list(meta.get("routing_messages") or []) + [
            "No contractor reached the strong-match threshold — review top candidates carefully before assigning."
        ]
    return {
        "contractors": out,
        "total": len(out),
        "no_strong_match": no_strong_match,
        "work_order_id": work_order.get("work_order_id"),
        "routing": routing_block,
    }
