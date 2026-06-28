"""COMPLIANCE-EVIDENCE-GRAPH Phase 1 runtime validation (fixtures only)."""
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
    from services.compliance_graph_service.access import ActorContext
    from services.compliance_graph_service import service as graph_service
    from services.compliance_graph_service.fixtures import seed_fixture_decision
    from services.compliance_evidence_graph.config import graph_mode, graph_producers_enabled

    report: dict = {
        "programme": "COMPLIANCE-EVIDENCE-GRAPH-PHASE-1",
        "validated_at": datetime.now(timezone.utc).isoformat(),
        "run_tag": RUN_TAG,
        "feature_flag": {"mode": graph_mode(), "producers_enabled": graph_producers_enabled()},
        "checks": [],
    }

    def add(name: str, passed: bool, **detail):
        report["checks"].append({"name": name, "passed": passed, **detail})

    await database.connect()
    db = database.get_db()
    actor = ActorContext(is_admin=True)

    t0 = time.perf_counter()
    dec1 = await seed_fixture_decision(dedupe_suffix=f"{RUN_TAG}-a")
    dec2 = await seed_fixture_decision(
        dedupe_suffix=f"{RUN_TAG}-b",
        outcome="PENDING",
        previous_decision_id=dec1,
        decision_timestamp="2026-06-02T10:00:00+00:00",
    )
    emit_ms = round((time.perf_counter() - t0) * 1000, 2)
    add("fixture_emit", bool(dec1 and dec2), dec1=dec1, dec2=dec2, latency_ms=emit_ms)

    if dec1:
        t0 = time.perf_counter()
        explain = await graph_service.explain_decision(dec1, actor=actor)
        explain_ms = round((time.perf_counter() - t0) * 1000, 2)
        add(
            "explain_decision",
            explain.get("service") == "explain_decision" and not explain.get("insufficient_evidence"),
            latency_ms=explain_ms,
            has_snapshot_ref=bool(explain.get("historical_references", {}).get("snapshot_id")),
        )

        t0 = time.perf_counter()
        replay = await graph_service.replay_decision(dec1, actor=actor)
        replay_ms = round((time.perf_counter() - t0) * 1000, 2)
        add(
            "replay_decision",
            replay.get("service") == "replay_decision" and len(replay.get("payload", {}).get("phases", [])) > 0,
            latency_ms=replay_ms,
        )

    if dec1 and dec2:
        t0 = time.perf_counter()
        compare = await graph_service.compare_decision(dec1, dec2, actor=actor)
        compare_ms = round((time.perf_counter() - t0) * 1000, 2)
        add(
            "compare_decision",
            compare.get("payload", {}).get("outcome_changed") is True,
            latency_ms=compare_ms,
        )

    hist = await graph_service.find_historical_decision(
        client_id="ceg-fixture-client",
        as_of="2026-06-03T00:00:00+00:00",
        actor=actor,
        requirement_id="ceg-fixture-requirement",
    )
    add(
        "find_historical_decision",
        hist.get("payload", {}).get("decision_id") == dec2,
        resolved=hist.get("payload", {}).get("decision_id"),
    )

    if dec1:
        snap = await db.compliance_decision_snapshots.find_one({"decision_id": dec1}, {"_id": 0})
        edge = await db.compliance_evidence_edges.find_one({"provenance.decision_id": dec1}, {"_id": 0})
        add("snapshot_immutable_exists", bool(snap and snap.get("snapshot_hash")))
        add(
            "edge_provenance_complete",
            bool(
                edge
                and edge.get("provenance", {}).get("why_exists")
                and edge.get("provenance", {}).get("created_by_authority")
                and edge.get("provenance", {}).get("is_active") is True
            ),
        )

    passed = sum(1 for c in report["checks"] if c["passed"])
    failed = len(report["checks"]) - passed
    report["summary"] = {
        "passed": passed,
        "failed": failed,
        "overall": failed == 0,
        "recommendation": "PHASE_2_READY" if failed == 0 else "PHASE_1_BLOCKED",
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "PHASE_1_RUNTIME_VALIDATION.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
    print(f"Report: {out}")
    return 0 if report["summary"]["overall"] else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
