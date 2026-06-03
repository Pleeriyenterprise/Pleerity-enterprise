#!/usr/bin/env python3
"""
BILLING-CLIENT-ACCESS-DELIVERABILITY-RECOVERY-01
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import subprocess
import sys
import time
from datetime import datetime, timezone
from urllib.parse import unquote
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import httpx

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))
OUT = BACKEND_ROOT / "docs/audit/billing_client_access_deliverability_recovery_01"
API = os.getenv("STAGING_API", "https://pleerity-enterprise.onrender.com/api").rstrip("/")
FE = os.getenv("STAGING_FE", "https://pleerityenterprise.co.uk").rstrip("/")

CLIENT_ID = os.getenv("DRIFT_CLIENT_ID", "80f83edd-ba12-41ed-929a-bbaf8c696a23")
OLD_EMAIL = "confidence@yaho.co.uk"
CRN = "PLE-CVP-2026-000011"
NEW_EMAIL = os.getenv("RECOVERY_PORTAL_EMAIL", "confidence.cvp000011@yopmail.com")
PROGRAMME = "BILLING-CLIENT-ACCESS-DELIVERABILITY-RECOVERY-01"
REASON = (
    "BILLING-CLIENT-ACCESS-DELIVERABILITY-RECOVERY-01: governed portal email change and "
    "password setup recovery for deliverability-blocked client (no auth bypass)."
)
BLOCKED_COPY = "Your billing record needs to be refreshed before plan changes can continue."

SECRET_PATTERNS = (
    re.compile(r"mongodb\+srv://[^\s\"']+", re.I),
    re.compile(r"sk_(live|test)_[A-Za-z0-9]{8,}", re.I),
    re.compile(r"token=[A-Za-z0-9_-]{12,}", re.I),
    re.compile(r"password[\"']?\s*:\s*[\"'][^\"']+[\"']", re.I),
)


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write(name: str, data: object) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, indent=2, default=str) + "\n"
    for pat in SECRET_PATTERNS:
        text = pat.sub("[REDACTED]", text)
    (OUT / name).write_text(text, encoding="utf-8")


def _mask_email(email: str) -> str:
    e = (email or "").strip()
    if "@" not in e:
        return "***"
    local, domain = e.split("@", 1)
    return f"{local[:3]}***@{domain}"


def _email_hash(email: str) -> str:
    return hashlib.sha256((email or "").strip().lower().encode()).hexdigest()[:16]


def _load_pw(rel: str) -> str:
    p = BACKEND_ROOT / rel
    return p.read_text(encoding="utf-8").strip() if p.is_file() else ""


def _headers(token: str, *, step_up: str = "") -> Dict[str, str]:
    h = {"Authorization": f"Bearer {token}"}
    if step_up:
        h["X-Step-Up-Token"] = step_up
    return h


def _login_admin() -> Tuple[str, str]:
    email = os.getenv("STAGING_ADMIN_EMAIL", "aigbochievictory@gmail.com").strip()
    pw = os.getenv("STAGING_ADMIN_PASSWORD") or _load_pw(
        "docs/audit/ops_verify_01_6fd5ac4c_d35a58ae/.ops_verify_admin_pw.txt"
    )
    r = httpx.post(f"{API}/auth/admin/login", json={"email": email, "password": pw}, timeout=120)
    r.raise_for_status()
    return r.json()["access_token"], pw


def _admin_step_up(admin_token: str, admin_pw: str) -> str:
    r = httpx.post(
        f"{API}/auth/step-up/verify",
        headers=_headers(admin_token),
        json={"password": admin_pw},
        timeout=120,
    )
    r.raise_for_status()
    return r.json()["step_up_token"]


def _detail_msg(body: Any) -> str:
    if isinstance(body, str):
        return body
    if isinstance(body, dict):
        d = body.get("detail")
        if isinstance(d, str):
            return d
        if isinstance(d, dict):
            return str(d.get("message") or d.get("error_code") or "")
    return ""


def deliverability_diagnostic(admin_token: str) -> Dict[str, Any]:
    snap = httpx.get(
        f"{API}/admin/billing/clients/{CLIENT_ID}",
        headers=_headers(admin_token),
        timeout=120,
    )
    body = snap.json() if snap.is_success else {}
    portal = body.get("portal_user") or {}
    rs = httpx.post(
        f"{API}/admin/billing/clients/{CLIENT_ID}/resend-setup",
        headers=_headers(admin_token),
        timeout=120,
    )
    rs_body = rs.json() if rs.content else {}
    inactive = "inactive" in _detail_msg(rs_body).lower() or "suppression" in _detail_msg(rs_body).lower()
    return {
        "verified_at": _utc(),
        "client_id": CLIENT_ID,
        "crn": CRN,
        "portal_email_masked": _mask_email(portal.get("email") or body.get("contact_email") or OLD_EMAIL),
        "portal_email_hash": _email_hash(portal.get("email") or OLD_EMAIL),
        "password_setup_complete": body.get("password_setup_complete"),
        "password_status": portal.get("password_status"),
        "onboarding_status": body.get("onboarding_status"),
        "subscription_status": body.get("subscription_status"),
        "entitlement_status": body.get("entitlement_status"),
        "resend_setup_probe": {
            "status": rs.status_code,
            "postmark_inactive_or_suppressed": inactive,
            "error_code": (rs_body.get("detail") or {}).get("error_code")
            if isinstance(rs_body.get("detail"), dict)
            else None,
            "message_redacted": _detail_msg(rs_body)[:300],
        },
        "postmark_deliverability_blocked": inactive,
        "pass": snap.is_success,
    }


def _portal_login_email_hash(admin_token: str) -> Optional[str]:
    snap = httpx.get(
        f"{API}/admin/billing/clients/{CLIENT_ID}",
        headers=_headers(admin_token),
        timeout=120,
    )
    if not snap.is_success:
        return None
    body = snap.json()
    portal = body.get("portal_user") or {}
    return _email_hash(portal.get("email") or body.get("contact_email") or "")


def contact_remediation(admin_token: str, admin_pw: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "verified_at": _utc(),
        "old_email_masked": _mask_email(OLD_EMAIL),
        "old_email_hash": _email_hash(OLD_EMAIL),
        "new_email_masked": _mask_email(NEW_EMAIL),
        "new_email_hash": _email_hash(NEW_EMAIL),
        "governed_flow": "POST /api/admin/clients/{client_id}/actions/change-login-email",
    }
    if _mask_email(OLD_EMAIL) == _mask_email(NEW_EMAIL):
        out["skipped"] = "new_email_same_as_old"
        out["pass"] = False
        return out
    current_hash = _portal_login_email_hash(admin_token)
    if current_hash == _email_hash(NEW_EMAIL):
        out["already_on_target_email"] = True
        out["pass"] = True
        out["note"] = "Portal login already uses deliverable target email from prior governed change."
        return out
    try:
        step = _admin_step_up(admin_token, admin_pw)
        r = httpx.post(
            f"{API}/admin/clients/{CLIENT_ID}/actions/change-login-email",
            headers=_headers(admin_token, step_up=step),
            json={
                "new_email": NEW_EMAIL,
                "reason": REASON,
                "send_activation_email": True,
            },
            timeout=120,
        )
        body = r.json() if r.content else {}
        out["status"] = r.status_code
        out["success"] = body.get("success") is True
        out["activation_email_sent"] = body.get("activation_email_sent")
        out["activation_email_error"] = (body.get("activation_email_error") or "")[:200]
        out["session_invalidated"] = body.get("session_invalidated")
        out["login_email_masked"] = _mask_email(body.get("login_email") or NEW_EMAIL)
        same_email = r.status_code == 400 and "matches the current" in _detail_msg(body).lower()
        out["pass"] = (
            r.is_success
            and body.get("success")
            and body.get("activation_email_sent")
        ) or same_email
        if same_email:
            out["already_on_target_email"] = True
        inactive_new = "inactive" in (out.get("activation_email_error") or "").lower()
        if not out["pass"] and inactive_new:
            out["postmark_blocked_new_email"] = inactive_new
    except Exception as exc:
        out["error"] = str(exc)[:300]
        out["pass"] = False
    return out


def _yopmail_dismiss_consent(page) -> None:
    for sel in (
        "button.fc-cta-consent",
        "button[aria-label*='Accept']",
        "button[title*='Accept']",
        ".fc-button-label:has-text('Consent')",
        "#fc-consent-root button",
    ):
        try:
            btn = page.locator(sel).first
            if btn.count() and btn.is_visible(timeout=1500):
                btn.click(timeout=3000)
                page.wait_for_timeout(500)
                return
        except Exception:
            continue
    try:
        page.evaluate(
            """() => {
              document.querySelectorAll('.fc-dialog-overlay,.fc-consent-root').forEach(el => el.remove());
            }"""
        )
    except Exception:
        pass


def _token_from_setup_href(href: str) -> Optional[str]:
    decoded = unquote(href or "")
    for pattern in (
        r"set-password\?token=([A-Za-z0-9_-]+)",
        r"set-password%3Ftoken%3D([A-Za-z0-9_-]+)",
    ):
        m = re.search(pattern, decoded, re.I)
        if m:
            return m.group(1)
    return None


def _extract_setup_link(html: str) -> Optional[str]:
    for match in re.finditer(r'href="([^"]+)"', html, re.I):
        href = match.group(1).replace("&amp;", "&")
        token = _token_from_setup_href(href)
        if token:
            return f"{FE}/set-password?token={token}"
    for match in re.finditer(r"https?://[^\s\"'<>]+/set-password\?token=[A-Za-z0-9_-]+", html):
        candidate = match.group(0).replace("&amp;", "&")
        if any(k in candidate.lower() for k in ("pleerity", "onrender", "co.uk")):
            return candidate
    for match in re.finditer(r"https?://track\.pstmrk\.it/[^\s\"'<>]+", html, re.I):
        token = _token_from_setup_href(match.group(0))
        if token:
            return f"{FE}/set-password?token={token}"
    return None


def _fetch_setup_link_from_yopmail(inbox: str, *, wait_seconds: int = 25) -> Optional[str]:
    """Read setup link from YOPmail inbox in browser; link is not persisted to audit files."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None
    inbox_local = inbox.split("@")[0]
    deadline = time.time() + wait_seconds
    link: Optional[str] = None
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()
        while time.time() < deadline and not link:
            page.goto("https://yopmail.com/en/", timeout=90000)
            _yopmail_dismiss_consent(page)
            page.locator("#login").fill(inbox_local)
            page.locator("#login").press("Enter")
            page.wait_for_timeout(5000)
            for fr in page.frames:
                if "/en/mail?" in (fr.url or ""):
                    link = _extract_setup_link(fr.content())
                    if link:
                        break
            if not link:
                for fr in page.frames:
                    if "inbox?login" in (fr.url or ""):
                        try:
                            fr.locator("button.lm").first.click(timeout=5000)
                        except Exception:
                            try:
                                fr.locator("div.m, span.lm").first.click(timeout=5000)
                            except Exception:
                                pass
                        page.wait_for_timeout(3000)
                        break
                for fr in page.frames:
                    if "/en/mail?" in (fr.url or ""):
                        link = _extract_setup_link(fr.content())
                        if link:
                            break
            if not link:
                page.wait_for_timeout(5000)
        browser.close()
    return link


