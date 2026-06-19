"""
Discovery audit log service — Stage L.

Append-only persistence and retrieval for discovery_audit_logs.
No routes, imports, LeadService, or workflow execution.
"""
from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from database import database
from services.discovery.discovery_audit_helpers import (
    DiscoveryAuditValidationError,
    build_audit_event,
    prepare_audit_payload,
    validate_audit_event_type,
)
from services.discovery.discovery_models import (
    DISCOVERY_AUDIT_LOGS_COLLECTION,
    FROZEN_AUDIT_EVENT_VALUES,
    PLATFORM_TENANT_ID,
    is_frozen_audit_event,
)

DEFAULT_CONTENT_HASH_VERSION = "1"
DEFAULT_HASH_ALGORITHM = "sha256"
DEFAULT_SOURCE_METADATA_VERSION = "1.0.0"

CONTENT_HASH_HEX = re.compile(r"^[a-f0-9]{64}$")

# Governance events requiring actor attribution.
ACTOR_REQUIRED_EVENT_TYPES = frozenset(
    {
        "PROSPECT_APPROVED",
        "PROSPECT_REJECTED",
        "PROSPECT_REVIEWED",
        "PROSPECT_ARCHIVED",
        "PROSPECT_IMPORTED",
        "IMPORT_REQUESTED",
        "PROSPECT_ERASED",
        "PROSPECT_ERASURE_REQUESTED",
        "DUPLICATE_DETECTED",
        "DUPLICATE_OVERRIDDEN",
        "RUN_ATTESTED",
        "LEGAL_HOLD_SET",
        "LEGAL_HOLD_RELEASED",
        "ERASURE_REQUESTED",
        "ERASURE_EXECUTED",
        "LEGAL_HOLD_APPLIED",
        "RETENTION_EXPIRY_REACHED",
        "PURGE_ELIGIBLE",
        "PURGE_BLOCKED",
        "LEAD_DISCOVERY_PROVENANCE_ERASED",
    }
)

FORBIDDEN_DETAIL_KEYS = frozenset(
    {"raw_payload", "raw_row", "csv_row", "html_payload", "provider_raw_response"}
)


@dataclass(frozen=True)
class AuditListFilters:
    prospect_id: Optional[str] = None
    campaign_id: Optional[str] = None
    run_id: Optional[str] = None
    provider: Optional[str] = None
    actor_id: Optional[str] = None
    event_type: Optional[str] = None
    created_from: Optional[datetime] = None
    created_to: Optional[datetime] = None
    tenant_id: str = PLATFORM_TENANT_ID


@dataclass(frozen=True)
class AuditListResult:
    items: List[Dict[str, Any]]
    total: int
    skip: int
    limit: int


class DiscoveryAuditServiceError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


