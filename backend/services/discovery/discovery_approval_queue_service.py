"""
Discovery approval queue service — Stage N.

Reviewer decisions, import eligibility, and audit integration.
No imports, CRM writes, routes, UI, or nurture.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional, Sequence

from database import database
from services.discovery.discovery_audit_service import DiscoveryAuditService
from services.discovery.discovery_duplicate_service import (
    DiscoveryDuplicateService,
    DuplicateClassification,
)
from services.discovery.discovery_models import (
    DISCOVERY_PROSPECTS_COLLECTION,
    PLATFORM_TENANT_ID,
    DiscoveryDuplicateStatus,
    DiscoveryErasureStatus,
    DiscoveryLawfulBasis,
    DiscoveryReviewStatus,
)
from services.discovery.discovery_prospect_service import (
    DiscoveryProspectError,
    DiscoveryProspectService,
)

HIGH_PRIORITY_THRESHOLD = 70

REVIEWER_ACTIONS = frozenset(
    {
        "approve",
        "reject",
        "request_changes",
        "mark_duplicate",
        "clear_duplicate",
        "archive",
    }
)


@dataclass(frozen=True)
class ReviewerAttribution:
    actor_id: str
    actor_email: str
    timestamp: Optional[datetime] = None

    def resolved_timestamp(self) -> datetime:
        return self.timestamp or datetime.now(timezone.utc)


@dataclass(frozen=True)
class ReviewQueueFilters:
    review_status: Optional[str] = None
    duplicate_status: Optional[str] = None
    provider: Optional[str] = None
    campaign_id: Optional[str] = None
    quality_score_min: Optional[int] = None
    quality_score_max: Optional[int] = None
    review_priority_min: Optional[int] = None
    review_priority_max: Optional[int] = None
    created_from: Optional[datetime] = None
    created_to: Optional[datetime] = None
    tenant_id: str = PLATFORM_TENANT_ID
    skip: int = 0
    limit: int = 50


@dataclass(frozen=True)
class ReviewQueueResult:
    items: List[Dict[str, Any]]
    total: int
    skip: int
    limit: int


@dataclass
class ImportEligibilityResult:
    eligible: bool
    blocking_reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    evaluated_at: Optional[datetime] = None


class DiscoveryApprovalQueueError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


class DiscoveryApprovalQueueService:
    """Review and approval governance — no CRM or import execution."""

    @staticmethod
    def validate_reviewer_attribution(attribution: ReviewerAttribution) -> List[str]:
        errors: List[str] = []
        if not attribution.actor_id or not str(attribution.actor_id).strip():
            errors.append("actor_id is required")
        if not attribution.actor_email or not str(attribution.actor_email).strip():
            errors.append("actor_email is required")
        if "@" not in str(attribution.actor_email):
            errors.append("actor_email must be a valid email")
        return errors

    @staticmethod
    def validate_reviewer_action(
        action: str,
        prospect: Mapping[str, Any],
        *,
        change_request_notes: Optional[str] = None,
        reason_code: Optional[str] = None,
        override_reason: Optional[str] = None,
        override_notes: Optional[str] = None,
        override_reason_code: Optional[str] = None,
    ) -> List[str]:
        errors: List[str] = []
        normalised = str(action or "").strip().lower()
        if normalised not in REVIEWER_ACTIONS:
            errors.append(f"unknown reviewer action: {action}")

        review_status = prospect.get("review_status")
        duplicate_status = prospect.get("duplicate_status")
        erasure_status = prospect.get("erasure_status")

        if erasure_status == DiscoveryErasureStatus.ERASED.value:
            errors.append("prospect is erased")

        if normalised == "approve":
            if review_status not in (
                DiscoveryReviewStatus.NEEDS_REVIEW.value,
                DiscoveryReviewStatus.DUPLICATE_DETECTED.value,
            ):
                errors.append(
                    f"approve not allowed from review_status={review_status}"
                )
            lb = prospect.get("lawful_basis")
            if not lb or lb == DiscoveryLawfulBasis.UNKNOWN.value:
                errors.append("lawful_basis must be valid for approval")

        elif normalised == "reject":
            if review_status not in (
                DiscoveryReviewStatus.NEEDS_REVIEW.value,
                DiscoveryReviewStatus.DUPLICATE_DETECTED.value,
            ):
                errors.append(
                    f"reject not allowed from review_status={review_status}"
                )
            if not reason_code or not str(reason_code).strip():
                errors.append("reason_code is required for reject")

        elif normalised == "request_changes":
            if review_status not in (
                DiscoveryReviewStatus.NEEDS_REVIEW.value,
                DiscoveryReviewStatus.DUPLICATE_DETECTED.value,
            ):
                errors.append(
                    f"request_changes not allowed from review_status={review_status}"
                )
            if not change_request_notes or not str(change_request_notes).strip():
                errors.append("change_request_notes is required for request_changes")

        elif normalised == "archive":
            if review_status not in (
                DiscoveryReviewStatus.APPROVED.value,
                DiscoveryReviewStatus.REJECTED.value,
                DiscoveryReviewStatus.IMPORTED.value,
            ):
                errors.append(
                    f"archive not allowed from review_status={review_status}"
                )

        elif normalised == "mark_duplicate":
            if review_status not in (
                DiscoveryReviewStatus.NEEDS_REVIEW.value,
                DiscoveryReviewStatus.DUPLICATE_DETECTED.value,
            ):
                errors.append(
                    f"mark_duplicate not allowed from review_status={review_status}"
                )

        elif normalised == "clear_duplicate":
            if duplicate_status == DiscoveryDuplicateStatus.NONE.value:
                errors.append("duplicate_status is already none")

        return errors

    @staticmethod
    def validate_duplicate_override(
        prospect: Mapping[str, Any],
        *,
        attribution: Optional[ReviewerAttribution] = None,
        override_reason: Optional[str] = None,
        override_notes: Optional[str] = None,
        override_reason_code: Optional[str] = None,
        for_approval: bool = False,
    ) -> List[str]:
        errors: List[str] = []
        duplicate_status = prospect.get("duplicate_status")
        review_status = prospect.get("review_status")
        needs_override = (
            duplicate_status == DiscoveryDuplicateStatus.CONFIRMED.value
            or review_status == DiscoveryReviewStatus.DUPLICATE_DETECTED.value
        )
        if not needs_override or not for_approval:
            return errors

        notes = override_notes or override_reason
        reason = override_reason_code or override_reason
        errors.extend(
            DiscoveryDuplicateService.validate_duplicate_override(
                reviewer_id=attribution.actor_id if attribution else None,
                reason_code=reason,
                notes=notes,
                timestamp=attribution.resolved_timestamp() if attribution else None,
            )
        )
        return errors

    @staticmethod
    def determine_import_eligibility(
        prospect: Mapping[str, Any],
        *,
        evaluated_at: Optional[datetime] = None,
    ) -> ImportEligibilityResult:
        now = evaluated_at or datetime.now(timezone.utc)
        blocking: List[str] = []
        warnings: List[str] = []

        review_status = prospect.get("review_status")
        if review_status != DiscoveryReviewStatus.APPROVED.value:
            blocking.append("review_status must be approved")

        if review_status == DiscoveryReviewStatus.ARCHIVED.value:
            blocking.append("prospect is archived")

        if prospect.get("erasure_status") == DiscoveryErasureStatus.ERASED.value:
            blocking.append("prospect is erased")

        lawful_basis = prospect.get("lawful_basis")
        if not lawful_basis or lawful_basis == DiscoveryLawfulBasis.UNKNOWN.value:
            blocking.append("lawful_basis is invalid")

        if prospect.get("imported_lead_id"):
            blocking.append("prospect already imported")

        duplicate_status = prospect.get("duplicate_status")
        if duplicate_status == DiscoveryDuplicateStatus.CONFIRMED.value:
            if not prospect.get("duplicate_override_reason"):
                blocking.append(
                    "confirmed duplicate requires override before import"
                )
        elif duplicate_status == DiscoveryDuplicateStatus.POSSIBLE.value:
            warnings.append("possible_duplicate — review before import")

        if review_status == DiscoveryReviewStatus.DUPLICATE_DETECTED.value:
            blocking.append("review_status duplicate_detected blocks import")

        return ImportEligibilityResult(
            eligible=len(blocking) == 0,
            blocking_reasons=blocking,
            warnings=warnings,
            evaluated_at=now,
        )

    @staticmethod
    def build_import_readiness_summary(
        prospect: Mapping[str, Any],
    ) -> Dict[str, Any]:
        eligibility = DiscoveryApprovalQueueService.determine_import_eligibility(
            prospect
        )
        return {
            "eligible": eligibility.eligible,
            "blocking_reasons": list(eligibility.blocking_reasons),
            "warnings": list(eligibility.warnings),
            "review_status": prospect.get("review_status"),
            "duplicate_status": prospect.get("duplicate_status"),
            "imported_lead_id": prospect.get("imported_lead_id"),
            "evaluated_at": eligibility.evaluated_at.isoformat()
            if eligibility.evaluated_at
            else None,
        }

    @staticmethod
    def build_review_audit_context(
        prospect: Mapping[str, Any],
        *,
        action: str,
        attribution: ReviewerAttribution,
        review_decision_id: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        ts = attribution.resolved_timestamp()
        ctx: Dict[str, Any] = {
            "action": action,
            "review_decision_id": review_decision_id or str(uuid.uuid4()),
            "actor_id": attribution.actor_id,
            "actor_email": attribution.actor_email,
            "timestamp": ts.isoformat(),
            "review_status": prospect.get("review_status"),
            "duplicate_status": prospect.get("duplicate_status"),
            "import_readiness": DiscoveryApprovalQueueService.build_import_readiness_summary(
                prospect
            ),
        }
        if extra:
            ctx.update(extra)
        return ctx

    @staticmethod
    async def create_review_audit_event(
        event_type: str,
        prospect: Mapping[str, Any],
        attribution: ReviewerAttribution,
        *,
        action: str,
        details: Optional[Dict[str, Any]] = None,
        duplicate_evidence_snapshot: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        merged_details = dict(details or {})
        merged_details["audit_context"] = DiscoveryApprovalQueueService.build_review_audit_context(
            prospect,
            action=action,
            attribution=attribution,
            extra=merged_details.get("review_decision"),
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
            content_hash=prospect.get("content_hash"),
            details=merged_details,
            duplicate_evidence_snapshot=duplicate_evidence_snapshot,
            created_at=attribution.resolved_timestamp(),
        )

    @staticmethod
    def _require_attribution(attribution: ReviewerAttribution) -> None:
        errors = DiscoveryApprovalQueueService.validate_reviewer_attribution(
            attribution
        )
        if errors:
            raise DiscoveryApprovalQueueError(
                "MISSING_ATTRIBUTION",
                "; ".join(errors),
            )

    @staticmethod
    async def _get_prospect_or_raise(prospect_id: str) -> Dict[str, Any]:
        prospect = await DiscoveryProspectService.get_prospect(prospect_id)
        if not prospect:
            raise DiscoveryApprovalQueueError(
                "PROSPECT_NOT_FOUND",
                f"Prospect {prospect_id} not found",
            )
        return prospect

    @staticmethod
    async def approve_prospect(
        prospect_id: str,
        attribution: ReviewerAttribution,
        *,
        override_reason: Optional[str] = None,
        override_notes: Optional[str] = None,
        reason_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        DiscoveryApprovalQueueService._require_attribution(attribution)
        prospect = await DiscoveryApprovalQueueService._get_prospect_or_raise(
            prospect_id
        )
        action_errors = DiscoveryApprovalQueueService.validate_reviewer_action(
            "approve",
            prospect,
        )
        if action_errors:
            raise DiscoveryApprovalQueueError(
                "INVALID_ACTION",
                "; ".join(action_errors),
            )
        override_errors = DiscoveryApprovalQueueService.validate_duplicate_override(
            prospect,
            attribution=attribution,
            override_reason=override_reason,
            override_notes=override_notes,
            override_reason_code=reason_code,
            for_approval=True,
        )
        if override_errors:
            raise DiscoveryApprovalQueueError(
                "OVERRIDE_REQUIRED",
                "; ".join(override_errors),
            )

        warnings: List[str] = []
        if prospect.get("duplicate_status") == DiscoveryDuplicateStatus.POSSIBLE.value:
            warnings.append("possible_duplicate approved with warning")

        prior_status = prospect.get("review_status")
        try:
            updated, _prepared = await DiscoveryProspectService.update_review_status(
                prospect_id,
                DiscoveryReviewStatus.APPROVED,
                actor_id=attribution.actor_id,
                override_reason=override_reason,
            )
        except DiscoveryProspectError as exc:
            raise DiscoveryApprovalQueueError(exc.code, exc.message) from exc

        audit = await DiscoveryApprovalQueueService.create_review_audit_event(
            "PROSPECT_APPROVED",
            updated,
            attribution,
            action="approve",
            details={
                "from_review_status": prior_status,
                "to_review_status": updated.get("review_status"),
                "override_reason": override_reason,
                "reason_code": reason_code,
                "override_notes": override_notes,
                "warnings": warnings,
            },
        )
        eligibility = DiscoveryApprovalQueueService.determine_import_eligibility(
            updated
        )
        return {
            "prospect": updated,
            "audit": audit,
            "warnings": warnings,
            "import_eligible": eligibility.eligible,
            "import_blocking_reasons": eligibility.blocking_reasons,
        }

    @staticmethod
    async def reject_prospect(
        prospect_id: str,
        attribution: ReviewerAttribution,
        *,
        reason_code: str,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        DiscoveryApprovalQueueService._require_attribution(attribution)
        prospect = await DiscoveryApprovalQueueService._get_prospect_or_raise(
            prospect_id
        )
        action_errors = DiscoveryApprovalQueueService.validate_reviewer_action(
            "reject",
            prospect,
            reason_code=reason_code,
        )
        if action_errors:
            raise DiscoveryApprovalQueueError(
                "INVALID_ACTION",
                "; ".join(action_errors),
            )

        prior_status = prospect.get("review_status")
        try:
            updated, _prepared = await DiscoveryProspectService.update_review_status(
                prospect_id,
                DiscoveryReviewStatus.REJECTED,
                actor_id=attribution.actor_id,
            )
        except DiscoveryProspectError as exc:
            raise DiscoveryApprovalQueueError(exc.code, exc.message) from exc

        audit = await DiscoveryApprovalQueueService.create_review_audit_event(
            "PROSPECT_REJECTED",
            updated,
            attribution,
            action="reject",
            details={
                "from_review_status": prior_status,
                "reason_code": reason_code,
                "notes": notes,
            },
        )
        return {"prospect": updated, "audit": audit}

    @staticmethod
    async def request_changes(
        prospect_id: str,
        attribution: ReviewerAttribution,
        *,
        change_request_notes: str,
    ) -> Dict[str, Any]:
        DiscoveryApprovalQueueService._require_attribution(attribution)
        prospect = await DiscoveryApprovalQueueService._get_prospect_or_raise(
            prospect_id
        )
        action_errors = DiscoveryApprovalQueueService.validate_reviewer_action(
            "request_changes",
            prospect,
            change_request_notes=change_request_notes,
        )
        if action_errors:
            raise DiscoveryApprovalQueueError(
                "INVALID_ACTION",
                "; ".join(action_errors),
            )

        prior_status = prospect.get("review_status")
        duplicate_status_before = prospect.get("duplicate_status")

        if prior_status == DiscoveryReviewStatus.DUPLICATE_DETECTED.value:
            try:
                updated, _prepared = await DiscoveryProspectService.update_review_status(
                    prospect_id,
                    DiscoveryReviewStatus.NEEDS_REVIEW,
                    actor_id=attribution.actor_id,
                )
            except DiscoveryProspectError as exc:
                raise DiscoveryApprovalQueueError(exc.code, exc.message) from exc
        else:
            updated = dict(prospect)
            now = attribution.resolved_timestamp().isoformat()
            db = database.get_db()
            await db[DISCOVERY_PROSPECTS_COLLECTION].update_one(
                {"prospect_id": prospect_id},
                {"$set": {"updated_at": now}},
            )
            refreshed = await DiscoveryProspectService.get_prospect(prospect_id)
            updated = refreshed or updated

        audit = await DiscoveryApprovalQueueService.create_review_audit_event(
            "PROSPECT_REVIEWED",
            updated,
            attribution,
            action="request_changes",
            details={
                "from_review_status": prior_status,
                "to_review_status": updated.get("review_status"),
                "change_request_notes": change_request_notes,
                "duplicate_status_unchanged": duplicate_status_before,
            },
        )
        eligibility = DiscoveryApprovalQueueService.determine_import_eligibility(
            updated
        )
        return {
            "prospect": updated,
            "audit": audit,
            "import_eligible": eligibility.eligible,
        }

    @staticmethod
    async def archive_prospect(
        prospect_id: str,
        attribution: ReviewerAttribution,
    ) -> Dict[str, Any]:
        DiscoveryApprovalQueueService._require_attribution(attribution)
        prospect = await DiscoveryApprovalQueueService._get_prospect_or_raise(
            prospect_id
        )
        action_errors = DiscoveryApprovalQueueService.validate_reviewer_action(
            "archive",
            prospect,
        )
        if action_errors:
            raise DiscoveryApprovalQueueError(
                "INVALID_ACTION",
                "; ".join(action_errors),
            )

        prior_status = prospect.get("review_status")
        try:
            updated, _prepared = await DiscoveryProspectService.archive_prospect(
                prospect_id,
                actor_id=attribution.actor_id,
            )
        except DiscoveryProspectError as exc:
            raise DiscoveryApprovalQueueError(exc.code, exc.message) from exc

        audit = await DiscoveryApprovalQueueService.create_review_audit_event(
            "PROSPECT_ARCHIVED",
            updated,
            attribution,
            action="archive",
            details={"from_review_status": prior_status},
        )
        return {"prospect": updated, "audit": audit}

    @staticmethod
    async def mark_duplicate(
        prospect_id: str,
        attribution: ReviewerAttribution,
    ) -> Dict[str, Any]:
        DiscoveryApprovalQueueService._require_attribution(attribution)
        prospect = await DiscoveryApprovalQueueService._get_prospect_or_raise(
            prospect_id
        )
        action_errors = DiscoveryApprovalQueueService.validate_reviewer_action(
            "mark_duplicate",
            prospect,
        )
        if action_errors:
            raise DiscoveryApprovalQueueError(
                "INVALID_ACTION",
                "; ".join(action_errors),
            )

        enriched = DiscoveryDuplicateService.enrich_prospect_hashes(prospect)
        candidates = await DiscoveryDuplicateService.find_duplicate_candidates(
            enriched, exclude_prospect_id=prospect_id
        )
        classification = DiscoveryDuplicateService.classify_duplicate(
            enriched, candidates
        )

        if classification.classification == DuplicateClassification.NONE:
            raise DiscoveryApprovalQueueError(
                "NO_DUPLICATE_FOUND",
                "No duplicate candidates matched classification thresholds",
            )

        if classification.classification == DuplicateClassification.CONFIRMED_DUPLICATE:
            result = await DiscoveryDuplicateService.mark_confirmed_duplicate(
                prospect_id,
                classification,
                actor_id=attribution.actor_id,
            )
        else:
            result = await DiscoveryDuplicateService.mark_possible_duplicate(
                prospect_id,
                classification,
                actor_id=attribution.actor_id,
            )

        updated = result["prospect"]
        snapshot = DiscoveryAuditService.freeze_duplicate_evidence_snapshot(
            classification.to_dict()
        )
        audit = await DiscoveryApprovalQueueService.create_review_audit_event(
            "DUPLICATE_DETECTED",
            updated,
            attribution,
            action="mark_duplicate",
            details={
                "classification": classification.classification.value,
            },
            duplicate_evidence_snapshot=snapshot,
        )
        return {
            "prospect": updated,
            "classification": classification.to_dict(),
            "audit": audit,
        }

    @staticmethod
    async def clear_duplicate(
        prospect_id: str,
        attribution: ReviewerAttribution,
        *,
        reason_code: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        DiscoveryApprovalQueueService._require_attribution(attribution)
        prospect = await DiscoveryApprovalQueueService._get_prospect_or_raise(
            prospect_id
        )
        action_errors = DiscoveryApprovalQueueService.validate_reviewer_action(
            "clear_duplicate",
            prospect,
        )
        if action_errors:
            raise DiscoveryApprovalQueueError(
                "INVALID_ACTION",
                "; ".join(action_errors),
            )

        prior_duplicate = prospect.get("duplicate_status")
        result = await DiscoveryDuplicateService.clear_duplicate_status(
            prospect_id,
            actor_id=attribution.actor_id,
        )
        updated = result["prospect"]

        audit = await DiscoveryApprovalQueueService.create_review_audit_event(
            "DUPLICATE_OVERRIDDEN",
            updated,
            attribution,
            action="clear_duplicate",
            details={
                "prior_duplicate_status": prior_duplicate,
                "reason_code": reason_code,
                "notes": notes,
            },
        )
        return {"prospect": updated, "audit": audit}

    @staticmethod
    def _queue_sort_key(doc: Mapping[str, Any]) -> tuple:
        priority = int(doc.get("review_priority") or 0)
        created = str(doc.get("created_at") or "")
        pid = str(doc.get("prospect_id") or "")
        return (-priority, created, pid)

    @staticmethod
    def _matches_queue_filters(
        doc: Mapping[str, Any],
        filters: ReviewQueueFilters,
    ) -> bool:
        if filters.review_status and doc.get("review_status") != filters.review_status:
            return False
        if filters.duplicate_status and doc.get("duplicate_status") != filters.duplicate_status:
            return False
        if filters.provider and doc.get("provider") != filters.provider:
            return False
        if filters.campaign_id and doc.get("campaign_id") != filters.campaign_id:
            return False

        score = doc.get("platform_quality_score")
        if score is not None:
            if filters.quality_score_min is not None and int(score) < filters.quality_score_min:
                return False
            if filters.quality_score_max is not None and int(score) > filters.quality_score_max:
                return False

        priority = doc.get("review_priority")
        if priority is not None:
            if filters.review_priority_min is not None and int(priority) < filters.review_priority_min:
                return False
            if filters.review_priority_max is not None and int(priority) > filters.review_priority_max:
                return False

        created = str(doc.get("created_at") or "")
        if filters.created_from and created < filters.created_from.isoformat():
            return False
        if filters.created_to and created > filters.created_to.isoformat():
            return False

        return doc.get("tenant_id", PLATFORM_TENANT_ID) == filters.tenant_id

    @staticmethod
    async def list_review_queue(
        filters: Optional[ReviewQueueFilters] = None,
    ) -> ReviewQueueResult:
        filt = filters or ReviewQueueFilters()
        db = database.get_db()
        query: Dict[str, Any] = {"tenant_id": filt.tenant_id}
        if filt.review_status:
            query["review_status"] = filt.review_status
        if filt.duplicate_status:
            query["duplicate_status"] = filt.duplicate_status
        if filt.provider:
            query["provider"] = filt.provider
        if filt.campaign_id:
            query["campaign_id"] = filt.campaign_id

        all_docs = await db[DISCOVERY_PROSPECTS_COLLECTION].find(
            query, {"_id": 0}
        ).to_list(length=10_000)

        matched = [
            dict(d)
            for d in all_docs
            if DiscoveryApprovalQueueService._matches_queue_filters(d, filt)
        ]
        sorted_items = sorted(
            matched,
            key=DiscoveryApprovalQueueService._queue_sort_key,
        )
        total = len(sorted_items)
        page = sorted_items[filt.skip : filt.skip + filt.limit]
        return ReviewQueueResult(
            items=page,
            total=total,
            skip=filt.skip,
            limit=filt.limit,
        )

    @staticmethod
    async def get_review_item(prospect_id: str) -> Optional[Dict[str, Any]]:
        prospect = await DiscoveryProspectService.get_prospect(prospect_id)
        if not prospect:
            return None
        return {
            "prospect": prospect,
            "import_readiness": DiscoveryApprovalQueueService.build_import_readiness_summary(
                prospect
            ),
        }

    @staticmethod
    async def get_review_summary(
        *,
        tenant_id: str = PLATFORM_TENANT_ID,
    ) -> Dict[str, Any]:
        db = database.get_db()
        docs = await db[DISCOVERY_PROSPECTS_COLLECTION].find(
            {"tenant_id": tenant_id},
            {"_id": 0},
        ).to_list(length=10_000)

        counts = {
            "total_needs_review": 0,
            "total_duplicates": 0,
            "total_approved": 0,
            "total_rejected": 0,
            "total_archived": 0,
        }
        scores: List[int] = []
        high_priority = 0

        for doc in docs:
            rs = doc.get("review_status")
            if rs == DiscoveryReviewStatus.NEEDS_REVIEW.value:
                counts["total_needs_review"] += 1
            elif rs == DiscoveryReviewStatus.DUPLICATE_DETECTED.value:
                counts["total_duplicates"] += 1
            elif rs == DiscoveryReviewStatus.APPROVED.value:
                counts["total_approved"] += 1
            elif rs == DiscoveryReviewStatus.REJECTED.value:
                counts["total_rejected"] += 1
            elif rs == DiscoveryReviewStatus.ARCHIVED.value:
                counts["total_archived"] += 1

            score = doc.get("platform_quality_score")
            if score is not None:
                scores.append(int(score))
            priority = int(doc.get("review_priority") or 0)
            if priority >= HIGH_PRIORITY_THRESHOLD:
                high_priority += 1

        avg_score = round(sum(scores) / len(scores), 2) if scores else None
        return {
            **counts,
            "average_quality_score": avg_score,
            "high_priority_count": high_priority,
            "tenant_id": tenant_id,
        }
