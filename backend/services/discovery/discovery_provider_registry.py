"""
Discovery provider registry — metadata and capability enforcement (Stage C).

Registers provider metadata only. No ingest adapter implementations.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from services.discovery import discovery_config
from services.discovery.discovery_models import DiscoveryProviderId
from services.discovery.providers.discovery_provider_protocol import (
    PROHIBITED_PROVIDER_CAPABILITIES,
    ProviderCapabilities,
    validate_provider_capabilities,
)

ADAPTER_VERSION = "1.0.0"


class DiscoveryProviderRegistryError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


@dataclass(frozen=True)
class ProviderRegistryEntry:
    provider_id: DiscoveryProviderId
    adapter_version: str
    capabilities: ProviderCapabilities
    phase: int
    ingest_implemented: bool
    description: str

    def capability_violations(self) -> List[str]:
        return validate_provider_capabilities(self.capabilities)


def _csv_capabilities() -> ProviderCapabilities:
    return ProviderCapabilities(
        supports_async=False,
        supports_enrichment=False,
        supports_cost_tracking=False,
        supports_webhook=False,
        max_batch_size=2000,
    )


def _manual_capabilities() -> ProviderCapabilities:
    return ProviderCapabilities(
        supports_async=False,
        supports_enrichment=False,
        supports_cost_tracking=False,
        supports_webhook=False,
        max_batch_size=100,
    )


def _async_provider_capabilities() -> ProviderCapabilities:
    return ProviderCapabilities(
        supports_async=True,
        supports_enrichment=True,
        supports_cost_tracking=True,
        supports_webhook=True,
        max_batch_size=50000,
    )


def _crawler_capabilities() -> ProviderCapabilities:
    return ProviderCapabilities(
        supports_async=True,
        supports_enrichment=False,
        supports_cost_tracking=False,
        supports_webhook=False,
        max_batch_size=10000,
    )


def _twin_capabilities() -> ProviderCapabilities:
    """Stage W — async ingest without enrichment workflows."""
    return ProviderCapabilities(
        supports_async=True,
        supports_enrichment=False,
        supports_cost_tracking=True,
        supports_webhook=True,
        max_batch_size=50000,
    )


def _build_default_registry() -> Dict[str, ProviderRegistryEntry]:
    entries = {
        DiscoveryProviderId.CSV.value: ProviderRegistryEntry(
            provider_id=DiscoveryProviderId.CSV,
            adapter_version=ADAPTER_VERSION,
            capabilities=_csv_capabilities(),
            phase=1,
            ingest_implemented=True,
            description="CSV file upload provider (Phase 1 — Stage M ingest adapter)",
        ),
        DiscoveryProviderId.MANUAL.value: ProviderRegistryEntry(
            provider_id=DiscoveryProviderId.MANUAL,
            adapter_version=ADAPTER_VERSION,
            capabilities=_manual_capabilities(),
            phase=1,
            ingest_implemented=False,
            description="Admin manual entry provider (Phase 1 — metadata only)",
        ),
        DiscoveryProviderId.APOLLO.value: ProviderRegistryEntry(
            provider_id=DiscoveryProviderId.APOLLO,
            adapter_version=ADAPTER_VERSION,
            capabilities=_async_provider_capabilities(),
            phase=2,
            ingest_implemented=False,
            description="Apollo API provider (Phase 2 reserved)",
        ),
        DiscoveryProviderId.CLAY.value: ProviderRegistryEntry(
            provider_id=DiscoveryProviderId.CLAY,
            adapter_version=ADAPTER_VERSION,
            capabilities=_async_provider_capabilities(),
            phase=2,
            ingest_implemented=False,
            description="Clay table sync provider (Phase 2 reserved)",
        ),
        DiscoveryProviderId.TWIN.value: ProviderRegistryEntry(
            provider_id=DiscoveryProviderId.TWIN,
            adapter_version=ADAPTER_VERSION,
            capabilities=_twin_capabilities(),
            phase=2,
            ingest_implemented=True,
            description="Twin orchestration export ingest (Stage W — adapter only, flag-gated)",
        ),
        DiscoveryProviderId.INTERNAL_CRAWLER.value: ProviderRegistryEntry(
            provider_id=DiscoveryProviderId.INTERNAL_CRAWLER,
            adapter_version=ADAPTER_VERSION,
            capabilities=_crawler_capabilities(),
            phase=2,
            ingest_implemented=False,
            description="Internal web crawler (Phase 2 reserved)",
        ),
    }
    for entry in entries.values():
        violations = entry.capability_violations()
        if violations:
            raise DiscoveryProviderRegistryError(
                "REGISTRY_INVALID",
                f"Provider {entry.provider_id.value}: {violations}",
            )
    return entries


class DiscoveryProviderRegistry:
    """Provider metadata registry with feature-flag-aware enablement."""

    def __init__(self, entries: Optional[Dict[str, ProviderRegistryEntry]] = None):
        self._entries = entries or _build_default_registry()

    def list_providers(self) -> List[ProviderRegistryEntry]:
        return list(self._entries.values())

    def get(self, provider_id: str | DiscoveryProviderId) -> ProviderRegistryEntry:
        key = provider_id.value if isinstance(provider_id, DiscoveryProviderId) else provider_id
        entry = self._entries.get(key)
        if not entry:
            raise DiscoveryProviderRegistryError(
                "PROVIDER_NOT_REGISTERED",
                f"Provider '{key}' is not registered",
            )
        return entry

    def is_enabled(self, provider_id: str | DiscoveryProviderId) -> bool:
        key = provider_id.value if isinstance(provider_id, DiscoveryProviderId) else provider_id
        self.get(key)
        return discovery_config.is_provider_enabled(key)

    def is_ingest_available(self, provider_id: str | DiscoveryProviderId) -> bool:
        """True only when flag-enabled AND adapter implemented (none in Stage C)."""
        entry = self.get(provider_id)
        return entry.ingest_implemented and self.is_enabled(provider_id)

    def assert_provider_allowed_for_metadata(
        self, provider_id: str | DiscoveryProviderId
    ) -> ProviderRegistryEntry:
        """
        Allow referencing csv/manual for run metadata when phase-appropriate.
        Phase 2 providers raise when disabled by flag.
        """
        entry = self.get(provider_id)
        if entry.phase > 1 and not self.is_enabled(provider_id):
            raise DiscoveryProviderRegistryError(
                "PROVIDER_DISABLED",
                f"Provider '{entry.provider_id.value}' is reserved and disabled",
            )
        return entry

    def assert_prohibited_capabilities_enforced(
        self, capabilities: ProviderCapabilities
    ) -> None:
        violations = validate_provider_capabilities(capabilities)
        if violations:
            raise DiscoveryProviderRegistryError(
                "PROHIBITED_CAPABILITIES",
                "; ".join(violations),
            )

    def provider_state(self, provider_id: str | DiscoveryProviderId) -> Dict[str, object]:
        entry = self.get(provider_id)
        return {
            "provider_id": entry.provider_id.value,
            "adapter_version": entry.adapter_version,
            "phase": entry.phase,
            "ingest_implemented": entry.ingest_implemented,
            "enabled": self.is_enabled(provider_id),
            "ingest_available": self.is_ingest_available(provider_id),
            "supports_async": entry.capabilities.supports_async,
            "supports_enrichment": entry.capabilities.supports_enrichment,
            "prohibited_capabilities": sorted(PROHIBITED_PROVIDER_CAPABILITIES),
        }

    def resolve_ingest_adapter(self, provider_id: str | DiscoveryProviderId):
        """
        Return ingest adapter instance when implemented and registered.
        Does not check feature flags — callers must gate on is_ingest_available().
        """
        entry = self.get(provider_id)
        key = entry.provider_id.value
        if not entry.ingest_implemented:
            raise DiscoveryProviderRegistryError(
                "INGEST_NOT_IMPLEMENTED",
                f"Provider '{key}' has no ingest adapter",
            )
        if key == DiscoveryProviderId.CSV.value:
            from services.discovery.providers.csv_import_provider import CSVImportProvider

            return CSVImportProvider()
        if key == DiscoveryProviderId.TWIN.value:
            from services.discovery.providers.twin_provider import TwinProvider

            return TwinProvider()
        raise DiscoveryProviderRegistryError(
            "INGEST_ADAPTER_MISSING",
            f"No adapter factory for provider '{key}'",
        )


# Module singleton for service layer
default_provider_registry = DiscoveryProviderRegistry()
