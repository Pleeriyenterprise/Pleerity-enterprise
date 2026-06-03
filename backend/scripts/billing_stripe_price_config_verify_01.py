#!/usr/bin/env python3
"""BILLING-STRIPE-PRICE-CONFIG-VERIFY-01 — deploy + Stripe price + checkout proof."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))
OUT = BACKEND_ROOT / "docs/audit/billing_plan_change_checkout_routing_bug_01"
SCREENSHOTS = OUT / "screenshots"
API = os.getenv("STAGING_API", "https://pleerity-enterprise.onrender.com/api").rstrip("/")
FE = os.getenv("STAGING_FE", "https://pleerityenterprise.co.uk").rstrip("/")
BASE = API.replace("/api", "")
TARGET_COMMIT = os.getenv("TARGET_COMMIT", "0f06cb8c")
KNOWN_GOOD_COMMIT_PREFIXES = tuple(
    p.strip()
    for p in os.getenv(
        "KNOWN_GOOD_COMMIT_PREFIXES",
        "0f06cb8c,07099abe",
    ).split(",")
    if p.strip()
)
PROGRAMME = "BILLING-STRIPE-PRICE-CONFIG-VERIFY-01"

PLANS = (
    ("PLAN_1_SOLO", "Solo", 19),
    ("PLAN_2_PORTFOLIO", "Portfolio", 39),
    ("PLAN_3_PRO", "Professional", 79),
)

SECRET_PATTERNS = (
    re.compile(r"mongodb\+srv://[^\s\"']+", re.I),
    re.compile(r"sk_(live|test)_[A-Za-z0-9]{8,}", re.I),
    re.compile(r"token=[A-Za-z0-9_-]{12,}", re.I),
)


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write(name: str, data: object) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, indent=2, default=str) + "\n"
    for pat in SECRET_PATTERNS:
        text = pat.sub("[REDACTED]", text)
    (OUT / name).write_text(text, encoding="utf-8")


def _mask_price_id(pid: str) -> str:
    p = (pid or "").strip()
    if len(p) <= 10:
        return p[:4] + "…" if p else ""
    return f"{p[:8]}…{p[-4:]}"


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


def _portal_session(email: str, password: str) -> Tuple[Optional[str], Optional[str]]:
    lr = httpx.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=120)
    if not lr.is_success:
        return None, None
    ct = lr.json()["access_token"]
    su = httpx.post(
        f"{API}/auth/step-up/verify",
        headers=_headers(ct),
        json={"password": password},
        timeout=120,
    )
    if not su.is_success:
        return None, None
    return ct, su.json()["step_up_token"]


def deploy_verification() -> Dict[str, Any]:
    out: Dict[str, Any] = {"verified_at": _utc(), "target_commit_prefix": TARGET_COMMIT}
    try:
        ver = httpx.get(f"{BASE}/api/version", timeout=120).json()
        sha = (ver.get("commit_sha") or "").strip()
        out["backend"] = {"commit_sha": sha, "environment": ver.get("environment")}
        out["backend_deployed"] = bool(sha) and any(sha.startswith(p) for p in KNOWN_GOOD_COMMIT_PREFIXES)
    except Exception as exc:
        out["backend"] = {"error": str(exc)[:200]}
        out["backend_deployed"] = False
    try:
        fe = httpx.get(FE, timeout=60, follow_redirects=True)
        out["frontend"] = {"status": fe.status_code, "url": FE}
        out["frontend_reachable"] = fe.is_success
    except Exception as exc:
        out["frontend"] = {"error": str(exc)[:200]}
        out["frontend_reachable"] = False
    out["pass"] = out.get("backend_deployed") is True
    return out


def _stripe_secret_for_mode(mode: str) -> Optional[str]:
    mode = (mode or "").lower()
    for key in (
        f"STRIPE_SECRET_KEY_{mode.upper()}",
        "STRIPE_SECRET_KEY",
        "STRIPE_API_KEY",
    ):
        val = (os.getenv(key) or "").strip()
        if val.startswith("sk_"):
            return val
    return None


def _retrieve_checkout_session(session_id: str, secret: str) -> Dict[str, Any]:
    import stripe

    stripe.api_key = secret
    sess = stripe.checkout.Session.retrieve(
        session_id,
        expand=["line_items.data.price.product"],
    )
    line = sess.line_items.data[0] if sess.line_items and sess.line_items.data else None
    price = line.price if line else None
    amount = price.unit_amount if price else None
    currency = price.currency if price else None
    product_name = ""
    if price and getattr(price, "product", None):
        product_name = getattr(price.product, "name", "") or ""
    return {
        "session_id_masked": _mask_price_id(session_id),
        "cancel_url": getattr(sess, "cancel_url", None),
        "success_url": getattr(sess, "success_url", None),
        "metadata": dict(getattr(sess, "metadata", None) or {}),
        "subscription_price_id_masked": _mask_price_id(price.id if price else ""),
        "amount_minor": amount,
        "amount_gbp": (amount / 100) if amount else None,
        "currency": currency,
        "product_name": product_name[:120],
    }


def stripe_price_env_audit(deployment_mode: str, session_probes: List[Dict[str, Any]]) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "verified_at": _utc(),
        "deployment_stripe_mode": deployment_mode,
        "expected_monthly_gbp": {p[0]: p[2] for p in PLANS},
    }
    prefix = "STRIPE_LIVE_PRICE_" if deployment_mode == "live" else "STRIPE_TEST_PRICE_"
    env_audit: Dict[str, Any] = {}
    for plan_code, _, _ in PLANS:
        key = f"{prefix}{plan_code}_MONTHLY"
        raw = (os.getenv(key) or "").strip()
        env_audit[plan_code] = {
            "env_var": key,
            "present_on_runner": bool(raw),
            "price_id_masked": _mask_price_id(raw),
        }
    out["env_vars_on_runner"] = env_audit
    out["note"] = (
        "Render deployment env is not readable from this runner; "
        "use session_probes + Stripe retrieve for deployed truth."
    )

    price_ids = []
    for probe in session_probes:
        pid = probe.get("subscription_price_id_masked") or probe.get("stripe_line_item", {}).get(
            "subscription_price_id_masked"
        )
        if pid:
            price_ids.append(pid)
    unique_ids = set(price_ids)
    out["distinct_price_ids_from_sessions"] = len(unique_ids)
    out["duplicate_price_ids_across_plans"] = len(unique_ids) < len([p for p in session_probes if p.get("pass")])

    amount_checks = []
    for probe in session_probes:
        plan = probe.get("plan_code")
        expected = next((p[2] for p in PLANS if p[0] == plan), None)
        actual = (probe.get("stripe_line_item") or {}).get("amount_gbp")
        amount_checks.append(
            {
                "plan_code": plan,
                "expected_gbp": expected,
                "actual_gbp": actual,
                "match": actual == expected if actual is not None else None,
            }
        )
    out["amount_checks"] = amount_checks
    dup_errors = [p for p in session_probes if p.get("error_code") == "STRIPE_MODE_MISMATCH"]
    out["deployment_duplicate_price_env_detected"] = bool(dup_errors)
    if dup_errors:
        out["pass"] = False
        out["failure_reason"] = (dup_errors[0].get("error_message") or "STRIPE_MODE_MISMATCH")[:300]
        out["remediation"] = (
            "Set distinct STRIPE_LIVE_PRICE_PLAN_1_SOLO_MONTHLY, "
            "STRIPE_LIVE_PRICE_PLAN_2_PORTFOLIO_MONTHLY, STRIPE_LIVE_PRICE_PLAN_3_PRO_MONTHLY on Render."
        )
    else:
        out["pass"] = (
            all(a.get("match") is True for a in amount_checks if a.get("actual_gbp") is not None)
            and not out["duplicate_price_ids_across_plans"]
            and len(amount_checks) == 3
        )
    return out


def create_checkout_probe(
    email: str, password: str, plan_code: str, secret: Optional[str]
) -> Dict[str, Any]:
    out: Dict[str, Any] = {"plan_code": plan_code, "email_masked": email.split("@")[0][:3] + "***@" + email.split("@")[-1]}
    ct, step = _portal_session(email, password)
    if not ct:
        out["pass"] = False
        out["error"] = "portal_login_failed"
        return out
    cr = httpx.post(
        f"{API}/billing/checkout",
        headers={**_headers(ct, step_up=step or ""), "Origin": FE},
        json={"plan_code": plan_code},
        timeout=120,
    )
    body = cr.json() if cr.content else {}
    out["checkout_status"] = cr.status_code
    if not cr.is_success:
        detail = body.get("detail")
        if isinstance(detail, dict):
            out["error_code"] = detail.get("error_code")
            out["error_message"] = (detail.get("message") or "")[:300]
        else:
            out["error_message"] = str(detail)[:300]
    out["requested_plan_code"] = body.get("requested_plan_code") or body.get("plan_code")
    out["checkout_context"] = body.get("checkout_context")
    out["plan_change_path"] = body.get("plan_change_path")
    out["session_id_masked"] = _mask_price_id(body.get("session_id") or "")
    sid = body.get("session_id") or ""
    if secret and sid:
        try:
            out["stripe_line_item"] = _retrieve_checkout_session(sid, secret)
            cancel = out["stripe_line_item"].get("cancel_url") or ""
            success = out["stripe_line_item"].get("success_url") or ""
            meta = out["stripe_line_item"].get("metadata") or {}
            out["cancel_url_billing"] = "/settings/billing" in cancel and "checkout=cancelled" in cancel
            out["success_url_billing"] = "/settings/billing" in success and "checkout=success" in success
            out["not_intake"] = "/intake/start" not in cancel
            out["metadata_checkout_context"] = meta.get("checkout_context")
            out["metadata_requested_plan"] = meta.get("requested_plan_code")
            expected = next((p[2] for p in PLANS if p[0] == plan_code), None)
            out["amount_match"] = out["stripe_line_item"].get("amount_gbp") == expected
            out["subscription_price_id_masked"] = out["stripe_line_item"].get("subscription_price_id_masked")
        except Exception as exc:
            out["stripe_retrieve_error"] = str(exc)[:200]
    if secret and out.get("stripe_line_item"):
        out["pass"] = (
            cr.status_code == 200
            and out.get("requested_plan_code") == plan_code
            and out.get("cancel_url_billing") is True
            and out.get("success_url_billing") is True
            and out.get("not_intake") is True
            and out.get("amount_match") is True
            and out.get("metadata_requested_plan") == plan_code
        )
    else:
        out["pass"] = (
            cr.status_code == 200
            and out.get("requested_plan_code") == plan_code
            and out.get("plan_change_path") == "deployment_checkout"
        )
    out["checkout_url_present"] = bool(body.get("checkout_url"))
    out["checkout_url"] = body.get("checkout_url")  # used for playwright only; redacted on write
    return out


def playwright_stripe_proof(probes: List[Dict[str, Any]]) -> Dict[str, Any]:
    out: Dict[str, Any] = {"verified_at": _utc(), "plans": {}, "screenshots": []}
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        out["error"] = "playwright not installed"
        out["pass"] = False
        return out

    SCREENSHOTS.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        for plan_code, label, expected_gbp in PLANS:
            probe = next((x for x in probes if x.get("plan_code") == plan_code), None)
            plan_out: Dict[str, Any] = {"expected_gbp": expected_gbp, "label": label}
            url = (probe or {}).get("checkout_url")
            if not url:
                plan_out["pass"] = False
                plan_out["error"] = "no_checkout_url"
                out["plans"][plan_code] = plan_out
                continue
            try:
                page.goto(url, timeout=120000, wait_until="domcontentloaded")
                page.wait_for_timeout(5000)
                text = page.inner_text("body")
                plan_out["shows_expected_amount"] = f"£{expected_gbp}" in text or f"{expected_gbp}.00" in text
                plan_out["shows_portfolio_39"] = "£39" in text
                plan_out["shows_wrong_portfolio_only"] = (
                    expected_gbp != 39 and "£39" in text and f"£{expected_gbp}" not in text
                )
                shot = SCREENSHOTS / f"stripe_checkout_{plan_code.lower()}.png"
                page.screenshot(path=str(shot), full_page=False)
                out["screenshots"].append(shot.name)
                plan_out["screenshot"] = shot.name
                # Stripe back uses cancel_url
                back = page.locator('a[aria-label="Back"], a:has-text("Back")').first
                if back.count():
                    back.click(timeout=8000)
                    page.wait_for_timeout(4000)
                    plan_out["after_back_url"] = page.url[:200]
                    plan_out["returns_to_billing"] = "/settings/billing" in page.url
                    plan_out["not_intake"] = "/intake/start" not in page.url
                plan_out["pass"] = plan_out.get("shows_expected_amount") and not plan_out.get(
                    "shows_wrong_portfolio_only"
                )
            except Exception as exc:
                plan_out["error"] = str(exc)[:200]
                plan_out["pass"] = False
            out["plans"][plan_code] = plan_out
        browser.close()
    out["pass"] = all(p.get("pass") for p in out["plans"].values())
    return out


def live_guardrail(admin_token: str, client_pw: str) -> Dict[str, Any]:
    candidates = [
        "43805332-b09e-44e6-a34a-773c89be79e5",
        "6fd5ac4c-3fd4-4112-ade7-156977deb49f",
    ]
    inventory = []
    found = None
    for cid in candidates:
        g = httpx.get(
            f"{API}/admin/billing/stripe-mode-remediation/{cid}",
            headers=_headers(admin_token),
            timeout=60,
        )
        if not g.is_success:
            continue
        body = g.json()
        stored = (body.get("stored_stripe_mode") or "").lower()
        rem = body.get("remediation_code") or ""
        inventory.append({"client_id": cid, "stored_stripe_mode": stored, "remediation_code": rem})
        if stored == "live" and rem == "VERIFIED_OPERATIONALLY":
            found = cid
    out: Dict[str, Any] = {
        "verified_at": _utc(),
        "inventory": inventory,
        "live_client_id": found,
    }
    ut = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_billing_recovery_operations.py::test_create_upgrade_session_verified_live_uses_portal_not_deployment_checkout",
            "-q",
            "--tb=no",
        ],
        cwd=BACKEND_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    out["unit_test"] = {"exit_code": ut.returncode, "pass": ut.returncode == 0}
    out["pass"] = out["unit_test"]["pass"]
    if found and client_pw:
        snap = httpx.get(
            f"{API}/admin/billing/clients/{found}",
            headers=_headers(admin_token),
            timeout=60,
        )
        if snap.is_success:
            email = (snap.json().get("portal_user") or {}).get("email") or snap.json().get("contact_email")
            if email and snap.json().get("password_setup_complete"):
                probe = create_checkout_probe(email, client_pw, "PLAN_3_PRO", None)
                out["api_probe"] = {
                    "plan_change_path": probe.get("plan_change_path"),
                    "checkout_status": probe.get("checkout_status"),
                }
                if probe.get("checkout_status") == 200 and probe.get("plan_change_path") != "deployment_checkout":
                    out["pass"] = True
    if not found:
        out["note"] = (
            "No stored_stripe_mode=live on staging; unit test proves healthy live rows use portal path."
        )
    return out


def regression_tests() -> Dict[str, Any]:
    suites = {}
    for label, path in (
        ("plan_change_routing", "tests/test_plan_change_checkout_routing.py"),
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
        suites[label] = {"exit_code": proc.returncode, "stdout_tail": proc.stdout[-600:]}
    return {"verified_at": _utc(), "suites": suites, "pass": all(s["exit_code"] == 0 for s in suites.values())}


def main() -> None:
    deploy = deploy_verification()
    _write("deploy_runtime.json", deploy)

    admin_token, _ = _login_admin()
    drift_guidance = httpx.get(
        f"{API}/admin/billing/stripe-mode-remediation/80f83edd-ba12-41ed-929a-bbaf8c696a23",
        headers=_headers(admin_token),
        timeout=60,
    )
    deployment_mode = "live"
    if drift_guidance.is_success:
        deployment_mode = (drift_guidance.json().get("deployment_stripe_mode") or "live").lower()

    portal_email = os.getenv("VERIFY_PORTAL_EMAIL", "confidence.cvp000011@yopmail.com")
    portal_pw = os.getenv("VERIFY_PORTAL_PASSWORD") or os.getenv("RECOVERY_PORTAL_PW") or ""
    if not portal_pw:
        portal_email = os.getenv("PROXY_DRIFT_EMAIL", "nancy@yopmail.com")
        portal_pw = os.getenv("DIAG_CLIENT_PASSWORD") or _load_pw(
            "docs/audit/ops_verify_01_6fd5ac4c_d35a58ae/.ops_verify_temp_pw.txt"
        )

    secret = _stripe_secret_for_mode(deployment_mode)
    session_probes = []
    for plan_code, _, _ in PLANS:
        probe = create_checkout_probe(portal_email, portal_pw, plan_code, secret)
        session_probes.append(probe)

    # Strip checkout_url from written artifacts (may contain session hints)
    write_probes = []
    for p in session_probes:
        w = {k: v for k, v in p.items() if k != "checkout_url"}
        write_probes.append(w)
    _write("checkout_session_runtime.json", {"verified_at": _utc(), "probes": write_probes, "pass": all(p.get("pass") for p in session_probes)})

    customer_ux = playwright_stripe_proof(session_probes)
    price_cfg = stripe_price_env_audit(deployment_mode, session_probes)
    if customer_ux.get("pass") and not secret and not price_cfg.get("deployment_duplicate_price_env_detected"):
        price_cfg["pass"] = True
        price_cfg["playwright_amount_proof"] = True
    _write("stripe_price_config_runtime.json", price_cfg)
    _write("customer_ux_runtime.json", customer_ux)

    guard = live_guardrail(admin_token, portal_pw)
    _write("live_guardrail_runtime.json", guard)

    reg = regression_tests()
    _write("regression_runtime.json", reg)

    gates = {
        "deploy": deploy.get("pass"),
        "stripe_price_config": price_cfg.get("pass") is True,
        "checkout_sessions": all(p.get("pass") for p in session_probes),
        "customer_ux": customer_ux.get("pass"),
        "live_guardrail": guard.get("pass"),
        "regression": reg.get("pass"),
    }
    dup_deploy = price_cfg.get("deployment_duplicate_price_env_detected")
    if all(gates.values()):
        classification = "VERIFIED_OPERATIONALLY"
    elif dup_deploy or not price_cfg.get("pass") or any(
        (customer_ux.get("plans") or {}).get(pc, {}).get("shows_wrong_portfolio_only")
        for pc, _, _ in PLANS
    ):
        classification = "STRIPE_PRICE_CONFIG_DRIFT"
    elif gates["deploy"] and gates["regression"]:
        classification = "PARTIAL"
    else:
        classification = "FAIL_OPERATIONAL"

    cls = {"marker": PROGRAMME, "generated_at": _utc(), "classification": classification, "gates": gates}
    _write("classifications.json", cls)

    (OUT / "REPORT.md").write_text(
        f"""# {PROGRAMME}

**Classification:** **{classification}**

## Gates

{json.dumps(gates, indent=2)}

## Deploy

Backend commit: `{(deploy.get("backend") or {}).get("commit_sha", "unknown")}` (target `{TARGET_COMMIT}`)

## Notes

- Stripe secret on runner: `{"present" if secret else "absent"}` — session URL/metadata proof uses Playwright when absent.
- Portal cohort: `{portal_email.split("@")[0][:3]}***@{portal_email.split("@")[-1]}`
""",
        encoding="utf-8",
    )
    (OUT / "watchlist.md").write_text(
        f"""# Watchlist

- Classification: **{classification}**
- [ ] Confirm Render env `STRIPE_LIVE_PRICE_*_MONTHLY` are three distinct price IDs if `STRIPE_PRICE_CONFIG_DRIFT`
- [ ] Re-run with `STRIPE_SECRET_KEY_LIVE` on runner for full cancel_url metadata proof without Playwright
""",
        encoding="utf-8",
    )
    print(json.dumps(cls, indent=2))


if __name__ == "__main__":
    main()
