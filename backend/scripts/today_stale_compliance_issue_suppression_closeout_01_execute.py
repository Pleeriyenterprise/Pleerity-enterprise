#!/usr/bin/env python3
"""TODAY-STALE-COMPLIANCE-ISSUE-SUPPRESSION-CLOSEOUT-01 — post-deploy verification."""
from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
import time
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

OUT = ROOT / "docs/audit/plan_based_business_outcome_runtime_audit_01"
SHOT = OUT / "closeout_screenshots"
PROGRAMME = "TODAY-STALE-COMPLIANCE-ISSUE-SUPPRESSION-CLOSEOUT-01"
DEPLOY_COMMIT = "93ec5951"
RUN_TAG = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
MARKER = f"TODAY-STALE-ISSUE-CLOSEOUT-{RUN_TAG}"

SOPHIE_CID = "10b2ddba-e952-4484-91d1-a8f0299d0824"
PARTIAL_CLIENTS = {
    "B": "616258a5-51a6-4def-aa00-baa1598b2557",
    "F": "6bcc43c0-16f4-46a5-adf4-26693a0919d0",
    "I": "6fd5ac4c-3fd4-4112-ade7-156977deb49f",
}

_closeout_path = ROOT / "scripts/plan_based_business_outcome_fixture_closeout_01_execute.py"
_spec = importlib.util.spec_from_file_location("_plan_fixture_closeout", _closeout_path)
_fc = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_fc)

API = _fc.API
FRONTEND = _fc.FRONTEND
PACE = float(os.environ.get("OPS_API_PACE_S", "4"))
BATCH_PAUSE = float(os.environ.get("PLAN_FIXTURE_BATCH_PAUSE_S", "8"))
DEPLOY_POLL_ATTEMPTS = int(os.environ.get("STALE_ISSUE_DEPLOY_POLL_ATTEMPTS", "12"))
DEPLOY_POLL_SECONDS = int(os.environ.get("STALE_ISSUE_DEPLOY_POLL_SECONDS", "30"))


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_artifact(name: str, data: Any) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


def source_deploy_markers() -> Dict[str, Any]:
    uts = (ROOT / "services/unified_tasks_service.py").read_text(encoding="utf-8")
    tps = (ROOT / "services/today_projection_service.py").read_text(encoding="utf-8")
    markers = {
        "suppress_stale_compliance_issue_tasks": "_suppress_stale_compliance_issue_tasks" in uts,
        "suppress_called_in_get_unified": "await _suppress_stale_compliance_issue_tasks" in uts,
        "operational_root_key_in_action_to_task": 'task_metadata["operational_root_key"]' in uts,
        "today_filter_before_compact": "if filter_non_actionable:" in tps
        and "working = [dict(x) for x in tasks]" in tps
        and "_task_for_actionability_check" in tps,
    }
    try:
        rev = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(ROOT.parent),
            capture_output=True,
            text=True,
            check=True,
        )
        head = rev.stdout.strip()
    except Exception:
        head = ""
    try:
        log = subprocess.run(
            ["git", "log", "-1", "--oneline", DEPLOY_COMMIT],
            cwd=str(ROOT.parent),
            capture_output=True,
            text=True,
        )
        fix_in_history = log.returncode == 0
    except Exception:
        fix_in_history = False
    return {
        "deploy_commit": DEPLOY_COMMIT,
        "repo_head": head,
        "fix_commit_in_history": fix_in_history,
        "markers": markers,
        "all_markers": all(markers.values()),
    }


def sophie_metrics(token: str) -> Dict[str, Any]:
    today = _fc.req("get", "/today/items", token).json()
    tasks_api = _fc.req("get", "/client/tasks", token).json()
    score = _fc.req("get", "/client/compliance-score", token).json()
    summary = today.get("summary") or {}
    today_tasks = today.get("tasks") or {}
    unified_tasks = tasks_api.get("tasks") or {}
    stats = score.get("stats") or {}
    in_prog_today = list(today_tasks.get("in_progress") or [])
    in_prog_unified = list(unified_tasks.get("in_progress") or [])
    urgent = int(summary.get("urgent_count") or 0)
    in_prog = int(summary.get("in_progress_count") or 0)
    satisfied = int(stats.get("satisfied") or 0)
    total = int(stats.get("total_requirements") or 0)
    all_sat = total > 0 and satisfied >= total and int(stats.get("overdue") or 0) == 0
    calm = urgent == 0 and in_prog == 0
    return {
        "all_satisfied": all_sat,
        "today_calm": calm,
        "urgent_count": urgent,
        "in_progress_count": in_prog,
        "today_in_progress_titles": [t.get("title") for t in in_prog_today],
        "unified_in_progress_count": len(in_prog_unified),
        "unified_in_progress_titles": [t.get("title") for t in in_prog_unified],
        "score": score.get("score"),
        "gap_engine_open": (stats.get("gap_engine") or {}).get("total_open"),
        "gap_engine_by_kind": (stats.get("gap_engine") or {}).get("by_kind"),
    }


