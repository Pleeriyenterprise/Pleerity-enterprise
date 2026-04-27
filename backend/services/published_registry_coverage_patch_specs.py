"""
Authoritative merge patches for active published registry coverage (UK client obligations).

Used by ``scripts/repair_published_registry_coverage.py`` to normalise ``display_jurisdictions``,
relax over-tight ``conditions``, and ensure missing core keys exist with ``validate_registry_draft``-clean
payloads. Editorial ``why_it_matters_short`` strings are concrete (not placeholders) so rows are
publish-review clean.
"""
from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional, Tuple

from services.compliance_registry_admin_service import default_draft_shell, merge_partial_draft

# Re-open eligibility on snapshots that were soft-retired in Mongo while retaining keys.
_RUNTIME_SANITY_PATCH: Dict[str, Any] = {
    "governance": {"archived": False, "materialization_excluded": False},
    "jurisdiction": {"deprecated": False, "is_active": True},
    "classification": {"client_surface_visible": True},
    "conditions": {"logic": "ALL", "rules": []},
}

_ALL_UK: List[str] = ["ENGLAND", "WALES", "SCOTLAND", "NORTHERN_IRELAND"]

# Single client-facing authority for domestic smoke / heat / CO and fire alarm / detection testing evidence.
SMOKE_HEAT_ALARMS_UNIFIED_CLIENT_PATCH: Dict[str, Any] = {
    "identity": {"name": "Smoke, Heat & CO Alarm Compliance", "category": "FIRE"},
    "jurisdiction": {"display_jurisdictions": list(_ALL_UK)},
    "action_behaviour": {
        "primary_action_mode": "upload_document",
        "cta_label_override": "Upload smoke, heat or CO alarm evidence",
    },
    "why_it_matters_short": (
        "Confirms the property has appropriate alarm systems and evidence that they are installed, "
        "maintained, or checked as required."
    ),
}

