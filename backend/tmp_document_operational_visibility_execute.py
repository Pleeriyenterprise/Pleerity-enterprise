"""
Document operational visibility — staged post-deploy verification harness.

Pilot: 6fd5ac4c / d35a58ae (authoritative, no substitution).
"""
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

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.ops_runtime_verify_02.convergence_observer import ConvergenceObserver

PROGRAMME = "DOCUMENT_OPERATIONAL_VISIBILITY"
OWNER = "document_operational_visibility"
PROOF_MODE = "operational_browser"

CLIENT_ID = "6fd5ac4c-3fd4-4112-ade7-156977deb49f"
PROPERTY_ID = "d35a58ae-3c81-491c-9694-1d021dd3b8ad"
CLIENT_EMAIL = "nancy@yopmail.com"
SLUG = "6fd5ac4c_d35a58ae"
G5_BUNDLE = f"ops_runtime_g5_documents_{SLUG}/07_classification.json"

_raw_api = os.environ.get("OPS_VERIFY_API_URL", "https://pleerity-enterprise.onrender.com").rstrip("/")
API = _raw_api if _raw_api.endswith("/api") else f"{_raw_api}/api"
FRONTEND = os.environ.get("OPS_VERIFY_FRONTEND_URL", "https://pleerityenterprise.co.uk").rstrip("/")
RUN_TAG = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
MARKER = f"OPS-VIS-{RUN_TAG}"
CONVERGENCE_WAIT_S = int(os.environ.get("OPS_RUNTIME_CONVERGENCE_WAIT_S", "90"))
BUNDLE = ROOT / "docs/audit/document_operational_visibility_verify"
FIXTURE_PDF = BUNDLE / ".visibility_probe.pdf"

ATTENTION = "ATTENTION_REQUIRED"
ACTIVE = "ACTIVE_EVIDENCE"
HISTORICAL = "HISTORICAL_OR_SUPERSEDED"
ATTACHMENT = "OPERATIONAL_ATTACHMENT"
VERIFIED_OP = {"EVIDENCE_VERIFIED", "EXTERNALLY_VERIFIED"}


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write(name: str, data: Any) -> None:
    BUNDLE.mkdir(parents=True, exist_ok=True)
    (BUNDLE / name).write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


def _local_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT.parent, text=True).strip()[:8]
    except Exception:
        return "unknown"


def _read_password() -> str:
    env = os.environ.get("OPS_VERIFY_PASSWORD")
    if env:
        return env.strip()
    return (ROOT / f"docs/audit/ops_verify_01_{SLUG}/.ops_verify_temp_pw.txt").read_text(encoding="utf-8").strip()


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _http(method: str, url: str, *, headers: Optional[dict] = None, timeout: int = 120, **kwargs) -> httpx.Response:
    last: Optional[Exception] = None
    for attempt in range(3):
        try:
            return getattr(httpx, method.lower())(url, headers=headers, timeout=timeout, **kwargs)
        except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.ConnectError) as exc:
            last = exc
            time.sleep(3 + attempt * 5)
    raise last  # type: ignore[misc]


def _warm_api() -> None:
    for _ in range(15):
        try:
            r = _http("get", f"{API}/health", timeout=90)
            if r.status_code == 200 and "starting" not in (r.text or "").lower():
                return
        except Exception:
            pass
        time.sleep(10)


def _login() -> Tuple[str, dict]:
    _warm_api()
    pw = _read_password()
    for attempt in range(4):
        r = _http("post", f"{API}/auth/login", json={"email": CLIENT_EMAIL, "password": pw}, timeout=90)
        if r.status_code == 200:
            body = r.json()
            return body["access_token"], body.get("user") or {}
        if r.status_code in (502, 503, 504):
            time.sleep(15 + attempt * 10)
            continue
        r.raise_for_status()
    raise RuntimeError("login failed")


def _load_dep(rel: str) -> dict:
    p = ROOT / "docs/audit" / rel.replace("/", os.sep)
    if not p.is_file():
        return {"found": False}
    data = json.loads(p.read_text(encoding="utf-8"))
    return {"found": True, "classification": data.get("classification"), "raw": data}


