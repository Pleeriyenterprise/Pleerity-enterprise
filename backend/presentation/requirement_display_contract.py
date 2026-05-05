"""
Backend-owned requirement display contract for client surfaces.

Maps normalized canonical codes to consistent titles, descriptions, and CTA labels
(sourced from take_action / resolver, not duplicated in the frontend).
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from presentation.label_service import get_domain_labels_public_payload, requirement_label
from services.requirement_code_registry import normalize_requirement_code

_LICENSE_DISPLAY_GROUP = frozenset({"hmo_license", "property_licence", "selective_license"})
_HMO_FIRE_GROUP = frozenset({"hmo_fire_risk", "hmo_fire_risk_evidence"})

_DISPLAY_OVERRIDES: Dict[str, Dict[str, str]] = {
    "right_to_rent": {
        "canonical_name": "Right to Rent Checks",
        "short_name": "Right to Rent",
        "description": "",
    },
    "deposit_pi": {
        "canonical_name": "Tenancy Deposit Protection",
        "short_name": "Deposit Protection",
        "description": "",
    },
    "hmo_license": {
        "canonical_name": "HMO / Selective / Additional Licensing",
        "short_name": "HMO Licensing",
        "description": "",
    },
    "hmo_fire_risk": {
        "canonical_name": "HMO Fire Safety Management",
        "short_name": "HMO Fire Safety",
        "description": (
            "Log book, fire tests, compartmentation and related fire safety evidence."
        ),
    },
    "smoke_heat_alarms": {
        "canonical_name": "Smoke, Heat & Carbon Monoxide Alarm Compliance",
        "short_name": "Smoke, Heat & CO Alarms",
        "description": "",
    },
    "how_to_rent": {
        "canonical_name": "How to Rent Guide",
        "short_name": "How to Rent",
        "description": "",
    },
    "legionella": {
        "canonical_name": "Legionella Risk Assessment",
        "short_name": "Legionella",
        "description": "",
    },
    "gas_safety": {
        "canonical_name": "Gas Safety Certificate (CP12)",
        "short_name": "Gas Safety",
        "description": "",
    },
    "eicr": {
        "canonical_name": "Electrical Installation Condition Report (EICR)",
        "short_name": "EICR",
        "description": "",
    },
    "epc": {
        "canonical_name": "Energy Performance Certificate (EPC)",
        "short_name": "EPC",
        "description": "",
    },
    "portable_appliance_test": {
        "canonical_name": "Portable Appliance Testing (PAT)",
        "short_name": "PAT",
        "description": "",
    },
    "tenancy_agreement": {
        "canonical_name": "Tenancy Agreement",
        "short_name": "Tenancy Agreement",
        "description": "",
    },
}


def _override_lookup_key(canon: Optional[str]) -> Optional[str]:
    if not canon:
        return None
    if canon in _LICENSE_DISPLAY_GROUP:
        return "hmo_license"
    if canon in _HMO_FIRE_GROUP:
        return "hmo_fire_risk"
    return canon if canon in _DISPLAY_OVERRIDES else None


def _domain_entry_for_code(codes_block: Dict[str, Any], canon: Optional[str]) -> Dict[str, Any]:
    if not canon:
        return {}
    ent = codes_block.get(canon)
    return ent if isinstance(ent, dict) else {}


def _category_for_canon(codes_block: Dict[str, Any], canon: Optional[str]) -> str:
    if canon in _LICENSE_DISPLAY_GROUP:
        return str(_domain_entry_for_code(codes_block, "hmo_license").get("category") or "").strip()
    if canon in _HMO_FIRE_GROUP:
        return str(_domain_entry_for_code(codes_block, "hmo_fire_risk").get("category") or "").strip()
    return str(_domain_entry_for_code(codes_block, canon).get("category") or "").strip()


def build_requirement_display(row: Dict[str, Any], *, audience: str = "client") -> Dict[str, Any]:
    """
    Build the client requirement_display payload. CTA labels are taken from row['take_action'] when present.
    """
    raw_code = str(row.get("requirement_code") or row.get("requirement_type") or "").strip()
    canon = row.get("canonical_requirement_code") or normalize_requirement_code(raw_code)
    if not canon and row.get("canonical_code"):
        canon = normalize_requirement_code(str(row.get("canonical_code") or ""))
    canon_key = canon or ""

    codes_block = (get_domain_labels_public_payload().get("requirement_codes") or {})
    ov_key = _override_lookup_key(canon_key)
    ov = _DISPLAY_OVERRIDES.get(ov_key) if ov_key else None

    if ov:
        canonical_name = ov["canonical_name"]
        short_name = ov["short_name"]
        description = ov.get("description") or ""
        category_label = _category_for_canon(codes_block, canon_key)
    else:
        domain = _domain_entry_for_code(codes_block, canon_key)
        canonical_name = str(
            domain.get("display_label") or requirement_label(canon_key or raw_code, audience=audience)
        ).strip()
        short_name = str(domain.get("short_label") or canonical_name).strip()
        description = ""
        category_label = str(domain.get("category") or "").strip()

    take = row.get("take_action") if isinstance(row.get("take_action"), dict) else {}
    pri = take.get("primary") if isinstance(take.get("primary"), dict) else None
    sec = take.get("secondary") if isinstance(take.get("secondary"), dict) else None
    primary_cta_label = str(pri.get("label")).strip() if pri and pri.get("label") else None
    secondary_cta_label = str(sec.get("label")).strip() if sec and sec.get("label") else None

    return {
        "canonical_name": canonical_name,
        "short_name": short_name,
        "description": description,
        "category_label": category_label,
        "primary_cta_label": primary_cta_label,
        "secondary_cta_label": secondary_cta_label,
    }


def compact_display_for_requirement_row(
    requirement: Optional[Dict[str, Any]],
    code: str,
    *,
    audience: str = "client",
) -> str:
    """Short title for gap/task prefixes when requirement_display is present."""
    if isinstance(requirement, dict):
        rd = requirement.get("requirement_display")
        if isinstance(rd, dict):
            name = (rd.get("short_name") or rd.get("canonical_name") or "").strip()
            if name:
                return name
    return requirement_label(code, audience=audience) if code else "Compliance item"