class DiscoveryAuditService:
    """Append-only audit trail — create and read only."""

    @staticmethod
    def validate_event_type(event_type: str) -> str:
        return validate_audit_event_type(event_type)

    @staticmethod
    def build_audit_context(
        *,
        prospect_id: Optional[str] = None,
        campaign_id: Optional[str] = None,
        discovery_run_id: Optional[str] = None,
        provider: Optional[str] = None,
        actor_id: Optional[str] = None,
        actor_email: Optional[str] = None,
        event_type: Optional[str] = None,
        timestamp: Optional[datetime] = None,
        content_hash: Optional[str] = None,
        content_hash_version: str = DEFAULT_CONTENT_HASH_VERSION,
        hash_algorithm: str = DEFAULT_HASH_ALGORITHM,
        source_metadata_version: str = DEFAULT_SOURCE_METADATA_VERSION,
    ) -> Dict[str, Any]:
        ctx: Dict[str, Any] = {
            "content_hash_version": content_hash_version,
            "hash_algorithm": hash_algorithm,
            "source_metadata_version": source_metadata_version,
        }
        if prospect_id:
            ctx["prospect_id"] = prospect_id
        if campaign_id:
            ctx["campaign_id"] = campaign_id
        if discovery_run_id:
            ctx["discovery_run_id"] = discovery_run_id
        if provider:
            ctx["provider"] = provider
        if actor_id:
            ctx["actor_id"] = actor_id
        if actor_email:
            ctx["actor_email"] = actor_email
        if event_type:
            ctx["event_type"] = event_type
        if timestamp:
            ctx["timestamp"] = timestamp.isoformat()
        if content_hash:
            ctx["content_hash"] = content_hash
        return ctx

    @staticmethod
    def freeze_duplicate_evidence_snapshot(
        classification: Mapping[str, Any],
        *,
        content_hash_version: str = DEFAULT_CONTENT_HASH_VERSION,
        hash_algorithm: str = DEFAULT_HASH_ALGORITHM,
        captured_at: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Immutable duplicate evidence snapshot for audit-grade storage.
        Must be persisted at decision time — never regenerated later.
        """
        now = captured_at or datetime.now(timezone.utc)
        evidence = classification.get("evidence")
        if evidence is None and "classification" in classification:
            evidence = classification.get("evidence", [])
        return {
            "classification": classification.get("classification"),
            "evidence": copy.deepcopy(list(evidence or [])),
            "primary_match_prospect_id": classification.get("primary_match_prospect_id"),
            "content_hash_version": content_hash_version,
            "hash_algorithm": hash_algorithm,
            "captured_at": now.isoformat(),
            "frozen": True,
        }

    @staticmethod
    def _validate_version_metadata(context: Mapping[str, Any]) -> List[str]:
        errors: List[str] = []
        chv = context.get("content_hash_version")
        if chv is not None and str(chv).strip() == "":
            errors.append("content_hash_version must not be empty when provided")
        ha = context.get("hash_algorithm")
        if ha is not None and str(ha).strip() == "":
            errors.append("hash_algorithm must not be empty when provided")
        smv = context.get("source_metadata_version")
        if smv is not None and str(smv).strip() == "":
            errors.append("source_metadata_version must not be empty when provided")
        if context.get("content_hash"):
            ch = str(context["content_hash"])
            if not CONTENT_HASH_HEX.match(ch):
                errors.append("content_hash in context must be 64-char hex")
        return errors

    @staticmethod
    def _validate_duplicate_evidence_snapshot(snapshot: Any) -> List[str]:
        errors: List[str] = []
        if not isinstance(snapshot, dict):
            return ["duplicate_evidence_snapshot must be an object"]
        if not snapshot.get("classification"):
            errors.append("duplicate_evidence_snapshot.classification is required")
        if "evidence" not in snapshot or not isinstance(snapshot.get("evidence"), list):
            errors.append("duplicate_evidence_snapshot.evidence must be a list")
        if not snapshot.get("captured_at"):
            errors.append("duplicate_evidence_snapshot.captured_at is required")
        if snapshot.get("frozen") is not True:
            errors.append("duplicate_evidence_snapshot must be frozen at capture time")
        for field in ("content_hash_version", "hash_algorithm"):
            if field in snapshot and not str(snapshot[field]).strip():
                errors.append(f"duplicate_evidence_snapshot.{field} invalid")
        return errors

    @staticmethod
    def validate_audit_event(
        event: Mapping[str, Any],
        *,
        require_actor: bool = False,
    ) -> List[str]:
        errors: List[str] = []
        audit_id = event.get("audit_id")
        if not audit_id or not str(audit_id).strip():
            errors.append("audit_id is required")

        event_type = event.get("event_type")
        try:
            normalised = DiscoveryAuditService.validate_event_type(str(event_type or ""))
        except DiscoveryAuditValidationError as exc:
            errors.append(str(exc))
            normalised = None

        created_at = event.get("created_at")
        if not created_at:
            errors.append("created_at timestamp is required")

        if not event.get("prospect_id") and not event.get("run_id") and not event.get("campaign_id"):
            errors.append("at least one of prospect_id, run_id, or campaign_id is required")

        actor_required = require_actor or (
            normalised in ACTOR_REQUIRED_EVENT_TYPES if normalised else False
        )
        if actor_required and not event.get("actor_id"):
            errors.append(f"actor_id is required for event_type {normalised}")

        details = event.get("details") or {}
        if not isinstance(details, dict):
            errors.append("details must be an object")
            details = {}

        for key in FORBIDDEN_DETAIL_KEYS:
            if key in details:
                errors.append(f"forbidden detail key '{key}'")

        context = details.get("audit_context") or {}
        if isinstance(context, dict):
            errors.extend(DiscoveryAuditService._validate_version_metadata(context))

        if normalised == "DUPLICATE_DETECTED":
            snapshot = details.get("duplicate_evidence_snapshot")
            if snapshot is None:
                errors.append("DUPLICATE_DETECTED requires duplicate_evidence_snapshot")
            else:
                errors.extend(
                    DiscoveryAuditService._validate_duplicate_evidence_snapshot(snapshot)
                )

        return errors

    @staticmethod
    async def create_audit_event(
        *,
        event_type: str,
        prospect_id: Optional[str] = None,
        run_id: Optional[str] = None,
        campaign_id: Optional[str] = None,
        job_id: Optional[str] = None,
        lead_id: Optional[str] = None,
        provider: Optional[str] = None,
        actor_id: Optional[str] = None,
        actor_email: Optional[str] = None,
        reason_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        audit_context: Optional[Dict[str, Any]] = None,
        duplicate_evidence_snapshot: Optional[Dict[str, Any]] = None,
        content_hash: Optional[str] = None,
        content_hash_version: str = DEFAULT_CONTENT_HASH_VERSION,
        hash_algorithm: str = DEFAULT_HASH_ALGORITHM,
        source_metadata_version: str = DEFAULT_SOURCE_METADATA_VERSION,
        tenant_id: str = PLATFORM_TENANT_ID,
        created_at: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Persist a single immutable audit record."""
        now = created_at or datetime.now(timezone.utc)
        normalised_type = DiscoveryAuditService.validate_event_type(event_type)

        merged_details = prepare_audit_payload(dict(details or {}))
        ctx = DiscoveryAuditService.build_audit_context(
            prospect_id=prospect_id,
            campaign_id=campaign_id,
            discovery_run_id=run_id,
            provider=provider,
            actor_id=actor_id,
            actor_email=actor_email,
            event_type=normalised_type,
            timestamp=now,
            content_hash=content_hash,
            content_hash_version=content_hash_version,
            hash_algorithm=hash_algorithm,
            source_metadata_version=source_metadata_version,
        )
        if audit_context:
            ctx.update(audit_context)
        merged_details["audit_context"] = ctx

        if duplicate_evidence_snapshot is not None:
            merged_details["duplicate_evidence_snapshot"] = copy.deepcopy(
                duplicate_evidence_snapshot
            )
        elif normalised_type == "DUPLICATE_DETECTED":
            raise DiscoveryAuditServiceError(
                "DUPLICATE_EVIDENCE_REQUIRED",
                "DUPLICATE_DETECTED requires duplicate_evidence_snapshot",
            )

        event_doc = build_audit_event(
            event_type=normalised_type,
            prospect_id=prospect_id,
            run_id=run_id,
            campaign_id=campaign_id,
            job_id=job_id,
            lead_id=lead_id,
            provider=provider,
            actor_id=actor_id,
            actor_email=actor_email,
            reason_code=reason_code,
            details=merged_details,
            tenant_id=tenant_id,
            created_at=now,
        )
        payload = event_doc.model_dump(mode="json")

        validation_errors = DiscoveryAuditService.validate_audit_event(payload)
        if validation_errors:
            raise DiscoveryAuditServiceError(
                "INVALID_AUDIT_EVENT",
                "; ".join(validation_errors),
            )

        db = database.get_db()
        await db[DISCOVERY_AUDIT_LOGS_COLLECTION].insert_one(payload)
        stored = await db[DISCOVERY_AUDIT_LOGS_COLLECTION].find_one(
            {"audit_id": payload["audit_id"]}, {"_id": 0}
        )
        return stored or payload

    @staticmethod
    async def get_audit_event(audit_id: str) -> Optional[Dict[str, Any]]:
        db = database.get_db()
        return await db[DISCOVERY_AUDIT_LOGS_COLLECTION].find_one(
            {"audit_id": audit_id}, {"_id": 0}
        )

    @staticmethod
    def _build_query(filters: AuditListFilters) -> Dict[str, Any]:
        query: Dict[str, Any] = {"tenant_id": filters.tenant_id}
        if filters.prospect_id:
            query["prospect_id"] = filters.prospect_id
        if filters.campaign_id:
            query["campaign_id"] = filters.campaign_id
        if filters.run_id:
            query["run_id"] = filters.run_id
        if filters.provider:
            query["provider"] = filters.provider
        if filters.actor_id:
            query["actor_id"] = filters.actor_id
        if filters.event_type:
            query["event_type"] = validate_audit_event_type(filters.event_type)
        if filters.created_from or filters.created_to:
            created: Dict[str, Any] = {}
            if filters.created_from:
                created["$gte"] = filters.created_from.isoformat()
            if filters.created_to:
                created["$lte"] = filters.created_to.isoformat()
            query["created_at"] = created
        return query

    @staticmethod
    async def list_audit_events(
        filters: Optional[AuditListFilters] = None,
        *,
        skip: int = 0,
        limit: int = 50,
    ) -> AuditListResult:
        filt = filters or AuditListFilters()
        query = DiscoveryAuditService._build_query(filt)
        db = database.get_db()
        coll = db[DISCOVERY_AUDIT_LOGS_COLLECTION]

        all_matches = await coll.find(query, {"_id": 0}).to_list(length=10_000)
        sorted_items = sorted(
            all_matches,
            key=lambda d: (
                -DiscoveryAuditService._created_at_sort_key(d),
                str(d.get("audit_id", "")),
            ),
        )
        total = len(sorted_items)
        page = sorted_items[skip : skip + limit]
        return AuditListResult(items=page, total=total, skip=skip, limit=limit)

    @staticmethod
    async def list_prospect_audit_events(
        prospect_id: str,
        *,
        skip: int = 0,
        limit: int = 50,
    ) -> AuditListResult:
        return await DiscoveryAuditService.list_audit_events(
            AuditListFilters(prospect_id=prospect_id),
            skip=skip,
            limit=limit,
        )

    @staticmethod
    async def list_run_audit_events(
        run_id: str,
        *,
        skip: int = 0,
        limit: int = 50,
    ) -> AuditListResult:
        return await DiscoveryAuditService.list_audit_events(
            AuditListFilters(run_id=run_id),
            skip=skip,
            limit=limit,
        )

    @staticmethod
    async def list_campaign_audit_events(
        campaign_id: str,
        *,
        skip: int = 0,
        limit: int = 50,
    ) -> AuditListResult:
        return await DiscoveryAuditService.list_audit_events(
            AuditListFilters(campaign_id=campaign_id),
            skip=skip,
            limit=limit,
        )

    @staticmethod
    def build_audit_summary(events: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
        """Template-driven investigation summary — no AI."""
        if not events:
            return {
                "prospect_id": None,
                "event_count": 0,
                "latest_status": None,
                "duplicate_classification": None,
                "latest_event_type": None,
                "lines": ["No audit events."],
            }

        ordered = sorted(
            events,
            key=lambda e: (str(e.get("created_at", "")), str(e.get("audit_id", ""))),
        )
        latest = ordered[-1]
        prospect_id = latest.get("prospect_id") or ordered[0].get("prospect_id")

        latest_status = None
        duplicate_classification = None
        for event in reversed(ordered):
            details = event.get("details") or {}
            if latest_status is None and details.get("review_status"):
                latest_status = details["review_status"]
            if duplicate_classification is None:
                snap = details.get("duplicate_evidence_snapshot")
                if snap and snap.get("classification"):
                    duplicate_classification = snap["classification"]
            if latest_status and duplicate_classification:
                break

        lines = [
            f"Prospect:",
            str(prospect_id or "—"),
            "",
            f"Events:",
            str(len(ordered)),
            "",
            f"Latest Status:",
            str(latest_status or "—"),
            "",
            f"Duplicate Classification:",
            str(duplicate_classification or "none"),
            "",
            f"Latest Event:",
            str(latest.get("event_type") or "—"),
        ]

        return {
            "prospect_id": prospect_id,
            "event_count": len(ordered),
            "latest_status": latest_status,
            "duplicate_classification": duplicate_classification,
            "latest_event_type": latest.get("event_type"),
            "lines": lines,
        }

    @staticmethod
    def frozen_taxonomy_values() -> frozenset[str]:
        return FROZEN_AUDIT_EVENT_VALUES

    @staticmethod
    def _created_at_sort_key(doc: Mapping[str, Any]) -> float:
        raw = doc.get("created_at")
        if not raw:
            return 0.0
        if isinstance(raw, datetime):
            return raw.timestamp()
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00")).timestamp()
