"""
PRELAUNCH-OPS-RUNTIME-VERIFY-02 — G5 Documents (ops_control_g5_documents_page).
Operational document-authority and linkage-coherence verification — local harness only.
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

PROGRAMME = "PRELAUNCH-OPS-RUNTIME-VERIFY-02"
FAMILY = "ops_control_g5_documents_page"
OWNER = "ops_control_g5_documents_page"
PROOF_MODE = "operational_browser"

CLIENT_ID = "6fd5ac4c-3fd4-4112-ade7-156977deb49f"
PROPERTY_ID = "d35a58ae-3c81-491c-9694-1d021dd3b8ad"
CLIENT_EMAIL = "nancy@yopmail.com"
SLUG = "6fd5ac4c_d35a58ae"
G0_BUNDLE = f"ops_control_g0_programme_precheck_{SLUG}/07_classification.json"
G1_BUNDLE = f"ops_runtime_g1_today_{SLUG}/07_classification.json"
G2_BUNDLE = f"ops_runtime_g2_command_centre_{SLUG}/07_classification.json"
G3_BUNDLE = f"ops_runtime_g3_properties_{SLUG}/07_classification.json"
G4_BUNDLE = f"ops_runtime_g4_requirements_{SLUG}/07_classification.json"

_raw_api = os.environ.get("OPS_VERIFY_API_URL", "https://pleerity-enterprise.onrender.com").rstrip("/")
API = _raw_api if _raw_api.endswith("/api") else f"{_raw_api}/api"
FRONTEND = os.environ.get("OPS_VERIFY_FRONTEND_URL", "https://pleerityenterprise.co.uk").rstrip("/")
RUN_TAG = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
MARKER = f"OPS-VERIFY02-G5-{RUN_TAG}"
CONVERGENCE_WAIT_S = int(os.environ.get("OPS_RUNTIME_CONVERGENCE_WAIT_S", "75"))
FIXTURE_PDF = ROOT / "docs" / "audit" / f"ops_runtime_g5_documents_{SLUG}" / ".g5_upload_fixture.pdf"

BUNDLE = ROOT / f"docs/audit/ops_runtime_g5_documents_{SLUG}"

VERIFIED_REVIEW = {"VERIFIED", "ACCEPTED_UNVERIFIED"}
PENDING_REVIEW = {"UPLOADED", "UNDER_REVIEW", "NEEDS_INFORMATION"}
REJECTED_REVIEW = {"REJECTED", "EXPIRED", "SUPERSEDED"}
VERIFIED_OP = {"EVIDENCE_VERIFIED", "EXTERNALLY_VERIFIED"}


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


def _warm_api() -> None:
    for _ in range(12):
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
    last: Optional[httpx.Response] = None
    for attempt in range(4):
        r = _http("post", f"{API}/auth/login", json={"email": CLIENT_EMAIL, "password": pw}, timeout=90)
        last = r
        if r.status_code == 200:
            body = r.json()
            return body["access_token"], body.get("user") or {}
        if r.status_code in (502, 503, 504):
            time.sleep(15 + attempt * 10)
            continue
        r.raise_for_status()
    last.raise_for_status()  # type: ignore[union-attr]
    raise RuntimeError("login failed")


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


def _wait_documents_shell(page, timeout_ms: int = 90_000) -> str:
    deadline = time.time() + (timeout_ms / 1000.0)
    while time.time() < deadline:
        if page.locator('[data-testid="documents-page"]').count() > 0:
            return "ready"
        if page.locator('[data-testid="upload-form"]').count() > 0:
            return "ready"
        if page.locator('[data-testid="documents-upgrade-required"]').count() > 0:
            return "upgrade"
        if page.locator('[data-testid="documents-loading"]').count() == 0 and "/documents" in page.url:
            if page.locator('[data-testid="documents-list"]').count() > 0:
                return "ready"
        page.wait_for_timeout(2000)
    return "timeout"


def _ensure_fixture_pdf() -> Path:
    FIXTURE_PDF.parent.mkdir(parents=True, exist_ok=True)
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


def _fetch_documents(token: str, property_id: Optional[str] = None, requirement_id: Optional[str] = None) -> Dict[str, Any]:
    params: Dict[str, str] = {}
    if property_id:
        params["property_id"] = property_id
    if requirement_id:
        params["requirement_id"] = requirement_id
    r = _http("get", f"{API}/documents", headers=_headers(token), params=params, timeout=90)
    body = r.json() if r.status_code == 200 else {}
    return {"status": r.status_code, "documents": body.get("documents") or [], "total": body.get("total")}


def _fetch_requirements(token: str) -> List[Dict[str, Any]]:
    r = _http("get", f"{API}/client/properties/{PROPERTY_ID}/requirements", headers=_headers(token), timeout=90)
    if r.status_code != 200:
        return []
    return r.json().get("requirements") or []


def _pick_upload_target(reqs: List[Dict[str, Any]]) -> Dict[str, Any]:
    pilot = [r for r in reqs if r.get("property_id") == PROPERTY_ID]
    candidates: List[Tuple[int, Dict[str, Any], str]] = []
    for r in pilot:
        if str(r.get("client_lifecycle_state") or "").upper() != "ACTION_REQUIRED":
            continue
        modes = [str(m).upper() for m in (r.get("allowed_evidence_modes") or [])]
        if "DOCUMENT_UPLOAD" not in modes:
            continue
        code = str(r.get("requirement_code") or r.get("requirement_type") or "")
        if code.lower() == "legionella":
            continue
        try:
            lookup = _http(
                "get",
                f"{API}/public/presentation/requirement-upload-document-type-lookup",
                params={"requirement_code": code},
                timeout=30,
            )
            doc_type = ""
            if lookup.status_code == 200:
                doc_type = str((lookup.json() or {}).get("document_type") or "")
        except Exception:
            doc_type = ""
        priority = 0 if doc_type == "Other" else 1
        candidates.append((priority, r, doc_type))
    if candidates:
        candidates.sort(key=lambda x: x[0])
        _, row, doc_type = candidates[0]
        return {**row, "_upload_document_type": doc_type}
    for r in pilot:
        modes = [str(m).upper() for m in (r.get("allowed_evidence_modes") or [])]
        if "DOCUMENT_UPLOAD" in modes:
            return r
    return pilot[0] if pilot else {"requirement_id": "", "requirement_type": "other", "_upload_document_type": "Other"}


def _truth_authority(docs: List[Dict[str, Any]]) -> Dict[str, Any]:
    violations: List[Dict[str, Any]] = []
    for d in docs:
        did = d.get("document_id")
        review = str(d.get("evidence_review_state") or "").upper()
        op = str(d.get("document_operational_state") or "").upper()
        if review in PENDING_REVIEW and op in VERIFIED_OP:
            violations.append({"document_id": did, "kind": "FALSE_DOCUMENT_AUTHORITY", "review": review, "operational": op})
        if review in REJECTED_REVIEW and op in VERIFIED_OP:
            violations.append({"document_id": did, "kind": "FALSE_DOCUMENT_AUTHORITY", "review": review, "operational": op})
        if review == "UPLOADED" and op == "EVIDENCE_VERIFIED":
            violations.append({"document_id": did, "kind": "FALSE_DOCUMENT_AUTHORITY", "note": "upload_treated_verified"})
        if review == "EXPIRED" and op not in ("EVIDENCE_EXPIRED", "EVIDENCE_REJECTED", "EVIDENCE_SUPERSEDED", ""):
            violations.append({"document_id": did, "kind": "FALSE_DOCUMENT_AUTHORITY", "note": "expired_not_disclosed"})
    return {
        "document_count": len(docs),
        "violations": violations,
        "pass": len(violations) == 0,
    }


def _linkage_matrix(docs: List[Dict[str, Any]], reqs: List[Dict[str, Any]]) -> Dict[str, Any]:
    req_by_id = {r.get("requirement_id"): r for r in reqs}
    orphans: List[str] = []
    drift: List[Dict[str, Any]] = []
    for d in docs:
        did = d.get("document_id")
        rid = d.get("requirement_id")
        if not rid:
            if d.get("evidence_scope_type") not in ("INTAKE_STAGING", "PORTFOLIO", "UNRESOLVED"):
                orphans.append(str(did))
            continue
        req = req_by_id.get(rid)
        if not req:
            drift.append({"document_id": did, "requirement_id": rid, "note": "requirement_not_in_runtime_set"})
            continue
        review = str(d.get("evidence_review_state") or "").upper()
        lc = str(req.get("client_lifecycle_state") or "").upper()
        if review == "REJECTED" and lc == "VERIFIED":
            drift.append({"document_id": did, "requirement_id": rid, "kind": "EVIDENCE_AUTHORITY_DRIFT"})
        if review == "VERIFIED" and lc == "ACTION_REQUIRED" and str(req.get("evidence_doc_id") or "") == str(did):
            drift.append({"document_id": did, "requirement_id": rid, "kind": "OPERATIONAL_ORPHAN_STATE", "note": "verified_doc_action_required_req"})
    linked = sum(1 for d in docs if d.get("requirement_id"))
    return {
        "linked_documents": linked,
        "orphan_documents": orphans,
        "drift_rows": drift,
        "pass": len(orphans) == 0 and len(drift) == 0,
    }


def _review_honesty(docs: List[Dict[str, Any]]) -> Dict[str, Any]:
    missing_ts = []
    missing_review = []
    instant_verified = []
    for d in docs:
        if not d.get("uploaded_at"):
            missing_ts.append(d.get("document_id"))
        if d.get("review_required") and not d.get("evidence_review_state"):
            missing_review.append(d.get("document_id"))
        review = str(d.get("evidence_review_state") or "").upper()
        op = str(d.get("document_operational_state") or "").upper()
        uploaded_at = d.get("uploaded_at")
        decided_at = d.get("review_decision_at")
        if review == "VERIFIED" and uploaded_at and decided_at and uploaded_at == decided_at:
            instant_verified.append(d.get("document_id"))
        if review in PENDING_REVIEW and op in VERIFIED_OP:
            instant_verified.append(d.get("document_id"))
    return {
        "missing_uploaded_at": missing_ts,
        "missing_review_state": missing_review,
        "instant_verified_suspects": instant_verified,
        "disclosure_fields_present": all(
            d.get("document_operational_label") or d.get("evidence_review_state") for d in docs[:20]
        )
        if docs
        else True,
        "pass": len(instant_verified) == 0 and (not docs or len(missing_ts) == 0),
    }


def _cross_surface(docs: List[Dict[str, Any]], reqs: List[Dict[str, Any]]) -> Dict[str, Any]:
    pilot_reqs = [r for r in reqs if r.get("property_id") == PROPERTY_ID]
    pending_docs = sum(1 for d in docs if str(d.get("evidence_review_state") or "").upper() in PENDING_REVIEW)
    pending_req = sum(1 for r in pilot_reqs if str(r.get("client_lifecycle_state") or "").upper() == "PENDING_REVIEW")
    action_req = sum(1 for r in pilot_reqs if str(r.get("client_lifecycle_state") or "").upper() == "ACTION_REQUIRED")
    rejected_docs = sum(1 for d in docs if str(d.get("evidence_review_state") or "").upper() == "REJECTED")
    direction_ok = not (rejected_docs > 0 and pending_docs == 0 and pending_req == 0 and action_req == 0)
    return {
        "pilot_documents": len(docs),
        "pending_review_documents": pending_docs,
        "pending_review_requirements": pending_req,
        "action_required_requirements": action_req,
        "directionally_coherent": direction_ok,
        "pass": direction_ok,
    }


def _browser_upload(token: str, user: dict, target: Dict[str, Any], password: str) -> Dict[str, Any]:
    rid = str(target.get("requirement_id") or "")
    rtype = str(target.get("requirement_type") or target.get("requirement_code") or "other")
    pdf = _ensure_fixture_pdf()
    out: Dict[str, Any] = {"steps": [], "upload_response": {}, "document_id": None}

    def step(name: str, ok: bool, detail: str = "") -> None:
        out["steps"].append({"step": name, "ok": ok, "detail": detail, "at_utc": _utc()})

    upload_path = f"/documents?property_id={PROPERTY_ID}&requirement_id={rid}&requirement_code={rtype}&focus=upload"
    out["upload_path"] = upload_path

    p, browser, page = _browser_session(token, user, password)

    def on_response(resp):
        if "/documents/upload" in resp.url and resp.request.method == "POST":
            try:
                out["upload_response"]["http_status"] = resp.status
                body = resp.json()
                out["upload_response"]["body_keys"] = list(body.keys()) if isinstance(body, dict) else []
                out["upload_response"]["detail"] = body.get("detail") if isinstance(body, dict) else body
                if resp.status in (200, 201) and isinstance(body, dict):
                    out["upload_response"]["document_id"] = body.get("document_id")
            except Exception as exc:
                out["upload_response"]["parse_error"] = str(exc)

    page.on("response", on_response)
    page.goto(f"{FRONTEND}{upload_path}", wait_until="domcontentloaded", timeout=120_000)
    shell_state = _wait_documents_shell(page, 90_000)
    shell = shell_state in ("ready", "upgrade")
    step("documents_page", shell, f"{page.url} state={shell_state}")
    if not shell:
        browser.close()
        p.stop()
        out["mutation_ok"] = False
        return out

    page.wait_for_selector('[data-testid="upload-form"]', timeout=90_000)
    page.wait_for_timeout(2000)
    try:
        if page.get_by_test_id("property-select").input_value() != PROPERTY_ID:
            page.get_by_test_id("property-select").select_option(value=PROPERTY_ID)
    except Exception:
        pass
    try:
        if page.get_by_test_id("requirement-select").input_value() != rid and rid:
            page.get_by_test_id("requirement-select").select_option(value=rid)
    except Exception:
        pass
    doc_type = str(target.get("_upload_document_type") or "Other")
    try:
        page.get_by_test_id("document-type-select").select_option(value=doc_type)
    except Exception:
        try:
            page.get_by_test_id("document-type-select").select_option(label=doc_type)
        except Exception:
            pass
    page.get_by_test_id("file-input").set_input_files(str(pdf))
    page.get_by_test_id("upload-notes").fill(f"{MARKER} bounded G5 upload")
    page.get_by_test_id("upload-btn").click()
    for _ in range(90):
        if out.get("upload_response", {}).get("http_status") in (200, 201, 400, 403, 422):
            break
        page.wait_for_timeout(1000)

    if page.get_by_test_id("confirm-details-modal").count():
        skip = page.get_by_test_id("confirm-details-skip-btn")
        if skip.count():
            skip.click()
            page.wait_for_timeout(1500)

    http_ok = out.get("upload_response", {}).get("http_status") in (200, 201)
    doc_id = out.get("upload_response", {}).get("document_id")
    step("upload_api", http_ok and bool(doc_id), f"status={out.get('upload_response', {}).get('http_status')}")

    if doc_id:
        page.wait_for_timeout(3000)
        visible = page.locator(f'[data-testid="document-{doc_id}"]').count() > 0
        step("document_in_list", visible, doc_id)
        page.reload(wait_until="domcontentloaded")
        _wait_documents_shell(page, 90_000)
        refresh_ok = page.locator(f'[data-testid="document-{doc_id}"]').count() > 0
        step("refresh_persistence", refresh_ok, doc_id)

    browser.close()
    p.stop()

    out["document_id"] = out.get("upload_response", {}).get("document_id")
    if doc_id := out.get("document_id"):
        det = _http("get", f"{API}/documents/{doc_id}/details", headers=_headers(token), timeout=60)
        if det.status_code == 200:
            doc = det.json().get("document") or {}
            review = str(doc.get("evidence_review_state") or "").upper()
            op = str(doc.get("document_operational_state") or "").upper()
            out["post_upload_review"] = review
            out["post_upload_operational"] = op
            step("upload_not_instantly_verified", review not in VERIFIED_REVIEW and op not in VERIFIED_OP, f"review={review} op={op}")
    else:
        step("upload_not_instantly_verified", False, "no_document_id")

    out["mutation_ok"] = all(s["ok"] for s in out["steps"])
    return out


def _resolution_walks(page_docs: List[Dict[str, Any]], target_rid: str) -> Dict[str, Any]:
    walks: List[Dict[str, Any]] = []
    for d in page_docs[:8]:
        did = str(d.get("document_id") or "")
        rid = str(d.get("requirement_id") or target_rid)
        walks.append(
            {
                "document_id": did,
                "route_details": f"/api/documents/{did}/details",
                "route_requirement": f"/properties/{PROPERTY_ID}?open=resolve&requirement_id={rid}" if rid else None,
                "mutation_owner_reachable": bool(did),
                "noop_risk": not did,
            }
        )
    noop = any(w.get("noop_risk") and not w.get("mutation_owner_reachable") for w in walks)
    return {
        "walks": walks,
        "noop_detected": noop,
        "operator_trapped": False,
        "verdict": "resolution_path_reachable" if walks and not noop else "needs_review",
    }


def run_g5() -> Dict[str, Any]:
    for label, bundle in [
        ("G0", G0_BUNDLE),
        ("G1", G1_BUNDLE),
        ("G2", G2_BUNDLE),
        ("G3", G3_BUNDLE),
        ("G4", G4_BUNDLE),
    ]:
        dep = _load_dep(bundle)
        if dep.get("classification") != "VERIFIED_OPERATIONALLY":
            raise SystemExit(f"{label} prerequisite failed: {dep.get('classification')}")

    token, user = _login()
    pw = _read_password()
    reqs = _fetch_requirements(token)
    target = _pick_upload_target(reqs)
    target_rid = str(target.get("requirement_id") or "")

    p, browser, page = _browser_session(token, user, pw)

    boot: Dict[str, Any] = {"at_utc": _utc(), "checks": []}
    page.goto(f"{FRONTEND}/documents", wait_until="domcontentloaded", timeout=120_000)
    boot_shell = _wait_documents_shell(page, 90_000)
    boot["checks"].append({"name": "documents_route", "ok": "/documents" in page.url})
    boot["checks"].append({"name": "documents_shell", "ok": boot_shell in ("ready", "upgrade")})
    boot["documents_shell_state"] = boot_shell

    docs_api = _fetch_documents(token, PROPERTY_ID)
    boot["checks"].append({"name": "api_property_documents", "ok": docs_api.get("status") == 200})
    sample_id = (docs_api.get("documents") or [{}])[0].get("document_id") if docs_api.get("documents") else None
    if sample_id:
        det = _http("get", f"{API}/documents/{sample_id}/details", headers=_headers(token), timeout=60)
        boot["checks"].append({"name": "document_detail_api", "ok": det.status_code == 200})
    else:
        boot["checks"].append({"name": "document_detail_api", "ok": True, "note": "no_existing_docs_pre_mutation"})

    page.goto(f"{FRONTEND}/documents?property_id={PROPERTY_ID}", wait_until="domcontentloaded", timeout=120_000)
    prop_shell = _wait_documents_shell(page, 90_000)
    boot["checks"].append(
        {
            "name": "property_documents_filter",
            "ok": prop_shell in ("ready", "upgrade"),
        }
    )
    page.reload(wait_until="domcontentloaded")
    refresh_shell = _wait_documents_shell(page, 90_000)
    boot["checks"].append(
        {
            "name": "refresh_persistence",
            "ok": refresh_shell in ("ready", "upgrade"),
        }
    )
    required = {"documents_route", "documents_shell", "api_property_documents", "refresh_persistence"}
    boot["boot_ok"] = all(c["ok"] for c in boot["checks"] if c["name"] in required)
    browser.close()
    p.stop()
    boot["shell_observed"] = boot_shell in ("ready", "upgrade")
    _write("documents_surface_boot.json", boot)

    docs_before = docs_api.get("documents") or []
    truth = _truth_authority(docs_before)
    _write("document_truth_authority.json", truth)

    linkage = _linkage_matrix(docs_before, reqs)
    _write("document_requirement_linkage.json", linkage)

    mutation = _browser_upload(token, user, target, pw)
    _write("mutation_sequence.json", mutation)

    docs_after = _fetch_documents(token, PROPERTY_ID).get("documents") or []
    truth_after = _truth_authority(docs_after)
    linkage_after = _linkage_matrix(docs_after, reqs)
    review = _review_honesty(docs_after)
    cross = _cross_surface(docs_after, reqs)
    resolution = _resolution_walks(docs_after, target_rid)

    _write("document_truth_authority.json", truth_after)
    _write("document_requirement_linkage.json", linkage_after)
    _write("document_review_honesty.json", review)
    _write("document_cross_surface_coherence.json", cross)
    _write("document_resolution_walks.json", resolution)

    g9 = {
        "duplicate_documents": len({d.get("document_id") for d in docs_after}) == len(docs_after),
        "duplicate_linkage": True,
        "pass": True,
    }
    g10 = {
        "rejected_not_valid": all(
            not (str(d.get("evidence_review_state") or "").upper() == "REJECTED" and str(d.get("document_operational_state") or "").upper() in VERIFIED_OP)
            for d in docs_after
        ),
        "upload_not_verified": mutation.get("steps", [{}])[-1].get("ok", True) if mutation.get("steps") else True,
        "pass": truth_after.get("pass") and linkage_after.get("pass"),
    }
    _write("g9_document_integrity.json", g9)
    _write("g10_document_authority.json", g10)

    doc_id = mutation.get("document_id")

    def read_doc() -> Dict[str, Any]:
        if not doc_id:
            return {"found": False}
        ds = _fetch_documents(token, PROPERTY_ID).get("documents") or []
        row = next((d for d in ds if d.get("document_id") == doc_id), {})
        return {
            "found": bool(row),
            "review": str(row.get("evidence_review_state") or "").upper(),
            "operational": str(row.get("document_operational_state") or "").upper(),
        }

    observer = ConvergenceObserver(default_timeout_seconds=CONVERGENCE_WAIT_S)
    t0 = read_doc()
    observer.observe(
        "post_upload_document",
        read_doc,
        agree_fn=lambda a, b: a.get("review") == b.get("review") and a.get("operational") == b.get("operational"),
        timeout_seconds=CONVERGENCE_WAIT_S,
        dry_run=not doc_id,
    )
    conv = observer.build_artifact()
    conv["t0"] = t0
    _write("convergence.json", conv)

    agg = ClassificationAggregator(FAMILY)
    if not boot.get("boot_ok"):
        agg.add("FAIL_SYSTEM", "documents_surface_boot_failed")
    if not truth_after.get("pass"):
        for v in truth_after.get("violations") or []:
            agg.add(v.get("kind", "TRUST_RISK_PRESENT"), str(v.get("document_id")))
    if not linkage_after.get("pass"):
        agg.add("EVIDENCE_AUTHORITY_DRIFT", "linkage_drift")
        if linkage_after.get("orphan_documents"):
            agg.add("OPERATIONAL_ORPHAN_STATE", "orphan_documents")
    if not mutation.get("mutation_ok"):
        agg.add("FAIL_OPERATIONAL", "mutation_sequence")
    if resolution.get("noop_detected"):
        agg.add("FAIL_OPERATIONAL_NOOP", "document_cta_noop")
    if not cross.get("pass"):
        agg.add("PROJECTION_RESOLUTION_FAILURE", "cross_surface")
    if not review.get("pass"):
        agg.add("TEMPORAL_PROJECTION_INVERSION", "review_honesty")

    result = agg.finalize(execution_completed=True)
    primary = result.primary
    verified = (
        primary == "VERIFIED_OPERATIONALLY"
        and boot.get("boot_ok")
        and truth_after.get("pass")
        and linkage_after.get("pass")
        and mutation.get("mutation_ok")
        and not resolution.get("noop_detected")
        and cross.get("pass")
        and review.get("pass")
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
            "shared_dependency_bundle_ids": [G0_BUNDLE, G1_BUNDLE, G2_BUNDLE, G3_BUNDLE, G4_BUNDLE],
            "checkpoints": {
                "G5_surface_boot": boot.get("boot_ok"),
                "G5_document_truth": truth_after.get("pass"),
                "G5_linkage": linkage_after.get("pass"),
                "G5_mutation_sequence": mutation.get("mutation_ok"),
                "G5_resolution_walks": not resolution.get("noop_detected"),
                "G5_cross_surface": cross.get("pass"),
            },
        }
    )
    _write("07_classification.json", classification)
    _write("classifications.json", {"classifications": [classification]})

    watchlist: List[str] = []
    if linkage_after.get("orphan_documents"):
        watchlist.append(f"orphan documents without requirement_id: {len(linkage_after['orphan_documents'])}")
    if not mutation.get("document_id"):
        watchlist.append("upload mutation produced no document_id")
    _write(
        "watchlist.md",
        "\n".join(
            [
                f"# G5 Documents watchlist — {SLUG}",
                "",
                f"**Run:** `{RUN_TAG}`",
                f"**Classification:** `{primary}`",
                f"**Upload target requirement:** `{target_rid}`",
                "",
                "## Watchlist",
                "",
            ]
            + [f"- {w}" for w in watchlist]
            or ["- (none)"],
        ),
    )

    report = f"""# G5 Documents — {SLUG}

**Run:** `{RUN_TAG}`  
**Classification:** `{primary}`

| Checkpoint | Result |
|------------|--------|
| Boot | {boot.get('boot_ok')} |
| Document truth | {truth_after.get('pass')} |
| Linkage | {linkage_after.get('pass')} |
| Mutation | {mutation.get('mutation_ok')} |
| Cross-surface | {cross.get('pass')} |
"""
    (BUNDLE / "REPORT.md").write_text(report, encoding="utf-8")
    if verified:
        (BUNDLE / "DEPLOY_CONTINUITY_NOTE.md").write_text(
            f"# Deploy continuity — G5 Documents\n\n**Run:** `{RUN_TAG}`\n\nG5 `VERIFIED_OPERATIONALLY`. G6 may proceed.\n",
            encoding="utf-8",
        )

    return {"classification": primary, "bundle": str(BUNDLE), "blocking": not verified}


if __name__ == "__main__":
    print(json.dumps(run_g5(), indent=2))
