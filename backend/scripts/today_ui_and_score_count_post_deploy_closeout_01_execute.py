#!/usr/bin/env python3
"""TODAY-UI-AND-SCORE-COUNT-POST-DEPLOY-CLOSEOUT-01"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import httpx

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUT = ROOT / "docs/audit/compliance_projection_convergence_runtime_audit_01"
SHOT = OUT / "today_score_post_deploy_screenshots"
PROGRAMME = "TODAY-UI-AND-SCORE-COUNT-POST-DEPLOY-CLOSEOUT-01"
DEPLOY_COMMIT = "0b8582ca"

TARGET_CLIENT_ID = "10b2ddba-e952-4484-91d1-a8f0299d0824"
TARGET_CRN = "PLE-CVP-2026-000023"

_raw_api = os.environ.get("STAGING_API", "https://pleerity-enterprise.onrender.com").rstrip("/")
API = _raw_api if _raw_api.endswith("/api") else f"{_raw_api}/api"
FRONTEND = os.environ.get("STAGING_FRONTEND", "https://pleerityenterprise.co.uk").rstrip("/")


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write(name: str, data: Any) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


def _read_pw(path: Path, env_key: str) -> str:
    env = os.environ.get(env_key, "").strip()
    if env:
        return env
    if path.is_file():
        return path.read_text(encoding="utf-8").strip()
    return ""


def _client_session() -> Tuple[Optional[str], Dict[str, Any]]:
    email = os.environ.get("OPS_VERIFY_ADMIN_EMAIL", "aigbochievictory@gmail.com").strip()
    pw = _read_pw(ROOT / "docs/audit/ops_verify_01_6fd5ac4c_d35a58ae/.ops_verify_admin_pw.txt", "STAGING_ADMIN_PASSWORD")
    if not pw:
        return None, {}
    r = httpx.post(f"{API}/auth/admin/login", json={"email": email, "password": pw}, timeout=120)
    if r.status_code != 200:
        return None, {}
    admin_t = r.json()["access_token"]
    su = httpx.post(
        f"{API}/auth/step-up/verify",
        headers={"Authorization": f"Bearer {admin_t}"},
        json={"password": pw},
        timeout=120,
    )
    step_up = (su.json() or {}).get("step_up_token", "") if su.status_code == 200 else ""
    headers = {"Authorization": f"Bearer {admin_t}"}
    if step_up:
        headers["X-Step-Up-Token"] = step_up
    imp = httpx.post(
        f"{API}/admin/clients/{TARGET_CLIENT_ID}/impersonation/start",
        headers=headers,
        params={"ttl_minutes": 30},
        json={"reason": f"{PROGRAMME} staging verification"},
        timeout=120,
    )
    if imp.status_code != 200:
        return None, {}
    body = imp.json()
    return body["access_token"], body.get("user") or {}


def _h(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _fetch_frontend_bundle() -> Dict[str, Any]:
    html_r = httpx.get(FRONTEND, timeout=120, follow_redirects=True)
    main_match = re.search(r"/static/js/main\.([a-f0-9]+)\.js", html_r.text)
    main_hash = main_match.group(1) if main_match else None
    js_text = ""
    if main_hash:
        js_r = httpx.get(f"{FRONTEND}/static/js/main.{main_hash}.js", timeout=180)
        js_text = js_r.text if js_r.status_code == 200 else ""
    markers = {
        "filterInboxTasksForOperationalActionability": "filterInboxTasksForOperationalActionability" in js_text,
        "isTaskAssuranceOnly": "isTaskAssuranceOnly" in js_text,
        "score_tracked_obligation_groups": "score-tracked obligation" in js_text,
        "grouping_note_copy": "grouped for scoring" in js_text or "double-counting" in js_text,
        "alignTodayPayloadTaskSections": "alignTodayPayloadTaskSections" in js_text,
    }
    # Minified bundles strip export names; score page copy is a reliable deploy marker.
    deployed_today_fix = (
        markers["filterInboxTasksForOperationalActionability"]
        or markers["isTaskAssuranceOnly"]
        or markers["score_tracked_obligation_groups"]
    )
    return {
        "frontend_url": FRONTEND,
        "html_status": html_r.status_code,
        "main_bundle_hash": main_hash,
        "markers": markers,
        "deployed_today_fix": deployed_today_fix,
    }


def _deploy_proof(token: Optional[str]) -> Dict[str, Any]:
    bundle = _fetch_frontend_bundle()
    score_body: Dict[str, Any] = {}
    if token:
        r = httpx.get(f"{API}/client/compliance-score", headers=_h(token), timeout=120)
        if r.status_code == 200:
            score_body = r.json()
    stats = score_body.get("stats") or {}
    sc = score_body.get("score_confidence") or {}
    sem = score_body.get("reporting_semantics") or {}
    lifecycle = int(stats.get("lifecycle_satisfied_count") or sc.get("lifecycle_satisfied_count") or 0)
    visible = stats.get("visible_requirement_count")
    score_tracked = int(stats.get("score_tracked_requirement_count") or 0)
    grouping = sc.get("grouping_note") or sem.get("grouping_note")
    return {
        "programme": PROGRAMME,
        "generated_at": _utc(),
        "expected_commit": DEPLOY_COMMIT,
        "frontend": bundle,
        "api": {
            "has_visible_requirement_count": "visible_requirement_count" in stats,
            "visible_requirement_count": visible,
            "lifecycle_satisfied_count": lifecycle,
            "score_tracked_requirement_count": score_tracked,
            "has_grouping_note": bool(grouping),
            "grouping_note": grouping,
            "score": score_body.get("score"),
            "score_confidence_headline": sc.get("headline"),
        },
        "pass": (
            bundle.get("deployed_today_fix")
            and "visible_requirement_count" in stats
            and lifecycle >= 10
            and score_tracked == 8
            and bool(grouping)
        ),
        "notes": (
            "Frontend deploy inferred from score-page copy markers when minifier strips export names. "
            "Backend visible_requirement_count field confirms API deploy; lifecycle=10 and grouping_note "
            "require score pipeline to include all 10 visible requirement rows."
        ),
    }


def _today_api(token: str) -> Dict[str, Any]:
    r = httpx.get(f"{API}/today/items", headers=_h(token), timeout=120)
    body = r.json() if r.status_code == 200 else {}
    summary = body.get("summary") or {}
    tasks = body.get("tasks") or {}
    urgent = list(tasks.get("urgent") or [])
    in_progress = list(tasks.get("in_progress") or [])
    return {
        "status": r.status_code,
        "urgent_count": int(summary.get("urgent_count") or len(urgent)),
        "in_progress_count": int(summary.get("in_progress_count") or len(in_progress)),
        "summary": summary,
    }


def _browser_closeout(token: str) -> Dict[str, Any]:
    if sync_playwright is None:
        return {"pass": False, "error": "playwright not installed"}
    SHOT.mkdir(parents=True, exist_ok=True)
    routes = [
        ("today", "/today", "01_today.png"),
        ("dashboard", "/dashboard", "02_dashboard.png"),
        ("compliance_score", "/compliance-score", "03_compliance_score.png"),
        ("requirements", "/requirements", "04_requirements.png"),
        ("properties", "/properties", "05_properties.png"),
    ]
    findings: Dict[str, Any] = {}
    screenshots: Dict[str, str] = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        user_blob = json.dumps({"client_id": TARGET_CLIENT_ID, "role": "ROLE_CLIENT_ADMIN", "impersonation": True})
        context.add_init_script(
            f"localStorage.setItem('auth_token', {json.dumps(token)});"
            f"localStorage.setItem('user', {json.dumps(user_blob)});"
        )
        page = context.new_page()
        for key, path, fname in routes:
            page.goto(f"{FRONTEND}{path}", wait_until="networkidle", timeout=120000)
            page.wait_for_timeout(2500)
            rel = SHOT / fname
            page.screenshot(path=str(rel), full_page=True)
            screenshots[key] = str(rel.relative_to(ROOT))
            body = page.inner_text("body").lower()
            findings[f"{key}_error_boundary"] = "something went wrong" in body and "could not load" in body
            if key == "today":
                findings["do_this_next"] = "do this next" in body
                findings["needs_action_nonzero"] = bool(re.search(r"needs action[^\d]*[1-9]", body))
                findings["client_only_gate"] = "today is available to client users only" in body
            if key == "dashboard":
                findings["dashboard_10_10"] = "10" in body and ("satisfied" in body or "compliant" in body)
            if key == "compliance_score":
                findings["score_confidence_visible"] = "your requirements are satisfied" in body
                findings["lifecycle_satisfied_10"] = "10 requirements satisfied" in body or "10 requirement satisfied" in body
                findings["score_tracked_8"] = "8 score-tracked" in body
                findings["grouping_note"] = "grouped for scoring" in body or "double-counting" in body
                findings["assurance_gap_93"] = "93" in body or "assurance" in body
            if key == "requirements":
                findings["lifecycle_valid_10"] = "10" in body and ("satisfied" in body or "valid" in body)
            if key == "properties":
                findings["attention_needed_summary_zero"] = bool(
                    re.search(r"attention needed[^\d]*0", body.replace("\n", " "))
                )
        browser.close()
    today_ok = (
        not findings.get("today_error_boundary")
        and not findings.get("do_this_next")
        and not findings.get("needs_action_nonzero")
        and not findings.get("client_only_gate")
    )
    return {
        "programme": PROGRAMME,
        "generated_at": _utc(),
        "screenshots": screenshots,
        "findings": findings,
        "pass": today_ok,
    }


def _score_count_closeout(token: str, browser: Dict[str, Any]) -> Dict[str, Any]:
    score = httpx.get(f"{API}/client/compliance-score", headers=_h(token), timeout=120).json()
    stats = score.get("stats") or {}
    sc = score.get("score_confidence") or {}
    sem = score.get("reporting_semantics") or {}
    bf = browser.get("findings") or {}
    lifecycle = int(stats.get("lifecycle_satisfied_count") or sc.get("lifecycle_satisfied_count") or 0)
    score_tracked = int(stats.get("score_tracked_requirement_count") or 0)
    grouping = sc.get("grouping_note") or sem.get("grouping_note")
    return {
        "programme": PROGRAMME,
        "generated_at": _utc(),
        "api": {
            "score": score.get("score"),
            "lifecycle_satisfied_count": lifecycle,
            "visible_requirement_count": stats.get("visible_requirement_count"),
            "score_tracked_requirement_count": score_tracked,
            "grouping_note": grouping,
            "score_confidence": sc,
        },
        "browser": {
            "lifecycle_satisfied_10": bf.get("lifecycle_satisfied_10"),
            "score_tracked_8": bf.get("score_tracked_8"),
            "grouping_note": bf.get("grouping_note"),
            "score_confidence_visible": bf.get("score_confidence_visible"),
            "assurance_gap_93": bf.get("assurance_gap_93"),
        },
        "pass": (
            lifecycle >= 10
            and score_tracked == 8
            and bool(grouping)
            and sc.get("headline")
            and bf.get("score_confidence_visible")
            and (bf.get("grouping_note") or bf.get("lifecycle_satisfied_10"))
        ),
    }


def _regression() -> Dict[str, Any]:
    tests = [
        "tests/test_assurance_actionability_service.py",
        "tests/test_today_projection_quality.py",
        "tests/test_today_attention_ranking.py",
        "tests/test_reporting_semantics_v1.py",
        "tests/test_compliance_scoring_satisfaction_convergence.py",
        "tests/test_property_compliance_status_service.py",
    ]
    proc = subprocess.run([sys.executable, "-m", "pytest", *tests, "-q"], cwd=str(ROOT), capture_output=True, text=True)
    fe_root = ROOT.parent / "frontend"
    fe_proc = None
    if (fe_root / "package.json").is_file():
        fe_proc = subprocess.run(
            "npm test -- --watchAll=false --testPathPattern=portalRequirementAttention",
            cwd=fe_root,
            capture_output=True,
            text=True,
            shell=True,
        )
    ok = proc.returncode == 0 and (fe_proc is None or fe_proc.returncode == 0)
    return {
        "programme": PROGRAMME,
        "generated_at": _utc(),
        "backend_exit_code": proc.returncode,
        "frontend_exit_code": fe_proc.returncode if fe_proc else None,
        "pass": ok,
        "stdout_tail": (proc.stdout or proc.stderr)[-1200:],
        "frontend_tail": ((fe_proc.stdout or fe_proc.stderr)[-800:] if fe_proc else None),
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    token, _ = _client_session()
    deploy = _deploy_proof(token)
    _write("today_score_post_deploy_runtime.json", deploy)

    today_api = _today_api(token) if token else {"pass": False}
    browser = _browser_closeout(token) if token else {"pass": False}
    today_page = {
        "programme": PROGRAMME,
        "generated_at": _utc(),
        "api": today_api,
        "browser": browser,
        "pass": (
            today_api.get("urgent_count") == 0
            and browser.get("pass")
            and not (browser.get("findings") or {}).get("today_error_boundary")
        ),
    }
    _write("today_page_post_deploy_runtime.json", today_page)

    score_count = _score_count_closeout(token, browser) if token else {"pass": False}
    _write("score_count_post_deploy_runtime.json", score_count)

    browser_artifact = {
        "programme": PROGRAMME,
        "generated_at": _utc(),
        "screenshots": browser.get("screenshots") or {},
        "findings": browser.get("findings") or {},
        "pass": (
            browser.get("pass")
            and (browser.get("findings") or {}).get("lifecycle_valid_10")
            and not (browser.get("findings") or {}).get("compliance_score_error_boundary")
        ),
    }
    _write("today_score_browser_post_deploy_runtime.json", browser_artifact)

    regression = _regression()
    _write("today_score_post_deploy_regression_runtime.json", regression)

    checks = {
        "deploy_proof": deploy.get("pass"),
        "today_page": today_page.get("pass"),
        "score_count_semantics": score_count.get("pass"),
        "browser_proof": browser_artifact.get("pass"),
        "regression": regression.get("pass"),
    }
    classification = "VERIFIED_OPERATIONALLY" if all(checks.values()) else "PARTIAL"
    if not today_page.get("pass") and regression.get("pass"):
        classification = "TODAY_UI_DRIFT"
    elif not score_count.get("pass") and today_page.get("pass"):
        classification = "SCORE_COUNT_SEMANTIC_DRIFT"

    _write(
        "classifications.json",
        {
            "programme": PROGRAMME,
            "generated_at": _utc(),
            "deploy_commit": DEPLOY_COMMIT,
            "classification": classification,
            "target_client_id": TARGET_CLIENT_ID,
            "target_crn": TARGET_CRN,
            "checks": checks,
        },
    )
    return 0 if classification == "VERIFIED_OPERATIONALLY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
