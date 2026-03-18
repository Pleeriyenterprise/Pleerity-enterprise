"""
Backward-compatible aliases for URL resolution.

All new code should import from utils.app_urls (get_app_base_url, get_api_base_url).
"""
from utils.app_urls import get_app_base_url

_CANONICAL_FRONTEND_URL = "https://pleerityenterprise.co.uk"


def get_frontend_base_url() -> str:
    """Password reset, activation, invitation links (HTTPS in production)."""
    return get_app_base_url(for_email_links=True)


def get_public_app_url(for_email_links: bool = False) -> str:
    """Same as get_app_base_url; for_email_links mirrors app_urls behaviour."""
    return get_app_base_url(for_email_links=for_email_links)
