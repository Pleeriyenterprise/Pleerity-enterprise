"""
Jurisdiction-aware narrative for PDFs, digests, and client-facing reports (information layer only).

Not legal advice — framing and scope so multi-jurisdiction portfolios are described accurately.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from services.compliance_rules_registry import canonicalize_uk_portfolio_label


def _reporting_label_from_property_jurisdiction(raw: Optional[str]) -> Optional[str]:
    """Map stored property.jurisdiction to a portfolio-facing label; omit legacy ENGLAND_WALES bucket strings."""
    if not raw or not str(raw).strip():
        return None
    canon = canonicalize_uk_portfolio_label(raw)
    if canon:
        return canon
    u = str(raw).strip().upper().replace(" ", "_").replace("/", "_")
    if u == "SCOTLAND":
        return "Scotland"
    if u in ("ENGLAND_WALES", "NORTHERN_IRELAND", "NORTHERNIRELAND"):
        return None
    return str(raw).strip()


def unique_property_jurisdictions(properties: Sequence[Dict[str, Any]]) -> List[str]:
    seen = []
    for p in properties or []:
        label = _reporting_label_from_property_jurisdiction(p.get("jurisdiction"))
        if label and label not in seen:
            seen.append(label)
    return sorted(seen)


def portfolio_jurisdiction_summary_sentence(
    client_doc: Optional[Dict[str, Any]],
    properties: Sequence[Dict[str, Any]],
) -> str:
    """
    One or two sentences: which regions appear on properties, account default, scoring bucket note.
    """
    labels = unique_property_jurisdictions(properties)
    default_j = ((client_doc or {}).get("default_jurisdiction") or "").strip()
    if not labels and default_j:
        return (
            f"Compliance framing uses your account default region ({default_j}) for properties without "
            "an explicit jurisdiction on the property record. Operational rules may still differ by asset; "
            "this report is an evidence summary only and not legal advice."
        )
    if not labels:
        return (
            "Several properties have no jurisdiction set on the record; the system assumes an England & Wales–style "
            "evidence window until you set property or account defaults. This is an operational summary only — "
            "not legal advice."
        )
    if len(labels) == 1:
        region = labels[0]
        extra = ""
        if default_j and default_j != region:
            extra = f" Your account default is {default_j}; each property’s record takes precedence where set."
        return (
            f"This portfolio includes assets framed for {region} compliance context.{extra} "
            f"Requirements that are deliberately shared across UK nations are scored the same; where rules differ "
            f"by nation (for example selective licensing), only the configured rule set applies. Not legal advice."
        )
    joined = ", ".join(labels[:-1]) + f" and {labels[-1]}"
    return (
        f"Properties in this report span multiple regions ({joined}). Counts and scores combine evidence from "
        f"those contexts; review each property’s jurisdiction on its record for local nuance. Not legal advice."
    )


def digest_jurisdiction_notice_text(client_doc: Optional[Dict[str, Any]], properties: Sequence[Dict[str, Any]]) -> str:
    """Plain text for HTML / PDF digest bodies."""
    return portfolio_jurisdiction_summary_sentence(client_doc, properties)


def jurisdiction_default_fallback_report_disclaimer() -> str:
    """PDF/digest appendix line when compliance used system default (England/EW) for unset jurisdictions."""
    return (
        "Important: At least one property in this report had no jurisdiction on the property record and no saved "
        "account default. Compliance scoring and dates for those assets used the system default "
        "(England & Wales–style rules). Set jurisdiction under Settings → Jurisdiction or on each property record "
        "so evaluation matches your portfolio. This notice is technical scope only — not legal advice."
    )
