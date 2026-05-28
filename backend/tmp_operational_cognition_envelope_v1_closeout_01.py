#!/usr/bin/env python3
"""
OPERATIONAL-COGNITION-ENVELOPE-V1-CLOSEOUT-01 — post-deploy operational convergence verification.
"""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

try:
    from playwright.sync_api import Page, sync_playwright
except ImportError:
    Page = None  # type: ignore
    sync_playwright = None

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "docs/audit/operational_cognition_envelope_v1_closeout_01"
SHOT = OUT / "screenshots"
PROGRAMME = "OPERATIONAL-COGNITION-ENVELOPE-V1-CLOSEOUT-01"
RUN_TAG = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

API_BASE = "https://pleerity-enterprise.onrender.com"
API = f"{API_BASE}/api"
FRONTEND = "https://pleerityenterprise.co.uk"

EXPECTED_COMMITS = ("45ca2bb4", "c3220725", "82acc7f9")

LANDLORD_EMAIL = "nancy@yopmail.com"
LANDLORD_PW = ROOT / "docs/audit/ops_verify_01_6fd5ac4c_d35a58ae/.ops_verify_temp_pw.txt"
ADMIN_EMAIL = "aigbochievictory@gmail.com"
ADMIN_PW = ROOT / "docs/audit/ops_verify_01_6fd5ac4c_d35a58ae/.ops_verify_admin_pw.txt"
CONTRACTOR_EMAIL = "f2-ops-heating-wales@yopmail.com"
CONTRACTOR_PW = ROOT / "docs/audit/ops_runtime_03_contractor_6fd5ac4c_d35a58ae/.ops_contractor_temp_pw.txt"
TENANT_EMAIL = "f7-ops-wales@yopmail.com"
TENANT_PW = ROOT / "docs/audit/ops_runtime_07_tenant_portal_6fd5ac4c_d35a58ae/.ops_tenant_temp_pw.txt"
PILOT_PROPERTY = "0a5b4497-a1ba-4ee9-87e1-ae2bb9d4cc68"

ENVELOPE_FIELDS = (
    "primary_action",
    "continuation_state",
    "blockers",
    "progression_state",
    "degraded_state",
    "stale_state",
    "operational_truth_flags",
    "forbidden_mutations",
    "list_guidance",
)


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write(name: str, data: Any) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


def _read_pw(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _api_login(email: str, pw: str) -> Tuple[str, dict]:
    r = httpx.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=120)
    r.raise_for_status()
    body = r.json()
    return body["access_token"], body.get("user") or {}


def _get(path: str, token: Optional[str] = None, **params: Any) -> Dict[str, Any]:
    headers = _h(token) if token else {}
    last_exc: Optional[Exception] = None
    for attempt in range(4):
        t0 = time.perf_counter()
        try:
            r = httpx.get(f"{API}{path}", headers=headers, params=params or None, timeout=120)
            elapsed = round((time.perf_counter() - t0) * 1000, 1)
            try:
                body = r.json()
            except Exception:
                body = (r.text or "")[:800]
            return {"status": r.status_code, "ok": r.is_success, "body": body, "elapsed_ms": elapsed}
        except Exception as exc:
            last_exc = exc
            time.sleep(2.0 * (attempt + 1))
    raise last_exc  # type: ignore[misc]


def _envelope_complete(env: Any) -> Tuple[bool, List[str]]:
    if not isinstance(env, dict):
        return False, ["not_dict"]
    missing = [f for f in ENVELOPE_FIELDS if f not in env]
    if not env.get("read_only"):
        missing.append("read_only_false")
    if env.get("cognition_version") != "operational_cognition_v1":
        missing.append("cognition_version")
    if not env.get("forbidden_mutations"):
        missing.append("forbidden_mutations_empty")
    return len(missing) == 0, missing


def _parity(list_label: Optional[str], detail_label: Optional[str]) -> bool:
    if not list_label and not detail_label:
        return True
    if not list_label or not detail_label:
        return False
    return list_label.strip().lower() == detail_label.strip().lower()


def _login_page(page: Page, portal: str, email: str, password: str) -> bool:
    paths = {"client": "/login/client", "admin": "/login/admin", "contractor": "/login/contractor", "tenant": "/login/tenant"}
    page.goto(f"{FRONTEND}{paths.get(portal, '/login/client')}", wait_until="domcontentloaded", timeout=120_000)
    page.wait_for_timeout(2000)
    for sel, val in [("#email, input[type=email]", email), ("#password, input[type=password]", password)]:
        loc = page.locator(sel)
        if loc.count():
            loc.first.fill(val)
    submit = page.locator('button[type="submit"]')
    if submit.count():
        submit.first.click()
    page.wait_for_timeout(6000)
    return "login" not in page.url.lower()


