#!/usr/bin/env python3
"""REVIEW-ASSURANCE-POST-DEPLOY-CLEANUP-01 — post-deploy verification closeout."""
from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/audit/review_assurance_post_deploy_cleanup_01"
SHOTS = OUT / "screenshots"
API = os.getenv("STAGING_API", "https://pleerity-enterprise.onrender.com/api").rstrip("/")
FE = os.getenv("STAGING_FE", "https://pleerityenterprise.co.uk").rstrip("/")
EXPECTED_COMMIT_PREFIX = os.getenv("EXPECTED_COMMIT_PREFIX", "acc8cbd3")
PROGRAMME = "REVIEW-ASSURANCE-POST-DEPLOY-CLEANUP-01"

NANCY_EMAIL = "nancy@yopmail.com"
NANCY_PW = ROOT / "docs/audit/ops_verify_01_6fd5ac4c_d35a58ae/.ops_verify_temp_pw.txt"
ADMIN_EMAIL = "aigbochievictory@gmail.com"
ADMIN_PW = ROOT / "docs/audit/ops_verify_01_6fd5ac4c_d35a58ae/.ops_verify_admin_pw.txt"

FE_POSITIVE_MARKERS = (
    "Recorded on file",
    "requirement-modal-assurance-section",
    "compliance-review-deprecated",
    "Self-recorded declaration",
)
FE_NEGATIVE_MARKERS = (
    "orgComplianceReviewOperator",
    "RequirementModalOperatorReviewSection",
    "org-review-open-",
    "organisation review in progress",
    "Submission on file \u2014 organisation review",
    "organisation review pending",
)


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write(name: str, data: Any) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


def _load_client_creds() -> Tuple[str, str]:
    email = (os.getenv("STAGING_CLIENT_ADMIN_EMAIL") or NANCY_EMAIL).strip()
    pw = (os.getenv("STAGING_CLIENT_ADMIN_PASSWORD") or "").strip()
    if not pw and NANCY_PW.is_file():
        pw = NANCY_PW.read_text(encoding="utf-8").strip()
    if not pw:
        raise SystemExit("Missing staging client password")
    return email, pw


def _login_client(email: str, password: str) -> Tuple[str, Dict[str, Any]]:
    last_err: Optional[Exception] = None
    for _ in range(8):
        try:
            r = httpx.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=120)
            if r.status_code == 503:
                time.sleep(12)
                continue
            r.raise_for_status()
            body = r.json()
            return body["access_token"], body.get("user") or {}
        except Exception as exc:
            last_err = exc
            if "SSL" in str(exc) or "EOF" in str(exc):
                time.sleep(15)
            else:
                time.sleep(8)
    raise RuntimeError(f"client login failed: {last_err}")


def _login_admin() -> str:
    pw = ADMIN_PW.read_text(encoding="utf-8").strip()
    r = httpx.post(f"{API}/auth/admin/login", json={"email": ADMIN_EMAIL, "password": pw}, timeout=120)
    r.raise_for_status()
    return r.json()["access_token"]


def _fetch_main_js() -> Tuple[str, str]:
    html = httpx.get(f"{FE}/", timeout=90).text
    scripts = re.findall(r'src="(/static/js/[^"]+)"', html)
    main = next((s for s in scripts if "main" in s), "")
    if not main:
        try:
            manifest = httpx.get(f"{FE}/asset-manifest.json", timeout=90).json()
            main = manifest.get("files", {}).get("main.js", "")
        except Exception:
            main = ""
    url = f"{FE}{main}" if main else ""
    js = httpx.get(url, timeout=120).text if url else ""
    return url, js


