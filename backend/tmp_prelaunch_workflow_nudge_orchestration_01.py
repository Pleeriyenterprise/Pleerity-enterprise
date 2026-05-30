#!/usr/bin/env python3
"""PRELAUNCH-WORKFLOW-NUDGE-ORCHESTRATION-01 staging/API verification harness."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import requests

API = os.environ.get("PRELAUNCH_API", "https://pleerity-enterprise.onrender.com/api")
MARK = "PRELAUNCH-WFN-01"
OUT_DIR = Path(__file__).resolve().parent / "docs/audit/prelaunch_workflow_nudge_orchestration_01"
WALES_PROPERTY = "d35a58ae-3c81-491c-9694-1d021dd3b8ad"
CONTRACTOR_ID = os.environ.get("PRELAUNCH_CONTRACTOR_ID", "")


def _read_pw(rel: str) -> str:
    p = Path(__file__).resolve().parent / "docs/audit" / rel
    return p.read_text(encoding="utf-8").strip() if p.exists() else ""


def _login(email: str, password: str) -> str:
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=60)
    r.raise_for_status()
    return r.json()["access_token"]


def _call(method: str, path: str, token: str, body: Dict | None = None) -> Dict[str, Any]:
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{API}{path}"
    if method == "GET":
        r = requests.get(url, headers=headers, timeout=60)
    else:
        r = requests.request(method, url, headers=headers, json=body or {}, timeout=60)
    return {"status": r.status_code, "ok": r.ok, "body": r.json() if r.content else {}}


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results: Dict[str, Any] = {
        "programme": "PRELAUNCH-WORKFLOW-NUDGE-ORCHESTRATION-01",
        "api": API,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "checks": [],
    }
    landlord_pw = _read_pw("ops_verify_01_6fd5ac4c_d35a58ae/.ops_verify_temp_pw.txt")
    contractor_pw = _read_pw("ops_runtime_03_contractor_6fd5ac4c_d35a58ae/.ops_contractor_temp_pw.txt")
    if not landlord_pw:
        results["checks"].append({"name": "credentials", "ok": False, "detail": "landlord pw missing"})
        _write(results)
        return 2
    try:
        client_tok = _login("nancy@yopmail.com", landlord_pw)
    except Exception as exc:
        results["checks"].append({"name": "landlord_login", "ok": False, "detail": str(exc)})
        _write(results)
        return 2

    today = _call("GET", "/today/items", client_tok)
    cc = _call("GET", "/client/command-center?projection=primary", client_tok)
    results["checks"].append({
        "name": "today_items",
        "ok": today["ok"],
        "has_stall_disclosure_key": "workflow_stall_disclosure" in (today.get("body") or {}),
    })
    results["checks"].append({
        "name": "command_centre_primary",
        "ok": cc["ok"],
        "urgent_count": len((cc.get("body") or {}).get("urgent_actions") or []),
    })

    # Dry-run nudge sweep via admin job trigger if available
    admin_pw = os.environ.get("PRELAUNCH_ADMIN_PW", "")
    if admin_pw:
        try:
            admin_tok = _login(os.environ.get("PRELAUNCH_ADMIN_EMAIL", "admin@pleerityenterprise.co.uk"), admin_pw)
            job = _call("POST", "/admin/jobs/workflow_nudge_processing/run", admin_tok)
            results["checks"].append({"name": "nudge_job_run", "ok": job["ok"], "status": job["status"]})
        except Exception as exc:
            results["checks"].append({"name": "nudge_job_run", "ok": False, "detail": str(exc)})
    else:
        results["checks"].append({"name": "nudge_job_run", "ok": None, "detail": "skipped — set PRELAUNCH_ADMIN_PW for live sweep"})

    # Module presence checks (local)
    backend = Path(__file__).resolve().parent
    modules = [
        "services/workflow_timer_service.py",
        "services/workflow_nudge_reconciliation_service.py",
        "services/workflow_nudge_orchestration_service.py",
        "services/workflow_stall_priority_service.py",
        "services/workflow_nudge_guardrails.py",
    ]
    for m in modules:
        results["checks"].append({"name": f"module_{m}", "ok": (backend / m).exists()})

    passed = sum(1 for c in results["checks"] if c.get("ok") is True)
    failed = sum(1 for c in results["checks"] if c.get("ok") is False)
    results["summary"] = {"passed": passed, "failed": failed, "skipped": len(results["checks"]) - passed - failed}
    _write(results)
    (OUT_DIR / "browser_runtime.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    return 0 if failed == 0 else 1


def _write(results: Dict[str, Any]) -> None:
    (OUT_DIR / "harness_runtime.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results["summary"], indent=2))


if __name__ == "__main__":
    sys.exit(main())
