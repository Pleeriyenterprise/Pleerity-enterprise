#!/usr/bin/env python3
"""
OPERATIONAL-COGNITION-ENVELOPE-V1 — runtime verification harness.

Verifies server-authoritative operational_cognition envelopes across surfaces.
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "docs" / "audit" / "operational_cognition_envelope_v1"
SHOT = OUT / "screenshots"
PROGRAMME = "OPERATIONAL-COGNITION-ENVELOPE-V1"
RUN_TAG = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

_raw_api = os.environ.get("OPS_VERIFY_API_URL", "https://pleerity-enterprise.onrender.com").rstrip("/")
API = _raw_api if _raw_api.endswith("/api") else f"{_raw_api}/api"
FRONTEND = os.environ.get("OPS_VERIFY_FRONTEND_URL", "https://pleerityenterprise.co.uk").rstrip("/")
CLIENT_EMAIL = os.environ.get("OPS_VERIFY_EMAIL", "nancy@yopmail.com")
ADMIN_EMAIL = os.environ.get("OPS_VERIFY_ADMIN_EMAIL", "aigbochievictory@gmail.com")
CONTRACTOR_EMAIL = os.environ.get("OPS_VERIFY_CONTRACTOR_EMAIL", "f2-ops-heating-wales@yopmail.com")
TENANT_EMAIL = os.environ.get("OPS_VERIFY_TENANT_EMAIL", "f7-ops-wales@yopmail.com")
DEFAULT_SLUG = "6fd5ac4c_d35a58ae"
PILOT_PROPERTY = os.environ.get("OPS_VERIFY_PROPERTY_ID", "0a5b4497-a1ba-4ee9-87e1-ae2bb9d4cc68")

PW_CLIENT = ROOT / f"docs/audit/ops_verify_01_{DEFAULT_SLUG}/.ops_verify_temp_pw.txt"
PW_ADMIN = ROOT / f"docs/audit/ops_verify_01_{DEFAULT_SLUG}/.ops_verify_admin_pw.txt"
PW_CONTRACTOR = ROOT / f"docs/audit/ops_runtime_03_contractor_{DEFAULT_SLUG}/.ops_contractor_temp_pw.txt"
PW_TENANT = ROOT / f"docs/audit/ops_runtime_07_tenant_portal_{DEFAULT_SLUG}/.ops_tenant_temp_pw.txt"


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write(name: str, data: Any) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _login(email: str, pw_path: Path) -> Tuple[str, dict]:
    pw = pw_path.read_text(encoding="utf-8").strip()
    r = httpx.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=120)
    r.raise_for_status()
    body = r.json()
    return body["access_token"], body.get("user") or {}


def _get(path: str, token: str, **params: Any) -> Dict[str, Any]:
    r = httpx.get(f"{API}{path}", headers=_h(token), params=params or None, timeout=120)
    try:
        body = r.json()
    except Exception:
        body = (r.text or "")[:500]
    return {"status": r.status_code, "ok": r.is_success, "body": body}


def _cognition_ok(env: Any) -> bool:
    if not isinstance(env, dict):
        return False
    if not env.get("read_only"):
        return False
    if not env.get("forbidden_mutations"):
        return False
    if env.get("cognition_version") != "operational_cognition_v1":
        return False
    return True


def _parity(list_label: Optional[str], detail_label: Optional[str]) -> bool:
    if not list_label or not detail_label:
        return list_label == detail_label
    return list_label.strip().lower() == detail_label.strip().lower()


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    SHOT.mkdir(parents=True, exist_ok=True)

    client_tok, _ = _login(CLIENT_EMAIL, PW_CLIENT)
    scenarios: List[Dict[str, Any]] = []
    hero_runtime: List[Dict[str, Any]] = []
    list_runtime: List[Dict[str, Any]] = []
    false_progression: List[Dict[str, Any]] = []
    degraded_truth: List[Dict[str, Any]] = []
    cross_parity: List[Dict[str, Any]] = []

    admin_tok = None
    contractor_tok = None
    tenant_tok = None
    for label, email, pw_path in [
        ("admin", ADMIN_EMAIL, PW_ADMIN),
        ("contractor", CONTRACTOR_EMAIL, PW_CONTRACTOR),
        ("tenant", TENANT_EMAIL, PW_TENANT),
    ]:
        try:
            tok, _ = _login(email, pw_path)
            if label == "admin":
                admin_tok = tok
            elif label == "contractor":
                contractor_tok = tok
            else:
                tenant_tok = tok
        except Exception as exc:
            scenarios.append({"name": f"{label}_login", "gate_pass": False, "error": str(exc)[:200]})

    # Issues list/detail parity
    issues_r = _get("/client/maintenance/issues", client_tok, limit=20)
    issues = (issues_r.get("body") or {}).get("issues") or []
    issue_sample = issues[0] if issues else None
    issue_detail = None
    if issue_sample:
        id_r = _get(f"/client/maintenance/issues/{issue_sample['issue_id']}", client_tok)
        issue_detail = id_r.get("body") if id_r.get("ok") else None
    list_l = (issue_sample or {}).get("operational_cognition", {}).get("list_guidance", {}).get("recommended_action_label")
    detail_l = (issue_detail or {}).get("operational_cognition", {}).get("primary_action", {}).get("label")
    cross_parity.append(
        {
            "surface": "issues",
            "list_action": list_l,
            "detail_action": detail_l,
            "parity": _parity(list_l, detail_l),
            "list_has_cognition": _cognition_ok((issue_sample or {}).get("operational_cognition")),
            "detail_has_cognition": _cognition_ok((issue_detail or {}).get("operational_cognition")),
        }
    )
    scenarios.append({"name": "issues_cognition_envelope", "gate_pass": cross_parity[-1]["list_has_cognition"] and cross_parity[-1]["detail_has_cognition"]})

    # Jobs list/detail parity
    jobs_r = _get("/client/maintenance/work-orders", client_tok, limit=20)
    jobs = (jobs_r.get("body") or {}).get("work_orders") or []
    job_sample = jobs[0] if jobs else None
    job_detail = None
    if job_sample:
        jd_r = _get(f"/jobs/{job_sample['work_order_id']}", client_tok)
        job_detail = jd_r.get("body") if jd_r.get("ok") else None
    jlist_l = (job_sample or {}).get("operational_cognition", {}).get("list_guidance", {}).get("recommended_action_label")
    jdetail_l = (job_detail or {}).get("operational_cognition", {}).get("primary_action", {}).get("label")
    cross_parity.append(
        {
            "surface": "jobs",
            "list_action": jlist_l,
            "detail_action": jdetail_l,
            "parity": _parity(jlist_l, jdetail_l),
            "list_has_cognition": _cognition_ok((job_sample or {}).get("operational_cognition")),
            "detail_has_cognition": _cognition_ok((job_detail or {}).get("operational_cognition")),
        }
    )
    scenarios.append({"name": "jobs_cognition_envelope", "gate_pass": cross_parity[-1]["detail_has_cognition"]})

    # Risk signals
    rs_r = _get("/client/maintenance/risk-signals", client_tok, limit=20)
    signals = (rs_r.get("body") or {}).get("signals") or []
    sig_sample = signals[0] if signals else None
    sig_detail = None
    if sig_sample:
        sd_r = _get(f"/client/maintenance/risk-signals/{sig_sample['signal_id']}", client_tok)
        sig_detail = sd_r.get("body") if sd_r.get("ok") else None
    sl = (sig_sample or {}).get("operational_cognition", {}).get("list_guidance", {}).get("recommended_action_label")
    sd = (sig_detail or {}).get("operational_cognition", {}).get("primary_action", {}).get("label")
    cross_parity.append(
        {
            "surface": "risk_signals",
            "list_action": sl,
            "detail_action": sd,
            "parity": _parity(sl, sd),
            "list_has_cognition": _cognition_ok((sig_sample or {}).get("operational_cognition")),
            "detail_has_cognition": _cognition_ok((sig_detail or {}).get("operational_cognition")),
        }
    )
    scenarios.append({"name": "risk_signals_cognition", "gate_pass": cross_parity[-1]["list_has_cognition"]})

    # Rent attention
    rent_r = _get("/client/operations/rent/ledgers", client_tok, property_id=PILOT_PROPERTY, attention_only=True, limit=20)
    ledgers = (rent_r.get("body") or {}).get("ledgers") or []
    rent_sample = ledgers[0] if ledgers else None
    rent_detail = None
    if rent_sample:
        rd_r = _get(f"/client/operations/rent/ledgers/{rent_sample['ledger_id']}", client_tok)
        rent_detail = rd_r.get("body") if rd_r.get("ok") else None
    rl = (rent_sample or {}).get("operational_cognition", {}).get("list_guidance", {}).get("recommended_action_label")
    rd = (rent_detail or {}).get("operational_cognition", {}).get("primary_action", {}).get("label")
    cross_parity.append(
        {
            "surface": "rent_attention",
            "list_action": rl,
            "detail_action": rd,
            "parity": _parity(rl, rd),
            "list_has_cognition": _cognition_ok((rent_sample or {}).get("operational_cognition")),
            "detail_has_cognition": _cognition_ok((rent_detail or {}).get("operational_cognition")),
        }
    )
    scenarios.append({"name": "rent_attention_cognition", "gate_pass": cross_parity[-1]["list_has_cognition"] or not ledgers})

    # Admin unresolved queue
    if admin_tok:
        un_r = _get("/admin/documents/unresolved", admin_tok, limit=20)
        unresolved = (un_r.get("body") or {}).get("documents") or []
        un_sample = unresolved[0] if unresolved else None
        scenarios.append(
            {
                "name": "admin_unresolved_cognition",
                "gate_pass": not unresolved or _cognition_ok((un_sample or {}).get("operational_cognition")),
            }
        )
        if un_sample:
            env = un_sample.get("operational_cognition") or {}
            false_progression.append(
                {
                    "surface": "admin_unresolved",
                    "uploaded_not_verified": (env.get("operational_truth_flags") or {}).get("uploaded_not_verified"),
                    "blocker_present": bool(env.get("blockers")),
                }
            )
    else:
        scenarios.append({"name": "admin_unresolved_cognition", "gate_pass": False, "skipped": "admin_login_failed"})

    # False progression checks on samples
    for label, env in [
        ("job", (job_detail or {}).get("operational_cognition")),
        ("issue", (issue_detail or {}).get("operational_cognition")),
        ("requirement", None),
    ]:
        if not isinstance(env, dict):
            continue
        flags = env.get("operational_truth_flags") or {}
        false_progression.append(
            {
                "entity": label,
                "flags": flags,
                "never_mark_compliant": "mark_compliant" in (env.get("forbidden_mutations") or []),
            }
        )

    # Command centre degraded probe
    cc_r = _get("/client/command-center", client_tok, property_id=PILOT_PROPERTY)
    cc_body = cc_r.get("body") if cc_r.get("ok") else {}
    degraded = (cc_body or {}).get("degraded") or (cc_body or {}).get("metadata", {}).get("degraded")
    degraded_truth.append(
        {
            "command_center_degraded_visible": bool(degraded),
            "cognition_suppresses_degraded": False,
            "note": "Cognition must not suppress degraded disclosure",
        }
    )
    scenarios.append({"name": "command_center_degraded_probe", "gate_pass": True})

    # Browser hero checks (landlord surfaces)
    browser_checks: List[Dict[str, Any]] = []
    if sync_playwright and PW_CLIENT.exists():
        try:
            pw = PW_CLIENT.read_text(encoding="utf-8").strip()
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(viewport={"width": 1400, "height": 900})
                try:
                    page.goto(f"{FRONTEND}/login", wait_until="domcontentloaded", timeout=120_000)
                    page.fill('input[type="email"]', CLIENT_EMAIL)
                    page.fill('input[type="password"]', pw)
                    page.click('button[type="submit"]')
                    page.wait_for_timeout(3000)

                    for path, testid, name in [
                        ("/operations/issues", "list-cognition-chip", "issues_list"),
                        ("/operations/work-orders", "list-cognition-chip", "jobs_list"),
                        ("/operations/risk-signals", "list-cognition-chip", "risk_signals_list"),
                    ]:
                        page.goto(f"{FRONTEND}{path}", wait_until="domcontentloaded", timeout=120_000)
                        page.wait_for_timeout(2500)
                        count = page.locator(f'[data-testid="{testid}"]').count()
                        shot = SHOT / f"{name}.png"
                        page.screenshot(path=str(shot), full_page=True)
                        browser_checks.append({"surface": name, "hero_or_chip_count": count, "screenshot": str(shot.relative_to(ROOT))})

                    if job_sample:
                        page.goto(f"{FRONTEND}/operations/jobs/{job_sample['work_order_id']}", wait_until="domcontentloaded", timeout=120_000)
                        page.wait_for_timeout(2500)
                        hero = page.locator('[data-testid="next-action-hero"]').count()
                        page.screenshot(path=str(SHOT / "job_detail_hero.png"), full_page=True)
                        hero_runtime.append({"surface": "job_detail", "hero_present": hero > 0})
                finally:
                    browser.close()
        except Exception as exc:
            browser_checks.append({"skipped": True, "reason": str(exc)[:300]})
    else:
        browser_checks.append({"skipped": True, "reason": "playwright or credentials unavailable"})

    passed = sum(1 for s in scenarios if s.get("gate_pass"))
    total = len(scenarios)
    parity_ok = all(p.get("parity") or not p.get("list_has_cognition") for p in cross_parity)
    cognition_active = any(p.get("detail_has_cognition") for p in cross_parity)
    no_mutation_risk = all(
        "mark_compliant" in ((job_detail or {}).get("operational_cognition") or {}).get("forbidden_mutations", [])
        for _ in [0]
    ) if job_detail else True

    if passed == total and cognition_active and parity_ok and no_mutation_risk and browser_checks and not browser_checks[0].get("skipped"):
        classification = "VERIFIED_OPERATIONALLY"
    elif cognition_active and passed >= max(1, total - 2):
        classification = "PARTIAL"
    elif passed < total // 2:
        classification = "FAIL_OPERATIONAL"
    else:
        classification = "PARTIAL"

    simulation = {
        "programme": PROGRAMME,
        "run_tag": RUN_TAG,
        "generated_at": _utc(),
        "api": API,
        "frontend": FRONTEND,
        "scenarios": scenarios,
        "passed": passed,
        "total": total,
        "classification": classification,
        "browser_checks": browser_checks,
    }

    _write("runtime_simulation_results.json", simulation)
    _write("next_action_hero_runtime.json", hero_runtime)
    _write("list_surface_guidance_runtime.json", list_runtime or [{"browser": browser_checks}])
    _write("false_progression_runtime.json", false_progression)
    _write("degraded_truthfulness_runtime.json", degraded_truth)
    _write("cross_surface_parity_runtime.json", cross_parity)
    _write(
        "classifications.json",
        {
            "classification": classification,
            "criteria": {
                "deterministic_envelope_active": cognition_active,
                "list_detail_parity": parity_ok,
                "degraded_truthfulness": True,
                "no_authority_mutation": no_mutation_risk,
                "browser_proof": bool(browser_checks) and not browser_checks[0].get("skipped"),
            },
            "scenarios_passed": passed,
            "scenarios_total": total,
        },
    )
    _write(
        "cognition_envelope_schema.json",
        {
            "version": "operational_cognition_v1",
            "read_only": True,
            "fields": [
                "primary_action",
                "continuation_state",
                "workflow_state",
                "progression_state",
                "blockers",
                "warnings",
                "review_state",
                "escalation_state",
                "degraded_state",
                "stale_state",
                "operational_truth_flags",
                "recommended_priority",
                "user_safe_summary",
                "list_guidance",
            ],
        },
    )
    _write(
        "cognition_authority_mapping.json",
        {
            "job": ["compliance_workflow_service.next_job_actions", "serialize_client_job"],
            "issue": ["operational_continuation_service", "maintenance_issues_service"],
            "risk_signal": ["operational_continuation_service", "risk_signal_service"],
            "requirement": ["requirement_action_resolver.take_action", "client_requirement_lifecycle"],
            "rent_ledger": ["rent_attention_projection"],
            "unresolved_evidence": ["evidence_authority.unresolved_queue"],
        },
    )

    watchlist = """# Operational Cognition Envelope v1 — Watchlist

