#!/usr/bin/env python3
"""COMPLIANCE-PROJECTION-CONVERGENCE-POST-DEPLOY-CLOSEOUT-01"""
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

OUT = ROOT / "docs/audit/compliance_projection_convergence_runtime_audit_01/post_deploy_closeout"
SHOT = OUT / "screenshots"
PROGRAMME = "COMPLIANCE-PROJECTION-CONVERGENCE-POST-DEPLOY-CLOSEOUT-01"
DEPLOY_COMMIT = "103649d4"

TARGET_CLIENT_ID = "10b2ddba-e952-4484-91d1-a8f0299d0824"
TARGET_CRN = "PLE-CVP-2026-000023"
TARGET_NAME = "Sophie Walker"
EXPECTED_PROPERTIES = ("Brixton Hill", "Willow Grove")
EXPECTED_REQS_PER_PROPERTY = 5

_raw_api = os.environ.get("STAGING_API", "https://pleerity-enterprise.onrender.com").rstrip("/")
API = _raw_api if _raw_api.endswith("/api") else f"{_raw_api}/api"
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


def _admin_credentials() -> Tuple[str, str]:
    email = os.environ.get("OPS_VERIFY_ADMIN_EMAIL", "aigbochievictory@gmail.com").strip()
    pw = _read_pw(
        ROOT / "docs/audit/ops_verify_01_6fd5ac4c_d35a58ae/.ops_verify_admin_pw.txt",
        "STAGING_ADMIN_PASSWORD",
    )
    if not pw:
        raise RuntimeError("Admin password not found")
    return email, pw


def _admin_login() -> Tuple[str, str]:
    email, pw = _admin_credentials()
    r = httpx.post(f"{API}/auth/admin/login", json={"email": email, "password": pw}, timeout=120)
    r.raise_for_status()
    body = r.json()
    admin_token = body["access_token"]
    step_up = body.get("step_up_token") or ""
    if not step_up:
        su = httpx.post(
            f"{API}/auth/step-up/verify",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"password": pw},
            timeout=120,
        )
        if su.status_code == 200:
            step_up = (su.json() or {}).get("step_up_token") or ""
    return admin_token, step_up


def _admin_headers(admin_token: str, step_up: str = "") -> Dict[str, str]:
    headers = {"Authorization": f"Bearer {admin_token}"}
    if step_up:
        headers["X-Step-Up-Token"] = step_up
    return headers


def _client_session() -> Tuple[str, Dict[str, Any]]:
    """Prefer direct client login; fall back to admin impersonation."""
    email = (
        os.environ.get("SOPHIE_WALKER_EMAIL", "").strip()
        or os.environ.get("STAGING_CLIENT_ADMIN_EMAIL", "").strip()
        or "sophiewalker@mailinator.com"
    )
    pw = os.environ.get("STAGING_CLIENT_ADMIN_PASSWORD", "").strip() or _read_pw(
        ROOT / "docs/audit/ops_verify_01_6fd5ac4c_d35a58ae/.ops_verify_temp_pw.txt",
        "STAGING_CLIENT_PASSWORD",
    )
    if email and pw:
        r = httpx.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=120)
        if r.status_code == 200:
            u = r.json().get("user") or {}
            if u.get("client_id") == TARGET_CLIENT_ID or u.get("customer_reference") == TARGET_CRN:
                return r.json()["access_token"], u
    admin_token, step_up = _admin_login()
    headers = _admin_headers(admin_token, step_up)
    imp = httpx.post(
        f"{API}/admin/clients/{TARGET_CLIENT_ID}/impersonation/start",
        headers=headers,
        params={"ttl_minutes": 30},
        json={"reason": f"{PROGRAMME} post-deploy convergence verification"},
        timeout=120,
    )
    imp.raise_for_status()
    body = imp.json()
    user = body.get("user") or {}
    user["impersonation"] = True
    return body["access_token"], user


