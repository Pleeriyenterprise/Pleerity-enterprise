from __future__ import annotations

from typing import Any, Dict, List

# Presence categories
REQUIRED = "REQUIRED"
EXPECTED_IF_AVAILABLE = "EXPECTED_IF_AVAILABLE"
EXPECTED_IF_RELEVANT = "EXPECTED_IF_RELEVANT"
OPTIONAL = "OPTIONAL"
NOT_REQUIRED = "NOT_REQUIRED"
FORBIDDEN = "FORBIDDEN"

# Row types
CANONICAL_REQUIREMENT_ROW = "CANONICAL_REQUIREMENT_ROW"
PROPERTY_REQUIREMENT_ROW = "PROPERTY_REQUIREMENT_ROW"
REQUIREMENT_BACKED_TASK = "REQUIREMENT_BACKED_TASK"
COMMAND_CENTRE_REQUIREMENT_ACTION = "COMMAND_CENTRE_REQUIREMENT_ACTION"
SCORE_DRIVER_REQUIREMENT = "SCORE_DRIVER_REQUIREMENT"
REQUIREMENT_DETAIL_ROW = "REQUIREMENT_DETAIL_ROW"
OPERATIONAL_TASK_ROW = "OPERATIONAL_TASK_ROW"
GENERIC_PRIORITY_ACTION = "GENERIC_PRIORITY_ACTION"
RISK_SIGNAL_ROW = "RISK_SIGNAL_ROW"
WORK_ORDER_ROW = "WORK_ORDER_ROW"

FIELD_NAMES = (
    "semantic_state",
    "workflow_class",
    "take_action",
    "requirement_display",
    "evidence_authority",
    "evidence_completeness",
    "guidance_target",
    "allowed_evidence_modes",
    "requirement_id",
    "property_id",
    "source_type",
    # Operational / action route fields
    "primary_action_type",
    "primary_action_label",
    "primary_action_url",
    "cta_url",
    "action_context_type",
)


