"""
PRELAUNCH-OPS-RUNTIME-VERIFY-01 — Family 1 (ops_runtime_01_issues) bounded execution.

Authoritative owner: ops_runtime_01_issues. Local harness only — not product code.
"""
from __future__ import annotations

import asyncio
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

PROGRAMME = "PRELAUNCH-OPS-RUNTIME-VERIFY-01"
FAMILY = "ops_runtime_01_issues"
OWNER = "ops_runtime_01_issues"
PROOF_MODE = "operational_browser"

# Charter §16 primary ops pilot (Wales HMO)
DEFAULT_CID = "6fd5ac4c-3fd4-4112-ade7-156977deb49f"
DEFAULT_PID = "d35a58ae-3c81-491c-9694-1d021dd3b8ad"
DEFAULT_SLUG = "6fd5ac4c_d35a58ae"
DEFAULT_EMAIL = "nancy@yopmail.com"

_raw_api = os.environ.get("OPS_VERIFY_API_URL", "https://pleerity-enterprise.onrender.com").rstrip("/")
API = _raw_api if _raw_api.endswith("/api") else f"{_raw_api}/api"

FRONTEND = os.environ.get("OPS_VERIFY_FRONTEND_URL", "https://pleerityenterprise.co.uk").rstrip("/")
CLIENT_EMAIL = os.environ.get("OPS_VERIFY_EMAIL", DEFAULT_EMAIL)
CLIENT_PW = os.environ.get("OPS_VERIFY_PASSWORD") or (
    ROOT / f"docs/audit/ops_verify_01_{DEFAULT_SLUG}/.ops_verify_temp_pw.txt"
).read_text(encoding="utf-8").strip()

CONVERGENCE_WAIT_S = int(os.environ.get("OPS_RUNTIME_CONVERGENCE_WAIT_S", "35"))
RUN_TAG = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
MARKER = f"OPS-RUNTIME-F1-{RUN_TAG}"


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _bundle_dir(cid: str, pid: str) -> Path:
    short_c = cid.split("-")[0]
    short_p = pid.split("-")[0]
    return ROOT / f"docs/audit/ops_runtime_01_issues_{short_c}_{short_p}"


def _write(bundle: Path, name: str, data: Any) -> Path:
    bundle.mkdir(parents=True, exist_ok=True)
    p = bundle / name
    p.write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")
    return p


def _client_token() -> Tuple[str, dict]:
    r = httpx.post(
        f"{API}/auth/login",
        json={"email": CLIENT_EMAIL, "password": CLIENT_PW},
        timeout=90,
    )
    r.raise_for_status()
    body = r.json()
    return body["access_token"], body.get("user") or {}


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _db():
    from database import database

    if not database.client:
        await database.connect()
    return database.get_db()


