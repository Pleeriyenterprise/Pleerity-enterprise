"""
Graph Integrity Validator — read-only structural validation.

Shared by Graph Health service, staging acceptance, and future scheduled checks.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Set

from database import database

from services.compliance_evidence_graph.constants import ALL_DECISION_TYPES, ALL_EDGE_TYPES
from services.compliance_evidence_graph.storage import decisions as decision_storage
from services.compliance_evidence_graph.storage import edges as edge_storage
from services.compliance_evidence_graph.storage import nodes as node_storage
from services.compliance_evidence_graph.storage import snapshots as snapshot_storage
from services.compliance_evidence_graph.validation.result import CheckFailure, ValidationResult

VALIDATOR_VERSION = "1.0.0"

_PROVENANCE_REQUIRED = (
    "why_exists",
    "created_by_component",
    "created_by_authority",
    "created_at",
    "is_active",
)


async def validate_graph(
    *,
    client_id: Optional[str] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
    max_decisions: int = 10_000,
) -> ValidationResult:
    t0 = time.perf_counter()
    result = ValidationResult(valid=True)
    decisions = await decision_storage.list_decisions_for_scope(
        client_id=client_id,
        since=since,
        until=until,
        limit=max_decisions,
    )
    result.stats["decisions_examined"] = len(decisions)

    seen_dedupe: Dict[str, str] = {}
    seen_snapshot: Dict[str, str] = {}
    node_ids: Set[str] = set()
    edge_count = 0

    for dec in decisions:
        did = dec.get("decision_id", "")
        sub = await validate_decision(did)
        result.merge(sub)

        dk = dec.get("dedupe_key")
        if dk:
            if dk in seen_dedupe:
                result.add_failure(
                    CheckFailure(
                        check="validate_graph",
                        severity="failure",
                        entity_type="decision",
                        entity_id=did,
                        decision_id=did,
                        message="duplicate dedupe_key",
                        details={"dedupe_key": dk, "other_decision_id": seen_dedupe[dk]},
                    )
                )
            else:
                seen_dedupe[dk] = did

        sid = dec.get("snapshot_id")
        if sid:
            if sid in seen_snapshot:
                result.add_failure(
                    CheckFailure(
                        check="validate_graph",
                        severity="failure",
                        entity_type="snapshot",
                        entity_id=sid,
                        decision_id=did,
                        message="duplicate snapshot_id across decisions",
                    )
                )
            else:
                seen_snapshot[sid] = did

        for node in await node_storage.list_nodes_for_decision(did):
            nid = node.get("node_id")
            if nid:
                node_ids.add(nid)

        edges = await edge_storage.list_edges_for_decision(did)
        edge_count += len(edges)
        rel = await validate_relationships(decision_id=did)
        result.merge(rel)

    result.stats["nodes_examined"] = len(node_ids)
    result.stats["edges_examined"] = edge_count

    orphan_result = await _validate_orphan_edges(node_ids)
    result.merge(orphan_result)

    if client_id:
        tenant_result = await validate_tenant_isolation(client_id=client_id)
        result.merge(tenant_result)

    result.duration_ms = round((time.perf_counter() - t0) * 1000, 2)
    result.checks_run = max(result.checks_run, 1)
    return result


async def validate_decision(decision_id: str) -> ValidationResult:
    result = ValidationResult(valid=True, checks_run=1)
    dec = await decision_storage.get_decision(decision_id)
    if not dec:
        result.add_failure(
            CheckFailure(
                check="validate_decision",
                severity="failure",
                entity_type="decision",
                entity_id=decision_id,
                message="decision not found",
            )
        )
        return result

    if dec.get("decision_type") not in ALL_DECISION_TYPES:
        result.add_failure(
            CheckFailure(
                check="validate_decision",
                severity="failure",
                entity_type="decision",
                entity_id=decision_id,
                decision_id=decision_id,
                message="invalid decision_type",
            )
        )

    if not dec.get("snapshot_id"):
        result.add_failure(
            CheckFailure(
                check="validate_decision",
                severity="failure",
                entity_type="decision",
                entity_id=decision_id,
                decision_id=decision_id,
                message="missing snapshot_id",
            )
        )

    source = dec.get("source") or {}
    if not source.get("collection") or not source.get("id"):
        result.add_failure(
            CheckFailure(
                check="validate_decision",
                severity="failure",
                entity_type="decision",
                entity_id=decision_id,
                decision_id=decision_id,
                message="missing source pointer",
            )
        )

    if not dec.get("client_id"):
        result.add_failure(
            CheckFailure(
                check="validate_decision",
                severity="failure",
                entity_type="decision",
                entity_id=decision_id,
                decision_id=decision_id,
                message="missing client_id",
            )
        )

    dq = dec.get("decision_quality")
    if not dq and not (dec.get("metadata") or {}).get("backfill"):
        result.add_failure(
            CheckFailure(
                check="validate_decision",
                severity="warning",
                entity_type="decision",
                entity_id=decision_id,
                decision_id=decision_id,
                message="missing decision_quality",
            )
        )

    snap = await snapshot_storage.get_snapshot_by_decision(decision_id)
    if not snap:
        result.add_failure(
            CheckFailure(
                check="validate_decision",
                severity="failure",
                entity_type="decision",
                entity_id=decision_id,
                decision_id=decision_id,
                message="snapshot not found for decision",
            )
        )

    return result


async def validate_snapshot(snapshot_id: str) -> ValidationResult:
    result = ValidationResult(valid=True, checks_run=1)
    snap = await snapshot_storage.get_snapshot(snapshot_id)
    if not snap:
        result.add_failure(
            CheckFailure(
                check="validate_snapshot",
                severity="failure",
                entity_type="snapshot",
                entity_id=snapshot_id,
                message="snapshot not found",
            )
        )
        return result

    if not snap.get("snapshot_hash"):
        result.add_failure(
            CheckFailure(
                check="validate_snapshot",
                severity="failure",
                entity_type="snapshot",
                entity_id=snapshot_id,
                decision_id=snap.get("decision_id"),
                message="missing snapshot_hash",
            )
        )

    did = snap.get("decision_id")
    if did:
        dec = await decision_storage.get_decision(did)
        if not dec:
            result.add_failure(
                CheckFailure(
                    check="validate_snapshot",
                    severity="failure",
                    entity_type="snapshot",
                    entity_id=snapshot_id,
                    decision_id=did,
                    message="decision not found for snapshot",
                )
            )
        elif dec.get("snapshot_id") != snapshot_id:
            result.add_failure(
                CheckFailure(
                    check="validate_snapshot",
                    severity="failure",
                    entity_type="snapshot",
                    entity_id=snapshot_id,
                    decision_id=did,
                    message="decision.snapshot_id mismatch",
                )
            )

    return result


async def validate_relationships(*, decision_id: Optional[str] = None) -> ValidationResult:
    result = ValidationResult(valid=True, checks_run=1)
    if not decision_id:
        return result

    edges = await edge_storage.list_edges_for_decision(decision_id)
    for edge in edges:
        eid = edge.get("edge_id", "")
        et = edge.get("edge_type")
        if et not in ALL_EDGE_TYPES:
            result.add_failure(
                CheckFailure(
                    check="validate_relationships",
                    severity="failure",
                    entity_type="edge",
                    entity_id=eid,
                    decision_id=decision_id,
                    message="invalid edge_type",
                    details={"edge_type": et},
                )
            )

        prov = edge.get("provenance") or {}
        for field in _PROVENANCE_REQUIRED:
            if field not in prov or prov[field] is None:
                result.add_failure(
                    CheckFailure(
                        check="validate_relationships",
                        severity="failure",
                        entity_type="edge",
                        entity_id=eid,
                        decision_id=decision_id,
                        message=f"missing provenance.{field}",
                    )
                )

        for node_ref, label in (
            (edge.get("from_node_id"), "from_node_id"),
            (edge.get("to_node_id"), "to_node_id"),
        ):
            if not node_ref:
                result.add_failure(
                    CheckFailure(
                        check="validate_relationships",
                        severity="failure",
                        entity_type="edge",
                        entity_id=eid,
                        decision_id=decision_id,
                        message=f"missing {label}",
                    )
                )
            else:
                node = await node_storage.get_node(node_ref)
                if not node:
                    result.add_failure(
                        CheckFailure(
                            check="validate_relationships",
                            severity="failure",
                            entity_type="edge",
                            entity_id=eid,
                            decision_id=decision_id,
                            message=f"broken reference {label}",
                            details={label: node_ref},
                        )
                    )

    return result


async def validate_rule_lineage(*, decision_id: str) -> ValidationResult:
    result = ValidationResult(valid=True, checks_run=1)
    dec = await decision_storage.get_decision(decision_id)
    if not dec:
        return result

    snap = await snapshot_storage.get_snapshot_by_decision(decision_id)
    lineage = (snap or {}).get("rule_lineage") or {}
    if lineage.get("lineage_complete") is False and not lineage.get("lineage_incomplete_reason"):
        result.add_failure(
            CheckFailure(
                check="validate_rule_lineage",
                severity="warning",
                entity_type="decision",
                entity_id=decision_id,
                decision_id=decision_id,
                message="incomplete rule lineage without reason",
            )
        )

    edges = await edge_storage.list_edges_for_decision(decision_id)
    has_decided_under = any(e.get("edge_type") in ("decided_under", "governed_by") for e in edges)
    if dec.get("decision_type") in ("compliance_assessment", "requirement_applicability") and not has_decided_under:
        if not lineage.get("lineage_incomplete"):
            result.add_failure(
                CheckFailure(
                    check="validate_rule_lineage",
                    severity="warning",
                    entity_type="decision",
                    entity_id=decision_id,
                    decision_id=decision_id,
                    message="no decided_under/governed_by edge for assessment decision",
                )
            )

    return result


async def validate_operational_links(*, decision_id: str) -> ValidationResult:
    result = ValidationResult(valid=True, checks_run=1)
    dec = await decision_storage.get_decision(decision_id)
    if not dec:
        return result

    cid = dec.get("operational_correlation_id")
    if not cid:
        return result

    db = database.get_db()
    oe = await db.operational_evidence_events.find_one({"correlation_id": cid}, {"_id": 0, "event_id": 1})
    queue = await db.compliance_recalc_queue.find_one({"correlation_id": cid}, {"_id": 0, "correlation_id": 1})
    if not oe and not queue:
        result.add_failure(
            CheckFailure(
                check="validate_operational_links",
                severity="warning",
                entity_type="decision",
                entity_id=decision_id,
                decision_id=decision_id,
                message="operational_correlation_id has no matching OE event or recalc queue row",
                details={"correlation_id": cid},
            )
        )

    return result


async def validate_supersession(*, decision_id: Optional[str] = None) -> ValidationResult:
    result = ValidationResult(valid=True, checks_run=1)
    if not decision_id:
        return result

    dec = await decision_storage.get_decision(decision_id)
    if not dec:
        return result

    prev_id = dec.get("previous_decision_id")
    if prev_id:
        prev = await decision_storage.get_decision(prev_id)
        if not prev:
            result.add_failure(
                CheckFailure(
                    check="validate_supersession",
                    severity="failure",
                    entity_type="decision",
                    entity_id=decision_id,
                    decision_id=decision_id,
                    message="previous_decision_id not found",
                    details={"previous_decision_id": prev_id},
                )
            )
        elif prev.get("superseding_decision_id") and prev.get("superseding_decision_id") != decision_id:
            result.add_failure(
                CheckFailure(
                    check="validate_supersession",
                    severity="failure",
                    entity_type="decision",
                    entity_id=decision_id,
                    decision_id=decision_id,
                    message="supersession chain mismatch",
                )
            )

    return result


async def validate_tenant_isolation(*, client_id: Optional[str] = None) -> ValidationResult:
    result = ValidationResult(valid=True, checks_run=1)
    db = database.get_db()
    q: Dict[str, Any] = {}
    if client_id:
        q["client_id"] = client_id

    cursor = db.compliance_evidence_nodes.find(q, {"_id": 0, "node_id": 1, "client_id": 1, "decision_id": 1}).limit(
        5000
    )
    nodes = await cursor.to_list(5000)
    for node in nodes:
        nid = node.get("node_id", "")
        ncid = node.get("client_id")
        did = node.get("decision_id")
        if not did or not ncid:
            continue
        dec = await decision_storage.get_decision(did)
        if dec and dec.get("client_id") and dec.get("client_id") != ncid:
            result.add_failure(
                CheckFailure(
                    check="validate_tenant_isolation",
                    severity="failure",
                    entity_type="node",
                    entity_id=nid,
                    decision_id=did,
                    message="node client_id mismatch with decision",
                    details={"node_client_id": ncid, "decision_client_id": dec.get("client_id")},
                )
            )

    return result


async def _validate_orphan_edges(node_ids: Set[str]) -> ValidationResult:
    result = ValidationResult(valid=True, checks_run=1)
    if not node_ids:
        return result

    db = database.get_db()
    cursor = db.compliance_evidence_edges.find({}, {"_id": 0}).limit(5000)
    edges = await cursor.to_list(5000)
    for edge in edges:
        eid = edge.get("edge_id", "")
        for ref, label in ((edge.get("from_node_id"), "from"), (edge.get("to_node_id"), "to")):
            if ref and ref not in node_ids:
                node = await node_storage.get_node(ref)
                if not node:
                    result.add_failure(
                        CheckFailure(
                            check="validate_graph",
                            severity="failure",
                            entity_type="edge",
                            entity_id=eid,
                            message=f"orphan edge {label} node",
                            details={f"{label}_node_id": ref},
                        )
                    )
                    if ref:
                        node_ids.add(ref)

    return result
