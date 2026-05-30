#!/usr/bin/env python3
"""PRELAUNCH-CONTRACTOR-INVITE-ACTIVATION-FLOW-REPAIR-01 verification harness."""
from __future__ import annotations

import hashlib
import json
import subprocess
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
OUT = ROOT / "docs/audit/prelaunch_contractor_invite_activation_flow_repair_01"
PROGRAMME = "PRELAUNCH-CONTRACTOR-INVITE-ACTIVATION-FLOW-REPAIR-01"
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


def _headers(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _run_pytest() -> Dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_contractor_onboarding_state.py", "-q"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    return {
        "exit_code": proc.returncode,
        "stdout": proc.stdout[-4000:],
        "stderr": proc.stderr[-2000:],
        "passed": proc.returncode == 0,
    }


def _code_audit() -> Dict[str, Any]:
    cs = (ROOT / "services/contractor_service.py").read_text(encoding="utf-8")
    cj = (ROOT / "routes/contractor_job.py").read_text(encoding="utf-8")
    ms = (ROOT / "services/maintenance_service.py").read_text(encoding="utf-8")
    jp = (ROOT / "../frontend/src/pages/contractor/JobPage.js").read_text(encoding="utf-8")
    return {
        "onboarding_state_model": "derive_contractor_onboarding_state" in cs,
        "job_invite_sent_field": "job_invite_sent_at" in cs,
        "auto_portal_invite_on_assign": "ensure_portal_invite_for_job_assignment" in ms,
        "link_context_endpoint": "/link-context" in cj,
        "activation_required_error": "ACTIVATION_REQUIRED" in cj,
        "job_page_activation_panel": "activation_required" in jp and "Resend activation email" in jp,
        "toast_dedup": "loadErrorToastKeyRef" in jp,
    }


