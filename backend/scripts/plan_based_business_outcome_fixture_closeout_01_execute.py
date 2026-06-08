#!/usr/bin/env python3
"""PLAN-BASED-BUSINESS-OUTCOME-FIXTURE-CLOSEOUT-01 — deterministic fixture closeout."""
from __future__ import annotations

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
PROGRAMME = "PLAN-BASED-BUSINESS-OUTCOME-FIXTURE-CLOSEOUT-01"
RUN_TAG = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
MARKER = f"PLAN-FIXTURE-CLOSEOUT-{RUN_TAG}"

_raw_api = os.environ.get("STAGING_API", "https://pleerity-enterprise.onrender.com").rstrip("/")
API = _raw_api if _raw_api.endswith("/api") else f"{_raw_api}/api"
FRONTEND = os.environ.get("STAGING_FRONTEND", "https://pleerityenterprise.co.uk").rstrip("/")
PACE = float(os.environ.get("OPS_API_PACE_S", "2.5"))
BATCH_PAUSE = float(os.environ.get("PLAN_FIXTURE_BATCH_PAUSE_S", "8"))
MAX_429_RETRIES = int(os.environ.get("PLAN_FIXTURE_429_RETRIES", "6"))

# Harness-only discovery hints (not production code). Resolved and verified at runtime.
FIXTURE_REGISTRY: Dict[str, Dict[str, Any]] = {
    "A": {
        "label": "Solo 1 property same jurisdiction all satisfied",
        "plan_code": "PLAN_1_SOLO",
        "criteria": {"min_properties": 1, "max_properties": 1, "all_satisfied": True, "mixed_jurisdiction": False},
        "search_hints": ["000023"],
        "candidate_client_ids": [],
        "expected_today": "calm",
        "expected_properties": "valid",
    },
    "B": {
        "label": "Solo partial unsatisfied",
        "plan_code": "PLAN_1_SOLO",
        "criteria": {"min_properties": 1, "max_properties": 2, "all_satisfied": False},
        "search_hints": ["000020"],
        "candidate_client_ids": ["616258a5-51a6-4def-aa00-baa1598b2557"],
        "expected_today": "operational_action",
        "expected_properties": "attention",
    },
    "C": {
        "label": "Solo property limit enforcement",
        "plan_code": "PLAN_1_SOLO",
        "local_only": True,
        "criteria": {"max_properties_plan": 2},
        "expected_today": "n/a",
    },
    "D": {
        "label": "Portfolio 5 properties same jurisdiction all satisfied",
        "plan_code": "PLAN_2_PORTFOLIO",
        "criteria": {"min_properties": 5, "max_properties": 5, "all_satisfied": True, "mixed_jurisdiction": False},
        "search_hints": ["000011"],
        "candidate_client_ids": ["80f83edd-ba12-41ed-929a-bbaf8c696a23"],
        "expected_today": "calm",
    },
    "E": {
        "label": "Portfolio 5-10 mixed jurisdictions all satisfied",
        "plan_code": "PLAN_2_PORTFOLIO",
        "criteria": {"min_properties": 5, "max_properties": 10, "all_satisfied": True, "mixed_jurisdiction": True},
        "search_hints": ["000023"],
        "candidate_client_ids": ["10b2ddba-e952-4484-91d1-a8f0299d0824"],
        "expected_today": "calm",
        "note": "Sophie Walker reference — verify plan + property count at runtime",
    },
    "F": {
        "label": "Portfolio 5-10 mixed partial",
        "plan_code": "PLAN_2_PORTFOLIO",
        "criteria": {"min_properties": 5, "max_properties": 10, "all_satisfied": False, "mixed_jurisdiction": True},
        "search_hints": ["000040"],
        "candidate_client_ids": ["6bcc43c0-16f4-46a5-adf4-26693a0919d0"],
        "expected_today": "operational_action",
    },
    "G": {
        "label": "Professional 3-5 same jurisdiction all satisfied",
        "plan_code": "PLAN_3_PRO",
        "criteria": {"min_properties": 3, "max_properties": 5, "all_satisfied": True, "mixed_jurisdiction": False},
        "search_hints": ["000028"],
        "candidate_client_ids": ["6fd5ac4c-3fd4-4112-ade7-156977deb49f"],
        "expected_today": "calm",
    },
    "H": {
        "label": "Professional 5-10 mixed all satisfied",
        "plan_code": "PLAN_3_PRO",
        "criteria": {"min_properties": 5, "max_properties": 10, "all_satisfied": True, "mixed_jurisdiction": True},
        "search_hints": [],
        "candidate_client_ids": [],
        "expected_today": "calm",
    },
    "I": {
        "label": "Professional 5-10 mixed partial",
        "plan_code": "PLAN_3_PRO",
        "criteria": {"min_properties": 5, "max_properties": 10, "all_satisfied": False, "mixed_jurisdiction": True},
        "search_hints": [],
        "candidate_client_ids": ["6fd5ac4c-3fd4-4112-ade7-156977deb49f"],
        "expected_today": "operational_action",
    },
}

