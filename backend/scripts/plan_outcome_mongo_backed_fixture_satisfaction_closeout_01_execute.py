#!/usr/bin/env python3
"""PLAN-OUTCOME-MONGO-BACKED-FIXTURE-SATISFACTION-CLOSEOUT-01."""
from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import httpx

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.plan_outcome_governed_fixture_seed_lib import (  # noqa: E402
    FIXTURE_PLAN,
    StagingApi,
    ensure_properties,
    load_mongo_url,
    run_db_satisfy,
    write_registry_override,
)

OUT = ROOT / "docs/audit/plan_based_business_outcome_runtime_audit_01"
SHOT = OUT / "closeout_screenshots"
PROGRAMME = "PLAN-OUTCOME-MONGO-BACKED-FIXTURE-SATISFACTION-CLOSEOUT-01"
MARKER = "PLAN-OUTCOME-MONGO-SAT-20260608"
PRIOR_MARKER = "PLAN-OUTCOME-GOVERNED-FIXTURE-20260602"
WRITE_FIXTURES = ("D", "E", "G", "H")
ALL_SCENARIOS = ("A", "B", "C", "D", "E", "F", "G", "H", "I")

FORBIDDEN_MONGO_MARKERS = frozenset({"prod", "production", "pleerity-prod", "pleerity_production"})
ALLOWED_TARGET_CLIENTS = frozenset(
    FIXTURE_PLAN[s]["base_client_id"] for s in WRITE_FIXTURES
) | {"10b2ddba-e952-4484-91d1-a8f0299d0824"}

BROWSER_TARGETS = [
    ("solo_all_sat", "A", "10b2ddba-e952-4484-91d1-a8f0299d0824"),
    ("solo_partial", "B", "616258a5-51a6-4def-aa00-baa1598b2557"),
    ("portfolio_all_same", "D", "80f83edd-ba12-41ed-929a-bbaf8c696a23"),
    ("portfolio_all_mixed", "E", "6bcc43c0-16f4-46a5-adf4-26693a0919d0"),
    ("portfolio_partial", "F", "6bcc43c0-16f4-46a5-adf4-26693a0919d0"),
    ("pro_all_same", "G", "f68d4f4b-8007-43c6-84cb-a20c4ab69891"),
    ("pro_all_mixed", "H", "6fd5ac4c-3fd4-4112-ade7-156977deb49f"),
    ("pro_partial", "I", "6fd5ac4c-3fd4-4112-ade7-156977deb49f"),
]

_closeout_path = ROOT / "scripts/plan_based_business_outcome_fixture_closeout_01_execute.py"
_spec = importlib.util.spec_from_file_location("_plan_fixture_closeout", _closeout_path)
_fc = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_fc)


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def fixture_client_id(sid: str) -> Optional[str]:
    """Harness fixture client — prefer FIXTURE_PLAN base over stale registry hints."""
    if sid in FIXTURE_PLAN:
        return FIXTURE_PLAN[sid].get("base_client_id")
    reg = _fc.effective_fixture_registry()
    cands = reg.get(sid, {}).get("candidate_client_ids") or []
    return cands[0] if cands else None


def write_artifact(name: str, data: Any) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


def mongo_cluster_label(mongo_url: str) -> str:
    try:
        parsed = urlparse(mongo_url.replace("mongodb+srv://", "https://").replace("mongodb://", "http://"))
        host = parsed.hostname or mongo_url.split("@")[-1].split("/")[0].split("?")[0]
        return host
    except Exception:
        return "unparsed"


def check_mongo_safety(
    *,
    mongo_url: Optional[str],
    db_name: Optional[str],
    dry_run: bool,
    confirm_write: bool,
    mongo_url_file: str,
) -> Dict[str, Any]:
    blocked: List[str] = []
    cluster = None
    staging_only = False
    if not mongo_url:
        blocked.append("STAGING_MONGO_URL not configured")
    else:
        lower = mongo_url.lower()
        if any(m in lower for m in FORBIDDEN_MONGO_MARKERS):
            blocked.append("production_mongo_marker_detected")
        cluster = mongo_cluster_label(mongo_url)
        staging_only = "staging" in lower or "pleerity_staging" in (db_name or "").lower() or cluster.endswith(".mongodb.net")
        if not staging_only and "localhost" not in lower and "127.0.0.1" not in lower:
            blocked.append("cluster_not_confirmed_staging")
    write_allowed = bool(mongo_url) and not blocked and confirm_write and not dry_run
    return {
        "programme": PROGRAMME,
        "generated_at": utc(),
        "marker": MARKER,
        "prior_marker": PRIOR_MARKER,
        "mongo_url_present": bool(mongo_url),
        "mongo_url_file": mongo_url_file,
        "db_name": db_name,
        "cluster_label": cluster,
        "dry_run": dry_run,
        "confirm_write": confirm_write,
        "write_allowed": write_allowed,
        "staging_only": staging_only and bool(mongo_url),
        "target_clients": sorted(ALLOWED_TARGET_CLIENTS),
        "idempotency_marker": MARKER,
        "blocked_reasons": blocked,
        "pass": bool(mongo_url) and not blocked,
    }


