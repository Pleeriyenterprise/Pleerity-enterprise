"""Recommendation template catalogue — deterministic gap → recommendation_type mapping."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

RECOMMENDATION_TEMPLATES_V1: Dict[str, Dict[str, Any]] = {
    "upload_missing_document": {
        "recommendation_type": "upload_missing_document",
        "title": "Upload missing evidence",
        "action_summary": "Upload the missing compliance document referenced in the assessment decision",
        "reason_code": "missing_evidence",
        "regulatory_severity": "statutory",
    },
    "renew_expired_certificate": {
        "recommendation_type": "renew_eicr",
        "title": "Renew expired certificate",
        "action_summary": "Renew the expired compliance certificate before the statutory deadline",
        "reason_code": "evidence_expired",
        "regulatory_severity": "statutory",
    },
    "review_rejected_evidence": {
        "recommendation_type": "review_evidence",
        "title": "Review rejected evidence",
        "action_summary": "Review and resubmit evidence that was rejected during assessment",
        "reason_code": "evidence_rejected",
        "regulatory_severity": "contractual",
    },
    "resolve_evidence_conflict": {
        "recommendation_type": "resolve_evidence_conflict",
        "title": "Resolve conflicting evidence",
        "action_summary": "Resolve conflicting evidence records cited in the compliance decision",
        "reason_code": "evidence_conflict",
        "regulatory_severity": "contractual",
    },
    "address_high_risk_requirement": {
        "recommendation_type": "address_high_risk_requirement",
        "title": "Address high-risk requirement",
        "action_summary": "Remediate the high-risk compliance requirement identified in assessment",
        "reason_code": "high_risk_requirement",
        "regulatory_severity": "statutory",
    },
    "review_stale_evidence": {
        "recommendation_type": "review_evidence",
        "title": "Review stale evidence",
        "action_summary": "Review superseded or stale evidence and upload current documentation",
        "reason_code": "stale_evidence",
        "regulatory_severity": "advisory",
    },
}


def match_gap_to_template(gap_item: Any) -> Optional[Dict[str, Any]]:
    """Map graph gap item to recommendation template."""
    if isinstance(gap_item, str):
        key = gap_item.strip().lower()
        if "missing" in key or "upload" in key:
            return RECOMMENDATION_TEMPLATES_V1["upload_missing_document"]
        if "expir" in key:
            return RECOMMENDATION_TEMPLATES_V1["renew_expired_certificate"]
        if "reject" in key:
            return RECOMMENDATION_TEMPLATES_V1["review_rejected_evidence"]
        if "conflict" in key:
            return RECOMMENDATION_TEMPLATES_V1["resolve_evidence_conflict"]
        if "risk" in key:
            return RECOMMENDATION_TEMPLATES_V1["address_high_risk_requirement"]
        if "stale" in key or "supersed" in key:
            return RECOMMENDATION_TEMPLATES_V1["review_stale_evidence"]
        return RECOMMENDATION_TEMPLATES_V1["upload_missing_document"]
    if isinstance(gap_item, dict):
        code = str(gap_item.get("code") or gap_item.get("type") or gap_item.get("reason") or "").lower()
        if "expir" in code:
            return RECOMMENDATION_TEMPLATES_V1["renew_expired_certificate"]
        if "reject" in code:
            return RECOMMENDATION_TEMPLATES_V1["review_rejected_evidence"]
        if "conflict" in code:
            return RECOMMENDATION_TEMPLATES_V1["resolve_evidence_conflict"]
        if "risk" in code:
            return RECOMMENDATION_TEMPLATES_V1["address_high_risk_requirement"]
        if "stale" in code or "supersed" in code:
            return RECOMMENDATION_TEMPLATES_V1["review_stale_evidence"]
        return RECOMMENDATION_TEMPLATES_V1["upload_missing_document"]
    return None


def normalize_gaps(graph_envelope: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract gap candidates from find_missing_evidence envelope."""
    if graph_envelope.get("insufficient_evidence"):
        return []
    gaps = (graph_envelope.get("payload") or {}).get("gaps") or []
    out: List[Dict[str, Any]] = []
    for g in gaps:
        decision_id = g.get("decision_id")
        for item in g.get("missing") or []:
            tmpl = match_gap_to_template(item)
            if tmpl:
                out.append({"decision_id": decision_id, "gap_item": item, "template": tmpl})
    return out
