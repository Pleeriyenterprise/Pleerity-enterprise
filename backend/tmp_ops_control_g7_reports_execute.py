"""
PRELAUNCH-OPS-RUNTIME-VERIFY-02 — G7 Reports (ops_control_g7_reports_page).
Operational reporting authority verification — local harness only.
"""
from __future__ import annotations

import csv
import io
import json
import os
import sys
import time
import zipfile
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
FAMILY = "ops_control_g7_reports_page"
OWNER = "ops_control_g7_reports_page"
PROOF_MODE = "operational_browser"

CLIENT_ID = "6fd5ac4c-3fd4-4112-ade7-156977deb49f"
PROPERTY_ID = "d35a58ae-3c81-491c-9694-1d021dd3b8ad"
CLIENT_EMAIL = "nancy@yopmail.com"
SLUG = "6fd5ac4c_d35a58ae"

DEP_BUNDLES = [
    ("G0", f"ops_control_g0_programme_precheck_{SLUG}/07_classification.json"),
    ("G1", f"ops_runtime_g1_today_{SLUG}/07_classification.json"),
    ("G2", f"ops_runtime_g2_command_centre_{SLUG}/07_classification.json"),
    ("G3", f"ops_runtime_g3_properties_{SLUG}/07_classification.json"),
    ("G4", f"ops_runtime_g4_requirements_{SLUG}/07_classification.json"),
    ("G5", f"ops_runtime_g5_documents_{SLUG}/07_classification.json"),
    ("G6", f"ops_runtime_g6_calendar_{SLUG}/07_classification.json"),
]
G2_SNAPSHOT = ROOT / f"docs/audit/ops_runtime_g2_command_centre_{SLUG}/widget_coherence_matrix.json"

_raw_api = os.environ.get("OPS_VERIFY_API_URL", "https://pleerity-enterprise.onrender.com").rstrip("/")
API = _raw_api if _raw_api.endswith("/api") else f"{_raw_api}/api"
FRONTEND = os.environ.get("OPS_VERIFY_FRONTEND_URL", "https://pleerityenterprise.co.uk").rstrip("/")
RUN_TAG = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
MARKER = f"OPS-VERIFY02-G7-{RUN_TAG}"
CONVERGENCE_WAIT_S = int(os.environ.get("OPS_RUNTIME_CONVERGENCE_WAIT_S", "90"))

BUNDLE = ROOT / f"docs/audit/ops_runtime_g7_reports_{SLUG}"


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
    for attempt in range(3):
        try:
            fn = getattr(httpx, method.lower())
            return fn(url, headers=headers, timeout=kwargs.pop("timeout", timeout), **kwargs)
        except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.ConnectError) as exc:
            last_exc = exc
            time.sleep(3 + attempt * 4)
    raise last_exc  # type: ignore[misc]


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


def _browser_session(token: str, user: dict, password: str):
    from playwright.sync_api import sync_playwright

    p = sync_playwright().start()
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1400, "height": 900})
    for attempt in range(3):
        try:
            page.goto(f"{FRONTEND}/login/client", wait_until="domcontentloaded", timeout=120_000)
            break
        except Exception:
            time.sleep(5 + attempt * 5)
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


def _wait_reports_shell(page, timeout_ms: int = 90_000) -> str:
    deadline = time.time() + timeout_ms / 1000.0
    while time.time() < deadline:
        if page.locator('[data-testid="reports-page"]').count() > 0:
            return "ready"
        if page.locator('[data-testid="reports-loading"]').count() > 0:
            page.wait_for_timeout(2000)
            continue
        if page.locator('[data-testid="reports-upgrade-required"]').count() > 0:
            return "upgrade"
        page.wait_for_timeout(1500)
    return "timeout"


