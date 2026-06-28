"""Shared P0 decision emit helper."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Optional, Tuple

from services.compliance_evidence_graph.bridge_operational import (
    merge_bridge_into_snapshot,
    resolve_operational_bridge,
)
from services.compliance_evidence_graph.emit_service import emit_compliance_decision
from services.compliance_evidence_graph.producers._base import build_dedupe_key, compute_decision_quality


async def emit_p0_decision(
    *,
    decision_type: str,
    decision_outcome: str,
    summary: str,
    source_collection: str,
    source_id: str,
    dedupe_key: str,
    client_id: str,
    decision_authority: Dict[str, Any],
    snapshot_payload: Dict[str, Any],
    quality_inputs: Dict[str, Any],
    property_id: Optional[str] = None,
    requirement_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
    mutation_timestamp: Optional[str] = None,
    previous_decision_id: Optional[str] = None,
    document_ids: Optional[list] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Optional[Tuple[str, str]]:
    """
    Emit decision + snapshot with decision_quality and operational bridge.
    Returns (decision_id, snapshot_id) or None.
    """
    decision_quality = compute_decision_quality(**quality_inputs)
    bridge = resolve_operational_bridge(
        correlation_id=correlation_id,
        client_id=client_id,
        property_id=property_id,
        requirement_id=requirement_id,
    )
    snap = merge_bridge_into_snapshot(snapshot_payload, bridge)
    snap["decision_quality"] = decision_quality

    decision_id = await emit_compliance_decision(
        decision_type=decision_type,
        decision_outcome=decision_outcome,
        summary=summary,
        source_collection=source_collection,
        source_id=str(source_id),
        dedupe_key=dedupe_key,
        client_id=client_id,
        property_id=property_id,
        requirement_id=requirement_id,
        decision_timestamp=mutation_timestamp,
        previous_decision_id=previous_decision_id,
        decision_authority=decision_authority,
        snapshot_payload=snap,
        operational_correlation_id=bridge.get("operational_correlation_id"),
        document_ids=document_ids,
        metadata={**(metadata or {}), "producer": "p0"},
        decision_quality=decision_quality,
    )
    if not decision_id:
        return None

    from services.compliance_evidence_graph.storage import decisions as decision_storage

    dec = await decision_storage.get_decision(decision_id)
    snapshot_id = (dec or {}).get("snapshot_id") or ""
    return decision_id, snapshot_id


def fact_hash(payload: Dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
