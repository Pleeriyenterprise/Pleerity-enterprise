"""
Discovery platform quality scoring — Stage J.

Deterministic, governance-controlled quality assessment.
Provider confidence is bounded supporting input only — never authoritative.
No dedupe, import, routes, or LeadService integration.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Union

from services.discovery.discovery_hashing import validate_origin_lineage
from services.discovery.discovery_models import (
    DiscoveryBusinessType,
    DiscoveryLandlordType,
    DiscoveryLawfulBasis,
    OriginLineageEntry,
    ProspectLocation,
)

# Category maximums — sum to 100.
IDENTITY_COMPLETENESS_MAX = 40
BUSINESS_CONTEXT_MAX = 25
SOURCE_QUALITY_MAX = 15
GOVERNANCE_QUALITY_MAX = 10
PROVIDER_CONFIDENCE_MAX = 10

PROVIDER_CONFIDENCE_WEIGHT = 0.10  # Max 10% of total score


@dataclass(frozen=True)
class QualityInputs:
    """Normalised inputs for deterministic quality scoring."""

    email: Optional[str] = None
    phone: Optional[str] = None
    company_name: Optional[str] = None
    website: Optional[str] = None
    source_url: Optional[str] = None
    provider_reference: Optional[str] = None
    business_type: DiscoveryBusinessType = DiscoveryBusinessType.UNKNOWN
    landlord_type: DiscoveryLandlordType = DiscoveryLandlordType.UNKNOWN
    location: Optional[ProspectLocation] = None
    lawful_basis: DiscoveryLawfulBasis = DiscoveryLawfulBasis.LEGITIMATE_INTEREST_B2B
    marketing_consent: bool = False
    marketing_consent_explicit: bool = False
    provider_confidence: int = 0
    risk_flags: List[str] = field(default_factory=list)
    origin_lineage: List[OriginLineageEntry] = field(default_factory=list)


@dataclass(frozen=True)
class QualityFactorBreakdown:
    identity_completeness: int
    business_context: int
    source_quality: int
    governance_quality: int
    provider_confidence_contribution: int
    total: int

    def to_display_lines(self) -> List[str]:
        return [
            f"Identity Completeness: {self.identity_completeness}/{IDENTITY_COMPLETENESS_MAX}",
            f"Business Context: {self.business_context}/{BUSINESS_CONTEXT_MAX}",
            f"Source Quality: {self.source_quality}/{SOURCE_QUALITY_MAX}",
            f"Governance Quality: {self.governance_quality}/{GOVERNANCE_QUALITY_MAX}",
            f"Provider Confidence: {self.provider_confidence_contribution}/{PROVIDER_CONFIDENCE_MAX}",
            f"Total: {self.total}",
        ]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "identity_completeness": {
                "score": self.identity_completeness,
                "max": IDENTITY_COMPLETENESS_MAX,
            },
            "business_context": {
                "score": self.business_context,
                "max": BUSINESS_CONTEXT_MAX,
            },
            "source_quality": {
                "score": self.source_quality,
                "max": SOURCE_QUALITY_MAX,
            },
            "governance_quality": {
                "score": self.governance_quality,
                "max": GOVERNANCE_QUALITY_MAX,
            },
            "provider_confidence": {
                "score": self.provider_confidence_contribution,
                "max": PROVIDER_CONFIDENCE_MAX,
            },
            "total": self.total,
        }


def _present(value: Optional[str]) -> bool:
    return bool(value and str(value).strip())


def _location_present(location: Optional[ProspectLocation]) -> bool:
    if location is None:
        return False
    return any(
        _present(getattr(location, part, None))
        for part in ("city", "region", "postcode", "country")
    )


def _lineage_valid(origin_lineage: Sequence[Union[OriginLineageEntry, Mapping[str, Any]]]) -> bool:
    if not origin_lineage:
        return False
    return len(validate_origin_lineage(list(origin_lineage))) == 0


def _bounded_provider_contribution(provider_confidence: int) -> int:
    """Provider confidence contributes at most 10% of total score (10 points)."""
    clamped = max(0, min(100, int(provider_confidence)))
    return min(PROVIDER_CONFIDENCE_MAX, (clamped * PROVIDER_CONFIDENCE_MAX) // 100)


class DiscoveryQualityService:
    @staticmethod
    def validate_quality_inputs(
        inputs: QualityInputs,
    ) -> List[str]:
        errors: List[str] = []
        if inputs.provider_confidence < 0 or inputs.provider_confidence > 100:
            errors.append("provider_confidence must be between 0 and 100")
        if inputs.lawful_basis == DiscoveryLawfulBasis.UNKNOWN:
            errors.append("lawful_basis cannot be unknown for quality scoring")
        return errors

    @staticmethod
    def build_quality_factor_breakdown(inputs: QualityInputs) -> QualityFactorBreakdown:
        identity = 0
        if _present(inputs.email):
            identity += 10
        if _present(inputs.phone):
            identity += 10
        if _present(inputs.company_name):
            identity += 10
        if _present(inputs.website):
            identity += 10
        identity = min(IDENTITY_COMPLETENESS_MAX, identity)

        business = 0
        if inputs.business_type != DiscoveryBusinessType.UNKNOWN:
            business += 10
        if inputs.landlord_type != DiscoveryLandlordType.UNKNOWN:
            business += 8
        if _location_present(inputs.location):
            business += 7
        business = min(BUSINESS_CONTEXT_MAX, business)

        source = 0
        if _present(inputs.source_url):
            source += 5
        if _present(inputs.provider_reference):
            source += 5
        if _lineage_valid(inputs.origin_lineage):
            source += 5
        source = min(SOURCE_QUALITY_MAX, source)

        governance = 0
        if inputs.lawful_basis != DiscoveryLawfulBasis.UNKNOWN:
            governance += 4
        if inputs.marketing_consent_explicit:
            governance += 3
        if not inputs.risk_flags:
            governance += 3
        governance = min(GOVERNANCE_QUALITY_MAX, governance)

        provider_part = _bounded_provider_contribution(inputs.provider_confidence)

        total = min(
            100,
            identity + business + source + governance + provider_part,
        )
        return QualityFactorBreakdown(
            identity_completeness=identity,
            business_context=business,
            source_quality=source,
            governance_quality=governance,
            provider_confidence_contribution=provider_part,
            total=total,
        )

    @staticmethod
    def compute_platform_quality_score(inputs: QualityInputs) -> int:
        """Authoritative platform quality score — deterministic 0–100."""
        return DiscoveryQualityService.build_quality_factor_breakdown(inputs).total

    @staticmethod
    def calculate_review_priority(
        platform_quality_score: int,
        *,
        inputs: Optional[QualityInputs] = None,
        risk_flags: Optional[List[str]] = None,
        lawful_basis: Optional[DiscoveryLawfulBasis] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        company_name: Optional[str] = None,
        website: Optional[str] = None,
    ) -> int:
        """
        Higher value surfaces first in review queues.
        Lower quality, governance gaps, and risk increase priority.
        """
        flags = risk_flags or (inputs.risk_flags if inputs else []) or []
        basis = lawful_basis or (inputs.lawful_basis if inputs else None)

        priority = 100 - max(0, min(100, int(platform_quality_score)))
        priority += len(flags) * 5

        if basis is None or basis == DiscoveryLawfulBasis.UNKNOWN:
            priority += 15

        em = email if email is not None else (inputs.email if inputs else None)
        ph = phone if phone is not None else (inputs.phone if inputs else None)
        co = company_name if company_name is not None else (inputs.company_name if inputs else None)
        web = website if website is not None else (inputs.website if inputs else None)

        identity_fields = sum(
            1 for v in (em, ph, co, web) if _present(v)
        )
        if identity_fields == 0:
            priority += 20
        elif identity_fields == 1:
            priority += 10

        return max(0, min(100, priority))

    @staticmethod
    def explain_quality_score(inputs: QualityInputs) -> Dict[str, Any]:
        """Template-driven explanation — no AI-generated text."""
        breakdown = DiscoveryQualityService.build_quality_factor_breakdown(inputs)
        strengths: List[str] = []
        weaknesses: List[str] = []
        improvements: List[str] = []

        if breakdown.identity_completeness >= 30:
            strengths.append("Strong identity completeness across contact fields.")
        elif breakdown.identity_completeness < 20:
            weaknesses.append("Identity completeness is low — missing core contact fields.")
            improvements.append("Add email, phone, company name, or website where available.")

        if breakdown.business_context >= 18:
            strengths.append("Business context fields are well populated.")
        elif breakdown.business_context < 10:
            weaknesses.append("Business context is sparse.")
            improvements.append("Provide business_type, landlord_type, and location.")

        if breakdown.source_quality >= 10:
            strengths.append("Source provenance fields are present.")
        else:
            weaknesses.append("Source quality signals are weak.")
            improvements.append("Include source_url, provider_reference, and valid origin lineage.")

        if breakdown.governance_quality >= 8:
            strengths.append("Governance signals meet expectations.")
        else:
            weaknesses.append("Governance quality needs attention.")
            if inputs.lawful_basis == DiscoveryLawfulBasis.UNKNOWN:
                improvements.append("Declare a valid lawful_basis before import.")
            if inputs.risk_flags:
                improvements.append("Resolve risk_flags before approval.")
            if not inputs.marketing_consent_explicit:
                improvements.append("Explicitly set marketing_consent when known.")

        if breakdown.provider_confidence_contribution > 0:
            strengths.append(
                f"Provider confidence contributed {breakdown.provider_confidence_contribution} "
                f"points (capped at {PROVIDER_CONFIDENCE_MAX})."
            )

        if not strengths:
            strengths.append("Baseline prospect record created — review recommended.")

        return {
            "score": breakdown.total,
            "breakdown": breakdown.to_dict(),
            "breakdown_lines": breakdown.to_display_lines(),
            "strengths": strengths,
            "weaknesses": weaknesses,
            "recommended_improvements": improvements,
        }

    @staticmethod
    def quality_inputs_from_mapping(data: Mapping[str, Any]) -> QualityInputs:
        """Build QualityInputs from prospect document or request dict."""
        location = data.get("location")
        loc_model: Optional[ProspectLocation] = None
        if location is not None:
            if isinstance(location, ProspectLocation):
                loc_model = location
            elif isinstance(location, dict):
                loc_model = ProspectLocation(**location)

        lineage_raw = data.get("origin_lineage") or []
        lineage: List[OriginLineageEntry] = []
        for entry in lineage_raw:
            if isinstance(entry, OriginLineageEntry):
                lineage.append(entry)
            elif isinstance(entry, dict):
                lineage.append(OriginLineageEntry(**entry))

        bt = data.get("business_type", DiscoveryBusinessType.UNKNOWN)
        if not isinstance(bt, DiscoveryBusinessType):
            bt = DiscoveryBusinessType(str(bt))

        lt = data.get("landlord_type", DiscoveryLandlordType.UNKNOWN)
        if not isinstance(lt, DiscoveryLandlordType):
            lt = DiscoveryLandlordType(str(lt))

        lb = data.get("lawful_basis", DiscoveryLawfulBasis.LEGITIMATE_INTEREST_B2B)
        if not isinstance(lb, DiscoveryLawfulBasis):
            lb = DiscoveryLawfulBasis(str(lb))

        flags = list(data.get("risk_flags") or [])

        return QualityInputs(
            email=data.get("email"),
            phone=data.get("phone"),
            company_name=data.get("company_name"),
            website=data.get("website"),
            source_url=data.get("source_url"),
            provider_reference=data.get("provider_reference"),
            business_type=bt,
            landlord_type=lt,
            location=loc_model,
            lawful_basis=lb,
            marketing_consent=bool(data.get("marketing_consent", False)),
            marketing_consent_explicit=bool(data.get("marketing_consent_explicit", False)),
            provider_confidence=int(data.get("provider_confidence", 0)),
            risk_flags=flags,
            origin_lineage=lineage,
        )
