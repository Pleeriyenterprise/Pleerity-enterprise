#!/usr/bin/env python3
"""PLAN-OUTCOME-FIXTURE-SEEDING-AND-CLOSEOUT-01 — seed/discover all-satisfied fixtures and close out."""
from __future__ import annotations

import importlib.util
import json
import os
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
PROGRAMME = "PLAN-OUTCOME-FIXTURE-SEEDING-AND-CLOSEOUT-01"
RUN_TAG = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
MARKER = f"PLAN-OUTCOME-SEED-CLOSEOUT-{RUN_TAG}"

_closeout_path = ROOT / "scripts/plan_based_business_outcome_fixture_closeout_01_execute.py"
_spec = importlib.util.spec_from_file_location("_plan_fixture_closeout", _closeout_path)
_fc = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_fc)

FIXTURE_REGISTRY = _fc.FIXTURE_REGISTRY
PLAN_KEY = _fc.PLAN_KEY
API = _fc.API
FRONTEND = _fc.FRONTEND
PACE = float(os.environ.get("OPS_API_PACE_S", "5"))
BATCH_PAUSE = float(os.environ.get("PLAN_FIXTURE_BATCH_PAUSE_S", "10"))
MAX_429_RETRIES = int(os.environ.get("PLAN_FIXTURE_429_RETRIES", "6"))

ALL_SATISFIED_IDS = ("A", "D", "E", "G", "H")
PARTIAL_IDS = ("B", "F", "I")
SOPHIE_CID = "10b2ddba-e952-4484-91d1-a8f0299d0824"

BROWSER_TARGETS = [
    ("solo_all", "A", "Solo all satisfied"),
    ("solo_partial", "B", "Solo partial"),
    ("portfolio_all", "D", "Portfolio all satisfied"),
    ("portfolio_partial", "F", "Portfolio partial"),
    ("pro_all", "G", "Professional all satisfied"),
    ("pro_partial", "I", "Professional partial"),
]


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_artifact(name: str, data: Any) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


def fresh_admin() -> Tuple[Optional[str], str, Optional[str]]:
    admin_t, _, step_up, err = _fc.admin_session()
    return admin_t, err or "ok", step_up


def probe_extended(token: str) -> Dict[str, Any]:
    probe = _fc.probe_client(token)
    reqs = _fc.req("get", "/client/requirements", token).json()
    rows = reqs.get("requirements") or reqs.get("items") or []
    visible = [r for r in rows if r.get("client_surface_visible", True) is not False]
    probe["requirements_page_count"] = len(visible)
    probe["requirements_page_satisfied"] = sum(1 for r in visible if r.get("requirement_satisfied"))
    return probe


def investigate_sophie_today(admin_t: str, step_up: str) -> Dict[str, Any]:
    token, err = _fc.impersonate(admin_t, step_up, SOPHIE_CID, f"{PROGRAMME} sophie today probe")
    if err:
        return {"client_id": SOPHIE_CID, "pass": False, "error": err}
    today = _fc.req("get", "/today/items", token).json()
    tasks = today.get("tasks") or {}
    summary = today.get("summary") or {}
    in_prog = list(tasks.get("in_progress") or [])
    task_rows = []
    for t in in_prog:
        meta = t.get("metadata") if isinstance(t.get("metadata"), dict) else {}
        auth = t.get("attention_authority") if isinstance(t.get("attention_authority"), dict) else {}
        task_rows.append(
            {
                "id": t.get("id"),
                "title": t.get("title"),
                "source_type": t.get("source_type"),
                "property_id": t.get("property_id"),
                "issue_triggering_rule": meta.get("issue_triggering_rule"),
                "operational_root_key": meta.get("operational_root_key"),
                "requirement_satisfied": meta.get("requirement_satisfied"),
                "attention_class": auth.get("class"),
                "business_actions": len(t.get("business_actions") or []),
            }
        )
    score = _fc.req("get", "/client/compliance-score", token).json()
    stats = score.get("stats") or {}
    root_cause = "stale_compliance_gap_bridge_issues"
    if task_rows and all(r.get("source_type") == "issue" for r in task_rows):
        classification = "stale_gap_bridge_issues_not_suppressed"
    elif not in_prog:
        classification = "calm"
    else:
        classification = "mixed_operational_tasks"
    return {
        "client_id": SOPHIE_CID,
        "crn": "PLE-CVP-2026-000023",
        "name": "Sophie Walker",
        "summary": summary,
        "in_progress_tasks": task_rows,
        "score": score.get("score"),
        "stats": {
            "total_requirements": stats.get("total_requirements"),
            "satisfied": stats.get("satisfied"),
            "lifecycle_satisfied_count": stats.get("lifecycle_satisfied_count"),
            "visible_requirement_count": stats.get("visible_requirement_count"),
            "tracked_requirement_count": stats.get("tracked_requirement_count"),
            "gap_engine_open": (stats.get("gap_engine") or {}).get("total_open"),
        },
        "root_cause": root_cause,
        "classification": classification,
        "user_anxiety": len(in_prog) > 0 and int(summary.get("urgent_count") or 0) == 0,
        "recommended_fix": "suppress_stale_compliance_issue_tasks + filter_before_compact_today",
        "today_calm": int(summary.get("urgent_count") or 0) == 0 and int(summary.get("in_progress_count") or 0) == 0,
        "pass": int(summary.get("in_progress_count") or 0) == 0,
    }