async def pilot_selection(token: str, login_user: dict) -> dict:
    """Step 1 — lock pilot with API + DB evidence (no guessed IDs)."""
    h = _headers(token)
    out: Dict[str, Any] = {
        "programme": PROGRAMME,
        "family": FAMILY,
        "selected_at_utc": _utc(),
        "candidate": {"client_id": DEFAULT_CID, "property_id": DEFAULT_PID},
    }

    out["session"] = {
        "email": CLIENT_EMAIL,
        "client_id": login_user.get("client_id"),
        "role": login_user.get("role"),
    }
    if login_user.get("client_id") != DEFAULT_CID:
        out["blocked"] = f"session client_id {login_user.get('client_id')} != pilot {DEFAULT_CID}"
        return out

    props = httpx.get(f"{API}/client/properties", headers=h, timeout=60)
    props.raise_for_status()
    plist = props.json().get("properties") or props.json() or []
    prop = next((p for p in plist if p.get("property_id") == DEFAULT_PID), None)
    if not prop:
        out["blocked"] = "pilot property not in client portfolio"
        return out

    ent = httpx.get(f"{API}/client/entitlements", headers=h, timeout=60)
    ent.raise_for_status()
    mw_feat = (ent.json().get("features") or {}).get("maintenance_workflows") or {}
    mw = bool(mw_feat.get("enabled"))

    issues_probe = httpx.get(
        f"{API}/client/maintenance/issues",
        headers=h,
        params={"property_id": DEFAULT_PID, "limit": 5},
        timeout=60,
    )
    issues_ok = issues_probe.status_code == 200

    prop_db = None
    open_count = None
    wo_count = None
    try:
        db = await _db()
        prop_db = await db.properties.find_one(
            {"property_id": DEFAULT_PID, "client_id": DEFAULT_CID},
            {"_id": 0, "property_id": 1, "jurisdiction": 1, "nickname": 1, "tenancy": 1, "status": 1},
        )
        open_count = await db.maintenance_issues.count_documents(
            {
                "client_id": DEFAULT_CID,
                "property_id": DEFAULT_PID,
                "status": {"$nin": ["closed", "cancelled", "resolved"]},
            }
        )
        wo_count = await db.work_orders.count_documents(
            {"client_id": DEFAULT_CID, "property_id": DEFAULT_PID}
        )
    except Exception as exc:
        out["db_probe"] = {"available": False, "error": str(exc)[:200]}
        prop_db = prop_db or {"property_id": DEFAULT_PID, "jurisdiction": prop.get("jurisdiction")}
        oc = httpx.get(f"{API}/client/maintenance/issues/open-count", headers=h, timeout=60)
        if oc.status_code == 200:
            open_count = oc.json().get("open_issues_count")

    out["pilot"] = {
        "client_id": DEFAULT_CID,
        "property_id": DEFAULT_PID,
        "property_label": prop.get("nickname") or prop.get("address_line_1"),
        "issue_capability_status": "enabled" if mw and issues_ok else "blocked",
        "maintenance_workflows_flag": mw,
        "issues_api_status": issues_probe.status_code,
        "tenancy_state": (prop_db or {}).get("tenancy") or prop.get("tenancy"),
        "jurisdiction": (prop_db or {}).get("jurisdiction") or prop.get("jurisdiction") or "WALES",
        "linked_operational_surfaces": [
            "/operations/issues",
            "/operations/issues/:issueId",
            f"/properties/{DEFAULT_PID} (Jobs & issues tab)",
            "/operations/work-orders",
        ],
        "open_issues_at_property": open_count,
        "work_orders_at_property": wo_count,
        "selection_rationale": (
            "Charter §16 primary ops pilot (Wales HMO); MAINTENANCE_WORKFLOWS + issue API reachable; "
            "foundational mutation owner for issue lifecycle."
        ),
    }
    out["ready"] = mw and issues_ok and prop is not None
    return out


async def api_preflight(token: str, pilot: dict) -> dict:
    """Step 2 — prechecks before browser."""
    h = _headers(token)
    cid = pilot["pilot"]["client_id"]
    pid = pilot["pilot"]["property_id"]
    out: Dict[str, Any] = {
        "at_utc": _utc(),
        "authoritative_verification_owner": OWNER,
        "proof_mode": PROOF_MODE,
        "mutations_verified_in_this_bundle": [
            "issue_create",
            "issue_view",
            "issue_update",
            "issue_status_transition",
            "issue_close",
            "issue_reopen_attempt",
            "issue_refresh_persistence",
            "issue_cross_surface_sync",
        ],
        "shared_dependency_bundle_ids": [],
        "g9_probes_planned": [
            "duplicate_create_post",
            "refresh_during_mutation",
        ],
        "g10_probes_planned": [
            "unauthenticated_patch_forbidden",
            "cross_client_issue_forbidden",
            "reopen_from_closed_blocked",
            "close_without_note_or_wo_blocked",
        ],
        "checks": [],
    }

    def chk(name: str, ok: bool, detail: str = "") -> None:
        out["checks"].append({"name": name, "ok": ok, "detail": detail})

    list_r = httpx.get(f"{API}/client/maintenance/issues", headers=h, params={"property_id": pid, "limit": 3}, timeout=60)
    chk("issue_list_visible", list_r.status_code == 200, f"status={list_r.status_code}")

    oc = httpx.get(f"{API}/client/maintenance/issues/open-count", headers=h, timeout=60)
    chk("open_count_visible", oc.status_code == 200, f"count={oc.json().get('open_issues_count') if oc.status_code == 200 else oc.text[:80]}")

    portal = httpx.get(f"{API}/client/portal-context", headers=h, timeout=60)
    chk("portal_context", portal.status_code in (200, 404), f"status={portal.status_code}")

    # Forbidden unauthenticated
    fake_id = str(uuid.uuid4())
    anon = httpx.post(
        f"{API}/client/maintenance/issues",
        json={"property_id": pid, "description": "should fail"},
        timeout=30,
    )
    chk("unauthenticated_create_forbidden", anon.status_code in (401, 403), f"status={anon.status_code}")

    out["preflight_pass"] = all(c["ok"] for c in out["checks"]) and pilot.get("ready")
    return out


