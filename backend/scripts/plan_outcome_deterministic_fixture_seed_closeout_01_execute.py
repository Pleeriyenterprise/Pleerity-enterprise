#!/usr/bin/env python3
"""PLAN-OUTCOME-DETERMINISTIC-FIXTURE-SEED-CLOSEOUT-01 — discover/verify all-satisfied fixtures A–H."""
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
PROGRAMME = "PLAN-OUTCOME-DETERMINISTIC-FIXTURE-SEED-CLOSEOUT-01"
RUN_TAG = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
MARKER = f"PLAN-DETERMINISTIC-FIXTURE-{RUN_TAG}"

_closeout_path = ROOT / "scripts/plan_based_business_outcome_fixture_closeout_01_execute.py"
_spec = importlib.util.spec_from_file_location("_plan_fixture_closeout", _closeout_path)
_fc = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_fc)

FIXTURE_REGISTRY = _fc.FIXTURE_REGISTRY
PLAN_KEY = _fc.PLAN_KEY
API = _fc.API
FRONTEND = _fc.FRONTEND
BATCH_PAUSE = float(os.environ.get("PLAN_FIXTURE_BATCH_PAUSE_S", "8"))

ALL_SATISFIED = ("A", "D", "E", "G", "H")
PARTIAL = ("B", "F", "I")
ALL_SCENARIOS = ALL_SATISFIED + PARTIAL

BROWSER_TARGETS = [
    ("solo_all_sat", "A", "Solo all-satisfied"),
    ("solo_partial", "B", "Solo partial"),
    ("portfolio_all_same", "D", "Portfolio 5 same jurisdiction all-satisfied"),
    ("portfolio_all_mixed", "E", "Portfolio mixed all-satisfied"),
    ("portfolio_partial", "F", "Portfolio partial"),
    ("pro_all_same", "G", "Professional 3-5 all-satisfied"),
    ("pro_all_mixed", "H", "Professional mixed all-satisfied"),
    ("pro_partial", "I", "Professional partial"),
]


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_artifact(name: str, data: Any) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


def fixture_row(sid: str, fx: Dict[str, Any]) -> Dict[str, Any]:
    spec = FIXTURE_REGISTRY[sid]
    sel = fx.get("selected") or {}
    probe = sel.get("probe") or {}
    rag = probe.get("property_rag") or {}
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
        "today_urgent_count": probe.get("today_urgent_count"),
        "today_in_progress_count": probe.get("today_in_progress_count"),
        "today_calm": probe.get("today_calm"),
        "property_rag": rag,
        "properties_valid": probe.get("properties_valid"),
        "entitlements_plan": probe.get("entitlements_plan"),
        "features_enabled": probe.get("features_enabled"),
        "criteria_match": sel.get("criteria_match"),
        "gaps": sel.get("gaps"),
        "exact_fixture": bool(fx.get("pass")),
        "expected_user_outcome": "calm" if spec.get("expected_today") == "calm" else "operational_action",
    }


def satisfaction_row(sid: str, fx: Dict[str, Any]) -> Dict[str, Any]:
    probe = ((fx.get("selected") or {}).get("probe") or {})
    if not probe:
        return {"scenario": sid, "pass": False, "reason": "no_probe"}
    expected_calm = FIXTURE_REGISTRY[sid].get("expected_today") == "calm"
    checks = {
        "all_satisfied": probe.get("all_satisfied"),
        "overdue_zero": int(probe.get("overdue") or 0) == 0,
        "today_calm": probe.get("today_calm"),
        "properties_valid": probe.get("properties_valid"),
        "score_confidence": probe.get("score_confidence_present") if expected_calm else True,
    }
    if expected_calm:
        return {"scenario": sid, "client_id": (fx.get("selected") or {}).get("client_id"), "checks": checks, "pass": all(checks.values()) and fx.get("pass")}
    return {
        "scenario": sid,
        "client_id": (fx.get("selected") or {}).get("client_id"),
        "checks": {"has_unsatisfied": (probe.get("requirement_unsatisfied") or 0) > 0},
        "pass": (probe.get("requirement_unsatisfied") or 0) > 0,
    }


def plan_closeout(sid: str, fx: Dict[str, Any], extra: Optional[Dict[str, bool]] = None) -> Dict[str, Any]:
    closeout = _fc.evaluate_closeout(fx, FIXTURE_REGISTRY[sid])
    ent = FIXTURE_REGISTRY[sid]["plan_code"]
    probe = ((fx.get("selected") or {}).get("probe") or {})
    checks = dict(closeout.get("checks") or {})
    if extra:
        checks.update(extra)
    checks["entitlement_plan_match"] = probe.get("entitlements_plan") == ent
    return {"fixture": fixture_row(sid, fx), "closeout": closeout, "checks": checks, "pass": closeout.get("pass") and checks.get("entitlement_plan_match")}


