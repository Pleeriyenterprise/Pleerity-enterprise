"""Recovery guidance for contractor assignment eligibility (server-authoritative)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

EXCLUSION_SAMPLE_LIMIT = 5

EXCLUSION_REASON_LABELS: Dict[str, str] = {
    "excluded_not_assignment_ready": "Not assignment-ready",
    "excluded_wrong_client_scope": "Wrong client scope",
    "excluded_property_scope": "Property scope",
    "excluded_location_postcode": "Location / coverage",
    "excluded_execution_capability": "Job capability",
    "excluded_maintenance_trade": "Trade vs job category",
    "excluded_service_region_jurisdiction": "Service region",
}


def contractor_exclusion_sample(contractor: Dict[str, Any]) -> Dict[str, Any]:
    """Minimal contractor row for excluded-contractor review (no PII beyond directory fields)."""
    return {
        "contractor_id": contractor.get("contractor_id"),
        "name": (contractor.get("company_name") or contractor.get("name") or "").strip() or None,
        "trade_types": list(contractor.get("trade_types") or []),
    }


def build_assignment_eligibility_recovery(
    diag: Dict[str, int],
    *,
    job_jurisdiction: Optional[str] = None,
    property_postcode: Optional[str] = None,
    eligible: int = 0,
    exclusion_samples: Optional[Dict[str, List[Dict[str, Any]]]] = None,
) -> Dict[str, Any]:
    """Actionable recovery paths when no (or too few) contractors qualify."""
    actions: List[Dict[str, Any]] = []
    loc = int(diag.get("excluded_location_postcode") or 0)
    prop_scope = int(diag.get("excluded_property_scope") or 0)
    region = int(diag.get("excluded_service_region_jurisdiction") or 0)
    coverage_total = loc + prop_scope + region
    readiness = int(diag.get("excluded_not_assignment_ready") or 0)
    capability = int(diag.get("excluded_execution_capability") or 0)
    trade = int(diag.get("excluded_maintenance_trade") or 0)
    client_scope = int(diag.get("excluded_wrong_client_scope") or 0)

    coverage_names: List[str] = []
    samples = exclusion_samples or {}
    for reason_key in (
        "excluded_location_postcode",
        "excluded_property_scope",
        "excluded_service_region_jurisdiction",
    ):
        for row in samples.get(reason_key) or []:
            n = (row.get("name") or "").strip()
            if n and n not in coverage_names:
                coverage_names.append(n)

    if coverage_total > 0:
        detail_parts: List[str] = []
        if loc:
            detail_parts.append(f"{loc} do not cover this property area")
        if prop_scope:
            detail_parts.append(f"{prop_scope} are limited to other properties")
        if region:
            detail_parts.append(
                f"{region} do not include {job_jurisdiction or 'this job'} in service regions"
            )
        named = ""
        if coverage_names:
            first = coverage_names[0]
            named = (
                f"{first} already exists but does not currently cover this postcode. "
                if loc
                else f"{first} already exists but is not currently eligible for this property. "
            )
        actions.append(
            {
                "key": "update_coverage",
                "headline": f"{coverage_total} contractor{'s' if coverage_total != 1 else ''} do not cover this property area.",
                "detail": named
                + (" ".join(detail_parts) + ". " if detail_parts else "")
                + "Update contractor service areas, postcodes, or UK service regions to include this job.",
                "cta_label": "Review contractors",
                "href": "/contractors",
                "count": coverage_total,
                "named_contractors": coverage_names[:5],
            }
        )

    if readiness > 0:
        actions.append(
            {
                "key": "complete_setup",
                "headline": f"{readiness} contractor{'s' if readiness != 1 else ''} missing assignment-ready details.",
                "detail": "Complete email, vetting, portal activation, and availability before assignment.",
                "cta_label": "Complete contractor setup",
                "href": "/contractors",
                "count": readiness,
            }
        )

    cap_total = capability + trade
    if cap_total > 0:
        parts: List[str] = []
        if capability:
            parts.append(f"{capability} lack verified capability for this job type")
        if trade:
            parts.append(f"{trade} do not match this maintenance category")
        actions.append(
            {
                "key": "edit_trade_capability",
                "headline": f"{cap_total} contractor{'s' if cap_total != 1 else ''} do not match this job type.",
                "detail": ". ".join(parts) + ". Edit trade types or verified compliance capabilities.",
                "cta_label": "Edit contractor trade / services",
                "href": "/contractors",
                "count": cap_total,
            }
        )

    if client_scope > 0:
        actions.append(
            {
                "key": "client_scope",
                "headline": f"{client_scope} contractor{'s' if client_scope != 1 else ''} scoped to another client.",
                "detail": "These contractors are not linked to your organisation.",
                "cta_label": "Review contractors",
                "href": "/contractors",
                "count": client_scope,
            }
        )

    actions.append(
        {
            "key": "add_contractor",
            "headline": "Add a new contractor for this area",
            "detail": (
                f"Create a contractor with coverage for {property_postcode or 'this property'}"
                f"{f' in {job_jurisdiction}' if job_jurisdiction else ''}."
            ),
            "cta_label": "Add a new contractor",
            "action": "focus_add_form",
        }
    )

    primary_blocker: Optional[str] = None
    blocker_counts = [
        ("update_coverage", coverage_total),
        ("complete_setup", readiness),
        ("edit_trade_capability", cap_total),
        ("client_scope", client_scope),
    ]
    blocker_counts.sort(key=lambda x: x[1], reverse=True)
    if eligible <= 0 and blocker_counts[0][1] > 0:
        primary_blocker = blocker_counts[0][0]

    return {
        "recovery_actions": actions,
        "primary_blocker": primary_blocker,
        "eligible": eligible,
    }
