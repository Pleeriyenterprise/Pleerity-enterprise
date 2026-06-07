#!/usr/bin/env python3
"""TODAY-HERO-AND-SCORE-SCOPE-POST-DEPLOY-CLOSEOUT-01"""
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
SHOT = OUT / "today_score_scope_post_deploy_screenshots"
PROGRAMME = "TODAY-HERO-AND-SCORE-SCOPE-POST-DEPLOY-CLOSEOUT-01"
DEPLOY_COMMIT = "b0510957"

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
    return imp.json()["access_token"], imp.json().get("user") or {}


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
        "score_based_on_score_tracked": "score based on" in js_text and "score-tracked obligation" in js_text,
        "grouping_note_copy": "grouped for scoring" in js_text or "double-counting" in js_text,
        "urgent_hero_gate": "urgentHeroTasks" in js_text or "urgent_count" in js_text,
        "no_sorted0_fallback_comment": "sorted[0]" not in js_text,
        "registry_display_semantics": "compliance-score-scope-copy" in js_text or "requirements satisfied on file" in js_text,
    }
    return {
        "frontend_url": FRONTEND,
        "html_status": html_r.status_code,
        "main_bundle_hash": main_hash,
        "markers": markers,
        "deployed_score_scope_ui": markers["score_based_on_score_tracked"] or markers["registry_display_semantics"],
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
    score_tracked = int(stats.get("score_tracked_requirement_count") or 0)
    grouping = sc.get("grouping_note") or sem.get("grouping_note")
    return {
        "programme": PROGRAMME,
        "generated_at": _utc(),
        "expected_commit": DEPLOY_COMMIT,
        "frontend": bundle,
        "api": {
            "score": score_body.get("score"),
            "lifecycle_satisfied_count": lifecycle,
            "visible_requirement_count": stats.get("visible_requirement_count"),
            "score_tracked_requirement_count": score_tracked,
            "has_grouping_note": bool(grouping),
            "grouping_note": grouping,
            "registry_visible_lifecycle_deployed": lifecycle >= 10 and score_tracked == 8,
        },
        "pass": (
            bundle.get("deployed_score_scope_ui")
            and score_body.get("score") == 93
            and lifecycle >= 10
            and score_tracked == 8
            and bool(grouping)
        ),
    }


def _browser_closeout(token: str) -> Dict[str, Any]:
    if sync_playwright is None:
        return {"pass": False, "error": "playwright not installed", "findings": {}, "screenshots": {}}
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
                needs_action_match = re.search(r"needs action\s*(\d+)", body.replace("\n", " "))
                needs_action_count = int(needs_action_match.group(1)) if needs_action_match else None
                findings["needs_action_count"] = needs_action_count
                findings["needs_action_zero"] = needs_action_count == 0
                findings["needs_action_nonzero"] = needs_action_count is not None and needs_action_count > 0
                findings["file_review_hero"] = "review the uploaded file" in body and "do this next" in body
            if key == "dashboard":
                findings["dashboard_10_active"] = "10" in body and ("active" in body or "tracked in requirements" in body)
                findings["dashboard_8_score_tracked"] = "8" in body and "score-tracked" in body
            if key == "compliance_score":
                findings["lifecycle_satisfied_10"] = "10 requirements satisfied" in body
                findings["score_tracked_8"] = "8 score-tracked" in body
                findings["grouping_note"] = "grouped for scoring" in body or "double-counting" in body
                findings["score_93"] = "93" in body
                findings["achievability_copy"] = "100/100" in body or "platform-verified" in body
            if key == "requirements":
                findings["lifecycle_valid_10"] = "10" in body and ("satisfied" in body or "valid" in body)
            if key == "properties":
                findings["attention_needed_zero"] = bool(
                    re.search(r"attention needed[^\d]*0", body.replace("\n", " "))
                )
        browser.close()

    today_ok = (
        not findings.get("today_error_boundary")
        and not findings.get("do_this_next")
        and not findings.get("needs_action_nonzero")
        and findings.get("needs_action_zero")
    )
    score_ok = (
        findings.get("lifecycle_satisfied_10")
        and findings.get("score_tracked_8")
        and findings.get("grouping_note")
        and findings.get("score_93")
    )
    return {
        "programme": PROGRAMME,
        "generated_at": _utc(),
        "screenshots": screenshots,
        "findings": findings,
        "today_pass": today_ok,
        "score_pass": score_ok,
        "pass": today_ok and score_ok and findings.get("lifecycle_valid_10") and findings.get("attention_needed_zero"),
    }


def _non_regression() -> Dict[str, Any]:
    from services.assurance_actionability_service import (
        ASSURANCE_CONFIDENCE_OPPORTUNITY,
        OPERATIONAL_ACTION,
        classify_score_action,
        task_is_assurance_only_inbox_item,
    )

    scenarios = []
    missing = {"status": "MISSING", "client_lifecycle_state": "ACTION_REQUIRED", "truth_presentation_stage": "collect_evidence"}
    scenarios.append(
        {
            "id": "missing_evidence_operational",
            "classify": classify_score_action({"action": "Upload missing evidence", "priority": "high"}, missing),
            "pass": classify_score_action({"action": "Upload missing evidence", "priority": "high"}, missing) == OPERATIONAL_ACTION,
        }
    )
    rejected = {
        "requirement_id": "r-rej",
        "requirement_type": "epc",
        "truth_presentation_stage": "action_required",
        "evidence_authority_synced_at": "2026-01-01T00:00:00+00:00",
        "evidence_authority": {"version": 1, "state": "REJECTED"},
        "take_action": {
            "primary": {"label": "Replace document", "route": "/documents?property_id=p1"},
        },
    }
    rejected_kind = classify_score_action({"action": "Re-upload rejected evidence", "priority": "high"}, rejected)
    scenarios.append(
        {
            "id": "rejected_operational",
            "classify": rejected_kind,
            "pass": rejected_kind == OPERATIONAL_ACTION,
        }
    )
    overdue = {"status": "OVERDUE", "client_lifecycle_state": "ACTION_REQUIRED"}
    scenarios.append(
        {
            "id": "overdue_operational",
            "classify": classify_score_action({"action": "Renew overdue certificate", "priority": "critical"}, overdue),
            "pass": classify_score_action({"action": "Renew overdue certificate", "priority": "critical"}, overdue) == OPERATIONAL_ACTION,
        }
    )
    file_review_task = {
        "source_type": "issue",
        "title": "Please review the uploaded file",
        "metadata": {
            "requirement_id": "r1",
            "issue_triggering_rule": "MISMATCHED_EVIDENCE",
            "client_lifecycle_state": "SATISFIED_UNVERIFIED",
            "requirement_satisfied": True,
        },
    }
    scenarios.append(
        {
            "id": "assurance_file_review_suppressed",
            "assurance_only": task_is_assurance_only_inbox_item(file_review_task),
            "pass": task_is_assurance_only_inbox_item(file_review_task) is True,
        }
    )
    satisfied = {
        "client_lifecycle_state": "SATISFIED_UNVERIFIED",
        "requirement_satisfied": True,
        "assurance_tier": "SELF_RECORDED",
    }
    scenarios.append(
        {
            "id": "assurance_classified_not_operational",
            "classify": classify_score_action({"action": "Optional assurance"}, satisfied),
            "pass": classify_score_action({"action": "Optional assurance"}, satisfied) == ASSURANCE_CONFIDENCE_OPPORTUNITY,
        }
    )
    ok = all(s.get("pass") for s in scenarios)
    return {"programme": PROGRAMME, "generated_at": _utc(), "scenarios": scenarios, "pass": ok}


def _regression() -> Dict[str, Any]:
    tests = [
        "tests/test_assurance_actionability_service.py",
        "tests/test_today_projection_quality.py",
        "tests/test_reporting_semantics_v1.py",
        "tests/test_compliance_scoring_satisfaction_convergence.py",
        "tests/test_property_compliance_status_service.py",
    ]
    proc = subprocess.run([sys.executable, "-m", "pytest", *tests, "-q"], cwd=str(ROOT), capture_output=True, text=True)
    fe_root = ROOT.parent / "frontend"
    fe_proc = subprocess.run(
        'npm test -- --watchAll=false --testPathPattern="(portalRequirementAttention|todayExecutionWorkspace)"',
        cwd=fe_root,
        capture_output=True,
        text=True,
        shell=True,
    )
    ok = proc.returncode == 0 and fe_proc.returncode == 0
    return {
        "programme": PROGRAMME,
        "generated_at": _utc(),
        "backend_exit_code": proc.returncode,
        "frontend_exit_code": fe_proc.returncode,
        "pass": ok,
        "stdout_tail": (proc.stdout or proc.stderr)[-1000:],
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    token, _ = _client_session()
    deploy = _deploy_proof(token)
    _write("today_score_scope_post_deploy_runtime.json", deploy)

    today_api: Dict[str, Any] = {}
    if token:
        tr = httpx.get(f"{API}/today/items", headers=_h(token), timeout=120)
        if tr.status_code == 200:
            today_api = tr.json().get("summary") or {}

    browser = _browser_closeout(token) if token else {"pass": False, "today_pass": False, "score_pass": False, "findings": {}, "screenshots": {}}
    findings = browser.get("findings") or {}

    _write(
        "today_final_browser_runtime.json",
        {
            "programme": PROGRAMME,
            "generated_at": _utc(),
            "api": {"urgent_count": today_api.get("urgent_count"), "in_progress_count": today_api.get("in_progress_count")},
            "browser": findings,
            "screenshot": (browser.get("screenshots") or {}).get("today"),
            "pass": browser.get("today_pass") and int(today_api.get("urgent_count") or 0) == 0,
        },
    )
    _write(
        "score_scope_final_browser_runtime.json",
        {
            "programme": PROGRAMME,
            "generated_at": _utc(),
            "browser": {k: findings.get(k) for k in (
                "lifecycle_satisfied_10", "score_tracked_8", "grouping_note", "score_93", "achievability_copy",
                "compliance_score_error_boundary",
            )},
            "screenshot": (browser.get("screenshots") or {}).get("compliance_score"),
            "pass": browser.get("score_pass"),
        },
    )
    _write("today_score_scope_full_surface_runtime.json", browser)
    non_regression = _non_regression()
    _write("today_score_scope_non_regression_post_deploy_runtime.json", non_regression)
    regression = _regression()
    _write("today_score_scope_post_deploy_regression_runtime.json", regression)

    checks = {
        "deploy_proof": deploy.get("pass"),
        "today_final": browser.get("today_pass") and int(today_api.get("urgent_count") or 0) == 0,
        "score_scope_final": browser.get("score_pass"),
        "full_surface": browser.get("pass"),
        "non_regression": non_regression.get("pass"),
        "regression": regression.get("pass"),
    }
    classification = "VERIFIED_OPERATIONALLY" if all(checks.values()) else "PARTIAL"
    if not browser.get("today_pass") and regression.get("pass"):
        classification = "TODAY_UI_DRIFT"
    elif browser.get("today_pass") and not browser.get("score_pass"):
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
