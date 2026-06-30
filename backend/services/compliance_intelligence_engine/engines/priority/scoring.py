"""CIE-2 priority scoring formula — versioned, registry-backed."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from services.compliance_intelligence_engine.registry.loader import get_weight_set_v1
from services.compliance_intelligence_engine.registry.versions import SCORING_MODEL_V1

# Factor catalogue → registry weight key mapping (documented in CIE_2_IMPLEMENTATION.md)
FACTOR_WEIGHT_KEYS: Dict[str, str] = {
    "regulatory_exposure": "risk_weight",
    "expiry_proximity": "urgency_weight",
    "compliance_impact": "risk_weight",
    "missing_evidence_criticality": "urgency_weight",
    "dependency_criticality": "dependency_weight",
    "portfolio_relevance": "portfolio_weight",
    "evidence_confidence": "audit_weight",
    "operational_impact": "operational_capacity_weight",
}

PRIORITY_BAND_THRESHOLDS = {
    "critical": 80.0,
    "high": 60.0,
    "medium": 40.0,
}


def score_to_band(score: float) -> str:
    if score >= PRIORITY_BAND_THRESHOLDS["critical"]:
        return "critical"
    if score >= PRIORITY_BAND_THRESHOLDS["high"]:
        return "high"
    if score >= PRIORITY_BAND_THRESHOLDS["medium"]:
        return "medium"
    return "low"


def regulatory_exposure_raw(severity: str) -> float:
    return {"statutory": 95.0, "contractual": 70.0, "advisory": 40.0}.get(severity, 50.0)


def expiry_proximity_raw(days_until_expiry: Optional[int]) -> float:
    if days_until_expiry is None:
        return 30.0
    if days_until_expiry <= 0:
        return 100.0
    if days_until_expiry <= 30:
        return 90.0
    if days_until_expiry <= 90:
        return 70.0
    return 40.0


def compute_priority_score(
    *,
    factors: List[Dict[str, Any]],
    weight_set: Optional[Dict[str, Any]] = None,
) -> Tuple[float, List[Dict[str, Any]], str]:
    """
    priority_score = Σ (registry_weight[factor] × raw_score[factor])
    Normalised to 0–100 by dividing by sum of applied registry weights used.
    """
    weights_doc = weight_set or get_weight_set_v1()
    registry_weights = weights_doc.get("weights") or {}
    weighted_factors: List[Dict[str, Any]] = []
    total = 0.0
    weight_sum = 0.0
    for f in factors:
        fid = f["factor_id"]
        wkey = FACTOR_WEIGHT_KEYS.get(fid, "risk_weight")
        w = float(registry_weights.get(wkey, 0.0))
        raw = float(f.get("raw_score", 0.0))
        ws = round(w * raw, 4)
        weighted_factors.append(
            {
                **f,
                "weight": w,
                "weighted_score": ws,
                "registry_weight_key": wkey,
            }
        )
        total += ws
        weight_sum += w
    score = round(min(100.0, (total / weight_sum) if weight_sum > 0 else 0.0), 2)
    return score, weighted_factors, score_to_band(score)


def scoring_model_version() -> str:
    return SCORING_MODEL_V1
