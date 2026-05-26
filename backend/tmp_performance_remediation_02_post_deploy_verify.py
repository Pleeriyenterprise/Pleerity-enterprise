#!/usr/bin/env python3
"""Post-deploy verification for PRELAUNCH-PERFORMANCE-BACKEND-REMEDIATION-02."""
from __future__ import annotations

import json
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

BASE = os.environ.get("OPS_API_BASE", "https://pleerity-enterprise.onrender.com/api")
FRONTEND = os.environ.get("OPS_FRONTEND", "https://pleerityenterprise.co.uk")
EMAIL = os.environ.get("OPS_CLIENT_EMAIL", "nancy@yopmail.com")
PW = os.environ.get("OPS_CLIENT_PASSWORD", "OpsVerify01!StagingWalk")
PACE_S = float(os.environ.get("OPS_API_PACE_S", "4"))
EXPECTED_COMMIT = os.environ.get("EXPECTED_COMMIT", "ceb653e2")
OUT = Path(__file__).resolve().parent / "docs" / "audit" / "performance_backend_remediation_02"
BASELINE = Path(__file__).resolve().parent / "docs" / "audit" / "performance_runtime_verify_01" / "page_latency_matrix.json"
BASELINE_BROWSER = Path(__file__).resolve().parent / "docs" / "audit" / "performance_runtime_verify_01" / "browser_navigation_timings.json"

