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


def deployment_environment() -> str:
    """Host deployment ENVIRONMENT/ENV (staging|production|development|…)."""
    return (os.environ.get("ENV") or os.environ.get("ENVIRONMENT") or "").strip().lower()


def zoho_analytics_schedule_registration_allowed() -> bool:
    """
    APScheduler registration gate for zoho_analytics_export.

    Staging only. Production must never receive the Analytics daily cron via this path.
    Uses deployment ENVIRONMENT/ENV — not ZOHO_ENVIRONMENT (credential namespace).
    """
    env = deployment_environment()
    if env in ("production", "prod"):
        return False
    return env == "staging"


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
    """Deprecated legacy refresh token — see OAUTH_DEPRECATION_POLICY.md."""
    return (os.environ.get("ZOHO_REFRESH_TOKEN") or "").strip()


def zoho_refresh_token_env_key(integration: str) -> str:
    return f"ZOHO_{integration.upper()}_REFRESH_TOKEN"


def zoho_refresh_token_for(integration: str) -> tuple[str, str]:
    """
    Return (refresh_token, source) for an integration.
    source: per_integration | legacy | none
    """
    from services.integrations.zoho.credential_resolver import RefreshTokenSource, resolve_oauth_credentials

    resolved = resolve_oauth_credentials(integration)
    if not resolved:
        return "", "none"
    return resolved.refresh_token, resolved.refresh_token_source.value


def zoho_shared_oauth_client_configured() -> bool:
    return bool(zoho_client_id() and zoho_client_secret())


def zoho_oauth_configured_for(integration: str) -> bool:
    """True when shared OAuth client and integration refresh token are configured."""
    from services.integrations.zoho.credential_resolver import resolve_oauth_credentials

    resolved = resolve_oauth_credentials(integration)
    return bool(resolved and resolved.credentials_configured)


def zoho_webhook_secret(integration: str) -> str:
    key = f"ZOHO_{integration.upper()}_WEBHOOK_SECRET"
    return (os.environ.get(key) or os.environ.get("ZOHO_WEBHOOK_SECRET") or "").strip()


def zoho_org_id() -> str:
    return (os.environ.get("ZOHO_ORG_ID") or "").strip()


def zoho_crm_module() -> str:
    return (os.environ.get("ZOHO_CRM_MODULE") or "Leads").strip()


def crm_target_config_snapshot() -> dict:
    """Non-secret CRM outbound target / identity configuration for observability."""
    from services.integrations.zoho.oauth_credential_registry import OAUTH_INTEGRATION_REGISTRY

    module = zoho_crm_module()
    oauth = zoho_oauth_configured_for("crm")
    shared = zoho_shared_oauth_client_configured()
    record = OAUTH_INTEGRATION_REGISTRY.get("crm")
    missing = []
    if not shared:
        missing.append("ZOHO_CLIENT_ID/ZOHO_CLIENT_SECRET")
    if not oauth:
        missing.append("ZOHO_CRM_REFRESH_TOKEN")
    if not module:
        missing.append("ZOHO_CRM_MODULE")
    return {
        "module": module,
        "module_configured": bool(module),
        "oauth_configured": oauth,
        "shared_client_configured": shared,
        "api_base": zoho_api_base(),
        "identity_field": "Pleerity_Lead_ID",
        "identity_resolution_order": [
            "external_key",
            "pleerity_lead_id_lookup",
            "create",
            "persist_external_key",
        ],
        "forbidden_identity_matchers": ["email", "name", "heuristic"],
        "expected_scope": record.expected_scope if record else None,
        "target_complete": bool(module) and oauth and shared,
        "missing": missing,
    }


def zoho_analytics_workspace_id() -> str:
    return (os.environ.get("ZOHO_ANALYTICS_WORKSPACE_ID") or "").strip()


def zoho_analytics_view_id() -> str:
    """Zoho Analytics table/view ID for existing-table import (required for Phase B append)."""
    return (os.environ.get("ZOHO_ANALYTICS_VIEW_ID") or "").strip()


def zoho_analytics_org_id() -> str:
    """
    Zoho Analytics organisation ID for ZANALYTICS-ORGID header.

    Prefer ZOHO_ANALYTICS_ORG_ID; fall back to ZOHO_ORG_ID only when Analytics-specific
    value is unset (Books and Analytics org IDs may differ — set Analytics explicitly).
    """
    return (
        (os.environ.get("ZOHO_ANALYTICS_ORG_ID") or "").strip()
        or (os.environ.get("ZOHO_ORG_ID") or "").strip()
    )