ROW_TYPE_CONTRACTS: Dict[str, Dict[str, str]] = {
    CANONICAL_REQUIREMENT_ROW: {
        "semantic_state": EXPECTED_IF_AVAILABLE,
        "workflow_class": REQUIRED,
        "take_action": REQUIRED,
        "requirement_display": REQUIRED,
        "evidence_authority": EXPECTED_IF_AVAILABLE,
        "evidence_completeness": EXPECTED_IF_RELEVANT,
        "guidance_target": EXPECTED_IF_AVAILABLE,
        "allowed_evidence_modes": EXPECTED_IF_AVAILABLE,
        "requirement_id": REQUIRED,
        "property_id": REQUIRED,
        "source_type": NOT_REQUIRED,
        "primary_action_type": NOT_REQUIRED,
        "primary_action_label": NOT_REQUIRED,
        "primary_action_url": NOT_REQUIRED,
        "cta_url": NOT_REQUIRED,
        "action_context_type": NOT_REQUIRED,
    },
    PROPERTY_REQUIREMENT_ROW: {
        "semantic_state": EXPECTED_IF_AVAILABLE,
        "workflow_class": REQUIRED,
        "take_action": REQUIRED,
        "requirement_display": REQUIRED,
        "evidence_authority": EXPECTED_IF_AVAILABLE,
        "evidence_completeness": EXPECTED_IF_RELEVANT,
        "guidance_target": EXPECTED_IF_AVAILABLE,
        "allowed_evidence_modes": EXPECTED_IF_AVAILABLE,
        "requirement_id": REQUIRED,
        "property_id": REQUIRED,
        "source_type": NOT_REQUIRED,
        "primary_action_type": NOT_REQUIRED,
        "primary_action_label": NOT_REQUIRED,
        "primary_action_url": NOT_REQUIRED,
        "cta_url": NOT_REQUIRED,
        "action_context_type": NOT_REQUIRED,
    },
    REQUIREMENT_BACKED_TASK: {
        "semantic_state": EXPECTED_IF_AVAILABLE,
        "workflow_class": REQUIRED,
        "take_action": REQUIRED,
        "requirement_display": REQUIRED,
        "evidence_authority": EXPECTED_IF_AVAILABLE,
        "evidence_completeness": EXPECTED_IF_RELEVANT,
        "guidance_target": EXPECTED_IF_AVAILABLE,
        "allowed_evidence_modes": EXPECTED_IF_AVAILABLE,
        "requirement_id": REQUIRED,
        "property_id": REQUIRED,
        "source_type": REQUIRED,
        "primary_action_type": EXPECTED_IF_AVAILABLE,
        "primary_action_label": EXPECTED_IF_AVAILABLE,
        "primary_action_url": EXPECTED_IF_AVAILABLE,
        "cta_url": OPTIONAL,
        "action_context_type": EXPECTED_IF_AVAILABLE,
    },
    COMMAND_CENTRE_REQUIREMENT_ACTION: {
        "semantic_state": EXPECTED_IF_AVAILABLE,
        "workflow_class": REQUIRED,
        "take_action": REQUIRED,
        "requirement_display": REQUIRED,
        "evidence_authority": EXPECTED_IF_AVAILABLE,
        "evidence_completeness": EXPECTED_IF_RELEVANT,
        "guidance_target": EXPECTED_IF_AVAILABLE,
        "allowed_evidence_modes": EXPECTED_IF_AVAILABLE,
        "requirement_id": REQUIRED,
        "property_id": REQUIRED,
        "source_type": REQUIRED,
        "primary_action_type": EXPECTED_IF_AVAILABLE,
        "primary_action_label": EXPECTED_IF_AVAILABLE,
        "primary_action_url": EXPECTED_IF_AVAILABLE,
        "cta_url": EXPECTED_IF_AVAILABLE,
        "action_context_type": EXPECTED_IF_AVAILABLE,
    },
    SCORE_DRIVER_REQUIREMENT: {
        "semantic_state": EXPECTED_IF_AVAILABLE,
        "workflow_class": REQUIRED,
        "take_action": EXPECTED_IF_AVAILABLE,
        "requirement_display": EXPECTED_IF_AVAILABLE,
        "evidence_authority": EXPECTED_IF_AVAILABLE,
        "evidence_completeness": EXPECTED_IF_RELEVANT,
        "guidance_target": EXPECTED_IF_AVAILABLE,
        "allowed_evidence_modes": EXPECTED_IF_AVAILABLE,
        "requirement_id": REQUIRED,
        "property_id": REQUIRED,
        "source_type": NOT_REQUIRED,
        "primary_action_type": NOT_REQUIRED,
        "primary_action_label": NOT_REQUIRED,
        "primary_action_url": NOT_REQUIRED,
        "cta_url": NOT_REQUIRED,
        "action_context_type": NOT_REQUIRED,
    },
    REQUIREMENT_DETAIL_ROW: {
        "semantic_state": EXPECTED_IF_AVAILABLE,
        "workflow_class": REQUIRED,
        "take_action": REQUIRED,
        "requirement_display": REQUIRED,
        "evidence_authority": EXPECTED_IF_AVAILABLE,
        "evidence_completeness": EXPECTED_IF_RELEVANT,
        "guidance_target": EXPECTED_IF_AVAILABLE,
        "allowed_evidence_modes": EXPECTED_IF_AVAILABLE,
        "requirement_id": REQUIRED,
        "property_id": REQUIRED,
        "source_type": NOT_REQUIRED,
        "primary_action_type": NOT_REQUIRED,
        "primary_action_label": NOT_REQUIRED,
        "primary_action_url": NOT_REQUIRED,
        "cta_url": NOT_REQUIRED,
        "action_context_type": NOT_REQUIRED,
    },
    OPERATIONAL_TASK_ROW: {
        "semantic_state": NOT_REQUIRED,
        "workflow_class": NOT_REQUIRED,
        "take_action": NOT_REQUIRED,
        "requirement_display": NOT_REQUIRED,
        "evidence_authority": FORBIDDEN,
        "evidence_completeness": FORBIDDEN,
        "guidance_target": NOT_REQUIRED,
        "allowed_evidence_modes": NOT_REQUIRED,
        "requirement_id": NOT_REQUIRED,
        "property_id": REQUIRED,
        "source_type": REQUIRED,
        "primary_action_type": REQUIRED,
        "primary_action_label": REQUIRED,
        "primary_action_url": EXPECTED_IF_AVAILABLE,
        "cta_url": OPTIONAL,
        "action_context_type": EXPECTED_IF_AVAILABLE,
    },
    GENERIC_PRIORITY_ACTION: {
        "semantic_state": NOT_REQUIRED,
        "workflow_class": FORBIDDEN,
        "take_action": FORBIDDEN,
        "requirement_display": FORBIDDEN,
        "evidence_authority": FORBIDDEN,
        "evidence_completeness": FORBIDDEN,
        "guidance_target": FORBIDDEN,
        "allowed_evidence_modes": FORBIDDEN,
        "requirement_id": NOT_REQUIRED,
        "property_id": NOT_REQUIRED,
        "source_type": REQUIRED,
        "primary_action_type": REQUIRED,
        "primary_action_label": REQUIRED,
        "primary_action_url": EXPECTED_IF_AVAILABLE,
        "cta_url": OPTIONAL,
        "action_context_type": EXPECTED_IF_AVAILABLE,
    },
    RISK_SIGNAL_ROW: {
        "semantic_state": NOT_REQUIRED,
        "workflow_class": FORBIDDEN,
        "take_action": FORBIDDEN,
        "requirement_display": FORBIDDEN,
        "evidence_authority": FORBIDDEN,
        "evidence_completeness": FORBIDDEN,
        "guidance_target": FORBIDDEN,
        "allowed_evidence_modes": FORBIDDEN,
        "requirement_id": NOT_REQUIRED,
        "property_id": EXPECTED_IF_AVAILABLE,
        "source_type": REQUIRED,
        "primary_action_type": EXPECTED_IF_AVAILABLE,
        "primary_action_label": EXPECTED_IF_AVAILABLE,
        "primary_action_url": EXPECTED_IF_AVAILABLE,
        "cta_url": OPTIONAL,
        "action_context_type": EXPECTED_IF_AVAILABLE,
    },
    WORK_ORDER_ROW: {
        "semantic_state": NOT_REQUIRED,
        "workflow_class": FORBIDDEN,
        "take_action": FORBIDDEN,
        "requirement_display": FORBIDDEN,
        "evidence_authority": FORBIDDEN,
        "evidence_completeness": FORBIDDEN,
        "guidance_target": FORBIDDEN,
        "allowed_evidence_modes": FORBIDDEN,
        "requirement_id": NOT_REQUIRED,
        "property_id": REQUIRED,
        "source_type": REQUIRED,
        "primary_action_type": REQUIRED,
        "primary_action_label": REQUIRED,
        "primary_action_url": EXPECTED_IF_AVAILABLE,
        "cta_url": OPTIONAL,
        "action_context_type": EXPECTED_IF_AVAILABLE,
    },
}


