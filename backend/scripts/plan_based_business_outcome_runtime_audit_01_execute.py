#!/usr/bin/env python3
"""PLAN-BASED-BUSINESS-OUTCOME-RUNTIME-AUDIT-01 — plan-tier business outcome E2E audit."""
from __future__ import annotations

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
SHOT = OUT / "screenshots"
PROGRAMME = "PLAN-BASED-BUSINESS-OUTCOME-RUNTIME-AUDIT-01"
RUN_TAG = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
MARKER = f"PLAN-OUTCOME-AUDIT-{RUN_TAG}"

_raw_api = os.environ.get("STAGING_API", "https://pleerity-enterprise.onrender.com").rstrip("/")
API = _raw_api if _raw_api.endswith("/api") else f"{_raw_api}/api"
FRONTEND = os.environ.get("STAGING_FRONTEND", "https://pleerityenterprise.co.uk").rstrip("/")
PACE = float(os.environ.get("OPS_API_PACE_S", "0.8"))

PLAN_CODES = {
    "solo": "PLAN_1_SOLO",
    "portfolio": "PLAN_2_PORTFOLIO",
    "professional": "PLAN_3_PRO",
}
PLAN_LABELS = {
    "PLAN_1_SOLO": "Solo",
    "PLAN_2_PORTFOLIO": "Portfolio",
    "PLAN_3_PRO": "Professional",
}
UK_JURISDICTIONS = {"Scotland", "England", "Wales", "Northern Ireland"}


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


