"""LEGACY-RESIDUE-VERIFICATION-01 — repository-wide legacy authority residue checks."""
from __future__ import annotations

from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
FRONTEND_SRC = REPO_ROOT / "frontend" / "src"
ROUTES_DIR = BACKEND_ROOT / "routes"
SERVICES_DIR = BACKEND_ROOT / "services"

PRODUCTION_ROUTE_FILES = sorted(ROUTES_DIR.glob("*.py"))
PRODUCTION_FRONTEND_PAGES = sorted((FRONTEND_SRC / "pages").glob("*.js"))
PRODUCTION_FRONTEND_COMPONENTS = sorted((FRONTEND_SRC / "components").rglob("*.jsx"))
PRODUCTION_FRONTEND_COMPONENTS += sorted((FRONTEND_SRC / "components").rglob("*.js"))

LEGACY_FRONTEND_PERMISSION_PATTERNS = (
    "useEntitlements",
    "EntitlementsContext",
    "hasFeature(",
)

LEGACY_ROUTE_PERMISSION_PATTERNS = (
    "require_feature(",
    "enforce_feature(",
    "from services.entitlement_access",
    "plan_gating",
    "feature_entitlement",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _customer_frontend_sources():
    for path in PRODUCTION_FRONTEND_PAGES:
        name = path.name
        if "Admin" in name or name.startswith("admin"):
            continue
        if ".test." in name or ".capability.test." in name:
            continue
        yield path
    for path in PRODUCTION_FRONTEND_COMPONENTS:
        if "admin" in path.parts:
            continue
        if ".test." in path.name:
            continue
        yield path


def test_customer_frontend_pages_avoid_legacy_entitlement_permissions():
    offenders = []
    for path in _customer_frontend_sources():
        text = _read(path)
        for pattern in LEGACY_FRONTEND_PERMISSION_PATTERNS:
            if pattern in text:
                offenders.append(f"{path.relative_to(REPO_ROOT)}: {pattern}")
    assert not offenders, offenders


def test_customer_routes_avoid_legacy_feature_gating():
    offenders = []
    for path in PRODUCTION_ROUTE_FILES:
        if path.name.startswith("admin"):
            continue
        text = _read(path)
        for pattern in LEGACY_ROUTE_PERMISSION_PATTERNS:
            if pattern in text:
                offenders.append(f"{path.name}: {pattern}")
    assert not offenders, offenders


def test_branding_resolver_uses_runtime_capability_not_enforce_feature():
    text = _read(SERVICES_DIR / "branding_resolver_service.py")
    assert "CAP_BRANDING_WHITE_LABEL" in text
    assert "enforce_feature(" not in text


def test_feature_gating_middleware_marked_obsolete():
    text = _read(BACKEND_ROOT / "middleware" / "feature_gating.py")
    assert "OBSOLETE" in text
    assert "require_feature" in text


def test_obsolete_gating_modules_removed():
    for name in ("plan_gating.py", "feature_entitlement.py"):
        assert not (SERVICES_DIR / name).is_file(), name


def test_app_does_not_mount_entitlements_provider():
    app_src = _read(FRONTEND_SRC / "App.js")
    assert "EntitlementsContext" not in app_src
    assert "EntitlementsProvider" not in app_src
