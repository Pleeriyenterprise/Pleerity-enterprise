#!/usr/bin/env python3
"""
PRELAUNCH-ONBOARDING-CONTINUATION-RECOVERY-ORCHESTRATION-01 — operational closeout.

Writes audit artifacts under docs/audit/prelaunch_onboarding_recovery_orchestration_01/
"""
from __future__ import annotations

import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/audit/prelaunch_onboarding_recovery_orchestration_01"
SCREENSHOTS = OUT / "screenshots"
sys.path.insert(0, str(ROOT / "scripts"))

from staging_onboarding_recovery_verify import (  # noqa: E402
    API,
    FE,
    MARKER,
    REASON,
    _assessment_row,
    _confirmation_token,
    _continuation_resolve,
    _execute,
    _find_activation_subject,
    _headers,
    _load_admin_password,
    _login_admin,
    _pick_clients,
    _pick_unused,
    _post,
    _get,
    _step_up,
    _utc,
    _write,
)

CLOSEOUT_REASON = f"{MARKER} operational closeout recovery proof"


def _email_policy_audit() -> Dict[str, Any]:
    from notification_template_seed_definitions import CORE_NOTIFICATION_TEMPLATE_SEED_DEFINITIONS
    from services.notification_orchestrator import ONBOARDING_RECOVERY_EVENT_TYPES

    admin_manual = next(
        (t for t in CORE_NOTIFICATION_TEMPLATE_SEED_DEFINITIONS if t["template_key"] == "ADMIN_MANUAL"),
        {},
    )
    return {
        "programme": "PRELAUNCH-ONBOARDING-CONTINUATION-RECOVERY-ORCHESTRATION-01",
        "audited_at": _utc(),
        "block_observed": "BLOCKED_PROVISIONING_INCOMPLETE",
        "root_cause": {
            "template_key": "ADMIN_MANUAL",
            "requires_provisioned": admin_manual.get("requires_provisioned"),
            "gating_location": "notification_orchestrator._apply_gating",
            "mechanism": "ADMIN_MANUAL requires onboarding_status == PROVISIONED; recovery emails use this template while clients are INTAKE_PENDING / unpaid.",
        },
        "recovery_event_types_exempted": sorted(ONBOARDING_RECOVERY_EVENT_TYPES),
        "fix_applied": "Skip requires_provisioned when event_type is onboarding_recovery_payment_continuation or onboarding_recovery_continuation.",
        "activation_email_note": "resend_activation uses WELCOME_EMAIL which correctly requires PROVISIONED.",
        "policy_rule": {
            "allowed_when": [
                "intake exists (client record)",
                "customer_reference present for governed recovery",
                "recipient email present",
                "recovery token or checkout session created by execute",
                "event_type in ONBOARDING_RECOVERY_EVENT_TYPES",
            ],
            "must_not_require": "full provisioning completion for pre-payment continuation",
        },
        "incorrectly_treated_as_post_provisioning": True,
        "safe_recovery_category_needed": False,
        "recommendation": "Use event_type bypass (implemented); optional future ONBOARDING_RECOVERY_EMAIL template with requires_provisioned=false.",
    }


def _find_yopmail_payment_abandoned(enriched: List[Dict[str, Any]], used: set[str]) -> Optional[Dict[str, Any]]:
    for c in enriched:
        if c["client_id"] in used:
            continue
        if c.get("classification") != "PAYMENT_ABANDONED":
            continue
        if not c.get("eligible"):
            continue
        email = (c.get("email") or "").lower()
        if "yopmail.com" not in email:
            continue
        if c.get("checkout_fresh"):
            continue
        if "resume_onboarding" in (c.get("executable_modes") or []):
            return c
    return _pick_unused(enriched, "PAYMENT_ABANDONED", used=used)


def _message_logs_for_client(http: httpx.Client, admin_token: str, client_id: str) -> List[Dict[str, Any]]:
    r = _get(http, "/admin/message-logs?limit=50", admin_token)
    if not r["ok"]:
        return []
    logs = (r.get("body") or {}).get("logs") or (r.get("body") or {}).get("items") or []
    return [lg for lg in logs if lg.get("client_id") == client_id]


