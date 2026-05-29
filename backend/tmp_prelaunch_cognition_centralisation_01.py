#!/usr/bin/env python3
"""PRELAUNCH-COGNITION-CENTRALISATION-01 runtime verification harness."""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import httpx

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "docs/audit/prelaunch_cognition_centralisation_01"
PROGRAMME = "PRELAUNCH-COGNITION-CENTRALISATION-01"
API = "https://pleerity-enterprise.onrender.com/api"
FRONTEND = "https://pleerityenterprise.co.uk"
EMAIL = "nancy@yopmail.com"
PW_FILE = ROOT / "docs/audit/ops_verify_01_6fd5ac4c_d35a58ae/.ops_verify_temp_pw.txt"


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write(name: str, data: Any) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


def _login() -> str:
    pw = PW_FILE.read_text(encoding="utf-8").strip()
    r = httpx.post(f"{API}/auth/login", json={"email": EMAIL, "password": pw}, timeout=120)
    r.raise_for_status()
    return r.json()["access_token"]


def api_cognition_parity(token: str) -> Dict[str, Any]:
    h = {"Authorization": f"Bearer {token}"}
    list_r = httpx.get(f"{API}/client/requirements", headers=h, params={"projection": "list"}, timeout=120)
    full_r = httpx.get(f"{API}/client/requirements", headers=h, params={"projection": "full"}, timeout=120)
    list_body = list_r.json() if list_r.is_success else {}
    full_body = full_r.json() if full_r.is_success else {}
    list_reqs = list_body.get("requirements") or []
    full_reqs = full_body.get("requirements") or []
    lr = list_reqs[0] if list_reqs else {}
    fr = full_reqs[0] if full_reqs else {}
    return {
        "captured_at": _utc(),
        "list_count": len(list_reqs),
        "full_count": len(full_reqs),
        "list_has_cognition": bool(lr.get("operational_cognition")),
        "full_has_cognition": bool(fr.get("operational_cognition")),
        "list_enrichment_deferred": list_body.get("enrichment_deferred"),
        "full_list_guidance_label": ((fr.get("operational_cognition") or {}).get("list_guidance") or {}).get(
            "recommended_action_label"
        ),
        "projection_drift_risk": bool(fr.get("operational_cognition")) and not lr.get("operational_cognition"),
    }


def api_entity_cognition(token: str) -> Dict[str, Any]:
    h = {"Authorization": f"Bearer {token}"}
    out: Dict[str, Any] = {"captured_at": _utc(), "surfaces": []}
    wo = httpx.get(f"{API}/client/maintenance/work-orders", headers=h, params={"limit": 3}, timeout=120)
    if wo.is_success:
        rows = (wo.json().get("work_orders") or wo.json().get("items") or [])[:1]
        if rows:
            out["surfaces"].append(
                {
                    "surface": "jobs",
                    "has_operational_cognition": bool(rows[0].get("operational_cognition")),
                    "list_guidance": bool((rows[0].get("operational_cognition") or {}).get("list_guidance")),
                }
            )
    issues = httpx.get(f"{API}/client/maintenance/issues", headers=h, params={"limit": 3}, timeout=120)
    if issues.is_success:
        rows = issues.json().get("issues") or []
        if rows:
            out["surfaces"].append(
                {
                    "surface": "issues",
                    "has_operational_cognition": bool(rows[0].get("operational_cognition")),
                    "has_continuation": bool(rows[0].get("operational_continuation")),
                }
            )
    rs = httpx.get(f"{API}/client/maintenance/risk-signals", headers=h, params={"limit": 3}, timeout=120)
    if rs.is_success:
        rows = rs.json().get("risk_signals") or rs.json().get("signals") or []
        if rows:
            out["surfaces"].append(
                {
                    "surface": "risk_signals",
                    "has_operational_cognition": bool(rows[0].get("operational_cognition")),
                }
            )
    return out


def browser_checks() -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "captured_at": _utc(),
        "login_ok": False,
        "bundle_has_authority_contract": False,
        "today_hero": False,
        "today_cognition_chips": 0,
        "today_enrichment_notice": False,
        "requirements_operational_in_bundle": False,
    }
    if sync_playwright is None:
        out["notes"] = ["playwright_unavailable"]
        return out
    manifest = httpx.get(f"{FRONTEND}/asset-manifest.json", timeout=60).json()
    main_js = httpx.get(f"{FRONTEND}{manifest['files']['main.js']}", timeout=120).text
    out["bundle_has_authority_contract"] = "operationalAuthorityContract" in main_js or "resolveCanonicalPrimaryAction" in main_js
    out["requirements_operational_in_bundle"] = "requirementsOperational" in main_js

    pw = PW_FILE.read_text(encoding="utf-8").strip()
    with sync_playwright() as p:
        page = p.chromium.launch(headless=True).new_context(viewport={"width": 1440, "height": 900}).new_page()
        page.goto(f"{FRONTEND}/login/client", timeout=120_000)
        page.locator("#email").fill(EMAIL)
        page.locator("#password").fill(pw)
        page.locator('button[type="submit"]').click()
        page.wait_for_timeout(6000)
        out["login_ok"] = "login" not in page.url.lower()
        page.goto(f"{FRONTEND}/today", wait_until="networkidle", timeout=120_000)
        page.wait_for_timeout(5000)
        out["today_hero"] = page.locator('[data-testid="today-execution-hero"]').count() > 0
        out["today_cognition_chips"] = page.locator('[data-testid="list-cognition-chip"]').count()
        out["today_enrichment_notice"] = page.locator('[data-testid="today-requirements-enrichment-notice"]').count() > 0
        out["false_calm_notice"] = page.locator('[data-testid="today-false-calm-notice"]').count() > 0
        out["error_boundary"] = "Something went wrong" in page.inner_text("body")
    return out


def classify(api_parity: Dict[str, Any], entities: Dict[str, Any], browser: Dict[str, Any]) -> Dict[str, Any]:
    blockers: List[str] = []
    if not api_parity.get("full_has_cognition"):
        blockers.append("full_projection_missing_cognition")
    if browser.get("error_boundary"):
        blockers.append("today_error_boundary")
    if not browser.get("today_hero") and not browser.get("false_calm_notice"):
        blockers.append("today_no_hero_without_disclosure")
    if api_parity.get("projection_drift_risk") and not browser.get("requirements_operational_in_bundle"):
        blockers.append("projection_drift_unmitigated")

    if blockers:
        label = "PARTIAL"
        if "projection_drift_unmitigated" in blockers or "full_projection_missing_cognition" in blockers:
            label = "COGNITION_FRAGMENTATION_RISK"
    else:
        label = "PARTIAL"  # requirementTakeActionResolver fallback still exists — not TRUST_HARDENED

    return {
        "classification": label,
        "blockers": blockers,
        "evaluated_at": _utc(),
        "push_audit_artifacts_allowed": True,
    }


def main() -> int:
    print(f"[{PROGRAMME}] {_utc()}")
    token = _login()
    parity = api_cognition_parity(token)
    entities = api_entity_cognition(token)
    browser = browser_checks()
    runtime = {
        "captured_at": _utc(),
        "api_projection_parity": parity,
        "api_entity_cognition": entities,
        "browser": browser,
        "contradictions": [],
        "notes": [
            "CC/Dashboard migrated to requirementsOperational in this programme",
            "primaryActionResolver now prefers operational_cognition before continuation/create fallbacks",
        ],
    }
    _write("runtime_cognition_consistency.json", runtime)
    cls = classify(parity, entities, browser)
    _write("classifications.json", cls)
    print(json.dumps(cls, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
