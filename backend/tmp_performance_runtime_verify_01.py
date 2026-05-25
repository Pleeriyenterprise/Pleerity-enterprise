#!/usr/bin/env python3
"""PRELAUNCH-PERFORMANCE-RUNTIME-VERIFY-01 — staging API latency sample for landlord surfaces."""
from __future__ import annotations

import json
import time
from pathlib import Path

import httpx

BASE = "https://pleerity-enterprise.onrender.com/api"
EMAIL = "nancy@yopmail.com"
PW = "OpsVerify01!StagingWalk"
OUT = Path(__file__).resolve().parent / "docs" / "audit" / "performance_runtime_verify_01"

ENDPOINTS = [
    ("P1_today", "GET", "/today/items", None),
    ("P2_command_center", "GET", "/client/command-center", None),
    ("P3_dashboard", "GET", "/client/dashboard", None),
    ("P4_properties", "GET", "/client/properties", None),
    ("P5_requirements", "GET", "/client/requirements", None),
    ("P6_documents", "GET", "/documents", None),
    ("P7_rent_summary", "GET", "/client/operations/rent/summary", None),
    ("P7_rent_ledgers", "GET", "/client/operations/rent/ledgers", {"limit": 200}),
    ("portfolio_compliance_summary", "GET", "/portfolio/compliance-summary", None),
]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    timings: list[dict] = []
    with httpx.Client(timeout=90.0) as client:
        t0 = time.perf_counter()
        login = client.post(f"{BASE}/auth/login", json={"email": EMAIL, "password": PW})
        login_ms = round((time.perf_counter() - t0) * 1000)
        if login.status_code != 200:
            raise SystemExit(f"login failed {login.status_code}: {login.text[:200]}")
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        for key, method, path, params in ENDPOINTS:
            started = time.perf_counter()
            r = client.request(method, f"{BASE}{path}", headers=headers, params=params)
            elapsed_ms = round((time.perf_counter() - started) * 1000)
            size = len(r.content) if r.content else 0
            timings.append(
                {
                    "surface_key": key,
                    "method": method,
                    "path": path,
                    "status": r.status_code,
                    "latency_ms": elapsed_ms,
                    "payload_bytes": size,
                }
            )

        # Waterfall: dashboard then requirements (old Properties pattern)
        seq_started = time.perf_counter()
        client.get(f"{BASE}/client/dashboard", headers=headers)
        client.get(f"{BASE}/client/requirements", headers=headers)
        seq_ms = round((time.perf_counter() - seq_started) * 1000)

        # Parallel bundle (new Requirements pattern)
        par_started = time.perf_counter()
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
            futs = [
                ex.submit(client.get, f"{BASE}/client/properties", headers=headers),
                ex.submit(client.get, f"{BASE}/client/requirements", headers=headers),
                ex.submit(client.get, f"{BASE}/documents", headers=headers),
            ]
            for f in futs:
                f.result()
        par_ms = round((time.perf_counter() - par_started) * 1000)

    matrix = {
        "login_ms": login_ms,
        "endpoints": timings,
        "waterfall_dashboard_then_requirements_ms": seq_ms,
        "parallel_properties_requirements_documents_ms": par_ms,
        "captured_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT / "page_latency_matrix.json").write_text(json.dumps(matrix, indent=2), encoding="utf-8")
    print(json.dumps(matrix, indent=2))


if __name__ == "__main__":
    main()
