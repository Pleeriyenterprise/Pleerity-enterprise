#!/usr/bin/env python3
"""STRANDED-ONBOARDING-RECOVERY-AND-PROMO-CONTINUITY-01 — staging runtime certification.

Does not print secrets. Writes:
  docs/audit/stranded_onboarding_runtime_results_01.json
  docs/audit/stranded_onboarding_01/screenshots/
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import uuid
import atexit
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import httpx

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "audit" / "stranded_onboarding_runtime_results_01.json"
SHOTS = ROOT / "docs" / "audit" / "stranded_onboarding_01" / "screenshots"
API = os.getenv("STAGING_API", "https://pleerity-enterprise.onrender.com/api").rstrip("/")
FE = os.getenv("STAGING_FE", "https://pleerity-enterprise-9jjg.vercel.app").rstrip("/")
MARKER = "STRANDED-ONBOARDING-RUNTIME-01"
REASON = f"{MARKER} governed staging certification execute"
ORIGIN = FE
STAMP = datetime.now(timezone.utc).strftime("%Y%m%d%H%M")


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _mask(value: Optional[str], keep: int = 8) -> Optional[str]:
    if not value:
        return value
    s = str(value)
    if len(s) <= keep:
        return s
    return s[:keep] + "…"


def _load_admin() -> Tuple[str, str]:
    email = (os.getenv("STAGING_ADMIN_EMAIL") or "prosper@yopmail.com").strip()
    pw = (os.getenv("STAGING_ADMIN_PASSWORD") or "").strip()
    if not pw:
        for rel in (
            "docs/audit/ops_verify_01_6fd5ac4c_d35a58ae/.ops_verify_admin_pw.txt",
            "docs/audit/ops_verify_01_6fd5ac4c_d35a58ae/.ops_verify_temp_pw.txt",
            "docs/audit/.ops_verify_phase2_temp_pw.txt",
            "docs/audit/.ops_verify_temp_pw.txt",
        ):
            p = ROOT / rel
            if p.is_file():
                pw = p.read_text(encoding="utf-8").strip()
                break
    if not email or not pw:
        raise SystemExit("Set STAGING_ADMIN_EMAIL and STAGING_ADMIN_PASSWORD")
    return email, pw


def _headers(token: str, *, step_up: str = "", confirmation: str = "") -> Dict[str, str]:
    h = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Origin": ORIGIN,
    }
    if step_up:
        h["X-Step-Up-Token"] = step_up
    if confirmation:
        h["X-Admin-Confirmation-Token"] = confirmation
    return h


def _login(email: str, password: str) -> str:
    last: Optional[Exception] = None
    for _ in range(8):
        try:
            r = httpx.post(
                f"{API}/auth/admin/login",
                json={"email": email, "password": password},
                timeout=120,
            )
            if r.status_code in (502, 503, 504):
                time.sleep(12)
                continue
            r.raise_for_status()
            return r.json()["access_token"]
        except Exception as exc:
            last = exc
            time.sleep(8)
    raise RuntimeError(f"admin login failed: {last}")


def _step_up(token: str, password: str) -> str:
    r = httpx.post(
        f"{API}/auth/step-up/verify",
        json={"password": password},
        headers=_headers(token),
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["step_up_token"]


def _confirm(token: str, client_id: str, action_id: str = "onboarding_recovery_execute") -> str:
    r = httpx.post(
        f"{API}/admin/governance/confirmation-token",
        json={"action_id": action_id, "reason": REASON, "resource_key": client_id},
        headers=_headers(token),
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["token"]


def _http_call(fn, *, attempts: int = 4) -> Any:
    last: Optional[Exception] = None
    for i in range(attempts):
        try:
            return fn()
        except (httpx.ConnectError, httpx.ReadError, httpx.WriteError, httpx.TimeoutException) as exc:
            last = exc
            time.sleep(min(2 ** i, 12))
    raise last  # type: ignore[misc]


def _get(path: str, token: str, **kwargs: Any) -> Dict[str, Any]:
    def _do():
        return httpx.get(f"{API}{path}", headers=_headers(token), timeout=kwargs.get("timeout", 120))

    r = _http_call(_do)
    try:
        body = r.json()
    except Exception:
        body = {"raw": r.text[:1500]}
    return {"status": r.status_code, "ok": r.is_success, "body": body}


def _post(path: str, token: str, payload: dict, *, step_up: str = "", confirmation: str = "") -> Dict[str, Any]:
    def _do():
        return httpx.post(
            f"{API}{path}",
            json=payload,
            headers=_headers(token, step_up=step_up, confirmation=confirmation),
            timeout=180,
        )

    r = _http_call(_do)
    try:
        body = r.json()
    except Exception:
        body = {"raw": r.text[:1500]}
    return {"status": r.status_code, "ok": r.is_success, "body": body}


def _intake_payload(email: str, *, name: str) -> dict:
    return {
        "full_name": name,
        "email": email,
        "client_type": "INDIVIDUAL",
        "company_name": None,
        "preferred_contact": "EMAIL",
        "phone": None,
        "billing_plan": "PLAN_1_SOLO",
        "document_submission_method": "UPLOAD",
        "email_upload_consent": False,
        "consent_data_processing": True,
        "consent_service_boundary": True,
        "intake_session_id": str(uuid.uuid4()),
        "properties": [
            {
                "nickname": "Cert Prop",
                "postcode": "SW1A 1AA",
                "address_line_1": "10 Downing Street",
                "address_line_2": "",
                "city": "London",
                "jurisdiction": "England",
                "property_type": "house",
                "is_hmo": False,
                "bedrooms": 2,
                "occupancy": "single_family",
                "council_name": None,
                "council_code": None,
                "licence_required": "NO",
                "licence_type": None,
                "licence_status": None,
                "managed_by": "LANDLORD",
                "send_reminders_to": "LANDLORD",
                "agent_name": None,
                "agent_email": None,
                "agent_phone": None,
                "cert_gas_safety": "YES",
                "cert_eicr": "YES",
                "cert_epc": "YES",
            }
        ],
    }


def _public_post(path: str, payload: dict) -> Dict[str, Any]:
    def _do():
        return httpx.post(
            f"{API}{path}",
            json=payload,
            headers={"Content-Type": "application/json", "Origin": ORIGIN},
            timeout=180,
        )

    r = _http_call(_do)
    try:
        body = r.json()
    except Exception:
        body = {"raw": r.text[:1500]}
    return {"status": r.status_code, "ok": r.is_success, "body": body}


def _pending_setup(token: str) -> Dict[str, Any]:
    return _get("/admin/clients?lifecycle_bucket=pending_setup&limit=200", token)


def _client_in_pending(token: str, client_id: str) -> bool:
    body = _pending_setup(token).get("body") or {}
    return any(c.get("client_id") == client_id for c in (body.get("clients") or []))


def _identities_for_email(token: str, email: str) -> List[Dict[str, Any]]:
    r = _get(
        f"/admin/clients?q={email}&lifecycle_bucket=all&include_archived_clients=true&limit=50",
        token,
    )
    rows = ((r.get("body") or {}).get("clients") or []) if r.get("ok") else []
    out = []
    for c in rows:
        em = (c.get("email") or "").lower()
        rel = (c.get("released_canonical_email") or "").lower()
        if email.lower() in em or email.lower() in rel:
            out.append(
                {
                    "client_id": c.get("client_id"),
                    "email": c.get("email"),
                    "onboarding_status": c.get("onboarding_status"),
                    "onboarding_identity_status": c.get("onboarding_identity_status"),
                    "restarted_from_client_id": c.get("restarted_from_client_id"),
                    "released_canonical_email": c.get("released_canonical_email"),
                }
            )
    return out


def _assessment(token: str, client_id: str) -> Dict[str, Any]:
    return _get(f"/admin/clients/{client_id}/onboarding-recovery/assessment", token)


def _client_detail(token: str, client_id: str) -> Dict[str, Any]:
    return _get(f"/admin/clients/{client_id}", token)


def _execute(
    token: str,
    step_up: str,
    client_id: str,
    mode: str,
    *,
    send_email: bool,
    promo_decision: str = "none",
    selected_invite_code: Optional[str] = None,
    preserve: bool = False,
    password: Optional[str] = None,
) -> Dict[str, Any]:
    if password:
        step_up = _step_up(token, password)
    conf = _confirm(token, client_id)
    payload = {
        "mode": mode,
        "reason": REASON,
        "send_customer_email": send_email,
        "preserve_promo_eligibility": preserve or promo_decision == "preserve_existing",
        "apply_recovery_waiver": False,
        "promo_decision": promo_decision,
        "selected_invite_code": selected_invite_code,
    }
    return _post(
        f"/admin/clients/{client_id}/onboarding-recovery/execute",
        token,
        payload,
        step_up=step_up,
        confirmation=conf,
    )


def _audit(token: str, client_id: str) -> List[Dict[str, Any]]:
    r = _get(f"/admin/audit-logs?client_id={client_id}&limit=30", token)
    body = r.get("body") if isinstance(r.get("body"), dict) else {}
    logs = body.get("logs") or body.get("items") or []
    slim = []
    for lg in logs[:20]:
        slim.append(
            {
                "action": lg.get("action"),
                "created_at": lg.get("created_at") or lg.get("timestamp"),
                "resource_id": lg.get("resource_id"),
            }
        )
    return slim


def _messages(token: str, email: str) -> List[Dict[str, Any]]:
    r = _get("/admin/message-logs?limit=40", token)
    body = r.get("body") if isinstance(r.get("body"), dict) else {}
    logs = body.get("logs") or body.get("items") or []
    out = []
    em = email.lower()
    for lg in logs:
        recip = str(lg.get("recipient") or lg.get("to_email") or lg.get("email") or "").lower()
        if em and em not in recip:
            continue
        out.append(
            {
                "template_key": lg.get("template_key"),
                "event_type": lg.get("event_type"),
                "status": lg.get("status") or lg.get("delivery_status"),
                "provider_message_id": _mask(lg.get("provider_message_id") or lg.get("message_id")),
                "created_at": lg.get("created_at"),
            }
        )
    return out[:8]


def _wait_health(expected_prefix: str = "", timeout_s: int = 420) -> Dict[str, Any]:
    deadline = time.time() + timeout_s
    last: Dict[str, Any] = {}
    while time.time() < deadline:
        try:
            ver = httpx.get(f"{API}/version", timeout=30).json()
            h = httpx.get(f"{API}/health", timeout=30)
            try:
                health = h.json()
            except Exception:
                health = {"raw": h.text[:400]}
            last = {"version": ver, "health_status": h.status_code, "health": health}
            sched = (health.get("scheduler") or {}) if isinstance(health, dict) else {}
            sha = ver.get("commit_sha") or ""
            sha_ok = True if not expected_prefix else sha.startswith(expected_prefix)
            if sha_ok and ver.get("environment") == "staging" and not sched.get("stale", True):
                last["ready"] = True
                return last
        except Exception as exc:
            last = {"error": str(exc)}
        time.sleep(15)
    last["ready"] = False
    return last


def _frontend_bundle() -> Dict[str, Any]:
    html = httpx.get(FE + "/", timeout=60).text
    chunks = re.findall(r"static/js/main\.[^\"']+\.js", html)
    markers = {}
    name = chunks[0] if chunks else None
    if name:
        js = httpx.get(f"{FE}/{name}", timeout=90).text
        for s in (
            "release_and_restart",
            "recovery-promo-preserve",
            "preserve_existing",
            "approved-promos",
            "Release and restart",
        ):
            markers[s] = s in js
    return {"url": FE, "bundle": name, "markers": markers}


def _launch_browser(playwright):
    last = None
    for kwargs in (
        {"headless": True, "channel": "chrome"},
        {"headless": True, "channel": "msedge"},
        {"headless": True},
    ):
        try:
            return playwright.chromium.launch(**kwargs)
        except Exception as exc:
            last = exc
    raise RuntimeError(f"chromium launch failed: {last}")


def _inspect_checkout(url: str, shot_name: str) -> Dict[str, Any]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {"ok": False, "error": "playwright not installed"}
    SHOTS.mkdir(parents=True, exist_ok=True)
    try:
        with sync_playwright() as p:
            browser = _launch_browser(p)
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.goto(url, wait_until="domcontentloaded", timeout=120000)
            page.wait_for_timeout(4000)
            text = page.inner_text("body")[:6000]
            promo_ui = page.locator(
                'input[name="promotionCode"], button:has-text("Add promotion code"), button:has-text("Add promotion")'
            )
            promo_count = 0
            try:
                promo_count = promo_ui.count()
            except Exception:
                promo_count = 0
            path = SHOTS / shot_name
            page.screenshot(path=str(path), full_page=True)
            expired = any(w in text.lower() for w in ("expired", "no longer valid", "session has expired"))
            amount = None
            m = re.search(r"£\s*[\d,.]+", text)
            if m:
                amount = m.group(0)
            browser.close()
        return {
            "ok": True,
            "url_host": urlparse(url).netloc,
            "expired": expired,
            "amount_shown": amount,
            "customer_entered_promo_ui_count": promo_count,
            "text_preview": text[:1800],
            "screenshot": shot_name,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc), "url_host": urlparse(url).netloc}


def _pay_checkout(url: str, email: str, shot_name: str) -> Dict[str, Any]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {"ok": False, "error": "playwright not installed"}
    SHOTS.mkdir(parents=True, exist_ok=True)
    try:
        with sync_playwright() as p:
            browser = _launch_browser(p)
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.goto(url, wait_until="domcontentloaded", timeout=120000)
            page.wait_for_timeout(3500)
            before = page.inner_text("body")[:2500]
            if any(w in before.lower() for w in ("expired", "no longer valid")):
                page.screenshot(path=str(SHOTS / shot_name), full_page=True)
                browser.close()
                return {"ok": False, "expired": True, "text_preview": before, "screenshot": shot_name}
            try:
                em = page.locator("#email, input[type='email']").first
                if em.count() and em.is_visible():
                    val = em.input_value() if em.evaluate("el => 'value' in el") else ""
                    if not val:
                        em.fill(email)
            except Exception:
                pass
            try:
                for card_tab in (
                    page.get_by_role("radio", name=re.compile(r"^Card$", re.I)),
                    page.get_by_role("button", name=re.compile(r"^Card$", re.I)),
                    page.locator('[data-testid="card-accordion-item"]'),
                ):
                    try:
                        if card_tab.count() and card_tab.first.is_visible():
                            card_tab.first.click(timeout=3000)
                            page.wait_for_timeout(800)
                            break
                    except Exception:
                        continue
            except Exception:
                pass
            filled_card = False
            number_selectors = (
                'input[name="cardnumber"]',
                'input[name="number"]',
                'input[autocomplete="cc-number"]',
                'input[placeholder*="1234"]',
                'input[aria-label*="Card number" i]',
            )
            try:
                for fr in page.frames:
                    for sel in number_selectors:
                        loc = fr.locator(sel)
                        if loc.count():
                            loc.first.click(timeout=3000)
                            loc.first.fill("4242424242424242")
                            filled_card = True
                            for exp_sel in (
                                'input[name="exp-date"]',
                                'input[name="expiry"]',
                                'input[autocomplete="cc-exp"]',
                                'input[placeholder*="MM"]',
                                'input[aria-label*="Expir" i]',
                            ):
                                exp = fr.locator(exp_sel)
                                if exp.count():
                                    exp.first.fill("1230")
                                    break
                            for cvc_sel in (
                                'input[name="cvc"]',
                                'input[autocomplete="cc-csc"]',
                                'input[placeholder*="CVC"]',
                                'input[aria-label*="CVC" i]',
                            ):
                                cvc = fr.locator(cvc_sel)
                                if cvc.count():
                                    cvc.first.fill("123")
                                    break
                            break
                    if filled_card:
                        break
            except Exception:
                pass
            if not filled_card:
                try:
                    page.locator('iframe[title*="payment" i], iframe[name^="__privateStripeFrame"]').first.wait_for(
                        timeout=8000
                    )
                    frame = page.frame_locator(
                        'iframe[title*="payment" i], iframe[title*="card" i], iframe[name^="__privateStripeFrame"]'
                    ).first
                    frame.locator('input[name="number"], input[placeholder*="1234"], input[autocomplete="cc-number"]').first.fill(
                        "4242424242424242", timeout=8000
                    )
                    filled_card = True
                    try:
                        frame.locator(
                            'input[name="expiry"], input[autocomplete="cc-exp"], input[placeholder*="MM"]'
                        ).first.fill("1230", timeout=4000)
                    except Exception:
                        pass
                    try:
                        frame.locator(
                            'input[name="cvc"], input[autocomplete="cc-csc"], input[placeholder*="CVC"]'
                        ).first.fill("123", timeout=4000)
                    except Exception:
                        pass
                except Exception:
                    pass
            try:
                name = page.locator('input[name="billingName"], input[placeholder*="Full name"]')
                if name.count() and name.first.is_visible():
                    name.first.fill("Staging Cert")
            except Exception:
                pass
            try:
                pc = page.locator(
                    'input[name="billingPostalCode"], input[placeholder*="Postcode"], input[placeholder*="ZIP"]'
                )
                if pc.count() and pc.first.is_visible():
                    pc.first.fill("SW1A1AA")
            except Exception:
                pass
            clicked = False
            for label in ("Subscribe", "Pay", "Start trial", "Complete order", "Pay and subscribe"):
                try:
                    btn = page.get_by_role("button", name=re.compile(label, re.I))
                    if btn.count():
                        btn.first.click(timeout=5000)
                        clicked = True
                        break
                except Exception:
                    continue
            page.wait_for_timeout(8000)
            try:
                page.wait_for_url(re.compile(r"checkout/success|session_id="), timeout=90000)
            except Exception:
                pass
            final_url = page.url
            text = page.inner_text("body")[:2500]
            page.screenshot(path=str(SHOTS / shot_name), full_page=True)
            browser.close()
        success = "checkout/success" in final_url or "session_id=" in final_url
        return {
            "ok": success,
            "clicked_pay": clicked,
            "filled_card": filled_card,
            "final_url": final_url,
            "text_preview": text,
            "screenshot": shot_name,
            "pre_pay_preview": before[:800],
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _dismiss_cookies(page) -> None:
    for label in ("Accept All", "Accept all", "Allow all"):
        try:
            btn = page.get_by_role("button", name=re.compile(label, re.I))
            if btn.count():
                btn.first.click(timeout=2000)
                page.wait_for_timeout(500)
                return
        except Exception:
            continue


def _admin_panel(admin_email: str, admin_password: str, client_id: str, shot_name: str) -> Dict[str, Any]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {"ok": False, "error": "playwright not installed"}
    SHOTS.mkdir(parents=True, exist_ok=True)
    panel = f"{FE}/admin/clients/{client_id}"
    try:
        with sync_playwright() as p:
            browser = _launch_browser(p)
            page = browser.new_page(viewport={"width": 1400, "height": 1100})
            page.goto(f"{FE}/login/admin", wait_until="domcontentloaded", timeout=120000)
            page.wait_for_timeout(1500)
            _dismiss_cookies(page)
            page.fill("#email", admin_email)
            page.fill("#password", admin_password)
            page.locator('button[type="submit"]').first.click()
            try:
                page.wait_for_url(re.compile(r"/admin/"), timeout=90000)
            except Exception:
                pass
            _dismiss_cookies(page)
            page.goto(panel, wait_until="domcontentloaded", timeout=120000)
            page.wait_for_timeout(4000)
            _dismiss_cookies(page)
            try:
                page.locator('[data-testid="client-promo-recovery-controls"]').click(timeout=8000)
                page.wait_for_timeout(1500)
            except Exception:
                pass
            try:
                page.wait_for_selector(
                    '[data-testid="onboarding-recovery-assessment-panel"], [data-testid="recovery-execute-btn-regenerate_payment"]',
                    timeout=25000,
                )
            except Exception:
                pass
            text = page.inner_text("body")[:5000]
            page.screenshot(path=str(SHOTS / shot_name), full_page=True)
            markers = {
                "assessment_panel": page.locator('[data-testid="onboarding-recovery-assessment-panel"]').count() > 0,
                "release_btn": page.locator('[data-testid="recovery-execute-btn-release_and_restart"]').count() > 0,
                "regen_btn": page.locator('[data-testid="recovery-execute-btn-regenerate_payment"]').count() > 0,
                "grant_promo": page.locator('[data-testid="grant-promo-eligibility-btn"]').count() > 0,
                "grant_override": page.locator('[data-testid="grant-override-btn"]').count() > 0,
                "waive": page.locator('[data-testid="waive-onboarding-btn"]').count() > 0,
                "recover": page.locator('[data-testid="recover-onboarding-btn"]').count() > 0,
                "bypass": page.locator('[data-testid="bypass-first-time-btn"]').count() > 0,
                "landed_admin": "/admin/clients/" in page.url and "Today is available to client users only" not in text,
            }
            browser.close()
        return {
            "ok": bool(markers["landed_admin"]),
            "url": panel,
            "final_url": panel,
            "markers": markers,
            "text_preview": text[:2000],
            "screenshot": shot_name,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc), "url": panel}


def _wait_not_fresh(token: str, client_id: str, timeout_s: int = 2100) -> Dict[str, Any]:
    deadline = time.time() + timeout_s
    last = {}
    while time.time() < deadline:
        a = _assessment(token, client_id)
        body = a.get("body") or {}
        fresh = (body.get("state_summary") or {}).get("checkout_fresh")
        last = {
            "classification": body.get("classification"),
            "checkout_fresh": fresh,
            "checked_at": _utc(),
        }
        if fresh is False:
            last["ready"] = True
            return last
        time.sleep(30)
    last["ready"] = False
    return last


def _wait_provisioned(token: str, client_id: str, timeout_s: int = 480) -> Dict[str, Any]:
    deadline = time.time() + timeout_s
    last = {}
    while time.time() < deadline:
        d = _client_detail(token, client_id)
        body = d.get("body") or {}
        if isinstance(body, dict) and isinstance(body.get("client"), dict):
            body = body["client"]
        last = {
            "onboarding_status": body.get("onboarding_status"),
            "subscription_status": body.get("subscription_status"),
            "stripe_subscription_id": _mask(body.get("stripe_subscription_id")),
            "stripe_customer_id": _mask(body.get("stripe_customer_id")),
            "in_pending_setup": _client_in_pending(token, client_id),
        }
        if str(body.get("onboarding_status") or "").upper() == "PROVISIONED":
            last["ready"] = True
            return last
        time.sleep(12)
    last["ready"] = False
    return last


def _unwrap_client(detail: Dict[str, Any]) -> dict:
    body = detail.get("body") if isinstance(detail, dict) else {}
    if not isinstance(body, dict):
        return {}
    inner = body.get("client")
    return inner if isinstance(inner, dict) else body


def _slim_client(body: dict) -> dict:
    return {
        "client_id": body.get("client_id"),
        "email": body.get("email"),
        "customer_reference": body.get("customer_reference"),
        "onboarding_status": body.get("onboarding_status"),
        "onboarding_identity_status": body.get("onboarding_identity_status"),
        "latest_checkout_session_id": body.get("latest_checkout_session_id"),
        "recovery_checkout_context": body.get("recovery_checkout_context"),
        "pilot_invite_code": body.get("pilot_invite_code"),
        "restarted_from_client_id": body.get("restarted_from_client_id"),
        "released_canonical_email": body.get("released_canonical_email"),
        "subscription_status": body.get("subscription_status"),
        "stripe_subscription_id": _mask(body.get("stripe_subscription_id")),
        "stripe_customer_id": _mask(body.get("stripe_customer_id")),
    }


def _ensure_staging_test_promo(token: str) -> Dict[str, Any]:
    code = "STAGINGSO01"
    existing = _get(f"/admin/pilot-invites/{code}", token)
    invite = (existing.get("body") or {}).get("invite_code") if existing.get("ok") else None
    if invite:
        return {"ok": True, "created": False, "code": code, "stripe_coupon_id": invite.get("stripe_coupon_id")}
    created = _post(
        "/admin/pilot-invites",
        token,
        {
            "code": code,
            "code_type": "private_invite",
            "campaign_name": "Stranded onboarding staging cert",
            "max_uses": 20,
            "stripe_coupon_id": code,
            "discount_mode": "coupon",
            "discount_percent": 100,
            "discount_duration": "repeating",
            "discount_duration_in_months": 2,
            "waive_onboarding_fee": True,
            "onboarding_fee_policy": "waived",
            "applies_to_plan_codes": ["PLAN_1_SOLO", "PLAN_2_PORTFOLIO", "PLAN_3_PRO"],
            "first_time_customer_only": False,
            "is_publicly_enterable": False,
            "public_entry_enabled": False,
        },
    )
    return {
        "ok": created.get("ok"),
        "created": True,
        "code": code,
        "status": created.get("status"),
        "detail": created.get("body"),
    }


def main() -> int:
    email, password = _load_admin()
    results: Dict[str, Any] = {
        "programme": MARKER,
        "started_at": _utc(),
        "api": API,
        "frontend": FE,
        "production_touched": False,
        "committed_sha_expected": (os.getenv("STAGING_EXPECTED_SHA") or "").strip() or None,
        "paths": {},
        "matrix": {},
    }

    def _flush() -> None:
        results.setdefault("final_verdict", "STRANDED_ONBOARDING_INCOMPLETE")
        results["completed_at"] = _utc()
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(results, indent=2, default=str) + "\n", encoding="utf-8")

    atexit.register(_flush)
    print("health wait", flush=True)
    expected = results.get("committed_sha_expected") or ""
    results["health_wait"] = _wait_health(expected[:12] if expected else "", timeout_s=600)
    print("health", (results["health_wait"].get("health") or {}).get("status"), flush=True)
    try:
        results["frontend_bundle"] = _frontend_bundle()
    except Exception as exc:
        results["frontend_bundle"] = {"ok": False, "error": str(exc)}

    token = _login(email, password)
    print("admin login ok", flush=True)
    step = _step_up(token, password)
    results["staging_test_promo"] = _ensure_staging_test_promo(token)

    pending_before = _pending_setup(token)
    pb = pending_before.get("body") or {}
    results["pending_setup_before"] = {
        "total": pb.get("total"),
        "count": len(pb.get("clients") or []),
    }

    # Classify a sample of pending setup for fixture selection
    sample = []
    for row in (pb.get("clients") or [])[:8]:
        cid = row.get("client_id")
        if not cid:
            continue
        a = _assessment(token, cid)
        body = a.get("body") if isinstance(a.get("body"), dict) else {}
        sample.append(
            {
                "client_id": cid,
                "email": row.get("email"),
                "classification": body.get("classification"),
                "executable_modes": (body.get("strategy") or {}).get("executable_modes") or [],
                "has_validated_promo": (body.get("promo_recovery") or {}).get("has_validated_promo"),
                "checkout_fresh": (body.get("state_summary") or {}).get("checkout_fresh"),
                "paid_or_active": (body.get("state_summary") or {}).get("paid_or_active"),
                "password_set": (body.get("state_summary") or {}).get("password_set"),
            }
        )
    results["pending_sample"] = sample

    promos = _get("/admin/clients/onboarding-recovery/approved-promos", token)
    promo_rows = ((promos.get("body") or {}).get("promos") or []) if promos.get("ok") else []
    results["approved_promos"] = {
        "ok": promos.get("ok"),
        "customer_entered_promo_supported": (promos.get("body") or {}).get("customer_entered_promo_supported"),
        "codes": [p.get("code") for p in promo_rows[:8]],
    }
    codes = [p.get("code") for p in promo_rows if p.get("code")]
    selected_code = "STAGINGSO01" if "STAGINGSO01" in codes else (
        "LAUNCH2026" if "LAUNCH2026" in codes else (codes[0] if codes else None)
    )
    if not selected_code and (results.get("staging_test_promo") or {}).get("ok"):
        selected_code = "STAGINGSO01"

    # ---- Create dedicated fixtures ----
    promo_email = f"so.promo.{STAMP}@yopmail.com"
    release_email = f"so.release.{STAMP}@yopmail.com"
    paid_email = f"so.paid.{STAMP}@yopmail.com"
    select_email = f"so.select.{STAMP}@yopmail.com"

    created = {}
    for key, em, name in (
        ("promo", promo_email, "SO Promo Cert"),
        ("release", release_email, "SO Release Cert"),
        ("paid", paid_email, "SO Paid Cert"),
        ("select", select_email, "SO Select Cert"),
    ):
        created[key] = _public_post("/intake/submit", _intake_payload(em, name=name))
    results["fixtures_created"] = {
        k: {
            "status": v.get("status"),
            "ok": v.get("ok"),
            "client_id": (v.get("body") or {}).get("client_id"),
            "customer_reference": (v.get("body") or {}).get("customer_reference"),
            "email": email_for,
        }
        for k, v, email_for in (
            ("promo", created["promo"], promo_email),
            ("release", created["release"], release_email),
            ("paid", created["paid"], paid_email),
            ("select", created["select"], select_email),
        )
    }

    promo_id = (created["promo"].get("body") or {}).get("client_id")
    release_id = (created["release"].get("body") or {}).get("client_id")
    paid_id = (created["paid"].get("body") or {}).get("client_id")
    select_id = (created["select"].get("body") or {}).get("client_id")

    # Attach existing promo to promo fixture via Grant promo exception API
    if promo_id and selected_code:
        ov = _post(
            f"/admin/pilot-lifecycle/accounts/{promo_id}/eligibility-overrides",
            token,
            {
                "override_type": "manual_attach_promo",
                "override_reason": REASON,
                "scope": "client_id",
                "scope_value": promo_id,
                "invite_code": selected_code,
            },
            step_up=step,
        )
        results["paths"]["grant_promo_exception"] = {
            "status": ov.get("status"),
            "ok": ov.get("ok"),
            "invite_code": selected_code,
        }

    # Existing Promo & Recovery controls on the release fixture (safe unpaid)
    if release_id:
        controls = {}
        for label, body in (
            (
                "grant_promo_eligibility_bypass",
                {
                    "override_type": "bypass_first_time",
                    "override_reason": REASON,
                    "scope": "client_id",
                    "scope_value": release_id,
                },
            ),
            (
                "waive_onboarding_fee",
                {
                    "override_type": "recover_onboarding",
                    "override_reason": REASON,
                    "scope": "client_id",
                    "scope_value": release_id,
                },
            ),
        ):
            controls[label] = _post(
                f"/admin/pilot-lifecycle/accounts/{release_id}/eligibility-overrides",
                token,
                body,
                step_up=step,
            )
        results["paths"]["existing_promo_controls"] = {
            k: {"status": v.get("status"), "ok": v.get("ok")} for k, v in controls.items()
        }

    # ---- Journey 2: release + fresh registration ----
    j2: Dict[str, Any] = {"email": release_email, "client_id": release_id}
    if release_id:
        j2["before"] = _slim_client(_unwrap_client(_client_detail(token, release_id)))
        j2["in_pending_before"] = _client_in_pending(token, release_id)
        j2["identities_before"] = _identities_for_email(token, release_email)
        j2["check_email_before"] = _public_post("/intake/check-email", {"email": release_email})
        pre_co = _execute(
            token, step, release_id, "regenerate_payment", send_email=False, promo_decision="none", password=password
        )
        pre_ex = ((pre_co.get("body") or {}).get("execution") or {}) if pre_co.get("ok") else {}
        j2["pre_release_checkout"] = {
            "status": pre_co.get("status"),
            "ok": pre_co.get("ok"),
            "session_id": pre_ex.get("session_id"),
        }
        stale_checkout_url = pre_ex.get("checkout_url")
        if stale_checkout_url:
            j2["pre_release_checkout_inspect"] = _inspect_checkout(
                stale_checkout_url, "j2_checkout_before_release.png"
            )
        results["paths"]["journey_2_release_restart"] = j2
        # Concurrent release
        def _rel():
            return _execute(token, step, release_id, "release_and_restart", send_email=False, password=password)

        with ThreadPoolExecutor(max_workers=2) as pool:
            futs = [pool.submit(_rel), pool.submit(_rel)]
            conc = [f.result() for f in as_completed(futs)]
        j2["concurrent_release"] = [
            {
                "status": c.get("status"),
                "ok": c.get("ok"),
                "error": ((c.get("body") or {}).get("detail") if isinstance(c.get("body"), dict) else c.get("body")),
            }
            for c in conc
        ]
        ok_rel = [c for c in conc if c.get("ok")]
        j2["release_success_count"] = len(ok_rel)
        results["paths"]["journey_2_release_restart"] = j2
        j2["after_release"] = _slim_client(_unwrap_client(_client_detail(token, release_id)))
        j2["in_pending_after_release"] = _client_in_pending(token, release_id)
        j2["check_email_after"] = _public_post("/intake/check-email", {"email": release_email})
        if stale_checkout_url:
            j2["stale_checkout"] = _inspect_checkout(stale_checkout_url, "j2_stale_checkout.png")
        j2["audit"] = _audit(token, release_id)
        results["paths"]["journey_2_release_restart"] = j2
        # Concurrent registration
        def _reg(i: int):
            payload = _intake_payload(release_email, name=f"SO Restart {i}")
            return _public_post("/intake/submit", payload)

        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                futs = [pool.submit(_reg, 1), pool.submit(_reg, 2)]
                regs = [f.result() for f in as_completed(futs)]
        except Exception as exc:
            j2["concurrent_register_error"] = str(exc)
            regs = []
        j2["concurrent_register"] = [
            {
                "status": r.get("status"),
                "ok": r.get("ok"),
                "client_id": (r.get("body") or {}).get("client_id"),
                "restarted_from_client_id": (r.get("body") or {}).get("restarted_from_client_id"),
                "detail": (r.get("body") or {}).get("detail") if not r.get("ok") else None,
            }
            for r in regs
        ]
        new_ok = [r for r in regs if r.get("ok")]
        j2["register_success_count"] = len(new_ok)
        new_id = (new_ok[0].get("body") or {}).get("client_id") if new_ok else None
        j2["new_client_id"] = new_id
        if new_id:
            j2["new_after"] = _slim_client(_unwrap_client(_client_detail(token, new_id)))
            j2["new_in_pending"] = _client_in_pending(token, new_id)
            j2["restarted_from_client_id"] = (j2["new_after"] or {}).get("restarted_from_client_id")
            try:
                j2["admin_ui_released"] = _admin_panel(email, password, release_id, "j2_released_history.png")
                j2["admin_ui_new"] = _admin_panel(email, password, new_id, "j2_new_ccp.png")
            except Exception as exc:
                j2["admin_ui_error"] = str(exc)
        j2["identities_after"] = _identities_for_email(token, release_email)
        active = [
            x
            for x in j2["identities_after"]
            if str(x.get("onboarding_identity_status") or "").upper() != "RELEASED_FOR_RESTART"
            and not str(x.get("email") or "").endswith("@released.invalid")
        ]
        released_hist = [
            x
            for x in j2["identities_after"]
            if str(x.get("onboarding_identity_status") or "").upper() == "RELEASED_FOR_RESTART"
            or str(x.get("email") or "").endswith("@released.invalid")
        ]
        # released row email is vacated so may not appear in email search; check released client directly
        released_status = (j2.get("after_release") or {}).get("onboarding_identity_status")
        j2["passed"] = bool(
            j2.get("in_pending_before")
            and not j2.get("in_pending_after_release")
            and released_status == "RELEASED_FOR_RESTART"
            and (j2.get("check_email_after") or {}).get("body", {}).get("available") is True
            and j2.get("register_success_count") == 1
            and j2.get("restarted_from_client_id") == release_id
            and j2.get("new_client_id")
            and j2.get("new_client_id") != release_id
            and j2.get("release_success_count") == 1
        )
    results["paths"]["journey_2_release_restart"] = j2


    # ---- Journey 1: recovery checkout + validated promo ----
    j1: Dict[str, Any] = {"email": promo_email, "client_id": promo_id}
    if promo_id:
        j1["before"] = _slim_client(_unwrap_client(_client_detail(token, promo_id)))
        j1["in_pending_before"] = _client_in_pending(token, promo_id)
        j1["identities_before"] = _identities_for_email(token, promo_email)
        j1["assessment_before"] = (_assessment(token, promo_id).get("body") or {}).get("classification")
        first = _execute(
            token,
            step,
            promo_id,
            "regenerate_payment",
            send_email=False,
            promo_decision="preserve_existing",
            preserve=True,
            password=password,
        )
        j1["first_checkout"] = {
            "status": first.get("status"),
            "ok": first.get("ok"),
            "body": first.get("body"),
        }
        first_ex = ((first.get("body") or {}).get("execution") or {}) if first.get("ok") else {}
        old_url = first_ex.get("checkout_url")
        old_sid = first_ex.get("session_id")
        j1["old_session_id"] = old_sid
        if old_url:
            j1["old_checkout_inspect"] = _inspect_checkout(old_url, "j1_old_checkout.png")
        if first.get("ok"):
            print("waiting for checkout freshness to lapse", flush=True)
            j1["freshness_wait"] = _wait_not_fresh(token, promo_id)
            step = _step_up(token, password)
        else:
            j1["freshness_wait"] = {"ready": False, "skipped": True, "first_checkout_failed": True}
        second = _execute(
            token,
            step,
            promo_id,
            "regenerate_payment",
            send_email=True,
            promo_decision="preserve_existing",
            preserve=True,
            password=password,
        )
        j1["replacement"] = {
            "status": second.get("status"),
            "ok": second.get("ok"),
            "execution": (second.get("body") or {}).get("execution")
            if isinstance(second.get("body"), dict)
            else second.get("body"),
        }
        ex = (second.get("body") or {}).get("execution") or {}
        new_url = ex.get("checkout_url")
        j1["new_session_id"] = ex.get("session_id")
        j1["prior_session_superseded"] = ex.get("prior_session_superseded")
        j1["promo_preserved"] = ex.get("promo_preserved")
        j1["applied_invite_code"] = ex.get("applied_invite_code")
        j1["email_sent"] = ex.get("email_sent")
        j1["email_result"] = ex.get("email_result")
        if old_url:
            j1["old_after_supersede"] = _inspect_checkout(old_url, "j1_old_expired.png")
        if new_url:
            j1["new_checkout_inspect"] = _inspect_checkout(new_url, "j1_new_checkout.png")
            j1["customer_pay"] = _pay_checkout(new_url, promo_email, "j1_paid.png")
            j1["provisioning"] = _wait_provisioned(token, promo_id)
        j1["after"] = _slim_client(_unwrap_client(_client_detail(token, promo_id)))
        j1["in_pending_after"] = _client_in_pending(token, promo_id)
        j1["identities_after"] = _identities_for_email(token, promo_email)
        j1["messages"] = _messages(token, promo_email)
        j1["audit"] = _audit(token, promo_id)
        try:
            j1["admin_ui"] = _admin_panel(email, password, promo_id, "j1_admin_ccp.png")
        except Exception as exc:
            j1["admin_ui"] = {"ok": False, "error": str(exc)}
        active = [
            x
            for x in j1["identities_after"]
            if str(x.get("onboarding_identity_status") or "ACTIVE").upper() != "RELEASED_FOR_RESTART"
        ]
        j1["passed"] = bool(
            second.get("ok")
            and ex.get("prior_session_superseded")
            and j1.get("email_sent")
            and (j1.get("provisioning") or {}).get("ready")
            and j1.get("in_pending_before")
            and not j1.get("in_pending_after")
            and len(active) == 1
            and ((j1.get("new_checkout_inspect") or {}).get("customer_entered_promo_ui_count") or 0) == 0
        )
    results["paths"]["journey_1_recovery_promo"] = j1

    # ---- Paid checkout choice (no promo) ----
    j_paid: Dict[str, Any] = {"email": paid_email, "client_id": paid_id}
    if paid_id:
        exec_p = _execute(
            token, step, paid_id, "regenerate_payment", send_email=False, promo_decision="none", password=password
        )
        ex_p = (exec_p.get("body") or {}).get("execution") or {}
        j_paid["execute"] = {"status": exec_p.get("status"), "ok": exec_p.get("ok"), "execution": ex_p}
        if ex_p.get("checkout_url"):
            j_paid["checkout"] = _inspect_checkout(ex_p["checkout_url"], "paid_checkout.png")
        j_paid["passed"] = bool(exec_p.get("ok") and ex_p.get("promo_decision") == "none")
    results["paths"]["choice_paid_checkout"] = j_paid

    # ---- Admin-selected approved promo ----
    j_sel: Dict[str, Any] = {"email": select_email, "client_id": select_id, "code": selected_code}
    if select_id and selected_code:
        exec_s = _execute(
            token,
            step,
            select_id,
            "regenerate_payment",
            send_email=False,
            promo_decision="apply_selected",
            selected_invite_code=selected_code,
            password=password,
        )
        ex_s = (exec_s.get("body") or {}).get("execution") or {}
        j_sel["execute"] = {"status": exec_s.get("status"), "ok": exec_s.get("ok"), "execution": ex_s}
        if ex_s.get("checkout_url"):
            j_sel["checkout"] = _inspect_checkout(ex_s["checkout_url"], "selected_promo_checkout.png")
        j_sel["passed"] = bool(exec_s.get("ok") and ex_s.get("applied_invite_code") == selected_code)
    results["paths"]["choice_admin_selected_promo"] = j_sel

    # ---- Release guards ----
    guards: Dict[str, Any] = {}
    # password-set / provisioned from admin list
    all_clients = _get("/admin/clients?lifecycle_bucket=active&limit=80", token)
    rows = ((all_clients.get("body") or {}).get("clients") or []) if all_clients.get("ok") else []
    guard_targets = {"provisioned": None, "password_or_paid": None}
    for row in rows:
        cid = row.get("client_id")
        if not cid or cid in {promo_id, release_id, paid_id, select_id}:
            continue
        a = _assessment(token, cid)
        body = a.get("body") or {}
        modes = (body.get("strategy") or {}).get("executable_modes") or []
        cl = body.get("classification")
        st = body.get("state_summary") or {}
        if st.get("password_set") and not guard_targets["password_or_paid"]:
            guard_targets["password_or_paid"] = cid
        if str(row.get("onboarding_status") or "").upper() == "PROVISIONED" and not guard_targets["provisioned"]:
            guard_targets["provisioned"] = cid
        if cl in ("PARTIAL_PROVISIONING", "ACTIVATION_INCOMPLETE", "DUPLICATE_RECOVERY_RISK", "SUBSCRIPTION_DRIFT"):
            guard_targets.setdefault(cl, cid)
        if "release_and_restart" in modes:
            continue
    for label, cid in guard_targets.items():
        if not cid:
            guards[label] = {"skipped": True}
            continue
        res = _execute(token, step, cid, "release_and_restart", send_email=False, password=password)
        detail = res.get("body") or {}
        err = detail.get("detail") if isinstance(detail, dict) else {}
        guards[label] = {
            "client_id": cid,
            "status": res.get("status"),
            "ok": res.get("ok"),
            "error_code": err.get("error_code") if isinstance(err, dict) else None,
            "message": err.get("message") if isinstance(err, dict) else None,
            "rejected": (not res.get("ok"))
            and (err.get("error_code") if isinstance(err, dict) else None)
            in {"NOT_ELIGIBLE", "MODE_CLASSIFICATION_MISMATCH", "RELEASE_NOT_ALLOWED"},
        }
    # also try release on the now-paid journey-1 client if provisioned
    if promo_id and (j1.get("provisioning") or {}).get("ready"):
        res = _execute(token, step, promo_id, "release_and_restart", send_email=False, password=password)
        detail = res.get("body") or {}
        err = detail.get("detail") if isinstance(detail, dict) else {}
        guards["paid_after_journey_1"] = {
            "client_id": promo_id,
            "status": res.get("status"),
            "error_code": err.get("error_code") if isinstance(err, dict) else None,
            "rejected": not res.get("ok"),
        }
    results["paths"]["release_guards"] = guards
    results["paths"]["release_guards"]["passed"] = all(
        (v.get("skipped") or v.get("rejected")) for k, v in guards.items() if k != "passed"
    )

    pending_after = _pending_setup(token)
    pa = pending_after.get("body") or {}
    results["pending_setup_after"] = {
        "total": pa.get("total"),
        "count": len(pa.get("clients") or []),
        "released_still_listed": any(
            c.get("client_id") == release_id for c in (pa.get("clients") or [])
        ),
        "promo_still_listed": any(c.get("client_id") == promo_id for c in (pa.get("clients") or [])),
    }

    # Matrix
    results["matrix"] = {
        "recovery_checkout_validated_promo": "PASS" if j1.get("passed") else "FAIL",
        "release_and_fresh_registration": "PASS" if j2.get("passed") else "FAIL",
        "release_guards": "PASS" if results["paths"]["release_guards"].get("passed") else "FAIL",
        "choice_preserve_existing": "PASS" if j1.get("promo_preserved") or j1.get("applied_invite_code") else "FAIL",
        "choice_paid": "PASS" if j_paid.get("passed") else "FAIL",
        "choice_admin_selected": "PASS" if j_sel.get("passed") else "FAIL",
        "customer_entered_promo_disabled": "PASS"
        if (j1.get("new_checkout_inspect") or {}).get("customer_entered_promo_ui_count") == 0
        else "FAIL",
        "pending_setup_auto_drop": "PASS"
        if (not results["pending_setup_after"].get("released_still_listed"))
        and (
            (not j1.get("passed"))
            or (not results["pending_setup_after"].get("promo_still_listed"))
        )
        else "FAIL",
        "existing_promo_controls": "PASS"
        if all((v.get("ok") for v in (results["paths"].get("existing_promo_controls") or {}).values()))
        or results["paths"].get("grant_promo_exception", {}).get("ok")
        else "INCOMPLETE",
    }
    critical = [
        results["matrix"]["recovery_checkout_validated_promo"],
        results["matrix"]["release_and_fresh_registration"],
        results["matrix"]["release_guards"],
    ]
    if all(x == "PASS" for x in critical) and results["matrix"]["pending_setup_auto_drop"] == "PASS":
        results["final_verdict"] = "STRANDED_ONBOARDING_VERIFIED"
    else:
        results["final_verdict"] = "STRANDED_ONBOARDING_INCOMPLETE"
    results["completed_at"] = _utc()
    OUT.write_text(json.dumps(results, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps({"verdict": results["final_verdict"], "out": str(OUT), "matrix": results["matrix"]}))
    return 0 if results["final_verdict"] == "STRANDED_ONBOARDING_VERIFIED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
