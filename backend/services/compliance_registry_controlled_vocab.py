"""
Canonical enums and normalisation for compliance requirement registry drafts.

Single source of truth for controlled fields (category, classification, jurisdictions,
action behaviour, action link kinds). Used by validate/normalise paths and exposed read-only
to the admin editor via HTTP so the UI stays aligned with enforcement.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set, Tuple

# --- Identity category (governed product taxonomy) ---

REGISTRY_IDENTITY_CATEGORIES: Tuple[str, ...] = (
    "ELECTRICAL",
    "GAS",
    "FIRE",
    "HEALTH",
    "REGULATORY",
    "ENERGY",
    "TENANCY",
    "LICENSING",
    "SAFETY",
    "OTHER",
)

REGISTRY_IDENTITY_CATEGORY_SET: Set[str] = set(REGISTRY_IDENTITY_CATEGORIES)

# Legacy / synonym -> canonical (normalisation only; unknown values are left for strict validation to reject)
_CATEGORY_NORMALISATION: Dict[str, str] = {
    "COMPLIANCE": "REGULATORY",
    "GENERAL": "REGULATORY",
    "STATUTORY": "REGULATORY",
    "LEGAL": "REGULATORY",
    "MISC": "OTHER",
    "MISCELLANEOUS": "OTHER",
}

# --- Classification ---

REGISTRY_REQUIREMENT_TYPES: Tuple[str, ...] = ("DOCUMENT", "JOB", "OBLIGATION", "SYSTEM")
REGISTRY_REQUIREMENT_TYPE_SET: Set[str] = set(REGISTRY_REQUIREMENT_TYPES)

REGISTRY_CRITICALITY: Tuple[str, ...] = ("HIGH", "MEDIUM", "LOW")
REGISTRY_CRITICALITY_SET: Set[str] = set(REGISTRY_CRITICALITY)

# --- UK display regions (stored tokens) ---

REGISTRY_UK_DISPLAY_REGIONS: Tuple[str, ...] = ("ENGLAND", "SCOTLAND", "WALES", "NORTHERN_IRELAND")
REGISTRY_UK_DISPLAY_REGION_SET: Set[str] = set(REGISTRY_UK_DISPLAY_REGIONS)

# --- Action behaviour ---

REGISTRY_PRIMARY_ACTION_MODES: Tuple[str, ...] = (
    "upload_document",
    "arrange_job",
    "view_guidance",
    "hidden",
)
REGISTRY_PRIMARY_ACTION_MODE_SET: Set[str] = set(REGISTRY_PRIMARY_ACTION_MODES)

# --- Action link kind (registry draft / published snapshot) ---

REGISTRY_ACTION_LINK_KINDS: Tuple[str, ...] = ("official", "directory", "partner")
REGISTRY_ACTION_LINK_KIND_SET: Set[str] = set(REGISTRY_ACTION_LINK_KINDS)

_ACTION_LINK_KIND_LEGACY: Dict[str, str] = {
    "guidance": "official",
    "form": "official",
    "info": "official",
    "register": "directory",
    "other": "partner",
}

_TOKEN_SPLIT_RE = re.compile(r"[\s,;|]+")


def human_label_for_category(code: str) -> str:
    c = str(code or "").strip().upper()
    labels = {
        "ELECTRICAL": "Electrical",
        "GAS": "Gas",
        "FIRE": "Fire safety",
        "HEALTH": "Health",
        "REGULATORY": "Regulatory / statutory",
        "ENERGY": "Energy",
        "TENANCY": "Tenancy",
        "LICENSING": "Licensing",
        "SAFETY": "Safety",
        "OTHER": "Other",
    }
    return labels.get(c, c.replace("_", " ").title())


def human_label_for_region(code: str) -> str:
    c = str(code or "").strip().upper()
    return {
        "ENGLAND": "England",
        "SCOTLAND": "Scotland",
        "WALES": "Wales",
        "NORTHERN_IRELAND": "Northern Ireland",
    }.get(c, c.replace("_", " ").title())


def human_label_for_requirement_type(code: str) -> str:
    c = str(code or "").strip().upper()
    return {
        "DOCUMENT": "Document",
        "JOB": "Job",
        "OBLIGATION": "Obligation",
        "SYSTEM": "System",
    }.get(c, c)


def human_label_for_action_mode(mode: str) -> str:
    m = str(mode or "").strip().lower()
    return {
        "upload_document": "Upload document",
        "arrange_job": "Arrange job",
        "view_guidance": "View guidance",
        "hidden": "Hidden",
    }.get(m, m)


def normalise_action_link_kind(raw: Any) -> Tuple[str, Optional[str]]:
    """
    Return (canonical_kind, warning).
    Unknown kinds return a sentinel empty string and no warning — caller validates membership.
    """
    s = str(raw or "").strip().lower()
    if not s:
        return "official", None
    if s in REGISTRY_ACTION_LINK_KIND_SET:
        return s, None
    mapped = _ACTION_LINK_KIND_LEGACY.get(s)
    if mapped:
        return mapped, f"action_links.kind:{raw!r} normalised to {mapped!r} (legacy value)"
    return s, None


def _expand_region_token(t: str) -> Tuple[List[str], Optional[str]]:
    """
    Map one normalised token to 0+ canonical UK region codes.
    Returns ([], warning_or_error_message) for empty; ([codes], warning) on expansion.
    """
    u = (t or "").strip().upper().replace(" ", "_").replace("-", "_")
    if not u:
        return [], None
    if u in ("NI", "N_IRELAND"):
        u = "NORTHERN_IRELAND"
    if u in REGISTRY_UK_DISPLAY_REGION_SET:
        return [u], None
    if u in ("ENGLAND_WALES", "ENGLANDANDWALES", "E_W", "EW"):
        return ["ENGLAND", "WALES"], f"jurisdiction.display_jurisdictions:{t!r} expanded to ENGLAND and WALES"
    if u in ("UK", "UNITED_KINGDOM", "GREAT_BRITAIN", "GB", "ALL_UK"):
        return [], f"jurisdiction token {t!r} is not allowed; choose explicit ENGLAND, SCOTLAND, WALES, and/or NORTHERN_IRELAND"
    if u in ("BRITAIN", "GREATBRITAIN"):
        return [], f"jurisdiction token {t!r} is ambiguous; use explicit region codes"
    return [], f"unknown jurisdiction token: {t!r}"


def _flatten_display_jurisdiction_inputs(raw_list: Any) -> List[str]:
    if not isinstance(raw_list, list):
        return []
    out: List[str] = []
    for item in raw_list:
        if item is None:
            continue
        s = str(item).strip()
        if not s:
            continue
        if any(ch in s for ch in ",;|") or " and " in s.lower():
            parts = [p for p in _TOKEN_SPLIT_RE.split(s) if p.strip()]
            if len(parts) > 1:
                out.extend(p.strip() for p in parts if p.strip())
                continue
        out.append(s)
    return out


def normalise_registry_draft_for_storage(doc: Dict[str, Any]) -> List[str]:
    """
    Mutate ``doc`` in place to canonical enum / region / link tokens where safe.
    Returns human-readable warnings (e.g. legacy mappings). Idempotent for already-canonical docs.
    """
    warnings: List[str] = []

    ident = doc.get("identity") if isinstance(doc.get("identity"), dict) else {}
    cat_raw = ident.get("category")
    if cat_raw is not None:
        c0 = str(cat_raw).strip().upper()
        if c0:
            c1 = _CATEGORY_NORMALISATION.get(c0, c0)
            if c1 != c0:
                ident["category"] = c1
                doc["identity"] = ident
                warnings.append(f"identity.category:{cat_raw!r} normalised to {c1!r}")
            elif c0 != str(cat_raw).strip():
                ident["category"] = c0
                doc["identity"] = ident

    cls = doc.get("classification") if isinstance(doc.get("classification"), dict) else {}
    if cls:
        rt = str(cls.get("requirement_type") or "").strip().upper()
        if rt:
            cls["requirement_type"] = rt
        cr = str(cls.get("criticality") or "MEDIUM").strip().upper()
        cls["criticality"] = cr
        doc["classification"] = cls

    jur = doc.get("jurisdiction") if isinstance(doc.get("jurisdiction"), dict) else {}
    dj = jur.get("display_jurisdictions")
    if dj is not None and isinstance(dj, list):
        flat = _flatten_display_jurisdiction_inputs(dj)
        seen: Set[str] = set()
        built: List[str] = []
        for piece in flat:
            codes, w = _expand_region_token(piece)
            if w:
                warnings.append(w)
            if not codes:
                if piece.strip():
                    built.append(piece.strip())
                continue
            for c in codes:
                if c not in seen:
                    seen.add(c)
                    built.append(c)
        jur["display_jurisdictions"] = built
        doc["jurisdiction"] = jur

    ab = doc.get("action_behaviour") if isinstance(doc.get("action_behaviour"), dict) else {}
    if ab:
        pam = str(ab.get("primary_action_mode") or "upload_document").strip().lower()
        pam = pam.replace(" ", "_")
        ab["primary_action_mode"] = pam
        doc["action_behaviour"] = ab

    er = doc.get("evidence_resolution") if isinstance(doc.get("evidence_resolution"), dict) else None
    if er:
        modes = er.get("allowed_evidence_modes")
        if isinstance(modes, list):
            er["allowed_evidence_modes"] = [str(x).strip().upper() for x in modes if str(x or "").strip()]
        prw = str(er.get("primary_resolution_workflow") or "").strip()
        if prw:
            er["primary_resolution_workflow"] = prw.replace(" ", "_")
        doc["evidence_resolution"] = er

    links = doc.get("action_links")
    if isinstance(links, list):
        for i, raw in enumerate(links):
            if not isinstance(raw, dict):
                continue
            k0 = raw.get("kind")
            k1, kw = normalise_action_link_kind(k0)
            if kw:
                warnings.append(f"Row {i + 1} link: {kw}")
            raw["kind"] = k1
            jin = raw.get("jurisdictions")
            if isinstance(jin, list):
                seen_j: Set[str] = set()
                out_j: List[str] = []
                for jt in jin:
                    codes, jw = _expand_region_token(str(jt))
                    if jw:
                        warnings.append(f"Row {i + 1} link jurisdictions: {jw}")
                    if not codes:
                        if str(jt).strip():
                            out_j.append(str(jt).strip())
                        continue
                    for c in codes:
                        if c not in seen_j:
                            seen_j.add(c)
                            out_j.append(c)
                raw["jurisdictions"] = out_j
            pri = raw.get("priority")
            if pri is not None and pri != "":
                try:
                    raw["priority"] = int(pri)
                except (TypeError, ValueError):
                    pass
    return warnings


def controlled_field_options_payload() -> Dict[str, Any]:
    """JSON-serialisable option sets + display hints for the admin editor."""
    return {
        "identity_categories": [
            {"value": c, "label": human_label_for_category(c)} for c in REGISTRY_IDENTITY_CATEGORIES
        ],
        "requirement_types": [
            {"value": c, "label": human_label_for_requirement_type(c)} for c in REGISTRY_REQUIREMENT_TYPES
        ],
        "criticality": [{"value": c, "label": c.title()} for c in REGISTRY_CRITICALITY],
        "uk_display_regions": [
            {"value": c, "label": human_label_for_region(c)} for c in REGISTRY_UK_DISPLAY_REGIONS
        ],
        "primary_action_modes": [
            {"value": m, "label": human_label_for_action_mode(m)} for m in REGISTRY_PRIMARY_ACTION_MODES
        ],
        "action_link_kinds": [
            {"value": k, "label": k.title()} for k in REGISTRY_ACTION_LINK_KINDS
        ],
        "notes": (
            "Stored values are canonical system tokens. The editor loads this payload from the API; "
            "invalid combinations are still blocked by draft validation and publish checks."
        ),
    }
