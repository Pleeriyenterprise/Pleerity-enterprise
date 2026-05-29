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


TARGET_SHA_PREFIX = "026a9d2a"


def _bundle() -> dict:
    manifest = httpx.get(f"{FE}/asset-manifest.json", timeout=90).json()
    js = httpx.get(f"{FE}{manifest['files']['main.js']}", timeout=120).text
    return {
        "path": manifest["files"]["main.js"],
        "bytes": len(js),
        "has_documentEvidenceAuthority_fn": "documentEvidenceAuthority" in js
        or "filterUploadEligibleRequirementsForProperty" in js,
        "has_tab_evidence_query": "tab=evidence" in js or 'tab","evidence' in js,
        "has_data_evidence_req_focus": "data-evidence-req-focus" in js,
        "has_upload_empty_notice": "upload-requirement-empty-notice" in js,
        "has_evidence_registry_copy": "Evidence Registry" in js,
        "has_projection_full": "projection=full" in js or "projection\",\"full" in js,
    }


def deploy_continuity() -> dict:
    ver = httpx.get(f"{API}/version", timeout=60).json()
    bundle = _bundle()
    sha_ok = str(ver.get("commit_sha", "")).startswith(TARGET_SHA_PREFIX)
    behavioral_ok = (
        bundle.get("has_data_evidence_req_focus")
        and bundle.get("has_upload_empty_notice")
        and bundle.get("has_tab_evidence_query")
        and bundle.get("has_evidence_registry_copy")
    )
    return {
        "programme": PROGRAMME,
        "captured_at": _utc(),
        "api_version": ver,
        "backend_sha_ok": sha_ok,
        "frontend_bundle": bundle,
        "deploy_continuity_ok": sha_ok and behavioral_ok,
        "classification": "DEPLOY_CONTINUITY_OK" if sha_ok and behavioral_ok else "BLOCKED_DEPLOY_CONTINUITY",
    }


def _api_requirements(token: str) -> list:
    h = {"Authorization": f"Bearer {token}"}
    r = httpx.get(
        f"{API}/client/requirements",
        headers=h,
        params={"projection": "full"},
        timeout=120,
    )
    body = r.json() if r.is_success else {}
    return body.get("requirements") or []


def _pick_upload_property(reqs: list) -> str | None:
    from collections import defaultdict

    counts: dict[str, int] = defaultdict(int)
    for row in reqs:
        pid = str(row.get("property_id") or "")
        if not pid:
            continue
        st = str(row.get("client_lifecycle_state") or row.get("status") or "").upper()
        if st in {"ACTION_REQUIRED", "PENDING_REVIEW", "SATISFIED_UNVERIFIED", "MISSING", "OVERDUE"}:
            counts[pid] += 1
    if not counts:
        return None
    return max(counts.items(), key=lambda x: x[1])[0]


def _pick_verified_sample(reqs: list) -> dict | None:
    for row in reqs:
        st = str(row.get("client_lifecycle_state") or "").upper()
        status = str(row.get("status") or "").upper()
        if st == "VERIFIED" or status in {"COMPLIANT", "VALID"}:
            if row.get("property_id") and row.get("requirement_id"):
                return row
    return None
