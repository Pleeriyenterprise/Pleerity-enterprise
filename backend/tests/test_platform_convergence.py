"""ILP-10 platform convergence verification tests."""
from __future__ import annotations

import ast
import os
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
ROUTES_DIR = BACKEND_ROOT / "routes"
SERVICES_DIR = BACKEND_ROOT / "services"

AUTHORITY_MODULES = [
    "account_lifecycle_state_resolver.py",
    "account_lifecycle_runtime_contract.py",
    "account_capability_enforcement.py",
    "account_session_runtime_service.py",
    "account_background_runtime_authority.py",
    "account_lifecycle_response_authority.py",
    "account_customer_communication_authority.py",
    "account_lifecycle_reactivation_authority.py",
    "account_lifecycle_event_authority.py",
]

OBSOLETE_MODULES = [
    "plan_gating.py",
    "feature_entitlement.py",
]

LEGACY_IMPORTS = (
    "plan_gating",
    "feature_entitlement",
    "plan_gating_service",
    "feature_entitlement_service",
)


def _route_py_files():
    return sorted(ROUTES_DIR.glob("*.py"))


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_authority_stack_modules_exist():
    for name in AUTHORITY_MODULES:
        assert (SERVICES_DIR / name).is_file(), name


def test_obsolete_gating_modules_removed():
    for name in OBSOLETE_MODULES:
        assert not (SERVICES_DIR / name).is_file(), f"{name} should be removed"


def test_customer_routes_avoid_obsolete_gating_imports():
    offenders = []
    for path in _route_py_files():
        text = _read(path)
        for legacy in LEGACY_IMPORTS:
            if legacy in text:
                offenders.append(f"{path.name}: {legacy}")
    assert not offenders, offenders


def test_client_context_guard_uses_runtime_contract():
    text = _read(BACKEND_ROOT / "middleware" / "__init__.py")
    guard_section = text.split("_client_context_guard")[1].split("async def client_route_guard")[0]
    assert "resolve_runtime_contract_for_client" in guard_section
    assert "emit_events=False" in guard_section
    assert "compute_canonical_entitlement_state" not in guard_section
    assert "client_billing.find_one" in guard_section


def test_middleware_avoids_subscription_access_blocked():
    text = _read(BACKEND_ROOT / "middleware" / "__init__.py")
    assert "SUBSCRIPTION_ACCESS_BLOCKED" not in text


@pytest.mark.parametrize("module", AUTHORITY_MODULES)
def test_authority_modules_are_importable(module):
    mod = module.replace(".py", "")
    __import__(f"services.{mod}")
