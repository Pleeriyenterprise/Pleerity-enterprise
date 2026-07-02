"""LifecycleCommunicationAuthority facade."""

from __future__ import annotations

from typing import Any, Dict, Optional

from lifecycle_communication.constants import AUTHORITY_VERSION
from lifecycle_communication.registry import get_registry_entry, iter_registry_entries, registry_as_list
from lifecycle_communication.resolver import (
    resolve_customer_communication,
    resolve_group_semantic_line,
    resolve_reminder_subject,
)


class LifecycleCommunicationAuthority:
    """Single entry point for governed lifecycle customer communication."""

    version = AUTHORITY_VERSION

    resolve = staticmethod(resolve_customer_communication)
    resolve_group_semantic_line = staticmethod(resolve_group_semantic_line)
    resolve_reminder_subject = staticmethod(resolve_reminder_subject)
    get_registry_entry = staticmethod(get_registry_entry)
    iter_registry_entries = staticmethod(iter_registry_entries)
    registry_as_list = staticmethod(registry_as_list)

    @staticmethod
    def enrich_requirement_row(
        row: Dict[str, Any],
        *,
        surface: str = "portal_detail",
        channel: str = "PORTAL",
        take_action: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Attach customer_communication to a requirement row for API consumers."""
        comm = resolve_customer_communication(
            row,
            surface=surface,  # type: ignore[arg-type]
            channel=channel,  # type: ignore[arg-type]
            take_action=take_action,
        )
        return comm