def deploy_continuity() -> Dict[str, Any]:
    out: Dict[str, Any] = {"captured_at": _utc(), "classification": "BLOCKED_DEPLOY_CONTINUITY", "checks": []}
    health_ok = False
    for i in range(5):
        hr = _get("/health")
        if hr["status"] == 200:
            health_ok = True
            break
        time.sleep(1.5)
    ver = _get("/version")
    ver_body = ver.get("body") if isinstance(ver.get("body"), dict) else {}
    commit = str(ver_body.get("commit_sha") or ver_body.get("commit") or "")
    commit_prefix = commit[:8].lower()
    deploy_ok = any(commit_prefix.startswith(c[:8]) for c in EXPECTED_COMMITS)

    frontend_markers: Dict[str, Any] = {"reachable": False, "bundle_has_hero_marker": False, "bundle_has_chip_marker": False}
    try:
        fr = httpx.get(FRONTEND, timeout=60, follow_redirects=True)
        html = fr.text if fr.status_code == 200 else ""
        frontend_markers["reachable"] = bool(html)
        # Resolve main JS bundle from index.html
        m = re.search(r'src="(/static/js/main\.[a-f0-9]+\.js)"', html)
        if m:
            js_url = f"{FRONTEND}{m.group(1)}"
            js = httpx.get(js_url, timeout=120).text
            frontend_markers["bundle_has_hero_marker"] = "next-action-hero" in js
            frontend_markers["bundle_has_chip_marker"] = "list-cognition-chip" in js
            frontend_markers["main_js"] = m.group(1)
    except Exception as exc:
        frontend_markers["error"] = str(exc)[:300]

    out["health_ok"] = health_ok
    out["version"] = {"status": ver["status"], "commit_sha": commit, "body": ver_body}
    out["deploy_ok"] = deploy_ok
    out["expected_commits"] = list(EXPECTED_COMMITS)
    out["frontend_markers"] = frontend_markers

    checks = [
        {"name": "health_200", "pass": health_ok},
        {"name": "version_200", "pass": ver["status"] == 200},
        {"name": "deploy_commit_successor", "pass": deploy_ok},
        {"name": "frontend_reachable", "pass": frontend_markers["reachable"]},
        {"name": "frontend_bundle_hero_marker", "pass": frontend_markers["bundle_has_hero_marker"]},
        {"name": "frontend_bundle_chip_marker", "pass": frontend_markers["bundle_has_chip_marker"]},
    ]
    out["checks"] = checks
    if all(c["pass"] for c in checks):
        out["classification"] = "PASS"
    return out