DEPLOY_MARKERS = [
    "portal-stale-refresh-banner",
    "fetchOperational",
    "OPERATIONAL_CACHE_KEYS",
    "include_score_headline",
    "projection",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _json_body(r: httpx.Response) -> Dict[str, Any]:
    try:
        return r.json()
    except Exception:
        return {}


def verify_deployment(client: httpx.Client, headers: Dict[str, str]) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "verified_at_utc": utc_now(),
        "expected_commit": EXPECTED_COMMIT,
        "api_base": BASE,
        "frontend": FRONTEND,
        "checks": [],
    }

    health = httpx.get(f"{BASE}/health", timeout=60)
    out["health"] = {"status_code": health.status_code, "body": _json_body(health)}
    out["checks"].append(
        {
            "name": "api_health_200",
            "pass": health.status_code == 200 and (_json_body(health).get("status") == "healthy"),
        }
    )

    ver = httpx.get(f"{BASE}/version", timeout=30)
    ver_body = _json_body(ver)
    out["version"] = {"status_code": ver.status_code, "body": ver_body}
    sha = str(ver_body.get("commit_sha") or "")
    out["commit_sha_from_api"] = sha
    exp7 = EXPECTED_COMMIT[:7]
    sha_match = exp7 in sha or sha.startswith(exp7) or sha == EXPECTED_COMMIT
    out["checks"].append({"name": "commit_sha_matches_expected", "pass": sha_match, "detail": sha})

    try:
        origin = subprocess.check_output(
            ["git", "rev-parse", "--short", EXPECTED_COMMIT],
            cwd=str(OUT.parent.parent.parent),
            text=True,
        ).strip()
        out["local_expected_short"] = origin
    except Exception as exc:
        out["local_git_error"] = str(exc)[:200]

    # Frontend bundle markers
    try:
        fr = httpx.get(FRONTEND, timeout=60, follow_redirects=True)
        html = fr.text
        scripts = re.findall(r'src="(/static/js/[^"]+\.js)"', html)
        marker_hits: Dict[str, List[str]] = {}
        for rel in scripts[:10]:
            try:
                js = httpx.get(f"{FRONTEND}{rel}", timeout=90).text
                for m in DEPLOY_MARKERS:
                    if m in js:
                        marker_hits.setdefault(m, []).append(rel)
            except Exception:
                continue
        out["frontend_status"] = fr.status_code
        out["frontend_marker_hits"] = marker_hits
        out["checks"].append(
            {
                "name": "frontend_fetchOperational_deployed",
                "pass": bool(marker_hits.get("fetchOperational") or marker_hits.get("OPERATIONAL_CACHE_KEYS")),
            }
        )
    except Exception as exc:
        out["frontend_error"] = str(exc)[:300]
        out["checks"].append({"name": "frontend_bundle", "pass": False})

    # Behavioural API probes
    today_default = client.get(f"{BASE}/today/items", headers=headers, timeout=120)
    td = _json_body(today_default)
    items_default = td.get("items")
    out["today_default"] = {
        "status": today_default.status_code,
        "payload_bytes": len(today_default.content),
        "items_is_list": isinstance(items_default, list),
        "items_len": len(items_default) if isinstance(items_default, list) else None,
        "has_tasks_buckets": isinstance(td.get("tasks"), dict),
        "freshness_keys": list((td.get("freshness") or {}).keys()),
    }
    out["checks"].append(
        {
            "name": "today_include_flat_items_false_default",
            "pass": today_default.status_code == 200
            and isinstance(items_default, list)
            and len(items_default) == 0,
        }
    )

    today_flat = client.get(
        f"{BASE}/today/items",
        headers=headers,
        params={"include_flat_items": True},
        timeout=120,
    )
    tf = _json_body(today_flat)
    out["today_with_flat_items"] = {
        "status": today_flat.status_code,
        "payload_bytes": len(today_flat.content),
        "items_len": len(tf.get("items") or []) if isinstance(tf.get("items"), list) else None,
    }
    out["checks"].append(
        {
            "name": "today_include_flat_items_true_populates_items",
            "pass": today_flat.status_code == 200 and len(tf.get("items") or []) > 0,
        }
    )

    docs_list = client.get(
        f"{BASE}/documents",
        headers=headers,
        params={"projection": "list", "limit": 10},
        timeout=120,
    )
    dl = _json_body(docs_list)
    sample = (dl.get("documents") or [{}])[0] if isinstance(dl.get("documents"), list) else {}
    out["documents_list_projection"] = {
        "status": docs_list.status_code,
        "deferred_linkage": sample.get("linkage_projection_deferred"),
        "payload_bytes": len(docs_list.content),
    }
    out["checks"].append(
        {
            "name": "documents_projection_list_supported",
            "pass": docs_list.status_code == 200 and sample.get("linkage_projection_deferred") is True,
        }
    )

    dash_light = client.get(
        f"{BASE}/client/dashboard",
        headers=headers,
        params={"include_score_headline": False},
        timeout=120,
    )
    dash_heavy = client.get(
        f"{BASE}/client/dashboard",
        headers=headers,
        params={"include_score_headline": True},
        timeout=120,
    )
    dl_body = _json_body(dash_light)
    dh_body = _json_body(dash_heavy)
    out["dashboard_lightweight"] = {
        "light_status": dash_light.status_code,
        "light_headline": dl_body.get("compliance_score_headline"),
        "heavy_status": dash_heavy.status_code,
        "heavy_has_score": (dh_body.get("compliance_score_headline") or {}).get("score") is not None
        if isinstance(dh_body.get("compliance_score_headline"), dict)
        else dh_body.get("compliance_score_headline") is not None,
    }
    out["checks"].append(
        {
            "name": "dashboard_include_score_headline_false_default_light",
            "pass": dash_light.status_code == 200 and dl_body.get("compliance_score_headline") is None,
        }
    )

    # Warm cache: two command-center calls
    time.sleep(1)
    cc1 = client.get(f"{BASE}/client/command-center", headers=headers, timeout=120)
    cc2 = client.get(f"{BASE}/client/command-center", headers=headers, timeout=120)
    f1 = ( _json_body(cc1).get("freshness") or {})
    f2 = ( _json_body(cc2).get("freshness") or {})
    out["unified_cache_probe"] = {
        "first_cache_hit": f1.get("cache_hit"),
        "second_cache_hit": f2.get("cache_hit"),
        "second_cached_at": f2.get("cached_at"),
        "second_cache_ttl_seconds": f2.get("cache_ttl_seconds"),
    }
    out["checks"].append(
        {
            "name": "operational_surface_cache_metadata_on_warm_hit",
            "pass": f2.get("cache_hit") is True and f2.get("cached_at") is not None,
        }
    )

    props = client.get(f"{BASE}/client/properties", headers=headers, timeout=60)
    prop_id = None
    if props.status_code == 200:
        plist = _json_body(props).get("properties") or []
        if plist:
            prop_id = plist[0].get("property_id")
    if prop_id:
        detail = client.get(
            f"{BASE}/portfolio/properties/{prop_id}/compliance-detail",
            headers=headers,
            timeout=120,
        )
        out["compliance_detail_probe"] = {
            "property_id": prop_id,
            "status": detail.status_code,
            "payload_bytes": len(detail.content),
            "has_matrix": isinstance(_json_body(detail).get("matrix"), list),
        }
        out["checks"].append(
            {"name": "compliance_detail_route_ok", "pass": detail.status_code == 200}
        )

    passed = sum(1 for c in out["checks"] if c.get("pass"))
    out["checks_passed"] = passed
    out["checks_total"] = len(out["checks"])
    out["deploy_continuity_pass"] = passed == len(out["checks"]) and health.status_code == 200
    return out


