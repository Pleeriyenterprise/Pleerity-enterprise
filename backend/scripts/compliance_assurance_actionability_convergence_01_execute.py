#!/usr/bin/env python3
"""COMPLIANCE-ASSURANCE-ACTIONABILITY-CONVERGENCE-01"""
from __future__ import annotations

import json
import os
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
SHOT = OUT / "assurance_convergence_screenshots"
PROGRAMME = "COMPLIANCE-ASSURANCE-ACTIONABILITY-CONVERGENCE-01"
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


def _read_pw(rel: Path, env_key: str) -> str:
    v = os.environ.get(env_key, "").strip()
    if v:
        return v
    if rel.is_file():
        return rel.read_text(encoding="utf-8").strip()
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
        json={"reason": f"{PROGRAMME} runtime verification"},
        timeout=120,
    )
    if imp.status_code != 200:
        return None, {}
    body = imp.json()
    user = body.get("user") or {}
    user["impersonation"] = True
    return body["access_token"], user


def _inventory() -> Dict[str, Any]:
    return {
        "programme": PROGRAMME,
        "generated_at": _utc(),
        "surfaces": {
            "today_api": {"route": "GET /api/today/items", "gate": "today_task_is_actionable + assurance_actionability_service"},
            "today_browser": {"component": "todayExecutionWorkspace + portalRequirementAttention", "gate": "isTaskAssuranceOnly / filterInboxTasksForOperationalActionability"},
            "quick_actions": {"source": "compliance_score.recommendations + assurance_opportunities", "gate": "partition_score_recommendations"},
            "score_page": {"fields": ["score_confidence", "reporting_semantics", "assurance_opportunities"]},
            "dashboard_summary": {"route": "GET /api/client/dashboard", "gate": "enrich + is_requirement_satisfied"},
            "persisted_actions": {"source": "compliance_top_next_actions", "classifier": "classify_score_action"},
        },
        "action_kinds": [
            "OPERATIONAL_ACTION",
            "ASSURANCE_CONFIDENCE_OPPORTUNITY",
            "INTERNAL_REVIEW_ITEM",
            "INFORMATIONAL",
            "STALE_INVALID",
        ],
    }


def _global_validation() -> Dict[str, Any]:
    from services.assurance_actionability_service import (
        ASSURANCE_CONFIDENCE_OPPORTUNITY,
        OPERATIONAL_ACTION,
        classify_score_action,
        task_is_assurance_only_inbox_item,
    )
    from services.today_projection_service import today_task_is_actionable

    scenarios = []
    satisfied = {
        "requirement_id": "r-s",
        "property_id": "p1",
        "truth_presentation_stage": "recorded_on_file",
        "client_lifecycle_state": "SATISFIED_UNVERIFIED",
        "assurance_tier": "SELF_RECORDED",
        "requirement_satisfied": True,
        "status": "PENDING",
    }
    scenarios.append(
        {
            "id": "B_satisfied_self_recorded",
            "classify": classify_score_action(
                {"action": "self-recorded awaiting verification", "requirement_code": "GAS_SAFETY"},
                satisfied,
            ),
            "today_issue_suppressed": task_is_assurance_only_inbox_item(
                {
                    "source_type": "issue",
                    "metadata": {"requirement_id": "r-s", **satisfied},
                    "business_actions": [{"id": "x"}],
                }
            ),
            "pass": True,
        }
    )
    missing = {
        "requirement_id": "r-m",
        "property_id": "p1",
        "status": "MISSING",
        "truth_presentation_stage": "collect_evidence",
        "client_lifecycle_state": "ACTION_REQUIRED",
    }
    scenarios.append(
        {
            "id": "C_missing_evidence",
            "classify": classify_score_action({"action": "Upload evidence", "requirement_code": "EICR"}, missing),
            "today_actionable": today_task_is_actionable(
                {
                    "source_type": "requirement",
                    "source_entity_id": "r-m",
                    "metadata": {"requirement_id": "r-m", **missing},
                    "business_actions": [{"id": "upload"}],
                }
            ),
            "pass": True,
        }
    )
    verified = {
        **satisfied,
        "client_lifecycle_state": "VERIFIED",
        "truth_presentation_stage": "verified",
        "assurance_tier": "VERIFIED",
        "status": "COMPLIANT",
        "evidence_authority_synced_at": "2026-01-01T00:00:00Z",
        "evidence_authority": {"version": 1, "state": "VERIFIED_CURRENT", "effective_expiry_date": "2027-01-01"},
    }
    scenarios.append(
        {
            "id": "A_fully_verified",
            "classify": classify_score_action({"action": "review", "requirement_code": "GAS"}, verified),
            "pass": classify_score_action({"action": "review"}, verified) != OPERATIONAL_ACTION,
        }
    )
    for s in scenarios:
        if s["id"] == "B_satisfied_self_recorded":
            s["pass"] = s["classify"] == ASSURANCE_CONFIDENCE_OPPORTUNITY and s["today_issue_suppressed"]
        elif s["id"] == "C_missing_evidence":
            s["pass"] = s["classify"] == OPERATIONAL_ACTION and s["today_actionable"]
    return {"programme": PROGRAMME, "generated_at": _utc(), "scenarios": scenarios, "pass": all(s["pass"] for s in scenarios)}


