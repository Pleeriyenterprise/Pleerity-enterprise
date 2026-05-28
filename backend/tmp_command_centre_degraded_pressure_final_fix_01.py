#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import httpx

ROOT = Path(__file__).resolve().parent
API = "https://pleerity-enterprise.onrender.com/api"
SLUG = "6fd5ac4c_d35a58ae"
PID = "d35a58ae-3c81-491c-9694-1d021dd3b8ad"
OUT = ROOT / "docs" / "audit" / "prelaunch_contractor_tenant_trust_risk_remediation_01"
EXPECTED_MSG = "Some pressure metrics are still refreshing. Urgent items remain visible below."
MARK = f"CC-DEGRADED-FINAL-FIX-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(name: str, payload: Any) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")


def parse_resp(resp: httpx.Response) -> Any:
    try:
        return resp.json()
    except Exception:
        return resp.text[:700]


def call(method: str, path: str, token: str = "", body: Dict[str, Any] | None = None) -> Dict[str, Any]:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        with httpx.Client(timeout=35) as c:
            r = c.request(method, f"{API}{path}", headers=headers, json=body)
    except httpx.TimeoutException as exc:
        return {"method": method, "path": path, "status": 599, "ok": False, "body": f"timeout: {exc}"}
    return {"method": method, "path": path, "status": r.status_code, "ok": 200 <= r.status_code < 300, "body": parse_resp(r)}


def login(email: str, password: str, *, contractor: bool = False) -> str:
    ep = "/auth/contractor-login" if contractor else "/auth/login"
    with httpx.Client(timeout=35) as c:
        r = c.post(f"{API}{ep}", json={"email": email, "password": password})
        r.raise_for_status()
        return r.json()["access_token"]


def main() -> int:
    cpw = (ROOT / f"docs/audit/ops_verify_01_{SLUG}/.ops_verify_temp_pw.txt").read_text(encoding="utf-8").strip()
    tp = ROOT / f"docs/audit/ops_runtime_07_tenant_portal_{SLUG}/.ops_tenant_temp_pw.txt"
    tpw = tp.read_text(encoding="utf-8").strip() if tp.exists() else "F7OpsWales!Staging2026"
    kpw = (ROOT / f"docs/audit/ops_runtime_03_contractor_{SLUG}/.ops_contractor_temp_pw.txt").read_text(encoding="utf-8").strip()

    client = login("nancy@yopmail.com", cpw)
    tenant = login("f7-ops-wales@yopmail.com", tpw)
    contractor = login("f2-ops-heating-wales@yopmail.com", kpw, contractor=True)

    pressure: Dict[str, Any] = {"captured_at": utc(), "marker": MARK, "checks": [], "evaluation": {}}
    pressure["checks"].append(
        {
            "name": "tenant_seed_1",
            **call(
                "POST",
                "/tenant/report-issue",
                tenant,
                {"property_id": PID, "description": f"{MARK} urgent-seed", "category": "general"},
            ),
        }
    )
    pressure["checks"].append(
        {
            "name": "tenant_seed_2",
            **call(
                "POST",
                "/tenant/report-issue",
                tenant,
                {"property_id": PID, "description": f"{MARK} urgent-seed", "category": "general"},
            ),
        }
    )

    for i in range(8):
        pressure["checks"].append(
            {
                "name": f"command_center_primary_{i+1}",
                **call("GET", "/client/command-center?projection=primary", client),
            }
        )
        time.sleep(0.8)

    rows = [x for x in pressure["checks"] if str(x.get("name", "")).startswith("command_center_primary_")]
    ok_200 = [x for x in rows if int(x.get("status", 0)) == 200 and isinstance(x.get("body"), dict)]
    degraded = [x for x in ok_200 if (x["body"].get("pressure_status") == "degraded")]

    chosen = degraded[0]["body"] if degraded else (ok_200[0]["body"] if ok_200 else {})
    urgent_actions = chosen.get("urgent_actions") or []
    pressure_rows = chosen.get("pressure_urgent_rows") or []
    pressure_count = int(chosen.get("pressure_urgent_count") or 0)
    has_urgent_debt = len(urgent_actions) > 0 or pressure_count > 0

    pressure["evaluation"] = {
        "primary_returns_200": len(ok_200) > 0,
        "degraded_disclosure_present": (
            chosen.get("pressure_degraded") is True
            and chosen.get("pressure_status") == "degraded"
            and str(chosen.get("pressure_message") or "") == EXPECTED_MSG
            and bool(chosen.get("pressure_fallback_reason"))
        ),
        "pressure_rows_count_match_urgent_actions": (pressure_rows == urgent_actions),
        "pressure_count_matches_urgent_open": (pressure_count == int(chosen.get("tasks_digest_summary", {}).get("urgent_count") or 0)),
        "no_false_calm_when_urgent_debt_exists": (not has_urgent_debt) or (len(pressure_rows) > 0 and pressure_count > 0),
        "has_urgent_debt": has_urgent_debt,
    }
    write_json("command_centre_degraded_pressure.json", pressure)

    cross = {"captured_at": utc(), "checks": [], "evaluation": {}}
    cross["checks"].append({"name": "tenant_boundary", **call("GET", "/client/dashboard", tenant)})
    cross["checks"].append(
        {"name": "contractor_boundary", **call("GET", "/contractor/work-orders/00000000-0000-0000-0000-000000000099", contractor)}
    )
    c = {x["name"]: x for x in cross["checks"]}
    cross["evaluation"] = {
        "tenant_boundary_ok": int(c.get("tenant_boundary", {}).get("status", 0)) == 403,
        "contractor_boundary_ok": int(c.get("contractor_boundary", {}).get("status", 0)) == 404,
    }
    write_json("cross_role_smoke.json", cross)

    p = pressure["evaluation"]
    x = cross["evaluation"]
    pressure_pass = all(
        bool(p.get(k))
        for k in (
            "primary_returns_200",
            "degraded_disclosure_present",
            "pressure_rows_count_match_urgent_actions",
            "pressure_count_matches_urgent_open",
            "no_false_calm_when_urgent_debt_exists",
        )
    )
    cross_pass = all(bool(v) for v in x.values())

    if pressure_pass and cross_pass:
        classification = "VERIFIED_OPERATIONALLY"
    elif cross_pass:
        classification = "PARTIAL"
    else:
        classification = "TRUST_RISK_PRESENT"
    write_json(
        "classifications.json",
        {
            "classification": classification,
            "command_centre_degraded_pressure_pass": pressure_pass,
            "cross_role_smoke_pass": cross_pass,
            "finished_at": utc(),
        },
    )
    print(json.dumps({"classification": classification, "out": str(OUT)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