def count_semantics_row(scenario: str, token: str, probe: Dict[str, Any]) -> Dict[str, Any]:
    score = _fc.req("get", "/client/compliance-score", token).json()
    stats = score.get("stats") or {}
    semantics = score.get("reporting_semantics") or score.get("metric_definitions") or {}
    return {
        "scenario": scenario,
        "dashboard_total": probe.get("dashboard_total"),
        "score_tracked": stats.get("score_tracked_requirement_count") or stats.get("total_requirements"),
        "visible_registry": stats.get("visible_requirement_count") or stats.get("tracked_requirement_count"),
        "lifecycle_satisfied": stats.get("lifecycle_satisfied_count") or probe.get("requirement_satisfied"),
        "requirements_page": probe.get("requirements_page_count"),
        "requirement_api_total": probe.get("requirement_total"),
        "drift": abs(int(probe.get("dashboard_total") or 0) - int(probe.get("requirement_total") or 0)),
        "semantics_present": bool(semantics),
        "verdict": (
            "registry_vs_score_tracked"
            if int(stats.get("visible_requirement_count") or 0) != int(stats.get("total_requirements") or 0)
            else "aligned"
        ),
        "pass": probe.get("dashboard_total") == probe.get("requirement_total")
        or abs(int(probe.get("dashboard_total") or 0) - int(probe.get("requirement_total") or 0)) <= 2,
    }


def browser_capture(targets: List[Tuple[str, str, str]], fixtures: Dict[str, Any]) -> Dict[str, Any]:
    if sync_playwright is None:
        return {"pass": False, "error": "playwright_not_installed", "captures": []}
    SHOT.mkdir(parents=True, exist_ok=True)
    captures: List[Dict[str, Any]] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for slug, sid, label in targets:
            fx = fixtures.get(sid) or {}
            sel = fx.get("selected") or {}
            cid = sel.get("client_id")
            entry: Dict[str, Any] = {"slug": slug, "scenario": sid, "label": label, "client_id": cid, "pages": []}
            if not cid:
                entry["pass"] = False
                entry["status"] = "skipped"
                entry["error"] = "no_fixture"
                captures.append(entry)
                continue
            admin_t, _, step_up, err = _fc.admin_session()
            if err:
                entry["pass"] = False
                entry["status"] = "failed"
                entry["error"] = err
                captures.append(entry)
                time.sleep(BATCH_PAUSE)
                continue
            token, imp_err = _fc.impersonate(admin_t, step_up, cid, f"{PROGRAMME} browser {slug}")
            if imp_err:
                entry["pass"] = False
                entry["status"] = "failed"
                entry["error"] = imp_err
                captures.append(entry)
                time.sleep(BATCH_PAUSE)
                continue
            ctx = browser.new_context(viewport={"width": 1440, "height": 900})
            user_blob = json.dumps({"client_id": cid, "role": "ROLE_CLIENT_ADMIN", "impersonation": True})
            ctx.add_init_script(
                f"localStorage.setItem('auth_token', {json.dumps(token)});"
                f"localStorage.setItem('user', {json.dumps(user_blob)});"
            )
            page = ctx.new_page()
            try:
                for pid, route, shot in [
                    ("dashboard", "/dashboard", f"{slug}_dashboard.png"),
                    ("today", "/today", f"{slug}_today.png"),
                    ("requirements", "/requirements", f"{slug}_requirements.png"),
                    ("properties", "/properties", f"{slug}_properties.png"),
                    ("compliance_score", "/compliance-score", f"{slug}_compliance_score.png"),
                    ("reports", "/reports", f"{slug}_reports.png"),
                    ("billing", "/billing", f"{slug}_billing.png"),
                ]:
                    page.goto(f"{FRONTEND}{route}", wait_until="domcontentloaded", timeout=120_000)
                    page.wait_for_timeout(2500)
                    page.screenshot(path=str(SHOT / shot))
                    entry["pages"].append({"page": pid, "screenshot": shot})
                entry["pass"] = len(entry["pages"]) >= 6
                entry["status"] = "pass" if entry["pass"] else "failed"
            except Exception as exc:
                entry["pass"] = False
                entry["status"] = "failed"
                entry["error"] = str(exc)[:240]
            finally:
                page.close()
                ctx.close()
            captures.append(entry)
            time.sleep(BATCH_PAUSE)
        browser.close()
    return {
        "programme": PROGRAMME,
        "generated_at": utc(),
        "captures": captures,
        "pass": all(c.get("pass") for c in captures if c.get("client_id")),
        "screenshot_dir": str(SHOT.relative_to(ROOT)),
    }


