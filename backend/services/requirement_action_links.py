"""
Jurisdiction-filtered external action links for compliance requirements.

Source of truth: presentation/requirements_action_links.json (registry catalog).
Resolver precedence (highest to lowest):
1) requirement.registry_metadata.action_links_manual_override (or legacy action_links)
2) requirement.registry_metadata.action_links_published (materialised from active published registry snapshot)
3) presentation/requirements_action_links.json fallback by requirement code + region.

Future: Mongo requirements_catalog or admin collection can supply action_links without changing item schema.
"""
from __future__ import annotations

import json
import logging
import os
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_MAX_CLIENT_LINKS = 2

_VALID_REGIONS = frozenset({"ENGLAND", "SCOTLAND", "WALES", "NORTHERN_IRELAND"})

# Normalize scoring/storage slugs to registry `code` keys in requirements_action_links.json
_ACTION_LINK_CODE_ALIASES: Dict[str, str] = {
    "DEPOSIT_PI": "DEPOSIT_PROTECTION",
    "DEPOSIT_PRESCRIBED_INFO": "DEPOSIT_PROTECTION",
    "FIRE_DETECTION": "SMOKE_CO_ALARMS",
    "OCCUPATION_CONTRACT": "WALES_OCCUPATION_CONTRACT",
}

_STORAGE_SLUG_TO_REGISTRY: Dict[str, str] = {
    "gas_safety": "GAS_SAFETY",
    "gas_safety_certificate": "GAS_SAFETY",
    "cp12": "GAS_SAFETY",
    "eicr": "EICR",
    "electrical_safety": "EICR",
    "electrical_safety_ni": "ELECTRICAL_SAFETY_NI",
    "epc": "EPC",
    "fire_risk_assessment": "FIRE_RISK_ASSESSMENT",
    "hmo_fire_risk": "HMO_FIRE_RISK",
    "smoke_alarms": "SMOKE_CO_ALARMS",
    "co_alarms": "SMOKE_CO_ALARMS",
    "deposit_pi": "DEPOSIT_PROTECTION",
    "deposit_prescribed_info": "DEPOSIT_PROTECTION",
    "deposit_protection": "DEPOSIT_PROTECTION",
    "scotland_landlord_registration": "SCOTLAND_LANDLORD_REGISTRATION",
    "landlord_registration_ni": "LANDLORD_REGISTRATION_NI",
    "fit_for_habitation": "FIT_FOR_HABITATION",
    "wales_occupation_contract": "WALES_OCCUPATION_CONTRACT",
    "occupation_contract": "WALES_OCCUPATION_CONTRACT",
    "tenancy_agreement": "WALES_OCCUPATION_CONTRACT",
}


def _slug_key(raw: Optional[str]) -> str:
    if not raw:
        return ""
    return str(raw).strip().lower().replace("-", "_")


@lru_cache(maxsize=1)
def _load_registry_by_code() -> Dict[str, List[Dict[str, Any]]]:
    path = os.path.join(os.path.dirname(__file__), "..", "presentation", "requirements_action_links.json")
    path = os.path.normpath(path)
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logger.error("requirements_action_links: failed to load %s: %s", path, e)
        return {}
    out: Dict[str, List[Dict[str, Any]]] = {}
    for block in data.get("requirements_action_links") or []:
        code = str(block.get("code") or "").strip().upper()
        links = block.get("action_links") or []
        if code and isinstance(links, list):
            out[code] = [dict(x) for x in links if isinstance(x, dict)]
    if "WALES_OCCUPATION_CONTRACT" in out:
        out.setdefault("OCCUPATION_CONTRACT", out["WALES_OCCUPATION_CONTRACT"])
    return out


def portfolio_label_to_region(portfolio_label: Optional[str]) -> str:
    """Map portfolio jurisdiction label (e.g. Scotland) to registry region token."""
    s = (portfolio_label or "").strip().lower()
    if "scotland" in s:
        return "SCOTLAND"
    if "northern ireland" in s or "northern_ireland" in s:
        return "NORTHERN_IRELAND"
    if "wales" in s and "england" not in s:
        return "WALES"
    return "ENGLAND"


def resolve_action_links_registry_key(raw_code: Optional[str]) -> Optional[str]:
    """Map requirement code / type slug to registry block code."""
    if not raw_code:
        return None
    # Lazy import avoids cycle: compliance_scoring_v2 → requirement_truth → requirement_action_resolver → this module.
    from services.compliance_scoring_v2 import normalize_requirement_code

    norm = normalize_requirement_code(str(raw_code).strip())
    if norm:
        key = _ACTION_LINK_CODE_ALIASES.get(norm, norm)
        if key in _load_registry_by_code():
            return key
    sk = _slug_key(raw_code)
    return _STORAGE_SLUG_TO_REGISTRY.get(sk)


