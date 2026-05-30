"""Authoritative work-order operational workflow modes (quote + visit negotiation)."""
from __future__ import annotations

from typing import Any, Dict

from services.work_order_pricing_constants import PRICING_MODE_MAINTENANCE_INSPECTION_REQUIRED

WORKFLOW_MODE_QUOTE_FIRST = "QUOTE_FIRST"
WORKFLOW_MODE_INSPECTION_FIRST = "INSPECTION_FIRST"

ALLOWED_WORKFLOW_MODES = frozenset({WORKFLOW_MODE_QUOTE_FIRST, WORKFLOW_MODE_INSPECTION_FIRST})

WORKFLOW_MODE_LABELS = {
    WORKFLOW_MODE_QUOTE_FIRST: "Quote first",
    WORKFLOW_MODE_INSPECTION_FIRST: "Inspection first",
}

# Governed visit lifecycle labels (maps schedule_status + context)
VISIT_AUTHORITY_LABELS = {
    "proposed": "Visit proposed",
    "confirmed": "Visit confirmed",
    "reschedule_requested": "New date requested",
    "cancelled": "Visit cancelled",
    "completed": "Visit completed",
}


def workflow_mode_for_create(*, work_order_kind: str, inspection_required: bool = False) -> str:
    kind = (work_order_kind or "MAINTENANCE").strip().upper()
    if kind == "COMPLIANCE":
        return WORKFLOW_MODE_QUOTE_FIRST
    if inspection_required:
        return WORKFLOW_MODE_INSPECTION_FIRST
    return WORKFLOW_MODE_QUOTE_FIRST


def resolve_workflow_mode(wo: Dict[str, Any]) -> str:
    raw = (wo.get("workflow_mode") or "").strip().upper()
    if raw in ALLOWED_WORKFLOW_MODES:
        return raw
    mode = (wo.get("pricing_mode") or "").strip().upper()
    if mode == PRICING_MODE_MAINTENANCE_INSPECTION_REQUIRED or wo.get("inspection_required"):
        return WORKFLOW_MODE_INSPECTION_FIRST
    return WORKFLOW_MODE_QUOTE_FIRST


def visit_authority_label(wo: Dict[str, Any]) -> str:
    st = (wo.get("schedule_status") or "").strip().lower()
    if not st and not wo.get("scheduled_at"):
        return "Visit not scheduled"
    return VISIT_AUTHORITY_LABELS.get(st, st.replace("_", " ").title() if st else "—")
