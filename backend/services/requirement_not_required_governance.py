"""
Governance helpers for NOT_REQUIRED persistence vs operator-curated decisions.

B1: Only operator-curated NOT_REQUIRED rows are immutable on materialise; automated
``not_required_reason`` presets (e.g. bulk ``not_applicable``) must not block reopen
when the type is back in the planner.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from services.applicability_provenance_backfill import operator_override_from_doc
from services.applicability_provenance_constants import OPERATOR_OVERRIDE


def is_operator_curated_not_required(row: Dict[str, Any]) -> bool:
    """
    True when the row represents a deliberate manual/operator NOT_REQUIRED decision
    that materialisation must preserve.
    """
    if not isinstance(row, dict):
        return False
    active, _ = operator_override_from_doc(row)
    if active:
        return True
    audit = str(row.get("not_applicable_audit_reason") or "").strip()
    if len(audit) >= 10:
        return True
    src = str(row.get("applicability_resolution_source") or "").strip().upper()
    if src == OPERATOR_OVERRIDE:
        return True
    nested = row.get("applicability_provenance")
    if isinstance(nested, dict):
        nsrc = str(nested.get("applicability_resolution_source") or "").strip().upper()
        if nsrc == OPERATOR_OVERRIDE:
            return True
    return False


def build_automated_not_required_metadata(
    *,
    reason_code: str,
    source_subsystem: str,
    reconcile_source: Optional[str] = None,
    planned_types_snapshot: Optional[list] = None,
) -> Dict[str, Any]:
    """Persist on ``registry_metadata.automated_not_required`` for automated transitions."""
    out: Dict[str, Any] = {
        "reason": str(reason_code or "").strip().upper(),
        "source_subsystem": str(source_subsystem or "").strip(),
        "classification": "automated",
        "at": datetime.now(timezone.utc).isoformat(),
    }
    if reconcile_source:
        out["reconcile_source"] = str(reconcile_source).strip()
    if planned_types_snapshot is not None:
        out["planned_types_snapshot"] = list(planned_types_snapshot)
    return out


def automated_not_required_from_row(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    meta = row.get("registry_metadata") if isinstance(row.get("registry_metadata"), dict) else {}
    auto = meta.get("automated_not_required")
    return auto if isinstance(auto, dict) else None


def is_already_reconciled_obsolete(row: Dict[str, Any]) -> bool:
    """
    True when reconcile_obsolete has already converged this row — skip repeat writes/audit.
    """
    if not isinstance(row, dict):
        return False
    meta = row.get("registry_metadata") if isinstance(row.get("registry_metadata"), dict) else {}
    if not meta.get("reconciled_obsolete"):
        return False
    app = (row.get("applicability") or "").upper()
    st = (row.get("status") or "").upper()
    return app == "NOT_REQUIRED" and st == "NOT_REQUIRED"
