"""Graph health metric definitions and status tiers."""
from __future__ import annotations

from typing import Any, Dict, List

SERVICE_VERSION = "1.0.0"


def compute_overall_status(
    *,
    integrity_failure_count: int,
    warning_count: int,
    warning_threshold: int = 50,
) -> str:
    if integrity_failure_count > 0:
        return "unhealthy"
    if warning_count > warning_threshold:
        return "degraded"
    return "healthy"


def build_metrics_from_validation(stats: Dict[str, Any], validation_dict: Dict[str, Any]) -> Dict[str, Any]:
    decisions = stats.get("decisions_examined", 0) or 0
    failures = validation_dict.get("failures") or []
    warnings = validation_dict.get("warnings") or []

    dup_failures = [f for f in failures if "duplicate" in f.get("message", "").lower()]
    orphan_failures = [f for f in failures if "orphan" in f.get("message", "").lower()]
    tenant_failures = [f for f in failures if f.get("check") == "validate_tenant_isolation"]
    missing_dq = [w for w in warnings if "decision_quality" in w.get("message", "").lower()]
    missing_oe = [w for w in warnings if w.get("check") == "validate_operational_links"]

    return {
        "decision_completeness_rate": 1.0 if decisions == 0 else max(0.0, 1.0 - len(failures) / max(decisions, 1)),
        "snapshot_pairing_rate": 1.0,
        "orphan_node_count": len([f for f in orphan_failures if "node" in f.get("message", "")]),
        "orphan_edge_count": len(orphan_failures),
        "duplicate_dedupe_key_count": len(dup_failures),
        "broken_supersession_count": len(
            [f for f in failures if f.get("check") == "validate_supersession"]
        ),
        "missing_operational_link_count": len(missing_oe),
        "cross_tenant_violation_count": len(tenant_failures),
        "decision_quality_present_rate": (
            1.0
            if decisions == 0
            else max(0.0, 1.0 - len(missing_dq) / max(decisions, 1))
        ),
        "integrity_failure_count": len(failures),
        "warning_count": len(warnings),
    }


def sample_ids(items: List[Dict[str, Any]], *, field: str = "decision_id", limit: int = 5) -> List[str]:
    out: List[str] = []
    for item in items:
        val = item.get(field) or item.get("entity_id")
        if val and val not in out:
            out.append(str(val))
        if len(out) >= limit:
            break
    return out
