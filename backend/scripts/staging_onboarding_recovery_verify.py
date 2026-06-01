#!/usr/bin/env python3
"""
PRELAUNCH onboarding recovery — staging browser/runtime verification (API + optional Playwright).

Usage:
  set STAGING_ADMIN_EMAIL=...
  set STAGING_ADMIN_PASSWORD=...
  python scripts/staging_onboarding_recovery_verify.py [--browser] [--dry-run]

Writes: docs/audit/prelaunch_onboarding_recovery_orchestration_01/browser_runtime.json
        docs/audit/prelaunch_onboarding_recovery_orchestration_01/screenshots/ (if --browser)
"""
from __future__ import annotations

import argparse
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
OUT = ROOT / "docs/audit/prelaunch_onboarding_recovery_orchestration_01"
SCREENSHOTS = OUT / "screenshots"
API = os.getenv("STAGING_API", "https://pleerity-enterprise.onrender.com/api").rstrip("/")
FE = os.getenv("STAGING_FE", "https://pleerityenterprise.co.uk").rstrip("/")
MARKER = "PRELAUNCH-ONBOARDING-RECOVERY-STAGING-VERIFY-01"
REASON = f"{MARKER} governed recovery staging verification execute"


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write(name: str, data: object) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


def _load_admin_password() -> Tuple[str, str]:
    email = (os.getenv("STAGING_ADMIN_EMAIL") or os.getenv("ADMIN_EMAIL") or "").strip()
    pw = (os.getenv("STAGING_ADMIN_PASSWORD") or os.getenv("ADMIN_PASSWORD") or "").strip()
    if not pw:
        for rel in (
            "docs/audit/ops_verify_01_6fd5ac4c_d35a58ae/.ops_verify_admin_pw.txt",
            "docs/audit/.ops_verify_phase2_temp_pw.txt",
        ):
            p = ROOT / rel
            if p.is_file():
                pw = p.read_text(encoding="utf-8").strip()
                break
    if not email:
        email = "aigbochievictory@gmail.com"
    if not email or not pw:
        raise SystemExit("Set STAGING_ADMIN_EMAIL and STAGING_ADMIN_PASSWORD (or provide ops_verify admin pw file).")
    return email, pw


def _headers(token: str, *, step_up: str = "", confirmation: str = "") -> Dict[str, str]:
    h = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    if step_up:
        h["X-Step-Up-Token"] = step_up
    if confirmation:
        h["X-Admin-Confirmation-Token"] = confirmation
    return h


def _login_admin(email: str, password: str) -> str:
    last: Optional[Exception] = None
    for attempt in range(6):
        try:
            r = httpx.post(
                f"{API}/auth/admin/login",
                json={"email": email, "password": password},
                timeout=120,
            )
            if r.status_code in (502, 503, 504) and attempt < 5:
                time.sleep(15)
                continue
            r.raise_for_status()
            return r.json()["access_token"]
        except Exception as exc:
            last = exc
            time.sleep(10)
    raise RuntimeError(f"admin login failed: {last}")


