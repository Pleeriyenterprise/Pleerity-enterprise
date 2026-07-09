"""Phase 2E acceptance validation — CEG full programme gate."""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
if not os.environ.get("MONGO_URL") and os.environ.get("MONGO_URI"):
    os.environ["MONGO_URL"] = os.environ["MONGO_URI"]

os.environ.setdefault("COMPLIANCE_EVIDENCE_GRAPH_MODE", "shadow")

OUT_DIR = Path(__file__).resolve().parent / "docs/audit/compliance_evidence_graph_and_explainable_intelligence_01"
RUN_TAG = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


async def main() -> int:
    from database import database
    from services.compliance_evidence_graph.acceptance import evaluate_mutation_coverage
    from services.compliance_evidence_graph.backfill_service import run_bounded_backfill
    from services.compliance_evidence_graph.config import graph_mode, graph_producers_enabled
    from services.compliance_evidence_graph.producers.bootstrap import ensure_producers_initialized
    from services.compliance_evidence_graph.producers.registry import list_producer_registry
    from services.compliance_evidence_graph.validation.integrity_validator import validate_graph
    from services.compliance_graph_health.service import generate_health_report

    report: dict = {
        "programme": "COMPLIANCE-EVIDENCE-GRAPH-PHASE-2E",
        "validated_at": datetime.now(timezone.utc).isoformat(),
        "run_tag": RUN_TAG,
        "feature_flag": {"mode": graph_mode(), "producers_enabled": graph_producers_enabled()},
        "checks": [],
        "coverage": {},
        "acceptance": "PENDING",
    }

    def add(name: str, passed: bool, **detail):
        row = {"name": name, "passed": passed}
        row.update({k: v for k, v in detail.items() if k != "passed"})
        report["checks"].append(row)

    t0 = time.perf_counter()
    await database.connect()
    ensure_producers_initialized()

    registry = list_producer_registry()
    coverage = evaluate_mutation_coverage(registry)
    report["coverage"] = coverage
    add("mutation_coverage_thresholds", coverage["all_passed"], **coverage)

    health = await generate_health_report(max_decisions=500)
    add(
        "graph_health_report",
        str(health.get("overall_status", "")).lower() in ("healthy", "warning"),
        overall=health.get("overall_status"),
    )

    integrity = await validate_graph(max_decisions=500)
    idict = integrity.to_dict()
    add(
        "integrity_validator",
        integrity.valid is True,
        failures=len(idict.get("failures") or []),
        warnings=len(idict.get("warnings") or []),
        stats=idict.get("stats"),
    )

    backfill1 = await run_bounded_backfill(max_decisions=5, dry_run=True)
    backfill2 = await run_bounded_backfill(max_decisions=5, dry_run=True)

    def _backfill_semantic(bf: dict) -> dict:
        return {k: v for k, v in bf.items() if k != "completed_at"}

    add(
        "backfill_dry_run_idempotent",
        backfill1.get("ok") is True and _backfill_semantic(backfill1) == _backfill_semantic(backfill2),
        run1=backfill1,
        run2=backfill2,
    )

    from services.compliance_evidence_graph.producers.hooks import dispatch_p2_producer
    from services.compliance_evidence_graph.producers.registry import ProducerContext

    smoke_cid = f"ceg-2e-{RUN_TAG}"
    smoke_ctx = ProducerContext(
        mutation_kind="daily_reminder",
        client_id=smoke_cid,
        source_collection="reminders",
        source_id=f"accept-{RUN_TAG}",
        correlation_id=f"ACC:{RUN_TAG}",
        authoritative_payload={"success_count": 1, "validation": True},
    )
    d1 = await dispatch_p2_producer(smoke_ctx)
    d2 = await dispatch_p2_producer(smoke_ctx)
    add("p2_emit_idempotent", d1 is not None and d1 == d2, decision_id=d1)

    if d1:
        from services.compliance_graph_service import service as graph_service
        from services.compliance_graph_service.access import ActorContext

        actor = ActorContext(is_admin=True, client_id=smoke_cid)
        explain = await graph_service.explain_decision(d1, actor=actor)
        replay = await graph_service.replay_decision(d1, actor=actor)
        add(
            "graph_service_explain_replay",
            explain.get("status") != "insufficient" and bool(replay.get("payload")),
            explain_status=explain.get("status"),
        )
    else:
        add("graph_service_explain_replay", False, reason="no_decision_emitted")

    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    report["elapsed_ms"] = elapsed_ms
    all_passed = all(c["passed"] for c in report["checks"])
    report["acceptance"] = "PHASE_2E_ACCEPTED" if all_passed and coverage["all_passed"] else "PHASE_2E_PENDING"

    coverage_path = OUT_DIR / "PHASE_2_MUTATION_COVERAGE_VALIDATION.json"
    readiness_path = OUT_DIR / "PHASE_2_STAGING_READINESS.json"
    with coverage_path.open("w", encoding="utf-8") as fh:
        json.dump({"run_tag": RUN_TAG, "coverage": coverage, "registry_count": len(registry)}, fh, indent=2)
    with readiness_path.open("w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)

    print(json.dumps(report, indent=2))
    return 0 if report["acceptance"] == "PHASE_2E_ACCEPTED" else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
