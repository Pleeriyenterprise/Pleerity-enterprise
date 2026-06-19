"""
Discovery erasure, legal hold, suppression, and lifecycle governance — Stage T.

GDPR-aligned lifecycle enforcement without CRM deletion, routes, or schedulers.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional

from database import database
from services.discovery.discovery_audit_service import DiscoveryAuditService
from services.discovery.discovery_models import (
    DISCOVERY_PROSPECTS_COLLECTION,
    DISCOVERY_SUPPRESSION_RECORDS_COLLECTION,
    DiscoveryErasureStatus,
    DiscoveryReviewStatus,
    email_hash,
    phone_hash,
)
from services.discovery.discovery_prospect_service import (
    DiscoveryProspectError,
    DiscoveryProspectService,
)
from services.discovery.discovery_retention_service import DiscoveryRetentionService


PII_FIELDS_TO_ANONYMISE = (
    "email",
    "phone",
    "contact_name",
    "company_name",
    "website",
    "location",
    "raw_payload_reference",
)


@dataclass(frozen=True)
class LifecycleAttribution:
    actor_id: str
    actor_email: str
    timestamp: Optional[datetime] = None

    def resolved_timestamp(self) -> datetime:
        return self.timestamp or datetime.now(timezone.utc)


@dataclass
class ErasureValidationResult:
    valid: bool
    errors: List[str] = field(default_factory=list)


@dataclass
class SuppressionValidationResult:
    valid: bool
    errors: List[str] = field(default_factory=list)


class DiscoveryErasureServiceError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


class DiscoveryErasureService:
    """Erasure workflow, legal hold, suppression persistence, lifecycle summaries."""

    @staticmethod
    def _iso(dt: datetime) -> str:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    @staticmethod
    def validate_erasure_request(
        prospect: Mapping[str, Any],
    ) -> ErasureValidationResult:
        errors: List[str] = []
        if not prospect.get("prospect_id"):
            errors.append("prospect_id is required")
        if prospect.get("erasure_status") == DiscoveryErasureStatus.ERASED.value:
            errors.append("prospect already erased")
        if bool(prospect.get("legal_hold")):
            errors.append("legal_hold blocks erasure execution")
        return ErasureValidationResult(valid=len(errors) == 0, errors=errors)

    @staticmethod
    def validate_legal_hold(
        prospect: Mapping[str, Any],
        *,
        applying: bool,
    ) -> List[str]:
        errors: List[str] = []
        if not prospect.get("prospect_id"):
            errors.append("prospect_id is required")
        if applying and bool(prospect.get("legal_hold")):
            errors.append("legal_hold already active")
        if not applying and not bool(prospect.get("legal_hold")):
            errors.append("legal_hold not active")
        return errors

    @staticmethod
    def validate_suppression_record(record: Mapping[str, Any]) -> SuppressionValidationResult:
        errors: List[str] = []
        if not record.get("suppression_id"):
            errors.append("suppression_id is required")
        if not record.get("email_hash") and not record.get("phone_hash"):
            errors.append("email_hash or phone_hash is required")
        if record.get("active") is None:
            errors.append("active flag is required")
        return SuppressionValidationResult(valid=len(errors) == 0, errors=errors)

    @staticmethod
    def build_erasure_summary(prospect: Mapping[str, Any]) -> str:
        status = str(prospect.get("erasure_status") or DiscoveryErasureStatus.ACTIVE.value)
        requested = prospect.get("erasure_requested_at") or "Not requested"
        erased = prospect.get("erased_at") or "Not executed"
        return (
            f"Erasure Status:\n{status}\n\n"
            f"Erasure Requested At:\n{requested}\n\n"
            f"Erased At:\n{erased}\n\n"
            f"Legal Hold:\n{'Yes' if prospect.get('legal_hold') else 'No'}"
        )

    @staticmethod
    def build_suppression_summary(
        prospect: Mapping[str, Any],
        *,
        suppression_records: Optional[List[Mapping[str, Any]]] = None,
    ) -> str:
        active = [
            r
            for r in (suppression_records or [])
            if r.get("active") is True
            or str(r.get("prospect_id")) == str(prospect.get("prospect_id"))
        ]
        if prospect.get("erasure_status") == DiscoveryErasureStatus.ERASED.value:
            state = "Active"
        elif active:
            state = "Active"
        else:
            state = "None"
        return (
            f"Suppression:\n{state}\n\n"
            f"Email Hash Retained:\n{'Yes' if prospect.get('email_hash') else 'No'}\n\n"
            f"Phone Hash Retained:\n{'Yes' if prospect.get('phone_hash') else 'No'}"
        )

    @staticmethod
    def build_lifecycle_summary(
        prospect: Mapping[str, Any],
        *,
        evaluated_at: Optional[datetime] = None,
        suppression_records: Optional[List[Mapping[str, Any]]] = None,
    ) -> str:
        retention = DiscoveryRetentionService.evaluate_retention_status(
            prospect, evaluated_at=evaluated_at
        )
        purge = DiscoveryRetentionService.determine_purge_eligibility(
            prospect, evaluated_at=evaluated_at
        )
        expiry_line = (
            retention.expiry_at.date().isoformat()
            if retention.expiry_at
            else "Indefinite"
        )
        retention_line = "Valid" if retention.status == "valid" else retention.status.title()
        erasure_status = str(prospect.get("erasure_status") or "none")
        suppression = DiscoveryErasureService.build_suppression_summary(
            prospect, suppression_records=suppression_records
        ).split("\n\n")[0].split("\n")[1]
        purge_line = "Yes" if purge.eligible else "No"
        return (
            f"Retention:\n{retention_line}\n\n"
            f"Retention Expiry:\n{expiry_line}\n\n"
            f"Legal Hold:\n{'Yes' if prospect.get('legal_hold') else 'No'}\n\n"
            f"Erasure Status:\n{erasure_status}\n\n"
            f"Suppression:\n{suppression}\n\n"
            f"Purge Eligibility:\n{purge_line}"
        )

    @staticmethod
    async def create_suppression_record(
        prospect: Mapping[str, Any],
        *,
        source: str = "erasure",
        reason: Optional[str] = None,
        attribution: Optional[LifecycleAttribution] = None,
    ) -> Dict[str, Any]:
        email_h = prospect.get("email_hash") or email_hash(prospect.get("email"))
        phone_h = prospect.get("phone_hash") or phone_hash(prospect.get("phone"))
        now = (attribution.resolved_timestamp() if attribution else datetime.now(timezone.utc))
        record = {
            "suppression_id": f"DSUP-{uuid.uuid4().hex[:12].upper()}",
            "prospect_id": prospect.get("prospect_id"),
            "email_hash": email_h,
            "phone_hash": phone_h,
            "content_hash": prospect.get("content_hash"),
            "source": source,
            "reason": reason or "post_erasure_suppression",
            "active": True,
            "erased_at": prospect.get("erased_at") or DiscoveryErasureService._iso(now),
            "created_at": DiscoveryErasureService._iso(now),
            "created_by_id": attribution.actor_id if attribution else None,
            "created_by_email": attribution.actor_email if attribution else None,
        }
        validation = DiscoveryErasureService.validate_suppression_record(record)
        if not validation.valid:
            raise DiscoveryErasureServiceError(
                "INVALID_SUPPRESSION",
                "; ".join(validation.errors),
            )
        db = database.get_db()
        await db[DISCOVERY_SUPPRESSION_RECORDS_COLLECTION].insert_one(record)
        return record

    @staticmethod
    async def _persist_lifecycle_audit(
        event_type: str,
        prospect: Mapping[str, Any],
        attribution: LifecycleAttribution,
        *,
        details: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        merged = dict(details or {})
        merged["lifecycle_context"] = {
            "actor_id": attribution.actor_id,
            "actor_email": attribution.actor_email,
            "timestamp": attribution.resolved_timestamp().isoformat(),
            "prospect_id": prospect.get("prospect_id"),
            "legal_hold": bool(prospect.get("legal_hold")),
            "erasure_status": prospect.get("erasure_status"),
        }
        return await DiscoveryAuditService.create_audit_event(
            event_type=event_type,
            prospect_id=prospect.get("prospect_id"),
            run_id=prospect.get("discovery_run_id"),
            campaign_id=prospect.get("campaign_id"),
            provider=prospect.get("provider"),
            actor_id=attribution.actor_id,
            actor_email=attribution.actor_email,
            details=merged,
            content_hash=prospect.get("content_hash"),
            created_at=attribution.resolved_timestamp(),
        )

    @staticmethod
    async def request_erasure(
        prospect_id: str,
        attribution: LifecycleAttribution,
        *,
        reason_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        prospect = await DiscoveryProspectService.get_prospect(prospect_id)
        if not prospect:
            raise DiscoveryErasureServiceError(
                "PROSPECT_NOT_FOUND", f"Prospect {prospect_id} not found"
            )
        validation = DiscoveryErasureService.validate_erasure_request(prospect)
        if not validation.valid:
            raise DiscoveryErasureServiceError(
                "INVALID_ERASURE_REQUEST", "; ".join(validation.errors)
            )

        now = attribution.resolved_timestamp()
        db = database.get_db()
        await db[DISCOVERY_PROSPECTS_COLLECTION].update_one(
            {"prospect_id": prospect_id},
            {
                "$set": {
                    "erasure_requested_at": DiscoveryErasureService._iso(now),
                    "updated_at": DiscoveryErasureService._iso(now),
                }
            },
        )
        updated = await DiscoveryProspectService.get_prospect(prospect_id)
        assert updated is not None

        audits = [
            await DiscoveryErasureService._persist_lifecycle_audit(
                "ERASURE_REQUESTED",
                updated,
                attribution,
                details={"reason_code": reason_code},
            ),
            await DiscoveryErasureService._persist_lifecycle_audit(
                "PROSPECT_ERASURE_REQUESTED",
                updated,
                attribution,
                details={"reason_code": reason_code},
            ),
        ]
        return {"prospect": updated, "audits": audits}

    @staticmethod
    async def execute_erasure(
        prospect_id: str,
        attribution: LifecycleAttribution,
        *,
        reason_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        prospect = await DiscoveryProspectService.get_prospect(prospect_id)
        if not prospect:
            raise DiscoveryErasureServiceError(
                "PROSPECT_NOT_FOUND", f"Prospect {prospect_id} not found"
            )
        validation = DiscoveryErasureService.validate_erasure_request(prospect)
        if not validation.valid:
            raise DiscoveryErasureServiceError(
                "INVALID_ERASURE_REQUEST", "; ".join(validation.errors)
            )

        now = attribution.resolved_timestamp()
        email_h = prospect.get("email_hash") or email_hash(prospect.get("email"))
        phone_h = prospect.get("phone_hash") or phone_hash(prospect.get("phone"))
        content_h = prospect.get("content_hash")

        anonymised: Dict[str, Any] = {
            "erasure_status": DiscoveryErasureStatus.ERASED.value,
            "erased_at": DiscoveryErasureService._iso(now),
            "email": None,
            "phone": None,
            "contact_name": "[ERASED]",
            "company_name": "[ERASED]",
            "website": None,
            "location": None,
            "raw_payload_reference": None,
            "email_hash": email_h,
            "phone_hash": phone_h,
            "content_hash": content_h,
            "updated_at": DiscoveryErasureService._iso(now),
        }

        db = database.get_db()
        await db[DISCOVERY_PROSPECTS_COLLECTION].update_one(
            {"prospect_id": prospect_id},
            {"$set": anonymised},
        )
        updated = await DiscoveryProspectService.get_prospect(prospect_id)
        assert updated is not None

        suppression = await DiscoveryErasureService.create_suppression_record(
            updated,
            source="erasure",
            reason=reason_code or "gdpr_erasure",
            attribution=attribution,
        )

        audits = [
            await DiscoveryErasureService._persist_lifecycle_audit(
                "ERASURE_EXECUTED",
                updated,
                attribution,
                details={
                    "reason_code": reason_code,
                    "suppression_id": suppression.get("suppression_id"),
                    "pii_anonymised": list(PII_FIELDS_TO_ANONYMISE),
                },
            ),
            await DiscoveryErasureService._persist_lifecycle_audit(
                "PROSPECT_ERASED",
                updated,
                attribution,
                details={"reason_code": reason_code},
            ),
        ]
        return {
            "prospect": updated,
            "suppression": suppression,
            "audits": audits,
        }

    @staticmethod
    async def apply_legal_hold(
        prospect_id: str,
        attribution: LifecycleAttribution,
        *,
        hold_reason: str,
    ) -> Dict[str, Any]:
        if not hold_reason or not str(hold_reason).strip():
            raise DiscoveryErasureServiceError(
                "MISSING_HOLD_REASON", "hold_reason is required"
            )
        prospect = await DiscoveryProspectService.get_prospect(prospect_id)
        if not prospect:
            raise DiscoveryErasureServiceError(
                "PROSPECT_NOT_FOUND", f"Prospect {prospect_id} not found"
            )
        errors = DiscoveryErasureService.validate_legal_hold(prospect, applying=True)
        if errors:
            raise DiscoveryErasureServiceError("INVALID_LEGAL_HOLD", "; ".join(errors))

        now = attribution.resolved_timestamp()
        db = database.get_db()
        await db[DISCOVERY_PROSPECTS_COLLECTION].update_one(
            {"prospect_id": prospect_id},
            {
                "$set": {
                    "legal_hold": True,
                    "legal_hold_reason": hold_reason,
                    "legal_hold_applied_at": DiscoveryErasureService._iso(now),
                    "legal_hold_applied_by_id": attribution.actor_id,
                    "legal_hold_applied_by_email": attribution.actor_email,
                    "updated_at": DiscoveryErasureService._iso(now),
                }
            },
        )
        updated = await DiscoveryProspectService.get_prospect(prospect_id)
        assert updated is not None
        details = {
            "hold_reason": hold_reason,
            "actor_id": attribution.actor_id,
            "actor_email": attribution.actor_email,
            "timestamp": DiscoveryErasureService._iso(now),
        }
        audits = [
            await DiscoveryErasureService._persist_lifecycle_audit(
                "LEGAL_HOLD_APPLIED",
                updated,
                attribution,
                details=details,
            ),
            await DiscoveryErasureService._persist_lifecycle_audit(
                "LEGAL_HOLD_SET",
                updated,
                attribution,
                details=details,
            ),
        ]
        return {"prospect": updated, "audits": audits}

    @staticmethod
    async def release_legal_hold(
        prospect_id: str,
        attribution: LifecycleAttribution,
        *,
        release_reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        prospect = await DiscoveryProspectService.get_prospect(prospect_id)
        if not prospect:
            raise DiscoveryErasureServiceError(
                "PROSPECT_NOT_FOUND", f"Prospect {prospect_id} not found"
            )
        errors = DiscoveryErasureService.validate_legal_hold(prospect, applying=False)
        if errors:
            raise DiscoveryErasureServiceError("INVALID_LEGAL_HOLD", "; ".join(errors))

        now = attribution.resolved_timestamp()
        db = database.get_db()
        await db[DISCOVERY_PROSPECTS_COLLECTION].update_one(
            {"prospect_id": prospect_id},
            {
                "$set": {
                    "legal_hold": False,
                    "legal_hold_released_at": DiscoveryErasureService._iso(now),
                    "legal_hold_released_by_id": attribution.actor_id,
                    "legal_hold_released_by_email": attribution.actor_email,
                    "updated_at": DiscoveryErasureService._iso(now),
                },
                "$unset": {
                    "legal_hold_reason": "",
                    "legal_hold_applied_at": "",
                },
            },
        )
        updated = await DiscoveryProspectService.get_prospect(prospect_id)
        assert updated is not None
        details = {
            "release_reason": release_reason,
            "actor_id": attribution.actor_id,
            "actor_email": attribution.actor_email,
            "timestamp": DiscoveryErasureService._iso(now),
        }
        audits = [
            await DiscoveryErasureService._persist_lifecycle_audit(
                "LEGAL_HOLD_RELEASED",
                updated,
                attribution,
                details=details,
            ),
        ]
        return {"prospect": updated, "audits": audits}

    @staticmethod
    async def evaluate_lifecycle_purge(
        prospect_id: str,
        attribution: LifecycleAttribution,
        *,
        evaluated_at: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Evaluate purge eligibility and emit PURGE_ELIGIBLE or PURGE_BLOCKED audit."""
        prospect = await DiscoveryProspectService.get_prospect(prospect_id)
        if not prospect:
            raise DiscoveryErasureServiceError(
                "PROSPECT_NOT_FOUND", f"Prospect {prospect_id} not found"
            )
        purge = DiscoveryRetentionService.determine_purge_eligibility(
            prospect, evaluated_at=evaluated_at
        )
        retention = DiscoveryRetentionService.evaluate_retention_status(
            prospect, evaluated_at=evaluated_at
        )

        audits: List[Dict[str, Any]] = []
        if retention.retention_expiry_reached:
            audits.append(
                await DiscoveryErasureService._persist_lifecycle_audit(
                    "RETENTION_EXPIRY_REACHED",
                    prospect,
                    attribution,
                    details={"category": retention.category},
                )
            )

        event_type = "PURGE_ELIGIBLE" if purge.eligible else "PURGE_BLOCKED"
        audits.append(
            await DiscoveryErasureService._persist_lifecycle_audit(
                event_type,
                prospect,
                attribution,
                details={
                    "blocking_reasons": purge.blocking_reasons,
                    "review_required": purge.review_required,
                },
            )
        )
        return {"purge": purge.to_dict(), "retention": retention.to_dict(), "audits": audits}

    @staticmethod
    def determine_purge_eligibility(
        prospect: Mapping[str, Any],
        *,
        evaluated_at: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        return DiscoveryRetentionService.determine_purge_eligibility(
            prospect, evaluated_at=evaluated_at
        ).to_dict()

    @staticmethod
    def verify_anonymisation(prospect: Mapping[str, Any]) -> List[str]:
        errors: List[str] = []
        if prospect.get("erasure_status") != DiscoveryErasureStatus.ERASED.value:
            errors.append("erasure_status is not erased")
        for field in ("email", "phone", "website", "raw_payload_reference"):
            if prospect.get(field):
                errors.append(f"{field} must be cleared after erasure")
        if not prospect.get("email_hash") and not prospect.get("phone_hash"):
            errors.append("suppression hashes must be retained")
        return errors