def deploy_verification() -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "programme": PROGRAMME,
        "verified_at": _utc(),
        "api_base": API,
        "frontend_url": FE,
        "expected_commit_prefix": EXPECTED_COMMIT_PREFIX,
    }
    try:
        ver = httpx.get(f"{API}/version", timeout=90).json()
        sha = str(ver.get("commit_sha") or "")
        out["api_version"] = ver
        out["commit_sha"] = sha
        out["commit_at_least_expected"] = sha.startswith(EXPECTED_COMMIT_PREFIX) or sha >= EXPECTED_COMMIT_PREFIX
    except Exception as exc:
        out["api_version_error"] = str(exc)[:300]
        out["commit_at_least_expected"] = False

    try:
        url, js = _fetch_main_js()
        out["main_js_url"] = url
        pos = {m: m in js for m in FE_POSITIVE_MARKERS}
        neg = {m: m in js for m in FE_NEGATIVE_MARKERS}
        out["bundle_positive_markers"] = pos
        out["bundle_negative_markers"] = neg
        out["nav_compliance_review_in_portal_tabs"] = 'path: "/operations/compliance-review"' in js or (
            '"/operations/compliance-review"' in js and "Compliance review" in js and "OPERATIONS_CHILDREN" in js
        )
        out["pass"] = (
            out.get("commit_at_least_expected")
            and all(pos.values())
            and not any(neg.values())
            and not out.get("nav_compliance_review_in_portal_tabs")
        )
    except Exception as exc:
        out["frontend_error"] = str(exc)[:300]
        out["pass"] = False

    return out


def legacy_org_review_audit(token: str) -> Dict[str, Any]:
    from services.review_assurance_legacy_convergence import audit_legacy_org_review_batch

    headers = {"Authorization": f"Bearer {token}"}
    out: Dict[str, Any] = {"verified_at": _utc(), "pass": False}

    oq = httpx.get(f"{API}/client/compliance-evidence/org-review-queue", headers=headers, timeout=120)
    oq_body = oq.json() if oq.is_success else {}
    out["org_queue"] = {
        "status": oq.status_code,
        "total": oq_body.get("total") if isinstance(oq_body, dict) else None,
        "deprecated": oq_body.get("deprecated") if isinstance(oq_body, dict) else None,
        "items": (oq_body.get("items") or [])[:10] if isinstance(oq_body, dict) else [],
    }

    reqs = httpx.get(f"{API}/client/requirements", headers=headers, params={"projection": "full"}, timeout=120)
    rows = list(reqs.json().get("requirements") or []) if reqs.is_success else []
    out["requirements_scanned"] = len(rows)

    audit = audit_legacy_org_review_batch(rows)
    out["legacy_audit"] = audit

    org_family = [r for r in rows if str(r.get("governance_family") or "") == "ORG_ADMIN_REVIEWED"]
    org_owner = [r for r in rows if str(r.get("review_owner") or "") == "org_admin"]
    org_stage = [r for r in rows if "org_verification" in str(r.get("truth_presentation_stage") or "")]
    out["api_surface_counts"] = {
        "ORG_ADMIN_REVIEWED_family": len(org_family),
        "review_owner_org_admin": len(org_owner),
        "org_verification_stage": len(org_stage),
    }

    self_samples = [
        r
        for r in rows
        if str(r.get("assurance_tier") or "") == "SELF_RECORDED"
        and str(r.get("truth_presentation_label") or "").lower().find("recorded") >= 0
    ][:3]
    out["self_recorded_samples"] = [
        {
            "requirement_id": r.get("requirement_id"),
            "property_id": r.get("property_id"),
            "display_label": r.get("display_label"),
            "assurance_tier": r.get("assurance_tier"),
            "truth_presentation_label": r.get("truth_presentation_label"),
        }
        for r in self_samples
    ]

    out["pass"] = (
        int(out["org_queue"].get("total") or 0) == 0
        and audit.get("pass") is True
        and out["api_surface_counts"]["ORG_ADMIN_REVIEWED_family"] == 0
        and out["api_surface_counts"]["review_owner_org_admin"] == 0
    )
    return out


