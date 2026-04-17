"""
Admin-only: preview, validate, and mutate requirement.registry_metadata action_links overrides.

Manual override source (resolver precedence top): registry_metadata.action_links_manual_override
Legacy compatibility key: registry_metadata.action_links
Draft: registry_metadata.action_links_draft
Audit: registry_metadata.action_links_audit (newest last; capped)
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from services.compliance_rules_registry import portfolio_jurisdiction_label
from services.requirement_action_links import (
    _VALID_REGIONS,
    filter_action_links_for_region,
    get_client_action_links_for_requirement_row,
    portfolio_label_to_region,
    registry_block_for_region,
    resolve_action_links_registry_key,
)

_AUDIT_CAP = 80


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _valid_http_url(url: str) -> bool:
    try:
        p = urlparse(url)
    except Exception:
        return False
    return p.scheme in ("http", "https") and bool(p.netloc)


def normalize_admin_action_link_item(raw: Dict[str, Any], *, generate_key_if_missing: bool = False) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Return (stored dict, error) — preserves is_active false."""
    if not isinstance(raw, dict):
        return None, "Each link must be an object"
    label = str(raw.get("label") or "").strip()
    url = str(raw.get("url") or "").strip()
    if not label:
        return None, "label is required"
    if not url or not _valid_http_url(url):
        return None, "url must be a valid http(s) URL"
    key = str(raw.get("key") or "").strip()
    if not key:
        if generate_key_if_missing:
            key = f"admin_{uuid.uuid4().hex[:12]}"
        else:
            return None, "key is required"
    jurs_in = raw.get("jurisdictions")
    if not isinstance(jurs_in, list) or not jurs_in:
        return None, "jurisdictions must be a non-empty list of region codes"
    regions: List[str] = []
    for j in jurs_in:
        t = str(j).strip().upper()
        if t in _VALID_REGIONS:
            regions.append(t)
    if not regions:
        return None, "jurisdictions must contain at least one of ENGLAND, SCOTLAND, WALES, NORTHERN_IRELAND"
    pri = raw.get("priority")
    try:
        priority = int(pri) if pri is not None else 100
    except (TypeError, ValueError):
        return None, "priority must be an integer"
    is_active = raw.get("is_active")
    is_active_b = False if is_active is False else True
    kind = str(raw.get("kind") or "official").strip() or "official"
    return (
        {
            "key": key,
            "label": label,
            "url": url,
            "kind": kind,
            "jurisdictions": regions,
            "is_active": is_active_b,
            "priority": priority,
        },
        None,
    )


def validate_action_links_override(links: List[Dict[str, Any]]) -> List[str]:
    """Return human-readable errors; empty list means valid."""
    errors: List[str] = []
    if not isinstance(links, list):
        return ["links must be a list"]
    if len(links) > 24:
        return ["At most 24 override links allowed per requirement"]

    normalized: List[Dict[str, Any]] = []
    for i, raw in enumerate(links):
        item, err = normalize_admin_action_link_item(raw if isinstance(raw, dict) else {}, generate_key_if_missing=True)
        if err:
            errors.append(f"Row {i + 1}: {err}")
        elif item:
            normalized.append(item)

    keys = [x["key"] for x in normalized]
    if len(keys) != len(set(keys)):
        errors.append("Duplicate key values are not allowed")

    # Same URL twice for overlapping active jurisdictions
    for i, a in enumerate(normalized):
        if a.get("is_active") is False:
            continue
        for j, b in enumerate(normalized):
            if j <= i or b.get("is_active") is False:
                continue
            if a["url"].strip().lower() == b["url"].strip().lower():
                overlap = set(a["jurisdictions"]) & set(b["jurisdictions"])
                if overlap:
                    errors.append(
                        f"Duplicate active URL for jurisdictions {sorted(overlap)}: {a['key']} and {b['key']}",
                    )

    for reg in sorted(_VALID_REGIONS):
        active_for_r = [x for x in normalized if x.get("is_active") is not False and reg in x["jurisdictions"]]
        if len(active_for_r) > 2:
            errors.append(f"At most 2 active links may include jurisdiction {reg}; found {len(active_for_r)}")

    return errors


def _trim_audit(meta: Dict[str, Any]) -> List[Dict[str, Any]]:
    trail = meta.get("action_links_audit")
    if not isinstance(trail, list):
        return []
    return trail[-_AUDIT_CAP:]


