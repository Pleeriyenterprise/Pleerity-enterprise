"""
Canonical operational cognition contract — backend dispatcher and validation.
Single attach surface for entity types; avoids parallel cognition derivation paths.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from services.operational_cognition_service import (
    COGNITION_VERSION,
    assert_cognition_read_only,
    attach_cognition_to_issue_sync,
    attach_cognition_to_rent_ledger,
    attach_cognition_to_risk_signal_sync,
    attach_cognition_to_unresolved_evidence,
    attach_cognition_to_work_order,
    build_envelope_for_requirement,
)

ENTITY_ATTACHERS: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {
    "requirement": lambda row: {**row, "operational_cognition": build_envelope_for_requirement(row)},
    "work_order": attach_cognition_to_work_order,
    "job": attach_cognition_to_work_order,
    "issue": attach_cognition_to_issue_sync,
    "risk_signal": attach_cognition_to_risk_signal_sync,
    "rent_ledger": lambda row: {**row, "operational_cognition": build_envelope_for_rent_ledger(row)},
    "unresolved_evidence": attach_cognition_to_unresolved_evidence,
}


def attach_operational_cognition(entity_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Attach operational_cognition envelope for supported entity types."""
    fn = ENTITY_ATTACHERS.get(str(entity_type or "").lower())
    if not fn:
        return payload
    return fn(payload)


def cognition_contract_version() -> str:
    return COGNITION_VERSION


def assert_read_only_envelope(envelope: Optional[Dict[str, Any]]) -> None:
    """Validate envelope meets read-only contract before serialization."""
    if envelope:
        assert_cognition_read_only(envelope)
