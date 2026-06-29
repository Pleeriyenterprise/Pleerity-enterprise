"""Registry v1 seed documents — immutable catalogue entries."""
from __future__ import annotations

from typing import Any, Dict, List

from services.compliance_intelligence_engine.hashing import sha256_digest
from services.compliance_intelligence_engine.registry.versions import (
    CONSTRAINT_SET_V1,
    DEPENDENCY_STRATEGY_V1,
    IMPACT_STRATEGY_V1,
    PRIORITY_STRATEGY_V1,
    REC_STRATEGY_V1,
    WEIGHT_SET_V1,
)


def _with_content_hash(doc: Dict[str, Any], *, hash_keys: List[str]) -> Dict[str, Any]:
    body = {k: doc[k] for k in hash_keys}
    out = dict(doc)
    out["content_hash"] = sha256_digest(body)
    return out


def strategy_seed_v1() -> List[Dict[str, Any]]:
    seeds = [
      {
          "strategy_id": REC_STRATEGY_V1,
          "strategy_family": "recommendation",
          "semantic_version": "1.0.0",
          "status": "active",
          "description": "Template-matched gap recommendations v1 (CIE-1.5 seed)",
          "constraint_set_binding": CONSTRAINT_SET_V1,
          "weight_set_binding": WEIGHT_SET_V1,
      },
      {
          "strategy_id": PRIORITY_STRATEGY_V1,
          "strategy_family": "priority",
          "semantic_version": "1.0.0",
          "status": "active",
          "description": "Weighted priority ordering v1 (CIE-1.5 seed)",
          "constraint_set_binding": CONSTRAINT_SET_V1,
          "weight_set_binding": WEIGHT_SET_V1,
      },
      {
          "strategy_id": DEPENDENCY_STRATEGY_V1,
          "strategy_family": "dependency",
          "semantic_version": "1.0.0",
          "status": "active",
          "description": "Dependency chain resolution v1 (CIE-1.5 seed)",
          "constraint_set_binding": CONSTRAINT_SET_V1,
          "weight_set_binding": None,
      },
      {
          "strategy_id": IMPACT_STRATEGY_V1,
          "strategy_family": "impact",
          "semantic_version": "1.0.0",
          "status": "active",
          "description": "Decision impact projection v1 (CIE-1.5 seed)",
          "constraint_set_binding": CONSTRAINT_SET_V1,
          "weight_set_binding": None,
      },
    ]
    return [
      _with_content_hash(
          s,
          hash_keys=[
              "strategy_id",
              "strategy_family",
              "semantic_version",
              "status",
              "description",
              "constraint_set_binding",
              "weight_set_binding",
          ],
      )
      for s in seeds
    ]


def weight_seed_v1() -> Dict[str, Any]:
    doc = {
        "weight_set_id": WEIGHT_SET_V1,
        "semantic_version": "1.0.0",
        "status": "active",
        "description": "Default operational weighting v1 (CIE-1.5 seed)",
        "scope": {"global": True, "client_id": None, "jurisdiction_id": None},
        "weights": {
            "risk_weight": 0.35,
            "urgency_weight": 0.25,
            "portfolio_weight": 0.10,
            "dependency_weight": 0.10,
            "cost_weight": 0.05,
            "insurance_weight": 0.05,
            "audit_weight": 0.05,
            "tenant_impact_weight": 0.03,
            "operational_capacity_weight": 0.01,
            "commercial_impact_weight": 0.01,
        },
        "normalization_rule": "sum_to_1.0",
    }
    return _with_content_hash(
        doc,
        hash_keys=["weight_set_id", "semantic_version", "status", "weights", "normalization_rule"],
    )


def constraint_seed_v1() -> Dict[str, Any]:
    doc = {
        "constraint_set_id": CONSTRAINT_SET_V1,
        "semantic_version": "1.0.0",
        "status": "active",
        "description": "CIE v1 deterministic constraint catalogue (CIE-1.5 seed)",
        "constraints": [
            {
                "constraint_id": "evidence_completeness_min",
                "constraint_type": "evidence",
                "severity": "blocking",
                "failure_code": "INSUFFICIENT_EVIDENCE",
            },
            {
                "constraint_id": "recommendation_eligibility",
                "constraint_type": "eligibility",
                "severity": "blocking",
                "failure_code": "NOT_ELIGIBLE",
            },
        ],
    }
    return _with_content_hash(
        doc,
        hash_keys=["constraint_set_id", "semantic_version", "status", "constraints"],
    )


def all_registry_seeds_v1() -> Dict[str, Any]:
    return {
        "strategies": strategy_seed_v1(),
        "weights": weight_seed_v1(),
        "constraints": constraint_seed_v1(),
    }