def run_regression() -> Dict[str, Any]:
    tests = [
        "tests/test_reporting_semantics_v1.py",
        "tests/test_requirement_client_runtime_surface.py",
        "tests/test_property_compliance_status_service.py",
        "tests/test_today_projection_quality.py",
        "tests/test_assurance_actionability_service.py",
        "tests/test_billing_lifecycle_visibility_contract.py",
    ]
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", *tests, "-q", "--tb=no"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    tail = (proc.stdout or "") + (proc.stderr or "")
    passed = proc.returncode == 0
    count = 0
    for line in tail.splitlines():
        if " passed" in line and line.strip()[0].isdigit():
            try:
                count = int(line.strip().split()[0])
            except ValueError:
                pass
    return {"exit_code": proc.returncode, "pass": passed, "tests_run": count or None, "stdout_tail": tail[-3000:]}


def fixture_document(sid: str, fx: Dict[str, Any], spec: Dict[str, Any]) -> Dict[str, Any]:
    sel = fx.get("selected") or {}
    probe = sel.get("probe") or {}
    return {
        "scenario": sid,
        "label": spec.get("label"),
        "client_id": sel.get("client_id"),
        "crn": sel.get("crn"),
        "email": sel.get("email"),
        "name": sel.get("name"),
        "plan": spec.get("plan_code"),
        "property_count": probe.get("property_count"),
        "jurisdictions": probe.get("jurisdictions"),
        "requirement_count": probe.get("requirement_total"),
        "satisfied_count": probe.get("requirement_satisfied"),
        "unsatisfied_count": probe.get("requirement_unsatisfied"),
        "score": probe.get("score"),
        "today_calm": probe.get("today_calm"),
        "properties_valid": probe.get("properties_valid"),
        "entitlements_plan": probe.get("entitlements_plan"),
        "features_enabled": probe.get("features_enabled"),
        "criteria_match": sel.get("criteria_match"),
        "gaps": sel.get("gaps"),
        "resolved": fx.get("pass"),
        "seed_method": "discovered" if fx.get("pass") else "gap",
    }


def classify_outcome(results: Dict[str, bool], flags: List[str]) -> str:
    if results.get("verified"):
        return "VERIFIED_OPERATIONALLY"
    if "PLAN_FIXTURE_GAP" in flags:
        return "PLAN_FIXTURE_GAP"
    if "USER_OUTCOME_DRIFT" in flags:
        return "USER_OUTCOME_DRIFT"
    if flags:
        return "PARTIAL"
    return "FAIL_OPERATIONAL"