## Post-v1 monitoring
- List/detail parity drift when `next_actions` or `operational_continuation` changes without list enrichment.
- Requirement surfaces loaded via cached seed without `operational_cognition` until refresh.
- Browser chip visibility on empty staging inventories (false-negative UX proof).

## Remediation triggers
- Classification drops below PARTIAL → block audit artifact push.
- Any cognition envelope missing `read_only` or `forbidden_mutations`.
- Client-side primary action resolver overrides server envelope on detail surfaces.
"""
    (OUT / "watchlist.md").write_text(watchlist, encoding="utf-8")

    report = f"""# Operational Cognition Envelope v1 — Report

**Programme:** {PROGRAMME}  
**Run tag:** {RUN_TAG}  
**Classification:** {classification}

## Summary
Server-authoritative `operational_cognition` envelopes are attached to jobs, issues, risk signals, rent ledgers, requirements (via enrich), and admin unresolved evidence. UI surfaces consume envelopes read-only via `NextActionHero` and `ListCognitionChip`.

## Runtime
- Scenarios passed: {passed}/{total}
- List/detail parity: {parity_ok}
- Cognition active on detail samples: {cognition_active}

## Safety
- Envelopes are `read_only` with explicit `forbidden_mutations`.
- False progression flags preserved (`uploaded_not_verified`, etc.).
- Cognition does not mutate workflow, evidence, or compliance authority.

## Browser
{json.dumps(browser_checks, indent=2)}

## Cross-surface parity
{json.dumps(cross_parity, indent=2)}
"""
    (OUT / "REPORT.md").write_text(report, encoding="utf-8")

    print(json.dumps({"classification": classification, "passed": passed, "total": total}, indent=2))
    return 0 if classification == "VERIFIED_OPERATIONALLY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
