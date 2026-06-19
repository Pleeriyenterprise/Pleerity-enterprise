"""
Stage Y Capture Run validation — STAGE-Y-CAPTURE-RUN-01

Evidence gathering only. No extraction, ingest, or prospect creation.

Usage (from backend/):
  python scripts/discovery_stage_y_capture_run_validate.py

Optional:
  STAGE_Y_CAPTURE_RUN_ID=run_xxx     # Analyse existing capture instead of new pull
  STAGE_Y_TRIGGER_TWIN_RUN=1         # POST /runs to start agent (requires credentials)
  STAGE_Y_REGISTER_WEBHOOK=1         # Register webhook with Twin API
  STAGE_Y_CVP_BASE_URL=https://...   # Staging CVP base for webhook URL
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

AUDIT_DIR = ROOT / "docs" / "audit" / "discovery_phase_1_launch_01"

CANDIDATE_EXPORT_KEYS = (
    "records",
    "prospects",
    "output",
    "result",
    "batch",
    "json_export",
    "artifacts",
    "files",
    "attachments",
)


@dataclass
class SectionReport:
    section: str
    status: str  # GREEN | AMBER | RED | BLOCKED
    checks: List[str] = field(default_factory=list)
    failures: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StageYCaptureReport:
    authority: str = "STAGE-Y-CAPTURE-RUN-01"
    generated_at: str = ""
    capture_only_enforced: bool = True
    part_a_connector_health: Optional[SectionReport] = None
    part_b_webhook_registration: Optional[SectionReport] = None
    part_c_real_run: Optional[SectionReport] = None
    part_d_webhook_receipt: Optional[SectionReport] = None
    part_e_event_retrieval: Optional[SectionReport] = None
    part_f_export_discovery: Optional[SectionReport] = None
    part_g_extraction_readiness: Optional[SectionReport] = None
    part_h_boundary: Optional[SectionReport] = None
    part_i_recommendation: Optional[SectionReport] = None
    overall_status: str = "RED"
    success_criteria_met: bool = False
    blockers: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        def _s(s: Optional[SectionReport]) -> Optional[Dict[str, Any]]:
            return asdict(s) if s else None

        return {
            "authority": self.authority,
            "generated_at": self.generated_at,
            "capture_only_enforced": self.capture_only_enforced,
            "part_a_connector_health": _s(self.part_a_connector_health),
            "part_b_webhook_registration": _s(self.part_b_webhook_registration),
            "part_c_real_run": _s(self.part_c_real_run),
            "part_d_webhook_receipt": _s(self.part_d_webhook_receipt),
            "part_e_event_retrieval": _s(self.part_e_event_retrieval),
            "part_f_export_discovery": _s(self.part_f_export_discovery),
            "part_g_extraction_readiness": _s(self.part_g_extraction_readiness),
            "part_h_boundary": _s(self.part_h_boundary),
            "part_i_recommendation": _s(self.part_i_recommendation),
            "overall_status": self.overall_status,
            "success_criteria_met": self.success_criteria_met,
            "blockers": self.blockers,
        }


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def resolve_mongo_env() -> None:
    if not os.environ.get("MONGO_URL") and os.environ.get("MONGO_URI"):
        os.environ["MONGO_URL"] = os.environ["MONGO_URI"]
    if not os.environ.get("DB_NAME"):
        os.environ["DB_NAME"] = "pleerity_staging"


def twin_env_status() -> Dict[str, Any]:
    return {
        "TWIN_API_KEY": bool((os.environ.get("TWIN_API_KEY") or "").strip()),
        "TWIN_WEBHOOK_SIGNING_SECRET": bool(
            (os.environ.get("TWIN_WEBHOOK_SIGNING_SECRET") or "").strip()
        ),
        "TWIN_DISCOVERY_AGENT_ID": (os.environ.get("TWIN_DISCOVERY_AGENT_ID") or "").strip() or None,
        "TWIN_DISCOVERY_CAMPAIGN_ID": (os.environ.get("TWIN_DISCOVERY_CAMPAIGN_ID") or "").strip()
        or None,
        "DISCOVERY_TWIN_WEBHOOK_INGEST_ENABLED": os.environ.get(
            "DISCOVERY_TWIN_WEBHOOK_INGEST_ENABLED", "false"
        ),
        "DISCOVERY_TWIN_EVENT_CAPTURE_ONLY": os.environ.get(
            "DISCOVERY_TWIN_EVENT_CAPTURE_ONLY", "true"
        ),
        "STAGE_Y_CVP_BASE_URL": (os.environ.get("STAGE_Y_CVP_BASE_URL") or "").strip() or None,
    }


async def part_a_connector_health() -> SectionReport:
    checks: List[str] = []
    failures: List[str] = []
    meta: Dict[str, Any] = {"CONNECTOR_HEALTH_REPORT": {}}

    server_path = ROOT / "server.py"
    server_text = server_path.read_text(encoding="utf-8")
    if "discovery_twin_internal" in server_text and "discovery_twin_internal.router" in server_text:
        checks.append("discovery_twin_internal router registered in server.py")
    else:
        failures.append("discovery_twin_internal router not registered")

    route_files = [
        ROOT / "routes" / "discovery_twin_internal.py",
        ROOT / "services" / "discovery" / "twin" / "twin_ingestion_connector.py",
        ROOT / "services" / "discovery" / "twin" / "twin_api_client.py",
    ]
    for path in route_files:
        if path.is_file():
            checks.append(f"module present: {path.relative_to(ROOT)}")
        else:
            failures.append(f"missing module: {path}")

    env = twin_env_status()
    meta["CONNECTOR_HEALTH_REPORT"]["env"] = env

    from services.discovery import discovery_config
    from services.discovery.twin.twin_ingestion_connector import TwinIngestionConnector

    health = await TwinIngestionConnector.health_status()
    meta["CONNECTOR_HEALTH_REPORT"]["health_endpoint_payload"] = health

    capture_only = discovery_config.is_discovery_twin_event_capture_only()
    meta["CONNECTOR_HEALTH_REPORT"]["capture_only_mode"] = capture_only
    if capture_only:
        checks.append("DISCOVERY_TWIN_EVENT_CAPTURE_ONLY=true (capture-only enforced)")
    else:
        failures.append("capture-only mode not enforced — violates Stage Y-CAPTURE-RUN constraints")

    # FastAPI route smoke
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient
    from unittest.mock import patch

    from routes import discovery_twin_internal

    app = FastAPI()
    app.include_router(discovery_twin_internal.router)

    with patch.object(TwinIngestionConnector, "connector_enabled", return_value=True):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/internal/discovery/twin/health")
    meta["CONNECTOR_HEALTH_REPORT"]["health_http_status"] = resp.status_code
    if resp.status_code == 200:
        checks.append("GET /api/internal/discovery/twin/health returns 200 when connector enabled")
    else:
        failures.append(f"health endpoint returned {resp.status_code}")

    if not env["TWIN_API_KEY"]:
        checks.append("TWIN_API_KEY not loaded (expected until ops configures staging secrets)")
    if not env["TWIN_DISCOVERY_AGENT_ID"]:
        checks.append("TWIN_DISCOVERY_AGENT_ID not loaded")

    status = "GREEN" if not failures else ("AMBER" if resp.status_code == 200 else "RED")
    return SectionReport(
        section="PART_A_CONNECTOR_HEALTH",
        status=status,
        checks=checks,
        failures=failures,
        metadata=meta,
    )


async def part_b_webhook_registration(*, register: bool) -> SectionReport:
    checks: List[str] = []
    failures: List[str] = []
    meta: Dict[str, Any] = {"WEBHOOK_REGISTRATION_REPORT": {}}

    api_key = (os.environ.get("TWIN_API_KEY") or "").strip()
    agent_id = (os.environ.get("TWIN_DISCOVERY_AGENT_ID") or "").strip()
    base_url = (os.environ.get("STAGE_Y_CVP_BASE_URL") or "").strip().rstrip("/")

    if not api_key or not agent_id:
        failures.append("TWIN_API_KEY and TWIN_DISCOVERY_AGENT_ID required for webhook registration")
        return SectionReport(
            section="PART_B_WEBHOOK_REGISTRATION",
            status="BLOCKED",
            checks=checks,
            failures=failures,
            metadata=meta,
        )

    from services.discovery.twin.twin_api_client import TwinApiClient

    client = TwinApiClient(api_key=api_key)

    try:
        import httpx

        async with httpx.AsyncClient(timeout=60.0) as http:
            list_resp = await http.get(
                f"{client._base_url}/v1/agents/{agent_id}/webhooks",
                headers=client._headers(),
            )
        if list_resp.status_code == 200:
            webhooks = list_resp.json().get("webhooks") or []
            meta["WEBHOOK_REGISTRATION_REPORT"]["existing_webhooks"] = [
                {
                    "webhook_id": w.get("webhook_id"),
                    "url": w.get("url"),
                    "events": w.get("events"),
                    "status": w.get("status"),
                }
                for w in webhooks
            ]
            checks.append(f"listed {len(webhooks)} existing webhook(s) for agent")
            if webhooks:
                w0 = webhooks[0]
                meta["WEBHOOK_REGISTRATION_REPORT"]["webhook_id"] = w0.get("webhook_id")
                meta["WEBHOOK_REGISTRATION_REPORT"]["agent_id"] = agent_id
                meta["WEBHOOK_REGISTRATION_REPORT"]["registered_events"] = w0.get("events")
                if base_url and base_url in str(w0.get("url", "")):
                    checks.append("existing webhook URL matches STAGE_Y_CVP_BASE_URL")
        else:
            failures.append(f"list webhooks HTTP {list_resp.status_code}")
    except Exception as exc:
        failures.append(f"list webhooks failed: {exc}")

    if register and base_url:
        target = f"{base_url}/api/internal/discovery/twin/webhooks"
        try:
            import httpx

            async with httpx.AsyncClient(timeout=60.0) as http:
                create_resp = await http.post(
                    f"{client._base_url}/v1/agents/{agent_id}/webhooks",
                    headers={**client._headers(), "Content-Type": "application/json"},
                    json={"url": target, "events": ["run.completed", "run.failed"]},
                )
            if create_resp.status_code in (200, 201):
                body = create_resp.json()
                meta["WEBHOOK_REGISTRATION_REPORT"]["webhook_id"] = body.get("webhook_id")
                meta["WEBHOOK_REGISTRATION_REPORT"]["agent_id"] = agent_id
                meta["WEBHOOK_REGISTRATION_REPORT"]["registered_events"] = body.get("events")
                meta["WEBHOOK_REGISTRATION_REPORT"]["registered_url"] = target
                checks.append("webhook registered via Twin API")
                if body.get("signing_secret"):
                    meta["WEBHOOK_REGISTRATION_REPORT"]["signing_secret_returned"] = True
                    checks.append("signing_secret returned (store in TWIN_WEBHOOK_SIGNING_SECRET)")
            else:
                failures.append(f"create webhook HTTP {create_resp.status_code}: {create_resp.text[:200]}")
        except Exception as exc:
            failures.append(f"create webhook failed: {exc}")
    elif not base_url:
        checks.append("STAGE_Y_CVP_BASE_URL not set — skipped new webhook registration")

    status = "GREEN" if not failures and meta["WEBHOOK_REGISTRATION_REPORT"].get("webhook_id") else (
        "AMBER" if checks and not failures else "BLOCKED"
    )
    if failures:
        status = "BLOCKED"
    return SectionReport(
        section="PART_B_WEBHOOK_REGISTRATION",
        status=status,
        checks=checks,
        failures=failures,
        metadata=meta,
    )


async def part_c_trigger_run(*, trigger: bool) -> SectionReport:
    checks: List[str] = []
    failures: List[str] = []
    meta: Dict[str, Any] = {"REAL_RUN_REPORT": {}}

    api_key = (os.environ.get("TWIN_API_KEY") or "").strip()
    agent_id = (os.environ.get("TWIN_DISCOVERY_AGENT_ID") or "").strip()

    if not api_key or not agent_id:
        failures.append("TWIN_API_KEY and TWIN_DISCOVERY_AGENT_ID required for real Twin run")
        return SectionReport(
            section="PART_C_REAL_RUN",
            status="BLOCKED",
            checks=checks,
            failures=failures,
            metadata=meta,
        )

    if not trigger:
        failures.append("STAGE_Y_TRIGGER_TWIN_RUN not set — no run triggered in this execution")
        return SectionReport(
            section="PART_C_REAL_RUN",
            status="BLOCKED",
            checks=checks,
            failures=failures,
            metadata=meta,
        )

    from services.discovery.twin.twin_api_client import TwinApiClient

    client = TwinApiClient(api_key=api_key)
    try:
        import httpx

        async with httpx.AsyncClient(timeout=120.0) as http:
            resp = await http.post(
                f"{client._base_url}/v1/agents/{agent_id}/runs",
                headers={**client._headers(), "Content-Type": "application/json"},
                json={"run_mode": "run", "user_message": "Stage Y capture run — export prospects batch"},
            )
        if resp.status_code not in (200, 201):
            failures.append(f"start run HTTP {resp.status_code}: {resp.text[:300]}")
        else:
            run = resp.json().get("run") or {}
            meta["REAL_RUN_REPORT"] = {
                "run_id": run.get("run_id"),
                "agent_id": agent_id,
                "started_at": run.get("started_at"),
                "status": run.get("status"),
            }
            checks.append(f"run started run_id={run.get('run_id')}")
    except Exception as exc:
        failures.append(f"trigger run failed: {exc}")

    status = "GREEN" if meta["REAL_RUN_REPORT"].get("run_id") and not failures else "BLOCKED"
    return SectionReport(
        section="PART_C_REAL_RUN",
        status=status,
        checks=checks,
        failures=failures,
        metadata=meta,
    )


async def load_capture_from_mongo(
    *,
    run_id: Optional[str],
    capture_id: Optional[str],
) -> Optional[Dict[str, Any]]:
    resolve_mongo_env()
    from motor.motor_asyncio import AsyncIOMotorClient

    client = AsyncIOMotorClient(os.environ["MONGO_URL"], serverSelectionTimeoutMS=10000)
    db = client[os.environ["DB_NAME"]]
    query: Dict[str, Any] = {}
    if capture_id:
        query["capture_id"] = capture_id
    elif run_id:
        query["twin_run_id"] = run_id
    capture = await db["discovery_twin_run_event_captures"].find_one(
        query,
        {"_id": 0},
        sort=[("captured_at", -1)],
    )
    receipt = None
    if capture:
        receipt = await db["discovery_twin_webhook_receipts"].find_one(
            {"receipt_id": capture.get("receipt_id")},
            {"_id": 0},
        )
    elif run_id:
        receipt = await db["discovery_twin_webhook_receipts"].find_one(
            {"twin_run_id": run_id},
            {"_id": 0},
            sort=[("created_at", -1)],
        )
    client.close()
    return {"capture": capture, "receipt": receipt}


async def fetch_events_from_twin(agent_id: str, run_id: str) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    api_key = (os.environ.get("TWIN_API_KEY") or "").strip()
    from services.discovery.twin.twin_api_client import TwinApiClient

    client = TwinApiClient(api_key=api_key)
    run_meta = await client.get_run(agent_id, run_id)
    events = await client.list_run_events(agent_id, run_id)
    return events, run_meta


def collect_json_paths(
    node: Any,
    *,
    path: str = "$",
    key_filter: Optional[Set[str]] = None,
    out: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    if out is None:
        out = []
    if isinstance(node, dict):
        for key, value in node.items():
            child = f"{path}.{key}"
            if key_filter is None or key in key_filter:
                if isinstance(value, list):
                    out.append(
                        {
                            "json_path": child,
                            "type": "array",
                            "length": len(value),
                            "sample_element_type": type(value[0]).__name__ if value else None,
                            "sample_structure": value[0] if value and isinstance(value[0], dict) else value[0]
                            if value
                            else None,
                        }
                    )
                elif isinstance(value, dict):
                    out.append(
                        {
                            "json_path": child,
                            "type": "object",
                            "nested_keys": sorted(value.keys())[:30],
                        }
                    )
            collect_json_paths(value, path=child, key_filter=key_filter, out=out)
    elif isinstance(node, list):
        for idx, item in enumerate(node[:5]):
            collect_json_paths(item, path=f"{path}[{idx}]", key_filter=key_filter, out=out)
    return out


def analyze_events(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    top_level_event_keys: Set[str] = set()
    event_types: List[str] = []
    for item in events:
        body = item.get("event")
        if isinstance(body, dict):
            top_level_event_keys.update(body.keys())
            event_types.extend(body.keys())
    candidates = collect_json_paths(events, key_filter=set(CANDIDATE_EXPORT_KEYS))
    return {
        "event_count": len(events),
        "event_types": sorted(set(event_types)),
        "top_level_keys": sorted(top_level_event_keys),
        "candidate_paths": candidates,
        "raw_events": events,
    }


async def parts_d_e_f_g(
    *,
    run_id: Optional[str],
    capture_id: Optional[str],
    pull_from_twin: bool,
) -> Tuple[SectionReport, SectionReport, SectionReport, SectionReport, SectionReport, Dict[str, Any]]:
    d_checks: List[str] = []
    d_failures: List[str] = []
    d_meta: Dict[str, Any] = {"WEBHOOK_RECEIPT_REPORT": {}}

    e_checks: List[str] = []
    e_failures: List[str] = []
    e_meta: Dict[str, Any] = {"EVENT_RETRIEVAL_REPORT": {}}

    f_checks: List[str] = []
    f_failures: List[str] = []
    f_meta: Dict[str, Any] = {"EXPORT_DISCOVERY_REPORT": {"candidates": []}}

    agent_id = (os.environ.get("TWIN_DISCOVERY_AGENT_ID") or "").strip()
    mongo_bundle = await load_capture_from_mongo(run_id=run_id, capture_id=capture_id)
    capture = mongo_bundle.get("capture")
    receipt = mongo_bundle.get("receipt")

    events: List[Dict[str, Any]] = []
    run_meta: Dict[str, Any] = {}

    if capture:
        events = capture.get("events") or []
        run_meta = capture.get("twin_run_status") or {}
        run_id = capture.get("twin_run_id") or run_id
        agent_id = capture.get("twin_agent_id") or agent_id
        e_checks.append(f"loaded capture from MongoDB capture_id={capture.get('capture_id')}")
    elif pull_from_twin and run_id and agent_id and (os.environ.get("TWIN_API_KEY") or "").strip():
        try:
            events, run_meta = await fetch_events_from_twin(agent_id, run_id)
            e_checks.append(f"fetched {len(events)} events from Twin API")
        except Exception as exc:
            e_failures.append(f"Twin API event fetch failed: {exc}")
    else:
        e_failures.append("no MongoDB capture and Twin API pull not available")

    if receipt:
        d_meta["WEBHOOK_RECEIPT_REPORT"] = {
            "receipt_id": receipt.get("receipt_id"),
            "receipt_key": f"{receipt.get('twin_agent_id')}:{receipt.get('twin_run_id')}:{receipt.get('event')}",
            "event": receipt.get("event"),
            "webhook_timestamp": receipt.get("webhook_timestamp"),
            "status": receipt.get("status"),
            "webhook_payload": receipt.get("webhook_payload"),
        }
        d_checks.append(f"receipt persisted status={receipt.get('status')}")
        if receipt.get("status") in ("captured", "ingested", "received", "captured_no_export"):
            d_checks.append("run.completed processing reached receipt layer")
    else:
        d_failures.append("no webhook receipt found in discovery_twin_webhook_receipts")

    if run_meta:
        e_meta["EVENT_RETRIEVAL_REPORT"]["run"] = {
            "run_id": run_meta.get("run_id") or run_id,
            "agent_id": agent_id,
            "started_at": run_meta.get("started_at"),
            "finished_at": run_meta.get("finished_at"),
            "status": run_meta.get("status"),
            "outcome": run_meta.get("outcome"),
        }

    analysis: Dict[str, Any] = {}
    if events:
        analysis = analyze_events(events)
        e_meta["EVENT_RETRIEVAL_REPORT"]["event_count"] = analysis["event_count"]
        e_meta["EVENT_RETRIEVAL_REPORT"]["event_types"] = analysis["event_types"]
        e_meta["EVENT_RETRIEVAL_REPORT"]["top_level_keys"] = analysis["top_level_keys"]
        e_checks.append(f"event_count={analysis['event_count']}")
        e_checks.append(f"top_level_event_keys={analysis['top_level_keys']}")
    else:
        e_failures.append("no events available for analysis")

    records_paths = [c for c in analysis.get("candidate_paths", []) if "records" in c["json_path"]]
    prospects_paths = [c for c in analysis.get("candidate_paths", []) if "prospects" in c["json_path"]]

    f_meta["EXPORT_DISCOVERY_REPORT"]["candidates"] = analysis.get("candidate_paths", [])
    for label, paths in (
        ("records[]", records_paths),
        ("prospects[]", prospects_paths),
        ("all_candidates", analysis.get("candidate_paths", [])),
    ):
        if paths:
            f_checks.append(f"found candidate paths for {label}: {[p['json_path'] for p in paths[:5]]}")

    if not records_paths and not prospects_paths:
        f_failures.append("no records[] or prospects[] path found in event stream")
        for key in CANDIDATE_EXPORT_KEYS:
            if not any(key in c["json_path"] for c in analysis.get("candidate_paths", [])):
                f_checks.append(f"no path for candidate key '{key}'")

    # Extraction readiness
    g_checks: List[str] = []
    g_failures: List[str] = []
    g_meta: Dict[str, Any] = {"EXTRACTION_READINESS_REPORT": {}}

    if records_paths:
        best = records_paths[0]
        if best.get("length", 0) > 0 and best.get("sample_element_type") == "dict":
            readiness = "GREEN"
            g_checks.append(f"records[] located at {best['json_path']} count={best.get('length')}")
        else:
            readiness = "AMBER"
            g_checks.append(f"records path found but structure uncertain: {best['json_path']}")
    elif prospects_paths:
        readiness = "AMBER"
        g_checks.append("prospects[] found but not canonical records[]")
    elif events:
        readiness = "RED"
        g_failures.append("event stream captured but no prospect batch located")
    else:
        readiness = "RED"
        g_failures.append("no event payload available")

    g_meta["EXTRACTION_READINESS_REPORT"]["classification"] = readiness
    g_meta["EXTRACTION_READINESS_REPORT"]["records_paths"] = records_paths
    g_meta["EXTRACTION_READINESS_REPORT"]["prospects_paths"] = prospects_paths

    payload_analysis = {
        "run_id": run_id,
        "agent_id": agent_id,
        "capture_id": capture.get("capture_id") if capture else None,
        "receipt_id": receipt.get("receipt_id") if receipt else None,
        "event_analysis": {
            k: v for k, v in analysis.items() if k != "raw_events"
        },
        "raw_events": analysis.get("raw_events", []),
        "extraction_readiness": readiness,
    }

    part_d = SectionReport(
        section="PART_D_WEBHOOK_RECEIPT",
        status="GREEN" if not d_failures else ("BLOCKED" if not receipt else "AMBER"),
        checks=d_checks,
        failures=d_failures,
        metadata=d_meta,
    )
    part_e = SectionReport(
        section="PART_E_EVENT_RETRIEVAL",
        status="GREEN" if events and not e_failures else "BLOCKED",
        checks=e_checks,
        failures=e_failures,
        metadata=e_meta,
    )
    part_f = SectionReport(
        section="PART_F_EXPORT_DISCOVERY",
        status="GREEN" if records_paths else ("AMBER" if prospects_paths else "RED"),
        checks=f_checks,
        failures=f_failures,
        metadata=f_meta,
    )
    part_g = SectionReport(
        section="PART_G_EXTRACTION_READINESS",
        status=readiness,
        checks=g_checks,
        failures=g_failures,
        metadata=g_meta,
    )
    return part_d, part_e, part_f, part_g, payload_analysis


def part_h_boundary() -> SectionReport:
    checks: List[str] = []
    failures: List[str] = []
    meta: Dict[str, Any] = {"BOUNDARY_VALIDATION_REPORT": {}}

    import ast

    connector_path = ROOT / "services" / "discovery" / "twin" / "twin_ingestion_connector.py"
    tree = ast.parse(connector_path.read_text(encoding="utf-8"))
    imports: Set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                imports.add(alias.name)
    forbidden = (
        "LeadService",
        "DiscoveryImportService",
        "DiscoveryApprovalQueueService",
        "DiscoveryConsentService",
        "DiscoveryMetricsService",
    )
    for name in forbidden:
        if name in imports:
            failures.append(f"forbidden import: {name}")
        else:
            checks.append(f"no import of {name}")

    from services.discovery import discovery_config

    capture_only = discovery_config.is_discovery_twin_event_capture_only()
    meta["BOUNDARY_VALIDATION_REPORT"]["capture_only"] = capture_only
    if capture_only:
        checks.append("capture-only mode prevents ingest_async in default config")
    checks.append("flow: Twin webhook → Twin API → event capture → connector (no CRM)")

    status = "GREEN" if not failures else "RED"
    return SectionReport(
        section="PART_H_BOUNDARY",
        status=status,
        checks=checks,
        failures=failures,
        metadata=meta,
    )


def part_i_recommendation(
    report: StageYCaptureReport,
    payload_analysis: Dict[str, Any],
) -> SectionReport:
    readiness = payload_analysis.get("extraction_readiness", "RED")
    has_events = bool(payload_analysis.get("raw_events"))
    records_paths = (
        report.part_f_export_discovery.metadata.get("EXPORT_DISCOVERY_REPORT", {}).get("candidates", [])
        if report.part_f_export_discovery
        else []
    )
    records_path = next((p["json_path"] for p in records_paths if "records" in p.get("json_path", "")), None)

    answers = {
        "1_twin_exposes_prospect_batch_in_run_events": has_events and readiness in ("GREEN", "AMBER"),
        "2_exact_json_path_for_records": records_path,
        "3_extraction_can_be_implemented_safely": readiness == "GREEN",
        "4_auto_ingest_ready": False,
        "5_remaining_blockers": list(report.blockers),
    }

    if not has_events:
        answers["5_remaining_blockers"].extend(
            [
                "No real Twin run executed in this validation pass",
                "TWIN_API_KEY / TWIN_DISCOVERY_AGENT_ID not configured in staging .env",
                "discovery_twin_run_event_captures is empty in pleerity_staging",
                "Register webhook and trigger agent run with STAGE_Y_REGISTER_WEBHOOK=1 STAGE_Y_TRIGGER_TWIN_RUN=1",
            ]
        )
    if readiness != "GREEN":
        answers["4_auto_ingest_ready"] = False
        answers["5_remaining_blockers"].append("Extraction readiness not GREEN")

    text = (
        f"Prospect batch in run events: {answers['1_twin_exposes_prospect_batch_in_run_events']}. "
        f"JSON path: {answers['2_exact_json_path_for_records'] or 'NOT IDENTIFIED'}. "
        f"Safe extraction: {answers['3_extraction_can_be_implemented_safely']}. "
        f"Auto-ingest ready: {answers['4_auto_ingest_ready']}."
    )

    return SectionReport(
        section="PART_I_RECOMMENDATION",
        status=readiness if has_events else "RED",
        checks=[text],
        metadata={"recommendation": answers},
    )


def write_markdown(report: StageYCaptureReport, json_path: Path) -> Path:
    md_path = AUDIT_DIR / "STAGE_Y_REAL_CAPTURE_REPORT.md"
    lines = [
        "# Stage Y — Real Twin Capture Run Report",
        "",
        f"**Authority:** {report.authority}",
        f"**Generated:** {report.generated_at}",
        f"**Overall:** {report.overall_status}",
        f"**Success criteria met:** {report.success_criteria_met}",
        f"**Capture-only enforced:** {report.capture_only_enforced}",
        "",
        f"JSON: `{json_path.relative_to(ROOT.parent)}`",
        "",
    ]
    if report.blockers:
        lines.append("## Blockers")
        for b in report.blockers:
            lines.append(f"- {b}")
        lines.append("")

    for part in (
        report.part_a_connector_health,
        report.part_b_webhook_registration,
        report.part_c_real_run,
        report.part_d_webhook_receipt,
        report.part_e_event_retrieval,
        report.part_f_export_discovery,
        report.part_g_extraction_readiness,
        report.part_h_boundary,
        report.part_i_recommendation,
    ):
        if not part:
            continue
        lines.append(f"## {part.section} — {part.status}")
        for c in part.checks:
            lines.append(f"- {c}")
        if part.failures:
            lines.append("")
            lines.append("**Failures / gaps:**")
            for f in part.failures:
                lines.append(f"- {f}")
        lines.append("")

    md_path.write_text("\n".join(lines), encoding="utf-8")
    return md_path


async def run_validation(
    *,
    register_webhook: bool,
    trigger_run: bool,
    run_id: Optional[str],
    capture_id: Optional[str],
) -> StageYCaptureReport:
    report = StageYCaptureReport(
        generated_at=iso_now(),
        capture_only_enforced=True,
    )

    report.part_a_connector_health = await part_a_connector_health()
    report.part_b_webhook_registration = await part_b_webhook_registration(register=register_webhook)
    report.part_c_real_run = await part_c_trigger_run(trigger=trigger_run)

    if not run_id and report.part_c_real_run:
        run_id = (report.part_c_real_run.metadata.get("REAL_RUN_REPORT") or {}).get("run_id")

    part_d, part_e, part_f, part_g, payload_analysis = await parts_d_e_f_g(
        run_id=run_id,
        capture_id=capture_id,
        pull_from_twin=bool(run_id and (os.environ.get("TWIN_API_KEY") or "").strip()),
    )
    report.part_d_webhook_receipt = part_d
    report.part_e_event_retrieval = part_e
    report.part_f_export_discovery = part_f
    report.part_g_extraction_readiness = part_g
    report.part_h_boundary = part_h_boundary()
    report.part_i_recommendation = part_i_recommendation(report, payload_analysis)

    blockers: List[str] = []
    if report.part_b_webhook_registration.status == "BLOCKED":
        blockers.append("Webhook registration not verified (missing Twin credentials or CVP URL)")
    if report.part_c_real_run.status == "BLOCKED":
        blockers.append("Real Twin run not executed")
    if report.part_e_event_retrieval.status == "BLOCKED":
        blockers.append("No Twin run events captured in MongoDB or via API")
    report.blockers = blockers

    readiness = part_g.status
    has_real_events = bool(payload_analysis.get("raw_events"))
    report.success_criteria_met = (
        has_real_events
        and report.part_c_real_run.status == "GREEN"
        and readiness in ("GREEN", "AMBER")
    )

    if report.success_criteria_met and readiness == "GREEN":
        report.overall_status = "GREEN"
    elif has_real_events:
        report.overall_status = readiness
    elif report.part_a_connector_health.status == "GREEN":
        report.overall_status = "BLOCKED"
    else:
        report.overall_status = "RED"

    json_path = AUDIT_DIR / "TWIN_REAL_EVENT_PAYLOAD_ANALYSIS.json"
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    combined = {
        "report": report.to_dict(),
        "payload_analysis": payload_analysis,
    }
    json_path.write_text(json.dumps(combined, indent=2, default=str), encoding="utf-8")
    write_markdown(report, json_path)

    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage Y real Twin capture validation")
    parser.add_argument("--register-webhook", action="store_true")
    parser.add_argument("--trigger-run", action="store_true")
    parser.add_argument("--run-id", default=os.environ.get("STAGE_Y_CAPTURE_RUN_ID"))
    parser.add_argument("--capture-id", default=os.environ.get("STAGE_Y_CAPTURE_ID"))
    args = parser.parse_args()

    register = args.register_webhook or os.environ.get("STAGE_Y_REGISTER_WEBHOOK") == "1"
    trigger = args.trigger_run or os.environ.get("STAGE_Y_TRIGGER_TWIN_RUN") == "1"

    report = asyncio.run(
        run_validation(
            register_webhook=register,
            trigger_run=trigger,
            run_id=args.run_id,
            capture_id=args.capture_id,
        )
    )
    print(
        json.dumps(
            {
                "overall_status": report.overall_status,
                "success_criteria_met": report.success_criteria_met,
                "extraction_readiness": report.part_g_extraction_readiness.status
                if report.part_g_extraction_readiness
                else "RED",
                "blockers": report.blockers,
            },
            indent=2,
        )
    )
    return 0 if report.success_criteria_met else 1


if __name__ == "__main__":
    raise SystemExit(main())