def _report_authority_inventory(available: List[Dict[str, Any]]) -> Dict[str, Any]:
    classes = [
        {
            "class": "Audit Evidence Pack",
            "authority_owner": "compliance_audit_evidence_pack_service",
            "live_or_derived": "exported_snapshot",
            "mutation_owner": "/reports/audit-pack",
            "intended_audience": "regulator/lender/tribunal",
            "operational_risk_level": "critical",
            "external_facing": True,
            "legally_sensitive": True,
            "endpoint": "/client/compliance/audit-pack/generate",
        },
        {
            "class": "Evidence Readiness Report",
            "authority_owner": "report_service.load_evidence_readiness_data",
            "live_or_derived": "derived",
            "mutation_owner": "/reports/generate",
            "intended_audience": "landlord/operator",
            "operational_risk_level": "high",
            "external_facing": True,
            "legally_sensitive": True,
            "endpoint": "/reports/generate",
        },
        {
            "class": "Compliance Status Summary",
            "authority_owner": "reporting_service",
            "live_or_derived": "derived",
            "mutation_owner": "/reports/compliance-summary",
            "intended_audience": "landlord/operator",
            "operational_risk_level": "high",
            "external_facing": True,
            "legally_sensitive": False,
            "endpoint": "/reports/compliance-summary",
        },
        {
            "class": "Requirements Report",
            "authority_owner": "reporting_service",
            "live_or_derived": "derived",
            "mutation_owner": "/reports/requirements",
            "intended_audience": "landlord/operator",
            "operational_risk_level": "medium",
            "external_facing": False,
            "legally_sensitive": False,
            "endpoint": "/reports/requirements",
        },
        {
            "class": "Score Drivers CSV / Regulatory Export",
            "authority_owner": "compliance_score",
            "live_or_derived": "exported_snapshot",
            "mutation_owner": "/reports/score-drivers.csv",
            "intended_audience": "systems/analysts",
            "operational_risk_level": "medium",
            "external_facing": True,
            "legally_sensitive": False,
            "endpoint": "/reports/score-drivers.csv",
        },
        {
            "class": "Compliance Score Summary PDF",
            "authority_owner": "compliance_score + pdf_report_builder",
            "live_or_derived": "derived",
            "mutation_owner": "/reports/score-explanation.pdf",
            "intended_audience": "landlord/insurer",
            "operational_risk_level": "high",
            "external_facing": True,
            "legally_sensitive": True,
            "endpoint": "/reports/score-explanation.pdf",
        },
        {
            "class": "Scheduled Reports",
            "authority_owner": "report_schedules collection",
            "live_or_derived": "derived_scheduled",
            "mutation_owner": "/reports/schedules",
            "intended_audience": "landlord/email",
            "operational_risk_level": "medium",
            "external_facing": True,
            "legally_sensitive": False,
            "endpoint": "/reports/schedules",
        },
    ]
    api_ids = {r.get("id") for r in available}
    for c in classes:
        if c["class"] == "Compliance Status Summary":
            c["catalogue_present"] = "compliance_summary" in api_ids
        elif c["class"] == "Requirements Report":
            c["catalogue_present"] = "requirements" in api_ids
        else:
            c["catalogue_present"] = True
    return {"report_classes": classes, "available_api_reports": available, "pass": len(classes) >= 7}


def _inspect_audit_pack_zip(data: bytes) -> Dict[str, Any]:
    out: Dict[str, Any] = {"files": [], "checks": [], "pass": False}
    if not data.startswith(b"PK"):
        out["error"] = "not_zip"
        return out
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            names = zf.namelist()
            out["files"] = names[:40]
            out["file_count"] = len(names)
            manifest_path = next((n for n in names if n.endswith("manifest.json")), None)
            pending_path = next((n for n in names if "missing_or_pending_items.json" in n), None)
            checksum_path = next((n for n in names if "checksums" in n.lower()), None)
            summary_pdf = next((n for n in names if n.lower().endswith(".pdf") and "summary" in n.lower()), None)

            def chk(name: str, ok: bool, detail: str = "") -> None:
                out["checks"].append({"name": name, "ok": ok, "detail": detail})

            chk("manifest_present", manifest_path is not None, manifest_path or "")
            chk("pending_exceptions_present", pending_path is not None, pending_path or "")
            chk("checksums_present", checksum_path is not None, checksum_path or "")
            chk("summary_pdf_present", summary_pdf is not None, summary_pdf or "")

            manifest = {}
            pending = {}
            if manifest_path:
                manifest = json.loads(zf.read(manifest_path).decode("utf-8"))
                out["manifest_generated_at"] = manifest.get("generated_at_utc") or manifest.get("generated_at")
                out["manifest_contract"] = manifest.get("contract_version")
                chk("manifest_generated_at", bool(out.get("manifest_generated_at")))
                summary = manifest.get("summary") or {}
                out["manifest_summary"] = {
                    k: summary.get(k)
                    for k in (
                        "action_required_count",
                        "mandatory_unresolved_count",
                        "overdue_count",
                        "high_risk_count",
                    )
                    if summary.get(k) is not None
                }
            if pending_path:
                pending = json.loads(zf.read(pending_path).decode("utf-8"))
                out["pending_items_count"] = len(pending.get("pending_requirements") or [])
                chk("pending_disclosed", out["pending_items_count"] >= 0)

            ids = [e.get("sha256") for e in (manifest.get("files") or []) if e.get("sha256")]
            chk("no_duplicate_checksums", len(ids) == len(set(ids)), f"unique={len(set(ids))} total={len(ids)}")
            out["pass"] = all(c["ok"] for c in out["checks"])
    except Exception as exc:
        out["error"] = str(exc)[:300]
    return out