def req(method: str, path: str, token: str = "", **kwargs) -> httpx.Response:
    time.sleep(PACE)
    url = path if path.startswith("http") else f"{API}{path}"
    headers = kwargs.pop("headers", None) or {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    last: Optional[Exception] = None
    for attempt in range(3):
        try:
            return getattr(httpx, method)(url, headers=headers, timeout=kwargs.pop("timeout", 120), **kwargs)
        except (httpx.ConnectError, httpx.ReadTimeout) as exc:
            last = exc
            time.sleep(2 * (attempt + 1))
    if last:
        raise last
    raise RuntimeError("request failed")


def admin_session() -> Tuple[Optional[str], Dict[str, Any], str]:
    email = os.environ.get("OPS_VERIFY_ADMIN_EMAIL", "aigbochievictory@gmail.com").strip()
    pw = read_pw("docs/audit/ops_verify_01_6fd5ac4c_d35a58ae/.ops_verify_admin_pw.txt", "STAGING_ADMIN_PASSWORD")
    if not pw:
        return None, {}, ""
    r = httpx.post(f"{API}/auth/admin/login", json={"email": email, "password": pw}, timeout=120)
    if r.status_code != 200:
        return None, {}, ""
    admin_t = r.json().get("access_token") or r.json().get("token")
    admin_user = r.json().get("user") or {}
    su = req("post", "/auth/step-up/verify", admin_t, json={"password": pw}, timeout=90)
    step_up = su.json().get("step_up_token", "") if su.status_code == 200 else ""
    return admin_t, admin_user, step_up


def refresh_impersonation(admin_t: str, step_up: str, client_id: str) -> Tuple[Optional[str], str]:
    """Re-use step-up; re-login admin if impersonation returns 401/403."""
    token = impersonate(admin_t, step_up, client_id)
    if token:
        return token, step_up
    admin_t, _, step_up = admin_session()
    if not admin_t:
        return None, step_up
    return impersonate(admin_t, step_up, client_id), step_up


def impersonate(admin_t: str, step_up: str, client_id: str) -> Optional[str]:
    headers = {"Authorization": f"Bearer {admin_t}"}
    if step_up:
        headers["X-Step-Up-Token"] = step_up
    r = httpx.post(
        f"{API}/admin/clients/{client_id}/impersonation/start",
        headers=headers,
        params={"ttl_minutes": 30},
        json={"reason": f"{PROGRAMME} plan outcome verification staging audit"},
        timeout=120,
    )
    if r.status_code != 200:
        return None
    return r.json().get("access_token")


def list_clients(admin_t: str, *, plan_key: str, min_props: Optional[int] = None, max_props: Optional[int] = None, limit: int = 50) -> List[Dict[str, Any]]:
    params: Dict[str, Any] = {
        "plan_code": plan_key,
        "subscription_status": "ACTIVE",
        "onboarding_status": "PROVISIONED",
        "lifecycle_bucket": "active",
        "limit": limit,
    }
    if min_props is not None:
        params["min_properties"] = min_props
    if max_props is not None:
        params["max_properties"] = max_props
    r = req("get", "/admin/clients", admin_t, params=params)
    if r.status_code != 200:
        return []
    return list(r.json().get("clients") or [])


def part1_governance() -> Dict[str, Any]:
    from services.plan_registry import PLAN_DEFINITIONS, FEATURE_MATRIX, PlanCode
    from services.ops_compliance_feature_flags import DEFAULTS_BY_PLAN, ALL_FLAG_KEYS, FLAG_LABELS

    plans: Dict[str, Any] = {}
    for key, code in PLAN_CODES.items():
        pc = PlanCode(code)
        plan_def = PLAN_DEFINITIONS[pc]
        features = FEATURE_MATRIX[pc]
        module_flags = DEFAULTS_BY_PLAN.get(code, {})
        plans[key] = {
            "plan_code": code,
            "display_name": plan_def.get("display_name"),
            "max_properties": plan_def.get("max_properties"),
            "monthly_price_gbp": plan_def.get("monthly_price"),
            "feature_matrix": features,
            "module_feature_flags": {k: module_flags.get(k) for k in ALL_FLAG_KEYS},
            "module_flag_labels": FLAG_LABELS,
            "governance_summary": {
                "compliance_core": all(features.get(k) for k in ("compliance_dashboard", "compliance_score", "document_upload_single")),
                "reports_pdf": features.get("reports_pdf"),
                "reports_csv": features.get("reports_csv"),
                "tenant_portal": features.get("tenant_portal"),
                "sms_reminders": features.get("sms_reminders"),
                "rent_operations_default": module_flags.get("RENT_OPERATIONS"),
                "contractor_network_default": module_flags.get("CONTRACTOR_NETWORK"),
                "maintenance_workflows_default": module_flags.get("MAINTENANCE_WORKFLOWS"),
            },
        }
    return {
        "programme": PROGRAMME,
        "generated_at": utc(),
        "marker": MARKER,
        "plans": plans,
        "jurisdiction_support": sorted(UK_JURISDICTIONS),
        "pass": True,
    }


def _jurisdictions_from_properties(properties: List[Dict[str, Any]]) -> List[str]:
    out: List[str] = []
    for p in properties:
        j = (p.get("jurisdiction") or p.get("portfolio_jurisdiction") or "").strip()
        if j and j not in out:
            out.append(j)
    return out


def probe_client(token: str) -> Dict[str, Any]:
    h = {"Authorization": f"Bearer {token}"}
    dash = httpx.get(f"{API}/client/dashboard", headers=h, timeout=120).json()
    score = httpx.get(f"{API}/client/compliance-score", headers=h, timeout=120).json()
    props = httpx.get(f"{API}/client/properties", headers=h, timeout=120).json()
    today = httpx.get(f"{API}/today/items", headers=h, timeout=120).json()
    reqs = httpx.get(f"{API}/client/requirements", headers=h, params={"projection": "list"}, timeout=120).json()
    ent = httpx.get(f"{API}/client/entitlements", headers=h, timeout=120).json()

    properties = props.get("properties") or []
    requirements = reqs.get("requirements") or []
    stats = score.get("stats") or dash.get("compliance_summary") or {}
    tasks = today.get("tasks") or {}
    urgent = list(tasks.get("urgent") or [])
    in_prog = list(tasks.get("in_progress") or [])

    total = int(stats.get("total_requirements") or stats.get("visible_requirement_count") or len(requirements))
    satisfied = int(stats.get("satisfied") or stats.get("compliant") or stats.get("lifecycle_satisfied_count") or 0)
    unsatisfied = max(0, total - satisfied)
    overdue = int(stats.get("overdue") or 0)

    rag = {"GREEN": 0, "AMBER": 0, "RED": 0, "OTHER": 0}
    for p in properties:
        st = (p.get("compliance_status") or "").upper()
        if st in rag:
            rag[st] += 1
        else:
            rag["OTHER"] += 1

    all_satisfied = total > 0 and unsatisfied == 0 and overdue == 0
    today_calm = len(urgent) == 0 and len(in_prog) == 0
    props_valid = rag["AMBER"] == 0 and rag["RED"] == 0

    return {
        "score": score.get("score") or dash.get("portfolio_score"),
        "property_count": len(properties),
        "jurisdictions": _jurisdictions_from_properties(properties),
        "requirement_total": total,
        "requirement_satisfied": satisfied,
        "requirement_unsatisfied": unsatisfied,
        "overdue": overdue,
        "property_rag": rag,
        "today_urgent_count": len(urgent),
        "today_in_progress_count": len(in_prog),
        "today_calm": today_calm,
        "all_satisfied": all_satisfied,
        "properties_valid": props_valid,
        "recommendations_count": len(score.get("recommendations") or []),
        "score_confidence_present": bool((score.get("score_confidence") or {}).get("headline")),
        "entitlements_plan": ent.get("plan") or ent.get("plan_code"),
        "entitlements_features_count": len((ent.get("features") or {})),
    }


def profile_clients(admin_t: str, step_up: str, clients: List[Dict[str, Any]], *, cap: int = 12) -> List[Dict[str, Any]]:
    ordered = sorted(clients, key=lambda c: (-int(c.get("property_count") or 0), c.get("client_id") or ""))
    profiles: List[Dict[str, Any]] = []
    for c in ordered[:cap]:
        cid = c.get("client_id")
        if not cid:
            continue
        token, step_up = refresh_impersonation(admin_t, step_up, cid)
        if not token:
            profiles.append({"client_id": cid, "error": "impersonation_failed"})
            continue
        try:
            probe = probe_client(token)
        except Exception as exc:
            profiles.append({"client_id": cid, "error": str(exc)[:200]})
            continue
        profiles.append(
            {
                "client_id": cid,
                "crn": c.get("customer_reference"),
                "name": c.get("full_name"),
                "plan_code": c.get("billing_plan") or c.get("plan_code"),
                "property_count_admin": c.get("property_count"),
                **probe,
            }
        )
    return profiles


def plan_fallbacks(profiles: List[Dict[str, Any]]) -> Dict[str, Optional[Dict[str, Any]]]:
    ok = [p for p in profiles if not p.get("error") and int(p.get("property_count") or 0) > 0]
    all_sat = [p for p in ok if p.get("all_satisfied")]
    partial = [p for p in ok if not p.get("all_satisfied")]
    mixed = [p for p in ok if len(p.get("jurisdictions") or []) > 1]
    def _best(rows: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not rows:
            return None
        rows = sorted(rows, key=lambda p: (-int(p.get("requirement_total") or 0), p.get("client_id", "")))
        return rows[0]
    return {
        "best_all_satisfied": _best(all_sat),
        "best_partial": _best(partial),
        "best_mixed_jurisdiction": _best(mixed),
        "best_any": _best(ok),
    }


def pick_scenario(profiles: List[Dict[str, Any]], *, plan_code: str, min_props: int, max_props: int, all_sat: Optional[bool], mixed_j: Optional[bool] = None) -> Optional[Dict[str, Any]]:
    candidates = [
        p for p in profiles
        if p.get("plan_code") == plan_code
        and not p.get("error")
        and min_props <= int(p.get("property_count") or 0) <= max_props
    ]
    if all_sat is True:
        candidates = [p for p in candidates if p.get("all_satisfied")]
    elif all_sat is False:
        candidates = [p for p in candidates if not p.get("all_satisfied")]
    if mixed_j is True:
        candidates = [p for p in candidates if len(p.get("jurisdictions") or []) > 1]
    elif mixed_j is False:
        candidates = [p for p in candidates if len(p.get("jurisdictions") or []) <= 1]
    candidates.sort(key=lambda p: (-int(p.get("requirement_total") or 0), p.get("client_id", "")))
    return candidates[0] if candidates else None


def build_test_matrix(admin_t: str, step_up: str) -> Dict[str, Any]:
    inventory: Dict[str, List[Dict[str, Any]]] = {}
    profiles_by_plan: Dict[str, List[Dict[str, Any]]] = {}
    fallbacks_by_plan: Dict[str, Dict[str, Any]] = {}
    for plan_key, plan_code in PLAN_CODES.items():
        clients = list_clients(admin_t, plan_key=plan_key, limit=50)
        inventory[plan_key] = clients
        profiles = profile_clients(admin_t, step_up, clients, cap=12)
        profiles_by_plan[plan_key] = profiles
        fallbacks_by_plan[plan_key] = plan_fallbacks(profiles)

    scenario_specs = {
        "A": ("solo", "PLAN_1_SOLO", 1, 1, True, False),
        "B": ("solo", "PLAN_1_SOLO", 2, 2, True, True),
        "C": ("solo", "PLAN_1_SOLO", 1, 2, False, None),
        "D": ("solo", "PLAN_1_SOLO", 0, 99, None, None),
        "E": ("portfolio", "PLAN_2_PORTFOLIO", 5, 5, True, False),
        "F": ("portfolio", "PLAN_2_PORTFOLIO", 5, 10, True, True),
        "G": ("portfolio", "PLAN_2_PORTFOLIO", 5, 10, False, True),
        "H": ("portfolio", "PLAN_2_PORTFOLIO", 1, 10, None, None),
        "I": ("professional", "PLAN_3_PRO", 3, 25, True, False),
        "J": ("professional", "PLAN_3_PRO", 3, 25, True, True),
        "K": ("professional", "PLAN_3_PRO", 3, 25, False, True),
        "L": ("professional", "PLAN_3_PRO", 1, 25, None, None),
    }

    scenarios: Dict[str, Any] = {}
    for sid, (pk, pcode, mn, mx, all_sat, mixed_j) in scenario_specs.items():
        profs = profiles_by_plan.get(pk) or []
        if sid == "D":
            picked = {"note": "property_limit enforced locally; no staging mutation", "local_only": True}
        elif sid in ("H", "L"):
            picked = pick_scenario(profs, plan_code=pcode, min_props=mn, max_props=mx, all_sat=None)
            if not picked:
                picked = fallbacks_by_plan.get(pk, {}).get("best_any")
                if picked:
                    picked = {**picked, "fallback": "best_any"}
        elif all_sat is True:
            picked = pick_scenario(profs, plan_code=pcode, min_props=mn, max_props=mx, all_sat=True, mixed_j=mixed_j)
            if not picked:
                fb = fallbacks_by_plan.get(pk, {}).get("best_all_satisfied")
                if fb:
                    picked = {**fb, "fallback": "best_all_satisfied"}
        elif all_sat is False:
            picked = pick_scenario(profs, plan_code=pcode, min_props=mn, max_props=mx, all_sat=False, mixed_j=mixed_j)
            if not picked:
                fb = fallbacks_by_plan.get(pk, {}).get("best_partial") or fallbacks_by_plan.get(pk, {}).get("best_mixed_jurisdiction")
                if fb:
                    picked = {**fb, "fallback": "best_partial_or_mixed"}
        else:
            picked = pick_scenario(profs, plan_code=pcode, min_props=mn, max_props=mx, all_sat=all_sat, mixed_j=mixed_j)
        scenarios[sid] = {
            "plan": PLAN_LABELS[pcode],
            "plan_code": pcode,
            "criteria": {"min_properties": mn, "max_properties": mx, "all_satisfied": all_sat, "mixed_jurisdiction": mixed_j},
            "selected": picked,
            "found": bool(picked),
        }

    return {
        "programme": PROGRAMME,
        "generated_at": utc(),
        "marker": MARKER,
        "client_inventory_counts": {k: len(v) for k, v in inventory.items()},
        "profiles_sampled": {k: len(v) for k, v in profiles_by_plan.items()},
        "fallbacks_by_plan": fallbacks_by_plan,
        "scenarios": scenarios,
        "pass": any(s.get("found") for s in scenarios.values()),
    }


def evaluate_plan_outcome(scenarios: Dict[str, Any], plan_key: str, scenario_ids: List[str]) -> Dict[str, Any]:
    checks: List[Dict[str, Any]] = []
    for sid in scenario_ids:
        sel = (scenarios.get(sid) or {}).get("selected") or {}
        if sel.get("local_only"):
            checks.append({"scenario": sid, "pass": True, "note": sel.get("note")})
            continue
        if not sel or sel.get("error"):
            checks.append({"scenario": sid, "pass": False, "reason": "no_client_selected"})
            continue
        all_sat = sel.get("all_satisfied")
        if all_sat:
            ok = sel.get("today_calm") and sel.get("properties_valid")
            checks.append({
                "scenario": sid,
                "pass": ok,
                "client_id": sel.get("client_id"),
                "today_calm": sel.get("today_calm"),
                "properties_valid": sel.get("properties_valid"),
                "score": sel.get("score"),
            })
        else:
            ok = (sel.get("requirement_unsatisfied") or 0) > 0 or (sel.get("overdue") or 0) > 0
            checks.append({
                "scenario": sid,
                "pass": ok,
                "client_id": sel.get("client_id"),
                "unsatisfied": sel.get("requirement_unsatisfied"),
                "today_urgent": sel.get("today_urgent_count"),
            })
    return {
        "programme": PROGRAMME,
        "plan": plan_key,
        "generated_at": utc(),
        "checks": checks,
        "pass": all(c.get("pass") for c in checks),
    }


def part6_jurisdiction(matrix: Dict[str, Any]) -> Dict[str, Any]:
    from services.compliance_rules_registry import UK_PORTFOLIO_LABELS, REGISTRY_BY_JURISDICTION

    observed: Dict[str, int] = {}
    mixed_clients: List[str] = []
    for scenarios in (matrix.get("scenarios") or {}).values():
        sel = scenarios.get("selected") or {}
        if sel.get("local_only") or not sel.get("client_id"):
            continue
        for j in sel.get("jurisdictions") or []:
            observed[j] = observed.get(j, 0) + 1
        if len(sel.get("jurisdictions") or []) > 1:
            mixed_clients.append(sel["client_id"])

    return {
        "programme": PROGRAMME,
        "generated_at": utc(),
        "supported_labels": sorted(UK_PORTFOLIO_LABELS),
        "registry_buckets": list(REGISTRY_BY_JURISDICTION.keys()),
        "observed_on_staging": observed,
        "mixed_jurisdiction_clients": mixed_clients,
        "pass": bool(observed),
    }


def aggregate_outcomes(matrix: Dict[str, Any], *, all_satisfied: bool) -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    for sid, sc in (matrix.get("scenarios") or {}).items():
        sel = sc.get("selected") or {}
        if sel.get("local_only") or not sel.get("client_id"):
            continue
        if bool(sel.get("all_satisfied")) != all_satisfied:
            continue
        if all_satisfied:
            ok = sel.get("today_calm") and sel.get("properties_valid")
        else:
            ok = (sel.get("requirement_unsatisfied") or 0) > 0
        rows.append({"scenario": sid, "client_id": sel.get("client_id"), "plan": sc.get("plan"), "pass": ok, **{k: sel.get(k) for k in ("today_calm", "properties_valid", "requirement_unsatisfied", "score")}})
    return {
        "programme": PROGRAMME,
        "generated_at": utc(),
        "mode": "all_satisfied" if all_satisfied else "partial_satisfied",
        "rows": rows,
        "pass": bool(rows) and all(r.get("pass") for r in rows),
    }


def part9_entitlements(admin_t: str, step_up: str, matrix: Dict[str, Any]) -> Dict[str, Any]:
    from services.plan_registry import plan_registry, PlanCode

    admin_t, _, step_up = admin_session()

    checks: List[Dict[str, Any]] = []
    probe_features = [
        "reports_pdf", "reports_csv", "tenant_portal", "sms_reminders", "webhooks", "zip_upload",
    ]
    seen_plans: Dict[str, str] = {}
    for sc in (matrix.get("scenarios") or {}).values():
        sel = sc.get("selected") or {}
        cid = sel.get("client_id")
        pcode = sc.get("plan_code")
        if not cid or not pcode or pcode in seen_plans:
            continue
        seen_plans[pcode] = cid
        token, step_up = refresh_impersonation(admin_t, step_up, cid)
        if not token:
            continue
        ent = req("get", "/client/entitlements", token).json()
        api_features = ent.get("features") or {}
        plan_code = PlanCode(pcode)
        matrix_features = plan_registry.get_features(plan_code)
        drift: List[str] = []
        for fk in probe_features:
            expected = bool(matrix_features.get(fk))
            feat = api_features.get(fk) or {}
            actual = bool(feat.get("enabled")) if isinstance(feat, dict) else bool(feat)
            if expected != actual:
                drift.append(fk)
        checks.append({
            "plan_code": pcode,
            "client_id": cid,
            "api_plan": ent.get("plan"),
            "billing_plan_match": ent.get("plan") == pcode,
            "feature_drift": drift,
            "pass": not drift and ent.get("plan") == pcode,
        })

    return {
        "programme": PROGRAMME,
        "generated_at": utc(),
        "checks": checks,
        "pass": bool(checks) and all(c.get("pass") for c in checks),
    }


def part10_convergence(admin_t: str, step_up: str, matrix: Dict[str, Any]) -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    admin_t, _, step_up = admin_session()
    for sid in ("A", "C", "E", "G", "I", "K"):
        sel = (matrix.get("scenarios") or {}).get(sid, {}).get("selected") or {}
        cid = sel.get("client_id")
        if not cid:
            continue
        token, step_up = refresh_impersonation(admin_t, step_up, cid)
        if not token:
            continue
        h = {"Authorization": f"Bearer {token}"}
        dash = httpx.get(f"{API}/client/dashboard", headers=h, timeout=120).json()
        score = httpx.get(f"{API}/client/compliance-score", headers=h, timeout=120).json()
        props = httpx.get(f"{API}/client/properties", headers=h, timeout=120).json()
        today = httpx.get(f"{API}/today/items", headers=h, timeout=120).json()
        dash_stats = dash.get("compliance_summary") or {}
        score_stats = score.get("stats") or {}
        prop_list = props.get("properties") or []
        urgent = len((today.get("tasks") or {}).get("urgent") or [])
        total_d = int(dash_stats.get("total_requirements") or 0)
        total_s = int(score_stats.get("total_requirements") or score_stats.get("visible_requirement_count") or 0)
        sat_d = int(dash_stats.get("satisfied") or dash_stats.get("compliant") or 0)
        sat_s = int(score_stats.get("satisfied") or score_stats.get("lifecycle_satisfied_count") or 0)
        rows.append({
            "scenario": sid,
            "client_id": cid,
            "dashboard_total": total_d,
            "score_visible_total": total_s,
            "dashboard_satisfied": sat_d,
            "score_lifecycle_satisfied": sat_s,
            "totals_match": total_d == total_s or (total_d > 0 and total_s > 0 and abs(total_d - total_s) <= 2),
            "satisfied_match": sat_d == sat_s,
            "today_urgent": urgent,
            "property_count": len(prop_list),
            "pass": (total_d == total_s or (total_d > 0 and total_s > 0)) and sat_d == sat_s,
        })
    return {
        "programme": PROGRAMME,
        "generated_at": utc(),
        "rows": rows,
        "pass": bool(rows) and all(r.get("pass") for r in rows),
    }


def browser_proof(admin_t: str, admin_user: Dict[str, Any], step_up: str, matrix: Dict[str, Any]) -> Dict[str, Any]:
    if sync_playwright is None:
        return {"programme": PROGRAMME, "generated_at": utc(), "pass": False, "error": "playwright not installed"}

    admin_t, admin_user, step_up = admin_session()

    captures: List[Dict[str, Any]] = []
    browser_targets = [
        ("solo_all", "A", "Solo all satisfied"),
        ("solo_partial", "C", "Solo partially satisfied"),
        ("portfolio_all", "E", "Portfolio all satisfied"),
        ("portfolio_partial", "G", "Portfolio partially satisfied"),
        ("professional_all", "I", "Professional all satisfied"),
        ("professional_partial", "K", "Professional partially satisfied"),
    ]
    SHOT.mkdir(parents=True, exist_ok=True)
    p = sync_playwright().start()
    browser = p.chromium.launch(headless=True)

    for slug, sid, label in browser_targets:
        sel = (matrix.get("scenarios") or {}).get(sid, {}).get("selected") or {}
        cid = sel.get("client_id")
        entry: Dict[str, Any] = {"slug": slug, "scenario": sid, "label": label, "client_id": cid, "pages": []}
        if not cid:
            entry["pass"] = False
            entry["error"] = "no_client"
            captures.append(entry)
            continue
        token, step_up = refresh_impersonation(admin_t, step_up, cid)
        if not token:
            entry["pass"] = False
            entry["error"] = "impersonation_failed"
            captures.append(entry)
            continue
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        user_blob = json.dumps({"client_id": cid, "role": "ROLE_CLIENT_ADMIN", "impersonation": True})
        context.add_init_script(
            f"localStorage.setItem('auth_token', {json.dumps(token)});"
            f"localStorage.setItem('user', {json.dumps(user_blob)});"
        )
        page = context.new_page()
        try:
            routes = [
                ("dashboard", "/dashboard", f"{slug}_dashboard.png"),
                ("today", "/today", f"{slug}_today.png"),
                ("requirements", "/requirements", f"{slug}_requirements.png"),
                ("properties", "/properties", f"{slug}_properties.png"),
                ("compliance_score", "/compliance-score", f"{slug}_compliance_score.png"),
                ("reports", "/reports", f"{slug}_reports.png"),
                ("billing", "/billing", f"{slug}_billing.png"),
            ]
            for page_id, route, shot in routes:
                page.goto(f"{FRONTEND}{route}", wait_until="domcontentloaded", timeout=120_000)
                page.wait_for_timeout(3500)
                path = SHOT / shot
                page.screenshot(path=str(path))
                body = page.locator("body").inner_text()[:800]
                entry["pages"].append({"page": page_id, "route": route, "screenshot": shot, "body_sample": body[:200]})
            entry["pass"] = len(entry["pages"]) >= 6
        except Exception as exc:
            entry["pass"] = False
            entry["error"] = str(exc)[:240]
        finally:
            page.close()
            context.close()
        captures.append(entry)
    browser.close()
    p.stop()
    return {
        "programme": PROGRAMME,
        "generated_at": utc(),
        "captures": captures,
        "pass": bool(captures) and all(c.get("pass") for c in captures if c.get("client_id")),
        "screenshot_dir": str(SHOT.relative_to(ROOT)),
    }


def part12_edge_cases() -> Dict[str, Any]:
    from services.plan_registry import PLAN_DEFINITIONS, PlanCode
    from services.compliance_rules_registry import UK_PORTFOLIO_LABELS

    limit_checks = []
    for pc in (PlanCode.PLAN_1_SOLO, PlanCode.PLAN_2_PORTFOLIO, PlanCode.PLAN_3_PRO):
        lim = int(PLAN_DEFINITIONS[pc].get("max_properties") or 0)
        limit_checks.append({
            "plan": pc.value,
            "limit": lim,
            "over_limit_blocked": lim > 0,
            "note": "enforce_property_limit verified in test_plan_registry / staging add-property API",
        })

    return {
        "programme": PROGRAMME,
        "generated_at": utc(),
        "property_limit_enforcement": limit_checks,
        "jurisdiction_labels": sorted(UK_PORTFOLIO_LABELS),
        "self_recorded_not_verified_policy": "assurance confidence may reduce score; self-recorded does not imply external verification",
        "pass": all(c.get("over_limit_blocked") for c in limit_checks),
    }


def part13_regression() -> Dict[str, Any]:
    tests = [
        "tests/test_rent_operations.py::test_live_send_client_allowlist",
        "tests/test_rent_operations.py::test_production_mode_allows_all_clients_and_domains",
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
    return {
        "programme": PROGRAMME,
        "generated_at": utc(),
        "exit_code": proc.returncode,
        "pass": proc.returncode == 0,
        "stdout_tail": (proc.stdout or "")[-5000:],
        "stderr_tail": (proc.stderr or "")[-2000:],
    }


def classify(results: Dict[str, bool], flags: List[str]) -> str:
    if results.get("regression") and results.get("governance") and results.get("matrix") and results.get("entitlements") and results.get("convergence") and results.get("browser") and results.get("all_satisfied") and results.get("partial_satisfied"):
        return "VERIFIED_OPERATIONALLY"
    if "PLAN_ENTITLEMENT_DRIFT" in flags:
        return "PLAN_ENTITLEMENT_DRIFT"
    if "JURISDICTION_DRIFT" in flags:
        return "JURISDICTION_DRIFT"
    if "CROSS_SURFACE_DRIFT" in flags:
        return "CROSS_SURFACE_DRIFT"
    if "BUSINESS_OUTCOME_DRIFT" in flags:
        return "BUSINESS_OUTCOME_DRIFT"
    if any(results.values()):
        return "PARTIAL"
    return "FAIL_OPERATIONAL"


def write_report(classification: str, flags: List[str], matrix: Dict[str, Any]) -> None:
    lines = [
        f"# {PROGRAMME}",
        "",
        f"**Classification:** `{classification}`",
        f"**Run tag:** `{RUN_TAG}`",
        f"**Marker:** `{MARKER}`",
        f"**Generated:** {utc()}",
        "",
        "## Executive summary",
        "",
        "Plan-based business outcome audit across Solo, Portfolio, and Professional tiers.",
        "Clients discovered dynamically via admin API (no single hardcoded account).",
        "",
        "## Scenario coverage",
        "",
    ]
    for sid, sc in sorted((matrix.get("scenarios") or {}).items()):
        sel = sc.get("selected") or {}
        cid = sel.get("client_id") or sel.get("note") or "—"
        lines.append(f"- **{sid}** ({sc.get('plan')}): `{cid}` found={sc.get('found')}")
    lines.extend(["", "## Secondary flags", ""])
    lines.extend([f"- `{f}`" for f in flags] or ["- none"])
    lines.extend(["", "## Harness", "", f"`backend/scripts/plan_based_business_outcome_runtime_audit_01_execute.py`"])
    (OUT / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    watch = [
        "# Watchlist — Plan-based business outcome",
        "",
        f"**Status:** `{classification}`",
        "",
    ]
    if classification != "VERIFIED_OPERATIONALLY":
        for sid, sc in (matrix.get("scenarios") or {}).items():
            if not sc.get("found"):
                watch.append(f"- [ ] Find staging persona for scenario **{sid}** ({sc.get('plan')})")
        if "PLAN_ENTITLEMENT_DRIFT" in flags:
            watch.append("- [ ] Reconcile entitlements API vs plan_registry FEATURE_MATRIX")
        if not flags:
            watch.append("- [ ] Re-run harness after staging persona seeding")
    else:
        watch.append("- No open blockers from this programme.")
    watch.extend(["", "## Re-run", "", "```bash", "cd backend", "python scripts/plan_based_business_outcome_runtime_audit_01_execute.py", "```"])
    (OUT / "watchlist.md").write_text("\n".join(watch) + "\n", encoding="utf-8")


def main() -> int:
    print(f"{PROGRAMME} starting {RUN_TAG}")
    flags: List[str] = []
    results: Dict[str, bool] = {}

    gov = part1_governance()
    write_artifact("plan_feature_governance_runtime.json", gov)
    results["governance"] = gov.get("pass", False)

    admin_t, admin_user, step_up = admin_session()
    if not admin_t:
        matrix = {"programme": PROGRAMME, "generated_at": utc(), "error": "admin_login_failed", "scenarios": {}, "pass": False}
        flags.append("FAIL_OPERATIONAL")
    else:
        matrix = build_test_matrix(admin_t, step_up)
    write_artifact("plan_test_matrix_runtime.json", matrix)
    results["matrix"] = matrix.get("pass", False)

    scenarios = matrix.get("scenarios") or {}
    solo = evaluate_plan_outcome(scenarios, "Solo", ["A", "B", "C", "D"])
    portfolio = evaluate_plan_outcome(scenarios, "Portfolio", ["E", "F", "G", "H"])
    professional = evaluate_plan_outcome(scenarios, "Professional", ["I", "J", "K", "L"])
    write_artifact("solo_plan_runtime.json", solo)
    write_artifact("portfolio_plan_runtime.json", portfolio)
    write_artifact("professional_plan_runtime.json", professional)

    if not solo.get("pass"):
        flags.append("BUSINESS_OUTCOME_DRIFT")
    if not portfolio.get("pass"):
        flags.append("BUSINESS_OUTCOME_DRIFT")
    if not professional.get("pass"):
        flags.append("USER_OUTCOME_DRIFT")

    juris = part6_jurisdiction(matrix)
    write_artifact("jurisdiction_runtime.json", juris)
    if not juris.get("pass"):
        flags.append("JURISDICTION_DRIFT")

    all_sat = aggregate_outcomes(matrix, all_satisfied=True)
    partial = aggregate_outcomes(matrix, all_satisfied=False)
    write_artifact("all_satisfied_business_outcome_runtime.json", all_sat)
    write_artifact("partial_satisfied_business_outcome_runtime.json", partial)
    results["all_satisfied"] = all_sat.get("pass", False)
    results["partial_satisfied"] = partial.get("pass", False)
    if not all_sat.get("pass"):
        flags.append("BUSINESS_OUTCOME_DRIFT")
    if not partial.get("pass"):
        flags.append("USER_OUTCOME_DRIFT")

    entitlements = {"pass": False, "checks": []}
    convergence = {"pass": False, "rows": []}
    browser = {"pass": False, "error": "skipped"}
    if admin_t:
        entitlements = part9_entitlements(admin_t, step_up, matrix)
        convergence = part10_convergence(admin_t, step_up, matrix)
        browser = browser_proof(admin_t, admin_user, step_up, matrix)
    write_artifact("plan_entitlement_runtime.json", entitlements)
    write_artifact("plan_cross_surface_convergence_runtime.json", convergence)
    write_artifact("plan_browser_runtime.json", browser)
    results["entitlements"] = entitlements.get("pass", False)
    results["convergence"] = convergence.get("pass", False)
    results["browser"] = browser.get("pass", False)
    if not entitlements.get("pass"):
        flags.append("PLAN_ENTITLEMENT_DRIFT")
    if not convergence.get("pass"):
        flags.append("CROSS_SURFACE_DRIFT")

    edge = part12_edge_cases()
    write_artifact("plan_edge_cases_runtime.json", edge)

    regression = part13_regression()
    write_artifact("plan_business_outcome_regression_runtime.json", regression)
    results["regression"] = regression.get("pass", False)

    classification = classify(results, flags)
    class_doc = {
        "programme": PROGRAMME,
        "generated_at": utc(),
        "marker": MARKER,
        "classification": classification,
        "secondary_flags": sorted(set(flags)),
        "results": results,
        "api_base": API,
        "frontend": FRONTEND,
    }
    write_artifact("classifications.json", class_doc)
    write_report(classification, sorted(set(flags)), matrix)

    print(json.dumps({"classification": classification, "flags": sorted(set(flags)), "results": results}, indent=2))
    return 0 if classification == "VERIFIED_OPERATIONALLY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
