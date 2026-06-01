#!/usr/bin/env python3
"""Build PRELAUNCH onboarding recovery orchestration verification bundle (Phase 4)."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/audit/prelaunch_onboarding_recovery_orchestration_01"
PROGRAMME = "PRELAUNCH-ONBOARDING-CONTINUATION-RECOVERY-ORCHESTRATION-01"


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _write(name: str, data: object) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


def _run_pytest() -> dict:
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_onboarding_recovery_orchestration.py",
            "tests/test_onboarding_continuation.py",
            "tests/test_onboarding_recovery_observability.py",
            "-q",
            "--tb=no",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    return {
        "exit_code": proc.returncode,
        "stdout": proc.stdout[-4000:] if proc.stdout else "",
        "stderr": proc.stderr[-2000:] if proc.stderr else "",
        "passed": proc.returncode == 0,
    }


def main() -> int:
    run_id = _utc()
    regression = _run_pytest()

    classifications = {
        "PAYMENT_ABANDONED": "regenerate_payment | resume_onboarding",
        "EXPIRED_CHECKOUT": "regenerate_payment | resume_onboarding",
        "PROMO_REDEMPTION_FAILED": "regenerate_payment | resume_onboarding",
        "FIRST_TIME_RESTRICTION_COLLISION": "regenerate_payment | resume_onboarding (+ optional waiver)",
        "ACTIVATION_INCOMPLETE": "resend_activation",
        "PARTIAL_PROVISIONING": "manual_escalation",
        "SUBSCRIPTION_DRIFT": "manual_escalation",
        "DUPLICATE_RECOVERY_RISK": "blocked",
        "RECOVERY_ALREADY_ACTIVE": "blocked",
    }

    _write(
        "root_cause.json",
        {
            "programme": PROGRAMME,
            "run_id": run_id,
            "problem": "Hidden recover_onboarding override mutated state without customer continuation.",
            "resolution": "Governed orchestration with assessment, execution modes, continuation links, and observability.",
        },
    )
    _write("classifications.json", {"classifications": classifications, "run_id": run_id})
    _write(
        "recovery_classification_runtime.json",
        {"unit_tests": regression, "note": "Classification covered by pytest orchestration module.", "run_id": run_id},
    )
    _write(
        "regression_runtime.json",
        regression,
    )
    _write(
        "continuation_runtime.json",
        {
            "modes": ["resume_onboarding", "regenerate_payment", "resend_activation"],
            "public_routes": [
                "GET /api/onboarding/continuation/resolve",
                "POST /api/onboarding/continuation/checkout",
            ],
            "landing_route": "/onboarding/continue",
            "run_id": run_id,
        },
    )
    _write(
        "notification_runtime.json",
        {
            "templates": ["ADMIN_MANUAL", "WELCOME_EMAIL"],
            "events": [
                "onboarding_recovery_payment_continuation",
                "onboarding_recovery_continuation",
                "onboarding_recovery_activation",
            ],
            "run_id": run_id,
        },
    )
    _write(
        "payment_recovery_runtime.json",
        {
            "execution_modes": ["regenerate_payment", "resume_onboarding + continuation checkout"],
            "governance_fields": [
                "recovery_checkout_context",
                "recovery_origin_reference",
                "recovery_attempt_count",
                "last_recovery_checkout_id",
                "continuation_delivered_at",
            ],
            "run_id": run_id,
        },
    )
    _write(
        "recovery_metrics_runtime.json",
        {
            "collections": ["onboarding_recovery_audit", "onboarding_recovery_metrics"],
            "admin_route": "GET /api/admin/clients/onboarding-recovery/fleet-metrics",
            "audit_actions": [
                "ONBOARDING_RECOVERY_EXECUTED",
                "ONBOARDING_RECOVERY_CONTINUATION_RECORDED",
            ],
            "run_id": run_id,
        },
    )

    report = f"""# {PROGRAMME} — Verification bundle

**Run:** `{run_id}`

## Summary

Phases 1–4 implement governed onboarding recovery orchestration:

| Phase | Deliverable |
|-------|-------------|
| 1 | Classification & read-only assessment |
| 2 | Payment regeneration & activation resend execution |
| 3 | Secure continuation links & customer landing |
| 4 | Audit trail, metrics, completion detection |

## Regression

Unit tests: **{"PASS" if regression["passed"] else "FAIL"}** (exit {regression["exit_code"]})

## Staging scenarios (manual)

- **A:** Intake complete → payment abandoned → resume or regenerate → pay → activate
- **B:** Paid → activation incomplete → resend activation
- **C:** Promo preserved on regenerate / continuation checkout
- **D:** Duplicate recovery blocked when checkout still fresh
- **E:** Expired checkout superseded by new session

## Classification

See `classifications.json`.

## Watchlist

See `watchlist.md`.
"""
    (OUT / "REPORT.md").write_text(report, encoding="utf-8")

    watchlist = """# Watchlist — onboarding recovery orchestration

## Before production sign-off

- [ ] Staging browser proof: admin execute + customer email + continuation landing
- [ ] Stripe webhook completes after continuation checkout
- [ ] No duplicate subscription created on recovery retry
- [ ] Fleet metrics endpoint returns sensible counters after test runs

## Known limits

- Fleet metrics mix global counters with recent-event sampling (30-day window).
- `VERIFIED_OPERATIONALLY` requires staging evidence — unit tests alone are insufficient.

## Do not regress

- Recover onboarding override alone does **not** constitute recovery complete.
- Recovery execute requires step-up, reason, and confirmation token.
"""
    (OUT / "watchlist.md").write_text(watchlist, encoding="utf-8")

    print(f"Bundle written to {OUT} (run_id={run_id}, tests={'PASS' if regression['passed'] else 'FAIL'})")
    return 0 if regression["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