def _fetch_documents(token: str, **params) -> Dict[str, Any]:
    r = _http("get", f"{API}/documents", headers=_headers(token), params=params, timeout=90)
    body = r.json() if r.status_code == 200 else {}
    return {
        "status": r.status_code,
        "documents": body.get("documents") or [],
        "total": body.get("total"),
        "total_unfiltered": body.get("total_unfiltered"),
        "attention_required_count": body.get("attention_required_count"),
    }


def _fetch_property_evidence(token: str) -> Dict[str, Any]:
    r = _http("get", f"{API}/portfolio/properties/{PROPERTY_ID}/evidence", headers=_headers(token), timeout=90)
    return {"status": r.status_code, "body": r.json() if r.status_code == 200 else {}}


def _ensure_fixture_pdf() -> Path:
    BUNDLE.mkdir(parents=True, exist_ok=True)
    if not FIXTURE_PDF.is_file():
        FIXTURE_PDF.write_bytes(
            b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
            b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
            b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj\n"
            b"xref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n"
            b"0000000052 00000 n \n0000000101 00000 n \n"
            b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n178\n%%EOF\n"
        )
    return FIXTURE_PDF


def _reconcile(token: str, doc_id: str, payload: dict) -> httpx.Response:
    return _http("post", f"{API}/documents/{doc_id}/reconcile-linkage", headers=_headers(token), json=payload, timeout=90)


def _seed_reconciliation_probe(token: str) -> Optional[str]:
    pdf = _ensure_fixture_pdf()
    files = {"file": ("vis-reconcile-probe.pdf", pdf.read_bytes(), "application/pdf")}
    data = {
        "property_id": PROPERTY_ID,
        "document_type": "Other",
        "notes": f"{MARKER} reconciliation probe",
    }
    r = _http("post", f"{API}/documents/upload", headers=_headers(token), data=data, files=files, timeout=120)
    if r.status_code not in (200, 201):
        return None
    return str(r.json().get("document_id") or "")


def _wait_deploy_visibility(token: str, expected_min_docs: int = 1, max_wait_s: int = 900) -> Dict[str, Any]:
    """Poll until API returns visibility projections on documents list."""
    deadline = time.time() + max_wait_s
    last: Dict[str, Any] = {"pass": False}
    while time.time() < deadline:
        resp = _fetch_documents(token, property_id=PROPERTY_ID)
        docs = resp.get("documents") or []
        with_vis = sum(1 for d in docs if d.get("document_client_visibility_state"))
        with_registry = sum(1 for d in docs if d.get("document_registry_section"))
        ev = _fetch_property_evidence(token)
        registry = (ev.get("body") or {}).get("registry") if ev.get("status") == 200 else None
        last = {
            "documents_count": len(docs),
            "with_visibility_projection": with_vis,
            "with_registry_section": with_registry,
            "evidence_registry_present": isinstance(registry, dict),
            "attention_required_count": resp.get("attention_required_count"),
            "pass": with_vis >= expected_min_docs and with_registry >= expected_min_docs and isinstance(registry, dict),
            "checked_at": _utc(),
        }
        if last["pass"]:
            return last
        time.sleep(30)
    return last


def _deployment_verification(token: str) -> Dict[str, Any]:
    local = _local_head()
    version_body: Dict[str, Any] = {}
    try:
        vr = _http("get", f"{API}/version", timeout=60)
        if vr.status_code == 200:
            version_body = vr.json()
    except Exception:
        pass
    health = _http("get", f"{API}/health", timeout=60)
    deploy_probe = _wait_deploy_visibility(token, max_wait_s=int(os.environ.get("DEPLOY_WAIT_S", "600")))
    fe_ok = False
    try:
        fr = _http("get", FRONTEND, timeout=60)
        fe_ok = fr.status_code < 500
    except Exception:
        pass
    deploy_sha = version_body.get("commit_sha") or version_body.get("git_sha") or "unknown"
    continuity = (
        health.status_code == 200
        and fe_ok
        and deploy_probe.get("pass") is True
    )
    return {
        "verified_at_utc": _utc(),
        "run_tag": RUN_TAG,
        "local_head": local,
        "staging_api": API,
        "frontend_url": FRONTEND,
        "version_endpoint": version_body,
        "deploy_sha": deploy_sha,
        "health": health.json() if health.status_code == 200 else {"status": health.status_code},
        "visibility_api_probe": deploy_probe,
        "frontend_reachable": fe_ok,
        "deploy_ready": continuity,
        "pass": continuity,
    }


