"""
Phase 2 S1 — lifecycle-aware extraction profile registry (read-only).

Registry only: no extraction pipeline behaviour changes in S1–S3.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional, Tuple

from services.lifecycle_semantics_types import LifecycleSemantics

ProfileId = str


@dataclass(frozen=True)
class ExtractionProfile:
    profile_id: ProfileId
    lifecycle_semantics: LifecycleSemantics
    extracted_fields: Tuple[str, ...]
    required_fields: Tuple[str, ...]
    optional_fields: Tuple[str, ...]
    forbidden_fields: Tuple[str, ...]
    storage_slugs: FrozenSet[str] = field(default_factory=frozenset)
    description: str = ""


_PROFILES: Dict[ProfileId, ExtractionProfile] = {
    "certificate_standard_v1": ExtractionProfile(
        profile_id="certificate_standard_v1",
        lifecycle_semantics="EXPIRY_BASED",
        extracted_fields=(
            "doc_type",
            "certificate_number",
            "issue_date",
            "expiry_date",
            "inspector_company",
            "inspector_id",
            "address_line_1",
            "postcode",
            "confidence",
        ),
        required_fields=("expiry_date",),
        optional_fields=(
            "issue_date",
            "certificate_number",
            "inspector_company",
            "inspector_id",
        ),
        forbidden_fields=(),
        storage_slugs=frozenset(
            {
                "gas_safety",
                "eicr",
                "epc",
                "fire_risk_assessment",
                "portable_appliance_test",
                "fire_alarm",
                "hmo_fire_risk",
                "hmo_fire_risk_evidence",
                "pat_testing",
            }
        ),
        description="Standard expiry-based certificate extraction profile",
    ),
    "hmo_licence_v1": ExtractionProfile(
        profile_id="hmo_licence_v1",
        lifecycle_semantics="EXPIRY_BASED",
        extracted_fields=(
            "doc_type",
            "licence_number",
            "issue_date",
            "expiry_date",
            "licensing_authority",
            "address_line_1",
            "postcode",
            "confidence",
        ),
        required_fields=("expiry_date",),
        optional_fields=("issue_date", "licence_number", "licensing_authority"),
        forbidden_fields=(),
        storage_slugs=frozenset(
            {"hmo_license", "property_licence", "selective_license", "hmo_licensing"}
        ),
        description="HMO / selective / additional licensing — expiry-based",
    ),
    "tenancy_agreement_v1": ExtractionProfile(
        profile_id="tenancy_agreement_v1",
        lifecycle_semantics="TENANCY_LIFECYCLE",
        extracted_fields=(
            "tenancy_start_date",
            "fixed_term_end_date",
            "tenant_name",
            "landlord_name",
            "agreement_type",
            "rent_amount",
            "confidence",
        ),
        required_fields=("tenancy_start_date",),
        optional_fields=("fixed_term_end_date", "tenant_name", "agreement_type", "rent_amount"),
        forbidden_fields=("expiry_date", "confirmed_expiry_date", "certificate_number"),
        storage_slugs=frozenset({"tenancy_agreement", "occupation_contract"}),
        description="Tenancy agreement / occupation contract lifecycle",
    ),
    "deposit_protection_v1": ExtractionProfile(
        profile_id="deposit_protection_v1",
        lifecycle_semantics="DECLARATION_BASED",
        extracted_fields=(
            "scheme_name",
            "scheme_reference",
            "protection_date",
            "deposit_amount",
            "deposit_received_date",
            "confidence",
        ),
        required_fields=("protection_date",),
        optional_fields=("scheme_name", "scheme_reference", "deposit_amount"),
        forbidden_fields=("expiry_date", "confirmed_expiry_date"),
        storage_slugs=frozenset(
            {
                "deposit_pi",
                "tenancy_deposit_protection",
                "deposit_prescribed_info",
            }
        ),
        description="Tenancy deposit protection evidence",
    ),
    "prescribed_information_v1": ExtractionProfile(
        profile_id="prescribed_information_v1",
        lifecycle_semantics="DECLARATION_BASED",
        extracted_fields=(
            "served_date",
            "served_to",
            "service_method",
            "guide_version",
            "confidence",
        ),
        required_fields=("served_date",),
        optional_fields=("served_to", "service_method", "guide_version"),
        forbidden_fields=("expiry_date", "confirmed_expiry_date"),
        storage_slugs=frozenset({"how_to_rent", "prescribed_information"}),
        description="Prescribed information / guide delivery proof",
    ),
    "right_to_rent_v1": ExtractionProfile(
        profile_id="right_to_rent_v1",
        lifecycle_semantics="OCCUPANCY_LIFECYCLE",
        extracted_fields=(
            "tenant_name",
            "check_date",
            "document_type",
            "right_to_rent_status",
            "follow_up_date",
            "confidence",
        ),
        required_fields=("check_date",),
        optional_fields=("follow_up_date", "document_type", "tenant_name"),
        forbidden_fields=("expiry_date", "confirmed_expiry_date"),
        storage_slugs=frozenset({"right_to_rent", "right_to_rent_checks"}),
        description="Right to rent occupancy check evidence",
    ),
    "legionella_review_v1": ExtractionProfile(
        profile_id="legionella_review_v1",
        lifecycle_semantics="REVIEW_BASED",
        extracted_fields=(
            "assessment_date",
            "assessor_type",
            "risk_level",
            "next_review_date",
            "control_measures_summary",
            "confidence",
        ),
        required_fields=("assessment_date",),
        optional_fields=("next_review_date", "risk_level", "assessor_type"),
        forbidden_fields=("expiry_date", "confirmed_expiry_date", "extracted_expiry_date"),
        storage_slugs=frozenset({"legionella", "lead_testing"}),
        description="Legionella / lead review-based assessment",
    ),
    "landlord_registration_v1": ExtractionProfile(
        profile_id="landlord_registration_v1",
        lifecycle_semantics="REVIEW_BASED",
        extracted_fields=(
            "registration_number",
            "issuing_authority",
            "issue_date",
            "registration_status",
            "confidence",
        ),
        required_fields=("registration_number",),
        optional_fields=("issue_date", "issuing_authority", "registration_status"),
        forbidden_fields=("expiry_date", "confirmed_expiry_date"),
        storage_slugs=frozenset(
            {
                "landlord_registration",
                "scotland_landlord_registration",
                "landlord_registration_ni",
                "rent_smart_wales",
            }
        ),
        description="Landlord registration evidence",
    ),
    "event_completion_v1": ExtractionProfile(
        profile_id="event_completion_v1",
        lifecycle_semantics="EVENT_BASED",
        extracted_fields=(
            "event_date",
            "event_type",
            "completion_notes",
            "installer_name",
            "confidence",
        ),
        required_fields=("event_date",),
        optional_fields=("event_type", "completion_notes", "installer_name"),
        forbidden_fields=("expiry_date", "confirmed_expiry_date"),
        storage_slugs=frozenset(
            {
                "smoke_heat_alarms",
                "smoke_alarms",
                "co_alarms",
                "fire_detection",
            }
        ),
        description="Event-based completion evidence (alarms, servicing)",
    ),
    "operational_workflow_v1": ExtractionProfile(
        profile_id="operational_workflow_v1",
        lifecycle_semantics="OPERATIONAL",
        extracted_fields=(
            "completion_date",
            "responsible_person",
            "work_summary",
            "confidence",
        ),
        required_fields=("completion_date",),
        optional_fields=("responsible_person", "work_summary"),
        forbidden_fields=("expiry_date", "confirmed_expiry_date"),
        storage_slugs=frozenset(
            {"fitness_for_human_habitation", "repairing_standard"}
        ),
        description="Operational workflow completion evidence",
    ),
    "supporting_document_v1": ExtractionProfile(
        profile_id="supporting_document_v1",
        lifecycle_semantics="REVIEW_BASED",
        extracted_fields=(
            "doc_type",
            "document_date",
            "reference_number",
            "summary",
            "confidence",
        ),
        required_fields=("document_date",),
        optional_fields=("reference_number", "summary", "doc_type"),
        forbidden_fields=(),
        storage_slugs=frozenset(),
        description="Fallback supporting document profile",
    ),
}

PROFILE_BY_STORAGE_SLUG: Dict[str, ProfileId] = {}
for _profile in _PROFILES.values():
    for _slug in _profile.storage_slugs:
        PROFILE_BY_STORAGE_SLUG[_slug] = _profile.profile_id

PROFILE_BY_SEMANTICS: Dict[LifecycleSemantics, ProfileId] = {
    "EXPIRY_BASED": "certificate_standard_v1",
    "REVIEW_BASED": "legionella_review_v1",
    "EVENT_BASED": "event_completion_v1",
    "DECLARATION_BASED": "deposit_protection_v1",
    "TENANCY_LIFECYCLE": "tenancy_agreement_v1",
    "OCCUPANCY_LIFECYCLE": "right_to_rent_v1",
    "OPERATIONAL": "operational_workflow_v1",
}

EXTRACTION_PROFILE_IDS: FrozenSet[str] = frozenset(_PROFILES.keys())


def get_extraction_profile(profile_id: Optional[str]) -> Optional[ExtractionProfile]:
    if not profile_id:
        return None
    return _PROFILES.get(str(profile_id).strip())


def list_extraction_profiles() -> List[ExtractionProfile]:
    return list(_PROFILES.values())


def profile_for_storage_slug(slug: Optional[str]) -> Optional[ProfileId]:
    if not slug:
        return None
    from services.requirement_code_registry import normalize_requirement_code

    normalized = normalize_requirement_code(slug)
    key = str(normalized).strip().lower() if normalized else str(slug).strip().lower()
    return PROFILE_BY_STORAGE_SLUG.get(key)


def default_profile_for_semantics(semantics: LifecycleSemantics) -> ProfileId:
    return PROFILE_BY_SEMANTICS.get(semantics, "supporting_document_v1")
