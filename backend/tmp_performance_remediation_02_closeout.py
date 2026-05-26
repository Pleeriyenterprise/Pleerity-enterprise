#!/usr/bin/env python3
"""Close-out verification for PRELAUNCH-PERFORMANCE-BACKEND-REMEDIATION-02."""
from __future__ import annotations

import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "docs" / "audit" / "performance_backend_remediation_02"
BASE = os.environ.get("OPS_API_BASE", "https://pleerity-enterprise.onrender.com/api")
FRONTEND = os.environ.get("OPS_FRONTEND", "https://pleerityenterprise.co.uk")
EMAIL = os.environ.get("OPS_CLIENT_EMAIL", "nancy@yopmail.com")
PW = os.environ.get("OPS_CLIENT_PASSWORD", "OpsVerify01!StagingWalk")
PACE_S = float(os.environ.get("OPS_API_PACE_S", "3"))
TODAY_PAYLOAD_TARGET_BYTES = int(os.environ.get("TODAY_PAYLOAD_TARGET_BYTES", "204800"))
CC_PRIMARY_TARGET_MS = int(os.environ.get("CC_PRIMARY_TARGET_MS", "15000"))
LIST_PRIMARY_TARGET_MS = int(os.environ.get("LIST_PRIMARY_TARGET_MS", "10000"))


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _expected_commit() -> str:
    env = (os.environ.get("EXPECTED_COMMIT") or "").strip()
    if env:
        return env
    try:
        return (
            subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=str(ROOT.parent), text=True)
            .strip()
        )
    except Exception:
        return "cb4cff71"


def _json_body(r: httpx.Response) -> Dict[str, Any]:
    try:
        return r.json()
    except Exception:
        return {}


def _login(client: httpx.Client) -> Dict[str, str]:
    r = client.post(
        f"{BASE}/auth/login",
        json={"email": EMAIL, "password": PW},
        timeout=90,
    )
    r.raise_for_status()
    token = _json_body(r).get("access_token") or _json_body(r).get("token")
    if not token:
        raise RuntimeError("login missing token")
    return {"Authorization": f"Bearer {token}"}


