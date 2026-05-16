"""
Additive enrichment readiness for admin pending-verification queue rows.

Derives operational readiness from existing document / extraction fields only —
does not mutate workflow authority or stored enum values.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

READINESS_READY = "READY"
READINESS_PROCESSING = "PROCESSING"
READINESS_PARTIAL = "PARTIAL"
READINESS_FAILED = "FAILED"

MATCH_STATUS_PENDING = "PENDING"
MATCH_STATUS_COMPLETE = "COMPLETE"
MATCH_STATUS_FAILED = "FAILED"
MATCH_STATUS_SKIPPED = "SKIPPED"

EXTRACTION_TERMINAL = frozenset({
    "CONFIRMED",
    "REJECTED",
    "FAILED",
    "EXTRACTED",
    "NEEDS_REVIEW",
})
EXTRACTION_IN_PROGRESS = frozenset({"PENDING"})
EXTRACTION_FAILED = frozenset({"FAILED", "REJECTED"})

# Log when upload→ready exceeds this (ms) for observability
DELAYED_ENRICHMENT_THRESHOLD_MS = 5 * 60 * 1000


def _parse_iso(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    s = str(value).strip()
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _ms_between(start: Optional[datetime], end: Optional[datetime]) -> Optional[int]:
    if not start or not end:
        return None
    return int((end - start).total_seconds() * 1000)


def effective_extraction_status(
    doc: Dict[str, Any],
    extraction_record: Optional[Dict[str, Any]] = None,
) -> str:
    """Normalized extraction status for readiness (does not change stored values)."""
    direct = str(doc.get("extraction_status") or "").strip().upper()
    if direct:
        return direct
    rec_status = str((extraction_record or {}).get("status") or "").strip().upper()
    if rec_status and rec_status != "PENDING":
        return rec_status
    ai = doc.get("ai_extraction") if isinstance(doc.get("ai_extraction"), dict) else {}
    ai_st = str(ai.get("status") or "").strip().lower()
    if ai_st == "failed":
        return "FAILED"
    if ai_st == "completed":
        return "EXTRACTED"
    if doc.get("extraction_id") or (extraction_record or {}).get("extraction_id"):
        return "PENDING"
    return ""


def extraction_is_terminal(status: str) -> bool:
    return status in EXTRACTION_TERMINAL


def extraction_is_failed(status: str) -> bool:
    return status in EXTRACTION_FAILED


def match_evaluation_attempted(doc: Dict[str, Any]) -> bool:
    if doc.get("match_outcome"):
        return True
    if doc.get("mismatch_reason_code"):
        return True
    if doc.get("predicted_document_type"):
        return True
    if doc.get("evidence_match_legacy_state"):
        return True
    signals = doc.get("detection_signals")
    if isinstance(signals, dict) and signals:
        return True
    return False


def derive_match_status(doc: Dict[str, Any]) -> str:
    if match_evaluation_attempted(doc):
        return MATCH_STATUS_COMPLETE
    ext = effective_extraction_status(doc)
    if extraction_is_failed(ext):
        return MATCH_STATUS_FAILED
    return MATCH_STATUS_PENDING


def _enrichment_timestamps(
    doc: Dict[str, Any],
    extraction_record: Optional[Dict[str, Any]] = None,
) -> Tuple[Optional[datetime], Optional[datetime]]:
    started = _parse_iso(doc.get("uploaded_at"))
    rec = extraction_record or {}
    audit = rec.get("audit") if isinstance(rec.get("audit"), dict) else {}
    candidates: List[datetime] = []
    for raw in (
        (doc.get("ai_extraction") or {}).get("extracted_at") if isinstance(doc.get("ai_extraction"), dict) else None,
        (doc.get("ai_assistance") or {}).get("extraction_timestamp") if isinstance(doc.get("ai_assistance"), dict) else None,
        rec.get("extraction_timestamp"),
        audit.get("updated_at"),
        audit.get("created_at"),
    ):
        dt = _parse_iso(raw)
        if dt:
            candidates.append(dt)
    if not started and candidates:
        started = min(candidates)
    completed = max(candidates) if candidates else None
    return started, completed


def _partial_reasons(
    doc: Dict[str, Any],
    *,
    extraction_status: str,
    match_status: str,
    requirement_label_resolved: bool,
) -> List[str]:
    reasons: List[str] = []
    if extraction_is_terminal(extraction_status) and match_status == MATCH_STATUS_PENDING:
        reasons.append("match_pending")
    if doc.get("requirement_id") and not requirement_label_resolved:
        reasons.append("requirement_label_missing")
    if not doc.get("requirement_id") and not doc.get("property_id") and not doc.get("authoritative_property_id"):
        reasons.append("property_context_missing")
    if extraction_status == "NEEDS_REVIEW":
        reasons.append("extraction_needs_review")
    return reasons


def derive_enrichment_readiness(
    doc: Dict[str, Any],
    *,
    extraction_record: Optional[Dict[str, Any]] = None,
    requirement_label_resolved: bool = True,
) -> Dict[str, Any]:
    """
    Returns additive readiness payload for a single pending-verification document row.
    """
    extraction_status = effective_extraction_status(doc, extraction_record)
    match_status = derive_match_status(doc)
    started_at, completed_at = _enrichment_timestamps(doc, extraction_record)
    partial_reasons = _partial_reasons(
        doc,
        extraction_status=extraction_status,
        match_status=match_status,
        requirement_label_resolved=requirement_label_resolved,
    )

    readiness = READINESS_PROCESSING
    label = "Processing document…"
    detail = "Extraction and matching are still in progress."

    if extraction_is_failed(extraction_status) and match_status != MATCH_STATUS_COMPLETE:
        readiness = READINESS_FAILED
        label = "Extraction failed — review manually"
        detail = "Automated extraction did not complete. Open the file and verify manually."
    elif extraction_status in EXTRACTION_IN_PROGRESS or (
        not extraction_is_terminal(extraction_status) and not extraction_status
    ):
        if doc.get("extraction_id") or extraction_record:
            label = "Extraction in progress"
            detail = "Document text is being extracted before matching can run."
        elif not match_evaluation_attempted(doc):
            label = "Review preparation in progress"
            detail = "Automated analysis is still running after upload."
        readiness = READINESS_PROCESSING
    elif match_status == MATCH_STATUS_PENDING:
        readiness = READINESS_PARTIAL if extraction_is_terminal(extraction_status) else READINESS_PROCESSING
        label = "Matching requirement…" if readiness == READINESS_PARTIAL else "Processing document…"
        detail = (
            "Extraction finished but requirement matching has not completed yet."
            if readiness == READINESS_PARTIAL
            else detail
        )
    elif partial_reasons:
        readiness = READINESS_PARTIAL
        if "requirement_label_missing" in partial_reasons:
            label = "Requirement details pending"
            detail = "Requirement is linked but display details are still loading."
        elif "property_context_missing" in partial_reasons:
            label = "Property context pending"
            detail = "Property linkage is missing or still resolving."
        elif "extraction_needs_review" in partial_reasons:
            label = "Extraction needs review"
            detail = "Extracted fields need confirmation before full review."
        else:
            label = "Review preparation incomplete"
            detail = "Some operational context is still missing for this row."
    else:
        readiness = READINESS_READY
        label = "Ready for review"
        detail = "Extraction and matching have completed. You can verify or resolve match."

    latency_ms = _ms_between(started_at, completed_at if readiness == READINESS_READY else None)
    if latency_ms is None and started_at and readiness in (READINESS_READY, READINESS_PARTIAL, READINESS_FAILED):
        latency_ms = _ms_between(started_at, datetime.now(timezone.utc))

    return {
        "enrichment_readiness": readiness,
        "enrichment_readiness_label": label,
        "enrichment_readiness_detail": detail,
        "enrichment_partial_reasons": partial_reasons,
        "extraction_status": extraction_status or None,
        "match_status": match_status,
        "enrichment_started_at": started_at.isoformat() if started_at else None,
        "enrichment_completed_at": completed_at.isoformat() if completed_at and readiness == READINESS_READY else None,
        "enrichment_latency_ms": latency_ms,
    }


async def load_extraction_records_by_id(db, extraction_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    if not extraction_ids:
        return {}
    cursor = db.extracted_documents.find(
        {"extraction_id": {"$in": extraction_ids}},
        {
            "_id": 0,
            "extraction_id": 1,
            "status": 1,
            "extraction_timestamp": 1,
            "audit.created_at": 1,
            "audit.updated_at": 1,
            "errors": 1,
        },
    )
    rows = await cursor.to_list(len(extraction_ids))
    return {str(r["extraction_id"]): r for r in rows if r.get("extraction_id")}


def attach_verification_readiness_fields(
    items: List[Dict[str, Any]],
    extraction_by_id: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Mutates each document dict with readiness fields; returns observability summary.
    """
    summary: Dict[str, int] = {
        READINESS_READY: 0,
        READINESS_PROCESSING: 0,
        READINESS_PARTIAL: 0,
        READINESS_FAILED: 0,
    }
    delayed: List[str] = []
    stale_match_pending: List[str] = []
    now = datetime.now(timezone.utc)

    for doc in items:
        ext_id = doc.get("extraction_id")
        ext_rec = extraction_by_id.get(str(ext_id)) if ext_id else None
        req_resolved = bool(doc.get("requirement_label")) or not doc.get("requirement_id")
        payload = derive_enrichment_readiness(
            doc,
            extraction_record=ext_rec,
            requirement_label_resolved=req_resolved,
        )
        doc.update(payload)
        readiness = payload["enrichment_readiness"]
        summary[readiness] = summary.get(readiness, 0) + 1

        started = _parse_iso(payload.get("enrichment_started_at"))
        if started and readiness != READINESS_READY:
            age_ms = _ms_between(started, now) or 0
            if age_ms >= DELAYED_ENRICHMENT_THRESHOLD_MS:
                delayed.append(str(doc.get("document_id") or ""))
        if payload.get("match_status") == MATCH_STATUS_PENDING and extraction_is_terminal(
            str(payload.get("extraction_status") or "")
        ):
            stale_match_pending.append(str(doc.get("document_id") or ""))

    observability = {
        "readiness_counts": summary,
        "delayed_enrichment_count": len(delayed),
        "delayed_document_ids": [d for d in delayed if d][:20],
        "stale_match_pending_count": len(stale_match_pending),
        "stale_match_pending_document_ids": [d for d in stale_match_pending if d][:20],
        "delayed_threshold_ms": DELAYED_ENRICHMENT_THRESHOLD_MS,
    }
    if delayed or stale_match_pending:
        logger.warning(
            "pending_verification_enrichment_observability delayed=%s stale_match_pending=%s counts=%s",
            len(delayed),
            len(stale_match_pending),
            summary,
            extra={"observability": observability},
        )
    else:
        logger.info(
            "pending_verification_enrichment_observability counts=%s returned=%s",
            summary,
            len(items),
            extra={"observability": observability},
        )
    return observability
