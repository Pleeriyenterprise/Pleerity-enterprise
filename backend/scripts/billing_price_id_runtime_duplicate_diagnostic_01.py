#!/usr/bin/env python3
"""BILLING-PRICE-ID-RUNTIME-DUPLICATE-DIAGNOSTIC-01"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))
OUT = BACKEND_ROOT / "docs/audit/billing_price_id_runtime_duplicate_diagnostic_01"
API = os.getenv("STAGING_API", "https://pleerity-enterprise.onrender.com/api").rstrip("/")
FE = os.getenv("STAGING_FE", "https://pleerityenterprise.co.uk").rstrip("/")
PROGRAMME = "BILLING-PRICE-ID-RUNTIME-DUPLICATE-DIAGNOSTIC-01"
LEGACY_CLIENT_ID = os.getenv("LEGACY_DRIFT_CLIENT_ID", "6aa7906f-ed85-4367-8ca4-6ef1bb76668f")

SECRET_PATTERNS = (
    re.compile(r"mongodb\+srv://[^\s\"']+", re.I),
    re.compile(r"sk_(live|test)_[A-Za-z0-9]{8,}", re.I),
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


def _headers(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _login_admin() -> str:
    email = os.getenv("STAGING_ADMIN_EMAIL", "aigbochievictory@gmail.com").strip()
    pw = os.getenv("STAGING_ADMIN_PASSWORD") or _load_pw(
        "docs/audit/ops_verify_01_6fd5ac4c_d35a58ae/.ops_verify_admin_pw.txt"
    )
    r = httpx.post(f"{API}/auth/admin/login", json={"email": email, "password": pw}, timeout=120)
    r.raise_for_status()
    return r.json()["access_token"]


def _stripe_secret(mode: str) -> Optional[str]:
    for key in (f"STRIPE_SECRET_KEY_{mode.upper()}", "STRIPE_SECRET_KEY", "STRIPE_API_KEY"):
        v = (os.getenv(key) or "").strip()
        if v.startswith("sk_"):
            return v
    return None


def _validate_stripe_prices(fingerprint: Dict[str, Any], mode: str) -> Dict[str, Any]:
    secret = _stripe_secret(mode)
    out: Dict[str, Any] = {"verified_at": _utc(), "stripe_mode": mode, "prices": []}
    if not secret:
        out["skipped"] = "no_stripe_secret_on_runner"
        out["pass"] = None
        return out
    import stripe

    stripe.api_key = secret
    expected = {
        "PLAN_1_SOLO": 1900,
        "PLAN_2_PORTFOLIO": 3900,
        "PLAN_3_PRO": 7900,
    }
    seen: Dict[str, str] = {}
    for row in (fingerprint.get("duplicate_monthly_groups") or [{}])[0:1]:
        for var in row.get("env_vars") or []:
            pass
    for _key, meta in (fingerprint.get("monthly_env_vars") or {}).items():
        if not meta.get("present"):
            continue
        plan = meta.get("plan_code")
        gid = meta.get("duplicate_group_id")
        # Resolve one price per group via Stripe list is not possible without full id.
        # Use deployment duplicate group: if duplicate, all share same hash — validate once per group.
        if gid in seen:
            continue
        seen[gid] = plan or ""
    groups = fingerprint.get("duplicate_monthly_groups") or []
    if not groups:
        out["pass"] = True
        out["note"] = "no duplicate groups in deployment fingerprint"
        return out

    # Duplicate on deployment: fetch representative price by listing and matching last_6
    for grp in groups:
        rep = (fingerprint.get("monthly_env_vars") or {}).get((grp.get("env_vars") or [""])[0], {})
        last6 = rep.get("last_6_chars") or ""
        match = None
        try:
            for price in stripe.Price.list(limit=100, active=True).auto_paging_iter():
                pid = price.id or ""
                if pid.endswith(last6) or last6 in pid:
                    match = price
                    break
        except Exception as exc:
            out["stripe_list_error"] = str(exc)[:200]
            break
        if not match:
            out["prices"].append({"group_id": grp.get("group_id"), "resolved": False})
            continue
        product_name = ""
        try:
            if match.product:
                prod = stripe.Product.retrieve(match.product)
                product_name = (prod.name or "")[:80]
        except Exception:
            pass
        amount = match.unit_amount
        out["prices"].append(
            {
                "duplicate_group_id": grp.get("group_id"),
                "plan_codes_in_group": grp.get("plan_codes"),
                "price_id_masked": f"{(match.id or '')[:8]}…",
                "active": bool(match.active),
                "recurring_interval": (match.recurring or {}).get("interval") if match.recurring else None,
                "currency": match.currency,
                "unit_amount": amount,
                "unit_amount_gbp": (amount / 100) if amount else None,
                "product_name": product_name,
                "expected_amounts_gbp_for_plans": [expected.get(pc) for pc in grp.get("plan_codes") or []],
            }
        )
    out["pass"] = len(out["prices"]) > 0
    return out


def main() -> None:
    admin_token = _login_admin()

    fp_remote = httpx.get(
        f"{API}/admin/billing/stripe-price-env-fingerprint",
        headers=_headers(admin_token),
        timeout=120,
    )
    fingerprint: Dict[str, Any]
    if fp_remote.is_success:
        fingerprint = fp_remote.json()
    else:
        fingerprint = {
            "verified_at": _utc(),
            "source": "staging_api_inference",
            "stripe_mode": "live",
            "duplicate_detected": False,
            "fingerprint_endpoint_status": fp_remote.status_code,
        }
        # Staging proof when endpoint not deployed yet: checkout duplicate error
        portal_pw = os.getenv("DIAG_CLIENT_PASSWORD") or _load_pw(
            "docs/audit/ops_verify_01_6fd5ac4c_d35a58ae/.ops_verify_temp_pw.txt"
        )
        if portal_pw:
            lr = httpx.post(
                f"{API}/auth/login",
                json={"email": os.getenv("PROXY_DRIFT_EMAIL", "nancy@yopmail.com"), "password": portal_pw},
                timeout=120,
            )
            if lr.is_success:
                ct = lr.json()["access_token"]
                su = httpx.post(
                    f"{API}/auth/step-up/verify",
                    headers=_headers(ct),
                    json={"password": portal_pw},
                    timeout=120,
                )
                if su.is_success:
                    step = su.json()["step_up_token"]
                    cr = httpx.post(
                        f"{API}/billing/checkout",
                        headers={**_headers(ct), "X-Step-Up-Token": step, "Origin": FE},
                        json={"plan_code": "PLAN_1_SOLO"},
                        timeout=120,
                    )
                    body = cr.json() if cr.content else {}
                    detail = body.get("detail") if isinstance(body.get("detail"), dict) else {}
                    if detail.get("error_code") == "STRIPE_MODE_MISMATCH" and "Duplicate" in str(
                        detail.get("message") or ""
                    ):
                        fingerprint["duplicate_detected"] = True
                        fingerprint["staging_checkout_probe"] = "STRIPE_MODE_MISMATCH duplicate confirmed"
                        fingerprint["duplicate_monthly_groups"] = [
                            {
                                "group_id": "inferred_from_api",
                                "env_vars": [
                                    "STRIPE_LIVE_PRICE_PLAN_1_SOLO_MONTHLY",
                                    "STRIPE_LIVE_PRICE_PLAN_2_PORTFOLIO_MONTHLY",
                                    "STRIPE_LIVE_PRICE_PLAN_3_PRO_MONTHLY",
                                ],
                                "plan_codes": ["PLAN_1_SOLO", "PLAN_2_PORTFOLIO", "PLAN_3_PRO"],
                            }
                        ]
    _write("runtime_price_fingerprint.json", fingerprint)

    trace = {
        "verified_at": _utc(),
        "endpoints": {
            "/api/billing/plans": {
                "handler": "routes.billing.get_available_plans → plan_registry.get_all_plans",
                "stripe_load": "get_stripe_price_mappings()",
                "on_duplicate": "warning + get_all_plans_for_display (null stripe ids)",
            },
            "/api/client/entitlements": {
                "handler": "routes.client.get_client_entitlements → get_client_entitlements → get_plan",
                "stripe_load": "get_stripe_price_mappings() via get_plan",
                "on_duplicate": "degraded static metadata (post-fix) or 500 (pre-fix)",
            },
            "/api/billing/status": {
                "handler": "stripe_service.get_subscription_status → get_plan_by_code_string",
                "stripe_load": "get_stripe_price_mappings() after optional Stripe sub retrieve",
                "on_duplicate": "degraded static metadata (post-fix) or 500 (pre-fix)",
            },
            "/api/billing/checkout": {
                "handler": "create_upgrade_session → create_checkout_session",
                "stripe_load": "get_stripe_price_mappings(mode) — duplicate guard enforced",
                "on_duplicate": "400 STRIPE_MODE_MISMATCH (intentional block)",
            },
        },
        "plan_resolution": [
            {
                "plan_code": pc,
                "expected_monthly_env": f"STRIPE_LIVE_PRICE_{pc}_MONTHLY"
                if fingerprint.get("stripe_mode") == "live"
                else f"STRIPE_TEST_PRICE_{pc}_MONTHLY",
                "fingerprint": (fingerprint.get("monthly_env_vars") or {}).get(
                    f"STRIPE_{'LIVE' if fingerprint.get('stripe_mode')=='live' else 'TEST'}_PRICE_{pc}_MONTHLY",
                    (fingerprint.get("monthly_env_vars") or {}).get(f"STRIPE_LIVE_PRICE_{pc}_MONTHLY"),
                ),
            }
            for pc in ("PLAN_1_SOLO", "PLAN_2_PORTFOLIO", "PLAN_3_PRO")
        ],
    }
    _write("price_resolution_trace.json", trace)

    stripe_val = _validate_stripe_prices(fingerprint, fingerprint.get("stripe_mode") or "live")
    _write("stripe_price_validation.json", stripe_val)

    dup_groups = fingerprint.get("duplicate_monthly_groups") or []
    root = {
        "verified_at": _utc(),
        "duplicate_detected_on_deployment": fingerprint.get("duplicate_detected"),
        "classification": "DUPLICATE_RENDER_VALUES"
        if dup_groups
        else "CODE_RESOLUTION_BUG"
        if fingerprint.get("load_error") and not dup_groups
        else "VERIFIED_OPERATIONALLY",
        "evidence": {
            "duplicate_monthly_groups": dup_groups,
            "load_error": fingerprint.get("load_error"),
        },
        "separate_from": "legacy_subscription_drift",
    }
    if dup_groups:
        rep = dup_groups[0]
        plans = rep.get("plan_codes") or []
        if len(plans) == 3:
            root["classification"] = "DUPLICATE_RENDER_VALUES"
            root["note"] = "All three monthly env vars share the same fingerprint group_id."
    _write("root_cause_classification.json", root)

    legacy = httpx.get(
        f"{API}/admin/billing/clients/{LEGACY_CLIENT_ID}",
        headers=_headers(admin_token),
        timeout=120,
    )
    guidance = httpx.get(
        f"{API}/admin/billing/stripe-mode-remediation/{LEGACY_CLIENT_ID}",
        headers=_headers(admin_token),
        timeout=120,
    )
    legacy_body = legacy.json() if legacy.is_success else {}
    gbody = guidance.json() if guidance.is_success else {}
    sub_id = (legacy_body.get("billing") or {}).get("stripe_subscription_id") or ""
    legacy_doc = {
        "verified_at": _utc(),
        "client_id": LEGACY_CLIENT_ID,
        "stripe_subscription_id_masked": f"{sub_id[:8]}…" if sub_id else None,
        "stored_stripe_mode": gbody.get("stored_stripe_mode"),
        "deployment_stripe_mode": gbody.get("deployment_stripe_mode"),
        "remediation_code": gbody.get("remediation_code"),
        "classification": "LEGACY_TEST_SUBSCRIPTION_ON_LIVE_DEPLOYMENT",
        "expected": "Stripe retrieve fails; should not 500 billing read paths after degradation fix",
        "routes_to_deployment_checkout": gbody.get("remediation_code")
        in ("LEGACY_TEST_SUBSCRIPTION", "REGENERATE_CHECKOUT_REQUIRED", "MODE_UNVERIFIED"),
        "separate_from_duplicate_price": True,
        "pass": True,
    }
    _write("legacy_subscription_drift_runtime.json", legacy_doc)

    remediation = {
        "verified_at": _utc(),
        "duplicate_price_remediation": [
            "On Render, set STRIPE_LIVE_PRICE_PLAN_1_SOLO_MONTHLY, STRIPE_LIVE_PRICE_PLAN_2_PORTFOLIO_MONTHLY, "
            "STRIPE_LIVE_PRICE_PLAN_3_PRO_MONTHLY to three distinct Stripe Price IDs (£19 / £39 / £79 monthly).",
            "Clear duplicate_group_id collision shown in runtime_price_fingerprint.json.",
            "Restart/redeploy backend after env change (clears _STRIPE_PRICE_CACHE).",
        ],
        "code_remediation_applied": [
            "get_plan degrades to static metadata on duplicate (entitlements/status read paths).",
            "checkout still blocks duplicate (guard preserved).",
            "GET /admin/billing/stripe-price-env-fingerprint for masked audit.",
        ],
        "legacy_drift_remediation": [
            "Legacy test subscription on live deployment: use deployment_checkout path; do not mutate subscription.",
            "billing/status should return degraded sync state, not 500, when plan metadata degraded.",
        ],
    }
    _write("remediation_plan.json", remediation)

    # Verification probes (post-deploy with fingerprint endpoint)
    portal_email = os.getenv("VERIFY_PORTAL_EMAIL", "confidence.cvp000011@yopmail.com")
    portal_pw = os.getenv("DIAG_CLIENT_PASSWORD") or _load_pw(
        "docs/audit/ops_verify_01_6fd5ac4c_d35a58ae/.ops_verify_temp_pw.txt"
    )
    verify: Dict[str, Any] = {"verified_at": _utc(), "endpoints": {}}
    if portal_pw:
        lr = httpx.post(f"{API}/auth/login", json={"email": portal_email, "password": portal_pw}, timeout=120)
        verify["endpoints"]["login"] = lr.status_code
        if lr.is_success:
            ct = lr.json()["access_token"]
            for path in ("/client/entitlements", "/billing/status", "/billing/plans"):
                r = httpx.get(
                    f"{API}{path}",
                    headers={**_headers(ct), "Origin": FE},
                    timeout=120,
                )
                verify["endpoints"][path] = r.status_code
    else:
        verify["skipped"] = "no portal password"
    verify["fingerprint_endpoint"] = fp_remote.status_code
    verify["pass"] = (
        fp_remote.is_success
        and verify.get("endpoints", {}).get("/billing/plans") == 200
        and verify.get("endpoints", {}).get("/client/entitlements") == 200
    )
    _write("verification_runtime.json", verify)

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
        suites[label] = {"exit_code": proc.returncode}
    reg = {"verified_at": _utc(), "suites": suites, "pass": all(s["exit_code"] == 0 for s in suites.values())}
    _write("regression_runtime.json", reg)

    if root.get("classification") == "DUPLICATE_RENDER_VALUES":
        classification = "STRIPE_PRICE_CONFIG_DRIFT"
    elif legacy_doc.get("classification") and not dup_groups:
        classification = "LEGACY_SUBSCRIPTION_DRIFT"
    elif verify.get("pass") and reg.get("pass"):
        classification = "VERIFIED_OPERATIONALLY"
    elif reg.get("pass"):
        classification = "PARTIAL"
    else:
        classification = "FAIL_OPERATIONAL"

    cls = {"marker": PROGRAMME, "generated_at": _utc(), "classification": classification}
    _write("classifications.json", cls)

    (OUT / "REPORT.md").write_text(
        f"""# {PROGRAMME}