def poll_staging_deploy(admin_t: str, step_up: str) -> Dict[str, Any]:
    attempts: List[Dict[str, Any]] = []
    health_r = httpx.get(f"{API}/health", timeout=60)
    health_ok = health_r.status_code == 200
    deployed = False
    metrics: Dict[str, Any] = {}
    for i in range(1, DEPLOY_POLL_ATTEMPTS + 1):
        token, err = _fc.impersonate(admin_t, step_up, SOPHIE_CID, f"{PROGRAMME} deploy poll {i}")
        if err:
            attempts.append({"attempt": i, "error": err})
            time.sleep(DEPLOY_POLL_SECONDS)
            admin_t, _, step_up, _ = _fc.admin_session()
            continue
        metrics = sophie_metrics(token)
        deployed = metrics.get("today_calm") and metrics.get("all_satisfied")
        attempts.append({"attempt": i, "generated_at": utc(), **metrics, "deployed_behavior": deployed})
        if deployed:
            break
        time.sleep(DEPLOY_POLL_SECONDS)
        admin_t, _, step_up, _ = _fc.admin_session()
    return {
        "health_status": health_r.status_code,
        "health_ok": health_ok,
        "deployed_behavior": deployed,
        "final_metrics": metrics,
        "attempts": attempts,
        "pass": health_ok and deployed,
    }


def sophie_recheck(admin_t: str, step_up: str) -> Dict[str, Any]:
    token, err = _fc.impersonate(admin_t, step_up, SOPHIE_CID, f"{PROGRAMME} sophie recheck")
    if err:
        return {"pass": False, "error": err}
    metrics = sophie_metrics(token)
    today = _fc.req("get", "/today/items", token).json()
    hero = today.get("hero") or today.get("digest") or {}
    checks = {
        "all_satisfied": metrics.get("all_satisfied"),
        "urgent_zero": metrics.get("urgent_count") == 0,
        "in_progress_zero": metrics.get("in_progress_count") == 0,
        "today_calm": metrics.get("today_calm"),
        "no_stale_issue_titles": not any(
            "review the uploaded file" in str(t).lower() or "upload the correct certificate" in str(t).lower()
            for t in metrics.get("today_in_progress_titles") or []
        ),
        "no_do_this_next": "do this next" not in json.dumps(today).lower(),
        "no_needs_action": "needs action" not in json.dumps(today).lower(),
    }
    screenshot = None
    if sync_playwright:
        SHOT.mkdir(parents=True, exist_ok=True)
        shot_name = "sophie_today_stale_issue_closeout.png"
        try:
            admin_t2, _, step2, _ = _fc.admin_session()
            token2, _ = _fc.impersonate(admin_t2, step2 or "", SOPHIE_CID, f"{PROGRAMME} browser")
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                ctx = browser.new_context(viewport={"width": 1440, "height": 900})
                user_blob = json.dumps({"client_id": SOPHIE_CID, "role": "ROLE_CLIENT_ADMIN", "impersonation": True})
                ctx.add_init_script(
                    f"localStorage.setItem('auth_token', {json.dumps(token2)});"
                    f"localStorage.setItem('user', {json.dumps(user_blob)});"
                )
                page = ctx.new_page()
                page.goto(f"{FRONTEND}/today", wait_until="domcontentloaded", timeout=120_000)
                page.wait_for_timeout(3000)
                page.screenshot(path=str(SHOT / shot_name))
                browser.close()
            screenshot = shot_name
        except Exception as exc:
            screenshot = f"error:{str(exc)[:120]}"
    return {
        "client_id": SOPHIE_CID,
        "crn": "PLE-CVP-2026-000023",
        "name": "Sophie Walker",
        "metrics": metrics,
        "checks": checks,
        "hero_snapshot": {k: hero.get(k) for k in ("headline", "subheadline", "primary_cta_label") if hero.get(k)},
        "screenshot": screenshot,
        "pass": all(checks.values()),
    }


