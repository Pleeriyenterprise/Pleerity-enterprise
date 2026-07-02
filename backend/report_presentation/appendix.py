"""Technical and governance appendix copy."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

# Customer-facing snapshot framing (replaces engineering-heavy frozen snapshot in body)
CUSTOMER_SNAPSHOT_FRAMING = (
    "This report reflects compliance records available at the time of generation. "
    "Later updates in the portal may differ from this export."
)

GOVERNANCE_APPENDIX_INTRO = (
    "Governance and technical metadata below supports evidential integrity. "
    "It is provided for audit traceability and does not alter the business conclusions above."
)

FROZEN_ARTIFACT_GOVERNANCE = (
    "Immutable export: this file was stored at generation. Re-download returns the same document bytes."
)

TECHNICAL_APPENDIX_INTRO = (
    "Technical audit record — original system actions, identifiers, and precise timestamps "
    "preserved for forensic review."
)


def customer_snapshot_line(*, immutable: bool = False) -> str:
    if immutable:
        return FROZEN_ARTIFACT_GOVERNANCE
    return CUSTOMER_SNAPSHOT_FRAMING


def governance_appendix_lines(
    *,
    export_id: Optional[str] = None,
    export_rules_version: Optional[str] = None,
    authority_version: Optional[str] = None,
    manifest_checksum: Optional[str] = None,
    generation_boundary: Optional[str] = None,
) -> List[str]:
    """Lines for governance appendix only — never executive summary."""
    lines = [GOVERNANCE_APPENDIX_INTRO]
    if export_id:
        lines.append(f"Export reference: {export_id}")
    if export_rules_version:
        lines.append(f"Export rules version: {export_rules_version}")
    if authority_version:
        lines.append(f"Presentation authority: {authority_version}")
    if manifest_checksum:
        lines.append(f"Manifest checksum: {manifest_checksum}")
    if generation_boundary:
        lines.append(f"Generation boundary: {generation_boundary}")
    return lines


def readiness_section_intro() -> str:
    """Customer-facing readiness intro without engineering vocabulary."""
    return (
        "Indicators summarise whether evidence and delivery proof appear sufficient "
        "for independent review at the report date."
    )
