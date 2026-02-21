"""
Canonical public frontend base URL for activation/reset links and redirects.
Use get_public_app_url() so emails never point to localhost in production.
"""
import os
import logging

logger = logging.getLogger(__name__)


def get_public_app_url(for_email_links: bool = False) -> str:
    """
    Return normalized public frontend base URL (no trailing slash).
    Fallback order: PUBLIC_APP_URL, FRONTEND_URL, VERCEL_URL (as https), RENDER_EXTERNAL_URL.

    Rules:
    - Result is stripped and trailing slash removed.
    - In production (non-localhost), https is enforced for the returned value when possible.
    - If for_email_links=True and no valid public URL is available (missing or localhost in prod),
      raises ValueError so callers do not send broken links.

    Returns:
        Base URL, e.g. https://app.example.com
    """
    raw = (
        (os.getenv("PUBLIC_APP_URL") or "").strip()
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
                "PUBLIC_APP_URL or FRONTEND_URL must be set for activation email links. "
                "Set PUBLIC_APP_URL=https://<your-frontend-domain> (no trailing slash)."
            )
        return "http://localhost:3000"
    if raw.startswith("http://") and "localhost" not in raw:
        raw = "https://" + raw.split("://", 1)[1]
    if for_email_links and "localhost" in raw.lower():
        env = (os.getenv("ENVIRONMENT") or os.getenv("ENV") or "").strip().lower()
        if env in ("production", "prod"):
            raise ValueError(
                "PUBLIC_APP_URL must be your public frontend URL in production (no localhost). "
                "Set PUBLIC_APP_URL=https://<your-frontend-domain>"
            )
        logger.warning(
            "get_public_app_url(for_email_links=True): using localhost; set PUBLIC_APP_URL for production emails."
        )
    return raw
