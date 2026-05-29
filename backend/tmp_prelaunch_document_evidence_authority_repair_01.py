#!/usr/bin/env python3
"""PRELAUNCH-DOCUMENT-EVIDENCE-AUTHORITY-REPAIR-01 verification harness."""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "docs/audit/prelaunch_document_evidence_authority_repair_01"
PROGRAMME = "PRELAUNCH-DOCUMENT-EVIDENCE-AUTHORITY-REPAIR-01"
API = "https://pleerity-enterprise.onrender.com/api"
FE = "https://pleerityenterprise.co.uk"
EMAIL = "nancy@yopmail.com"
PW_FILE = ROOT / "docs/audit/ops_verify_01_6fd5ac4c_d35a58ae/.ops_verify_temp_pw.txt"


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write(name: str, data: object) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


def _login() -> str:
    pw = PW_FILE.read_text(encoding="utf-8").strip()
    r = httpx.post(f"{API}/auth/login", json={"email": EMAIL, "password": pw}, timeout=120)
    r.raise_for_status()
    return r.json()["access_token"]


def _bundle() -> dict:
    manifest = httpx.get(f"{FE}/asset-manifest.json", timeout=90).json()
    js = httpx.get(f"{FE}{manifest['files']['main.js']}", timeout=120).text
    return {
        "path": manifest["files"]["main.js"],
        "has_filterUploadEligibleRequirementsForProperty": "filterUploadEligibleRequirementsForProperty" in js
        or "documentEvidenceAuthority" in js,
        "has_composeRequirementStatusBadgeVisibility": "composeRequirementStatusBadgeVisibility" in js,
        "has_resolveSettledEvidenceNavigationTarget": "resolveSettledEvidenceNavigationTarget" in js,
        "has_tab_evidence": "tab=evidence" in js or "tab','evidence" in js,
    }


def browser(token: str) -> dict:
    del token
    if sync_playwright is None:
        return {"skipped": True}
    pw = PW_FILE.read_text(encoding="utf-8").strip()
    out: dict = {"captured_at": _utc(), "checks": {}}
    with sync_playwright() as p:
        page = p.chromium.launch(headless=True).new_context(viewport={"width": 1440, "height": 900}).new_page()
        page.goto(f"{FE}/login/client", timeout=120000)
        page.locator("#email").fill(EMAIL)
        page.locator("#password").fill(pw)
        page.locator('button[type="submit"]').click()
        page.wait_for_timeout(5000)

        page.goto(f"{FE}/documents", wait_until="networkidle", timeout=120000)
        page.wait_for_timeout(3000)
        page.locator('[data-testid="property-select"]').select_option(index=1)
        page.wait_for_timeout(2000)
        req_options = page.locator('[data-testid="requirement-select"] option').count()
        out["checks"]["upload_dropdown_option_count"] = max(0, req_options - 1)

        page.goto(f"{FE}/requirements", wait_until="networkidle", timeout=120000)
        page.wait_for_timeout(4000)
        verified_row = page.locator('[data-testid^="requirement-row-"]').filter(has_text=re.compile(r"Verified", re.I)).first
        badge_count = 0
        if verified_row.count():
            badge_count = verified_row.locator("span").filter(has_text=re.compile(r"^Verified$", re.I)).count()
        out["checks"]["verified_badge_duplicates_sample"] = badge_count

        view_btn = page.get_by_role("button", name=re.compile(r"^View evidence", re.I)).first
        if view_btn.count():
            view_btn.click()
            page.wait_for_timeout(3000)
            out["checks"]["view_evidence_url"] = page.url
            out["checks"]["view_evidence_lands_on_registry"] = "tab=evidence" in page.url or "property-evidence-registry" in page.content()

        page.goto(f"{FE}/documents", wait_until="networkidle", timeout=120000)
        page.wait_for_timeout(2000)
        out["checks"]["operations_queue_clear"] = page.locator("text=Operations queue clear").count() > 0
    return out


