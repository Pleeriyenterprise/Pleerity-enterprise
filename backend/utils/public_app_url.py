"""
Canonical public frontend base URL for activation/reset links and redirects.
Use get_frontend_base_url() for ALL email links (set-password, activation). No other code should build frontend links directly.
"""
import os
import logging

logger = logging.getLogger(__name__)


def get_frontend_base_url() -> str:
    """
    Single helper for frontend base URL used in email links (set-password, activation).
    Reads FRONTEND_PUBLIC_URL (then PUBLIC_APP_URL, FRONTEND_URL, VERCEL_URL, RENDER_EXTERNAL_URL).
    Strips trailing slash. Raises clear error if missing when building email links (except local dev).
    """
    return get_public_app_url(for_email_links=True)


def get_public_app_url(for_email_links: bool = False) -> str:
    """
    Return normalized public frontend base URL (no trailing slash).
    Single source of truth for ALL email links (activation, set-password); never backend host or localhost in production.
    Fallback order: FRONTEND_PUBLIC_URL, PUBLIC_APP_URL, FRONTEND_URL, VERCEL_URL (as https), RENDER_EXTERNAL_URL.

    Rules:
    - Result is stripped and trailing slash removed.
    - In production (non-localhost), https is enforced for the returned value when possible.
    - If for_email_links=True and no valid public URL is available (missing or localhost in prod),
      raises ValueError so callers do not send broken links.

    Returns:
        Base URL, e.g. https://app.example.com
    """
    raw = (
        (os.getenv("FRONTEND_PUBLIC_URL") or "").strip()
        or (os.getenv("PUBLIC_APP_URL") or "").strip()
        or (os.getenv("FRONTEND_URL") or "").strip()
        or ""
    )
    if not raw and os.getenv("VERCEL_URL"):
        raw = f"https://{os.getenv('VERCEL_URL', '').strip()}"
    if not raw and os.getenv("RENDER_EXTERNAL_URL"):
        raw = (os.getenv("RENDER_EXTERNAL_URL") or "").strip()
    raw = (raw or "").strip().rstrip("/")
    if not raw:
        if for_email_links:
            raise ValueError(
                "FRONTEND_PUBLIC_URL or PUBLIC_APP_URL or FRONTEND_URL must be set for activation email links. "
                "Set FRONTEND_PUBLIC_URL=https://<your-frontend-domain> (no trailing slash)."
            )
        return "http://localhost:3000"
    if raw.startswith("http://") and "localhost" not in raw:
        raw = "https://" + raw.split("://", 1)[1]
    if for_email_links and "localhost" in raw.lower():
        env = (os.getenv("ENVIRONMENT") or os.getenv("ENV") or "").strip().lower()
        if env in ("production", "prod"):
            raise ValueError(
                "FRONTEND_PUBLIC_URL (or PUBLIC_APP_URL) must be your public frontend URL in production (no localhost). "
                "Set FRONTEND_PUBLIC_URL=https://<your-frontend-domain>"
            )
        logger.warning(
            "get_public_app_url(for_email_links=True): using localhost; set FRONTEND_PUBLIC_URL for production emails."
        )
    return raw
