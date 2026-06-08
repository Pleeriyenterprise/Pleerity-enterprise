#!/usr/bin/env python3
"""PLAN-OUTCOME-GOVERNED-STAGING-FIXTURE-SEEDING-01 — governed staging fixture seed + closeout."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.plan_outcome_governed_fixture_seed_lib import (  # noqa: E402
    FIXTURE_MARKER,
    FIXTURE_PLAN,
    PROGRAMME,
    StagingApi,
    build_seed_plan,
    check_safety_guards,
    create_fixture,
    load_mongo_url,
    write_registry_override,
)

OUT = ROOT / "docs/audit/plan_based_business_outcome_runtime_audit_01"
SHOT = OUT / "closeout_screenshots"
RUN_TAG = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

_closeout_path = ROOT / "scripts/plan_based_business_outcome_fixture_closeout_01_execute.py"
_spec = importlib.util.spec_from_file_location("_plan_fixture_closeout", _closeout_path)
_fc = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_fc)

ALL_SAT = ("A", "D", "E", "G", "H")
BROWSER_SLUGS = {
    "A": "solo_all_sat",
    "D": "portfolio_all_same",
    "E": "portfolio_all_mixed",
    "G": "pro_all_same",
    "H": "pro_all_mixed",
}


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_artifact(name: str, data: Any) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


def load_registry() -> Dict[str, Any]:
    reg = dict(_fc.FIXTURE_REGISTRY)
    override = OUT / "governed_fixture_registry_runtime.json"
    if override.is_file():
        data = json.loads(override.read_text(encoding="utf-8"))
        for sid, row in (data.get("fixtures") or {}).items():
            if sid in reg and row.get("client_id"):
                reg[sid]["candidate_client_ids"] = [row["client_id"]]
    return reg


def verify_fixture(api: StagingApi, client_id: str) -> Dict[str, Any]:
    admin_t, step = api.admin_session()
    token = api.impersonate(admin_t, step, client_id, f"{PROGRAMME} verify")
    probe = api.probe(token)
    reqs = api.client_get(token, "/client/requirements")
    rows = reqs.get("requirements") or reqs.get("items") or []
    visible = [r for r in rows if r.get("client_surface_visible", True) is not False]
    return {
        "client_id": client_id,
        "probe": {k: v for k, v in probe.items() if k != "properties"},
        "visible_requirements": len(visible),
        "satisfied_visible": sum(1 for r in visible if r.get("requirement_satisfied")),
        "pass": bool(probe.get("all_satisfied") and probe.get("today_calm") and probe.get("properties_valid")),
    }


def browser_proof(api: StagingApi, fixtures: Dict[str, str]) -> Dict[str, Any]:
    if sync_playwright is None:
        return {"pass": False, "error": "playwright_not_installed", "captures": []}
    SHOT.mkdir(parents=True, exist_ok=True)
    captures: List[Dict[str, Any]] = []
    frontend = _fc.FRONTEND
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for sid in ALL_SAT:
            cid = fixtures.get(sid)
            slug = BROWSER_SLUGS[sid]
            entry: Dict[str, Any] = {"scenario": sid, "slug": slug, "client_id": cid, "pages": []}
            if not cid:
                entry.update({"pass": False, "status": "skipped", "error": "no_client"})
                captures.append(entry)
                continue
            admin_t, step = api.admin_session()
            try:
                token = api.impersonate(admin_t, step, cid, f"{PROGRAMME} browser {sid}")
            except Exception as exc:
                entry.update({"pass": False, "status": "failed", "error": str(exc)[:200]})
                captures.append(entry)
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
                    page.goto(f"{frontend}{route}", wait_until="domcontentloaded", timeout=120_000)
                    page.wait_for_timeout(2200)
                    page.screenshot(path=str(SHOT / shot))
                    entry["pages"].append({"page": pid, "screenshot": shot})
                entry["pass"] = len(entry["pages"]) >= 7
                entry["status"] = "pass" if entry["pass"] else "failed"
            except Exception as exc:
                entry.update({"pass": False, "status": "failed", "error": str(exc)[:200]})
            finally:
                page.close()
                ctx.close()
            captures.append(entry)
            time.sleep(float(os.environ.get("PLAN_FIXTURE_BATCH_PAUSE_S", "10")))
        browser.close()
    with_cid = [c for c in captures if c.get("client_id")]
    return {
        "programme": PROGRAMME,
        "generated_at": utc(),
        "marker": FIXTURE_MARKER,
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
        "tests/test_compliance_evidence_governance.py",
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


def classify(flags: List[str], exact: int) -> str:
    if exact == len(ALL_SAT) and "FAIL_OPERATIONAL" not in flags:
        return "VERIFIED_OPERATIONALLY"
    if "FIXTURE_SEEDING_GAP" in flags:
        return "FIXTURE_SEEDING_GAP"
    if "PLAN_FIXTURE_GAP" in flags:
        return "PLAN_FIXTURE_GAP"
    if flags:
        return "PARTIAL"
    return "FAIL_OPERATIONAL"


def main() -> int:
    parser = argparse.ArgumentParser(description=PROGRAMME)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--confirm-write", action="store_true", help="Required for staging writes")
    parser.add_argument("--mongo-url", default="")
    parser.add_argument("--mongo-url-file", default="")
    parser.add_argument("--skip-rerun", action="store_true")
    parser.add_argument("--skip-browser", action="store_true")
    parser.add_argument("--skip-seed", action="store_true", help="Verification/browser/regression only")
    parser.add_argument(
        "--fixtures",
        default="",
        help="Comma-separated fixture ids to seed (default all A,D,E,G,H)",
    )
    args = parser.parse_args()
    selected = tuple(s.strip().upper() for s in args.fixtures.split(",") if s.strip()) or ALL_SAT

    print(f"{PROGRAMME} {RUN_TAG}")
    api_base = os.environ.get("STAGING_API", "https://pleerity-enterprise.onrender.com")
    mongo_url, _ = load_mongo_url(args.mongo_url, args.mongo_url_file)
    api = StagingApi(api_base, pace=float(os.environ.get("OPS_API_PACE_S", "5")))

    plan = build_seed_plan()
    write_artifact("governed_fixture_seed_plan_runtime.json", plan)

    safety = check_safety_guards(
        api_base=api_base,
        dry_run=args.dry_run,
        confirm_write=args.confirm_write,
        mongo_url=mongo_url,
    )
    write_artifact("fixture_seed_safety_runtime.json", safety)

    creation: Dict[str, Any] = {"programme": PROGRAMME, "generated_at": utc(), "fixtures": {}, "pass": False}
    flags: List[str] = []
    if not safety.get("environment_guard"):
        flags.append("FAIL_OPERATIONAL")
    elif not args.dry_run and not args.confirm_write:
        flags.append("FIXTURE_SEEDING_GAP")
        creation["blocked"] = "confirm_write_required"

    seeded_clients: Dict[str, str] = {}
    if safety.get("write_allowed"):
        for sid in ALL_SAT:
            print(f"seed {sid}...")
            try:
                row = create_fixture(
                    api,
                    sid,
                    FIXTURE_PLAN[sid],
                    dry_run=args.dry_run,
                    write_allowed=bool(safety.get("write_allowed")),
                    mongo_url=mongo_url,
                )
            except Exception as exc:
                row = {"scenario": sid, "pass": False, "error": str(exc)[:300]}
            creation["fixtures"][sid] = row
            if row.get("client_id"):
                seeded_clients[sid] = row["client_id"]
            if not row.get("pass"):
                flags.append("FIXTURE_SEEDING_GAP")
            time.sleep(float(os.environ.get("PLAN_FIXTURE_BATCH_PAUSE_S", "10")))
        write_registry_override(creation["fixtures"])
    else:
        for sid in ALL_SAT:
            if args.skip_seed:
                cid = FIXTURE_PLAN[sid].get("base_client_id")
                creation["fixtures"][sid] = {
                    "scenario": sid,
                    "client_id": cid,
                    "status": "verify_only",
                    "pass": sid == "A",
                }
                if cid:
                    seeded_clients[sid] = cid
            else:
                creation["fixtures"][sid] = {"scenario": sid, "status": "not_executed", "pass": False}
        if not args.dry_run and not args.skip_seed:
            flags.append("FIXTURE_SEEDING_GAP")

    creation["pass"] = all((creation["fixtures"].get(s) or {}).get("pass") for s in ALL_SAT)
    write_artifact("fixture_creation_runtime.json", creation)

    # merge registry overrides for probes
    registry = load_registry()
    for sid in ALL_SAT:
        cid = seeded_clients.get(sid) or (FIXTURE_PLAN[sid].get("base_client_id"))
        if cid:
            seeded_clients.setdefault(sid, cid)

    satisfaction_rows = []
    for sid in ALL_SAT:
        cid = seeded_clients.get(sid)
        if not cid:
            satisfaction_rows.append({"scenario": sid, "pass": False, "reason": "no_client"})
            continue
        try:
            row = verify_fixture(api, cid)
            spec = registry[sid]
            ok, gaps = _fc.matches_criteria(row["probe"], spec.get("criteria") or {}, spec["plan_code"], row["probe"].get("entitlements_plan") or "")
            row["criteria_match"] = ok
            row["gaps"] = gaps
            row["scenario"] = sid
            satisfaction_rows.append(row)
            if not ok or not row.get("pass"):
                flags.append("PLAN_FIXTURE_GAP")
        except Exception as exc:
            satisfaction_rows.append({"scenario": sid, "pass": False, "error": str(exc)[:200]})
            flags.append("PLAN_FIXTURE_GAP")
        time.sleep(float(os.environ.get("PLAN_FIXTURE_BATCH_PAUSE_S", "8")))

    sat_pass = all(r.get("pass") and r.get("criteria_match") for r in satisfaction_rows if r.get("scenario"))
    write_artifact(
        "fixture_satisfaction_recalc_runtime.json",
        {"programme": PROGRAMME, "generated_at": utc(), "rows": satisfaction_rows, "pass": sat_pass},
    )

    ent_rows = []
    for row in satisfaction_rows:
        sid = row.get("scenario")
        probe = row.get("probe") or {}
        if sid:
            ent_rows.append(
                {
                    "scenario": sid,
                    "expected_plan": registry[sid]["plan_code"],
                    "api_plan": probe.get("entitlements_plan"),
                    "features_enabled": probe.get("features_enabled"),
                    "pass": probe.get("entitlements_plan") == registry[sid]["plan_code"],
                }
            )
    ent_pass = bool(ent_rows) and all(r.get("pass") for r in ent_rows)
    write_artifact(
        "fixture_plan_entitlement_runtime.json",
        {"programme": PROGRAMME, "generated_at": utc(), "rows": ent_rows, "pass": ent_pass},
    )
    if not ent_pass:
        flags.append("PLAN_FIXTURE_GAP")

    outcome_rows = []
    for row in satisfaction_rows:
        probe = row.get("probe") or {}
        outcome_rows.append(
            {
                "scenario": row.get("scenario"),
                "client_id": row.get("client_id"),
                "dashboard_calm": probe.get("today_calm"),
                "all_satisfied": probe.get("all_satisfied"),
                "properties_valid": probe.get("properties_valid"),
                "score": probe.get("score"),
                "pass": bool(row.get("pass") and row.get("criteria_match")),
            }
        )
    outcome_pass = all(r.get("pass") for r in outcome_rows)
    write_artifact(
        "fixture_all_satisfied_outcome_runtime.json",
        {"programme": PROGRAMME, "generated_at": utc(), "rows": outcome_rows, "pass": outcome_pass},
    )

    if args.skip_browser:
        prior = OUT / "fixture_browser_proof_runtime.json"
        browser = (
            json.loads(prior.read_text(encoding="utf-8"))
            if prior.is_file()
            else {"pass": False, "error": "skipped_no_prior", "captures": []}
        )
    else:
        try:
            browser = browser_proof(api, seeded_clients)
        except Exception as exc:
            browser = {"pass": False, "error": str(exc)[:300], "captures": []}
    write_artifact("fixture_browser_proof_runtime.json", browser)

    rerun = {"programme": PROGRAMME, "skipped": args.skip_rerun, "pass": False, "runs": []}
    if not args.skip_rerun and not args.dry_run:
        for script in (
            "plan_outcome_fixture_seeding_and_closeout_01_execute.py",
            "plan_fixture_browser_capture_01.py",
        ):
            proc = subprocess.run(
                [sys.executable, f"scripts/{script}"],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
            )
            rerun["runs"].append(
                {
                    "script": script,
                    "exit_code": proc.returncode,
                    "stdout_tail": (proc.stdout or "")[-1500:],
                    "stderr_tail": (proc.stderr or "")[-800:],
                }
            )
        rerun["pass"] = all(r["exit_code"] == 0 for r in rerun["runs"])
    write_artifact("plan_outcome_rerun_runtime.json", rerun)

    regression = run_regression()
    write_artifact("fixture_seed_regression_runtime.json", {"programme": PROGRAMME, "generated_at": utc(), **regression})

    exact = sum(1 for r in satisfaction_rows if r.get("criteria_match") and r.get("pass"))
    results = {
        "plan": True,
        "safety": safety.get("pass"),
        "creation": creation.get("pass"),
        "satisfaction": sat_pass,
        "entitlements": ent_pass,
        "outcome": outcome_pass,
        "browser": browser.get("pass"),
        "rerun": rerun.get("pass"),
        "regression": regression.get("pass"),
        "exact_fixtures": f"{exact}/{len(ALL_SAT)}",
    }
    verified = (
        exact == len(ALL_SAT)
        and outcome_pass
        and browser.get("pass")
        and regression.get("pass")
        and ent_pass
    )
    results["verified"] = verified
    classification = classify(sorted(set(flags)), exact)
    if verified:
        classification = "VERIFIED_OPERATIONALLY"

    write_artifact(
        "classifications.json",
        {
            "programme": PROGRAMME,
            "prior_programme": "PLAN-OUTCOME-DETERMINISTIC-FIXTURE-SEED-CLOSEOUT-01",
            "generated_at": utc(),
            "marker": FIXTURE_MARKER,
            "classification": classification,
            "secondary_flags": sorted(set(flags)),
            "results": results,
            "exact_fixtures": results["exact_fixtures"],
        },
    )

    report_lines = [
        f"# {PROGRAMME}",
        "",
        f"**Classification:** `{classification}`",
        f"**Marker:** `{FIXTURE_MARKER}`",
        f"**Exact fixtures:** {results['exact_fixtures']}",
        "",
        "## Seeded fixtures",
        "",
    ]
    for row in satisfaction_rows:
        report_lines.append(
            f"- **{row.get('scenario')}** `{row.get('client_id')}` match={row.get('criteria_match')} pass={row.get('pass')} gaps={row.get('gaps')}"
        )
    (OUT / "REPORT.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    watch = [
        "# Watchlist — Governed staging fixture seeding",
        "",
        f"Status: `{classification}`",
        "",
        "## Fixture gaps",
        "",
    ]
    for row in satisfaction_rows:
        if not row.get("criteria_match") or not row.get("pass"):
            watch.append(f"- [ ] **{row.get('scenario')}** — {row.get('gaps') or row.get('error') or 'not exact'}")
    if not mongo_url:
        watch.append("- [ ] Provide STAGING_MONGO_URL for document-authority governed satisfaction on document-only requirements")
    watch.extend(
        [
            "",
            "## Re-run",
            "",
            "```bash",
            "cd backend",
            "python scripts/plan_outcome_governed_staging_fixture_seeding_01_execute.py --confirm-write",
            "```",
        ]
    )
    (OUT / "watchlist.md").write_text("\n".join(watch) + "\n", encoding="utf-8")

    print(json.dumps({"classification": classification, "results": results, "flags": sorted(set(flags))}, indent=2))
    return 0 if classification == "VERIFIED_OPERATIONALLY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
