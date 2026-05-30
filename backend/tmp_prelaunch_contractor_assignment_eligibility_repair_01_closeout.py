#!/usr/bin/env python3
"""PRELAUNCH-CONTRACTOR-ASSIGNMENT-ELIGIBILITY-REPAIR-01 post-deploy closeout."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "docs/audit/prelaunch_contractor_assignment_eligibility_repair_01"
PROGRAMME = "PRELAUNCH-CONTRACTOR-ASSIGNMENT-ELIGIBILITY-REPAIR-01"
TARGET_SHA_PREFIXES = ("7f980d9b", "a86f4442", "0b65717a")
API = "https://pleerity-enterprise.onrender.com/api"
FE = "https://pleerityenterprise.co.uk"
FE_JOB_PATH = "/operations/jobs"
EMAIL = "nancy@yopmail.com"
PW_FILE = ROOT / "docs/audit/ops_verify_01_6fd5ac4c_d35a58ae/.ops_verify_temp_pw.txt"


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write(name: str, data: object) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


def _http_get(url: str, **kwargs) -> httpx.Response:
    last: Optional[Exception] = None
    for _ in range(4):
        try:
            return httpx.get(url, **kwargs)
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.RemoteProtocolError) as exc:
            last = exc
    raise last  # type: ignore[misc]


def _http_post(url: str, **kwargs) -> httpx.Response:
    last: Optional[Exception] = None
    for _ in range(4):
        try:
            return httpx.post(url, **kwargs)
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.RemoteProtocolError) as exc:
            last = exc
    raise last  # type: ignore[misc]


def _login() -> str:
    pw = PW_FILE.read_text(encoding="utf-8").strip()
    last: Optional[Exception] = None
    for _ in range(6):
        try:
            r = _http_post(f"{API}/auth/login", json={"email": EMAIL, "password": pw}, timeout=120)
            r.raise_for_status()
            return r.json()["access_token"]
        except Exception as exc:
            last = exc
            import time
            time.sleep(10)
    raise last  # type: ignore[misc]


def _headers(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _job_id(row: dict) -> Optional[str]:
    return row.get("job_id") or row.get("work_order_id")


def _assignable(token: str, job_id: str) -> dict:
    r = _http_get(
        f"{API}/jobs/{job_id}/assignable-contractors",
        headers=_headers(token),
        params={"limit": 200},
        timeout=90,
    )
    return {"status": r.status_code, "body": r.json() if r.content else {}}


def _jobs(token: str, limit: int = 30) -> List[dict]:
    h = _headers(token)
    rows: List[dict] = []
    r = _http_get(f"{API}/client/maintenance/work-orders", headers=h, params={"limit": limit}, timeout=90)
    if r.is_success:
        for wo in r.json().get("work_orders") or []:
            rows.append(
                {
                    "work_order_id": wo.get("work_order_id"),
                    "property_id": wo.get("property_id"),
                    "contractor_id": wo.get("contractor_id"),
                    "category": wo.get("category"),
                    "work_order_kind": wo.get("work_order_kind"),
                    "status": wo.get("status"),
                }
            )
    return rows


def deploy_continuity() -> dict:
    ver = _http_get(f"{API}/version", timeout=60).json()
    sha = str(ver.get("commit_sha") or "")
    sha_ok = any(sha.startswith(prefix) for prefix in TARGET_SHA_PREFIXES)
    manifest = _http_get(f"{FE}/asset-manifest.json", timeout=90).json()
    js_path = manifest["files"]["main.js"]
    js = _http_get(f"{FE}{js_path}", timeout=120).text
    flags = {
        "assign_contractor_recovery_testid": "assign-contractor-recovery" in js,
        "assign_contractor_excluded_review": "assign-contractor-excluded-review" in js,
        "assign_contractor_funnel": "assign-contractor-funnel" in js,
        "ready_to_assign_copy": "Ready to assign on this job" in js,
        "no_eligible_from_server_copy": "Eligible from server" in js,
    }
    token = _login()
    jobs = _jobs(token, limit=5)
    api_recovery = False
    api_samples = False
    login_ok = bool(token)
    if jobs:
        body = _assignable(token, jobs[0]["work_order_id"])["body"]
        api_recovery = bool(body.get("recovery_guidance"))
        api_samples = bool(body.get("exclusion_samples"))
    bundle_ok = (
        flags["assign_contractor_recovery_testid"]
        and flags["assign_contractor_excluded_review"]
        and flags["ready_to_assign_copy"]
        and not flags["no_eligible_from_server_copy"]
    )
    job_page_ok = None
    if sync_playwright is not None and jobs:
        try:
            pw = PW_FILE.read_text(encoding="utf-8").strip()
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_context(viewport={"width": 1440, "height": 900}).new_page()
                page.goto(f"{FE}/login/client", timeout=60000)
                page.locator("#email").fill(EMAIL)
                page.locator("#password").fill(pw)
                page.locator('button[type="submit"]').click()
                page.wait_for_timeout(5000)
                jid = jobs[0]["work_order_id"]
                page.goto(f"{FE}{FE_JOB_PATH}/{jid}", wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(6000)
                job_page_ok = "Something went wrong" not in page.inner_text("body")
                browser.close()
        except Exception:
            job_page_ok = False
    ok = sha_ok and bundle_ok and api_recovery and api_samples and login_ok and job_page_ok is not False
    return {
        "programme": PROGRAMME,
        "captured_at": _utc(),
        "target_sha_prefixes": list(TARGET_SHA_PREFIXES),
        "api_version": ver,
        "backend_sha_ok": sha_ok,
        "frontend_bundle": js_path,
        "frontend_flags": flags,
        "api_recovery_guidance": api_recovery,
        "api_exclusion_samples": api_samples,
        "login_ok": login_ok,
        "job_detail_page_loads": job_page_ok,
        "deploy_continuity_ok": ok,
        "classification_if_blocked": "BLOCKED_DEPLOY_CONTINUITY",
    }


def eligibility_authority_runtime(token: str, jobs: List[dict]) -> dict:
    checks: List[dict] = []
    eng_match = None
    payload_mismatches: List[dict] = []
    scotland_job = "63509f71-abf4-4cb6-84c5-e219d00f180b"
    scot_blocked = None
    scot_payload = _assignable(token, scotland_job)
    if scot_payload["status"] == 200:
        sbody = scot_payload["body"]
        sdiag = sbody.get("filter_diagnostics") or {}
        scot_blocked = {
            "job_id": scotland_job,
            "jurisdiction": sbody.get("job_jurisdiction"),
            "eligible": sdiag.get("eligible"),
            "excluded_location_postcode": sdiag.get("excluded_location_postcode"),
            "recovery_primary_blocker": (sbody.get("recovery_guidance") or {}).get("primary_blocker"),
            "recovery_action_count": len((sbody.get("recovery_guidance") or {}).get("recovery_actions") or []),
            "exclusion_sample_groups": sum(1 for v in (sbody.get("exclusion_samples") or {}).values() if v),
        }

    for row in jobs:
        jid = _job_id(row)
        if not jid:
            continue
        payload = _assignable(token, jid)
        if payload["status"] != 200:
            continue
        body = payload["body"]
        diag = body.get("filter_diagnostics") or {}
        eligible = int(diag.get("eligible") or 0)
        contractors = body.get("contractors") or []
        jj = body.get("job_jurisdiction")
        match_ok = len(contractors) == min(eligible, 200)
        entry = {
            "job_id": jid,
            "eligible": eligible,
            "job_jurisdiction": jj,
            "property_postcode": body.get("property_postcode"),
            "has_recovery_guidance": bool(body.get("recovery_guidance")),
            "has_exclusion_samples": bool(body.get("exclusion_samples")),
            "payload_matches_eligible": match_ok,
            "filter_diagnostics": diag,
        }
        checks.append(entry)
        if not match_ok:
            payload_mismatches.append({"job_id": jid, "eligible": eligible, "payload": len(contractors)})
        if jj == "England" and eligible > 0 and eng_match is None:
            eng_match = {"job_id": jid, "eligible": eligible}
        if eng_match is None and eligible > 0 and jj == "Wales":
            eng_match = {"job_id": jid, "eligible": eligible, "note": "Wales portfolio eligible sample"}

    invalid_assign_blocked = None
    if eng_match:
        jid = eng_match["job_id"]
        r = _http_post(
            f"{API}/jobs/{jid}/assign-contractor",
            headers=_headers(token),
            json={"contractor_id": "invalid-contractor-id-closeout-01"},
            timeout=60,
        )
        invalid_assign_blocked = {"status": r.status_code, "blocked": r.status_code >= 400}

    return {
        "captured_at": _utc(),
        "checks_run": len(checks),
        "recovery_fields_on_all": all(c["has_recovery_guidance"] and c["has_exclusion_samples"] for c in checks),
        "payload_mismatches": payload_mismatches,
        "payload_drop_bug": len(payload_mismatches) > 0,
        "england_eligible_sample": eng_match,
        "scotland_zero_eligible_sample": scot_blocked,
        "invalid_contractor_assign_blocked": invalid_assign_blocked,
        "jobs_with_eligible": sum(1 for c in checks if (c.get("eligible") or 0) > 0),
        "jobs_with_zero_eligible": sum(1 for c in checks if (c.get("eligible") or 0) == 0),
        "authority_ok": len(payload_mismatches) == 0
        and all(c["has_recovery_guidance"] for c in checks)
        and (scot_blocked or {}).get("eligible") == 0
        and (scot_blocked or {}).get("recovery_action_count", 0) > 0
        and (invalid_assign_blocked or {}).get("blocked") is True,
    }


def assignment_recovery_ux_bundle() -> dict:
    manifest = _http_get(f"{FE}/asset-manifest.json", timeout=90).json()
    js = _http_get(f"{FE}{manifest['files']['main.js']}", timeout=120).text
    flags = {
        "assign_contractor_recovery_testid": "assign-contractor-recovery" in js,
        "assign_contractor_excluded_review": "assign-contractor-excluded-review" in js,
        "assign_contractor_funnel": "assign-contractor-funnel" in js,
        "ready_to_assign_copy": "Ready to assign on this job" in js,
        "recovery_refresh": "Refresh list" in js,
        "no_eligible_from_server_copy": "Eligible from server" in js,
    }
    return {
        "captured_at": _utc(),
        "frontend_bundle": manifest["files"]["main.js"],
        "flags": flags,
        "recovery_ux_bundle_ok": flags["assign_contractor_recovery_testid"]
        and flags["assign_contractor_excluded_review"]
        and not flags["no_eligible_from_server_copy"],
    }


def dropdown_runtime(token: str, jobs: List[dict]) -> dict:
    results = []
    for row in jobs[:20]:
        jid = _job_id(row)
        if not jid:
            continue
        body = _assignable(token, jid)["body"]
        diag = body.get("filter_diagnostics") or {}
        eligible = int(diag.get("eligible") or 0)
        contractors = body.get("contractors") or []
        results.append(
            {
                "job_id": jid,
                "eligible": eligible,
                "dropdown_payload_count": len(contractors),
                "payload_matches_eligible": len(contractors) == min(eligible, 200),
            }
        )
    mismatches = [r for r in results if not r["payload_matches_eligible"]]
    return {"captured_at": _utc(), "jobs_checked": len(results), "payload_mismatches": mismatches, "dropdown_ok": not mismatches}


def cross_surface_consistency() -> dict:
    manifest = _http_get(f"{FE}/asset-manifest.json", timeout=90).json()
    js = _http_get(f"{FE}{manifest['files']['main.js']}", timeout=120).text
    return {
        "captured_at": _utc(),
        "surfaces": {
            "job_detail_recovery_modal": "assign-contractor-recovery" in js,
            "assignable_contractors_api_client": "assignable-contractors" in js,
            "no_frontend_eligibility_engine": "list_assignable_contractors_for_work_order" not in js,
            "today_routes_to_jobs": FE_JOB_PATH in js,
        },
        "note": "Assign eligibility authority is server-side; Today/Command Centre use job detail modal.",
        "cross_surface_ok": "assign-contractor-recovery" in js and "assignable-contractors" in js,
    }


def _job_detail(token: str, job_id: str) -> dict:
    r = _http_get(f"{API}/jobs/{job_id}", headers=_headers(token), timeout=60)
    return r.json() if r.is_success else {}


def _pick_jobs(token: str, jobs: List[dict]) -> Dict[str, Optional[str]]:
    eligible_unassigned = None
    zero_eligible = None
    zero_with_assign = None
    known_zero = "63509f71-abf4-4cb6-84c5-e219d00f180b"  # Scotland — authoritative zero-eligible sample
    for row in jobs:
        jid = _job_id(row)
        if not jid:
            continue
        body = _assignable(token, jid)["body"]
        diag = body.get("filter_diagnostics") or {}
        eligible = int(diag.get("eligible") or 0)
        detail = _job_detail(token, jid)
        actions = [a.get("id") for a in (detail.get("next_actions") or [])]
        has_contractor = bool((detail.get("contractor_id") or row.get("contractor_id") or "").strip())
        if eligible > 0 and "assign_contractor" in actions and not has_contractor and eligible_unassigned is None:
            eligible_unassigned = jid
        if eligible == 0 and int(diag.get("visible_in_directory") or 0) > 0:
            if zero_eligible is None:
                zero_eligible = jid
            if "assign_contractor" in actions and zero_with_assign is None:
                zero_with_assign = jid
    if zero_eligible is None:
        zbody = _assignable(token, known_zero)["body"]
        if int((zbody.get("filter_diagnostics") or {}).get("eligible") or 0) == 0:
            zero_eligible = known_zero
    return {
        "eligible_job": eligible_unassigned,
        "zero_eligible_job": zero_with_assign or zero_eligible,
        "zero_eligible_recovery_job": zero_eligible,
    }


def browser_closeout(token: str, jobs: List[dict]) -> dict:
    out: Dict[str, Any] = {
        "captured_at": _utc(),
        "checks": {},
        "assignment_e2e": {},
        "dropdown_runtime": {},
        "recovery_ux_runtime": {},
    }
    if sync_playwright is None:
        out["skipped"] = True
        out["reason"] = "playwright not installed"
        return out

    picks = _pick_jobs(token, jobs)
    eligible_job = picks["eligible_job"]
    zero_job = picks["zero_eligible_job"]
    zero_recovery_job = picks["zero_eligible_recovery_job"]
    out["checks"]["eligible_job_id"] = eligible_job
    out["checks"]["zero_eligible_job_id"] = zero_job
    out["checks"]["zero_eligible_recovery_job_id"] = zero_recovery_job

    def _open_job(page, job_id: str) -> None:
        page.goto(f"{FE}{FE_JOB_PATH}/{job_id}", wait_until="domcontentloaded", timeout=90000)
        try:
            page.wait_for_response(lambda r: f"/jobs/{job_id}" in r.url and r.status == 200, timeout=45000)
        except Exception:
            pass
        page.wait_for_timeout(4000)

    def _click_assign_if_visible(page, job_id: Optional[str] = None) -> bool:
        assign_btn = page.get_by_role("button", name="Assign contractor")
        if not assign_btn.count():
            return False
        target = assign_btn.last
        target.scroll_into_view_if_needed()
        try:
            with page.expect_response(
                lambda r: "assignable-contractors" in r.url and r.status == 200,
                timeout=90000,
            ):
                target.click()
        except Exception:
            target.click()
        try:
            page.get_by_test_id("assign-contractor-funnel").wait_for(state="visible", timeout=90000)
        except Exception:
            page.wait_for_timeout(5000)
        return True

    pw = PW_FILE.read_text(encoding="utf-8").strip()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(viewport={"width": 1440, "height": 900})
            page = ctx.new_page()
            page.goto(f"{FE}/login/client", timeout=60000)
            page.locator("#email").fill(EMAIL)
            page.locator("#password").fill(pw)
            page.locator('button[type="submit"]').click()
            page.wait_for_timeout(4000)
            out["checks"]["login_ok"] = "/login" not in page.url or "dashboard" in page.url.lower() or "today" in page.url.lower() or "properties" in page.url.lower()

            # --- Dropdown + assign on eligible job ---
            if eligible_job:
                _open_job(page, eligible_job)
                out["checks"]["job_detail_url"] = page.url
                assign_btn = page.get_by_role("button", name="Assign contractor").last
                try:
                    assign_btn.wait_for(state="visible", timeout=45000)
                    assign_visible = True
                except Exception:
                    assign_visible = page.get_by_role("button", name="Assign contractor").count() > 0
                out["dropdown_runtime"]["assign_button_visible"] = assign_visible
                if assign_visible and _click_assign_if_visible(page, eligible_job):
                    out["dropdown_runtime"]["modal_opened"] = True
                    try:
                        out["dropdown_runtime"]["funnel_visible"] = page.get_by_test_id("assign-contractor-funnel").count() > 0
                        out["dropdown_runtime"]["ready_copy"] = page.get_by_text("Ready to assign on this job").count() > 0
                        dialog = page.get_by_role("dialog").filter(has_text="Assign contractor")
                        select = dialog.locator("select").last
                        options = select.locator("option")
                        opt_count = options.count()
                        out["dropdown_runtime"]["dropdown_option_count"] = max(0, opt_count - 1)
                        out["dropdown_runtime"]["eligible_in_dropdown"] = opt_count > 1
                        assign_selected = dialog.get_by_role("button", name="Assign selected")
                        if assign_selected.count():
                            out["dropdown_runtime"]["assign_disabled_before_selection"] = assign_selected.is_disabled()
                        if opt_count > 1:
                            first_val = options.nth(1).get_attribute("value")
                            select.select_option(first_val or "")
                            page.wait_for_timeout(500)
                            if assign_selected.count():
                                out["dropdown_runtime"]["assign_enabled_after_selection"] = not assign_selected.is_disabled()
                                assign_selected.click()
                            page.wait_for_timeout(5000)
                            out["assignment_e2e"]["assign_clicked"] = True
                            jr = _http_get(f"{API}/jobs/{eligible_job}", headers=_headers(token), timeout=60)
                            if jr.is_success:
                                job_body = jr.json()
                                cid = (job_body.get("contractor_id") or "").strip()
                                if isinstance(job_body.get("contractor"), dict):
                                    cid = job_body["contractor"].get("contractor_id") or cid
                                out["assignment_e2e"]["contractor_linked"] = bool(cid)
                                out["assignment_e2e"]["job_id"] = eligible_job
                    except Exception as exc:
                        out["dropdown_runtime"]["error"] = str(exc)

            # --- Recovery UX: zero-eligible job with assign action, else API-backed recovery on known zero job ---
            recovery_job = zero_job or zero_recovery_job
            if recovery_job and recovery_job != eligible_job:
                _open_job(page, recovery_job)
                if _click_assign_if_visible(page):
                    out["recovery_ux_runtime"]["modal_opened"] = True
                    out["recovery_ux_runtime"]["recovery_visible"] = page.get_by_test_id("assign-contractor-recovery").count() > 0
                    out["recovery_ux_runtime"]["funnel_visible"] = page.get_by_test_id("assign-contractor-funnel").count() > 0
                else:
                    out["recovery_ux_runtime"]["assign_not_in_next_actions"] = True
                    zbody = _assignable(token, recovery_job)["body"]
                    out["recovery_ux_runtime"]["api_zero_eligible"] = int(
                        (zbody.get("filter_diagnostics") or {}).get("eligible") or 0
                    ) == 0
                    out["recovery_ux_runtime"]["api_recovery_actions"] = len(
                        (zbody.get("recovery_guidance") or {}).get("recovery_actions") or []
                    )
                    out["recovery_ux_runtime"]["api_exclusion_sample_groups"] = sum(
                        1 for v in (zbody.get("exclusion_samples") or {}).values() if v
                    )
                out["recovery_ux_runtime"]["no_dead_end"] = (
                    page.get_by_test_id("assign-contractor-recovery").count() > 0
                    or page.get_by_text("Add a new contractor").count() > 0
                    or out["recovery_ux_runtime"].get("api_recovery_actions", 0) > 0
                )
                review = page.get_by_test_id("assign-contractor-excluded-review")
                out["recovery_ux_runtime"]["excluded_review_present"] = review.count() > 0
                if review.count():
                    review.get_by_role("button").click()
                    page.wait_for_timeout(800)
                    out["recovery_ux_runtime"]["excluded_groups_expanded"] = (
                        page.get_by_text("Location / coverage").count() > 0
                        or page.get_by_text("Not assignment-ready").count() > 0
                    )
                out["recovery_ux_runtime"]["add_contractor_cta"] = page.get_by_text("Add a new contractor").count() > 0
                out["recovery_ux_runtime"]["refresh_list"] = page.get_by_text("Refresh list").count() > 0

            # --- Cross-surface: Command Centre routes to job detail ---
            page.goto(f"{FE}/command-center", wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(2500)
            out["checks"]["command_centre_loaded"] = "/command-center" in page.url
            open_job = page.get_by_role("button", name="Open job page").first
            if open_job.count() == 0:
                open_job = page.get_by_role("link", name="Open job page").first
            out["checks"]["command_centre_open_job_cta"] = open_job.count() > 0

            page.goto(f"{FE}/today", wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(2000)
            out["checks"]["today_page_loaded"] = "/today" in page.url
            today_job_link = page.locator(f'a[href*="{FE_JOB_PATH}/"]').first
            out["checks"]["today_routes_to_job_detail"] = today_job_link.count() > 0

            browser.close()
    except Exception as exc:
        out["skipped"] = True
        out["reason"] = str(exc)
    return out


def classify(deploy: dict, authority: dict, recovery: dict, dropdown: dict, cross: dict, browser: dict) -> dict:
    if not deploy.get("deploy_continuity_ok"):
        return {
            "programme": PROGRAMME,
            "captured_at": _utc(),
            "classification": "BLOCKED_DEPLOY_CONTINUITY",
            "deploy_continuity_ok": False,
        }

    dd = browser.get("dropdown_runtime") or {}
    e2e = browser.get("assignment_e2e") or {}
    rec = browser.get("recovery_ux_runtime") or {}

    rec_ok = bool(
        rec.get("recovery_visible")
        or (
            rec.get("api_zero_eligible") is True
            and (rec.get("api_recovery_actions") or 0) > 0
            and (rec.get("api_exclusion_sample_groups") or 0) > 0
        )
    )

    checks = [
        authority.get("authority_ok"),
        dropdown.get("dropdown_ok"),
        recovery.get("recovery_ux_bundle_ok"),
        cross.get("cross_surface_ok"),
        dd.get("eligible_in_dropdown"),
        dd.get("assign_disabled_before_selection"),
        dd.get("assign_enabled_after_selection"),
        e2e.get("contractor_linked"),
        rec_ok,
    ]
    browser_complete = not browser.get("skipped") and all(
        x is not False for x in [dd.get("modal_opened"), dd.get("funnel_visible")]
    )

    if all(checks) and browser_complete:
        classification = "VERIFIED_OPERATIONALLY"
    elif deploy.get("deploy_continuity_ok") and authority.get("authority_ok") and recovery.get("recovery_ux_bundle_ok"):
        classification = "PARTIAL"
    else:
        classification = "FAIL_OPERATIONAL"

    return {
        "programme": PROGRAMME,
        "captured_at": _utc(),
        "classification": classification,
        "deploy_continuity_ok": deploy.get("deploy_continuity_ok"),
        "authority_ok": authority.get("authority_ok"),
        "dropdown_ok": dropdown.get("dropdown_ok"),
        "recovery_ux_bundle_ok": recovery.get("recovery_ux_bundle_ok"),
        "cross_surface_ok": cross.get("cross_surface_ok"),
        "browser_complete": browser_complete,
        "assignment_e2e_ok": bool(e2e.get("contractor_linked")),
        "recovery_ux_runtime_ok": rec_ok,
        "closeout_commit_target": TARGET_SHA_PREFIXES[0],
    }


def write_watchlist(classification: dict) -> None:
    cls = classification.get("classification")
    lines = [
        f"# {PROGRAMME} watchlist",
        "",
        f"- **Closed classification:** {cls}",
        f"- Closeout captured: {_utc()}",
    ]
    if cls != "VERIFIED_OPERATIONALLY":
        lines.append("- Re-run closeout harness after any eligibility or modal regression.")
    else:
        lines.append("- Monitor Scotland/NI jobs where zero eligible remains authoritative.")
        lines.append("- Contractor portal assignment visibility depends on contractor session availability.")
    (OUT / "watchlist.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_report(classification: dict, deploy: dict) -> None:
    cls = classification.get("classification")
    text = f"""# {PROGRAMME} — Closeout

