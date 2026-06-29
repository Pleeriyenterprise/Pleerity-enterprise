"""Validation helpers for intelligence artefacts."""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from services.compliance_intelligence_engine.lifecycle import validate_transition
from services.compliance_intelligence_engine.schema import IntelligenceArtefactBase, IntelligenceTransitionBase


def validate_artefact_dict(data: Dict[str, Any]) -> Tuple[bool, List[str]]:
    errors: List[str] = []
    if not data.get("provenance_id"):
        errors.append("provenance_id_required")
    try:
        IntelligenceArtefactBase.model_validate(data)
    except Exception as exc:
        errors.append(str(exc))
    if not data.get("insufficient_evidence") and not data.get("source_decision_ids"):
        errors.append("source_decision_ids_required_when_not_insufficient")
    return len(errors) == 0, errors


def validate_transition_dict(data: Dict[str, Any]) -> Tuple[bool, List[str]]:
    errors: List[str] = []
    try:
        IntelligenceTransitionBase.model_validate(data)
    except Exception as exc:
        errors.append(str(exc))
        return False, errors
    ok, reason = validate_transition(data.get("from_state", ""), data.get("to_state", ""))
    if not ok:
        errors.append(reason)
    return len(errors) == 0, errors