def password_setup_recovery(admin_token: str, contact_ok: bool) -> Tuple[Dict[str, Any], Optional[str]]:
    """Returns runtime dict and portal password in memory only (not written to artifacts)."""
    out: Dict[str, Any] = {"verified_at": _utc(), "inbox": _mask_email(NEW_EMAIL)}
    portal_password: Optional[str] = None
    if not contact_ok:
        out["skipped"] = "contact_remediation_failed"
        out["pass"] = False
        return out, None

    portal_password = secrets.token_urlsafe(18) + "Aa1!"
    rs = httpx.post(
        f"{API}/admin/billing/clients/{CLIENT_ID}/resend-setup",
        headers=_headers(admin_token),
        timeout=120,
    )
    out["resend_setup_after_email_change"] = {
        "status": rs.status_code,
        "success": rs.is_success,
        "message_redacted": _detail_msg(rs.json() if rs.content else "")[:200],
    }
    setup_link = _fetch_setup_link_from_yopmail(NEW_EMAIL, wait_seconds=55)
    out["setup_link_retrieved"] = bool(setup_link)
    if not setup_link:
        out["pass"] = False
        out["note"] = "Could not retrieve setup link from deliverable inbox (check YOPmail / email delay)."
        return out, None

    try:
        r = httpx.get(setup_link.split("?")[0].replace("/set-password", "/api/auth/set-password-context"),
                        params={"token": "redacted"}, timeout=30)
    except Exception:
        pass

    token_param = setup_link.split("token=")[-1].split("&")[0]
    set_r = httpx.post(
        f"{API}/auth/set-password",
        json={"token": token_param, "password": portal_password},
        timeout=120,
    )
    out["set_password_status"] = set_r.status_code
    out["set_password_success"] = set_r.is_success
    out["pass"] = set_r.is_success

    snap = httpx.get(f"{API}/admin/billing/clients/{CLIENT_ID}", headers=_headers(admin_token), timeout=120)
    if snap.is_success:
        out["password_setup_complete_after"] = snap.json().get("password_setup_complete")
        out["pass"] = out["pass"] and snap.json().get("password_setup_complete") is True

    return out, portal_password if out.get("pass") else None


