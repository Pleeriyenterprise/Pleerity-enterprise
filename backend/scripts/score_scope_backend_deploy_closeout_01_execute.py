#!/usr/bin/env python3
"""SCORE-SCOPE-BACKEND-DEPLOY-CLOSEOUT-01"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
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
SHOT = OUT / "score_scope_backend_closeout_screenshots"
PROGRAMME = "SCORE-SCOPE-BACKEND-DEPLOY-CLOSEOUT-01"
DEPLOY_COMMIT = "b0510957"

TARGET_CLIENT_ID = "10b2ddba-e952-4484-91d1-a8f0299d0824"
TARGET_CRN = "PLE-CVP-2026-000023"

_raw_api = os.environ.get("STAGING_API", "https://pleerity-enterprise.onrender.com").rstrip("/")
API = _raw_api if _raw_api.endswith("/api") else f"{_raw_api}/api"
FRONTEND = os.environ.get("STAGING_FRONTEND", "https://pleerityenterprise.co.uk").rstrip("/")

DEPLOY_POLL_ATTEMPTS = int(os.environ.get("SCORE_SCOPE_DEPLOY_POLL_ATTEMPTS", "20"))
DEPLOY_POLL_SECONDS = int(os.environ.get("SCORE_SCOPE_DEPLOY_POLL_SECONDS", "45"))


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
        json={"reason": f"{PROGRAMME} staging backend deploy verification"},
        timeout=120,
    )
    if imp.status_code != 200:
        return None, {}
    return imp.json()["access_token"], imp.json().get("user") or {}


def _h(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _source_markers() -> Dict[str, bool]:
    paths = {
        "reporting_semantics_v1.py": ROOT / "services/reporting_semantics_v1.py",
        "compliance_score.py": ROOT / "services/compliance_score.py",
        "routes_client.py": ROOT / "routes/client.py",
    }
    texts = {k: p.read_text(encoding="utf-8") if p.is_file() else "" for k, p in paths.items()}
    return {
        "apply_registry_display_semantics": "def apply_registry_display_semantics" in texts["reporting_semantics_v1.py"],
        "compute_registry_display_semantic_overrides": "def compute_registry_display_semantic_overrides" in texts["reporting_semantics_v1.py"],
        "compliance_score_apply_registry": "apply_registry_display_semantics" in texts["compliance_score.py"],
        "client_route_apply_registry": "apply_registry_display_semantics" in texts["routes_client.py"],
        "grouping_note_constant": "SCORE_OBLIGATION_GROUPING_NOTE" in texts["reporting_semantics_v1.py"],
    }


def _fetch_score(token: str) -> Dict[str, Any]:
    r = httpx.get(f"{API}/client/compliance-score", headers=_h(token), timeout=120)
    return r.json() if r.status_code == 200 else {}


def _score_metrics(body: Dict[str, Any]) -> Dict[str, Any]:
    stats = body.get("stats") or {}
    sc = body.get("score_confidence") or {}
    sem = body.get("reporting_semantics") or {}
    sem_counts = sem.get("counts") or {}
    visible = int(stats.get("visible_requirement_count") or sem_counts.get("visible_requirement_count") or 0)
    lifecycle = int(
        stats.get("lifecycle_satisfied_count")
        or sc.get("lifecycle_satisfied_count")
        or sem_counts.get("lifecycle_satisfied_count")
        or 0
    )
    score_tracked = int(stats.get("score_tracked_requirement_count") or sem_counts.get("score_tracked_requirement_count") or 0)
    grouping = sc.get("grouping_note") or sem.get("grouping_note")
    return {
        "score": body.get("score"),
        "visible_requirement_count": visible,
        "lifecycle_satisfied_count": lifecycle,
        "score_tracked_requirement_count": score_tracked,
        "has_grouping_note": bool(grouping),
        "grouping_note": grouping,
        "score_confidence_headline": sc.get("headline"),
        "assurance_explanation_present": bool(
            sc.get("headline") or sc.get("detail") or "assurance" in json.dumps(sc).lower()
        ),
    }


def _registry_deployed(metrics: Dict[str, Any]) -> bool:
    return (
        metrics.get("visible_requirement_count") == 10
        and metrics.get("lifecycle_satisfied_count") == 10
        and metrics.get("score_tracked_requirement_count") == 8
        and metrics.get("has_grouping_note")
    )


def _poll_backend_deploy(token: str) -> Dict[str, Any]:
    attempts = []
    for i in range(1, DEPLOY_POLL_ATTEMPTS + 1):
        body = _fetch_score(token)
        metrics = _score_metrics(body)
        ready = _registry_deployed(metrics)
        attempts.append({"attempt": i, "generated_at": _utc(), **metrics, "registry_deployed": ready})
        if ready:
            return {"pass": True, "attempts": attempts, "polls": i}
        if i < DEPLOY_POLL_ATTEMPTS:
            time.sleep(DEPLOY_POLL_SECONDS)
    return {"pass": False, "attempts": attempts, "polls": DEPLOY_POLL_ATTEMPTS}


def _backend_deploy_proof(token: Optional[str], poll: Dict[str, Any]) -> Dict[str, Any]:
    source = _source_markers()
    score_body = _fetch_score(token) if token else {}
    metrics = _score_metrics(score_body)
    health_r = httpx.get(f"{API}/health", timeout=60)
    return {
        "programme": PROGRAMME,
        "generated_at": _utc(),
        "expected_commit": DEPLOY_COMMIT,
        "api_base": API,
        "health_status": health_r.status_code,
        "source_code_markers": source,
        "source_ready": all(source.values()),
        "deploy_poll": poll,
        "api": metrics,
        "registry_visible_lifecycle_deployed": _registry_deployed(metrics),
        "pass": poll.get("pass") and metrics.get("score") == 93 and _registry_deployed(metrics),
    }


def _api_closeout(token: str, metrics: Dict[str, Any]) -> Dict[str, Any]:
    body = _fetch_score(token)
    sc = body.get("score_confidence") or {}
    grouping = metrics.get("grouping_note") or ""
    no_missing_implication = metrics.get("lifecycle_satisfied_count", 0) >= 10
    return {
        "programme": PROGRAMME,
        "generated_at": _utc(),
        "metrics": metrics,
        "score_93": metrics.get("score") == 93,
        "lifecycle_10": metrics.get("lifecycle_satisfied_count") == 10,
        "score_tracked_8": metrics.get("score_tracked_requirement_count") == 8,
        "grouping_note_present": metrics.get("has_grouping_note"),
        "no_missing_implication": no_missing_implication,
        "assurance_explanation_present": metrics.get("assurance_explanation_present"),
        "score_confidence_sample": {
            "headline": sc.get("headline"),
            "detail": (sc.get("detail") or "")[:300] if sc.get("detail") else None,
        },
        "pass": (
            metrics.get("score") == 93
            and metrics.get("lifecycle_satisfied_count") == 10
            and metrics.get("score_tracked_requirement_count") == 8
            and metrics.get("has_grouping_note")
            and no_missing_implication
        ),
    }


def _browser_closeout(token: str) -> Dict[str, Any]:
    if sync_playwright is None:
        return {"pass": False, "error": "playwright not installed", "findings": {}, "screenshot": None}
    SHOT.mkdir(parents=True, exist_ok=True)
    findings: Dict[str, Any] = {}
    screenshot_rel = None
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        user_blob = json.dumps({"client_id": TARGET_CLIENT_ID, "role": "ROLE_CLIENT_ADMIN", "impersonation": True})
        context.add_init_script(
            f"localStorage.setItem('auth_token', {json.dumps(token)});"
            f"localStorage.setItem('user', {json.dumps(user_blob)});"
        )
        page = context.new_page()
        page.goto(f"{FRONTEND}/compliance-score", wait_until="networkidle", timeout=120000)
        page.wait_for_timeout(2500)
        rel = SHOT / "01_compliance_score.png"
        page.screenshot(path=str(rel), full_page=True)
        screenshot_rel = str(rel.relative_to(ROOT))
        body = page.inner_text("body").lower()
        findings["error_boundary"] = "something went wrong" in body and "could not load" in body
        findings["lifecycle_satisfied_10"] = "10 requirements satisfied" in body
        findings["score_tracked_8"] = "8 score-tracked" in body
        findings["grouping_note"] = "grouped for scoring" in body or "double-counting" in body
        findings["score_93"] = "93" in body
        findings["confidence_explanation"] = (
            "assurance" in body or "self-recorded" in body or "platform verification" in body
        )
        findings["achievability_copy"] = "100/100" in body or "platform-verified" in body or "optional:" in body
        browser.close()
    ok = (
        not findings.get("error_boundary")
        and findings.get("lifecycle_satisfied_10")
        and findings.get("score_tracked_8")
        and findings.get("grouping_note")
        and findings.get("score_93")
    )
    return {
        "programme": PROGRAMME,
        "generated_at": _utc(),
        "findings": findings,
        "screenshot": screenshot_rel,
        "pass": ok,
    }


def _surface_parity(token: str) -> Dict[str, Any]:
    if sync_playwright is None:
        return {"pass": False, "error": "playwright not installed", "surfaces": {}}
    routes = [
        ("dashboard", "/dashboard"),
        ("compliance_score", "/compliance-score"),
        ("requirements", "/requirements"),
        ("properties", "/properties"),
        ("today", "/today"),
    ]
    surfaces: Dict[str, Any] = {}
    today_api: Dict[str, Any] = {}
    tr = httpx.get(f"{API}/today/items", headers=_h(token), timeout=120)
    if tr.status_code == 200:
        today_api = tr.json().get("summary") or {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        user_blob = json.dumps({"client_id": TARGET_CLIENT_ID, "role": "ROLE_CLIENT_ADMIN", "impersonation": True})
        context.add_init_script(
            f"localStorage.setItem('auth_token', {json.dumps(token)});"
            f"localStorage.setItem('user', {json.dumps(user_blob)});"
        )
        page = context.new_page()
        for key, path in routes:
            page.goto(f"{FRONTEND}{path}", wait_until="networkidle", timeout=120000)
            page.wait_for_timeout(2000)
            body = page.inner_text("body").lower()
            if key == "dashboard":
                surfaces[key] = {
                    "ten_active": "10" in body and ("active" in body or "tracked in requirements" in body),
                    "eight_score_tracked": "8" in body and "score-tracked" in body,
                }
            elif key == "compliance_score":
                surfaces[key] = {
                    "ten_satisfied": "10 requirements satisfied" in body,
                    "eight_score_tracked": "8 score-tracked" in body,
                    "grouping_note": "grouped for scoring" in body or "double-counting" in body,
                }
            elif key == "requirements":
                surfaces[key] = {"ten_ten": "10" in body and ("satisfied" in body or "valid" in body)}
            elif key == "properties":
                surfaces[key] = {
                    "two_valid": "2" in body and "valid" in body,
                    "attention_zero": bool(re.search(r"attention needed[^\d]*0", body.replace("\n", " "))),
                }
            elif key == "today":
                needs_match = re.search(r"needs action\s*(\d+)", body.replace("\n", " "))
                needs_count = int(needs_match.group(1)) if needs_match else None
                surfaces[key] = {
                    "urgent_count_api": int(today_api.get("urgent_count") or 0),
                    "needs_action_count": needs_count,
                    "no_do_this_next": "do this next" not in body,
                    "calm": needs_count == 0 and int(today_api.get("urgent_count") or 0) == 0,
                }
        browser.close()

    checks = {
        "dashboard": surfaces.get("dashboard", {}).get("ten_active") and surfaces.get("dashboard", {}).get("eight_score_tracked"),
        "compliance_score": all(surfaces.get("compliance_score", {}).get(k) for k in ("ten_satisfied", "eight_score_tracked", "grouping_note")),
        "requirements": surfaces.get("requirements", {}).get("ten_ten"),
        "properties": surfaces.get("properties", {}).get("two_valid") and surfaces.get("properties", {}).get("attention_zero"),
        "today": surfaces.get("today", {}).get("calm"),
    }
    return {
        "programme": PROGRAMME,
        "generated_at": _utc(),
        "surfaces": surfaces,
        "checks": checks,
        "pass": all(checks.values()),
    }


def _regression() -> Dict[str, Any]:
    tests = [
        "tests/test_reporting_semantics_v1.py",
        "tests/test_compliance_scoring_satisfaction_convergence.py",
        "tests/test_assurance_actionability_service.py",
        "tests/test_property_compliance_status_service.py",
        "tests/test_today_projection_quality.py",
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
    if not token:
        print("auth failed", file=sys.stderr)
        return 2

    poll = _poll_backend_deploy(token)
    deploy = _backend_deploy_proof(token, poll)
    metrics = deploy.get("api") or {}
    _write("score_scope_backend_deploy_runtime.json", deploy)

    api_closeout = _api_closeout(token, metrics)
    _write("score_scope_api_closeout_runtime.json", api_closeout)

    browser = _browser_closeout(token)
    _write("score_scope_browser_closeout_runtime.json", browser)

    parity = _surface_parity(token)
    _write("score_scope_surface_parity_runtime.json", parity)

    regression = _regression()
    _write("score_scope_backend_regression_runtime.json", regression)

    checks = {
        "backend_deploy": deploy.get("pass"),
        "api_closeout": api_closeout.get("pass"),
        "browser_closeout": browser.get("pass"),
        "surface_parity": parity.get("pass"),
        "regression": regression.get("pass"),
    }
    classification = "VERIFIED_OPERATIONALLY" if all(checks.values()) else "SCORE_COUNT_SEMANTIC_DRIFT"
    if not deploy.get("pass") and not browser.get("pass"):
        classification = "SCORE_COUNT_SEMANTIC_DRIFT"
    elif deploy.get("pass") and not browser.get("pass"):
        classification = "PARTIAL"
    elif not deploy.get("pass"):
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
            "prior_programme": "TODAY-HERO-AND-SCORE-SCOPE-POST-DEPLOY-CLOSEOUT-01",
            "prior_classification": "SCORE_COUNT_SEMANTIC_DRIFT",
        },
    )
    return 0 if classification == "VERIFIED_OPERATIONALLY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