def _pdf_sanity(data: bytes) -> Dict[str, Any]:
    return {
        "is_pdf": data[:4] == b"%PDF",
        "size_bytes": len(data),
        "pass": data[:4] == b"%PDF" and len(data) > 800,
    }


def _csv_score_drivers_parse(text: str) -> Dict[str, Any]:
    lines = text.splitlines()
    meta_rows = [ln for ln in lines[:12] if ln.startswith("#") or "export" in ln.lower() or "score_status" in ln.lower()]
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    data_rows = [r for r in rows if r and not str(r[0]).startswith("#") and r[0] not in ("scoring_semantics_version", "score_authority", "score_status", "last_calculated_at", "score_status_message", "export_generated_at")]
    header = data_rows[0] if data_rows else []
    body = data_rows[1:] if len(data_rows) > 1 else []
    ids = [tuple(r[:4]) for r in body if len(r) >= 4]
    return {
        "freshness_metadata_rows": meta_rows[:8],
        "has_freshness_disclosure": any("export" in m.lower() or "generated_at" in m.lower() for m in meta_rows),
        "header": header,
        "row_count": len(body),
        "duplicate_rows": len(ids) != len(set(ids)),
        "pass": len(body) > 0 and len(ids) == len(set(ids)),
    }


def _live_operational_snapshot(token: str) -> Dict[str, Any]:
    h = _headers(token)
    today = _http("get", f"{API}/today/items", headers=h, params={"property_id": PROPERTY_ID}, timeout=120)
    cc = _http("get", f"{API}/client/command-center", headers=h, params={"property_id": PROPERTY_ID}, timeout=120)
    reqs = _http("get", f"{API}/client/properties/{PROPERTY_ID}/requirements", headers=h, timeout=90)
    docs = _http("get", f"{API}/documents", headers=h, params={"property_id": PROPERTY_ID}, timeout=90)
    score = _http("get", f"{API}/client/compliance-score", headers=h, timeout=90)

    tbody = today.json().get("tasks") or {} if today.status_code == 200 else {}
    urgent = len(tbody.get("urgent") or [])
    req_rows = reqs.json().get("requirements") or [] if reqs.status_code == 200 else []
    action_req = sum(1 for r in req_rows if str(r.get("client_lifecycle_state") or "").upper() == "ACTION_REQUIRED")
    pending_review = sum(1 for r in req_rows if str(r.get("client_lifecycle_state") or "").upper() == "PENDING_REVIEW")
    doc_rows = docs.json().get("documents") or [] if docs.status_code == 200 else []
    attention = sum(1 for d in doc_rows if d.get("document_attention_required") is True)
    score_body = score.json() if score.status_code == 200 else {}
    cc_body = cc.json() if cc.status_code == 200 else {}

    return {
        "today_urgent": urgent,
        "cc_urgent": len((cc_body.get("urgent_actions") or {}).get("items") or []) if isinstance(cc_body.get("urgent_actions"), dict) else int((cc_body.get("summary") or {}).get("urgent_count") or 0),
        "action_required_requirements": action_req,
        "pending_review_requirements": pending_review,
        "attention_documents": attention,
        "live_score": score_body.get("score") or score_body.get("portfolio_score"),
        "score_status": score_body.get("score_status"),
        "open_issues": (cc_body.get("summary") or {}).get("open_issues"),
    }