def _timed_get(
    client: httpx.Client,
    url: str,
    headers: Dict[str, str],
    *,
    params: Optional[Dict[str, Any]] = None,
    timeout: int = 180,
) -> tuple[httpx.Response, int]:
    t0 = time.perf_counter()
    r = client.get(url, headers=headers, params=params, timeout=timeout)
    return r, int((time.perf_counter() - t0) * 1000)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    expected = _expected_commit()
    exp7 = expected[:7]

    deploy: Dict[str, Any] = {
        "verified_at_utc": utc_now(),
        "expected_commit": expected,
        "api_base": BASE,
        "checks": [],
    }
    today_out: Dict[str, Any] = {"verified_at_utc": utc_now(), "target_bytes": TODAY_PAYLOAD_TARGET_BYTES}
    cc_out: Dict[str, Any] = {"verified_at_utc": utc_now(), "target_primary_ms": CC_PRIMARY_TARGET_MS}
    docs_req_out: Dict[str, Any] = {"verified_at_utc": utc_now(), "target_primary_ms": LIST_PRIMARY_TARGET_MS}
    property_out: Dict[str, Any] = {"verified_at_utc": utc_now()}
    authority_out: Dict[str, Any] = {"verified_at_utc": utc_now(), "checks": []}
    browser_out: Dict[str, Any] = {"verified_at_utc": utc_now(), "surfaces": []}

    with httpx.Client() as client:
        ver = httpx.get(f"{BASE}/version", timeout=30)
        ver_body = _json_body(ver)
        sha = str(ver_body.get("commit_sha") or "unknown")
        deploy["version"] = ver_body
        deploy["commit_sha_from_api"] = sha
        sha_ok = exp7 in sha or sha.startswith(exp7) or sha == expected
        deploy["checks"].append(
            {
                "name": "commit_sha_matches_expected",
                "pass": sha_ok,
                "detail": sha,
                "note": "Render must set GIT_COMMIT_SHA or RENDER_GIT_COMMIT",
            }
        )

        headers = _login(client)
        time.sleep(PACE_S)

        r_today, ms_today = _timed_get(client, f"{BASE}/today/items", headers)
        td = _json_body(r_today)
        payload_bytes = len(r_today.content)
        items = td.get("items")
        today_out.update(
            {
                "status_code": r_today.status_code,
                "latency_ms": ms_today,
                "payload_bytes": payload_bytes,
                "under_target": payload_bytes < TODAY_PAYLOAD_TARGET_BYTES,
                "items_is_empty_list": isinstance(items, list) and len(items) == 0,
                "flat_items_included": td.get("flat_items_included"),
                "list_projection": td.get("list_projection"),
                "bucket_continuation": td.get("bucket_continuation"),
                "summary_urgent_count": (td.get("summary") or {}).get("urgent_count"),
                "freshness_keys": list((td.get("freshness") or {}).keys()),
            }
        )
        deploy["checks"].append(
            {
                "name": "today_default_items_empty",
                "pass": isinstance(items, list) and len(items) == 0,
            }
        )
        deploy["checks"].append(
            {
                "name": "today_payload_under_200kb",
                "pass": payload_bytes < TODAY_PAYLOAD_TARGET_BYTES,
                "bytes": payload_bytes,
            }
        )

        time.sleep(PACE_S)
        r_cc, ms_cc = _timed_get(client, f"{BASE}/client/command-center", headers)
        cc_body = _json_body(r_cc)
        cc_out.update(
            {
                "status_code": r_cc.status_code,
                "latency_ms": ms_cc,
                "under_target": ms_cc < CC_PRIMARY_TARGET_MS,
                "secondary_sections_deferred": cc_body.get("secondary_sections_deferred"),
                "cache_hit": (cc_body.get("freshness") or {}).get("cache_hit"),
                "urgent_actions_len": len(cc_body.get("urgent_actions") or []),
            }
        )

        time.sleep(PACE_S)
        r_cc2, ms_cc2 = _timed_get(client, f"{BASE}/client/command-center", headers)
        cc_out["warm_latency_ms"] = ms_cc2

        time.sleep(PACE_S)
        r_docs, ms_docs = _timed_get(
            client, f"{BASE}/documents", headers, params={"projection": "list", "limit": 80}
        )
        docs_body = _json_body(r_docs)
        docs_req_out["documents"] = {
            "latency_ms": ms_docs,
            "under_target": ms_docs < LIST_PRIMARY_TARGET_MS,
            "count": len(docs_body.get("documents") or []),
            "linkage_deferred_sample": any(
                d.get("linkage_projection_deferred") for d in (docs_body.get("documents") or [])[:5]
            ),
        }

        time.sleep(PACE_S)
        r_req, ms_req = _timed_get(
            client, f"{BASE}/client/requirements", headers, params={"projection": "list"}
        )
        req_body = _json_body(r_req)
        docs_req_out["requirements"] = {
            "latency_ms": ms_req,
            "under_target": ms_req < LIST_PRIMARY_TARGET_MS,
            "count": len(req_body.get("requirements") or []),
            "presentation": req_body.get("presentation"),
        }

        time.sleep(PACE_S)
        props = _json_body(_timed_get(client, f"{BASE}/client/properties", headers)[0])
        pid = None
        for p in props.get("properties") or []:
            if p.get("property_id"):
                pid = p["property_id"]
                break
        if pid:
            r_pd, ms_pd = _timed_get(
                client, f"{BASE}/portfolio/properties/{pid}/compliance-detail", headers
            )
            property_out["compliance_detail"] = {
                "property_id": pid,
                "latency_ms": ms_pd,
                "status_code": r_pd.status_code,
                "has_matrix": bool((_json_body(r_pd) or {}).get("matrix")),
            }

        authority_out["checks"] = [
            {
                "name": "today_freshness_present",
                "pass": bool((td.get("freshness") or {})),
            },
            {
                "name": "today_summary_counts_present",
                "pass": isinstance((td.get("summary") or {}).get("urgent_count"), int),
            },
            {
                "name": "command_center_compliance_summary_present",
                "pass": isinstance(cc_body.get("compliance_status_summary"), dict),
            },
            {
                "name": "requirements_list_projection",
                "pass": (req_body.get("presentation") or {}).get("projection") == "list",
            },
        ]

    # Browser harness (optional)
    browser_script = ROOT / "tmp_performance_browser_verify_02.py"
    if os.environ.get("SKIP_BROWSER") != "1" and browser_script.is_file():
        try:
            subprocess.run(
                [os.environ.get("PYTHON", "python"), str(browser_script)],
                cwd=str(ROOT),
                check=False,
                timeout=900,
            )
            bt_path = OUT / "browser_navigation_timings.json"
            if bt_path.is_file():
                browser_out = json.loads(bt_path.read_text(encoding="utf-8"))
        except Exception as exc:
            browser_out["error"] = str(exc)[:300]

    gates = {
        "deploy_verified": all(c.get("pass") for c in deploy["checks"] if c["name"] == "commit_sha_matches_expected"),
        "today_payload": today_out.get("under_target") and today_out.get("items_is_empty_list"),
        "command_centre_api": cc_out.get("under_target"),
        "documents_requirements_api": (
            (docs_req_out.get("documents") or {}).get("under_target")
            and (docs_req_out.get("requirements") or {}).get("under_target")
        ),
        "property_detail_api": bool(property_out.get("compliance_detail")),
        "authority": all(c.get("pass") for c in authority_out.get("checks") or []),
    }
    cc_browser_ms = None
    for row in browser_out.get("surfaces") or browser_out.get("results") or []:
        if row.get("surface") in ("P2_CommandCentre", "CommandCentre"):
            cc_browser_ms = row.get("primary_ms") or row.get("t_primary_ms")
        if row.get("surface") == "P7_PropertyDetail":
            property_out["browser_primary_ms"] = row.get("primary_ms") or row.get("t_primary_ms")

    if cc_browser_ms is not None:
        cc_out["browser_primary_ms"] = cc_browser_ms
        cc_out["browser_under_target"] = cc_browser_ms < CC_PRIMARY_TARGET_MS

    if gates["deploy_verified"] and gates["today_payload"] and gates["command_centre_api"] and gates["documents_requirements_api"] and gates["property_detail_api"] and gates["authority"]:
        if cc_out.get("browser_under_target") is False and cc_browser_ms:
            classification = "PARTIAL"
        else:
            classification = "VERIFIED_OPERATIONALLY"
    elif gates["today_payload"] or cc_out.get("warm_latency_ms", 99999) < CC_PRIMARY_TARGET_MS:
        classification = "PARTIAL"
    else:
        classification = "PERFORMANCE_DEGRADATION"

    push_result: Dict[str, Any] = {"attempted": False}
    if os.environ.get("CLOSEOUT_PUSH") == "1":
        push_result["attempted"] = True
        try:
            subprocess.run(["git", "push", "origin", "HEAD"], cwd=str(ROOT.parent), check=True, timeout=120)
            push_result["pushed"] = True
        except Exception as exc:
            push_result["pushed"] = False
            push_result["error"] = str(exc)[:200]

    (OUT / "deployment_verification_closeout.json").write_text(
        json.dumps(deploy, indent=2), encoding="utf-8"
    )
    (OUT / "today_payload_closeout.json").write_text(json.dumps(today_out, indent=2), encoding="utf-8")
    (OUT / "command_centre_latency_closeout.json").write_text(json.dumps(cc_out, indent=2), encoding="utf-8")
    (OUT / "documents_requirements_latency_closeout.json").write_text(
        json.dumps(docs_req_out, indent=2), encoding="utf-8"
    )
    (OUT / "property_detail_closeout.json").write_text(json.dumps(property_out, indent=2), encoding="utf-8")
    (OUT / "authority_regression_closeout.json").write_text(
        json.dumps(authority_out, indent=2), encoding="utf-8"
    )
    if browser_out.get("surfaces") or browser_out.get("results"):
        (OUT / "browser_navigation_timings_closeout.json").write_text(
            json.dumps(browser_out, indent=2), encoding="utf-8"
        )

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
