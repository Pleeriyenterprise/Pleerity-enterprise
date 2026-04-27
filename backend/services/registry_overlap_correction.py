"""
Remove duplicate / competing keys from the active published registry ``entries`` map.

Run before (or independently of) coverage repair merge when cleaning production snapshots.
Does not touch the legacy client-truth migration.
"""
from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional, Tuple

# Snapshot keys that duplicate authority modelled elsewhere (overlap review).
OVERLAP_SNAPSHOT_KEYS_TO_REMOVE: Tuple[str, ...] = (
    "TENANCY_DEPOSIT_PROTECTION|DEFAULT",
    "RIGHT_TO_RENT_CHECKS|ENGLAND",
    "OCCUPATION_CONTRACT|WALES",
    "LANDLORD_REGISTRATION|NORTHERN IRELAND",
    "LANDLORD_REGISTRATION|SCOTLAND",
    "FIRE_DETECTION|DEFAULT",
)


def apply_registry_overlap_correction(
    entries: Optional[Dict[str, Any]],
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Return a copy of ``entries`` with overlapping snapshot keys removed.

    Changelog rows: ``{"action": "removed", "registry_key": "..."}``.
    """
    base: Dict[str, Any] = copy.deepcopy(entries) if isinstance(entries, dict) else {}
    log: List[Dict[str, Any]] = []
    for key in OVERLAP_SNAPSHOT_KEYS_TO_REMOVE:
        if key in base:
            del base[key]
            log.append({"action": "removed", "registry_key": key})
    return base, log
