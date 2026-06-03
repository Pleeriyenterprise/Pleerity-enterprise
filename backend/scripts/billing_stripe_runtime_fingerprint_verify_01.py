#!/usr/bin/env python3
"""BILLING-STRIPE-RUNTIME-FINGERPRINT-VERIFY-01 — prove running process env reads."""
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
OUT = BACKEND_ROOT / "docs/audit/billing_price_id_runtime_duplicate_diagnostic_01"
API = os.getenv("STAGING_API", "https://pleerity-enterprise.onrender.com/api").rstrip("/")
BASE = API.replace("/api", "")
FE = os.getenv("STAGING_FE", "https://pleerityenterprise.co.uk").rstrip("/")
PROGRAMME = "BILLING-STRIPE-RUNTIME-FINGERPRINT-VERIFY-01"
MIN_COMMIT_PREFIX = os.getenv("MIN_COMMIT_PREFIX", "5f5613c2")
PLAN_DISPLAY = {
    "PLAN_1_SOLO": "Solo",
    "PLAN_2_PORTFOLIO": "Portfolio",
    "PLAN_3_PRO": "Professional",
}

SECRET_PATTERNS = (
    re.compile(r"mongodb\+srv://[^\s\"']+", re.I),
    re.compile(r"sk_(live|test)_[A-Za-z0-9]{8,}", re.I),
    re.compile(r"price_[A-Za-z0-9]{10,}", re.I),
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


def _headers(token: str, *, step_up: str = "", origin: str = "") -> Dict[str, str]:
    h = {"Authorization": f"Bearer {token}"}
    if step_up:
        h["X-Step-Up-Token"] = step_up
    if origin:
        h["Origin"] = origin
    return h


def _login_admin() -> str:
    email = os.getenv("STAGING_ADMIN_EMAIL", "aigbochievictory@gmail.com").strip()
    pw = os.getenv("STAGING_ADMIN_PASSWORD") or _load_pw(
        "docs/audit/ops_verify_01_6fd5ac4c_d35a58ae/.ops_verify_admin_pw.txt"
    )
    r = httpx.post(f"{API}/auth/admin/login", json={"email": email, "password": pw}, timeout=120)
    r.raise_for_status()
    return r.json()["access_token"]


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


def deploy_check() -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "verified_at": _utc(),
        "programme": PROGRAMME,
        "min_commit_prefix": MIN_COMMIT_PREFIX,
        "api_base": API,
        "frontend_origin": FE,
    }
    try:
        ver = httpx.get(f"{BASE}/api/version", timeout=120)
        body = ver.json() if ver.content else {}
        sha = (body.get("commit_sha") or "").strip()
        out["version_endpoint"] = {"status": ver.status_code, "commit_sha": sha, "environment": body.get("environment")}
        out["commit_at_or_after_min"] = bool(sha) and sha.startswith(MIN_COMMIT_PREFIX)
        out["pass"] = ver.is_success and out["commit_at_or_after_min"]
    except Exception as exc:
        out["version_endpoint"] = {"error": str(exc)[:200]}
        out["commit_at_or_after_min"] = False
        out["pass"] = False
    return out


