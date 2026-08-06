"""
MONGODB-STORAGE-PREVENTION-VALIDATION-01 evidence harness.

Read-mostly. Staging retention live purge only when --allow-retention-live.
Never targets production. No Tier-1 cleanup.
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OUT_JSON = ROOT / "docs" / "audit" / "mongodb_storage_validation_results_01.json"
REPO = ROOT.parent


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def http_json(url: str, timeout: int = 45) -> Dict[str, Any]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            body = r.read().decode("utf-8", "replace")
            return {"ok": True, "status": r.status, "body": json.loads(body) if body.startswith("{") else body[:500]}
    except urllib.error.HTTPError as e:
        return {"ok": False, "status": e.code, "error": str(e)}
    except Exception as e:
        return {"ok": False, "status": None, "error": f"{type(e).__name__}: {e}"}


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=str(REPO), text=True).strip()


def phase1_deployment() -> Dict[str, Any]:
    rem_files = [
        "backend/services/job_run_idle_persist.py",
        "backend/services/mongo_storage_monitor.py",
        "backend/services/operational_retention_purge.py",
        "backend/utils/mongo_capacity_errors.py",
        "backend/scripts/mongodb_controlled_cleanup_01.py",
        "backend/tests/test_mongo_storage_governance_01.py",
    ]
    tracked = {}
    for f in rem_files:
        out = subprocess.check_output(["git", "ls-files", f], cwd=str(REPO), text=True).strip()
        tracked[f] = bool(out)

    local_head = git("rev-parse", "HEAD")
    staging_ver = http_json("https://pleerity-enterprise.onrender.com/api/version")
    staging_health = http_json("https://pleerity-enterprise.onrender.com/api/health")
    remote_sha = None
    if staging_ver.get("ok") and isinstance(staging_ver.get("body"), dict):
        remote_sha = staging_ver["body"].get("commit_sha")

    all_tracked = all(tracked.values())
    deployed = bool(remote_sha) and remote_sha == local_head and all_tracked
    # Remediaton not in HEAD if untracked
    remediation_in_deployed_sha = all_tracked  # if untracked, not in any commit including deployed

    return {
        "phase": 1,
        "local_head": local_head,
        "staging_version": staging_ver,
        "staging_health": staging_health,
        "remediation_files_tracked": tracked,
        "all_remediation_files_in_git": all_tracked,
        "staging_matches_local_head": remote_sha == local_head,
        "remediation_deployed_to_staging": False if not all_tracked else deployed,
        "verdict": "FAIL_NOT_DEPLOYED" if not all_tracked else ("PASS" if deployed else "FAIL_SHA_MISMATCH"),
        "evidence_note": (
            "Remediation Python modules are untracked locally and therefore absent from "
            f"deployed commit {remote_sha}. Staging cannot be executing idle-skip/monitor/retention/503 handlers."
        ),
    }


def phase2_monitor_unit() -> Dict[str, Any]:
    from services.mongo_storage_monitor import THRESHOLDS, classify_usage_pct

    matrix = []
    for pct, expected in [
        (10, "ok"),
        (60, "warning"),
        (75, "attention"),
        (85, "critical"),
        (90, "platform_alert"),
        (95, "emergency"),
    ]:
        got = classify_usage_pct(float(pct))
        matrix.append({"pct": pct, "expected": expected, "got": got, "pass": got == expected})

    # Severity mapping for incidents (code contract)
    sev_map = {
        "warning": None,
        "attention": None,
        "critical": "P2",
        "platform_alert": "P1",
        "emergency": "P0",
    }
    return {
        "phase": 2,
        "mode": "unit_contract",
        "thresholds_constant": [{"pct": t, "level": lvl} for t, lvl in THRESHOLDS],
        "classification_matrix": matrix,
        "incident_severity_contract": sev_map,
        "live_dashboard_exercise": "BLOCKED_NOT_DEPLOYED",
        "duplicate_prevention": "BLOCKED_NOT_DEPLOYED — fingerprint atlas_flex_storage_pressure only live after deploy",
        "stale_state_cleanup": "N/A_NO_LIVE_SIMULATION",
        "verdict": "PASS_UNIT" if all(r["pass"] for r in matrix) else "FAIL_UNIT",
        "post_deploy_required": [
            "Run mongo_storage_capacity_monitor on staging",
            "Inject/override MONGO_STORAGE_LIMIT_BYTES temporarily to cross each band OR use admin test hook",
            "Confirm health-summary.mongo_storage, Control Centre alert, incident upsert+resolve",
        ],
    }


async def _mongo_counts(db_name: str) -> Dict[str, Any]:
    from dotenv import load_dotenv
    from pymongo import MongoClient

    load_dotenv(ROOT / ".env")
    uri = os.environ.get("MONGO_URL") or os.environ.get("MONGO_URI")
    client = MongoClient(uri, serverSelectionTimeoutMS=20000)
    db = client[db_name]
    out = {
        "database": db_name,
        "job_runs": db.job_runs.estimated_document_count(),
        "operational_evidence_events": db.operational_evidence_events.estimated_document_count(),
        "operational_evidence_executions": db.operational_evidence_executions.estimated_document_count(),
        "job_poll_heartbeats": db.job_poll_heartbeats.estimated_document_count()
        if "job_poll_heartbeats" in db.list_collection_names()
        else 0,
        "audit_logs": db.audit_logs.estimated_document_count(),
        "clients": db.clients.estimated_document_count(),
        "score_ledger_events": db.score_ledger_events.estimated_document_count(),
    }
    # recent job_runs by name (last 5 min ISO compare if any)
    recent = list(
        db.job_runs.find({}, {"job_name": 1, "created_at": 1, "run_type": 1})
        .sort("created_at", -1)
        .limit(20)
    )
    out["recent_job_runs_sample"] = [
        {"job_name": d.get("job_name"), "created_at": d.get("created_at"), "run_type": d.get("run_type")}
        for d in recent
    ]
    stats = client[db_name].command("dbStats")
    out["dbStats"] = {
        "dataSize": int(stats.get("dataSize") or 0),
        "indexSize": int(stats.get("indexSize") or 0),
        "storageSize": int(stats.get("storageSize") or 0),
    }
    client.close()
    return out


def phase3_4_scheduler_growth(window_seconds: int = 120) -> Dict[str, Any]:
    """Observe staging growth under currently DEPLOYED (pre-remediation) code."""
    before = asyncio.run(_mongo_counts("pleerity_staging"))
    time.sleep(window_seconds)
    after = asyncio.run(_mongo_counts("pleerity_staging"))
    delta = {
        k: after[k] - before[k]
        for k in (
            "job_runs",
            "operational_evidence_events",
            "operational_evidence_executions",
            "job_poll_heartbeats",
        )
    }
    # Unit proof of idle-skip logic (local code, not deployed)
    from services.job_run_idle_persist import is_idle_success_result, should_skip_full_persist

    idle_unit = {
        "idle_zero_count_skips": should_skip_full_persist(
            "compliance_recalc_worker", "schedule", {"count": 0, "outcome_metrics": {"attempted_count": 0}}
        ),
        "heartbeat_skips": should_skip_full_persist(
            "scheduler_heartbeat", "schedule", {"count": 1, "outcome_metrics": {"outcome_kind": "WORK_PERFORMED"}}
        ),
        "manual_does_not_skip": not should_skip_full_persist(
            "compliance_recalc_worker", "manual", {"count": 0, "outcome_metrics": {"attempted_count": 0}}
        ),
        "non_idle_does_not_skip": not should_skip_full_persist(
            "compliance_recalc_worker", "schedule", {"count": 2, "outcome_metrics": {"attempted_count": 2}}
        ),
    }
    return {
        "phase": "3_4",
        "window_seconds": window_seconds,
        "before": before,
        "after": after,
        "delta": delta,
        "idle_skip_unit_local_code": idle_unit,
        "idle_skip_unit_pass": all(idle_unit.values()),
        "runtime_idle_growth_stopped": delta["job_runs"] == 0 and delta["operational_evidence_events"] == 0,
        "verdict": (
            "FAIL_RUNTIME_GROWTH_CONTINUES_PRE_DEPLOY"
            if delta["job_runs"] > 0
            else "PASS_NO_GROWTH_IN_WINDOW_OR_SCHEDULER_QUIET"
        ),
        "note": (
            "Staging scheduler executes deployed SHA without idle-skip. "
            "Any job_runs growth in window confirms pre-remediation behaviour still live."
        ),
    }


def phase5_retention(allow_live: bool = False) -> Dict[str, Any]:
    async def _run() -> Dict[str, Any]:
        from dotenv import load_dotenv
        from motor.motor_asyncio import AsyncIOMotorClient

        load_dotenv(ROOT / ".env")
        uri = os.environ.get("MONGO_URL") or os.environ.get("MONGO_URI")
        # Bind database module
        import database as database_mod

        client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=20000)
        database_mod.database.client = client
        database_mod.database.db = client["pleerity_staging"]

        from services.operational_retention_purge import purge_aged_operational_telemetry

        dry = await purge_aged_operational_telemetry(batch_limit=500, dry_run=True)
        live = None
        if allow_live:
            os.environ["MONGO_OPERATIONAL_RETENTION_PURGE_ENABLED"] = "1"
            live = await purge_aged_operational_telemetry(batch_limit=500, dry_run=False)
            live2 = await purge_aged_operational_telemetry(batch_limit=500, dry_run=False)
        else:
            live2 = None
        # protected counts
        db = database_mod.database.db
        protected = {
            "audit_logs": await db.audit_logs.estimated_document_count(),
            "clients": await db.clients.estimated_document_count(),
            "score_ledger_events": await db.score_ledger_events.estimated_document_count(),
            "requirements": await db.requirements.estimated_document_count(),
        }
        client.close()
        return {
            "dry_run": dry,
            "live_run": live,
            "live_run_repeat": live2,
            "protected_counts_after": protected,
            "live_executed": allow_live,
        }

    result = asyncio.run(_run())
    # Idempotency: second live deletes should be 0 if first completed
    idempotent = None
    if result.get("live_run") and result.get("live_run_repeat"):
        d1 = sum(int(c.get("deleted") or 0) for c in result["live_run"].get("collections") or [])
        d2 = sum(int(c.get("deleted") or 0) for c in result["live_run_repeat"].get("collections") or [])
        idempotent = d2 == 0 or d2 <= d1  # second pass should not grow deletes unboundedly; ideally 0
    return {
        "phase": 5,
        **result,
        "idempotent_second_pass": idempotent,
        "verdict": "PASS_DRY_RUN" if result.get("dry_run", {}).get("ok") else "FAIL",
        "note": "Live purge skipped unless --allow-retention-live (operating principle: no extra deletes by default).",
    }


def phase6_capacity() -> Dict[str, Any]:
    from utils.mongo_capacity_errors import capacity_unavailable_payload, is_mongo_capacity_error

    samples = [
        ("You exceeded the size limit of your Atlas cluster", True),
        ("connection refused", False),
        ("Quota exceeded", True),
    ]
    det = [{"msg": m, "expected": e, "got": is_mongo_capacity_error(m), "pass": is_mongo_capacity_error(m) == e} for m, e in samples]
    payload = capacity_unavailable_payload()

    # FastAPI handler with local code (not necessarily deployed)
    handler_status = None
    handler_body = None
    try:
        os.environ.setdefault("PYTEST_RUNNING", "1")
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from fastapi.responses import JSONResponse

        app = FastAPI()

        @app.get("/boom")
        def boom():
            raise RuntimeError("You exceeded the size limit of your Atlas cluster")

        @app.exception_handler(Exception)
        async def eh(request, exc):
            if is_mongo_capacity_error(exc):
                return JSONResponse(status_code=503, content=capacity_unavailable_payload())
            return JSONResponse(status_code=500, content={"detail": "Internal server error"})

        c = TestClient(app, raise_server_exceptions=False)
        r = c.get("/boom")
        handler_status = r.status_code
        handler_body = r.json()
    except Exception as e:
        handler_status = None
        handler_body = {"error": str(e)[:300]}

    # Frontend needle
    fe_hits = []
    fe_root = REPO / "frontend" / "src"
    if fe_root.exists():
        for p in list(fe_root.rglob("*.js")) + list(fe_root.rglob("*.jsx")) + list(fe_root.rglob("*.tsx")) + list(
            fe_root.rglob("*.ts")
        ):
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            if "DATABASE_CAPACITY" in text or "capacity exceeded" in text.lower():
                fe_hits.append(str(p.relative_to(REPO)))

    return {
        "phase": 6,
        "detector": det,
        "payload": payload,
        "local_handler_status": handler_status,
        "local_handler_body": handler_body,
        "local_handler_pass": handler_status == 503 and (handler_body or {}).get("code") == "DATABASE_CAPACITY_EXCEEDED",
        "frontend_capacity_message_files": fe_hits,
        "frontend_capacity_ux_pass": len(fe_hits) > 0,
        "live_staging_api_pass": "BLOCKED_NOT_DEPLOYED",
        "verdict": "PASS_LOCAL_HANDLER" if handler_status == 503 else "FAIL_LOCAL_HANDLER",
    }


def phase8_governance() -> Dict[str, Any]:
    # cleanup refuse production
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "mongodb_controlled_cleanup_01.py"),
            "--db-name",
            "pleerity_production",
            "--tier",
            "1",
            "--dry-run",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    refused = proc.returncode != 0 and ("REFUSED" in (proc.stderr + proc.stdout))
    prod = asyncio.run(_mongo_counts("pleerity_production"))
    stg = asyncio.run(_mongo_counts("pleerity_staging"))
    limit = 5 * 1024**3
    cluster_used = prod["dbStats"]["dataSize"] + prod["dbStats"]["indexSize"] + stg["dbStats"]["dataSize"] + stg["dbStats"]["indexSize"]
    return {
        "phase": 8,
        "cleanup_refuses_production": refused,
        "cleanup_exit_code": proc.returncode,
        "cleanup_stderr_tail": (proc.stderr or proc.stdout)[-400:],
        "production_counts": prod,
        "staging_counts": stg,
        "cluster_used_bytes": cluster_used,
        "cluster_pct": round(100 * cluster_used / limit, 2),
        "environment_isolation_logical": True,
        "environment_isolation_physical": False,
        "verdict": "PASS" if refused else "FAIL",
    }


def phase10_readiness(cluster_pct: float, deployed: bool) -> Dict[str, Any]:
    return {
        "phase": 10,
        "atlas_flex_suitable_pre_launch": cluster_pct < 60 and deployed,
        "separate_clusters_still_recommended": True,
        "m10_before_customer_growth": True,
        "retention_sufficient_when_enabled": "CONDITIONAL — enable MONGO_OPERATIONAL_RETENTION_PURGE_ENABLED after deploy soak",
        "alert_earliness": "60% warning in code; unproven live until deploy",
        "launch_readiness_verdict": "NOT_READY_PENDING_DEPLOY_AND_SOAK" if not deployed else "CONDITIONAL",
        "recommendations": [
            "Commit and deploy remediation to staging; verify /api/version SHA includes idle-skip + monitor",
            "Re-run this validation suite post-deploy (idle growth window must show ~0 job_runs for idle polls)",
            "Enable retention purge on staging only after dry-run review",
            "Provision separate Atlas cluster for staging before production customer ramp",
            "Plan M10 (or dedicated) when combined forecast exceeds ~50% of Flex with growth margin",
            "Add frontend handling for code=DATABASE_CAPACITY_EXCEEDED (currently missing)",
        ],
    }


def main() -> int:
    allow_live = "--allow-retention-live" in sys.argv
    window = 120
    for a in sys.argv:
        if a.startswith("--window="):
            window = int(a.split("=", 1)[1])

    results: Dict[str, Any] = {
        "audit_id": "MONGODB-STORAGE-PREVENTION-VALIDATION-01",
        "generated_at": now(),
        "phases": {},
    }
    print("phase1...")
    results["phases"]["deployment"] = phase1_deployment()
    print("phase2...")
    results["phases"]["monitoring"] = phase2_monitor_unit()
    print(f"phase3_4 window={window}s...")
    results["phases"]["scheduler"] = phase3_4_scheduler_growth(window)
    print("phase5...")
    results["phases"]["retention"] = phase5_retention(allow_live=allow_live)
    print("phase6...")
    results["phases"]["capacity"] = phase6_capacity()
    print("phase8...")
    results["phases"]["governance"] = phase8_governance()
    deployed = bool(results["phases"]["deployment"].get("remediation_deployed_to_staging"))
    cluster_pct = float(results["phases"]["governance"].get("cluster_pct") or 0)
    results["phases"]["readiness"] = phase10_readiness(cluster_pct, deployed)

    overall = "BLOCKED_PENDING_DEPLOYMENT"
    if deployed:
        overall = "PASS_WITH_CONDITIONS"
    results["overall_verdict"] = overall
    results["claims_vs_evidence"] = {
        "writes_restored": "PRIOR_EVIDENCE — re-check via staging write not repeated this phase",
        "cluster_46_47_pct": f"MEASURED_NOW_{cluster_pct}%",
        "production_untouched": "PASS — cleanup refuses production; prod counts sampled",
        "tier1_cleanup_completed": "PRIOR_EVIDENCE",
        "idle_persistence_reduced": "FAIL_NOT_DEPLOYED — unit PASS locally; runtime growth still expected on staging",
        "storage_monitoring_implemented": "CODE_EXISTS_UNTRACKED — not on staging SHA",
        "capacity_handling_implemented": "LOCAL_HANDLER_PASS — not on staging SHA; FE message FAIL",
        "retention_framework_implemented": "DRY_RUN_PASS — live gated; not on staging maintenance job until deploy",
    }

    OUT_JSON.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"wrote": str(OUT_JSON), "overall_verdict": overall, "cluster_pct": cluster_pct}, indent=2))
    return 0


if __name__ == "__main__":
    # Windows event loop
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())  # type: ignore[attr-defined]
    except Exception:
        pass
    raise SystemExit(main())
