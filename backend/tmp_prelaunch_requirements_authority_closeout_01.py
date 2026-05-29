#!/usr/bin/env python3
"""PRELAUNCH-REQUIREMENTS-AUTHORITY-REGRESSION-01 closeout after frontend deploy."""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "docs/audit/prelaunch_requirements_authority_regression_01"
SHOT = OUT / "screenshots"
PROGRAMME = "PRELAUNCH-REQUIREMENTS-AUTHORITY-REGRESSION-01-CLOSEOUT"
API = "https://pleerity-enterprise.onrender.com/api"
FRONTEND = "https://pleerityenterprise.co.uk"
LANDLORD_EMAIL = "nancy@yopmail.com"
LANDLORD_PW = ROOT / "docs/audit/ops_verify_01_6fd5ac4c_d35a58ae/.ops_verify_temp_pw.txt"
PILOT_PROPERTY = "d35a58ae-3c81-491c-9694-1d021dd3b8ad"
EXPECTED_COMMITS = ("5d71bac1", "3c5119b6")

SPECIFIC_CTA_PATTERNS = (
    "Record Legionella",
    "Upload valid",
    "Upload HMO",
    "Record registration",
    "Record deposit",
    "Add compliance evidence",
    "Record tenancy",
    "Upload portable",
    "Resolve requirement",
)


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
        body = (r.text or "")[:800]
    return {"status": r.status_code, "ok": r.is_success, "body": body}


def deploy_continuity() -> Dict[str, Any]:
    ver = httpx.get(f"{API}/version", timeout=60).json()
    commit = str(ver.get("commit_sha") or "")[:8].lower()
    manifest = httpx.get(f"{FRONTEND}/asset-manifest.json", timeout=60).json()
    main_js = httpx.get(f"{FRONTEND}{manifest['files']['main.js']}", timeout=120).text
    markers = {
        "requirementsOperational_cache_key": (
            "requirementsOperational" in main_js or "client:requirements:operational" in main_js
        ),
        "list_cognition_chip": "list-cognition-chip" in main_js,
        "pickWhyItMattersForDisplay": "pickWhyItMattersForDisplay" in main_js,
        "projection_full_param": (
            'projection:"full"' in main_js
            or "projection: 'full'" in main_js
            or 'projection:"full"' in main_js
        ),
    }
    return {
        "captured_at": _utc(),
        "backend_commit": ver.get("commit_sha"),
        "backend_commit_prefix_ok": any(commit.startswith(p[:7]) for p in EXPECTED_COMMITS),
        "frontend_markers": markers,
        "gate_pass": markers["list_cognition_chip"] and markers["projection_full_param"],
    }


def _network_full_projection(token: str) -> Dict[str, Any]:
    """Intercept requirements API call from browser via direct fetch after login."""
    body = _get(token, "/client/requirements", projection="full").get("body") or {}
    pres = body.get("presentation") or {}
    rows = body.get("requirements") or []
    sample = rows[0] if rows else {}
    return {
        "presentation": pres,
        "row_count": len(rows),
        "sample_has_take_action": bool((sample.get("take_action") or {}).get("primary")),
        "sample_has_cognition": bool(sample.get("operational_cognition")),
        "sample_has_why": bool(sample.get("why_it_matters_long") or sample.get("why_it_matters_short")),
    }