def _req_action(req: Dict[str, Any]) -> str:
    if req.get("requirement_satisfied"):
        return "already_satisfied"
    meta = req.get("registry_metadata") or {}
    modes = ((meta.get("evidence_resolution") or {}).get("allowed_evidence_modes")) or []
    if "STRUCTURED_DECLARATION" in modes:
        return "structured_declaration_or_mongo_cer"
    if "DOCUMENT_UPLOAD" in modes or not modes:
        return "governed_document_seed_authority_sync"
    return f"mongo_seed_{modes[0] if modes else 'unknown'}"


def build_api_dry_run(api: StagingApi, sid: str, spec: Dict[str, Any]) -> Dict[str, Any]:
    cid = spec["base_client_id"]
    admin_t, step = api.admin_session()
    token = api.impersonate(admin_t, step, cid, f"{PROGRAMME} dry-run {sid}")
    probe = api.probe(token)
    props = api.client_get(token, "/client/properties").get("properties") or []
    active = [p for p in props if p.get("is_active", True) is not False]
    req_actions: List[Dict[str, Any]] = []
    doc_only_pending = 0
    for p in active:
        pid = p.get("property_id")
        if not pid:
            continue
        rows = api.client_get(token, f"/client/properties/{pid}/requirements").get("requirements") or []
        for r in rows:
            if r.get("client_surface_visible", True) is False:
                continue
            action = _req_action(r)
            if not r.get("requirement_satisfied") and "document" in action:
                doc_only_pending += 1
            req_actions.append(
                {
                    "property_id": pid,
                    "requirement_id": r.get("requirement_id"),
                    "requirement_type": r.get("requirement_type"),
                    "satisfied": r.get("requirement_satisfied"),
                    "action_required": action,
                    "evidence_method": "governed_fixture_document" if "document" in action else "cer_structured_declaration",
                    "authority_sync": "sync_requirement_evidence_authority",
                    "recalc": "enqueue_compliance_recalc",
                }
            )
    pending = [x for x in req_actions if not x.get("satisfied")]
    return {
        "scenario": sid,
        "client_id": cid,
        "plan": spec["plan_code"],
        "property_count": len(active),
        "jurisdictions": probe.get("jurisdictions"),
        "requirements_total": probe.get("requirement_total"),
        "requirements_satisfied": probe.get("requirement_satisfied"),
        "document_only_pending": doc_only_pending,
        "pending_count": len(pending),
        "requirement_actions": req_actions,
        "expected_post_run": {
            "all_satisfied": True,
            "today_calm": True,
            "properties_green": True,
            "score_confidence": True,
        },
        "pass": True,
    }


