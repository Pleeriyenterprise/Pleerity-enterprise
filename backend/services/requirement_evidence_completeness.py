"""
Read-only evidence completeness hints for unified multi-mode requirements (visibility layer).

Does not enforce compliance, alter scoring, or replace evidence authority.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set, Tuple

from services.compliance_evidence_record_service import (
    EVIDENCE_MODE_CONTRACTOR_CONFIRMATION,
    EVIDENCE_MODE_DOCUMENT_UPLOAD,
    EVIDENCE_MODE_INSPECTION_CHECKLIST,
    EVIDENCE_MODE_STRUCTURED_DECLARATION,
)
from services.requirement_code_registry import normalize_requirement_code

COMPONENT_SMOKE = "smoke_alarm"
COMPONENT_CO = "co_alarm"

# Registry / row hints that CO evidence should be tracked for this property-row (non-exhaustive).
_CO_REGISTRY_KEYS_TRUE = frozenset(
    {
        "co_alarm_required",
        "requires_co_alarm_evidence",
        "domestic_co_alarm_required",
    }
)


def _norm_status(st: Optional[str]) -> str:
    return (st or "").strip().upper()


def _flatten_text_from_record(rec: Dict[str, Any]) -> str:
    parts: List[str] = []
    payload = rec.get("evidence_payload")
    if isinstance(payload, dict):
        for k, v in payload.items():
            if isinstance(v, (str, int, float)):
                parts.append(str(v))
            elif isinstance(v, dict):
                for vv in v.values():
                    if isinstance(vv, (str, int, float)):
                        parts.append(str(vv))
    return " ".join(parts).lower()


def _checklist_answers(rec: Dict[str, Any]) -> Dict[str, Any]:
    payload = rec.get("evidence_payload")
    if not isinstance(payload, dict):
        return {}
    ca = payload.get("checklist_answers")
    return ca if isinstance(ca, dict) else {}


def _record_covers_smoke(rec: Dict[str, Any]) -> bool:
    mode = _norm_status(rec.get("evidence_mode"))
    text = _flatten_text_from_record(rec)
    if any(k in text for k in ("smoke", "smoke alarm", "fire alarm", "alarm tested")):
        return True
    if mode == EVIDENCE_MODE_INSPECTION_CHECKLIST:
        ca = _checklist_answers(rec)
        for key in ca:
            lk = str(key).lower()
            if "alarm" in lk and "co" not in lk and "carbon" not in lk:
                return True
        if ca.get("alarm_present") in ("PASS", "pass", True):
            return True
    if mode == EVIDENCE_MODE_DOCUMENT_UPLOAD:
        return True
    if mode in (EVIDENCE_MODE_STRUCTURED_DECLARATION, EVIDENCE_MODE_CONTRACTOR_CONFIRMATION):
        return bool(text)
    return False


def _record_covers_co(rec: Dict[str, Any]) -> bool:
    text = _flatten_text_from_record(rec)
    if any(
        k in text
        for k in (
            "carbon monoxide",
            "co alarm",
            "co_alarm",
            "carbon monoxide alarm",
        )
    ):
        return True
    mode = _norm_status(rec.get("evidence_mode"))
    if mode == EVIDENCE_MODE_INSPECTION_CHECKLIST:
        ca = _checklist_answers(rec)
        for key, val in ca.items():
            lk = str(key).lower()
            if "co" in lk or "carbon" in lk:
                return True
            if isinstance(val, str) and ("co" in val.lower() or "carbon" in val.lower()):
                return True
    return False


def _property_requires_co_evidence(property_context: Optional[Dict[str, Any]], requirement: Dict[str, Any]) -> bool:
    meta = requirement.get("registry_metadata") if isinstance(requirement.get("registry_metadata"), dict) else {}
    er = meta.get("evidence_resolution") if isinstance(meta.get("evidence_resolution"), dict) else {}
    for block in (meta, er):
        for k in _CO_REGISTRY_KEYS_TRUE:
            if block.get(k) is True:
                return True
        v = block.get("co_alarm_evidence_required")
        if v is True:
            return True
    ctx = property_context or {}
    for k in (
        "has_fuel_burning_appliance",
        "fuel_burning_appliance",
        "gas_appliance_present",
        "solid_fuel_appliance",
        "open_flame_appliance",
    ):
        v = ctx.get(k)
        if v is True:
            return True
        if isinstance(v, str) and v.strip().upper() in ("YES", "TRUE", "1", "Y"):
            return True
    notes = str(ctx.get("compliance_notes") or ctx.get("property_notes") or "").lower()
    if any(t in notes for t in ("fuel burning", "gas appliance", "solid fuel", "wood burner", "open fire")):
        return True
    return False


def _merge_satisfaction_from_records(records: List[Dict[str, Any]]) -> Tuple[Set[str], Set[str]]:
    smoke_hit: Set[str] = set()
    co_hit: Set[str] = set()
    for rec in records:
        if not isinstance(rec, dict):
            continue
        if _record_covers_smoke(rec):
            smoke_hit.add(rec.get("evidence_record_id") or id(rec))
        if _record_covers_co(rec):
            co_hit.add(rec.get("evidence_record_id") or id(rec))
    return smoke_hit, co_hit


def evaluate_domestic_alarm_completeness(
    requirement: Dict[str, Any],
    property_context: Optional[Dict[str, Any]],
    evidence_records: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Evaluate sub-component coverage for the unified domestic alarm obligation.

    Returns a dict suitable for admin diagnostics and client summary projection.
    """
    raw_code = str(requirement.get("requirement_code") or requirement.get("requirement_type") or "").strip()
    canon = normalize_requirement_code(raw_code) or raw_code.lower().replace(" ", "_")
    if canon != "smoke_heat_alarms":
        return {
            "evaluated": False,
            "is_complete": True,
            "required_components": [],
            "missing_components": [],
            "completeness_reason": "not_domestic_alarm_unified_requirement",
            "summary_label": "",
        }

    co_required = _property_requires_co_evidence(property_context, requirement)
    smoke_ok, co_ok = _merge_satisfaction_from_records(evidence_records or [])

    required_components: List[Dict[str, Any]] = [
        {
            "key": COMPONENT_SMOKE,
            "label": "Smoke alarm compliance",
            "required": True,
            "satisfied": len(smoke_ok) > 0,
        },
        {
            "key": COMPONENT_CO,
            "label": "Carbon monoxide alarm compliance",
            "required": co_required,
            "satisfied": len(co_ok) > 0,
        },
    ]

    missing = [c for c in required_components if c["required"] and not c["satisfied"]]
    is_complete = len(missing) == 0

    if is_complete:
        reason = "all_required_components_have_evidence_signals"
        summary = "Complete"
    elif not required_components[0]["satisfied"]:
        reason = "smoke_alarm_evidence_not_detected"
        summary = "Incomplete: smoke alarm evidence missing"
    elif co_required and not required_components[1]["satisfied"]:
        reason = "co_alarm_evidence_required_but_missing"
        summary = "Incomplete: CO alarm evidence missing"
    else:
        reason = "partial_coverage"
        summary = "Partially complete"

    return {
        "evaluated": True,
        "is_complete": is_complete,
        "required_components": required_components,
        "missing_components": missing,
        "completeness_reason": reason,
        "summary_label": summary,
        "co_alarm_required": co_required,
        "signals_detected": {"smoke_alarm_records": len(smoke_ok), "co_alarm_records": len(co_ok)},
    }


def project_evidence_completeness_for_client(full: Dict[str, Any]) -> Dict[str, Any]:
    """Strip internal fields for tenant/client JSON."""
    if not full.get("evaluated"):
        return {"evaluated": False}
    missing = full.get("missing_components") or []
    pub_missing = [{"key": m.get("key"), "label": m.get("label")} for m in missing if isinstance(m, dict)]
    return {
        "evaluated": True,
        "is_complete": full.get("is_complete"),
        "summary_label": full.get("summary_label") or "",
        "missing_components": pub_missing,
    }


def requirement_status_appears_satisfied_top_level(requirement: Dict[str, Any]) -> bool:
    """Heuristic: row-level status looks satisfied for drift audit (not legal verdict)."""
    st = _norm_status(requirement.get("status"))
    return st in (
        "COMPLIANT",
        "VALID",
        "VERIFIED",
        "COMPLETE",
        "SATISFIED",
        "PASS",
    )
