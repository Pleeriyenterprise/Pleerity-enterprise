#!/usr/bin/env python3
"""Final Command Centre cold-path closeout."""
from __future__ import annotations

import json
import os
import re
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
CC_TARGET_MS = int(os.environ.get("CC_PRIMARY_TARGET_MS", "15000"))


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _login() -> Dict[str, str]:
    r = httpx.post(f"{BASE}/auth/login", json={"email": EMAIL, "password": PW}, timeout=90)
    r.raise_for_status()
    token = r.json().get("access_token") or r.json().get("token")
    return {"Authorization": f"Bearer {token}"}


def frontend_deploy() -> Dict[str, Any]:
    html = httpx.get(FRONTEND, timeout=60, follow_redirects=True).text
    scripts = re.findall(r'src="(/static/js/[^"]+\.js)"', html)
    markers = [
        "getCommandCenterPrimary",
        "getCommandCenterSecondary",
        "command-center-primary-ready",
        "command-center-secondary-risks-loading",
    ]
    hits: Dict[str, list] = {}
    for rel in scripts[:10]:
        try:
            js = httpx.get(f"{FRONTEND}{rel}", timeout=90).text
        except Exception:
            continue
        for m in markers:
            if m in js:
                hits.setdefault(m, []).append(rel)
    return {
        "verified_at_utc": utc_now(),
        "frontend": FRONTEND,
        "scripts": scripts[:5],
        "marker_hits": hits,
        "pass": all(m in hits for m in markers[:3]),
    }


def api_profile(headers: Dict[str, str]) -> Dict[str, Any]:
    timings: Dict[str, Any] = {}
    with httpx.Client() as client:
        for label, params in (
            ("primary_cold", {"projection": "primary"}),
            ("primary_warm", {"projection": "primary"}),
            ("full_legacy", {"projection": "full"}),
        ):
            t0 = time.perf_counter()
            r = client.get(f"{BASE}/client/command-center", headers=headers, params=params, timeout=180)
            ms = int((time.perf_counter() - t0) * 1000)
            body = r.json() if r.status_code == 200 else {}
            timings[label] = {
                "latency_ms": ms,
                "payload_bytes": len(r.content),
                "projection": body.get("projection"),
                "cache_hit": (body.get("freshness") or {}).get("cache_hit"),
                "urgent_count": (body.get("tasks_digest_summary") or {}).get("urgent_count"),
                "urgent_len": len(body.get("urgent_actions") or []),
                "continuation": (body.get("tasks_digest_summary") or {}).get("urgent_continuation"),
            }
            time.sleep(2)
    cold = timings["primary_cold"]["latency_ms"]
    warm = timings["primary_warm"]["latency_ms"]
    return {
        "verified_at_utc": utc_now(),
        "timings": timings,
        "primary_cold_under_15s": cold < CC_TARGET_MS,
        "warm_faster_than_cold": warm < cold,
        "cache_disclosed_on_warm": timings["primary_warm"].get("cache_hit") is True,
    }


def authority(headers: Dict[str, str]) -> Dict[str, Any]:
    with httpx.Client() as client:
        r = client.get(f"{BASE}/client/command-center", headers=headers, params={"projection": "primary"}, timeout=180)
        body = r.json()
        summary = body.get("tasks_digest_summary") or {}
        urgent_len = len(body.get("urgent_actions") or [])
        urgent_count = summary.get("urgent_count") or 0
        cont = summary.get("urgent_continuation") or 0
        req = client.get(f"{BASE}/client/requirements", headers=headers, params={"projection": "list"}, timeout=60)
        req_body = req.json() if req.status_code == 200 else {}
    checks = [
        {"name": "urgent_count_truthful_gte_rows", "pass": urgent_count >= urgent_len},
        {"name": "continuation_when_capped", "pass": cont > 0 or urgent_count <= urgent_len},
        {"name": "primary_complete", "pass": body.get("primary_complete") is True},
        {"name": "secondary_deferred", "pass": body.get("secondary_sections_deferred") is True},
        {"name": "freshness_present", "pass": bool(body.get("freshness"))},
        {"name": "requirements_projection_list", "pass": (req_body.get("presentation") or {}).get("projection") == "list"},
    ]
    return {"verified_at_utc": utc_now(), "checks": checks, "pass": all(c["pass"] for c in checks)}


def browser() -> Dict[str, Any]:
    if os.environ.get("SKIP_BROWSER") == "1":
        return {"skipped": True}
    subprocess.run([os.environ.get("PYTHON", "python"), str(ROOT / "tmp_performance_browser_verify_02.py")], cwd=str(ROOT), timeout=900)
    bt_path = ROOT / "docs/audit/performance_backend_remediation_02/browser_navigation_timings_closeout.json"
    if not bt_path.is_file():
        return {"error": "browser timings missing"}
    bt = json.loads(bt_path.read_text(encoding="utf-8"))
    cc = next((x for x in bt.get("surfaces", []) if x.get("surface") == "P2_CommandCentre"), None)
    shell = cc.get("shell_visible_ms") if cc else None
    primary = cc.get("primary_content_ms") if cc else None
    return {
        "verified_at_utc": utc_now(),
        "command_centre": cc,
        "shell_under_1s": shell is not None and shell < 1000,
        "primary_under_15s": primary is not None and primary < CC_TARGET_MS,
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    deploy = frontend_deploy()
    (OUT / "deployment_verification.json").write_text(json.dumps(deploy, indent=2), encoding="utf-8")

    headers = _login()
    profile = api_profile(headers)
    (OUT / "command_centre_cold_profile.json").write_text(json.dumps(profile, indent=2), encoding="utf-8")

    auth = authority(headers)
    (OUT / "authority_regression_closeout.json").write_text(json.dumps(auth, indent=2), encoding="utf-8")

    brow = browser()
    (OUT / "command_centre_browser_closeout.json").write_text(json.dumps(brow, indent=2), encoding="utf-8")

    gates = {
        "frontend_deploy": deploy.get("pass"),
        "api_primary_cold": profile.get("primary_cold_under_15s"),
        "api_cache_disclosed": profile.get("cache_disclosed_on_warm"),
        "browser_primary": brow.get("primary_under_15s"),
        "authority": auth.get("pass"),
    }
    if all(gates.values()):
        classification = "VERIFIED_OPERATIONALLY"
    elif gates["browser_primary"] or gates["api_primary_cold"] or profile.get("warm_faster_than_cold"):
        classification = "PARTIAL"
    else:
        classification = "PERFORMANCE_DEGRADATION"

    summary = {"classification": classification, "gates": gates, "verified_at_utc": utc_now()}
    (OUT / "classifications.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0 if classification == "VERIFIED_OPERATIONALLY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