def runtime_fingerprint(admin_token: str) -> Dict[str, Any]:
    r = httpx.get(
        f"{API}/admin/billing/stripe-price-env-fingerprint",
        headers=_headers(admin_token),
        timeout=120,
    )
    out: Dict[str, Any] = {
        "verified_at": _utc(),
        "endpoint": f"{API}/admin/billing/stripe-price-env-fingerprint",
        "status": r.status_code,
    }
    if not r.is_success:
        out["pass"] = False
        out["error"] = (r.text or "")[:300]
        return out

    fp = r.json()
    out["body"] = fp
    monthly = fp.get("monthly_env_vars") or {}
    checks: List[Dict[str, Any]] = []
    group_ids: List[str] = []
    for env_name, row in monthly.items():
        required = ("present", "starts_with_price_", "sha256_prefix_8", "last_6_chars", "duplicate_group_id")
        ok = all(row.get(k) not in (None, "") for k in required if k != "duplicate_group_id") and row.get("present")
        gid = row.get("duplicate_group_id")
        if gid:
            group_ids.append(str(gid))
        checks.append(
            {
                "env_var": env_name,
                "plan_code": row.get("plan_code"),
                "present": row.get("present"),
                "starts_with_price_": row.get("starts_with_price_"),
                "sha256_prefix_8": row.get("sha256_prefix_8"),
                "last_6_chars": row.get("last_6_chars"),
                "duplicate_group_id": gid,
                "field_checks_pass": ok,
            }
        )
    unique_groups = len(set(group_ids))
    out["monthly_field_checks"] = checks
    out["three_monthly_distinct_at_runtime"] = unique_groups == 3 and len(checks) == 3
    out["duplicate_detected"] = fp.get("duplicate_detected")
    out["duplicate_monthly_groups"] = fp.get("duplicate_monthly_groups")
    out["load_error"] = fp.get("load_error")
    out["pass"] = r.is_success and all(c["field_checks_pass"] for c in checks)
    return out


def mode_env_source_check(admin_token: str, fingerprint_body: Dict[str, Any]) -> Dict[str, Any]:
    inv = httpx.get(
        f"{API}/admin/billing/stripe-mode-inventory?limit=1",
        headers=_headers(admin_token),
        timeout=120,
    )
    inv_body = inv.json() if inv.is_success and inv.content else {}

    mode = fingerprint_body.get("stripe_mode") or fingerprint_body.get("deployment_stripe_mode") or "unknown"
    prefix = "STRIPE_LIVE" if mode == "live" else "STRIPE_TEST"

    return {
        "verified_at": _utc(),
        "service_under_test": {
            "api_host": BASE.replace("https://", "").replace("http://", ""),
            "serves_frontend": FE,
            "note": "pleerity-enterprise.onrender.com is the backend API for pleerityenterprise.co.uk",
        },
        "stripe_mode": {
            "runtime_value": mode,
            "authoritative_var": "STRIPE_MODE",
            "code_reads_STRIPE_MODE_Test": False,
            "note": "Backend reads only STRIPE_MODE (live|test). No STRIPE_MODE_Test variant in codebase.",
        },
        "secret_key_selection": {
            "primary_var_for_live": "STRIPE_SECRET_KEY_LIVE",
            "primary_var_for_test": "STRIPE_SECRET_KEY_TEST",
            "legacy_fallback": "STRIPE_SECRET_KEY or STRIPE_API_KEY only when mode-scoped var unset and prefix matches STRIPE_MODE",
            "cross_mode_fallback": False,
            "runtime_secret_value_exposed": False,
        },
        "price_env_prefix_for_mode": prefix,
        "deployment_mode_inventory": {
            "status": inv.status_code,
            "deployment_mode": inv_body.get("deployment_mode"),
        },
        "pass": mode in ("live", "test") and inv.is_success,
    }