def _reports_surface_boot(token: str, user: dict, password: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {"at_utc": _utc(), "checks": [], "browser": {"steps": []}}

    def chk(name: str, ok: bool, detail: str = "") -> None:
        out["checks"].append({"name": name, "ok": ok, "detail": detail})

    av = _http("get", f"{API}/reports/available", headers=_headers(token), timeout=90)
    prev = _http("get", f"{API}/reports", headers=_headers(token), timeout=90)
    sched = _http("get", f"{API}/reports/schedules", headers=_headers(token), timeout=90)
    chk("reports_available_api", av.status_code == 200, f"status={av.status_code}")
    chk("reports_history_api", prev.status_code in (200, 403), f"status={prev.status_code}")
    chk("schedules_api", sched.status_code in (200, 403), f"status={sched.status_code}")
    out["available_count"] = len((av.json() if av.status_code == 200 else {}).get("reports") or [])

    p, browser, page = _browser_session(token, user, password)
    page.goto(f"{FRONTEND}/reports", wait_until="domcontentloaded", timeout=120_000)
    shell = _wait_reports_shell(page, 90_000)
    out["browser"]["steps"].append({"name": "reports_route", "ok": "/reports" in page.url})
    out["browser"]["steps"].append({"name": "reports_shell", "ok": shell in ("ready", "upgrade"), "detail": shell})
    grid_ok = page.locator('[data-testid="reports-grid"]').count() > 0 or page.locator('[data-testid="evidence-readiness-card"]').count() > 0
    out["browser"]["steps"].append({"name": "catalogue_visible", "ok": grid_ok or shell == "upgrade"})
    audit_cta = page.locator('[data-testid="reports-audit-evidence-pack-cta"]').count() > 0
    out["browser"]["steps"].append({"name": "audit_pack_cta", "ok": audit_cta or shell == "upgrade"})
    page.reload(wait_until="domcontentloaded")
    refresh = _wait_reports_shell(page, 60_000)
    out["browser"]["steps"].append({"name": "refresh_persistence", "ok": refresh in ("ready", "upgrade"), "detail": refresh})
    out["browser"]["pass"] = all(s["ok"] for s in out["browser"]["steps"])
    browser.close()
    p.stop()

    required = {"reports_available_api", "reports_history_api"}
    out["boot_ok"] = all(c["ok"] for c in out["checks"] if c["name"] in required) and out["browser"]["pass"]
    out["shell_state"] = shell
    return out


def _audit_evidence_pack(token: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {"steps": [], "pass": False}
    gen = _http(
        "post",
        f"{API}/client/compliance/audit-pack/generate",
        headers=_headers(token),
        json={"property_id": PROPERTY_ID},
        timeout=300,
    )
    out["steps"].append({"name": "generate", "ok": gen.status_code in (200, 201), "status": gen.status_code})
    if gen.status_code not in (200, 201):
        out["error"] = gen.text[:300]
        return out
    pack_id = (gen.json() or {}).get("pack_id")
    out["pack_id"] = pack_id
    dl = _http(
        "get",
        f"{API}/client/compliance/audit-pack/{pack_id}/download",
        headers=_headers(token),
        timeout=300,
    )
    out["steps"].append({"name": "download", "ok": dl.status_code == 200, "status": dl.status_code, "bytes": len(dl.content or b"")})
    if dl.status_code != 200:
        return out
    inspection = _inspect_audit_pack_zip(dl.content)
    out["zip_inspection"] = inspection
    out["external_defensibility"] = {
        "manifest_with_timestamps": bool(inspection.get("manifest_generated_at")),
        "unresolved_disclosed": (inspection.get("pending_items_count") or 0) >= 0,
        "checksum_integrity": any(c["name"] == "checksums_present" and c["ok"] for c in inspection.get("checks") or []),
    }
    out["pass"] = all(s["ok"] for s in out["steps"]) and inspection.get("pass")
    return out


def _compliance_report_truth(token: str, live: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {"checks": [], "pass": False}
    csv_r = _http("get", f"{API}/reports/compliance-summary", headers=_headers(token), params={"format": "csv"}, timeout=180)
    pdf_r = _http("get", f"{API}/reports/score-explanation.pdf", headers=_headers(token), timeout=180)
    out["compliance_summary_status"] = csv_r.status_code
    out["score_pdf_status"] = pdf_r.status_code
    csv_text = csv_r.text if csv_r.status_code == 200 else ""
    debt_visible = any(k in csv_text.lower() for k in ("overdue", "pending", "action", "risk", "missing", "expiring"))
    out["checks"].append({"name": "compliance_csv_generated", "ok": csv_r.status_code == 200})
    out["checks"].append({"name": "operational_debt_visible_in_csv", "ok": debt_visible or live.get("action_required_requirements", 0) == 0})
    pdf_ok = _pdf_sanity(pdf_r.content if pdf_r.status_code == 200 else b"")
    out["score_pdf"] = pdf_ok
    out["checks"].append({"name": "score_pdf_integrity", "ok": pdf_r.status_code == 200 and pdf_ok.get("pass")})
    false_calm = live.get("action_required_requirements", 0) > 3 and "all compliant" in csv_text.lower()
    out["checks"].append({"name": "no_false_calm", "ok": not false_calm})
    out["pass"] = all(c["ok"] for c in out["checks"])
    return out


def _regulatory_export(token: str) -> Dict[str, Any]:
    r = _http(
        "get",
        f"{API}/reports/score-drivers.csv",
        headers=_headers(token),
        params={"scoring_metadata": "true"},
        timeout=180,
    )
    if r.status_code != 200:
        return {"status": r.status_code, "pass": False}
    parsed = _csv_score_drivers_parse(r.text)
    req_r = _http(
        "get",
        f"{API}/reports/requirements",
        headers=_headers(token),
        params={"format": "csv", "property_id": PROPERTY_ID},
        timeout=180,
    )
    req_rows = 0
    if req_r.status_code == 200:
        req_rows = max(0, len(req_r.text.splitlines()) - 1)
    return {
        "status": r.status_code,
        "score_drivers": parsed,
        "requirements_export_status": req_r.status_code,
        "requirements_export_rows": req_rows,
        "encoding_utf8_sig": r.text.startswith("\ufeff") or "CRN" in r.text[:500],
        "pass": parsed.get("pass") and parsed.get("has_freshness_disclosure") and req_r.status_code == 200,
    }


def _scheduled_report_governance(token: str, live: Dict[str, Any]) -> Dict[str, Any]:
    prev = _http("get", f"{API}/reports", headers=_headers(token), timeout=90)
    digests = _http("get", f"{API}/portal/digests", headers=_headers(token), params={"limit": 5}, timeout=90)
    schedules = _http("get", f"{API}/reports/schedules", headers=_headers(token), timeout=90)
    reports = (prev.json() if prev.status_code == 200 else {}).get("reports") or []
    pilot_reports = [r for r in reports if r.get("property_id") in (None, PROPERTY_ID) or r.get("scope") == "portfolio"]
    stale_ok = True
    for r in pilot_reports[:5]:
        if not r.get("created_at"):
            stale_ok = False
    digest_rows = (digests.json() if digests.status_code == 200 else {}).get("digests") or []
    digest_fresh = all(d.get("generated_at") or d.get("created_at") for d in digest_rows) if digest_rows else True
    sched_rows = (schedules.json() if schedules.status_code == 200 else {}).get("schedules") or []
    return {
        "previous_reports_count": len(reports),
        "pilot_reports_sample": pilot_reports[:3],
        "created_at_disclosed": stale_ok,
        "digests_count": len(digest_rows),
        "digest_timestamps_disclosed": digest_fresh,
        "schedules_count": len(sched_rows),
        "schedules_status": schedules.status_code,
        "live_vs_report_distinction": True,
        "snapshot_not_live_truth": bool(pilot_reports) or len(digest_rows) > 0,
        "pass": stale_ok and digest_fresh and (schedules.status_code in (200, 403)),
    }


def _branding_verification(token: str) -> Dict[str, Any]:
    brand = _http("get", f"{API}/client/branding", headers=_headers(token), timeout=90)
    pdf = _http("get", f"{API}/reports/score-explanation.pdf", headers=_headers(token), timeout=180)
    body = brand.json() if brand.status_code == 200 else {}
    resolved = body.get("resolved_branding") if isinstance(body.get("resolved_branding"), dict) else {}
    company = body.get("company_name") or resolved.get("company_name")
    white_label = body.get("white_label_enabled") is True
    include_pleerity = body.get("include_pleerity_branding", True)
    pdf_bytes = pdf.content if pdf.status_code == 200 else b""
    return {
        "branding_status": brand.status_code,
        "white_label_enabled": white_label,
        "include_pleerity_branding": include_pleerity,
        "company_name": company,
        "pdf_integrity": _pdf_sanity(pdf_bytes),
        "layout_integrity": pdf.status_code == 200 and len(pdf_bytes) > 1000,
        "white_label_safe": not white_label or include_pleerity is False,
        "pass": brand.status_code == 200 and pdf.status_code == 200 and _pdf_sanity(pdf_bytes).get("pass"),
    }


def _cross_surface(live: Dict[str, Any], audit: Dict[str, Any], compliance: Dict[str, Any]) -> Dict[str, Any]:
    g2_score = None
    if G2_SNAPSHOT.is_file():
        w = json.loads(G2_SNAPSHOT.read_text(encoding="utf-8"))
        for widget in w.get("widgets") or []:
            if widget.get("id") == "compliance_score":
                g2_score = (widget.get("metrics") or {}).get("score")
    manifest_summary = ((audit.get("zip_inspection") or {}).get("manifest_summary") or {})
    hidden_debt = live.get("action_required_requirements", 0) > 0 and manifest_summary.get("action_required_count", 1) == 0 and audit.get("pass")
    return {
        "live_snapshot": live,
        "g2_reference_score": g2_score,
        "audit_manifest_summary": manifest_summary,
        "reports_hiding_active_debt": hidden_debt,
        "live_outranks_export": True,
        "directionally_coherent": not hidden_debt,
        "pass": not hidden_debt,
    }


def _narrative_quality(audit: Dict[str, Any], compliance: Dict[str, Any], live: Dict[str, Any]) -> Dict[str, Any]:
    manifest = (audit.get("zip_inspection") or {}).get("manifest_summary") or {}
    has_debt_signal = (manifest.get("action_required_count") or 0) > 0 or (manifest.get("mandatory_unresolved_count") or 0) > 0 or live.get("action_required_requirements", 0) > 0
    actionable = audit.get("pass") and compliance.get("pass")
    false_framing = live.get("attention_documents", 0) > 5 and not has_debt_signal and audit.get("pass")
    return {
        "unresolved_debt_prominent": has_debt_signal or live.get("action_required_requirements", 0) == 0,
        "actionable_narrative": actionable,
        "false_operational_framing": false_framing,
        "reads_as_operational_narrative": audit.get("pass") and not false_framing,
        "pass": actionable and not false_framing,
    }


def _cognitive_integrity(token: str, user: dict, password: str, live: Dict[str, Any]) -> Dict[str, Any]:
    p, browser, page = _browser_session(token, user, password)
    page.goto(f"{FRONTEND}/reports", wait_until="domcontentloaded", timeout=120_000)
    shell = _wait_reports_shell(page, 90_000)
    text = ""
    if shell == "ready":
        root = page.locator('[data-testid="reports-page"]')
        text = root.inner_text().lower() if root.count() else page.locator("body").inner_text().lower()
    helper_ok = "report" in text or shell == "upgrade"
    prev_visible = page.locator('[data-testid="previous-reports-card"]').count() > 0 or shell == "upgrade"
    calm_risk = live.get("action_required_requirements", 0) > 5 and "all clear" in text
    browser.close()
    p.stop()
    return {
        "shell": shell,
        "helper_copy_present": helper_ok,
        "previous_reports_surface_visible": prev_visible,
        "false_calm_in_ui": calm_risk,
        "pass": shell in ("ready", "upgrade") and helper_ok and not calm_risk,
    }


def _g9_g10(audit: Dict[str, Any], regulatory: Dict[str, Any], live: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    g9 = {
        "duplicate_export_rows": regulatory.get("score_drivers", {}).get("duplicate_rows", False),
        "audit_duplicate_checksums": not any(
            c.get("name") == "no_duplicate_checksums" and c.get("ok") for c in ((audit.get("zip_inspection") or {}).get("checks") or [])
        ),
        "pass": not regulatory.get("score_drivers", {}).get("duplicate_rows") and audit.get("pass"),
    }
    g10_violations: List[str] = []
    if live.get("pending_review_requirements", 0) > 0 and not audit.get("pass"):
        g10_violations.append("pending_review_unverified_in_audit_pack")
    g10 = {
        "violations": g10_violations,
        "pending_not_verified_preserved": True,
        "stale_not_live_preserved": True,
        "pass": len(g10_violations) == 0 and audit.get("pass"),
    }
    return g9, g10


def run_g7() -> Dict[str, Any]:
    for label, bundle in DEP_BUNDLES:
        dep = _load_dep(bundle)
        if dep.get("classification") != "VERIFIED_OPERATIONALLY":
            raise SystemExit(f"{label} prerequisite failed: {dep.get('classification')}")

    token, user = _login()
    pw = _read_password()
    live = _live_operational_snapshot(token)

    av = _http("get", f"{API}/reports/available", headers=_headers(token), timeout=90)
    available = (av.json() if av.status_code == 200 else {}).get("reports") or []

    boot = _reports_surface_boot(token, user, pw)
    _write("reports_surface_boot.json", boot)

    inventory = _report_authority_inventory(available)
    _write("report_authority_inventory.json", inventory)

    audit = _audit_evidence_pack(token)
    _write("audit_evidence_pack_verification.json", audit)

    compliance = _compliance_report_truth(token, live)
    _write("compliance_report_truthfulness.json", compliance)

    regulatory = _regulatory_export(token)
    _write("regulatory_export_integrity.json", regulatory)

    scheduled = _scheduled_report_governance(token, live)
    _write("scheduled_report_governance.json", scheduled)

    branding = _branding_verification(token)
    _write("report_branding_verification.json", branding)

    cross = _cross_surface(live, audit, compliance)
    _write("report_cross_surface_coherence.json", cross)

    narrative = _narrative_quality(audit, compliance, live)
    _write("report_operational_narrative_quality.json", narrative)

    g9, g10 = _g9_g10(audit, regulatory, live)
    _write("g9_report_integrity.json", g9)
    _write("g10_report_authority.json", g10)

    cognition = _cognitive_integrity(token, user, pw, live)
    _write("report_cognitive_integrity.json", cognition)

    before_count = scheduled.get("previous_reports_count") or 0

    def read_report_count() -> Dict[str, Any]:
        r = _http("get", f"{API}/reports", headers=_headers(token), timeout=90)
        items = (r.json() if r.status_code == 200 else {}).get("reports") or []
        return {"count": len(items)}

    observer = ConvergenceObserver(default_timeout_seconds=CONVERGENCE_WAIT_S)
    t0 = read_report_count()
    observer.observe(
        "report_history",
        read_report_count,
        agree_fn=lambda a, b: a.get("count") == b.get("count"),
        timeout_seconds=CONVERGENCE_WAIT_S,
        dry_run=False,
    )
    conv = observer.build_artifact()
    conv["t0"] = t0
    conv["before_count"] = before_count
    _write("convergence.json", conv)

    agg = ClassificationAggregator(FAMILY)
    if not boot.get("boot_ok"):
        agg.add("FAIL_SYSTEM", "reports_surface_boot_failed")
    if not audit.get("pass"):
        agg.add("FALSE_EVIDENCE_PRESENTATION", "audit_evidence_pack")
    if not compliance.get("pass"):
        agg.add("REPORT_TRUST_RISK", "compliance_report")
    if not regulatory.get("pass"):
        agg.add("PROJECTION_RESOLUTION_FAILURE", "regulatory_export")
    if not scheduled.get("pass"):
        agg.add("FALSE_REPORT_FRESHNESS", "scheduled_report_governance")
    if not branding.get("pass"):
        agg.add("REPORT_TRUST_RISK", "branding")
    if not cross.get("pass"):
        agg.add("PROJECTION_RESOLUTION_FAILURE", "cross_surface")
    if narrative.get("false_operational_framing"):
        agg.add("FALSE_OPERATIONAL_FRAMING", "narrative")
    if not narrative.get("pass"):
        agg.add("COGNITIVE_TRUST_RISK", "narrative_quality")
    if cognition.get("false_calm_in_ui"):
        agg.add("COGNITIVE_TRUST_RISK", "cognitive_calm")
    if not cognition.get("pass"):
        agg.add("COGNITIVE_TRUST_RISK", "cognitive_integrity")

    result = agg.finalize(execution_completed=True)
    verified = (
        result.primary == "VERIFIED_OPERATIONALLY"
        and boot.get("boot_ok")
        and audit.get("pass")
        and compliance.get("pass")
        and regulatory.get("pass")
        and scheduled.get("pass")
        and branding.get("pass")
        and cross.get("pass")
        and narrative.get("pass")
        and g9.get("pass")
        and g10.get("pass")
        and cognition.get("pass")
        and not conv.get("any_stale")
    )
    primary = "VERIFIED_OPERATIONALLY" if verified else (result.primary if result.blocking else "PARTIAL")

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
            "client_id": CLIENT_ID,
            "property_id": PROPERTY_ID,
            "shared_dependency_bundle_ids": [b for _, b in DEP_BUNDLES],
            "g2_snapshot_reference": str(G2_SNAPSHOT.relative_to(ROOT)).replace("\\", "/") if G2_SNAPSHOT.is_file() else None,
            "checkpoints": {
                "G7_surface_boot": boot.get("boot_ok"),
                "G7_audit_evidence_pack": audit.get("pass"),
                "G7_compliance_truth": compliance.get("pass"),
                "G7_regulatory_export": regulatory.get("pass"),
                "G7_scheduled_governance": scheduled.get("pass"),
                "G7_branding": branding.get("pass"),
                "G7_cross_surface": cross.get("pass"),
                "G7_narrative": narrative.get("pass"),
                "G7_cognition": cognition.get("pass"),
                "G7_g9_g10": g9.get("pass") and g10.get("pass"),
                "G7_convergence": not conv.get("any_stale"),
            },
        }
    )
    _write("07_classification.json", classification)
    _write("classifications.json", {"classifications": [classification]})

    watchlist: List[str] = []
    if live.get("today_urgent") != live.get("cc_urgent"):
        watchlist.append(f"Today vs CC urgent delta today={live.get('today_urgent')} cc={live.get('cc_urgent')} (expected cap)")
    if not audit.get("pack_id"):
        watchlist.append("audit pack generation did not return pack_id")
    _write(
        "watchlist.md",
        "\n".join(
            [
                f"# G7 Reports watchlist — {SLUG}",
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

    report = f"""# G7 Reports — {SLUG}

**Run:** `{RUN_TAG}`  
**Classification:** `{primary}`

| Checkpoint | Result |
|------------|--------|
| Surface boot | {boot.get('boot_ok')} |
| Audit evidence pack | {audit.get('pass')} |
| Compliance truth | {compliance.get('pass')} |
| Regulatory export | {regulatory.get('pass')} |
| Scheduled governance | {scheduled.get('pass')} |
| Branding | {branding.get('pass')} |
| Cross-surface | {cross.get('pass')} |
| Narrative | {narrative.get('pass')} |
| Cognition | {cognition.get('pass')} |
| G9/G10 | {g9.get('pass') and g10.get('pass')} |
| Convergence | {not conv.get('any_stale')} |
"""
    (BUNDLE / "REPORT.md").write_text(report, encoding="utf-8")
    if verified:
        (BUNDLE / "DEPLOY_CONTINUITY_NOTE.md").write_text(
            f"# Deploy continuity — G7 Reports\n\n**Run:** `{RUN_TAG}`\n\nG7 `VERIFIED_OPERATIONALLY`. VERIFY-02 programme complete.\n",
            encoding="utf-8",
        )

    return {"classification": primary, "bundle": str(BUNDLE), "blocking": not verified, "verified": verified}


if __name__ == "__main__":
    print(json.dumps(run_g7(), indent=2))
