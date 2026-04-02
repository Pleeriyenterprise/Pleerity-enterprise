#!/usr/bin/env python3
"""Run the production-surface pytest allowlist (Phase 5.3).

Covers: client portal, admin, plan registry, notifications, onboarding (intake),
billing (subscription gating, document packs), email P0, provisioning, pending
payment recovery, compliance scoring, certificate expiry, document generation.

REF-PRODTEST-SURFACE-001 — paths are relative to backend/ (this script's parent).
CI: require MongoDB (MONGO_URL / DB_NAME; conftest defaults for local). Full `pytest tests`
still skips quarantined CMS/blog/experimental modules unless PYTEST_RUN_QUARANTINED=1.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent

_EXTRA = [
    "tests/test_plan_registry_gating.py",
    "tests/test_notification_bypass_governance.py",
    "tests/test_notification_preferences_enforcement.py",
    "tests/test_notification_orchestrator.py",
    "tests/test_enterprise_notification.py",
    "tests/test_onboarding_email_governance_unit.py",
    "tests/test_stripe_webhook_route_behavior.py",
    "tests/test_entitlements_context.py",
    "tests/test_webhook_security_guards.py",
    "tests/test_orders_public_status_gate.py",
    "tests/test_portal_setup_status.py",
    # Phase 5.3 — business-critical journeys
    "tests/test_intake_wizard.py",
    "tests/test_intake_uploads.py",
    "tests/test_subscription_state_gating_integration.py",
    "tests/test_document_pack_purchase_flow.py",
    "tests/test_email_reliability_p0.py",
    "tests/test_provisioning_reliability.py",
    "tests/test_provisioning_hardening.py",
    "tests/test_provisioning_jobs_idempotency.py",
    "tests/test_pending_payment_recovery.py",
    "tests/test_compliance_scoring_enterprise.py",
    "tests/test_compliance_score_golden.py",
    "tests/test_compliance_score_document_flows.py",
    "tests/test_compliance_sla_monitor.py",
    "tests/test_certificate_expiry_tracking.py",
    "tests/test_document_generation_guardrails.py",
    "tests/test_owner_admin_governance.py",
    "tests/test_production_cross_flow_smoke.py",
]


def _paths() -> list[str]:
    tests = BACKEND_ROOT / "tests"
    admin = sorted(tests.glob("test_admin_*.py"))
    client = sorted(tests.glob("test_client_*.py"))
    out = [str(p.relative_to(BACKEND_ROOT)).replace("\\", "/") for p in admin + client]
    out.extend(_EXTRA)
    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("pytest_args", nargs=argparse.REMAINDER, help="passed through to pytest (use -- ...)")
    args = p.parse_args()
    paths = _paths()
    tail = args.pytest_args
    if tail and tail[0] == "--":
        tail = tail[1:]
    cmd = [sys.executable, "-m", "pytest", *paths, *tail]
    return subprocess.call(cmd, cwd=str(BACKEND_ROOT))


if __name__ == "__main__":
    raise SystemExit(main())
