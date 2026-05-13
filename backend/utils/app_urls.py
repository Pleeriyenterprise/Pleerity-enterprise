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
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import quote, urlparse

logger = logging.getLogger(__name__)


def _running_on_render() -> bool:
    """True on Render.com (web or worker). RENDER_SERVICE_ID is always set; RENDER may be absent in some setups."""
    if (os.getenv("RENDER") or "").strip().lower() in ("true", "1", "yes"):
        return True
    return bool((os.getenv("RENDER_SERVICE_ID") or "").strip())


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


def _app_origin_for_conflict_check(url: str) -> Optional[str]:
    """
    Same logical public app host must not count as multiple origins (e.g. http vs https
    on pleerityenterprise.co.uk), or production deploy fails when legacy vars mix schemes.
    """
    url = _strip_base(url)
    if not url:
        return None
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    p = urlparse(url)
    if not p.netloc:
        return None
    host = p.netloc.lower()
    if _is_localhost(url):
        return f"{(p.scheme or 'http')}://{host}"
    return f"https://{host}"


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
    On Render (RENDER or RENDER_SERVICE_ID) we log CRITICAL and continue instead of raising so the process can bind to PORT.
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

    _on_render = _running_on_render()

    pairs = _legacy_app_pairs()
    origins: Set[str] = set()
    for _key, val in pairs:
        ok = _app_origin_for_conflict_check(val)
        if ok:
            origins.add(ok)
    if len(origins) > 1:
        msg = (
            "URL configuration error: multiple distinct app origins in env. "
            "Set APP_BASE_URL to a single canonical HTTPS origin and remove or align "
            "FRONTEND_URL, FRONTEND_PUBLIC_URL, PUBLIC_APP_URL, PORTAL_BASE_URL. "
            f"Conflicting origins: {sorted(origins)}"
        )
        if _on_render:
            logger.critical("%s (RENDER: continuing so service can bind to PORT)", msg)
            return
        raise RuntimeError(msg)

    app = get_app_base_url(for_email_links=True)
    if not _is_localhost(app) and not app.lower().startswith("https://"):
        msg = f"Production app URL must use HTTPS (got {app!r}). Set APP_BASE_URL=https://..."
        if _on_render:
            logger.critical("%s (RENDER: continuing so service can bind to PORT)", msg)
            return
        raise RuntimeError(msg)

    logger.info("URL validation OK: app_base=%s api_base=%s", app, get_api_base_url())


def client_portal_requirements_list_url(app_base: str, *, status: Optional[str] = None) -> str:
    """
    Client SPA URL for the Requirements list.

    ``status`` must match ``RequirementsPage`` query semantics (e.g. ``OVERDUE_OR_MISSING``, ``DUE_SOON``).
    """
    b = _strip_base(app_base)
    if not b:
        return "/requirements"
    if status:
        st = quote(str(status).strip(), safe="")
        return f"{b}/requirements?status={st}"
    return f"{b}/requirements"


def client_portal_documents_evidence_url(
    app_base: str, *, property_id: str, requirement_id: str = ""
) -> str:
    """
    Documents vault with property (and optional requirement) pre-selection — supported by ``DocumentsPage`` query params.
    """
    b = _strip_base(app_base)
    pid = quote(str(property_id or "").strip(), safe="")
    if not pid:
        return f"{b}/documents" if b else "/documents"
    if requirement_id:
        rid = quote(str(requirement_id).strip(), safe="")
        return f"{b}/documents?property_id={pid}&requirement_id={rid}"
    return f"{b}/documents?property_id={pid}"


def compliance_alert_email_portal_url(app_base: str, affected_properties: Optional[List[Dict[str, Any]]]) -> str:
    """
    Primary CTA for COMPLIANCE_ALERT emails: land on Requirements with a filter that matches the worst
    dashboard indicator in the batch (no new routes; portal remains authoritative).
    """
    b = _strip_base(app_base)
    if not b:
        return "/dashboard"
    if not affected_properties:
        return f"{b}/dashboard"
    worst = -1
    worst_label = ""
    rank = {"GREEN": 0, "AMBER": 1, "RED": 2}
    for row in affected_properties:
        st = str(row.get("new_status") or "").upper()
        sev = rank.get(st, -1)
        if sev > worst:
            worst = sev
            worst_label = st
    if worst_label == "RED":
        return client_portal_requirements_list_url(b, status="OVERDUE_OR_MISSING")
    if worst_label == "AMBER":
        return client_portal_requirements_list_url(b, status="DUE_SOON")
    return f"{b}/dashboard"
