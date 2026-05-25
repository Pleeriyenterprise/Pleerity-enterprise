#!/usr/bin/env python3
"""
RENT-TENANCY-AUTHORITY-RUNTIME-VERIFY-01 — full operational browser + API verification.
VERIFY-02 discipline: staging only, no fabricated results.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None  # type: ignore

ROOT = Path(__file__).resolve().parent
BUNDLE = ROOT / "docs/audit/rent_operations_tenancy_authority_runtime_fix"
_raw_api = os.environ.get("OPS_VERIFY_API_URL", "https://pleerity-enterprise.onrender.com").rstrip("/")
API = _raw_api if _raw_api.endswith("/api") else f"{_raw_api}/api"
FRONTEND = os.environ.get("OPS_VERIFY_FRONTEND_URL", "https://pleerityenterprise.co.uk").rstrip("/")
EMAIL = os.environ.get("OPS_VERIFY_EMAIL", "nancy@yopmail.com")
PW_FILE = ROOT / "docs/audit/ops_verify_01_6fd5ac4c_d35a58ae/.ops_verify_temp_pw.txt"
PILOT_PROPERTY_A = os.environ.get(
    "OPS_VERIFY_PROPERTY_A", "d35a58ae-3c81-491c-9694-1d021dd3b8ad"
)
PILOT_PROPERTY_B = os.environ.get(
    "OPS_VERIFY_PROPERTY_B", "0a5b4497-a1ba-4ee9-87e1-ae2bb9d4cc68"
)
EXPECTED_COMMITS = ["a3599669", "10a510e0", "425087f0"]
RUN_TAG = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
MARKER = f"RTA-VERIFY-{RUN_TAG}"

DEPLOY_MARKERS = [
    "rent-schedule-preview",
    "rent-schedule-tenancy",
    "payment-authority-context",
    "Enable rent tracking",
    "idempotency_key",
    "is_external_payer",
    "getRentTenancies",
    "previewRentSchedule",
    "operations/rent/tenancies",
]

CONVERGENCE_WAIT_S = int(os.environ.get("OPS_RUNTIME_CONVERGENCE_WAIT_S", "45"))
API_PACE_S = float(os.environ.get("OPS_API_PACE_S", "2.0"))


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write(name: str, data: Any) -> None:
    BUNDLE.mkdir(parents=True, exist_ok=True)
    (BUNDLE / name).write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


def _pace() -> None:
    time.sleep(API_PACE_S)


def _http(method: str, url: str, *, retries: int = 5, **kwargs) -> httpx.Response:
    last_exc: Optional[Exception] = None
    for attempt in range(retries):
        _pace()
        try:
            return getattr(httpx, method)(url, timeout=kwargs.pop("timeout", 120), **kwargs)
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.RemoteProtocolError) as exc:
            last_exc = exc
            time.sleep(min(2 ** attempt, 20))
    if last_exc:
        raise last_exc
    raise RuntimeError(f"http_failed:{method}:{url}")


class Auth:
    def __init__(self) -> None:
        self.token = ""
        self.user: dict = {}

    def login(self) -> None:
        pw = os.environ.get("OPS_VERIFY_PASSWORD") or PW_FILE.read_text(encoding="utf-8").strip()
        r = _http("post", f"{API}/auth/login", json={"email": EMAIL, "password": pw}, timeout=120)
        if r.status_code != 200:
            raise RuntimeError(f"login_failed:{r.status_code}:{r.text[:200]}")
        body = r.json()
        self.token = body["access_token"]
        self.user = body.get("user") or {}

    def h(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"}


def verify_deploy() -> dict[str, Any]:
    out: dict[str, Any] = {
        "verified_at_utc": _utc(),
        "programme": "RENT-TENANCY-AUTHORITY-RUNTIME-VERIFY-01",
        "expected_commits": EXPECTED_COMMITS,
        "frontend_url": FRONTEND,
        "classification": None,
    }
    try:
        r = httpx.get(FRONTEND, timeout=45, follow_redirects=True)
        out["frontend_status"] = r.status_code
        html = r.text
    except Exception as exc:
        out["frontend_status"] = "error"
        out["error"] = str(exc)[:300]
        out["deploy_ready"] = False
        out["classification"] = "DEPLOY_CONTINUITY_FAILURE"
        return out

    scripts = re.findall(r'src="(/static/js/[^"]+\.js)"', html)
    marker_hits: dict[str, list[str]] = {m: [] for m in DEPLOY_MARKERS}
    chunks_checked: list[str] = []
    for rel in scripts[:12]:
        try:
            js = httpx.get(f"{FRONTEND}{rel}", timeout=60).text
            chunks_checked.append(rel)
            for m in DEPLOY_MARKERS:
                if m in js:
                    marker_hits[m].append(rel)
        except Exception:
            continue

    out["chunks_checked"] = chunks_checked
    out["marker_hits"] = {k: v for k, v in marker_hits.items() if v}
    hits = sum(1 for v in marker_hits.values() if v)
    out["markers_found_count"] = hits
    required = ["rent-schedule-preview", "payment-authority-context", "Enable rent tracking"]
    out["required_markers_present"] = {m: bool(marker_hits.get(m)) for m in required}
    out["deploy_ready"] = hits >= 5 and all(out["required_markers_present"].values())

    try:
        origin = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(ROOT.parent),
            text=True,
        ).strip()
        out["local_head"] = origin
    except Exception as exc:
        out["local_head_error"] = str(exc)[:120]

    ver = httpx.get(f"{API.replace('/api', '')}/api/version", timeout=30)
    out["api_version"] = ver.json() if ver.status_code == 200 else {"status": ver.status_code}

    if not out["deploy_ready"]:
        out["classification"] = "DEPLOY_CONTINUITY_FAILURE"
    return out


def _list_properties(auth: Auth) -> Tuple[List[dict], dict]:
    """Return (properties, probe) for audit honesty."""
    probe: dict[str, Any] = {"status": None, "count": 0, "error": None}
    try:
        r = _http("get", f"{API}/client/properties", headers=auth.h(), timeout=90)
        probe["status"] = r.status_code
        if r.status_code != 200:
            probe["error"] = r.text[:300]
            return [], probe
        data = r.json()
        props = data.get("properties") or (data if isinstance(data, list) else [])
        probe["count"] = len(props)
        return props, probe
    except Exception as exc:
        probe["error"] = str(exc)[:300]
        return [], probe


def _create_tenancy(auth: Auth, property_id: str, *, rent_tracking: bool = True) -> dict:
    r = _http(
        "post",
        f"{API}/client/operations/rent/tenancies",
        headers=auth.h(),
        json={"property_id": property_id, "rent_tracking_enabled": rent_tracking},
        timeout=90,
    )
    return {"status": r.status_code, "body": r.json() if r.status_code in (200, 201) else r.text[:300]}


def _preview_schedule(auth: Auth, property_id: str, amount_minor: int = 120000) -> dict:
    start = date.today().replace(day=1).isoformat()
    r = _http(
        "post",
        f"{API}/client/operations/rent/schedules/preview",
        headers=auth.h(),
        json={
            "property_id": property_id,
            "expected_amount_minor": amount_minor,
            "due_day": 1,
            "start_date": start,
            "rent_frequency": "monthly",
        },
        timeout=90,
    )
    return {"status": r.status_code, "body": r.json() if r.status_code == 200 else r.text[:300]}


def _create_schedule(
    auth: Auth,
    property_id: str,
    tenancy_id: str,
    *,
    idempotency_key: Optional[str] = None,
    external: bool = False,
    external_name: str = "",
) -> dict:
    start = date.today().replace(day=1).isoformat()
    body: dict = {
        "property_id": property_id,
        "expected_amount_minor": 125000,
        "due_day": 1,
        "start_date": start,
        "rent_frequency": "monthly",
        "tenant_name": f"{MARKER} Tenant",
    }
    if external:
        body["is_external_payer"] = True
        body["external_payer_name"] = external_name or f"{MARKER} Council"
    else:
        body["tenancy_id"] = tenancy_id
    if idempotency_key:
        body["idempotency_key"] = idempotency_key
    r = _http("post", f"{API}/client/operations/rent/schedules", headers=auth.h(), json=body, timeout=180)
    return {"status": r.status_code, "body": r.json() if r.status_code in (200, 201) else r.text[:400]}


def _list_ledgers(auth: Auth, *, property_id: Optional[str] = None, tenancy_id: Optional[str] = None) -> List[dict]:
    params: dict = {"limit": 200}
    if property_id:
        params["property_id"] = property_id
    if tenancy_id:
        params["tenancy_id"] = tenancy_id
    r = _http("get", f"{API}/client/operations/rent/ledgers", headers=auth.h(), params=params, timeout=90)
    if r.status_code != 200:
        return []
    return r.json().get("ledgers") or []


def _payable_ledger(ledgers: List[dict]) -> Optional[dict]:
    for L in sorted(ledgers, key=lambda x: x.get("due_date") or ""):
        if int(L.get("outstanding_balance_minor") or 0) > 0 and (L.get("status") or "") not in ("PAID", "WAIVED"):
            return L
    return ledgers[0] if ledgers else None


def _record_payment(auth: Auth, ledger_id: str, amount_minor: int, *, idempotency_key: Optional[str] = None) -> dict:
    body = {
        "amount_minor": amount_minor,
        "payment_date": date.today().isoformat(),
        "reference": f"{MARKER}-pay",
        "payment_method": "bank_transfer",
        "ledger_id": ledger_id,
    }
    if idempotency_key:
        body["idempotency_key"] = idempotency_key
    r = _http(
        "post",
        f"{API}/client/operations/rent/ledgers/{ledger_id}/payments",
        headers=auth.h(),
        json=body,
        timeout=120,
    )
    return {"status": r.status_code, "body": r.json() if r.status_code in (200, 201) else r.text[:300]}


def _close_tenancy(auth: Auth, tenancy_id: str) -> dict:
    r = _http(
        "post",
        f"{API}/client/operations/rent/tenancies/{tenancy_id}/close",
        headers=auth.h(),
        json={"status": "moved_out"},
        timeout=90,
    )
    return {"status": r.status_code, "body": r.json() if r.status_code == 200 else r.text[:300]}


def _rent_summary(auth: Auth, property_id: Optional[str] = None) -> dict:
    params = {"property_id": property_id} if property_id else {}
    r = _http("get", f"{API}/client/operations/rent/summary", headers=auth.h(), params=params, timeout=90)
    return {"status": r.status_code, "body": r.json() if r.status_code == 200 else {}}


def _occupancy_summary(auth: Auth, property_id: str) -> dict:
    r = _http(
        "get",
        f"{API}/client/properties/{property_id}/occupancy-operational-summary",
        headers=auth.h(),
        timeout=90,
    )
    return {"status": r.status_code, "body": r.json() if r.status_code == 200 else {}}


def _today_items(auth: Auth) -> dict:
    r = _http("get", f"{API}/client/today/items", headers=auth.h(), timeout=120)
    body = r.json() if r.status_code == 200 else {}
    rent_items = [
        i for i in (body.get("items") or body if isinstance(body, list) else [])
        if "rent" in json.dumps(i).lower()
    ] if isinstance(body, dict) else []
    return {"status": r.status_code, "rent_related_count": len(rent_items), "body_sample": body if isinstance(body, dict) else {}}


def _command_center(auth: Auth, property_id: Optional[str] = None) -> dict:
    params = {"property_id": property_id} if property_id else {}
    r = _http("get", f"{API}/client/command-center", headers=auth.h(), params=params, timeout=120)
    body = r.json() if r.status_code == 200 else {}
    rent_signals = []
    if isinstance(body, dict):
        for key in ("attention_items", "items", "sections", "rent_attention"):
            chunk = body.get(key)
            if chunk:
                rent_signals.append({key: chunk})
    return {"status": r.status_code, "body_keys": list(body.keys()) if isinstance(body, dict) else [], "rent_signals": rent_signals}


def run_browser(auth: Auth, pilot: dict) -> dict[str, Any]:
    out: dict[str, Any] = {"attempted": False, "browser_available": sync_playwright is not None}
    if sync_playwright is None:
        out["error"] = "playwright_not_installed"
        return out

    prop_a = pilot["property_a"]
    prop_b = pilot.get("property_b")
    pw = os.environ.get("OPS_VERIFY_PASSWORD") or PW_FILE.read_text(encoding="utf-8").strip()

    timings: dict[str, int] = {}
    captures: dict[str, Any] = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()

        t0 = time.perf_counter()
        page.goto(f"{FRONTEND}/login/client", wait_until="domcontentloaded", timeout=120_000)
        page.fill("#email", EMAIL)
        page.fill("#password", pw)
        page.click('button[type="submit"]')
        page.wait_for_timeout(5000)
        page.goto(
            f"{FRONTEND}/operations/rent?property_id={prop_a}&setup=1",
            wait_until="networkidle",
            timeout=120_000,
        )
        timings["rent_shell_ms"] = int((time.perf_counter() - t0) * 1000)

        captures["rent_page_visible"] = page.locator('[data-testid="rent-operations-page"]').count() > 0
        captures["enable_tracking_visible"] = page.locator('[data-testid="rent-enable-tracking"]').count() > 0

        if page.locator('[data-testid="rent-enable-tracking"]').count():
            page.locator('[data-testid="rent-enable-tracking"]').first.click()
            page.wait_for_timeout(500)

        t_modal = time.perf_counter()
        captures["schedule_modal"] = page.locator('[data-testid="rent-schedule-modal"]').count() > 0
        timings["schedule_modal_ms"] = int((time.perf_counter() - t_modal) * 1000)

        if captures["schedule_modal"]:
            page.wait_for_timeout(1500)
            captures["schedule_preview_visible"] = page.locator('[data-testid="rent-schedule-preview"]').count() > 0
            preview_text = ""
            if captures["schedule_preview_visible"]:
                preview_text = (page.locator('[data-testid="rent-schedule-preview"]').first.inner_text() or "").strip()
            captures["schedule_preview_text"] = preview_text[:500]

        # Payment from ledger if any row exists
        page.goto(
            f"{FRONTEND}/operations/rent?property_id={prop_a}&tab=ledger",
            wait_until="networkidle",
            timeout=120_000,
        )
        page.wait_for_timeout(2500)
        pay_btn = page.locator('button:has-text("Record payment")')
        captures["ledger_record_payment_buttons"] = (
            pay_btn.count() + page.locator('[data-testid="ledger-record-payment"]').count()
        )
        if pay_btn.count() > 0:
            pay_btn.first.click()
            page.wait_for_timeout(500)
            captures["payment_modal"] = page.locator('[data-testid="record-payment-modal"]').count() > 0
            captures["payment_authority_context"] = page.locator('[data-testid="payment-authority-context"]').count() > 0
            if captures["payment_authority_context"]:
                captures["payment_context_text"] = (
                    page.locator('[data-testid="payment-authority-context"]').first.inner_text() or ""
                )[:400]

        # Occupancy enable rent link
        if prop_a:
            page.goto(
                f"{FRONTEND}/properties/{prop_a}?tab=occupancy",
                wait_until="networkidle",
                timeout=120_000,
            )
            page.wait_for_timeout(3000)
            captures["occupancy_enable_link"] = page.locator('[data-testid="occupancy-enable-rent-tracking"]').count() > 0

        # Property B filter isolation (no cross-leak in UI label)
        if prop_b:
            page.goto(
                f"{FRONTEND}/operations/rent?property_id={prop_b}",
                wait_until="networkidle",
                timeout=120_000,
            )
            page.wait_for_timeout(2500)
            captures["property_b_filter_loaded"] = page.locator('[data-testid="rent-filter-property"]').count() > 0

        browser.close()

    out["attempted"] = True
    out["timings"] = timings
    out["captures"] = captures
    out["finished_at_utc"] = _utc()
    return out


def main() -> int:
    results: dict[str, Any] = {
        "programme": "RENT-TENANCY-AUTHORITY-RUNTIME-VERIFY-01",
        "run_tag": MARKER,
        "started_at_utc": _utc(),
        "frontend": FRONTEND,
        "api": API,
        "pilot_email": EMAIL,
    }
    defects: List[str] = []

    # PART 1 — Deploy
    deploy = verify_deploy()
    _write("deployment_verification.json", deploy)
    results["deploy_continuity"] = deploy
    if not deploy.get("deploy_ready"):
        defects.append("DEPLOY_CONTINUITY_FAILURE")
        _write("classifications.json", {
            "classification": "BLOCKED",
            "verified_operationally": False,
            "reason": "Staging frontend missing tenancy-authority deploy markers",
            "defects": defects,
            "verified_at_utc": _utc(),
        })
        print(json.dumps({"classification": "BLOCKED", "deploy": deploy}, indent=2))
        return 1

    auth = Auth()
    try:
        auth.login()
    except Exception as exc:
        _write("classifications.json", {
            "classification": "BLOCKED",
            "reason": f"login_failed: {exc}",
            "verified_at_utc": _utc(),
        })
        return 1

    properties, properties_probe = _list_properties(auth)
    if len(properties) < 2:
        defects.append("insufficient_properties_for_multi_property_pilot")
    prop_a = (
        properties[0]["property_id"]
        if properties
        else (PILOT_PROPERTY_A or None)
    )
    prop_b = (
        properties[1]["property_id"]
        if len(properties) > 1
        else (
            properties[0]["property_id"]
            if len(properties) == 1 and PILOT_PROPERTY_B
            else (PILOT_PROPERTY_B or prop_a)
        )
    )
    if prop_b == prop_a and len(properties) >= 2:
        prop_b = properties[1]["property_id"]

    pilot = {
        "property_a": prop_a,
        "property_b": prop_b,
        "properties_count": len(properties),
        "properties_probe": properties_probe,
        "pilot_fallback_used": len(properties) == 0 and bool(PILOT_PROPERTY_A),
    }

    cap_probe = _http("get", f"{API}/client/operations/rent/capabilities", headers=auth.h(), timeout=60)
    ten_probe = _http(
        "get",
        f"{API}/client/operations/rent/tenancies",
        headers=auth.h(),
        params={"property_id": prop_a or ""},
        timeout=60,
    )
    prev_probe = _http(
        "post",
        f"{API}/client/operations/rent/schedules/preview",
        headers=auth.h(),
        json={
            "property_id": prop_a or "",
            "expected_amount_minor": 125000,
            "due_day": 1,
            "start_date": date.today().replace(day=1).isoformat(),
            "rent_frequency": "monthly",
        },
        timeout=60,
    )
    api_routes = {
        "capabilities_status": cap_probe.status_code,
        "capabilities_body": cap_probe.json() if cap_probe.status_code == 200 else cap_probe.text[:200],
        "tenancies_list_status": ten_probe.status_code,
        "schedules_preview_status": prev_probe.status_code,
        "schedule_create_requires_tenancy_probe": None,
        "backend_tenancy_routes_live": ten_probe.status_code == 200,
        "backend_preview_live": prev_probe.status_code == 200,
    }
    if prop_a:
        probe_sched = _http(
            "post",
            f"{API}/client/operations/rent/schedules",
            headers=auth.h(),
            json={
                "property_id": prop_a,
                "tenant_name": f"{MARKER} probe",
                "expected_amount_minor": 125000,
                "due_day": 1,
                "start_date": date.today().replace(day=1).isoformat(),
                "rent_frequency": "monthly",
            },
            timeout=60,
        )
        api_routes["schedule_create_requires_tenancy_probe"] = probe_sched.status_code
        api_routes["schedule_create_detail"] = (
            probe_sched.json() if probe_sched.headers.get("content-type", "").startswith("application/json") else probe_sched.text[:200]
        )
    deploy["api_routes"] = api_routes
    if not api_routes["backend_tenancy_routes_live"]:
        defects.append("BACKEND_TENANCY_API_NOT_DEPLOYED")
        deploy["backend_partial"] = "schedule_validation_requires_tenancy_but_tenancy_CRUD_404"
        deploy["deploy_ready"] = False
        deploy["classification"] = "DEPLOY_CONTINUITY_FAILURE"
    _write("deployment_verification.json", deploy)

    # PART 2 — Tenancy schedule flow (API + structure)
    tenancy_a = _create_tenancy(auth, prop_a) if prop_a else {"status": 0, "body": ""}
    tenancy_b = _create_tenancy(auth, prop_b) if prop_b and prop_b != prop_a else tenancy_a
    tenancy_a_id = (
        (tenancy_a.get("body") or {}).get("tenancy_id")
        if isinstance(tenancy_a.get("body"), dict)
        else None
    )
    preview = _preview_schedule(auth, prop_a) if prop_a else {}
    idem_key = f"idem_{MARKER}_{uuid.uuid4().hex[:8]}"
    sched1 = (
        _create_schedule(auth, prop_a, tenancy_a_id, idempotency_key=idem_key)
        if prop_a and tenancy_a_id
        else {"status": 400, "body": {"error": "tenancy_unavailable", "tenancy_probe": tenancy_a}}
    )
    sched2_replay = (
        _create_schedule(auth, prop_a, tenancy_a_id, idempotency_key=idem_key)
        if prop_a and tenancy_a_id
        else sched1
    )

    sched_body = sched1.get("body") if isinstance(sched1.get("body"), dict) else {}
    preview_body = preview.get("body") if isinstance(preview.get("body"), dict) else {}
    tenancy_sched = {
        "verified_at_utc": _utc(),
        "api_routes": api_routes,
        "tenancy_a": tenancy_a,
        "tenancy_b": tenancy_b,
        "preview": preview,
        "schedule_create": sched1,
        "tenancy_required_enforced": sched1.get("status") not in (200, 201) or bool(sched_body.get("tenancy_id")),
        "preview_period_count": preview_body.get("period_count"),
        "schedule_periods_created": sched_body.get("periods_created"),
        "preview_disclosure": preview_body.get("disclosure"),
        "pass": (
            preview.get("status") == 200
            and sched1.get("status") in (200, 201)
            and bool(sched_body.get("tenancy_id"))
            and int(sched_body.get("periods_created") or 0) >= 1
        ),
    }
    _write("tenancy_schedule_runtime.json", tenancy_sched)
    results["tenancy_schedule"] = tenancy_sched
    if not tenancy_sched["pass"]:
        defects.append("RENT_AUTHORITY_DRIFT")

    # PART 3 — Idempotency
    replay_body = sched2_replay.get("body") or {}
    active_schedules_r = _http(
        "get",
        f"{API}/client/operations/rent/schedules",
        headers=auth.h(),
        params={"property_id": prop_a},
        timeout=60,
    )
    active_count = len((active_schedules_r.json().get("schedules") or []) if active_schedules_r.status_code == 200 else [])
    idem = {
        "verified_at_utc": _utc(),
        "idempotency_key": idem_key,
        "first_create": sched1,
        "replay_create": sched2_replay,
        "idempotent_replay_flag": bool(replay_body.get("idempotent_replay")),
        "same_schedule_id": replay_body.get("schedule_id") == sched_body.get("schedule_id"),
        "active_schedules_for_tenancy": active_count,
        "pass": bool(replay_body.get("idempotent_replay")) and active_count <= 2,
    }
    _write("schedule_idempotency_runtime.json", idem)
    _write("g9_rent_integrity.json", {**idem, "g9_label": "schedule_payment_idempotency"})
    results["idempotency"] = idem
    if not idem["pass"]:
        defects.append("LEDGER_DUPLICATION_RISK")

    # PART 4 — Ledger materialisation
    ledgers_a = _list_ledgers(auth, property_id=prop_a, tenancy_id=tenancy_a_id)
    period_keys = [L.get("period_key") for L in ledgers_a if L.get("schedule_id") == sched_body.get("schedule_id")]
    dup_keys = len(period_keys) != len(set(period_keys))
    ledger_mat = {
        "verified_at_utc": _utc(),
        "preview_period_count": preview_body.get("period_count"),
        "ledger_rows_for_schedule": len(period_keys),
        "duplicate_period_keys": dup_keys,
        "sample_period_keys": period_keys[:8],
        "schedule_id": sched_body.get("schedule_id"),
        "pass": not dup_keys and len(period_keys) >= 1,
    }
    _write("ledger_materialisation_runtime.json", ledger_mat)
    results["ledger_materialisation"] = ledger_mat
    if not ledger_mat["pass"]:
        defects.append("LEDGER_DUPLICATION_RISK")

    # PART 5 — Payment authority
    target = _payable_ledger(ledgers_a)
    pay_result = {}
    partial_ok = False
    if target:
        outstanding = int(target.get("outstanding_balance_minor") or 0)
        partial_amt = max(outstanding // 2, 1) if outstanding > 1 else outstanding
        pay_idem = f"pay_{MARKER}_{uuid.uuid4().hex[:8]}"
        pay_result = _record_payment(auth, target["ledger_id"], partial_amt, idempotency_key=pay_idem)
        pay_replay = _record_payment(auth, target["ledger_id"], partial_amt, idempotency_key=pay_idem)
        ld_r = _http(
            "get",
            f"{API}/client/operations/rent/ledgers/{target['ledger_id']}",
            headers=auth.h(),
            timeout=60,
        )
        after = ld_r.json() if ld_r.status_code == 200 else {}
        payments = after.get("payments") or []
        partial_ok = (
            pay_result.get("status") in (200, 201)
            and int(after.get("outstanding_balance_minor") or 0) < outstanding
            and bool(payments)
            and all(p.get("ledger_id") == target["ledger_id"] for p in payments[-2:])
        )
        pay_auth = {
            "verified_at_utc": _utc(),
            "target_ledger": {
                "ledger_id": target["ledger_id"],
                "tenancy_id": target.get("tenancy_id"),
                "period_key": target.get("period_key"),
                "outstanding_before": outstanding,
            },
            "partial_payment": pay_result,
            "payment_idempotent_replay": (pay_replay.get("body") or {}).get("idempotent_replay"),
            "after_ledger": {
                "status": after.get("status"),
                "outstanding_balance_minor": after.get("outstanding_balance_minor"),
                "received_amount_minor": after.get("received_amount_minor"),
            },
            "payments_have_tenancy_id": all(p.get("tenancy_id") for p in payments) if payments else False,
            "legacy_ledger_without_tenancy_id": target.get("tenancy_id") is None if target else True,
            "pass": partial_ok
            and bool((pay_replay.get("body") or {}).get("idempotent_replay"))
            and (target.get("tenancy_id") is not None if target else False),
        }
    else:
        pay_auth = {"pass": False, "reason": "no_payable_ledger", "verified_at_utc": _utc()}
    _write("payment_runtime.json", pay_auth)
    results["payment_authority"] = pay_auth
    if not pay_auth.get("pass"):
        defects.append("PAYMENT_ATTRIBUTION_FAILURE")

    # PART 6 — External payer
    ext_key = f"ext_{MARKER}"
    ext_sched = _create_schedule(
        auth,
        prop_b or prop_a,
        "",
        idempotency_key=ext_key,
        external=True,
        external_name=f"{MARKER} Housing Benefit",
    )
    ext_body = ext_sched.get("body") if isinstance(ext_sched.get("body"), dict) else {}
    external = {
        "verified_at_utc": _utc(),
        "create": ext_sched,
        "is_external_payer": ext_body.get("is_external_payer"),
        "external_payer_name": ext_body.get("external_payer_name"),
        "tenancy_id_starts_with_ext": str(ext_body.get("tenancy_id") or "").startswith("ext_"),
        "pass": ext_sched.get("status") in (200, 201) and ext_body.get("is_external_payer") is True,
    }
    _write("external_payer_runtime.json", external)
    results["external_payer"] = external
    if not external["pass"]:
        defects.append("RENT_AUTHORITY_DRIFT")

    # PART 7 — Tenancy lifecycle
    hist_ledgers = len(_list_ledgers(auth, property_id=prop_a, tenancy_id=tenancy_a_id) if tenancy_a_id else [])
    close_res = (
        _close_tenancy(auth, tenancy_a_id)
        if tenancy_a_id
        else {"status": 404, "body": "tenancy_close_unavailable"}
    )
    replacement = _create_tenancy(auth, prop_a, rent_tracking=False) if prop_a else tenancy_a
    repl_id = (replacement.get("body") or {}).get("tenancy_id") if isinstance(replacement.get("body"), dict) else None
    new_sched = (
        _create_schedule(auth, prop_a, repl_id, idempotency_key=f"new_{MARKER}")
        if repl_id
        else {"status": 400, "body": {"error": "replacement_tenancy_unavailable"}}
    )
    ledgers_after_close = _list_ledgers(auth, property_id=prop_a, tenancy_id=tenancy_a_id) if tenancy_a_id else []
    lifecycle = {
        "verified_at_utc": _utc(),
        "close": close_res,
        "historical_ledger_count_preserved": hist_ledgers,
        "ledgers_after_close_same_count": len(ledgers_after_close) == hist_ledgers,
        "replacement_tenancy": replacement,
        "new_schedule_on_replacement": new_sched,
        "lineage_parent_observed": replacement.get("lineage_parent_tenancy_id") is None,
        "pass": close_res.get("status") == 200 and hist_ledgers >= 1 and new_sched.get("status") in (200, 201),
    }
    _write("tenancy_lifecycle_runtime.json", lifecycle)
    _write(
        "tenancy_lineage_runtime.json",
        {
            **lifecycle,
        "old_tenancy_id": tenancy_a_id,
        "new_tenancy_id": repl_id,
        "distinct_lineage": tenancy_a_id != repl_id if tenancy_a_id and repl_id else False,
        },
    )
    results["tenancy_lifecycle"] = lifecycle
    if not lifecycle["pass"]:
        defects.append("TENANCY_LINEAGE_BREAK")

    # PART 8 — Multi-property isolation
    ledgers_b = _list_ledgers(auth, property_id=prop_b) if prop_b else []
    iso = {
        "verified_at_utc": _utc(),
        "property_a": prop_a,
        "property_b": prop_b,
        "ledgers_a_count": len(ledgers_a),
        "ledgers_b_count": len(ledgers_b),
        "tenancy_ids_distinct": (
            tenancy_a_id
            != (
                (tenancy_b.get("body") or {}).get("tenancy_id")
                if isinstance(tenancy_b.get("body"), dict)
                else None
            )
            if prop_b != prop_a
            else True
        ),
        "summary_a": _rent_summary(auth, prop_a),
        "summary_b": _rent_summary(auth, prop_b),
        "pass": prop_b != prop_a and len(properties) >= 2,
    }
    _write("multi_property_isolation_runtime.json", iso)
    results["multi_property_isolation"] = iso
    if not iso["pass"]:
        defects.append("MULTI_PROPERTY_LEAKAGE")

    # PART 9 — Cross-surface
    occ = _occupancy_summary(auth, prop_a) if prop_a else {}
    summ = _rent_summary(auth, prop_a)
    today = _today_items(auth)
    cc = _command_center(auth, prop_a)
    occ_rent = (occ.get("body") or {}).get("rent_status") or {}
    cross = {
        "verified_at_utc": _utc(),
        "occupancy_rent_overdue": occ_rent.get("overdue_count"),
        "rent_ops_overdue": (summ.get("body") or {}).get("overdue_count"),
        "today_status": today.get("status"),
        "command_center_status": cc.get("status"),
        "coherent_overdue": True,
        "pass": summ.get("status") == 200 and occ.get("status") == 200,
    }
    if occ_rent.get("overdue_count") is not None and (summ.get("body") or {}).get("overdue_count") is not None:
        cross["coherent_overdue"] = occ_rent.get("overdue_count") == (summ.get("body") or {}).get("overdue_count")
    _write("cross_surface_rent_coherence.json", cross)
    g10 = {**cross, "authority_chain_preserved": pay_auth.get("pass") and tenancy_sched.get("pass")}
    _write("g10_rent_authority.json", g10)
    results["cross_surface"] = cross
    if not cross.get("pass"):
        defects.append("RENT_AUTHORITY_DRIFT")

    # PART 10 — Browser + performance
    browser = run_browser(auth, pilot)
    perf = {
        "verified_at_utc": _utc(),
        "browser": browser,
        "shell_ms": (browser.get("timings") or {}).get("rent_shell_ms"),
        "schedule_modal_ms": (browser.get("timings") or {}).get("schedule_modal_ms"),
        "payment_authority_in_browser": (browser.get("captures") or {}).get("payment_authority_context"),
        "schedule_preview_in_browser": (browser.get("captures") or {}).get("schedule_preview_visible"),
        "pass": browser.get("attempted")
        and (browser.get("captures") or {}).get("rent_page_visible")
        and (browser.get("timings") or {}).get("rent_shell_ms", 99999) < 15000,
    }
    _write("rent_performance_runtime.json", perf)
    results["performance"] = perf
    if not perf.get("pass"):
        defects.append("PERFORMANCE_DEGRADATION")

    # PART 11 — Convergence
    conv_reads: List[dict] = []
    if target and partial_ok:
        for i in range(4):
            time.sleep(CONVERGENCE_WAIT_S // 4)
            s = _rent_summary(auth, prop_a)
            conv_reads.append({
                "t": i,
                "outstanding": (s.get("body") or {}).get("total_outstanding_minor"),
                "overdue": (s.get("body") or {}).get("overdue_count"),
            })
    convergence = {
        "verified_at_utc": _utc(),
        "wait_s": CONVERGENCE_WAIT_S,
        "reads": conv_reads,
        "pass": len(conv_reads) >= 2 and conv_reads[-1].get("outstanding") is not None,
    }
    _write("convergence.json", convergence)
    results["convergence"] = convergence

    # Classification
    critical = {
        "DEPLOY_CONTINUITY_FAILURE",
        "RENT_AUTHORITY_DRIFT",
        "PAYMENT_ATTRIBUTION_FAILURE",
        "TENANCY_LINEAGE_BREAK",
        "LEDGER_DUPLICATION_RISK",
        "MULTI_PROPERTY_LEAKAGE",
    }
    all_pass = (
        deploy.get("deploy_ready")
        and tenancy_sched.get("pass")
        and idem.get("pass")
        and ledger_mat.get("pass")
        and pay_auth.get("pass")
        and external.get("pass")
        and lifecycle.get("pass")
        and iso.get("pass")
        and cross.get("pass")
        and perf.get("pass")
        and convergence.get("pass")
        and browser.get("attempted")
        and (
            (browser.get("captures") or {}).get("payment_authority_context")
            or (browser.get("captures") or {}).get("ledger_record_payment_buttons", 0) > 0
        )
    )
    if not api_routes.get("backend_tenancy_routes_live"):
        classification = "BLOCKED"
        reason = (
            "Staging backend missing tenancy-authority API routes "
            "(GET/POST /client/operations/rent/tenancies, POST /schedules/preview → 404). "
            "Frontend bundle deployed; operational tenancy-centric flows cannot complete."
        )
    elif all_pass:
        classification = "VERIFIED_OPERATIONALLY"
        reason = "Staging browser and API verification passed for tenancy-authority rent model."
    elif any(d in defects for d in critical):
        classification = "DEPLOY_CONTINUITY_FAILURE" if "BACKEND_TENANCY_API_NOT_DEPLOYED" in defects else (
            "FAIL_OPERATIONAL" if len(defects) > 1 else defects[0]
        )
        reason = f"Operational defects: {', '.join(sorted(set(defects)))}"
    else:
        classification = "PARTIAL"
        reason = f"Incomplete verification: {', '.join(defects) or 'browser_gaps'}"

    cls = {
        "classification": classification,
        "verified_operationally": classification == "VERIFIED_OPERATIONALLY",
        "reason": reason,
        "defects": defects,
        "run_tag": MARKER,
        "verified_at_utc": _utc(),
        "pilot": pilot,
        "browser_captures": browser.get("captures"),
    }
    _write("classifications.json", cls)

    watchlist = BUNDLE / "watchlist.md"
    watchlist.write_text(
        f"# Rent Tenancy Authority — Runtime Watchlist\n\n"
        f"**Run:** {MARKER}\n"
        f"**Classification:** {classification}\n\n"
        f"## Defects\n"
        + ("\n".join(f"- {d}" for d in defects) if defects else "- None\n")
        + f"\n## Browser\n"
        f"- Attempted: {browser.get('attempted')}\n"
        f"- Payment authority context: {(browser.get('captures') or {}).get('payment_authority_context')}\n"
        f"- Schedule preview: {(browser.get('captures') or {}).get('schedule_preview_visible')}\n",
        encoding="utf-8",
    )

    report = BUNDLE / "REPORT.md"
    report.write_text(
        f"# Rent Tenancy Authority — Runtime Verification\n\n"
        f"**Run:** {MARKER}  \n"
        f"**Classification:** `{classification}`  \n"
        f"**Verified at:** {_utc()}\n\n"
        f"## Summary\n\n{reason}\n\n"
        f"## Gates\n\n"
        f"| Gate | Pass |\n|------|------|\n"
        f"| Deploy continuity | {deploy.get('deploy_ready')} |\n"
        f"| Tenancy schedule | {tenancy_sched.get('pass')} |\n"
        f"| Idempotency | {idem.get('pass')} |\n"
        f"| Ledger materialisation | {ledger_mat.get('pass')} |\n"
        f"| Payment authority | {pay_auth.get('pass')} |\n"
        f"| External payer | {external.get('pass')} |\n"
        f"| Tenancy lifecycle | {lifecycle.get('pass')} |\n"
        f"| Multi-property | {iso.get('pass')} |\n"
        f"| Cross-surface | {cross.get('pass')} |\n"
        f"| Browser/perf | {perf.get('pass')} |\n"
        f"| Convergence | {convergence.get('pass')} |\n",
        encoding="utf-8",
    )

    results["classification"] = cls
    print(json.dumps(cls, indent=2))
    return 0 if classification == "VERIFIED_OPERATIONALLY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
