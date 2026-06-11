#!/usr/bin/env python3
"""DASHBOARD-TODAY-COMMANDCENTER-PERFORMANCE-PHASE1 — staging API timing (after patterns)."""
from __future__ import annotations

import importlib.util
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "docs/audit/dashboard_today_commandcenter_performance_phase1_01"
AUDIT_BEFORE = ROOT / "docs/audit/dashboard_today_commandcenter_load_performance_audit_01/api_timing_runtime.json"
PROGRAMME = "DASHBOARD-TODAY-COMMANDCENTER-PERFORMANCE-PHASE1"
RUN_TAG = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

_fc_path = ROOT / "scripts/plan_based_business_outcome_fixture_closeout_01_execute.py"
_spec = importlib.util.spec_from_file_location("_fc", _fc_path)
_fc = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_fc)
API = _fc.API

NANCY_EMAIL = "nancy@yopmail.com"
PW_PATH = ROOT / "docs/audit/ops_verify_01_6fd5ac4c_d35a58ae/.ops_verify_temp_pw.txt"


def write(name: str, data: Any) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


def login() -> str:
    pw = PW_PATH.read_text(encoding="utf-8").strip()
    r = httpx.post(f"{API}/auth/login", json={"email": NANCY_EMAIL, "password": pw}, timeout=120)
    r.raise_for_status()
    body = r.json()
    return body.get("access_token") or body.get("token")


def timed_get(
    client: httpx.Client,
    label: str,
    path: str,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    t0 = time.perf_counter()
    r = client.get(path, params=params or {})
    ms = (time.perf_counter() - t0) * 1000.0
    payload_bytes = len(r.content)
    cache_hit = r.headers.get("x-operational-cache-hit") or r.headers.get("X-Operational-Cache-Hit")
    return {
        "label": label,
        "path": path,
        "params": params or {},
        "status": r.status_code,
        "duration_ms": round(ms, 1),
        "payload_bytes": payload_bytes,
        "cache_hit": cache_hit,
    }


def run_parallel(client: httpx.Client, specs: List[Tuple[str, str, Optional[Dict[str, Any]]]]) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=min(8, len(specs) or 1)) as pool:
        futs = {
            pool.submit(timed_get, client, label, path, params): label
            for label, path, params in specs
        }
        for fut in as_completed(futs):
            results.append(fut.result())
    return results


def summarize(page: str, requests: List[Dict[str, Any]], critical_path_ms: float) -> Dict[str, Any]:
    ok = [r for r in requests if r["status"] == 200]
    return {
        "page": page,
        "request_count": len(requests),
        "ok_count": len(ok),
        "critical_path_ms": round(critical_path_ms, 1),
        "sum_request_ms": round(sum(r["duration_ms"] for r in requests), 1),
        "max_single_ms": round(max((r["duration_ms"] for r in requests), default=0.0), 1),
        "total_payload_bytes": sum(r["payload_bytes"] for r in requests),
        "requests": sorted(requests, key=lambda x: -x["duration_ms"]),
    }


def measure_today(client: httpx.Client) -> Dict[str, Any]:
    gate = run_parallel(
        client,
        [
            ("today:/today/items", "/today/items", {}),
            ("today:/client/requirements", "/client/requirements", {"projection": "full"}),
            (
                "today:/client/command-center",
                "/client/command-center",
                {"projection": "primary"},
            ),
        ],
    )
    compliance = timed_get(client, "today:compliance-summary", "/portfolio/compliance-summary")
    requests = gate + [compliance]
    critical = max(r["duration_ms"] for r in gate)
    return summarize("today", requests, critical)


def measure_command_center(client: httpx.Client) -> Dict[str, Any]:
    reqs = timed_get(client, "cc:requirements-full", "/client/requirements", {"projection": "full"})
    primary = timed_get(
        client,
        "cc:command-center-primary",
        "/client/command-center",
        {"projection": "primary"},
    )
    secondary_cc = timed_get(
        client,
        "cc:command-center-secondary",
        "/client/command-center",
        {"projection": "secondary", "include_secondary": "true"},
    )
    secondary = run_parallel(
        client,
        [
            ("cc:compliance-summary", "/portfolio/compliance-summary", {}),
            (
                "cc:work-orders",
                "/client/maintenance/work-orders",
                {"skip": 0, "limit": 200},
            ),
        ],
    )
    requests = [reqs, primary, secondary_cc] + secondary
    critical = primary["duration_ms"]
    return summarize("command_center", requests, critical)