PLAN_KEY = {"PLAN_1_SOLO": "solo", "PLAN_2_PORTFOLIO": "portfolio", "PLAN_3_PRO": "professional"}


def effective_fixture_registry() -> Dict[str, Dict[str, Any]]:
    """Harness registry with optional governed seed overrides (not production runtime)."""
    reg = dict(FIXTURE_REGISTRY)
    override = OUT / "governed_fixture_registry_runtime.json"
    if override.is_file():
        try:
            data = json.loads(override.read_text(encoding="utf-8"))
            for sid, row in (data.get("fixtures") or {}).items():
                if sid in reg and row.get("client_id"):
                    reg[sid]["candidate_client_ids"] = [row["client_id"]]
        except (json.JSONDecodeError, OSError):
            pass
    return reg


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_artifact(name: str, data: Any) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


def read_pw(rel: str, env_key: str = "") -> str:
    if env_key and os.environ.get(env_key):
        return os.environ[env_key].strip()
    p = ROOT / rel
    return p.read_text(encoding="utf-8").strip() if p.is_file() else ""


def _sleep_pace() -> None:
    time.sleep(PACE)


def req(method: str, path: str, token: str = "", **kwargs) -> httpx.Response:
    url = path if path.startswith("http") else f"{API}{path}"
    headers = dict(kwargs.pop("headers", None) or {})
    if token:
        headers["Authorization"] = f"Bearer {token}"
    last_status = 0
    for attempt in range(MAX_429_RETRIES):
        _sleep_pace()
        try:
            r = getattr(httpx, method)(url, headers=headers, timeout=kwargs.pop("timeout", 120), **kwargs)
        except (httpx.ConnectError, httpx.ReadTimeout) as exc:
            if attempt + 1 >= MAX_429_RETRIES:
                raise exc
            time.sleep(min(120, 10 * (attempt + 1)))
            continue
        if r.status_code == 429:
            last_status = 429
            time.sleep(min(120, 15 * (2 ** attempt)))
            continue
        return r
    raise RuntimeError(f"rate_limited_after_retries status={last_status}")


def admin_session() -> Tuple[Optional[str], Dict[str, Any], str, Optional[str]]:
    email = os.environ.get("OPS_VERIFY_ADMIN_EMAIL", "aigbochievictory@gmail.com").strip()
    pw = read_pw("docs/audit/ops_verify_01_6fd5ac4c_d35a58ae/.ops_verify_admin_pw.txt", "STAGING_ADMIN_PASSWORD")
    if not pw:
        return None, {}, "", "missing_admin_password"
    try:
        r = req("post", "/auth/admin/login", json={"email": email, "password": pw}, timeout=120)
    except RuntimeError as exc:
        return None, {}, "", str(exc)
    if r.status_code != 200:
        return None, {}, "", f"admin_login_{r.status_code}"
    admin_t = r.json().get("access_token") or r.json().get("token")
    admin_user = r.json().get("user") or {}
    su = req("post", "/auth/step-up/verify", admin_t, json={"password": pw}, timeout=90)
    step_up = su.json().get("step_up_token", "") if su.status_code == 200 else ""
    return admin_t, admin_user, step_up, None


