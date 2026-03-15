"""
Canonical public frontend base URL for activation/reset links and redirects.
Use get_frontend_base_url() for ALL email links (set-password, activation). No other code should build frontend links directly.

Preferred source of truth: FRONTEND_URL=https://pleerityenterprise.co.uk (or FRONTEND_PUBLIC_URL for email links).
We do NOT use VERCEL_URL or RENDER_EXTERNAL_URL for customer-facing links (they are deployment hostnames, not the custom domain).
"""
import os
import logging

logger = logging.getLogger(__name__)

# Canonical production frontend URL when no env is set (avoids sending users to Vercel default domain).
_CANONICAL_FRONTEND_URL = "https://pleerityenterprise.co.uk"


def get_frontend_base_url() -> str:
    """
    Single helper for frontend base URL used in email links (set-password, activation).
    Reads FRONTEND_PUBLIC_URL, then PUBLIC_APP_URL, then FRONTEND_URL. Never uses VERCEL_URL.
    If none set, returns _CANONICAL_FRONTEND_URL so password reset and activation links use the custom domain.
    """
    return get_public_app_url(for_email_links=True)


def get_public_app_url(for_email_links: bool = False) -> str:
    """
    Return normalized public frontend base URL (no trailing slash).
    Single source of truth for ALL email links (activation, set-password).
    Fallback order: FRONTEND_PUBLIC_URL, PUBLIC_APP_URL, FRONTEND_URL. Then for_email_links -> _CANONICAL_FRONTEND_URL, else localhost.

    We do NOT use VERCEL_URL or RENDER_EXTERNAL_URL so customer-facing links never point at the default Vercel deployment URL.

    Returns:
        Base URL, e.g. https://pleerityenterprise.co.uk
    """
    raw = (
        (os.getenv("FRONTEND_PUBLIC_URL") or "").strip()
        or (os.getenv("PUBLIC_APP_URL") or "").strip()
        or (os.getenv("FRONTEND_URL") or "").strip()
        or ""
    )
    raw = (raw or "").strip().rstrip("/")
    if not raw:
        if for_email_links:
            logger.info(
                "get_public_app_url: no FRONTEND_URL/FRONTEND_PUBLIC_URL set; using canonical %s for email links",
                _CANONICAL_FRONTEND_URL,
            )
            return _CANONICAL_FRONTEND_URL
        return "http://localhost:3000"
    if raw.startswith("http://") and "localhost" not in raw:
        raw = "https://" + raw.split("://", 1)[1]
    if for_email_links and "localhost" in raw.lower():
        env = (os.getenv("ENVIRONMENT") or os.getenv("ENV") or "").strip().lower()
        if env in ("production", "prod"):
            logger.warning(
                "get_public_app_url(for_email_links=True): localhost in production; using canonical %s",
                _CANONICAL_FRONTEND_URL,
            )
            return _CANONICAL_FRONTEND_URL
        logger.warning(
            "get_public_app_url(for_email_links=True): using localhost; set FRONTEND_PUBLIC_URL for production emails."
        )
    return raw
