"""
Policy-backed aggregate counters for persisted open compliance gaps.

Read-only diagnostics path: tenant scoped and bounded output.
"""
from __future__ import annotations

from typing import Any, Dict, Optional


_MAX_REASON_CODES = 20


async def aggregate_policy_gap_counts_for_client(
    db: Any,
    client_id: str,
    property_id: Optional[str] = None,
) -> Dict[str, Any]:
    match: Dict[str, Any] = {"client_id": client_id, "status": "open"}
    if property_id:
        match["property_id"] = property_id

    policy_pipeline = [
        {"$match": match},
        {
            "$group": {
                "_id": None,
                "critical_mandatory_breach_count": {
                    "$sum": {"$cond": [{"$eq": ["$critical_mandatory_breach", True]}, 1, 0]}
                },
                "high_risk_gap_count": {"$sum": {"$cond": [{"$eq": ["$high_risk_gap", True]}, 1, 0]}},
                "attention_only_gap_count": {
                    "$sum": {"$cond": [{"$eq": ["$attention_only_gap", True]}, 1, 0]}
                },
                "unknown_or_stale_signal_count": {
                    "$sum": {"$cond": [{"$eq": ["$unknown_or_stale_signal", True]}, 1, 0]}
                },
                "policy_fields_present_count": {
                    "$sum": {
                        "$cond": [
                            {
                                "$and": [
                                    {"$ne": ["$requirement_code_normalized", None]},
                                    {"$ne": ["$applicability_state", None]},
                                    {"$ne": ["$is_mandatory", None]},
                                    {"$ne": ["$policy_criticality", None]},
                                    {"$ne": ["$evidence_state_normalized", None]},
                                ]
                            },
                            1,
                            0,
                        ]
                    }
                },
                "total_open": {"$sum": 1},
            }
        },
    ]

    reason_pipeline = [
        {"$match": match},
        {"$unwind": {"path": "$policy_reason_codes", "preserveNullAndEmptyArrays": False}},
        {"$group": {"_id": "$policy_reason_codes", "c": {"$sum": 1}}},
        {"$sort": {"c": -1, "_id": 1}},
        {"$limit": _MAX_REASON_CODES},
    ]

    version_pipeline = [
        {"$match": match},
        {"$group": {"_id": "$policy_classification_version", "c": {"$sum": 1}}},
        {"$sort": {"c": -1, "_id": 1}},
        {"$limit": 10},
    ]

    try:
        policy_rows = await db.compliance_gaps.aggregate(policy_pipeline).to_list(2)
        reason_rows = await db.compliance_gaps.aggregate(reason_pipeline).to_list(_MAX_REASON_CODES)
        version_rows = await db.compliance_gaps.aggregate(version_pipeline).to_list(10)
    except Exception:
        return {
            "critical_mandatory_breach_count": 0,
            "high_risk_gap_count": 0,
            "attention_only_gap_count": 0,
            "unknown_or_stale_signal_count": 0,
            "policy_fields_present_count": 0,
            "policy_coverage_percent": 0.0,
            "top_reason_codes": {},
            "policy_versions": {},
            "total_open": 0,
        }

    p = policy_rows[0] if policy_rows else {}
    total_open = int(p.get("total_open") or 0)
    policy_fields_present_count = int(p.get("policy_fields_present_count") or 0)
    coverage = round((policy_fields_present_count / total_open) * 100, 1) if total_open > 0 else 0.0
    top_reason_codes = {str(r.get("_id") or "UNKNOWN"): int(r.get("c") or 0) for r in reason_rows}
    policy_versions = {str(r.get("_id") or "UNKNOWN"): int(r.get("c") or 0) for r in version_rows}

    return {
        "critical_mandatory_breach_count": int(p.get("critical_mandatory_breach_count") or 0),
        "high_risk_gap_count": int(p.get("high_risk_gap_count") or 0),
        "attention_only_gap_count": int(p.get("attention_only_gap_count") or 0),
        "unknown_or_stale_signal_count": int(p.get("unknown_or_stale_signal_count") or 0),
        "policy_fields_present_count": policy_fields_present_count,
        "policy_coverage_percent": coverage,
        "top_reason_codes": top_reason_codes,
        "policy_versions": policy_versions,
        "total_open": total_open,
    }