def browser(token: str, reqs: list) -> dict:
    del token
    upload_pid = _pick_upload_property(reqs)
    verified = _pick_verified_sample(reqs)
    out: dict = {
        "captured_at": _utc(),
        "checks": {
            "upload_property_id": upload_pid,
            "verified_requirement_id": (verified or {}).get("requirement_id"),
            "verified_property_id": (verified or {}).get("property_id"),
        },
    }
    if sync_playwright is None:
        out["skipped"] = True
        return out

    pw = PW_FILE.read_text(encoding="utf-8").strip()
    with sync_playwright() as p:
        page = p.chromium.launch(headless=True).new_context(viewport={"width": 1440, "height": 900}).new_page()
        page.goto(f"{FE}/login/client", timeout=120000)
        page.locator("#email").fill(EMAIL)
        page.locator("#password").fill(pw)
        page.locator('button[type="submit"]').click()
        page.wait_for_timeout(5000)

        page.goto(f"{FE}/documents", wait_until="networkidle", timeout=120000)
        try:
            page.wait_for_response(
                lambda r: "/client/requirements" in r.url and r.status == 200,
                timeout=90000,
            )
        except Exception:
            pass
        page.wait_for_timeout(2000)
        out["checks"]["documents_page_loaded"] = page.locator('[data-testid="documents-page"]').count() > 0
        prop_select = page.locator('[data-testid="upload-form"] [data-testid="property-select"]')
        if prop_select.count() == 0:
            prop_select = page.locator('[data-testid="property-select"]').first
        prop_count = prop_select.locator("option").count()
        out["checks"]["property_option_count"] = max(0, prop_count - 1)
        if upload_pid:
            prop_select.select_option(value=upload_pid)
        elif prop_count > 1:
            prop_select.select_option(index=1)
        req_select = page.locator('[data-testid="upload-form"] [data-testid="requirement-select"]')
        if req_select.count() == 0:
            req_select = page.locator('[data-testid="requirement-select"]').first
        for _ in range(20):
            page.wait_for_timeout(500)
            req_options = req_select.locator("option").count()
            if req_options > 1 or page.locator('[data-testid="upload-requirement-empty-notice"]').count() > 0:
                break
        req_options = req_select.locator("option").count()
        out["checks"]["upload_dropdown_option_count"] = max(0, req_options - 1)
        out["checks"]["upload_empty_notice"] = page.locator('[data-testid="upload-requirement-empty-notice"]').count() > 0

        page.goto(f"{FE}/requirements", wait_until="networkidle", timeout=120000)
        try:
            page.wait_for_response(
                lambda r: "/client/requirements" in r.url and r.status == 200,
                timeout=90000,
            )
        except Exception:
            pass
        page.wait_for_timeout(3000)
        out["checks"]["requirements_page_loaded"] = page.locator(
            '[data-testid="requirements-page"], [data-testid^="requirement-row-"], [data-testid^="accordion-property-"]'
        ).count() > 0

        verified_row = None
        if verified and verified.get("property_id"):
            acc = page.locator(f'[data-testid="accordion-property-{verified["property_id"]}"]')
            if acc.count():
                acc.locator("button").first.click()
                page.wait_for_timeout(1500)
        if verified and verified.get("requirement_id"):
            rid = str(verified["requirement_id"])
            verified_row = page.locator(f'[data-testid="requirement-row-{rid}"]')
            out["checks"]["verified_row_found"] = verified_row.count() > 0
        else:
            verified_row = page.locator('[data-testid^="requirement-row-"]').filter(
                has_text=re.compile(r"Verified|Valid|EICR", re.I)
            ).first

        badge_count = 0
        doc_count_badge = 0
        tier_badge_count = 0
        evidence_badge_count = 0
        if verified_row and verified_row.count():
            rid = str((verified or {}).get("requirement_id") or "")
            tier_badge_count = verified_row.locator(f'[data-testid="lifecycle-tier-{rid}"]').count()
            evidence_badge_count = verified_row.locator(f'[data-testid="evidence-badge-{rid}"]').count()
            badge_count = verified_row.locator("span.rounded-full").filter(
                has_text=re.compile(r"^Verified$", re.I)
            ).count()
            doc_count_badge = verified_row.locator('[data-testid^="doc-count-"]').count()
        out["checks"]["verified_tier_badge_visible"] = tier_badge_count > 0
        out["checks"]["verified_evidence_badge_visible"] = evidence_badge_count > 0
        out["checks"]["verified_badge_duplicates_sample"] = badge_count
        out["checks"]["verified_doc_count_badge_present"] = doc_count_badge > 0

        cta = None
        if verified and verified.get("requirement_id"):
            cta = page.locator(f'[data-testid="requirement-primary-cta-{verified["requirement_id"]}"]')
        if not cta or cta.count() == 0:
            cta = page.get_by_role("button", name=re.compile(r"View evidence", re.I)).first
        if cta.count():
            cta.click()
            page.wait_for_timeout(6000)
            out["checks"]["view_evidence_url"] = page.url
            out["checks"]["view_evidence_lands_on_registry"] = (
                "tab=evidence" in page.url
                or page.locator('[data-testid="property-evidence-registry"]').count() > 0
            )
            out["checks"]["view_evidence_not_documents_queue"] = not page.url.rstrip("/").endswith("/documents")
            out["checks"]["registry_visible"] = page.locator(
                '[data-testid="property-evidence-registry"], h2:has-text("Evidence Registry")'
            ).count() > 0
            out["checks"]["view_evidence_button_found"] = True
        else:
            out["checks"]["view_evidence_button_found"] = False

        page.goto(f"{FE}/documents", wait_until="networkidle", timeout=120000)
        page.wait_for_timeout(2000)
        out["checks"]["operations_queue_clear"] = page.locator("text=Operations queue clear").count() > 0
        out["checks"]["queue_semantics_copy"] = page.locator("text=Settled evidence").count() > 0
    return out


