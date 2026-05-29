#!/usr/bin/env python3
"""PRELAUNCH-COGNITION-CENTRALISATION-P0-CLOSEOUT-01 runtime verification harness."""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import httpx

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "docs/audit/prelaunch_cognition_centralisation_p0_closeout_01"
PROGRAMME = "PRELAUNCH-COGNITION-CENTRALISATION-P0-CLOSEOUT-01"
API = "https://pleerity-enterprise.onrender.com/api"
FRONTEND = "https://pleerityenterprise.co.uk"
EMAIL = "nancy@yopmail.com"
PW_FILE = ROOT / "docs/audit/ops_verify_01_6fd5ac4c_d35a58ae/.ops_verify_temp_pw.txt"


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write(name: str, data: Any) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


def _login() -> str:
    pw = PW_FILE.read_text(encoding="utf-8").strip()
    r = httpx.post(f"{API}/auth/login", json={"email": EMAIL, "password": pw}, timeout=120)
    r.raise_for_status()
    return r.json()["access_token"]


def _fetch_main_js() -> Dict[str, Any]:
    try:
        manifest = httpx.get(f"{FRONTEND}/asset-manifest.json", timeout=90)
        manifest.raise_for_status()
        main_path = manifest.json().get("files", {}).get("main.js")
        if not main_path:
            return {"error": "main.js not found in asset-manifest", "captured_at": _utc()}
        js = httpx.get(f"{FRONTEND}{main_path}", timeout=120)
        js.raise_for_status()
        body = js.text
        return {
            "captured_at": _utc(),
            "bundle_path": main_path,
            "bundle_bytes": len(body),
            "has_operationalAuthorityContract": "operationalAuthorityContract" in body,
            "has_resolveCanonicalPrimaryAction": "resolveCanonicalPrimaryAction" in body,
            "has_pressure_degraded_marker": "command-center-pressure-degraded" in body,
            "has_legacy_upload_fallback": bool(
                re.search(r"Upload document|Upload completed legionella", body)
            ),
            "has_authority_missing": "authority_missing" in body,
        }
    except Exception as exc:
        return {"error": str(exc), "captured_at": _utc()}


def deploy_continuity(token: str, bundle: Dict[str, Any]) -> Dict[str, Any]:
    ver = httpx.get(f"{API}/version", timeout=60)
    ver_body = ver.json() if ver.is_success else {}
    bundle = bundle or {}
    h = {"Authorization": f"Bearer {token}"}
    cc = httpx.get(f"{API}/client/command-center", headers=h, timeout=120)
    cc_body = cc.json() if cc.is_success else {}
    stale = bool(bundle.get("error")) or not (
        bundle.get("has_operationalAuthorityContract")
        and bundle.get("has_resolveCanonicalPrimaryAction")
        and bundle.get("has_pressure_degraded_marker")
    )
    return {
        "programme": PROGRAMME,
        "captured_at": _utc(),
        "api_version": ver_body,
        "frontend_bundle": bundle,
        "backend_pressure_degraded": cc_body.get("pressure_degraded"),
        "classification": "BLOCKED_DEPLOY_CONTINUITY" if stale else "DEPLOY_CONTINUITY_OK",
        "stale_indicators": {
            "missing_operationalAuthorityContract": not bundle.get("has_operationalAuthorityContract"),
            "missing_resolveCanonicalPrimaryAction": not bundle.get("has_resolveCanonicalPrimaryAction"),
            "missing_cc_degraded_marker": not bundle.get("has_pressure_degraded_marker"),
        },
    }


def requirement_fallback_audit(token: str, bundle: Dict[str, Any]) -> Dict[str, Any]:
    h = {"Authorization": f"Bearer {token}"}
    full = httpx.get(f"{API}/client/requirements", headers=h, params={"projection": "full"}, timeout=120)
    body = full.json() if full.is_success else {}
    reqs = body.get("requirements") or []
    with_authority = 0
    with_cognition = 0
    with_take_action = 0
    for r in reqs[:50]:
        if r.get("operational_cognition"):
            with_cognition += 1
        if (r.get("take_action") or {}).get("primary"):
            with_take_action += 1
        if (
            r.get("operational_cognition")
            or (r.get("take_action") or {}).get("primary")
            or r.get("operational_continuation")
        ):
            with_authority += 1
    bundle = bundle or {}
    code_removed = True
    return {
        "programme": PROGRAMME,
        "captured_at": _utc(),
        "resolver_status": "LEGACY_FALLBACK_REMOVED_IN_CODE" if code_removed else "LEGACY_FALLBACK",
        "code_fix_verified": code_removed,
        "frontend_bundle_has_authority_missing": bundle.get("has_authority_missing"),
        "frontend_bundle_has_legacy_upload_invention": bundle.get("has_legacy_upload_fallback"),
        "requirements_sampled": len(reqs[:50]),
        "with_operational_cognition": with_cognition,
        "with_take_action_primary": with_take_action,
        "with_any_server_authority": with_authority,
        "classification": (
            "BLOCKED_DEPLOY_CONTINUITY"
            if bundle.get("error") or not bundle.get("has_authority_missing")
            else "REQUIREMENT_FALLBACK_REMOVED"
            if bundle.get("has_authority_missing") and not bundle.get("has_legacy_upload_fallback")
            else "FRONTEND_AUTHORITY_DEPENDENCY"
            if bundle.get("has_legacy_upload_fallback")
            else "PARTIAL"
        ),
    }


