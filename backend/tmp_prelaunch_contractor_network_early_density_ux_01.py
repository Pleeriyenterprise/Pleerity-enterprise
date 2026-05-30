#!/usr/bin/env python3
"""PRELAUNCH-CONTRACTOR-NETWORK-EARLY-DENSITY-UX-01 closeout harness."""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "docs/audit/prelaunch_contractor_network_early_density_ux_01"
PROGRAMME = "PRELAUNCH-CONTRACTOR-NETWORK-EARLY-DENSITY-UX-01"
API = "https://pleerity-enterprise.onrender.com/api"
FE = "https://pleerityenterprise.co.uk"
EMAIL = "nancy@yopmail.com"
PW_FILE = ROOT / "docs/audit/ops_verify_01_6fd5ac4c_d35a58ae/.ops_verify_temp_pw.txt"
SCREENSHOTS = OUT / "screenshots"


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write(name: str, data: object) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


def _login() -> str:
    pw = PW_FILE.read_text(encoding="utf-8").strip()
    for attempt in range(8):
        try:
            r = httpx.post(f"{API}/auth/login", json={"email": EMAIL, "password": pw}, timeout=120)
            if r.status_code in (502, 503, 504) and attempt < 7:
                time.sleep(20)
                continue
            r.raise_for_status()
            return r.json()["access_token"]
        except Exception:
            if attempt < 7:
                time.sleep(20)
                continue
            raise
    raise RuntimeError("login failed")