def live_envelope_proof(client_tok: str, admin_tok: Optional[str]) -> Dict[str, Any]:
    surfaces: List[Dict[str, Any]] = []
    samples: Dict[str, Any] = {}

    # Jobs list + detail
    jr = _get("/client/maintenance/work-orders", client_tok, limit=30)
    jobs = (jr.get("body") or {}).get("work_orders") or []
    job = jobs[0] if jobs else None
    job_detail = None
    if job:
        jd = _get(f"/jobs/{job['work_order_id']}", client_tok)
        job_detail = jd.get("body") if jd.get("ok") else None
    samples["job"] = {"list": job, "detail": job_detail}
    ok_l, miss_l = _envelope_complete((job or {}).get("operational_cognition"))
    ok_d, miss_d = _envelope_complete((job_detail or {}).get("operational_cognition"))
    surfaces.append({"surface": "jobs_list", "present": bool(job and job.get("operational_cognition")), "complete": ok_l, "missing": miss_l})
    surfaces.append({"surface": "job_detail", "present": bool(job_detail and job_detail.get("operational_cognition")), "complete": ok_d, "missing": miss_d})

    # Issues
    ir = _get("/client/maintenance/issues", client_tok, limit=30)
    issues = (ir.get("body") or {}).get("issues") or []
    issue = issues[0] if issues else None
    issue_detail = None
    if issue:
        idr = _get(f"/client/maintenance/issues/{issue['issue_id']}", client_tok)
        issue_detail = idr.get("body") if idr.get("ok") else None
    samples["issue"] = {"list": issue, "detail": issue_detail}
    ok_l, miss_l = _envelope_complete((issue or {}).get("operational_cognition"))
    ok_d, miss_d = _envelope_complete((issue_detail or {}).get("operational_cognition"))
    surfaces.append({"surface": "issues_list", "present": bool(issue and issue.get("operational_cognition")), "complete": ok_l, "missing": miss_l})
    surfaces.append({"surface": "issue_detail", "present": bool(issue_detail and issue_detail.get("operational_cognition")), "complete": ok_d, "missing": miss_d})

    # Risk signals
    rs = _get("/client/maintenance/risk-signals", client_tok, limit=30)
    signals = (rs.get("body") or {}).get("signals") or []
    sig = signals[0] if signals else None
    sig_detail = None
    if sig:
        sdr = _get(f"/client/maintenance/risk-signals/{sig['signal_id']}", client_tok)
        sig_detail = sdr.get("body") if sdr.get("ok") else None
    samples["risk_signal"] = {"list": sig, "detail": sig_detail}
    ok_l, miss_l = _envelope_complete((sig or {}).get("operational_cognition"))
    ok_d, miss_d = _envelope_complete((sig_detail or {}).get("operational_cognition"))
    surfaces.append({"surface": "risk_signals_list", "present": bool(sig and sig.get("operational_cognition")), "complete": ok_l, "missing": miss_l})
    surfaces.append({"surface": "risk_signal_detail", "present": bool(sig_detail and sig_detail.get("operational_cognition")), "complete": ok_d, "missing": miss_d})

    # Rent
    rr = _get("/client/operations/rent/ledgers", client_tok, property_id=PILOT_PROPERTY, attention_only=True, limit=30)
    ledgers = (rr.get("body") or {}).get("ledgers") or []
    ledger = ledgers[0] if ledgers else None
    ledger_detail = None
    if ledger:
        ldr = _get(f"/client/operations/rent/ledgers/{ledger['ledger_id']}", client_tok)
        ledger_detail = ldr.get("body") if ldr.get("ok") else None
    samples["rent_ledger"] = {"list": ledger, "detail": ledger_detail}
    ok_l, miss_l = _envelope_complete((ledger or {}).get("operational_cognition"))
    ok_d, miss_d = _envelope_complete((ledger_detail or {}).get("operational_cognition"))
    surfaces.append({"surface": "rent_attention_list", "present": bool(ledger and ledger.get("operational_cognition")), "complete": ok_l, "missing": miss_l})
    surfaces.append({"surface": "rent_ledger_detail", "present": bool(ledger_detail and ledger_detail.get("operational_cognition")), "complete": ok_d, "missing": miss_d})

    # Requirement
    props = _get("/client/properties", client_tok, limit=5)
    prop_list = (props.get("body") or {}).get("properties") or props.get("body") or []
    if isinstance(prop_list, list) and prop_list:
        pid = prop_list[0].get("property_id") or PILOT_PROPERTY
    else:
        pid = PILOT_PROPERTY
    reqs = _get(f"/client/properties/{pid}/requirements", client_tok, limit=20)
    req_rows = (reqs.get("body") or {}).get("requirements") or []
    req = req_rows[0] if req_rows else None
    req_detail = None
    if req and req.get("requirement_id"):
        rdr = _get(f"/requirements/{req['requirement_id']}", client_tok)
        if rdr.get("ok") and isinstance(rdr.get("body"), dict):
            req_detail = (rdr["body"] or {}).get("requirement")
    samples["requirement"] = {"list": req, "detail": req_detail}
    ok_d, miss_d = _envelope_complete((req_detail or {}).get("operational_cognition"))
    surfaces.append({"surface": "requirement_detail", "present": bool(req_detail and req_detail.get("operational_cognition")), "complete": ok_d, "missing": miss_d})

    # Admin unresolved
    if admin_tok:
        un = _get("/admin/documents/unresolved", admin_tok, limit=20)
        docs = (un.get("body") or {}).get("documents") or []
        doc = docs[0] if docs else None
        samples["unresolved"] = doc
        ok_d, miss_d = _envelope_complete((doc or {}).get("operational_cognition"))
        surfaces.append({"surface": "admin_unresolved", "present": bool(doc and doc.get("operational_cognition")), "complete": ok_d, "missing": miss_d, "count": len(docs)})
    else:
        surfaces.append({"surface": "admin_unresolved", "present": False, "skipped": "admin_login_failed"})

    required_surfaces = [s for s in surfaces if s["surface"] not in ("rent_attention_list", "rent_ledger_detail", "admin_unresolved")]
    # rent and admin optional if empty inventory
    rent_optional = not ledgers
    admin_optional = not admin_tok or surfaces[-1].get("count", 0) == 0

    all_present = all(s.get("present") for s in required_surfaces)
    all_complete = all(s.get("complete") for s in surfaces if s.get("present"))

    return {
        "captured_at": _utc(),
        "surfaces": surfaces,
        "all_required_present": all_present,
        "all_complete": all_complete,
        "rent_optional_empty": rent_optional,
        "admin_optional_empty": admin_optional,
        "gate_pass": all_present and all_complete,
        "sample_ids": {
            "job_id": (job or {}).get("work_order_id"),
            "issue_id": (issue or {}).get("issue_id"),
            "signal_id": (sig or {}).get("signal_id"),
            "ledger_id": (ledger or {}).get("ledger_id"),
            "requirement_id": (req or {}).get("requirement_id"),
        },
    }