def impersonate(admin_t: str, step_up: str, client_id: str, reason: str) -> Tuple[Optional[str], Optional[str]]:
    headers = {"Authorization": f"Bearer {admin_t}"}
    if step_up:
        headers["X-Step-Up-Token"] = step_up
    try:
        r = req(
            "post",
            f"/admin/clients/{client_id}/impersonation/start",
            headers=headers,
            params={"ttl_minutes": 15},
            json={"reason": reason},
            timeout=120,
        )
    except RuntimeError as exc:
        return None, str(exc)
    if r.status_code != 200:
        return None, f"impersonation_{r.status_code}"
    return r.json().get("access_token"), None


def list_clients(admin_t: str, *, plan_key: str = "", q: str = "", min_props: Optional[int] = None, max_props: Optional[int] = None) -> List[Dict[str, Any]]:
    params: Dict[str, Any] = {"subscription_status": "ACTIVE", "onboarding_status": "PROVISIONED", "limit": 30}
    if plan_key:
        params["plan_code"] = plan_key
    if q:
        params["q"] = q
    if min_props is not None:
        params["min_properties"] = min_props
    if max_props is not None:
        params["max_properties"] = max_props
    try:
        r = req("get", "/admin/clients", admin_t, params=params)
    except RuntimeError:
        return []
    if r.status_code != 200:
        return []
    return list(r.json().get("clients") or [])


def probe_client(token: str) -> Dict[str, Any]:
    dash = req("get", "/client/dashboard", token).json()
    score = req("get", "/client/compliance-score", token).json()
    props = req("get", "/client/properties", token).json()
    today = req("get", "/today/items", token).json()
    ent = req("get", "/client/entitlements", token).json()
    properties = props.get("properties") or []
    active_properties = [p for p in properties if p.get("is_active", True) is not False]
    stats = score.get("stats") or dash.get("compliance_summary") or {}
    tasks = today.get("tasks") or {}
    urgent = list(tasks.get("urgent") or [])
    in_prog = list(tasks.get("in_progress") or [])
    total = int(stats.get("total_requirements") or stats.get("visible_requirement_count") or 0)
    satisfied = int(stats.get("satisfied") or stats.get("compliant") or stats.get("lifecycle_satisfied_count") or 0)
    jurisdictions: List[str] = []
    for p in active_properties:
        j = (p.get("jurisdiction") or p.get("portfolio_jurisdiction") or "").strip()
        if j and j not in jurisdictions:
            jurisdictions.append(j)
    rag = {"GREEN": 0, "AMBER": 0, "RED": 0}
    for p in active_properties:
        st = (p.get("compliance_status") or "").upper()
        if st in rag:
            rag[st] += 1
    sc = score.get("score_confidence") or {}
    return {
        "score": score.get("score"),
        "property_count": len(active_properties),
        "jurisdictions": jurisdictions,
        "requirement_total": total,
        "requirement_satisfied": satisfied,
        "requirement_unsatisfied": max(0, total - satisfied),
        "overdue": int(stats.get("overdue") or 0),
        "property_rag": rag,
        "today_urgent_count": len(urgent),
        "today_in_progress_count": len(in_prog),
        "today_calm": len(urgent) == 0 and len(in_prog) == 0,
        "all_satisfied": total > 0 and satisfied >= total and int(stats.get("overdue") or 0) == 0,
        "properties_valid": rag["AMBER"] == 0 and rag["RED"] == 0,
        "score_confidence_present": bool(sc.get("headline")),
        "score_confidence_headline": sc.get("headline"),
        "entitlements_plan": ent.get("plan"),
        "features_enabled": int((ent.get("feature_summary") or {}).get("enabled") or 0),
        "dashboard_total": int((dash.get("compliance_summary") or {}).get("total_requirements") or 0),
        "dashboard_satisfied": int((dash.get("compliance_summary") or {}).get("compliant") or 0),
    }


