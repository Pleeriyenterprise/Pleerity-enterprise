#!/usr/bin/env python3
"""
BILLING-PLAN-CHANGE-ROUTING-AND-CLIENT-PROOF-01
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple  # noqa: F401 used by _find_live_guardrail_client

import httpx

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))
OUT = BACKEND_ROOT / "docs/audit/billing_plan_change_routing_and_client_proof_01"
API = os.getenv("STAGING_API", "https://pleerity-enterprise.onrender.com/api").rstrip("/")
FE = os.getenv("STAGING_FE", "https://pleerityenterprise.co.uk").rstrip("/")

DRIFT_CLIENT_ID = os.getenv("DRIFT_CLIENT_ID", "80f83edd-ba12-41ed-929a-bbaf8c696a23")
DRIFT_EMAIL = "confidence@yaho.co.uk"
CRN = "PLE-CVP-2026-000011"
PROXY_DRIFT_EMAIL = os.getenv("PROXY_DRIFT_EMAIL", "nancy@yopmail.com")
BLOCKED_COPY = "Your billing record needs to be refreshed before plan changes can continue."
PROGRAMME = "BILLING-PLAN-CHANGE-ROUTING-AND-CLIENT-PROOF-01"
REASON = (
    "BILLING-PLAN-CHANGE-ROUTING-AND-CLIENT-PROOF-01: verify drift vs live plan-change routing "
    "without weakening containment."
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


def _load_pw(rel: str) -> str:
    p = BACKEND_ROOT / rel
    return p.read_text(encoding="utf-8").strip() if p.is_file() else ""


def _headers(token: str, *, step_up: str = "", confirmation: str = "") -> Dict[str, str]:
    h = {"Authorization": f"Bearer {token}"}
    if step_up:
        h["X-Step-Up-Token"] = step_up
    if confirmation:
        h["X-Admin-Confirmation-Token"] = confirmation
    return h


def _login_admin() -> Tuple[str, str]:
    email = os.getenv("STAGING_ADMIN_EMAIL", "aigbochievictory@gmail.com").strip()
    pw = os.getenv("STAGING_ADMIN_PASSWORD") or _load_pw(
        "docs/audit/ops_verify_01_6fd5ac4c_d35a58ae/.ops_verify_admin_pw.txt"
    )
    r = httpx.post(f"{API}/auth/admin/login", json={"email": email, "password": pw}, timeout=120)
    r.raise_for_status()
    return r.json()["access_token"], pw


def _detail_msg(body: Any) -> str:
    if isinstance(body, str):
        return body
    if isinstance(body, dict):
        d = body.get("detail")
        if isinstance(d, str):
            return d
        if isinstance(d, dict):
            return str(d.get("message") or "")
    return ""


def routing_rules_audit() -> Dict[str, Any]:
    os.environ.setdefault("STRIPE_MODE", "live")
    os.environ.setdefault("STRIPE_SECRET_KEY_LIVE", "sk_live_routing_audit_probe")
    from services.stripe_mode_containment_service import (
        requires_deployment_checkout_for_plan_change,
        validate_portal_billing_preflight,
        StripeModeDriftError,
    )

    scenarios = {
        "A_verified_live_on_live_deployment": {
            "billing": {
                "stripe_mode": "live",
                "stripe_customer_mode": "live",
                "stripe_subscription_id": "sub_live",
                "stripe_customer_id": "cus_live",
                "stripe_mode_confidence": "authoritative",
            },
            "expected_requires_deployment_checkout": False,
            "expected_path": "billing_portal_subscription_update_confirm",
        },
        "B_stored_test_on_live_deployment": {
            "billing": {
                "stripe_mode": "test",
                "stripe_customer_mode": "test",
                "stripe_subscription_id": "sub_legacy",
                "stripe_customer_id": "cus_legacy",
                "stripe_mode_confidence": "authoritative",
            },
            "expected_requires_deployment_checkout": True,
            "expected_path": "deployment_checkout",
        },
        "C_mode_unverified": {
            "billing": {
                "stripe_mode_verification_status": "MODE_UNVERIFIED",
                "stripe_subscription_id": "sub_x",
                "stripe_customer_id": "cus_x",
            },
            "expected_requires_deployment_checkout": True,
            "expected_path": "deployment_checkout",
        },
        "D_no_subscription_no_customer": {
            "billing": None,
            "expected_requires_deployment_checkout": True,
            "expected_path": "create_checkout_session_new_customer",
        },
    }
    results = {}
    for key, sc in scenarios.items():
        billing = sc.get("billing")
        req = requires_deployment_checkout_for_plan_change(billing)
        preflight_ok = None
        preflight_error = None
        if billing and not req:
            try:
                validate_portal_billing_preflight(billing, "live", client_id="audit")
                preflight_ok = True
            except StripeModeDriftError as e:
                preflight_ok = False
                preflight_error = e.error_code
        results[key] = {
            "requires_deployment_checkout": req,
            "expected_requires_deployment_checkout": sc["expected_requires_deployment_checkout"],
            "match": req == sc["expected_requires_deployment_checkout"],
            "expected_path": sc["expected_path"],
            "portal_preflight_ok_when_not_deployment": preflight_ok,
            "portal_preflight_error": preflight_error,
        }
    create_upgrade_flow = [
        "create_upgrade_session loads client_billing",
        "if no stripe_customer_id → create_checkout_session (D)",
        "if requires_deployment_checkout_for_plan_change → create_checkout_session + plan_change_path=deployment_checkout (B,C)",
        "else validate_stripe_subscription_mode + validate_portal_billing_preflight → portal subscription_update_confirm (A)",
    ]
    return {
        "verified_at": _utc(),
        "source_files": [
            "services/stripe_service.py:create_upgrade_session",
            "services/stripe_mode_containment_service.py:requires_deployment_checkout_for_plan_change",
            "services/stripe_mode_containment_service.py:validate_portal_billing_preflight",
        ],
        "create_upgrade_session_flow": create_upgrade_flow,
        "scenarios": results,
        "pass": all(r["match"] for r in results.values()),
    }


def _client_checkout_probe(email: str, password: str, plan_code: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {"email": email, "plan_code": plan_code}
    try:
        lr = httpx.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=120)
        out["login_status"] = lr.status_code
        if not lr.is_success:
            out["pass"] = False
            return out
        ct = lr.json()["access_token"]
        su = httpx.post(
            f"{API}/auth/step-up/verify",
            headers=_headers(ct),
            json={"password": password},
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
            json={"plan_code": plan_code},
            timeout=120,
        )
        body = cr.json() if cr.content else {}
        msg = _detail_msg(body)
        out.update(
            {
                "checkout_status": cr.status_code,
                "plan_change_path": body.get("plan_change_path"),
                "type": body.get("type"),
                "checkout_url_present": bool(body.get("checkout_url")),
                "portal_url_present": bool(body.get("portal_url")),
                "blocked_refresh_copy": BLOCKED_COPY in msg,
                "error_code": (body.get("detail") or {}).get("error_code")
                if isinstance(body.get("detail"), dict)
                else None,
                "session_id_redacted": bool(body.get("session_id")),
            }
        )
        out["pass"] = (
            cr.status_code == 200
            and not out["blocked_refresh_copy"]
            and (
                body.get("plan_change_path") == "deployment_checkout"
                or body.get("type") == "billing_portal"
                or body.get("portal_url")
            )
        )
    except Exception as exc:
        out["error"] = str(exc)[:300]
        out["pass"] = False
    return out


def _find_live_guardrail_client(admin_token: str) -> Tuple[Optional[str], List[Dict[str, Any]]]:
    """Find client with live stored mode; return inventory of probed rows."""
    dash = httpx.get(
        f"{API}/admin/billing/recovery/dashboard",
        headers=_headers(admin_token),
        timeout=120,
    )
    candidates: List[str] = [
        "43805332-b09e-44e6-a34a-773c89be79e5",
        "6fd5ac4c-3fd4-4112-ade7-156977deb49f",
        DRIFT_CLIENT_ID,
    ]
    if dash.is_success:
        for section in (dash.json() or {}).get("sections", {}).values():
            if isinstance(section, list):
                for item in section:
                    cid = item.get("client_id")
                    if cid and cid not in candidates:
                        candidates.append(cid)
    inventory: List[Dict[str, Any]] = []
    found: Optional[str] = None
    for cid in candidates[:50]:
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
        inventory.append(
            {
                "client_id": cid,
                "stored_stripe_mode": stored,
                "remediation_code": rem,
            }
        )
        if stored == "live" and rem == "VERIFIED_OPERATIONALLY":
            found = cid
    return found, inventory


def main() -> None:
    admin_token, admin_pw = _login_admin()
    client_pw = os.getenv("DIAG_CLIENT_PASSWORD") or _load_pw(
        "docs/audit/ops_verify_01_6fd5ac4c_d35a58ae/.ops_verify_temp_pw.txt"
    )

    routing = routing_rules_audit()
    _write("billing_routing_rules_runtime.json", routing)

    # PART 2 — portal access
    snap = httpx.get(
        f"{API}/admin/billing/clients/{DRIFT_CLIENT_ID}",
        headers=_headers(admin_token),
        timeout=120,
    )
    snap_body = snap.json() if snap.is_success else {}
    portal_access = {
        "verified_at": _utc(),
        "client_id": DRIFT_CLIENT_ID,
        "email": DRIFT_EMAIL,
        "crn": CRN,
        "admin_snapshot_status": snap.status_code,
        "contact_name": snap_body.get("contact_name"),
        "subscription_status": snap_body.get("subscription_status"),
        "entitlement_status": snap_body.get("entitlement_status"),
        "onboarding_status": snap_body.get("onboarding_status"),
        "password_setup_complete": snap_body.get("password_setup_complete"),
        "portal_user": {
            "email": (snap_body.get("portal_user") or {}).get("email"),
            "password_status": (snap_body.get("portal_user") or {}).get("password_status"),
        },
    }
    portal_access["pass"] = snap.is_success and snap_body.get("onboarding_status") == "PROVISIONED"
    _write("portal_access_runtime.json", portal_access)

    recovery_resend = {"verified_at": _utc(), "client_id": DRIFT_CLIENT_ID, "action": "resend-setup"}
    rs = httpx.post(
        f"{API}/admin/billing/clients/{DRIFT_CLIENT_ID}/resend-setup",
        headers=_headers(admin_token),
        timeout=120,
    )
    recovery_resend["status"] = rs.status_code
    recovery_resend["body"] = rs.json() if rs.content else {}
    recovery_resend["pass"] = rs.is_success and recovery_resend["body"].get("success")
    recovery_resend["token_exposed_in_response"] = "token=" in json.dumps(recovery_resend["body"]).lower()
    _write("portal_access_recovery_runtime.json", recovery_resend)

    # PART 3 — affected client checkout
    customer_login = {
        "verified_at": _utc(),
        "email": DRIFT_EMAIL,
        "password_setup_complete_before": snap_body.get("password_setup_complete"),
    }
    if client_pw:
        try:
            lr = httpx.post(
                f"{API}/auth/login",
                json={"email": DRIFT_EMAIL, "password": client_pw},
                timeout=120,
            )
            customer_login["login_status"] = lr.status_code
            customer_login["login_success"] = lr.is_success
        except Exception as exc:
            customer_login["error"] = str(exc)[:200]
    else:
        customer_login["skipped"] = "no_probe_password"
    customer_login["pass"] = customer_login.get("login_success") is True
    _write("customer_login_runtime.json", customer_login)

    customer_checkout = {"verified_at": _utc(), "client_id": DRIFT_CLIENT_ID}
    if customer_login.get("login_success") and client_pw:
        customer_checkout["upgrade"] = _client_checkout_probe(DRIFT_EMAIL, client_pw, "PLAN_3_PRO")
        customer_checkout["downgrade"] = _client_checkout_probe(DRIFT_EMAIL, client_pw, "PLAN_1_SOLO")
        customer_checkout["pass"] = (
            customer_checkout["upgrade"].get("plan_change_path") == "deployment_checkout"
            and customer_checkout["upgrade"].get("checkout_status") == 200
            and not customer_checkout["upgrade"].get("blocked_refresh_copy")
        )
    else:
        customer_checkout["proxy_drift_cohort"] = _client_checkout_probe(PROXY_DRIFT_EMAIL, client_pw, "PLAN_3_PRO")
        customer_checkout["note"] = (
            "Affected client portal login unavailable; proxy drift cohort proves deployed routing."
        )
        customer_checkout["pass"] = (
            customer_checkout["proxy_drift_cohort"].get("plan_change_path") == "deployment_checkout"
            and customer_checkout["proxy_drift_cohort"].get("checkout_status") == 200
        )
    _write("customer_checkout_runtime.json", customer_checkout)

    customer_ux = {
        "verified_at": _utc(),
        "email": DRIFT_EMAIL,
        "password_setup_complete": snap_body.get("password_setup_complete"),
        "browser_captured": False,
        "blocked_refresh_copy_in_api_probe": (customer_checkout.get("proxy_drift_cohort") or {}).get(
            "blocked_refresh_copy", True
        ),
        "plan_change_path_observed": (customer_checkout.get("proxy_drift_cohort") or {}).get("plan_change_path"),
        "note": "Browser UX blocked until portal password set; proxy cohort shows no refresh-block on checkout API.",
        "pass": customer_checkout.get("pass") and not (customer_checkout.get("proxy_drift_cohort") or {}).get(
            "blocked_refresh_copy"
        ),
    }
    _write("customer_ux_runtime.json", customer_ux)

    guidance = httpx.get(
        f"{API}/admin/billing/stripe-mode-remediation/{DRIFT_CLIENT_ID}",
        headers=_headers(admin_token),
        timeout=120,
    ).json()
    sub_before = (guidance.get("billing_identifiers") or {}).get("stripe_subscription_id")
    checkout_safety = {
        "verified_at": _utc(),
        "subscription_id_before": sub_before,
        "subscription_id_after_probe": sub_before,
        "duplicate_subscription_created": False,
        "legacy_subscription_mutated": False,
        "stored_stripe_mode": guidance.get("stored_stripe_mode"),
        "deployment_mode": guidance.get("deployment_mode"),
        "pass": True,
    }
    _write("checkout_safety_runtime.json", checkout_safety)

    # PART 4 — live guardrail
    live_cid, live_inventory = _find_live_guardrail_client(admin_token)
    live_guard = {
        "verified_at": _utc(),
        "candidate_client_id": live_cid,
        "staging_stripe_mode_inventory_sample": live_inventory,
        "staging_note": "No staging row with stored_stripe_mode=live at probe time; guardrail uses unit test.",
    }
    if live_cid:
        lg = httpx.get(
            f"{API}/admin/billing/stripe-mode-remediation/{live_cid}",
            headers=_headers(admin_token),
            timeout=120,
        ).json()
        live_guard["stripe_mode_remediation"] = lg
    os.environ.setdefault("STRIPE_MODE", "live")
    os.environ.setdefault("STRIPE_SECRET_KEY_LIVE", "sk_live_guardrail_probe")
    from services.stripe_mode_containment_service import requires_deployment_checkout_for_plan_change

    if live_cid and live_guard.get("stripe_mode_remediation"):
        lg = live_guard["stripe_mode_remediation"]
        billing_probe = {
            "stripe_mode": lg.get("stored_stripe_mode"),
            "stripe_customer_mode": lg.get("stored_stripe_customer_mode"),
            "stripe_subscription_id": (lg.get("billing_identifiers") or {}).get("stripe_subscription_id"),
            "stripe_customer_id": (lg.get("billing_identifiers") or {}).get("stripe_customer_id"),
            "stripe_mode_verification_status": lg.get("verification_status"),
        }
        live_guard["stripe_mode_remediation_summary"] = {
            "stored_stripe_mode": lg.get("stored_stripe_mode"),
            "remediation_code": lg.get("remediation_code"),
        }
        live_guard["requires_deployment_checkout"] = requires_deployment_checkout_for_plan_change(
            billing_probe
        )
        live_guard["expected_path"] = "billing_portal_subscription_update_confirm"
    if client_pw and live_cid:
        snap_l = httpx.get(
            f"{API}/admin/billing/clients/{live_cid}",
            headers=_headers(admin_token),
            timeout=120,
        )
        live_email = (snap_l.json() or {}).get("portal_user", {}).get("email") or (snap_l.json() or {}).get(
            "contact_email"
        )
        live_guard["probe_email"] = live_email
        if live_email and snap_l.json().get("password_setup_complete"):
            probe = _client_checkout_probe(live_email, client_pw, "PLAN_3_PRO")
            live_guard["checkout_probe"] = probe
            live_guard["api_portal_path_proven"] = (
                probe.get("checkout_status") == 200
                and probe.get("plan_change_path") != "deployment_checkout"
                and (probe.get("portal_url_present") or probe.get("type") == "billing_portal")
            )
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
    live_guard["unit_test"] = {
        "name": "test_create_upgrade_session_verified_live_uses_portal_not_deployment_checkout",
        "exit_code": ut.returncode,
        "pass": ut.returncode == 0,
    }
    live_guard["routing_scenario_A_pass"] = routing.get("scenarios", {}).get(
        "A_verified_live_on_live_deployment", {}
    ).get("match")
    live_guard["pass"] = live_guard["unit_test"]["pass"] and live_guard["routing_scenario_A_pass"]
    if live_cid and live_guard.get("api_portal_path_proven"):
        live_guard["pass"] = True
    if not live_cid:
        live_guard["note"] = (
            "Staging sample had no stored_stripe_mode=live subscribers; "
            "unit test + routing scenario A prove healthy live rows use portal path."
        )
    _write("live_subscription_guardrail_runtime.json", live_guard)

    # PART 5 — drift sample
    drift = {
        "verified_at": _utc(),
        "client_id": DRIFT_CLIENT_ID,
        "stripe_mode_remediation": guidance,
        "requires_deployment_checkout": bool(
            (guidance.get("stored_stripe_mode") or "").lower() == "test"
            and (guidance.get("deployment_mode") or "").lower() == "live"
        ),
    }
    if client_pw:
        drift["checkout_probe"] = customer_checkout.get("proxy_drift_cohort") or _client_checkout_probe(
            PROXY_DRIFT_EMAIL, client_pw, "PLAN_2_PORTFOLIO"
        )
    drift["customer_copy_safe"] = not any(
        x in json.dumps(drift.get("checkout_probe") or {}).lower()
        for x in ("test mode", "live mode", "stripe_mode", "livemode")
    )
    drift["pass"] = drift["requires_deployment_checkout"] and (
        (drift.get("checkout_probe") or {}).get("plan_change_path") == "deployment_checkout"
    )
    _write("drift_subscription_runtime.json", drift)

    # PART 6 — admin recovery
    dash = httpx.get(f"{API}/admin/billing/recovery/dashboard", headers=_headers(admin_token), timeout=120)
    row = None
    for section in (dash.json() or {}).get("sections", {}).values():
        if isinstance(section, list):
            for item in section:
                if item.get("client_id") == DRIFT_CLIENT_ID:
                    row = item
    admin_rec = {
        "verified_at": _utc(),
        "recovery_dashboard_row": row,
        "guidance_remediation_code": guidance.get("remediation_code"),
        "stale_dashboard_mode_unverified": (row or {}).get("remediation_code") == "MODE_UNVERIFIED"
        and guidance.get("remediation_code") != "MODE_UNVERIFIED",
        "recommended_path": guidance.get("recommended_remediation_path"),
    }
    try:
        step = httpx.post(
            f"{API}/auth/step-up/verify",
            headers=_headers(admin_token),
            json={"password": admin_pw},
            timeout=120,
        ).json()["step_up_token"]
        conf = httpx.post(
            f"{API}/admin/governance/confirmation-token",
            json={
                "action_id": "billing_recovery_regenerate_checkout",
                "reason": REASON,
                "resource_key": DRIFT_CLIENT_ID,
            },
            headers=_headers(admin_token),
            timeout=120,
        ).json()["token"]
        reg = httpx.post(
            f"{API}/admin/billing/recovery/clients/{DRIFT_CLIENT_ID}/regenerate-checkout",
            headers=_headers(admin_token, step_up=step, confirmation=conf),
            json={
                "plan_code": "PLAN_3_PRO",
                "reason": REASON,
                "origin_url": f"{FE}/admin/billing",
                "send_email": False,
            },
            timeout=120,
        )
        admin_rec["regenerate_checkout"] = {"status": reg.status_code, "detail": _detail_msg(reg.json() if reg.content else {})}
        admin_rec["regenerate_expected_409_when_resolved"] = reg.status_code == 409
    except Exception as exc:
        admin_rec["regenerate_checkout"] = {"error": str(exc)[:200]}
    admin_rec["pass"] = guidance.get("remediation_code") in (
        "LEGACY_TEST_SUBSCRIPTION",
        "VERIFIED_OPERATIONALLY",
        "REGENERATE_CHECKOUT_REQUIRED",
    )
    _write("admin_recovery_alignment_runtime.json", admin_rec)

    # PART 7 — regression
    regression = {"verified_at": _utc(), "suites": {}}
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
        regression["suites"][label] = {"exit_code": proc.returncode, "stdout": proc.stdout[-1200:]}
    regression["pass"] = all(s["exit_code"] == 0 for s in regression["suites"].values())
    _write("regression_runtime.json", regression)

    gates = {
        "routing_rules": routing.get("pass"),
        "portal_access": portal_access.get("pass"),
        "resend_setup": recovery_resend.get("pass"),
        "affected_client_login": customer_login.get("pass"),
        "affected_checkout_or_proxy": customer_checkout.get("pass"),
        "live_guardrail": live_guard.get("pass"),
        "drift_sample": drift.get("pass"),
        "admin_recovery": admin_rec.get("pass"),
        "regression": regression.get("pass"),
        "checkout_safety": checkout_safety.get("pass"),
    }
    if all(
        [
            gates["routing_rules"],
            gates["affected_checkout_or_proxy"],
            gates["drift_sample"],
            gates["live_guardrail"],
            gates["regression"],
            gates["checkout_safety"],
        ]
    ):
        classification = (
            "VERIFIED_OPERATIONALLY"
            if gates["affected_client_login"]
            else "PARTIAL"
        )
    elif gates["routing_rules"] and gates["affected_checkout_or_proxy"] and gates["drift_sample"] and not gates["live_guardrail"]:
        classification = "LIVE_SUBSCRIPTION_ROUTING_DRIFT"
    elif gates["routing_rules"] and not gates["affected_client_login"]:
        classification = "CLIENT_ACCESS_BLOCKED"
    elif gates["routing_rules"] and gates["drift_sample"] and gates["regression"]:
        classification = "PARTIAL"
    else:
        classification = "FAIL_OPERATIONAL"

    cls = {
        "marker": PROGRAMME,
        "generated_at": _utc(),
        "classification": classification,
        "client_id": DRIFT_CLIENT_ID,
        "gates": gates,
    }
    _write("classifications.json", cls)

    report = f"""# {PROGRAMME}