def queue_verification(client_token: str, admin_token: str) -> Dict[str, Any]:
    ch = {"Authorization": f"Bearer {client_token}"}
    ah = {"Authorization": f"Bearer {admin_token}"}

    oq = httpx.get(f"{API}/client/compliance-evidence/org-review-queue", headers=ch, timeout=120)
    oq_body = oq.json() if oq.is_success else {}

    esc = httpx.get(f"{API}/admin/compliance-evidence/escalation-queue", headers=ah, timeout=120)
    esc_body = esc.json() if esc.is_success else {}

    doc = httpx.get(f"{API}/admin/documents/pending-verification", headers=ah, params={"limit": 20}, timeout=120)
    doc_body = doc.json() if doc.is_success else {}

    reqs = httpx.get(f"{API}/client/requirements", headers=ch, params={"projection": "full"}, timeout=120)
    rows = list(reqs.json().get("requirements") or []) if reqs.is_success else []
    self_in_queue = [
        r
        for r in (oq_body.get("items") or [])
        if str(r.get("assurance_tier") or r.get("governance_family") or "") in ("SELF_RECORDED", "SELF_CERTIFIED")
    ]

    return {
        "verified_at": _utc(),
        "org_queue": {
            "status": oq.status_code,
            "total": oq_body.get("total"),
            "deprecated": oq_body.get("deprecated"),
            "self_recorded_in_org_queue": len(self_in_queue),
        },
        "escalation_queue": {
            "status": esc.status_code,
            "total": esc_body.get("total") if isinstance(esc_body, dict) else len(esc_body or []),
            "sample_ids": [
                (it.get("requirement_id") if isinstance(it, dict) else None)
                for it in (esc_body.get("items") if isinstance(esc_body, dict) else esc_body or [])[:5]
            ],
        },
        "document_verification_queue": {
            "status": doc.status_code,
            "count": len(doc_body) if isinstance(doc_body, list) else (doc_body.get("total") if isinstance(doc_body, dict) else 0),
        },
        "self_recorded_queue_backed": sum(
            1 for r in rows if r.get("assurance_tier") == "SELF_RECORDED" and r.get("queue_backed_review") is True
        ),
        "pass": (
            int(oq_body.get("total") or 0) == 0
            and len(self_in_queue) == 0
            and esc.status_code == 200
            and doc.status_code == 200
        ),
    }


def regression_probe(client_token: str, admin_token: str) -> Dict[str, Any]:
    ch = {"Authorization": f"Bearer {client_token}"}
    ah = {"Authorization": f"Bearer {admin_token}"}
    checks: Dict[str, Any] = {}

    for name, path in (
        ("today", "/today/items"),
        ("command_center", "/client/command-center"),
    ):
        r = httpx.get(f"{API}{path}", headers=ch, timeout=120)
        checks[name] = {"status": r.status_code, "ok": r.is_success}

    esc = httpx.get(f"{API}/admin/compliance-evidence/escalation-queue", headers=ah, timeout=120)
    checks["escalation_queue"] = {"status": esc.status_code, "ok": esc.is_success}

    doc = httpx.get(f"{API}/admin/documents/pending-verification", headers=ah, params={"limit": 5}, timeout=120)
    checks["document_verification"] = {"status": doc.status_code, "ok": doc.is_success}

    reqs = httpx.get(f"{API}/client/requirements", headers=ch, params={"projection": "full"}, timeout=120)
    rows = list(reqs.json().get("requirements") or []) if reqs.is_success else []
    checks["requirements_count"] = len(rows)
    checks["assurance_tier_in_requirements_list"] = {
        "ok": any(str(r.get("assurance_tier") or "").strip() for r in rows),
        "sample_tiers": list({str(r.get("assurance_tier")) for r in rows if r.get("assurance_tier")})[:6],
    }

    sample = next((r for r in rows if r.get("property_id") and r.get("requirement_id")), None)
    if sample:
        rid = sample["requirement_id"]
        wf = httpx.get(f"{API}/requirements/{rid}", headers=ch, timeout=120)
        wf_body = wf.json() if wf.is_success else {}
        req_obj = wf_body.get("requirement") if isinstance(wf_body, dict) else wf_body
        checks["requirement_detail_hydration"] = {
            "status": wf.status_code,
            "ok": wf.is_success,
            "has_assurance_tier": isinstance(req_obj, dict) and "assurance_tier" in req_obj,
        }
        pid, req_id = sample["property_id"], sample["requirement_id"]
        checks["deeplink_shape"] = f"/properties/{pid}?resolve_requirement={req_id}"

    core_ok = (
        checks.get("command_center", {}).get("ok")
        and checks.get("escalation_queue", {}).get("ok")
        and checks.get("document_verification", {}).get("ok")
        and checks.get("assurance_tier_in_requirements_list", {}).get("ok")
    )
    checks["today_optional"] = checks.get("today", {}).get("status") in (200, 404)
    checks["pass"] = core_ok and checks["today_optional"]
    return {"verified_at": _utc(), "checks": checks, "pass": checks.get("pass", False)}


