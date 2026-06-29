"""Provenance and registry validation helpers."""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from services.compliance_intelligence_engine.provenance_schema import IntelligenceProvenanceBase
from services.compliance_intelligence_engine.registry.seeds_v1 import (
    all_registry_seeds_v1,
    constraint_seed_v1,
    strategy_seed_v1,
    weight_seed_v1,
)
from services.compliance_intelligence_engine.registry_schema import (
    ConstraintRegistryEntry,
    StrategyRegistryEntry,
    WeightRegistryEntry,
)
from services.compliance_intelligence_engine.schema import IntelligenceArtefactBase
from services.compliance_intelligence_engine.validation import validate_artefact_dict


def validate_provenance_dict(data: Dict[str, Any]) -> Tuple[bool, List[str]]:
    errors: List[str] = []
    try:
        IntelligenceProvenanceBase.model_validate(data)
    except Exception as exc:
        errors.append(str(exc))
    if not data.get("calculation_trace"):
        errors.append("calculation_trace_required")
    if not data.get("constraint_set_version"):
        errors.append("constraint_set_version_required")
    return len(errors) == 0, errors


def validate_artefact_provenance_link(
    artefact: Dict[str, Any], provenance: Dict[str, Any]
) -> Tuple[bool, List[str]]:
    errors: List[str] = []
    ok_a, err_a = validate_artefact_dict(artefact)
    ok_p, err_p = validate_provenance_dict(provenance)
    errors.extend(err_a)
    errors.extend(err_p)
    if artefact.get("provenance_id") != provenance.get("provenance_id"):
        errors.append("provenance_id_mismatch")
    if provenance.get("artefact_id") and artefact.get("artefact_id"):
        if artefact.get("artefact_id") != provenance.get("artefact_id"):
            errors.append("artefact_id_mismatch")
    if artefact.get("inputs_hash") != provenance.get("inputs_hash"):
        errors.append("inputs_hash_mismatch")
    if artefact.get("response_hash") != provenance.get("response_hash"):
        errors.append("response_hash_mismatch")
    return len(errors) == 0, errors


def validate_strategy_seed(data: Dict[str, Any]) -> Tuple[bool, List[str]]:
    try:
        StrategyRegistryEntry.model_validate(data)
        return True, []
    except Exception as exc:
        return False, [str(exc)]


def validate_weight_seed(data: Dict[str, Any]) -> Tuple[bool, List[str]]:
    try:
        WeightRegistryEntry.model_validate(data)
        return True, []
    except Exception as exc:
        return False, [str(exc)]


def validate_constraint_seed(data: Dict[str, Any]) -> Tuple[bool, List[str]]:
    try:
        ConstraintRegistryEntry.model_validate(data)
        return True, []
    except Exception as exc:
        return False, [str(exc)]


def validate_all_registry_seeds_v1() -> Tuple[bool, List[str]]:
    errors: List[str] = []
    seeds = all_registry_seeds_v1()
    for strategy in seeds["strategies"]:
        ok, errs = validate_strategy_seed(strategy)
        if not ok:
            errors.extend(errs)
    ok, errs = validate_weight_seed(seeds["weights"])
    if not ok:
        errors.extend(errs)
    ok, errs = validate_constraint_seed(seeds["constraints"])
    if not ok:
        errors.extend(errs)
    return len(errors) == 0, errors


def validate_artefact_requires_provenance_id(data: Dict[str, Any]) -> Tuple[bool, List[str]]:
    if not data.get("provenance_id"):
        return False, ["provenance_id_required"]
    try:
        IntelligenceArtefactBase.model_validate(data)
        return True, []
    except Exception as exc:
        return False, [str(exc)]