def matches_criteria(probe: Dict[str, Any], criteria: Dict[str, Any], plan_code: str, billing_plan: str) -> Tuple[bool, List[str]]:
    gaps: List[str] = []
    if billing_plan and billing_plan != plan_code:
        gaps.append(f"plan_mismatch:{billing_plan}!={plan_code}")
    pc = int(probe.get("property_count") or 0)
    if "min_properties" in criteria and pc < criteria["min_properties"]:
        gaps.append(f"property_count<{criteria['min_properties']}")
    if "max_properties" in criteria and pc > criteria["max_properties"]:
        gaps.append(f"property_count>{criteria['max_properties']}")
    if criteria.get("all_satisfied") is True and not probe.get("all_satisfied"):
        gaps.append("not_all_satisfied")
    if criteria.get("all_satisfied") is False and probe.get("all_satisfied"):
        gaps.append("unexpected_all_satisfied")
    mj = criteria.get("mixed_jurisdiction")
    if mj is True and len(probe.get("jurisdictions") or []) < 2:
        gaps.append("not_mixed_jurisdiction")
    if mj is False and len(probe.get("jurisdictions") or []) > 1:
        gaps.append("unexpected_mixed_jurisdiction")
    return len(gaps) == 0, gaps


def resolve_fixture(
    admin_t: str,
    step_up: str,
    sid: str,
    spec: Dict[str, Any],
    resilience: Dict[str, Any],
) -> Dict[str, Any]:
    if spec.get("local_only"):
        from services.plan_registry import PLAN_DEFINITIONS, PlanCode
        lim = PLAN_DEFINITIONS[PlanCode.PLAN_1_SOLO]["max_properties"]
        return {
            "scenario": sid,
            "label": spec["label"],
            "resolved": True,
            "local_only": True,
            "property_limit": lim,
            "pass": lim == 2,
        }

    plan_code = spec["plan_code"]
    plan_key = PLAN_KEY[plan_code]
    criteria = spec.get("criteria") or {}
    tried: List[str] = []
    candidates: List[Dict[str, Any]] = []

    for cid in spec.get("candidate_client_ids") or []:
        tried.append(cid)
        token, err = impersonate(admin_t, step_up, cid, f"{PROGRAMME} fixture probe {sid}")
        if err:
            resilience.setdefault("impersonation_errors", []).append({"scenario": sid, "client_id": cid, "error": err})
            time.sleep(BATCH_PAUSE)
            continue
        probe = probe_client(token)
        ok, gaps = matches_criteria(probe, criteria, plan_code, probe.get("entitlements_plan") or plan_code)
        row = {"client_id": cid, "source": "candidate", "probe": probe, "criteria_match": ok, "gaps": gaps}
        candidates.append(row)
        if ok:
            return {"scenario": sid, "label": spec["label"], "resolved": True, "selected": row, "tried": tried, "pass": True}
        time.sleep(BATCH_PAUSE)

    for hint in spec.get("search_hints") or []:
        for row in list_clients(admin_t, plan_key=plan_key, q=hint):
            cid = row.get("client_id")
            if not cid or cid in tried:
                continue
            tried.append(cid)
            token, err = impersonate(admin_t, step_up, cid, f"{PROGRAMME} fixture search {sid}")
            if err:
                resilience.setdefault("impersonation_errors", []).append({"scenario": sid, "client_id": cid, "error": err})
                time.sleep(BATCH_PAUSE)
                continue
            probe = probe_client(token)
            ok, gaps = matches_criteria(probe, criteria, plan_code, row.get("billing_plan") or probe.get("entitlements_plan") or "")
            entry = {"client_id": cid, "crn": row.get("customer_reference"), "name": row.get("full_name"), "source": f"search:{hint}", "probe": probe, "criteria_match": ok, "gaps": gaps}
            candidates.append(entry)
            if ok:
                return {"scenario": sid, "label": spec["label"], "resolved": True, "selected": entry, "tried": tried, "pass": True}
            time.sleep(BATCH_PAUSE)

    # Discovery scan (limited)
    scan = list_clients(
        admin_t,
        plan_key=plan_key,
        min_props=criteria.get("min_properties"),
        max_props=criteria.get("max_properties"),
    )
    for row in scan[:8]:
        cid = row.get("client_id")
        if not cid or cid in tried:
            continue
        tried.append(cid)
        token, err = impersonate(admin_t, step_up, cid, f"{PROGRAMME} fixture scan {sid}")
        if err:
            time.sleep(BATCH_PAUSE)
            continue
        probe = probe_client(token)
        ok, gaps = matches_criteria(probe, criteria, plan_code, row.get("billing_plan") or "")
        entry = {"client_id": cid, "source": "scan", "probe": probe, "criteria_match": ok, "gaps": gaps}
        candidates.append(entry)
        if ok:
            return {"scenario": sid, "label": spec["label"], "resolved": True, "selected": entry, "tried": tried, "pass": True}
        time.sleep(BATCH_PAUSE)

    best = next((c for c in candidates if c.get("probe")), None)
    return {
        "scenario": sid,
        "label": spec["label"],
        "resolved": bool(best),
        "selected": best,
        "candidates_evaluated": candidates,
        "tried": tried,
        "pass": False,
        "gap": "no_exact_fixture_match",
    }