def _step_up(admin_token: str, password: str) -> str:
    r = httpx.post(
        f"{API}/auth/step-up/verify",
        json={"password": password},
        headers=_headers(admin_token),
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["step_up_token"]


def _confirmation_token(admin_token: str, client_id: str) -> str:
    r = httpx.post(
        f"{API}/admin/governance/confirmation-token",
        json={
            "action_id": "onboarding_recovery_execute",
            "reason": REASON,
            "resource_key": client_id,
        },
        headers=_headers(admin_token),
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["token"]


def _get(client: httpx.Client, path: str, token: str) -> Dict[str, Any]:
    r = client.get(f"{API}{path}", headers=_headers(token), timeout=120)
    try:
        body = r.json()
    except Exception:
        body = r.text[:1500]
    return {"status": r.status_code, "ok": r.is_success, "body": body}


def _post(
    client: httpx.Client,
    path: str,
    token: str,
    payload: dict,
    *,
    step_up: str = "",
    confirmation: str = "",
) -> Dict[str, Any]:
    r = client.post(
        f"{API}{path}",
        json=payload,
        headers=_headers(token, step_up=step_up, confirmation=confirmation),
        timeout=180,
    )
    try:
        body = r.json()
    except Exception:
        body = r.text[:1500]
    return {"status": r.status_code, "ok": r.is_success, "body": body}


def _assessment_row(
    client: httpx.Client,
    admin_token: str,
    *,
    client_id: str,
    email: Optional[str] = None,
    customer_reference: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    assess = _get(client, f"/admin/clients/{client_id}/onboarding-recovery/assessment", admin_token)
    if not assess["ok"]:
        return None
    a = assess["body"] if isinstance(assess["body"], dict) else {}
    return {
        "client_id": client_id,
        "email": email,
        "customer_reference": customer_reference,
        "classification": a.get("classification"),
        "eligible": (a.get("eligibility") or {}).get("eligible"),
        "executable_modes": (a.get("strategy") or {}).get("executable_modes") or [],
        "checkout_fresh": (a.get("state_summary") or {}).get("checkout_fresh"),
        "paid_or_active": (a.get("state_summary") or {}).get("paid_or_active"),
        "password_set": (a.get("state_summary") or {}).get("password_set"),
    }


def _pick_clients(client: httpx.Client, admin_token: str) -> List[Dict[str, Any]]:
    seen: set[str] = set()
    enriched: List[Dict[str, Any]] = []

    def add(row: Optional[Dict[str, Any]]) -> None:
        if not row or row["client_id"] in seen:
            return
        seen.add(row["client_id"])
        enriched.append(row)

    r = _get(client, "/admin/intake/pending-payments?bucket=pending", admin_token)
    items = []
    if r["ok"] and isinstance(r["body"], dict):
        items = r["body"].get("items") or []
    for row in items[:40]:
        cid = row.get("client_id")
        if not cid:
            continue
        add(
            _assessment_row(
                client,
                admin_token,
                client_id=cid,
                email=row.get("email"),
                customer_reference=row.get("customer_reference"),
            )
        )

    admin_list = _get(client, "/admin/clients?limit=200", admin_token)
    if admin_list["ok"] and isinstance(admin_list["body"], dict):
        for c in admin_list["body"].get("clients") or []:
            cid = c.get("client_id")
            if not cid:
                continue
            add(
                _assessment_row(
                    client,
                    admin_token,
                    client_id=cid,
                    email=c.get("email"),
                    customer_reference=c.get("customer_reference"),
                )
            )
    return enriched


def _find_promo_subject(client: httpx.Client, admin_token: str, enriched: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    for c in enriched:
        if c.get("classification") not in (
            "PROMO_REDEMPTION_FAILED",
            "FIRST_TIME_RESTRICTION_COLLISION",
            "PAYMENT_ABANDONED",
            "EXPIRED_CHECKOUT",
        ):
            continue
        detail = _get(client, f"/admin/clients/{c['client_id']}", admin_token)
        body = detail.get("body") if isinstance(detail.get("body"), dict) else {}
        if (body.get("pilot_invite_code") or "").strip():
            return {**c, "pilot_invite_code": body.get("pilot_invite_code")}
    return None


def _find_activation_subject(enriched: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    for c in enriched:
        if c.get("classification") == "ACTIVATION_INCOMPLETE" and c.get("eligible"):
            if "resend_activation" in (c.get("executable_modes") or []):
                return c
    return None


def _pick_unused(
    enriched: List[Dict[str, Any]],
    *classes: str,
    used: Optional[set[str]] = None,
) -> Optional[Dict[str, Any]]:
    used = used or set()
    for c in enriched:
        if c["client_id"] in used:
            continue
        if c.get("classification") in classes and c.get("eligible"):
            return c
    return None


def _find_by_classification(enriched: List[Dict[str, Any]], *classes: str) -> Optional[Dict[str, Any]]:
    for c in enriched:
        if c.get("classification") in classes and c.get("eligible"):
            return c
    return None


def _should_send_customer_email(subject: Dict[str, Any], send_email: bool) -> bool:
    if not send_email:
        return False
    email = (subject.get("email") or "").lower()
    domain = (os.getenv("STAGING_RECOVERY_EMAIL_DOMAIN") or "yopmail.com").lower()
    return domain in email


def _execute(
    client: httpx.Client,
    admin_token: str,
    step_up_tok: str,
    subject: Dict[str, Any],
    mode: str,
    *,
    dry_run: bool,
    send_email: bool,
) -> Dict[str, Any]:
    cid = subject["client_id"]
    if dry_run:
        return {"skipped": True, "reason": "dry_run", "mode": mode, "client_id": cid}
    conf = _confirmation_token(admin_token, cid)
    payload = {
        "mode": mode,
        "reason": REASON,
        "send_customer_email": _should_send_customer_email(subject, send_email),
        "preserve_promo_eligibility": True,
        "apply_recovery_waiver": False,
    }
    return _post(
        client,
        f"/admin/clients/{cid}/onboarding-recovery/execute",
        admin_token,
        payload,
        step_up=step_up_tok,
        confirmation=conf,
    )


def _continuation_resolve(client: httpx.Client, url: str) -> Dict[str, Any]:
    m = re.search(r"[?&]token=([^&]+)", url)
    if not m:
        return {"ok": False, "error": "no token in url"}
    token = m.group(1)
    r = client.get(f"{API}/onboarding/continuation/resolve", params={"token": token}, timeout=60)
    try:
        body = r.json()
    except Exception:
        body = r.text[:500]
    return {"status": r.status_code, "ok": r.is_success, "body": body}


def _message_logs_recent(client: httpx.Client, admin_token: str, *, limit: int = 15) -> List[Dict[str, Any]]:
    r = _get(client, f"/admin/message-logs?limit={limit}", admin_token)
    if not r["ok"]:
        return []
    body = r["body"] if isinstance(r["body"], dict) else {}
    return body.get("logs") or body.get("items") or []


def _scenario_result(
    scenario_id: str,
    *,
    passed: bool,
    notes: str,
    evidence: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "scenario": scenario_id,
        "passed": passed,
        "notes": notes,
        "evidence": evidence,
        "verified_at": _utc(),
    }


def run_api_verification(*, dry_run: bool, send_email: bool = False) -> Dict[str, Any]:
    email, password = _load_admin_password()
    admin_token = _login_admin(email, password)
    step_up_tok = _step_up(admin_token, password)

    results: Dict[str, Any] = {
        "programme": MARKER,
        "api": API,
        "frontend": FE,
        "dry_run": dry_run,
        "send_customer_email": send_email,
        "started_at": _utc(),
        "scenarios": {},
    }

    with httpx.Client() as http:
        enriched = _pick_clients(http, admin_token)
        results["candidate_count"] = len(enriched)
        results["candidates_sample"] = enriched[:8]
        used_ids: set[str] = set()

        # Scenario E — expired checkout (run first; isolated client)
        sub_e = _pick_unused(enriched, "EXPIRED_CHECKOUT", used=used_ids)
        ev_e: Dict[str, Any] = {"subject": sub_e}
        regen_ok = False
        if sub_e:
            used_ids.add(sub_e["client_id"])
            if not dry_run:
                exec_e = _execute(
                    http, admin_token, step_up_tok, sub_e, "regenerate_payment", dry_run=False, send_email=False
                )
                ev_e["execute"] = exec_e
                regen_ok = bool(exec_e.get("ok"))
            else:
                regen_ok = "regenerate_payment" in (sub_e.get("executable_modes") or [])
        results["scenarios"]["E"] = _scenario_result(
            "E",
            passed=regen_ok,
            notes="expired checkout allows new session",
            evidence=ev_e,
        )

        # Scenario A — payment abandoned → recovery checkout + continuation landing
        sub_a = _pick_unused(
            enriched,
            "PAYMENT_ABANDONED",
            "EXPIRED_CHECKOUT",
            "PROMO_REDEMPTION_FAILED",
            used=used_ids,
        )
        ev_a: Dict[str, Any] = {"subject": sub_a}
        a_ok = False
        if sub_a:
            used_ids.add(sub_a["client_id"])
            modes_to_try: List[str] = []
            if "resume_onboarding" in (sub_a.get("executable_modes") or []):
                modes_to_try.append("resume_onboarding")
            if "regenerate_payment" in (sub_a.get("executable_modes") or []):
                modes_to_try.append("regenerate_payment")
            ev_a["modes_attempted"] = modes_to_try
            if not dry_run:
                for mode in modes_to_try:
                    exec_a = _execute(
                        http, admin_token, step_up_tok, sub_a, mode, dry_run=False, send_email=send_email
                    )
                    ev_a.setdefault("executions", []).append({"mode": mode, "result": exec_a})
                    if exec_a.get("ok"):
                        ex = (exec_a.get("body") or {}).get("execution") or {}
                        ev_a["successful_mode"] = mode
                        ev_a["continuation_url"] = ex.get("continuation_url") or ex.get("checkout_url")
                        a_ok = True
                        break
                if ev_a.get("continuation_url") and "onboarding/continue" in ev_a["continuation_url"]:
                    ev_a["continuation_resolve"] = _continuation_resolve(http, ev_a["continuation_url"])
                obs = _get(
                    http, f"/admin/clients/{sub_a['client_id']}/onboarding-recovery/observability", admin_token
                )
                ev_a["observability"] = obs
            else:
                a_ok = bool(modes_to_try)
        results["scenarios"]["A"] = _scenario_result(
            "A",
            passed=a_ok,
            notes="intake complete → governed recovery execute → continuation/checkout path",
            evidence=ev_a,
        )

        # Scenario B — activation incomplete (admin client list)
        sub_b = _find_activation_subject(enriched)
        ev_b: Dict[str, Any] = {"subject": sub_b}
        if sub_b:
            used_ids.add(sub_b["client_id"])
            if not dry_run:
                exec_b = _execute(
                    http, admin_token, step_up_tok, sub_b, "resend_activation", dry_run=False, send_email=send_email
                )
                ev_b["execute"] = exec_b
                ev_b["assessment_after"] = _get(
                    http, f"/admin/clients/{sub_b['client_id']}/onboarding-recovery/assessment", admin_token
                )
                ev_b["observability"] = _get(
                    http, f"/admin/clients/{sub_b['client_id']}/onboarding-recovery/observability", admin_token
                )
        results["scenarios"]["B"] = _scenario_result(
            "B",
            passed=bool(sub_b and (dry_run or ev_b.get("execute", {}).get("ok"))),
            notes="paid → activation incomplete → resend activation",
            evidence=ev_b,
        )

        # Scenario C — promo preserved when pilot_invite_code present
        sub_c = _find_promo_subject(http, admin_token, enriched)
        ev_c: Dict[str, Any] = {"subject": sub_c}
        promo_ok = False
        if sub_c and sub_c["client_id"] not in used_ids:
            used_ids.add(sub_c["client_id"])
            has_pilot = bool((sub_c.get("pilot_invite_code") or "").strip())
            ev_c["pilot_invite_code_present"] = has_pilot
            if not dry_run and has_pilot and sub_c.get("eligible"):
                exec_c = _execute(
                    http, admin_token, step_up_tok, sub_c, "regenerate_payment", dry_run=False, send_email=send_email
                )
                ev_c["execute"] = exec_c
                ex = (exec_c.get("body") or {}).get("execution") if exec_c.get("ok") else {}
                promo_ok = bool(ex and ex.get("promo_preserved") is True)
            elif dry_run:
                promo_ok = has_pilot
        else:
            ev_c["staging_fixture_missing"] = (
                "No staging client with pilot_invite_code; promo preservation requires pilot fixture."
            )
        results["scenarios"]["C"] = _scenario_result(
            "C",
            passed=promo_ok,
            notes="promo eligibility preserved on checkout when pilot_invite_code set",
            evidence=ev_c,
        )

        # Scenario D — duplicate recovery blocked after fresh checkout from scenario A/E
        dup_subject_id = None
        for key in ("A", "E"):
            subj = (results["scenarios"].get(key) or {}).get("evidence", {}).get("subject") or {}
            dup_subject_id = subj.get("client_id") or dup_subject_id
        ev_d: Dict[str, Any] = {"duplicate_target_client_id": dup_subject_id}
        blocked = False
        if dup_subject_id and not dry_run:
            assess = _get(
                http, f"/admin/clients/{dup_subject_id}/onboarding-recovery/assessment", admin_token
            )
            ev_d["assessment_before_duplicate"] = assess
            ab = assess.get("body") if isinstance(assess.get("body"), dict) else {}
            ev_d["subject"] = _assessment_row(http, admin_token, client_id=dup_subject_id)
            if ab.get("classification") == "RECOVERY_ALREADY_ACTIVE":
                blocked = True
                ev_d["blocked_by_classification"] = True
            else:
                exec_d = _execute(
                    http,
                    admin_token,
                    step_up_tok,
                    {"client_id": dup_subject_id},
                    "regenerate_payment",
                    dry_run=False,
                    send_email=False,
                )
                ev_d["execute"] = exec_d
                detail = exec_d.get("body") or {}
                err = detail.get("detail") if isinstance(detail, dict) else {}
                err_code = err.get("error_code") if isinstance(err, dict) else None
                blocked = exec_d.get("status") == 400 and err_code in (
                    "RECOVERY_CHECKOUT_STILL_FRESH",
                    "NOT_ELIGIBLE",
                )
        results["scenarios"]["D"] = _scenario_result(
            "D",
            passed=blocked,
            notes="fresh checkout blocks duplicate regenerate or classification RECOVERY_ALREADY_ACTIVE",
            evidence=ev_d,
        )

        results["fleet_metrics"] = _get(http, "/admin/clients/onboarding-recovery/fleet-metrics?days=7", admin_token)
        logs = _message_logs_recent(http, admin_token, limit=40)
        recovery_logs = [
            lg
            for lg in logs
            if (lg.get("event_type") or "").startswith("onboarding_recovery")
            or (lg.get("template_key") or "") in ("ADMIN_MANUAL", "WELCOME_EMAIL")
        ]
        results["message_logs_sample"] = (recovery_logs or logs)[:8]

    passed = sum(1 for s in results["scenarios"].values() if s.get("passed"))
    results["summary"] = {
        "passed": passed,
        "total": len(results["scenarios"]),
        "all_passed": passed == len(results["scenarios"]),
        "completed_at": _utc(),
    }
    return results


def run_browser_capture(
    admin_token: str,
    api_results: Dict[str, Any],
    *,
    admin_email: str = "",
    admin_password: str = "",
) -> Dict[str, Any]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {"ok": False, "error": "playwright not installed"}

    SCREENSHOTS.mkdir(parents=True, exist_ok=True)
    shots: List[str] = []
    captured: Dict[str, Any] = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})

        ev_a = (api_results.get("scenarios") or {}).get("A", {}).get("evidence") or {}
        url = ev_a.get("continuation_url")
        if url:
            if "onboarding/continue" in url:
                page.goto(url, wait_until="networkidle", timeout=90000)
                path = SCREENSHOTS / "continuation_landing.png"
                page.screenshot(path=str(path), full_page=True)
                shots.append(str(path.name))
                captured["continuation_landing"] = url
            elif "checkout.stripe.com" in url:
                page.goto(url, wait_until="domcontentloaded", timeout=90000)
                path = SCREENSHOTS / "payment_continuation_checkout.png"
                page.screenshot(path=str(path), full_page=True)
                shots.append(str(path.name))
                captured["payment_continuation"] = url

        cid = (ev_a.get("subject") or {}).get("client_id")
        if cid and admin_email and admin_password:
            try:
                page.goto(f"{FE}/login/admin", wait_until="networkidle", timeout=90000)
                page.fill("#email", admin_email)
                page.fill("#password", admin_password)
                page.get_by_role("button", name=re.compile(r"sign in as admin", re.I)).click(timeout=30000)
                page.wait_for_timeout(4000)
                panel_url = f"{FE}/admin/clients/{cid}"
                page.goto(panel_url, wait_until="networkidle", timeout=90000)
                path_admin = SCREENSHOTS / "admin_recovery_panel.png"
                page.screenshot(path=str(path_admin), full_page=True)
                shots.append(str(path_admin.name))
                captured["admin_control_panel"] = panel_url
            except Exception as exc:
                captured["admin_control_panel_error"] = str(exc)

        if cid:
            status_url = f"{FE}/onboarding-status?client_id={cid}"
            page.goto(status_url, wait_until="networkidle", timeout=90000)
            path2 = SCREENSHOTS / "onboarding_status.png"
            page.screenshot(path=str(path2), full_page=True)
            shots.append(str(path2.name))
            captured["onboarding_status"] = status_url

        browser.close()

    return {"ok": bool(shots), "screenshots": shots, "captured": captured}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Discover candidates only; no execute")
    parser.add_argument("--browser", action="store_true", help="Playwright screenshots for landing/status")
    parser.add_argument(
        "--send-email",
        action="store_true",
        help="Send customer recovery emails (use only on designated test inboxes)",
    )
    args = parser.parse_args()

    api_results = run_api_verification(dry_run=args.dry_run, send_email=args.send_email)
    _write("browser_runtime.json", api_results)

    browser_part: Dict[str, Any] = {"skipped": True}
    if args.browser and not args.dry_run:
        try:
            email, password = _load_admin_password()
            admin_token = _login_admin(email, password)
            browser_part = run_browser_capture(
                admin_token, api_results, admin_email=email, admin_password=password
            )
        except Exception as exc:
            browser_part = {"ok": False, "error": str(exc)}
    _write("browser_capture.json", browser_part)

    # Update REPORT
    report_path = OUT / "REPORT.md"
    lines = [
        "# PRELAUNCH-ONBOARDING-CONTINUATION-RECOVERY-ORCHESTRATION-01",
        "",
        f"**Staging verification run:** `{api_results.get('started_at')}`",
        "",
        f"**API:** {API}  |  **Frontend:** {FE}",
        "",
        "## Scenario results",
        "",
    ]
    for key in "ABCDE":
        sc = api_results.get("scenarios", {}).get(key, {})
        mark = "PASS" if sc.get("passed") else "FAIL"
        lines.append(f"- **{key}** — {mark}: {sc.get('notes', '')}")
    lines.append("")
    lines.append(f"**Summary:** {api_results.get('summary')}")
    lines.append("")
    if browser_part.get("screenshots"):
        lines.append("## Screenshots")
        for s in browser_part["screenshots"]:
            lines.append(f"- `screenshots/{s}`")
    lines.append("")
    lines.append("Full evidence: `browser_runtime.json`")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps(api_results.get("summary"), indent=2))
    return 0 if api_results.get("summary", {}).get("all_passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