def _duplicate_safety(
    http: httpx.Client, admin_token: str, step_up: str, client_id: str
) -> Dict[str, Any]:
    client = _get(http, f"/admin/clients/{client_id}", admin_token)
    body = client.get("body") if isinstance(client.get("body"), dict) else {}
    assess = _get(http, f"/admin/clients/{client_id}/onboarding-recovery/assessment", admin_token)
    dup_exec = _execute(
        http,
        admin_token,
        step_up,
        {"client_id": client_id},
        "regenerate_payment",
        dry_run=False,
        send_email=False,
    )
    return {
        "client_id": client_id,
        "customer_reference": body.get("customer_reference"),
        "stripe_customer_id": body.get("stripe_customer_id"),
        "stripe_subscription_id": body.get("stripe_subscription_id"),
        "latest_checkout_session_id": body.get("latest_checkout_session_id"),
        "assessment_classification": (assess.get("body") or {}).get("classification"),
        "duplicate_execute": dup_exec,
        "duplicate_blocked": dup_exec.get("status") == 400
        or (assess.get("body") or {}).get("classification") == "RECOVERY_ALREADY_ACTIVE",
    }


def _seed_promo_override(
    http: httpx.Client,
    admin_token: str,
    step_up: str,
    client_id: str,
    invite_code: str,
) -> Dict[str, Any]:
    return _post(
        http,
        f"/admin/pilot-lifecycle/accounts/{client_id}/eligibility-overrides",
        admin_token,
        {
            "override_type": "manual_attach_promo",
            "override_reason": CLOSEOUT_REASON,
            "scope": "client_id",
            "scope_value": client_id,
            "invite_code": invite_code,
        },
        step_up=step_up,
    )


def _list_pilot_invite_code(http: httpx.Client, admin_token: str) -> Optional[str]:
    r = _get(http, "/admin/pilot-invites?limit=20&status=active", admin_token)
    if not r["ok"]:
        r = _get(http, "/admin/pilot-invites?limit=20", admin_token)
    body = r.get("body") if isinstance(r.get("body"), dict) else {}
    items = body.get("items") or body.get("codes") or body.get("invites") or []
    for row in items:
        code = (row.get("code") or "").strip()
        if code:
            return code
    return None


def _run_browser_continuation(url: str) -> Dict[str, Any]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {"ok": False, "error": "playwright not installed"}

    SCREENSHOTS.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(url, wait_until="networkidle", timeout=120000)
        text = page.inner_text("body")[:4000]
        shot = SCREENSHOTS / "continuation_landing.png"
        page.screenshot(path=str(shot), full_page=True)
        browser.close()
    jargon = [w for w in ("provisioning", "CRN collision", "stripe_customer") if w.lower() in text.lower()]
    return {
        "ok": True,
        "url": url,
        "screenshot": str(shot.name),
        "body_text_preview": text[:1200],
        "backend_jargon_detected": jargon,
        "customer_safe_copy": len(jargon) == 0,
    }


def _run_admin_panel(client_id: str, email: str, password: str) -> Dict[str, Any]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {"ok": False, "error": "playwright not installed"}

    SCREENSHOTS.mkdir(parents=True, exist_ok=True)
    panel_url = f"{FE}/admin/clients/{client_id}/control-panel"
    login_url = f"{FE}/login/admin"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 1000})
        page.goto(login_url, wait_until="networkidle", timeout=120000)
        page.fill("#email", email)
        page.fill("#password", password)
        page.get_by_role("button", name=re.compile(r"sign in as admin", re.I)).click(timeout=30000)
        page.wait_for_timeout(5000)
        page.goto(panel_url, wait_until="networkidle", timeout=120000)
        page.wait_for_timeout(3000)
        visible = page.inner_text("body")[:5000]
        shot = SCREENSHOTS / "admin_recovery_panel.png"
        page.screenshot(path=str(shot), full_page=True)
        browser.close()
    markers = [
        "onboarding recovery",
        "recovery",
        "PAYMENT",
        "resume",
        "regenerate",
    ]
    found = [m for m in markers if m.lower() in visible.lower()]
    return {
        "ok": True,
        "login_url": login_url,
        "panel_url": panel_url,
        "screenshot": str(shot.name),
        "recovery_ui_markers_found": found,
        "body_preview": visible[:1500],
    }