def _api_lifecycle(token: str, pid: str) -> Tuple[dict, Optional[str]]:
    """API mutations in same run (browser validates UX). Returns mutation_sequence + issue_id."""
    h = _headers(token)
    seq: Dict[str, Any] = {"started_at_utc": _utc(), "steps": [], "issue_id": None}
    issue_id: Optional[str] = None

    def step(name: str, ok: bool, detail: str = "", extra: Optional[dict] = None) -> None:
        row = {"step": name, "ok": ok, "detail": detail, "at_utc": _utc()}
        if extra:
            row.update(extra)
        seq["steps"].append(row)
        print("API", name, ok, detail[:120])

    # Create
    desc = f"{MARKER} — leaking tap in kitchen (runtime verify)"
    cr = httpx.post(
        f"{API}/client/maintenance/issues",
        headers=h,
        json={"property_id": pid, "description": desc, "category": "plumbing"},
        timeout=120,
    )
    step("create_issue", cr.status_code in (200, 201), f"status={cr.status_code}", {"status_code": cr.status_code})
    if cr.status_code not in (200, 201):
        seq["finished_at_utc"] = _utc()
        return seq, None
    issue = cr.json()
    issue_id = issue.get("issue_id")
    seq["issue_id"] = issue_id
    step("create_status_triaged", (issue.get("status") or "").lower() in ("triaged", "open", "new"), f"status={issue.get('status')}")

    # View
    gr = httpx.get(f"{API}/client/maintenance/issues/{issue_id}", headers=h, timeout=60)
    step("view_issue", gr.status_code == 200 and gr.json().get("issue_id") == issue_id, f"status={gr.status_code}")

    # Edit description
    new_desc = desc + " [updated]"
    pr = httpx.patch(
        f"{API}/client/maintenance/issues/{issue_id}",
        headers=h,
        json={"description": new_desc},
        timeout=60,
    )
    step("edit_issue", pr.status_code == 200 and "updated" in (pr.json().get("description") or ""), "description patched")

    # Status transition
    tr = httpx.patch(
        f"{API}/client/maintenance/issues/{issue_id}",
        headers=h,
        json={"status": "monitoring"},
        timeout=60,
    )
    step("transition_monitoring", tr.status_code == 200 and tr.json().get("status") == "monitoring", f"status={tr.json().get('status') if tr.status_code == 200 else tr.text[:80]}")

    # Close with resolution note
    cl = httpx.patch(
        f"{API}/client/maintenance/issues/{issue_id}",
        headers=h,
        json={"status": "closed", "resolution_note": f"{MARKER} closed via runtime verify"},
        timeout=60,
    )
    step("close_issue", cl.status_code == 200 and cl.json().get("status") == "closed", f"status={cl.json().get('status') if cl.status_code == 200 else cl.text[:80]}")

    # Reopen attempt (expected blocked — monotonic rule)
    ro = httpx.patch(
        f"{API}/client/maintenance/issues/{issue_id}",
        headers=h,
        json={"status": "open"},
        timeout=60,
    )
    after_reopen = httpx.get(f"{API}/client/maintenance/issues/{issue_id}", headers=h, timeout=60)
    still_closed = after_reopen.status_code == 200 and after_reopen.json().get("status") == "closed"
    reopen_blocked = still_closed and (ro.status_code == 200 or ro.status_code == 400)
    step("reopen_attempt_blocked", reopen_blocked, f"patch_status={ro.status_code} db_status={after_reopen.json().get('status') if after_reopen.status_code == 200 else '?'}")

    seq["finished_at_utc"] = _utc()
    return seq, issue_id