def measure_endpoint(
    client: httpx.Client,
    headers: Dict[str, str],
    key: str,
    path: str,
    params: Optional[Dict[str, Any]],
    *,
    label: str,
) -> Dict[str, Any]:
    started = time.perf_counter()
    r = client.get(f"{BASE}{path}", headers=headers, params=params, timeout=120)
    elapsed_ms = round((time.perf_counter() - started) * 1000)
    body = _json_body(r)
    freshness = body.get("freshness") if isinstance(body.get("freshness"), dict) else {}
    trust = body.get("trust_surface_operational_metadata")
    return {
        "surface_key": key,
        "label": label,
        "path": path,
        "params": params,
        "status": r.status_code,
        "latency_ms": elapsed_ms,
        "payload_bytes": len(r.content) if r.content else 0,
        "cache_hit": freshness.get("cache_hit"),
        "cached_at": freshness.get("cached_at"),
        "cache_ttl_seconds": freshness.get("cache_ttl_seconds"),
        "trust_surface_present": trust is not None,
        "error_detail": body.get("detail") if r.status_code >= 400 else None,
    }


def run_api_timings(client: httpx.Client, headers: Dict[str, str]) -> Dict[str, Any]:
    endpoints = [
        ("P1_today_cold", "/today/items", None),
        ("P1_today_warm", "/today/items", None),
        ("P2_command_center_cold", "/client/command-center", None),
        ("P2_command_center_warm", "/client/command-center", None),
        ("P3_dashboard", "/client/dashboard", {"include_score_headline": False}),
        ("P4_properties", "/client/properties", None),
        ("P5_requirements", "/client/requirements", None),
        ("P6_documents", "/documents", {"projection": "list", "limit": 120}),
        ("portfolio_compliance_summary", "/portfolio/compliance-summary", None),
    ]
    rows: List[Dict[str, Any]] = []
    for key, path, params in endpoints:
        time.sleep(PACE_S)
        rows.append(
            measure_endpoint(client, headers, key, path, params, label="cold" if "cold" in key else "warm")
        )

    props = client.get(f"{BASE}/client/properties", headers=headers, timeout=60)
    prop_id = None
    if props.status_code == 200:
        plist = _json_body(props).get("properties") or []
        if plist:
            prop_id = plist[0].get("property_id")
    if prop_id:
        time.sleep(PACE_S)
        rows.append(
            measure_endpoint(
                client,
                headers,
                "P_property_compliance_detail",
                f"/portfolio/properties/{prop_id}/compliance-detail",
                None,
                label="cold",
            )
        )

    baseline = json.loads(BASELINE.read_text(encoding="utf-8")) if BASELINE.is_file() else {}
    before_by = {e["surface_key"]: e for e in baseline.get("endpoints", [])}
    key_map = {
        "P1_today_cold": "P1_today",
        "P2_command_center_cold": "P2_command_center",
        "P3_dashboard": "P3_dashboard",
        "P6_documents": "P6_documents",
    }
    deltas = []
    for row in rows:
        bkey = key_map.get(row["surface_key"])
        b = before_by.get(bkey, {}) if bkey else {}
        deltas.append(
            {
                "surface_key": row["surface_key"],
                "latency_ms_before": b.get("latency_ms"),
                "latency_ms_after": row["latency_ms"],
                "latency_delta_ms": (row["latency_ms"] - b["latency_ms"]) if b.get("latency_ms") else None,
                "payload_bytes_before": b.get("payload_bytes"),
                "payload_bytes_after": row["payload_bytes"],
                "cache_hit": row.get("cache_hit"),
            }
        )

    return {
        "captured_at_utc": utc_now(),
        "environment": BASE,
        "expected_commit": EXPECTED_COMMIT,
        "endpoints": rows,
        "deltas": deltas,
        "baseline_ref": "performance_runtime_verify_01/page_latency_matrix.json",
    }