def gap_reconciliation(admin_t: str, step_up: str) -> Dict[str, Any]:
    token, err = _fc.impersonate(admin_t, step_up, SOPHIE_CID, f"{PROGRAMME} gap reconcile")
    if err:
        return {"pass": False, "error": err}
    score = _fc.req("get", "/client/compliance-score", token).json()
    stats = score.get("stats") or {}
    gap = stats.get("gap_engine") or {}
    tasks_raw = _fc.req("get", "/client/tasks", token).json()
    today = _fc.req("get", "/today/items", token).json()
    issues_r = _fc.req("get", "/client/maintenance/issues", token, params={"limit": 50})
    issues = (issues_r.json().get("issues") or []) if issues_r.status_code == 200 else []
    open_issues = [i for i in issues if (i.get("status") or "").lower() not in ("closed", "resolved", "cancelled")]
    unified_in_prog = list((tasks_raw.get("tasks") or {}).get("in_progress") or [])
    today_in_prog = list((today.get("tasks") or {}).get("in_progress") or [])
    issue_rows = []
    for iss in open_issues[:20]:
        ork = iss.get("operational_root_key") or ""
        rid = None
        if ork.count(":") >= 3:
            rid = ork.split(":")[2]
        issue_rows.append(
            {
                "issue_id": iss.get("issue_id"),
                "status": iss.get("status"),
                "triggering_rule": iss.get("triggering_rule"),
                "operational_root_key": ork,
                "parsed_requirement_id": rid,
                "created_from": iss.get("created_from"),
            }
        )
    stored_but_suppressed = len(unified_in_prog) == 0 and len(open_issues) > 0 and len(today_in_prog) == 0
    return {
        "gap_engine": {
            "total_open": gap.get("total_open"),
            "by_kind": gap.get("by_kind"),
            "by_severity": gap.get("by_severity"),
        },
        "open_maintenance_issues_count": len(open_issues),
        "issue_sample": issue_rows,
        "unified_in_progress_count": len(unified_in_prog),
        "today_in_progress_count": len(today_in_prog),
        "stored_but_suppressed": stored_but_suppressed,
        "governed_cleanup_needed": len(open_issues) > 0,
        "governed_cleanup_note": "Historical issue rows may remain for audit; user-facing inbox must not surface them when requirement satisfied",
        "pass": len(today_in_prog) == 0,
    }


def non_regression(admin_t: str, step_up: str) -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    for label, cid in [("sophie_all_satisfied", SOPHIE_CID), *[(k, v) for k, v in PARTIAL_CLIENTS.items()]]:
        admin_t, _, step_up, _ = _fc.admin_session()
        token, err = _fc.impersonate(admin_t, step_up or "", cid, f"{PROGRAMME} nonreg {label}")
        if err:
            rows.append({"label": label, "client_id": cid, "pass": False, "error": err})
            time.sleep(BATCH_PAUSE)
            continue
        m = sophie_metrics(token) if cid == SOPHIE_CID else _partial_metrics(token)
        if label == "sophie_all_satisfied":
            ok = m.get("today_calm") and m.get("all_satisfied")
        elif label == "B":
            # Solo partial: must remain unsatisfied; calm Today acceptable if requirements hold gaps
            ok = not m.get("all_satisfied") and (m.get("requirement_unsatisfied") or 0) > 0
        else:
            # Portfolio/Professional partial: must show operational urgency in Today buckets
            ok = not m.get("all_satisfied") and (
                (m.get("urgent_count") or 0) > 0 or (m.get("in_progress_count") or 0) > 0
            )
        rows.append({"label": label, "client_id": cid, "metrics": m, "pass": bool(ok)})
        time.sleep(BATCH_PAUSE)
    return {"rows": rows, "pass": all(r.get("pass") for r in rows)}


def _partial_metrics(token: str) -> Dict[str, Any]:
    base = sophie_metrics(token)
    score = _fc.req("get", "/client/compliance-score", token).json()
    stats = score.get("stats") or {}
    total = int(stats.get("total_requirements") or 0)
    sat = int(stats.get("satisfied") or 0)
    base["requirement_unsatisfied"] = max(0, total - sat)
    return base


def run_regression() -> Dict[str, Any]:
    tests = [
        "tests/test_today_projection_quality.py",
        "tests/test_assurance_actionability_service.py",
        "tests/test_requirement_client_runtime_surface.py",
        "tests/test_property_compliance_status_service.py",
        "tests/test_reporting_semantics_v1.py",
    ]
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", *tests, "-q", "--tb=no"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    tail = (proc.stdout or "") + (proc.stderr or "")
    count = 0
    for line in tail.splitlines():
        if " passed" in line and line.strip() and line.strip()[0].isdigit():
            try:
                count = int(line.strip().split()[0])
            except ValueError:
                pass
    return {"exit_code": proc.returncode, "pass": proc.returncode == 0, "tests_run": count or None, "stdout_tail": tail[-2500:]}


def classify(results: Dict[str, bool], flags: List[str]) -> str:
    if results.get("verified"):
        return "VERIFIED_OPERATIONALLY"
    if "TODAY_STALE_ISSUE_DRIFT" in flags:
        return "TODAY_STALE_ISSUE_DRIFT"
    if "USER_OUTCOME_DRIFT" in flags:
        return "USER_OUTCOME_DRIFT"
    if flags:
        return "PARTIAL"
    return "FAIL_OPERATIONAL"


