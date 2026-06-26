"""
Deployment tier guardrails — refuse unsafe staging/production environment pairings at boot.

Set DEPLOYMENT_TIER=staging|production on each Render service for explicit classification.
When unset, tier is inferred from ENVIRONMENT and DB_NAME (see resolve_deployment_tier).

Emergency bypass (not for production): SKIP_DEPLOYMENT_GUARD=1
"""
from __future__ import annotations

import logging
import os
from typing import List, Optional, Tuple
from urllib.parse import urlparse

from auth import JWT_SECRET_DEFAULT
from utils.app_urls import get_api_base_url, get_app_base_url

logger = logging.getLogger(__name__)

PRODUCTION_DB_NAME = "pleerity_production"
STAGING_DB_NAME = "pleerity_staging"

# Host fragments that must not appear in production APP/API URLs.
_STAGING_URL_MARKERS = (
    "localhost",
    "127.0.0.1",
    "staging.",
    "-staging.",
    "pleerity-enterprise.onrender.com",
    ".vercel.app",
)

# Canonical production hosts — must not be used on staging tier (refuse).
_PRODUCTION_APP_HOSTS = (
    "pleerityenterprise.co.uk",
    "www.pleerityenterprise.co.uk",
)
_PRODUCTION_API_HOSTS = (
    "api.pleerityenterprise.co.uk",
)


class DeploymentEnvironmentError(RuntimeError):
    """Fatal deployment configuration mismatch."""


def _skipped() -> bool:
    if os.getenv("PYTEST_RUNNING") == "1":
        return True
    return os.getenv("SKIP_DEPLOYMENT_GUARD", "").strip().lower() in ("1", "true", "yes")


def _env_name() -> str:
    return (os.getenv("ENVIRONMENT") or os.getenv("ENV") or "").strip().lower()


def resolve_deployment_tier() -> str:
    """
    Return 'production', 'staging', or 'unknown'.

    Explicit DEPLOYMENT_TIER wins. When unset, DB_NAME is authoritative over ENVIRONMENT
    so the legacy combined stack (ENVIRONMENT=production + pleerity_staging) stays staging
    until DEPLOYMENT_TIER=production is set explicitly on a production service.
    """
    explicit = (os.getenv("DEPLOYMENT_TIER") or "").strip().lower()
    if explicit in ("production", "staging"):
        return explicit

    db = (os.getenv("DB_NAME") or "").strip().lower()
    if db == PRODUCTION_DB_NAME:
        return "production"
    if "staging" in db or db == STAGING_DB_NAME:
        return "staging"

    env = _env_name()
    if env in ("production", "prod"):
        return "production"
    if env in ("staging", "preview"):
        return "staging"

    return "unknown"


def _host_from_url(url: str) -> str:
    raw = (url or "").strip()
    if not raw:
        return ""
    if not raw.startswith(("http://", "https://")):
        raw = f"https://{raw}"
    return (urlparse(raw).netloc or "").lower()


def _url_has_staging_markers(url: str) -> bool:
    host = _host_from_url(url)
    combined = f"{url} {host}".lower()
    return any(marker in combined for marker in _STAGING_URL_MARKERS)


def _host_is_exact(host: str, allowed: Tuple[str, ...]) -> bool:
    """Exact host match only — staging.pleerityenterprise.co.uk is not production."""
    h = (host or "").lower()
    return h in allowed


def _collect_production_violations() -> List[str]:
    errors: List[str] = []

    db_name = (os.getenv("DB_NAME") or "").strip()
    if not db_name:
        errors.append("DB_NAME is not set.")
    elif "staging" in db_name.lower():
        errors.append(f"Production must not use a staging database (DB_NAME={db_name!r}).")

    stripe_mode = (os.getenv("STRIPE_MODE") or "").strip().lower()
    if stripe_mode != "live":
        errors.append(
            f"Production requires STRIPE_MODE=live (got {stripe_mode!r}). "
            "Set STRIPE_MODE=live and live Stripe keys in the production Render service."
        )

    app_url = get_app_base_url(for_email_links=True)
    if _url_has_staging_markers(app_url):
        errors.append(f"APP_BASE_URL resolves to a staging/dev host ({app_url!r}). Set APP_BASE_URL to the production frontend.")

    api_url = get_api_base_url()
    if _url_has_staging_markers(api_url):
        errors.append(f"API_BASE_URL resolves to a staging/dev host ({api_url!r}). Set API_BASE_URL to the production API.")

    jwt_secret = (os.getenv("JWT_SECRET") or "").strip()
    if not jwt_secret or jwt_secret == JWT_SECRET_DEFAULT:
        errors.append(
            "JWT_SECRET must be set to a non-default value in production. "
            "Set the JWT_SECRET environment variable to a secure random string."
        )

    return errors