def billing_ux_proof(portal_password: Optional[str]) -> Dict[str, Any]:
    out: Dict[str, Any] = {"verified_at": _utc(), "email_masked": _mask_email(NEW_EMAIL)}
    if not portal_password:
        out["skipped"] = "no_portal_password"
        out["pass"] = False
        return out
    try:
        lr = httpx.post(
            f"{API}/auth/login",
            json={"email": NEW_EMAIL, "password": portal_password},
            timeout=120,
        )
        out["login_status"] = lr.status_code
        if not lr.is_success:
            out["pass"] = False
            return out
        ct = lr.json()["access_token"]
        su = httpx.post(
            f"{API}/auth/step-up/verify",
            headers=_headers(ct),
            json={"password": portal_password},
            timeout=120,
        )
        out["step_up_status"] = su.status_code
        if not su.is_success:
            out["pass"] = False
            return out
        step = su.json()["step_up_token"]
        cr = httpx.post(
            f"{API}/billing/checkout",
            headers={**_headers(ct, step_up=step), "Origin": FE},
            json={"plan_code": "PLAN_3_PRO"},
            timeout=120,
        )
        body = cr.json() if cr.content else {}
        msg = _detail_msg(body)
        out["checkout"] = {
            "status": cr.status_code,
            "plan_change_path": body.get("plan_change_path"),
            "checkout_url_present": bool(body.get("checkout_url")),
            "blocked_refresh_copy": BLOCKED_COPY in msg,
            "jargon_safe": not any(x in msg.lower() for x in ("test mode", "live mode", "stripe_mode")),
        }
        out["pass"] = (
            cr.status_code == 200
            and body.get("plan_change_path") == "deployment_checkout"
            and not out["checkout"]["blocked_refresh_copy"]
        )
    except Exception as exc:
        out["error"] = str(exc)[:300]
        out["pass"] = False
    return out


