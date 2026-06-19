"""
Discovery consent and compliance validation — Stage R.

Governance-only: lawful basis, marketing consent, LIA framework, internal suppression.
No TPS/CTPS integrations, notifications, or CRM writes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional

from database import database
from services.discovery.discovery_models import (
    DISCOVERY_PROSPECTS_COLLECTION,
    DISCOVERY_SUPPRESSION_RECORDS_COLLECTION,
    DiscoveryErasureStatus,
    DiscoveryLawfulBasis,
    email_hash,
    phone_hash,
)

# UK GDPR lawful basis values supported at import validation.
SUPPORTED_LAWFUL_BASIS = frozenset(
    {
        "consent",
        "legitimate_interest",
        DiscoveryLawfulBasis.LEGITIMATE_INTEREST_B2B.value,
        "contract",
        "legal_obligation",
        "vital_interest",
        "public_task",
    }
)

LEGITIMATE_INTEREST_BASES = frozenset(
    {
        "legitimate_interest",
        DiscoveryLawfulBasis.LEGITIMATE_INTEREST_B2B.value,
    }
)

MARKETING_CONSENT_FALSE_REQUIRED_BASES = frozenset(
    {
        "legal_obligation",
        "vital_interest",
        "public_task",
    }
)

# Reserved — not implemented in Stage R.
SUPPRESSION_SOURCE_CRM = "crm_suppression"
SUPPRESSION_SOURCE_TPS = "tps"
SUPPRESSION_SOURCE_CTPS = "ctps"
SUPPRESSION_SOURCE_ERASED_PROSPECT = "erased_prospect"
SUPPRESSION_SOURCE_DISCOVERY_RECORD = "discovery_suppression_record"
SUPPRESSION_SOURCE_IMPORTED_LEAD = "imported_lead_suppression"


@dataclass
class LawfulBasisValidationResult:
    valid: bool
    lawful_basis: Optional[str] = None
    errors: List[str] = field(default_factory=list)


@dataclass
class MarketingConsentValidationResult:
    valid: bool
    errors: List[str] = field(default_factory=list)


@dataclass
class LiaValidationResult:
    required: bool
    complete: bool
    errors: List[str] = field(default_factory=list)
    lia_reference: Optional[str] = None


@dataclass
class SuppressionCheckResult:
    status: str  # allowed | blocked | warning
    allowed: bool
    matched_sources: List[str] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)


@dataclass
class ImportComplianceResult:
    compliant: bool
    blocking_reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    lawful_basis: LawfulBasisValidationResult = field(
        default_factory=lambda: LawfulBasisValidationResult(valid=False)
    )
    marketing_consent: MarketingConsentValidationResult = field(
        default_factory=lambda: MarketingConsentValidationResult(valid=False)
    )
    lia: LiaValidationResult = field(
        default_factory=lambda: LiaValidationResult(required=False, complete=True)
    )
    suppression: SuppressionCheckResult = field(
        default_factory=lambda: SuppressionCheckResult(status="allowed", allowed=True)
    )
    compliance_audit_events: List[Dict[str, Any]] = field(default_factory=list)
    checklist: Dict[str, bool] = field(default_factory=dict)


class DiscoveryConsentService:
    """Compliance enforcement for discovery import eligibility."""

    @staticmethod
    def _normalise_basis(value: Any) -> Optional[str]:
        if value is None:
            return None
        text = str(value).strip().lower()
        return text or None

    @staticmethod
    def _lia_fields(prospect: Mapping[str, Any]) -> Dict[str, Any]:
        return {
            "lia_reference": prospect.get("lia_reference")
            or prospect.get("lawful_basis_declaration_id"),
            "lia_completed": prospect.get("lia_completed"),
            "lia_review_date": prospect.get("lia_review_date"),
        }

    @staticmethod
    def validate_lawful_basis(
        prospect: Mapping[str, Any],
    ) -> LawfulBasisValidationResult:
        basis = DiscoveryConsentService._normalise_basis(prospect.get("lawful_basis"))
        if not basis or basis == DiscoveryLawfulBasis.UNKNOWN.value:
            return LawfulBasisValidationResult(
                valid=False,
                lawful_basis=basis,
                errors=["lawful_basis is invalid or unknown"],
            )
        if basis not in SUPPORTED_LAWFUL_BASIS:
            return LawfulBasisValidationResult(
                valid=False,
                lawful_basis=basis,
                errors=[f"lawful_basis '{basis}' is not supported"],
            )
        return LawfulBasisValidationResult(valid=True, lawful_basis=basis, errors=[])

    @staticmethod
    def validate_legitimate_interest(
        prospect: Mapping[str, Any],
    ) -> LiaValidationResult:
        basis = DiscoveryConsentService._normalise_basis(prospect.get("lawful_basis"))
        if basis not in LEGITIMATE_INTEREST_BASES:
            return LiaValidationResult(required=False, complete=True, errors=[])

        lia = DiscoveryConsentService._lia_fields(prospect)
        reference = lia.get("lia_reference")
        completed = lia.get("lia_completed")
        errors: List[str] = []

        if not reference or not str(reference).strip():
            errors.append("lia_reference is required for legitimate_interest")
        if completed is not True:
            errors.append("lia_completed must be true for legitimate_interest")

        return LiaValidationResult(
            required=True,
            complete=len(errors) == 0,
            errors=errors,
            lia_reference=str(reference).strip() if reference else None,
        )

    @staticmethod
    def validate_marketing_consent(
        prospect: Mapping[str, Any],
    ) -> MarketingConsentValidationResult:
        marketing_consent = bool(prospect.get("marketing_consent", False))
        if not marketing_consent:
            return MarketingConsentValidationResult(valid=True, errors=[])

        basis = DiscoveryConsentService._normalise_basis(prospect.get("lawful_basis"))
        errors: List[str] = []

        if basis in MARKETING_CONSENT_FALSE_REQUIRED_BASES:
            errors.append(
                f"marketing_consent=true is not permitted for lawful_basis={basis}"
            )
            return MarketingConsentValidationResult(valid=False, errors=errors)

        if basis == DiscoveryLawfulBasis.CONSENT.value:
            return MarketingConsentValidationResult(valid=True, errors=[])

        if basis in LEGITIMATE_INTEREST_BASES:
            lia = DiscoveryConsentService.validate_legitimate_interest(prospect)
            if lia.complete:
                return MarketingConsentValidationResult(valid=True, errors=[])
            errors.append(
                "marketing_consent=true with legitimate_interest requires valid LIA"
            )
            return MarketingConsentValidationResult(valid=False, errors=errors)

        if basis == "contract":
            if bool(prospect.get("marketing_consent_justified", False)):
                return MarketingConsentValidationResult(valid=True, errors=[])
            errors.append(
                "marketing_consent=true with contract requires marketing_consent_justified"
            )
            return MarketingConsentValidationResult(valid=False, errors=errors)

        errors.append(
            "marketing_consent=true requires lawful_basis=consent or valid legitimate_interest LIA"
        )
        return MarketingConsentValidationResult(valid=False, errors=errors)

    @staticmethod
    async def check_suppression_lists(
        prospect: Mapping[str, Any],
    ) -> SuppressionCheckResult:
        """
        Internal suppression only (Stage R).
        Reserved: CRM suppression, TPS, CTPS — no external calls.
        """
        matched: List[str] = []
        reasons: List[str] = []

        if prospect.get("erasure_status") == DiscoveryErasureStatus.ERASED.value:
            matched.append(SUPPRESSION_SOURCE_ERASED_PROSPECT)
            reasons.append("prospect erasure_status is erased")

        email_h = prospect.get("email_hash") or email_hash(prospect.get("email"))
        phone_h = prospect.get("phone_hash") or phone_hash(prospect.get("phone"))

        db = database.get_db()
        prospects_coll = db[DISCOVERY_PROSPECTS_COLLECTION]

        hash_clauses: List[Dict[str, Any]] = []
        if email_h:
            hash_clauses.append({"email_hash": email_h})
        if phone_h:
            hash_clauses.append({"phone_hash": phone_h})

        if hash_clauses:
            erased_match = await prospects_coll.find_one(
                {
                    "erasure_status": DiscoveryErasureStatus.ERASED.value,
                    "prospect_id": {"$ne": prospect.get("prospect_id")},
                    "$or": hash_clauses,
                }
            )
            if erased_match:
                matched.append(SUPPRESSION_SOURCE_ERASED_PROSPECT)
                reasons.append("contact hash matches an erased prospect")

        suppression_coll = db[DISCOVERY_SUPPRESSION_RECORDS_COLLECTION]
        if hash_clauses:
            record_match = await suppression_coll.find_one(
                {
                    "active": True,
                    "$or": hash_clauses,
                }
            )
            if record_match:
                matched.append(SUPPRESSION_SOURCE_DISCOVERY_RECORD)
                reasons.append("contact hash matches discovery suppression record")

        if prospect.get("imported_lead_id") and prospect.get("suppression_import_block"):
            matched.append(SUPPRESSION_SOURCE_IMPORTED_LEAD)
            reasons.append("imported lead suppression marker present")

        if matched:
            return SuppressionCheckResult(
                status="blocked",
                allowed=False,
                matched_sources=list(dict.fromkeys(matched)),
                reasons=reasons,
            )

        return SuppressionCheckResult(
            status="allowed",
            allowed=True,
            matched_sources=[],
            reasons=[],
        )

    @staticmethod
    def build_compliance_audit_context(
        prospect: Mapping[str, Any],
        compliance: ImportComplianceResult,
        *,
        evaluated_at: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        now = evaluated_at or datetime.now(timezone.utc)
        lia = DiscoveryConsentService._lia_fields(prospect)
        return {
            "evaluated_at": now.isoformat().replace("+00:00", "Z"),
            "prospect_id": prospect.get("prospect_id"),
            "lawful_basis": compliance.lawful_basis.lawful_basis,
            "marketing_consent": bool(prospect.get("marketing_consent", False)),
            "lia_reference": lia.get("lia_reference"),
            "lia_completed": lia.get("lia_completed"),
            "lia_review_date": lia.get("lia_review_date"),
            "suppression_status": compliance.suppression.status,
            "suppression_sources": list(compliance.suppression.matched_sources),
            "compliance_checklist": dict(compliance.checklist),
        }

    @staticmethod
    def build_compliance_summary(
        compliance: ImportComplianceResult,
    ) -> str:
        """Template-driven compliance summary — no AI output."""
        lb_line = "Valid" if compliance.lawful_basis.valid else "Invalid"
        mc_line = "Valid" if compliance.marketing_consent.valid else "Invalid"

        if compliance.lia.required:
            lia_line = "Complete" if compliance.lia.complete else "Required / Incomplete"
        else:
            lia_line = "Not Required"

        if compliance.suppression.status == "blocked":
            suppression_line = "Match"
        elif compliance.suppression.status == "warning":
            suppression_line = "Warning"
        else:
            suppression_line = "No Match"

        import_line = "PASS" if compliance.compliant else "FAIL"

        return (
            f"Lawful Basis:\n{lb_line}\n\n"
            f"Marketing Consent:\n{mc_line}\n\n"
            f"LIA:\n{lia_line}\n\n"
            f"Suppression:\n{suppression_line}\n\n"
            f"Import Compliance:\n{import_line}"
        )

    @staticmethod
    def _compliance_audit_events(
        compliance: ImportComplianceResult,
    ) -> List[Dict[str, Any]]:
        events: List[Dict[str, Any]] = []
        if not compliance.lia.complete and compliance.lia.required:
            events.append(
                {
                    "event_type": "LIA_VALIDATION_FAILED",
                    "details": {
                        "failure_code": "LIA_VALIDATION_FAILED",
                        "errors": list(compliance.lia.errors),
                        "lia_reference": compliance.lia.lia_reference,
                    },
                }
            )
        if not compliance.marketing_consent.valid:
            events.append(
                {
                    "event_type": "CONSENT_VALIDATION_FAILED",
                    "details": {
                        "failure_code": "CONSENT_VALIDATION_FAILED",
                        "errors": list(compliance.marketing_consent.errors),
                    },
                }
            )
        if compliance.suppression.status == "blocked":
            events.append(
                {
                    "event_type": "SUPPRESSION_MATCH",
                    "details": {
                        "failure_code": "SUPPRESSION_MATCH",
                        "matched_sources": list(compliance.suppression.matched_sources),
                        "reasons": list(compliance.suppression.reasons),
                    },
                }
            )
        return events

    @staticmethod
    async def validate_import_compliance(
        prospect: Mapping[str, Any],
    ) -> ImportComplianceResult:
        blocking: List[str] = []
        warnings: List[str] = []
        checklist: Dict[str, bool] = {}

        lawful = DiscoveryConsentService.validate_lawful_basis(prospect)
        checklist["lawful_basis_valid"] = lawful.valid
        if not lawful.valid:
            blocking.extend(lawful.errors)

        lia = DiscoveryConsentService.validate_legitimate_interest(prospect)
        checklist["lia_complete"] = (not lia.required) or lia.complete
        if lia.required and not lia.complete:
            blocking.extend(lia.errors)

        marketing = DiscoveryConsentService.validate_marketing_consent(prospect)
        checklist["marketing_consent_valid"] = marketing.valid
        if not marketing.valid:
            blocking.extend(marketing.errors)

        suppression = await DiscoveryConsentService.check_suppression_lists(prospect)
        checklist["suppression_clear"] = suppression.allowed
        if suppression.status == "blocked":
            blocking.extend(suppression.reasons)
        elif suppression.status == "warning":
            warnings.extend(suppression.reasons)

        result = ImportComplianceResult(
            compliant=len(blocking) == 0,
            blocking_reasons=blocking,
            warnings=warnings,
            lawful_basis=lawful,
            marketing_consent=marketing,
            lia=lia,
            suppression=suppression,
            checklist=checklist,
        )
        result.compliance_audit_events = DiscoveryConsentService._compliance_audit_events(
            result
        )
        return result
