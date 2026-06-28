"""
Compliance Evidence Graph — atomic decision + snapshot + graph emit.

Indexes authoritative compliance decisions. Does not create or override compliance authority.
Emit failures are logged and never block business logic.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from services.compliance_evidence_graph.config import graph_emit_allowed
from services.compliance_evidence_graph.constants import (
    ALL_DECISION_TYPES,
    ALL_EDGE_TYPES,
    COLLECTION_DECISIONS,
    EDGE_BASED_ON_EVIDENCE,
    EDGE_SNAPSHOT_OF,
    NODE_COMPLIANCE_DECISION,
    NODE_DECISION_SNAPSHOT,
)
from services.compliance_evidence_graph.storage import decisions as decision_storage
from services.compliance_evidence_graph.storage import edges as edge_storage
from services.compliance_evidence_graph.storage import nodes as node_storage
from services.compliance_evidence_graph.storage import snapshots as snapshot_storage

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve_build_sha() -> str:
    for key in ("GIT_COMMIT_SHA", "BUILD_SHA", "RENDER_GIT_COMMIT", "SOURCE_VERSION", "COMMIT_SHA"):
        val = (os.getenv(key) or "").strip()
        if val and val.lower() != "unknown":
            return val
    return "unknown"


def _resolve_environment() -> str:
    return (os.getenv("ENVIRONMENT") or os.getenv("DEPLOYMENT_TIER") or "development").strip().lower()


def _canonical_hash(payload: Dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _validate_provenance(provenance: Dict[str, Any]) -> None:
    required = (
        "why_exists",
        "created_by_component",
        "created_by_authority",
        "created_at",
        "is_active",
    )
    for field in required:
        if field not in provenance or provenance[field] is None:
            raise ValueError(f"edge provenance.{field} required")


def _validate_edge(*, edge_type: str, provenance: Dict[str, Any]) -> None:
    if edge_type not in ALL_EDGE_TYPES:
        raise ValueError(f"invalid edge_type: {edge_type}")
    _validate_provenance(provenance)


async def emit_compliance_decision(
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
    property_id: Optional[str] = None,
    requirement_id: Optional[str] = None,
    decision_timestamp: Optional[str] = None,
    previous_decision_id: Optional[str] = None,
    decision_confidence: Optional[Dict[str, Any]] = None,
    rules_version: Optional[Dict[str, Any]] = None,
    jurisdiction_version: Optional[Dict[str, Any]] = None,
    legislation_version: Optional[Dict[str, Any]] = None,
    evidence_node_ids: Optional[List[str]] = None,
    document_ids: Optional[List[str]] = None,
    cer_ids: Optional[List[str]] = None,
    operational_correlation_id: Optional[str] = None,
    scope: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    evidence_edges: Optional[List[Dict[str, Any]]] = None,
) -> Optional[str]:
    """
    Atomically emit compliance decision + snapshot + graph nodes/edges.
    Returns decision_id or None on failure / idempotent duplicate / emit disallowed.
    """
    if not graph_emit_allowed():
        logger.debug("compliance_evidence_graph emit skipped: mode=%s", os.getenv("COMPLIANCE_EVIDENCE_GRAPH_MODE"))
        return None

    if decision_type not in ALL_DECISION_TYPES:
        logger.warning("compliance_evidence_graph emit rejected: invalid decision_type %s", decision_type)
        return None
    if not source_collection or not source_id:
        logger.warning("compliance_evidence_graph emit rejected: source pointer required")
        return None
    if not dedupe_key:
        logger.warning("compliance_evidence_graph emit rejected: dedupe_key required")
        return None
    if not client_id:
        logger.warning("compliance_evidence_graph emit rejected: client_id required")
        return None

    existing = await decision_storage.get_decision_by_dedupe(dedupe_key)
    if existing:
        return existing.get("decision_id")

    now = _now_iso()
    ts = decision_timestamp or now
    decision_id = f"dec_{uuid.uuid4().hex}"
    snapshot_id = f"snap_{uuid.uuid4().hex}"
    decision_node_id = f"ceg_{uuid.uuid4().hex}"
    snapshot_node_id = f"ceg_{uuid.uuid4().hex}"

    snap_body = dict(snapshot_payload)
    snap_body.setdefault("snapshot_id", snapshot_id)
    snap_body.setdefault("decision_id", decision_id)
    snap_body.setdefault("snapshot_timestamp", ts)
    snap_body.setdefault("recorded_at", now)
    snap_body.setdefault("client_id", client_id)
    if property_id:
        snap_body.setdefault("property_id", property_id)
    if requirement_id:
        snap_body.setdefault("requirement_id", requirement_id)
    snap_body["snapshot_hash"] = _canonical_hash(snap_body)

    decision_doc: Dict[str, Any] = {
        "decision_id": decision_id,
        "decision_type": decision_type,
        "decision_version": 1,
        "decision_timestamp": ts,
        "recorded_at": now,
        "decision_outcome": decision_outcome,
        "previous_decision_id": previous_decision_id,
        "superseding_decision_id": None,
        "decision_authority": decision_authority,
        "decision_confidence": decision_confidence
        or {"score": 100, "label": "runtime_confirmed", "reason": "Indexed from authoritative source"},
        "rules_version": rules_version or {},
        "jurisdiction_version": jurisdiction_version or {},
        "legislation_version": legislation_version or {},
        "evidence_set": {
            "snapshot_id": snapshot_id,
            "evidence_node_ids": evidence_node_ids or [],
            "document_ids": document_ids or [],
            "cer_ids": cer_ids or [],
        },
        "operational_correlation_id": operational_correlation_id,
        "client_id": client_id,
        "property_id": property_id,
        "requirement_id": requirement_id,
        "scope": scope or {},
        "summary": summary.strip(),
        "reasoning_inputs_hash": snap_body["snapshot_hash"],
        "snapshot_id": snapshot_id,
        "graph_node_id": decision_node_id,
        "dedupe_key": dedupe_key,
        "source": {"collection": source_collection, "id": str(source_id)},
        "environment": _resolve_environment(),
        "build_sha": _resolve_build_sha(),
        "metadata": metadata or {},
    }

    decision_node = {
        "node_id": decision_node_id,
        "node_type": NODE_COMPLIANCE_DECISION,
        "decision_id": decision_id,
        "snapshot_id": snapshot_id,
        "dedupe_key": f"node:decision:{decision_id}",
        "occurred_at": ts,
        "recorded_at": now,
        "client_id": client_id,
        "property_id": property_id,
        "requirement_id": requirement_id,
        "correlation_id": operational_correlation_id,
        "environment": decision_doc["environment"],
        "build_sha": decision_doc["build_sha"],
        "source": decision_doc["source"],
        "summary": summary.strip(),
        "status": "success",
        "severity": "info",
    }

    snapshot_node = {
        "node_id": snapshot_node_id,
        "node_type": NODE_DECISION_SNAPSHOT,
        "decision_id": decision_id,
        "snapshot_id": snapshot_id,
        "dedupe_key": f"node:snapshot:{snapshot_id}",
        "occurred_at": ts,
        "recorded_at": now,
        "client_id": client_id,
        "property_id": property_id,
        "requirement_id": requirement_id,
        "source": {"collection": COLLECTION_DECISIONS, "id": decision_id},
        "summary": f"Decision snapshot for {decision_id}",
        "status": "success",
        "severity": "info",
    }

    authority = decision_authority.get("service", "compliance_evidence_graph")
    component = decision_authority.get("component", "emit_compliance_decision")

    snapshot_edge = {
        "edge_id": f"ceg_edge_{uuid.uuid4().hex}",
        "from_node_id": decision_node_id,
        "to_node_id": snapshot_node_id,
        "edge_type": EDGE_SNAPSHOT_OF,
        "relationship_strength": "authoritative",
        "occurred_at": ts,
        "recorded_at": now,
        "dedupe_key": f"snapshot_of:{decision_id}:{snapshot_id}",
        "provenance": {
            "why_exists": f"Decision {decision_id} frozen knowledge state at decision time",
            "created_by_component": component,
            "created_by_authority": authority,
            "created_at": now,
            "decision_id": decision_id,
            "runtime_event_id": None,
            "operational_event_id": None,
            "correlation_id": operational_correlation_id,
            "is_active": True,
            "superseded_by_edge_id": None,
        },
        "metadata": {},
    }

    try:
        _validate_edge(edge_type=EDGE_SNAPSHOT_OF, provenance=snapshot_edge["provenance"])
        await decision_storage.insert_decision(decision_doc)
        await snapshot_storage.insert_snapshot(snap_body)
        await node_storage.insert_node(decision_node)
        await node_storage.insert_node(snapshot_node)
        await edge_storage.insert_edge(snapshot_edge)

        for raw_edge in evidence_edges or []:
            edge_type = raw_edge.get("edge_type", EDGE_BASED_ON_EVIDENCE)
            prov = dict(raw_edge.get("provenance") or {})
            prov.setdefault("created_at", now)
            prov.setdefault("decision_id", decision_id)
            prov.setdefault("is_active", True)
            prov.setdefault("created_by_component", component)
            prov.setdefault("created_by_authority", authority)
            prov.setdefault("why_exists", raw_edge.get("why_exists", "Evidence supported decision"))
            _validate_edge(edge_type=edge_type, provenance=prov)
            edge_doc = {
                "edge_id": f"ceg_edge_{uuid.uuid4().hex}",
                "from_node_id": raw_edge["from_node_id"],
                "to_node_id": raw_edge["to_node_id"],
                "edge_type": edge_type,
                "relationship_strength": raw_edge.get("relationship_strength", "authoritative"),
                "occurred_at": raw_edge.get("occurred_at", ts),
                "recorded_at": now,
                "dedupe_key": raw_edge["dedupe_key"],
                "provenance": prov,
                "metadata": raw_edge.get("metadata") or {},
            }
            dup = await edge_storage.get_edge_by_dedupe(edge_doc["dedupe_key"])
            if not dup:
                await edge_storage.insert_edge(edge_doc)

    except Exception as exc:
        logger.warning("compliance_evidence_graph emit failed: %s", exc)
        return None

    return decision_id