def evaluate_closeout(fixture: Dict[str, Any], spec: Dict[str, Any]) -> Dict[str, Any]:
    if spec.get("local_only") or fixture.get("local_only"):
        return {"pass": bool(fixture.get("pass")), "note": "local_property_limit"}
    selected = fixture.get("selected") or {}
    probe = selected.get("probe") or {}
    if not probe:
        return {"pass": False, "reason": "no_probe"}
    expected = spec.get("expected_today")
    checks: Dict[str, Any] = {}
    if expected == "calm":
        checks["today_calm"] = probe.get("today_calm")
        checks["properties_valid"] = probe.get("properties_valid")
        checks["all_satisfied"] = probe.get("all_satisfied")
    elif expected == "operational_action":
        checks["has_unsatisfied"] = (probe.get("requirement_unsatisfied") or 0) > 0
        checks["today_not_calm"] = not probe.get("today_calm") or (probe.get("today_urgent_count") or 0) > 0
    checks["score_confidence"] = probe.get("score_confidence_present") if probe.get("all_satisfied") else True
    checks["dashboard_score_parity"] = (
        probe.get("dashboard_total") == probe.get("requirement_total")
        or abs(int(probe.get("dashboard_total") or 0) - int(probe.get("requirement_total") or 0)) <= 2
    )
    return {"checks": checks, "pass": all(v for v in checks.values() if v is not None)}


