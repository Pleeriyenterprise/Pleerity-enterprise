"""
Single source of truth for human-readable domain labels (loaded from domain_labels.json).
Internal codes remain in APIs for filtering and storage; presentation fields are added for UI.
"""
from __future__ import annotations

import json
import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_DATA_PATH = Path(__file__).resolve().parent / "domain_labels.json"


@lru_cache(maxsize=1)
def _raw_data() -> Dict[str, Any]:
    with open(_DATA_PATH, encoding="utf-8") as f:
        return json.load(f)


def get_domain_labels_public_payload() -> Dict[str, Any]:
    """
    Full presentation dictionary for clients (SPA, mobile) and tooling.
    Contains no secrets — only display strings. Cached with _raw_data().
    """
    return _raw_data()


def _audience_key(audience: str) -> str:
    a = (audience or "client").strip().lower()
    return "admin_label" if a == "admin" else "client_label"


def normalize_requirement_code(code: Optional[str]) -> str:
    if not code:
        return ""
    return re.sub(r"[^a-z0-9]+", "_", str(code).strip().lower()).strip("_")


def requirement_label(code: Optional[str], audience: str = "client") -> str:
    """Full display name for a requirement / compliance code."""
    key = normalize_requirement_code(code)
    if not key:
        return "Compliance item"
    req = (_raw_data().get("requirement_codes") or {}).get(key)
    if req and isinstance(req, dict):
        return str(req.get("display_label") or req.get("short_label") or key).strip()
    up = str(code).strip().upper()
    if up != key:
        req = (_raw_data().get("requirement_codes") or {}).get(up.lower())
        if req and isinstance(req, dict):
            return str(req.get("display_label") or req.get("short_label") or key).strip()
    return _title_from_snake(key)


def requirement_action_phrase(code: Optional[str]) -> str:
    key = normalize_requirement_code(code)
    req = (_raw_data().get("requirement_codes") or {}).get(key) if key else None
    if req and isinstance(req, dict) and req.get("action_label"):
        return str(req["action_label"])
    return f"Complete this obligation: {requirement_label(code, 'client')}"


def today_inbox_action_title(source_type: Optional[str]) -> Optional[str]:
    """
    Single voice for Today inbox titles (non-requirement rows). Copy lives in domain_labels.json
    under today_inbox_action_titles; requirement rows use requirement_action_phrase instead.
    """
    st = (source_type or "").strip()
    if not st:
        return None
    block = (_raw_data().get("today_inbox_action_titles") or {}).get(st)
    if isinstance(block, str) and block.strip():
        return block.strip()
    return None


def issue_status_label(status: Optional[str], audience: str = "client") -> str:
    s = (status or "").strip().lower()
    if not s:
        return "Open"
    block = (_raw_data().get("issue_statuses") or {}).get(s)
    if block and isinstance(block, dict):
        k = _audience_key(audience)
        return str(block.get(k) or block.get("client_label") or s)
    return _title_from_snake(s)


def work_order_status_label(status: Optional[str], audience: str = "client") -> str:
    s = (status or "").strip().upper()
    if not s:
        return "Open"
    block = (_raw_data().get("work_order_statuses") or {}).get(s)
    if block and isinstance(block, dict):
        k = _audience_key(audience)
        return str(block.get(k) or block.get("client_label") or s)
    return _title_from_snake(s.lower())


def sla_state_label(state: Optional[str], audience: str = "client") -> str:
    s = (state or "").strip().lower()
    block = (_raw_data().get("sla_presentations") or {}).get(s)
    if block and isinstance(block, dict):
        k = _audience_key(audience)
        return str(block.get(k) or block.get("client_label") or s)
    return _title_from_snake(s)


def risk_type_client_label(risk_type: Optional[str]) -> str:
    rt = (risk_type or "").strip()
    if not rt:
        return "Risk requires review"
    block = (_raw_data().get("risk_types") or {}).get(rt)
    if block and isinstance(block, dict) and block.get("client_label"):
        return str(block["client_label"])
    if re.fullmatch(r"[A-Z0-9_]+", rt.replace(" ", "")):
        return _title_from_snake(rt.lower())
    return rt


def risk_type_admin_label(risk_type: Optional[str]) -> str:
    rt = (risk_type or "").strip()
    if not rt:
        return "Risk signal"
    block = (_raw_data().get("risk_types") or {}).get(rt)
    if block and isinstance(block, dict) and block.get("admin_label"):
        return str(block["admin_label"])
    return rt


def recommended_action_client_text(risk_type: Optional[str], stored_action: Optional[str]) -> str:
    rt = (risk_type or "").strip()
    block = (_raw_data().get("risk_types") or {}).get(rt)
    if block and isinstance(block, dict) and block.get("recommended_action_client"):
        return str(block["recommended_action_client"])
    raw = (stored_action or "").strip()
    if raw:
        return raw if raw.endswith(".") else f"{raw}."
    return "Review this signal and choose the next best step."