def assess_api(api: Dict[str, Any], deploy: Dict[str, Any]) -> Dict[str, Any]:
    by_key = {r["surface_key"]: r for r in api.get("endpoints", [])}
    today = by_key.get("P1_today_cold", {})
    cc_cold = by_key.get("P2_command_center_cold", {})
    cc_warm = by_key.get("P2_command_center_warm", {})
    dash = by_key.get("P3_dashboard", {})
    docs = by_key.get("P6_documents", {})

    targets = {
        "today_payload_under_200kb": (today.get("payload_bytes") or 0) < 200_000,
        "today_under_15s": (today.get("latency_ms") or 999999) < 15_000,
        "command_center_cold_under_15s": (cc_cold.get("latency_ms") or 999999) < 15_000,
        "command_center_material_improvement": (cc_cold.get("latency_ms") or 999999) < 45_000,
        "dashboard_under_12s": (dash.get("latency_ms") or 999999) < 12_000,
        "documents_under_12s": (docs.get("latency_ms") or 999999) < 12_000,
        "cache_warm_faster": (cc_warm.get("latency_ms") or 999999) < (cc_cold.get("latency_ms") or 0),
        "cache_hit_on_warm": cc_warm.get("cache_hit") is True,
    }
    material = (
        targets["today_payload_under_200kb"]
        and targets["command_center_material_improvement"]
        and deploy.get("deploy_continuity_pass")
    )
    return {"targets": targets, "api_material_pass": material}


def build_payload_matrix(api: Dict[str, Any]) -> Dict[str, Any]:
    baseline = json.loads(BASELINE.read_text(encoding="utf-8")) if BASELINE.is_file() else {}
    before_by = {e["surface_key"]: e for e in baseline.get("endpoints", [])}
    rows = []
    for row in api.get("endpoints", []):
        sk = row["surface_key"]
        bkey = sk.replace("_cold", "").replace("_warm", "")
        if bkey.startswith("P_property"):
            bkey = None
        b = before_by.get(bkey, {}) if bkey in before_by else {}
        rows.append(
            {
                "endpoint": row["path"],
                "probe_key": sk,
                "before_bytes": b.get("payload_bytes"),
                "after_bytes": row.get("payload_bytes"),
                "reduction_pct": round(
                    100 * (1 - (row.get("payload_bytes") or 0) / b["payload_bytes"]), 1
                )
                if b.get("payload_bytes")
                else None,
            }
        )
    return {"captured_at_utc": utc_now(), "rows": rows}


def authority_regression(api: Dict[str, Any], deploy: Dict[str, Any]) -> Dict[str, Any]:
    checks = [
        {
            "rule": "Today default excludes flat items (no duplicate megabyte payload)",
            "pass": deploy.get("today_default", {}).get("items_len") == 0,
        },
        {
            "rule": "Command Centre trust_surface metadata present",
            "pass": any(
                r.get("trust_surface_present")
                for r in api.get("endpoints", [])
                if "command_center" in r.get("surface_key", "")
            ),
        },
        {
            "rule": "Dashboard light mode omits score headline unless requested",
            "pass": deploy.get("dashboard_lightweight", {}).get("light_headline") is None,
        },
        {
            "rule": "Documents list projection defers linkage without hiding rows",
            "pass": deploy.get("documents_list_projection", {}).get("deferred_linkage") is True,
        },
        {
            "rule": "Cache freshness disclosed on warm hit",
            "pass": deploy.get("unified_cache_probe", {}).get("second_cache_hit") is True,
        },
        {
            "rule": "No 401 on core landlord endpoints after login",
            "pass": all(
                r.get("status") == 200
                for r in api.get("endpoints", [])
                if r.get("surface_key") in (
                    "P1_today_cold",
                    "P2_command_center_cold",
                    "P3_dashboard",
                    "P5_requirements",
                    "P6_documents",
                )
            ),
        },
    ]
    return {
        "checked_at_utc": utc_now(),
        "authority_preserved": all(c["pass"] for c in checks),
        "checks": checks,
    }