async def build_mongo_dry_run(client_id: str, db_name: str) -> Dict[str, Any]:
    from database import database
    from services.compliance_evidence_record_service import effective_evidence_resolution
    from services.requirement_satisfaction_service import attach_satisfaction_fields, is_requirement_satisfied

    await database.connect()
    db = database.get_db()
    client = await db.clients.find_one({"client_id": client_id}, {"_id": 0, "billing_plan": 1})
    props = await db.properties.find(
        {"client_id": client_id, "$or": [{"is_active": True}, {"is_active": {"$exists": False}}]},
        {"_id": 0, "property_id": 1, "jurisdiction": 1},
    ).to_list(100)
    rows: List[Dict[str, Any]] = []
    doc_only = 0
    for p in props:
        pid = p["property_id"]
        reqs = await db.requirements.find(
            {"client_id": client_id, "property_id": pid, "status": {"$nin": ["NOT_REQUIRED"]}},
            {"_id": 0},
        ).to_list(500)
        for req in reqs:
            enriched = attach_satisfaction_fields(req)
            sat = is_requirement_satisfied(enriched)
            policy = effective_evidence_resolution(req)
            modes = policy.get("allowed_evidence_modes") or []
            if not sat and "DOCUMENT_UPLOAD" in modes and "STRUCTURED_DECLARATION" not in modes:
                doc_only += 1
            action = "already_satisfied" if sat else (
                "structured_declaration_cer" if "STRUCTURED_DECLARATION" in modes else "governed_document_seed"
            )
            rows.append(
                {
                    "property_id": pid,
                    "requirement_id": req.get("requirement_id"),
                    "requirement_type": req.get("requirement_type"),
                    "satisfied": sat,
                    "allowed_modes": modes,
                    "action_required": action,
                }
            )
    return {
        "client_id": client_id,
        "plan": client.get("billing_plan") if client else None,
        "property_count": len(props),
        "requirements_total": len(rows),
        "document_only_pending": doc_only,
        "requirement_actions": rows,
    }


def run_mongo_write(
    api: StagingApi,
    mongo_url: str,
    db_name: str,
) -> Dict[str, Any]:
    os.environ["MONGO_URL"] = mongo_url
    os.environ["DB_NAME"] = db_name
    results: Dict[str, Any] = {"programme": PROGRAMME, "generated_at": utc(), "marker": MARKER, "fixtures": {}}
    for sid in WRITE_FIXTURES:
        spec = FIXTURE_PLAN[sid]
        cid = spec["base_client_id"]
        entry: Dict[str, Any] = {"scenario": sid, "client_id": cid, "actions": []}
        try:
            if sid in ("G", "E") and "ensure_property_count" in (spec.get("actions") or []):
                admin_t, step = api.admin_session()
                token = api.impersonate(admin_t, step, cid, f"{PROGRAMME} ensure props {sid}")
                prop_res = ensure_properties(
                    api,
                    token,
                    target_count=int(spec["property_count"]),
                    marker=MARKER,
                    jurisdiction=(spec.get("jurisdictions") or ["England"])[0],
                    mixed_jurisdictions=spec.get("jurisdictions") if spec.get("mixed_jurisdiction") else None,
                )
                entry["actions"].append({"ensure_properties": prop_res})
            admin_t, step = api.admin_session()
            token = api.impersonate(admin_t, step, cid, f"{PROGRAMME} list props {sid}")
            props = api.client_get(token, "/client/properties").get("properties") or []
            active_ids = [p["property_id"] for p in props if p.get("is_active", True) is not False and p.get("property_id")]
            sat = run_db_satisfy(cid, active_ids, MARKER)
            entry["actions"].append({"satisfaction": sat})
            admin_t, step = api.admin_session()
            token = api.impersonate(admin_t, step, cid, f"{PROGRAMME} post probe {sid}")
            probe = api.probe(token)
            entry["probe_after"] = probe
            entry["pass"] = bool(probe.get("all_satisfied") and probe.get("today_calm") and probe.get("properties_valid"))
            entry["status"] = "seeded" if entry["pass"] else "partial"
        except Exception as exc:
            entry["pass"] = False
            entry["error"] = str(exc)[:300]
            entry["status"] = "failed"
        results["fixtures"][sid] = entry
        time.sleep(float(os.environ.get("PLAN_FIXTURE_BATCH_PAUSE_S", "8")))
    results["pass"] = all((results["fixtures"].get(s) or {}).get("pass") for s in WRITE_FIXTURES)
    write_registry_override(results["fixtures"])
    return results


def verify_post_write(api: StagingApi, sid: str, cid: str) -> Dict[str, Any]:
    reg = _fc.effective_fixture_registry()
    reg_spec = reg[sid]
    plan_spec = FIXTURE_PLAN.get(sid, {})
    plan_code = reg_spec.get("plan_code") or plan_spec.get("plan_code")
    admin_t, step = api.admin_session()
    token = api.impersonate(admin_t, step, cid, f"{PROGRAMME} verify {sid}")
    probe = api.probe(token)
    ok, gaps = _fc.matches_criteria(
        probe,
        reg_spec.get("criteria", {}),
        plan_code,
        probe.get("entitlements_plan") or "",
    )
    checks = {
        "all_satisfied": probe.get("all_satisfied"),
        "today_calm": probe.get("today_calm"),
        "today_urgent_zero": int(probe.get("today_urgent_count") or 0) == 0,
        "today_in_progress_zero": int(probe.get("today_in_progress_count") or 0) == 0,
        "properties_valid": probe.get("properties_valid"),
        "overdue_zero": int(probe.get("overdue") or 0) == 0,
        "score_confidence": probe.get("score_confidence_present"),
        "criteria_match": ok,
    }
    return {
        "scenario": sid,
        "client_id": cid,
        "probe": probe,
        "checks": checks,
        "gaps": gaps,
        "pass": all(checks.values()) and ok,
    }