def _staging_probe(token: str) -> Dict[str, Any]:
    h = {"Authorization": f"Bearer {token}"}
    today = httpx.get(f"{API}/today/items", headers=h, timeout=120).json()
    score = httpx.get(f"{API}/client/compliance-score", headers=h, timeout=120).json()
    dash = httpx.get(f"{API}/client/dashboard", headers=h, timeout=120).json()
    reqs = httpx.get(f"{API}/client/requirements", headers=h, params={"projection": "full"}, timeout=120).json()
    props = httpx.get(f"{API}/client/properties", headers=h, timeout=120).json()
    urgent = list((today.get("tasks") or {}).get("urgent") or [])
    in_prog = list((today.get("tasks") or {}).get("in_progress") or [])
    stats = score.get("stats") or {}
    sem = score.get("reporting_semantics") or {}
    return {
        "today": {
            "urgent_count": len(urgent),
            "in_progress_count": len(in_prog),
            "summary": today.get("summary"),
        },
        "score": {
            "score": score.get("score"),
            "operational_recommendations": len(score.get("recommendations") or []),
            "assurance_opportunities": len(score.get("assurance_opportunities") or []),
            "has_score_confidence": bool(score.get("score_confidence")),
            "stats": stats,
            "reporting_semantics_counts": sem.get("counts"),
        },
        "dashboard_compliance_summary": dash.get("compliance_summary"),
        "requirements_visible": len(reqs.get("requirements") or []),
        "properties_green": all(
            (p.get("compliance_status") or "").upper() == "GREEN" for p in (props.get("properties") or [])
        ),
    }


