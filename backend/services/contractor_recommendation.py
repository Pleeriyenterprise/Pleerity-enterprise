"""
Rule-based Contractor Recommendation Engine (pure logic, no I/O).
Scores and ranks contractors for a work order. Explainable, configurable weights.
"""
from typing import Any, Dict, List, Optional, Tuple

from services.contractor_recommendation_config import (
    DEFAULT_WEIGHTS,
    MIN_SCORE_STRONG_MATCH,
    REQUIRED_CREDENTIALS_BY_TYPE,
    VERIFICATION_REQUIRED_TYPES,
    POSTCODE_PREFIX_LEN,
    REWORK_RATE_MAX_PENALTY,
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


def _trade_match(wo: Dict[str, Any], c: Dict[str, Any], weights: Dict[str, int]) -> Tuple[int, List[str]]:
    """Trade match: 0 or full weight. Reasons if match."""
    rec_type = _normalize(wo.get("recommended_contractor_type") or "general")
    category = _normalize(wo.get("category") or "general")
    trade_keys = list(set(TYPE_TO_TRADES.get(rec_type, ["general"]) + [category]))
    trades = [_normalize(t) for t in (c.get("trade_types") or [])]
    match = any(t in trade_keys for t in trades) or "general" in trades
    if not match:
        return 0, []
    return weights.get("trade_match", 30), [f"Matches trade: {category or rec_type}"]


def _region_match(wo: Dict[str, Any], property_doc: Optional[Dict[str, Any]], c: Dict[str, Any], weights: Dict[str, int]) -> Tuple[int, List[str]]:
    """Region match: property postcode prefix or region in contractor areas_served/region."""
    postcode = ""
    if property_doc:
        postcode = _normalize((property_doc.get("postcode") or "").replace(" ", ""))[:POSTCODE_PREFIX_LEN]
    region_wo = _normalize(property_doc.get("region") or "") if property_doc else ""
    areas = [_normalize(a) for a in (c.get("areas_served") or [])]
    contractor_region = _normalize(c.get("region") or "")
    if not postcode and not region_wo and not areas and not contractor_region:
        return weights.get("region_match", 20), ["No region filter"]
    if postcode:
        if any(postcode in a or a in postcode for a in areas) or (contractor_region and postcode in contractor_region):
            return weights.get("region_match", 20), [f"Covers postcode area {postcode}"]
        if contractor_region and contractor_region in postcode:
            return weights.get("region_match", 20), [f"Region: {contractor_region}"]
    if region_wo and (region_wo in areas or region_wo == contractor_region):
        return weights.get("region_match", 20), [f"Covers {region_wo}"]
    if not areas and not contractor_region:
        return weights.get("region_match", 20) // 2, ["No area restriction"]
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


def _price_fit(wo: Dict[str, Any], _c: Dict[str, Any], _price_books: Optional[List[Dict[str, Any]]], weights: Dict[str, int]) -> Tuple[int, List[str], Optional[str]]:
    """Price fit from price_books if available; else 0 and benchmark_fit null. When price_books exist and WO has category, return label only (no invented prices)."""
    if not _price_books:
        return 0, [], None
    category = wo.get("category") or wo.get("recommended_contractor_type")
    if not (category and str(category).strip()):
        return 0, [], None
    return 0, ["Benchmark available"], "Benchmark available"


def _should_exclude(wo: Dict[str, Any], property_doc: Optional[Dict[str, Any]], c: Dict[str, Any]) -> Optional[str]:
    """Return exclusion reason or None if contractor is eligible."""
    status = (c.get("status") or "").strip().lower()
    if status == "suspended":
        return "Suspended"
    if status and status != "active":
        return "Inactive"
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
) -> Dict[str, Any]:
    """
    Pure recommendation: filter, score, rank. No I/O.
    performance_map: contractor_id -> (jobs_completed, jobs_on_time).
    Returns: { contractors: [...], total, no_strong_match, work_order_id }.
    Each item: contractorId, score, rank, recommendationLabel, reasons, benchmarkFit, plus contractor display fields.
    """
    w = weights or DEFAULT_WEIGHTS
    perf = performance_map or {}
    min_strong = min_strong_match if min_strong_match is not None else MIN_SCORE_STRONG_MATCH
    out: List[Dict[str, Any]] = []
    for c in contractors:
        cid = c.get("contractor_id")
        if not cid:
            continue
        exclude = _should_exclude(work_order, property_doc, c)
        if exclude:
            continue
        reasons: List[str] = []
        t_score, t_reasons = _trade_match(work_order, c, w)
        reasons.extend(t_reasons)
        r_score, r_reasons = _region_match(work_order, property_doc, c, w)
        reasons.extend(r_reasons)
        cr_score, cr_reasons = _credential_match(work_order, c, w)
        reasons.extend(cr_reasons)
        s_score, s_reasons = _sla_score(perf.get(cid, (0, 0)), c, w)
        reasons.extend(s_reasons)
        rt_score, rt_reasons = _rating_score(c, w)
        reasons.extend(rt_reasons)
        rw_score, rw_reasons = _rework_score(c, w)
        reasons.extend(rw_reasons)
        p_score, p_reasons, benchmark_fit = _price_fit(work_order, c, price_books, w)
        reasons.extend(p_reasons)
        total = t_score + r_score + cr_score + s_score + rt_score + rw_score + p_score
        out.append({
            "contractor_id": cid,
            "score": total,
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
        })
    out.sort(key=lambda x: -x["score"])
    for i, item in enumerate(out, 1):
        item["rank"] = i
        if i == 1 and item["score"] >= min_strong:
            item["recommendation_label"] = "Best Match"
        elif i == 1:
            item["recommendation_label"] = "Best available"
        elif i == 2 and item["score"] >= min_strong:
            item["recommendation_label"] = "Good match"
        else:
            item["recommendation_label"] = "Available"
    top_score = out[0]["score"] if out else 0
    no_strong_match = not out or top_score < min_strong
    return {
        "contractors": out,
        "total": len(out),
        "no_strong_match": no_strong_match,
        "work_order_id": work_order.get("work_order_id"),
    }