def _collect_staging_violations(*, tier_explicit: bool) -> Tuple[List[str], List[str]]:
    """Return (fatal_errors, warnings)."""
    fatal: List[str] = []
    warnings: List[str] = []

    db_name = (os.getenv("DB_NAME") or "").strip().lower()
    if db_name == PRODUCTION_DB_NAME:
        fatal.append(
            f"Staging must not use production database {PRODUCTION_DB_NAME!r}. "
            f"Use DB_NAME={STAGING_DB_NAME!r} on the staging Render service."
        )

    stripe_mode = (os.getenv("STRIPE_MODE") or "").strip().lower()
    if stripe_mode == "live":
        msg = (
            "Staging must not use STRIPE_MODE=live. Use STRIPE_MODE=test and test Stripe keys on staging."
        )
        if tier_explicit:
            fatal.append(msg)
        else:
            warnings.append(msg + " Set DEPLOYMENT_TIER=staging once STRIPE_MODE=test is configured.")

    app_url = get_app_base_url(for_email_links=True)
    app_host = _host_from_url(app_url)
    from utils.app_urls import is_dead_staging_app_host

    raw_app_env = (os.getenv("APP_BASE_URL") or "").strip()
    if is_dead_staging_app_host(raw_app_env or app_url):
        fatal.append(
            "APP_BASE_URL uses retired Vercel deployment pleerity-enterprise-9jig.vercel.app. "
            "Set APP_BASE_URL to https://pleerity-enterprise-9jjg.vercel.app (canonical staging frontend)."
        )
    if _host_is_exact(app_host, _PRODUCTION_APP_HOSTS):
        msg = (
            f"Staging APP_BASE_URL points at production frontend ({app_url!r}). "
            "Use a staging frontend host (e.g. staging.pleerityenterprise.co.uk or Vercel preview)."
        )
        if tier_explicit:
            fatal.append(msg)
        else:
            warnings.append(msg + " Set DEPLOYMENT_TIER=staging once staging URLs are configured.")

    api_url = get_api_base_url()
    api_host = _host_from_url(api_url)
    if _host_is_exact(api_host, _PRODUCTION_API_HOSTS):
        msg = (
            f"Staging API_BASE_URL points at production API ({api_url!r}). "
            "Use the staging Render URL (e.g. pleerity-enterprise.onrender.com or staging-api.*)."
        )
        if tier_explicit:
            fatal.append(msg)
        else:
            warnings.append(msg + " Set DEPLOYMENT_TIER=staging once staging API URL is configured.")

    env = _env_name()
    if env in ("production", "prod"):
        warnings.append(
            f"ENVIRONMENT={env!r} on a staging-tier deployment. Prefer ENVIRONMENT=staging and DEPLOYMENT_TIER=staging."
        )

    if not db_name:
        warnings.append("DB_NAME is not set on staging; expected pleerity_staging.")

    return fatal, warnings


def validate_deployment_environment(*, tier: Optional[str] = None) -> str:
    """
    Validate environment for the resolved deployment tier.

    Raises DeploymentEnvironmentError on fatal misconfiguration.
    Returns the tier string ('production', 'staging', or 'unknown').
    """
    if _skipped():
        return tier or resolve_deployment_tier()

    resolved = tier or resolve_deployment_tier()

    if resolved == "production":
        violations = _collect_production_violations()
        if violations:
            msg = "Production deployment guard failed:\n- " + "\n- ".join(violations)
            logger.critical(msg)
            raise DeploymentEnvironmentError(msg)
        logger.info("Deployment guard OK: tier=production DB_NAME=%s STRIPE_MODE=live", os.getenv("DB_NAME"))
        return resolved

    if resolved == "staging":
        tier_explicit = (os.getenv("DEPLOYMENT_TIER") or "").strip().lower() == "staging"
        fatal, warnings = _collect_staging_violations(tier_explicit=tier_explicit)
        for w in warnings:
            logger.warning("Staging deployment guard warning: %s", w)
        if fatal:
            msg = "Staging deployment guard failed:\n- " + "\n- ".join(fatal)
            logger.critical(msg)
            raise DeploymentEnvironmentError(msg)
        logger.info(
            "Deployment guard OK: tier=staging DB_NAME=%s STRIPE_MODE=%s",
            os.getenv("DB_NAME"),
            os.getenv("STRIPE_MODE", "(unset)"),
        )
        return resolved

    logger.warning(
        "Deployment tier unknown (set DEPLOYMENT_TIER=staging|production). "
        "ENVIRONMENT=%s DB_NAME=%s",
        _env_name() or "(unset)",
        os.getenv("DB_NAME") or "(unset)",
    )
    return resolved