def _value_present(v: Any) -> bool:
    if v is None:
        return False
    if isinstance(v, str):
        return bool(v.strip())
    if isinstance(v, (list, tuple, set, dict)):
        return len(v) > 0
    return True


def _is_relevant(row: Dict[str, Any], field_name: str) -> bool:
    wf = str(row.get("workflow_class") or "").strip().upper()
    if field_name == "evidence_completeness":
        return wf in {"MULTI_EVIDENCE", "GUIDED_DECLARATION", "EXTERNAL_ASSESSMENT_EVIDENCE"}
    return False


def validate_semantic_payload_contract(row: Dict[str, Any], row_type: str) -> Dict[str, Any]:
    contract = ROW_TYPE_CONTRACTS.get(row_type)
    if not isinstance(contract, dict):
        return {
            "row_type": row_type,
            "severity": "ERROR",
            "missing_required": [],
            "unexpected_fields": [],
            "warnings": [f"Unknown row_type contract: {row_type}"],
        }

    missing_required: List[str] = []
    unexpected_fields: List[str] = []
    warnings: List[str] = []

    for field in FIELD_NAMES:
        category = contract.get(field, OPTIONAL)
        present = _value_present(row.get(field))
        if category == REQUIRED and not present:
            missing_required.append(field)
        elif category == FORBIDDEN and present:
            unexpected_fields.append(field)
        elif category == EXPECTED_IF_AVAILABLE and not present:
            warnings.append(f"{field}: expected_if_available_not_present")
        elif category == EXPECTED_IF_RELEVANT and _is_relevant(row, field) and not present:
            warnings.append(f"{field}: expected_if_relevant_not_present")

    severity = "OK"
    if missing_required or unexpected_fields:
        severity = "ERROR"
    elif warnings:
        severity = "WARNING"

    return {
        "row_type": row_type,
        "severity": severity,
        "missing_required": missing_required,
        "unexpected_fields": unexpected_fields,
        "warnings": warnings,
    }


def validate_semantic_payload_contract_batch(rows: List[Dict[str, Any]], row_type: str) -> Dict[str, Any]:
    diagnostics = [validate_semantic_payload_contract(r, row_type) for r in (rows or [])]
    counts = {"OK": 0, "WARNING": 0, "ERROR": 0}
    for d in diagnostics:
        counts[d.get("severity", "OK")] = counts.get(d.get("severity", "OK"), 0) + 1
    severity = "OK"
    if counts.get("ERROR", 0) > 0:
        severity = "ERROR"
    elif counts.get("WARNING", 0) > 0:
        severity = "WARNING"
    return {
        "row_type": row_type,
        "severity": severity,
        "counts": counts,
        "diagnostics": diagnostics,
    }
