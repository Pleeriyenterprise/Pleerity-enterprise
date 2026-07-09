"""COMPLIANCE-EVIDENCE-GRAPH Phase 2B P0 runtime validation (shadow mode)."""
from __future__ import annotations

import asyncio
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

from dotenv import load_dotenv

load_dotenv()
if not os.environ.get("MONGO_URL") and os.environ.get("MONGO_URI"):
    os.environ["MONGO_URL"] = os.environ["MONGO_URI"]

os.environ["COMPLIANCE_EVIDENCE_GRAPH_MODE"] = "shadow"

OUT_DIR = Path(__file__).resolve().parent / "docs/audit/compliance_evidence_graph_and_explainable_intelligence_01"
RUN_TAG = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


async def main() -> int:
    from database import database
    from services.compliance_evidence_graph.config import graph_mode, graph_producers_enabled
    from services.compliance_evidence_graph.producers.bootstrap import initialize_p0_producers
    from services.compliance_evidence_graph.producers.registry import list_producer_registry
    from services.compliance_evidence_graph.validation.integrity_validator import validate_graph
    from services.compliance_graph_health.service import generate_health_report
    from services.compliance_graph_service.access import ActorContext
    from services.compliance_graph_service import service as graph_service
    from services.compliance_evidence_graph.producers.hooks import dispatch_p0_producer
    from services.compliance_evidence_graph.producers.registry import ProducerContext

    report: dict = {
        "programme": "COMPLIANCE-EVIDENCE-GRAPH-PHASE-2B",
        "validated_at": datetime.now(timezone.utc).isoformat(),
        "run_tag": RUN_TAG,
        "feature_flag": {"mode": graph_mode(), "producers_enabled": graph_producers_enabled()},
        "checks": [],
    }

    def add(name: str, passed: bool, **detail):
        report["checks"].append({"name": name, "passed": passed, **detail})

    await database.connect()
    initialize_p0_producers()

    registry = list_producer_registry()
    p0 = [e for e in registry if e["priority"] == "P0"]
    add(
        "p0_registry_implemented",
        len(p0) >= 5 and all(e["emit_implemented"] for e in p0),
        p0_count=len(p0),
        live_active=sum(1 for e in p0 if e.get("live_emit_active")),
    )

    # Simulated score recalc producer journey
    t0 = time.perf_counter()
    with patch(
        "services.compliance_evidence_graph.producers.score.stamp_document",
        new_callable=AsyncMock,
    ):
        dec1 = await dispatch_p0_producer(
            ProducerContext(
                mutation_kind="compliance_score_recalc",
                client_id=f"ceg-2b-{RUN_TAG}",
                source_collection="properties",
                source_id=f"prop-{RUN_TAG}",
                property_id=f"prop-{RUN_TAG}",
                correlation_id=f"corr-recalc-{RUN_TAG}",
                mutation_timestamp=datetime.now(timezone.utc).isoformat(),
                authoritative_payload={
                    "previous_score": 70,
                    "new_score": 78,
                    "delta": 8,
                    "reason": "PHASE_2B_VALIDATION",
                    "changed_requirements": [],
                },
            )
        )
        dec1_dup = await dispatch_p0_producer(
            ProducerContext(
                mutation_kind="compliance_score_recalc",
                client_id=f"ceg-2b-{RUN_TAG}",
                source_collection="properties",
                source_id=f"prop-{RUN_TAG}",
                property_id=f"prop-{RUN_TAG}",
                correlation_id=f"corr-recalc-{RUN_TAG}",
                mutation_timestamp=datetime.now(timezone.utc).isoformat(),
                authoritative_payload={
                    "previous_score": 70,
                    "new_score": 78,
                    "delta": 8,
                    "reason": "PHASE_2B_VALIDATION",
                    "changed_requirements": [],
                },
            )
        )
    emit_ms = round((time.perf_counter() - t0) * 1000, 2)
    add(
        "score_recalc_emit",
        bool(dec1),
        decision_id=dec1,
        idempotent_match=dec1 == dec1_dup,
        latency_ms=emit_ms,
    )

    if dec1:
        actor = ActorContext(is_admin=True, client_id=f"ceg-2b-{RUN_TAG}")
        explain = await graph_service.explain_decision(dec1, actor=actor)
        replay = await graph_service.replay_decision(dec1, actor=actor)
        add(
            "explain_decision_no_ai",
            explain.get("service") == "explain_decision" and not explain.get("insufficient_evidence"),
            has_quality=bool((explain.get("payload") or {}).get("decision_quality") or explain.get("confidence_metadata")),
        )
        add(
            "replay_decision_no_ai",
            replay.get("service") == "replay_decision" and len((replay.get("payload") or {}).get("phases") or []) > 0,
        )

        from services.compliance_evidence_graph.storage import decisions as decision_storage
        from services.compliance_evidence_graph.storage import snapshots as snapshot_storage
        from services.compliance_evidence_graph.storage import nodes as node_storage
        from services.compliance_evidence_graph.storage import edges as edge_storage

        dec = await decision_storage.get_decision(dec1)
        snap = await snapshot_storage.get_snapshot_by_decision(dec1) if dec1 else None
        nodes = await node_storage.list_nodes_for_decision(dec1)
        edges = await edge_storage.list_edges_for_decision(dec1)
        add(
            "decision_lineage_complete",
            bool(dec and snap and len(nodes) >= 2 and len(edges) >= 1),
            has_decision_quality=bool((dec or {}).get("decision_quality")),
            node_count=len(nodes),
            edge_count=len(edges),
        )

    validation = await validate_graph(max_decisions=500)
    vdict = validation.to_dict()
    health = await generate_health_report(max_decisions=500)
    report["integrity_validator"] = vdict
    report["graph_health"] = {
        "overall_status": health.get("overall_status"),
        "summary": health.get("summary"),
        "metrics": health.get("metrics"),
    }
    add("integrity_validator_pass", validation.valid or len(vdict.get("failures") or []) == 0)
    add("graph_health_acceptable", health.get("overall_status") in ("healthy", "degraded"))

    passed = sum(1 for c in report["checks"] if c["passed"])
    total = len(report["checks"])
    report["summary"] = {
        "passed": passed,
        "total": total,
        "verdict": "PHASE_2B_P0_ACCEPTED" if passed == total else "PHASE_2B_P0_FAILED",
        "phase_2c_ready_recommendation": passed == total,
        "emit_latency_ms": emit_ms,
    }
    out = OUT_DIR / "PHASE_2B_RUNTIME_VALIDATION.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
