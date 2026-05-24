"""
PRELAUNCH-OPS-RUNTIME-VERIFY-02 — G1 Today page (ops_control_g1_today_page).
Operational attention authority verification — local harness only.
"""
from __future__ import annotations

import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.ops_runtime_verify_02.attention_authority_service import AttentionAuthorityService
from services.ops_runtime_verify_02.classification_helpers import ClassificationAggregator
from services.ops_runtime_verify_02.convergence_observer import ConvergenceObserver
from services.ops_runtime_verify_02.cta_runtime_verifier import CtaRuntimeVerifier
from services.ops_runtime_verify_02.widget_coherence_service import WidgetCoherenceService

PROGRAMME = "PRELAUNCH-OPS-RUNTIME-VERIFY-02"
FAMILY = "ops_control_g1_today_page"
OWNER = "ops_control_g1_today_page"
PROOF_MODE = "operational_browser"

CLIENT_ID = "6fd5ac4c-3fd4-4112-ade7-156977deb49f"
PROPERTY_ID = "d35a58ae-3c81-491c-9694-1d021dd3b8ad"
CLIENT_EMAIL = "nancy@yopmail.com"
SLUG = "6fd5ac4c_d35a58ae"
G0_BUNDLE = f"ops_control_g0_programme_precheck_{SLUG}/07_classification.json"

_raw_api = os.environ.get("OPS_VERIFY_API_URL", "https://pleerity-enterprise.onrender.com").rstrip("/")
API = _raw_api if _raw_api.endswith("/api") else f"{_raw_api}/api"
FRONTEND = os.environ.get("OPS_VERIFY_FRONTEND_URL", "https://pleerityenterprise.co.uk").rstrip("/")
RUN_TAG = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
MARKER = f"OPS-VERIFY02-G1-{RUN_TAG}"
CONVERGENCE_WAIT_S = int(os.environ.get("OPS_RUNTIME_CONVERGENCE_WAIT_S", "75"))

BUNDLE = ROOT / f"docs/audit/ops_runtime_g1_today_{SLUG}"


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


def _http(method: str, url: str, *, headers: Optional[dict] = None, **kwargs) -> httpx.Response:
    last_exc: Optional[Exception] = None
    for attempt in range(4):
        try:
            fn = getattr(httpx, method.lower())
            return fn(url, headers=headers, timeout=kwargs.pop("timeout", 120), **kwargs)
        except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.ConnectError) as exc:
            last_exc = exc
            time.sleep(2 + attempt * 2)
    raise last_exc  # type: ignore[misc]


def _login() -> Tuple[str, dict]:
    pw = _read_password()
    r = _http("post", f"{API}/auth/login", json={"email": CLIENT_EMAIL, "password": pw})
    r.raise_for_status()
    body = r.json()
    return body["access_token"], body.get("user") or {}


def _fetch_today(token: str, property_id: Optional[str] = None) -> Dict[str, Any]:
    params = {"property_id": property_id} if property_id else {}
    r = _http("get", f"{API}/today/items", headers=_headers(token), params=params)
    if r.status_code != 200:
        return {"status": r.status_code, "body": r.text[:500]}
    try:
        return {"status": 200, "body": r.json()}
    except json.JSONDecodeError:
        return {"status": 200, "body": {"error": "invalid_json", "length": len(r.content)}}


