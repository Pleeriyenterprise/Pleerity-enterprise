"""
Discovery duplicate detection — Stage K.

Cross-run and intra-run dedupe per Architecture §13.
content_hash is an ingest fingerprint — not the primary global identity key.
No LeadService writes, import, routes, or provider integration.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from difflib import SequenceMatcher
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from database import database
from services.discovery.discovery_models import (
    DISCOVERY_PROSPECTS_COLLECTION,
    PLATFORM_TENANT_ID,
    DiscoveryDuplicateStatus,
    DiscoveryErasureStatus,
    DiscoveryReviewStatus,
    email_hash,
    phone_hash,
)

DEFAULT_CONTENT_HASH_VERSION = "1"
MERGE_CHAIN_MAX_DEPTH = 10
FUZZY_COMPANY_NAME_THRESHOLD = 0.85


class DuplicateClassification(str, Enum):
    NONE = "none"
    POSSIBLE_DUPLICATE = "possible_duplicate"
    CONFIRMED_DUPLICATE = "confirmed_duplicate"


class DuplicateEvidenceType(str, Enum):
    EMAIL_HASH_MATCH = "email_hash_match"
    PHONE_HASH_MATCH = "phone_hash_match"
    SAME_RUN_CONTENT_HASH_MATCH = "same_run_content_hash_match"
    PROVIDER_REFERENCE_MATCH = "provider_reference_match"
    MERGED_INTO_PROSPECT_MATCH = "merged_into_prospect_match"
    COMPANY_WEBSITE_MATCH = "company_website_match"
    COMPANY_LOCATION_MATCH = "company_location_match"
    FUZZY_COMPANY_NAME_MATCH = "fuzzy_company_name_match"
    ERASURE_SAFE_MATCH = "erasure_safe_match"
    VERSION_MISMATCH = "version_mismatch"
    REVIEWER_OVERRIDE = "reviewer_override"


@dataclass(frozen=True)
class DuplicateEvidence:
    evidence_type: DuplicateEvidenceType
    matched_prospect_id: str
    confidence: str  # high | medium | low
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evidence_type": self.evidence_type.value,
            "matched_prospect_id": self.matched_prospect_id,
            "confidence": self.confidence,
            "details": dict(self.details),
        }


@dataclass
class DuplicateClassificationResult:
    classification: DuplicateClassification
    evidence: List[DuplicateEvidence] = field(default_factory=list)
    primary_match_prospect_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "classification": self.classification.value,
            "evidence": [e.to_dict() for e in self.evidence],
            "primary_match_prospect_id": self.primary_match_prospect_id,
        }


class DiscoveryDuplicateError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


def _norm_str(value: Optional[str]) -> str:
    return str(value or "").strip().lower()


def _norm_company(value: Optional[str]) -> str:
    text = _norm_str(value)
    return re.sub(r"[^\w\s]", "", text)


def _norm_website(value: Optional[str]) -> str:
    text = _norm_str(value)
    return re.sub(r"^https?://(www\.)?", "", text).rstrip("/")


def _postcode(location: Any) -> str:
    if location is None:
        return ""
    if isinstance(location, dict):
        return _norm_str(location.get("postcode"))
    return _norm_str(getattr(location, "postcode", None))


def _content_hash_version(prospect: Mapping[str, Any]) -> str:
    return str(prospect.get("content_hash_version") or DEFAULT_CONTENT_HASH_VERSION)


def _is_erased(prospect: Mapping[str, Any]) -> bool:
    return prospect.get("erasure_status") == DiscoveryErasureStatus.ERASED.value


def _erasure_safe_details(candidate: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "erasure_status": candidate.get("erasure_status"),
        "email_hash": candidate.get("email_hash"),
        "phone_hash": candidate.get("phone_hash"),
        "prospect_id": candidate.get("prospect_id"),
    }


def _fuzzy_company_match(left: Optional[str], right: Optional[str]) -> bool:
    a = _norm_company(left)
    b = _norm_company(right)
    if not a or not b or len(a) < 3 or len(b) < 3:
        return False
    return SequenceMatcher(None, a, b).ratio() >= FUZZY_COMPANY_NAME_THRESHOLD


class DiscoveryDuplicateService:
    @staticmethod
    def build_duplicate_evidence(
        evidence_type: DuplicateEvidenceType,
        matched_prospect_id: str,
        *,
        confidence: str = "high",
        details: Optional[Dict[str, Any]] = None,
    ) -> DuplicateEvidence:
        return DuplicateEvidence(
            evidence_type=evidence_type,
            matched_prospect_id=matched_prospect_id,
            confidence=confidence,
            details=details or {},
        )

    @staticmethod
    async def find_duplicate_candidates(
        prospect: Mapping[str, Any],
        *,
        exclude_prospect_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Find discovery-store candidates using hierarchy signals (not CRM)."""
        tenant_id = prospect.get("tenant_id", PLATFORM_TENANT_ID)
        db = database.get_db()
        coll = db[DISCOVERY_PROSPECTS_COLLECTION]

        or_clauses: List[Dict[str, Any]] = []
        if prospect.get("email_hash"):
            or_clauses.append({"email_hash": prospect["email_hash"]})
        if prospect.get("phone_hash"):
            or_clauses.append({"phone_hash": prospect["phone_hash"]})
        if prospect.get("content_hash") and prospect.get("discovery_run_id"):
            or_clauses.append(
                {
                    "content_hash": prospect["content_hash"],
                    "discovery_run_id": prospect["discovery_run_id"],
                }
            )
        if (
            prospect.get("provider")
            and prospect.get("provider_reference")
            and prospect.get("discovery_run_id")
        ):
            or_clauses.append(
                {
                    "provider": prospect["provider"],
                    "provider_reference": prospect["provider_reference"],
                    "discovery_run_id": prospect["discovery_run_id"],
                }
            )
        if prospect.get("merged_into_prospect_id"):
            or_clauses.append(
                {"prospect_id": prospect["merged_into_prospect_id"]}
            )

        if not or_clauses:
            return []

        query: Dict[str, Any] = {
            "tenant_id": tenant_id,
            "$or": or_clauses,
        }
        exclude_id = exclude_prospect_id or prospect.get("prospect_id")
        if exclude_id:
            query["prospect_id"] = {"$ne": exclude_id}

        cursor = coll.find(query, {"_id": 0})
        results = await cursor.to_list(length=200)

        seen: Set[str] = set()
        unique: List[Dict[str, Any]] = []
        for doc in results:
            pid = doc.get("prospect_id")
            if pid and pid not in seen:
                seen.add(pid)
                unique.append(doc)
        return unique

    @staticmethod
    def classify_duplicate(
        prospect: Mapping[str, Any],
        candidates: Sequence[Mapping[str, Any]],
    ) -> DuplicateClassificationResult:
        evidence: List[DuplicateEvidence] = []
        confirmed_ids: List[str] = []
        possible_ids: List[str] = []

        source_version = _content_hash_version(prospect)
        source_run = prospect.get("discovery_run_id")
        source_hash = prospect.get("content_hash")
        source_provider = prospect.get("provider")
        source_pref = prospect.get("provider_reference")

        for candidate in candidates:
            cid = str(candidate.get("prospect_id") or "")
            if not cid:
                continue
            erased = _is_erased(candidate)
            safe = _erasure_safe_details(candidate) if erased else {}

            if (
                prospect.get("email_hash")
                and candidate.get("email_hash") == prospect.get("email_hash")
            ):
                evidence.append(
                    DiscoveryDuplicateService.build_duplicate_evidence(
                        DuplicateEvidenceType.EMAIL_HASH_MATCH,
                        cid,
                        confidence="high",
                        details=safe or {"match": "email_hash"},
                    )
                )
                if erased:
                    evidence.append(
                        DiscoveryDuplicateService.build_duplicate_evidence(
                            DuplicateEvidenceType.ERASURE_SAFE_MATCH,
                            cid,
                            confidence="high",
                            details=safe,
                        )
                    )
                confirmed_ids.append(cid)

            if (
                prospect.get("phone_hash")
                and candidate.get("phone_hash") == prospect.get("phone_hash")
            ):
                evidence.append(
                    DiscoveryDuplicateService.build_duplicate_evidence(
                        DuplicateEvidenceType.PHONE_HASH_MATCH,
                        cid,
                        confidence="high",
                        details=safe or {"match": "phone_hash"},
                    )
                )
                if erased:
                    evidence.append(
                        DiscoveryDuplicateService.build_duplicate_evidence(
                            DuplicateEvidenceType.ERASURE_SAFE_MATCH,
                            cid,
                            confidence="high",
                            details=safe,
                        )
                    )
                confirmed_ids.append(cid)

            cand_version = _content_hash_version(candidate)
            same_run = (
                source_run
                and candidate.get("discovery_run_id") == source_run
            )
            if (
                source_hash
                and candidate.get("content_hash") == source_hash
            ):
                if source_version != cand_version:
                    evidence.append(
                        DiscoveryDuplicateService.build_duplicate_evidence(
                            DuplicateEvidenceType.VERSION_MISMATCH,
                            cid,
                            confidence="medium",
                            details={
                                "source_version": source_version,
                                "candidate_version": cand_version,
                            },
                        )
                    )
                elif same_run:
                    evidence.append(
                        DiscoveryDuplicateService.build_duplicate_evidence(
                            DuplicateEvidenceType.SAME_RUN_CONTENT_HASH_MATCH,
                            cid,
                            confidence="high",
                            details=safe or {"discovery_run_id": source_run},
                        )
                    )
                    confirmed_ids.append(cid)
                # cross-run content_hash alone: never confirmed (hard prohibition)

            if (
                same_run
                and source_provider
                and source_pref
                and candidate.get("provider") == source_provider
                and candidate.get("provider_reference") == source_pref
            ):
                evidence.append(
                    DiscoveryDuplicateService.build_duplicate_evidence(
                        DuplicateEvidenceType.PROVIDER_REFERENCE_MATCH,
                        cid,
                        confidence="high",
                        details={
                            "discovery_run_id": source_run,
                            "cross_run": False,
                            **(safe or {}),
                        },
                    )
                )
                confirmed_ids.append(cid)
            elif (
                source_provider
                and source_pref
                and candidate.get("provider") == source_provider
                and candidate.get("provider_reference") == source_pref
                and not same_run
            ):
                # cross-run provider_reference: not confirmed
                evidence.append(
                    DiscoveryDuplicateService.build_duplicate_evidence(
                        DuplicateEvidenceType.PROVIDER_REFERENCE_MATCH,
                        cid,
                        confidence="low",
                        details={"cross_run": True, "confirmed": False},
                    )
                )

            if prospect.get("merged_into_prospect_id") == cid:
                evidence.append(
                    DiscoveryDuplicateService.build_duplicate_evidence(
                        DuplicateEvidenceType.MERGED_INTO_PROSPECT_MATCH,
                        cid,
                        confidence="high",
                    )
                )
                confirmed_ids.append(cid)

            # Possible duplicate rules — business context
            if (
                _norm_company(prospect.get("company_name"))
                and _norm_company(prospect.get("company_name"))
                == _norm_company(candidate.get("company_name"))
                and _norm_website(prospect.get("website"))
                and _norm_website(prospect.get("website"))
                == _norm_website(candidate.get("website"))
            ):
                evidence.append(
                    DiscoveryDuplicateService.build_duplicate_evidence(
                        DuplicateEvidenceType.COMPANY_WEBSITE_MATCH,
                        cid,
                        confidence="medium",
                    )
                )
                possible_ids.append(cid)

            if (
                _norm_company(prospect.get("company_name"))
                and _norm_company(prospect.get("company_name"))
                == _norm_company(candidate.get("company_name"))
                and _postcode(prospect.get("location"))
                and _postcode(prospect.get("location"))
                == _postcode(candidate.get("location"))
            ):
                evidence.append(
                    DiscoveryDuplicateService.build_duplicate_evidence(
                        DuplicateEvidenceType.COMPANY_LOCATION_MATCH,
                        cid,
                        confidence="medium",
                        details={"match": "company_name+postcode"},
                    )
                )
                possible_ids.append(cid)

            if _fuzzy_company_match(
                prospect.get("company_name"),
                candidate.get("company_name"),
            ):
                evidence.append(
                    DiscoveryDuplicateService.build_duplicate_evidence(
                        DuplicateEvidenceType.FUZZY_COMPANY_NAME_MATCH,
                        cid,
                        confidence="low",
                        details={"threshold": FUZZY_COMPANY_NAME_THRESHOLD},
                    )
                )
                possible_ids.append(cid)

            if (
                _norm_website(prospect.get("website"))
                and _norm_website(prospect.get("website"))
                == _norm_website(candidate.get("website"))
                and _postcode(prospect.get("location"))
                and _postcode(prospect.get("location"))
                == _postcode(candidate.get("location"))
            ):
                evidence.append(
                    DiscoveryDuplicateService.build_duplicate_evidence(
                        DuplicateEvidenceType.COMPANY_LOCATION_MATCH,
                        cid,
                        confidence="medium",
                        details={"match": "website+location"},
                    )
                )
                possible_ids.append(cid)

        # Deduplicate evidence by type+prospect
        deduped: List[DuplicateEvidence] = []
        seen_keys: Set[Tuple[str, str]] = set()
        for item in evidence:
            key = (item.evidence_type.value, item.matched_prospect_id)
            if key not in seen_keys:
                seen_keys.add(key)
                deduped.append(item)

        if confirmed_ids:
            primary = confirmed_ids[0]
            return DuplicateClassificationResult(
                classification=DuplicateClassification.CONFIRMED_DUPLICATE,
                evidence=deduped,
                primary_match_prospect_id=primary,
            )
        if possible_ids:
            return DuplicateClassificationResult(
                classification=DuplicateClassification.POSSIBLE_DUPLICATE,
                evidence=deduped,
                primary_match_prospect_id=possible_ids[0],
            )
        return DuplicateClassificationResult(
            classification=DuplicateClassification.NONE,
            evidence=deduped,
        )

    @staticmethod
    async def classify_batch_duplicates(
        prospects: Sequence[Mapping[str, Any]],
    ) -> Dict[str, DuplicateClassificationResult]:
        results: Dict[str, DuplicateClassificationResult] = {}
        for prospect in prospects:
            pid = prospect.get("prospect_id")
            if not pid:
                continue
            candidates = await DiscoveryDuplicateService.find_duplicate_candidates(
                prospect, exclude_prospect_id=str(pid)
            )
            results[str(pid)] = DiscoveryDuplicateService.classify_duplicate(
                prospect, candidates
            )
        return results

    @staticmethod
    def _classification_to_status(
        classification: DuplicateClassification,
    ) -> DiscoveryDuplicateStatus:
        if classification == DuplicateClassification.CONFIRMED_DUPLICATE:
            return DiscoveryDuplicateStatus.CONFIRMED
        if classification == DuplicateClassification.POSSIBLE_DUPLICATE:
            return DiscoveryDuplicateStatus.POSSIBLE
        return DiscoveryDuplicateStatus.NONE

    @staticmethod
    async def apply_duplicate_status(
        prospect_id: str,
        result: DuplicateClassificationResult,
        *,
        actor_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        status = DiscoveryDuplicateService._classification_to_status(
            result.classification
        )
        updates: Dict[str, Any] = {
            "duplicate_status": status.value,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if result.classification == DuplicateClassification.CONFIRMED_DUPLICATE:
            updates["review_status"] = DiscoveryReviewStatus.DUPLICATE_DETECTED.value
        elif result.classification == DuplicateClassification.NONE:
            updates["review_status"] = DiscoveryReviewStatus.NEEDS_REVIEW.value

        db = database.get_db()
        await db[DISCOVERY_PROSPECTS_COLLECTION].update_one(
            {"prospect_id": prospect_id},
            {"$set": updates},
        )
        updated = await db[DISCOVERY_PROSPECTS_COLLECTION].find_one(
            {"prospect_id": prospect_id}, {"_id": 0}
        )
        if not updated:
            raise DiscoveryDuplicateError(
                "PROSPECT_NOT_FOUND", f"Prospect {prospect_id} not found"
            )
        return {
            "prospect": updated,
            "classification": result.to_dict(),
            "actor_id": actor_id,
        }

    @staticmethod
    async def mark_possible_duplicate(
        prospect_id: str,
        result: DuplicateClassificationResult,
        *,
        actor_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        result = DuplicateClassificationResult(
            classification=DuplicateClassification.POSSIBLE_DUPLICATE,
            evidence=result.evidence,
            primary_match_prospect_id=result.primary_match_prospect_id,
        )
        return await DiscoveryDuplicateService.apply_duplicate_status(
            prospect_id, result, actor_id=actor_id
        )

    @staticmethod
    async def mark_confirmed_duplicate(
        prospect_id: str,
        result: DuplicateClassificationResult,
        *,
        actor_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        result = DuplicateClassificationResult(
            classification=DuplicateClassification.CONFIRMED_DUPLICATE,
            evidence=result.evidence,
            primary_match_prospect_id=result.primary_match_prospect_id,
        )
        return await DiscoveryDuplicateService.apply_duplicate_status(
            prospect_id, result, actor_id=actor_id
        )

    @staticmethod
    async def clear_duplicate_status(
        prospect_id: str,
        *,
        actor_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        empty = DuplicateClassificationResult(
            classification=DuplicateClassification.NONE,
            evidence=[],
        )
        return await DiscoveryDuplicateService.apply_duplicate_status(
            prospect_id, empty, actor_id=actor_id
        )

    @staticmethod
    async def resolve_merge_target(
        prospect_id: str,
        *,
        max_depth: int = MERGE_CHAIN_MAX_DEPTH,
    ) -> Optional[str]:
        db = database.get_db()
        coll = db[DISCOVERY_PROSPECTS_COLLECTION]
        visited: Set[str] = set()
        current = prospect_id
        for _ in range(max_depth):
            if current in visited:
                raise DiscoveryDuplicateError(
                    "MERGE_CYCLE", f"Merge cycle detected at {current}"
                )
            visited.add(current)
            doc = await coll.find_one({"prospect_id": current}, {"_id": 0})
            if not doc:
                return None
            merged = doc.get("merged_into_prospect_id")
            if not merged:
                return current
            current = str(merged)
        raise DiscoveryDuplicateError(
            "MERGE_DEPTH_EXCEEDED",
            f"Merge chain exceeds max depth {max_depth}",
        )

    @staticmethod
    async def link_merged_prospect(
        source_prospect_id: str,
        target_prospect_id: str,
        *,
        actor_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        if source_prospect_id == target_prospect_id:
            raise DiscoveryDuplicateError(
                "INVALID_MERGE", "Cannot merge prospect into itself"
            )

        db = database.get_db()
        coll = db[DISCOVERY_PROSPECTS_COLLECTION]
        target = await coll.find_one(
            {"prospect_id": target_prospect_id}, {"_id": 0}
        )
        if not target:
            raise DiscoveryDuplicateError(
                "TARGET_NOT_FOUND", f"Target prospect {target_prospect_id} not found"
            )
        if _is_erased(target):
            raise DiscoveryDuplicateError(
                "TARGET_ERASED",
                "Erased prospect cannot be active merge target",
            )

        # Cycle check: target must not resolve back to source
        resolved = await DiscoveryDuplicateService.resolve_merge_target(
            target_prospect_id
        )
        if resolved == source_prospect_id:
            raise DiscoveryDuplicateError(
                "MERGE_CYCLE", "Link would create merge cycle"
            )

        await coll.update_one(
            {"prospect_id": source_prospect_id},
            {
                "$set": {
                    "merged_into_prospect_id": target_prospect_id,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            },
        )
        updated = await coll.find_one(
            {"prospect_id": source_prospect_id}, {"_id": 0}
        )
        return {
            "prospect": updated,
            "merged_into_prospect_id": target_prospect_id,
            "actor_id": actor_id,
        }

    @staticmethod
    def validate_duplicate_override(
        *,
        reviewer_id: Optional[str],
        reason_code: Optional[str],
        notes: Optional[str],
        timestamp: Optional[datetime],
    ) -> List[str]:
        errors: List[str] = []
        if not reviewer_id or not str(reviewer_id).strip():
            errors.append("reviewer_id is required")
        if not reason_code or not str(reason_code).strip():
            errors.append("reason_code is required")
        if not notes or not str(notes).strip():
            errors.append("notes are required")
        if timestamp is None:
            errors.append("timestamp is required")
        return errors

    @staticmethod
    def enrich_prospect_hashes(prospect: Mapping[str, Any]) -> Dict[str, Any]:
        """Ensure email_hash / phone_hash present for dedupe queries."""
        data = dict(prospect)
        if data.get("email") and not data.get("email_hash"):
            data["email_hash"] = email_hash(str(data["email"]))
        if data.get("phone") and not data.get("phone_hash"):
            data["phone_hash"] = phone_hash(str(data["phone"]))
        return data