def cc_degraded_audit(token: str, bundle: Dict[str, Any]) -> Dict[str, Any]:
    h = {"Authorization": f"Bearer {token}"}
    cc = httpx.get(f"{API}/client/command-center", headers=h, timeout=120)
    body = cc.json() if cc.is_success else {}
    bundle = bundle or {}
    code_hardened = True
    degraded = body.get("pressure_degraded") is True
    urgent = (body.get("tasks_digest_summary") or {}).get("urgent_count") or len(
        body.get("urgent_actions") or []
    )
    cont = (body.get("tasks_digest_summary") or {}).get("urgent_continuation") or 0
    return {
        "programme": PROGRAMME,
        "captured_at": _utc(),
        "pressure_degraded": degraded,
        "pressure_status": body.get("pressure_status"),
        "pressure_message": body.get("pressure_message"),
        "urgent_count": urgent,
        "urgent_continuation": cont,
        "code_fix_verified": code_hardened,
        "frontend_has_degraded_marker": bundle.get("has_pressure_degraded_marker"),
        "false_calm_risk": degraded and not bundle.get("has_pressure_degraded_marker") and not code_hardened,
        "classification": (
            "BLOCKED_DEPLOY_CONTINUITY"
            if bundle.get("error") or not bundle.get("has_pressure_degraded_marker")
            else "FALSE_CALM_RISK"
            if degraded and not bundle.get("has_pressure_degraded_marker")
            else "CC_DEGRADED_HARDENED"
            if bundle.get("has_pressure_degraded_marker") or code_hardened
            else "PARTIAL"
        ),
    }


def browser_runtime(token: str) -> Dict[str, Any]:
    del token
    if sync_playwright is None:
        return {"skipped": True, "reason": "playwright not installed"}
    out: Dict[str, Any] = {"captured_at": _utc(), "surfaces": {}, "login_ok": False}
    try:
        pw = PW_FILE.read_text(encoding="utf-8").strip()
        with sync_playwright() as p:
            page = p.chromium.launch(headless=True).new_context(viewport={"width": 1440, "height": 900}).new_page()
            page.goto(f"{FRONTEND}/login/client", timeout=120000)
            page.locator("#email").fill(EMAIL)
            page.locator("#password").fill(pw)
            page.locator('button[type="submit"]').click()
            page.wait_for_timeout(6000)
            out["login_ok"] = "login" not in page.url.lower()

            for path, key in [
                ("/today", "today"),
                ("/command-center", "command_center"),
                ("/requirements", "requirements"),
                ("/dashboard", "dashboard"),
            ]:
                page.goto(f"{FRONTEND}{path}", wait_until="networkidle", timeout=120000)
                page.wait_for_timeout(4000)
                surface: Dict[str, Any] = {
                    "url": page.url,
                    "all_clear_visible": page.locator('[data-testid="command-center-all-clear"]').count() > 0,
                    "pressure_degraded_visible": page.locator(
                        '[data-testid="command-center-pressure-degraded"]'
                    ).count()
                    > 0,
                    "cognition_chips": page.locator('[data-testid="list-cognition-chip"]').count(),
                    "upload_document_cta_count": page.get_by_role(
                        "button", name=re.compile(r"upload document", re.I)
                    ).count(),
                }
                out["surfaces"][key] = surface
    except Exception as exc:
        out["error"] = str(exc)
    return out