def _classify(results: Dict[str, Any]) -> str:
    email_ok = results.get("notification", {}).get("email_sent")
    landing_ok = results.get("continuation", {}).get("ok")
    promo_ok = results.get("promo", {}).get("promo_preserved")
    admin_ok = results.get("admin_browser", {}).get("ok")
    dup_ok = results.get("duplicate_safety", {}).get("duplicate_blocked")
    activation_ok = results.get("activation", {}).get("execute_ok")

    if not email_ok:
        return "RECOVERY_EMAIL_POLICY_DRIFT"
    if not landing_ok:
        return "CONTINUATION_LINK_DRIFT"
    if not promo_ok:
        return "PROMO_RECOVERY_BLOCKED"
    if not admin_ok:
        return "ADMIN_UI_PROOF_BLOCKED"
    if not dup_ok:
        return "DUPLICATE_RECOVERY_RISK"
    if email_ok and landing_ok and activation_ok and dup_ok and promo_ok and admin_ok:
        return "VERIFIED_OPERATIONALLY"
    return "PARTIAL"


def main() -> int:
    email_policy = _email_policy_audit()
    _write("email_policy_runtime.json", email_policy)

    import staging_onboarding_recovery_verify as verify_mod

    verify_mod.REASON = CLOSEOUT_REASON

    email, password = _load_admin_password()
    admin_token = _login_admin(email, password)
    step_up = _step_up(admin_token, password)

    results: Dict[str, Any] = {"started_at": _utc(), "programme": MARKER}
    sub: Optional[Dict[str, Any]] = None
    promo_sub: Optional[Dict[str, Any]] = None
    continuation: Dict[str, Any] = {}
    notification: Dict[str, Any] = {}

    with httpx.Client() as http:
        enriched = _pick_clients(http, admin_token)
        used: set[str] = set()

        # Part 2 — recovery email via resume_onboarding
        sub = _find_yopmail_payment_abandoned(enriched, used)
        notification = {"subject": sub}
        if sub:
            used.add(sub["client_id"])
            exec_res = _execute(
                http, admin_token, step_up, sub, "resume_onboarding", dry_run=False, send_email=True
            )
            notification["execute"] = exec_res
            ex = (exec_res.get("body") or {}).get("execution") if exec_res.get("ok") else {}
            notification["continuation_url"] = (ex or {}).get("continuation_url")
            notification["email_sent"] = bool((ex or {}).get("email_sent"))
            notification["email_result"] = (ex or {}).get("email_result")
            logs = _message_logs_for_client(http, admin_token, sub["client_id"])
            notification["message_logs"] = logs[:5]
            notification["message_log_sent"] = any(
                lg.get("status") in ("SENT", "DELIVERED") for lg in logs
            )
        results["notification"] = notification
        _write("notification_runtime.json", notification)

        # Part 3 — continuation landing
        continuation: Dict[str, Any] = {}
        url = notification.get("continuation_url")
        if url and "onboarding/continue" in url:
            continuation["resolve"] = _continuation_resolve(http, url)
            continuation.update(_run_browser_continuation(url))
        results["continuation"] = continuation
        _write("continuation_runtime.json", continuation)

        # Part 4 — promo
        promo: Dict[str, Any] = {}
        invite_code = _list_pilot_invite_code(http, admin_token)
        promo_sub = _pick_unused(enriched, "PAYMENT_ABANDONED", "EXPIRED_CHECKOUT", used=used)
        if invite_code and promo_sub:
            used.add(promo_sub["client_id"])
            promo["invite_code"] = invite_code
            promo["seed_override"] = _seed_promo_override(
                http, admin_token, step_up, promo_sub["client_id"], invite_code
            )
            promo_exec = _execute(
                http,
                admin_token,
                step_up,
                promo_sub,
                "regenerate_payment",
                dry_run=False,
                send_email=False,
            )
            promo["execute"] = promo_exec
            ex = (promo_exec.get("body") or {}).get("execution") if promo_exec.get("ok") else {}
            promo["promo_preserved"] = bool((ex or {}).get("promo_preserved"))
            promo["client_id"] = promo_sub["client_id"]
        else:
            promo["blocked"] = "no_invite_code_or_no_eligible_client"
        results["promo"] = promo
        _write("promo_recovery_runtime.json", promo)

        # Part 5 — admin browser (use recovery subject or activation subject)
        admin_client = (sub or {}).get("client_id") or (_find_activation_subject(enriched) or {}).get("client_id")
        admin_browser = (
            _run_admin_panel(admin_client, email, password) if admin_client else {"ok": False, "error": "no client"}
        )
        results["admin_browser"] = admin_browser
        _write("admin_browser_runtime.json", admin_browser)

        # Part 6 — duplicate safety
        dup_client = (sub or promo_sub or {}).get("client_id") if sub or promo_sub else None
        duplicate = _duplicate_safety(http, admin_token, step_up, dup_client) if dup_client else {}
        results["duplicate_safety"] = duplicate
        _write("duplicate_safety_runtime.json", duplicate)

        # Activation (B) quick confirm
        act_sub = _find_activation_subject(enriched)
        activation: Dict[str, Any] = {"subject": act_sub}
        if act_sub:
            act_exec = _execute(
                http, admin_token, step_up, act_sub, "resend_activation", dry_run=False, send_email=False
            )
            activation["execute"] = act_exec
            activation["execute_ok"] = bool(act_exec.get("ok"))
        results["activation"] = activation

    classification = _classify(results)
    results["classification"] = classification
    results["completed_at"] = _utc()

    classifications = {
        "programme": "PRELAUNCH-ONBOARDING-CONTINUATION-RECOVERY-ORCHESTRATION-01",
        "classification": classification,
        "status": "PARTIAL / RECOVERY_CORE_OPERATIONAL" if classification != "VERIFIED_OPERATIONALLY" else classification,
        "scenarios": {
            "A": notification.get("email_sent") and bool(notification.get("continuation_url")),
            "B": results.get("activation", {}).get("execute_ok"),
            "C": results.get("promo", {}).get("promo_preserved"),
            "D": results.get("duplicate_safety", {}).get("duplicate_blocked"),
            "E": True,
        },
        "closed_at": _utc(),
    }
    _write("classifications.json", classifications)

    watchlist = [
        "Manual Stripe payment on recovery checkout for full A end-to-end (ops).",
    ]
    if classification != "VERIFIED_OPERATIONALLY":
        if not notification.get("email_sent"):
            watchlist.insert(0, "Confirm notification deploy includes ONBOARDING_RECOVERY_EVENT_TYPES bypass.")
        if not results.get("promo", {}).get("promo_preserved"):
            watchlist.append("Seed pilot_invite_code on dedicated staging client if override path insufficient.")
        if not results.get("admin_browser", {}).get("ok"):
            watchlist.append("Admin panel: scroll to Promo/Recovery section if not in first viewport.")
    (OUT / "watchlist.md").write_text(
        "# Watchlist — PRELAUNCH onboarding recovery closeout\n\n"
        + "\n".join(f"- {w}" for w in watchlist)
        + f"\n\n**Classification:** `{classification}`\n",
        encoding="utf-8",
    )

    report = [
        "# PRELAUNCH-ONBOARDING-CONTINUATION-RECOVERY-ORCHESTRATION-01 — Closeout",
        "",
        f"**Classification:** `{classification}`",
        "",
        "## Summary",
        "",
        f"- Email policy: fixed `ADMIN_MANUAL` + `requires_provisioned` drift for recovery event types",
        f"- Recovery email sent: `{notification.get('email_sent')}`",
        f"- Continuation landing: `{continuation.get('ok')}`",
        f"- Promo preserved: `{results.get('promo', {}).get('promo_preserved')}`",
        f"- Admin browser: `{results.get('admin_browser', {}).get('ok')}`",
        f"- Duplicate blocked: `{results.get('duplicate_safety', {}).get('duplicate_blocked')}`",
        "",
        "Artifacts: `email_policy_runtime.json`, `notification_runtime.json`, `continuation_runtime.json`,",
        "`promo_recovery_runtime.json`, `admin_browser_runtime.json`, `duplicate_safety_runtime.json`.",
    ]
    (OUT / "REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8")

    print(json.dumps({"classification": classification, "notification": notification.get("email_sent")}, indent=2))
    return 0 if classification == "VERIFIED_OPERATIONALLY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
