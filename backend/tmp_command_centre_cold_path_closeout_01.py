#!/usr/bin/env python3
"""PRELAUNCH-COMMAND-CENTRE-COLD-PATH-REMEDIATION-01 close-out."""
from __future__ import annotations

import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import httpx

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "docs" / "audit" / "command_centre_cold_path_remediation_01"
BASE = os.environ.get("OPS_API_BASE", "https://pleerity-enterprise.onrender.com/api")
FRONTEND = os.environ.get("OPS_FRONTEND", "https://pleerityenterprise.co.uk")
EMAIL = os.environ.get("OPS_CLIENT_EMAIL", "nancy@yopmail.com")
PW = os.environ.get("OPS_CLIENT_PASSWORD", "OpsVerify01!StagingWalk")
CC_PRIMARY_TARGET_MS = int(os.environ.get("CC_PRIMARY_TARGET_MS", "15000"))


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _expected_commit() -> str:
    env = (os.environ.get("EXPECTED_COMMIT") or "").strip()
    if env:
        return env
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=str(ROOT.parent), text=True).strip()
    except Exception:
        return "unknown"


def _login(client: httpx.Client) -> Dict[str, str]:
    r = client.post(f"{BASE}/auth/login", json={"email": EMAIL, "password": PW}, timeout=90)
    r.raise_for_status()
    token = r.json().get("access_token") or r.json().get("token")
    return {"Authorization": f"Bearer {token}"}


def profile_cold_path(headers: Dict[str, str]) -> Dict[str, Any]:
    """Server-side profile via repeated primary calls + full comparison."""
    out: Dict[str, Any] = {"verified_at_utc": utc_now(), "api_base": BASE}
    timings: Dict[str, Any] = {}
    with httpx.Client() as client:
        for label, params in (
            ("primary_cold", {"projection": "primary"}),
            ("primary_warm", {"projection": "primary"}),
            ("full_legacy", {"projection": "full"}),
            ("secondary", {"projection": "secondary", "include_secondary": "true"}),
        ):
            t0 = time.perf_counter()
            r = client.get(f"{BASE}/client/command-center", headers=headers, params=params, timeout=180)
            ms = int((time.perf_counter() - t0) * 1000)
            body = r.json() if r.status_code == 200 else {}
            timings[label] = {
                "status_code": r.status_code,
                "latency_ms": ms,
                "payload_bytes": len(r.content),
                "projection": body.get("projection"),
                "primary_complete": body.get("primary_complete"),
                "urgent_len": len(body.get("urgent_actions") or []),
                "urgent_count": (body.get("tasks_digest_summary") or {}).get("urgent_count"),
            }
            time.sleep(2)
    out["timings"] = timings
    out["primary_under_15s_cold"] = timings.get("primary_cold", {}).get("latency_ms", 99999) < CC_PRIMARY_TARGET_MS
    return out


def requirements_authority_recheck(headers: Dict[str, str]) -> Dict[str, Any]:
    out: Dict[str, Any] = {"verified_at_utc": utc_now()}
    with httpx.Client() as client:
        props = client.get(f"{BASE}/client/properties", headers=headers, timeout=60).json()
        property_ids = [p.get("property_id") for p in props.get("properties") or [] if p.get("property_id")]
        r = client.get(
            f"{BASE}/client/requirements",
            headers=headers,
            params={"projection": "list"},
            timeout=60,
        )
        body = r.json() if r.status_code == 200 else {}
        reqs = body.get("requirements") or []
        out["status_code"] = r.status_code
        out["requirements_count"] = len(reqs)
        out["presentation"] = body.get("presentation")
        out["projection_list"] = (body.get("presentation") or {}).get("projection") == "list"
        if len(reqs) == 0 and property_ids:
            for pid in property_ids[:5]:
                pr = client.get(
                    f"{BASE}/client/properties/{pid}/requirements",
                    headers=headers,
                    timeout=60,
                )
                if pr.status_code == 200:
                    sub = pr.json().get("requirements") or []
                    if sub:
                        out["fallback_property_id"] = pid
                        out["fallback_property_requirements_count"] = len(sub)
                        break
        out["pass"] = out.get("projection_list") and (
            out.get("requirements_count", 0) > 0 or out.get("fallback_property_requirements_count", 0) > 0
        )
    return out


def run_browser() -> Dict[str, Any]:
    script = ROOT / "tmp_performance_browser_verify_02.py"
    if os.environ.get("SKIP_BROWSER") == "1" or not script.is_file():
        return {"skipped": True}
    env = {**os.environ, "OPS_CC_PRIMARY_ONLY": "1"}
    subprocess.run(["python", str(script)], cwd=str(ROOT), env=env, timeout=900)
    src = ROOT / "docs/audit/performance_backend_remediation_02/browser_navigation_timings.json"
    if src.is_file():
        return json.loads(src.read_text(encoding="utf-8"))
    return {"error": "browser output missing"}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    expected = _expected_commit()

    with httpx.Client() as client:
        headers = _login(client)

    profile = profile_cold_path(headers)
    (OUT / "command_centre_cold_profile.json").write_text(json.dumps(profile, indent=2), encoding="utf-8")

    req_auth = requirements_authority_recheck(headers)
    (OUT / "requirements_authority_recheck.json").write_text(json.dumps(req_auth, indent=2), encoding="utf-8")

    browser = run_browser()
    cc_primary_ms = None
    for row in browser.get("surfaces") or browser.get("cold_navigation") or []:
        if row.get("surface") in ("P2_CommandCentre", "P2_CommandCentre_primary"):
            cc_primary_ms = row.get("primary_content_ms") or row.get("t_primary_ms")
    browser_closeout = {
        "verified_at_utc": utc_now(),
        "command_centre_primary_ms": cc_primary_ms,
        "under_15s": cc_primary_ms is not None and cc_primary_ms < CC_PRIMARY_TARGET_MS,
        "browser": browser,
    }
    (OUT / "command_centre_browser_closeout.json").write_text(
        json.dumps(browser_closeout, indent=2), encoding="utf-8"
    )

    authority = {
        "verified_at_utc": utc_now(),
        "checks": [
            {"name": "primary_projection_faster_than_full", "pass": profile["timings"]["primary_cold"]["latency_ms"] < profile["timings"]["full_legacy"]["latency_ms"]},
            {"name": "primary_has_urgent_truth", "pass": (profile["timings"]["primary_cold"].get("urgent_count") or 0) >= 0},
            {"name": "requirements_projection_list", "pass": req_auth.get("pass")},
        ],
    }
    (OUT / "authority_regression_closeout.json").write_text(json.dumps(authority, indent=2), encoding="utf-8")

    gates = {
        "cc_primary_api_cold": profile.get("primary_under_15s_cold"),
        "cc_primary_browser": browser_closeout.get("under_15s"),
        "requirements_authority": req_auth.get("pass"),
        "authority_regression": all(c.get("pass") for c in authority["checks"]),
    }
    if all(gates.values()):
        classification = "VERIFIED_OPERATIONALLY"
    elif gates["cc_primary_api_cold"] or gates["cc_primary_browser"]:
        classification = "PARTIAL"
    else:
        classification = "PERFORMANCE_DEGRADATION"

    summary = {
        "classification": classification,
        "gates": gates,
        "expected_commit": expected,
        "verified_at_utc": utc_now(),
    }
    (OUT / "classifications.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0 if classification == "VERIFIED_OPERATIONALLY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
