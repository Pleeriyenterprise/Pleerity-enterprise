#!/usr/bin/env python3
from __future__ import annotations

import base64
import json
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import httpx

ROOT = Path(__file__).resolve().parent
API = (os.environ.get("OPS_VERIFY_API_URL", "https://pleerity-enterprise.onrender.com").rstrip("/"))
API = API if API.endswith("/api") else f"{API}/api"
SLUG = "6fd5ac4c_d35a58ae"
PID = "d35a58ae-3c81-491c-9694-1d021dd3b8ad"
CONTRACTOR_ID = "a1f2e3b4-c5d6-4789-a012-3456789abcde"
CONTRACTOR_EMAIL = "f2-ops-heating-wales@yopmail.com"
TENANT_EMAIL = "f7-ops-wales@yopmail.com"
OUT = ROOT / "docs" / "audit" / "prelaunch_contractor_tenant_trust_risk_remediation_01"
MARK = f"PRELAUNCH-CT-TRUST-RISK-REMEDIATION-01-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
EXPECTED_NOTE = "Uploaded evidence has been received but has not yet been reviewed or verified."
EXPECTED_CC_MESSAGE = "Some pressure metrics are still refreshing. Urgent items remain visible below."


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(name: str, payload: Any) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")


def auth(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def parse_resp(resp: httpx.Response) -> Any:
    try:
        return resp.json()
    except Exception:
        return resp.text[:700]


def call(method: str, path: str, token: Optional[str] = None, body: Optional[dict] = None, files: Optional[dict] = None) -> Dict[str, Any]:
    headers = auth(token) if token else {}
    try:
        with httpx.Client(timeout=35) as c:
            r = c.request(method, f"{API}{path}", headers=headers, json=body if files is None else None, files=files)
    except httpx.TimeoutException as exc:
        return {"method": method, "path": path, "status": 599, "ok": False, "body": f"timeout: {exc}"}
    return {"method": method, "path": path, "status": r.status_code, "ok": 200 <= r.status_code < 300, "body": parse_resp(r)}


def login_client() -> str:
    pw = (ROOT / f"docs/audit/ops_verify_01_{SLUG}/.ops_verify_temp_pw.txt").read_text(encoding="utf-8").strip()
    r = httpx.post(f"{API}/auth/login", json={"email": "nancy@yopmail.com", "password": pw}, timeout=35)
    r.raise_for_status()
    return r.json()["access_token"]


def login_contractor() -> str:
    pw = (ROOT / f"docs/audit/ops_runtime_03_contractor_{SLUG}/.ops_contractor_temp_pw.txt").read_text(encoding="utf-8").strip()
    r = httpx.post(f"{API}/auth/contractor-login", json={"email": CONTRACTOR_EMAIL, "password": pw}, timeout=35)
    r.raise_for_status()
    return r.json()["access_token"]


def login_tenant() -> str:
    p = ROOT / f"docs/audit/ops_runtime_07_tenant_portal_{SLUG}/.ops_tenant_temp_pw.txt"
    pw = p.read_text(encoding="utf-8").strip() if p.exists() else "F7OpsWales!Staging2026"
    r = httpx.post(f"{API}/auth/login", json={"email": TENANT_EMAIL, "password": pw}, timeout=35)
    r.raise_for_status()
    return r.json()["access_token"]


def seed_work_order(client_tok: str, desc: str, category: str = "general") -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for _ in range(3):
        issue = call("POST", "/client/maintenance/issues", client_tok, {"property_id": PID, "description": desc, "category": category})
        out["issue"] = issue
        if issue.get("status") == 200:
            break
        time.sleep(1.2)
    issue_id = (out.get("issue", {}).get("body") or {}).get("issue_id") if isinstance(out.get("issue", {}).get("body"), dict) else None
    if not issue_id:
        return out
    out["create_work_order"] = call("POST", f"/client/maintenance/issues/{issue_id}/create-work-order", client_tok)
    wo_id = (out.get("create_work_order", {}).get("body") or {}).get("work_order_id") if isinstance(out.get("create_work_order", {}).get("body"), dict) else None
    if not wo_id:
        return out
    out["assign"] = call("POST", f"/jobs/{wo_id}/assign-contractor", client_tok, {"contractor_id": CONTRACTOR_ID})
    out["issue_id"] = issue_id
    out["work_order_id"] = wo_id
    return out


def tiny_png() -> bytes:
    return base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO7Z0uUAAAAASUVORK5CYII=")


def tiny_pdf() -> bytes:
    return b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"


def bdict(row: Dict[str, Any]) -> Dict[str, Any]:
    b = row.get("body")
    return b if isinstance(b, dict) else {}


def sem_ok(payload: Dict[str, Any]) -> bool:
    state = str(payload.get("evidence_review_state") or "").lower()
    return (
        payload.get("uploaded_is_verified") is False
        and state in ("uploaded", "pending_review")
        and payload.get("evidence_requires_review") is True
        and str(payload.get("evidence_authority_note") or "") == EXPECTED_NOTE
        and payload.get("completed_work_is_compliant") is False
        and isinstance(payload.get("evidence_count"), int)
    )


def main() -> int:
    client_tok = login_client()
    contractor_tok = login_contractor()
    tenant_tok = login_tenant()

    evidence = {"captured_at": utc(), "seed": {}, "checks": [], "evaluation": {}}
    seed = seed_work_order(client_tok, f"{MARK} evidence")
    evidence["seed"] = seed
    wo = seed.get("work_order_id")
    if wo:
        evidence["checks"].append({"name": "accept", **call("POST", f"/contractor/work-orders/{wo}/accept", contractor_tok)})
        with tempfile.NamedTemporaryFile("wb", suffix=".png", delete=False) as f:
            f.write(tiny_png())
            p = f.name
        with open(p, "rb") as f:
            evidence["checks"].append({"name": "image_upload", **call("POST", f"/contractor/work-orders/{wo}/evidence", contractor_tok, files={"file": ("img.png", f, "image/png")})})
        with tempfile.NamedTemporaryFile("wb", suffix=".pdf", delete=False) as f:
            f.write(tiny_pdf())
            p2 = f.name
        with open(p2, "rb") as f:
            evidence["checks"].append({"name": "pdf_upload", **call("POST", f"/contractor/work-orders/{wo}/evidence", contractor_tok, files={"file": ("doc.pdf", f, "application/pdf")})})
        evidence["checks"].append({"name": "landlord_read", **call("GET", f"/client/maintenance/work-orders/{wo}", client_tok)})
        evidence["checks"].append({"name": "contractor_read", **call("GET", f"/contractor/work-orders/{wo}", contractor_tok)})
    e = {x["name"]: x for x in evidence["checks"]}
    evidence["evaluation"] = {
        "mutation_image_semantics_ok": int(e.get("image_upload", {}).get("status", 0)) == 200 and sem_ok(bdict(e.get("image_upload", {}))),
        "mutation_pdf_semantics_ok": int(e.get("pdf_upload", {}).get("status", 0)) == 200 and sem_ok(bdict(e.get("pdf_upload", {}))),
        "landlord_read_semantics_ok": int(e.get("landlord_read", {}).get("status", 0)) == 200 and sem_ok(bdict(e.get("landlord_read", {}))),
        "contractor_read_semantics_ok": int(e.get("contractor_read", {}).get("status", 0)) == 200 and sem_ok(bdict(e.get("contractor_read", {}))),
    }
    write_json("contractor_evidence_semantics.json", evidence)

    no_access = {"captured_at": utc(), "seed": {}, "checks": [], "evaluation": {}}
    nseed = seed_work_order(client_tok, f"{MARK} no-access")
    no_access["seed"] = nseed
    nwo = nseed.get("work_order_id")
    if nwo:
        no_access["checks"].append({"name": "accept", **call("POST", f"/contractor/work-orders/{nwo}/accept", contractor_tok)})
        no_access["checks"].append({"name": "quote_submit", **call("POST", f"/jobs/{nwo}/submit-quote", contractor_tok, {"amount": 150.0, "currency": "GBP", "notes": f"{MARK} quote"})})
        no_access["checks"].append({"name": "quote_approve", **call("POST", f"/jobs/{nwo}/approve-quote", client_tok)})
        no_access["checks"].append({"name": "mark_no_access", **call("POST", f"/contractor/work-orders/{nwo}/mark-no-access", contractor_tok, {"notes": "no key"})})
        no_access["checks"].append({"name": "set_in_progress", **call("PATCH", f"/contractor/work-orders/{nwo}", contractor_tok, {"status": "IN_PROGRESS"})})
        no_access["checks"].append({"name": "complete", **call("PATCH", f"/contractor/work-orders/{nwo}", contractor_tok, {"status": "COMPLETED"})})
        no_access["checks"].append({"name": "landlord_post_complete", **call("GET", f"/client/maintenance/work-orders/{nwo}", client_tok)})
        no_access["checks"].append({"name": "contractor_post_complete", **call("GET", f"/contractor/work-orders/{nwo}", contractor_tok)})
    n = {x["name"]: x for x in no_access["checks"]}
    landlord = bdict(n.get("landlord_post_complete", {}))
    contractor = bdict(n.get("contractor_post_complete", {}))
    no_access["evaluation"] = {
        "mark_no_access_ok": int(n.get("mark_no_access", {}).get("status", 0)) == 200,
        "in_progress_clears_current_exception": int(n.get("set_in_progress", {}).get("status", 0)) == 200 and not bdict(n.get("set_in_progress", {})).get("operational_exception"),
        "completed_keeps_exception_cleared_landlord": int(n.get("landlord_post_complete", {}).get("status", 0)) == 200 and not landlord.get("operational_exception"),
        "completed_keeps_exception_cleared_contractor": int(n.get("contractor_post_complete", {}).get("status", 0)) == 200 and not contractor.get("operational_exception"),
        "history_preserved": "No access" in str(landlord.get("contractor_notes") or contractor.get("contractor_notes") or ""),
    }
    write_json("no_access_cleanup.json", no_access)

    pressure = {"captured_at": utc(), "checks": [], "evaluation": {}}
    pressure["checks"].append({"name": "tenant_duplicate_seed_1", **call("POST", "/tenant/report-issue", tenant_tok, {"property_id": PID, "description": f"{MARK} pressure", "category": "general"})})
    pressure["checks"].append({"name": "tenant_duplicate_seed_2", **call("POST", "/tenant/report-issue", tenant_tok, {"property_id": PID, "description": f"{MARK} pressure", "category": "general"})})
    for i in range(6):
        pressure["checks"].append({"name": f"command_center_primary_{i+1}", **call("GET", "/client/command-center?projection=primary", client_tok)})
        time.sleep(0.8)
    rows = [x for x in pressure["checks"] if str(x.get("name")).startswith("command_center_primary_")]
    any_200 = [x for x in rows if int(x.get("status", 0)) == 200]
    degraded = [x for x in any_200 if bdict(x).get("pressure_status") == "degraded"]
    pb = bdict(degraded[0]) if degraded else (bdict(any_200[0]) if any_200 else {})
    pressure["evaluation"] = {
        "primary_returns_200": len(any_200) > 0,
        "degraded_disclosure_present": pb.get("pressure_degraded") is True and pb.get("pressure_status") == "degraded" and str(pb.get("pressure_message") or "") == EXPECTED_CC_MESSAGE,
        "urgent_count_present": isinstance(pb.get("pressure_urgent_count"), int),
        "urgent_rows_present": isinstance(pb.get("pressure_urgent_rows"), list) and len(pb.get("pressure_urgent_rows") or []) > 0,
        "fallback_reason_present": bool(pb.get("pressure_fallback_reason")),
        "no_false_healthy_empty_state": not (
            pb.get("pressure_status") == "degraded"
            and int(pb.get("pressure_urgent_count") or 0) == 0
            and len(pb.get("pressure_urgent_rows") or []) == 0
        ),
    }
    write_json("command_centre_degraded_pressure.json", pressure)

    cross = {"captured_at": utc(), "checks": [], "evaluation": {}}
    if wo:
        cross["checks"].append({"name": "landlord_read_evidence_job", **call("GET", f"/client/maintenance/work-orders/{wo}", client_tok)})
    if nwo:
        cross["checks"].append({"name": "landlord_read_no_access_job", **call("GET", f"/client/maintenance/work-orders/{nwo}", client_tok)})
    cross["checks"].append({"name": "tenant_boundary", **call("GET", "/client/dashboard", tenant_tok)})
    cross["checks"].append({"name": "contractor_boundary", **call("GET", "/contractor/work-orders/00000000-0000-0000-0000-000000000099", contractor_tok)})
    c = {x["name"]: x for x in cross["checks"]}
    cross["evaluation"] = {
        "landlord_reads_ok": all(int(c.get(k, {}).get("status", 0)) == 200 for k in c if k.startswith("landlord_read")),
        "tenant_boundary_ok": int(c.get("tenant_boundary", {}).get("status", 0)) == 403,
        "contractor_boundary_ok": int(c.get("contractor_boundary", {}).get("status", 0)) == 404,
    }
    write_json("cross_role_smoke.json", cross)

    ep = all(bool(v) for v in evidence["evaluation"].values())
    np = all(bool(v) for v in no_access["evaluation"].values())
    pp = all(bool(v) for v in pressure["evaluation"].values())
    cp = all(bool(v) for v in cross["evaluation"].values())
    if ep and np and pp and cp:
        classification = "VERIFIED_OPERATIONALLY"
    elif cp and (ep or np or pp):
        classification = "PARTIAL"
    elif not cp:
        classification = "FAIL_OPERATIONAL"
    else:
        classification = "TRUST_RISK_PRESENT"
    write_json(
        "classifications.json",
        {
            "classification": classification,
            "evidence_semantics_pass": ep,
            "no_access_cleanup_pass": np,
            "command_centre_degraded_pressure_pass": pp,
            "cross_role_smoke_pass": cp,
            "finished_at": utc(),
        },
    )
    (OUT / "REPORT.md").write_text(
        "\n".join(
            [
                "# PRELAUNCH-CONTRACTOR-TENANT-TRUST-RISK-REMEDIATION-01",
                "",
                f"- run marker: `{MARK}`",
                f"- classification: `{classification}`",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (OUT / "watchlist.md").write_text(
        "\n".join(
            [
                "# Watchlist",
                "",
                "- Keep command-center degraded pressure fallback visible and non-calm under load spikes.",
                "- Keep explicit evidence authority semantics on upload response and read models.",
                "- Keep NO_ACCESS history while clearing current exception on regained-access progression.",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"classification": classification, "out": str(OUT)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