def _h(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _requirements(token: str) -> List[Dict[str, Any]]:
    r = httpx.get(f"{API}/client/requirements", headers=_h(token), params={"projection": "full"}, timeout=120)
    r.raise_for_status()
    return list(r.json().get("requirements") or [])


def _today_tasks(token: str) -> Dict[str, Any]:
    r = httpx.get(f"{API}/today/items", headers=_h(token), timeout=120)
    r.raise_for_status()
    return r.json()


def _target_snapshot(token: str, user: Dict[str, Any]) -> Dict[str, Any]:
    props = httpx.get(f"{API}/client/properties", headers=_h(token), timeout=120).json()
    score = httpx.get(f"{API}/client/compliance-score", headers=_h(token), timeout=120).json()
    dash = httpx.get(f"{API}/client/dashboard", headers=_h(token), timeout=120).json()
    properties = list(props.get("properties") or [])
    reqs = _requirements(token)
    visible = [r for r in reqs if r.get("client_surface_visible") is not False]
    by_prop: Dict[str, List[Dict[str, Any]]] = {}
    for r in visible:
        pid = str(r.get("property_id") or "")
        by_prop.setdefault(pid, []).append(r)
    prop_summaries = []
    for p in properties:
        pid = str(p.get("property_id") or "")
        preqs = by_prop.get(pid, [])
        satisfied = sum(
            1
            for r in preqs
            if str(r.get("truth_presentation_stage") or "").lower() in SATISFIED_STAGES
            or r.get("requirement_satisfied") is True
            or str(r.get("client_lifecycle_state") or "").upper() in ("VERIFIED", "SATISFIED_UNVERIFIED")
        )
        prop_summaries.append(
            {
                "property_id": pid,
                "nickname": p.get("nickname") or p.get("address_line_1"),
                "compliance_status": p.get("compliance_status"),
                "requirement_count": len(preqs),
                "satisfied_count": satisfied,
            }
        )
    stats = score.get("stats") or {}
    return {
        "programme": PROGRAMME,
        "generated_at": _utc(),
        "deploy_commit": DEPLOY_COMMIT,
        "target": {
            "client_id": TARGET_CLIENT_ID,
            "crn": TARGET_CRN,
            "name": TARGET_NAME,
            "session_client_id": user.get("client_id"),
            "session_crn": user.get("customer_reference"),
            "auth_method": "impersonation" if user.get("impersonation") else "direct_login",
        },
        "property_count": len(properties),
        "properties": prop_summaries,
        "requirements_visible": len(visible),
        "requirements_satisfied_visible": sum(
            1
            for r in visible
            if str(r.get("truth_presentation_stage") or "").lower() in SATISFIED_STAGES
            or r.get("requirement_satisfied") is True
        ),
        "score": score.get("score"),
        "grade": score.get("grade"),
        "stats": stats,
        "dashboard_compliance_summary": dash.get("compliance_summary"),
        "portfolio_score_pending": score.get("portfolio_score_recalc_pending"),
        "checks": {
            "two_properties": len(properties) == 2,
            "ten_visible_requirements": len(visible) == 10,
            "all_properties_green": all((p.get("compliance_status") or "").upper() == "GREEN" for p in properties) if properties else False,
            "no_overdue": int(stats.get("overdue") or 0) == 0,
            "no_expiring": int(stats.get("expiring_soon") or 0) == 0,
            "satisfied_equals_total": int(stats.get("satisfied") or stats.get("compliant") or 0) == int(stats.get("total_requirements") or 0) if stats.get("total_requirements") else None,
        },
    }


def _today_closeout(token: str, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    body = _today_tasks(token)
    tasks = body.get("tasks") or {}
    urgent = list(tasks.get("urgent") or [])
    in_prog = list(tasks.get("in_progress") or [])
    summary = body.get("summary") or {}
    satisfied_ids = {
        str(r.get("requirement_id"))
        for r in rows
        if str(r.get("truth_presentation_stage") or "").lower() in SATISFIED_STAGES
        or r.get("requirement_satisfied") is True
    }

    def _req_tasks(bucket: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        out = []
        for t in bucket:
            meta = t.get("metadata") or {}
            rid = str(meta.get("requirement_id") or t.get("source_entity_id") or "")
            if t.get("source_type") == "requirement" or rid:
                out.append(
                    {
                        "id": t.get("id"),
                        "title": t.get("title"),
                        "section": t.get("section"),
                        "requirement_id": rid,
                        "leak": rid in satisfied_ids if rid else False,
                    }
                )
        return out

    urgent_req = _req_tasks(urgent)
    in_prog_req = _req_tasks(in_prog)
    leaks = [t for t in urgent_req + in_prog_req if t.get("leak")]
    body_text = " ".join(str(t.get("title") or "") for t in urgent + in_prog).lower()
    return {
        "programme": PROGRAMME,
        "generated_at": _utc(),
        "urgent_count": len(urgent),
        "in_progress_count": len(in_prog),
        "summary": summary,
        "urgent_requirement_tasks": urgent_req[:20],
        "in_progress_requirement_tasks": in_prog_req[:20],
        "satisfied_requirement_leaks": leaks,
        "do_this_next_phrase_present": "do this next" in body_text,
        "checks": {
            "no_urgent_requirement_leaks": len(leaks) == 0,
            "urgent_count_zero": len(urgent) == 0,
            "no_do_this_next_for_satisfied_portfolio": len(leaks) == 0,
        },
        "pass": len(leaks) == 0 and len(urgent) == 0,
    }


def _property_closeout(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    props = snapshot.get("properties") or []
    return {
        "programme": PROGRAMME,
        "generated_at": _utc(),
        "properties": props,
        "amber_count": sum(1 for p in props if (p.get("compliance_status") or "").upper() == "AMBER"),
        "green_count": sum(1 for p in props if (p.get("compliance_status") or "").upper() == "GREEN"),
        "pass": snapshot.get("checks", {}).get("all_properties_green") is True,
    }


def _score_closeout(token: str, snapshot: Dict[str, Any]) -> Dict[str, Any]:
    score = httpx.get(f"{API}/client/compliance-score", headers=_h(token), timeout=120).json()
    stats = score.get("stats") or {}
    recs = list(score.get("recommendations") or [])
    drivers = list(score.get("drivers") or [])
    total = int(stats.get("total_requirements") or 0)
    satisfied = int(stats.get("satisfied") or stats.get("compliant") or 0)
    score_val = score.get("score")
    assurance_note = (
        score_val is not None
        and satisfied == total
        and total > 0
        and float(score_val) < 100
    )
    return {
        "programme": PROGRAMME,
        "generated_at": _utc(),
        "score": score_val,
        "grade": score.get("grade"),
        "stats": stats,
        "recommendations": recs[:10],
        "drivers_count": len(drivers),
        "assurance_confidence_explains_sub_100": assurance_note,
        "checks": {
            "satisfied_count_aligned": satisfied == snapshot.get("requirements_satisfied_visible"),
            "total_tracked_ten": total == 10,
            "valid_display_equals_satisfied": satisfied == int(stats.get("compliant") or 0),
        },
        "pass": satisfied == total and total == 10,
    }


def _quick_actions_closeout(token: str, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    score = httpx.get(f"{API}/client/compliance-score", headers=_h(token), timeout=120).json()
    recs = list(score.get("recommendations") or [])
    satisfied_types = {str(r.get("requirement_type") or "").lower() for r in rows if r.get("requirement_satisfied") is True}
    stale = []
    for rec in recs:
        code = str(rec.get("requirement_code") or "").lower()
        action = str(rec.get("action") or "")
        if code and code in satisfied_types and "self-recorded" in action.lower():
            stale.append(rec)
    return {
        "programme": PROGRAMME,
        "generated_at": _utc(),
        "recommendations_count": len(recs),
        "stale_assurance_cards": stale,
        "recommendations": recs[:10],
        "pass": len(stale) == 0 and len(recs) == 0,
    }


def _live_convergence(snapshot: Dict[str, Any], today: Dict[str, Any], prop: Dict[str, Any], score: Dict[str, Any], quick: Dict[str, Any]) -> Dict[str, Any]:
    matrix = {
        "requirements_satisfied": snapshot.get("requirements_satisfied_visible") == 10,
        "today_no_urgent": today.get("checks", {}).get("urgent_count_zero"),
        "properties_green": prop.get("pass"),
        "score_counts_aligned": score.get("checks", {}).get("satisfied_count_aligned"),
        "quick_actions_clean": quick.get("pass"),
    }
    return {
        "programme": PROGRAMME,
        "generated_at": _utc(),
        "surface_matrix": matrix,
        "all_converged": all(v is True for v in matrix.values()),
        "pass": all(v is True for v in matrix.values()),
    }


def _refresh_closeout(token: str, snapshot: Dict[str, Any]) -> Dict[str, Any]:
    props = httpx.get(f"{API}/client/properties", headers=_h(token), timeout=120).json().get("properties") or []
    dash_props = httpx.get(f"{API}/client/dashboard", headers=_h(token), timeout=120).json().get("properties") or []
    live_api = {str(p.get("property_id")): p.get("compliance_status") for p in props}
    dash_rag = {str(p.get("property_id")): p.get("compliance_status") for p in dash_props}
    aligned = live_api == dash_rag
    return {
        "programme": PROGRAMME,
        "generated_at": _utc(),
        "properties_api_rag": live_api,
        "dashboard_rag": dash_rag,
        "api_dashboard_aligned": aligned,
        "portfolio_score_pending": snapshot.get("portfolio_score_pending"),
        "pass": aligned and snapshot.get("checks", {}).get("all_properties_green"),
    }


def _browser_closeout(token: str) -> Dict[str, Any]:
    if sync_playwright is None:
        return {"programme": PROGRAMME, "skipped": True, "pass": False, "reason": "playwright not installed"}
    OUT.mkdir(parents=True, exist_ok=True)
    SHOT.mkdir(parents=True, exist_ok=True)
    shots: Dict[str, str] = {}
    findings: Dict[str, Any] = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        user_blob = json.dumps({"client_id": TARGET_CLIENT_ID, "role": "ROLE_CLIENT_ADMIN"})
        context.add_init_script(
            f"localStorage.setItem('auth_token', {json.dumps(token)});"
            f"localStorage.setItem('user', {json.dumps(user_blob)});"
        )
        page = context.new_page()
        routes = [
            ("dashboard", f"{FRONTEND}/dashboard", "01_dashboard.png"),
            ("properties", f"{FRONTEND}/properties", "02_properties.png"),
            ("requirements", f"{FRONTEND}/requirements", "03_requirements.png"),
            ("compliance_score", f"{FRONTEND}/compliance-score", "04_compliance_score.png"),
            ("today", f"{FRONTEND}/today", "05_today.png"),
        ]
        for key, url, fname in routes:
            try:
                page.goto(url, wait_until="networkidle", timeout=120000)
                page.wait_for_timeout(2500)
                path = SHOT / fname
                page.screenshot(path=str(path), full_page=True)
                shots[key] = str(path.relative_to(ROOT))
                body = page.inner_text("body").lower()
                if key == "properties":
                    findings["attention_needed_count"] = body.count("attention needed")
                if key == "today":
                    findings["do_this_next"] = "do this next" in body
                    findings["need_action_label"] = "need action" in body or "needs action" in body
            except Exception as exc:
                shots[key] = f"error: {exc}"
        browser.close()
    return {
        "programme": PROGRAMME,
        "generated_at": _utc(),
        "screenshots": shots,
        "findings": findings,
        "pass": findings.get("attention_needed_count", 1) == 0 and not findings.get("do_this_next"),
    }


def _regression() -> Dict[str, Any]:
    tests = [
        "tests/test_property_compliance_status_service.py",
        "tests/test_requirement_attention_eligibility_service.py",
        "tests/test_requirement_client_runtime_surface.py",
        "tests/test_today_attention_ranking.py",
        "tests/test_today_projection_quality.py",
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
    rows = _requirements(token)
    snapshot = _target_snapshot(token, user)
    _write("target_account_runtime_snapshot.json", snapshot)

    today = _today_closeout(token, rows)
    _write("today_page_closeout_runtime.json", today)

    prop = _property_closeout(snapshot)
    _write("property_page_closeout_runtime.json", prop)

    score = _score_closeout(token, snapshot)
    _write("compliance_score_closeout_runtime.json", score)

    quick = _quick_actions_closeout(token, rows)
    _write("quick_actions_closeout_runtime.json", quick)

    live = _live_convergence(snapshot, today, prop, score, quick)
    _write("live_projection_convergence_runtime.json", live)

    refresh = _refresh_closeout(token, snapshot)
    _write("projection_refresh_closeout_runtime.json", refresh)

    browser = _browser_closeout(token)
    _write("projection_browser_closeout_runtime.json", browser)

    regression = _regression()
    _write("projection_closeout_regression_runtime.json", regression)

    classification = "VERIFIED_OPERATIONALLY"
    if not regression["pass"]:
        classification = "PARTIAL"
    if not live.get("pass"):
        if not prop.get("pass"):
            classification = "PROPERTY_RAG_DRIFT"
        elif not today.get("pass"):
            classification = "OPERATIONAL_INBOX_DRIFT" if classification == "VERIFIED_OPERATIONALLY" else classification
        elif not score.get("pass"):
            classification = "SCORE_DRIFT"
        else:
            classification = "PROJECTION_DRIFT"
    if not browser.get("pass") and not browser.get("skipped"):
        classification = "PARTIAL" if classification == "VERIFIED_OPERATIONALLY" else classification

    _write(
        "classifications.json",
        {
            "programme": PROGRAMME,
            "generated_at": _utc(),
            "deploy_commit": DEPLOY_COMMIT,
            "classification": classification,
            "target_client_id": TARGET_CLIENT_ID,
            "target_crn": TARGET_CRN,
            "checks": {
                "target_snapshot": snapshot.get("checks"),
                "today": today.get("pass"),
                "property": prop.get("pass"),
                "score": score.get("pass"),
                "quick_actions": quick.get("pass"),
                "live_convergence": live.get("pass"),
                "refresh": refresh.get("pass"),
                "browser": browser.get("pass"),
                "regression": regression.get("pass"),
            },
        },
    )

    watchlist: List[str] = []
    if classification != "VERIFIED_OPERATIONALLY":
        if not prop.get("pass"):
            watchlist.append("Property RAG still non-GREEN — confirm backend deploy 103649d4 live on Render")
        if not today.get("pass"):
            watchlist.append("Today inbox still shows operational urgency for satisfied requirements")
        if not score.get("pass"):
            watchlist.append("Score stats not aligned to 10/10 satisfied — verify enrich pipeline on staging")
        if score.get("assurance_confidence_explains_sub_100"):
            watchlist.append("Sub-100 score may be intentional assurance confidence — verify UI copy distinguishes compliance vs confidence")
    if browser.get("skipped"):
        watchlist.append("Install playwright for screenshot proof on CI runner")
    (OUT / "watchlist.md").write_text("# Watchlist\n\n" + "\n".join(f"- {w}" for w in watchlist) + ("\n" if watchlist else "- None — operational convergence verified.\n"), encoding="utf-8")

    (OUT / "REPORT.md").write_text(
        f"""# {PROGRAMME}

**Classification:** {classification}
**Deploy commit:** `{DEPLOY_COMMIT}`
**Target:** {TARGET_NAME} (`{TARGET_CRN}`)
**Generated:** {_utc()}

## Results

| Part | Pass |
|------|------|
| Target account | {snapshot.get('checks')} |
| Today | {today.get('pass')} |
| Properties | {prop.get('pass')} |
| Score | {score.get('pass')} |
| Quick actions | {quick.get('pass')} |
| Live convergence | {live.get('pass')} |
| Refresh | {refresh.get('pass')} |
| Browser | {browser.get('pass')} |
| Regression | {regression.get('pass')} |

Screenshots: `post_deploy_closeout/screenshots/`
""",
        encoding="utf-8",
    )

    print(json.dumps({"classification": classification, "live_pass": live.get("pass")}, indent=2))
    return 0 if classification == "VERIFIED_OPERATIONALLY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
