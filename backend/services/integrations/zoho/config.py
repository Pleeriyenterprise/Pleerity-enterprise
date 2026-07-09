"""
Zoho integration feature flags and environment isolation.

All integrations default disabled. Production sync requires explicit env enablement.
"""
from __future__ import annotations

import os

_FALSE = frozenset({"0", "false", "False", "no", "NO", ""})


def _flag(name: str, default: str = "false") -> bool:
    return os.environ.get(name, default) not in _FALSE


def zoho_environment() -> str:
    """staging | production — drives API base and credential namespace."""
    env = (os.environ.get("ZOHO_ENVIRONMENT") or os.environ.get("ENVIRONMENT") or "staging").strip().lower()
    if env in ("prod", "production"):
        return "production"
    return "staging"


def zoho_integration_enabled() -> bool:
    return _flag("ZOHO_INTEGRATION_ENABLED")


def zoho_kill_switch_active() -> bool:
    """Global kill switch — stops all outbound sync immediately."""
    return _flag("ZOHO_KILL_SWITCH", "false")


def _integration_enabled(base_flag: str) -> bool:
    if zoho_kill_switch_active():
        return False
    return zoho_integration_enabled() and _flag(base_flag)


def zoho_analytics_sync_enabled() -> bool:
    return _integration_enabled("ZOHO_ANALYTICS_SYNC_ENABLED")


def zoho_crm_sync_enabled() -> bool:
    return _integration_enabled("ZOHO_CRM_SYNC_ENABLED")


def zoho_campaigns_sync_enabled() -> bool:
    return (
        _integration_enabled("ZOHO_CAMPAIGNS_SYNC_ENABLED")
        and _flag("ZOHO_CAMPAIGNS_KIT_GAP_CONFIRMED")
    )


def zoho_sign_sync_enabled() -> bool:
    return _integration_enabled("ZOHO_SIGN_SYNC_ENABLED")


def zoho_books_sync_enabled() -> bool:
    return _integration_enabled("ZOHO_BOOKS_SYNC_ENABLED")


def zoho_workdrive_sync_enabled() -> bool:
    return _integration_enabled("ZOHO_WORKDRIVE_SYNC_ENABLED")


INTEGRATION_FLAG_CHECKERS = {
    "analytics": zoho_analytics_sync_enabled,
    "crm": zoho_crm_sync_enabled,
    "campaigns": zoho_campaigns_sync_enabled,
    "sign": zoho_sign_sync_enabled,
    "books": zoho_books_sync_enabled,
    "workdrive": zoho_workdrive_sync_enabled,
}


def is_integration_enabled(integration: str) -> bool:
    if zoho_kill_switch_active():
        return False
    checker = INTEGRATION_FLAG_CHECKERS.get(integration)
    return bool(checker and checker())


def zoho_api_base() -> str:
    """Zoho API domain — EU default for UK operations."""
    return (os.environ.get("ZOHO_API_BASE") or "https://www.zohoapis.eu").rstrip("/")


def zoho_accounts_url() -> str:
    return (os.environ.get("ZOHO_ACCOUNTS_URL") or "https://accounts.zoho.eu").rstrip("/")


def zoho_client_id() -> str:
    return (os.environ.get("ZOHO_CLIENT_ID") or "").strip()


def zoho_client_secret() -> str:
    return (os.environ.get("ZOHO_CLIENT_SECRET") or "").strip()


def zoho_refresh_token() -> str:
    return (os.environ.get("ZOHO_REFRESH_TOKEN") or "").strip()


def zoho_webhook_secret(integration: str) -> str:
    key = f"ZOHO_{integration.upper()}_WEBHOOK_SECRET"
    return (os.environ.get(key) or os.environ.get("ZOHO_WEBHOOK_SECRET") or "").strip()


def zoho_org_id() -> str:
    return (os.environ.get("ZOHO_ORG_ID") or "").strip()


def zoho_crm_module() -> str:
    return (os.environ.get("ZOHO_CRM_MODULE") or "Leads").strip()


def zoho_analytics_workspace_id() -> str:
    return (os.environ.get("ZOHO_ANALYTICS_WORKSPACE_ID") or "").strip()


def zoho_workdrive_folder_id() -> str:
    return (os.environ.get("ZOHO_WORKDRIVE_INTERNAL_FOLDER_ID") or "").strip()


def zoho_credentials_configured() -> bool:
    return bool(zoho_client_id() and zoho_client_secret() and zoho_refresh_token())


def integration_status_snapshot() -> dict:
    """Admin visibility — no secrets."""
    return {
        "environment": zoho_environment(),
        "zoho_integration_enabled": zoho_integration_enabled(),
        "kill_switch_active": zoho_kill_switch_active(),
        "credentials_configured": zoho_credentials_configured(),
        "integrations": {
            name: checker()
            for name, checker in INTEGRATION_FLAG_CHECKERS.items()
        },
    }