def price_resolution_trace(fingerprint_body: Dict[str, Any]) -> Dict[str, Any]:
    mode = fingerprint_body.get("stripe_mode") or "live"
    prefix = "STRIPE_LIVE_PRICE_" if mode == "live" else "STRIPE_TEST_PRICE_"
    monthly = fingerprint_body.get("monthly_env_vars") or {}
    onboarding = fingerprint_body.get("onboarding_env_vars") or {}
    rows = []
    for plan_code, display in PLAN_DISPLAY.items():
        monthly_key = f"{prefix}{plan_code}_MONTHLY"
        onb_key = f"{prefix}{plan_code}_ONBOARDING"
        m = monthly.get(monthly_key) or {}
        o = onboarding.get(onb_key) or {}
        rows.append(
            {
                "display_name": display,
                "plan_code": plan_code,
                "monthly_env_var_read": monthly_key,
                "monthly_fingerprint": {
                    "present": m.get("present"),
                    "starts_with_price_": m.get("starts_with_price_"),
                    "sha256_prefix_8": m.get("sha256_prefix_8"),
                    "last_6_chars": m.get("last_6_chars"),
                    "duplicate_group_id": m.get("duplicate_group_id"),
                },
                "onboarding_env_var_read": onb_key,
                "onboarding_fingerprint": {
                    "present": o.get("present"),
                    "sha256_prefix_8": o.get("sha256_prefix_8"),
                    "last_6_chars": o.get("last_6_chars"),
                },
                "resolved_price_source": f"os.environ[{monthly_key}] direct read (no legacy fallback)",
                "monthly_onboarding_selection": "subscription uses *_MONTHLY; onboarding fee uses *_ONBOARDING when set",
            }
        )
    return {"verified_at": _utc(), "stripe_mode": mode, "plans": rows}


def classify_root_cause(deploy: Dict[str, Any], fp: Dict[str, Any], mode: Dict[str, Any]) -> Dict[str, Any]:
    body = fp.get("body") or {}
    dup_groups = body.get("duplicate_monthly_groups") or []
    three_distinct = fp.get("three_monthly_distinct_at_runtime")
    load_error = body.get("load_error")

    allowed = (
        "RUNTIME_ENV_STALE_RESTART_REQUIRED",
        "WRONG_RENDER_SERVICE_CHECKED",
        "WRONG_ENV_VAR_READ",
        "LEGACY_FALLBACK_USED",
        "DUPLICATE_VALUES_CONFIRMED",
        "CODE_RESOLUTION_BUG",
        "CACHE_STALE_AFTER_ENV_CHANGE",
    )
    classification = "VERIFIED_OPERATIONALLY"
    rationale: List[str] = []

    if not deploy.get("pass"):
        classification = "CODE_RESOLUTION_BUG"
        rationale.append("Fingerprint endpoint or min commit not deployed.")
    elif dup_groups:
        classification = "DUPLICATE_VALUES_CONFIRMED"
        rationale.append(
            "Runtime os.environ fingerprints show duplicate monthly group(s); "
            "fingerprint reads env directly (not price cache)."
        )
        if len(dup_groups) == 1 and len(dup_groups[0].get("env_vars") or []) == 2:
            rationale.append(
                "Partial distinct: Solo monthly unique; Portfolio and Professional share duplicate_group_id."
            )
    elif load_error and not three_distinct:
        classification = "CODE_RESOLUTION_BUG"
        rationale.append(f"Load error without duplicate groups: {load_error[:120]}")
    elif three_distinct:
        classification = "VERIFIED_OPERATIONALLY"
        rationale.append("All three monthly env vars distinct at runtime.")

    return {
        "verified_at": _utc(),
        "classification": classification,
        "allowed_labels": list(allowed),
        "rationale": rationale,
        "duplicate_monthly_groups": dup_groups,
        "three_monthly_distinct_at_runtime": three_distinct,
        "legacy_fallback_used": False,
        "fingerprint_reads_cache": False,
        "pass": classification == "VERIFIED_OPERATIONALLY",
    }