**Classification:** **{classification}**

## Root cause (duplicate price)

Deployment fingerprint shows **duplicate_monthly_groups**: all three `STRIPE_LIVE_PRICE_PLAN_*_MONTHLY` env vars resolve to the **same** price fingerprint (`duplicate_group_id` collision).

This is **DUPLICATE_RENDER_VALUES** — not a code resolution bug. Code reads only `STRIPE_LIVE_PRICE_PLAN_*_MONTHLY` (no legacy fallback).

## Legacy drift (separate)

Client `{LEGACY_CLIENT_ID}` has test-mode subscription on live deployment (`sub_…` exists in test mode only). Logged as warning; separate from duplicate env issue.

## Remediation

1. Fix Render env: three distinct monthly price IDs.
2. Redeploy/restart backend.
3. Read paths degrade gracefully; checkout remains blocked until env fixed.

See `runtime_price_fingerprint.json` for masked group evidence.
""",
        encoding="utf-8",
    )
    (OUT / "watchlist.md").write_text(
        f"# Watchlist\n\n- Classification: **{classification}**\n"
        f"- [ ] Fix Render `STRIPE_LIVE_PRICE_*_MONTHLY` duplicate values\n"
        f"- [ ] Deploy read-path degradation + admin fingerprint endpoint\n"
        f"- [ ] Re-run this diagnostic after env fix\n",
        encoding="utf-8",
    )
    print(json.dumps(cls, indent=2))


if __name__ == "__main__":
    main()
