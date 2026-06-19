"""
Discovery import service — Stage P.

Sole approved CRM crossing for Discovery:
DiscoveryImportService → LeadService.create_lead()

No routes, UI, providers, notifications, or nurture changes.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional

from services.discovery.discovery_consent_service import (
    DiscoveryConsentService,
    ImportComplianceResult,
)
from services.discovery.discovery_approval_queue_service import (
    DiscoveryApprovalQueueService,
    ImportEligibilityResult,
)
from services.discovery.discovery_audit_service import DiscoveryAuditService
from services.discovery.discovery_metadata_contract import (
    validate_discovery_source_metadata,
)
from services.discovery.discovery_models import (
    DiscoveryDuplicateStatus,
    DiscoveryErasureStatus,
    DiscoveryLawfulBasis,
    DiscoveryReviewStatus,
)
from services.discovery.discovery_prospect_service import (
    DiscoveryProspectError,
    DiscoveryProspectService,
)
from services.lead_models import LeadCreateRequest, LeadServiceInterest, LeadSourcePlatform
from services.lead_service import LeadService

DEFAULT_CONTENT_HASH_VERSION = "1"
DEFAULT_HASH_ALGORITHM = "sha256"
METADATA_SCHEMA_VERSION = "1.0.0"
DISCOVERY_IMPORT_TAG = "discovery_import_v1"

FORBIDDEN_LEAD_METADATA_KEYS = frozenset(
    {"raw_payload", "raw_row", "csv_row", "html_payload", "provider_raw_response"}
)


@dataclass(frozen=True)
class ImportAttribution:
    actor_id: str
    actor_email: str
    timestamp: Optional[datetime] = None

    def resolved_timestamp(self) -> datetime:
        return self.timestamp or datetime.now(timezone.utc)


@dataclass(frozen=True)
class CrmDuplicateResult:
    found: bool
    lead_id: Optional[str] = None


@dataclass
class ImportValidationResult:
    eligible: bool
    blocking_reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    eligibility_checklist: Dict[str, bool] = field(default_factory=dict)
    evaluated_at: Optional[datetime] = None
    compliance_summary: Optional[str] = None
    compliance_audit_events: List[Dict[str, Any]] = field(default_factory=list)
    compliance_result: Optional[ImportComplianceResult] = None


class DiscoveryImportError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


class DiscoveryImportService:
    """Import orchestration — only service permitted to call LeadService.create_lead."""

    @staticmethod
    def _iso(dt: datetime) -> str:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _lineage_for_metadata(
        prospect: Mapping[str, Any],
    ) -> List[Dict[str, Any]]:
        raw = prospect.get("origin_lineage") or []
        if not raw:
            run_id = prospect.get("discovery_run_id")
            content_hash = prospect.get("content_hash")
            ingested = prospect.get("created_at") or datetime.now(timezone.utc).isoformat()
            if run_id and content_hash:
                return [
                    {
                        "provider": str(prospect.get("provider") or "manual"),
                        "provider_reference": prospect.get("provider_reference"),
                        "discovery_run_id": run_id,
                        "discovery_job_id": prospect.get("discovery_job_id"),
                        "campaign_id": prospect.get("campaign_id"),
                        "source_url": prospect.get("source_url"),
                        "content_hash": content_hash,
                        "content_hash_version": DEFAULT_CONTENT_HASH_VERSION,
                        "discovered_at": ingested,
                        "ingested_at": ingested,
                    }
                ]
            return []

        out: List[Dict[str, Any]] = []
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            ingested = entry.get("ingested_at") or prospect.get("created_at")
            discovered = entry.get("discovered_at") or ingested
            run_id = entry.get("discovery_run_id") or prospect.get("discovery_run_id")
            content_hash = entry.get("content_hash") or prospect.get("content_hash")
            if not run_id or not content_hash or not ingested:
                continue
            out.append(
                {
                    "provider": str(entry.get("provider") or prospect.get("provider")),
                    "provider_reference": entry.get("provider_reference"),
                    "discovery_run_id": run_id,
                    "discovery_job_id": entry.get("discovery_job_id"),
                    "campaign_id": entry.get("campaign_id"),
                    "source_url": entry.get("source_url"),
                    "content_hash": content_hash,
                    "content_hash_version": DEFAULT_CONTENT_HASH_VERSION,
                    "discovered_at": discovered,
                    "ingested_at": ingested,
                }
            )
        return out

    @staticmethod
    def build_discovery_source_metadata(
        prospect: Mapping[str, Any],
        *,
        imported_at: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        now = imported_at or datetime.now(timezone.utc)
        lineage = DiscoveryImportService._lineage_for_metadata(prospect)
        erasure = prospect.get("erasure_status") or DiscoveryErasureStatus.ACTIVE.value
        metadata: Dict[str, Any] = {
            "schema_version": METADATA_SCHEMA_VERSION,
            "discovery_provider": str(prospect.get("provider") or "manual"),
            "discovery_channel": prospect.get("discovery_channel"),
            "discovery_campaign_id": prospect.get("campaign_id"),
            "discovery_run_id": prospect.get("discovery_run_id"),
            "discovery_job_id": prospect.get("discovery_job_id"),
            "discovery_prospect_id": prospect.get("prospect_id"),
            "origin_lineage": lineage,
            "content_hash": prospect.get("content_hash"),
            "content_hash_version": DEFAULT_CONTENT_HASH_VERSION,
            "hash_algorithm": DEFAULT_HASH_ALGORITHM,
            "provider_reference": prospect.get("provider_reference"),
            "lawful_basis": prospect.get("lawful_basis"),
            "imported_at": DiscoveryImportService._iso(now),
            "quality_snapshot": {
                "platform_quality_score": int(
                    prospect.get("platform_quality_score") or 0
                ),
                "provider_confidence": int(prospect.get("provider_confidence") or 0),
                "risk_flags": list(prospect.get("risk_flags") or []),
            },
            "erasure_status": erasure,
        }
        return metadata

    @staticmethod
    def validate_metadata_contract(metadata: Mapping[str, Any]) -> List[str]:
        ok, errors = validate_discovery_source_metadata(dict(metadata))
        return [] if ok else errors

    @staticmethod
    async def validate_import_eligibility(
        prospect: Mapping[str, Any],
        *,
        evaluated_at: Optional[datetime] = None,
    ) -> ImportValidationResult:
        base: ImportEligibilityResult = (
            DiscoveryApprovalQueueService.determine_import_eligibility(
                prospect, evaluated_at=evaluated_at
            )
        )
        blocking = list(base.blocking_reasons)
        warnings = list(base.warnings)
        checklist: Dict[str, bool] = {
            "review_status_approved": prospect.get("review_status")
            == DiscoveryReviewStatus.APPROVED.value,
            "not_archived": prospect.get("review_status")
            != DiscoveryReviewStatus.ARCHIVED.value,
            "not_erased": prospect.get("erasure_status")
            != DiscoveryErasureStatus.ERASED.value,
            "not_already_imported": not bool(prospect.get("imported_lead_id")),
            "duplicate_governance_ok": prospect.get("duplicate_status")
            != DiscoveryDuplicateStatus.CONFIRMED.value
            or bool(prospect.get("duplicate_override_reason")),
        }

        if bool(prospect.get("legal_hold")):
            blocking.append("legal_hold active blocks import")
            checklist["legal_hold_clear"] = False
        else:
            checklist["legal_hold_clear"] = True

        compliance = await DiscoveryConsentService.validate_import_compliance(prospect)
        checklist.update(compliance.checklist)
        blocking.extend(compliance.blocking_reasons)
        warnings.extend(compliance.warnings)

        has_contact = bool(
            (prospect.get("email") and str(prospect.get("email")).strip())
            or (prospect.get("phone") and str(prospect.get("phone")).strip())
        )
        checklist["contact_present"] = has_contact
        if not has_contact:
            blocking.append("email or phone required for CRM import")

        lineage = DiscoveryImportService._lineage_for_metadata(prospect)
        checklist["origin_lineage_present"] = len(lineage) >= 1
        if not lineage:
            blocking.append("origin_lineage required for source metadata")

        metadata = DiscoveryImportService.build_discovery_source_metadata(prospect)
        meta_errors = DiscoveryImportService.validate_metadata_contract(metadata)
        checklist["metadata_contract_valid"] = len(meta_errors) == 0
        if meta_errors:
            blocking.append("source metadata contract validation failed")

        summary = DiscoveryConsentService.build_compliance_summary(compliance)

        return ImportValidationResult(
            eligible=len(blocking) == 0,
            blocking_reasons=blocking,
            warnings=warnings,
            eligibility_checklist=checklist,
            evaluated_at=base.evaluated_at,
            compliance_summary=summary,
            compliance_audit_events=list(compliance.compliance_audit_events),
            compliance_result=compliance,
        )

    @staticmethod
    def build_lead_create_payload(
        prospect: Mapping[str, Any],
        *,
        discovery_metadata: Mapping[str, Any],
        imported_at: Optional[datetime] = None,
    ) -> LeadCreateRequest:
        run_id = prospect.get("discovery_run_id") or "unknown"
        provider = str(prospect.get("provider") or "manual")
        tags = [
            DISCOVERY_IMPORT_TAG,
            f"discovery_run:{run_id}",
            f"discovery_provider:{provider}",
        ]
        source_metadata: Dict[str, Any] = {"discovery": dict(discovery_metadata)}
        for key in FORBIDDEN_LEAD_METADATA_KEYS:
            source_metadata.pop(key, None)

        return LeadCreateRequest(
            source_platform=LeadSourcePlatform.IMPORT,
            service_interest=LeadServiceInterest.UNKNOWN,
            name=prospect.get("contact_name") or prospect.get("company_name"),
            email=prospect.get("email"),
            phone=prospect.get("phone"),
            company_name=prospect.get("company_name"),
            marketing_consent=bool(prospect.get("marketing_consent", False)),
            source_metadata=source_metadata,
            tags=tags,
            admin_notes=(
                f"Discovery import prospect_id={prospect.get('prospect_id')} "
                f"run_id={run_id}"
            ),
        )

    @staticmethod
    async def check_crm_duplicate(
        lead_request: LeadCreateRequest,
    ) -> CrmDuplicateResult:
        duplicate = await LeadService.find_duplicate(
            email=lead_request.email,
            phone=lead_request.phone,
            source_metadata=lead_request.source_metadata,
        )
        if duplicate:
            return CrmDuplicateResult(
                found=True, lead_id=duplicate.get("lead_id")
            )
        return CrmDuplicateResult(found=False)

    @staticmethod
    def build_import_audit_context(
        prospect: Mapping[str, Any],
        *,
        attribution: ImportAttribution,
        import_decision_id: Optional[str] = None,
        stage: str,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        ctx: Dict[str, Any] = {
            "stage": stage,
            "import_decision_id": import_decision_id or str(uuid.uuid4()),
            "actor_id": attribution.actor_id,
            "actor_email": attribution.actor_email,
            "timestamp": attribution.resolved_timestamp().isoformat(),
            "prospect_id": prospect.get("prospect_id"),
            "review_status": prospect.get("review_status"),
            "duplicate_status": prospect.get("duplicate_status"),
            "content_hash": prospect.get("content_hash"),
        }
        if extra:
            ctx.update(extra)
        return ctx

    @staticmethod
    async def _persist_audit(
        event_type: str,
        prospect: Mapping[str, Any],
        attribution: ImportAttribution,
        *,
        details: Optional[Dict[str, Any]] = None,
        lead_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        merged = dict(details or {})
        merged["audit_context"] = DiscoveryImportService.build_import_audit_context(
            prospect,
            attribution=attribution,
            stage=event_type,
            extra=merged.get("import_context"),
        )
        return await DiscoveryAuditService.create_audit_event(
            event_type=event_type,
            prospect_id=prospect.get("prospect_id"),
            run_id=prospect.get("discovery_run_id"),
            campaign_id=prospect.get("campaign_id"),
            job_id=prospect.get("discovery_job_id"),
            provider=prospect.get("provider"),
            actor_id=attribution.actor_id,
            actor_email=attribution.actor_email,
            lead_id=lead_id,
            details=merged,
            content_hash=prospect.get("content_hash"),
            created_at=attribution.resolved_timestamp(),
        )

    @staticmethod
    async def mark_import_blocked(
        prospect: Mapping[str, Any],
        attribution: ImportAttribution,
        *,
        failure_code: str,
        failure_message: str,
        blocking_reasons: List[str],
        eligibility_checklist: Optional[Dict[str, bool]] = None,
    ) -> Dict[str, Any]:
        return await DiscoveryImportService._persist_audit(
            "IMPORT_BLOCKED",
            prospect,
            attribution,
            details={
                "failure_code": failure_code,
                "failure_message": failure_message,
                "blocked_reason": failure_message,
                "blocking_reasons": list(blocking_reasons),
                "eligibility_checklist": dict(eligibility_checklist or {}),
            },
        )

    @staticmethod
    async def mark_import_failed(
        prospect: Mapping[str, Any],
        attribution: ImportAttribution,
        *,
        failure_code: str,
        failure_message: str,
        lead_id: Optional[str] = None,
        manual_reconciliation_required: bool = False,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        details = {
            "failure_code": failure_code,
            "failure_message": failure_message,
            "manual_reconciliation_required": manual_reconciliation_required,
        }
        if extra:
            details.update(extra)
        if lead_id:
            details["lead_id"] = lead_id
        return await DiscoveryImportService._persist_audit(
            "IMPORT_FAILED",
            prospect,
            attribution,
            details=details,
            lead_id=lead_id,
        )

    @staticmethod
    async def mark_import_completed(
        prospect_id: str,
        imported_lead_id: str,
        prospect: Mapping[str, Any],
        attribution: ImportAttribution,
        *,
        imported_at: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        try:
            updated = await DiscoveryProspectService.mark_imported(
                prospect_id,
                imported_lead_id,
                imported_at=imported_at or attribution.resolved_timestamp(),
            )
        except DiscoveryProspectError as exc:
            raise DiscoveryImportError(exc.code, exc.message) from exc

        imported_audit = await DiscoveryImportService._persist_audit(
            "PROSPECT_IMPORTED",
            updated,
            attribution,
            details={
                "imported_lead_id": imported_lead_id,
                "from_review_status": prospect.get("review_status"),
                "to_review_status": updated.get("review_status"),
            },
            lead_id=imported_lead_id,
        )
        return {"prospect": updated, "audit": imported_audit}

    @staticmethod
    async def import_prospect(
        prospect_id: str,
        attribution: ImportAttribution,
    ) -> Dict[str, Any]:
        """
        Execute governed import workflow for a single prospect.
        """
        if not attribution.actor_id or not attribution.actor_email:
            raise DiscoveryImportError(
                "MISSING_ATTRIBUTION",
                "actor_id and actor_email are required",
            )

        prospect = await DiscoveryProspectService.get_prospect(prospect_id)
        if not prospect:
            raise DiscoveryImportError(
                "PROSPECT_NOT_FOUND",
                f"Prospect {prospect_id} not found",
            )

        audits: List[Dict[str, Any]] = []

        existing_lead_id = prospect.get("imported_lead_id")
        if existing_lead_id:
            return {
                "status": "idempotent",
                "prospect": prospect,
                "lead_id": existing_lead_id,
                "audits": audits,
                "manual_reconciliation_required": False,
            }

        requested = await DiscoveryImportService._persist_audit(
            "IMPORT_REQUESTED",
            prospect,
            attribution,
            details={
                "import_decision_id": str(uuid.uuid4()),
                "reviewer_id": attribution.actor_id,
            },
        )
        audits.append(requested)

        validation = await DiscoveryImportService.validate_import_eligibility(prospect)
        if not validation.eligible:
            for audit_spec in validation.compliance_audit_events:
                audit_details = dict(audit_spec.get("details") or {})
                audit_details["compliance_summary"] = validation.compliance_summary
                if validation.compliance_result is not None:
                    audit_details["compliance_audit_context"] = (
                        DiscoveryConsentService.build_compliance_audit_context(
                            prospect,
                            validation.compliance_result,
                        )
                    )
                compliance_audit = await DiscoveryImportService._persist_audit(
                    audit_spec["event_type"],
                    prospect,
                    attribution,
                    details=audit_details,
                )
                audits.append(compliance_audit)

            blocked = await DiscoveryImportService.mark_import_blocked(
                prospect,
                attribution,
                failure_code="ELIGIBILITY_FAILED",
                failure_message="Import eligibility validation failed",
                blocking_reasons=validation.blocking_reasons,
                eligibility_checklist=validation.eligibility_checklist,
            )
            audits.append(blocked)
            return {
                "status": "blocked",
                "prospect": prospect,
                "lead_id": None,
                "audits": audits,
                "blocking_reasons": validation.blocking_reasons,
                "manual_reconciliation_required": False,
            }

        imported_at = attribution.resolved_timestamp()
        discovery_metadata = DiscoveryImportService.build_discovery_source_metadata(
            prospect, imported_at=imported_at
        )
        meta_errors = DiscoveryImportService.validate_metadata_contract(
            discovery_metadata
        )
        if meta_errors:
            blocked = await DiscoveryImportService.mark_import_blocked(
                prospect,
                attribution,
                failure_code="METADATA_INVALID",
                failure_message="Discovery source metadata contract invalid",
                blocking_reasons=meta_errors,
                eligibility_checklist=validation.eligibility_checklist,
            )
            audits.append(blocked)
            return {
                "status": "blocked",
                "prospect": prospect,
                "lead_id": None,
                "audits": audits,
                "blocking_reasons": meta_errors,
                "manual_reconciliation_required": False,
            }

        lead_request = DiscoveryImportService.build_lead_create_payload(
            prospect,
            discovery_metadata=discovery_metadata,
            imported_at=imported_at,
        )

        crm_dup = await DiscoveryImportService.check_crm_duplicate(lead_request)
        if crm_dup.found:
            blocked = await DiscoveryImportService.mark_import_blocked(
                prospect,
                attribution,
                failure_code="CRM_DUPLICATE",
                failure_message="CRM duplicate lead exists",
                blocking_reasons=["crm_duplicate_found"],
                eligibility_checklist=validation.eligibility_checklist,
            )
            audits.append(blocked)
            return {
                "status": "blocked",
                "prospect": prospect,
                "lead_id": crm_dup.lead_id,
                "audits": audits,
                "blocking_reasons": ["crm_duplicate_found"],
                "manual_reconciliation_required": False,
            }

        validated = await DiscoveryImportService._persist_audit(
            "IMPORT_VALIDATED",
            prospect,
            attribution,
            details={
                "eligibility_checklist": validation.eligibility_checklist,
                "duplicate_status_at_validation": prospect.get("duplicate_status"),
                "content_hash": prospect.get("content_hash"),
            },
        )
        audits.append(validated)

        try:
            lead_result = await LeadService.create_lead(
                lead_request,
                actor_id=attribution.actor_id,
                actor_type="admin",
            )
        except Exception as exc:
            failed = await DiscoveryImportService.mark_import_failed(
                prospect,
                attribution,
                failure_code="LEAD_SERVICE_ERROR",
                failure_message=str(exc)[:500],
            )
            audits.append(failed)
            return {
                "status": "failed",
                "prospect": prospect,
                "lead_id": None,
                "audits": audits,
                "failure_code": "LEAD_SERVICE_ERROR",
                "manual_reconciliation_required": False,
            }

        if lead_result.get("is_duplicate"):
            failed = await DiscoveryImportService.mark_import_failed(
                prospect,
                attribution,
                failure_code="CRM_DUPLICATE_ON_CREATE",
                failure_message="LeadService returned duplicate without new lead",
                lead_id=lead_result.get("lead_id"),
            )
            audits.append(failed)
            return {
                "status": "failed",
                "prospect": prospect,
                "lead_id": lead_result.get("lead_id"),
                "audits": audits,
                "failure_code": "CRM_DUPLICATE_ON_CREATE",
                "manual_reconciliation_required": False,
            }

        lead_id = lead_result.get("lead_id")
        if not lead_id:
            failed = await DiscoveryImportService.mark_import_failed(
                prospect,
                attribution,
                failure_code="LEAD_ID_MISSING",
                failure_message="LeadService did not return lead_id",
            )
            audits.append(failed)
            return {
                "status": "failed",
                "prospect": prospect,
                "lead_id": None,
                "audits": audits,
                "failure_code": "LEAD_ID_MISSING",
                "manual_reconciliation_required": False,
            }

        try:
            completion = await DiscoveryImportService.mark_import_completed(
                prospect_id,
                lead_id,
                prospect,
                attribution,
                imported_at=imported_at,
            )
        except DiscoveryImportError as exc:
            failed = await DiscoveryImportService.mark_import_failed(
                prospect,
                attribution,
                failure_code=exc.code,
                failure_message=exc.message,
                lead_id=lead_id,
                manual_reconciliation_required=True,
            )
            audits.append(failed)
            return {
                "status": "failed",
                "prospect": prospect,
                "lead_id": lead_id,
                "audits": audits,
                "failure_code": exc.code,
                "manual_reconciliation_required": True,
            }

        audits.append(completion["audit"])
        return {
            "status": "imported",
            "prospect": completion["prospect"],
            "lead_id": lead_id,
            "audits": audits,
            "manual_reconciliation_required": False,
        }