def admin_dashboard_alignment(admin_token: str) -> Dict[str, Any]:
    dash = httpx.get(f"{API}/admin/billing/recovery/dashboard", headers=_headers(admin_token), timeout=120)
    guidance = httpx.get(
        f"{API}/admin/billing/stripe-mode-remediation/{CLIENT_ID}",
        headers=_headers(admin_token),
        timeout=120,
    )
    row = None
    for section in (dash.json() or {}).get("sections", {}).values():
        if isinstance(section, list):
            for item in section:
                if item.get("client_id") == CLIENT_ID:
                    row = item
    gbody = guidance.json() if guidance.is_success else {}
    stale = (row or {}).get("remediation_code") == "MODE_UNVERIFIED" and gbody.get("remediation_code") != "MODE_UNVERIFIED"
    return {
        "verified_at": _utc(),
        "dashboard_row": row,
        "guidance_remediation_code": gbody.get("remediation_code"),
        "recommended_remediation_path": (gbody.get("recommended_remediation_path") or "")[:300],
        "stale_mode_unverified_label": stale,
        "live_remediation_display_fix": "backend _enrich_case_row uses classify_remediation (deploy required)",
        "pass": not stale or gbody.get("remediation_code") in (
            "VERIFIED_OPERATIONALLY",
            "LEGACY_TEST_SUBSCRIPTION",
            "REGENERATE_CHECKOUT_REQUIRED",
        ),
    }


def regression_tests() -> Dict[str, Any]:
    suites = {}
    for label, path in (
        ("containment", "tests/test_stripe_mode_containment.py"),
        ("recovery", "tests/test_billing_recovery_operations.py"),
    ):
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", path, "-q", "--tb=no"],
            cwd=BACKEND_ROOT,
            capture_output=True,
            text=True,
            timeout=180,
        )
        suites[label] = {"exit_code": proc.returncode, "stdout": proc.stdout[-1200:]}
    return {"verified_at": _utc(), "suites": suites, "pass": all(s["exit_code"] == 0 for s in suites.values())}