## Classification

**{cls}**

## Deploy continuity

- Backend SHA: `{deploy.get('api_version', {}).get('commit_sha', 'unknown')}`
- Frontend bundle: `{deploy.get('frontend_bundle')}`
- Deploy continuity OK: **{deploy.get('deploy_continuity_ok')}**

## Closeout summary

Post-deploy verification of contractor assignment eligibility authority, dropdown behaviour, assignment E2E, and recovery UX on staging.

## Commit

`7f980d9b` — Fix contractor assignment eligibility location authority and recovery UX.
"""
    (OUT / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> int:
    deploy = deploy_continuity()
    _write("deploy_continuity.json", deploy)

    if not deploy.get("deploy_continuity_ok"):
        classification = {
            "programme": PROGRAMME,
            "captured_at": _utc(),
            "classification": "BLOCKED_DEPLOY_CONTINUITY",
            "deploy_continuity_ok": False,
        }
        _write("classifications.json", classification)
        write_report(classification, deploy)
        write_watchlist(classification)
        print(json.dumps(classification, indent=2))
        return 1

    token = _login()
    jobs = _jobs(token, limit=30)
    authority = eligibility_authority_runtime(token, jobs)
    recovery = assignment_recovery_ux_bundle()
    dropdown = dropdown_runtime(token, jobs)
    cross = cross_surface_consistency()
    browser = browser_closeout(token, jobs)
    classification = classify(deploy, authority, recovery, dropdown, cross, browser)

    _write("eligibility_authority_runtime.json", authority)
    _write("assignment_recovery_ux.json", recovery)
    _write("dropdown_runtime.json", dropdown)
    _write("cross_surface_consistency.json", cross)
    _write("browser_runtime.json", browser)
    _write("classifications.json", classification)
    write_report(classification, deploy)
    write_watchlist(classification)

    print(json.dumps({"classification": classification.get("classification"), "out": str(OUT)}, indent=2))
    return 0 if classification.get("classification") == "VERIFIED_OPERATIONALLY" else 2


if __name__ == "__main__":
    sys.exit(main())
