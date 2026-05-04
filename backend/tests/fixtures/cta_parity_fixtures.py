"""
Stream D Phase 4 — deterministic requirement rows and expected resolver outputs.

**Authority:** `services/requirement_action_resolver.py` (runtime). This module **freezes**
read-side expectations for contract tests; changing behaviour requires updating fixtures
**and** `frontend/src/utils/requirementTakeActionResolver.js` in lockstep
(see `docs/STREAM_D_CTA_PARITY_ENFORCEMENT.md`).

**Parity scope:** `intent`, `kind`, `handler`, route presence/shape, suppression,
guided vs direct vs navigate, and `resolve_take_action_for_priority_action` projection
(`primary_action_type`, `primary_action_url`, `primary_action_label`).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from services.compliance_requirement_engine import resolve_engine_payload_from_code

CTA_PARITY_PROPERTY_ID = "cta-parity-prop-01"
CTA_PARITY_REQUIREMENT_ID = "cta-parity-req-01"
CTA_PARITY_JURISDICTION = "England"


def _base_requirement(**overrides: Any) -> Dict[str, Any]:
    row: Dict[str, Any] = {
        "requirement_id": CTA_PARITY_REQUIREMENT_ID,
        "property_id": CTA_PARITY_PROPERTY_ID,
        "requirement_type": "parity_stub",
        "requirement_code": "parity_stub",
        "compliance_requirement_class": "DOCUMENT",
    }
    row.update(overrides)
    return row


class CtaParityExpectedPrimary:
    """Expected `take_action.primary` fields (None = skip assertion for that attribute)."""

    def __init__(
        self,
        *,
        intent: Optional[str] = None,
        kind: Optional[str] = None,
        handler: Optional[str] = None,
        route_is_none: Optional[bool] = None,
        route_contains: Optional[str] = None,
        route_equals: Optional[str] = None,
        label_equals: Optional[str] = None,
        label_substring: Optional[str] = None,
        evidence_mode: Optional[str] = None,
        metadata_incomplete: Optional[bool] = None,
    ) -> None:
        self.intent = intent
        self.kind = kind
        self.handler = handler
        self.route_is_none = route_is_none
        self.route_contains = route_contains
        self.route_equals = route_equals
        self.label_equals = label_equals
        self.label_substring = label_substring
        self.evidence_mode = evidence_mode
        self.metadata_incomplete = metadata_incomplete


class CtaParityExpectedSecondary:
    def __init__(
        self,
        *,
        route_contains: Optional[str] = None,
        label_substring: Optional[str] = None,
        absent: bool = False,
    ) -> None:
        self.route_contains = route_contains
        self.label_substring = label_substring
        self.absent = absent


class CtaParityCase:
    def __init__(
        self,
        case_id: str,
        *,
        requirement: Dict[str, Any],
        property_id: Optional[str] = None,
        property_jurisdiction: str = CTA_PARITY_JURISDICTION,
        action_type: Optional[str] = None,
        take_action_suppressed: Optional[bool] = None,
        primary_none: bool = False,
        primary: Optional[CtaParityExpectedPrimary] = None,
        secondary: Optional[CtaParityExpectedSecondary] = None,
        skip_priority_projection: bool = False,
        priority_compliance_engine: Optional[Dict[str, Any]] = None,
        priority_primary_action_type: Optional[str] = None,
        priority_primary_action_url: Optional[str] = None,
        priority_primary_action_url_is_empty: bool = False,
        priority_primary_action_label_substring: Optional[str] = None,
        priority_primary_action_label_equals: Optional[str] = None,
        priority_secondary_url_contains: Optional[str] = None,
    ) -> None:
        self.case_id = case_id
        self.requirement = requirement
        self.property_id = property_id
        self.property_jurisdiction = property_jurisdiction
        self.action_type = action_type
        self.take_action_suppressed = take_action_suppressed
        self.primary_none = primary_none
        self.primary = primary
        self.secondary = secondary
        self.skip_priority_projection = skip_priority_projection
        self.priority_compliance_engine = priority_compliance_engine
        self.priority_primary_action_type = priority_primary_action_type
        self.priority_primary_action_url = priority_primary_action_url
        self.priority_primary_action_url_is_empty = priority_primary_action_url_is_empty
        self.priority_primary_action_label_substring = priority_primary_action_label_substring
        self.priority_primary_action_label_equals = priority_primary_action_label_equals
        self.priority_secondary_url_contains = priority_secondary_url_contains


def all_cta_parity_cases() -> List[CtaParityCase]:
    """Stable IDs P01.. for doc cross-references."""
    pid, rid = CTA_PARITY_PROPERTY_ID, CTA_PARITY_REQUIREMENT_ID
    doc_q = f"/documents?property_id={pid}&requirement_id={rid}"

    return [
        CtaParityCase(
            "P01_hidden_registry_suppresses",
            requirement=_base_requirement(
                requirement_code="gas_safety",
                requirement_type="gas_safety",
                registry_metadata={"primary_action_mode": "hidden"},
            ),
            action_type="OBLIGATION",
            take_action_suppressed=True,
            primary_none=True,
            primary=None,
            secondary=CtaParityExpectedSecondary(absent=True),
            # Minimal priority rows do not replay visibility / hidden flags into synthetic row;
            # production uses full requirement + canonical_take_action. Envelope is authoritative.
            skip_priority_projection=True,
        ),
        CtaParityCase(
            "P02_client_surface_invisible_suppresses",
            requirement=_base_requirement(
                requirement_code="gas_safety",
                compliance_requirement_class="DOCUMENT",
                client_surface_visible=False,
            ),
            action_type="OBLIGATION",
            take_action_suppressed=True,
            primary_none=True,
            secondary=CtaParityExpectedSecondary(absent=True),
            skip_priority_projection=True,
        ),
        CtaParityCase(
            "P03_informational_obligation_view_guidance",
            requirement=_base_requirement(
                requirement_code="generic_ob",
                requirement_type="generic_ob",
                compliance_requirement_class="OBLIGATION",
            ),
            action_type="OBLIGATION",
            primary=CtaParityExpectedPrimary(
                intent="view_guidance",
                kind="navigate",
                handler="navigate",
                route_contains=f"/properties/{pid}#compliance",
                label_equals="View guidance",
            ),
            secondary=CtaParityExpectedSecondary(absent=True),
            priority_primary_action_type="view_requirement",
            priority_primary_action_url=f"/properties/{pid}#compliance",
            priority_primary_action_label_equals="View guidance",
            priority_compliance_engine={"compliance_requirement_class": "OBLIGATION"},
        ),
        CtaParityCase(
            "P04_maintenance_log_issue",
            requirement=_base_requirement(
                requirement_code="maint_x",
                requirement_type="maint_x",
                action_type="MAINTENANCE",
                compliance_requirement_class="DOCUMENT",
            ),
            action_type="MAINTENANCE",
            primary=CtaParityExpectedPrimary(
                intent="maintenance",
                kind="navigate",
                handler="navigate",
                route_contains=f"/operations/issues/new?property_id={pid}",
                label_equals="Log issue",
            ),
            secondary=CtaParityExpectedSecondary(absent=True),
            priority_primary_action_type="upload_evidence",
            priority_primary_action_url=f"/operations/issues/new?property_id={pid}",
            priority_primary_action_label_equals="Log issue",
            priority_compliance_engine={"action_type": "MAINTENANCE", "compliance_requirement_class": "DOCUMENT"},
        ),
        CtaParityCase(
            "P05_job_gas_coordinate_and_secondary_upload",
            requirement=_base_requirement(
                requirement_code="gas_safety",
                requirement_type="gas_safety",
                compliance_requirement_class="JOB",
            ),
            action_type="JOB",
            primary=CtaParityExpectedPrimary(
                intent="coordinate_inspection_evidence",
                kind="navigate",
                handler="navigate",
                route_contains=f"/properties/{pid}#req=gas_safety",
                label_substring="Gas Safety certificate",
            ),
            secondary=CtaParityExpectedSecondary(
                route_contains=doc_q,
                label_substring="Upload",
            ),
            priority_primary_action_type="work_order",
            priority_primary_action_url=f"/properties/{pid}#req=gas_safety",
            priority_primary_action_label_substring="Gas Safety certificate",
            priority_secondary_url_contains=doc_q,
            priority_compliance_engine={"compliance_requirement_class": "JOB"},
        ),
        CtaParityCase(
            "P06_document_gas_upload_navigate",
            requirement=_base_requirement(
                requirement_code="gas_safety",
                requirement_type="gas_safety",
                compliance_requirement_class="DOCUMENT",
            ),
            action_type="DOCUMENT",
            primary=CtaParityExpectedPrimary(
                intent="upload_evidence",
                kind="navigate",
                handler="navigate",
                route_equals=doc_q,
                label_equals="Upload Gas Safety Certificate",
            ),
            secondary=CtaParityExpectedSecondary(absent=True),
            priority_primary_action_type="upload_evidence",
            priority_primary_action_url=doc_q,
            priority_primary_action_label_equals="Upload Gas Safety Certificate",
            priority_compliance_engine=resolve_engine_payload_from_code("gas_safety"),
        ),
        CtaParityCase(
            "P07_guided_multi_mode_smoke_heat",
            requirement=_base_requirement(
                requirement_code="smoke_heat_alarms",
                requirement_type="smoke_heat_alarms",
                compliance_requirement_class="DOCUMENT",
            ),
            action_type="DOCUMENT",
            primary=CtaParityExpectedPrimary(
                intent="guided_evidence_resolution",
                kind="guided_evidence_resolution",
                handler="guided_evidence",
                route_is_none=True,
                label_equals="Add compliance evidence",
            ),
            secondary=CtaParityExpectedSecondary(absent=True),
            priority_primary_action_type="guided_evidence_resolution",
            priority_primary_action_url_is_empty=True,
            priority_primary_action_label_equals="Add compliance evidence",
            priority_compliance_engine=resolve_engine_payload_from_code("smoke_heat_alarms"),
        ),
        CtaParityCase(
            "P08_guided_unavailable_missing_ids",
            requirement={
                "requirement_id": None,
                "property_id": None,
                "requirement_type": "smoke_heat_alarms",
                "requirement_code": "smoke_heat_alarms",
                "compliance_requirement_class": "DOCUMENT",
            },
            property_id=None,
            action_type="DOCUMENT",
            primary=CtaParityExpectedPrimary(
                intent="guided_evidence_unavailable",
                kind="guided_evidence_resolution",
                handler="guided_evidence_unavailable",
                route_is_none=True,
                label_equals="Guided resolution unavailable",
                metadata_incomplete=True,
            ),
            secondary=CtaParityExpectedSecondary(route_contains="/documents"),
            priority_primary_action_type="guided_evidence_resolution",
            priority_primary_action_url_is_empty=True,
            priority_primary_action_label_equals="Guided resolution unavailable",
            priority_secondary_url_contains="/documents",
            priority_compliance_engine=resolve_engine_payload_from_code("smoke_heat_alarms"),
        ),
        CtaParityCase(
            "P09_direct_structured_declaration_only",
            requirement=_base_requirement(
                requirement_code="custom_evidence_row",
                requirement_type="custom_evidence_row",
                compliance_requirement_class="DOCUMENT",
                registry_metadata={
                    "evidence_resolution": {
                        "allowed_evidence_modes": ["STRUCTURED_DECLARATION"],
                        "primary_resolution_workflow": "DIRECT_EVIDENCE_ACTION",
                    },
                },
            ),
            action_type="DOCUMENT",
            primary=CtaParityExpectedPrimary(
                intent="direct_evidence_action",
                kind="direct_evidence_action",
                handler="direct_evidence",
                route_is_none=True,
                label_equals="Submit compliance declaration",
                evidence_mode="STRUCTURED_DECLARATION",
            ),
            secondary=CtaParityExpectedSecondary(absent=True),
            priority_primary_action_type="guided_evidence_resolution",
            priority_primary_action_url_is_empty=True,
            priority_primary_action_label_equals="Submit compliance declaration",
            priority_compliance_engine={
                "compliance_requirement_class": "DOCUMENT",
                "registry_metadata": {
                    "evidence_resolution": {
                        "allowed_evidence_modes": ["STRUCTURED_DECLARATION"],
                        "primary_resolution_workflow": "DIRECT_EVIDENCE_ACTION",
                    },
                },
            },
        ),
        CtaParityCase(
            "P10_document_default_upload_when_no_engine_modes",
            requirement=_base_requirement(
                requirement_code="parity_plain_doc",
                requirement_type="parity_plain_doc",
                compliance_requirement_class="DOCUMENT",
            ),
            action_type="DOCUMENT",
            primary=CtaParityExpectedPrimary(
                intent="upload_evidence",
                kind="navigate",
                handler="navigate",
                route_equals=doc_q,
                label_equals="Upload document",
            ),
            secondary=CtaParityExpectedSecondary(absent=True),
            priority_primary_action_type="upload_evidence",
            priority_primary_action_url=doc_q,
            priority_primary_action_label_equals="Upload document",
            priority_compliance_engine={"compliance_requirement_class": "DOCUMENT"},
        ),
    ]


def priority_action_row_from_requirement(req: Dict[str, Any]) -> Dict[str, Any]:
    """Minimal `client_priority_stream` row shape for `resolve_take_action_for_priority_action`."""
    return {
        "related_property_id": req.get("property_id") or "",
        "related_requirement_id": req.get("requirement_id") or "",
        "requirement_code": str(req.get("requirement_code") or req.get("requirement_type") or "").strip(),
        "jurisdiction": req.get("jurisdiction") or CTA_PARITY_JURISDICTION,
        "registry_metadata": req.get("registry_metadata") if isinstance(req.get("registry_metadata"), dict) else {},
        "display_label": req.get("display_label"),
    }