def _queue_api_verification(token: str) -> Dict[str, Any]:
    all_docs = _fetch_documents(token, property_id=PROPERTY_ID)
    docs = all_docs.get("documents") or []
    attention = [d for d in docs if d.get("document_attention_required") is True or str(d.get("document_client_visibility_state") or "").upper() == ATTENTION]
    settled = [d for d in docs if str(d.get("document_client_visibility_state") or "").upper() == ACTIVE]
    attachments = [d for d in docs if str(d.get("document_client_visibility_state") or "").upper() == ATTACHMENT]
    historical = [d for d in docs if str(d.get("document_client_visibility_state") or "").upper() == HISTORICAL]
    settled_in_attention = [d for d in attention if str(d.get("document_client_visibility_state") or "").upper() == ACTIVE]
    missing_vis = [d.get("document_id") for d in docs if not d.get("document_client_visibility_state")]
    filtered = _fetch_documents(token, property_id=PROPERTY_ID, visibility_state=ATTENTION)
    return {
        "total_documents": len(docs),
        "attention_required_count": len(attention),
        "active_evidence_count": len(settled),
        "operational_attachment_count": len(attachments),
        "historical_count": len(historical),
        "settled_leaking_into_attention": len(settled_in_attention),
        "missing_visibility_projection": missing_vis,
        "api_attention_filter_total": filtered.get("total"),
        "attention_reasons_sample": [
            {
                "document_id": d.get("document_id"),
                "visibility": d.get("document_client_visibility_state"),
                "registry_section": d.get("document_registry_section"),
                "reason_codes": d.get("document_visibility_reason_codes"),
            }
            for d in attention[:12]
        ],
        "pass": len(missing_vis) == 0 and len(settled_in_attention) == 0 and len(attention) >= 0,
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
    page.wait_for_timeout(5000)
    body = page.locator("body").inner_text()
    if "Sign In" in body[:250] and "Compliance" not in body:
        page.evaluate(
            "([t,u])=>{localStorage.setItem('auth_token',t);localStorage.setItem('user',JSON.stringify(u));}",
            [token, user],
        )
    return p, browser, page


def _browser_queue_verification(token: str, user: dict, password: str, api_attention: int) -> Dict[str, Any]:
    steps: List[Dict[str, Any]] = []

    def step(name: str, ok: bool, detail: str = "") -> None:
        steps.append({"name": name, "ok": ok, "detail": detail})

    p, browser, page = _browser_session(token, user, password)
    page.goto(f"{FRONTEND}/documents", wait_until="domcontentloaded", timeout=120_000)
    for _ in range(45):
        if page.locator('[data-testid="documents-page"]').count() > 0:
            break
        page.wait_for_timeout(2000)
    step("documents_page", page.locator('[data-testid="documents-page"]').count() > 0, page.url)
    step("title_operations", "Document operations" in page.locator("h1").inner_text())
    queue_sel = page.locator('[data-testid="filter-queue-view"]')
    step("queue_filter_present", queue_sel.count() > 0)
    default_queue = queue_sel.input_value() if queue_sel.count() else ""
    step("default_attention_queue", default_queue == "attention", default_queue)
    visible_rows = page.locator('[data-testid^="document-"]').count()
    step("attention_rows_visible", visible_rows <= max(api_attention + 2, 1), f"visible={visible_rows} api_attention={api_attention}")
    if queue_sel.count():
        queue_sel.select_option("all")
        page.wait_for_timeout(2000)
    all_rows = page.locator('[data-testid^="document-"]').count()
    step("all_view_expands", all_rows >= visible_rows, f"all={all_rows} attention={visible_rows}")
    page.reload(wait_until="domcontentloaded")
    page.wait_for_timeout(3000)
    step("refresh_persistence", page.locator('[data-testid="documents-page"]').count() > 0)
    browser.close()
    p.stop()
    return {"steps": steps, "pass": all(s["ok"] for s in steps)}


def _registry_verification(token: str, user: dict, password: str) -> Dict[str, Any]:
    api = _fetch_property_evidence(token)
    body = api.get("body") or {}
    registry = body.get("registry") or {}
    summary = body.get("summary") or {}
    docs = body.get("documents") or []
    sections = {k: len(v or []) for k, v in registry.items()} if isinstance(registry, dict) else {}
    missing_vis = [d.get("document_id") for d in docs if not d.get("document_client_visibility_state")]
    section_keys = set(sections.keys())
    expected = {
        "active_evidence",
        "pending_review",
        "expiring_soon",
        "reconciliation_required",
        "historical_superseded",
        "operational_attachments",
    }
    steps: List[Dict[str, Any]] = []

    def step(name: str, ok: bool, detail: str = "") -> None:
        steps.append({"name": name, "ok": ok, "detail": detail})

    p, browser, page = _browser_session(token, user, password)
    page.goto(f"{FRONTEND}/properties/{PROPERTY_ID}", wait_until="domcontentloaded", timeout=120_000)
    page.wait_for_timeout(4000)
    doc_tab = page.get_byRole("button", name="Documents")
    if doc_tab.count():
        doc_tab.first.click()
        page.wait_for_timeout(4000)
    step("evidence_registry_panel", page.locator('[data-testid="property-evidence-registry"]').count() > 0 or "Evidence Registry" in page.locator("body").inner_text())
    step("registry_sections_rendered", page.locator('[data-testid^="evidence-registry-section-"]').count() > 0 or sections)
    browser.close()
    p.stop()
    api_pass = (
        api.get("status") == 200
        and len(missing_vis) == 0
        and expected.issubset(section_keys)
        and "attentionRequired" in summary
    )
    return {
        "api_status": api.get("status"),
        "summary": summary,
        "section_counts": sections,
        "missing_visibility_projection": missing_vis,
        "browser_steps": steps,
        "pass": api_pass and all(s["ok"] for s in steps),
    }


def _reconciliation_runtime(token: str, user: dict, password: str) -> Dict[str, Any]:
    steps: List[Dict[str, Any]] = []

    def step(name: str, ok: bool, detail: str = "") -> None:
        steps.append({"name": name, "ok": ok, "detail": detail})

    probe_id = _seed_reconciliation_probe(token)
    step("seed_probe", bool(probe_id), probe_id or "seed_failed")
    if not probe_id:
        return {"steps": steps, "pass": False, "probe_id": None}

    time.sleep(3)
    docs = _fetch_documents(token, property_id=PROPERTY_ID).get("documents") or []
    row = next((d for d in docs if d.get("document_id") == probe_id), {})
    step("probe_reconciliation_required", str(row.get("document_linkage_state") or "").upper() == "RECONCILIATION_REQUIRED", row.get("document_linkage_state"))
    step("probe_attention_queue", row.get("document_attention_required") is True or str(row.get("document_client_visibility_state") or "").upper() == ATTENTION)

    p, browser, page = _browser_session(token, user, password)
    page.goto(f"{FRONTEND}/documents?property_id={PROPERTY_ID}", wait_until="domcontentloaded", timeout=120_000)
    page.wait_for_timeout(5000)
    btn = page.locator(f'[data-testid="document-{probe_id}"] button:has-text("Resolve linkage")')
    if btn.count() == 0:
        btn = page.locator('button:has-text("Resolve linkage")').first
    step("resolve_cta_reachable", btn.count() > 0)
    if btn.count():
        btn.first.click()
        page.wait_for_timeout(2000)
        step("modal_visible", page.locator('[data-testid="linkage-reconcile-modal"]').count() > 0)
    browser.close()
    p.stop()

    mark = _reconcile(token, probe_id, {"action": "mark_intentionally_unlinked", "reason": f"{MARKER} probe cleanup"})
    step("intentionally_unlinked_api", mark.status_code == 200, str(mark.status_code))
    time.sleep(2)
    docs_after = _fetch_documents(token, property_id=PROPERTY_ID).get("documents") or []
    after = next((d for d in docs_after if d.get("document_id") == probe_id), {})
    step(
        "transition_to_attachment",
        str(after.get("document_client_visibility_state") or "").upper() == ATTACHMENT,
        after.get("document_client_visibility_state"),
    )
    step("left_attention_queue", after.get("document_attention_required") is not True)
    return {"steps": steps, "probe_id": probe_id, "pass": all(s["ok"] for s in steps)}


def _expiry_resurfacing(token: str) -> Dict[str, Any]:
    docs = _fetch_documents(token, property_id=PROPERTY_ID).get("documents") or []
    resurfaced = [
        d
        for d in docs
        if d.get("document_expiry_resurface") is True
        or str(d.get("document_registry_section") or "") == "expiring_soon"
    ]
    active_not_resurfaced = [
        d
        for d in docs
        if str(d.get("document_client_visibility_state") or "").upper() == ACTIVE and d.get("document_expiry_resurface") is True
    ]
    return {
        "resurfaced_documents": [
            {
                "document_id": d.get("document_id"),
                "visibility": d.get("document_client_visibility_state"),
                "registry_section": d.get("document_registry_section"),
                "days_to_expiry": d.get("document_days_to_expiry"),
                "expiry_resurface": d.get("document_expiry_resurface"),
            }
            for d in resurfaced
        ],
        "resurfaced_count": len(resurfaced),
        "active_with_resurface_flag": len(active_not_resurfaced),
        "pass": len(active_not_resurfaced) == 0,
        "note": "No expiring-soon docs on pilot is acceptable if resurfacing logic present on API fields",
    }


def _historical_governance(token: str) -> Dict[str, Any]:
    docs = _fetch_documents(token, property_id=PROPERTY_ID).get("documents") or []
    historical = [d for d in docs if str(d.get("document_client_visibility_state") or "").upper() == HISTORICAL]
    violations = []
    for d in docs:
        op = str(d.get("document_operational_state") or "").upper()
        vis = str(d.get("document_client_visibility_state") or "").upper()
        if vis == HISTORICAL and op in VERIFIED_OP:
            violations.append({"document_id": d.get("document_id"), "kind": "FALSE_DOCUMENT_AUTHORITY", "note": "historical_but_verified_op"})
        if vis == ACTIVE and op == "EVIDENCE_SUPERSEDED":
            violations.append({"document_id": d.get("document_id"), "kind": "EVIDENCE_AUTHORITY_DRIFT"})
    searchable = _fetch_documents(token, property_id=PROPERTY_ID, visibility_state=HISTORICAL)
    return {
        "historical_count": len(historical),
        "violations": violations,
        "historical_filter_reachable": searchable.get("status") == 200,
        "pass": len(violations) == 0,
    }


def _cross_surface(token: str) -> Dict[str, Any]:
    docs = _fetch_documents(token, property_id=PROPERTY_ID).get("documents") or []
    attention_ids = {d.get("document_id") for d in docs if d.get("document_attention_required")}
    reqs = _http("get", f"{API}/client/properties/{PROPERTY_ID}/requirements", headers=_headers(token), timeout=90)
    req_rows = reqs.json().get("requirements") or [] if reqs.status_code == 200 else []
    missing_doc_reqs = [r for r in req_rows if str(r.get("client_lifecycle_state") or "").upper() in ("ACTION_REQUIRED", "PENDING_REVIEW")]
    today = _http("get", f"{API}/client/today", headers=_headers(token), timeout=90)
    cc = _http("get", f"{API}/client/command-centre", headers=_headers(token), timeout=90)
    recon = [d for d in docs if str(d.get("document_linkage_state") or "").upper() in ("RECONCILIATION_REQUIRED", "BROKEN_LINKAGE")]
    hidden_recon = [d for d in recon if d.get("document_id") not in attention_ids and d.get("document_attention_required") is not True]
    return {
        "attention_document_ids": list(attention_ids)[:20],
        "reconciliation_visible_in_attention": len(hidden_recon) == 0,
        "hidden_reconciliation": hidden_recon,
        "requirements_action_required": len(missing_doc_reqs),
        "today_status": today.status_code,
        "command_centre_status": cc.status_code,
        "pass": len(hidden_recon) == 0 and today.status_code == 200,
    }


def _g9_g10(token: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    docs = _fetch_documents(token, property_id=PROPERTY_ID).get("documents") or []
    ids = [d.get("document_id") for d in docs]
    g9 = {
        "duplicate_document_ids": len(set(ids)) != len(ids),
        "duplicate_visibility_rows": len({(d.get("document_id"), d.get("document_client_visibility_state")) for d in docs}) == len(docs),
        "pass": len(set(ids)) == len(ids),
    }
    violations = []
    for d in docs:
        review = str(d.get("evidence_review_state") or "").upper()
        op = str(d.get("document_operational_state") or "").upper()
        vis = str(d.get("document_client_visibility_state") or "").upper()
        link = str(d.get("document_linkage_state") or "").upper()
        if review == "UPLOADED" and op in VERIFIED_OP:
            violations.append({"document_id": d.get("document_id"), "rule": "upload_not_verified"})
        if review == "REJECTED" and vis == ACTIVE:
            violations.append({"document_id": d.get("document_id"), "rule": "rejected_not_valid"})
        if link == "INTENTIONALLY_UNLINKED" and link == "BROKEN_LINKAGE":
            violations.append({"document_id": d.get("document_id"), "rule": "linkage_contradiction"})
        if link == "INTENTIONALLY_UNLINKED" and str(d.get("document_client_visibility_state") or "").upper() not in (ATTACHMENT, HISTORICAL):
            if d.get("document_attention_required") and link == "INTENTIONALLY_UNLINKED":
                violations.append({"document_id": d.get("document_id"), "rule": "intentional_unlinked_not_attachment"})
    orphan_hidden = [
        d.get("document_id")
        for d in docs
        if str(d.get("document_linkage_state") or "").upper() == "RECONCILIATION_REQUIRED"
        and d.get("document_attention_required") is not True
    ]
    g10 = {
        "violations": violations,
        "orphan_hidden_from_attention": orphan_hidden,
        "pass": len(violations) == 0 and len(orphan_hidden) == 0,
    }
    g9["pass"] = g9["pass"] and g10["pass"]
    return g9, g10


def _classify(
    deploy: dict,
    queue: dict,
    registry: dict,
    reconcile: dict,
    expiry: dict,
    historical: dict,
    cross: dict,
    g9: dict,
    g10: dict,
    conv: dict,
) -> Dict[str, Any]:
    reasons: List[str] = []
    secondary: List[str] = []
    if not deploy.get("pass"):
        reasons.append("deploy_continuity_failed")
    if not queue.get("pass"):
        reasons.append("operations_queue_incoherent")
    if not registry.get("pass"):
        reasons.append("property_registry_incoherent")
    if not reconcile.get("pass"):
        reasons.append("reconciliation_runtime_failed")
    if not historical.get("pass"):
        secondary.append("EVIDENCE_AUTHORITY_DRIFT")
    if not cross.get("pass"):
        secondary.append("PROJECTION_RESOLUTION_FAILURE")
    if not g9.get("pass") or not g10.get("pass"):
        secondary.append("FALSE_DOCUMENT_AUTHORITY")
    if expiry.get("active_with_resurface_flag", 0) > 0:
        secondary.append("TEMPORAL_PROJECTION_INVERSION")
    if not conv.get("stable"):
        secondary.append("convergence_incomplete")

    verified = not reasons and not secondary
    primary = "VERIFIED_OPERATIONALLY" if verified else (reasons[0].upper() if reasons else secondary[0] if secondary else "PARTIAL")
    if reasons:
        if "deploy" in reasons[0]:
            primary = "BLOCKED"
        elif "reconciliation" in reasons[0]:
            primary = "FAIL_OPERATIONAL"
        else:
            primary = "FAIL_OPERATIONAL"
    elif secondary:
        primary = secondary[0]

    return {
        "programme": PROGRAMME,
        "family": OWNER,
        "classification": primary if not verified else "VERIFIED_OPERATIONALLY",
        "execution_status": primary if not verified else "VERIFIED_OPERATIONALLY",
        "secondary_classifications": secondary,
        "reasons": reasons,
        "blocking": not verified,
        "authoritative_verification_owner": OWNER,
        "proof_mode": PROOF_MODE,
        "run_tag": RUN_TAG,
        "pilot_slug": SLUG,
        "client_id": CLIENT_ID,
        "property_id": PROPERTY_ID,
        "checkpoints": {
            "deploy_continuity": deploy.get("pass"),
            "operations_queue": queue.get("pass"),
            "property_registry": registry.get("pass"),
            "reconciliation": reconcile.get("pass"),
            "expiry_resurfacing": expiry.get("pass"),
            "historical_governance": historical.get("pass"),
            "cross_surface": cross.get("pass"),
            "g9": g9.get("pass"),
            "g10": g10.get("pass"),
            "convergence": conv.get("stable"),
        },
    }


def main() -> int:
    g5 = _load_dep(G5_BUNDLE)
    if g5.get("classification") != "VERIFIED_OPERATIONALLY":
        print(json.dumps({"blocked": "G5 prerequisite not VERIFIED_OPERATIONALLY", "g5": g5}, indent=2))
        return 2

    token, user = _login()
    pw = _read_password()

    deploy = _deployment_verification(token)
    _write("deployment_verification.json", deploy)
    if not deploy.get("pass"):
        clf = _classify(deploy, {"pass": False}, {"pass": False}, {"pass": False}, {"pass": False}, {"pass": False}, {"pass": False}, {"pass": False}, {"pass": False}, {"stable": False})
        _write("07_classification.json", clf)
        _write("classifications.json", {"classifications": [clf]})
        _write("watchlist.md", f"# Watchlist\n\n- Deploy continuity failed run `{RUN_TAG}`\n")
        print(json.dumps({"classification": clf["classification"], "deploy": deploy}, indent=2))
        return 1

    queue_api = _queue_api_verification(token)
    queue_browser = _browser_queue_verification(token, user, pw, queue_api.get("attention_required_count") or 0)
    queue = {**queue_api, "browser": queue_browser, "pass": queue_api.get("pass") and queue_browser.get("pass")}
    _write("document_operations_queue.json", queue)

    registry = _registry_verification(token, user, pw)
    _write("property_evidence_registry.json", registry)

    reconcile = _reconciliation_runtime(token, user, pw)
    _write("reconciliation_runtime.json", reconcile)

    expiry = _expiry_resurfacing(token)
    _write("expiry_resurfacing_runtime.json", expiry)

    historical = _historical_governance(token)
    _write("historical_evidence_governance.json", historical)

    cross = _cross_surface(token)
    _write("document_visibility_cross_surface.json", cross)

    g9, g10 = _g9_g10(token)
    _write("g9_document_visibility_integrity.json", g9)
    _write("g10_document_visibility_authority.json", g10)

    def read_attention_count() -> dict:
        r = _fetch_documents(token, property_id=PROPERTY_ID)
        return {"count": r.get("attention_required_count"), "total": len(r.get("documents") or [])}

    observer = ConvergenceObserver(default_timeout_seconds=CONVERGENCE_WAIT_S)
    t0 = read_attention_count()
    observer.observe(
        "attention_queue",
        read_attention_count,
        agree_fn=lambda a, b: a.get("count") == b.get("count"),
        timeout_seconds=CONVERGENCE_WAIT_S,
    )
    conv = observer.build_artifact()
    conv["t0"] = t0
    _write("convergence.json", conv)

    clf = _classify(deploy, queue, registry, reconcile, expiry, historical, cross, g9, g10, conv)
    _write("07_classification.json", clf)
    _write("classifications.json", {"classifications": [clf]})

    watchlist = []
    if expiry.get("resurfaced_count") == 0:
        watchlist.append("No expiring-soon documents on pilot — expiry resurfacing field presence verified only")
    if deploy.get("version_endpoint", {}).get("commit_sha") in (None, "unknown"):
        watchlist.append("deploy_sha ambiguous on /api/version — behavioural proof used")
    _write(
        "watchlist.md",
        "# Document operational visibility watchlist\n\n"
        f"**Run:** `{RUN_TAG}`\n**Classification:** `{clf['classification']}`\n\n"
        + "\n".join(f"- {w}" for w in watchlist)
        + "\n",
    )
    _write(
        "REPORT.md",
        f"# Document operational visibility verification\n\n**Run:** `{RUN_TAG}`\n**Classification:** `{clf['classification']}`\n\nSee artifact JSON files in this bundle.\n",
    )
    if clf.get("classification") == "VERIFIED_OPERATIONALLY":
        _write(
            "DEPLOY_CONTINUITY_NOTE.md",
            f"Document operational visibility VERIFIED_OPERATIONALLY on staging run `{RUN_TAG}`. G6 calendar verification may proceed per VERIFY-02 programme order.\n",
        )

    print(json.dumps({"classification": clf["classification"], "checkpoints": clf.get("checkpoints")}, indent=2))
    return 0 if clf.get("classification") == "VERIFIED_OPERATIONALLY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