def browser_requirements_page(token: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "captured_at": _utc(),
        "login_ok": False,
        "page_loaded": False,
        "generic_upload_count": 0,
        "no_description_count": 0,
        "specific_cta_labels": [],
        "cognition_chip_count": 0,
        "requirement_row_count": 0,
        "network_capture": _network_full_projection(token),
        "gate_pass": False,
        "notes": [],
    }
    if sync_playwright is None:
        out["notes"].append("playwright_unavailable")
        return out

    pw = LANDLORD_PW.read_text(encoding="utf-8").strip()
    api_full_rows: List[Dict[str, Any]] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        def on_response(resp):
            if "/client/requirements" in resp.url and resp.request.method == "GET":
                try:
                    data = resp.json()
                    if isinstance(data, dict) and data.get("requirements"):
                        api_full_rows.append(data)
                except Exception:
                    pass

        page.on("response", on_response)
        page.goto(f"{FRONTEND}/login/client", timeout=120_000)
        page.wait_for_timeout(1500)
        page.locator("#email").fill(LANDLORD_EMAIL)
        page.locator("#password").fill(pw)
        page.locator('button[type="submit"]').click()
        page.wait_for_timeout(6000)
        out["login_ok"] = "login" not in page.url.lower()

        page.goto(f"{FRONTEND}/requirements", wait_until="domcontentloaded", timeout=120_000)
        try:
            page.wait_for_selector('[data-testid="requirements-loading"]', state="hidden", timeout=90_000)
        except Exception:
            pass
        page.wait_for_timeout(3000)
        out["page_loaded"] = "/requirements" in page.url

        # Rows live inside collapsed property accordions — expand property sections.
        accordion_items = page.locator('[data-testid^="accordion-property-"]')
        tcount = accordion_items.count()
        for i in range(min(tcount, 10)):
            try:
                item = accordion_items.nth(i)
                trigger = item.locator("button").first
                if trigger.count():
                    trigger.click(force=True)
                    page.wait_for_timeout(500)
            except Exception:
                pass
        try:
            page.wait_for_selector('[data-testid^="requirement-row-"]', timeout=30_000)
        except Exception:
            out["notes"].append("requirement_rows_not_visible_after_accordion_expand")

        out["accordion_expanded"] = tcount
        out["requirement_row_count"] = page.locator('[data-testid^="requirement-row-"]').count()
        out["generic_upload_count"] = page.get_by_role("button", name=re.compile(r"^Upload document\b", re.I)).count()
        out["no_description_count"] = page.get_by_text("No description available", exact=True).count()
        out["cognition_chip_count"] = page.locator('[data-testid="list-cognition-chip"]').count()

        primary_buttons = page.locator('[data-testid^="requirement-primary-cta-"]')
        n = min(primary_buttons.count(), 12)
        labels: List[str] = []
        for i in range(n):
            labels.append(primary_buttons.nth(i).inner_text().strip().replace("\n", " "))
        out["specific_cta_labels"] = labels

        if api_full_rows:
            last = api_full_rows[-1]
            out["runtime_api_presentation"] = last.get("presentation")
            out["runtime_api_projection_full"] = "full" in str(
                (last.get("presentation") or {}).get("projection") or ""
            ).lower() or not (last.get("presentation") or {}).get("enrichment_deferred")
        else:
            out["notes"].append("requirements_api_not_captured_in_browser")

        SHOT.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOT / f"requirements_closeout_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.png"), full_page=True)
        browser.close()

    specific_non_generic = [l for l in out["specific_cta_labels"] if l and not re.match(r"^Upload document\s*>?$", l, re.I)]
    out["specific_cta_count"] = len(specific_non_generic)
    out["gate_pass"] = (
        out["login_ok"]
        and out["page_loaded"]
        and out["no_description_count"] == 0
        and out["specific_cta_count"] >= 3
        and out["generic_upload_count"] < max(2, out["specific_cta_count"])
        and out["cognition_chip_count"] >= 1
        and (out.get("runtime_api_projection_full") is not False)
    )
    return out


def cross_surface_parity(token: str) -> Dict[str, Any]:
    full_body = _get(token, "/client/requirements", projection="full").get("body") or {}
    rows = full_body.get("requirements") or []
    samples: List[Dict[str, Any]] = []
    targets = []
    for r in rows:
        if str(r.get("property_id")) == PILOT_PROPERTY and str(r.get("client_lifecycle_state")) == "ACTION_REQUIRED":
            targets.append(r)
        if len(targets) >= 5:
            break
    if not targets:
        targets = [r for r in rows if r.get("take_action")][:5]

    contradictions: List[Dict[str, Any]] = []
    for r in targets:
        rid = str(r.get("requirement_id") or "")
        pid = str(r.get("property_id") or PILOT_PROPERTY)
        detail = _get(token, f"/requirements/{rid}").get("body") or {}
        req_d = detail.get("requirement") if isinstance(detail.get("requirement"), dict) else {}
        er = _get(token, f"/client/properties/{pid}/requirements/{rid}/evidence-resolution").get("body") or {}
        list_label = ((r.get("take_action") or {}).get("primary") or {}).get("label")
        detail_label = ((req_d.get("take_action") or {}).get("primary") or {}).get("label")
        er_guidance = (er.get("requirement_guidance_v1") or {}).get("recommended_next_step")
        cog_list = ((r.get("operational_cognition") or {}).get("list_guidance") or {}).get("recommended_action_label")
        entry = {
            "requirement_id": rid,
            "requirement_type": r.get("requirement_type"),
            "list_take_action": list_label,
            "detail_take_action": detail_label,
            "evidence_resolution_guidance": er_guidance,
            "list_cognition_chip_label": cog_list,
            "has_why_it_matters": bool(r.get("why_it_matters_long") or r.get("why_it_matters_short")),
        }
        if list_label and detail_label and list_label.strip() != detail_label.strip():
            contradictions.append({"rid": rid, "a": "list", "b": "detail", "va": list_label, "vb": detail_label})
        samples.append(entry)

    return {
        "captured_at": _utc(),
        "samples": samples,
        "contradiction_count": len(contradictions),
        "contradictions": contradictions,
        "gate_pass": len(contradictions) == 0 and len(samples) >= 2,
    }