def list_surface_parity(samples: Dict[str, Any]) -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []

    def add(name: str, list_ent: Any, detail_ent: Any) -> None:
        lc = (list_ent or {}).get("operational_cognition") or {}
        dc = (detail_ent or {}).get("operational_cognition") or {}
        ll = (lc.get("list_guidance") or {}).get("recommended_action_label")
        dl = (dc.get("primary_action") or {}).get("label")
        rows.append(
            {
                "surface": name,
                "list_label": ll,
                "detail_label": dl,
                "parity": _parity(ll, dl),
                "list_has_cognition": bool(lc),
                "detail_has_cognition": bool(dc),
            }
        )

    add("jobs", (samples.get("job") or {}).get("list"), (samples.get("job") or {}).get("detail"))
    add("issues", (samples.get("issue") or {}).get("list"), (samples.get("issue") or {}).get("detail"))
    add("risk_signals", (samples.get("risk_signal") or {}).get("list"), (samples.get("risk_signal") or {}).get("detail"))
    add("rent", (samples.get("rent_ledger") or {}).get("list"), (samples.get("rent_ledger") or {}).get("detail"))

    un = samples.get("unresolved")
    if isinstance(un, dict):
        dc = un.get("operational_cognition") or {}
        rows.append(
            {
                "surface": "admin_unresolved",
                "list_label": (dc.get("list_guidance") or {}).get("recommended_action_label"),
                "detail_label": (dc.get("primary_action") or {}).get("label"),
                "parity": True,
                "list_has_cognition": bool(dc),
                "detail_has_cognition": bool(dc),
            }
        )

    parity_ok = all(r["parity"] for r in rows if r.get("list_has_cognition") and r.get("detail_has_cognition"))
    return {"captured_at": _utc(), "rows": rows, "parity_ok": parity_ok, "gate_pass": parity_ok}


def false_progression_check(samples: Dict[str, Any], client_tok: str) -> Dict[str, Any]:
    checks: List[Dict[str, Any]] = []
    for label, key in [("job", "job"), ("issue", "issue"), ("requirement", "requirement")]:
        ent = (samples.get(key) or {}).get("detail") or (samples.get(key) or {}).get("list")
        env = (ent or {}).get("operational_cognition") if isinstance(ent, dict) else {}
        flags = (env or {}).get("operational_truth_flags") or {}
        forbidden = (env or {}).get("forbidden_mutations") or []
        checks.append(
            {
                "entity": label,
                "truth_flags": flags,
                "forbidden_includes_mark_compliant": "mark_compliant" in forbidden,
                "read_only": (env or {}).get("read_only"),
            }
        )
    # Command centre degraded
    cc = _get("/client/command-center", client_tok, property_id=PILOT_PROPERTY, projection="primary")
    body = cc.get("body") if isinstance(cc.get("body"), dict) else {}
    trust = body.get("trust_surface_operational_metadata") if isinstance(body.get("trust_surface_operational_metadata"), dict) else {}
    degraded = (
        body.get("pressure_degraded") is True
        or body.get("pressure_status") == "degraded"
        or trust.get("pressure_degraded") is True
        or bool((body.get("freshness") or {}).get("degraded_sections"))
    )
    checks.append(
        {
            "entity": "command_center",
            "degraded_visible": degraded,
            "pressure_status": body.get("pressure_status"),
            "pressure_degraded": body.get("pressure_degraded"),
        }
    )
    ro_ok = all(c.get("read_only") is True for c in checks if "read_only" in c)
    forb_ok = all(c.get("forbidden_includes_mark_compliant") for c in checks if "forbidden_includes_mark_compliant" in c)
    return {"captured_at": _utc(), "checks": checks, "gate_pass": ro_ok and forb_ok}