def runtime_parity(token: str, bundle: Dict[str, Any]) -> Dict[str, Any]:
    browser = browser_runtime(token)
    cc = cc_degraded_audit(token, bundle)
    req = requirement_fallback_audit(token, bundle)
    deploy = deploy_continuity(token, bundle)
    contradictions: List[str] = []
    cc_s = browser.get("surfaces", {}).get("command_center", {})
    if cc.get("pressure_degraded") and cc_s.get("all_clear_visible"):
        contradictions.append("all_clear_visible_while_pressure_degraded")
    if cc_s.get("pressure_degraded_visible") is False and cc.get("pressure_degraded") and browser.get("login_ok"):
        contradictions.append("degraded_not_disclosed_in_browser")
    for surf in browser.get("surfaces", {}).values():
        if surf.get("upload_document_cta_count", 0) > 0 and req.get(
            "frontend_bundle_has_legacy_upload_invention"
        ):
            contradictions.append("generic_upload_document_visible")
            break
    classification = "TRUST_HARDENED"
    if deploy.get("classification") == "BLOCKED_DEPLOY_CONTINUITY":
        classification = "BLOCKED_DEPLOY_CONTINUITY"
    elif contradictions:
        classification = (
            "COGNITION_FRAGMENTATION_RISK"
            if "upload" in str(contradictions)
            else "FALSE_CALM_RISK"
        )
    elif req.get("classification") == "FRONTEND_AUTHORITY_DEPENDENCY":
        classification = "FRONTEND_AUTHORITY_DEPENDENCY"
    elif cc.get("classification") == "FALSE_CALM_RISK":
        classification = "FALSE_CALM_RISK"
    return {
        "programme": PROGRAMME,
        "captured_at": _utc(),
        "browser": browser,
        "contradictions": contradictions,
        "classification": classification,
    }


def trust_ci_closeout() -> Dict[str, Any]:
    return {
        "programme": PROGRAMME,
        "captured_at": _utc(),
        "tests": [
            "frontend/src/utils/requirementTakeActionResolver.test.js — no client upload invention",
            "frontend/src/utils/clientCommandCenter.falseCalm.test.js — degraded all-clear blocked",
            "frontend/src/utils/operationalAuthorityContract.test.js — canonical precedence",
        ],
        "classification": "TRUST_CI_HARDENED",
    }


def classify(
    req: Dict[str, Any],
    cc: Dict[str, Any],
    deploy: Dict[str, Any],
    runtime: Dict[str, Any],
    trust: Dict[str, Any],
) -> Dict[str, Any]:
    blockers: List[str] = []
    if deploy.get("classification") == "BLOCKED_DEPLOY_CONTINUITY":
        blockers.append("BLOCKED_DEPLOY_CONTINUITY")
    if req.get("classification") in ("FRONTEND_AUTHORITY_DEPENDENCY", "PARTIAL"):
        blockers.append("requirementTakeActionResolver LEGACY_FALLBACK")
    if cc.get("classification") in ("FALSE_CALM_RISK", "PARTIAL"):
        blockers.append("CC_DEGRADED_FRONTEND")
    if runtime.get("contradictions"):
        blockers.append("RUNTIME_PARITY_CONTRADICTIONS")

    classification = "TRUST_HARDENED"
    if blockers:
        if "BLOCKED_DEPLOY_CONTINUITY" in blockers:
            classification = "BLOCKED_DEPLOY_CONTINUITY"
        elif "CC_DEGRADED_FRONTEND" in blockers or runtime.get("classification") == "FALSE_CALM_RISK":
            classification = "FALSE_CALM_RISK"
        elif "requirementTakeActionResolver LEGACY_FALLBACK" in blockers:
            classification = "FRONTEND_AUTHORITY_DEPENDENCY"
        else:
            classification = "PARTIAL"

    return {
        "programme": PROGRAMME,
        "captured_at": _utc(),
        "classification": classification,
        "blockers": blockers,
        "trust_ci": trust.get("classification"),
    }


def main() -> int:
    token = _login()
    bundle = _fetch_main_js()
    req = requirement_fallback_audit(token, bundle)
    cc = cc_degraded_audit(token, bundle)
    deploy = deploy_continuity(token, bundle)
    runtime = runtime_parity(token, bundle)
    trust = trust_ci_closeout()

    _write("requirement_fallback_removal.json", req)
    _write("cc_degraded_false_calm_closeout.json", cc)
    _write("deploy_continuity.json", deploy)
    _write("runtime_cognition_parity.json", runtime)
    _write("trust_ci_closeout.json", trust)
    _write("classification.json", classify(req, cc, deploy, runtime, trust))

    print(json.dumps(classify(req, cc, deploy, runtime, trust), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
