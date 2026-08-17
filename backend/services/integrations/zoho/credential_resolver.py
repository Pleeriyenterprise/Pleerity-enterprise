"""
OAuth credential resolver — determines which credentials belong to each integration.

Adapter → Credential Resolver → OAuth Manager → Zoho OAuth → Access Token

This module resolves credentials only; it does not perform OAuth operations.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Set

from services.integrations.zoho.oauth_credential_registry import (
    LEGACY_REFRESH_TOKEN_ENV_KEY,
    OAuthIntegrationRecord,
    get_oauth_integration_record,
)

logger = logging.getLogger(__name__)

# During migration, legacy ZOHO_REFRESH_TOKEN may only be used without warning for CRM.
LEGACY_REFRESH_TOKEN_MIGRATION_APPROVED_INTEGRATIONS = frozenset({"crm"})

_legacy_warning_emitted: Set[str] = set()


class RefreshTokenSource(str, Enum):
    PER_INTEGRATION = "per_integration"
    LEGACY = "legacy"
    NONE = "none"


@dataclass(frozen=True)
class ResolvedOAuthCredentials:
    integration: str
    client_id: str
    client_secret: str
    refresh_token: str
    refresh_token_source: RefreshTokenSource
    cache_identifier: str
    expected_scope: str
    shared_client_configured: bool
    refresh_token_configured: bool
    credentials_configured: bool

    @property
    def using_legacy_fallback(self) -> bool:
        return self.refresh_token_source == RefreshTokenSource.LEGACY


def _env(name: str) -> str:
    return (os.environ.get(name) or "").strip()


def _resolve_refresh_token(integration: str, record: OAuthIntegrationRecord) -> tuple[str, RefreshTokenSource]:
    per_integration = _env(record.refresh_token_env_key)
    if per_integration:
        return per_integration, RefreshTokenSource.PER_INTEGRATION

    legacy = _env(LEGACY_REFRESH_TOKEN_ENV_KEY)
    if legacy:
        _emit_legacy_warning(integration)
        return legacy, RefreshTokenSource.LEGACY

    return "", RefreshTokenSource.NONE


def _emit_legacy_warning(integration: str) -> None:
    if integration in LEGACY_REFRESH_TOKEN_MIGRATION_APPROVED_INTEGRATIONS:
        return
    if integration in _legacy_warning_emitted:
        return
    _legacy_warning_emitted.add(integration)
    logger.warning(
        "Zoho OAuth: integration '%s' is using deprecated legacy %s. "
        "Set %s before production Zoho rollout. Legacy fallback will be removed.",
        integration,
        LEGACY_REFRESH_TOKEN_ENV_KEY,
        get_oauth_integration_record(integration).refresh_token_env_key
        if get_oauth_integration_record(integration)
        else f"ZOHO_{integration.upper()}_REFRESH_TOKEN",
    )


def resolve_oauth_credentials(integration: str) -> Optional[ResolvedOAuthCredentials]:
    """
    Resolve OAuth credentials for an integration.

    Resolution order:
    1. ZOHO_{INTEGRATION}_REFRESH_TOKEN
    2. Legacy ZOHO_REFRESH_TOKEN (deprecated)
    3. No credentials
    """
    record = get_oauth_integration_record(integration)
    if not record:
        return None

    client_id = _env("ZOHO_CLIENT_ID")
    client_secret = _env("ZOHO_CLIENT_SECRET")
    refresh_token, source = _resolve_refresh_token(integration, record)
    shared_client_configured = bool(client_id and client_secret)
    refresh_token_configured = bool(refresh_token)
    credentials_configured = shared_client_configured and refresh_token_configured

    return ResolvedOAuthCredentials(
        integration=integration,
        client_id=client_id,
        client_secret=client_secret,
        refresh_token=refresh_token,
        refresh_token_source=source,
        cache_identifier=record.cache_identifier,
        expected_scope=record.expected_scope,
        shared_client_configured=shared_client_configured,
        refresh_token_configured=refresh_token_configured,
        credentials_configured=credentials_configured,
    )


def reset_legacy_warning_cache_for_tests() -> None:
    _legacy_warning_emitted.clear()