def main() -> int:
    print(f"{PROGRAMME} {RUN_TAG}")
    flags: List[str] = []

    source = source_deploy_markers()
    admin_t, _, step_up, login_err = _fc.admin_session()
    poll = {"pass": False, "error": login_err or "no_admin"}
    if admin_t:
        poll = poll_staging_deploy(admin_t, step_up or "")
    deploy = {
        "programme": PROGRAMME,
        "generated_at": utc(),
        "marker": MARKER,
        "source": source,
        "staging": poll,
        "pass": source.get("all_markers") and poll.get("pass"),
    }
    write_artifact("today_stale_issue_deploy_runtime.json", deploy)
    if not poll.get("pass"):
        flags.append("TODAY_STALE_ISSUE_DRIFT")

    sophie = {"pass": False, "error": "skipped"}
    if admin_t:
        admin_t, _, step_up, _ = _fc.admin_session()
        sophie = sophie_recheck(admin_t, step_up or "")
    write_artifact("sophie_today_stale_issue_runtime.json", {"programme": PROGRAMME, "generated_at": utc(), **sophie})
    if not sophie.get("pass"):
        flags.append("USER_OUTCOME_DRIFT")

    reconcile = {"pass": False}
    if admin_t:
        admin_t, _, step_up, _ = _fc.admin_session()
        reconcile = gap_reconciliation(admin_t, step_up or "")
    write_artifact("stale_gap_engine_reconciliation_runtime.json", {"programme": PROGRAMME, "generated_at": utc(), **reconcile})

    nonreg = {"pass": False}
    if admin_t:
        nonreg = non_regression(admin_t, step_up or "")
    write_artifact("today_stale_issue_non_regression_runtime.json", {"programme": PROGRAMME, "generated_at": utc(), **nonreg})
    if not nonreg.get("pass"):
        flags.append("TODAY_STALE_ISSUE_DRIFT")

    regression = run_regression()
    write_artifact("today_stale_issue_regression_runtime.json", {"programme": PROGRAMME, "generated_at": utc(), **regression})

    results = {
        "deploy": deploy.get("pass"),
        "sophie_today": sophie.get("pass"),
        "gap_reconciliation": reconcile.get("pass"),
        "non_regression": nonreg.get("pass"),
        "regression": regression.get("pass"),
        "browser": bool(sophie.get("screenshot")) and not str(sophie.get("screenshot", "")).startswith("error:"),
    }
    results["verified"] = all(results.values())
    classification = classify(results, sorted(set(flags)))

    write_artifact(
        "classifications.json",
        {
            "programme": PROGRAMME,
            "prior_programme": "PLAN-OUTCOME-FIXTURE-SEEDING-AND-CLOSEOUT-01",
            "generated_at": utc(),
            "marker": MARKER,
            "classification": classification,
            "secondary_flags": sorted(set(flags)),
            "results": results,
            "deploy_commit": DEPLOY_COMMIT,
        },
    )

    report = [
        f"# {PROGRAMME}",
        "",
        f"**Classification:** `{classification}`",
        f"**Deploy commit:** `{DEPLOY_COMMIT}`",
        f"**Marker:** `{MARKER}`",
        "",
        "## Deploy proof",
        "",
        f"- Source markers: {source.get('all_markers')}",
        f"- Staging Sophie Today calm: {sophie.get('checks', {}).get('today_calm')}",
        f"- in_progress_count: {sophie.get('metrics', {}).get('in_progress_count')}",
        "",
        "## Gap reconciliation",
        "",
        f"- Stored issues, suppressed inbox: {reconcile.get('stored_but_suppressed')}",
        "",
    ]
    (OUT / "REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8")

    watch = [
        "# Watchlist — Today stale compliance issue suppression",
        "",
        f"Status: `{classification}`",
        "",
    ]
    if not sophie.get("pass"):
        watch.append("- [ ] Deploy 93ec5951 to staging or wait for Render rollout; re-run closeout")
    if reconcile.get("governed_cleanup_needed"):
        watch.append("- [ ] Optional: governed backfill to close stale gap-bridge maintenance issues (audit retention)")
    if classification != "VERIFIED_OPERATIONALLY":
        watch.append("- [ ] All-satisfied fixture seeding (A,D,E,G,H) still open from prior programme")
    watch.extend(["", "```bash", "cd backend", "python scripts/today_stale_compliance_issue_suppression_closeout_01_execute.py", "```"])
    (OUT / "watchlist.md").write_text("\n".join(watch) + "\n", encoding="utf-8")

    print(json.dumps({"classification": classification, "results": results, "flags": sorted(set(flags))}, indent=2))
    return 0 if classification == "VERIFIED_OPERATIONALLY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
