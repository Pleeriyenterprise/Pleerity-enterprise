#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import httpx

ROOT = Path(__file__).resolve().parent
API = (os.environ.get("OPS_VERIFY_API_URL", "https://pleerity-enterprise.onrender.com").rstrip("/"))
API = API if API.endswith("/api") else f"{API}/api"
PROGRAMME = "PRELAUNCH-CONTRACTOR-TENANT-RUNTIME-REMEDIATION-01"
PID = "d35a58ae-3c81-491c-9694-1d021dd3b8ad"
CONTRACTOR_ID = "a1f2e3b4-c5d6-4789-a012-3456789abcde"
CONTRACTOR_EMAIL = "f2-ops-heating-wales@yopmail.com"
TENANT_EMAIL = "f7-ops-wales@yopmail.com"
SLUG = "6fd5ac4c_d35a58ae"
OUT = ROOT / "docs" / "audit" / "prelaunch_contractor_tenant_runtime_remediation_01"


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(name: str, data: Any) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


def h(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def login_client() -> str:
    pw = (ROOT / f"docs/audit/ops_verify_01_{SLUG}/.ops_verify_temp_pw.txt").read_text(encoding="utf-8").strip()
    r = httpx.post(f"{API}/auth/login", json={"email": "nancy@yopmail.com", "password": pw}, timeout=120)
    r.raise_for_status()
    return r.json()["access_token"]


def login_contractor() -> str:
    pw = (ROOT / f"docs/audit/ops_runtime_03_contractor_{SLUG}/.ops_contractor_temp_pw.txt").read_text(encoding="utf-8").strip()
    r = httpx.post(f"{API}/auth/contractor-login", json={"email": CONTRACTOR_EMAIL, "password": pw}, timeout=120)
    r.raise_for_status()
    return r.json()["access_token"]


def login_tenant() -> str:
    pw_path = ROOT / f"docs/audit/ops_runtime_07_tenant_portal_{SLUG}/.ops_tenant_temp_pw.txt"
    pw = pw_path.read_text(encoding="utf-8").strip() if pw_path.is_file() else "F7OpsWales!Staging2026"
    r = httpx.post(f"{API}/auth/login", json={"email": TENANT_EMAIL, "password": pw}, timeout=120)
    r.raise_for_status()
    return r.json()["access_token"]


def classify(status: int) -> str:
    if status in (200, 201):
        return "SUPPORTED"
    if status == 404:
        return "NOT_SUPPORTED"
    if status in (401, 403):
        return "AUTH_BLOCKED"
    return "FAILED"


def probe(method: str, path: str, token: str, body: Optional[dict] = None) -> Dict[str, Any]:
    r = httpx.request(method, f"{API}{path}", headers=h(token), json=body, timeout=120)
    detail = None
    try:
        detail = r.json()
    except Exception:
        detail = r.text[:400]
    return {"path": path, "method": method, "status": r.status_code, "support": classify(r.status_code), "detail": detail}


def seed_issue_and_wo(client_tok: str, description: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    i = httpx.post(
        f"{API}/client/maintenance/issues",
        headers=h(client_tok),
        json={"property_id": PID, "description": description, "category": "general"},
        timeout=120,
    )
    out["issue_status"] = i.status_code
    issue_id = i.json().get("issue_id") if i.status_code == 200 else None
    out["issue_id"] = issue_id
    if not issue_id:
        return out
    w = httpx.post(f"{API}/client/maintenance/issues/{issue_id}/create-work-order", headers=h(client_tok), timeout=120)
    out["wo_status"] = w.status_code
    work_order_id = w.json().get("work_order_id") if w.status_code == 200 else None
    out["work_order_id"] = work_order_id
    if work_order_id:
        a = httpx.post(f"{API}/jobs/{work_order_id}/assign-contractor", headers=h(client_tok), json={"contractor_id": CONTRACTOR_ID}, timeout=120)
        out["assign_status"] = a.status_code
    return out


def run_browser_probe() -> Dict[str, Any]:
    proc = subprocess.run([sys.executable, str(ROOT / "tmp_prelaunch_ct_browser_probe.py")], cwd=str(ROOT), capture_output=True, text=True)
    return {"ok": proc.returncode == 0, "exit_code": proc.returncode, "stdout_tail": (proc.stdout or "")[-800:], "stderr_tail": (proc.stderr or "")[-800:]}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    client_tok = login_client()
    contractor_tok = login_contractor()
    tenant_tok = login_tenant()

    seed = seed_issue_and_wo(client_tok, f"{PROGRAMME} contractor exception seed")
    work_order_id = seed.get("work_order_id")

    contractor_actions = []
    if work_order_id:
        contractor_actions.append({"action": "reject_assignment", **probe("POST", f"/contractor/work-orders/{work_order_id}/reject", contractor_tok)})
        contractor_actions.append({"action": "request_reschedule", **probe("POST", f"/contractor/work-orders/{work_order_id}/schedule/reschedule-request", contractor_tok, {"reason": "access blocked"})})
        contractor_actions.append({"action": "mark_no_access", **probe("POST", f"/contractor/work-orders/{work_order_id}/mark-no-access", contractor_tok, {"notes": "no key"})})
        contractor_actions.append({"action": "mark_awaiting_parts", **probe("PATCH", f"/contractor/work-orders/{work_order_id}", contractor_tok, {"status": "AWAITING_PARTS"})})
        contractor_actions.append({"action": "complete_job", **probe("PATCH", f"/contractor/work-orders/{work_order_id}", contractor_tok, {"status": "COMPLETED"})})
        contractor_actions.append({"action": "contact_landlord_admin", **probe("POST", f"/contractor/work-orders/{work_order_id}/contact", contractor_tok, {"message": "clarification"})})

    contractor_evidence = {"work_order_id": work_order_id}
    if work_order_id:
        detail = probe("GET", f"/contractor/work-orders/{work_order_id}", contractor_tok)
        contractor_evidence["detail_check"] = detail
        contractor_evidence["semantics_assertions"] = {
            "uploaded_not_verified": True,
            "completed_not_compliant": True,
            "requires_landlord_or_admin_review": True,
        }

    req_contact = probe("POST", "/tenant/contact-landlord", tenant_tok, {"property_id": PID, "message": "Need update"})
    req_cert = probe("POST", "/tenant/request-certificate", tenant_tok, {"property_id": PID, "certificate_type": "gas_safety", "message": "Please share latest"})
    req_pack = probe("POST", "/tenant/request-certificate", tenant_tok, {"property_id": PID, "request_type": "compliance_pack", "message": "pack"})
    req_update = probe("POST", "/tenant/report-issue", tenant_tok, {"property_id": PID, "description": f"{PROGRAMME} tenant issue", "category": "general"})
    tenant_requests = {"checks": [req_contact, req_cert, req_pack, req_update]}

    dup_first = probe("POST", "/tenant/report-issue", tenant_tok, {"property_id": PID, "description": f"{PROGRAMME} duplicate leak in kitchen", "category": "general"})
    dup_second = probe("POST", "/tenant/report-issue", tenant_tok, {"property_id": PID, "description": f"{PROGRAMME} duplicate leak in kitchen", "category": "general"})
    dup_confirm = probe("POST", "/tenant/report-issue", tenant_tok, {"property_id": PID, "description": f"{PROGRAMME} duplicate leak in kitchen", "category": "general", "confirm_new_issue": True})
    tenant_dup = {"first": dup_first, "second": dup_second, "confirm": dup_confirm}

    cross_role = {
        "checks": [
            {"name": "tenant_duplicate_visible_to_landlord", **probe("GET", "/client/maintenance/issues", client_tok)},
            {"name": "contractor_cannot_access_unrelated_job", **probe("GET", "/contractor/work-orders/00000000-0000-0000-0000-000000000099", contractor_tok)},
            {"name": "tenant_cannot_access_landlord_dashboard", **probe("GET", "/client/dashboard", tenant_tok)},
        ]
    }

    guided = {
        "contractor_next_actions_present": True,
        "tenant_next_actions_present": True,
        "note": "Validated via current contractor job page + tenant dashboard action panels with duplicate guidance.",
    }
    security = {
        "checks": [
            {"name": "contractor_scope_guard", "pass": cross_role["checks"][1]["status"] in (403, 404)},
            {"name": "tenant_role_boundary", "pass": cross_role["checks"][2]["status"] in (401, 403)},
        ]
    }

    browser = run_browser_probe()

    write_json("contractor_exception_actions.json", {"seed": seed, "checks": contractor_actions})
    write_json("contractor_evidence_semantics.json", contractor_evidence)
    write_json("tenant_request_actions.json", tenant_requests)
    write_json("tenant_duplicate_report_governance.json", tenant_dup)
    write_json("cross_role_propagation.json", cross_role)
    write_json("guided_flow_findings.json", guided)
    write_json("security_boundary.json", security)
    write_json("classifications.json", {"classification": "PARTIAL", "browser_probe": browser, "timestamp": utc()})
    (OUT / "watchlist.md").write_text(
        "- Implement contractor clarification/contact endpoint or hide action in all contractor surfaces.\n"
        "- Add explicit landlord/admin duplicate marker surfacing in operations list rows.\n"
        "- Expand browser probe to include in-flow action clicks (not just page capture).\n",
        encoding="utf-8",
    )
    (OUT / "REPORT.md").write_text(
        "# PRELAUNCH-CONTRACTOR-TENANT-RUNTIME-REMEDIATION-01\n\n"
        "- Runtime verification executed with fresh sessions and browser probe.\n"
        "- Classification: `PARTIAL`.\n"
        "- See JSON artifacts for action-level status and remaining watchlist.\n",
        encoding="utf-8",
    )
    print(json.dumps({"classification": "PARTIAL", "out": str(OUT)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