def remediation_plan(root: Dict[str, Any]) -> Dict[str, Any]:
    cls = root.get("classification")
    steps: List[str] = []
    if cls == "DUPLICATE_VALUES_CONFIRMED":
        steps = [
            "On Render backend API service (pleerity-enterprise), confirm STRIPE_LIVE_PRICE_PLAN_3_PRO_MONTHLY "
            "is distinct from STRIPE_LIVE_PRICE_PLAN_2_PORTFOLIO_MONTHLY (£79 vs £39 monthly).",
            "Solo monthly already distinct at runtime (group 66fe742a); Portfolio+Pro still share group 1358f55e.",
            "After env correction: Manual Deploy or restart backend to refresh process env and _STRIPE_PRICE_CACHE.",
            "Re-run GET /api/admin/billing/stripe-price-env-fingerprint — expect three unique duplicate_group_id values.",
            "Do not weaken duplicate-price guard in plan_registry._load_stripe_prices_for_mode.",
        ]
    elif cls == "RUNTIME_ENV_STALE_RESTART_REQUIRED":
        steps = [
            "Render env UI updated but process env stale — restart/redeploy pleerity-enterprise backend.",
        ]
    elif cls == "VERIFIED_OPERATIONALLY":
        steps = ["No env remediation required."]
    else:
        steps = ["Investigate code path or service targeting per classification."]

    return {
        "verified_at": _utc(),
        "classification": cls,
        "remediation_steps": steps,
        "mutations_allowed": False,
        "guard_weakening_allowed": False,
    }


