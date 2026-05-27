#!/usr/bin/env python3
"""
EXECUTION-CAPACITY-AND-NETWORK-RELIABILITY-01 staging validation harness.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import httpx

ROOT = Path(__file__).resolve().parent
PROGRAMME = "EXECUTION-CAPACITY-AND-NETWORK-RELIABILITY-01"
RUN_TAG = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

DEFAULT_CID = "6fd5ac4c-3fd4-4112-ade7-156977deb49f"
DEFAULT_SLUG = "6fd5ac4c_d35a58ae"

_raw_api = os.environ.get("OPS_VERIFY_API_URL", "https://pleerity-enterprise.onrender.com").rstrip("/")
API = _raw_api if _raw_api.endswith("/api") else f"{_raw_api}/api"
CLIENT_EMAIL = os.environ.get("OPS_VERIFY_EMAIL", "nancy@yopmail.com")
PW_PATH = ROOT / f"docs/audit/ops_verify_01_{DEFAULT_SLUG}/.ops_verify_temp_pw.txt"
CLIENT_PW = os.environ.get("OPS_VERIFY_PASSWORD") or (
    PW_PATH.read_text(encoding="utf-8").strip() if PW_PATH.is_file() else "OpsVerify01!StagingWalk"
)

OUT = ROOT / "docs" / "audit" / "execution_capacity_network_reliability_01"


def utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write(name: str, data: Any) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


def login() -> str:
    r = httpx.post(f"{API}/auth/login", json={"email": CLIENT_EMAIL, "password": CLIENT_PW}, timeout=120)
    r.raise_for_status()
    return r.json()["access_token"]


def get_json(url: str, token: str, *, params: Optional[dict] = None) -> Tuple[int, Any]:
    r = httpx.get(url, headers={"Authorization": f"Bearer {token}"}, params=params, timeout=180)
    if "application/json" in (r.headers.get("content-type") or "").lower():
        return r.status_code, r.json()
    return r.status_code, r.text


def execution_snapshot(token: str) -> Dict[str, Any]:
    snap: Dict[str, Any] = {"captured_at": utc()}
    st, cc = get_json(f"{API}/client/command-center", token, params={"projection": "primary"})
    if st != 200 or not isinstance(cc, dict):
        snap["error"] = "command_center_unavailable"
        return snap

    ov = cc.get("operational_value_v1") or {}
    ec = ov.get("execution_capacity_v1") or {}
    snap["execution_capacity_available"] = ec.get("available", True) and not ec.get("error")

    audit = ec.get("contractor_network_audit_v1") or {}
    assign = ec.get("assignment_conversion_v1") or {}
    kpis = ec.get("execution_momentum_kpis_v1") or {}
    recovery = ec.get("execution_recovery_v1") or {}
    quote = ec.get("quote_throughput_v1") or {}

    snap["unassigned_total"] = audit.get("unassigned_jobs_total")
    snap["no_coverage_jobs"] = (audit.get("coverage_distribution") or {}).get("no_coverage")
    snap["assignment_failure_taxonomy"] = audit.get("assignment_failure_taxonomy")
    snap["unsupported_zones"] = len(audit.get("unsupported_operational_zones") or [])
    snap["open_unassigned"] = assign.get("open_unassigned_count")
    snap["assignment_conversion_rate"] = assign.get("assignment_conversion_rate")
    snap["contractor_reliability_score"] = assign.get("contractor_reliability_score")
    snap["execution_capacity_confidence"] = kpis.get("execution_capacity_confidence")
    snap["unsupported_job_ratio"] = kpis.get("unsupported_job_ratio")
    snap["quote_awaiting"] = quote.get("awaiting_quote_count")
    snap["recovery_actions"] = len(recovery.get("recovery_actions") or [])
    snap["execution_capacity_dominant"] = (recovery.get("workflow_blockage_vs_execution_capacity") or {}).get(
        "execution_capacity_dominant"
    )

    urgent = cc.get("urgent_actions") or []
    snap["urgent_execution_capacity_actions"] = sum(
        1 for u in urgent if ((u.get("metadata") or {}).get("execution_capacity_action"))
    )

    closure = ov.get("closure_conversion_v1") or {}
    snap["decision_confidence"] = (closure.get("landlord_decision_confidence_v1") or {}).get("decision_confidence_score")

    st2, wos_body = get_json(f"{API}/client/maintenance/work-orders", token, params={"limit": 200})
    wos = (wos_body or {}).get("work_orders") or [] if st2 == 200 else []
    snap["jobs_no_contractor"] = sum(
        1
        for w in wos
        if (w.get("status") or "").upper() in ("OPEN", "ASSIGNED", "SCHEDULED") and not w.get("contractor_id")
    )
    snap["jobs_completed_unverified"] = sum(
        1 for w in wos if (w.get("status") or "").upper() == "COMPLETED" and not w.get("verified_at")
    )

    return snap


def classify_execution(snap: Dict[str, Any]) -> Tuple[str, str, Dict[str, Any]]:
    if not snap.get("execution_capacity_available"):
        return (
            "STALLED_OPERATIONAL_SYSTEM",
            "OPERATIONAL_VALUE_FAILURE",
            {"reason": "execution_capacity_bundle_unavailable"},
        )

    no_cov = snap.get("no_coverage_jobs") or 0
    unassigned = snap.get("unassigned_total") or 0
    conf = snap.get("execution_capacity_confidence") or 0
    exec_urgent = snap.get("urgent_execution_capacity_actions") or 0
    taxonomy = snap.get("assignment_failure_taxonomy") or {}

    exec_detail = {
        "no_coverage_jobs": no_cov,
        "unassigned_total": unassigned,
        "execution_capacity_confidence": conf,
        "taxonomy_top": list(taxonomy.items())[:5],
        "recovery_actions": snap.get("recovery_actions"),
    }

    if conf >= 0.55 and no_cov < unassigned * 0.3 and exec_urgent > 0:
        exec_class = "VERIFIED_EXECUTION_RELIABILITY"
    elif snap.get("execution_capacity_available") and taxonomy and exec_urgent > 0:
        exec_class = "PARTIAL_EXECUTION_RELIABILITY"
    elif no_cov >= 10:
        exec_class = "EXECUTION_NETWORK_FAILURE_RISK"
    else:
        exec_class = "PARTIAL_EXECUTION_RELIABILITY"

    if exec_class == "VERIFIED_EXECUTION_RELIABILITY":
        ov_class = "VERIFIED_OPERATIONAL_VALUE"
    elif exec_class in ("PARTIAL_EXECUTION_RELIABILITY", "EXECUTION_NETWORK_FAILURE_RISK"):
        ov_class = "PARTIAL_OPERATIONAL_VALUE" if exec_class == "PARTIAL_EXECUTION_RELIABILITY" else "EXECUTION_CAPACITY_RISK"
    else:
        ov_class = "EXECUTION_CAPACITY_RISK"

    return exec_class, ov_class, exec_detail


def run_child(script: str) -> Dict[str, Any]:
    proc = subprocess.run([sys.executable, str(ROOT / script)], cwd=str(ROOT), capture_output=True, text=True)
    for line in reversed((proc.stdout or "").strip().split("\n")):
        if line.strip().startswith("{"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    return {"exit_code": proc.returncode}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    write("programme.json", {"programme": PROGRAMME, "run_tag": RUN_TAG, "client_id": DEFAULT_CID})

    token = login()
    snap = execution_snapshot(token)
    write("01_execution_snapshot.json", snap)

    exec_class, ov_class, detail = classify_execution(snap)
    write(
        "02_classification.json",
        {
            "programme": PROGRAMME,
            "execution_reliability_classification": exec_class,
            "operational_value_classification": ov_class,
            "detail": detail,
            "verified_at_utc": utc(),
        },
    )

    child_results = {}
    for script, key in [
        ("tmp_outcome_effectiveness_validation_01_execute.py", "outcome"),
        ("tmp_closure_conversion_effectiveness_01_execute.py", "closure"),
        ("tmp_backlog_reduction_runtime_01_execute.py", "backlog"),
    ]:
        child_results[key] = run_child(script)
    write("03_child_validations.json", child_results)

    lines = [
        f"# {PROGRAMME}",
        "",
        f"**Execution reliability:** `{exec_class}`",
        f"**Operational value (derived):** `{ov_class}`",
        "",
        json.dumps(snap, indent=2),
        "",
    ]
    (OUT / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "programme": PROGRAMME,
                "execution_reliability_classification": exec_class,
                "operational_value_classification": ov_class,
                "snapshot": snap,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
