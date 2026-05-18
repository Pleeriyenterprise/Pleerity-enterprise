"""
OPS-VERIFY-01 Journey A — final browser walkthrough (post frontend remediation).

Existing CER on occupation_contract: uses property deep-link ?open=resolve to open guided modal (re-submit path).
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SLUG = "6fd5ac4c_d35a58ae"
CID = "6fd5ac4c-3fd4-4112-ade7-156977deb49f"
PID = "d35a58ae-3c81-491c-9694-1d021dd3b8ad"
RID = "488269bb-1be7-47e7-a030-98accf6dffc4"
FRONTEND = os.environ.get("OPS_VERIFY_FRONTEND_URL", "http://127.0.0.1:3000")
API = os.environ.get("OPS_VERIFY_API_URL", "http://127.0.0.1:8000")
EMAIL = os.environ.get("OPS_VERIFY_EMAIL", "nancy@yopmail.com")
PASSWORD = os.environ.get("OPS_VERIFY_PASSWORD") or (
    ROOT / f"docs/audit/ops_verify_01_{SLUG}/.ops_verify_temp_pw.txt"
).read_text(encoding="utf-8").strip()
BUNDLE = ROOT / f"docs/audit/ops_verify_01_{SLUG}"
CONVERGENCE_WAIT_S = int(os.environ.get("OPS_VERIFY_CONVERGENCE_WAIT_S", "95"))


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_baseline() -> None:
    os.environ.setdefault("MONGO_URL", os.environ.get("MONGO_URL", ""))
    from scripts.ops_verify_01_capture import _parse_args, _run_capture

    args = _parse_args()
    args.slug_suffix = SLUG
    args.out_dir = "docs/audit"
    args.client_id = CID
    args.property_id = PID
    args.requirement_id = RID
    args.phase = "baseline"
    args.init_bundle = False
    asyncio.run(_run_capture(args))
    print("baseline capture done")


def run_browser() -> dict:
    from playwright.sync_api import sync_playwright

    out: dict = {
        "started_at_utc": _utc(),
        "frontend_url": FRONTEND,
        "api_url": API,
        "requirement_id": RID,
        "property_id": PID,
        "submit_mode": "existing_cer_resubmit_via_property_deeplink",
        "prior_cer_id": "cer_799b0c6abff04bb6a8d51ec63ec904a0",
        "steps": [],
        "checkpoints": {},
    }

    def log(step: str, ok: bool, detail: str = "") -> None:
        out["steps"].append({"step": step, "ok": ok, "detail": detail, "at": _utc()})
        print(step, ok, detail)

    login = httpx.post(f"{API}/api/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=60)
    login.raise_for_status()
    token = login.json()["access_token"]
    user = login.json().get("user") or {}
    submit_payload: dict = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})

        def on_response(resp):
            url = resp.url
            if "compliance-evidence" in url and resp.request.method == "POST":
                try:
                    if resp.status == 200:
                        submit_payload["http_status"] = resp.status
                        body = resp.json()
                        submit_payload["body"] = body
                        er = body.get("evidence_record") or {}
                        submit_payload["evidence_record_id"] = er.get("evidence_record_id") or body.get(
                            "evidence_record_id"
                        )
                        submit_payload["workflow_complete"] = body.get("workflow_complete")
                except Exception as exc:
                    submit_payload["parse_error"] = str(exc)

        page.on("response", on_response)

        page.goto(f"{FRONTEND}/login/client", wait_until="domcontentloaded", timeout=120_000)
        page.evaluate(
            "([t, u]) => { localStorage.setItem('auth_token', t); localStorage.setItem('user', JSON.stringify(u)); }",
            [token, user],
        )

        # Confirm requirement visible
        page.goto(f"{FRONTEND}/requirements?highlight={RID}", wait_until="domcontentloaded", timeout=120_000)
        page.wait_for_selector('[data-testid="requirements-page"]', timeout=90_000)
        page.wait_for_timeout(6000)
        acc = page.locator(f'[data-testid="accordion-property-{PID}"]')
        if acc.count():
            acc.click()
            page.wait_for_timeout(2000)
        row_count = page.locator(f'[data-testid="requirement-row-{RID}"]').count()
        log("requirement_visible", row_count > 0, f"count={row_count}")
        out["checkpoints"]["A-8"] = row_count > 0

        # Guided modal via property deep-link (works with existing CER)
        page.goto(
            f"{FRONTEND}/properties/{PID}?open=resolve&requirement_id={RID}",
            wait_until="domcontentloaded",
            timeout=120_000,
        )
        page.wait_for_selector('[data-testid="compliance-evidence-resolve-modal"]', timeout=90_000)
        log("guided_modal_opened", True, "property_deeplink")

        page.get_by_test_id("guided-evidence-mode-STRUCTURED_DECLARATION").click()
        decl = (
            "OPS-VERIFY-01 Journey A final browser walkthrough — Wales occupation contract "
            f"re-submit at {_utc()}"
        )
        page.locator('[data-testid="compliance-evidence-resolve-modal"] textarea').first.fill(decl)
        page.locator('[data-testid="checklist-field-occupation_contract_issued"]').select_option("YES")
        page.locator('[data-testid="checklist-field-issue_date"]').fill("2026-02-01")
        page.locator('[data-testid="checklist-field-contract_holder_name"]').fill("OPS-VERIFY-01 Final Browser")
        page.locator('[data-testid="checklist-field-service_method"]').select_option("email")
        page.locator('[data-testid="checklist-field-declaration_confirmed"]').select_option("YES")

        page.get_by_role("button", name="Submit evidence").click()
        page.wait_for_selector('[data-testid="compliance-evidence-submit-summary"]', timeout=120_000)
        summary_el = page.get_by_test_id("compliance-evidence-submit-summary")
        summary_text = summary_el.inner_text()
        recorded = "submission recorded" in summary_text.lower() or "recorded" in summary_text.lower()
        log("A-1_submit_summary", recorded, summary_text[:200])
        out["checkpoints"]["A-1"] = recorded
        out["submit_summary_text"] = summary_text[:500]

        page.get_by_test_id("compliance-evidence-submit-summary-done").click()
        page.wait_for_timeout(2000)

        # TRUST-01
        page.goto(f"{FRONTEND}/requirements?highlight={RID}", wait_until="domcontentloaded", timeout=120_000)
        page.wait_for_selector('[data-testid="requirements-page"]', timeout=90_000)
        page.wait_for_timeout(6000)
        acc2 = page.locator(f'[data-testid="accordion-property-{PID}"]')
        if acc2.count():
            acc2.click()
            page.wait_for_timeout(2000)
        reopen = page.locator(f'[data-testid="compliance-view-requirement-{RID}"]')
        if reopen.count() == 0:
            reopen = page.locator(f'[data-testid="requirements-guided-open-{RID}"]')
        reopen.first.click(timeout=30_000)
        page.wait_for_selector('[data-testid="view-requirement-modal"]', timeout=60_000)
        page.wait_for_selector('[data-testid="requirement-submission-inspect-panel"]', timeout=60_000)
        panel_ok = page.get_by_test_id("requirement-submission-inspect-panel").count() > 0
        log("A-5_panel", panel_ok, "")
        page.wait_for_selector('[data-testid="submission-inspect-content"]', timeout=60_000)
        content_ok = page.get_by_test_id("submission-inspect-content").count() > 0
        log("A-5_content", content_ok, page.get_by_test_id("submission-inspect-content").inner_text()[:100])
        out["checkpoints"]["A-5"] = panel_ok and content_ok

        view_link = page.get_by_test_id("requirement-intel-view-submission")
        if view_link.count():
            view_link.click()
            page.wait_for_timeout(1000)
            log("A-5_view_submission_scroll", True, "")
        else:
            log("A-5_view_submission_scroll", False, "link missing")

        page.reload(wait_until="domcontentloaded")
        page.wait_for_selector('[data-testid="requirements-page"]', timeout=90_000)
        page.wait_for_timeout(8000)
        acc3 = page.locator(f'[data-testid="accordion-property-{PID}"]')
        if acc3.count():
            acc3.click()
            page.wait_for_timeout(1500)
        reopen2 = page.locator(f'[data-testid="compliance-view-requirement-{RID}"]')
        if reopen2.count() == 0:
            reopen2 = page.locator(f'[data-testid="requirements-guided-open-{RID}"]')
        reopen2.first.click(timeout=30_000)
        page.wait_for_selector('[data-testid="requirement-submission-inspect-panel"]', timeout=60_000)
        refresh_ok = page.get_by_test_id("requirement-submission-inspect-panel").count() > 0
        log("A-9_refresh", refresh_ok, "")
        out["checkpoints"]["A-9"] = refresh_ok

        shot = BUNDLE / "ops_verify_01_journey_a_final_ui.png"
        page.screenshot(path=str(shot), full_page=True)
        out["screenshot"] = str(shot)
        out["finished_at_utc"] = _utc()
        browser.close()

    out["submit_response"] = submit_payload
    if submit_payload.get("evidence_record_id"):
        out["new_cer_id"] = submit_payload["evidence_record_id"]
    path = BUNDLE / "ops_verify_01_browser_journey_a_final.json"
    path.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    return out


def run_post_submit(correlation_id: str | None) -> None:
    from scripts.ops_verify_01_capture import _parse_args, _run_capture

    args = _parse_args()
    args.slug_suffix = SLUG
    args.out_dir = "docs/audit"
    args.client_id = CID
    args.property_id = PID
    args.requirement_id = RID
    args.phase = "post-submit"
    args.correlation_id = correlation_id or ""
    asyncio.run(_run_capture(args))


def run_convergence(correlation_id: str | None) -> None:
    from scripts.ops_verify_01_capture import _parse_args, _run_capture

    args = _parse_args()
    args.slug_suffix = SLUG
    args.out_dir = "docs/audit"
    args.client_id = CID
    args.property_id = PID
    args.requirement_id = RID
    args.phase = "convergence"
    args.correlation_id = correlation_id or ""
    asyncio.run(_run_capture(args))


def update_manifest(browser_out: dict, post_snap: dict | None) -> None:
    from scripts.ops_verify_01_manifest import bundle_paths, read_json_if_exists, write_json

    paths = bundle_paths(BUNDLE, SLUG)
    manifest = read_json_if_exists(paths["manifest"]) or {}
    manifest["proof_mode"] = "operational_browser"
    manifest["browser_walkthrough_completed"] = True
    manifest["staging_url"] = FRONTEND
    manifest["api_url"] = API
    manifest["submit_via"] = "browser_guided_modal"
    manifest["submit_mode"] = browser_out.get("submit_mode")
    manifest["prior_cer_id"] = browser_out.get("prior_cer_id")
    manifest["captured_at_utc"] = _utc()
    new_cer = browser_out.get("new_cer_id")
    if new_cer:
        manifest["cer_id"] = new_cer
    corr = None
    if post_snap:
        corr = post_snap.get("correlation_id") or (post_snap.get("queue_rows") or [{}])[0].get("correlation_id")
    if corr:
        manifest["submit_correlation_id"] = corr

    cps = {
        "A-1": bool(browser_out.get("checkpoints", {}).get("A-1")),
        "A-5": bool(browser_out.get("checkpoints", {}).get("A-5")),
        "A-8": bool(browser_out.get("checkpoints", {}).get("A-8")),
        "A-9": bool(browser_out.get("checkpoints", {}).get("A-9")),
    }
    submit_resp = browser_out.get("submit_response") or {}
    if post_snap:
        cps["A-2"] = int(post_snap.get("cer_count_delta_from_baseline") or 0) > 0 or bool(post_snap.get("cer_rows"))
        cps["A-3"] = bool(post_snap.get("authority_changed_from_baseline"))
        cps["A-4"] = bool(submit_resp.get("workflow_complete"))
        cps["A-6"] = False
        cps["A-7"] = False
    conv_path = BUNDLE / f"ops_verify_01_convergence_{SLUG}.json"
    if conv_path.is_file():
        conv_snap = json.loads(conv_path.read_text(encoding="utf-8"))
        cps["A-6"] = bool(conv_snap.get("score_converged_observable"))
        qr = conv_snap.get("queue_row_for_correlation") or {}
        cps["A-7"] = str(qr.get("status") or "").upper() == "DONE"
    manifest["checkpoint_results"] = {"A_guided_structured_evidence_submit": cps}
    manifest["ui_attestations"] = {
        "A_guided_structured_evidence_submit": {
            "submission_visible": cps.get("A-5", False),
            "refresh_persisted": cps.get("A-9", False),
            "modal_submit_observed": cps.get("A-1", False),
            "user_visible_gap": False,
        }
    }
    manifest["execution_notes"] = (
        "Journey A final browser walkthrough after frontend remediation. "
        "occupation_contract had existing CER; guided modal opened via property ?open=resolve deep-link (re-submit)."
    )
    write_json(paths["manifest"], manifest)


def main() -> None:
    if not os.environ.get("MONGO_URL"):
        print("WARN: set MONGO_URL for captures", file=sys.stderr)
    print("=== 1 baseline ===")
    run_baseline()
    print("=== 2 browser ===")
    browser_out = run_browser()
    corr = None
    new_cer = browser_out.get("new_cer_id")
    if new_cer:
        corr = f"GUIDED_EVIDENCE_AUTHORITY:{PID}:{RID}:{new_cer}"
    print("=== 3 post-submit ===")
    run_post_submit(corr)
    post_path = BUNDLE / f"ops_verify_01_post_submit_{SLUG}.json"
    post_snap = json.loads(post_path.read_text(encoding="utf-8")) if post_path.is_file() else None
    print(f"=== 4 wait {CONVERGENCE_WAIT_S}s ===")
    time.sleep(CONVERGENCE_WAIT_S)
    print("=== 5 convergence ===")
    run_convergence(corr)
    print("=== 6 manifest ===")
    update_manifest(browser_out, post_snap)
    print("=== 7 classify ===")
    from scripts.ops_verify_01_classify import classify_bundle

    print(json.dumps(classify_bundle(BUNDLE, SLUG, journeys=["A_guided_structured_evidence_submit"]), indent=2))


if __name__ == "__main__":
    main()