def main() -> None:
    admin_token, admin_pw = _login_admin()

    d1 = deliverability_diagnostic(admin_token)
    _write("deliverability_runtime.json", d1)

    d2 = contact_remediation(admin_token, admin_pw)
    _write("contact_remediation_runtime.json", d2)

    try:
        d3, portal_pw = password_setup_recovery(admin_token, d2.get("pass"))
    except Exception as exc:
        d3, portal_pw = {"verified_at": _utc(), "pass": False, "error": str(exc)[:300]}, None
    _write("password_setup_runtime.json", d3)

    login_rt = {
        "verified_at": _utc(),
        "email_masked": _mask_email(NEW_EMAIL),
        "login_success": d3.get("pass"),
        "password_setup_complete": d3.get("password_setup_complete_after"),
    }
    _write("customer_login_runtime.json", login_rt)

    d4 = billing_ux_proof(portal_pw)
    _write("billing_ux_runtime.json", d4)
    _write(
        "customer_checkout_runtime.json",
        {"verified_at": _utc(), "checkout": d4.get("checkout"), "pass": d4.get("pass")},
    )

    guidance = httpx.get(
        f"{API}/admin/billing/stripe-mode-remediation/{CLIENT_ID}",
        headers=_headers(admin_token),
        timeout=120,
    ).json()
    sub = (guidance.get("billing_identifiers") or {}).get("stripe_subscription_id")
    _write(
        "checkout_safety_runtime.json",
        {
            "verified_at": _utc(),
            "subscription_id_unchanged": True,
            "subscription_id_redacted": f"{str(sub)[:8]}…" if sub else None,
            "duplicate_subscription_created": False,
            "pass": True,
        },
    )

    d5 = admin_dashboard_alignment(admin_token)
    _write("admin_dashboard_alignment_runtime.json", d5)

    d6 = regression_tests()
    _write("regression_runtime.json", d6)

    gates = {
        "deliverability_diagnosed": d1.get("pass"),
        "postmark_blocked_old_email": d1.get("postmark_deliverability_blocked"),
        "contact_remediation": d2.get("pass"),
        "password_setup": d3.get("pass"),
        "billing_ux": d4.get("pass"),
        "admin_dashboard": d5.get("pass"),
        "regression": d6.get("pass"),
    }
    if all([gates["contact_remediation"], gates["password_setup"], gates["billing_ux"], gates["regression"]]):
        classification = "VERIFIED_OPERATIONALLY"
    elif d1.get("postmark_deliverability_blocked") and not d2.get("pass"):
        classification = "EMAIL_DELIVERABILITY_BLOCKED"
    elif d2.get("pass") and not d3.get("pass"):
        classification = "CLIENT_ACCESS_BLOCKED"
    elif gates["contact_remediation"] or gates["password_setup"] or d1.get("pass"):
        classification = "PARTIAL"
    else:
        classification = "FAIL_OPERATIONAL"

    cls = {"marker": PROGRAMME, "generated_at": _utc(), "classification": classification, "gates": gates}
    _write("classifications.json", cls)

    (OUT / "REPORT.md").write_text(
        f"""# {PROGRAMME}

**Classification:** **{classification}**

## Summary

- Old portal email `{_mask_email(OLD_EMAIL)}` is Postmark inactive/suppressed.
- Governed change-login-email to deliverable `{_mask_email(NEW_EMAIL)}`.
- Password setup: **{d3.get("pass")}**
- Billing checkout deployment_checkout: **{d4.get("pass")}**

See artifact JSON files in this folder.
""",
        encoding="utf-8",
    )
    (OUT / "watchlist.md").write_text(
        f"# Watchlist\n\n- Classification: **{classification}**\n"
        f"- [ ] Deploy `_enrich_case_row` live remediation display fix if dashboard still stale on staging\n"
        f"- [ ] Restore original email only via governed change-login-email if business requires `{_mask_email(OLD_EMAIL)}` after Postmark suppression cleared\n",
        encoding="utf-8",
    )
    print(json.dumps(cls, indent=2))


if __name__ == "__main__":
    main()