def enrich_risk_signal(signal: Dict[str, Any]) -> Dict[str, Any]:
    """Add presentation fields; keep risk_type and recommended_action for filters and audit."""
    rt = signal.get("risk_type")
    ra = signal.get("recommended_action")
    signal["risk_type_label_client"] = risk_type_client_label(rt)
    signal["risk_type_label_admin"] = risk_type_admin_label(rt)
    signal["recommended_action_client"] = recommended_action_client_text(rt, ra)
    try:
        from services.risk_signal_operational_history_governance import customer_safe_reasons

        if signal.get("reasons"):
            signal["reasons"] = customer_safe_reasons(signal["reasons"], rt)
    except Exception:
        pass
    return signal


def enrich_risk_signals(signals: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    if not signals:
        return []
    for s in signals:
        enrich_risk_signal(s)
    return signals


def suggested_action_label(code: Optional[str], audience: str = "client") -> str:
    c = (code or "").strip().lower()
    block = (_raw_data().get("suggested_action_codes") or {}).get(c)
    if block and isinstance(block, dict):
        k = _audience_key(audience)
        return str(block.get(k) or block.get("client_label") or c)
    return _title_from_snake(c)


def _title_from_snake(s: str) -> str:
    if not s:
        return ""
    parts = re.split(r"[_\s]+", s.replace("-", "_"))
    out = []
    for p in parts:
        if not p:
            continue
        if p.upper() in ("EICR", "EPC", "PAT", "HMO", "CP12", "CO"):
            out.append(p.upper())
        else:
            out.append(p[:1].upper() + p[1:].lower() if len(p) > 1 else p.upper())
    return " ".join(out) if out else s


def compliance_requirement_status_label(status: Optional[str], audience: str = "client") -> str:
    s = (status or "").strip().upper()
    if not s:
        return "—"
    block = (_raw_data().get("compliance_requirement_statuses") or {}).get(s)
    if block and isinstance(block, dict):
        k = _audience_key(audience)
        return str(block.get(k) or block.get("client_label") or s.replace("_", " ").title())
    return _title_from_snake(s.lower())


def property_compliance_rag_label(status: Optional[str], audience: str = "client") -> str:
    """Portfolio traffic-light status for a property (GREEN / AMBER / RED / UNKNOWN)."""
    s = (status or "").strip().upper()
    if not s:
        return "—"
    block = (_raw_data().get("property_compliance_rag") or {}).get(s)
    if block and isinstance(block, dict):
        k = _audience_key(audience)
        return str(block.get(k) or block.get("client_label") or s.replace("_", " ").title())
    return _title_from_snake(s.lower())


def property_type_label(raw: Optional[str], audience: str = "client") -> str:
    if not raw:
        return "—"
    if str(raw).strip().upper() == "N/A":
        return "—"
    key = normalize_requirement_code(str(raw))
    block = (_raw_data().get("property_types") or {}).get(key) if key else None
    if block and isinstance(block, dict):
        k = _audience_key(audience)
        return str(block.get(k) or block.get("client_label") or key)
    return _title_from_snake(key or str(raw).strip().lower())


def document_type_label(raw: Optional[str]) -> str:
    """Map extraction / vault document type codes to readable labels."""
    if not raw:
        return "Document"
    s = str(raw).strip()
    low = normalize_requirement_code(s)
    req = (_raw_data().get("requirement_codes") or {}).get(low)
    if req and isinstance(req, dict):
        return str(req.get("display_label") or req.get("short_label") or s)
    if s.isupper() and "_" in s:
        return requirement_label(s.lower(), "client")
    if "_" in s or s.islower():
        return requirement_label(s, "client")
    return s


def requirement_upload_document_type_map() -> Dict[str, str]:
    """
    Canonical requirement_code -> upload form document_type string.
    Values must match the client Documents upload control options exactly.
    """
    out: Dict[str, str] = {}
    for key, req in (_raw_data().get("requirement_codes") or {}).items():
        if not isinstance(key, str) or not isinstance(req, dict):
            continue
        v = req.get("upload_document_type")
        if v is not None and str(v).strip():
            out[key] = str(v).strip()
    return out


def lookup_requirement_upload_document_type(code: Optional[str]) -> Dict[str, Any]:
    """
    Resolve upload document_type for a requirement code; log coverage gaps (unknown or unmapped codes).
    """
    key = normalize_requirement_code(code)
    if not key:
        return {
            "requirement_code_normalized": "",
            "document_type": None,
            "known_requirement": False,
            "mapped": False,
        }
    reqs = _raw_data().get("requirement_codes") or {}
    req = reqs.get(key)
    if not req or not isinstance(req, dict):
        logger.warning(
            "requirement_upload_document_type: unknown requirement_code %r (normalized=%s) — add to domain_labels.json requirement_codes",
            code,
            key,
        )
        return {
            "requirement_code_normalized": key,
            "document_type": None,
            "known_requirement": False,
            "mapped": False,
        }
    ut = req.get("upload_document_type")
    if ut is None or not str(ut).strip():
        logger.warning(
            "requirement_upload_document_type: requirement %s has no upload_document_type — add upload_document_type to domain_labels.json",
            key,
        )
        return {
            "requirement_code_normalized": key,
            "document_type": None,
            "known_requirement": True,
            "mapped": False,
        }
    return {
        "requirement_code_normalized": key,
        "document_type": str(ut).strip(),
        "known_requirement": True,
        "mapped": True,
    }