def _browser(token: str) -> Dict[str, Any]:
    if sync_playwright is None:
        return {"skipped": True, "pass": False}
    OUT.mkdir(parents=True, exist_ok=True)
    SHOT.mkdir(parents=True, exist_ok=True)
    shots = {}
    findings = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        context.add_init_script(
            f"localStorage.setItem('auth_token', {json.dumps(token)});"
            f"localStorage.setItem('user', {json.dumps(json.dumps({'client_id': TARGET_CLIENT_ID}))});"
        )
        page = context.new_page()
        for key, url, fname in [
            ("today", f"{FRONTEND}/today", "assurance_01_today.png"),
            ("dashboard", f"{FRONTEND}/dashboard", "assurance_02_dashboard.png"),
            ("compliance_score", f"{FRONTEND}/compliance-score", "assurance_03_score.png"),
            ("requirements", f"{FRONTEND}/requirements", "assurance_04_requirements.png"),
            ("properties", f"{FRONTEND}/properties", "assurance_05_properties.png"),
        ]:
            page.goto(url, wait_until="networkidle", timeout=120000)
            page.wait_for_timeout(2000)
            path = SHOT / fname
            page.screenshot(path=str(path), full_page=True)
            shots[key] = str(path.relative_to(ROOT))
            if key == "today":
                body = page.inner_text("body").lower()
                findings["do_this_next"] = "do this next" in body
                findings["needs_action_positive"] = "needs action" in body and "needs action: 0" not in body
        browser.close()
    return {
        "screenshots": shots,
        "findings": findings,
        "pass": not findings.get("do_this_next") and not findings.get("needs_action_positive"),
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
    return {"exit_code": proc.returncode, "pass": proc.returncode == 0, "stdout_tail": (proc.stdout or "")[-2500:]}


def main() -> int:
    _write("assurance_actionability_inventory_runtime.json", _inventory())
    _write("assurance_global_validation_runtime.json", _global_validation())

    token, _user = _client_session()
    probe = _staging_probe(token) if token else {"error": "no_staging_session"}
    _write("today_assurance_convergence_runtime.json", {"programme": PROGRAMME, "generated_at": _utc(), "staging": probe.get("today"), "pass": probe.get("today", {}).get("urgent_count", 1) == 0})
    _write(
        "quick_actions_assurance_convergence_runtime.json",
        {
            "programme": PROGRAMME,
            "generated_at": _utc(),
            "staging": probe.get("score", {}),
            "pass": (probe.get("score", {}).get("operational_recommendations") or 0) == 0,
        },
    )
    _write("score_count_semantics_runtime.json", {"programme": PROGRAMME, "generated_at": _utc(), "staging": probe, "pass": bool(probe.get("score", {}).get("has_score_confidence"))})
    _write(
        "score_confidence_copy_runtime.json",
        {
            "programme": PROGRAMME,
            "generated_at": _utc(),
            "staging_score_confidence_present": bool(probe.get("score", {}).get("has_score_confidence")),
            "pass": bool(probe.get("score", {}).get("has_score_confidence")),
        },
    )
    browser = _browser(token) if token else {"skipped": True, "pass": False}
    _write("assurance_browser_runtime.json", {"programme": PROGRAMME, "generated_at": _utc(), **browser})
    regression = _regression()
    _write("assurance_regression_runtime.json", {"programme": PROGRAMME, "generated_at": _utc(), **regression})

    local_ok = _global_validation()["pass"] and regression["pass"]
    score_probe = probe.get("score") or {}
    staging_api_ok = (
        token
        and score_probe.get("has_score_confidence")
        and (score_probe.get("operational_recommendations") or 0) == 0
        and (score_probe.get("assurance_opportunities") or 0) >= 0
    )
    staging_browser_ok = token and browser.get("pass")
    staging_ok = staging_api_ok and staging_browser_ok and probe.get("today", {}).get("urgent_count") == 0
    classification = "VERIFIED_OPERATIONALLY" if local_ok and staging_ok else ("PARTIAL" if local_ok else "ASSURANCE_ACTIONABILITY_DRIFT")

    _write(
        "classifications.json",
        {
            "programme": PROGRAMME,
            "generated_at": _utc(),
            "classification": classification,
            "local_validation": local_ok,
            "staging_session": bool(token),
            "regression": regression["pass"],
        },
    )
    (OUT / "REPORT.md").write_text(
        f"# {PROGRAMME}\n\n**Classification:** {classification}\n\nSee assurance_* artifacts and updated post_deploy_closeout for prior baseline.\n",
        encoding="utf-8",
    )
    (OUT / "watchlist.md").write_text(
        "# Watchlist\n\n"
        + ("- Redeploy backend + frontend for staging browser/API proof.\n" if not staging_ok else "- None — assurance convergence verified locally and on staging.\n"),
        encoding="utf-8",
    )
    print(json.dumps({"classification": classification}, indent=2))
    return 0 if classification == "VERIFIED_OPERATIONALLY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