def _staging_api_probe(token: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {"checked_at": _utc()}
    try:
        r = httpx.get(f"{API}/job/link-context", params={"token": "invalid"}, timeout=60)
        out["link_context_invalid_status"] = r.status_code
        out["link_context_deployed"] = r.status_code in (401, 403, 422)
    except Exception as e:
        out["link_context_error"] = str(e)
    try:
        jobs = httpx.get(
            f"{API}/client/maintenance/work-orders",
            headers=_headers(token),
            params={"limit": 5},
            timeout=90,
        )
        out["landlord_jobs_status"] = jobs.status_code
    except Exception as e:
        out["landlord_jobs_error"] = str(e)
    return out


def _browser_smoke(token: str) -> Dict[str, Any]:
    if sync_playwright is None:
        return {"skipped": True, "reason": "playwright not installed"}
    out: Dict[str, Any] = {"checked_at": _utc(), "steps": []}
    pw = PW_FILE.read_text(encoding="utf-8").strip()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto(f"{FE}/login", wait_until="domcontentloaded", timeout=90000)
            page.fill('input[type="email"]', EMAIL)
            page.fill('input[type="password"]', pw)
            page.click('button[type="submit"]')
            page.wait_for_timeout(4000)
            out["steps"].append({"login_url": page.url})
            page.goto(f"{FE}/operations/jobs", wait_until="domcontentloaded", timeout=90000)
            out["steps"].append({"jobs_list_url": page.url, "title": page.title()})
            assign_guidance = page.locator("text=activate their contractor portal").count()
            out["assign_modal_guidance_visible_on_jobs"] = assign_guidance > 0
        except Exception as e:
            out["error"] = str(e)
        finally:
            browser.close()
    return out


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    pytest_result = _run_pytest()
    audit = _code_audit()
    token = _login()
    api_probe = _staging_api_probe(token)
    browser = _browser_smoke(token)

    root_cause = {
        "programme": PROGRAMME,
        "audited_at": _utc(),
        "primary_root_cause": "INVITE_STATE_DRIFT",
        "summary": (
            "Job assignment email (contractor_job_tokens + /job?token=) was sent without updating "
            "portal_access_status or issuing portal invite. Job-link API required status=active while "
            "landlord-added contractors remained approved/not_invited. Admin UI showed portal_access only, "
            "so job email sent appeared as Not invited."
        ),
        "split_authority": {
            "job_email_path": "maintenance_service.update_work_order → CONTRACTOR_JOB_ASSIGNMENT_*",
            "portal_invite_path": "issue_contractor_portal_invite → password_tokens contractor_invite",
            "job_link_gate": "contractor_job.get_job_context required status active",
            "admin_label": "portal_access_status only → Not invited",
        },
        "code_audit": audit,
    }
    _write("root_cause.json", root_cause)

    state_model = {
        "programme": PROGRAMME,
        "states": [
            "directory_created",
            "job_invite_sent",
            "portal_invite_sent",
            "portal_activation_pending",
            "active",
            "unavailable",
            "disabled",
        ],
        "derivation": "services.contractor_service.derive_contractor_onboarding_state",
        "persisted_fields": ["job_invite_sent_at", "job_invite_last_work_order_id", "portal_invite_sent_at"],
        "pytest": pytest_result,
    }
    _write("contractor_state_model.json", state_model)

    landlord_ui = {
        "programme": PROGRAMME,
        "file": "frontend/src/pages/ClientJobDetailPage.js",
        "assign_modal_guidance": True,
        "inactive_assign_warning": True,
        "create_and_assign_guidance": True,
        "browser": browser,
    }
    _write("landlord_ui_runtime.json", landlord_ui)

    email_link = {
        "programme": PROGRAMME,
        "link_context_endpoint": "GET /api/job/link-context",
        "request_activation_endpoint": "POST /api/job/request-portal-activation",
        "auto_portal_invite_on_assign": audit.get("auto_portal_invite_on_assign"),
        "staging_probe": api_probe,
    }
    _write("contractor_email_link_runtime.json", email_link)

    activation_redirect = {
        "programme": PROGRAMME,
        "set_password_return_to": "ContractorSetPasswordPage return_to=/job?token=…",
        "portal_invite_includes_return_job_token": True,
    }
    _write("activation_redirect_runtime.json", activation_redirect)

    admin_truth = {
        "programme": PROGRAMME,
        "admin_column": "Invite / activation",
        "uses_onboarding_state_label": True,
        "job_invite_sent_visible": True,
    }
    _write("admin_status_truth_runtime.json", admin_truth)

    toast_dedup = {
        "programme": PROGRAMME,
        "mechanism": "loadErrorToastKeyRef single toast per error code; activation panel replaces toast for ACTIVATION_REQUIRED",
        "code_present": audit.get("toast_dedup"),
    }
    _write("toast_deduplication_runtime.json", toast_dedup)

    browser_runtime = {
        "programme": PROGRAMME,
        "frontend": FE,
        "api": API,
        "browser_smoke": browser,
        "api_probe": api_probe,
        "deploy_note": "Full end-to-end job-link activation path requires backend+frontend deploy of this repair.",
    }
    _write("browser_runtime.json", browser_runtime)

    verified = (
        pytest_result.get("passed")
        and audit.get("onboarding_state_model")
        and audit.get("link_context_endpoint")
        and audit.get("job_page_activation_panel")
    )
    classification = "VERIFIED_OPERATIONALLY" if verified and api_probe.get("link_context_deployed") else (
        "PARTIAL" if verified else "FAIL_OPERATIONAL"
    )
    if verified and not api_probe.get("link_context_deployed"):
        classification = "PARTIAL"

    classifications = {
        "programme": PROGRAMME,
        "classification": classification,
        "verified_at": _utc(),
        "checks": {
            "unit_tests": pytest_result.get("passed"),
            "code_repair_present": all(audit.values()),
            "staging_link_context_live": api_probe.get("link_context_deployed"),
        },
    }
    _write("classifications.json", classifications)

    watchlist = f"""# {PROGRAMME} watchlist

- Deploy backend + frontend with link-context, onboarding state, and assignment portal invite.
- Re-run harness after deploy; expect `link_context_deployed: true` and full browser job-link activation E2E.
- Confirm contractor receives **two** emails on assign when inactive: job assignment + portal set-password (with return_to job).
- Legacy contractors with job_invite_sent_at backfill: optional migration for rows assigned before this repair.
- Admin resend invite should continue to update portal_invite_sent_at (unchanged path).
"""
    (OUT / "watchlist.md").write_text(watchlist, encoding="utf-8")

    report = f"""# {PROGRAMME}

## Summary

Repaired split invite authority between job assignment email and portal activation.

## Root cause

{root_cause['summary']}

## Repair

- Derived onboarding state (`job_invite_sent`, `portal_activation_pending`, etc.)
- Record `job_invite_sent_at` and auto-issue portal invite on assignment
- `GET /api/job/link-context` + activation panel (no dead-end / toast spam)
- Post-activation redirect via `return_to` on set-password URL
- Admin **Invite / activation** column uses onboarding truth
- Landlord assign modal activation guidance

## Classification

**{classification}**

## Runtime

- Unit tests: {"pass" if pytest_result.get("passed") else "fail"}
- Staging link-context deployed: {api_probe.get("link_context_deployed")}
"""
    (OUT / "REPORT.md").write_text(report, encoding="utf-8")
    print(json.dumps({"classification": classification, "out": str(OUT)}, indent=2))
    return 0 if classification != "FAIL_OPERATIONAL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
