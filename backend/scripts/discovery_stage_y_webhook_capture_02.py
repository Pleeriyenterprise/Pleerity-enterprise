"""
STAGE-Y-WEBHOOK-REGISTRATION-AND-REAL-EVENT-CAPTURE-02

Capture-first Twin webhook registration + real event capture + finished-event analysis.
No ingest, no extraction implementation, no CRM.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

# Staging secrets file (gitignored via *.env.*) — load before .env
load_dotenv(ROOT / ".env.twin.staging")
load_dotenv(ROOT / ".env")

AUDIT_DIR = ROOT / "docs" / "audit" / "discovery_phase_1_launch_01"
DEFAULT_AGENT_ID = "019edece-894a-7836-aecd-2b6eedbe443f"
BUILD_TEST_RUN_ID = "019edece-8b1d-7f1b-b5e3-dedc720ed840"
SECRETS_FILE = ROOT / ".env.twin.staging"


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def resolve_mongo_env() -> None:
    if not os.environ.get("MONGO_URL") and os.environ.get("MONGO_URI"):
        os.environ["MONGO_URL"] = os.environ["MONGO_URI"]
    if not os.environ.get("DB_NAME"):
        os.environ["DB_NAME"] = "pleerity_staging"


def agent_id() -> str:
    return (os.environ.get("TWIN_DISCOVERY_AGENT_ID") or DEFAULT_AGENT_ID).strip()


def api_key() -> str:
    return (os.environ.get("TWIN_API_KEY") or "").strip()


def cvp_base_url() -> str:
    return (os.environ.get("STAGE_Y_CVP_BASE_URL") or "https://pleerity-enterprise.onrender.com").strip().rstrip("/")


async def check_staging_connector_health() -> Dict[str, Any]:
    """Probe deployed staging CVP twin connector (no secrets)."""
    import httpx

    base = cvp_base_url()
    url = f"{base}/api/internal/discovery/twin/health"
    out: Dict[str, Any] = {"cvp_base_url": base, "health_url": url}
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(url)
        out["http_status"] = resp.status_code
        if resp.status_code == 200:
            out["connector_reachable"] = True
            try:
                out["health_body"] = resp.json()
            except Exception:
                out["health_body"] = resp.text[:500]
        elif resp.status_code == 404:
            out["connector_reachable"] = False
            out["deployment_note"] = (
                "404 — set DISCOVERY_TWIN_WEBHOOK_INGEST_ENABLED=true on staging Render "
                "and redeploy before Twin can POST webhooks"
            )
        else:
            out["connector_reachable"] = False
            out["deployment_note"] = f"Unexpected status {resp.status_code}"
    except Exception as exc:
        out["connector_reachable"] = False
        out["error"] = str(exc)
    return out


def store_signing_secret(secret: str) -> None:
    """Append to gitignored .env.twin.staging — never log secret."""
    lines = [
        "",
        f"# Updated {iso_now()} by discovery_stage_y_webhook_capture_02.py",
        f"TWIN_WEBHOOK_SIGNING_SECRET={secret}",
        "DISCOVERY_TWIN_WEBHOOK_INGEST_ENABLED=true",
        "DISCOVERY_TWIN_EVENT_CAPTURE_ONLY=true",
        f"TWIN_DISCOVERY_AGENT_ID={agent_id()}",
    ]
    existing = SECRETS_FILE.read_text(encoding="utf-8") if SECRETS_FILE.is_file() else ""
    if "TWIN_WEBHOOK_SIGNING_SECRET=" in existing:
        updated: List[str] = []
        for line in existing.splitlines():
            if line.startswith("TWIN_WEBHOOK_SIGNING_SECRET="):
                updated.append(f"TWIN_WEBHOOK_SIGNING_SECRET={secret}")
            else:
                updated.append(line)
        SECRETS_FILE.write_text("\n".join(updated) + "\n", encoding="utf-8")
    else:
        SECRETS_FILE.write_text(existing + "\n".join(lines) + "\n", encoding="utf-8")
    os.environ["TWIN_WEBHOOK_SIGNING_SECRET"] = secret


async def register_webhook(*, force_recreate: bool) -> Dict[str, Any]:
    from services.discovery.twin.twin_api_client import TwinApiClient
    from services.discovery.twin.twin_finished_event_analyzer import mask_signing_secret

    report: Dict[str, Any] = {
        "webhook_registration_status": "BLOCKED",
        "webhook_id": None,
        "registered_events": ["run.completed", "run.failed"],
        "registered_url": None,
        "signing_secret": mask_signing_secret(""),
    }

    key = api_key()
    aid = agent_id()
    base = cvp_base_url()
    target = f"{base}/api/internal/discovery/twin/webhooks"
    report["registered_url"] = target
    if not key:
        report["error"] = "TWIN_API_KEY missing"
        return report
    if not base:
        report["error"] = "STAGE_Y_CVP_BASE_URL missing"
        return report

    client = TwinApiClient(api_key=key)

    existing = await client.list_webhooks(aid)
    report["existing_webhooks"] = [
        {"webhook_id": w.get("webhook_id"), "url": w.get("url"), "events": w.get("events")}
        for w in existing
    ]

    if existing and not force_recreate:
        match = next((w for w in existing if w.get("url") == target), existing[0])
        report["webhook_registration_status"] = "EXISTING"
        report["webhook_id"] = match.get("webhook_id")
        report["signing_secret"] = mask_signing_secret(os.environ.get("TWIN_WEBHOOK_SIGNING_SECRET", ""))
        if not report["signing_secret"]["secret_present"]:
            report["warning"] = "Webhook exists but TWIN_WEBHOOK_SIGNING_SECRET not in env — recreate if lost"
        return report

    if force_recreate:
        for w in existing:
            wid = w.get("webhook_id")
            if wid:
                await client.delete_webhook(aid, wid)

    created = await client.create_webhook(
        aid,
        url=target,
        events=["run.completed", "run.failed"],
    )
    secret = created.get("signing_secret") or ""
    report["webhook_id"] = created.get("webhook_id")
    report["webhook_registration_status"] = "REGISTERED"
    report["signing_secret"] = mask_signing_secret(secret)
    if secret:
        store_signing_secret(secret)
        report["signing_secret_stored"] = True
        report["signing_secret_stored_path"] = str(SECRETS_FILE.name)
    return report


async def test_endpoints(run_id: str) -> Dict[str, Any]:
    from services.discovery.twin.twin_api_client import TwinApiClient
    from services.discovery.twin.twin_finished_event_analyzer import analyze_finished_output

    key = api_key()
    aid = agent_id()
    if not key:
        return {"status": "BLOCKED", "error": "TWIN_API_KEY missing"}

    client = TwinApiClient(api_key=key)
    out: Dict[str, Any] = {"run_id": run_id, "agent_id": aid, "endpoint_test": True}

    try:
        listed = await client.list_runs(aid, page_size=5)
        out["list_runs_ok"] = True
        out["list_runs_count"] = len(listed.get("runs") or [])
    except Exception as exc:
        out["list_runs_ok"] = False
        out["list_runs_error"] = str(exc)

    try:
        run = await client.get_run(aid, run_id)
        out["get_run_ok"] = True
        out["run_status"] = run.get("status")
        out["run_started_at"] = run.get("started_at")
        out["run_finished_at"] = run.get("finished_at")
    except Exception as exc:
        out["get_run_ok"] = False
        out["get_run_error"] = str(exc)

    try:
        events = await client.list_run_events(aid, run_id)
        out["events_ok"] = True
        out["event_count"] = len(events)
        finished = analyze_finished_output(events)
        out["finished_analysis"] = finished
        out["raw_events"] = events
    except Exception as exc:
        out["events_ok"] = False
        out["events_error"] = str(exc)

    return out


async def trigger_deployed_run() -> Dict[str, Any]:
    from services.discovery.twin.twin_api_client import TwinApiClient

    client = TwinApiClient(api_key=api_key())
    run = await client.start_run(
        agent_id(),
        run_mode="run",
        user_message="Stage Y-02 capture run — export prospect batch to finished event",
    )
    return {
        "run_id": run.get("run_id"),
        "agent_id": agent_id(),
        "status": run.get("status"),
        "started_at": run.get("started_at"),
        "run_mode": "run",
    }


async def wait_for_receipt(run_id: str, *, timeout_sec: int = 600) -> Optional[Dict[str, Any]]:
    resolve_mongo_env()
    from motor.motor_asyncio import AsyncIOMotorClient

    deadline = asyncio.get_event_loop().time() + timeout_sec
    client = AsyncIOMotorClient(os.environ["MONGO_URL"], serverSelectionTimeoutMS=10000)
    db = client[os.environ["DB_NAME"]]
    while asyncio.get_event_loop().time() < deadline:
        receipt = await db["discovery_twin_webhook_receipts"].find_one(
            {"twin_run_id": run_id, "twin_agent_id": agent_id()},
            {"_id": 0},
            sort=[("created_at", -1)],
        )
        if receipt:
            client.close()
            return receipt
        await asyncio.sleep(5)
    client.close()
    return None


async def pull_via_connector(run_id: str) -> Dict[str, Any]:
    from services.discovery.twin.twin_ingestion_connector import TwinIngestionConnector

    os.environ.setdefault("DISCOVERY_TWIN_WEBHOOK_INGEST_ENABLED", "true")
    os.environ.setdefault("DISCOVERY_TWIN_EVENT_CAPTURE_ONLY", "true")
    os.environ.setdefault("TWIN_DISCOVERY_AGENT_ID", agent_id())
    return await TwinIngestionConnector.pull_run_events(
        twin_agent_id=agent_id(),
        twin_run_id=run_id,
    )


async def find_latest_successful_run() -> Optional[str]:
    from services.discovery.twin.twin_api_client import TwinApiClient

    client = TwinApiClient(api_key=api_key())
    listed = await client.list_runs(agent_id(), page_size=20, filter_status="finished")
    for run in listed.get("runs") or []:
        if run.get("status") in ("finished", "completed"):
            return run.get("run_id")
    listed = await client.list_runs(agent_id(), page_size=20)
    for run in listed.get("runs") or []:
        if run.get("status") in ("finished", "completed"):
            return run.get("run_id")
    return None


async def run_capture_02(
    *,
    register: bool,
    force_recreate_webhook: bool,
    trigger_run: bool,
    test_build_run: bool,
    run_id: Optional[str],
    wait_webhook: bool,
) -> Dict[str, Any]:
    from services.discovery import discovery_config
    from services.discovery.twin.twin_finished_event_analyzer import analyze_finished_output

    result: Dict[str, Any] = {
        "authority": "STAGE-Y-WEBHOOK-REGISTRATION-AND-REAL-EVENT-CAPTURE-02",
        "generated_at": iso_now(),
        "agent_id": agent_id(),
        "capture_only_enforced": discovery_config.is_discovery_twin_event_capture_only(),
        "blockers": [],
        "success_criteria_met": False,
        "overall_status": "RED",
        "finished_event_located": False,
        "record_count": 0,
        "extraction_readiness": "RED",
    }

    result["staging_connector_health"] = await check_staging_connector_health()
    if not result["staging_connector_health"].get("connector_reachable"):
        note = result["staging_connector_health"].get("deployment_note") or result["staging_connector_health"].get(
            "error", "staging connector not reachable"
        )
        result["blockers"].append(note)

    if register:
        result["webhook_registration"] = await register_webhook(force_recreate=force_recreate_webhook)
        if result["webhook_registration"].get("webhook_registration_status") not in (
            "REGISTERED",
            "EXISTING",
        ):
            result["blockers"].append(result["webhook_registration"].get("error", "webhook registration failed"))

    if test_build_run and not run_id:
        result["build_run_endpoint_test"] = await test_endpoints(BUILD_TEST_RUN_ID)
        if result["build_run_endpoint_test"].get("events_ok"):
            result["build_run_note"] = "Stopped build run — endpoint test only, not used for export discovery"

    if trigger_run:
        result["triggered_run"] = await trigger_deployed_run()
        run_id = result["triggered_run"].get("run_id")

    if not run_id and api_key():
        run_id = await find_latest_successful_run()
        if run_id:
            result["selected_run_source"] = "latest_successful_from_twin_api"
        elif not test_build_run:
            result["blockers"].append("No deployed successful run_id available")

    result["deployed_run_id"] = run_id

    if run_id and api_key():
        if wait_webhook:
            result["webhook_receipt_wait"] = await wait_for_receipt(run_id)
        else:
            resolve_mongo_env()
            from motor.motor_asyncio import AsyncIOMotorClient

            client = AsyncIOMotorClient(os.environ["MONGO_URL"], serverSelectionTimeoutMS=10000)
            db = client[os.environ["DB_NAME"]]
            result["webhook_receipt"] = await db["discovery_twin_webhook_receipts"].find_one(
                {"twin_run_id": run_id},
                {"_id": 0},
                sort=[("created_at", -1)],
            )
            client.close()

        if not result.get("webhook_receipt") and not result.get("webhook_receipt_wait"):
            if discovery_config.is_discovery_twin_webhook_ingest_enabled() or os.environ.get(
                "DISCOVERY_TWIN_WEBHOOK_INGEST_ENABLED", ""
            ).lower() in ("1", "true", "yes"):
                try:
                    result["connector_pull"] = await pull_via_connector(run_id)
                except Exception as exc:
                    result["connector_pull_error"] = str(exc)
            else:
                result["blockers"].append(
                    "No webhook receipt — enable connector and pull via reconcile, or wait for webhook"
                )

        # Fetch events for analysis
        endpoint_data = await test_endpoints(run_id)
        result["event_retrieval"] = {
            "event_count": endpoint_data.get("event_count"),
            "events_ok": endpoint_data.get("events_ok"),
            "run_status": endpoint_data.get("run_status"),
        }
        finished = endpoint_data.get("finished_analysis") or {}
        if endpoint_data.get("raw_events"):
            finished = analyze_finished_output(endpoint_data["raw_events"])

        result["finished_event_located"] = finished.get("finished_event_located", False)
        result["final_output_json_path"] = finished.get("final_output_json_path")
        result["record_count"] = finished.get("record_count", 0)
        result["sample_record_shape"] = finished.get("sample_record_shape")
        result["extraction_readiness"] = finished.get("extraction_readiness", "RED")
        result["finished_analysis"] = finished
        result["raw_events_for_audit"] = endpoint_data.get("raw_events")

        resolve_mongo_env()
        from motor.motor_asyncio import AsyncIOMotorClient

        client = AsyncIOMotorClient(os.environ["MONGO_URL"], serverSelectionTimeoutMS=10000)
        db = client[os.environ["DB_NAME"]]
        capture = await db["discovery_twin_run_event_captures"].find_one(
            {"twin_run_id": run_id},
            {"_id": 0},
            sort=[("captured_at", -1)],
        )
        client.close()
        result["event_capture_status"] = capture.get("capture_id") if capture else None
        result["webhook_receipt_status"] = (
            (result.get("webhook_receipt") or result.get("webhook_receipt_wait") or {}).get("status")
        )

        if capture:
            result["mongo_capture_id"] = capture.get("capture_id")
            result["mongo_capture_events"] = capture.get("events")

    elif not api_key():
        if not any("TWIN_API_KEY" in b for b in result["blockers"]):
            result["blockers"].append("TWIN_API_KEY not configured — add to .env.twin.staging (gitignored)")

    readiness = result.get("extraction_readiness", "RED")
    has_webhook = result.get("webhook_registration", {}).get("webhook_registration_status") in (
        "REGISTERED",
        "EXISTING",
    )
    secret_ok = result.get("webhook_registration", {}).get("signing_secret", {}).get("secret_present")
    finished_ok = result.get("finished_event_located")
    records_ok = result.get("record_count", 0) > 0

    result["success_criteria_met"] = bool(
        has_webhook
        and secret_ok
        and run_id
        and finished_ok
        and records_ok
        and readiness == "GREEN"
    )
    if result["success_criteria_met"]:
        result["overall_status"] = "GREEN"
    elif finished_ok and readiness in ("GREEN", "AMBER"):
        result["overall_status"] = readiness
    elif api_key() and result.get("event_retrieval", {}).get("events_ok"):
        result["overall_status"] = "AMBER"
    elif not api_key():
        result["overall_status"] = "BLOCKED"
    else:
        result["overall_status"] = "RED"

    # Write audit artifacts after overall_status is final (masked — no secrets)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    finished = result.get("finished_analysis") or {}
    payload_path = AUDIT_DIR / "TWIN_REAL_EVENT_PAYLOAD_ANALYSIS.json"
    payload_out: Dict[str, Any] = {
        "authority": result.get("authority"),
        "generated_at": result.get("generated_at"),
        "overall_status": result.get("overall_status"),
        "blockers": result.get("blockers", []),
        "webhook_registration": result.get("webhook_registration"),
        "deployed_run_id": result.get("deployed_run_id"),
        "agent_id": result.get("agent_id"),
        "finished_analysis": finished,
        "extraction_readiness": result.get("extraction_readiness", "RED"),
        "event_retrieval": result.get("event_retrieval"),
        "webhook_receipt_status": result.get("webhook_receipt_status"),
        "event_capture_status": result.get("event_capture_status"),
    }
    if finished.get("sample_record_shape"):
        payload_out["sample_record_shape"] = finished["sample_record_shape"]
    if result.get("mongo_capture_id"):
        payload_out["mongo_capture_id"] = result["mongo_capture_id"]
    raw_events = result.get("mongo_capture_events") or result.get("raw_events_for_audit") or (
        (result.get("build_run_endpoint_test") or {}).get("raw_events")
    )
    if raw_events:
        payload_out["raw_events"] = raw_events
    payload_path.write_text(json.dumps(payload_out, indent=2, default=str), encoding="utf-8")
    result["json_path"] = str(payload_path)
    write_markdown(result, finished)

    return result


def write_markdown(result: Dict[str, Any], finished: Dict[str, Any]) -> None:
    md = AUDIT_DIR / "STAGE_Y_REAL_CAPTURE_REPORT.md"
    wh = result.get("webhook_registration") or {}
    sec = wh.get("signing_secret") or {}
    lines = [
        "# Stage Y — Real Twin Capture Run Report",
        "",
        f"**Authority:** {result.get('authority')}",
        f"**Generated:** {result.get('generated_at')}",
        f"**Overall:** {result.get('overall_status')}",
        f"**Success criteria met:** {result.get('success_criteria_met')}",
        "",
        "## Required fields",
        "",
        f"1. Webhook registration status: **{wh.get('webhook_registration_status', 'N/A')}**",
        f"2. webhook_id: `{wh.get('webhook_id')}`",
        f"3. signing_secret stored: secret_present={sec.get('secret_present')} "
        f"length={sec.get('secret_length')} masked={sec.get('secret_prefix_last4')}",
        f"4. deployed run_id: `{result.get('deployed_run_id')}`",
        f"5. run status: `{result.get('event_retrieval', {}).get('run_status')}`",
        f"6. webhook receipt status: `{result.get('webhook_receipt_status')}`",
        f"7. event capture status: `{result.get('event_capture_status')}`",
        f"8. finished event located: **{result.get('finished_event_located')}**",
        f"9. final output JSON path: `{result.get('final_output_json_path')}`",
        f"10. record count: **{result.get('record_count')}**",
        f"11. sample record shape: see JSON analysis file",
        f"12. extraction readiness: **{result.get('extraction_readiness')}**",
        "",
    ]
    staging = result.get("staging_connector_health") or {}
    if staging:
        lines.extend(
            [
                "## Staging connector",
                "",
                f"- CVP base: `{staging.get('cvp_base_url')}`",
                f"- Health HTTP status: `{staging.get('http_status')}`",
                f"- Connector reachable: **{staging.get('connector_reachable')}**",
            ]
        )
        if staging.get("deployment_note"):
            lines.append(f"- Note: {staging['deployment_note']}")
        lines.append("")
    if result.get("blockers"):
        lines.append("## Blockers")
        for b in result["blockers"]:
            lines.append(f"- {b}")
        lines.append("")
    if finished.get("output_paths"):
        lines.append("## Export candidate paths")
        for p in finished["output_paths"]:
            lines.append(f"- `{p.get('json_path')}` count={p.get('record_count')}")
        lines.append("")
    lines.extend(
        [
            "## Ops rerun (STAGE-Y-02)",
            "",
            "Create `backend/.env.twin.staging` from "
            "`docs/audit/discovery_phase_1_launch_01/twin_workspace/env.twin.staging.example` (gitignored):",
            "",
            "```bash",
            "DISCOVERY_TWIN_WEBHOOK_INGEST_ENABLED=true",
            "DISCOVERY_TWIN_EVENT_CAPTURE_ONLY=true",
            "TWIN_API_KEY=<Twin dashboard>",
            "TWIN_DISCOVERY_AGENT_ID=019edece-894a-7836-aecd-2b6eedbe443f",
            "STAGE_Y_CVP_BASE_URL=https://pleerity-enterprise.onrender.com",
            "```",
            "",
            "Register webhook + trigger deployed run + wait for receipt:",
            "",
            "```bash",
            "cd backend",
            "python scripts/discovery_stage_y_webhook_capture_02.py \\",
            "  --register-webhook --trigger-run --wait-webhook",
            "```",
            "",
            "Or after manual Twin run:",
            "",
            "```bash",
            "python scripts/discovery_stage_y_webhook_capture_02.py \\",
            "  --register-webhook --run-id <deployed_run_id> --wait-webhook",
            "```",
            "",
            "Endpoint test only (stopped build run):",
            "",
            "```bash",
            "python scripts/discovery_stage_y_webhook_capture_02.py --test-build-run",
            "```",
            "",
        ]
    )
    md.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage Y-02 webhook + real event capture")
    parser.add_argument("--register-webhook", action="store_true")
    parser.add_argument("--force-recreate-webhook", action="store_true")
    parser.add_argument("--trigger-run", action="store_true")
    parser.add_argument("--test-build-run", action="store_true")
    parser.add_argument("--run-id", default=os.environ.get("STAGE_Y_CAPTURE_RUN_ID"))
    parser.add_argument("--wait-webhook", action="store_true")
    args = parser.parse_args()

    os.environ.setdefault("TWIN_DISCOVERY_AGENT_ID", DEFAULT_AGENT_ID)
    os.environ.setdefault("DISCOVERY_TWIN_EVENT_CAPTURE_ONLY", "true")

    result = asyncio.run(
        run_capture_02(
            register=args.register_webhook or os.environ.get("STAGE_Y_REGISTER_WEBHOOK") == "1",
            force_recreate_webhook=args.force_recreate_webhook,
            trigger_run=args.trigger_run or os.environ.get("STAGE_Y_TRIGGER_TWIN_RUN") == "1",
            test_build_run=args.test_build_run,
            run_id=args.run_id,
            wait_webhook=args.wait_webhook,
        )
    )
    print(json.dumps({k: v for k, v in result.items() if k != "finished_analysis"}, indent=2, default=str))
    return 0 if result.get("success_criteria_met") else 1


if __name__ == "__main__":
    raise SystemExit(main())
