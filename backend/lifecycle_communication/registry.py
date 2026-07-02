"""Lifecycle Communication Registry — family × surface metadata."""

from __future__ import annotations

from typing import Any, Dict, Iterator, List

from lifecycle_communication.constants import AUTHORITY_VERSION, LIFECYCLE_FAMILIES
from lifecycle_communication.copy import family_action_bundle
from lifecycle_communication.headings import FAMILY_HEADINGS
from lifecycle_communication.verbs import GOVERNED_VERBS

SUPPORTED_SURFACES: List[str] = [
    "reminder_email",
    "reminder_sms",
    "enablement",
    "digest",
    "risk_card",
    "portal_chip",
    "portal_detail",
    "portal_cta",
    "today",
    "command_centre",
    "notification",
    "pdf_report",
    "admin_preview",
    "completion",
]


def iter_registry_entries() -> Iterator[Dict[str, Any]]:
    for family in sorted(LIFECYCLE_FAMILIES):
        actions = family_action_bundle(family)
        yield {
            "lifecycle_family": family,
            "primary_verb": GOVERNED_VERBS.get(family, "Complete"),
            "heading": FAMILY_HEADINGS.get(family, "Compliance action required"),
            "reason_pattern": f"family-specific reason for {family}",
            "evidence_expectation": actions["evidence_expectation"],
            "cta_pattern": actions["primary_action"],
            "completion_wording_key": family,
            "supported_surfaces": list(SUPPORTED_SURFACES),
            "authority_version": AUTHORITY_VERSION,
        }


def registry_as_list() -> List[Dict[str, Any]]:
    return list(iter_registry_entries())


def get_registry_entry(family: str) -> Dict[str, Any]:
    fam = str(family or "").strip().upper()
    for entry in iter_registry_entries():
        if entry["lifecycle_family"] == fam:
            return entry
    return {
        "lifecycle_family": fam or "DOCUMENT_EVIDENCE",
        "primary_verb": GOVERNED_VERBS.get(fam, "Complete"),
        "heading": FAMILY_HEADINGS.get(fam, "Compliance action required"),
        "authority_version": AUTHORITY_VERSION,
        "supported_surfaces": SUPPORTED_SURFACES,
    }
