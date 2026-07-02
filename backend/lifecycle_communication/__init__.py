"""
Lifecycle Communication Authority — governed customer-facing lifecycle wording.

Presentation and communication only. Consumes Lifecycle Authority outputs
(attention_kind, client_lifecycle_label, take_action) without reclassifying requirements.
"""

from lifecycle_communication.authority import LifecycleCommunicationAuthority
from lifecycle_communication.constants import AUTHORITY_VERSION
from lifecycle_communication.registry import get_registry_entry, iter_registry_entries, registry_as_list
from lifecycle_communication.resolver import (
    resolve_customer_communication,
    resolve_group_semantic_line,
    resolve_reminder_subject,
)

__all__ = [
    "AUTHORITY_VERSION",
    "LifecycleCommunicationAuthority",
    "get_registry_entry",
    "iter_registry_entries",
    "registry_as_list",
    "resolve_customer_communication",
    "resolve_group_semantic_line",
    "resolve_reminder_subject",
]
