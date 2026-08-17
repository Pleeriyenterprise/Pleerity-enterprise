"""
OAuth credential registry — configuration-driven metadata for Zoho OAuth integrations.

The registry describes how each integration resolves credentials; it does not perform OAuth.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from services.integrations.zoho.config import INTEGRATION_FLAG_CHECKERS


@dataclass(frozen=True)
class OAuthIntegrationRecord:
    integration: str
    oauth_client: str
    refresh_token_env_key: str
    expected_scope: str
    oauth_endpoint: str
    api_endpoint: str
    cache_identifier: str
    feature_flag: str
    requires_oauth: bool = True


def _cache_id(integration: str) -> str:
    return f"zoho_oauth_access_token_{integration}"


# Shared OAuth client (Option B). Per-integration refresh tokens in Render secrets.
OAUTH_INTEGRATION_REGISTRY: Dict[str, OAuthIntegrationRecord] = {
    "analytics": OAuthIntegrationRecord(
        integration="analytics",
        oauth_client="shared",
        refresh_token_env_key="ZOHO_ANALYTICS_REFRESH_TOKEN",
        expected_scope="ZohoAnalytics.data.create",
        oauth_endpoint="ZOHO_ACCOUNTS_URL",
        api_endpoint="ZOHO_API_BASE",
        cache_identifier=_cache_id("analytics"),
        feature_flag="ZOHO_ANALYTICS_SYNC_ENABLED",
    ),
    "crm": OAuthIntegrationRecord(
        integration="crm",
        oauth_client="shared",
        refresh_token_env_key="ZOHO_CRM_REFRESH_TOKEN",
        expected_scope=(
            "ZohoCRM.modules.leads.CREATE,"
            "ZohoCRM.modules.leads.UPDATE,"
            "ZohoCRM.modules.leads.READ"
        ),
        oauth_endpoint="ZOHO_ACCOUNTS_URL",
        api_endpoint="ZOHO_API_BASE",
        cache_identifier=_cache_id("crm"),
        feature_flag="ZOHO_CRM_SYNC_ENABLED",
    ),
    "campaigns": OAuthIntegrationRecord(
        integration="campaigns",
        oauth_client="shared",
        refresh_token_env_key="ZOHO_CAMPAIGNS_REFRESH_TOKEN",
        expected_scope="ZohoCampaigns.contact.CREATE-UPDATE",
        oauth_endpoint="ZOHO_ACCOUNTS_URL",
        api_endpoint="ZOHO_API_BASE",
        cache_identifier=_cache_id("campaigns"),
        feature_flag="ZOHO_CAMPAIGNS_SYNC_ENABLED",
    ),
    "books": OAuthIntegrationRecord(
        integration="books",
        oauth_client="shared",
        refresh_token_env_key="ZOHO_BOOKS_REFRESH_TOKEN",
        expected_scope="ZohoBooks.accountants.CREATE",
        oauth_endpoint="ZOHO_ACCOUNTS_URL",
        api_endpoint="ZOHO_API_BASE",
        cache_identifier=_cache_id("books"),
        feature_flag="ZOHO_BOOKS_SYNC_ENABLED",
    ),
    "workdrive": OAuthIntegrationRecord(
        integration="workdrive",
        oauth_client="shared",
        refresh_token_env_key="ZOHO_WORKDRIVE_REFRESH_TOKEN",
        expected_scope="WorkDrive.files.CREATE",
        oauth_endpoint="ZOHO_ACCOUNTS_URL",
        api_endpoint="ZOHO_API_BASE",
        cache_identifier=_cache_id("workdrive"),
        feature_flag="ZOHO_WORKDRIVE_SYNC_ENABLED",
    ),
}

# Sign is webhook-driven; no OAuth refresh token in current architecture.
NON_OAUTH_INTEGRATIONS = frozenset({"sign"})

LEGACY_REFRESH_TOKEN_ENV_KEY = "ZOHO_REFRESH_TOKEN"
LEGACY_CACHE_IDENTIFIER = "zoho_oauth_access_token"
SHARED_OAUTH_CLIENT_ENV_KEYS = ("ZOHO_CLIENT_ID", "ZOHO_CLIENT_SECRET")


def oauth_integrations() -> List[str]:
    return list(OAUTH_INTEGRATION_REGISTRY.keys())


def get_oauth_integration_record(integration: str) -> Optional[OAuthIntegrationRecord]:
    return OAUTH_INTEGRATION_REGISTRY.get(integration)


def registry_snapshot() -> Dict[str, Dict[str, object]]:
    """Admin-safe registry view — no secrets."""
    from services.integrations.zoho.config import zoho_accounts_url, zoho_api_base, zoho_environment

    env = zoho_environment()
    accounts = zoho_accounts_url()
    api_base = zoho_api_base()
    rows: Dict[str, Dict[str, object]] = {}
    for name, record in OAUTH_INTEGRATION_REGISTRY.items():
        checker = INTEGRATION_FLAG_CHECKERS.get(name)
        rows[name] = {
            "integration": record.integration,
            "oauth_client": record.oauth_client,
            "refresh_token_source": record.refresh_token_env_key,
            "expected_scope": record.expected_scope,
            "oauth_endpoint": accounts,
            "api_endpoint": api_base,
            "environment": env,
            "cache_identifier": record.cache_identifier,
            "feature_flag": record.feature_flag,
            "current_status": "enabled" if checker and checker() else "disabled",
            "requires_oauth": record.requires_oauth,
        }
    for name in NON_OAUTH_INTEGRATIONS:
        checker = INTEGRATION_FLAG_CHECKERS.get(name)
        rows[name] = {
            "integration": name,
            "oauth_client": None,
            "refresh_token_source": None,
            "expected_scope": None,
            "oauth_endpoint": None,
            "api_endpoint": api_base,
            "environment": env,
            "cache_identifier": None,
            "feature_flag": f"ZOHO_{name.upper()}_SYNC_ENABLED",
            "current_status": "enabled" if checker and checker() else "disabled",
            "requires_oauth": False,
        }
    return rows