def cross_surface_row(sid: str, token: str, probe: Dict[str, Any]) -> Dict[str, Any]:
    dash = _fc.req("get", "/client/dashboard", token).json()
    reqs = _fc.req("get", "/client/requirements", token).json()
    props = _fc.req("get", "/client/properties", token).json()
    score = _fc.req("get", "/client/compliance-score", token).json()
    req_rows = reqs.get("requirements") or reqs.get("items") or []
    visible = [r for r in req_rows if r.get("client_surface_visible", True) is not False]
    dsum = dash.get("compliance_summary") or {}
    return {
        "scenario": sid,
        "dashboard_total": dsum.get("total_requirements"),
        "dashboard_satisfied": dsum.get("compliant"),
        "score_total": (score.get("stats") or {}).get("total_requirements"),
        "requirements_visible": len(visible),
        "properties_count": len(props.get("properties") or []),
        "today_calm": probe.get("today_calm"),
        "pass": abs(int(dsum.get("total_requirements") or 0) - int(probe.get("requirement_total") or 0)) <= 3,
    }


def browser_capture(fixtures: Dict[str, Any]) -> Dict[str, Any]:
    if sync_playwright is None:
        return {"pass": False, "error": "playwright_not_installed", "captures": []}
    SHOT.mkdir(parents=True, exist_ok=True)
    captures: List[Dict[str, Any]] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for slug, sid, label in BROWSER_TARGETS:
            fx = fixtures.get(sid) or {}
            cid = ((fx.get("selected") or {}).get("client_id"))
            entry: Dict[str, Any] = {"slug": slug, "scenario": sid, "label": label, "client_id": cid, "pages": []}
            if not cid:
                entry.update({"pass": False, "status": "skipped", "error": "no_fixture"})
                captures.append(entry)
                continue
            admin_t, _, step_up, err = _fc.admin_session()
            if err:
                entry.update({"pass": False, "status": "failed", "error": err})
                captures.append(entry)
                time.sleep(BATCH_PAUSE)
                continue
            token, imp_err = _fc.impersonate(admin_t, step_up or "", cid, f"{PROGRAMME} browser {slug}")
            if imp_err:
                entry.update({"pass": False, "status": "failed", "error": imp_err})
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
                    page.wait_for_timeout(2200)
                    page.screenshot(path=str(SHOT / shot))
                    entry["pages"].append({"page": pid, "screenshot": shot})
                entry["pass"] = len(entry["pages"]) >= 6
                entry["status"] = "pass" if entry["pass"] else "failed"
            except Exception as exc:
                entry.update({"pass": False, "status": "failed", "error": str(exc)[:200]})
            finally:
                page.close()
                ctx.close()
            captures.append(entry)
            time.sleep(BATCH_PAUSE)
        browser.close()
    with_cid = [c for c in captures if c.get("client_id")]
    return {
        "programme": PROGRAMME,
        "generated_at": utc(),
        "captures": captures,
        "pass": bool(with_cid) and all(c.get("pass") for c in with_cid),
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
    if "PLAN_FIXTURE_GAP" in flags:
        return "PLAN_FIXTURE_GAP"
    if flags:
        return "PARTIAL"
    return "FAIL_OPERATIONAL"


def main() -> int:
    print(f"{PROGRAMME} {RUN_TAG}")
    resilience: Dict[str, Any] = {"programme": PROGRAMME, "generated_at": utc(), "marker": MARKER}
    flags: List[str] = []
    fixtures: Dict[str, Any] = {}

    admin_t, _, step_up, login_err = _fc.admin_session()
    resilience["admin_login"] = login_err or "ok"
    if not admin_t:
        flags.append("FAIL_OPERATIONAL")

    for sid in ALL_SCENARIOS:
        print(f"resolve {sid}...")
        if admin_t:
            fixtures[sid] = _fc.resolve_fixture(admin_t, step_up or "", sid, FIXTURE_REGISTRY[sid], resilience)
            if sid in ("B", "D", "F"):
                admin_t, _, step_up, login_err = _fc.admin_session()
        else:
            fixtures[sid] = {"scenario": sid, "pass": False, "error": login_err}
        if sid in ALL_SATISFIED and not fixtures[sid].get("pass"):
            flags.append("PLAN_FIXTURE_GAP")
        time.sleep(BATCH_PAUSE)

    seed_rows = [fixture_row(sid, fixtures.get(sid) or {}) for sid in ALL_SATISFIED]
    exact = sum(1 for r in seed_rows if r.get("exact_fixture"))
    write_artifact(
        "deterministic_fixture_seed_runtime.json",
        {"programme": PROGRAMME, "generated_at": utc(), "marker": MARKER, "fixtures": seed_rows, "exact_count": f"{exact}/{len(ALL_SATISFIED)}", "pass": exact == len(ALL_SATISFIED)},
    )

    sat_rows = [satisfaction_row(sid, fixtures.get(sid) or {}) for sid in ALL_SCENARIOS]
    write_artifact(
        "deterministic_fixture_satisfaction_runtime.json",
        {"programme": PROGRAMME, "generated_at": utc(), "rows": sat_rows, "pass": all(r.get("pass") for r in sat_rows if r.get("scenario") in ALL_SATISFIED)},
    )

    solo_a = plan_closeout("A", fixtures.get("A") or {})
    write_artifact("solo_all_satisfied_closeout_runtime.json", {"programme": PROGRAMME, "generated_at": utc(), "A": solo_a, "pass": solo_a.get("pass")})

    port = {sid: plan_closeout(sid, fixtures.get(sid) or {}) for sid in ("D", "E")}
    write_artifact(
        "portfolio_all_satisfied_closeout_runtime.json",
        {"programme": PROGRAMME, "generated_at": utc(), **port, "pass": all(v.get("pass") for v in port.values())},
    )

    pro = {sid: plan_closeout(sid, fixtures.get(sid) or {}) for sid in ("G", "H")}
    write_artifact(
        "professional_all_satisfied_closeout_runtime.json",
        {"programme": PROGRAMME, "generated_at": utc(), **pro, "pass": all(v.get("pass") for v in pro.values())},
    )

    partial = {sid: plan_closeout(sid, fixtures.get(sid) or {}) for sid in PARTIAL}
    write_artifact(
        "partial_outcome_reconfirmation_runtime.json",
        {"programme": PROGRAMME, "generated_at": utc(), **partial, "pass": all(v.get("pass") for v in partial.values())},
    )

    cross_rows = []
    for sid in ALL_SCENARIOS:
        fx = fixtures.get(sid) or {}
        cid = (fx.get("selected") or {}).get("client_id")
        probe = (fx.get("selected") or {}).get("probe") or {}
        if not cid or not admin_t:
            continue
        admin_t, _, step_up, _ = _fc.admin_session()
        token, err = _fc.impersonate(admin_t, step_up or "", cid, f"{PROGRAMME} cross {sid}")
        if err:
            cross_rows.append({"scenario": sid, "pass": False, "error": err})
            continue
        cross_rows.append(cross_surface_row(sid, token, probe))
        time.sleep(BATCH_PAUSE)
    cross_pass = bool(cross_rows) and all(r.get("pass") for r in cross_rows)
    write_artifact("plan_outcome_cross_surface_runtime.json", {"programme": PROGRAMME, "generated_at": utc(), "rows": cross_rows, "pass": cross_pass})
    if not cross_pass:
        flags.append("CROSS_SURFACE_DRIFT")

    browser = browser_capture(fixtures)
    write_artifact("plan_outcome_browser_proof_runtime.json", browser)

    regression = run_regression()
    write_artifact("plan_outcome_final_regression_runtime.json", {"programme": PROGRAMME, "generated_at": utc(), **regression})

    results = {
        "fixtures_exact": exact == len(ALL_SATISFIED),
        "satisfaction": all(r.get("pass") for r in sat_rows if r.get("scenario") in ALL_SATISFIED),
        "solo_all": solo_a.get("pass"),
        "portfolio_all": all(port[s].get("pass") for s in port),
        "professional_all": all(pro[s].get("pass") for s in pro),
        "partial": all(partial[s].get("pass") for s in partial),
        "cross_surface": cross_pass,
        "browser": browser.get("pass"),
        "regression": regression.get("pass"),
    }
    results["verified"] = all(results.values())
    if exact < len(ALL_SATISFIED):
        flags.append("PLAN_FIXTURE_GAP")
    classification = classify(results, sorted(set(flags)))

    write_artifact(
        "classifications.json",
        {
            "programme": PROGRAMME,
            "prior_programme": "TODAY-STALE-COMPLIANCE-ISSUE-SUPPRESSION-CLOSEOUT-01",
            "generated_at": utc(),
            "marker": MARKER,
            "classification": classification,
            "secondary_flags": sorted(set(flags)),
            "results": results,
            "exact_fixtures": f"{exact}/{len(ALL_SATISFIED)}",
        },
    )

    report = [
        f"# {PROGRAMME}",
        "",
        f"**Classification:** `{classification}`",
        f"**Marker:** `{MARKER}`",
        f"**Exact fixtures:** {exact}/{len(ALL_SATISFIED)}",
        "",
        "## All-satisfied fixtures",
        "",
    ]
    for r in seed_rows:
        report.append(f"- **{r['scenario']}** `{r.get('client_id') or '—'}` exact={r.get('exact_fixture')} gaps={r.get('gaps')}")
    (OUT / "REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8")

    watch = ["# Watchlist — Deterministic fixture seed closeout", "", f"Status: `{classification}`", ""]
    for r in seed_rows:
        if not r.get("exact_fixture"):
            watch.append(f"- [ ] **{r['scenario']}** — {r.get('gaps') or 'seed required'}")
    watch.extend(["", "```bash", "cd backend", "python scripts/plan_outcome_deterministic_fixture_seed_closeout_01_execute.py", "```"])
    (OUT / "watchlist.md").write_text("\n".join(watch) + "\n", encoding="utf-8")

    print(json.dumps({"classification": classification, "results": results, "exact": f"{exact}/{len(ALL_SATISFIED)}"}, indent=2))
    return 0 if classification == "VERIFIED_OPERATIONALLY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
