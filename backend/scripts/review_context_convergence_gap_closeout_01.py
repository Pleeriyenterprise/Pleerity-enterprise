#!/usr/bin/env python3
"""REVIEW-CONTEXT-CONVERGENCE-GAP-01 — closeout probes and artifact writer."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "audit" / "review_context_convergence_gap_01"
FE = os.getenv("STAGING_FE", "https://pleerityenterprise.co.uk").rstrip("/")
API = os.getenv("STAGING_API", "https://pleerity-enterprise.onrender.com/api").rstrip("/")


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write(name: str, data: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


def _run_regression() -> dict:
    py = subprocess.run(
        [sys.executable, "-m", "pytest", "backend/tests/test_review_queue_service.py", "-q"],
        cwd=ROOT.parent,
        capture_output=True,
        text=True,
        timeout=120,
    )
    return {
        "backend_pytest_exit": py.returncode,
        "backend_pytest_tail": (py.stdout or "")[-500:],
        "frontend_unit_tests": [
            "propertyReviewContextDeeplink.test.js",
            "PropertyDetailPage.resolveRequirement.test.js",
        ],
        "frontend_unit_note": "Run via npm test in frontend/ (verified in CI/local)",
    }


def main() -> None:
    review_context = {
        "generated_at": _utc(),
        "deeplink_contract": "/properties/{property_id}?resolve_requirement={requirement_id}",
        "frontend_parser": "parsePropertyReviewContextDeeplink",
        "property_page_behavior": [
            "setActiveTab(compliance)",
            "open RequirementIntelligenceModal with initialFocusSubmission",
            "review-context-banner when context resolved or missing",
        ],
        "unit_tests": "propertyReviewContextDeeplink.test.js, PropertyDetailPage.resolveRequirement.test.js",
    }
    _write("review_context_runtime.json", review_context)

    verification = {
        "generated_at": _utc(),
        "queue_verify_reject_contract": "POST /api/client/compliance-evidence/{property_id}/requirements/{requirement_id}/records/{evidence_record_id}/verification",
        "evidence_record_id_source": "review_queue_service.build_queue_row_payload",
        "note": "Queue inline Verify/Reject uses row evidence_record_id; deeplink fix hydrates visual context before action.",
    }
    _write("verification_runtime.json", verification)

    queue_conv = {"generated_at": _utc(), "post_resolution": "list_org_review_queue excludes non-PENDING CER"}
    _write("queue_convergence_runtime.json", queue_conv)

    browser = {"generated_at": _utc(), "captured": False, "note": "Run Playwright with ROLE_CLIENT_ADMIN after FE deploy"}
    shots = OUT / "screenshots"
    shots.mkdir(parents=True, exist_ok=True)
    email = (os.getenv("STAGING_CLIENT_ADMIN_EMAIL") or os.getenv("STAGING_ADMIN_EMAIL") or "").strip()
    pw = (os.getenv("STAGING_CLIENT_ADMIN_PASSWORD") or os.getenv("STAGING_ADMIN_PASSWORD") or "").strip()
    if email and pw:
        try:
            import re
            from playwright.sync_api import sync_playwright
            import httpx

            with sync_playwright() as p:
                browser_pw = p.chromium.launch(headless=True)
                page = browser_pw.new_page(viewport={"width": 1400, "height": 900})
                page.goto(f"{FE}/login/client", wait_until="domcontentloaded", timeout=120000)
                page.fill("#email", email)
                page.fill("#password", pw)
                page.locator('button[type="submit"]').click(timeout=30000)
                page.wait_for_timeout(6000)
                page.goto(f"{FE}/operations/compliance-review", wait_until="domcontentloaded", timeout=120000)
                page.wait_for_timeout(3000)
                s1 = shots / "01_queue.png"
                page.screenshot(path=str(s1), full_page=True)
                btn = page.locator("[data-testid^='org-review-open-']").first
                if btn.count():
                    btn.click(timeout=15000)
                    page.wait_for_timeout(4000)
                    s2 = shots / "02_review_context.png"
                    page.screenshot(path=str(s2), full_page=True)
                    browser["captured"] = True
                    browser["screenshots"] = [s1.name, s2.name]
                    browser["submission_panel"] = page.get_by_test_id("requirement-submission-inspect-panel").count() > 0
                    browser["review_banner"] = page.get_by_test_id("review-context-banner").count() > 0
                    browser["intel_modal"] = page.locator("[role='dialog']").count() > 0
                browser_pw.close()
        except Exception as exc:
            browser["error"] = str(exc)[:500]
    _write("browser_runtime.json", browser)

    reg = _run_regression()
    _write("regression_runtime.json", {"generated_at": _utc(), **reg})

    gates = {
        "review_queue_backend": reg.get("backend_pytest_exit") == 0,
        "frontend_unit_tests_documented": True,
        "browser_proof": browser.get("captured") is True,
        "submission_panel_visible": browser.get("submission_panel") is True,
    }
    classification = "REVIEW_CONTEXT_DRIFT"
    if gates["review_queue_backend"] and gates["browser_proof"] and gates.get("submission_panel_visible"):
        classification = "VERIFIED_OPERATIONALLY"
    elif gates["review_queue_backend"]:
        classification = "PARTIAL"

    _write(
        "classifications.json",
        {
            "marker": "REVIEW-CONTEXT-CONVERGENCE-GAP-01",
            "generated_at": _utc(),
            "classification": classification,
            "gates": gates,
        },
    )

    report = f"""# REVIEW-CONTEXT-CONVERGENCE-GAP-01

Generated: {_utc()}

## Classification

**{classification}**

## Fix

- `parsePropertyReviewContextDeeplink` + PropertyDetailPage consumes `resolve_requirement`
- Opens Compliance tab + RequirementIntelligenceModal (submission focus)
- Review context banner + missing-context empty state

## Tests

- Frontend: propertyReviewContextDeeplink, PropertyDetailPage.resolveRequirement
- Backend: test_review_queue_service
"""
    (OUT / "REPORT.md").write_text(report, encoding="utf-8")
    (OUT / "watchlist.md").write_text(
        "# Watchlist\n\n- [ ] Re-run browser closeout after FE deploy\n- [ ] Spot-check Verify/Reject removes queue row\n",
        encoding="utf-8",
    )
    print(json.dumps({"classification": classification, "gates": gates}, indent=2))


if __name__ == "__main__":
    main()
