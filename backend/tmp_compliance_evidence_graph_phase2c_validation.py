"""Runtime validation for CEG Phase 2C P1 producers (local shadow mode)."""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time


async def _main() -> int:
    os.environ.setdefault("COMPLIANCE_EVIDENCE_GRAPH_MODE", "shadow")
    from services.compliance_evidence_graph.config import graph_mode, graph_producers_enabled
    from services.compliance_evidence_graph.producers.bootstrap import ensure_producers_initialized
    from services.compliance_evidence_graph.producers.hooks import dispatch_p1_producer
    from services.compliance_evidence_graph.producers.registry import ProducerContext, list_producer_registry

    ensure_producers_initialized()
    registry = list_producer_registry()
    p1_live = [e for e in registry if e["priority"] == "P1" and e["emit_implemented"]]

    results = {
        "phase": "2C",
        "acceptance": "PHASE_2C_P1_LOCAL",
        "feature_flag": {"mode": graph_mode(), "producers_enabled": graph_producers_enabled()},
        "p1_registry_implemented": len(p1_live),
        "dispatch_samples": [],
        "elapsed_ms": 0,
    }

    t0 = time.perf_counter()
    samples = [
        ("applicability_operator", {"command": "MARK_REQUIRED"}),
        ("requirement_materialization", {"trigger": "validation", "upsert_passes": 1}),
        ("risk_signal_generation", {"generated": 0, "signals": []}),
        ("document_extraction_reject", {"reason": "validation"}),
    ]
    for kind, payload in samples:
        dec = await dispatch_p1_producer(
            ProducerContext(
                mutation_kind=kind,
                client_id="ceg_phase2c_validation",
                source_collection="validation",
                source_id=f"val_{kind}",
                property_id="val_property",
                requirement_id="val_requirement",
                correlation_id=f"PHASE2C:{kind}",
                authoritative_payload=payload,
            )
        )
        results["dispatch_samples"].append({"mutation_kind": kind, "decision_id": dec})

    results["elapsed_ms"] = int((time.perf_counter() - t0) * 1000)
    out_path = os.path.join(
        os.path.dirname(__file__),
        "docs/audit/compliance_evidence_graph_and_explainable_intelligence_01/PHASE_2C_RUNTIME_VALIDATION.json",
    )
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2)
    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