def cross_role_runtime(client_tok: str, contractor_tok: Optional[str], tenant_tok: Optional[str], admin_tok: Optional[str]) -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    # Landlord can read cognition
    jr = _get("/client/maintenance/work-orders", client_tok, limit=1)
    jobs = (jr.get("body") or {}).get("work_orders") or []
    rows.append({"role": "landlord", "endpoint": "work_orders", "cognition_on_first": bool(jobs and jobs[0].get("operational_cognition"))})

    if contractor_tok:
        # Contractor should NOT get landlord maintenance list with cognition (403 or no field)
        cr = _get("/client/maintenance/work-orders", contractor_tok, limit=1)
        body = cr.get("body")
        cog = False
        if isinstance(body, dict) and (body.get("work_orders") or []):
            cog = bool((body["work_orders"][0] or {}).get("operational_cognition"))
        rows.append({"role": "contractor", "endpoint": "landlord_work_orders", "status": cr["status"], "cognition_leak": cog, "gate_pass": cr["status"] in (401, 403) or not cog})

    if tenant_tok:
        tr = _get("/client/maintenance/work-orders", tenant_tok, limit=1)
        body = tr.get("body")
        cog = False
        if isinstance(body, dict) and (body.get("work_orders") or []):
            cog = bool((body["work_orders"][0] or {}).get("operational_cognition"))
        rows.append({"role": "tenant", "endpoint": "landlord_work_orders", "status": tr["status"], "cognition_leak": cog, "gate_pass": tr["status"] in (401, 403) or not cog})

    if admin_tok:
        un = _get("/admin/documents/unresolved", admin_tok, limit=1)
        docs = (un.get("body") or {}).get("documents") or []
        rows.append({"role": "admin", "endpoint": "unresolved", "cognition_present": bool(docs and docs[0].get("operational_cognition")), "gate_pass": not docs or bool(docs[0].get("operational_cognition"))})

    gate = all(r.get("gate_pass", r.get("cognition_on_first", False)) for r in rows if r["role"] == "landlord" or "gate_pass" in r)
    return {"captured_at": _utc(), "rows": rows, "gate_pass": gate}