def measure_dashboard(client: httpx.Client) -> Dict[str, Any]:
    gate = timed_get(
        client,
        "dash:dashboard-gate",
        "/client/dashboard",
        {"include_score_headline": "false"},
    )
    parallel = run_parallel(
        client,
        [
            ("dash:/client/compliance-score", "/client/compliance-score", {}),
            ("dash:/client/score/changes", "/client/score/changes", {"limit": 20}),
            ("dash:/portfolio/compliance-summary", "/portfolio/compliance-summary", {}),
            ("dash:/client/requirements", "/client/requirements", {"projection": "full"}),
            (
                "dash:/client/command-center",
                "/client/command-center",
                {"projection": "primary"},
            ),
            ("dash:/client/protection-snapshot", "/client/protection-snapshot", {}),
            ("dash:/client/activity-since", "/client/activity-since", {}),
            ("dash:/client/onboarding/checklist", "/client/onboarding/checklist", {}),
            ("dash:/client/value-insights", "/client/value-insights", {}),
            ("dash:/profile/notifications", "/profile/notifications", {}),
            ("dash:/client/dashboard/roi-summary", "/client/dashboard/roi-summary", {}),
            (
                "dash:/client/score-trend/portfolio",
                "/client/score-trend/portfolio",
                {"days": 90},
            ),
            (
                "dash:/client/maintenance/work-orders",
                "/client/maintenance/work-orders",
                {"skip": 0, "limit": 200},
            ),
            (
                "dash:/client/maintenance/issues/open-count",
                "/client/maintenance/issues/open-count",
                {},
            ),
            (
                "dash:/client/finance/maintenance-spend-this-month",
                "/client/finance/maintenance-spend-this-month",
                {},
            ),
        ],
    )
    today = timed_get(client, "dash:/today/items", "/today/items", {})
    requests = [gate] + parallel + [today]
    critical = max(
        gate["duration_ms"],
        max((r["duration_ms"] for r in parallel), default=0.0),
        today["duration_ms"],
    )
    return summarize("dashboard", requests, critical)


def load_before() -> Dict[str, Any]:
    if not AUDIT_BEFORE.is_file():
        return {}
    return json.loads(AUDIT_BEFORE.read_text(encoding="utf-8"))


def compare(before: Dict[str, Any], after: Dict[str, Any]) -> Dict[str, Any]:
    rows = {}
    for page in ("today", "command_center", "dashboard"):
        b = (before.get("cold_pass") or {}).get(page) or {}
        a = after.get(page) or {}
        b_crit = b.get("max_single_ms") or b.get("sequential_wall_ms")
        a_crit = a.get("critical_path_ms")
        rows[page] = {
            "requests_before": b.get("request_count"),
            "requests_after": a.get("request_count"),
            "payload_bytes_before": b.get("total_payload_bytes"),
            "payload_bytes_after": a.get("total_payload_bytes"),
            "critical_path_ms_before": b_crit,
            "critical_path_ms_after": a_crit,
            "critical_path_delta_ms": round((a_crit or 0) - (b_crit or 0), 1) if a_crit and b_crit else None,
            "perceived_first_content_ms_before": b_crit,
            "perceived_first_content_ms_after": a.get("requests", [{}])[0]["duration_ms"]
            if page == "dashboard" and a.get("requests")
            else a_crit,
        }
    return rows


def main() -> None:
    token = login()
    headers = {"Authorization": f"Bearer {token}"}
    with httpx.Client(base_url=API, headers=headers, timeout=120.0) as client:
        after = {
            "today": measure_today(client),
            "command_center": measure_command_center(client),
            "dashboard": measure_dashboard(client),
        }

    before = load_before()
    comparison = compare(before, after)
    payload = {
        "programme": PROGRAMME,
        "run_tag": RUN_TAG,
        "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        "api_base": API,
        "account": NANCY_EMAIL,
        "before_source": str(AUDIT_BEFORE.relative_to(ROOT)),
        "after_pass": after,
        "comparison": comparison,
        "phase1_changes": [
            "projection=primary on command-center mount paths",
            "single compliance-summary on Today (property dropdown + jurisdiction)",
            "single requirements/full on Dashboard (no list projection duplicate)",
            "layout CRN uses operational dashboard cache (no duplicate fetch when warm)",
            "removed dead score trend/timeline fetches",
            "risk KPI from protection-snapshot only (no risk-signals/predictive-insights lists)",
            "work-orders limit 200 (was 500, failed 422 on staging)",
        ],
        "snapshot_deferred": True,
    }
    write("api_timing_runtime.json", payload)
    write("comparison.json", comparison)
    print(json.dumps({"ok": True, "out": str(OUT), "comparison": comparison}, indent=2))


if __name__ == "__main__":
    main()