def append_action_links_audit(
    meta: Dict[str, Any],
    *,
    actor_user_id: str,
    actor_email: str,
    action: str,
    previous: Dict[str, Any],
    new: Dict[str, Any],
) -> Dict[str, Any]:
    out = dict(meta)
    entry = {
        "at": _utc_iso(),
        "actor_user_id": actor_user_id,
        "actor_email": actor_email,
        "action": action,
        "previous": previous,
        "new": new,
    }
    trail = [x for x in _trim_audit(out) if isinstance(x, dict)]
    trail.append(entry)
    out["action_links_audit"] = trail[-_AUDIT_CAP:]
    return out


def _published_override_list(meta: Optional[Dict[str, Any]]) -> Optional[List[Dict[str, Any]]]:
    if not meta or not isinstance(meta, dict):
        return None
    raw = meta.get("action_links_manual_override")
    if not isinstance(raw, list) or not raw:
        raw = meta.get("action_links")
    if not isinstance(raw, list) or not raw:
        return None
    return [dict(x) for x in raw if isinstance(x, dict)]


def _draft_override_list(meta: Optional[Dict[str, Any]]) -> Optional[List[Dict[str, Any]]]:
    if not meta or not isinstance(meta, dict):
        return None
    raw = meta.get("action_links_draft")
    if not isinstance(raw, list) or not raw:
        return None
    return [dict(x) for x in raw if isinstance(x, dict)]


def build_action_links_admin_preview(
    *,
    requirement_row: Dict[str, Any],
    property_doc: Dict[str, Any],
    client_doc: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    raw_code = requirement_row.get("requirement_code") or requirement_row.get("requirement_type")
    rkey = resolve_action_links_registry_key(str(raw_code) if raw_code else None)
    portfolio = portfolio_jurisdiction_label(property_doc, client_doc)
    region = portfolio_label_to_region(portfolio)
    registry_raw = registry_block_for_region(rkey, region) if rkey else []
    meta = requirement_row.get("registry_metadata") if isinstance(requirement_row.get("registry_metadata"), dict) else {}
    published = _published_override_list(meta)
    draft = _draft_override_list(meta)

    eff_registry = filter_action_links_for_region(list(registry_raw), region, max_links=2)
    eff_published = filter_action_links_for_region(list(published), region, max_links=2) if published else []
    eff_draft = filter_action_links_for_region(list(draft), region, max_links=2) if draft else []

    row_for_resolver = dict(requirement_row)
    row_for_resolver["jurisdiction"] = portfolio
    final_client = get_client_action_links_for_requirement_row(row_for_resolver, portfolio_jurisdiction_label=portfolio)

    audit = meta.get("action_links_audit") if isinstance(meta.get("action_links_audit"), list) else []

    return {
        "property_id": property_doc.get("property_id"),
        "requirement_id": requirement_row.get("requirement_id"),
        "client_id": requirement_row.get("client_id"),
        "requirement_code": raw_code,
        "registry_key": rkey,
        "portfolio_jurisdiction_label": portfolio,
        "resolved_region": region,
        "registry_default_links": registry_raw,
        "effective_from_registry_default": eff_registry,
        "override_published": published,
        "effective_from_published_override": eff_published if published else None,
        "override_draft": draft,
        "effective_if_draft_published": eff_draft if draft else None,
        "effective_final_client_shape": final_client,
        "action_links_audit": audit[-40:],
    }


def merge_registry_metadata_for_links(
    existing_meta: Optional[Dict[str, Any]],
    *,
    action_links: Optional[List[Dict[str, Any]]] = None,
    action_links_draft: Optional[List[Dict[str, Any]]] = None,
    unset_published: bool = False,
    unset_draft: bool = False,
) -> Dict[str, Any]:
    base = dict(existing_meta) if isinstance(existing_meta, dict) else {}
    if unset_published:
        base.pop("action_links_manual_override", None)
        base.pop("action_links", None)
    elif action_links is not None:
        base["action_links_manual_override"] = action_links
        base["action_links"] = action_links
    if unset_draft:
        base.pop("action_links_draft", None)
    elif action_links_draft is not None:
        base["action_links_draft"] = action_links_draft
    return base