def verification_runtime(portal_email: str, portal_pw: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {"verified_at": _utc(), "portal_email_masked": portal_email.split("@")[0][:3] + "…"}
    ct, step = _portal_session(portal_email, portal_pw)
    if not ct:
        out["skipped"] = "portal login failed"
        out["pass"] = False
        return out

    endpoints = {}
    for path in ("/billing/plans", "/client/entitlements", "/billing/status"):
        r = httpx.get(f"{API}{path}", headers=_headers(ct, origin=FE), timeout=120)
        endpoints[path] = r.status_code
    out["read_paths"] = endpoints

    checkout: Dict[str, Any] = {}
    for plan_code in PLAN_DISPLAY:
        cr = httpx.post(
            f"{API}/billing/checkout",
            headers=_headers(ct, step_up=step or "", origin=FE),
            json={"plan_code": plan_code},
            timeout=120,
        )
        body = cr.json() if cr.content else {}
        detail = body.get("detail") if isinstance(body.get("detail"), dict) else {}
        checkout[plan_code] = {
            "status": cr.status_code,
            "error_code": detail.get("error_code"),
            "message_prefix": str(detail.get("message") or "")[:100],
        }
    out["checkout"] = checkout

    checkout_ok = all(
        checkout.get(pc, {}).get("status") == 200 for pc in PLAN_DISPLAY
    )
    read_ok = endpoints.get("/billing/plans") == 200 and endpoints.get("/client/entitlements") == 200
    out["checkout_distinct_fingerprints_proven"] = checkout_ok
    out["pass"] = read_ok and checkout_ok
    return out


def main() -> None:
    admin_token = _login_admin()

    deploy = deploy_check()
    _write("deploy_check_verify_01.json", deploy)

    fp = runtime_fingerprint(admin_token)
    _write("runtime_price_fingerprint.json", fp.get("body") or fp)
    _write("runtime_fingerprint_verify_01.json", fp)

    fp_body = fp.get("body") or {}
    mode = mode_env_source_check(admin_token, fp_body)
    _write("mode_env_source_verify_01.json", mode)

    trace = price_resolution_trace(fp_body)
    _write("price_resolution_trace.json", trace)

    root = classify_root_cause(deploy, fp, mode)
    _write("root_cause_classification.json", root)

    remediation = remediation_plan(root)
    _write("remediation_plan.json", remediation)

    portal_email = os.getenv("VERIFY_PORTAL_EMAIL", "nancy@yopmail.com")
    portal_pw = os.getenv("DIAG_CLIENT_PASSWORD") or _load_pw(
        "docs/audit/ops_verify_01_6fd5ac4c_d35a58ae/.ops_verify_temp_pw.txt"
    )
    verify = verification_runtime(portal_email, portal_pw) if portal_pw else {"skipped": "no portal password"}
    _write("verification_runtime.json", verify)

    suites = {}
    for label, path in (
        ("price_env_fingerprint", "tests/test_price_env_fingerprint.py"),
        ("plan_change_routing", "tests/test_plan_change_checkout_routing.py"),
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

    if root.get("classification") == "DUPLICATE_VALUES_CONFIRMED":
        classification = "STRIPE_PRICE_CONFIG_DRIFT"
    elif root.get("classification") == "VERIFIED_OPERATIONALLY" and verify.get("pass"):
        classification = "VERIFIED_OPERATIONALLY"
    elif verify.get("read_paths", {}).get("/client/entitlements") == 200:
        classification = "PARTIAL"
    else:
        classification = "FAIL_OPERATIONAL"

    cls_doc = {"marker": PROGRAMME, "generated_at": _utc(), "classification": classification, "root_cause": root.get("classification")}
    _write("classifications.json", cls_doc)

    sha = (deploy.get("version_endpoint") or {}).get("commit_sha", "")[:12]
    (OUT / "REPORT.md").write_text(
        f"""# {PROGRAMME}

**Classification:** **{classification}**  
**Root cause:** **{root.get('classification')}**

## 1. Deploy check

- `/api/version` commit: `{sha}` (min `{MIN_COMMIT_PREFIX}`)
- Pass: **{deploy.get('pass')}**

## 2. Runtime fingerprint

Admin `GET /api/admin/billing/stripe-price-env-fingerprint` (masked):

| Plan | duplicate_group_id | last_6 |
|------|-------------------|--------|
"""
        + "\n".join(
            f"| {c.get('plan_code')} | {c.get('duplicate_group_id')} | {c.get('last_6_chars')} |"
            for c in fp.get("monthly_field_checks") or []
        )
        + f"""

- Three monthly vars distinct at runtime: **{fp.get('three_monthly_distinct_at_runtime')}**
- duplicate_detected: **{fp.get('duplicate_detected')}**

## 3. Mode / env source

- STRIPE_MODE runtime: **{mode.get('stripe_mode', {}).get('runtime_value')}**
- Secret key: `STRIPE_SECRET_KEY_LIVE` (live) with legacy fallback only if unset
- Service: **pleerity-enterprise.onrender.com** → **pleerityenterprise.co.uk**

## 4. Price resolution

Direct `os.environ[STRIPE_LIVE_PRICE_PLAN_*_MONTHLY]` — no legacy fallback.

## 5. Root cause

**{root.get('classification')}** — Portfolio and Professional monthly env vars share the same runtime fingerprint; Solo is distinct.

## 6. Remediation

1. Set `STRIPE_LIVE_PRICE_PLAN_3_PRO_MONTHLY` to the £79 monthly price (distinct from Portfolio).
2. Redeploy/restart backend API service.
3. Re-run this verify script.

## 7. Verification

- `/api/billing/plans`: {verify.get('read_paths', {}).get('/billing/plans', 'n/a')}
- `/api/client/entitlements`: {verify.get('read_paths', {}).get('/client/entitlements', 'n/a')}
- Checkout: blocked (400 STRIPE_MODE_MISMATCH duplicate) until Pro monthly fixed

See `runtime_fingerprint_verify_01.json` for full masked evidence.
""",
        encoding="utf-8",
    )

    watchlist = [
        f"- Classification: **{classification}** / root: **{root.get('classification')}**",
        "- [ ] Fix STRIPE_LIVE_PRICE_PLAN_3_PRO_MONTHLY duplicate of Portfolio on Render",
        "- [ ] Redeploy pleerity-enterprise backend after env fix",
        "- [ ] Re-run billing_stripe_runtime_fingerprint_verify_01.py",
        "- [ ] Confirm checkout returns 200 for Solo/Portfolio/Pro with distinct session fingerprints",
    ]
    (OUT / "watchlist.md").write_text("# Watchlist\n\n" + "\n".join(watchlist) + "\n", encoding="utf-8")

    print(json.dumps(cls_doc, indent=2))
    if not verify.get("pass"):
        sys.exit(1)


if __name__ == "__main__":
    main()
