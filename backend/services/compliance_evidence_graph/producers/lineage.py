"""Rule lineage snapshot builder — authoritative refs only (Phase 2C)."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional


def build_rule_lineage_from_refs(refs: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Build ``rule_lineage`` for decision snapshots from authoritative source data.
    Never infers legislation not present in refs.
    """
    r = refs or {}
    compliance_rule_id = (
        r.get("compliance_rule_id")
        or r.get("requirement_code")
        or r.get("requirement_type")
    )
    governed_rule_version_id = r.get("governed_rule_version_id") or r.get("rules_version")
    jurisdiction = r.get("jurisdiction") or r.get("portfolio_jurisdiction_label")
    policy_registry_version = r.get("policy_registry_version") or r.get("registry_publish_version")

    lineage_node_ids: List[str] = []
    for key in ("lineage_node_ids", "legislation_node_ids"):
        raw = r.get(key)
        if isinstance(raw, list):
            lineage_node_ids.extend(str(x) for x in raw if x)

    legislation = r.get("applicable_legislation") or r.get("legislation_refs") or []
    if isinstance(legislation, list) and legislation and not lineage_node_ids:
        for leg in legislation[:20]:
            if isinstance(leg, dict) and leg.get("node_id"):
                lineage_node_ids.append(str(leg["node_id"]))
            elif isinstance(leg, str) and leg.strip():
                lineage_node_ids.append(leg.strip())

    has_rule_ref = bool(compliance_rule_id)
    has_version_or_optional = bool(governed_rule_version_id) or not r.get("require_governed_version")
    lineage_complete = has_rule_ref and has_version_or_optional and (
        bool(lineage_node_ids) or bool(legislation) or r.get("lineage_optional") is True
    )

    payload = {
        "compliance_rule_id": compliance_rule_id,
        "governed_rule_version_id": governed_rule_version_id,
        "lineage_node_ids": sorted(set(lineage_node_ids)),
        "lineage_complete": lineage_complete,
        "lineage_incomplete": not lineage_complete,
        "jurisdiction": jurisdiction,
        "policy_registry_version": policy_registry_version,
    }
    if r.get("lineage_incomplete_reason"):
        payload["lineage_incomplete_reason"] = r["lineage_incomplete_reason"]

    canonical = json.dumps(
        {
            "compliance_rule_id": compliance_rule_id,
            "governed_rule_version_id": governed_rule_version_id,
            "lineage_node_ids": payload["lineage_node_ids"],
            "jurisdiction": jurisdiction,
        },
        sort_keys=True,
        default=str,
    )
    payload["lineage_hash"] = f"sha256:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()[:16]}"
    return payload


def lineage_refs_from_requirement(requirement: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Extract lineage refs from a requirement document."""
    if not requirement:
        return {"lineage_optional": True, "lineage_incomplete_reason": "requirement_missing"}
    meta = requirement.get("registry_metadata") if isinstance(requirement.get("registry_metadata"), dict) else {}
    return {
        "compliance_rule_id": requirement.get("requirement_code") or requirement.get("requirement_type"),
        "requirement_code": requirement.get("requirement_code"),
        "requirement_type": requirement.get("requirement_type"),
        "jurisdiction": requirement.get("jurisdiction"),
        "governed_rule_version_id": requirement.get("policy_classification_version"),
        "policy_registry_version": meta.get("registry_publish_state"),
        "catalog_keys": meta.get("catalog_keys"),
        "lineage_optional": True,
    }
