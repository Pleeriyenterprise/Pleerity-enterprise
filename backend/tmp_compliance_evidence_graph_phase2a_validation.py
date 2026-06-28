"""COMPLIANCE-EVIDENCE-GRAPH Phase 2A runtime validation."""
from __future__ import annotations

import asyncio
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
if not os.environ.get("MONGO_URL") and os.environ.get("MONGO_URI"):
    os.environ["MONGO_URL"] = os.environ["MONGO_URI"]

os.environ.setdefault("COMPLIANCE_EVIDENCE_GRAPH_MODE", "phase1_validation")

OUT_DIR = Path(__file__).resolve().parent / "docs/audit/compliance_evidence_graph_and_explainable_intelligence_01"
RUN_TAG = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


async def main() -> int:
    from database import database
    from services.compliance_evidence_graph.bridge_operational import resolve_operational_bridge
    from services.compliance_evidence_graph.config import graph_mode, graph_producers_enabled
    from services.compliance_evidence_graph.producers._base import compute_decision_quality
    from services.compliance_evidence_graph.producers.registry import (
        ProducerContext,
        emit_for_mutation,
        list_producer_registry,
    )
    from services.compliance_evidence_graph.validation.integrity_validator import validate_graph
    from services.compliance_graph_health.service import generate_health_report
    from services.compliance_graph_service.fixtures import seed_fixture_decision

    report: dict = {
        "programme": "COMPLIANCE-EVIDENCE-GRAPH-PHASE-2A",
        "validated_at": datetime.now(timezone.utc).isoformat(),
        "run_tag": RUN_TAG,
        "feature_flag": {"mode": graph_mode(), "producers_enabled": graph_producers_enabled()},
        "checks": [],
    }

    def add(name: str, passed: bool, **detail):
        report["checks"].append({"name": name, "passed": passed, **detail})

    await database.connect()

    # Registry metadata
    registry = list_producer_registry()
    add(
        "producer_registry",
        len(registry) >= 10 and all(not e["emit_implemented"] for e in registry),
        entry_count=len(registry),
        live_emit_count=sum(1 for e in registry if e.get("live_emit_active")),
    )

    # Shadow dispatch does not emit (2A)
    os.environ["COMPLIANCE_EVIDENCE_GRAPH_MODE"] = "shadow"
    ctx = ProducerContext(
        mutation_kind="evidence_authority_sync",
        client_id="phase2a-client",
        source_collection="requirements",
        source_id="req-phase2a",
    )
    dispatch_result = await emit_for_mutation(mutation_kind="evidence_authority_sync", context=ctx)
    add("producer_dispatch_no_live_emit", dispatch_result is None, dispatch_result=dispatch_result)
    os.environ["COMPLIANCE_EVIDENCE_GRAPH_MODE"] = "phase1_validation"

    # Decision quality
    dq = compute_decision_quality(
        evidence_completeness="complete",
        evidence_confidence_score=100,
        human_verification_status="approved",
    )
    add(
        "decision_quality_computation",
        dq.get("overall_label") == "confirmed" and bool(dq.get("computed_by")),
        overall_label=dq.get("overall_label"),
        computed_by=dq.get("computed_by"),
    )

    # Operational bridge
    bridge = resolve_operational_bridge(correlation_id=f"phase2a-{RUN_TAG}")
    add(
        "operational_bridge",
        bridge.get("operational_correlation_id") == f"phase2a-{RUN_TAG}",
        has_operational_context=bool(bridge.get("operational_context")),
    )

    # Fixture seed for validator + health (Phase 1 path — not a live producer)
    t0 = time.perf_counter()
    dec_id = await seed_fixture_decision(dedupe_suffix=f"phase2a-{RUN_TAG}")
    seed_ms = round((time.perf_counter() - t0) * 1000, 2)
    add("fixture_seed_for_validation", bool(dec_id), decision_id=dec_id, latency_ms=seed_ms)

    if dec_id:
        t0 = time.perf_counter()
        validation = await validate_graph(max_decisions=500)
        val_ms = round((time.perf_counter() - t0) * 1000, 2)
        vdict = validation.to_dict()
        add(
            "integrity_validator",
            validation.valid or len(vdict.get("failures") or []) == 0,
            latency_ms=val_ms,
            failures=len(vdict.get("failures") or []),
            warnings=len(vdict.get("warnings") or []),
        )
        report["integrity_validator_sample"] = vdict

        t0 = time.perf_counter()
        health = await generate_health_report(max_decisions=500)
        health_ms = round((time.perf_counter() - t0) * 1000, 2)
        add(
            "graph_health_service",
            health.get("service") == "compliance_graph_health",
            latency_ms=health_ms,
            overall_status=health.get("overall_status"),
        )
        report["graph_health_sample"] = {
            "overall_status": health.get("overall_status"),
            "summary": health.get("summary"),
            "metrics": health.get("metrics"),
            "producer_registry": health.get("producer_registry"),
        }

    passed = sum(1 for c in report["checks"] if c["passed"])
    total = len(report["checks"])
    report["summary"] = {
        "passed": passed,
        "total": total,
        "verdict": "PHASE_2A_ACCEPTED" if passed == total else "PHASE_2A_FAILED",
        "phase_2b_ready": passed == total,
    }

    out_path = OUT_DIR / "PHASE_2A_RUNTIME_VALIDATION.json"
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
    print(f"Wrote {out_path}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