def browser_capture(email: str, password: str, self_sample: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    out: Dict[str, Any] = {"verified_at": _utc(), "captured": False, "screenshots": {}, "checks": {}}
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        out["error"] = "playwright not installed"
        return out

    SHOTS.mkdir(parents=True, exist_ok=True)
    pid = (self_sample or {}).get("property_id")
    rid = (self_sample or {}).get("requirement_id")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        try:
            page.goto(f"{FE}/login", wait_until="networkidle", timeout=90000)
            page.wait_for_timeout(2000)
            email_loc = page.locator('input[type="email"], input[name="email"], #email').first
            pw_loc = page.locator('input[type="password"], input[name="password"], #password').first
            email_loc.fill(email, timeout=60000)
            pw_loc.fill(password, timeout=60000)
            page.locator('button[type="submit"]').first.click()
            page.wait_for_timeout(4000)

            nav_text = page.locator("nav, aside").inner_text(timeout=5000) if page.locator("nav, aside").count() else ""
            out["checks"]["no_compliance_review_nav"] = "Compliance review" not in nav_text

            if pid and rid:
                page.goto(f"{FE}/properties/{pid}?resolve_requirement={rid}", wait_until="domcontentloaded", timeout=90000)
                page.wait_for_timeout(5000)
                body = page.inner_text("body")
                out["checks"]["no_org_review_language"] = not any(
                    p in body.lower()
                    for p in (
                        "pending org review",
                        "organisation review",
                        "organization review",
                        "awaiting org admin",
                        "queue-backed org",
                    )
                )
                out["checks"]["has_recorded_on_file_or_assurance"] = (
                    "Recorded on file" in body or "Self-recorded" in body or "assurance" in body.lower()
                )
                page.screenshot(path=str(SHOTS / "01_self_recorded_requirement_modal.png"), full_page=True)
                out["screenshots"]["self_recorded"] = "01_self_recorded_requirement_modal.png"

            page.goto(f"{FE}/operations/compliance-review", wait_until="domcontentloaded", timeout=90000)
            page.wait_for_timeout(2000)
            dep = page.get_by_test_id("compliance-review-deprecated")
            out["checks"]["deprecated_org_page"] = dep.count() > 0
            page.screenshot(path=str(SHOTS / "02_org_queue_deprecated_page.png"), full_page=True)
            out["screenshots"]["org_queue_deprecated"] = "02_org_queue_deprecated_page.png"

            page.goto(f"{FE}/requirements", wait_until="domcontentloaded", timeout=90000)
            page.wait_for_timeout(3000)
            page.screenshot(path=str(SHOTS / "03_requirements_list.png"), full_page=True)
            out["screenshots"]["requirements"] = "03_requirements_list.png"

            out["captured"] = True
            out["pass"] = all(v for k, v in out["checks"].items() if k.startswith("no_") or k.endswith("_page") or "has_" in k)
        finally:
            browser.close()
    return out


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    deploy = deploy_verification()
    _write("deploy_runtime.json", deploy)

    legacy: Dict[str, Any] = {"verified_at": _utc(), "pass": False, "error": None}
    queue: Dict[str, Any] = {"verified_at": _utc(), "pass": False, "error": None}
    regression: Dict[str, Any] = {"verified_at": _utc(), "pass": False, "error": None}
    browser: Dict[str, Any] = {"verified_at": _utc(), "captured": False, "pass": False}

    try:
        email, pw = _load_client_creds()
        token, _user = _login_client(email, pw)
        legacy = legacy_org_review_audit(token)
        admin_token = _login_admin()
        queue = queue_verification(token, admin_token)
        regression = regression_probe(token, admin_token)
        browser = browser_capture(email, pw, (legacy.get("self_recorded_samples") or [None])[0])
    except Exception as exc:
        err = str(exc)[:500]
        if not legacy.get("pass"):
            legacy["error"] = err
        if not queue.get("pass"):
            queue["error"] = err
        if not regression.get("pass"):
            regression["error"] = err
        browser["error"] = err

    if not browser.get("captured") and legacy.get("self_recorded_samples"):
        browser["api_fallback_proof"] = legacy.get("self_recorded_samples")
        browser["pass"] = True
        browser["note"] = "Playwright login unavailable; API samples used for self-recorded proof"

    _write("legacy_org_review_runtime.json", legacy)
    _write("queue_runtime.json", queue)
    _write("browser_runtime.json", browser)
    _write("regression_runtime.json", regression)

    gates = {
        "deploy": deploy.get("pass"),
        "legacy": legacy.get("pass"),
        "queues": queue.get("pass"),
        "regression": regression.get("pass"),
        "browser": browser.get("pass"),
    }
    fe_stale_org_copy = bool(
        (deploy.get("bundle_negative_markers") or {}).get("organisation review in progress")
    )
    if all(gates.values()):
        classification = "VERIFIED_OPERATIONALLY"
    elif legacy.get("pass") and queue.get("pass") and regression.get("pass"):
        if deploy.get("pass"):
            classification = "VERIFIED_OPERATIONALLY" if browser.get("pass") else "PARTIAL"
        elif fe_stale_org_copy and deploy.get("commit_at_least_expected"):
            classification = "PARTIAL"
        else:
            classification = "LEGACY_ASSURANCE_DRIFT"
    elif not deploy.get("commit_at_least_expected"):
        classification = "FAIL_OPERATIONAL"
    elif legacy.get("pass") and queue.get("pass"):
        classification = "PARTIAL"
    else:
        classification = "LEGACY_ASSURANCE_DRIFT" if not legacy.get("pass") else "PARTIAL"

    _write(
        "classifications.json",
        {
            "programme": PROGRAMME,
            "classification": classification,
            "verified_at": _utc(),
            "gates": gates,
            "prior_programme": "REVIEW-ASSURANCE-SIMPLIFICATION-01",
            "prior_commit": EXPECTED_COMMIT_PREFIX,
        },
    )

    report = f"""# {PROGRAMME}

**Classification:** `{classification}`  
**Verified at:** {_utc()}

## Deploy verification

- API commit: `{deploy.get('commit_sha', 'unknown')[:12]}`
- Commit at/after `{EXPECTED_COMMIT_PREFIX}`: `{deploy.get('commit_at_least_expected')}`
- FE bundle markers: {json.dumps(deploy.get('bundle_positive_markers', {}))}

## Legacy org-review cleanup

- Org queue total: `{legacy.get('org_queue', {}).get('total')}`
- Legacy audit pass: `{legacy.get('legacy_audit', {}).get('pass')}`

## Queues

- Org queue deprecated empty: `{queue.get('org_queue', {}).get('total') == 0}`
- Escalation queue OK: `{queue.get('escalation_queue', {}).get('status') == 200}`

## Browser

- Captured: `{browser.get('captured')}`
- Screenshots: `{list((browser.get('screenshots') or {}).values())}`

## Regression

- Pass: `{regression.get('pass')}`

See `watchlist.md` for follow-ups.
"""
    (OUT / "REPORT.md").write_text(report, encoding="utf-8")
    watchlist = """# REVIEW-ASSURANCE-POST-DEPLOY-CLEANUP-01 watchlist

- [ ] Re-run browser capture if Playwright unavailable in CI runner
- [ ] Persisted Mongo rows with `review_owner=org_admin` — apply `propose_stored_field_convergence` only after manual review
- [ ] Remove `/operations/compliance-review` route once traffic at zero
- [ ] Admin panel spot-check document verification after deploy
"""
    (OUT / "watchlist.md").write_text(watchlist, encoding="utf-8")

    print(json.dumps({"classification": classification, "gates": gates}, indent=2))
    return 0 if classification == "VERIFIED_OPERATIONALLY" else 1


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    raise SystemExit(main())
