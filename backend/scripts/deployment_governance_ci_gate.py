#!/usr/bin/env python3
"""
CI gate: deployment governance — secrets, staging URLs in app code, production config drift.

Exit 0 on pass, 1 on failure.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FRONTEND_SRC = ROOT / "frontend" / "src"
BACKEND = ROOT / "backend"

SECRET_PATTERNS = [
    (re.compile(r"sk_live_[A-Za-z0-9]{20,}"), "Stripe live secret key"),
    (re.compile(r"pk_live_[A-Za-z0-9]{20,}"), "Stripe live publishable key"),
    (re.compile(r"whsec_[A-Za-z0-9]{20,}"), "Stripe webhook secret"),
    (re.compile(r"mongodb\+srv://[^:]+:[^@]+@"), "MongoDB connection string with credentials"),
]

# Application source only — exclude tests, audit docs, tmp scripts.
APP_GLOBS = [
    "frontend/src/**/*.js",
    "frontend/src/**/*.jsx",
    "backend/routes/**/*.py",
    "backend/services/**/*.py",
    "backend/utils/**/*.py",
    "backend/auth.py",
    "backend/server.py",
]

STAGING_URL_IN_PROD_CODE = re.compile(
    r"https?://pleerity-enterprise\.onrender\.com",
    re.IGNORECASE,
)

FRONTEND_STAGING_URL_ALLOWLIST = {
    "frontend/src/setupProxy.js",
}


def _rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def check_committed_secrets() -> list[str]:
    errors: list[str] = []
    scan_roots = [
        ROOT / "frontend" / "src",
        ROOT / "backend" / "routes",
        ROOT / "backend" / "services",
        ROOT / "backend" / "utils",
        ROOT / "backend" / "auth.py",
        ROOT / "backend" / "server.py",
        ROOT / "render.yaml",
        ROOT / "render.staging.yaml",
        ROOT / "render.production.yaml",
    ]
    known_secret_files = {
        "STRIPE_TEST_INFO.md",
        "memory/PRD.md",
    }
    for base in scan_roots:
        paths = [base] if base.is_file() else list(base.rglob("*"))
        for path in paths:
            if not path.is_file():
                continue
            rel = _rel(path)
            if any(rel.endswith(k) or k in rel for k in known_secret_files):
                continue
            if "docs/audit" in rel or "/tests/" in rel or rel.startswith("backend/tests"):
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for pattern, label in SECRET_PATTERNS:
                if pattern.search(text):
                    errors.append(f"{rel}: possible committed {label}")
    return errors


def check_staging_urls_in_frontend() -> list[str]:
    errors: list[str] = []
    if not FRONTEND_SRC.is_dir():
        return errors
    for path in FRONTEND_SRC.rglob("*"):
        if path.suffix not in (".js", ".jsx", ".ts", ".tsx"):
            continue
        rel = _rel(path)
        if rel in FRONTEND_STAGING_URL_ALLOWLIST:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if STAGING_URL_IN_PROD_CODE.search(text):
            errors.append(f"{rel}: hardcoded staging API URL (use REACT_APP_BACKEND_URL)")
        if 'REACT_APP_BACKEND_URL' in text and "pleerity-enterprise.onrender.com" in text:
            errors.append(f"{rel}: hardcoded staging API in REACT_APP_BACKEND_URL fallback")
    return errors


def check_render_production_blueprint() -> list[str]:
    errors: list[str] = []
    prod = ROOT / "render.production.yaml"
    if not prod.is_file():
        return errors
    text = prod.read_text(encoding="utf-8", errors="ignore").lower()
    if "pleerity_staging" in text:
        errors.append("render.production.yaml: must not reference pleerity_staging")
    if "stripe_mode" in text and "test" in text.split("stripe_mode", 1)[-1][:40]:
        errors.append("render.production.yaml: STRIPE_MODE must not be test")
    return errors


def check_production_blueprints_lifecycle_active() -> list[str]:
    """Fail if any production Render blueprint enables lifecycle active enforcement."""
    errors: list[str] = []
    candidates = [
        ROOT / "render.production.yaml",
        ROOT / "render.yaml",
    ]
    patterns = [
        (
            re.compile(
                r"lifecycle_aware_confirm[\s\S]{0,120}?\bactive\b",
                re.IGNORECASE,
            ),
            "LIFECYCLE_AWARE_CONFIRM must not be active in production blueprint",
        ),
        (
            re.compile(
                r"lifecycle_aware_extraction[\s\S]{0,120}?\bactive\b",
                re.IGNORECASE,
            ),
            "LIFECYCLE_AWARE_EXTRACTION must not be active in production blueprint",
        ),
        (
            re.compile(
                r"lifecycle_aware_scoring[\s\S]{0,120}?\bactive\b",
                re.IGNORECASE,
            ),
            "LIFECYCLE_AWARE_SCORING must not be active in production blueprint",
        ),
    ]
    for path in candidates:
        if not path.is_file():
            continue
        rel = _rel(path)
        if path.name != "render.production.yaml" and "production" not in path.read_text(
            encoding="utf-8", errors="ignore"
        ).lower():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern, message in patterns:
            if pattern.search(text):
                errors.append(f"{rel}: {message}")
    return errors


def main() -> int:
    failures: list[str] = []
    failures.extend(check_committed_secrets())
    failures.extend(check_staging_urls_in_frontend())
    failures.extend(check_render_production_blueprint())
    failures.extend(check_production_blueprints_lifecycle_active())

    if failures:
        print("DEPLOYMENT GOVERNANCE CI GATE: FAIL")
        for item in failures:
            print(f"  - {item}")
        return 1

    print("DEPLOYMENT GOVERNANCE CI GATE: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