def browser_batch(admin_t: str, step_up: str, batch: List[Tuple[str, str, Dict[str, Any]]], resilience: Dict[str, Any]) -> List[Dict[str, Any]]:
    if sync_playwright is None:
        return [{"pass": False, "error": "playwright_not_installed"}]
    admin_t, _, step_up, err = admin_session()
    if err:
        return [{"pass": False, "error": err}]
    SHOT.mkdir(parents=True, exist_ok=True)
    captures: List[Dict[str, Any]] = []
    p = sync_playwright().start()
    browser = p.chromium.launch(headless=True)
    for sid, slug, fixture in batch:
        sel = fixture.get("selected") or {}
        cid = sel.get("client_id")
        entry: Dict[str, Any] = {"scenario": sid, "slug": slug, "client_id": cid, "pages": []}
        if not cid:
            entry["pass"] = False
            entry["status"] = "skipped"
            entry["error"] = "no_fixture"
            captures.append(entry)
            continue
        token, imp_err = impersonate(admin_t, step_up, cid, f"{PROGRAMME} browser {sid}")
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
            for page_id, route, shot in [
                ("dashboard", "/dashboard", f"{slug}_dashboard.png"),
                ("today", "/today", f"{slug}_today.png"),
                ("requirements", "/requirements", f"{slug}_requirements.png"),
                ("properties", "/properties", f"{slug}_properties.png"),
                ("compliance_score", "/compliance-score", f"{slug}_compliance_score.png"),
                ("reports", "/reports", f"{slug}_reports.png"),
                ("billing", "/billing", f"{slug}_billing.png"),
            ]:
                page.goto(f"{FRONTEND}{route}", wait_until="domcontentloaded", timeout=120_000)
                page.wait_for_timeout(3000)
                page.screenshot(path=str(SHOT / shot))
                entry["pages"].append({"page": page_id, "screenshot": shot})
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
    p.stop()
    resilience["browser_batches_completed"] = resilience.get("browser_batches_completed", 0) + 1
    return captures