def browser_capture(api: StagingApi) -> Dict[str, Any]:
    if sync_playwright is None:
        return {"pass": False, "error": "playwright_not_installed", "captures": []}
    SHOT.mkdir(parents=True, exist_ok=True)
    captures: List[Dict[str, Any]] = []
    frontend = _fc.FRONTEND
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for slug, sid, cid in BROWSER_TARGETS:
            entry: Dict[str, Any] = {"slug": slug, "scenario": sid, "client_id": cid, "pages": []}
            try:
                admin_t, step = api.admin_session()
                token = api.impersonate(admin_t, step, cid, f"{PROGRAMME} browser {slug}")
                ctx = browser.new_context(viewport={"width": 1440, "height": 900})
                user_blob = json.dumps({"client_id": cid, "role": "ROLE_CLIENT_ADMIN", "impersonation": True})
                ctx.add_init_script(
                    f"localStorage.setItem('auth_token', {json.dumps(token)});"
                    f"localStorage.setItem('user', {json.dumps(user_blob)});"
                )
                page = ctx.new_page()
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
                page.close()
                ctx.close()
            except Exception as exc:
                entry["pass"] = False
                entry["error"] = str(exc)[:240]
            captures.append(entry)
            time.sleep(float(os.environ.get("PLAN_FIXTURE_BATCH_PAUSE_S", "10")))
        browser.close()
    return {
        "programme": PROGRAMME,
        "generated_at": utc(),
        "marker": MARKER,
        "captures": captures,
        "pass": all(c.get("pass") for c in captures),
    }


def cross_surface(api: StagingApi) -> Dict[str, Any]:
    reg = _fc.effective_fixture_registry()
    rows: List[Dict[str, Any]] = []
    for sid in ALL_SCENARIOS:
        if sid == "C":
            rows.append({"scenario": sid, "local_only": True, "pass": True})
            continue
        cid = fixture_client_id(sid)
        if not cid:
            rows.append({"scenario": sid, "pass": False, "error": "no_client"})
            continue
        try:
            admin_t, step = api.admin_session()
            token = api.impersonate(admin_t, step, cid, f"{PROGRAMME} cross {sid}")
            probe = api.probe(token)
            dash = api.client_get(token, "/client/dashboard")
            dsum = dash.get("compliance_summary") or {}
            rows.append(
                {
                    "scenario": sid,
                    "client_id": cid,
                    "dashboard_total": dsum.get("total_requirements"),
                    "score_total": probe.get("requirement_total"),
                    "today_calm": probe.get("today_calm"),
                    "all_satisfied": probe.get("all_satisfied"),
                    "properties_valid": probe.get("properties_valid"),
                    "pass": abs(int(dsum.get("total_requirements") or 0) - int(probe.get("requirement_total") or 0)) <= 3,
                }
            )
        except Exception as exc:
            rows.append({"scenario": sid, "pass": False, "error": str(exc)[:200]})
        time.sleep(float(os.environ.get("PLAN_FIXTURE_BATCH_PAUSE_S", "8")))
    return {"programme": PROGRAMME, "generated_at": utc(), "rows": rows, "pass": all(r.get("pass") for r in rows)}


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


def classify(flags: List[str], exact: int, mongo_safe: bool, write_ok: bool) -> str:
    if not mongo_safe:
        return "MONGO_SAFETY_GAP"
    if exact == 5 and write_ok and "FAIL_OPERATIONAL" not in flags:
        return "VERIFIED_OPERATIONALLY"
    if "FIXTURE_SEEDING_GAP" in flags or not write_ok:
        return "FIXTURE_SEEDING_GAP"
    if "CROSS_SURFACE_DRIFT" in flags:
        return "CROSS_SURFACE_DRIFT"
    if flags:
        return "PARTIAL"
    return "FAIL_OPERATIONAL"


