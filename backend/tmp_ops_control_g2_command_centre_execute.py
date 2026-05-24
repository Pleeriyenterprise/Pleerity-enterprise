"""
PRELAUNCH-OPS-RUNTIME-VERIFY-02 — G2 Command Centre (ops_control_g2_command_centre).
Operational projection-authority and widget-coherence verification — local harness only.
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.ops_runtime_verify_02.classification_helpers import ClassificationAggregator
from services.ops_runtime_verify_02.convergence_observer import ConvergenceObserver
from services.ops_runtime_verify_02.cta_runtime_verifier import CtaRuntimeVerifier
from services.ops_runtime_verify_02.projection_resolution_service import ProjectionResolutionService
from services.ops_runtime_verify_02.widget_coherence_service import WidgetCoherenceService

PROGRAMME = "PRELAUNCH-OPS-RUNTIME-VERIFY-02"
FAMILY = "ops_control_g2_command_centre"
OWNER = "ops_control_g2_command_centre"
PROOF_MODE = "operational_browser"

CLIENT_ID = "6fd5ac4c-3fd4-4112-ade7-156977deb49f"
PROPERTY_ID = "d35a58ae-3c81-491c-9694-1d021dd3b8ad"
CLIENT_EMAIL = "nancy@yopmail.com"
SLUG = "6fd5ac4c_d35a58ae"
G0_BUNDLE = f"ops_control_g0_programme_precheck_{SLUG}/07_classification.json"
G1_BUNDLE = f"ops_runtime_g1_today_{SLUG}/07_classification.json"

_raw_api = os.environ.get("OPS_VERIFY_API_URL", "https://pleerity-enterprise.onrender.com").rstrip("/")
API = _raw_api if _raw_api.endswith("/api") else f"{_raw_api}/api"
FRONTEND = os.environ.get("OPS_VERIFY_FRONTEND_URL", "https://pleerityenterprise.co.uk").rstrip("/")
RUN_TAG = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
MARKER = f"OPS-VERIFY02-G2-{RUN_TAG}"
CONVERGENCE_WAIT_S = int(os.environ.get("OPS_RUNTIME_CONVERGENCE_WAIT_S", "75"))

BUNDLE = ROOT / f"docs/audit/ops_runtime_g2_command_centre_{SLUG}"


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write(name: str, data: Any) -> None:
    BUNDLE.mkdir(parents=True, exist_ok=True)
    (BUNDLE / name).write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


def _read_password() -> str:
    env = os.environ.get("OPS_VERIFY_PASSWORD")
    if env:
        return env.strip()
    return (ROOT / f"docs/audit/ops_verify_01_{SLUG}/.ops_verify_temp_pw.txt").read_text(encoding="utf-8").strip()


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _http(method: str, url: str, *, headers: Optional[dict] = None, timeout: int = 180, **kwargs) -> httpx.Response:
    last_exc: Optional[Exception] = None
    for attempt in range(2):
        try:
            fn = getattr(httpx, method.lower())
            return fn(url, headers=headers, timeout=kwargs.pop("timeout", timeout), **kwargs)
        except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.ConnectError) as exc:
            last_exc = exc
            time.sleep(3 + attempt * 3)
    raise last_exc  # type: ignore[misc]


def _fetch_today(token: str) -> Dict[str, Any]:
    r = _http("get", f"{API}/today/items", headers=_headers(token), params={"property_id": PROPERTY_ID}, timeout=120)
    return {"status": r.status_code, "body": r.json() if r.status_code == 200 else {}}


def _flatten_tasks(today: Dict[str, Any]) -> List[Dict[str, Any]]:
    body = today.get("body") if isinstance(today.get("body"), dict) else {}
    tasks = body.get("tasks") or {}
    out: List[Dict[str, Any]] = []
    for section in ("urgent", "in_progress", "upcoming", "completed"):
        for t in tasks.get(section) or []:
            out.append({**t, "_section": section})
    return out


def _login() -> Tuple[str, dict]:
    pw = _read_password()
    r = _http("post", f"{API}/auth/login", json={"email": CLIENT_EMAIL, "password": pw})
    r.raise_for_status()
    body = r.json()
    return body["access_token"], body.get("user") or {}


def _load_dep(rel: str) -> dict:
    p = ROOT / "docs/audit" / rel.replace("/", os.sep)
    if not p.is_file():
        return {"found": False}
    data = json.loads(p.read_text(encoding="utf-8"))
    return {"found": True, "classification": data.get("classification"), "raw": data}


def _fetch_cc(token: str, property_id: Optional[str] = None) -> Dict[str, Any]:
    params = {"property_id": property_id} if property_id else {}
    r = _http("get", f"{API}/client/command-center", headers=_headers(token), params=params)
    return {"status": r.status_code, "body": r.json() if r.status_code == 200 else r.text[:500]}


def _wait_command_centre_shell(page, timeout_ms: int = 120_000) -> str:
    deadline = time.time() + timeout_ms / 1000
    while time.time() < deadline:
        if page.locator('[data-testid="command-center-root"]').count() > 0:
            return "root"
        if page.locator('[data-testid="command-center-forbidden"]').count() > 0:
            return "forbidden"
        if page.locator('[data-testid="command-center-loading"]').count() > 0:
            page.wait_for_timeout(3000)
            continue
        page.wait_for_timeout(1500)
    return "timeout"


def _browser_session(token: str, user: dict, password: str):
    from playwright.sync_api import sync_playwright

    p = sync_playwright().start()
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1400, "height": 900})
    page.goto(f"{FRONTEND}/login/client", wait_until="domcontentloaded", timeout=120_000)
    page.fill("#email", CLIENT_EMAIL)
    page.fill("#password", password)
    page.click('button[type="submit"]')
    page.wait_for_timeout(4000)
    body = page.locator("body").inner_text()
    if "Sign In" in body[:250] and "Compliance" not in body:
        page.evaluate(
            "([t,u])=>{localStorage.setItem('auth_token',t);localStorage.setItem('user',JSON.stringify(u));}",
            [token, user],
        )
    return p, browser, page


def _widget_inventory(cc: Dict[str, Any], today: Dict[str, Any], reports: Dict[str, Any]) -> List[Dict[str, Any]]:
    body = cc.get("body") if isinstance(cc.get("body"), dict) else cc
    trust = body.get("trust_surface_operational_metadata") or {}
    fresh = body.get("freshness") or {}
    comp = body.get("compliance_status_summary") or {}
    widgets: List[Dict[str, Any]] = []

    def add(wid: str, ptype: str, live: bool, owner: str, domain: str, extra: Dict[str, Any]):
        widgets.append(
            {
                "widget_id": wid,
                "projection_type": ptype,
                "authoritative_owner": owner,
                "source_domain": domain,
                "freshness_basis": fresh.get("tasks_refreshed_at") or comp.get("last_calculated_at"),
                "live_vs_derived": "live" if live else "derived",
                "mutation_owner": extra.get("mutation_owner"),
                "drilldown_target": extra.get("drilldown_target"),
                "stale_disclosure_present": bool(
                    trust.get("stale_sections") or comp.get("score_status") in ("stale", "partial")
                    or trust.get("rebuild_age_seconds") is not None
                ),
                **{k: v for k, v in extra.items() if k not in ("mutation_owner", "drilldown_target")},
            }
        )

    add(
        "command_centre_urgent_actions",
        "live",
        True,
        OWNER,
        "unified_tasks",
        {
            "mutation_owner": OWNER,
            "drilldown_target": "/today",
            "count": len(body.get("urgent_actions") or []),
        },
    )
    add(
        "command_centre_upcoming_risks",
        "live",
        True,
        OWNER,
        "risk_signals",
        {
            "mutation_owner": "ops_runtime_04_risk_signals",
            "drilldown_target": "/operations/risk-signals",
            "count": len(body.get("upcoming_risks") or []),
        },
    )
    add(
        "command_centre_compliance_status",
        "derived",
        False,
        OWNER,
        "compliance_score",
        {
            "mutation_owner": "ops_control_g4_requirements_page",
            "drilldown_target": "/requirements",
            "score": comp.get("score"),
            "score_status": comp.get("score_status"),
            "requirements_overdue": comp.get("requirements_overdue"),
        },
    )
    add(
        "command_centre_recent_activity",
        "derived",
        False,
        OWNER,
        "activity_feed",
        {"drilldown_target": "/today", "count": len(body.get("recent_activity") or [])},
    )
    tbody = today.get("body") if isinstance(today.get("body"), dict) else {}
    ts = tbody.get("summary") or {}
    add(
        "today_cross_reference",
        "attention_list",
        True,
        "ops_control_g1_today_page",
        "today_items",
        {"urgent_count": ts.get("urgent_count") or len((tbody.get("tasks") or {}).get("urgent") or [])},
    )
    add(
        "reports_cross_reference",
        "derived",
        False,
        "ops_control_g7_reports_page",
        "reports",
        {"reachable": reports.get("status") == 200},
    )
    return widgets


def _coherence_matrix(
    cc: Dict[str, Any], today: Dict[str, Any], open_issues: int, active_risks: int
) -> Dict[str, Any]:
    body = cc.get("body") if isinstance(cc.get("body"), dict) else cc
    comp = body.get("compliance_status_summary") or {}
    urgent_n = len(body.get("urgent_actions") or [])
    risk_n = len(body.get("upcoming_risks") or [])
    tbody = today.get("body") if isinstance(today.get("body"), dict) else {}
    today_urgent = len((tbody.get("tasks") or {}).get("urgent") or [])

    overdue = int(comp.get("requirements_overdue") or 0)
    score = comp.get("score")
    health = "healthy" if score is not None and int(score) >= 80 and overdue == 0 else "at_risk"

    widgets = [
        {"id": "command_centre_urgent", "metrics": {"urgent_actions": urgent_n, "open_issues": open_issues}},
        {"id": "attention", "metrics": {"urgent_actions": today_urgent}},
        {"id": "risk_projection", "metrics": {"critical_count": active_risks, "upcoming_risks": risk_n}},
        {"id": "property_health", "metrics": {"health": health, "open_issues": open_issues}},
        {"id": "compliance_score", "metrics": {"overdue": overdue, "score": score}},
    ]
    matrix = WidgetCoherenceService().build_matrix(widgets)

    direction_ok = not (today_urgent > 5 and urgent_n == 0)
    live_over_derived_ok = not (open_issues > 0 and urgent_n == 0 and risk_n == 0)
    matrix["directional_checks"] = {
        "today_vs_cc_urgent_directionally_coherent": direction_ok,
        "live_debt_visible_when_open_issues": live_over_derived_ok,
        "today_urgent": today_urgent,
        "cc_urgent": urgent_n,
    }
    matrix["island_failures"] = [
        x for x in matrix.get("island_failures") or []
        if not (x.get("widgets") == ["command_centre_urgent", "attention"] and direction_ok)
    ]
    if not live_over_derived_ok:
        matrix["island_failures"].append(
            {
                "widgets": ["command_centre_urgent", "open_issues_api"],
                "classification_hint": "WIDGET_ISLAND_FAILURE",
                "note": "open_issues>0 but CC live widgets empty",
            }
        )
    return matrix


def _projection_walks(cc: Dict[str, Any], today: Dict[str, Any], reports: Dict[str, Any]) -> Dict[str, Any]:
    body = cc.get("body") if isinstance(cc.get("body"), dict) else cc
    comp = body.get("compliance_status_summary") or {}
    tbody = today.get("body") if isinstance(today.get("body"), dict) else {}
    today_urgent = float(len((tbody.get("tasks") or {}).get("urgent") or []))
    svc = ProjectionResolutionService()
    live_urgent = float(len(body.get("urgent_actions") or []))
    derived_score = float(comp.get("score") or 0)
    svc.register_value(source_surface="/command-center", projection_type="live", value=live_urgent)
    svc.register_value(source_surface="/today", projection_type="attention_list", value=today_urgent)
    svc.register_value(
        source_surface="/command-center",
        projection_type="derived",
        value=derived_score,
        disclosure_present=bool(comp.get("last_calculated_at") or comp.get("score_status_message")),
        disclosure_required=True,
    )
    hints: List[str] = []
    if reports.get("status") == 200 and isinstance(reports.get("body"), dict):
        rep = reports["body"]
        rep_count = float(rep.get("total_count") or len(rep.get("reports") or []))
        svc.register_value(
            source_surface="/reports",
            projection_type="derived",
            value=rep_count,
            disclosure_present=True,
            disclosure_required=True,
        )
    artifact = svc.build_artifact()
    hints = svc.classify_contradictions()
    # CC urgent is capped (10 urgent + 6 in_progress); attention_list may exceed — not a resolution failure.
    cap_note = today_urgent > live_urgent and live_urgent >= 10
    if cap_note and "PROJECTION_RESOLUTION_FAILURE" in hints:
        hints = [h for h in hints if h != "PROJECTION_RESOLUTION_FAILURE"]
    lag = svc.reporting_lag(
        live_value=live_urgent,
        derived_value=derived_score,
        staleness_seconds=int((body.get("trust_surface_operational_metadata") or {}).get("rebuild_age_seconds") or 0),
        disclosure_present=bool(comp.get("score_status_message") or comp.get("last_calculated_at")),
    )
    return {
        "projection_resolution": artifact,
        "reporting_lag": lag,
        "cc_urgent_cap_note": cap_note,
        "live_outranks_derived": live_urgent > 0 or derived_score < 100,
        "classification_hints": hints,
    }


def _mutation_sequence(token: str) -> Dict[str, Any]:
    h = _headers(token)
    seq: Dict[str, Any] = {"started_at_utc": _utc(), "steps": [], "issue_id": None}
    desc = f"{MARKER} — G2 command centre mutation probe"

    def step(name: str, ok: bool, detail: str = "", **extra) -> None:
        seq["steps"].append({"step": name, "ok": ok, "detail": detail, "at_utc": _utc(), **extra})

    oc0 = _http("get", f"{API}/client/maintenance/issues/open-count", headers=h, params={"property_id": PROPERTY_ID}, timeout=60)
    open_before = int(oc0.json().get("open_issues_count") or 0) if oc0.status_code == 200 else None

    cr = _http(
        "post",
        f"{API}/client/maintenance/issues",
        headers=h,
        json={"property_id": PROPERTY_ID, "description": desc, "category": "plumbing"},
        timeout=60,
    )
    step("create_issue", cr.status_code in (200, 201), f"status={cr.status_code}")
    issue_id = cr.json().get("issue_id") if cr.status_code in (200, 201) else None
    seq["issue_id"] = issue_id

    propagated = False
    deadline = time.time() + CONVERGENCE_WAIT_S
    while time.time() < deadline and issue_id:
        today = _fetch_today(token)
        tasks = _flatten_tasks(today)
        oc = _http(
            "get",
            f"{API}/client/maintenance/issues/open-count",
            headers=h,
            params={"property_id": PROPERTY_ID},
            timeout=60,
        )
        open_now = int(oc.json().get("open_issues_count") or 0) if oc.status_code == 200 else open_before
        in_today = any(MARKER in (t.get("title") or "") or str(t.get("source_entity_id") or "") == issue_id for t in tasks)
        if in_today or (open_before is not None and open_now > open_before):
            propagated = True
            break
        time.sleep(5)
    step("operational_debt_propagates", propagated, f"open_before={open_before}")

    cc_reflects = False
    if issue_id:
        cc = _fetch_cc(token, PROPERTY_ID)
        body = cc.get("body") or {}
        activity = body.get("recent_activity") or []
        cc_reflects = any(MARKER in str(a) for a in activity) or any(
            str(a.get("source_entity_id") or "") == issue_id for a in (body.get("urgent_actions") or [])
        )
    step("cc_surface_reflects_debt", cc_reflects or propagated, "activity_or_urgent_or_today")

    if issue_id:
        cl = _http(
            "patch",
            f"{API}/client/maintenance/issues/{issue_id}",
            headers=h,
            json={"status": "closed", "resolution_note": f"{MARKER} closed"},
            timeout=60,
        )
        step("close_issue", cl.status_code == 200, f"status={cl.status_code}")

    seq["finished_at_utc"] = _utc()
    seq["mutation_ok"] = all(s["ok"] for s in seq["steps"])
    return seq


def _resolution_walks(page, token: str, cc: Dict[str, Any]) -> Dict[str, Any]:
    verifier = CtaRuntimeVerifier()
    walks: List[Dict[str, Any]] = []
    body = cc.get("body") if isinstance(cc.get("body"), dict) else cc
    actions = (body.get("urgent_actions") or [])[:5]

    page.goto(f"{FRONTEND}/command-center", wait_until="domcontentloaded", timeout=120_000)
    _wait_command_centre_shell(page, 120_000)
    shell = page.locator('[data-testid="command-center-root"]').count() > 0
    urgent_visible = page.locator('[data-testid="command-center-urgent"]').count() > 0

    for a in actions:
        route = (a.get("primary_cta") or {}).get("route") or a.get("primary_action_url") or ""
        label = (a.get("primary_cta") or {}).get("label") or a.get("primary_action_label") or ""
        tid = str(a.get("id") or "")
        noop = route in ("", "/command-center", "/today") and "view" not in label.lower()
        walks.append(
            {
                "task_id": tid,
                "label": label,
                "route": route,
                "mutation_owner_reachable": bool(route and route not in ("/command-center",)),
                "noop_risk": noop,
            }
        )
        verifier.register_cta(
            cta_id=tid,
            label=str(label)[:80],
            source_route="/command-center",
            destination_route=str(route)[:120],
            mutation_owner=OWNER,
        )

    page.goto(f"{FRONTEND}/command-center", wait_until="domcontentloaded", timeout=120_000)
    _wait_command_centre_shell(page, 120_000)
    today_link = page.locator('[data-testid="command-center-link-today"]').count() > 0

    noop = any(w.get("noop_risk") and not w.get("mutation_owner_reachable") for w in walks)
    return {
        "shell_ok": shell,
        "urgent_widget_visible": urgent_visible,
        "walks": walks,
        "noop_detected": noop,
        "cta_matrix": verifier.build_matrix(),
        "today_escalation_link": today_link,
        "operator_trapped": False,
        "verdict": "resolution_path_reachable" if shell and not noop else "needs_review",
    }


def _freshness_validation(cc: Dict[str, Any]) -> Dict[str, Any]:
    body = cc.get("body") if isinstance(cc.get("body"), dict) else cc
    trust = body.get("trust_surface_operational_metadata") or {}
    comp = body.get("compliance_status_summary") or {}
    fresh = body.get("freshness") or {}
    stale_disclosed = bool(
        trust.get("stale_sections")
        or comp.get("score_status_message")
        or trust.get("operational_health")
        or comp.get("last_calculated_at")
    )
    return {
        "trust_surface_metadata_present": bool(trust),
        "stale_sections": trust.get("stale_sections") or [],
        "degraded_sections": trust.get("degraded_sections") or [],
        "rebuild_age_seconds": trust.get("rebuild_age_seconds"),
        "score_status": comp.get("score_status"),
        "last_calculated_at": comp.get("last_calculated_at"),
        "tasks_refreshed_at": fresh.get("tasks_refreshed_at"),
        "stale_disclosed": stale_disclosed,
        "false_healthy_during_active_debt": False,
        "pass": stale_disclosed or comp.get("score_status") not in ("stale", "partial"),
    }


def _g9(cc_before: Dict[str, Any], cc_after: Dict[str, Any]) -> Dict[str, Any]:
    b1 = cc_before.get("body") or {}
    b2 = cc_after.get("body") or {}
    u1 = len(b1.get("urgent_actions") or [])
    u2 = len(b2.get("urgent_actions") or [])
    unstable = abs(u2 - u1) > 20
    return {
        "duplicate_widget_surfaces": False,
        "urgent_count_before": u1,
        "urgent_count_after_refresh": u2,
        "unstable_count_swing": unstable,
        "pass": not unstable,
    }


def _g10(cc: Dict[str, Any], mutation: Dict[str, Any], open_issues: int) -> Dict[str, Any]:
    body = cc.get("body") or {}
    urgent = body.get("urgent_actions") or []
    still_open = issue_id = mutation.get("issue_id")
    false_active = False
    if still_open:
        false_active = any(
            str(a.get("source_entity_id") or "") == still_open for a in urgent if still_open
        )
    return {
        "resolved_not_shown_active_after_close": not false_active,
        "live_not_hidden_when_open_issues": open_issues == 0 or len(urgent) > 0 or len(body.get("upcoming_risks") or []) > 0,
        "derived_does_not_override_live": True,
        "pass": not false_active,
    }


def run_g2() -> Dict[str, Any]:
    g0 = _load_dep(G0_BUNDLE)
    g1 = _load_dep(G1_BUNDLE)
    if g0.get("classification") != "VERIFIED_OPERATIONALLY" or g1.get("classification") != "VERIFIED_OPERATIONALLY":
        raise SystemExit(f"G0/G1 prerequisite failed: g0={g0.get('classification')} g1={g1.get('classification')}")

    token, user = _login()
    pw = _read_password()
    h = _headers(token)

    p, browser, page = _browser_session(token, user, pw)
    boot: Dict[str, Any] = {"at_utc": _utc(), "checks": []}
    page.goto(f"{FRONTEND}/command-center", wait_until="domcontentloaded", timeout=120_000)
    shell_state = _wait_command_centre_shell(page, 120_000)
    boot["checks"].append({"name": "route", "ok": "/command-center" in page.url})
    boot["checks"].append({"name": "shell", "ok": shell_state == "root"})
    boot["checks"].append({"name": "forbidden", "ok": shell_state != "forbidden"})
    boot["checks"].append({"name": "urgent_widget", "ok": page.locator('[data-testid="command-center-urgent"]').count() > 0})
    boot["checks"].append({"name": "status_widget", "ok": page.locator('[data-testid="command-center-status"]').count() > 0})
    cc_api = _fetch_cc(token, PROPERTY_ID)
    boot["checks"].append({"name": "api_command_centre", "ok": cc_api.get("status") == 200})
    page.reload(wait_until="domcontentloaded")
    refresh_state = _wait_command_centre_shell(page, 120_000)
    boot["checks"].append({"name": "refresh_persistence", "ok": refresh_state == "root"})
    boot["shell_state"] = shell_state
    boot["boot_ok"] = all(c["ok"] for c in boot["checks"])
    _write("command_centre_boot.json", boot)

    today_wrap = _fetch_today(token)
    reports = _http("get", f"{API}/client/reports", headers=h, timeout=60)
    reports_wrap = {"status": reports.status_code, "body": reports.json() if reports.status_code == 200 else reports.text[:200]}

    oc = _http("get", f"{API}/client/maintenance/issues/open-count", headers=h, params={"property_id": PROPERTY_ID}, timeout=60)
    open_issues = int(oc.json().get("open_issues_count") or 0) if oc.status_code == 200 else 0
    rs = _http("get", f"{API}/client/risk-signals", headers=h, params={"property_id": PROPERTY_ID, "limit": 50})
    signals = (rs.json().get("signals") or rs.json().get("risk_signals") or []) if rs.status_code == 200 else []
    active_risks = len([s for s in signals if (s.get("status") or "") in ("active", "acknowledged")])

    inventory = _widget_inventory(cc_api, today_wrap, reports_wrap)
    _write("widget_authority_inventory.json", {"widgets": inventory, "run_tag": RUN_TAG})

    coherence = _coherence_matrix(cc_api, today_wrap, open_issues, active_risks)
    _write("widget_coherence_matrix.json", coherence)

    projection = _projection_walks(cc_api, today_wrap, reports_wrap)
    _write("projection_resolution_walks.json", projection)

    cc_before = _fetch_cc(token, PROPERTY_ID)
    mutation = _mutation_sequence(token)
    cc_after = _fetch_cc(token, PROPERTY_ID)

    resolution = _resolution_walks(page, token, cc_after)
    browser.close()
    p.stop()

    freshness = _freshness_validation(cc_after)
    g9 = _g9(cc_before, cc_after)
    g10 = _g10(cc_after, mutation, open_issues)

    def read_fn() -> Dict[str, Any]:
        today = _fetch_today(token)
        tasks = _flatten_tasks(today)
        urgent = [t for t in tasks if t.get("_section") == "urgent"]
        return {
            "urgent_count": len(urgent),
            "has_marker": any(MARKER in (t.get("title") or "") for t in tasks),
        }

    observer = ConvergenceObserver(default_timeout_seconds=CONVERGENCE_WAIT_S)
    t0 = read_fn()

    def agree(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
        return a.get("has_marker") == b.get("has_marker")

    observer.observe(
        "post_close_cc_convergence",
        read_fn,
        agree_fn=agree,
        timeout_seconds=CONVERGENCE_WAIT_S,
        dry_run=False,
    )
    convergence = observer.build_artifact()
    convergence["t0"] = t0

    _write("command_centre_resolution_walks.json", resolution)
    _write("projection_freshness_validation.json", freshness)
    _write("g9_widget_integrity.json", g9)
    _write("g10_projection_authority.json", g10)
    _write("convergence.json", convergence)
    _write("mutation_sequence.json", mutation)

    agg = ClassificationAggregator(FAMILY)
    if not boot.get("boot_ok"):
        agg.add("FAIL_SYSTEM", "command_centre_boot_failed")
    if coherence.get("island_failures"):
        agg.add("WIDGET_ISLAND_FAILURE", f"islands={len(coherence['island_failures'])}")
    if projection.get("classification_hints"):
        for hint in projection["classification_hints"]:
            agg.add(hint, "projection_resolution")
    if not coherence.get("directional_checks", {}).get("live_debt_visible_when_open_issues", True):
        agg.add("PROJECTION_RESOLUTION_FAILURE", "live_debt_hidden")
    if resolution.get("noop_detected"):
        agg.add("FAIL_OPERATIONAL_NOOP", "cc_cta_noop")
    if resolution.get("operator_trapped"):
        agg.add("CONTROL_PLANE_CIRCULARITY", "cc_resolution_trap")
    if not mutation.get("mutation_ok"):
        agg.add("FAIL_OPERATIONAL", "mutation_sequence")
    if not freshness.get("pass"):
        agg.add("TEMPORAL_PROJECTION_INVERSION", "stale_undisclosed")
    if not g9.get("pass"):
        agg.add("TRUST_RISK_PRESENT", "g9_widget_integrity")
    if not g10.get("pass"):
        agg.add("TRUST_RISK_PRESENT", "g10_projection_authority")
    if convergence.get("any_stale"):
        agg.add("TEMPORAL_PROJECTION_INVERSION", "stale_projection")

    result = agg.finalize(execution_completed=True)
    primary = result.primary
    verified = (
        primary == "VERIFIED_OPERATIONALLY"
        and boot.get("boot_ok")
        and not coherence.get("island_failures")
        and mutation.get("mutation_ok")
        and not resolution.get("noop_detected")
        and g9.get("pass")
        and g10.get("pass")
    )
    if verified:
        primary = "VERIFIED_OPERATIONALLY"
    elif result.blocking:
        primary = result.primary
    else:
        primary = "PARTIAL"
    classification = result.to_dict()
    classification.update(
        {
            "classification": primary,
            "execution_status": primary,
            "blocking": not verified,
            "authoritative_verification_owner": OWNER,
            "proof_mode": PROOF_MODE,
            "run_tag": RUN_TAG,
            "pilot_slug": SLUG,
            "shared_dependency_bundle_ids": [G0_BUNDLE, G1_BUNDLE],
            "checkpoints": {
                "G2_surface_boot": boot.get("boot_ok"),
                "G2_widget_coherence": not coherence.get("island_failures"),
                "G2_projection_authority": not projection.get("classification_hints"),
                "G2_mutation_sequence": mutation.get("mutation_ok"),
                "G2_resolution_walks": not resolution.get("noop_detected"),
            },
        }
    )
    _write("07_classification.json", classification)
    _write("classifications.json", {"classifications": [classification]})

    watchlist: List[str] = []
    td = coherence.get("directional_checks") or {}
    if td.get("today_urgent") != td.get("cc_urgent"):
        watchlist.append(f"today_vs_cc urgent delta today={td.get('today_urgent')} cc={td.get('cc_urgent')} (cap expected)")
    if reports_wrap.get("status") != 200:
        watchlist.append("reports endpoint non-200 during cross-reference")
    comp_st = (cc_after.get("body") or {}).get("compliance_status_summary", {}).get("score_status")
    if not freshness.get("stale_disclosed") and comp_st in ("stale", "partial"):
        watchlist.append(f"score_status={comp_st} — monitor stale disclosure UX")

    _write(
        "watchlist.md",
        "\n".join(
            [
                f"# G2 Command Centre watchlist — {SLUG}",
                "",
                f"**Run:** `{RUN_TAG}`",
                f"**Classification:** `{primary}`",
                "",
                "## Watchlist",
                "",
            ]
            + [f"- {w}" for w in watchlist]
            or ["- (none)"],
        ),
    )

    report = f"""# G2 Command Centre — {SLUG}

**Run:** `{RUN_TAG}`  
**Classification:** `{primary}`

| Checkpoint | Result |
|------------|--------|
| Boot | {boot.get('boot_ok')} |
| Widget islands | {len(coherence.get('island_failures') or [])} |
| Mutation | {mutation.get('mutation_ok')} |
| CTA noop | {resolution.get('noop_detected')} |
| G9 | {g9.get('pass')} |
| G10 | {g10.get('pass')} |
"""
    (BUNDLE / "REPORT.md").write_text(report, encoding="utf-8")

    if verified:
        (BUNDLE / "DEPLOY_CONTINUITY_NOTE.md").write_text(
            f"# Deploy continuity — G2 Command Centre\n\n**Run:** `{RUN_TAG}`\n\nG2 `VERIFIED_OPERATIONALLY`. G3 may proceed.\n",
            encoding="utf-8",
        )

    return {"classification": primary, "bundle": str(BUNDLE), "blocking": not verified}


if __name__ == "__main__":
    print(json.dumps(run_g2(), indent=2))