def classify(deploy: Dict[str, Any], browser: Dict[str, Any], cross: Dict[str, Any]) -> Dict[str, Any]:
    blockers: List[str] = []
    if not deploy.get("gate_pass"):
        blockers.append("deploy_continuity_failed")
    if not browser.get("gate_pass"):
        if browser.get("no_description_count", 0) > 0:
            blockers.append("no_description_fallback_visible")
        if browser.get("generic_upload_count", 0) >= browser.get("specific_cta_count", 0):
            blockers.append("generic_upload_document_drift")
        if browser.get("cognition_chip_count", 0) < 1:
            blockers.append("cognition_chip_missing")
        if not browser.get("login_ok"):
            blockers.append("browser_login_failed")
    if not cross.get("gate_pass"):
        if cross.get("contradiction_count", 0) > 0:
            blockers.append("cross_surface_contradictions")
        elif len(cross.get("samples") or []) < 2:
            blockers.append("insufficient_cross_surface_samples")

    label = "VERIFIED_OPERATIONALLY" if not blockers else "PARTIAL" if len(blockers) <= 1 else "AUTHORITY_REGRESSION_PRESENT"
    return {
        "classification": label,
        "blockers": blockers,
        "push_audit_artifacts_allowed": label == "VERIFIED_OPERATIONALLY",
        "evaluated_at": _utc(),
    }


def main() -> int:
    print(f"[{PROGRAMME}] {_utc()}")
    deploy = deploy_continuity()
    _write("deploy_continuity.json", deploy)

    token = _login()
    browser = browser_requirements_page(token)
    _write("browser_runtime.json", browser)
    _write("cta_regression.json", {
        "generic_upload_count": browser.get("generic_upload_count"),
        "specific_cta_labels": browser.get("specific_cta_labels"),
        "specific_cta_count": browser.get("specific_cta_count"),
        "gate_pass": browser.get("specific_cta_count", 0) >= 3 and browser.get("generic_upload_count", 0) < browser.get("specific_cta_count", 0),
    })
    _write("description_regression.json", {
        "no_description_count": browser.get("no_description_count"),
        "gate_pass": browser.get("no_description_count") == 0,
    })
    _write("cognition_parity.json", {
        "cognition_chip_count": browser.get("cognition_chip_count"),
        "runtime_api": browser.get("runtime_api_presentation"),
        "gate_pass": browser.get("cognition_chip_count", 0) >= 1,
    })

    cross = cross_surface_parity(token)
    _write("cross_surface_consistency.json", cross)

    cls = classify(deploy, browser, cross)
    _write("classifications.json", cls)

    watchlist = (
        "# Watchlist\n\n"
        f"- Classification: **{cls['classification']}**\n"
        f"- Blockers: {', '.join(cls.get('blockers') or []) or 'none'}\n"
        "- Invariant: operational UI must never use `projection=list`.\n"
        "- `OPERATIONAL_CACHE_KEYS.requirements` remains list projection for KPI surfaces only.\n"
    )
    (OUT / "watchlist.md").write_text(watchlist, encoding="utf-8")

    report = f"""# {PROGRAMME}

Generated: {_utc()}

## Classification

**{cls['classification']}**

## Deploy continuity

- Backend commit: `{deploy.get('backend_commit')}`
- Frontend markers: {json.dumps(deploy.get('frontend_markers'), indent=2)}

## Browser proof

- Login: {browser.get('login_ok')}
- Generic Upload document buttons: {browser.get('generic_upload_count')}
- No description available: {browser.get('no_description_count')}
- Cognition chips: {browser.get('cognition_chip_count')}
- Sample CTAs: {', '.join((browser.get('specific_cta_labels') or [])[:6])}

## Cross-surface

- Contradictions: {cross.get('contradiction_count')}

## Projection safety invariant

- `projection=list` → stats/KPI/lightweight only (`enrichment_deferred: true`)
- Operational surfaces (Requirements workspace, detail, evidence modal) → `projection=full`

## Blockers

{chr(10).join('- ' + b for b in cls.get('blockers') or []) or '- none'}
"""
    (OUT / "REPORT.md").write_text(report, encoding="utf-8")
    print(json.dumps(cls, indent=2))
    return 0 if cls["classification"] == "VERIFIED_OPERATIONALLY" else 2


if __name__ == "__main__":
    sys.exit(main())
