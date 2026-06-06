"""Regression: frontend auth token drift and centralized admin API usage."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FRONTEND_SRC = ROOT / "frontend" / "src"

LEGACY_TOKEN_PATTERN = re.compile(
    r"""localStorage\.getItem\(\s*['"]token['"]\s*\)"""
)
MANUAL_BEARER_PATTERN = re.compile(
    r"""Authorization['"]\s*:\s*[`'"]Bearer\s*\$\{localStorage"""
)


def _iter_source_files():
    for path in FRONTEND_SRC.rglob("*"):
        if path.suffix not in {".js", ".jsx", ".ts", ".tsx"}:
            continue
        if "node_modules" in path.parts:
            continue
        yield path


def test_no_legacy_token_localstorage_reads():
    """Admin/marketing pages must not read legacy 'token' key."""
    drift = []
    for path in _iter_source_files():
        text = path.read_text(encoding="utf-8")
        if LEGACY_TOKEN_PATTERN.search(text):
            drift.append(str(path.relative_to(ROOT)).replace("\\", "/"))
    assert drift == [], f"Legacy token drift in: {drift}"


def test_auth_storage_module_exists():
    path = FRONTEND_SRC / "api" / "authStorage.js"
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "AUTH_TOKEN_KEY" in text
    assert "getAuthToken" in text


def test_admin_api_newsletter_list_uses_central_client():
    client = (FRONTEND_SRC / "api" / "client.js").read_text(encoding="utf-8")
    assert "listNewsletterSubscribers" in client
    assert "/admin/newsletter/subscribers" in client
    newsletter_page = (FRONTEND_SRC / "pages" / "AdminNewsletterPage.jsx").read_text(encoding="utf-8")
    assert "adminAPI.listNewsletterSubscribers" in newsletter_page
    assert "getItem('token')" not in newsletter_page


def test_admin_fetch_state_panel_exists():
    path = FRONTEND_SRC / "components" / "admin" / "AdminFetchStatePanel.jsx"
    assert path.is_file()


def test_auth_token_inventory_snapshot():
    """Document remaining manual Bearer usage for governance (allowlist known legacy)."""
    manual = []
    for path in _iter_source_files():
        rel = str(path.relative_to(ROOT)).replace("\\", "/")
        if rel.endswith("api/client.js"):
            continue
        text = path.read_text(encoding="utf-8")
        if MANUAL_BEARER_PATTERN.search(text):
            manual.append(rel)
    # Contact/submission pages still use manual fetch+auth_token — tracked, not blocking newsletter fix.
    allowed = {
        "frontend/src/pages/AdminContactEnquiriesPage.jsx",
        "frontend/src/pages/AdminSubmissionDetailPage.jsx",
        "frontend/src/pages/AdminBlogPage.js",
        "frontend/src/pages/AdminServiceCataloguePage.js",
        "frontend/src/pages/AssistantPage.js",
        "frontend/src/pages/ClientProvideInfoPage.js",
        "frontend/src/components/admin/orders/DocumentPreviewModal.jsx",
        "frontend/src/pages/AdminOrdersPage.old.js",
        "frontend/src/api/ordersApi.js",
    }
    unexpected = sorted(set(manual) - allowed)
    assert unexpected == [], f"Unexpected manual Bearer construction: {unexpected}"