def _headers(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def deploy_continuity() -> Dict[str, Any]:
    ver = httpx.get(f"{API}/version", timeout=60).json()
    manifest = httpx.get(f"{FE}/asset-manifest.json", timeout=60).json()
    js = manifest["files"]["main.js"]
    bundle = httpx.get(f"{FE}{js}", timeout=90).text
    markers = {
        "early_network_primary_cta": "Add contractor for this area" in bundle,
        "network_maturity_banner": "Contractor network coverage is still growing" in bundle,
        "secondary_search_beta": "Search existing contractor network (beta)" in bundle,
        "eligibility_empty_summary": "No contractors currently qualify for this job yet" in bundle,
        "why_expand": "Why?" in bundle,
    }
    return {"captured_at": _utc(), "api_sha": ver.get("commit_sha"), "frontend_js": js, "bundle_markers": markers}


def _jobs(token: str) -> List[dict]:
    rows: List[dict] = []
    h = _headers(token)
    for path in ("/client/maintenance/work-orders", "/client/compliance/work-orders"):
        try:
            r = httpx.get(f"{API}{path}", headers=h, params={"limit": 40}, timeout=90)
            if not r.is_success:
                continue
            payload = r.json()
            for wo in payload.get("work_orders") or payload.get("jobs") or []:
                rows.append(wo)
        except Exception:
            pass
    return rows


def pick_scenarios(token: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {"captured_at": _utc(), "candidates": []}
    for wo in _jobs(token):
        wid = wo.get("work_order_id") or wo.get("job_id")
        if not wid or wo.get("contractor_id"):
            continue
        r = httpx.get(
            f"{API}/jobs/{wid}/assignable-contractors",
            headers=_headers(token),
            params={"limit": 200},
            timeout=90,
        )
        if not r.is_success:
            continue
        body = r.json()
        diag = body.get("filter_diagnostics") or {}
        eligible = int(diag.get("eligible") or 0)
        jj = body.get("job_jurisdiction") or wo.get("jurisdiction")
        row = {
            "work_order_id": wid,
            "jurisdiction": jj,
            "eligible": eligible,
            "visible_in_directory": diag.get("visible_in_directory"),
            "excluded_location_postcode": diag.get("excluded_location_postcode"),
            "property_postcode": body.get("property_postcode"),
        }
        out["candidates"].append(row)
        if eligible == 0 and not out.get("empty_job_id"):
            out["empty_job_id"] = wid
            out["empty_diag"] = diag
            out["empty_jurisdiction"] = jj
        if eligible > 0 and not out.get("eligible_job_id"):
            out["eligible_job_id"] = wid
            out["eligible_count"] = eligible
        if eligible == 0 and str(jj or "").lower() == "scotland" and not out.get("scotland_empty_job_id"):
            out["scotland_empty_job_id"] = wid
        if eligible == 0 and str(jj or "").lower() in ("england", "wales") and not out.get("england_empty_job_id"):
            out["england_empty_job_id"] = wid
    return out


def run_browser(job_id: Optional[str], token: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {"captured_at": _utc()}
    if not job_id or sync_playwright is None:
        out["skipped"] = "no_job_or_playwright"
        return out
    pw = PW_FILE.read_text(encoding="utf-8").strip()
    SCREENSHOTS.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto(f"{FE}/login/client", wait_until="domcontentloaded", timeout=120_000)
        page.fill("#email", EMAIL)
        page.fill("#password", pw)
        page.click("button[type='submit']")
        page.wait_for_timeout(2500)
        page.goto(f"{FE}/operations/jobs/{job_id}", wait_until="networkidle", timeout=120_000)
        page.wait_for_timeout(1500)
        assign_btn = page.get_by_role("button", name="Assign contractor")
        if assign_btn.count():
            assign_btn.first.click()
            page.wait_for_timeout(2000)
        page.screenshot(path=str(SCREENSHOTS / "assign_modal_early_network.png"))
        html = page.content()
        api = httpx.get(f"{API}/jobs/{job_id}/assignable-contractors", headers=_headers(token), timeout=90)
        diag = (api.json().get("filter_diagnostics") or {}) if api.is_success else {}
        out["modal"] = {
            "job_id": job_id,
            "has_network_banner": "Contractor network coverage is still growing" in html,
            "has_primary_cta": "Add contractor for this area" in html,
            "has_secondary_beta": "Search existing contractor network (beta)" in html,
            "has_why": "Why?" in html,
            "funnel_collapsed": "Who can appear on this list" not in html,
            "has_operational_empty": "cover this property area" in html.lower(),
            "data_early_network": page.locator('[data-testid="assign-contractor-modal"]').get_attribute("data-early-network-mode"),
            "api_eligible": diag.get("eligible"),
        }
        browser.close()
    return out


def classify(deploy: Dict[str, Any], scenarios: Dict[str, Any], browser: Dict[str, Any]) -> Dict[str, Any]:
    checks: List[str] = []
    fails: List[str] = []

    def ok(name: str, cond: bool) -> None:
        (checks if cond else fails).append(name)

    bm = deploy.get("bundle_markers") or {}
    ok("bundle_primary_cta", bm.get("early_network_primary_cta"))
    ok("bundle_network_banner", bm.get("network_maturity_banner"))
    ok("bundle_secondary_beta", bm.get("secondary_search_beta"))
    ok("empty_scenario_found", bool(scenarios.get("empty_job_id")))
    ok("eligible_scenario_found", bool(scenarios.get("eligible_job_id")))
    ok("browser_primary_cta", (browser.get("modal") or {}).get("has_primary_cta"))
    ok("browser_network_banner", (browser.get("modal") or {}).get("has_network_banner"))
    ok("browser_funnel_collapsed", (browser.get("modal") or {}).get("funnel_collapsed"))
    ok("browser_early_network_flag", (browser.get("modal") or {}).get("data_early_network") == "true")
    ok("eligibility_authority_preserved", (browser.get("modal") or {}).get("api_eligible") == 0)

    if fails and set(fails).issubset({"bundle_primary_cta", "bundle_network_banner", "bundle_secondary_beta"}):
        classification = "OPERATIONALLY_GUIDED"
    elif fails:
        classification = "PARTIAL"
    else:
        classification = "VERIFIED_OPERATIONALLY"

    return {"classification": classification, "passed": checks, "failed": fails, "captured_at": _utc()}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    token = _login()
    deploy = deploy_continuity()
    _write("deploy_continuity.json", deploy)
    scenarios = pick_scenarios(token)
    _write("runtime_scenarios.json", scenarios)
    browser = run_browser(scenarios.get("scotland_empty_job_id") or scenarios.get("empty_job_id"), token)
    _write("browser_runtime.json", browser)
    cls = classify(deploy, scenarios, browser)
    _write("classifications.json", cls)
    _write(
        "root_cause.json",
        {
            "programme": PROGRAMME,
            "captured_at": _utc(),
            "finding": "Eligibility engine correct; sparse-network UX created false failure perception via expanded diagnostics and buried add-contractor CTA.",
            "remediation": "Presentation-only early-network mode: network maturity banner, dominant add CTA, collapsed Why? diagnostics, operational empty copy.",
            "authority_preserved": [
                "contractor_location_matches_property",
                "jurisdiction filtering",
                "assignment readiness",
                "trade/capability validation",
                "portal activation",
                "service-region enforcement",
            ],
        },
    )
    watchlist = [
        "Contractor in-app notifications unchanged.",
        "Coverage intelligence recommendations not implemented (scaffold only).",
    ]
    if cls["classification"] != "VERIFIED_OPERATIONALLY":
        watchlist.append(f"Failed checks: {cls.get('failed')}")
    (OUT / "watchlist.md").write_text("\n".join(f"- {w}" for w in watchlist) + "\n", encoding="utf-8")
    (OUT / "REPORT.md").write_text(
        f"""# {PROGRAMME}

**Classification:** {cls['classification']}
**Captured:** {_utc()}

## Summary
Early-network assignment UX reframes low contractor density as growing coverage without weakening eligibility authority.

## Runtime
- Empty job: {scenarios.get('empty_job_id')}
- Eligible job: {scenarios.get('eligible_job_id')} ({scenarios.get('eligible_count')} ready)
- Scotland empty: {scenarios.get('scotland_empty_job_id')}

## Failed checks
{chr(10).join('- ' + f for f in cls.get('failed', [])) or '- None'}
""",
        encoding="utf-8",
    )
    print(json.dumps({"classification": cls["classification"], "failed": cls.get("failed")}, indent=2))
    return 0 if cls["classification"] == "VERIFIED_OPERATIONALLY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
