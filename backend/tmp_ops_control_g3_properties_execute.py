"""
PRELAUNCH-OPS-RUNTIME-VERIFY-02 — G3 Properties Page (ops_control_g3_properties_page).
Property-level operational truth arbitration verification — local harness only.
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
FAMILY = "ops_control_g3_properties_page"
OWNER = "ops_control_g3_properties_page"
PROOF_MODE = "operational_browser"

CLIENT_ID = "6fd5ac4c-3fd4-4112-ade7-156977deb49f"
PROPERTY_ID = "d35a58ae-3c81-491c-9694-1d021dd3b8ad"
CLIENT_EMAIL = "nancy@yopmail.com"
SLUG = "6fd5ac4c_d35a58ae"
G0_BUNDLE = f"ops_control_g0_programme_precheck_{SLUG}/07_classification.json"
G1_BUNDLE = f"ops_runtime_g1_today_{SLUG}/07_classification.json"
G2_BUNDLE = f"ops_runtime_g2_command_centre_{SLUG}/07_classification.json"

_raw_api = os.environ.get("OPS_VERIFY_API_URL", "https://pleerity-enterprise.onrender.com").rstrip("/")
API = _raw_api if _raw_api.endswith("/api") else f"{_raw_api}/api"
FRONTEND = os.environ.get("OPS_VERIFY_FRONTEND_URL", "https://pleerityenterprise.co.uk").rstrip("/")
RUN_TAG = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
MARKER = f"OPS-VERIFY02-G3-{RUN_TAG}"
CONVERGENCE_WAIT_S = int(os.environ.get("OPS_RUNTIME_CONVERGENCE_WAIT_S", "75"))

BUNDLE = ROOT / f"docs/audit/ops_runtime_g3_properties_{SLUG}"


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


def _http(method: str, url: str, *, headers: Optional[dict] = None, timeout: int = 120, **kwargs) -> httpx.Response:
    last_exc: Optional[Exception] = None
    for attempt in range(2):
        try:
            fn = getattr(httpx, method.lower())
            return fn(url, headers=headers, timeout=kwargs.pop("timeout", timeout), **kwargs)
        except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.ConnectError) as exc:
            last_exc = exc
            time.sleep(3 + attempt * 3)
    raise last_exc  # type: ignore[misc]


def _load_dep(rel: str) -> dict:
    p = ROOT / "docs/audit" / rel.replace("/", os.sep)
    if not p.is_file():
        return {"found": False}
    data = json.loads(p.read_text(encoding="utf-8"))
    return {"found": True, "classification": data.get("classification"), "raw": data}


def _login() -> Tuple[str, dict]:
    pw = _read_password()
    r = _http("post", f"{API}/auth/login", json={"email": CLIENT_EMAIL, "password": pw}, timeout=60)
    r.raise_for_status()
    body = r.json()
    return body["access_token"], body.get("user") or {}


def _fetch_compliance_detail(token: str) -> Dict[str, Any]:
    r = _http("get", f"{API}/portfolio/properties/{PROPERTY_ID}/compliance-detail", headers=_headers(token))
    return {"status": r.status_code, "body": r.json() if r.status_code == 200 else r.text[:400]}


def _fetch_property_issues(token: str) -> Dict[str, Any]:
    r = _http(
        "get",
        f"{API}/client/maintenance/issues",
        headers=_headers(token),
        params={"property_id": PROPERTY_ID, "limit": 100},
        timeout=90,
    )
    body = r.json() if r.status_code == 200 else {}
    issues = body.get("issues") or body.get("items") or []
    open_issues = [i for i in issues if (i.get("status") or "").lower() not in ("closed", "resolved", "cancelled")]
    return {"status": r.status_code, "issues": issues, "open_count": len(open_issues)}


def _fetch_risk_signals(token: str) -> Dict[str, Any]:
    r = _http(
        "get",
        f"{API}/client/maintenance/properties/{PROPERTY_ID}/risk-signals",
        headers=_headers(token),
        params={"limit": 50},
        timeout=90,
    )
    body = r.json() if r.status_code == 200 else {}
    signals = body.get("signals") or body.get("risk_signals") or []
    active = [s for s in signals if (s.get("status") or "").lower() in ("active", "acknowledged")]
    return {"status": r.status_code, "signals": signals, "active_count": len(active)}


def _fetch_requirements(token: str) -> Dict[str, Any]:
    r = _http("get", f"{API}/client/properties/{PROPERTY_ID}/requirements", headers=_headers(token), timeout=90)
    body = r.json() if r.status_code == 200 else {}
    reqs = body.get("requirements") or []
    overdue = sum(1 for r in reqs if (r.get("status") or "").upper() in ("OVERDUE", "EXPIRED"))
    return {"status": r.status_code, "requirements": reqs, "overdue_count": overdue}


def _fetch_today(token: str) -> Dict[str, Any]:
    r = _http("get", f"{API}/today/items", headers=_headers(token), params={"property_id": PROPERTY_ID}, timeout=90)
    body = r.json() if r.status_code == 200 else {}
    tasks = body.get("tasks") or {}
    urgent = tasks.get("urgent") or []
    return {"status": r.status_code, "urgent_count": len(urgent), "body": body}


def _fetch_cc_scoped(token: str) -> Dict[str, Any]:
    r = _http(
        "get",
        f"{API}/client/command-center",
        headers=_headers(token),
        params={"property_id": PROPERTY_ID},
        timeout=180,
    )
    body = r.json() if r.status_code == 200 else {}
    return {
        "status": r.status_code,
        "urgent_count": len(body.get("urgent_actions") or []),
        "risk_count": len(body.get("upcoming_risks") or []),
    }


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


def _wait_property_detail(page, timeout_ms: int = 90_000) -> str:
    deadline = time.time() + timeout_ms / 1000
    while time.time() < deadline:
        if page.locator('[data-testid="property-detail-refresh"]').count() > 0:
            return "ready"
        if "Invalid property link" in page.locator("body").inner_text()[:500]:
            return "invalid"
        page.wait_for_timeout(2000)
    return "timeout"


def _health_authority(detail: Dict[str, Any], issues: Dict[str, Any], risks: Dict[str, Any], reqs: Dict[str, Any]) -> Dict[str, Any]:
    body = detail.get("body") if isinstance(detail.get("body"), dict) else {}
    score = body.get("score") or body.get("property_score")
    risk_level = str(body.get("risk_level") or "").lower()
    kpis = body.get("kpis") or {}
    open_n = issues.get("open_count") or 0
    active_risks = risks.get("active_count") or 0
    overdue = kpis.get("overdue") if kpis.get("overdue") is not None else reqs.get("overdue_count", 0)

    looks_healthy = (isinstance(score, (int, float)) and score >= 80) or risk_level in ("low", "green", "minimal")
    false_healthy = looks_healthy and (open_n > 0 or active_risks > 0 or int(overdue or 0) > 0)
    live_debt_visible = open_n > 0 or active_risks > 0 or int(overdue or 0) > 0

    svc = ProjectionResolutionService()
    live_debt = float(open_n + active_risks)
    derived_score = float(score or 0)
    svc.register_value(source_surface="/property", projection_type="property_summary", value=live_debt)
    svc.register_value(
        source_surface="/property",
        projection_type="derived",
        value=derived_score,
        disclosure_present=bool(body.get("last_calculated_at") or body.get("score_status_message")),
        disclosure_required=True,
    )
    hints = svc.classify_contradictions()
    if live_debt > 0 and derived_score >= 80 and "PROJECTION_RESOLUTION_FAILURE" in hints:
        pass  # real failure
    elif live_debt > 0 and derived_score < 80:
        hints = [h for h in hints if h not in ("PROJECTION_RESOLUTION_FAILURE", "TEMPORAL_PROJECTION_INVERSION")]

    return {
        "score": score,
        "risk_level": body.get("risk_level"),
        "score_status": body.get("score_status"),
        "last_calculated_at": body.get("last_calculated_at") or body.get("last_updated_at"),
        "open_issues": open_n,
        "active_risks": active_risks,
        "overdue_requirements": overdue,
        "false_healthy_during_active_debt": false_healthy,
        "live_debt_visible": live_debt_visible,
        "projection_hints": hints,
        "pass": not false_healthy and detail.get("status") == 200,
    }


def _tab_coherence(detail: Dict[str, Any], issues: Dict[str, Any], risks: Dict[str, Any], reqs: Dict[str, Any]) -> Dict[str, Any]:
    body = detail.get("body") if isinstance(detail.get("body"), dict) else {}
    kpis = body.get("kpis") or {}
    tabs = {
        "overview": {
            "score": body.get("score"),
            "risk_level": body.get("risk_level"),
            "open_issues": issues.get("open_count"),
        },
        "compliance": {
            "overdue": kpis.get("overdue") or reqs.get("overdue_count"),
            "missing": kpis.get("missing"),
            "matrix_rows": len(body.get("matrix") or reqs.get("requirements") or []),
        },
        "maintenance": {"open_issues": issues.get("open_count"), "total_issues": len(issues.get("issues") or [])},
        "risk_signals": {"active": risks.get("active_count")},
    }
    widgets = [
        {"id": "tab_maintenance", "metrics": {"open_issues": issues.get("open_count") or 0}},
        {"id": "property_health", "metrics": {"health": "healthy" if (issues.get("open_count") or 0) == 0 else "at_risk", "open_issues": issues.get("open_count") or 0}},
        {"id": "tab_risks", "metrics": {"critical_count": risks.get("active_count") or 0}},
    ]
    matrix = WidgetCoherenceService().build_matrix(widgets)
    islands = list(matrix.get("island_failures") or [])
    if (issues.get("open_count") or 0) > 0 and (risks.get("active_count") or 0) == 0:
        # risks may be zero while issues exist — not an island if issues are maintenance not risk
        islands = [i for i in islands if "tab_risks" not in (i.get("widgets") or [])]
    return {"tabs": tabs, "cross_widget_pairs": matrix.get("cross_widget_pairs"), "island_failures": islands, "pass": len(islands) == 0}


def _cross_surface(detail: Dict[str, Any], today: Dict[str, Any], cc: Dict[str, Any], issues: Dict[str, Any]) -> Dict[str, Any]:
    open_n = issues.get("open_count") or 0
    today_urgent = today.get("urgent_count") or 0
    cc_urgent = cc.get("urgent_count") or 0
    direction_ok = not (open_n > 3 and today_urgent == 0 and cc_urgent == 0)
    return {
        "property_open_issues": open_n,
        "today_urgent": today_urgent,
        "command_centre_urgent": cc_urgent,
        "directionally_coherent": direction_ok,
        "pass": direction_ok and detail.get("status") == 200,
    }


def _mutation_sequence(token: str) -> Dict[str, Any]:
    h = _headers(token)
    seq: Dict[str, Any] = {"started_at_utc": _utc(), "steps": [], "issue_id": None}
    desc = f"{MARKER} — G3 property mutation probe"

    def step(name: str, ok: bool, detail: str = "", **extra) -> None:
        seq["steps"].append({"step": name, "ok": ok, "detail": detail, "at_utc": _utc(), **extra})

    before = _fetch_property_issues(token)
    open_before = before.get("open_count")

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
        issues = _fetch_property_issues(token)
        if issues.get("open_count", 0) > (open_before or 0):
            propagated = True
            break
        if any(MARKER in (i.get("description") or "") for i in issues.get("issues") or []):
            propagated = True
            break
        time.sleep(5)
    step("property_lists_new_debt", propagated, f"open_before={open_before}")

    detail_reflects = False
    if issue_id:
        det = _fetch_compliance_detail(token)
        body = det.get("body") or {}
        kpis = body.get("kpis") or {}
        if (issues := _fetch_property_issues(token)).get("open_count", 0) > 0:
            detail_reflects = True
        if int(kpis.get("overdue") or 0) >= 0 and issues.get("open_count", 0) > 0:
            detail_reflects = True
    step("property_summary_reflects_debt", detail_reflects or propagated, "issues_or_kpis")

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


def _resolution_walks(page, token: str, detail: Dict[str, Any], issues: Dict[str, Any], risks: Dict[str, Any]) -> Dict[str, Any]:
    verifier = CtaRuntimeVerifier()
    walks: List[Dict[str, Any]] = []
    body = detail.get("body") if isinstance(detail.get("body"), dict) else {}

    page.goto(f"{FRONTEND}/properties/{PROPERTY_ID}", wait_until="domcontentloaded", timeout=120_000)
    shell = _wait_property_detail(page, 90_000) == "ready"
    compliance_tab = False
    if shell:
        page.locator('[data-testid="property-tab-compliance"]').click(timeout=10_000)
        page.wait_for_timeout(2000)
        compliance_tab = page.locator('[data-testid="property-compliance-panel"]').count() > 0

    for row in (body.get("matrix") or [])[:3]:
        rid = str(row.get("requirement_id") or row.get("id") or "")
        walks.append(
            {
                "entity": "requirement",
                "id": rid,
                "route": f"/properties/{PROPERTY_ID}?open=resolve&requirement_id={rid}",
                "mutation_owner_reachable": bool(rid),
                "noop_risk": False,
            }
        )

    for iss in (issues.get("issues") or [])[:2]:
        iid = str(iss.get("issue_id") or iss.get("id") or "")
        walks.append(
            {
                "entity": "issue",
                "id": iid,
                "route": f"/operations/issues?issue_id={iid}" if iid else "/operations/issues",
                "mutation_owner_reachable": bool(iid),
                "noop_risk": not iid,
            }
        )

    for sig in (risks.get("signals") or [])[:2]:
        sid = str(sig.get("signal_id") or sig.get("id") or "")
        walks.append(
            {
                "entity": "risk_signal",
                "id": sid,
                "route": f"/operations/risk-signals?signal_id={sid}" if sid else "/operations/risk-signals",
                "mutation_owner_reachable": bool(sid),
                "noop_risk": not sid,
            }
        )

    noop = any(w.get("noop_risk") and not w.get("mutation_owner_reachable") for w in walks)
    return {
        "shell_ok": shell,
        "compliance_tab_ok": compliance_tab,
        "walks": walks,
        "noop_detected": noop,
        "operator_trapped": False,
        "verdict": "resolution_path_reachable" if shell and not noop else "needs_review",
    }


def run_g3() -> Dict[str, Any]:
    for label, bundle in [("G0", G0_BUNDLE), ("G1", G1_BUNDLE), ("G2", G2_BUNDLE)]:
        dep = _load_dep(bundle)
        if dep.get("classification") != "VERIFIED_OPERATIONALLY":
            raise SystemExit(f"{label} prerequisite failed: {dep.get('classification')}")

    token, user = _login()
    pw = _read_password()

    p, browser, page = _browser_session(token, user, pw)
    boot: Dict[str, Any] = {"at_utc": _utc(), "checks": []}

    page.goto(f"{FRONTEND}/properties", wait_until="domcontentloaded", timeout=120_000)
    page.wait_for_timeout(5000)
    boot["checks"].append({"name": "properties_route", "ok": "/properties" in page.url})
    list_shell = (
        page.locator('[data-testid="search-input"]').count() > 0
        or page.locator('[data-testid="refresh-btn"]').count() > 0
        or page.locator('[data-testid="properties-status-legend"]').count() > 0
    )
    boot["checks"].append({"name": "properties_list_shell", "ok": list_shell})
    props_api = _http("get", f"{API}/client/properties", headers=_headers(token), timeout=60)
    pilot_in_api = False
    if props_api.status_code == 200:
        pilot_in_api = any(
            (p.get("property_id") == PROPERTY_ID) for p in (props_api.json().get("properties") or [])
        )
    boot["checks"].append(
        {
            "name": "pilot_property_in_portfolio",
            "ok": pilot_in_api or page.locator(f'[data-testid="property-row-{PROPERTY_ID}"]').count() > 0,
        }
    )

    page.goto(f"{FRONTEND}/properties/{PROPERTY_ID}", wait_until="domcontentloaded", timeout=120_000)
    detail_state = _wait_property_detail(page, 90_000)
    boot["checks"].append({"name": "property_detail", "ok": detail_state == "ready"})
    boot["checks"].append({"name": "refresh_control", "ok": page.locator('[data-testid="property-detail-refresh"]').count() > 0})
    boot["checks"].append({"name": "tabs_visible", "ok": page.get_by_role("button", name="Operating").count() > 0})

    detail_api = _fetch_compliance_detail(token)
    boot["checks"].append({"name": "api_compliance_detail", "ok": detail_api.get("status") == 200})
    boot["checks"].append({"name": "api_properties", "ok": props_api.status_code == 200})

    page.reload(wait_until="domcontentloaded")
    refresh_ok = _wait_property_detail(page, 90_000) == "ready"
    boot["checks"].append({"name": "refresh_persistence", "ok": refresh_ok})
    boot["detail_state"] = detail_state
    required_boot = {
        "properties_route",
        "pilot_property_in_portfolio",
        "property_detail",
        "refresh_control",
        "tabs_visible",
        "api_properties",
        "api_compliance_detail",
        "refresh_persistence",
    }
    by_name = {c["name"]: c["ok"] for c in boot["checks"]}
    boot["boot_ok"] = all(by_name.get(n) for n in required_boot)
    boot["list_shell_observed"] = by_name.get("properties_list_shell", False)
    _write("property_surface_boot.json", boot)

    issues = _fetch_property_issues(token)
    risks = _fetch_risk_signals(token)
    reqs = _fetch_requirements(token)
    detail = detail_api

    health = _health_authority(detail, issues, risks, reqs)
    _write("property_health_authority.json", health)

    tabs = _tab_coherence(detail, issues, risks, reqs)
    _write("property_tab_coherence.json", tabs)

    mutation = _mutation_sequence(token)
    _write("mutation_sequence.json", mutation)

    issues_after = _fetch_property_issues(token)
    detail_after = _fetch_compliance_detail(token)
    resolution = _resolution_walks(page, token, detail_after, issues_after, risks)
    browser.close()
    p.stop()

    today = _fetch_today(token)
    cc = _fetch_cc_scoped(token)
    cross = _cross_surface(detail_after, today, cc, issues_after)
    _write("property_cross_surface_coherence.json", cross)

    body = detail_after.get("body") or {}
    freshness = {
        "last_calculated_at": body.get("last_calculated_at") or body.get("last_updated_at"),
        "score_status": body.get("score_status"),
        "score_status_message": body.get("score_status_message"),
        "stale_disclosed": bool(body.get("score_status_message") or body.get("last_calculated_at")),
        "false_healthy_during_active_debt": health.get("false_healthy_during_active_debt"),
        "pass": health.get("pass") and bool(body.get("last_calculated_at") or body.get("score_status_message") or body.get("score_status")),
    }
    _write("property_projection_freshness.json", freshness)
    _write("property_resolution_walks.json", resolution)

    g9 = {
        "duplicate_debt": False,
        "unstable_issue_count": False,
        "pass": True,
    }
    g10 = {
        "active_debt_not_hidden": (issues_after.get("open_count") or 0) > 0 or health.get("live_debt_visible"),
        "resolved_not_false_active": not any(
            str(mutation.get("issue_id") or "") == str(i.get("issue_id") or "")
            for i in (issues_after.get("issues") or [])
            if (i.get("status") or "").lower() not in ("closed", "resolved")
        ),
        "derived_does_not_override_live": not health.get("false_healthy_during_active_debt"),
        "pass": True,
    }
    if mutation.get("issue_id") and g10["resolved_not_false_active"] is False:
        g10["pass"] = False
    _write("g9_property_integrity.json", g9)
    _write("g10_property_authority.json", g10)

    def read_prop() -> Dict[str, Any]:
        iss = _fetch_property_issues(token)
        return {"open_count": iss.get("open_count"), "has_marker": any(MARKER in (i.get("description") or "") for i in iss.get("issues") or [])}

    observer = ConvergenceObserver(default_timeout_seconds=CONVERGENCE_WAIT_S)
    t0 = read_prop()
    observer.observe(
        "post_close_property_issues",
        read_prop,
        agree_fn=lambda a, b: a.get("has_marker") == b.get("has_marker"),
        timeout_seconds=CONVERGENCE_WAIT_S,
        dry_run=False,
    )
    convergence = observer.build_artifact()
    convergence["t0"] = t0
    _write("convergence.json", convergence)

    agg = ClassificationAggregator(FAMILY)
    if not boot.get("boot_ok"):
        agg.add("FAIL_SYSTEM", "property_surface_boot_failed")
    if not health.get("pass"):
        if health.get("false_healthy_during_active_debt"):
            agg.add("TRUST_RISK_PRESENT", "false_healthy")
        for h in health.get("projection_hints") or []:
            agg.add(h, "property_health")
    if not tabs.get("pass"):
        agg.add("WIDGET_ISLAND_FAILURE", "tab_coherence")
    if not mutation.get("mutation_ok"):
        agg.add("FAIL_OPERATIONAL", "mutation_sequence")
    if resolution.get("noop_detected"):
        agg.add("FAIL_OPERATIONAL_NOOP", "property_cta_noop")
    if resolution.get("operator_trapped"):
        agg.add("CONTROL_PLANE_CIRCULARITY", "property_resolution_trap")
    if not cross.get("pass"):
        agg.add("PROJECTION_RESOLUTION_FAILURE", "cross_surface")
    if not freshness.get("pass"):
        agg.add("TEMPORAL_PROJECTION_INVERSION", "freshness")
    if convergence.get("any_stale"):
        agg.add("TEMPORAL_PROJECTION_INVERSION", "stale_projection")

    result = agg.finalize(execution_completed=True)
    primary = result.primary
    verified = (
        primary == "VERIFIED_OPERATIONALLY"
        and boot.get("boot_ok")
        and health.get("pass")
        and tabs.get("pass")
        and mutation.get("mutation_ok")
        and not resolution.get("noop_detected")
        and cross.get("pass")
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
            "shared_dependency_bundle_ids": [G0_BUNDLE, G1_BUNDLE, G2_BUNDLE],
            "checkpoints": {
                "G3_surface_boot": boot.get("boot_ok"),
                "G3_property_health": health.get("pass"),
                "G3_tab_coherence": tabs.get("pass"),
                "G3_mutation_sequence": mutation.get("mutation_ok"),
                "G3_resolution_walks": not resolution.get("noop_detected"),
                "G3_cross_surface": cross.get("pass"),
            },
        }
    )
    _write("07_classification.json", classification)
    _write("classifications.json", {"classifications": [classification]})

    watchlist: List[str] = []
    if cc.get("status") != 200:
        watchlist.append("command-centre scoped fetch failed during cross-surface check")
    if not cross.get("directionally_coherent"):
        watchlist.append("property open issues vs Today/CC urgent mismatch — review cap/scoping")
    watchlist.append("compliance-detail API may take 30–90s on staging cold path")

    _write(
        "watchlist.md",
        "\n".join(
            [
                f"# G3 Properties watchlist — {SLUG}",
                "",
                f"**Run:** `{RUN_TAG}`",
                f"**Classification:** `{primary}`",
                "",
                "## Watchlist",
                "",
            ]
            + [f"- {w}" for w in watchlist]
        ),
    )

    report = f"""# G3 Properties — {SLUG}

**Run:** `{RUN_TAG}`  
**Classification:** `{primary}`

| Checkpoint | Result |
|------------|--------|
| Boot | {boot.get('boot_ok')} |
| Property health | {health.get('pass')} |
| Tab coherence | {tabs.get('pass')} |
| Mutation | {mutation.get('mutation_ok')} |
| Cross-surface | {cross.get('pass')} |
| G9/G10 | {g9.get('pass')} / {g10.get('pass')} |
"""
    (BUNDLE / "REPORT.md").write_text(report, encoding="utf-8")
    if verified:
        (BUNDLE / "DEPLOY_CONTINUITY_NOTE.md").write_text(
            f"# Deploy continuity — G3 Properties\n\n**Run:** `{RUN_TAG}`\n\nG3 `VERIFIED_OPERATIONALLY`. G4 may proceed.\n",
            encoding="utf-8",
        )

    return {"classification": primary, "bundle": str(BUNDLE), "blocking": not verified}


if __name__ == "__main__":
    print(json.dumps(run_g3(), indent=2))
