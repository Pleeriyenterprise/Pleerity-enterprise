#!/usr/bin/env python3
"""
REQUIREMENT-COGNITION-GUIDANCE-ARCHITECTURE-01 — requirement/evidence flow audit + staging verification.
"""
from __future__ import annotations

import json
import re
import sys
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
OUT = ROOT / "docs/audit/requirement_cognition_guidance_architecture_01"
SHOT = OUT / "screenshots"
PROGRAMME = "REQUIREMENT-COGNITION-GUIDANCE-ARCHITECTURE-01"
RUN_TAG = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

API_BASE = "https://pleerity-enterprise.onrender.com"
API = f"{API_BASE}/api"
FRONTEND = "https://pleerityenterprise.co.uk"

LANDLORD_EMAIL = "nancy@yopmail.com"
LANDLORD_PW = ROOT / "docs/audit/ops_verify_01_6fd5ac4c_d35a58ae/.ops_verify_temp_pw.txt"
PILOT_PROPERTY = "0a5b4497-a1ba-4ee9-87e1-ae2bb9d4cc68"

GUIDANCE_FIELDS = (
    "recommended_next_step",
    "recommended_next_step_reason",
    "strongest_evidence_method",
    "weaker_alternative_methods",
    "current_progress_state",
    "missing_actions",
    "uploaded_not_submitted",
    "submitted_not_verified",
    "rejected_requires_action",
    "reviewer_requested_changes",
    "authority_confidence_level",
    "workflow_stage",
    "progression_steps",
    "operational_risk_flags",
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
    for attempt in range(4):
        try:
            r = httpx.get(f"{API}{path}", headers=headers, params=params or None, timeout=120)
            try:
                body = r.json()
            except Exception:
                body = (r.text or "")[:800]
            return {"status": r.status_code, "ok": r.is_success, "body": body}
        except Exception:
            time.sleep(2.0 * (attempt + 1))
    return {"status": 0, "ok": False, "body": "request_failed"}


def _guidance_complete(g: Any) -> Tuple[bool, List[str]]:
    if not isinstance(g, dict):
        return False, ["not_dict"]
    missing = [f for f in GUIDANCE_FIELDS if f not in g]
    if g.get("guidance_version") != "requirement_guidance_v1":
        missing.append("guidance_version")
    if g.get("read_only") is not True:
        missing.append("read_only_false")
    return len(missing) == 0, missing


def _body_dict(resp: Dict[str, Any]) -> Dict[str, Any]:
    body = resp.get("body")
    return body if isinstance(body, dict) else {}


def audit_requirement_flows(token: str) -> Dict[str, Any]:
    """Part 1 — probe requirement surfaces and detect flat/conflicting patterns."""
    findings: List[Dict[str, Any]] = []
    contradictions: List[Dict[str, Any]] = []

    reqs = _get("/client/requirements", token, projection="list")
    rows = _body_dict(reqs).get("requirements") or []
    if not isinstance(rows, list):
        rows = []

    sample_ids: List[str] = []
    for r in rows[:40]:
        rid = str(r.get("requirement_id") or "")
        if rid:
            sample_ids.append(rid)

    for rid in sample_ids[:12]:
        detail = _get(f"/requirements/{rid}", token)
        body = detail.get("body") if isinstance(detail.get("body"), dict) else {}
        req = body.get("requirement") if isinstance(body.get("requirement"), dict) else {}
        cog = req.get("operational_cognition") if isinstance(req.get("operational_cognition"), dict) else {}
        guidance = cog.get("requirement_guidance_v1") if isinstance(cog.get("requirement_guidance_v1"), dict) else {}
        ok_g, miss_g = _guidance_complete(guidance)
        list_label = (cog.get("list_guidance") or {}).get("recommended_action_label")
        detail_label = (cog.get("primary_action") or {}).get("label")
        pid = str(req.get("property_id") or PILOT_PROPERTY)
        er = _get(f"/client/properties/{pid}/requirements/{rid}/evidence-resolution", token)
        er_body = er.get("body") if isinstance(er.get("body"), dict) else {}
        er_guidance = er_body.get("requirement_guidance_v1") if isinstance(er_body.get("requirement_guidance_v1"), dict) else {}
        ok_er, miss_er = _guidance_complete(er_guidance)

        entry = {
            "requirement_id": rid,
            "property_id": pid,
            "requirement_type": req.get("requirement_type") or req.get("requirement_code"),
            "client_lifecycle_state": req.get("client_lifecycle_state"),
            "detail_guidance_present": bool(guidance),
            "detail_guidance_complete": ok_g,
            "detail_guidance_missing": miss_g,
            "evidence_resolution_guidance_present": bool(er_guidance),
            "evidence_resolution_guidance_complete": ok_er,
            "list_detail_parity": (list_label or "").strip().lower() == (detail_label or "").strip().lower()
            if list_label or detail_label
            else True,
            "detected_issues": [],
        }
        if not ok_g:
            entry["detected_issues"].append("missing_requirement_guidance_v1_on_detail")
        if not ok_er:
            entry["detected_issues"].append("missing_requirement_guidance_v1_on_evidence_resolution")
        if not entry["list_detail_parity"]:
            entry["detected_issues"].append("list_detail_cta_mismatch")
            contradictions.append(
                {
                    "requirement_id": rid,
                    "surface_a": "list_guidance",
                    "surface_b": "detail_primary_action",
                    "value_a": list_label,
                    "value_b": detail_label,
                }
            )
        if er_guidance and guidance:
            if er_guidance.get("recommended_next_step") != guidance.get("recommended_next_step"):
                contradictions.append(
                    {
                        "requirement_id": rid,
                        "surface_a": "requirement_detail",
                        "surface_b": "evidence_modal_api",
                        "value_a": guidance.get("recommended_next_step"),
                        "value_b": er_guidance.get("recommended_next_step"),
                    }
                )
                entry["detected_issues"].append("detail_modal_guidance_mismatch")
        findings.append(entry)

    return {
        "programme": PROGRAMME,
        "captured_at": _utc(),
        "samples": len(findings),
        "findings": findings,
        "contradiction_matrix": contradictions,
        "flat_hierarchy_indicators": [
            f for f in findings if "missing_requirement_guidance_v1" in str(f.get("detected_issues"))
        ],
    }


def cognition_runtime(token: str) -> Dict[str, Any]:
    rows = _body_dict(_get("/client/requirements", token, projection="list")).get("requirements") or []
    intents: List[Dict[str, Any]] = []
    for r in (rows or [])[:15]:
        rid = r.get("requirement_id")
        if not rid:
            continue
        detail = _get(f"/requirements/{rid}", token)
        body = detail.get("body") if isinstance(detail.get("body"), dict) else {}
        req = body.get("requirement") if isinstance(body.get("requirement"), dict) else {}
        g = ((req.get("operational_cognition") or {}).get("requirement_guidance_v1")) or {}
        if not g:
            continue
        intents.append(
            {
                "requirement_id": rid,
                "likely_intent": g.get("likely_intent"),
                "recommended_authority_path": g.get("recommended_authority_path"),
                "strongest_evidence_method": g.get("strongest_evidence_method"),
                "blocked_paths": g.get("blocked_paths"),
                "weak_submission_risk": g.get("weak_submission_risk"),
                "missing_required_step": g.get("missing_required_step"),
                "review_state": g.get("review_state"),
                "progression_state": g.get("progression_state"),
            }
        )
    return {"captured_at": _utc(), "samples": intents}


def next_action_dominance(token: str) -> Dict[str, Any]:
    checks: List[Dict[str, Any]] = []
    rows = _body_dict(_get("/client/requirements", token, projection="list")).get("requirements") or []
    for r in (rows or [])[:15]:
        rid = r.get("requirement_id")
        pid = r.get("property_id") or PILOT_PROPERTY
        if not rid:
            continue
        er = _get(f"/client/properties/{pid}/requirements/{rid}/evidence-resolution", token)
        body = er.get("body") if isinstance(er.get("body"), dict) else {}
        g = body.get("requirement_guidance_v1") if isinstance(body.get("requirement_guidance_v1"), dict) else {}
        cog = body.get("operational_cognition") if isinstance(body.get("operational_cognition"), dict) else {}
        primary = (cog.get("primary_action") or {}).get("label")
        strongest = g.get("strongest_evidence_method")
        weaker = g.get("weaker_alternative_methods") or []
        checks.append(
            {
                "requirement_id": rid,
                "dominant_next_step": g.get("recommended_next_step"),
                "dominant_reason": g.get("recommended_next_step_reason"),
                "primary_action_label": primary,
                "strongest_evidence_method": strongest,
                "weaker_alternatives_count": len(weaker),
                "dominance_ok": bool(g.get("recommended_next_step")) and bool(primary),
                "weak_paths_downgraded": len(weaker) == 0 or strongest is not None,
            }
        )
    ok = all(c.get("dominance_ok") for c in checks) if checks else False
    return {"captured_at": _utc(), "checks": checks, "gate_pass": ok}


def operational_truthfulness(token: str) -> Dict[str, Any]:
    flags: List[Dict[str, Any]] = []
    rows = _body_dict(_get("/client/requirements", token, projection="list")).get("requirements") or []
    for r in (rows or [])[:20]:
        rid = r.get("requirement_id")
        if not rid:
            continue
        detail = _get(f"/requirements/{rid}", token)
        body = detail.get("body") if isinstance(detail.get("body"), dict) else {}
        req = body.get("requirement") if isinstance(body.get("requirement"), dict) else {}
        cog = req.get("operational_cognition") or {}
        truth = cog.get("operational_truth_flags") or {}
        g = cog.get("requirement_guidance_v1") or {}
        flags.append(
            {
                "requirement_id": rid,
                "uploaded_not_submitted": g.get("uploaded_not_submitted"),
                "submitted_not_verified": g.get("submitted_not_verified"),
                "truth_flags": truth,
                "guidance_risk_flags": g.get("operational_risk_flags"),
            }
        )
    return {"captured_at": _utc(), "samples": flags}


def progression_runtime(token: str) -> Dict[str, Any]:
    out: List[Dict[str, Any]] = []
    rows = _body_dict(_get("/client/requirements", token, projection="list")).get("requirements") or []
    for r in (rows or [])[:15]:
        rid = r.get("requirement_id")
        if not rid:
            continue
        detail = _get(f"/requirements/{rid}", token)
        body = detail.get("body") if isinstance(detail.get("body"), dict) else {}
        req = body.get("requirement") if isinstance(body.get("requirement"), dict) else {}
        g = ((req.get("operational_cognition") or {}).get("requirement_guidance_v1")) or {}
        steps = g.get("progression_steps") or []
        out.append(
            {
                "requirement_id": rid,
                "workflow_stage": g.get("workflow_stage"),
                "progression_steps_count": len(steps),
                "has_current_step": any(s.get("status") == "current" for s in steps if isinstance(s, dict)),
            }
        )
    gate = all(x.get("progression_steps_count", 0) > 0 for x in out) if out else False
    return {"captured_at": _utc(), "samples": out, "gate_pass": gate}


def cognitive_load_findings(audit: Dict[str, Any], browser: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "captured_at": _utc(),
        "collapsed_truth_copy_in_modal": browser.get("supporting_truth_collapsed"),
        "secondary_methods_collapsed": browser.get("secondary_methods_collapsed"),
        "hero_present_in_modal": browser.get("modal_hero_present"),
        "residual_flat_blocks": audit.get("flat_hierarchy_indicators", [])[:5],
    }


def cross_surface_consistency(audit: Dict[str, Any]) -> Dict[str, Any]:
    contradictions = audit.get("contradiction_matrix") or []
    return {
        "captured_at": _utc(),
        "contradiction_count": len(contradictions),
        "contradictions": contradictions,
        "gate_pass": len(contradictions) == 0,
    }


def _login_page(page: Page, email: str, password: str) -> bool:
    page.goto(f"{FRONTEND}/login/client", wait_until="domcontentloaded", timeout=120_000)
    page.wait_for_timeout(1500)
    page.locator("#email, input[type=email]").first.fill(email)
    page.locator("#password, input[type=password]").first.fill(password)
    page.locator('button[type="submit"]').first.click()
    page.wait_for_timeout(5000)
    return "login" not in page.url.lower()


def browser_runtime(token: str, audit: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "captured_at": _utc(),
        "playwright_available": sync_playwright is not None,
        "modal_hero_present": False,
        "progression_visible": False,
        "supporting_truth_collapsed": False,
        "secondary_methods_collapsed": False,
        "primary_tier_markers": 0,
        "gate_pass": False,
        "notes": [],
        "target_requirement_id": None,
        "target_property_id": None,
    }
    findings = audit.get("findings") or []
    target = None
    priority_types = (
        "occupation_contract",
        "wales_occupation_contract",
        "deposit_pi",
        "legionella",
    )
    for req_type in priority_types:
        for f in findings:
            if (
                f.get("requirement_type") == req_type
                and f.get("client_lifecycle_state") == "ACTION_REQUIRED"
                and f.get("evidence_resolution_guidance_complete")
            ):
                target = f
                break
        if target:
            break
    if not target:
        for f in findings:
            if f.get("client_lifecycle_state") == "ACTION_REQUIRED" and f.get("evidence_resolution_guidance_complete"):
                target = f
                break
    if not target and findings:
        target = findings[0]
    sample_requirement_id = str((target or {}).get("requirement_id") or "")
    sample_property_id = str((target or {}).get("property_id") or PILOT_PROPERTY)
    out["target_requirement_id"] = sample_requirement_id or None
    out["target_property_id"] = sample_property_id

    if sync_playwright is None or not sample_requirement_id:
        out["notes"].append("browser_skipped")
        return out

    SHOT.mkdir(parents=True, exist_ok=True)
    pw = _read_pw(LANDLORD_PW)
    resolve_url = f"{FRONTEND}/properties/{sample_property_id}?open=resolve&requirement_id={sample_requirement_id}"
    intel_url = f"{FRONTEND}/properties/{sample_property_id}?open=intel&requirement_id={sample_requirement_id}"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        if not _login_page(page, LANDLORD_EMAIL, pw):
            out["notes"].append("login_failed")
            browser.close()
            return out

        # Primary path: deep-link directly opens guided evidence modal
        page.goto(resolve_url, wait_until="networkidle", timeout=120_000)
        page.wait_for_timeout(8000)
        try:
            page.wait_for_selector('[data-testid="compliance-evidence-resolve-modal"]', timeout=45_000)
        except Exception:
            out["notes"].append("resolve_deeplink_modal_timeout")

        modal = page.locator('[data-testid="compliance-evidence-resolve-modal"]')
        out["modal_open"] = modal.count() > 0

        # Fallback: intel modal → primary CTA → guided evidence
        if not out["modal_open"]:
            page.goto(intel_url, wait_until="networkidle", timeout=120_000)
            try:
                page.wait_for_selector('[data-testid="requirement-intel-dialog"]', timeout=30_000)
            except Exception:
                out["notes"].append("intel_modal_not_open")
            hero = page.locator('[data-testid="next-action-hero-primary"]')
            primary = page.locator('[data-testid="requirement-intel-primary-cta"]')
            if hero.count():
                hero.first.click()
                page.wait_for_timeout(2500)
            elif primary.count():
                primary.first.click()
                page.wait_for_timeout(2500)
            try:
                page.wait_for_selector('[data-testid="compliance-evidence-resolve-modal"]', timeout=20_000)
            except Exception:
                out["notes"].append("intel_cta_modal_timeout")
            out["modal_open"] = page.locator('[data-testid="compliance-evidence-resolve-modal"]').count() > 0

        try:
            page.wait_for_selector('[data-testid="next-action-hero"]', timeout=15_000)
        except Exception:
            pass
        try:
            page.wait_for_selector('[data-guided-evidence-tier="primary"]', timeout=15_000)
        except Exception:
            pass

        out["modal_hero_present"] = page.locator('[data-testid="next-action-hero"]').count() > 0
        out["progression_visible"] = page.locator('[data-testid="requirement-progression-steps"]').count() > 0
        out["supporting_truth_collapsed"] = page.locator('[data-testid="supporting-upload-truth-banner"]').count() > 0
        out["secondary_methods_collapsed"] = page.locator("details summary:has-text('Other evidence methods')").count() > 0
        out["primary_tier_markers"] = page.locator('[data-guided-evidence-tier="primary"]').count()
        out["intel_hero_present"] = page.locator('[data-testid="requirement-intel-dialog"] [data-testid="next-action-hero"]').count() > 0
        page.screenshot(path=str(SHOT / f"evidence_modal_{RUN_TAG}.png"), full_page=True)
        browser.close()

    out["gate_pass"] = (
        out.get("modal_open")
        and out["modal_hero_present"]
        and out["progression_visible"]
        and out["primary_tier_markers"] >= 1
    )
    return out


def classify(
    audit: Dict[str, Any],
    browser: Dict[str, Any],
    dominance: Dict[str, Any],
    cross: Dict[str, Any],
    progression: Dict[str, Any],
) -> Dict[str, Any]:
    blockers: List[str] = []
    if audit.get("flat_hierarchy_indicators"):
        blockers.append("guidance_missing_on_some_surfaces")
    if not dominance.get("gate_pass"):
        blockers.append("next_action_dominance_incomplete")
    if not cross.get("gate_pass"):
        blockers.append("cross_surface_contradictions")
    if not progression.get("gate_pass"):
        blockers.append("progression_not_visible")
    if not browser.get("gate_pass"):
        blockers.append("browser_runtime_proof_incomplete")

    if blockers:
        if "browser_runtime_proof_incomplete" in blockers and len(blockers) == 1:
            label = "PARTIAL"
        elif any("contradiction" in b for b in blockers):
            label = "OPERATIONALLY_CONFUSING"
        elif "guidance_missing" in str(blockers):
            label = "COGNITIVE_OVERLOAD_RISK"
        else:
            label = "PARTIAL"
    else:
        label = "OPERATIONALLY_GUIDED"

    allowed = {
        "OPERATIONALLY_GUIDED",
        "PARTIAL",
        "COGNITIVE_OVERLOAD_RISK",
        "OPERATIONALLY_CONFUSING",
        "TRUST_RISK_PRESENT",
    }
    if label not in allowed:
        label = "PARTIAL"
    return {
        "classification": label,
        "blockers": blockers,
        "push_audit_artifacts_allowed": label == "OPERATIONALLY_GUIDED",
        "evaluated_at": _utc(),
    }


def write_report(classification: Dict[str, Any], audit: Dict[str, Any]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    cls = classification.get("classification")
    blockers = classification.get("blockers") or []
    md = f"""# {PROGRAMME}

Generated: {_utc()}

## Classification

**{cls}**

Push audit artifacts: **{classification.get('push_audit_artifacts_allowed')}**

## Summary

Requirement/evidence flows now expose server-authoritative `requirement_guidance_v1` on enriched requirements and the evidence-resolution API. The guided evidence modal elevates a single recommended path via `NextActionHero`, progression steps, collapsed secondary methods, and explicit uploaded≠submitted semantics.

## Blockers

{chr(10).join(f'- {b}' for b in blockers) or '- none'}

## Samples audited

{audit.get('samples', 0)} requirements probed on staging.

## Remediation roadmap (if not OPERATIONALLY_GUIDED)

1. Deploy backend + frontend containing `requirement_guidance_v1` and modal guidance panel.
2. Re-run this harness after Render/Vercel deploy completes.
3. Resolve any cross-surface contradictions in `contradiction_matrix`.
4. Confirm browser proof: hero, progression, primary-tier evidence mode in modal screenshot.
"""
    (OUT / "REPORT.md").write_text(md, encoding="utf-8")

    watch = f"""# Watchlist — {PROGRAMME}

- Classification: {cls}
- Blockers: {', '.join(blockers) or 'none'}
- Re-run after deploy: `python tmp_requirement_cognition_guidance_architecture_01.py`
"""
    (OUT / "watchlist.md").write_text(watch, encoding="utf-8")


def main() -> int:
    print(f"[{PROGRAMME}] starting {_utc()}")
    token, _user = _api_login(LANDLORD_EMAIL, _read_pw(LANDLORD_PW))

    audit = audit_requirement_flows(token)
    _write("requirement_flow_audit.json", audit)

    cog = cognition_runtime(token)
    _write("cognition_guidance_runtime.json", cog)

    dominance = next_action_dominance(token)
    _write("next_action_dominance.json", dominance)

    truth = operational_truthfulness(token)
    _write("operational_truthfulness.json", truth)

    progression = progression_runtime(token)
    _write("progression_runtime.json", progression)

    browser = browser_runtime(token, audit)
    _write("browser_runtime.json", browser)

    cross = cross_surface_consistency(audit)
    _write("cross_surface_consistency.json", cross)

    cognitive = cognitive_load_findings(audit, browser)
    _write("cognitive_load_findings.json", cognitive)

    classification = classify(audit, browser, dominance, cross, progression)
    _write("classifications.json", classification)

    write_report(classification, audit)

    print(json.dumps(classification, indent=2))
    return 0 if classification.get("classification") == "OPERATIONALLY_GUIDED" else 2


if __name__ == "__main__":
    sys.exit(main())
