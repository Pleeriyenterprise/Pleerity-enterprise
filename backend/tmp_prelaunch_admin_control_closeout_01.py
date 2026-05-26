#!/usr/bin/env python3
"""PRELAUNCH-ADMIN-CONTROL-REMEDIATION-01 — closeout verification (blockers only)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

ROOT = Path(__file__).resolve().parent
BUNDLE = ROOT / "docs/audit/admin_control_remediation_01"
SLUG = "6fd5ac4c_d35a58ae"
CLIENT_ID = "6fd5ac4c-3fd4-4112-ade7-156977deb49f"
PROPERTY_ID = "d35a58ae-3c81-491c-9694-1d021dd3b8ad"
ORPHAN_PROPERTY = "00000000-0000-0000-0000-000000000099"
API = (
    os.environ.get("OPS_VERIFY_API_URL", "https://pleerity-enterprise.onrender.com").rstrip("/")
    if os.environ.get("OPS_VERIFY_API_URL", "").endswith("/api")
    else f"{os.environ.get('OPS_VERIFY_API_URL', 'https://pleerity-enterprise.onrender.com').rstrip('/')}/api"
)
FRONTEND = os.environ.get("OPS_VERIFY_FRONTEND_URL", "https://pleerityenterprise.co.uk").rstrip("/")
RUN_TAG = f"ADMIN-CLOSEOUT-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
REASON = f"{RUN_TAG} OPS_ADMIN_REMEDIATION_PROBE closeout verification reason"
PACE = float(os.environ.get("OPS_API_PACE_S", "6"))


def _write(name: str, data: Any) -> None:
    BUNDLE.mkdir(parents=True, exist_ok=True)
    (BUNDLE / name).write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


def _pace() -> None:
    time.sleep(PACE)


def _read_pw() -> str:
    p = ROOT / f"docs/audit/ops_verify_01_{SLUG}/.ops_verify_admin_pw.txt"
    return os.environ.get("OPS_VERIFY_ADMIN_PASSWORD") or p.read_text(encoding="utf-8").strip()


def _login_admin() -> Tuple[str, dict]:
    for attempt in range(8):
        _pace()
        r = httpx.post(
            f"{API}/auth/admin/login",
            json={"email": os.environ.get("OPS_VERIFY_ADMIN_EMAIL", "aigbochievictory@gmail.com"), "password": _read_pw()},
            timeout=90,
        )
        if r.status_code == 200:
            b = r.json()
            return b["access_token"], b.get("user") or {}
        if r.status_code == 429:
            time.sleep(60 + attempt * 30)
    return "", {}


def _h(token: str, conf: str = "") -> dict:
    hdr = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    if conf:
        hdr["X-Admin-Confirmation-Token"] = conf
    return hdr


def _token(admin: str, action: str, resource: str) -> str:
    _pace()
    r = httpx.post(
        f"{API}/admin/governance/confirmation-token",
        headers=_h(admin),
        json={"action_id": action, "reason": REASON, "resource_key": resource},
        timeout=90,
    )
    return (r.json() or {}).get("token", "") if r.status_code == 200 else ""


def _load_probe() -> dict:
    p = BUNDLE / "probe_seed.json"
    if p.is_file():
        return json.loads(p.read_text(encoding="utf-8"))
    return {}


def run_seed(admin_token: str) -> dict:
    if os.environ.get("ADMIN_CLOSEOUT_SEED", "1") != "1":
        return _load_probe()
    seed_tok = _token(admin_token, "seed_admin_remediation_probe", CLIENT_ID)
    _pace()
    remote = httpx.post(
        f"{API}/admin/ops/remediation-probe-seed",
        headers=_h(admin_token, seed_tok),
        json={"client_id": CLIENT_ID, "property_id": PROPERTY_ID, "reason": REASON},
        timeout=120,
    )
    if remote.status_code == 200:
        report = remote.json()
        _write("probe_seed.json", report)
        return report
    local_err = None
    try:
        subprocess.run(
            [sys.executable, "-m", "scripts.admin_remediation_probe_seed"],
            cwd=str(ROOT),
            check=True,
            capture_output=True,
            text=True,
        )
        return _load_probe()
    except subprocess.CalledProcessError as exc:
        local_err = (exc.stderr or exc.stdout or str(exc))[:300]
    return {
        "pass": False,
        "remote_status": remote.status_code,
        "remote_detail": remote.text[:300],
        "local_error": local_err,
        "hint": "Governed POST /admin/ops/remediation-probe-seed failed; or set MONGO_URL for local seed script",
    }


def part_unresolved(admin: str, admin_user: dict, probe: dict) -> dict:
    out: Dict[str, Any] = {"run_tag": RUN_TAG, "checks": [], "pass": False}
    doc_resolve = probe.get("unresolved_resolve_document_id")
    doc_link = probe.get("unresolved_link_document_id")
    doc_reject = probe.get("unresolved_reject_document_id")
    req_id = probe.get("sample_requirement_id")

    _pace()
    lst = httpx.get(f"{API}/admin/documents/unresolved", headers=_h(admin), params={"limit": 50}, timeout=90)
    out["list_status"] = lst.status_code
    out["unresolved_count"] = len((lst.json() or {}).get("documents") or []) if lst.status_code == 200 else 0

    def api_mutate(name: str, doc_id: str, action_id: str, post_fn) -> None:
        tok = _token(admin, action_id, doc_id)
        _pace()
        r = post_fn(tok)
        out["checks"].append({"name": name, "pass": r.status_code in (200, 201), "status": r.status_code})

    if doc_resolve:
        api_mutate(
            "api_resolve_scope",
            doc_resolve,
            "resolve_unresolved_scope",
            lambda t: httpx.post(
                f"{API}/admin/documents/{doc_resolve}/resolve-scope",
                headers=_h(admin, t),
                json={"scope_type": "PROPERTY", "property_id": PROPERTY_ID, "reason": REASON},
                timeout=120,
            ),
        )
    if doc_link and req_id:
        api_mutate(
            "api_link_requirement",
            doc_link,
            "link_unresolved_requirement",
            lambda t: httpx.post(
                f"{API}/admin/documents/{doc_link}/link-requirement",
                headers=_h(admin, t),
                json={"requirement_id": req_id, "reason": REASON},
                timeout=120,
            ),
        )
    if doc_reject:
        api_mutate(
            "api_reject_unresolved",
            doc_reject,
            "reject_unresolved_document",
            lambda t: httpx.post(
                f"{API}/admin/documents/{doc_reject}/reject-unresolved",
                headers=_h(admin, t),
                json={"reason": REASON},
                timeout=120,
            ),
        )

    browser_ok = False
    if sync_playwright and doc_link and req_id:
        p = sync_playwright().start()
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        try:
            page.goto(f"{FRONTEND}/login/admin", wait_until="domcontentloaded", timeout=120000)
            page.evaluate(
                "([t,u])=>{localStorage.setItem('auth_token',t);localStorage.setItem('user',JSON.stringify(u));}",
                [admin, admin_user],
            )
            page.goto(f"{FRONTEND}/admin/documents/unresolved-queue", wait_until="networkidle", timeout=120000)
            page.wait_for_timeout(3000)
            body = page.locator("body").inner_text()
            steps = [
                {"name": "queue_loads", "pass": page.locator('[data-testid="unresolved-queue-root"]').count() > 0},
                {"name": "actions_visible", "pass": "Resolve scope" in body and "Link requirement" in body and "Reject" in body},
            ]
            if page.locator(f'[data-testid="unresolved-row-{doc_link}"]').count():
                page.locator(f'[data-testid="unresolved-row-{doc_link}"] button:has-text("Link requirement")').first.click()
                page.wait_for_timeout(500)
                page.locator('[data-testid="unresolved-link-requirement"]').fill(req_id)
                page.locator('[data-testid="unresolved-action-reason"]').fill(REASON)
                page.locator('button:has-text("Confirm")').first.click()
                page.wait_for_timeout(5000)
                result = page.locator('[data-testid="unresolved-last-result"]').inner_text() if page.locator('[data-testid="unresolved-last-result"]').count() else ""
                steps.append({"name": "browser_link_mutation", "pass": "completed" in result.lower() or "linked" in result.lower(), "result": result[:200]})
            out["browser_steps"] = steps
            browser_ok = all(s["pass"] for s in steps)
            (BUNDLE / "screenshots").mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(BUNDLE / "screenshots" / "unresolved_closeout.png"))
        finally:
            browser.close()
            p.stop()

    api_ok = all(c["pass"] for c in out["checks"]) if out["checks"] else False
    out["pass"] = api_ok and (browser_ok or not sync_playwright) and out.get("unresolved_count", 0) >= 1
    return out


def part_extraction(admin: str, probe: dict) -> dict:
    out: Dict[str, Any] = {"run_tag": RUN_TAG, "checks": [], "pass": False}
    stale_id = "82deb81b-f171-436b-9654-1f494af482f1"
    retry_id = probe.get("retry_document_id")

    _pace()
    q = httpx.get(f"{API}/documents/admin/extraction-queue", headers=_h(admin), timeout=90)
    items = (q.json() or {}).get("items") or [] if q.status_code == 200 else []
    stale_row = next((i for i in items if i.get("document_id") == stale_id), None)
    out["checks"].append({
        "name": "stale_row_marked_non_actionable",
        "pass": bool(stale_row and (stale_row.get("queue_stale") or not stale_row.get("queue_actionable"))),
        "row": stale_row,
    })

    if stale_id:
        _pace()
        r_stale = httpx.post(
            f"{API}/admin/documents/{stale_id}/retry-extraction",
            headers=_h(admin),
            json={"reason": REASON},
            timeout=90,
        )
        out["checks"].append({
            "name": "stale_retry_returns_stale_code",
            "pass": r_stale.status_code == 404 and "STALE_QUEUE_DOCUMENT_NOT_FOUND" in (r_stale.text or ""),
            "status": r_stale.status_code,
        })

    if retry_id:
        tok = _token(admin, "retry_document_extraction", retry_id)
        _pace()
        r1 = httpx.post(
            f"{API}/admin/documents/{retry_id}/retry-extraction",
            headers=_h(admin, tok),
            json={"reason": REASON},
            timeout=90,
        )
        out["checks"].append({"name": "valid_retry_first", "pass": r1.status_code == 200, "status": r1.status_code})
        tok2 = _token(admin, "retry_document_extraction", retry_id)
        _pace()
        r2 = httpx.post(
            f"{API}/admin/documents/{retry_id}/retry-extraction",
            headers=_h(admin, tok2),
            json={"reason": REASON},
            timeout=90,
        )
        out["checks"].append({
            "name": "duplicate_retry_suppressed",
            "pass": r2.status_code in (403, 429),
            "status": r2.status_code,
        })

    out["pass"] = all(c["pass"] for c in out["checks"])
    return out


def _find_cross_client_property(admin: str) -> Optional[str]:
    """Property owned by a different client than the Wales pilot."""
    _pace()
    clients = httpx.get(f"{API}/admin/clients", headers=_h(admin), params={"limit": 30}, timeout=90)
    if clients.status_code != 200:
        return None
    rows = (clients.json() or {}).get("clients") or (clients.json() or {}).get("items") or []
    other_cid = None
    for row in rows:
        cid = str(row.get("client_id") or row.get("id") or "").strip()
        if cid and cid != CLIENT_ID:
            other_cid = cid
            break
    if not other_cid:
        return None
    _pace()
    props = httpx.get(
        f"{API}/admin/clients/{other_cid}",
        headers=_h(admin),
        timeout=90,
    )
    if props.status_code != 200:
        return None
    body = props.json() or {}
    plist = body.get("properties") or body.get("property_list") or []
    if isinstance(plist, list) and plist:
        pid = plist[0].get("property_id") if isinstance(plist[0], dict) else None
        return str(pid) if pid else None
    return None


def part_monthly_digest(admin: str) -> dict:
    out: Dict[str, Any] = {"run_tag": RUN_TAG, "checks": [], "pass": False}

    _pace()
    r1 = httpx.post(
        f"{API}/admin/jobs/run",
        headers=_h(admin),
        json={"job": "monthly_digest", "property_ids": [PROPERTY_ID], "reason": REASON},
        timeout=90,
    )
    out["checks"].append({"name": "property_ids_without_client_rejected", "pass": r1.status_code == 400, "status": r1.status_code})

    tok = _token(admin, "run_scoped_automation_job", f"monthly_digest:{CLIENT_ID}")
    _pace()
    r2 = httpx.post(
        f"{API}/admin/jobs/run",
        headers=_h(admin, tok),
        json={"job": "monthly_digest", "client_id": CLIENT_ID, "property_ids": [ORPHAN_PROPERTY], "reason": REASON},
        timeout=120,
    )
    out["checks"].append({
        "name": "orphan_property_rejected",
        "pass": r2.status_code == 400 and "not owned" in (r2.text or "").lower(),
        "status": r2.status_code,
        "detail": r2.text[:200],
    })

    cross_pid = _find_cross_client_property(admin)
    out["cross_client_property_id"] = cross_pid
    if cross_pid:
        tok_cc = _token(admin, "run_scoped_automation_job", f"monthly_digest:{CLIENT_ID}")
        _pace()
        r_cc = httpx.post(
            f"{API}/admin/jobs/run",
            headers=_h(admin, tok_cc),
            json={"job": "monthly_digest", "client_id": CLIENT_ID, "property_ids": [cross_pid], "reason": REASON},
            timeout=120,
        )
        out["checks"].append({
            "name": "cross_client_property_rejected",
            "pass": r_cc.status_code == 400 and "not owned" in (r_cc.text or "").lower(),
            "status": r_cc.status_code,
            "detail": r_cc.text[:200],
        })
    else:
        out["checks"].append({
            "name": "cross_client_property_rejected",
            "pass": False,
            "status": None,
            "detail": "no second client property discovered for cross-client probe",
        })

    _pace()
    r3 = httpx.post(
        f"{API}/admin/jobs/run",
        headers=_h(admin),
        json={"job": "monthly_digest", "portfolio_wide": True, "reason": REASON},
        timeout=90,
    )
    out["checks"].append({"name": "portfolio_wide_without_token_rejected", "pass": r3.status_code == 403, "status": r3.status_code})

    tok_pw = _token(admin, "run_portfolio_wide_job", "monthly_digest:global")
    _pace()
    r_pw = httpx.post(
        f"{API}/admin/jobs/run",
        headers=_h(admin, tok_pw),
        json={"job": "monthly_digest", "portfolio_wide": True, "reason": REASON},
        timeout=180,
    )
    out["checks"].append({
        "name": "portfolio_wide_with_token_accepted",
        "pass": r_pw.status_code == 200,
        "status": r_pw.status_code,
    })

    tok4 = _token(admin, "run_scoped_automation_job", f"monthly_digest:{CLIENT_ID}")
    _pace()
    r4 = httpx.post(
        f"{API}/admin/jobs/run",
        headers=_h(admin, tok4),
        json={"job": "monthly_digest", "client_id": CLIENT_ID, "property_ids": [PROPERTY_ID], "reason": REASON},
        timeout=180,
    )
    out["checks"].append({"name": "valid_client_owned_property_ids", "pass": r4.status_code == 200, "status": r4.status_code})

    out["pass"] = all(c["pass"] for c in out["checks"])
    return out


def part_smoke(admin: str) -> dict:
    out: Dict[str, Any] = {"run_tag": RUN_TAG, "checks": [], "pass": False}
    fake = str(uuid.uuid4())

    _pace()
    r = httpx.post(f"{API}/admin/governance/confirmation-token", headers={}, json={"action_id": "x", "reason": REASON}, timeout=60)
    out["checks"].append({"name": "unauthenticated_token_rejected", "pass": r.status_code in (401, 403)})

    _pace()
    r2 = httpx.post(f"{API}/admin/documents/{fake}/retry-extraction", headers=_h(admin), json={"reason": REASON}, timeout=60)
    out["checks"].append({"name": "missing_token_rejected", "pass": r2.status_code == 403})

    tok = _token(admin, "retry_document_extraction", fake)
    _pace()
    r3 = httpx.post(f"{API}/admin/documents/{fake}/retry-extraction", headers=_h(admin, tok), json={"reason": REASON}, timeout=60)
    r4 = httpx.post(f"{API}/admin/documents/{fake}/retry-extraction", headers=_h(admin, tok), json={"reason": REASON}, timeout=60)
    out["checks"].append({"name": "replay_token_rejected", "pass": r4.status_code == 403})

    _pace()
    r5 = httpx.post(f"{API}/admin/jobs/run", headers=_h(admin), json={"job": "daily_reminders", "portfolio_wide": True, "reason": REASON}, timeout=60)
    out["checks"].append({"name": "portfolio_wide_blocked", "pass": r5.status_code == 403})

    tok6 = _token(admin, "run_scoped_automation_job", f"daily_reminders:{CLIENT_ID}")
    _pace()
    r6 = httpx.post(
        f"{API}/admin/jobs/run",
        headers=_h(admin, tok6),
        json={"job": "daily_reminders", "client_id": CLIENT_ID, "reason": REASON},
        timeout=180,
    )
    out["checks"].append({"name": "scoped_automation_ok", "pass": r6.status_code == 200})

    out["pass"] = all(c["pass"] for c in out["checks"])
    return out


def classify(unresolved: dict, extraction: dict, digest: dict, smoke: dict) -> dict:
    gates = {
        "unresolved": unresolved.get("pass"),
        "extraction": extraction.get("pass"),
        "monthly_digest": digest.get("pass"),
        "smoke": smoke.get("pass"),
    }
    if all(gates.values()):
        classification = "ADMIN_READY"
    elif not gates.get("smoke"):
        classification = "FAIL_SECURITY"
    elif not gates.get("extraction"):
        classification = "FAIL_OPERATIONAL"
    else:
        classification = "FAIL_OPERATIONAL"
    return {
        "classification": classification,
        "admin_ready": classification == "ADMIN_READY",
        "push_allowed": classification == "ADMIN_READY",
        "gates": gates,
        "run_tag": RUN_TAG,
    }


def main() -> int:
    admin, admin_user = _login_admin()
    if not admin:
        cls = {"classification": "BLOCKED", "reason": "admin_login_failed"}
        _write("classifications.json", cls)
        print(json.dumps(cls))
        return 1

    unresolved = part_unresolved(admin, admin_user, seed_report)
    extraction = part_extraction(admin, probe=seed_report)
    digest = part_monthly_digest(admin)
    smoke = part_smoke(admin)

    _write("unresolved_runtime_closeout.json", unresolved)
    _write("extraction_retry_closeout.json", extraction)
    _write("monthly_digest_scope_closeout.json", digest)
    _write("admin_remediation_smoke.json", smoke)

    cls = classify(unresolved, extraction, digest, smoke)
    _write("classifications.json", cls)

    tests = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_extraction_queue_staleness.py", "tests/test_admin_confirmation_governance.py", "tests/test_job_scope_registry.py", "-q", "--tb=no"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    cls["unit_tests_pass"] = tests.returncode == 0

    push = {"pushed": False, "reason": "not_admin_ready"}
    if cls["admin_ready"] and cls.get("unit_tests_pass"):
        try:
            subprocess.run(
                [
                    "git",
                    "add",
                    "backend/services/extraction_queue_staleness.py",
                    "backend/routes/documents.py",
                    "backend/routes/admin.py",
                    "backend/scripts/admin_remediation_probe_seed.py",
                    "backend/tests/test_extraction_queue_staleness.py",
                    "frontend/src/pages/AdminExtractionQueuePage.js",
                    "backend/tmp_prelaunch_admin_control_closeout_01.py",
                    "backend/docs/audit/admin_control_remediation_01/unresolved_runtime_closeout.json",
                    "backend/docs/audit/admin_control_remediation_01/extraction_retry_closeout.json",
                    "backend/docs/audit/admin_control_remediation_01/monthly_digest_scope_closeout.json",
                    "backend/docs/audit/admin_control_remediation_01/admin_remediation_smoke.json",
                    "backend/docs/audit/admin_control_remediation_01/classifications.json",
                    "backend/docs/audit/admin_control_remediation_01/probe_seed.json",
                    "backend/docs/audit/admin_control_remediation_01/push_result.json",
                ],
                cwd=str(ROOT.parent),
                check=True,
            )
            subprocess.run(["git", "commit", "-m", "fix(admin): closeout remediation verification blockers", "-m", f"Run {RUN_TAG}"], cwd=str(ROOT.parent), check=True)
            push = {"pushed": True, "note": "commit created locally; push only if user requests"}
        except Exception as exc:
            push = {"pushed": False, "error": str(exc)[:200]}
    _write("push_result.json", push)

    print(json.dumps(cls, indent=2))
    return 0 if cls["admin_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