def main() -> int:
    token = _login()
    bundle = _bundle()
    b = browser(token)

    upload = {
        "programme": PROGRAMME,
        "captured_at": _utc(),
        "bundle": bundle,
        "dropdown_options_after_property_select": b.get("checks", {}).get("upload_dropdown_option_count"),
        "classification": "FIX_DEPLOYED"
        if bundle.get("has_filterUploadEligibleRequirementsForProperty") and (b.get("checks", {}).get("upload_dropdown_option_count") or 0) > 0
        else "PARTIAL",
    }
    nav = {
        "programme": PROGRAMME,
        "captured_at": _utc(),
        "view_evidence_url": b.get("checks", {}).get("view_evidence_url"),
        "lands_on_registry": b.get("checks", {}).get("view_evidence_lands_on_registry"),
        "classification": "FIX_DEPLOYED" if b.get("checks", {}).get("view_evidence_lands_on_registry") else "DOCUMENT_NAVIGATION_REGRESSION",
    }
    queue = {
        "programme": PROGRAMME,
        "captured_at": _utc(),
        "operations_queue_clear_visible": b.get("checks", {}).get("operations_queue_clear"),
        "semantics": "queue clear does not imply no evidence — settled evidence in property registry",
        "classification": "OK",
    }
    registry = {
        "programme": PROGRAMME,
        "captured_at": _utc(),
        "property_evidence_registry_marker": b.get("checks", {}).get("view_evidence_lands_on_registry"),
        "classification": "OK" if b.get("checks", {}).get("view_evidence_lands_on_registry") else "PARTIAL",
    }
    badges = {
        "programme": PROGRAMME,
        "captured_at": _utc(),
        "verified_badge_count_sample": b.get("checks", {}).get("verified_badge_duplicates_sample"),
        "classification": "FIX_DEPLOYED" if (b.get("checks", {}).get("verified_badge_duplicates_sample") or 99) <= 1 else "BADGE_SEMANTICS_DRIFT",
    }
    parity = {"programme": PROGRAMME, "captured_at": _utc(), "upload": upload["classification"], "navigation": nav["classification"], "badges": badges["classification"]}
    classification = "VERIFIED_OPERATIONALLY"
    blockers = []
    if upload["classification"] != "FIX_DEPLOYED":
        blockers.append("upload_dropdown")
    if nav["classification"] != "FIX_DEPLOYED":
        blockers.append("view_evidence_navigation")
    if badges["classification"] != "FIX_DEPLOYED":
        blockers.append("badge_deduplication")
    if blockers:
        classification = "PARTIAL" if bundle.get("has_resolveSettledEvidenceNavigationTarget") else "EVIDENCE_AUTHORITY_DRIFT"

    _write("upload_requirement_dropdown_runtime.json", upload)
    _write("verified_evidence_navigation_runtime.json", nav)
    _write("document_operations_queue_semantics.json", queue)
    _write("evidence_registry_runtime.json", registry)
    _write("badge_deduplication_runtime.json", badges)
    _write("cross_surface_parity.json", parity)
    _write("browser_runtime.json", b)
    _write("classifications.json", {"programme": PROGRAMME, "classification": classification, "blockers": blockers, "bundle": bundle})
    _write(
        "watchlist.md",
        "# Watchlist\n\n"
        + ("- None — runtime verified.\n" if classification == "VERIFIED_OPERATIONALLY" else "- Re-run after frontend deploy includes documentEvidenceAuthority.js\n- Confirm upload dropdown populated for multi-requirement property\n"),
    )
    Path(OUT / "REPORT.md").write_text(
        f"# {PROGRAMME}\n\nClassification: **{classification}**\n\nBlockers: {blockers or 'none'}\n",
        encoding="utf-8",
    )
    print(json.dumps({"classification": classification, "blockers": blockers}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
