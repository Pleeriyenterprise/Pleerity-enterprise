"""
Read-only evidence completeness hints for unified multi-mode requirements (visibility layer).

Does not enforce compliance, alter scoring, or replace evidence authority.
"""
from __future__ import annotations

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


# Checklist field ids / snake_case tokens that indicate CO coverage (never use bare ``"co" in key`` — false positives on e.g. ``test_count``).
_CO_CHECKLIST_KEY_MARKERS: Tuple[str, ...] = (
    "co_alarm",
    "carbon_monoxide",
    "carbon_monoxide_alarm",
    "co_detector",
    "monoxide_alarm",
)

# Phrases in free text that indicate CO evidence (avoid two-letter ``co`` substring — matches inside ``concerns``, ``count``, etc.).
_CO_TEXT_PHRASES: Tuple[str, ...] = (
    "carbon monoxide",
    "co alarm",
    "co_alarm",
    "carbon monoxide alarm",
    "co detector",
    " monoxide ",
)


def _text_indicates_co_evidence(text: str) -> bool:
    t = (text or "").lower()
    return any(p in t for p in _CO_TEXT_PHRASES)


def _checklist_key_indicates_co(key: str) -> bool:
    lk = str(key or "").lower().replace("-", "_")
    return any(m in lk for m in _CO_CHECKLIST_KEY_MARKERS)


def _checklist_value_text_co_evidence(val: Any) -> bool:
    """True when a stored answer clearly refers to CO alarms (not substring ``co``)."""
    if isinstance(val, str):
        return _text_indicates_co_evidence(val)
    if isinstance(val, dict):
        for sub in ("answer", "notes", "observation"):
            inner = val.get(sub)
            if isinstance(inner, str) and _text_indicates_co_evidence(inner):
                return True
    return False


def _checklist_key_suggests_smoke_alarm_evidence(key: str) -> bool:
    """
    True when a checklist field id plausibly relates to smoke / general alarm inspection evidence.
    CO-specific keys are excluded via ``_checklist_key_indicates_co`` (never use bare ``\"co\" in key`` —
    false negatives on e.g. ``codec_alarm``, false positives tying unrelated keys to CO elsewhere).
    """
    if _checklist_key_indicates_co(key):
        return False
    lk = str(key or "").lower().replace("-", "_")
    if any(m in lk for m in ("smoke", "heat", "fire_alarm", "smoke_alarm", "smoke_detector")):
        return True
    if "alarm" in lk:
        return True
    return False


def _record_covers_smoke(rec: Dict[str, Any]) -> bool:
    mode = _norm_status(rec.get("evidence_mode"))
    text = _flatten_text_from_record(rec)
    if any(k in text for k in ("smoke", "smoke alarm", "fire alarm", "alarm tested")):
        return True
    if mode == EVIDENCE_MODE_INSPECTION_CHECKLIST:
        ca = _checklist_answers(rec)
        for key in ca:
            if _checklist_key_suggests_smoke_alarm_evidence(key):
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
    if _text_indicates_co_evidence(text):
        return True
    mode = _norm_status(rec.get("evidence_mode"))
    if mode == EVIDENCE_MODE_INSPECTION_CHECKLIST:
        ca = _checklist_answers(rec)
        for key, val in ca.items():
            if _checklist_key_indicates_co(key):
                return True
            if _checklist_value_text_co_evidence(val):
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
        "required_missing_count": len(pub_missing),
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
