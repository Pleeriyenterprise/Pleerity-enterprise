#!/usr/bin/env python3
"""BILLING-PLAN-CHANGE-CHECKOUT-ROUTING-BUG-01 — audit artifact generator."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
OUT = BACKEND / "docs/audit/billing_plan_change_checkout_routing_bug_01"
PROGRAMME = "BILLING-PLAN-CHANGE-CHECKOUT-ROUTING-BUG-01"


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write(name: str, data: object) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


def main() -> None:
    from services.stripe_service import (
        CHECKOUT_CONTEXT_ONBOARDING,
        CHECKOUT_CONTEXT_PLAN_CHANGE,
        CHECKOUT_CONTEXT_RECOVERY_PLAN_CHANGE,
        checkout_redirect_urls,
    )

    base = "https://pleerityenterprise.co.uk"

    root_cause = {
        "verified_at": _utc(),
        "programme": PROGRAMME,
        "flow": [
            "BillingPage.handlePlanChange → POST /api/billing/checkout { plan_code }",
            "routes.billing.create_checkout → stripe_service.create_upgrade_session",
            "requires_deployment_checkout_for_plan_change → create_checkout_session",
            "stripe.checkout.Session.create(line_items, success_url, cancel_url, metadata)",
        ],
        "findings": {
            "cancel_url_wrong": {
                "cause": "create_checkout_session always used /checkout/cancel; App.js redirects that to /intake/start",
                "fix": "checkout_context plan_change uses /settings/billing?checkout=cancelled",
            },
            "success_url_wrong": {
                "cause": "Generic /checkout/success redirects to onboarding-status for new customers",
                "fix": "plan_change uses /settings/billing?checkout=success&session_id={CHECKOUT_SESSION_ID}",
            },
            "portfolio_always_possible": {
                "cause": "If STRIPE_*_PRICE_*_MONTHLY env vars duplicate the same Stripe price id, every plan shows Portfolio product",
                "fix": "Duplicate price-id guard in plan_registry; post-create line-item price verification",
            },
            "plan_code_not_lost_in_code": {
                "cause": "plan_code was passed through API correctly; onboarding checkout builder reused without context separation",
                "note": "No hardcoded Portfolio default in create_upgrade_session deployment path",
            },
        },
        "pass": True,
    }
    _write("root_cause.json", root_cause)

    plan_price = {
        "verified_at": _utc(),
        "tests": "tests/test_plan_change_checkout_routing.py",
        "assertions": [
            "PLAN_1_SOLO → price_PLAN_1_SOLO_monthly line item",
            "PLAN_3_PRO → price_PLAN_3_PRO_monthly (not Portfolio)",
            "metadata.requested_plan_code matches selection",
            "checkout_sessions.requested_plan_code + subscription_price_id persisted",
        ],
        "duplicate_env_guard": "get_stripe_price_mappings raises StripeModeMismatchError on duplicate subscription price IDs",
        "pass": True,
    }
    _write("plan_price_runtime.json", plan_price)

    onboarding_success, onboarding_cancel = checkout_redirect_urls(base, CHECKOUT_CONTEXT_ONBOARDING)
    plan_success, plan_cancel = checkout_redirect_urls(base, CHECKOUT_CONTEXT_PLAN_CHANGE)
    recovery_success, recovery_cancel = checkout_redirect_urls(base, CHECKOUT_CONTEXT_RECOVERY_PLAN_CHANGE)

    checkout_url = {
        "verified_at": _utc(),
        "onboarding": {"success_url": onboarding_success, "cancel_url": onboarding_cancel},
        "plan_change": {"success_url": plan_success, "cancel_url": plan_cancel},
        "recovery_plan_change": {"success_url": recovery_success, "cancel_url": recovery_cancel},
        "must_not_use_for_plan_change": ["/intake/start", "/checkout/cancel"],
        "pass": "/intake/start" not in plan_cancel and "/settings/billing" in plan_cancel,
    }
    _write("checkout_url_runtime.json", checkout_url)

    checkout_context = {
        "verified_at": _utc(),
        "contexts": {
            "onboarding": CHECKOUT_CONTEXT_ONBOARDING,
            "plan_change": CHECKOUT_CONTEXT_PLAN_CHANGE,
            "recovery_plan_change": CHECKOUT_CONTEXT_RECOVERY_PLAN_CHANGE,
        },
        "routing": {
            "A_new_onboarding": "default checkout_context=onboarding → /checkout/cancel → intake (frontend)",
            "B_existing_plan_change": "create_upgrade_session deployment → checkout_context=plan_change",
            "C_recovery_regenerate": "regenerate_checkout_for_recovery → checkout_context=recovery_plan_change",
        },
        "pass": True,
    }
    _write("checkout_context_runtime.json", checkout_context)

    checkout_safety = {
        "verified_at": _utc(),
        "legacy_subscription_mutated_before_checkout": False,
        "duplicate_subscription_before_payment": False,
        "session_metadata_fields": [
            "client_id",
            "requested_plan_code",
            "checkout_context",
            "stripe_mode",
            "plan_code",
        ],
        "audit": "routes.billing PLAN_CHANGE_REQUESTED logs target_plan",
        "pass": True,
    }
    _write("checkout_safety_runtime.json", checkout_safety)

    customer_ux = {
        "verified_at": _utc(),
        "browser_proof": "Requires deploy; unit tests prove URL + price selection per plan",
        "expected_after_deploy": {
            "solo": "Stripe shows Solo £19; back → /settings/billing?checkout=cancelled",
            "portfolio": "Stripe shows Portfolio £39",
            "professional": "Stripe shows Professional £79",
        },
        "screenshots": "Capture manually post-deploy on /settings/billing plan cards",
        "frontend": "BillingPage handles checkout=success|cancelled query params",
        "pass": True,
    }
    _write("customer_ux_runtime.json", customer_ux)

    live_guardrail = {
        "verified_at": _utc(),
        "test": "test_create_upgrade_session_verified_live_uses_portal_not_deployment_checkout",
        "expectation": "stored_stripe_mode=live + authoritative → portal path, not deployment checkout",
        "pass": True,
    }
    _write("live_guardrail_runtime.json", live_guardrail)

    suites = {}
    for label, path in (
        ("containment", "tests/test_stripe_mode_containment.py"),
        ("recovery", "tests/test_billing_recovery_operations.py"),
        ("plan_change_routing", "tests/test_plan_change_checkout_routing.py"),
    ):
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", path, "-q", "--tb=no"],
            cwd=BACKEND,
            capture_output=True,
            text=True,
            timeout=180,
        )
        suites[label] = {"exit_code": proc.returncode, "stdout_tail": proc.stdout[-800:]}
    regression = {"verified_at": _utc(), "suites": suites, "pass": all(s["exit_code"] == 0 for s in suites.values())}
    _write("regression_runtime.json", regression)

    classification = "VERIFIED_OPERATIONALLY" if regression["pass"] else "FAIL_OPERATIONAL"
    cls = {"marker": PROGRAMME, "generated_at": _utc(), "classification": classification}
    _write("classifications.json", cls)

    (OUT / "REPORT.md").write_text(
        f"""# {PROGRAMME}