# (canonical_code, scope_key, merge_partial_draft patch). Applied after _RUNTIME_SANITY_PATCH.
_COVERAGE_PATCHES: List[Tuple[str, str, Dict[str, Any]]] = [
    (
        "GAS_SAFETY",
        "DEFAULT",
        {
            "identity": {"name": "Gas safety certificate", "category": "GAS"},
            "jurisdiction": {"display_jurisdictions": list(_ALL_UK)},
            "why_it_matters_short": (
                "Annual gas safety checks reduce carbon monoxide risk and are a legal baseline for let homes."
            ),
        },
    ),
    (
        "EICR",
        "DEFAULT",
        {
            "identity": {"name": "Electrical Installation Condition Report (EICR)", "category": "ELECTRICAL"},
            "jurisdiction": {"display_jurisdictions": list(_ALL_UK)},
            "why_it_matters_short": (
                "EICR evidence shows the fixed electrical installation has been inspected within required intervals."
            ),
        },
    ),
    (
        "EPC",
        "DEFAULT",
        {
            "identity": {"name": "Energy Performance Certificate (EPC)", "category": "ENERGY"},
            "jurisdiction": {"display_jurisdictions": list(_ALL_UK)},
            "why_it_matters_short": (
                "Valid EPC evidence supports lawful marketing and helps tenants compare running costs."
            ),
        },
    ),
    (
        "LEGIONELLA",
        "DEFAULT",
        {
            "identity": {"name": "Legionella risk assessment", "category": "HEALTH"},
            "classification": {"requirement_type": "JOB", "requires_job": True, "requires_document": False},
            "jurisdiction": {"display_jurisdictions": list(_ALL_UK)},
            "action_behaviour": {"primary_action_mode": "arrange_job"},
            "why_it_matters_short": (
                "Water system risk reviews reduce legionella exposure for residents and visiting contractors."
            ),
        },
    ),
    (
        "SMOKE_HEAT_ALARMS",
        "DEFAULT",
        SMOKE_HEAT_ALARMS_UNIFIED_CLIENT_PATCH,
    ),
    (
        "HMO_FIRE_RISK",
        "DEFAULT",
        {
            "identity": {
                "name": "HMO fire safety management evidence (log book, tests, compartmentation)",
                "category": "FIRE",
            },
            "jurisdiction": {"display_jurisdictions": list(_ALL_UK)},
            "conditions": {"logic": "ALL", "rules": [{"field": "is_hmo", "op": "true"}]},
            "why_it_matters_short": (
                "HMOs must retain ongoing fire safety management records beyond a single FRA snapshot."
            ),
        },
    ),
    (
        "PAT_TESTING",
        "DEFAULT",
        {
            "identity": {"name": "Portable appliance testing (PAT)", "category": "ELECTRICAL"},
            "jurisdiction": {"display_jurisdictions": list(_ALL_UK)},
            "why_it_matters_short": (
                "PAT records show portable electrical appliances provided with the let have been formally tested."
            ),
        },
    ),
    (
        "RIGHT_TO_RENT",
        "DEFAULT",
        {
            "identity": {"name": "Right to rent compliance", "category": "REGULATORY"},
            "jurisdiction": {"display_jurisdictions": ["ENGLAND"]},
            "why_it_matters_short": (
                "England landlords must retain evidence that adult occupiers had a lawful right to rent before move-in."
            ),
        },
    ),
    (
        "HOW_TO_RENT",
        "DEFAULT",
        {
            "identity": {"name": "How to rent guide (England)", "category": "TENANCY"},
            "jurisdiction": {"display_jurisdictions": ["ENGLAND"]},
            "why_it_matters_short": (
                "Serving the current How to Rent booklet is part of England tenancy paperwork compliance at start."
            ),
        },
    ),
    (
        "TENANCY_AGREEMENT",
        "DEFAULT",
        {
            "identity": {"name": "Tenancy agreement", "category": "TENANCY"},
            "jurisdiction": {"display_jurisdictions": list(_ALL_UK)},
            "why_it_matters_short": (
                "The written tenancy records the parties, rent, and terms that govern occupation of the let property."
            ),
        },
    ),
    (
        "TENANCY_DEPOSIT_PROTECTION",
        "ENGLAND",
        {
            "identity": {"name": "Tenancy deposit protection (England)", "category": "TENANCY"},
            "jurisdiction": {"display_jurisdictions": ["ENGLAND"]},
            "conditions": {
                "logic": "ALL",
                "rules": [
                    {"field": "deposit_taken", "op": "true"},
                    {"field": "tenancy_active", "op": "true"},
                ],
            },
            "action_behaviour": {
                "primary_action_mode": "upload_document",
                "cta_label_override": "Upload tenancy deposit protection evidence",
            },
            "why_it_matters_short": (
                "England landlords must protect eligible deposits in an authorised scheme and provide prescribed "
                "information to the tenant where a tenancy deposit is taken."
            ),
        },
    ),
    (
        "TENANCY_DEPOSIT_PROTECTION",
        "WALES",
        {
            "identity": {"name": "Tenancy deposit protection (Wales)", "category": "TENANCY"},
            "jurisdiction": {"display_jurisdictions": ["WALES"]},
            "conditions": {
                "logic": "ALL",
                "rules": [
                    {"field": "deposit_taken", "op": "true"},
                    {"field": "tenancy_active", "op": "true"},
                ],
            },
            "action_behaviour": {
                "primary_action_mode": "upload_document",
                "cta_label_override": "Upload tenancy deposit protection evidence",
            },
            "why_it_matters_short": (
                "Wales landlords must protect eligible deposits in an authorised scheme and provide prescribed "
                "information to the contract-holder where a tenancy deposit is taken."
            ),
        },
    ),
    (
        "TENANCY_DEPOSIT_PROTECTION",
        "SCOTLAND",
        {
            "identity": {"name": "Tenancy deposit protection (Scotland)", "category": "TENANCY"},
            "jurisdiction": {"display_jurisdictions": ["SCOTLAND"]},
            "conditions": {
                "logic": "ALL",
                "rules": [
                    {"field": "deposit_taken", "op": "true"},
                    {"field": "tenancy_active", "op": "true"},
                ],
            },
            "action_behaviour": {
                "primary_action_mode": "upload_document",
                "cta_label_override": "Upload tenancy deposit protection evidence",
            },
            "why_it_matters_short": (
                "Scotland landlords must protect eligible deposits in an approved scheme and provide prescribed "
                "information to the tenant where a tenancy deposit is taken."
            ),
        },
    ),
    (
        "TENANCY_DEPOSIT_PROTECTION",
        "NORTHERN_IRELAND",
        {
            "identity": {"name": "Tenancy deposit protection (Northern Ireland)", "category": "TENANCY"},
            "jurisdiction": {"display_jurisdictions": ["NORTHERN_IRELAND"]},
            "conditions": {
                "logic": "ALL",
                "rules": [
                    {"field": "deposit_taken", "op": "true"},
                    {"field": "tenancy_active", "op": "true"},
                ],
            },
            "action_behaviour": {
                "primary_action_mode": "upload_document",
                "cta_label_override": "Upload tenancy deposit protection evidence",
            },
            "why_it_matters_short": (
                "Northern Ireland landlords must protect eligible deposits in an approved scheme and provide "
                "prescribed information to the tenant where a tenancy deposit is taken."
            ),
        },
    ),
    (
        "HMO_LICENSING",
        "DEFAULT",
        {
            "identity": {"name": "HMO / selective / additional licensing (local authority)", "category": "LICENSING"},
            "jurisdiction": {"display_jurisdictions": list(_ALL_UK)},
            "conditions": {"logic": "ALL", "rules": [{"field": "is_hmo", "op": "true"}]},
            "why_it_matters_short": (
                "Where licensing applies, keep the licence and conditions of use evidence aligned to the local scheme."
            ),
        },
    ),
    (
        "FIRE_RISK_ASSESSMENT",
        "DEFAULT",
        {
            "identity": {"name": "Fire risk assessment (FRA) — suitable & sufficient", "category": "FIRE"},
            "jurisdiction": {"display_jurisdictions": list(_ALL_UK)},
            "conditions": {"logic": "ALL", "rules": [{"field": "is_hmo", "op": "true"}]},
            "why_it_matters_short": (
                "The FRA identifies fire hazards and measures; it is distinct from day-to-day alarm servicing records."
            ),
        },
    ),
    (
        "OCCUPATION_CONTRACT",
        "DEFAULT",
        {
            "identity": {"name": "Written occupation contract (Wales)", "category": "TENANCY"},
            "jurisdiction": {"display_jurisdictions": ["WALES"]},
            "why_it_matters_short": (
                "Renting Homes (Wales) expects written occupation contracts with prescribed terms for regulated lets."
            ),
        },
    ),
    (
        "LANDLORD_REGISTRATION",
        "DEFAULT",
        {
            "identity": {"name": "Scottish landlord registration", "category": "REGULATORY"},
            "jurisdiction": {"display_jurisdictions": ["SCOTLAND"]},
            "why_it_matters_short": (
                "Scottish landlords must register and renew with the Scottish Landlord Register to let lawfully."
            ),
        },
    ),
    (
        "LANDLORD_REGISTRATION_NI",
        "DEFAULT",
        {
            "identity": {"name": "Northern Ireland landlord registration", "category": "REGULATORY"},
            "jurisdiction": {"display_jurisdictions": ["NORTHERN_IRELAND"]},
            "why_it_matters_short": (
                "NI landlords must register with the Department for Communities where the scheme applies to the let."
            ),
        },
    ),
]


def merge_coverage_into_published_entries(
    existing: Optional[Dict[str, Any]],
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Deep-merge coverage patches onto the active ``entries`` map.

    Returns ``(merged_entries, changelog)`` where each changelog row is
    ``{"registry_key", "action": "added"|"updated", "canonical_code", "scope_key"}``.
    """
    base: Dict[str, Any] = copy.deepcopy(existing) if isinstance(existing, dict) else {}
    log: List[Dict[str, Any]] = []
    for canon, sk, patch in _COVERAGE_PATCHES:
        key = f"{canon}|{sk}"
        prev = base.get(key)
        if not isinstance(prev, dict) or not prev:
            shell = default_draft_shell(canonical_code=canon, scope_key=sk)
            shell.pop("entry_id", None)
            shell.pop("status", None)
            shell.pop("updated_by", None)
            prev = shell
            action = "added"
        else:
            action = "updated"
        merged = merge_partial_draft(prev, _RUNTIME_SANITY_PATCH)
        merged = merge_partial_draft(merged, patch)
        base[key] = merged
        log.append({"registry_key": key, "action": action, "canonical_code": canon, "scope_key": sk})
    return base, log