def _normalize_link_item(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Validate shape; return client-safe dict or None."""
    url = str(item.get("url") or "").strip()
    label = str(item.get("label") or "").strip()
    if not url or not label:
        return None
    jurs = item.get("jurisdictions")
    if not isinstance(jurs, list) or not jurs:
        return None
    regions = []
    for j in jurs:
        t = str(j).strip().upper()
        if t in _VALID_REGIONS:
            regions.append(t)
    if not regions:
        return None
    pri = item.get("priority")
    try:
        priority = int(pri) if pri is not None else 100
    except (TypeError, ValueError):
        priority = 100
    is_active = item.get("is_active")
    if is_active is False:
        return None
    return {
        "key": str(item.get("key") or "") or None,
        "label": label,
        "kind": str(item.get("kind") or "official"),
        "jurisdictions": regions,
        "url": url,
        "priority": priority,
        "is_active": True,
    }


def format_client_external_link(link: Dict[str, Any]) -> Dict[str, Any]:
    """Stable client payload; UI opens in new tab. Label is plain text — portal marks externals in layout."""
    return {
        "key": link.get("key"),
        "label": link["label"],
        "url": link["url"],
        "external": True,
        "kind": link.get("kind") or "official",
    }


def registry_block_for_region(registry_key: Optional[str], region: str) -> List[Dict[str, Any]]:
    """JSON catalog block used for this code after NI/EICR swap (read-only copy)."""
    if not registry_key:
        return []
    reg = _load_registry_by_code()
    block = list(reg.get(registry_key) or [])
    regn = str(region or "ENGLAND").strip().upper()
    if regn not in _VALID_REGIONS:
        regn = "ENGLAND"
    if regn == "NORTHERN_IRELAND" and registry_key == "EICR" and "ELECTRICAL_SAFETY_NI" in reg:
        block = list(reg.get("ELECTRICAL_SAFETY_NI") or block)
    return block


def filter_action_links_for_region(
    links: List[Dict[str, Any]],
    region: str,
    *,
    max_links: int = _MAX_CLIENT_LINKS,
) -> List[Dict[str, Any]]:
    """Active links matching region, sorted by priority ascending, capped."""
    reg = str(region or "ENGLAND").strip().upper()
    if reg not in _VALID_REGIONS:
        reg = "ENGLAND"
    candidates: List[Tuple[int, Dict[str, Any]]] = []
    for raw in links:
        if not isinstance(raw, dict):
            continue
        if raw.get("is_active") is False:
            continue
        norm = _normalize_link_item(raw)
        if not norm:
            continue
        if reg not in norm["jurisdictions"]:
            continue
        candidates.append((norm["priority"], norm))
    candidates.sort(key=lambda x: x[0])
    out: List[Dict[str, Any]] = []
    for _, item in candidates[: max(0, int(max_links))]:
        out.append(
            {
                "key": item["key"],
                "label": item["label"],
                "kind": item["kind"],
                "url": item["url"],
                "external": True,
            }
        )
    return out


def _override_links_from_row(row: Optional[Dict[str, Any]]) -> Optional[List[Dict[str, Any]]]:
    if not row or not isinstance(row, dict):
        return None
    meta = row.get("registry_metadata")
    if not isinstance(meta, dict):
        return None
    raw = meta.get("action_links_manual_override")
    if not isinstance(raw, list) or not raw:
        raw = meta.get("action_links")
    if not isinstance(raw, list) or not raw:
        raw = meta.get("action_links_published")
    if not isinstance(raw, list) or not raw:
        return None
    return [x for x in raw if isinstance(x, dict)]


def get_client_action_links_for_requirement_row(
    row: Dict[str, Any],
    *,
    portfolio_jurisdiction_label: Optional[str] = None,
    max_links: int = _MAX_CLIENT_LINKS,
) -> List[Dict[str, Any]]:
    """
    Return ≤ max_links external action links for API / resolver (registry or registry_metadata override).
    """
    region = portfolio_label_to_region(
        portfolio_jurisdiction_label
        or row.get("jurisdiction")
        or row.get("effective_jurisdiction_label")
    )
    override = _override_links_from_row(row)
    if override is not None:
        return filter_action_links_for_region(override, region, max_links=max_links)

    raw_code = row.get("requirement_code") or row.get("requirement_type") or row.get("code")
    rkey = resolve_action_links_registry_key(str(raw_code) if raw_code else None)
    if not rkey:
        return []
    reg = _load_registry_by_code()
    block = reg.get(rkey) or []
    if region == "NORTHERN_IRELAND" and rkey == "EICR" and "ELECTRICAL_SAFETY_NI" in reg:
        block = reg.get("ELECTRICAL_SAFETY_NI") or block
    return filter_action_links_for_region(block, region, max_links=max_links)


def get_client_action_links_for_code_and_region(
    raw_code: Optional[str],
    portfolio_jurisdiction_label: Optional[str],
    *,
    max_links: int = _MAX_CLIENT_LINKS,
) -> List[Dict[str, Any]]:
    """Priority-stream path when only code + jurisdiction label are available."""
    region = portfolio_label_to_region(portfolio_jurisdiction_label)
    rkey = resolve_action_links_registry_key(raw_code)
    if not rkey:
        return []
    reg = _load_registry_by_code()
    block = reg.get(rkey) or []
    if region == "NORTHERN_IRELAND" and rkey == "EICR" and "ELECTRICAL_SAFETY_NI" in reg:
        block = reg.get("ELECTRICAL_SAFETY_NI") or block
    return filter_action_links_for_region(block, region, max_links=max_links)