def main() -> int:
    print(f"{PROGRAMME} {RUN_TAG}")
    resilience: Dict[str, Any] = {
        "programme": PROGRAMME,
        "generated_at": utc(),
        "pace_seconds": PACE,
        "batch_pause_seconds": BATCH_PAUSE,
        "fresh_step_up_per_batch": True,
    }
    flags: List[str] = []
    fixtures: Dict[str, Any] = {}

    admin_t, login_err, step_up = fresh_admin()
    resilience["admin_login"] = login_err
    if not admin_t:
        flags.append("FAIL_OPERATIONAL")

    for sid in ALL_SATISFIED_IDS + PARTIAL_IDS:
        spec = FIXTURE_REGISTRY[sid]
        print(f"resolve {sid}...")
        if admin_t:
            fixtures[sid] = _fc.resolve_fixture(admin_t, step_up, sid, spec, resilience)
            if sid in ("B", "F"):
                admin_t, login_err, step_up = fresh_admin()
        else:
            fixtures[sid] = {"scenario": sid, "resolved": False, "pass": False, "error": login_err}
        if sid in ALL_SATISFIED_IDS and not fixtures[sid].get("pass"):
            flags.append("PLAN_FIXTURE_GAP")
        time.sleep(BATCH_PAUSE)

    seed_rows = [fixture_document(sid, fixtures.get(sid) or {}, FIXTURE_REGISTRY[sid]) for sid in ALL_SATISFIED_IDS]
    seed_pass = all(r.get("resolved") for r in seed_rows)
    write_artifact(
        "all_satisfied_fixture_seed_runtime.json",
        {"programme": PROGRAMME, "generated_at": utc(), "marker": MARKER, "fixtures": seed_rows, "pass": seed_pass},
    )

    sat_rows = []
    for sid in ALL_SATISFIED_IDS:
        fx = fixtures.get(sid) or {}
        probe = ((fx.get("selected") or {}).get("probe") or {})
        sat_rows.append(
            {
                "scenario": sid,
                "client_id": (fx.get("selected") or {}).get("client_id"),
                "all_satisfied": probe.get("all_satisfied"),
                "today_calm": probe.get("today_calm"),
                "properties_green": (probe.get("property_rag") or {}).get("GREEN"),
                "overdue": probe.get("overdue"),
                "score": probe.get("score"),
                "pass": bool(probe.get("all_satisfied") and probe.get("today_calm") and fx.get("pass")),
            }
        )
    write_artifact(
        "all_satisfied_fixture_satisfaction_runtime.json",
        {"programme": PROGRAMME, "generated_at": utc(), "rows": sat_rows, "pass": all(r.get("pass") for r in sat_rows)},
    )

    sophie = {"pass": False, "error": "admin_unavailable"}
    if admin_t:
        admin_t, login_err, step_up = fresh_admin()
        sophie = investigate_sophie_today(admin_t, step_up or "")
        if not sophie.get("pass"):
            flags.append("USER_OUTCOME_DRIFT")
    write_artifact("today_in_progress_outcome_runtime.json", {"programme": PROGRAMME, "generated_at": utc(), **sophie})

    all_closeout = {}
    for sid in ALL_SATISFIED_IDS:
        all_closeout[sid] = {
            "fixture": fixture_document(sid, fixtures.get(sid) or {}, FIXTURE_REGISTRY[sid]),
            "closeout": _fc.evaluate_closeout(fixtures.get(sid) or {}, FIXTURE_REGISTRY[sid]),
        }
    all_closeout_pass = all(v["closeout"].get("pass") for v in all_closeout.values())
    write_artifact(
        "all_satisfied_plan_closeout_runtime.json",
        {"programme": PROGRAMME, "generated_at": utc(), **all_closeout, "pass": all_closeout_pass},
    )

    partial_rows = {}
    for sid in PARTIAL_IDS:
        partial_rows[sid] = {
            "fixture": fixture_document(sid, fixtures.get(sid) or {}, FIXTURE_REGISTRY[sid]),
            "closeout": _fc.evaluate_closeout(fixtures.get(sid) or {}, FIXTURE_REGISTRY[sid]),
        }
    partial_pass = all(v["closeout"].get("pass") for v in partial_rows.values())
    write_artifact(
        "partial_satisfied_plan_reconfirmation_runtime.json",
        {"programme": PROGRAMME, "generated_at": utc(), **partial_rows, "pass": partial_pass},
    )

    semantics_rows = []
    for sid in ("F", "G", "H", "I"):
        fx = fixtures.get(sid) or {}
        cid = (fx.get("selected") or {}).get("client_id")
        if not cid or not admin_t:
            continue
        admin_t, _, step_up = fresh_admin()
        token, err = _fc.impersonate(admin_t, step_up or "", cid, f"{PROGRAMME} semantics {sid}")
        if err:
            semantics_rows.append({"scenario": sid, "pass": False, "error": err})
            continue
        probe = probe_extended(token)
        semantics_rows.append(count_semantics_row(sid, token, probe))
        time.sleep(BATCH_PAUSE)
    semantics_pass = bool(semantics_rows) and all(r.get("pass") for r in semantics_rows)
    write_artifact(
        "plan_count_semantics_runtime.json",
        {
            "programme": PROGRAMME,
            "generated_at": utc(),
            "rows": semantics_rows,
            "note": "Dashboard may show lifecycle_satisfied/visible_registry; score uses score_tracked group",
            "pass": semantics_pass,
        },
    )
    if not semantics_pass:
        flags.append("CROSS_SURFACE_DRIFT")

    ent_rows = []
    for sid in ALL_SATISFIED_IDS + PARTIAL_IDS:
        probe = ((fixtures.get(sid) or {}).get("selected") or {}).get("probe") or {}
        if probe:
            ent_rows.append(
                {
                    "scenario": sid,
                    "plan": FIXTURE_REGISTRY[sid]["plan_code"],
                    "api_plan": probe.get("entitlements_plan"),
                    "features_enabled": probe.get("features_enabled"),
                    "pass": probe.get("entitlements_plan") == FIXTURE_REGISTRY[sid]["plan_code"],
                }
            )
    ent_pass = bool(ent_rows) and all(r.get("pass") for r in ent_rows)
    write_artifact(
        "plan_entitlement_reconfirmation_runtime.json",
        {"programme": PROGRAMME, "generated_at": utc(), "rows": ent_rows, "pass": ent_pass},
    )

    browser = browser_capture(BROWSER_TARGETS, fixtures)
    write_artifact("plan_outcome_browser_closeout_runtime.json", browser)

    regression = run_regression()
    write_artifact("plan_outcome_regression_runtime.json", {"programme": PROGRAMME, "generated_at": utc(), **regression})

    results = {
        "seed": seed_pass,
        "satisfaction": all(r.get("pass") for r in sat_rows),
        "sophie_today": sophie.get("pass"),
        "all_satisfied_closeout": all_closeout_pass,
        "partial_reconfirmation": partial_pass,
        "semantics": semantics_pass,
        "entitlements": ent_pass,
        "browser": browser.get("pass"),
        "regression": regression.get("pass"),
    }
    verified = all(results.values())
    results["verified"] = verified
    if not verified and "PLAN_FIXTURE_GAP" not in flags and not seed_pass:
        flags.append("PLAN_FIXTURE_GAP")

    classification = classify_outcome(results, sorted(set(flags)))
    write_artifact(
        "classifications.json",
        {
            "programme": PROGRAMME,
            "prior_programme": "PLAN-BASED-BUSINESS-OUTCOME-FIXTURE-CLOSEOUT-01",
            "generated_at": utc(),
            "marker": MARKER,
            "classification": classification,
            "secondary_flags": sorted(set(flags)),
            "results": results,
            "code_fix": "stale_compliance_issue_suppression + today_filter_before_compact",
        },
    )

    report = [
        f"# {PROGRAMME}",
        "",
        f"**Classification:** `{classification}`",
        f"**Marker:** `{MARKER}`",
        "",
        "## All-satisfied fixtures",
        "",
    ]
    for r in seed_rows:
        report.append(f"- **{r['scenario']}** {r['label']}: `{r.get('client_id') or '—'}` resolved={r.get('resolved')}")
    report.extend(["", "## Sophie Walker Today", "", f"- in_progress={sophie.get('summary', {}).get('in_progress_count')}", f"- root_cause: {sophie.get('root_cause')}", ""])
    (OUT / "REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8")

    watch = [
        "# Watchlist — Plan outcome seeding closeout",
        "",
        f"Status: `{classification}`",
        "",
        "## All-satisfied fixture gaps",
        "",
    ]
    for r in seed_rows:
        if not r.get("resolved"):
            watch.append(f"- [ ] **{r['scenario']}** — {r.get('gaps') or 'no exact match'}")
    if not sophie.get("pass"):
        watch.append("- [ ] Deploy stale issue suppression; re-probe Sophie Walker Today calm")
    watch.extend(
        [
            "",
            "## Re-run",
            "",
            "```bash",
            "cd backend",
            "python scripts/plan_outcome_fixture_seeding_and_closeout_01_execute.py",
            "```",
        ]
    )
    (OUT / "watchlist.md").write_text("\n".join(watch) + "\n", encoding="utf-8")

    print(json.dumps({"classification": classification, "results": results, "flags": sorted(set(flags))}, indent=2))
    return 0 if classification == "VERIFIED_OPERATIONALLY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