def zoho_analytics_api_base() -> str:
    """Analytics API host (EU default) — distinct from ZOHO_API_BASE (zohoapis)."""
    return (os.environ.get("ZOHO_ANALYTICS_API_BASE") or "https://analyticsapi.zoho.eu").rstrip("/")


def analytics_target_config_snapshot() -> dict:
    """Non-secret presence flags for Analytics import target (admin/observability)."""
    workspace = bool(zoho_analytics_workspace_id())
    view = bool(zoho_analytics_view_id())
    org = bool(zoho_analytics_org_id())
    return {
        "workspace_id_configured": workspace,
        "view_id_configured": view,
        "org_id_configured": org,
        "api_base": zoho_analytics_api_base(),
        "import_path_template": "/restapi/v2/workspaces/{workspace_id}/views/{view_id}/data",
        "table_name": "pleerity_daily_aggregates",
        "target_complete": workspace and view and org,
        "missing": [
            key
            for key, ok in (
                ("ZOHO_ANALYTICS_WORKSPACE_ID", workspace),
                ("ZOHO_ANALYTICS_VIEW_ID", view),
                ("ZOHO_ANALYTICS_ORG_ID", org),
            )
            if not ok
        ],
    }


def zoho_workdrive_folder_id() -> str:
    return (os.environ.get("ZOHO_WORKDRIVE_INTERNAL_FOLDER_ID") or "").strip()


def zoho_credentials_configured() -> bool:
    """
    Backward-compatible aggregate: shared OAuth client plus at least one refresh token.

    Prefer zoho_oauth_configured_for(integration) for per-integration checks.
    """
    if not zoho_shared_oauth_client_configured():
        return False
    if zoho_refresh_token():
        return True
    from services.integrations.zoho.oauth_credential_registry import OAUTH_INTEGRATION_REGISTRY

    for name in OAUTH_INTEGRATION_REGISTRY:
        token, _ = zoho_refresh_token_for(name)
        if token:
            return True
    return False


from services.integrations.zoho.version import version_metadata_snapshot


def _oauth_status_by_integration() -> dict:
    from services.integrations.zoho.credential_resolver import resolve_oauth_credentials
    from services.integrations.zoho.oauth_credential_registry import (
        NON_OAUTH_INTEGRATIONS,
        OAUTH_INTEGRATION_REGISTRY,
    )

    rows: dict = {}
    for name in OAUTH_INTEGRATION_REGISTRY:
        resolved = resolve_oauth_credentials(name)
        rows[name] = {
            "credentials_configured": bool(resolved and resolved.credentials_configured),
            "refresh_token_configured": bool(resolved and resolved.refresh_token_configured),
            "refresh_token_source": resolved.refresh_token_source.value if resolved else "none",
            "expected_scope": resolved.expected_scope if resolved else None,
            "cache_identifier": resolved.cache_identifier if resolved else None,
            "using_legacy_fallback": bool(resolved and resolved.using_legacy_fallback),
        }
    for name in NON_OAUTH_INTEGRATIONS:
        rows[name] = {
            "credentials_configured": False,
            "refresh_token_configured": False,
            "refresh_token_source": "not_applicable",
            "expected_scope": None,
            "cache_identifier": None,
            "using_legacy_fallback": False,
            "requires_oauth": False,
        }
    return rows


def integration_status_snapshot() -> dict:
    """Admin visibility — no secrets."""
    return {
        "environment": zoho_environment(),
        "zoho_integration_enabled": zoho_integration_enabled(),
        "kill_switch_active": zoho_kill_switch_active(),
        "credentials_configured": zoho_credentials_configured(),
        "shared_oauth_client_configured": zoho_shared_oauth_client_configured(),
        "legacy_refresh_token_configured": bool(zoho_refresh_token()),
        "oauth_by_integration": _oauth_status_by_integration(),
        "analytics_target": analytics_target_config_snapshot(),
        "crm_target": crm_target_config_snapshot(),
        "integrations": {
            name: checker()
            for name, checker in INTEGRATION_FLAG_CHECKERS.items()
        },
        **version_metadata_snapshot(),
    }


async def integration_status_snapshot_with_health() -> dict:
    """Admin status including operational health (async Mongo reads)."""
    from services.integrations.zoho.operational_health import (
        build_zoho_operational_health_summary,
        build_zoho_operational_snapshot,
    )

    base = integration_status_snapshot()
    snapshot = await build_zoho_operational_snapshot()
    base["operational_health"] = build_zoho_operational_health_summary(snapshot)
    base["operational_snapshot"] = snapshot
    return base
