#!/usr/bin/env python3
"""PRELAUNCH-PERFORMANCE-BACKEND-REMEDIATION-02 — staging API latency (after fixes)."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import httpx

BASE = os.environ.get("OPS_API_BASE", "https://pleerity-enterprise.onrender.com/api")
EMAIL = os.environ.get("OPS_CLIENT_EMAIL", "nancy@yopmail.com")
PW = os.environ.get("OPS_CLIENT_PASSWORD", "OpsVerify01!StagingWalk")
PACE_S = float(os.environ.get("OPS_API_PACE_S", "6"))
OUT = Path(__file__).resolve().parent / "docs" / "audit" / "performance_backend_remediation_02"
BASELINE = Path(__file__).resolve().parent / "docs" / "audit" / "performance_runtime_verify_01" / "page_latency_matrix.json"

ENDPOINTS = [
    ("P1_today", "GET", "/today/items", None),
    ("P2_command_center", "GET", "/client/command-center", None),
    ("P3_dashboard", "GET", "/client/dashboard", {"include_score_headline": False}),
    ("P4_properties", "GET", "/client/properties", None),
    ("P5_requirements", "GET", "/client/requirements", None),
    ("P6_documents", "GET", "/documents", {"projection": "list", "limit": 120}),
    ("portfolio_compliance_summary", "GET", "/portfolio/compliance-summary", None),
]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    timings: list[dict] = []
    with httpx.Client(timeout=120.0) as client:
        login = client.post(f"{BASE}/auth/login", json={"email": EMAIL, "password": PW})
        if login.status_code != 200:
            raise SystemExit(f"login failed {login.status_code}: {login.text[:300]}")
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        for key, method, path, params in ENDPOINTS:
            time.sleep(PACE_S)
            started = time.perf_counter()
            r = client.request(method, f"{BASE}{path}", headers=headers, params=params)
            elapsed_ms = round((time.perf_counter() - started) * 1000)
            timings.append(
                {
                    "surface_key": key,
                    "method": method,
                    "path": path,
                    "params": params,
                    "status": r.status_code,
                    "latency_ms": elapsed_ms,
                    "payload_bytes": len(r.content) if r.content else 0,
                    "cache_hit": (r.json().get("freshness") or {}).get("cache_hit")
                    if r.headers.get("content-type", "").startswith("application/json")
                    else None,
                }
            )

        time.sleep(PACE_S)
        par_started = time.perf_counter()
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
            futs = [
                ex.submit(
                    client.get,
                    f"{BASE}/client/properties",
                    headers=headers,
                ),
                ex.submit(
                    client.get,
                    f"{BASE}/client/requirements",
                    headers=headers,
                ),
                ex.submit(
                    client.get,
                    f"{BASE}/documents",
                    headers=headers,
                    params={"projection": "list", "limit": 120},
                ),
            ]
            for f in futs:
                f.result()
        par_ms = round((time.perf_counter() - par_started) * 1000)

    after = {
        "endpoints": timings,
        "parallel_properties_requirements_documents_ms": par_ms,
        "captured_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "environment": BASE,
    }
    (OUT / "after_api_timings.json").write_text(json.dumps(after, indent=2), encoding="utf-8")

    baseline = {}
    if BASELINE.is_file():
        baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    comparison = {"before": baseline, "after": after, "deltas": []}
    before_by = {e["surface_key"]: e for e in baseline.get("endpoints", [])}
    for row in timings:
        b = before_by.get(row["surface_key"], {})
        comparison["deltas"].append(
            {
                "surface_key": row["surface_key"],
                "latency_ms_before": b.get("latency_ms"),
                "latency_ms_after": row["latency_ms"],
                "latency_delta_ms": (row["latency_ms"] - b["latency_ms"]) if b.get("latency_ms") else None,
                "payload_bytes_before": b.get("payload_bytes"),
                "payload_bytes_after": row["payload_bytes"],
            }
        )
    (OUT / "before_after_api_timings.json").write_text(
        json.dumps(comparison, indent=2), encoding="utf-8"
    )
    print(json.dumps(comparison, indent=2))


if __name__ == "__main__":
    main()
