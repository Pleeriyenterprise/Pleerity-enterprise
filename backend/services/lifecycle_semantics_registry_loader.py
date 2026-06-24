"""Load lifecycle_semantics from published registry draft rows."""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from services.lifecycle_semantics_types import (
    LIFECYCLE_SEMANTICS_VALUES,
    FieldContract,
    LifecycleSemantics,
    field_contract_from_dict,
)

_REGISTRY_LIFECYCLE_KEY = "lifecycle"


def extract_lifecycle_from_registry_row(
    registry_row: Optional[Dict[str, Any]],
) -> Optional[Tuple[LifecycleSemantics, FieldContract, Optional[str]]]:
    """
    Return (semantics, field_contract, vocabulary_family) when registry publishes lifecycle block.
    """
    if not registry_row or not isinstance(registry_row, dict):
        return None
    block = registry_row.get(_REGISTRY_LIFECYCLE_KEY)
    if not isinstance(block, dict):
        return None
    semantics_raw = str(block.get("semantics") or "").strip().upper()
    if semantics_raw not in LIFECYCLE_SEMANTICS_VALUES:
        return None
    fc_raw = block.get("field_contract")
    field_contract = field_contract_from_dict(fc_raw if isinstance(fc_raw, dict) else {})
    vocab = block.get("vocabulary_family")
    vocabulary_family = str(vocab).strip() if vocab else None
    return semantics_raw, field_contract, vocabulary_family  # type: ignore[return-value]


def lifecycle_block_for_registry(
    semantics: LifecycleSemantics,
    field_contract: FieldContract,
    *,
    vocabulary_family: Optional[str] = None,
    extraction_profile_id: Optional[str] = None,
    reminder_profile_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Build publishable registry lifecycle block."""
    out: Dict[str, Any] = {
        "semantics": semantics,
        "field_contract": field_contract.to_dict(),
    }
    if vocabulary_family:
        out["vocabulary_family"] = vocabulary_family
    if extraction_profile_id:
        out["extraction_profile_id"] = extraction_profile_id
    if reminder_profile_id:
        out["reminder_profile_id"] = reminder_profile_id
    return out