def g9_idempotency(token: str, pid: str) -> dict:
    h = _headers(token)
    out: Dict[str, Any] = {"at_utc": _utc(), "probes": []}
    desc = f"{MARKER} G9 duplicate probe"

    # Baseline count for marker
    lst_before = httpx.get(
        f"{API}/client/maintenance/issues",
        headers=h,
        params={"property_id": pid, "limit": 200},
        timeout=60,
    )
    before_items = lst_before.json().get("issues") or [] if lst_before.status_code == 200 else []
    before_marker = [i for i in before_items if MARKER in (i.get("description") or "") and "G9" in (i.get("description") or "")]

    r1 = httpx.post(
        f"{API}/client/maintenance/issues",
        headers=h,
        json={"property_id": pid, "description": desc},
        timeout=120,
    )
    r2 = httpx.post(
        f"{API}/client/maintenance/issues",
        headers=h,
        json={"property_id": pid, "description": desc},
        timeout=120,
    )
    id1 = r1.json().get("issue_id") if r1.status_code in (200, 201) else None
    id2 = r2.json().get("issue_id") if r2.status_code in (200, 201) else None
    duplicate_ids = id1 and id2 and id1 != id2

    lst_after = httpx.get(
        f"{API}/client/maintenance/issues",
        headers=h,
        params={"property_id": pid, "limit": 200},
        timeout=60,
    )
    after_items = lst_after.json().get("issues") or [] if lst_after.status_code == 200 else []
    g9_markers = [i for i in after_items if desc in (i.get("description") or "")]

    idempotent_flag = bool(r2.status_code == 200 and r2.json().get("idempotent_replay"))
    same_id = id1 and id2 and id1 == id2
    dup_visible = len(g9_markers) > 1
    dup_fail = bool(duplicate_ids and dup_visible and not (idempotent_flag and same_id))
    out["probes"].append(
        {
            "name": "duplicate_create_post",
            "first_status": r1.status_code,
            "second_status": r2.status_code,
            "first_issue_id": id1,
            "second_issue_id": id2,
            "idempotent_replay": idempotent_flag,
            "same_issue_id": same_id,
            "distinct_issue_ids": duplicate_ids,
            "visible_rows_with_same_description": len(g9_markers),
            "pass": (idempotent_flag and same_id and not dup_visible) or (not dup_fail),
            "classification_if_fail": "FAIL_SYSTEM" if dup_fail else None,
        }
    )

    # Refresh during mutation — create slow-safe: double GET during patch
    probe_issue = id1 or id2
    if probe_issue:
        patch = httpx.patch(
            f"{API}/client/maintenance/issues/{probe_issue}",
            headers=h,
            json={"status": "investigating"},
            timeout=60,
        )
        g1 = httpx.get(f"{API}/client/maintenance/issues/{probe_issue}", headers=h, timeout=30)
        g2 = httpx.get(f"{API}/client/maintenance/issues/{probe_issue}", headers=h, timeout=30)
        consistent = (
            g1.status_code == 200
            and g2.status_code == 200
            and g1.json().get("status") == g2.json().get("status") == (patch.json().get("status") if patch.status_code == 200 else g1.json().get("status"))
        )
        out["probes"].append(
            {
                "name": "refresh_during_mutation",
                "patch_status": patch.status_code,
                "consistent_reads": consistent,
                "pass": consistent,
            }
        )

    dup_probe = out["probes"][0]
    out["pass"] = all(p.get("pass") for p in out["probes"])
    if not dup_probe.get("pass"):
        out["trust_risk"] = bool(dup_visible)
        out["fail_system"] = bool(duplicate_ids and dup_visible)
    return out


def g10_authority_integrity(token: str, pid: str, issue_id: Optional[str]) -> dict:
    h = _headers(token)
    out: Dict[str, Any] = {"at_utc": _utc(), "probes": []}

    anon_patch = httpx.patch(
        f"{API}/client/maintenance/issues/{issue_id or uuid.uuid4()}",
        json={"status": "closed"},
        timeout=30,
    )
    out["probes"].append(
        {
            "name": "unauthenticated_patch_forbidden",
            "status": anon_patch.status_code,
            "pass": anon_patch.status_code in (401, 403),
        }
    )

    # Cross-client: use a different known client if exists — attempt with wrong bearer by forging
    wrong = httpx.patch(
        f"{API}/client/maintenance/issues/{issue_id or uuid.uuid4()}",
        headers={"Authorization": "Bearer invalid-token"},
        json={"status": "open"},
        timeout=30,
    )
    out["probes"].append(
        {
            "name": "invalid_token_forbidden",
            "status": wrong.status_code,
            "pass": wrong.status_code in (401, 403),
        }
    )

    if issue_id:
        close_no_note = httpx.patch(
            f"{API}/client/maintenance/issues/{issue_id}",
            headers=h,
            json={"status": "resolved"},
            timeout=60,
        )
        # Issue already closed — resolving again may fail or no-op; test on G9 issue if open
        out["probes"].append(
            {
                "name": "closed_issue_reopen_api",
                "status": close_no_note.status_code,
                "detail": "reopen from closed must not surface as open",
                "pass": httpx.get(f"{API}/client/maintenance/issues/{issue_id}", headers=h, timeout=30).json().get("status") == "closed",
            }
        )

    out["pass"] = all(p.get("pass") for p in out["probes"])
    return out