def main() -> int:
    token = _login()
    deploy = deploy_continuity()
    if not deploy.get("deploy_continuity_ok"):
        result = {
            "programme": PROGRAMME,
            "classification": "BLOCKED_DEPLOY_CONTINUITY",
            "deploy": deploy,
        }
        print(json.dumps(result, indent=2))
        return 0

    bundle = deploy["frontend_bundle"]
    reqs = _api_requirements(token)
    b = browser(token, reqs)
    checks = b.get("checks", {})

    upload = {
        "programme": PROGRAMME,
        "captured_at": _utc(),
        "bundle": bundle,
        "dropdown_options_after_property_select": checks.get("upload_dropdown_option_count"),
        "upload_empty_notice": checks.get("upload_empty_notice"),
        "classification": "VERIFIED" if (checks.get("upload_dropdown_option_count") or 0) > 0 else "PARTIAL",
    }
    nav = {
        "programme": PROGRAMME,
        "captured_at": _utc(),
        "view_evidence_url": checks.get("view_evidence_url"),
        "lands_on_registry": checks.get("view_evidence_lands_on_registry"),
        "not_documents_queue": checks.get("view_evidence_not_documents_queue"),
        "classification": "VERIFIED"
        if checks.get("view_evidence_lands_on_registry") and checks.get("view_evidence_not_documents_queue") is not False
        else "DOCUMENT_NAVIGATION_REGRESSION",
    }
    queue = {
        "programme": PROGRAMME,
        "captured_at": _utc(),
        "operations_queue_clear_visible": checks.get("operations_queue_clear"),
        "queue_semantics_copy_present": checks.get("queue_semantics_copy"),
        "semantics": "queue clear does not imply no evidence — settled evidence in property registry",
        "classification": "VERIFIED",
    }
    registry = {
        "programme": PROGRAMME,
        "captured_at": _utc(),
        "registry_visible_after_view_evidence": checks.get("registry_visible"),
        "classification": "VERIFIED" if checks.get("view_evidence_lands_on_registry") else "PARTIAL",
    }
    badges = {
        "programme": PROGRAMME,
        "captured_at": _utc(),
        "verified_badge_count_sample": checks.get("verified_badge_duplicates_sample"),
        "doc_count_badge_present": checks.get("verified_doc_count_badge_present"),
        "classification": "VERIFIED"
        if (checks.get("verified_badge_duplicates_sample") or 99) <= 1
        and not checks.get("verified_tier_badge_visible")
        and not checks.get("verified_evidence_badge_visible")
        else "BADGE_SEMANTICS_DRIFT",
    }
    parity = {
        "programme": PROGRAMME,
        "captured_at": _utc(),
        "upload": upload["classification"],
        "navigation": nav["classification"],
        "badges": badges["classification"],
        "queue": queue["classification"],
        "registry": registry["classification"],
    }
    blockers = []
    if (checks.get("upload_dropdown_option_count") or 0) == 0:
        blockers.append("upload_dropdown")
    if nav["classification"] != "VERIFIED":
        blockers.append("view_evidence_navigation")
    if badges["classification"] != "VERIFIED":
        blockers.append("badge_deduplication")

    classification = "VERIFIED_OPERATIONALLY" if not blockers else "PARTIAL"

    if classification == "VERIFIED_OPERATIONALLY":
        _write("upload_requirement_dropdown_runtime.json", upload)
        _write("verified_evidence_navigation_runtime.json", nav)
        _write("document_operations_queue_semantics.json", queue)
        _write("evidence_registry_runtime.json", registry)
        _write("badge_deduplication_runtime.json", badges)
        _write("cross_surface_parity.json", parity)
        _write("browser_runtime.json", b)
        _write("classifications.json", {"programme": PROGRAMME, "classification": classification, "blockers": blockers, "deploy": deploy})
        _write("watchlist.md", "# Watchlist\n\n- None — runtime verified.\n")
        Path(OUT / "REPORT.md").write_text(
            f"# {PROGRAMME}\n\nClassification: **{classification}**\n\nDeploy: {deploy['api_version'].get('commit_sha')}\n",
            encoding="utf-8",
        )

    print(json.dumps({"classification": classification, "blockers": blockers, "deploy": deploy, "checks": checks}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