def run_regression() -> Dict[str, Any]:
    tests = [
        "tests/test_rent_operations.py::test_live_send_client_allowlist",
        "tests/test_reporting_semantics_v1.py",
        "tests/test_requirement_client_runtime_surface.py",
        "tests/test_property_compliance_status_service.py",
        "tests/test_today_projection_quality.py",
        "tests/test_billing_lifecycle_visibility_contract.py",
    ]
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", *tests, "-q", "--tb=no"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    return {"exit_code": proc.returncode, "pass": proc.returncode == 0, "stdout_tail": (proc.stdout or "")[-4000:]}


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
    resilience: Dict[str, Any] = {
        "programme": PROGRAMME,
        "generated_at": utc(),
        "pace_seconds": PACE,
        "batch_pause_seconds": BATCH_PAUSE,
        "max_429_retries": MAX_429_RETRIES,
        "fresh_step_up_per_batch": True,
    }
    flags: List[str] = []
    results: Dict[str, bool] = {}

    admin_t, admin_user, step_up, login_err = admin_session()
    resilience["admin_login"] = login_err or "ok"

    fixtures: Dict[str, Any] = {}
    fixture_registry = effective_fixture_registry()
    if admin_t:
        for sid, spec in fixture_registry.items():
            print(f"resolve {sid}...")
            fixtures[sid] = resolve_fixture(admin_t, step_up, sid, spec, resilience)
            write_artifact("plan_fixture_setup_runtime.json", {"programme": PROGRAMME, "generated_at": utc(), "marker": MARKER, "fixtures": fixtures, "resilience": resilience})
            if not fixtures[sid].get("pass"):
                flags.append("PLAN_FIXTURE_GAP")
            time.sleep(BATCH_PAUSE)
            # Fresh session every 3 scenarios
            if sid in ("C", "F", "I"):
                admin_t, admin_user, step_up, login_err = admin_session()
                if login_err:
                    resilience["mid_run_login_error"] = login_err
                    break
    else:
        flags.append("FAIL_OPERATIONAL")
        for sid, spec in FIXTURE_REGISTRY.items():
            fixtures[sid] = {"scenario": sid, "label": spec.get("label"), "resolved": False, "error": login_err or "admin_unavailable"}

    write_artifact("plan_fixture_setup_runtime.json", {"programme": PROGRAMME, "generated_at": utc(), "marker": MARKER, "fixtures": fixtures, "resilience": resilience})

    satisfaction_rows = []
    for sid, fx in fixtures.items():
        if fx.get("local_only"):
            satisfaction_rows.append({"scenario": sid, "method": "local_plan_limit", "pass": fx.get("pass")})
            continue
        probe = ((fx.get("selected") or {}).get("probe") or {})
        if not probe:
            satisfaction_rows.append({"scenario": sid, "pass": False, "reason": "no_probe"})
            continue
        satisfaction_rows.append({
            "scenario": sid,
            "client_id": (fx.get("selected") or {}).get("client_id"),
            "all_satisfied": probe.get("all_satisfied"),
            "overdue": probe.get("overdue"),
            "properties_green": probe.get("property_rag", {}).get("GREEN"),
            "score": probe.get("score"),
            "pass": probe.get("all_satisfied") if FIXTURE_REGISTRY[sid].get("expected_today") == "calm" else (probe.get("requirement_unsatisfied") or 0) > 0,
        })
    sat_pass = all(r.get("pass") for r in satisfaction_rows if r.get("scenario") != "C")
    write_artifact("plan_fixture_satisfaction_runtime.json", {"programme": PROGRAMME, "generated_at": utc(), "rows": satisfaction_rows, "pass": sat_pass})

    solo = {k: {"fixture": fixtures.get(k), "closeout": evaluate_closeout(fixtures.get(k) or {}, FIXTURE_REGISTRY[k])} for k in ("A", "B", "C")}
    port = {k: {"fixture": fixtures.get(k), "closeout": evaluate_closeout(fixtures.get(k) or {}, FIXTURE_REGISTRY[k])} for k in ("D", "E", "F")}
    pro = {k: {"fixture": fixtures.get(k), "closeout": evaluate_closeout(fixtures.get(k) or {}, FIXTURE_REGISTRY[k])} for k in ("G", "H", "I")}
    write_artifact("solo_plan_closeout_runtime.json", {"programme": PROGRAMME, "generated_at": utc(), **solo, "pass": all(v["closeout"].get("pass") for v in solo.values())})
    write_artifact("portfolio_plan_closeout_runtime.json", {"programme": PROGRAMME, "generated_at": utc(), **port, "pass": all(v["closeout"].get("pass") for v in port.values())})
    write_artifact("professional_plan_closeout_runtime.json", {"programme": PROGRAMME, "generated_at": utc(), **pro, "pass": all(v["closeout"].get("pass") for v in pro.values())})

    ent_rows = []
    for sid in ("A", "B", "D", "F", "G", "I"):
        fx = fixtures.get(sid) or {}
        sel = fx.get("selected") or {}
        probe = sel.get("probe") or {}
        if probe:
            ent_rows.append({"scenario": sid, "plan": FIXTURE_REGISTRY[sid]["plan_code"], "api_plan": probe.get("entitlements_plan"), "features_enabled": probe.get("features_enabled"), "pass": probe.get("entitlements_plan") == FIXTURE_REGISTRY[sid]["plan_code"]})
    ent_pass = bool(ent_rows) and all(r.get("pass") for r in ent_rows)
    write_artifact("plan_entitlement_closeout_runtime.json", {"programme": PROGRAMME, "generated_at": utc(), "rows": ent_rows, "pass": ent_pass})

    conv_rows = []
    for sid, fx in fixtures.items():
        probe = ((fx.get("selected") or {}).get("probe") or {})
        if not probe:
            continue
        conv_rows.append({
            "scenario": sid,
            "dashboard_total": probe.get("dashboard_total"),
            "requirement_total": probe.get("requirement_total"),
            "dashboard_satisfied": probe.get("dashboard_satisfied"),
            "requirement_satisfied": probe.get("requirement_satisfied"),
            "pass": probe.get("dashboard_total") == probe.get("requirement_total") or abs(int(probe.get("dashboard_total") or 0) - int(probe.get("requirement_total") or 0)) <= 2,
        })
    conv_pass = bool(conv_rows) and all(r.get("pass") for r in conv_rows)
    write_artifact("plan_cross_surface_closeout_runtime.json", {"programme": PROGRAMME, "generated_at": utc(), "rows": conv_rows, "pass": conv_pass})

    browser_all: List[Dict[str, Any]] = []
    if admin_t and sync_playwright:
        batches = [
            [("A", "solo_all", fixtures.get("A", {})), ("B", "solo_partial", fixtures.get("B", {}))],
            [("D", "portfolio_all", fixtures.get("D", {})), ("F", "portfolio_partial", fixtures.get("F", {}))],
            [("G", "pro_all", fixtures.get("G", {})), ("I", "pro_partial", fixtures.get("I", {}))],
        ]
        for batch in batches:
            browser_all.extend(browser_batch(admin_t, step_up, batch, resilience))
            time.sleep(BATCH_PAUSE * 2)
    browser_pass = bool(browser_all) and all(c.get("pass") for c in browser_all if c.get("client_id"))
    write_artifact("plan_browser_closeout_runtime.json", {"programme": PROGRAMME, "generated_at": utc(), "captures": browser_all, "pass": browser_pass, "screenshot_dir": str(SHOT.relative_to(ROOT))})

    write_artifact("plan_harness_resilience_runtime.json", resilience)

    regression = run_regression()
    write_artifact("plan_closeout_regression_runtime.json", {"programme": PROGRAMME, "generated_at": utc(), **regression})

    results.update({
        "fixtures": all(fx.get("pass") for fx in fixtures.values()),
        "satisfaction": sat_pass,
        "solo": solo["A"]["closeout"].get("pass") and solo["B"]["closeout"].get("pass") and solo["C"]["closeout"].get("pass"),
        "portfolio": all(v["closeout"].get("pass") for v in port.values()),
        "professional": all(v["closeout"].get("pass") for v in pro.values()),
        "entitlements": ent_pass,
        "convergence": conv_pass,
        "browser": browser_pass,
        "regression": regression.get("pass"),
    })
    verified = all(results.values())
    results["verified"] = verified
    if not verified:
        if not results.get("fixtures"):
            flags.append("PLAN_FIXTURE_GAP")
        if not results.get("browser"):
            flags.append("FAIL_OPERATIONAL")
        if not results.get("entitlements"):
            flags.append("PLAN_ENTITLEMENT_DRIFT")
        if not results.get("convergence"):
            flags.append("CROSS_SURFACE_DRIFT")

    classification = classify(results, flags)
    write_artifact("classifications.json", {
        "programme": PROGRAMME,
        "prior_programme": "PLAN-BASED-BUSINESS-OUTCOME-RUNTIME-AUDIT-01",
        "generated_at": utc(),
        "marker": MARKER,
        "classification": classification,
        "secondary_flags": sorted(set(flags)),
        "results": results,
    })

    report_lines = [
        f"# {PROGRAMME}",
        "",
        f"**Classification:** `{classification}`",
        f"**Marker:** `{MARKER}`",
        "",
        "## Fixture resolution",
        "",
    ]
    for sid, fx in fixtures.items():
        cid = ((fx.get("selected") or {}).get("client_id")) or fx.get("error") or "—"
        report_lines.append(f"- **{sid}** {FIXTURE_REGISTRY[sid]['label']}: `{cid}` pass={fx.get('pass')}")
    (OUT / "REPORT.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    watch = ["# Watchlist", "", f"Status: `{classification}`", ""]
    for sid, fx in fixtures.items():
        if not fx.get("pass"):
            watch.append(f"- [ ] Resolve fixture **{sid}**: {fx.get('gap') or fx.get('error') or 'criteria mismatch'}")
    if login_err:
        watch.append(f"- [ ] API login blocked: `{login_err}` — re-run after cooldown")
    watch.extend(["", "```bash", "cd backend", "python scripts/plan_based_business_outcome_fixture_closeout_01_execute.py", "```"])
    (OUT / "watchlist.md").write_text("\n".join(watch) + "\n", encoding="utf-8")

    print(json.dumps({"classification": classification, "results": results, "flags": sorted(set(flags))}, indent=2))
    return 0 if classification == "VERIFIED_OPERATIONALLY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