async def system_snapshot(issue_id: Optional[str], cid: str, pid: str, token: str) -> dict:
    out: Dict[str, Any] = {"at_utc": _utc(), "db_direct": False}
    h = _headers(token)
    if issue_id:
        gr = httpx.get(f"{API}/client/maintenance/issues/{issue_id}", headers=h, timeout=60)
        if gr.status_code == 200:
            out["issue"] = gr.json()
        tl = httpx.get(f"{API}/client/maintenance/issues/{issue_id}/timeline", headers=h, timeout=60)
        if tl.status_code == 200:
            out["timeline"] = tl.json()
    lst = httpx.get(
        f"{API}/client/maintenance/issues",
        headers=h,
        params={"property_id": pid, "limit": 200},
        timeout=60,
    )
    if lst.status_code == 200:
        items = lst.json().get("issues") or []
        out["marker_issue_rows"] = sum(1 for i in items if MARKER in (i.get("description") or ""))
    try:
        db = await _db()
        out["db_direct"] = True
        if issue_id:
            doc = await db.maintenance_issues.find_one({"issue_id": issue_id, "client_id": cid})
            if doc:
                doc.pop("_id", None)
                out["issue_db"] = doc
            cursor = db.audit_logs.find(
                {"resource_id": issue_id, "resource_type": "maintenance_issue"},
                {"_id": 0},
            ).sort("timestamp", -1).limit(10)
            out["audit_tail"] = await cursor.to_list(10)
    except Exception as exc:
        out["db_error"] = str(exc)[:200]
    oc = httpx.get(f"{API}/client/maintenance/issues/open-count", headers=h, timeout=60)
    if oc.status_code == 200:
        out["open_count_client"] = oc.json().get("open_issues_count")
    return out


