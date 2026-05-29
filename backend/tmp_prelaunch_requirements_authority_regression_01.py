#!/usr/bin/env python3
"""PRELAUNCH-REQUIREMENTS-AUTHORITY-REGRESSION-01 — list vs full projection + browser parity."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import httpx

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "docs/audit/prelaunch_requirements_authority_regression_01"
PROGRAMME = "PRELAUNCH-REQUIREMENTS-AUTHORITY-REGRESSION-01"
API = "https://pleerity-enterprise.onrender.com/api"
FRONTEND = "https://pleerityenterprise.co.uk"
LANDLORD_EMAIL = "nancy@yopmail.com"
LANDLORD_PW = ROOT / "docs/audit/ops_verify_01_6fd5ac4c_d35a58ae/.ops_verify_temp_pw.txt"
PILOT_PROPERTY = "d35a58ae-3c81-491c-9694-1d021dd3b8ad"


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write(name: str, data: Any) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


def _login() -> str:
    pw = LANDLORD_PW.read_text(encoding="utf-8").strip()
    r = httpx.post(f"{API}/auth/login", json={"email": LANDLORD_EMAIL, "password": pw}, timeout=120)
    r.raise_for_status()
    return r.json()["access_token"]


def _get(token: str, path: str, **params: Any) -> Dict[str, Any]:
    r = httpx.get(f"{API}{path}", headers={"Authorization": f"Bearer {token}"}, params=params or None, timeout=120)
    try:
        body = r.json()
    except Exception:
        body = (r.text or "")[:500]
    return {"status": r.status_code, "ok": r.is_success, "body": body}


def audit_projection_divergence(token: str) -> Dict[str, Any]:
    list_body = _get(token, "/client/requirements", projection="list").get("body") or {}
    full_body = _get(token, "/client/requirements", projection="full").get("body") or {}
    list_rows = list_body.get("requirements") or []
    full_rows = full_body.get("requirements") or []
    full_by_id = {str(r.get("requirement_id")): r for r in full_rows if r.get("requirement_id")}

    findings: List[Dict[str, Any]] = []
    for lr in list_rows[:25]:
        rid = str(lr.get("requirement_id") or "")
        fr = full_by_id.get(rid) or {}
        list_ta = (lr.get("take_action") or {}).get("primary", {}).get("label") if isinstance(lr.get("take_action"), dict) else None
        full_ta = (fr.get("take_action") or {}).get("primary", {}).get("label") if isinstance(fr.get("take_action"), dict) else None
        list_desc = bool(lr.get("why_it_matters_long") or lr.get("why_it_matters_short") or lr.get("description"))
        full_desc = bool(fr.get("why_it_matters_long") or fr.get("why_it_matters_short") or fr.get("description"))
        findings.append(
            {
                "requirement_id": rid,
                "requirement_type": lr.get("requirement_type") or lr.get("requirement_code"),
                "list_has_take_action": bool(list_ta),
                "full_has_take_action": bool(full_ta),
                "list_primary_label": list_ta,
                "full_primary_label": full_ta,
                "list_has_description": list_desc,
                "full_has_description": full_desc,
                "list_cognition": bool(lr.get("operational_cognition")),
                "full_cognition": bool(fr.get("operational_cognition")),
                "regression_if_list_used_for_ui": not list_ta and bool(full_ta),
            }
        )

    regressed = [f for f in findings if f.get("regression_if_list_used_for_ui")]
    return {
        "captured_at": _utc(),
        "list_deferred": (list_body.get("presentation") or {}).get("enrichment_deferred"),
        "full_projection": (full_body.get("presentation") or {}).get("projection"),
        "samples": len(findings),
        "regression_samples": len(regressed),
        "findings": findings,
        "root_cause": "list projection omits take_action and registry copy; UI must use projection=full",
    }


def browser_requirements_page(token: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {"captured_at": _utc(), "gate_pass": False, "generic_upload_count": 0, "no_description_count": 0, "specific_cta_count": 0, "notes": []}
    if sync_playwright is None:
        out["notes"].append("playwright_unavailable")
        return out
    pw = LANDLORD_PW.read_text(encoding="utf-8").strip()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto(f"{FRONTEND}/login/client", timeout=120_000)
        page.wait_for_timeout(1500)
        page.locator("#email").fill(LANDLORD_EMAIL)
        page.locator("#password").fill(pw)
        page.locator('button[type="submit"]').click()
        page.wait_for_timeout(5000)
        page.goto(f"{FRONTEND}/requirements", wait_until="networkidle", timeout=120_000)
        page.wait_for_timeout(8000)
        upload_btns = page.locator('button:has-text("Upload document")')
        out["generic_upload_count"] = upload_btns.count()
        out["no_description_count"] = page.locator('text=No description available').count()
        out["specific_cta_count"] = page.locator(
            'button:has-text("Record"), button:has-text("Add compliance evidence"), button:has-text("Upload valid"), button:has-text("Upload HMO"), button:has-text("Upload portable")'
        ).count()
        out["cognition_chip_count"] = page.locator('[data-testid="list-cognition-chip"]').count()
        (OUT / "screenshots").mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(OUT / "screenshots" / "requirements_page.png"), full_page=True)
        browser.close()
    out["gate_pass"] = (
        out["no_description_count"] == 0
        and out["specific_cta_count"] >= 3
        and out["generic_upload_count"] < max(3, out["specific_cta_count"])
    )
    return out


def classify(audit: Dict[str, Any], browser: Dict[str, Any]) -> Dict[str, Any]:
    blockers: List[str] = []
    if audit.get("regression_samples", 0) < 3:
        blockers.append("insufficient_projection_divergence_proof")
    if not browser.get("gate_pass"):
        if browser.get("no_description_count", 0) > 0:
            blockers.append("no_description_fallback_visible")
        if browser.get("generic_upload_count", 0) >= browser.get("specific_cta_count", 0):
            blockers.append("generic_upload_document_drift")
    label = "VERIFIED_OPERATIONALLY" if not blockers else "PARTIAL" if len(blockers) == 1 else "AUTHORITY_REGRESSION_PRESENT"
    return {
        "classification": label,
        "blockers": blockers,
        "push_audit_artifacts_allowed": label == "VERIFIED_OPERATIONALLY",
        "evaluated_at": _utc(),
    }


def main() -> int:
    print(f"[{PROGRAMME}] {_utc()}")
    token = _login()
    audit = audit_projection_divergence(token)
    _write("authority_divergence.json", audit)
    _write("root_cause.json", {"programme": PROGRAMME, "summary": audit.get("root_cause")})
    browser = browser_requirements_page(token)
    _write("browser_runtime.json", browser)
    cls = classify(audit, browser)
    _write("classifications.json", cls)
    (OUT / "REPORT.md").write_text(
        f"# {PROGRAMME}\n\nClassification: **{cls['classification']}**\n\n"
        f"Root cause: main Requirements page used `projection=list` which sets `enrichment_deferred: true` "
        f"and skips `enrich_requirements_for_client` (take_action, why_it_matters, operational_cognition).\n\n"
        f"Fix: RequirementsPage requests `projection=full` via dedicated operational cache key.\n\n"
        f"Blockers: {', '.join(cls.get('blockers') or []) or 'none'}\n",
        encoding="utf-8",
    )
    print(json.dumps(cls, indent=2))
    return 0 if cls["classification"] == "VERIFIED_OPERATIONALLY" else 2


if __name__ == "__main__":
    sys.exit(main())
