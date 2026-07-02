"""Technical language governance for customer-facing report sections."""

from __future__ import annotations

import re
from typing import Optional

_CUSTOMER_FORBIDDEN_RE = re.compile(
    r"\b("
    r"generation\s+boundary|runtime-visible|manifest\s+checksum|frozen\s+deterministic\s+snapshot|"
    r"immutable\s+artifact|authority_version|export_rules_version|projection=full|"
    r"live_regenerated|reporting_semantics_v1|persisted_property_score"
    r")\b",
    re.I,
)


def contains_technical_language_leak(text: Optional[str]) -> bool:
    if not text:
        return False
    return bool(_CUSTOMER_FORBIDDEN_RE.search(text))


def sanitize_customer_section_text(text: Optional[str]) -> str:
    """Replace known engineering phrases with customer-facing alternatives."""
    if not text:
        return ""
    out = str(text)
    replacements = {
        "generation boundary timestamp": "report date",
        "generation timestamp boundary": "report generation time",
        "generation boundary": "report date",
        "runtime-visible obligations": "active obligations in scope",
        "non-runtime-visible": "inactive or unpublished",
        "runtime-visible": "in-scope",
        "frozen deterministic snapshot": "point-in-time export",
        "manifest checksums": "integrity verification record",
        "immutable artifact": "stored export record",
        "authority_version": "presentation version",
        "live_regenerated": "current portfolio export",
    }
    for old, new in replacements.items():
        out = re.sub(re.escape(old), new, out, flags=re.I)
    return out
