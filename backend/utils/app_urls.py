"""
Canonical application and API base URLs for Pleerity.

- User-facing links: get_app_base_url() only.
- Backend absolute URLs (webhooks, download links, tracking pixels): get_api_base_url() only.

Legacy env vars (FRONTEND_URL, FRONTEND_PUBLIC_URL, PUBLIC_APP_URL, PORTAL_BASE_URL, BASE_URL,
BACKEND_URL, API_URL) are compatibility inputs only when APP_BASE_URL / API_BASE_URL are unset.
"""
from __future__ import annotations

import os
import logging
from typing import List, Optional, Set, Tuple
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

_CANONICAL_APP_URL = "https://pleerityenterprise.co.uk"
_DEFAULT_API_DEV = "http://localhost:8000"
_DEFAULT_APP_DEV = "http://localhost:3000"


def _strip_base(url: str) -> str:
    return (url or "").strip().rstrip("/")


def _is_localhost(url: str) -> bool:
    u = url.lower()
    return "localhost" in u or u.startswith("127.0.0.1")


def get_app_base_url(*, for_email_links: bool = False) -> str:
    """
    Canonical public web app origin (SPA). No trailing slash.

    Priority: APP_BASE_URL → FRONTEND_PUBLIC_URL → PUBLIC_APP_URL → FRONTEND_URL → PORTAL_BASE_URL.
    If still empty: for_email_links=True → _CANONICAL_APP_URL; else → http://localhost:3000.

    Upgrades bare http to https for non-localhost hosts (email safety).
    """
    raw = (
        (os.getenv("APP_BASE_URL") or "").strip()
        or (os.getenv("FRONTEND_PUBLIC_URL") or "").strip()
        or (os.getenv("PUBLIC_APP_URL") or "").strip()
        or (os.getenv("FRONTEND_URL") or "").strip()
        or (os.getenv("PORTAL_BASE_URL") or "").strip()
    )
    raw = _strip_base(raw)
    if not raw:
        if for_email_links:
            logger.debug(
                "get_app_base_url: no APP_BASE_URL/FRONTEND_* set; using canonical %s",
                _CANONICAL_APP_URL,
            )
            return _CANONICAL_APP_URL
        return _DEFAULT_APP_DEV

    if raw.startswith("http://") and not _is_localhost(raw):
        raw = "https://" + raw.split("://", 1)[1]

    env = (os.getenv("ENVIRONMENT") or os.getenv("ENV") or "").strip().lower()
    if for_email_links and _is_localhost(raw) and env in ("production", "prod"):
        logger.warning(
            "get_app_base_url(for_email_links=True): localhost in production; using %s",
            _CANONICAL_APP_URL,
        )
        return _CANONICAL_APP_URL
    if for_email_links and _is_localhost(raw):
        logger.warning(
            "get_app_base_url(for_email_links=True): localhost; set APP_BASE_URL for production emails."
        )
    return raw


def get_api_base_url() -> str:
    """
    Canonical backend API origin (where /api/* is served). No trailing slash.

    Priority: API_BASE_URL → BACKEND_URL → API_URL → BASE_URL (legacy) → http://localhost:8000
    """
    raw = (
        (os.getenv("API_BASE_URL") or "").strip()
        or (os.getenv("BACKEND_URL") or "").strip()
        or (os.getenv("API_URL") or "").strip()
        or (os.getenv("BASE_URL") or "").strip()
    )
    raw = _strip_base(raw)
    if not raw:
        return _DEFAULT_API_DEV
    return raw


def _origin_key(url: str) -> Optional[str]:
    url = _strip_base(url)
    if not url:
        return None
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    p = urlparse(url)
    if not p.netloc:
        return None
    scheme = p.scheme or "https"
    return f"{scheme}://{p.netloc.lower()}"


def _legacy_app_pairs() -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    for key in (
        "APP_BASE_URL",
        "FRONTEND_PUBLIC_URL",
        "FRONTEND_URL",
        "PUBLIC_APP_URL",
        "PORTAL_BASE_URL",
    ):
        v = (os.getenv(key) or "").strip()
        if v:
            out.append((key, v))
    return out


def validate_url_configuration() -> None:
    """
    Production: fail if multiple legacy app URL vars disagree; fail if resolved app URL is not HTTPS
    (unless localhost). Call after env is loaded. Skipped for PYTEST_RUNNING or SKIP_URL_VALIDATION=1.
    """
    if os.getenv("PYTEST_RUNNING") == "1" or os.getenv("SKIP_URL_VALIDATION", "").strip().lower() in (
        "1",
        "true",
        "yes",
    ):
        return
    env = (os.getenv("ENVIRONMENT") or os.getenv("ENV") or "").strip().lower()
    if env not in ("production", "prod"):
        return

    pairs = _legacy_app_pairs()
    origins: Set[str] = set()
    for _key, val in pairs:
        ok = _origin_key(val)
        if ok:
            origins.add(ok)
    if len(origins) > 1:
        raise RuntimeError(
            "URL configuration error: multiple distinct app origins in env. "
            "Set APP_BASE_URL to a single canonical HTTPS origin and remove or align "
            "FRONTEND_URL, FRONTEND_PUBLIC_URL, PUBLIC_APP_URL, PORTAL_BASE_URL. "
            f"Conflicting origins: {sorted(origins)}"
        )

    app = get_app_base_url(for_email_links=True)
    if not _is_localhost(app) and not app.lower().startswith("https://"):
        raise RuntimeError(
            f"Production app URL must use HTTPS (got {app!r}). Set APP_BASE_URL=https://..."
        )

    logger.info("URL validation OK: app_base=%s api_base=%s", app, get_api_base_url())