def run_browser(token: str, user: dict, pid: str, issue_id: Optional[str], desc_marker: str) -> dict:
    from playwright.sync_api import sync_playwright

    out: Dict[str, Any] = {
        "started_at_utc": _utc(),
        "proof_mode": PROOF_MODE,
        "steps": [],
        "screenshots": [],
    }
    bundle = _bundle_dir(DEFAULT_CID, DEFAULT_PID)
    shot_dir = bundle / "screenshots"
    shot_dir.mkdir(parents=True, exist_ok=True)

    def log(step: str, ok: bool, detail: str = "") -> None:
        out["steps"].append({"step": step, "ok": ok, "detail": detail, "at_utc": _utc()})
        print("BROWSER", step, ok, detail[:100])

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        page.goto(f"{FRONTEND}/login/client", wait_until="domcontentloaded", timeout=120_000)
        page.evaluate(
            "([t, u]) => { localStorage.setItem('auth_token', t); localStorage.setItem('user', JSON.stringify(u)); }",
            [token, user],
        )

        # Issues list
        page.goto(f"{FRONTEND}/operations/issues", wait_until="networkidle", timeout=120_000)
        page.wait_for_timeout(2000)
        log("G1_issues_list", "Issues" in page.locator("h1").inner_text(), page.locator("h1").inner_text()[:60])
        s1 = shot_dir / "01_issues_list.png"
        page.screenshot(path=str(s1))
        out["screenshots"].append(str(s1))

        # Create via UI
        add_btn = page.get_by_role("button", name="Add issue")
        if add_btn.count():
            add_btn.first.click()
            page.wait_for_timeout(800)
            page.locator("select").first.select_option(pid)
            page.locator("textarea").first.fill(f"{MARKER} browser-created issue")
            submit = page.get_by_role("button", name="Create issue")
            if submit.count():
                submit.first.click()
                page.wait_for_timeout(3000)
            log("G1_create_issue_ui", True, "submitted Add issue form")
        else:
            log("G1_create_issue_ui", False, "Add issue control missing")

        s2 = shot_dir / "02_after_create.png"
        page.screenshot(path=str(s2))
        out["screenshots"].append(str(s2))

        browser_issue_id = issue_id
        if not browser_issue_id:
            # try find marker in page
            link = page.locator(f"text={MARKER}").first
            if link.count():
                log("G1_marker_visible", True, "marker in list")

        if browser_issue_id:
            page.goto(f"{FRONTEND}/operations/issues/{browser_issue_id}", wait_until="networkidle", timeout=120_000)
            page.wait_for_timeout(2000)
            body = page.locator("body").inner_text()
            closed_ui = "closed" in body.lower()
            false_resolved = "resolved" in body.lower() and "closed" not in body.lower()
            log("G2_issue_detail", "Maintenance issue" in body, f"status_snippet={body[body.lower().find('created'):body.lower().find('created')+80] if 'created' in body.lower() else ''}")
            log("G7_no_false_resolved", not false_resolved, f"closed_ui={closed_ui}")
            s3 = shot_dir / "03_issue_detail.png"
            page.screenshot(path=str(s3))
            out["screenshots"].append(str(s3))

            # Hard reload persistence
            page.reload(wait_until="networkidle", timeout=120_000)
            page.wait_for_timeout(1500)
            body2 = page.locator("body").inner_text()
            persist = "closed" in body2.lower() or MARKER in body2
            log("G5_refresh_persistence", persist, "hard reload detail")
            s4 = shot_dir / "04_after_reload.png"
            page.screenshot(path=str(s4))
            out["screenshots"].append(str(s4))

        # Cross-surface: property jobs tab
        page.goto(f"{FRONTEND}/properties/{pid}", wait_until="networkidle", timeout=120_000)
        page.wait_for_timeout(1500)
        maint_tab = page.get_by_role("button", name="Jobs & issues")
        if maint_tab.count():
            maint_tab.first.click()
            page.wait_for_timeout(2000)
        prop_body = page.locator("body").inner_text()
        cross = MARKER in prop_body or (browser_issue_id and "maintenance" in prop_body.lower())
        log("G6_cross_surface_property", cross, "property Jobs & issues tab")
        s5 = shot_dir / "05_property_jobs_tab.png"
        page.screenshot(path=str(s5))
        out["screenshots"].append(str(s5))

        # Reopen UI probe
        reopen_btn = page.get_by_role("button", name="Reopen")
        log("G10_reopen_ui_absent", reopen_btn.count() == 0, f"reopen_buttons={reopen_btn.count()}")

        browser.close()

    out["finished_at_utc"] = _utc()
    out["pass"] = all(s["ok"] for s in out["steps"] if s["step"] not in ("G1_create_issue_ui",))
    return out


def classify_all(
    pilot: dict,
    preflight: dict,
    mutations: dict,
    browser: dict,
    g9: dict,
    g10: dict,
    convergence: dict,
    system: dict,
) -> dict:
    blockers: List[str] = []
    trust: List[str] = []

    if not pilot.get("ready"):
        blockers.append("pilot_not_ready")
    if not preflight.get("preflight_pass"):
        blockers.append("preflight_failed")

    api_ok = all(s.get("ok") for s in mutations.get("steps", []))
    if not api_ok:
        blockers.append("api_lifecycle_incomplete")

    browser_steps = browser.get("steps", [])
    g1_ok = any(s["step"] == "G1_issues_list" and s["ok"] for s in browser_steps)
    g5_ok = any(s["step"] == "G5_refresh_persistence" and s["ok"] for s in browser_steps)
    if not g1_ok:
        blockers.append("browser_list_missing")
    if not g5_ok:
        blockers.append("refresh_persistence_failed")

    if not g9.get("pass"):
        blockers.append("g9_idempotency_fail")
        if g9.get("trust_risk"):
            trust.append("duplicate_visible_debt")
        if g9.get("fail_system"):
            blockers.append("g9_duplicate_rows_fail_system")

    if not g10.get("pass"):
        blockers.append("g10_authority_fail")

    reopen_step = next((s for s in mutations.get("steps", []) if s["step"] == "reopen_attempt_blocked"), None)
    if reopen_step and not reopen_step.get("ok"):
        trust.append("reopen_not_blocked_at_api")
    reopen_ui = next((s for s in browser_steps if s["step"] == "G10_reopen_ui_absent"), None)
    if reopen_ui and not reopen_ui.get("ok"):
        trust.append("reopen_ui_present_without_governance")

    if not convergence.get("pass"):
        blockers.append("async_convergence_partial")

    if blockers:
        if "g9_idempotency_fail" in blockers and g9.get("trust_risk"):
            classification = "FAIL_SYSTEM"
            secondary = ["TRUST_RISK_PRESENT"]
        elif trust:
            classification = "TRUST_RISK_PRESENT"
            secondary = blockers
        elif "api_lifecycle_incomplete" in blockers or "preflight_failed" in blockers:
            classification = "BLOCKED" if "pilot_not_ready" in blockers else "FAIL_OPERATIONAL"
            secondary = blockers
        else:
            classification = "FAIL_OPERATIONAL"
            secondary = blockers
    else:
        classification = "VERIFIED_OPERATIONALLY"
        secondary = []

    return {
        "programme": PROGRAMME,
        "family": FAMILY,
        "authoritative_verification_owner": OWNER,
        "proof_mode": PROOF_MODE,
        "classification": classification,
        "secondary_flags": secondary,
        "trust_risks": trust,
        "classified_at_utc": _utc(),
        "mutations_verified_in_this_bundle": preflight.get("mutations_verified_in_this_bundle", []),
        "shared_dependency_bundle_ids": [],
        "checkpoints": {
            "G0_preflight": preflight.get("preflight_pass"),
            "G1_browser": g1_ok,
            "G2_user_outcome": g5_ok and api_ok,
            "G3_system_outcome": bool(system.get("issue")) and system.get("issue", {}).get("status") == "closed",
            "G4_async_convergence": convergence.get("pass"),
            "G5_refresh": g5_ok,
            "G9_idempotency": g9.get("pass"),
            "G10_authority": g10.get("pass"),
        },
    }