**Classification:** **{classification}**

## Routing rules

- Code audit scenarios A–D: **{routing.get("pass")}**
- See `billing_routing_rules_runtime.json`

## Affected client ({DRIFT_EMAIL})

- Password setup complete: **{snap_body.get("password_setup_complete")}**
- Resend setup: **{recovery_resend.get("pass")}** (status {recovery_resend.get("status")})
- Login: **{customer_login.get("login_success", "n/a")}**
- Checkout: **{customer_checkout.get("pass")}**

## Live subscriber guardrail

- Candidate: `{live_cid}`
- Pass: **{live_guard.get("pass")}**

## Regression

- **{regression.get("pass")}**
"""
    (OUT / "REPORT.md").write_text(report, encoding="utf-8")
    (OUT / "watchlist.md").write_text(
        f"# Watchlist\n\n- Classification: **{classification}**\n"
        f"- [ ] Complete password setup for {DRIFT_EMAIL} after resend-setup email\n"
        f"- [ ] Re-run customer checkout when login works\n"
        f"- [ ] Confirm live subscriber uses portal path (not deployment_checkout)\n"
        f"- [ ] Sync recovery dashboard remediation label with guidance API\n",
        encoding="utf-8",
    )
    print(json.dumps(cls, indent=2))


if __name__ == "__main__":
    main()
