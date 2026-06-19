"""
Discovery feature flags — read-only configuration.

All flags default false in production until launch gate approval.
See docs/governance/DISCOVERY_FEATURE_FLAGS.md.
"""
import os

_FALSE = ("0", "false", "False", "no", "NO", "")


def _flag(name: str, default: str = "false") -> bool:
    return os.environ.get(name, default) not in _FALSE


def is_discovery_module_enabled() -> bool:
    return _flag("DISCOVERY_MODULE_ENABLED")


def is_discovery_provider_layer_enabled() -> bool:
    return _flag("DISCOVERY_PROVIDER_LAYER_ENABLED")


def is_discovery_csv_import_enabled() -> bool:
    return _flag("DISCOVERY_CSV_IMPORT_ENABLED")


def is_discovery_provider_csv_enabled() -> bool:
    return _flag("DISCOVERY_PROVIDER_CSV_ENABLED")


def is_discovery_auto_import_on_approve() -> bool:
    return _flag("DISCOVERY_AUTO_IMPORT_ON_APPROVE", "true")


def is_discovery_provider_twin_enabled() -> bool:
    return _flag("DISCOVERY_PROVIDER_TWIN_ENABLED")


def is_discovery_twin_webhook_ingest_enabled() -> bool:
    """Stage Y: Twin webhook connector endpoint (staging only; default false)."""
    return _flag("DISCOVERY_TWIN_WEBHOOK_INGEST_ENABLED")


def is_discovery_twin_event_capture_only() -> bool:
    """
    When true (default), webhook processing captures Twin run events only.
    Set false to allow ingest_async after export extraction is proven.
    """
    return os.environ.get("DISCOVERY_TWIN_EVENT_CAPTURE_ONLY", "true") not in _FALSE


def is_discovery_provider_apollo_enabled() -> bool:
    return _flag("DISCOVERY_PROVIDER_APOLLO_ENABLED")


def is_discovery_provider_clay_enabled() -> bool:
    return _flag("DISCOVERY_PROVIDER_CLAY_ENABLED")


def is_discovery_provider_manual_enabled() -> bool:
    """Manual provider follows module + provider layer (no separate flag Phase 1)."""
    return is_discovery_module_enabled() and is_discovery_provider_layer_enabled()


def provider_feature_flag_name(provider_id: str) -> str | None:
    """Env flag name for provider enablement, if any."""
    mapping = {
        "csv": "DISCOVERY_PROVIDER_CSV_ENABLED",
        "manual": None,
        "twin": "DISCOVERY_PROVIDER_TWIN_ENABLED",
        "apollo": "DISCOVERY_PROVIDER_APOLLO_ENABLED",
        "clay": "DISCOVERY_PROVIDER_CLAY_ENABLED",
        "internal_crawler": "DISCOVERY_PROVIDER_INTERNAL_CRAWLER_ENABLED",
    }
    return mapping.get(provider_id)


def is_provider_enabled(provider_id: str) -> bool:
    """Whether a provider is enabled via feature flags (ingest not implied)."""
    if not is_discovery_module_enabled() or not is_discovery_provider_layer_enabled():
        return False
    if provider_id == "manual":
        return True
    if provider_id == "csv":
        return is_discovery_provider_csv_enabled()
    if provider_id == "twin":
        return is_discovery_provider_twin_enabled()
    if provider_id == "apollo":
        return is_discovery_provider_apollo_enabled()
    if provider_id == "clay":
        return is_discovery_provider_clay_enabled()
    if provider_id == "internal_crawler":
        return is_discovery_provider_internal_crawler_enabled()
    return False