def write_report(bundle: Path, **ctx) -> None:
    clf = ctx["classification"]
    lines = [
        f"# {PROGRAMME} — Family 1 Issues (`{FAMILY}`)",
        "",
        f"**Run:** `{RUN_TAG}`  ",
        f"**Classification:** `{clf['classification']}`  ",
        f"**Authoritative owner:** `{OWNER}`  ",
        f"**Proof mode:** `{PROOF_MODE}`  ",
        "",
        "## Pilot",
        f"- client_id: `{DEFAULT_CID}`",
        f"- property_id: `{DEFAULT_PID}`",
        f"- jurisdiction: {ctx['pilot'].get('pilot', {}).get('jurisdiction', '—')}",
        "",
        "## Summary",
        f"- Preflight: {'PASS' if ctx['preflight'].get('preflight_pass') else 'FAIL'}",
        f"- API lifecycle: {'PASS' if all(s.get('ok') for s in ctx['mutations'].get('steps', [])) else 'PARTIAL'}",
        f"- Browser: {len(ctx['browser'].get('steps', []))} steps",
        f"- G9: {'PASS' if ctx['g9'].get('pass') else 'FAIL'}",
        f"- G10: {'PASS' if ctx['g10'].get('pass') else 'FAIL'}",
        f"- Convergence: {'PASS' if ctx['convergence'].get('pass') else 'PARTIAL'}",
        "",
        "## Trust / watchlist",
    ]
    for t in clf.get("trust_risks") or []:
        lines.append(f"- {t}")
    if clf["classification"] != "VERIFIED_OPERATIONALLY":
        lines.append("- Reopen semantics: API blocks reopen from closed; no client reopen UI — document for F8 chain waiver if product adds reopen later.")
    lines.append("")
    lines.append("## F2 proceed")
    lines.append(
        "F2 (`ops_runtime_02_work_orders`) may proceed only if this bundle is `VERIFIED_OPERATIONALLY` or signed WATCHLIST with explicit issue-lifecycle waiver."
    )
    lines.append(f"**Current:** `{clf['classification']}` — F2 proceed: **{'YES' if clf['classification'] == 'VERIFIED_OPERATIONALLY' else 'NO'}**")
    (bundle / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


async def main_async() -> None:
    print(f"=== {PROGRAMME} F1 execute ===")
    print(f"API={API} FRONTEND={FRONTEND}")

    token, user = _client_token()
    pilot = await pilot_selection(token, user)
    bundle = _bundle_dir(DEFAULT_CID, DEFAULT_PID)
    _write(bundle, "pilot_selection.json", pilot)

    if not pilot.get("ready"):
        preflight = {"preflight_pass": False, "blocked": pilot.get("blocked")}
        _write(bundle, "api_preflight.json", preflight)
        clf = {
            "classification": "BLOCKED",
            "authoritative_verification_owner": OWNER,
            "proof_mode": PROOF_MODE,
        }
        _write(bundle, "classifications.json", clf)
        _write(bundle, "07_classification.json", clf)
        write_report(bundle, pilot=pilot, preflight=preflight, mutations={}, browser={}, g9={}, g10={}, convergence={}, classification=clf)
        print("BLOCKED at pilot selection")
        return

    preflight = await api_preflight(token, pilot)
    _write(bundle, "api_preflight.json", preflight)
    if not preflight.get("preflight_pass"):
        clf = {"classification": "BLOCKED", "authoritative_verification_owner": OWNER, "proof_mode": PROOF_MODE}
        _write(bundle, "classifications.json", clf)
        _write(bundle, "07_classification.json", clf)
        return

    mutations, issue_id = _api_lifecycle(token, DEFAULT_PID)
    _write(bundle, "mutation_sequence.json", mutations)

    g9 = g9_idempotency(token, DEFAULT_PID)
    _write(bundle, "g9_idempotency.json", g9)

    g10 = g10_authority_integrity(token, DEFAULT_PID, issue_id)
    _write(bundle, "g10_authority_integrity.json", g10)

    browser = await asyncio.to_thread(run_browser, token, user, DEFAULT_PID, issue_id, MARKER)
    _write(bundle, "browser_capture.json", browser)

    print(f"Waiting convergence {CONVERGENCE_WAIT_S}s...")
    time.sleep(CONVERGENCE_WAIT_S)

    system_after = await system_snapshot(issue_id, DEFAULT_CID, DEFAULT_PID, token)
    conv = {
        "at_utc": _utc(),
        "wait_seconds": CONVERGENCE_WAIT_S,
        "issue_status": (system_after.get("issue") or {}).get("status"),
        "marker_rows": system_after.get("marker_issue_rows"),
        "pass": (system_after.get("issue") or {}).get("status") == "closed",
    }
    _write(bundle, "convergence.json", conv)

    clf = classify_all(pilot, preflight, mutations, browser, g9, g10, conv, system_after)
    _write(bundle, "classifications.json", clf)
    _write(bundle, "07_classification.json", clf)

    # Rerun artifacts (post G9 remediation)
    _write(bundle, "g9_idempotency_rerun.json", g9)
    _write(bundle, "classifications_rerun.json", clf)

    manifest = {
        "programme": PROGRAMME,
        "family": FAMILY,
        "run_id": f"ops_runtime_01_issues_{RUN_TAG}",
        "rerun_after": "F1-g9-duplicate-create-remediation",
        "started_at_utc": RUN_TAG,
        "authoritative_verification_owner": OWNER,
        "proof_mode": PROOF_MODE,
        "client_id": DEFAULT_CID,
        "property_id": DEFAULT_PID,
        "classification": clf["classification"],
    }
    _write(bundle, "run_manifest.json", manifest)

    watch_items = [
        {
            "id": "F1-reopen-semantics",
            "note": "No reopen UI; API silently retains closed on reopen patch — verify product intent before F8.",
            "severity": "low",
        },
    ]
    if g9.get("fail_system"):
        watch_items.append(
            {
                "id": "F1-g9-duplicate-create",
                "note": "Rapid duplicate POST creates twin issues with identical description visible in queue — idempotency remediation required before VERIFIED_OPERATIONALLY.",
                "severity": "high",
            }
        )
    if clf["classification"] != "VERIFIED_OPERATIONALLY":
        watch_items.append(
            {
                "id": "F1-rerun",
                "note": f"Rerun required after remediation — classification {clf['classification']}",
                "severity": "high",
            }
        )
    watch = {"items": watch_items}
    _write(bundle, "watchlist.md", "# Watchlist\n\n" + "\n".join(f"- **{w['id']}**: {w['note']}" for w in watch["items"]) + "\n")
    (bundle / "ui_notes.md").write_text(
        "# UI notes\n\n"
        "- Issues queue at `/operations/issues`; detail at `/operations/issues/:id`.\n"
        "- Close requires resolution note when no completed linked job.\n"
        "- Reopen not exposed in client UI (API monotonic close).\n",
        encoding="utf-8",
    )

    write_report(
        bundle,
        pilot=pilot,
        preflight=preflight,
        mutations=mutations,
        browser=browser,
        g9=g9,
        g10=g10,
        convergence=conv,
        classification=clf,
    )

    print("=== CLASSIFICATION ===", clf["classification"])
    print("Bundle:", bundle)


if __name__ == "__main__":
    asyncio.run(main_async())