def browser_runtime_proof(sample_ids: Dict[str, Any], api_samples: Dict[str, Any]) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    hero_rows: List[Dict[str, Any]] = []
    browser_out: Dict[str, Any] = {"captured_at": _utc(), "captures": [], "gate_pass": False}
    if not sync_playwright:
        browser_out["skipped"] = "playwright_unavailable"
        return browser_out, hero_rows

    pw = _read_pw(LANDLORD_PW)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        page = ctx.new_page()
        if not _login_page(page, "client", LANDLORD_EMAIL, pw):
            browser.close()
            browser_out["skipped"] = "client_login_failed"
            return browser_out, hero_rows

        # List chips
        for path, name in [
            ("/operations/issues", "issues_list"),
            ("/operations/work-orders", "jobs_list"),
            ("/operations/risk-signals", "risk_signals_list"),
        ]:
            page.goto(f"{FRONTEND}{path}", wait_until="domcontentloaded", timeout=120_000)
            page.wait_for_timeout(6000)
            try:
                page.wait_for_selector('[data-testid="list-cognition-chip"]', timeout=12_000)
            except Exception:
                pass
            chips = page.locator('[data-testid="list-cognition-chip"]').count()
            shot = SHOT / f"{name}.png"
            page.screenshot(path=str(shot), full_page=True)
            browser_out["captures"].append({"surface": name, "list_cognition_chips": chips, "screenshot": str(shot.relative_to(ROOT))})

        # Job detail hero
        jid = sample_ids.get("job_id")
        if jid:
            page.goto(f"{FRONTEND}/operations/jobs/{jid}", wait_until="domcontentloaded", timeout=120_000)
            page.wait_for_timeout(5000)
            hero = page.locator('[data-testid="next-action-hero"]')
            hero_count = hero.count()
            primary_btn = page.locator('[data-testid="next-action-hero-primary"]')
            api_primary = ((api_samples.get("job") or {}).get("detail") or {}).get("operational_cognition", {}).get("primary_action", {}).get("label")
            hero_text = hero.inner_text() if hero_count else ""
            hero_rows.append(
                {
                    "surface": "job_detail",
                    "hero_present": hero_count > 0,
                    "api_primary_label": api_primary,
                    "hero_contains_api_label": bool(api_primary and api_primary.lower() in hero_text.lower()),
                    "blocker_visible": "blocker" in hero_text.lower(),
                }
            )
            page.screenshot(path=str(SHOT / "job_detail_hero.png"), full_page=True)
            browser_out["captures"].append({"surface": "job_detail", "hero_count": hero_count, "screenshot": "screenshots/job_detail_hero.png"})

        # Issue detail
        iid = sample_ids.get("issue_id")
        if iid:
            page.goto(f"{FRONTEND}/operations/issues/{iid}", wait_until="domcontentloaded", timeout=120_000)
            page.wait_for_timeout(5000)
            hero_count = page.locator('[data-testid="next-action-hero"]').count()
            api_primary = ((api_samples.get("issue") or {}).get("detail") or {}).get("operational_cognition", {}).get("primary_action", {}).get("label")
            hero_text = page.locator('[data-testid="next-action-hero"]').inner_text() if hero_count else ""
            hero_rows.append(
                {
                    "surface": "issue_detail",
                    "hero_present": hero_count > 0,
                    "api_primary_label": api_primary,
                    "hero_contains_api_label": bool(api_primary and api_primary.lower() in hero_text.lower()),
                }
            )
            page.screenshot(path=str(SHOT / "issue_detail_hero.png"), full_page=True)

        # Risk signal drawer (deep-link opens drawer with API-backed signal)
        sid = sample_ids.get("signal_id")
        if sid:
            page.goto(
                f"{FRONTEND}/operations/risk-signals?signal_id={sid}",
                wait_until="domcontentloaded",
                timeout=120_000,
            )
            try:
                page.wait_for_selector('[data-testid="next-action-hero"]', timeout=25_000)
            except Exception:
                page.wait_for_timeout(8000)
            hero_count = page.locator('[data-testid="next-action-hero"]').count()
            api_primary = ((api_samples.get("risk_signal") or {}).get("detail") or {}).get("operational_cognition", {}).get("primary_action", {}).get("label")
            hero_text = page.locator('[data-testid="next-action-hero"]').inner_text() if hero_count else ""
            hero_rows.append(
                {
                    "surface": "risk_signal_drawer",
                    "hero_present": hero_count > 0,
                    "api_primary_label": api_primary,
                    "hero_contains_api_label": bool(api_primary and api_primary.lower() in hero_text.lower()),
                }
            )
            page.screenshot(path=str(SHOT / "risk_signal_drawer.png"), full_page=True)

        # Requirement detail via property intel deep-link
        rid = sample_ids.get("requirement_id")
        req_detail = (api_samples.get("requirement") or {}).get("detail") or {}
        pid = req_detail.get("property_id") or PILOT_PROPERTY
        if rid and pid:
            page.goto(
                f"{FRONTEND}/properties/{pid}?open=intel&requirement_id={rid}",
                wait_until="domcontentloaded",
                timeout=120_000,
            )
            try:
                page.wait_for_selector('[data-testid="requirement-intel-dialog"]', timeout=25_000)
                page.wait_for_selector('[data-testid="next-action-hero"]', timeout=15_000)
            except Exception:
                page.wait_for_timeout(10000)
            hero_count = page.locator('[data-testid="next-action-hero"]').count()
            api_primary = (req_detail.get("operational_cognition") or {}).get("primary_action", {}).get("label")
            hero_text = page.locator('[data-testid="next-action-hero"]').inner_text() if hero_count else ""
            hero_rows.append(
                {
                    "surface": "requirement_detail",
                    "hero_present": hero_count > 0,
                    "api_primary_label": api_primary,
                    "hero_contains_api_label": bool(api_primary and api_primary.lower() in (hero_text or "").lower()),
                    "intel_dialog": page.locator('[data-testid="requirement-intel-dialog"]').count() > 0,
                }
            )
            page.screenshot(path=str(SHOT / "requirement_detail.png"), full_page=True)

        # Rent attention
        page.goto(f"{FRONTEND}/operations/rent?property_id={PILOT_PROPERTY}&tab=attention", wait_until="domcontentloaded", timeout=120_000)
        page.wait_for_timeout(4000)
        chips = page.locator('[data-testid="list-cognition-chip"]').count()
        browser_out["captures"].append({"surface": "rent_attention", "list_cognition_chips": chips})
        page.screenshot(path=str(SHOT / "rent_attention.png"), full_page=True)

        # Command centre degraded
        page.goto(f"{FRONTEND}/command-center", wait_until="domcontentloaded", timeout=120_000)
        page.wait_for_timeout(5000)
        body = page.inner_text("body")[:6000]
        browser_out["command_centre"] = {
            "degraded_mentioned": bool(re.search(r"degraded|incomplete|refresh", body, re.I)),
            "false_healthy": bool(re.search(r"all clear|fully compliant|everything is fine", body, re.I)),
        }
        page.screenshot(path=str(SHOT / "command_centre.png"), full_page=True)

        ctx.close()
        browser.close()

    required_heroes = {"job_detail", "issue_detail", "risk_signal_drawer", "requirement_detail"}
    present = {h["surface"] for h in hero_rows if h.get("hero_present")}
    label_match = all(h.get("hero_contains_api_label") for h in hero_rows if h.get("api_primary_label"))
    browser_out["gate_pass"] = required_heroes.issubset(present) and label_match
    browser_out["hero_rows"] = hero_rows
    return browser_out, hero_rows