def classify_all(deploy: Dict[str, Any], api_assess: Dict[str, Any], browser: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    targets = api_assess.get("targets", {})
    deploy_ok = deploy.get("deploy_continuity_pass")
    api_ok = api_assess.get("api_material_pass")
    browser_ok = False
    cc_primary = None
    if browser and browser.get("cold_navigation"):
        for row in browser["cold_navigation"]:
            if row.get("surface") == "P2_CommandCentre":
                cc_primary = row.get("primary_content_ms")
        browser_ok = (
            cc_primary is not None
            and cc_primary < 15_000
            and all((r.get("shell_visible_ms") or 9999) < 1000 for r in browser["cold_navigation"] if r.get("shell_visible_ms"))
        )

    if not deploy_ok:
        return {"classification": "BLOCKED", "reason": "deploy continuity failed"}
    if not targets.get("today_payload_under_200kb"):
        return {"classification": "PERFORMANCE_DEGRADATION", "reason": "Today payload still exceeds 200KB default"}
    if not targets.get("command_center_cold_under_15s"):
        if (api_assess.get("targets", {}).get("command_center_material_improvement")):
            return {
                "classification": "PARTIAL",
                "reason": "Material API improvement but Command Centre still above 15s browser/API target",
            }
        return {"classification": "PERFORMANCE_DEGRADATION", "reason": "Command Centre still critically slow"}
    if api_ok and browser_ok:
        return {"classification": "VERIFIED_OPERATIONALLY", "reason": "Deploy, API, payload, browser, and authority checks pass"}
    if api_ok:
        return {"classification": "PARTIAL", "reason": "API/payload pass; browser thresholds not fully met"}
    return {"classification": "PERFORMANCE_DEGRADATION", "reason": "API targets not met post-deploy"}


def run_browser_verify() -> Dict[str, Any]:
    """Run Playwright landlord navigation timings into remediation bundle."""
    try:
        from tmp_performance_browser_verify_02 import run_browser_timings  # type: ignore
    except ImportError:
        return {"attempted": False, "error": "browser module not available"}
    return run_browser_timings()


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=120.0) as client:
        login = client.post(f"{BASE}/auth/login", json={"email": EMAIL, "password": PW})
        if login.status_code != 200:
            raise SystemExit(f"login failed {login.status_code}: {login.text[:300]}")
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        deploy = verify_deployment(client, headers)
        (OUT / "deployment_verification.json").write_text(json.dumps(deploy, indent=2), encoding="utf-8")

        api = run_api_timings(client, headers)
        baseline = json.loads(BASELINE.read_text(encoding="utf-8")) if BASELINE.is_file() else {}
        comparison = {"before": baseline, "after": api, "deltas": api.get("deltas", [])}
        (OUT / "before_after_api_timings.json").write_text(json.dumps(comparison, indent=2), encoding="utf-8")
        (OUT / "after_api_timings.json").write_text(json.dumps(api, indent=2), encoding="utf-8")

        payload_matrix = build_payload_matrix(api)
        (OUT / "payload_size_matrix.json").write_text(json.dumps(payload_matrix, indent=2), encoding="utf-8")

        api_assess = assess_api(api, deploy)
        authority = authority_regression(api, deploy)

    browser = run_browser_verify()
    baseline_browser = {}
    if BASELINE_BROWSER.is_file():
        baseline_browser = json.loads(BASELINE_BROWSER.read_text(encoding="utf-8"))
    browser_compare = {
        "before": baseline_browser,
        "after": browser,
        "captured_at_utc": utc_now(),
    }
    (OUT / "before_after_browser_timings.json").write_text(
        json.dumps(browser_compare, indent=2), encoding="utf-8"
    )

    classification = classify_all(deploy, api_assess, browser)
    classification["programme"] = "PRELAUNCH-PERFORMANCE-BACKEND-REMEDIATION-02"
    classification["verified_at_utc"] = utc_now()
    classification["expected_commit"] = EXPECTED_COMMIT
    classification["api_assess"] = api_assess
    (OUT / "classifications.json").write_text(json.dumps(classification, indent=2), encoding="utf-8")
    (OUT / "authority_regression_check.json").write_text(json.dumps(authority, indent=2), encoding="utf-8")

    watchlist = []
    if classification["classification"] != "VERIFIED_OPERATIONALLY":
        watchlist.append("Re-run browser verify after Render deploy completes if API SHA mismatch")
    if not api_assess.get("targets", {}).get("command_center_cold_under_15s"):
        watchlist.append("Profile unified_tasks_for_client on pilot client if Command Centre still >15s")
    (OUT / "watchlist.md").write_text(
        "# Post-deploy watchlist\n\n" + "\n".join(f"- {w}" for w in watchlist) + "\n",
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "classification": classification,
                "deploy_pass": deploy.get("deploy_continuity_pass"),
                "api_assess": api_assess,
            },
            indent=2,
        )
    )
    return 0 if classification.get("classification") == "VERIFIED_OPERATIONALLY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