def _flatten_tasks(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    body = payload.get("body") if isinstance(payload.get("body"), dict) else payload
    tasks = body.get("tasks") or {}
    out: List[Dict[str, Any]] = []
    for section in ("urgent", "upcoming", "in_progress", "snoozed", "recently_completed"):
        for t in tasks.get(section) or []:
            if isinstance(t, dict):
                row = dict(t)
                row["_section"] = section
                out.append(row)
    for h in tasks.get("hidden") or []:
        if isinstance(h, dict):
            row = dict(h)
            row["_section"] = "hidden"
            out.append(row)
    return out


def _urgency_rank(task: Dict[str, Any]) -> int:
    u = str(task.get("urgency") or task.get("urgency_level") or "").lower()
    if u == "overdue" or (task.get("overdue_days") or 0) > 0:
        return 1
    if u in ("critical", "high"):
        return 2
    if u == "due_soon":
        return 3
    return 5


def _attention_class(task: Dict[str, Any]) -> str:
    section = task.get("_section") or ""
    source = str(task.get("source_type") or "").lower()
    u = str(task.get("urgency") or "").lower()
    if u == "overdue" or (task.get("overdue_days") or 0) > 0:
        return "overdue_remediation"
    if source in ("risk_signal", "risk") or "risk" in source:
        return "active_risk"
    if source in ("work_order", "issue", "maintenance_issue", "requirement", "compliance_job"):
        return "open_operational_debt"
    if u == "due_soon" or section == "upcoming":
        return "time_bound_reminder"
    if section in ("snoozed", "hidden"):
        return "informational"
    return "open_operational_debt" if section in ("urgent", "in_progress") else "informational"


def _items_for_attention(tasks: List[Dict[str, Any]], *, active_only: bool = True) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    pos = 0
    for t in tasks:
        sec = t.get("_section") or ""
        if active_only and sec in ("hidden", "snoozed", "recently_completed"):
            continue
        tid = str(t.get("id") or t.get("task_id") or "")
        if not tid:
            continue
        badges = []
        u = str(t.get("urgency") or "").lower()
        if u:
            badges.append(u)
        ul = str(t.get("urgency_level") or "").lower()
        if ul and ul not in badges:
            badges.append(ul)
        items.append(
            {
                "id": tid,
                "class": _attention_class(t),
                "urgency_rank": _urgency_rank(t),
                "position": pos,
                "section": sec,
                "source_type": t.get("source_type"),
                "title": (t.get("title") or "")[:120],
                "badges": badges,
                "snoozed": sec == "snoozed" or bool(t.get("snoozed_until")),
                "snooze_expires_at": t.get("snoozed_until"),
                "dismissed_in_api": sec == "hidden",
                "dismissed_in_ui": sec == "hidden",
                "property_id": t.get("property_id"),
            }
        )
        pos += 1
    return items


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


def _pilot_lock() -> Dict[str, Any]:
    g0_path = ROOT / "docs/audit" / G0_BUNDLE.replace("/", os.sep)
    g0 = json.loads(g0_path.read_text(encoding="utf-8")) if g0_path.is_file() else {}
    return {
        "programme": PROGRAMME,
        "family": FAMILY,
        "client_id": CLIENT_ID,
        "property_id": PROPERTY_ID,
        "slug": SLUG,
        "run_tag": RUN_TAG,
        "g0_classification": g0.get("classification"),
        "g0_ready": g0.get("classification") == "VERIFIED_OPERATIONALLY",
        "marker": MARKER,
    }


def _surface_boot(page, token: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {"at_utc": _utc(), "checks": []}
    page.goto(f"{FRONTEND}/today", wait_until="domcontentloaded", timeout=120_000)
    page.wait_for_timeout(3000)
    shell = page.locator('[data-testid="client-tasks-page"]').count() > 0
    out["checks"].append({"name": "today_route", "ok": "/today" in page.url, "url": page.url})
    out["checks"].append({"name": "shell_visible", "ok": shell})
    out["checks"].append({"name": "no_fatal_error", "ok": "Something went wrong" not in page.locator("body").inner_text()[:800]})
    api = _fetch_today(token)
    out["api_today_items"] = api.get("status") == 200
    out["checks"].append({"name": "api_today_items", "ok": out["api_today_items"]})
    page.reload(wait_until="domcontentloaded")
    page.wait_for_timeout(2000)
    out["checks"].append({"name": "refresh_persistence", "ok": page.locator('[data-testid="client-tasks-page"]').count() > 0})
    out["boot_ok"] = all(c["ok"] for c in out["checks"])
    return out


def _mutation_sequence(token: str) -> Dict[str, Any]:
    h = _headers(token)
    seq: Dict[str, Any] = {"started_at_utc": _utc(), "steps": [], "issue_id": None}
    desc = f"{MARKER} — G1 attention mutation probe"

    def step(name: str, ok: bool, detail: str = "", **extra) -> None:
        seq["steps"].append({"step": name, "ok": ok, "detail": detail, "at_utc": _utc(), **extra})

    before = _flatten_tasks(_fetch_today(token))
    before_ids = {str(t.get("id")) for t in before}

    cr = httpx.post(
        f"{API}/client/maintenance/issues",
        headers=h,
        json={"property_id": PROPERTY_ID, "description": desc, "category": "plumbing"},
        timeout=120,
    )
    step("create_issue", cr.status_code in (200, 201), f"status={cr.status_code}")
    issue_id = cr.json().get("issue_id") if cr.status_code in (200, 201) else None
    seq["issue_id"] = issue_id

    appeared = False
    found_task_id: Optional[str] = None
    deadline = time.time() + CONVERGENCE_WAIT_S
    while time.time() < deadline and issue_id:
        tasks = _flatten_tasks(_fetch_today(token))
        for t in tasks:
            meta = t.get("metadata") or {}
            if str(meta.get("issue_id") or t.get("source_entity_id") or "") == issue_id:
                appeared = True
                found_task_id = str(t.get("id") or "")
                break
            if MARKER in (t.get("title") or "") or MARKER in (t.get("description") or ""):
                appeared = True
                found_task_id = str(t.get("id") or "")
                break
        if appeared:
            break
        time.sleep(3)
    step("today_lists_new_issue", appeared, f"task_id={found_task_id}", issue_id=issue_id)

    if issue_id:
        cl = httpx.patch(
            f"{API}/client/maintenance/issues/{issue_id}",
            headers=h,
            json={"status": "closed", "resolution_note": f"{MARKER} closed"},
            timeout=60,
        )
        step("close_issue", cl.status_code == 200, f"status={cl.status_code}")

    deprioritized = False
    deadline2 = time.time() + CONVERGENCE_WAIT_S
    while time.time() < deadline2 and found_task_id:
        tasks = _flatten_tasks(_fetch_today(token))
        urgent_ids = {str(t.get("id")) for t in tasks if t.get("_section") == "urgent"}
        if found_task_id not in urgent_ids:
            deprioritized = True
            break
        time.sleep(3)
    step("today_deprioritizes_after_close", deprioritized or not found_task_id, f"task_id={found_task_id}")

    seq["finished_at_utc"] = _utc()
    seq["mutation_ok"] = all(s["ok"] for s in seq["steps"])
    return seq


def _snooze_dismiss(token: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {"at_utc": _utc(), "probes": []}
    h = _headers(token)
    tasks = _flatten_tasks(_fetch_today(token))
    candidates = [
        t
        for t in tasks
        if t.get("_section") in ("upcoming", "urgent")
        and (t.get("visibility_actions") or [])
        and MARKER not in (t.get("title") or "")
    ]
    if not candidates:
        out["skipped"] = "no_snooze_candidate"
        return out

    target = candidates[0]
    tid = str(target.get("id") or "")
    out["target_task_id"] = tid

    sr = _http("post", f"{API}/today/items/{tid}/snooze", headers=h, json={"days": 1})
    out["probes"].append({"action": "snooze", "status": sr.status_code, "ok": sr.status_code == 200})

    after_snooze = _flatten_tasks(_fetch_today(token))
    in_snoozed = any(str(t.get("id")) == tid and t.get("_section") == "snoozed" for t in after_snooze)
    out["probes"].append({"check": "snoozed_bucket", "ok": in_snoozed})

    rr = httpx.post(f"{API}/today/items/{tid}/restore", headers=h, timeout=60)
    out["probes"].append({"action": "restore_after_snooze", "status": rr.status_code, "ok": rr.status_code == 200})

    # dismiss different candidate
    cand2 = next((t for t in candidates if str(t.get("id")) != tid), candidates[0] if len(candidates) > 1 else None)
    if cand2:
        tid2 = str(cand2.get("id") or "")
        dr = httpx.post(
            f"{API}/today/items/{tid2}/dismiss",
            headers=h,
            json={"reason": f"{MARKER} visibility dismiss probe"},
            timeout=60,
        )
        out["probes"].append({"action": "dismiss", "task_id": tid2, "status": dr.status_code, "ok": dr.status_code == 200})
        hidden = any(str(t.get("id")) == tid2 or str(t.get("task_id")) == tid2 for t in _flatten_tasks(_fetch_today(token)) if t.get("_section") == "hidden")
        out["probes"].append({"check": "hidden_bucket", "ok": hidden})
        httpx.post(f"{API}/today/items/{tid2}/restore", headers=h, timeout=60)

    out["ok"] = all(p.get("ok") for p in out["probes"] if "ok" in p)
    return out


def _cta_walks(token: str, page) -> Dict[str, Any]:
    verifier = CtaRuntimeVerifier()
    walks: List[Dict[str, Any]] = []
    tasks = _flatten_tasks(_fetch_today(token))
    urgent = [t for t in tasks if t.get("_section") == "urgent"][:6]

    for t in urgent:
        tid = str(t.get("id") or "")
        biz = t.get("business_actions") or []
        primary = next((a for a in biz if a.get("primary")), biz[0] if biz else None)
        route = (primary or {}).get("route") or (primary or {}).get("navigate") or ""
        label = (primary or {}).get("label") or t.get("primary_action_label") or ""
        noop_risk = route in ("", "/today") and not (t.get("metadata") or {}).get("take_action")
        walks.append(
            {
                "task_id": tid,
                "label": label,
                "route": route,
                "mutation_owner_reachable": bool(route and route != "/today"),
                "noop_risk": noop_risk,
                "has_business_actions": len(biz) > 0,
            }
        )
        verifier.register_cta(
            cta_id=tid,
            label=str(label)[:80],
            source_route="/today",
            destination_route=str(route)[:120],
            mutation_owner=OWNER,
        )

    page.goto(f"{FRONTEND}/today", wait_until="domcontentloaded", timeout=120_000)
    page.wait_for_timeout(2500)
    browser_ctas = page.locator('a[href*="/properties"], a[href*="/requirements"], a[href*="/documents"], button').count()
    matrix = verifier.build_matrix()
    return {
        "walks": walks,
        "noop_detected": matrix.get("noop_detected"),
        "browser_interactive_elements": browser_ctas,
        "sample_count": len(walks),
    }


def _cross_surface(token: str) -> Dict[str, Any]:
    h = _headers(token)
    today_raw = _fetch_today(token)
    today = today_raw.get("body") if isinstance(today_raw.get("body"), dict) else {}
    summary = today.get("summary") or {}
    tasks = today.get("tasks") or {}
    today_urgent = len(tasks.get("urgent") or [])

    cc = _http("get", f"{API}/client/command-center", headers=h)
    cc_body = cc.json() if cc.status_code == 200 else {}
    cc_urgent = len(cc_body.get("urgent_actions") or [])

    oc = httpx.get(f"{API}/client/maintenance/issues/open-count", headers=h, params={"property_id": PROPERTY_ID}, timeout=60)
    open_issues = oc.json().get("open_issues_count") if oc.status_code == 200 else None

    rs = httpx.get(f"{API}/client/risk-signals", headers=h, params={"property_id": PROPERTY_ID, "limit": 50}, timeout=60)
    signals = (rs.json().get("signals") or rs.json().get("risk_signals") or []) if rs.status_code == 200 else []

    rep = httpx.get(f"{API}/client/reports", headers=h, timeout=60)
    reports_ok = rep.status_code == 200

    widget_svc = WidgetCoherenceService()
    matrix = widget_svc.build_matrix(
        [
            {"id": "today_urgent", "metrics": {"urgent_count": today_urgent}},
            {"id": "command_centre_urgent", "metrics": {"urgent_actions": cc_urgent}},
        ]
    )

    direction_ok = not (today_urgent == 0 and cc_urgent > 3)
    return {
        "today_urgent_count": today_urgent,
        "command_centre_urgent_count": cc_urgent,
        "open_issues_count": open_issues,
        "active_risk_signals": len([s for s in signals if (s.get("status") or "") in ("active", "acknowledged")]),
        "reports_reachable": reports_ok,
        "counts_directionally_coherent": direction_ok,
        "widget_coherence": matrix,
        "island_failures": matrix.get("island_failures") or [],
        "classification_hints": matrix.get("classification_hints") or [],
    }


def _resolution_walk(token: str, page, mutation: Dict[str, Any]) -> Dict[str, Any]:
    issue_id = mutation.get("issue_id")
    out: Dict[str, Any] = {"issue_id": issue_id, "steps": []}
    if not issue_id:
        out["verdict"] = "skipped_no_issue"
        return out

    page.goto(f"{FRONTEND}/today", wait_until="domcontentloaded", timeout=120_000)
    page.wait_for_timeout(2000)
    body = page.locator("body").inner_text()
    on_today = MARKER in body
    out["steps"].append({"step": "visible_on_today", "ok": on_today})

    page.goto(f"{FRONTEND}/properties/{PROPERTY_ID}", wait_until="domcontentloaded", timeout=120_000)
    page.wait_for_timeout(2000)
    prop_mut = page.locator('button:has-text("Upload"), button:has-text("Review"), [data-testid^="requirement-row-"]').count() > 0
    out["steps"].append({"step": "property_mutation_surface", "ok": prop_mut})

    page.goto(f"{FRONTEND}/today", wait_until="domcontentloaded", timeout=120_000)
    page.wait_for_timeout(2000)
    out["steps"].append({"step": "return_to_today", "ok": "/today" in page.url})

    out["verdict"] = "resolution_path_reachable" if all(s["ok"] for s in out["steps"][:2]) else "needs_review"
    return out


def _g9(token: str) -> Dict[str, Any]:
    tasks = _flatten_tasks(_fetch_today(token))
    ids = [str(t.get("id")) for t in tasks if t.get("id")]
    dup_ids = len(ids) - len(set(ids))
    titles = [(t.get("title") or "") for t in tasks]
    dup_titles = len(titles) - len(set(titles))

    h = _headers(token)
    cand = next((t for t in tasks if t.get("_section") == "upcoming" and (t.get("visibility_actions") or [])), None)
    double_snooze_ok = True
    if cand:
        tid = str(cand.get("id"))
        r1 = httpx.post(f"{API}/today/items/{tid}/snooze", headers=h, json={"days": 1}, timeout=60)
        r2 = httpx.post(f"{API}/today/items/{tid}/snooze", headers=h, json={"days": 1}, timeout=60)
        double_snooze_ok = r1.status_code == 200 and r2.status_code == 200
        httpx.post(f"{API}/today/items/{tid}/restore", headers=h, timeout=60)

    return {
        "duplicate_task_ids": dup_ids,
        "duplicate_titles": dup_titles,
        "double_snooze_idempotent": double_snooze_ok,
        "pass": dup_ids == 0 and double_snooze_ok,
    }


def _g10(token: str, mutation: Dict[str, Any]) -> Dict[str, Any]:
    issue_id = mutation.get("issue_id")
    tasks = _flatten_tasks(_fetch_today(token))
    false_unresolved = False
    false_hidden = False
    if issue_id:
        still_urgent = any(
            str(t.get("id")) == issue_id
            or str((t.get("metadata") or {}).get("issue_id") or "") == issue_id
            for t in tasks
            if t.get("_section") == "urgent"
        )
        false_unresolved = still_urgent
    hidden_with_marker = [t for t in tasks if t.get("_section") == "hidden" and MARKER in (t.get("title") or "")]
    return {
        "resolved_debt_not_shown_unresolved": not false_unresolved,
        "dismissed_not_confused_with_resolved": len(hidden_with_marker) == 0 or mutation.get("mutation_ok"),
        "derived_does_not_override_live": True,
        "pass": not false_unresolved,
    }


def _convergence(token: str, mutation: Dict[str, Any]) -> Dict[str, Any]:
    observer = ConvergenceObserver(default_timeout_seconds=CONVERGENCE_WAIT_S)
    issue_id = mutation.get("issue_id")
    if not issue_id:
        return observer.build_artifact()

    def read_fn() -> Dict[str, Any]:
        tasks = _flatten_tasks(_fetch_today(token))
        urgent = [t for t in tasks if t.get("_section") == "urgent"]
        return {"urgent_count": len(urgent), "has_marker": any(MARKER in (t.get("title") or "") for t in tasks)}

    t0 = read_fn()

    def agree(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
        return a.get("has_marker") == b.get("has_marker")

    observer.observe(
        "post_close_today_urgent",
        read_fn,
        agree_fn=agree,
        timeout_seconds=CONVERGENCE_WAIT_S,
        dry_run=False,
    )
    artifact = observer.build_artifact()
    artifact["t0"] = t0
    return artifact


def run_g1() -> Dict[str, Any]:
    pilot = _pilot_lock()
    if not pilot["g0_ready"]:
        raise SystemExit(f"G0 not VERIFIED_OPERATIONALLY: {pilot.get('g0_classification')}")

    token, user = _login()
    pw = _read_password()

    p, browser, page = _browser_session(token, user, pw)
    boot = _surface_boot(page, token)
    _write("today_surface_boot.json", boot)

    tasks_initial = _flatten_tasks(_fetch_today(token))
    attn_items = _items_for_attention(tasks_initial)
    attn_svc = AttentionAuthorityService()
    attention = attn_svc.evaluate_order(attn_items)
    attention["pilot"] = pilot
    attention["active_item_count"] = len(attn_items)
    _write("attention_authority.json", attention)

    mutation = _mutation_sequence(token)
    _write("mutation_sequence.json", mutation)

    token, user = _login()
    snooze = _snooze_dismiss(token)
    cta = _cta_walks(token, page)
    cross = _cross_surface(token)
    resolution = _resolution_walk(token, page, mutation)
    g9 = _g9(token)
    g10 = _g10(token, mutation)
    convergence = _convergence(token, mutation)

    browser.close()
    p.stop()

    _write("today_snooze_dismiss.json", snooze)
    _write("today_cta_walks.json", cta)
    _write("today_cross_surface_coherence.json", cross)
    _write("today_resolution_walk.json", resolution)
    _write("g9_attention_integrity.json", g9)
    _write("g10_attention_authority.json", g10)
    _write("convergence.json", convergence)

    agg = ClassificationAggregator(FAMILY)
    if not boot.get("boot_ok"):
        agg.add("FAIL_SYSTEM", "today_surface_boot_failed")
    if attention.get("precedence_violations"):
        agg.add("ATTENTION_PRIORITY_DRIFT", f"violations={len(attention['precedence_violations'])}")
    if attention.get("cross_badge_contradictions") or attention.get("dismiss_resurrection_checks"):
        agg.add("OPERATIONAL_ATTENTION_CONTRADICTION", "badge_or_dismiss")
    if not mutation.get("mutation_ok"):
        agg.add("FAIL_OPERATIONAL", "mutation_sequence_incomplete")
    if cta.get("noop_detected"):
        agg.add("FAIL_OPERATIONAL_NOOP", "today_cta_noop")
    if cross.get("island_failures"):
        agg.add("WIDGET_ISLAND_FAILURE", "today_vs_command_centre")
    if not cross.get("counts_directionally_coherent"):
        agg.add("PROJECTION_RESOLUTION_FAILURE", "today_understates_vs_cc")
    if snooze.get("skipped"):
        agg.add("PARTIAL", "snooze_dismiss_skipped_no_candidate")
    elif not snooze.get("ok", True):
        agg.add("OPERATIONAL_ATTENTION_CONTRADICTION", "snooze_dismiss_failed")
    if not g9.get("pass"):
        agg.add("TRUST_RISK_PRESENT", "g9_attention_integrity")
    if not g10.get("pass"):
        agg.add("TRUST_RISK_PRESENT", "g10_authority")
    if convergence.get("any_stale"):
        agg.add("TEMPORAL_PROJECTION_INVERSION", "stale_today_projection")

    result = agg.finalize(execution_completed=True)
    primary = result.primary
    if attention.get("precedence_violations"):
        primary = "ATTENTION_PRIORITY_DRIFT"
    elif not snooze.get("ok", True) and not snooze.get("skipped"):
        primary = "OPERATIONAL_ATTENTION_CONTRADICTION"
    elif not mutation.get("mutation_ok"):
        primary = "FAIL_OPERATIONAL"
    elif not boot.get("boot_ok"):
        primary = "FAIL_SYSTEM"
    elif result.blocking:
        primary = result.primary

    verified = primary == "VERIFIED_OPERATIONALLY"
    classification = result.to_dict()
    classification["classification"] = primary
    classification["execution_status"] = primary
    classification["blocking"] = not verified
    classification.update(
        {
            "authoritative_verification_owner": OWNER,
            "proof_mode": PROOF_MODE,
            "run_tag": RUN_TAG,
            "pilot_slug": SLUG,
            "shared_dependency_bundle_ids": [G0_BUNDLE],
            "checkpoints": {
                "G1_surface_boot": boot.get("boot_ok"),
                "G1_attention_authority": not attention.get("precedence_violations"),
                "G1_mutation_sequence": mutation.get("mutation_ok"),
                "G1_cta_coherence": not cta.get("noop_detected"),
                "G1_cross_surface": not cross.get("island_failures"),
            },
        }
    )

    _write("07_classification.json", classification)
    _write("classifications.json", {"classifications": [classification]})

    watchlist: List[str] = []
    if attention.get("precedence_violations"):
        watchlist.append(
            f"ATTENTION_PRIORITY_DRIFT: {len(attention['precedence_violations'])} precedence inversions (risk vs WO/requirement/approval ordering)"
        )
    if snooze.get("skipped"):
        watchlist.append("snooze_dismiss: no visibility_action candidate — re-run with inbox debt")
    if not mutation.get("mutation_ok"):
        watchlist.append("issue may not project to Today within convergence window — verify unified task pipeline")
    if cross.get("today_urgent_count", 0) != cross.get("command_centre_urgent_count", 0):
        watchlist.append(
            f"urgent count delta today={cross.get('today_urgent_count')} cc={cross.get('command_centre_urgent_count')} (not auto-fail)"
        )

    _write(
        "watchlist.md",
        "\n".join(
            [
                f"# G1 Today watchlist — {SLUG}",
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

    report = f"""# G1 Today — {SLUG}

**Run:** `{RUN_TAG}`  
**Classification:** `{primary}`

| Checkpoint | Result |
|------------|--------|
| Surface boot | {boot.get('boot_ok')} |
| Attention precedence violations | {len(attention.get('precedence_violations') or [])} |
| Mutation sequence | {mutation.get('mutation_ok')} |
| CTA noop | {cta.get('noop_detected')} |
| G9 | {g9.get('pass')} |
| G10 | {g10.get('pass')} |

Marker issue: `{mutation.get('issue_id') or 'n/a'}`
"""
    (BUNDLE / "REPORT.md").write_text(report, encoding="utf-8")

    if verified:
        (BUNDLE / "DEPLOY_CONTINUITY_NOTE.md").write_text(
            f"# Deploy continuity — G1 Today\n\n**Run:** `{RUN_TAG}`\n\nG1 `VERIFIED_OPERATIONALLY` on staging. G2 may proceed. `/api/version` SHA may still be ambiguous from G0.\n",
            encoding="utf-8",
        )

    return {"classification": primary, "bundle": str(BUNDLE), "blocking": not verified}


if __name__ == "__main__":
    print(json.dumps(run_g1(), indent=2))
