"""Zoho integration layer version metadata."""
from __future__ import annotations

from typing import Any, Dict

ZOHO_INTEGRATION_LAYER_VERSION = "1.0.0"
DEFAULT_MAPPING_VERSION = "1.0.0"
DEFAULT_PAYLOAD_VERSION = 1
DEFAULT_WEBHOOK_VERSION = 1

ADAPTER_VERSIONS: Dict[str, str] = {
    "analytics": "1.0.0",
    "crm": "1.2.0",
    "campaigns": "1.0.0",
    "sign": "1.0.0",
    "books": "1.0.0",
    "workdrive": "1.0.0",
}


def sync_run_versions(integration: str) -> Dict[str, Any]:
    """Version block persisted on each zoho_sync_runs document."""
    return {
        "layer": ZOHO_INTEGRATION_LAYER_VERSION,
        "adapter": ADAPTER_VERSIONS.get(integration, "1.0.0"),
        "mapping": DEFAULT_MAPPING_VERSION,
        "payload": DEFAULT_PAYLOAD_VERSION,
    }


def version_metadata_snapshot() -> Dict[str, Any]:
    """Non-secret version metadata for admin and platform observability."""
    return {
        "integration_layer_version": ZOHO_INTEGRATION_LAYER_VERSION,
        "mapping_version": DEFAULT_MAPPING_VERSION,
        "default_payload_version": DEFAULT_PAYLOAD_VERSION,
        "default_webhook_version": DEFAULT_WEBHOOK_VERSION,
        "adapters": dict(ADAPTER_VERSIONS),
    }