def main() -> int:
    parser = argparse.ArgumentParser(description=PROGRAMME)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--confirm-write", action="store_true")
    parser.add_argument("--mongo-url", default="")
    parser.add_argument(
        "--mongo-url-file",
        default="docs/audit/phase2c_commercial_entitlement_governance_01/.staging_mongo_url",
    )
    parser.add_argument("--skip-rerun", action="store_true")
    parser.add_argument("--skip-browser", action="store_true")
    parser.add_argument("--skip-cross-surface", action="store_true")
    parser.add_argument("--skip-dry-run", action="store_true")
    args = parser.parse_args()

    print(f"{PROGRAMME} {datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}")
    mongo_url, db_name = load_mongo_url(args.mongo_url, args.mongo_url_file)
    if not db_name:
        db_name = "pleerity_staging"

    safety = check_mongo_safety(
        mongo_url=mongo_url,
        db_name=db_name,
        dry_run=args.dry_run,
        confirm_write=args.confirm_write,
        mongo_url_file=args.mongo_url_file,
    )
    write_artifact("mongo_fixture_safety_runtime.json", safety)

    api = StagingApi(os.environ.get("STAGING_API", "https://pleerity-enterprise.onrender.com"))
    flags: List[str] = []
    if not safety.get("pass"):
        flags.append("MONGO_SAFETY_GAP")

    if args.skip_dry_run:
        prior = OUT / "mongo_fixture_dry_run_runtime.json"
        dry_payload = json.loads(prior.read_text(encoding="utf-8")) if prior.is_file() else {"fixtures": [], "pass": False}
    else:
        dry_rows = []
        for sid in WRITE_FIXTURES:
            spec = FIXTURE_PLAN[sid]
            row = build_api_dry_run(api, sid, spec)
            if mongo_url and safety.get("pass"):
                try:
                    os.environ["MONGO_URL"] = mongo_url
                    os.environ["DB_NAME"] = db_name
                    mongo_row = asyncio.run(build_mongo_dry_run(spec["base_client_id"], db_name))
                    row["mongo_detail"] = mongo_row
                except Exception as exc:
                    row["mongo_detail_error"] = str(exc)[:200]
            dry_rows.append(row)
            time.sleep(float(os.environ.get("PLAN_FIXTURE_BATCH_PAUSE_S", "6")))
        dry_payload = {"programme": PROGRAMME, "generated_at": utc(), "marker": MARKER, "fixtures": dry_rows, "pass": True}
    write_artifact("mongo_fixture_dry_run_runtime.json", dry_payload)

    write_result: Dict[str, Any] = {"programme": PROGRAMME, "skipped": True, "pass": False, "reason": "blocked"}
    if safety.get("write_allowed"):
        write_result = run_mongo_write(api, mongo_url, db_name)
    elif not mongo_url:
        write_result["reason"] = "STAGING_MONGO_URL not configured"
        flags.append("FIXTURE_SEEDING_GAP")
    write_artifact("mongo_fixture_write_runtime.json", write_result)

    reg = _fc.effective_fixture_registry()
    verify_rows = []
    for sid in ("A",) + WRITE_FIXTURES:
        cid = fixture_client_id(sid)
        if not cid:
            continue
        try:
            verify_rows.append(verify_post_write(api, sid, cid))
        except Exception as exc:
            verify_rows.append({"scenario": sid, "pass": False, "error": str(exc)[:200]})
        time.sleep(float(os.environ.get("PLAN_FIXTURE_BATCH_PAUSE_S", "8")))
    exact = sum(1 for r in verify_rows if r.get("pass") and r.get("checks", {}).get("criteria_match"))
    write_artifact(
        "mongo_fixture_post_write_verification_runtime.json",
        {"programme": PROGRAMME, "generated_at": utc(), "rows": verify_rows, "exact_count": f"{exact}/5", "pass": exact == 5},
    )
    if exact < 5:
        flags.append("PLAN_FIXTURE_GAP")

    rerun = {"programme": PROGRAMME, "skipped": args.skip_rerun, "pass": False, "runs": []}
    if not args.skip_rerun:
        for script in ("plan_outcome_fixture_seeding_and_closeout_01_execute.py", "plan_fixture_browser_capture_01.py"):
            proc = subprocess.run(
                [sys.executable, f"scripts/{script}"],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
            )
            rerun["runs"].append({"script": script, "exit_code": proc.returncode, "stdout_tail": (proc.stdout or "")[-1200:]})
        rerun["pass"] = all(r["exit_code"] == 0 for r in rerun["runs"])
    write_artifact("plan_outcome_mongo_rerun_runtime.json", rerun)

    if args.skip_cross_surface:
        prior = OUT / "plan_outcome_mongo_cross_surface_runtime.json"
        cross = (
            json.loads(prior.read_text(encoding="utf-8"))
            if prior.is_file()
            else {"pass": False, "skipped": True, "rows": []}
        )
    else:
        cross = cross_surface(api)
        if not cross.get("pass"):
            flags.append("CROSS_SURFACE_DRIFT")
    write_artifact("plan_outcome_mongo_cross_surface_runtime.json", cross)

    browser = {"pass": False, "skipped": args.skip_browser}
    if not args.skip_browser:
        try:
            browser = browser_capture(api)
        except Exception as exc:
            browser = {"pass": False, "error": str(exc)[:300]}
    write_artifact("plan_outcome_mongo_browser_runtime.json", browser)

    regression = run_regression()
    write_artifact("plan_outcome_mongo_regression_runtime.json", {"programme": PROGRAMME, "generated_at": utc(), **regression})

    write_ok = bool(write_result.get("pass"))
    verified = (
        safety.get("pass")
        and write_ok
        and exact == 5
        and browser.get("pass")
        and regression.get("pass")
    )
    classification = classify(sorted(set(flags)), exact, safety.get("pass"), write_ok)
    if verified:
        classification = "VERIFIED_OPERATIONALLY"

    write_artifact(
        "classifications.json",
        {
            "programme": PROGRAMME,
            "prior_programme": "PLAN-OUTCOME-GOVERNED-STAGING-FIXTURE-SEEDING-01",
            "generated_at": utc(),
            "marker": MARKER,
            "classification": classification,
            "secondary_flags": sorted(set(flags)),
            "results": {
                "mongo_safety": safety.get("pass"),
                "dry_run": True,
                "write": write_ok,
                "post_write": exact == 5,
                "rerun": rerun.get("pass"),
                "cross_surface": cross.get("pass"),
                "browser": browser.get("pass"),
                "regression": regression.get("pass"),
                "exact_fixtures": f"{exact}/5",
                "verified": verified,
            },
            "exact_fixtures": f"{exact}/5",
        },
    )

    report = [
        f"# {PROGRAMME}",
        "",
        f"**Classification:** `{classification}`",
        f"**Marker:** `{MARKER}`",
        f"**Exact fixtures:** {exact}/5",
        "",
        "## Mongo safety",
        "",
        f"- URL present: {safety.get('mongo_url_present')}",
        f"- Cluster: `{safety.get('cluster_label') or 'n/a'}`",
        f"- DB: `{db_name}`",
        f"- Write allowed: {safety.get('write_allowed')}",
        "",
        "## Post-write verification",
        "",
    ]
    for r in verify_rows:
        report.append(f"- **{r.get('scenario')}** `{r.get('client_id')}` pass={r.get('pass')} gaps={r.get('gaps')}")
    (OUT / "REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8")

    watch = [
        "# Watchlist — Mongo-backed fixture satisfaction",
        "",
        f"Status: `{classification}`",
        "",
    ]
    if not safety.get("pass"):
        watch.append("- [ ] Copy staging Atlas URI to `docs/audit/phase2c_commercial_entitlement_governance_01/.staging_mongo_url` (gitignored)")
    for r in verify_rows:
        if not r.get("pass"):
            watch.append(f"- [ ] **{r.get('scenario')}** — {r.get('gaps') or r.get('error') or 'not exact'}")
    watch.extend(
        [
            "",
            "## Re-run",
            "",
            "```bash",
            "cd backend",
            "python scripts/plan_outcome_mongo_backed_fixture_satisfaction_closeout_01_execute.py --dry-run",
            "python scripts/plan_outcome_mongo_backed_fixture_satisfaction_closeout_01_execute.py --confirm-write --mongo-url-file docs/audit/phase2c_commercial_entitlement_governance_01/.staging_mongo_url",
            "```",
        ]
    )
    (OUT / "watchlist.md").write_text("\n".join(watch) + "\n", encoding="utf-8")

    print(json.dumps({"classification": classification, "exact": f"{exact}/5", "flags": sorted(set(flags))}, indent=2))
    return 0 if classification == "VERIFIED_OPERATIONALLY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