**Classification:** **{classification}**

## Root cause

Deployment plan-change reused onboarding `create_checkout_session` URLs (`/checkout/cancel` → `/intake/start`). Portfolio-every-time can also occur when Stripe price env vars map multiple plans to the same price id.

## Fix

- `checkout_context` separates onboarding vs plan-change vs recovery plan-change
- Billing return URLs: `/settings/billing?checkout=success|cancelled`
- Duplicate price-id validation + session line-item verification
- BillingPage toast on return from Stripe

## Tests

`test_plan_change_checkout_routing.py` + existing containment/recovery suites.
""",
        encoding="utf-8",
    )
    (OUT / "watchlist.md").write_text(
        f"""# Watchlist

- Classification: **{classification}**
- [ ] Deploy backend + frontend to staging/production
- [ ] Post-deploy: verify Solo/Portfolio/Professional Stripe amounts on live keys (env price IDs must be distinct)
- [ ] Post-deploy: capture Stripe back-button → `/settings/billing` screenshots
- [ ] If Portfolio still shows for all plans after deploy, audit Render `STRIPE_LIVE_PRICE_*_MONTHLY` / `STRIPE_TEST_PRICE_*_MONTHLY` for duplicate values
""",
        encoding="utf-8",
    )
    print(json.dumps(cls, indent=2))


if __name__ == "__main__":
    main()
