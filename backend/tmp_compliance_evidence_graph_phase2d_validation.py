"""Local runtime validation for CEG Phase 2D P2 producers."""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time


async def _main() -> int:
    os.environ.setdefault("COMPLIANCE_EVIDENCE_GRAPH_MODE", "shadow")
    from services.compliance_evidence_graph.producers.bootstrap import ensure_producers_initialized
    from services.compliance_evidence_graph.producers.ceg_dispatch import try_dispatch_p2
    from services.compliance_evidence_graph.producers.registry import list_producer_registry

    ensure_producers_initialized()
    registry = list_producer_registry()
    p2 = [e for e in registry if e["priority"] == "P2" and e["emit_implemented"]]

    t0 = time.perf_counter()
    for kind in ("daily_reminder", "notification_sent", "work_order_lifecycle"):
        await try_dispatch_p2(
            mutation_kind=kind,
            client_id="ceg_phase2d_validation",
            source_collection="validation",
            source_id=f"val_{kind}",
            authoritative_payload={"validation": True},
        )

    results = {
        "phase": "2D",
        "acceptance": "PHASE_2D_P2_LOCAL",
        "p2_registry_implemented": len(p2),
        "elapsed_ms": int((time.perf_counter() - t0) * 1000),
    }
    out_path = os.path.join(
        os.path.dirname(__file__),
        "docs/audit/compliance_evidence_graph_and_explainable_intelligence_01/PHASE_2D_RUNTIME_VALIDATION.json",
    )
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2)
    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
