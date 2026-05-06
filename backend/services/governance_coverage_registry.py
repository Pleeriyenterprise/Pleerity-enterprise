"""
Machine-readable governance coverage by product surface (metadata only).

Phase 1: inventory + CI alignment checks. Does not mutate runtime behaviour or
wire consumers automatically. See docs/GOVERNANCE_CONSUMPTION_MAP.md.
"""
from __future__ import annotations

from typing import Any, Dict, FrozenSet, Literal

EnforcementLevel = Literal["NONE", "PARTIAL", "STRICT"]

GOVERNANCE_SURFACE_REGISTRY: Dict[str, Dict[str, Any]] = {
    "resolver": {
        "consumes_workflow_contract": True,
        "consumes_requirement_display_contract": False,
        "consumes_reporting_semantics": False,
        "consumes_execution_semantics": False,
        "uses_local_fallback_logic": True,
        "allows_noncanonical_requirement_rows": False,
        "enforcement_level": "PARTIAL",
    },
    "requirements_list": {
        "consumes_workflow_contract": True,
        "consumes_requirement_display_contract": True,
        "consumes_reporting_semantics": False,
        "consumes_execution_semantics": False,
        "uses_local_fallback_logic": True,
        "allows_noncanonical_requirement_rows": False,
        "enforcement_level": "PARTIAL",
    },
    "score_drivers": {
        "consumes_workflow_contract": False,
        "consumes_requirement_display_contract": True,
        "consumes_reporting_semantics": False,
        "consumes_execution_semantics": False,
        "uses_local_fallback_logic": True,
        "allows_noncanonical_requirement_rows": False,
        "enforcement_level": "PARTIAL",
    },
    "command_centre": {
        "consumes_workflow_contract": False,
        "consumes_requirement_display_contract": False,
        "consumes_reporting_semantics": False,
        "consumes_execution_semantics": False,
        "uses_local_fallback_logic": True,
        "allows_noncanonical_requirement_rows": False,
        "enforcement_level": "NONE",
    },
    "today_tasks": {
        "consumes_workflow_contract": True,
        "consumes_requirement_display_contract": True,
        "consumes_reporting_semantics": False,
        "consumes_execution_semantics": False,
        "uses_local_fallback_logic": True,
        "allows_noncanonical_requirement_rows": False,
        "enforcement_level": "PARTIAL",
    },
    "work_queue": {
        "consumes_workflow_contract": True,
        "consumes_requirement_display_contract": True,
        "consumes_reporting_semantics": False,
        "consumes_execution_semantics": False,
        "uses_local_fallback_logic": True,
        "allows_noncanonical_requirement_rows": False,
        "enforcement_level": "PARTIAL",
    },
    "reports_exports": {
        "consumes_workflow_contract": False,
        "consumes_requirement_display_contract": True,
        "consumes_reporting_semantics": False,
        "consumes_execution_semantics": False,
        "uses_local_fallback_logic": True,
        "allows_noncanonical_requirement_rows": True,
        "enforcement_level": "PARTIAL",
    },
    "property_compliance_matrix": {
        "consumes_workflow_contract": True,
        "consumes_requirement_display_contract": True,
        "consumes_reporting_semantics": False,
        "consumes_execution_semantics": False,
        "uses_local_fallback_logic": True,
        "allows_noncanonical_requirement_rows": False,
        "enforcement_level": "PARTIAL",
    },
    "needs_attention": {
        "consumes_workflow_contract": True,
        "consumes_requirement_display_contract": True,
        "consumes_reporting_semantics": False,
        "consumes_execution_semantics": False,
        "uses_local_fallback_logic": True,
        "allows_noncanonical_requirement_rows": False,
        "enforcement_level": "PARTIAL",
    },
    "audit_pipeline": {
        "consumes_workflow_contract": True,
        "consumes_requirement_display_contract": True,
        "consumes_reporting_semantics": True,
        "consumes_execution_semantics": True,
        "uses_local_fallback_logic": False,
        "allows_noncanonical_requirement_rows": False,
        "enforcement_level": "STRICT",
    },
    "frontend_cta": {
        "consumes_workflow_contract": True,
        "consumes_requirement_display_contract": True,
        "consumes_reporting_semantics": False,
        "consumes_execution_semantics": False,
        "uses_local_fallback_logic": True,
        "allows_noncanonical_requirement_rows": False,
        "enforcement_level": "PARTIAL",
    },
    "frontend_status": {
        "consumes_workflow_contract": False,
        "consumes_requirement_display_contract": True,
        "consumes_reporting_semantics": False,
        "consumes_execution_semantics": False,
        "uses_local_fallback_logic": True,
        "allows_noncanonical_requirement_rows": False,
        "enforcement_level": "PARTIAL",
    },
    "reminder_generation": {
        "consumes_workflow_contract": False,
        "consumes_requirement_display_contract": False,
        "consumes_reporting_semantics": False,
        "consumes_execution_semantics": False,
        "uses_local_fallback_logic": True,
        "allows_noncanonical_requirement_rows": False,
        "enforcement_level": "NONE",
    },
    "gap_engine": {
        "consumes_workflow_contract": False,
        "consumes_requirement_display_contract": True,
        "consumes_reporting_semantics": False,
        "consumes_execution_semantics": False,
        "uses_local_fallback_logic": True,
        "allows_noncanonical_requirement_rows": False,
        "enforcement_level": "PARTIAL",
    },
}


def list_governance_surface_ids() -> FrozenSet[str]:
    return frozenset(GOVERNANCE_SURFACE_REGISTRY.keys())


def get_surface_coverage(surface_id: str) -> Dict[str, Any]:
    return dict(GOVERNANCE_SURFACE_REGISTRY.get(str(surface_id).strip().lower(), {}))
