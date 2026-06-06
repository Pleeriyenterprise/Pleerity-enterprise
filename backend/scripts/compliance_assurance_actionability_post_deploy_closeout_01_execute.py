#!/usr/bin/env python3
"""COMPLIANCE-ASSURANCE-ACTIONABILITY-POST-DEPLOY-CLOSEOUT-01"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUT = ROOT / "docs/audit/compliance_projection_convergence_runtime_audit_01"
SHOT = OUT / "assurance_post_deploy_screenshots"
PROGRAMME = "COMPLIANCE-ASSURANCE-ACTIONABILITY-POST-DEPLOY-CLOSEOUT-01"
DEPLOY_COMMIT = "28743ee3"

TARGET_CLIENT_ID = "10b2ddba-e952-4484-91d1-a8f0299d0824"
TARGET_CRN = "PLE-CVP-2026-000023"
TARGET_NAME = "Sophie Walker"

_raw_api = os.environ.get("STAGING_API", "https://pleerity-enterprise.onrender.com").rstrip("/")
API = _raw_api if _raw_api.endswith("/api") else f"{_raw_api}/api"
API_ROOT = API.removesuffix("/api") if API.endswith("/api") else API
FRONTEND = os.environ.get("STAGING_FRONTEND", "https://pleerityenterprise.co.uk").rstrip("/")

SATISFIED_STAGES = frozenset(
    {"verified", "declaration_recorded", "evidence_recorded", "assessment_recorded", "recorded_on_file"}
)


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
    user = body.get("user") or {}
    user["impersonation"] = True
    return body["access_token"], user


def _h(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _fetch_frontend_bundle_markers() -> Dict[str, Any]:
    html_r = httpx.get(FRONTEND, timeout=120, follow_redirects=True)
    main_match = re.search(r"/static/js/main\.([a-f0-9]+)\.js", html_r.text)
    main_hash = main_match.group(1) if main_match else None
    js_text = ""
    if main_hash:
        js_r = httpx.get(f"{FRONTEND}/static/js/main.{main_hash}.js", timeout=180)
        js_text = js_r.text if js_r.status_code == 200 else ""
    markers = {
        "assurance_opportunities_literal": "assurance_opportunities" in js_text,
        "assurance_confidence_literal": "score_confidence" in js_text,
        "optional_assurance_label": "OPTIONAL" in js_text or "Assurance confidence" in js_text,
        "isTaskAssuranceOnly": "isTaskAssuranceOnly" in js_text,
    }
    return {
        "frontend_url": FRONTEND,
        "html_status": html_r.status_code,
        "main_bundle_hash": main_hash,
        "markers": markers,
        "deployed_assurance_ui": markers["assurance_opportunities_literal"] or markers["isTaskAssuranceOnly"],
    }


def _deploy_proof(token: Optional[str]) -> Dict[str, Any]:
    bundle = _fetch_frontend_bundle_markers()
    score_body: Dict[str, Any] = {}
    if token:
        r = httpx.get(f"{API}/client/compliance-score", headers=_h(token), timeout=120)
        if r.status_code == 200:
            score_body = r.json()
    stats = score_body.get("stats") or {}
    recs = list(score_body.get("recommendations") or [])
    assurance = list(score_body.get("assurance_opportunities") or [])
    high_assurance_in_ops = [
        x
        for x in recs
        if str(x.get("priority") or "").lower() in ("high", "critical")
        and (
            "self-recorded" in str(x.get("action") or "").lower()
            or x.get("action_kind") == "ASSURANCE_CONFIDENCE_OPPORTUNITY"
        )
    ]
    return {
        "programme": PROGRAMME,
        "generated_at": _utc(),
        "expected_commit": DEPLOY_COMMIT,
        "api": {
            "has_score_confidence": "score_confidence" in score_body and bool(score_body.get("score_confidence")),
            "has_assurance_opportunities_key": "assurance_opportunities" in score_body,
            "assurance_opportunities_count": len(assurance),
            "operational_recommendations_count": len(recs),
            "has_lifecycle_satisfied_count": "lifecycle_satisfied_count" in stats,
            "has_score_tracked_requirement_count": "score_tracked_requirement_count" in stats,
            "has_tracked_requirement_count": "tracked_requirement_count" in stats,
            "legacy_high_assurance_in_operational_recs": high_assurance_in_ops,
        },
        "frontend": bundle,
        "pass": (
            bool(score_body.get("score_confidence"))
            and "assurance_opportunities" in score_body
            and "lifecycle_satisfied_count" in stats
            and len(high_assurance_in_ops) == 0
            and bundle.get("deployed_assurance_ui")
        ),
    }


def _sophie_snapshot(token: str) -> Dict[str, Any]:
    h = _h(token)
    reqs = httpx.get(f"{API}/client/requirements", headers=h, params={"projection": "full"}, timeout=120).json()
    score = httpx.get(f"{API}/client/compliance-score", headers=h, timeout=120).json()
    today = httpx.get(f"{API}/today/items", headers=h, timeout=120).json()
    props = httpx.get(f"{API}/client/properties", headers=h, timeout=120).json()
    dash = httpx.get(f"{API}/client/dashboard", headers=h, timeout=120).json()
    visible = [r for r in (reqs.get("requirements") or []) if r.get("client_surface_visible") is not False]
    satisfied = sum(
        1
        for r in visible
        if str(r.get("truth_presentation_stage") or "").lower() in SATISFIED_STAGES
        or r.get("requirement_satisfied") is True
    )
    properties = list(props.get("properties") or [])
    return {
        "programme": PROGRAMME,
        "generated_at": _utc(),
        "target": {"client_id": TARGET_CLIENT_ID, "crn": TARGET_CRN, "name": TARGET_NAME},
        "requirements_visible": len(visible),
        "requirements_satisfied": satisfied,
        "score": score.get("score"),
        "grade": score.get("grade"),
        "stats": score.get("stats"),
        "score_confidence": score.get("score_confidence"),
        "recommendations": score.get("recommendations") or [],
        "assurance_opportunities": score.get("assurance_opportunities") or [],
        "reporting_semantics": score.get("reporting_semantics"),
        "today_summary": today.get("summary"),
        "today_urgent_count": len((today.get("tasks") or {}).get("urgent") or []),
        "today_in_progress_count": len((today.get("tasks") or {}).get("in_progress") or []),
        "dashboard_compliance_summary": dash.get("compliance_summary"),
        "properties": [
            {
                "property_id": p.get("property_id"),
                "nickname": p.get("nickname"),
                "compliance_status": p.get("compliance_status"),
            }
            for p in properties
        ],
        "checks": {
            "ten_visible": len(visible) == 10,
            "ten_satisfied": satisfied == 10,
            "two_properties": len(properties) == 2,
            "all_green": all((p.get("compliance_status") or "").upper() == "GREEN" for p in properties),
            "no_overdue": int((score.get("stats") or {}).get("overdue") or 0) == 0,
        },
    }


def _today_closeout(token: str, snapshot: Dict[str, Any]) -> Dict[str, Any]:
    today = httpx.get(f"{API}/today/items", headers=_h(token), timeout=120).json()
    urgent = list((today.get("tasks") or {}).get("urgent") or [])
    in_prog = list((today.get("tasks") or {}).get("in_progress") or [])
    return {
        "programme": PROGRAMME,
        "generated_at": _utc(),
        "urgent_count": len(urgent),
        "in_progress_count": len(in_prog),
        "summary": today.get("summary"),
        "pass": len(urgent) == 0,
    }


def _dashboard_closeout(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    recs = list(snapshot.get("recommendations") or [])
    assurance = list(snapshot.get("assurance_opportunities") or [])
    high_ops = [r for r in recs if str(r.get("priority") or "").lower() in ("high", "critical")]
    high_assurance = [r for r in assurance if str(r.get("priority") or "").lower() in ("high", "critical")]
    return {
        "programme": PROGRAMME,
        "generated_at": _utc(),
        "operational_recommendations": recs,
        "assurance_opportunities": assurance,
        "operational_count": len(recs),
        "assurance_count": len(assurance),
        "high_operational": high_ops,
        "high_assurance": high_assurance,
        "pass": len(recs) == 0 and len(high_assurance) == 0 and len(high_ops) == 0,
    }


def _score_page_closeout(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    conf = snapshot.get("score_confidence") or {}
    stats = snapshot.get("stats") or {}
    return {
        "programme": PROGRAMME,
        "generated_at": _utc(),
        "score": snapshot.get("score"),
        "score_confidence": conf,
        "stats": stats,
        "assurance_opportunities": snapshot.get("assurance_opportunities") or [],
        "recommendations": snapshot.get("recommendations") or [],
        "pass": bool(conf.get("detail")) and int(stats.get("overdue") or 0) == 0,
    }


def _count_semantics_closeout(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    stats = snapshot.get("stats") or {}
    dash = snapshot.get("dashboard_compliance_summary") or {}
    lifecycle = int(stats.get("lifecycle_satisfied_count") or 0)
    tracked = int(stats.get("tracked_requirement_count") or 0)
    score_tracked = int(stats.get("score_tracked_requirement_count") or stats.get("total_requirements") or 0)
    dash_satisfied = int(dash.get("satisfied_requirements") or dash.get("compliant") or 0)
    return {
        "programme": PROGRAMME,
        "generated_at": _utc(),
        "lifecycle_satisfied_count": lifecycle,
        "tracked_requirement_count": tracked,
        "score_tracked_requirement_count": score_tracked,
        "requirements_visible": snapshot.get("requirements_visible"),
        "requirements_satisfied": snapshot.get("requirements_satisfied"),
        "dashboard_satisfied": dash_satisfied,
        "dashboard_total": dash.get("total_requirements"),
        "reporting_semantics": snapshot.get("reporting_semantics"),
        "pass": lifecycle == 10 and snapshot.get("requirements_satisfied") == 10 and dash_satisfied >= 10,
    }


def _non_regression() -> Dict[str, Any]:
    from services.assurance_actionability_service import (
        ASSURANCE_CONFIDENCE_OPPORTUNITY,
        OPERATIONAL_ACTION,
        STALE_INVALID,
        classify_score_action,
        task_is_assurance_only_inbox_item,
    )
    from services.today_projection_service import today_task_is_actionable

    satisfied = {
        "requirement_id": "r-s",
        "property_id": "p1",
        "truth_presentation_stage": "recorded_on_file",
        "client_lifecycle_state": "SATISFIED_UNVERIFIED",
        "assurance_tier": "SELF_RECORDED",
        "requirement_satisfied": True,
        "status": "PENDING",
    }
    missing = {
        "requirement_id": "r-m",
        "property_id": "p1",
        "status": "MISSING",
        "truth_presentation_stage": "collect_evidence",
        "client_lifecycle_state": "ACTION_REQUIRED",
    }
    rejected = {
        "requirement_id": "r-r",
        "property_id": "p1",
        "status": "PENDING",
        "truth_presentation_stage": "action_required",
        "client_lifecycle_state": "ACTION_REQUIRED",
        "evidence_authority": {"state": "REJECTED", "version": 1},
        "evidence_authority_synced_at": "2026-01-01T00:00:00Z",
    }
    overdue = {
        "requirement_id": "r-o",
        "property_id": "p1",
        "status": "OVERDUE",
        "truth_presentation_stage": "action_required",
        "client_lifecycle_state": "ACTION_REQUIRED",
    }
    pending_admin = {
        "requirement_id": "r-p",
        "property_id": "p1",
        "status": "PENDING",
        "truth_presentation_stage": "platform_verification_pending",
        "client_lifecycle_state": "PENDING_REVIEW",
        "evidence_authority": {"state": "PENDING_ADMIN_REVIEW", "version": 1},
        "evidence_authority_synced_at": "2026-01-01T00:00:00Z",
    }
    scenarios = [
        {
            "id": "missing_evidence",
            "classify": classify_score_action({"action": "Upload"}, missing),
            "today": today_task_is_actionable(
                {"source_type": "requirement", "metadata": missing, "business_actions": [{"id": "u"}]}
            ),
            "pass": True,
        },
        {
            "id": "rejected",
            "classify": classify_score_action({"action": "Re-upload"}, rejected),
            "pass": classify_score_action({"action": "Re-upload"}, rejected) == OPERATIONAL_ACTION,
        },
        {
            "id": "overdue",
            "classify": classify_score_action({"action": "Renew"}, overdue),
            "pass": classify_score_action({"action": "Renew"}, overdue) == OPERATIONAL_ACTION,
        },
        {
            "id": "self_recorded_satisfied",
            "classify": classify_score_action({"action": "self-recorded awaiting verification"}, satisfied),
            "today_suppressed": task_is_assurance_only_inbox_item(
                {"source_type": "issue", "metadata": {"requirement_id": "r-s", **satisfied}}
            ),
            "pass": True,
        },
        {
            "id": "pending_admin_no_landlord_urgent",
            "classify": classify_score_action({"action": "review"}, pending_admin),
            "today_suppressed": task_is_assurance_only_inbox_item(
                {"source_type": "issue", "metadata": {"requirement_id": "r-p", **pending_admin}}
            ),
            "pass": True,
        },
    ]
    scenarios[0]["pass"] = scenarios[0]["classify"] == OPERATIONAL_ACTION and scenarios[0]["today"]
    scenarios[3]["pass"] = (
        scenarios[3]["classify"] == ASSURANCE_CONFIDENCE_OPPORTUNITY and scenarios[3]["today_suppressed"]
    )
    scenarios[4]["pass"] = scenarios[4]["classify"] != OPERATIONAL_ACTION or scenarios[4]["today_suppressed"]
    return {
        "programme": PROGRAMME,
        "generated_at": _utc(),
        "scenarios": scenarios,
        "pass": all(s["pass"] for s in scenarios),
    }


def _browser_closeout(token: str) -> Dict[str, Any]:
    if sync_playwright is None:
        return {"programme": PROGRAMME, "skipped": True, "pass": False}
    OUT.mkdir(parents=True, exist_ok=True)
    SHOT.mkdir(parents=True, exist_ok=True)
    shots: Dict[str, str] = {}
    findings: Dict[str, Any] = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        context.add_init_script(
            f"localStorage.setItem('auth_token', {json.dumps(token)});"
            f"localStorage.setItem('user', {json.dumps(json.dumps({'client_id': TARGET_CLIENT_ID}))});"
        )
        page = context.new_page()
        routes = [
            ("today", f"{FRONTEND}/today", "01_today.png"),
            ("dashboard", f"{FRONTEND}/dashboard", "02_dashboard.png"),
            ("compliance_score", f"{FRONTEND}/compliance-score", "03_compliance_score.png"),
            ("requirements", f"{FRONTEND}/requirements", "04_requirements.png"),
            ("properties", f"{FRONTEND}/properties", "05_properties.png"),
        ]
        for key, url, fname in routes:
            page.goto(url, wait_until="networkidle", timeout=120000)
            page.wait_for_timeout(2500)
            path = SHOT / fname
            page.screenshot(path=str(path), full_page=True)
            shots[key] = str(path.relative_to(ROOT))
            body = page.inner_text("body").lower()
            if key == "today":
                findings["do_this_next"] = "do this next" in body
                findings["needs_action_nonzero"] = "needs action: 0" not in body and (
                    "needs action" in body or "need action" in body
                )
            if key == "dashboard":
                findings["high_quick_action_red"] = "self-recorded" in body and "high" in body
                findings["optional_assurance_copy"] = "assurance confidence" in body or "optional" in body
            if key == "compliance_score":
                findings["score_confidence_visible"] = "requirements are satisfied" in body or "assurance" in body
                findings["assurance_section"] = "assurance confidence" in body
            if key == "properties":
                findings["attention_needed_summary_zero"] = "attention needed\n0" in body.replace(" ", "") or "attention needed: 0" in body
            if key == "requirements":
                findings["lifecycle_valid_10"] = "lifecycle valid" in body and "10" in body
        browser.close()
    return {
        "programme": PROGRAMME,
        "generated_at": _utc(),
        "screenshots": shots,
        "findings": findings,
        "pass": (
            not findings.get("do_this_next")
            and not findings.get("needs_action_nonzero")
            and findings.get("attention_needed_summary_zero", False)
        ),
    }


def _regression() -> Dict[str, Any]:
    tests = [
        "tests/test_assurance_actionability_service.py",
        "tests/test_today_projection_quality.py",
        "tests/test_today_attention_ranking.py",
        "tests/test_requirement_attention_eligibility_service.py",
        "tests/test_property_compliance_status_service.py",
        "tests/test_requirement_client_runtime_surface.py",
        "tests/test_compliance_scoring_satisfaction_convergence.py",
    ]
    proc = subprocess.run([sys.executable, "-m", "pytest", *tests, "-q"], cwd=str(ROOT), capture_output=True, text=True)
    return {
        "programme": PROGRAMME,
        "generated_at": _utc(),
        "exit_code": proc.returncode,
        "pass": proc.returncode == 0,
        "stdout_tail": (proc.stdout or "")[-3000:],
    }


def main() -> int:
    token, user = _client_session()
    if not token:
        raise SystemExit("Failed to obtain Sophie Walker staging session")

    deploy = _deploy_proof(token)
    _write("assurance_post_deploy_runtime.json", deploy)

    snapshot = _sophie_snapshot(token)
    snapshot["auth_method"] = "impersonation" if user.get("impersonation") else "direct"
    _write("sophie_assurance_snapshot_runtime.json", snapshot)

    today = _today_closeout(token, snapshot)
    _write("today_assurance_post_deploy_runtime.json", today)

    dash = _dashboard_closeout(snapshot)
    _write("dashboard_assurance_post_deploy_runtime.json", dash)

    score_page = _score_page_closeout(snapshot)
    _write("score_page_assurance_post_deploy_runtime.json", score_page)

    counts = _count_semantics_closeout(snapshot)
    _write("count_semantics_post_deploy_runtime.json", counts)

    non_reg = _non_regression()
    _write("assurance_non_regression_runtime.json", non_reg)

    browser = _browser_closeout(token)
    _write("assurance_post_deploy_browser_runtime.json", browser)

    regression = _regression()
    _write("assurance_post_deploy_regression_runtime.json", regression)

    classification = "VERIFIED_OPERATIONALLY"
    if not regression["pass"]:
        classification = "PARTIAL"
    if not deploy.get("pass"):
        classification = "ASSURANCE_ACTIONABILITY_DRIFT" if classification == "VERIFIED_OPERATIONALLY" else classification
    if not today.get("pass") or not browser.get("pass"):
        classification = "TODAY_UI_DRIFT" if classification == "VERIFIED_OPERATIONALLY" else classification
    if not counts.get("pass"):
        classification = "SCORE_COUNT_SEMANTIC_DRIFT" if classification == "VERIFIED_OPERATIONALLY" else classification
    if not dash.get("pass") or not score_page.get("pass"):
        classification = "ASSURANCE_ACTIONABILITY_DRIFT" if classification == "VERIFIED_OPERATIONALLY" else classification

    checks = {
        "deploy_proof": deploy.get("pass"),
        "sophie_snapshot": snapshot.get("checks"),
        "today": today.get("pass"),
        "dashboard": dash.get("pass"),
        "score_page": score_page.get("pass"),
        "count_semantics": counts.get("pass"),
        "non_regression": non_reg.get("pass"),
        "browser": browser.get("pass"),
        "regression": regression.get("pass"),
    }
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

    watchlist: List[str] = []
    if classification != "VERIFIED_OPERATIONALLY":
        if not deploy.get("pass"):
            watchlist.append("Staging API/frontend may not have deployed 28743ee3 — verify Render/Vercel deploy")
        if not counts.get("pass"):
            watchlist.append("Count semantics still diverge — lifecycle vs score-tracked vs dashboard")
        if not today.get("pass") or not browser.get("pass"):
            watchlist.append("Today still shows operational urgency for assurance items")
        if not dash.get("pass"):
            watchlist.append("Dashboard quick actions still show HIGH operational cards for assurance")
    else:
        watchlist.append("None — assurance actionability verified on staging.")

    (OUT / "watchlist.md").write_text(
        "# Watchlist — assurance post-deploy closeout\n\n" + "\n".join(f"- {w}" for w in watchlist) + "\n",
        encoding="utf-8",
    )
    (OUT / "REPORT.md").write_text(
        f"""# {PROGRAMME}

**Classification:** {classification}
**Deploy commit:** `{DEPLOY_COMMIT}`
**Target:** {TARGET_NAME} (`{TARGET_CRN}`)
**Generated:** {_utc()}

## Results

| Part | Pass |
|------|------|
| Deploy proof | {deploy.get('pass')} |
| Sophie snapshot | {snapshot.get('checks')} |
| Today | {today.get('pass')} |
| Dashboard | {dash.get('pass')} |
| Score page | {score_page.get('pass')} |
| Count semantics | {counts.get('pass')} |
| Non-regression | {non_reg.get('pass')} |
| Browser | {browser.get('pass')} |
| Regression | {regression.get('pass')} |

Screenshots: `assurance_post_deploy_screenshots/`
""",
        encoding="utf-8",
    )

    print(json.dumps({"classification": classification, "checks": checks}, indent=2))
    return 0 if classification == "VERIFIED_OPERATIONALLY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