def classify_all(
    deploy: Dict[str, Any],
    live: Dict[str, Any],
    parity: Dict[str, Any],
    hero_rows: List[Dict[str, Any]],
    browser: Dict[str, Any],
    false_prog: Dict[str, Any],
    cross_role: Dict[str, Any],
    degraded: Dict[str, Any],
) -> str:
    if deploy.get("classification") != "PASS":
        return "BLOCKED_DEPLOY_CONTINUITY"
    if not live.get("gate_pass"):
        return "FAIL_OPERATIONAL"
    if not parity.get("gate_pass"):
        return "OPERATIONAL_GUIDANCE_DRIFT"
    if not browser.get("gate_pass"):
        return "PARTIAL"
    if not false_prog.get("gate_pass"):
        return "TRUST_RISK_PRESENT"
    if not cross_role.get("gate_pass"):
        return "TRUST_RISK_PRESENT"
    if not degraded.get("gate_pass"):
        return "PARTIAL"
    required_heroes = {"job_detail", "issue_detail", "risk_signal_drawer", "requirement_detail"}
    if not required_heroes.issubset({h["surface"] for h in hero_rows if h.get("hero_present")}):
        return "PARTIAL"
    return "VERIFIED_OPERATIONALLY"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    SHOT.mkdir(parents=True, exist_ok=True)

    deploy = deploy_continuity()
    _write("deployment_continuity.json", deploy)

    if deploy.get("classification") != "PASS":
        classification = "BLOCKED_DEPLOY_CONTINUITY"
        _write("classifications.json", {"classification": classification, "blocking_gate": "deploy_continuity"})
        _write("live_envelope_runtime.json", {"skipped": True, "reason": "deploy_continuity_failed"})
        (OUT / "REPORT.md").write_text(
            f"# {PROGRAMME}\n\n**Classification:** {classification}\n\nDeploy continuity failed. See deployment_continuity.json.\n",
            encoding="utf-8",
        )
        (OUT / "watchlist.md").write_text("# Watchlist\n\n- Unblock deploy before cognition closeout.\n", encoding="utf-8")
        print(json.dumps({"classification": classification}, indent=2))
        return 1

    client_tok, _ = _api_login(LANDLORD_EMAIL, _read_pw(LANDLORD_PW))
    admin_tok = contractor_tok = tenant_tok = None
    for label, email, path in [
        ("admin", ADMIN_EMAIL, ADMIN_PW),
        ("contractor", CONTRACTOR_EMAIL, CONTRACTOR_PW),
        ("tenant", TENANT_EMAIL, TENANT_PW),
    ]:
        try:
            tok, _ = _api_login(email, _read_pw(path))
            if label == "admin":
                admin_tok = tok
            elif label == "contractor":
                contractor_tok = tok
            else:
                tenant_tok = tok
        except Exception:
            pass

    live = live_envelope_proof(client_tok, admin_tok)
    _write("live_envelope_runtime.json", live)

    samples = {
        "job": {"list": None, "detail": None},
        "issue": {"list": None, "detail": None},
        "risk_signal": {"list": None, "detail": None},
        "rent_ledger": {"list": None, "detail": None},
        "requirement": {"detail": None},
        "unresolved": None,
    }
    # Re-fetch samples for parity/browser (live_envelope_proof doesn't return full samples — refetch quickly)
    jr = _get("/client/maintenance/work-orders", client_tok, limit=5)
    jobs = (jr.get("body") or {}).get("work_orders") or []
    if jobs:
        samples["job"]["list"] = jobs[0]
        jd = _get(f"/jobs/{jobs[0]['work_order_id']}", client_tok)
        samples["job"]["detail"] = jd.get("body") if jd.get("ok") else None
    ir = _get("/client/maintenance/issues", client_tok, limit=5)
    issues = (ir.get("body") or {}).get("issues") or []
    if issues:
        samples["issue"]["list"] = issues[0]
        idr = _get(f"/client/maintenance/issues/{issues[0]['issue_id']}", client_tok)
        samples["issue"]["detail"] = idr.get("body") if idr.get("ok") else None
    rs = _get("/client/maintenance/risk-signals", client_tok, limit=5)
    signals = (rs.get("body") or {}).get("signals") or []
    if signals:
        samples["risk_signal"]["list"] = signals[0]
        sdr = _get(f"/client/maintenance/risk-signals/{signals[0]['signal_id']}", client_tok)
        samples["risk_signal"]["detail"] = sdr.get("body") if sdr.get("ok") else None
    rr = _get("/client/operations/rent/ledgers", client_tok, property_id=PILOT_PROPERTY, attention_only=True, limit=5)
    ledgers = (rr.get("body") or {}).get("ledgers") or []
    if ledgers:
        samples["rent_ledger"]["list"] = ledgers[0]
        ldr = _get(f"/client/operations/rent/ledgers/{ledgers[0]['ledger_id']}", client_tok)
        samples["rent_ledger"]["detail"] = ldr.get("body") if ldr.get("ok") else None
    props = _get("/client/properties", client_tok, limit=3)
    pl = (props.get("body") or {}).get("properties") or []
    pid = (pl[0].get("property_id") if pl else None) or PILOT_PROPERTY
    reqs = _get(f"/client/properties/{pid}/requirements", client_tok, limit=10)
    req_rows = (reqs.get("body") or {}).get("requirements") or []
    if req_rows:
        rdr = _get(f"/requirements/{req_rows[0]['requirement_id']}", client_tok)
        if rdr.get("ok"):
            samples["requirement"]["detail"] = (rdr.get("body") or {}).get("requirement")
    if admin_tok:
        un = _get("/admin/documents/unresolved", admin_tok, limit=5)
        docs = (un.get("body") or {}).get("documents") or []
        if docs:
            samples["unresolved"] = docs[0]

    parity = list_surface_parity(samples)
    _write("list_surface_parity.json", parity)

    false_prog = false_progression_check(samples, client_tok)
    _write("false_progression_runtime.json", false_prog)

    cross = cross_role_runtime(client_tok, contractor_tok, tenant_tok, admin_tok)
    _write("cross_role_runtime.json", cross)

    cc = _get("/client/command-center", client_tok, property_id=PILOT_PROPERTY, projection="primary")
    body = cc.get("body") if isinstance(cc.get("body"), dict) else {}
    degraded_visible = (
        body.get("pressure_degraded") is True
        or body.get("pressure_status") == "degraded"
        or len(body.get("urgent_actions") or []) > 0
    )
    degraded = {
        "captured_at": _utc(),
        "pressure_status": body.get("pressure_status"),
        "pressure_degraded": body.get("pressure_degraded"),
        "pressure_message": body.get("pressure_message"),
        "urgent_actions_count": len(body.get("urgent_actions") or []),
        "gate_pass": degraded_visible,
        "note": "Degraded disclosure or urgent rows remain visible (no false calm)",
    }
    _write("degraded_truthfulness_runtime.json", degraded)

    browser, hero_rows = browser_runtime_proof(live.get("sample_ids") or {}, samples)
    _write("browser_runtime.json", browser)
    _write("next_action_hero_runtime.json", {"captured_at": _utc(), "rows": hero_rows, "gate_pass": browser.get("gate_pass")})

    classification = classify_all(deploy, live, parity, hero_rows, browser, false_prog, cross, degraded)
    _write(
        "classifications.json",
        {
            "classification": classification,
            "programme": PROGRAMME,
            "run_tag": RUN_TAG,
            "gates": {
                "deploy_continuity": deploy.get("classification") == "PASS",
                "live_envelope": live.get("gate_pass"),
                "list_parity": parity.get("gate_pass"),
                "browser_hero": browser.get("gate_pass"),
                "false_progression": false_prog.get("gate_pass"),
                "cross_role": cross.get("gate_pass"),
                "degraded_truthfulness": degraded.get("gate_pass"),
            },
        },
    )

    report = f"""# {PROGRAMME}

**Run tag:** {RUN_TAG}  
**Classification:** {classification}

## Gates
| Gate | Pass |
|------|------|
| Deploy continuity | {deploy.get('classification') == 'PASS'} |
| Live API envelopes | {live.get('gate_pass')} |
| List/detail parity | {parity.get('gate_pass')} |
| Browser hero | {browser.get('gate_pass')} |
| False progression | {false_prog.get('gate_pass')} |
| Cross-role | {cross.get('gate_pass')} |
| Degraded truthfulness | {degraded.get('gate_pass')} |

## Deploy
- Commit: {(deploy.get('version') or {}).get('commit_sha')}
- Frontend bundle markers: {deploy.get('frontend_markers')}

## Blocking gate
{'' if classification == 'VERIFIED_OPERATIONALLY' else classification}
"""
    (OUT / "REPORT.md").write_text(report, encoding="utf-8")
    (OUT / "watchlist.md").write_text(
        "# Watchlist\n\n"
        + ("- None — VERIFIED_OPERATIONALLY.\n" if classification == "VERIFIED_OPERATIONALLY" else f"- Classification {classification}: re-run after remediation.\n"),
        encoding="utf-8",
    )

    print(json.dumps({"classification": classification, "deploy": deploy.get("classification"), "live": live.get("gate_pass")}, indent=2))
    return 0 if classification == "VERIFIED_OPERATIONALLY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
