from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Form, Depends, status, Body, Query
from pydantic import BaseModel, ConfigDict
from database import database
from middleware import client_route_guard, admin_route_guard
from models import Document, DocumentStatus, RequirementStatus, AuditAction
from utils.audit import create_audit_log
from utils.compliance_fanout_log import compliance_fanout_extra
from utils.api_errors import log_api_error, structured_error
from utils.rate_limiter import rate_limiter, log_rate_limit_event
from config.security_limits import security_limits
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Mapping, Optional, Tuple
import asyncio
import json
import os
import uuid
import logging
from pathlib import Path

from utils.storage_paths import resolve_data_dir, resolve_document_storage_path
from services.authority_mutation_fanout import (
    authority_sync_with_transition_observability,
    enqueue_compliance_recalc_with_fanout,
)
from services.requirement_evidence_authority import (
    normalize_document_evidence_scope,
    sync_for_documents_touching,
    sync_requirement_evidence_authority,
)
from services.requirement_transition_observability import (
    ensure_requirement_transition_correlation_id,
    merge_document_path_lineage_flags,
    merge_pre_authority_optimistic_requirement_promotion_marker,
    transition_origin_document_touch,
)
from services.compliance_evidence_record_service import safe_upsert_document_upload_evidence_for_linked_document
from services.work_order_execution_constants import (
    COMPLIANCE_PROOF_NOT_SUBMITTED,
    COMPLIANCE_PROOF_SUBMITTED,
    COMPLIANCE_PROOF_VERIFIED,
    WORK_ORDER_KIND_COMPLIANCE,
)
from services.evidence_document_taxonomy import POLICY_BLOCK_UPLOAD, MATCH_OUTCOME_MATCH_CONFIRMED
from services.evidence_document_match_engine import (
    evaluate_document_requirement_match,
    match_evaluation_to_persisted_document_fields,
    document_blocks_verified_satisfaction,
)
from services.evidence_review_migration import apply_v2_defaults_to_new_upload
from services.client_propagation_notice import (
    build_propagation_notice_from_transition_fanout,
    merge_propagation_notice_from_ordered_transition_fanouts,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/documents", tags=["documents"])


def _document_verification_replay_heuristic(old_status: Optional[str]) -> bool:
    """True when verify is applied while document was already VERIFIED (observability hint only)."""
    return str(old_status or "").strip().upper() == str(DocumentStatus.VERIFIED.value).upper()


async def _document_path_sync_requirement_authority(
    db,
    requirement_id: str,
    *,
    property_id: Optional[str],
    client_id: str,
    correlation_base: str,
    transition_origin: str,
    transition_fanout: Dict[str, Any],
    document_id: Optional[str] = None,
    verification_replay_possible: bool = False,
    revert_retrigger_possible: bool = False,
    document_replacement_detected: bool = False,
    stale_document_transition_possible: bool = False,
) -> None:
    await authority_sync_with_transition_observability(
        db,
        requirement_id,
        property_id=property_id,
        client_id=client_id,
        correlation_base=correlation_base,
        transition_origin=transition_origin,
        transition_fanout=transition_fanout,
    )
    if document_id:
        merge_document_path_lineage_flags(
            transition_fanout,
            document_id=document_id,
            verification_replay_possible=verification_replay_possible,
            revert_retrigger_possible=revert_retrigger_possible,
            document_replacement_detected=document_replacement_detected,
            stale_document_transition_possible=stale_document_transition_possible,
        )


async def _document_path_enqueue_recalc(
    transition_fanout: Optional[Dict[str, Any]],
    *,
    property_id: str,
    client_id: str,
    trigger_reason: str,
    actor_type: str,
    actor_id: Optional[str],
    correlation_id: str,
    trigger_origin: str,
    propagation_stage: str,
) -> None:
    await enqueue_compliance_recalc_with_fanout(
        transition_fanout,
        property_id=property_id,
        client_id=client_id,
        trigger_reason=trigger_reason,
        actor_type=actor_type,
        actor_id=actor_id,
        correlation_id=correlation_id,
        trigger_origin=trigger_origin,
        propagation_stage=propagation_stage,
        fanout_op="document_transition_fanout",
    )


def _finalize_bulk_zip_results_propagation_notices(
    results: List[Dict[str, Any]],
    fanout_by_document_id: Mapping[str, Dict[str, Any]],
) -> Optional[Dict[str, str]]:
    """
    L-009f: per successful row with an authority fanout, attach optional ``propagation_notice``.

    **Merge precedence (top-level summary):** ``merge_propagation_notice_from_ordered_transition_fanouts``
    over fanouts in **``results`` iteration order** (stable processing order). The merge helper applies
    **NOTICE_AUTHORITY_SYNC_DEFERRED** over **NOTICE_RECALC_ENQUEUE_DEFERRED** regardless of position
    once an authority-deferred fanout is seen later in the sequence (see helper implementation).
    """
    ordered: List[Optional[Dict[str, Any]]] = []
    for r in results:
        if r.get("status") != "uploaded" or not r.get("document_id"):
            continue
        did = str(r["document_id"])
        fo = fanout_by_document_id.get(did)
        if fo is None:
            continue
        pn_row = build_propagation_notice_from_transition_fanout(fo)
        if pn_row:
            r["propagation_notice"] = pn_row
        ordered.append(fo)
    return merge_propagation_notice_from_ordered_transition_fanouts(ordered)


# DOCUMENT_UPLOAD bounded slices: static registry only (gas_safety, eicr, epc). Observability attachment only.
_BOUND_DOCUMENT_UPLOAD_ACTIVATION_SLICES: Dict[str, Dict[str, frozenset[str]]] = {
    "gas_safety": {"canonical_codes": frozenset({"gas_safety"})},
    "eicr": {"canonical_codes": frozenset({"eicr"})},
    "epc": {"canonical_codes": frozenset({"epc"})},
}
# Explicit precedence when resolving slices (matches legacy if gas_safety / elif eicr / elif epc).
_BOUND_DOCUMENT_UPLOAD_ACTIVATION_SLICE_ORDER: Tuple[str, ...] = ("gas_safety", "eicr", "epc")

_DOCUMENT_UPLOAD_BOUND_SLICE_ACTIVATION_DOWNSTREAM_ALLOWLIST = frozenset(
    {
        "compliance_gap_sync.sync_compliance_gaps_for_requirement",
        "requirement_state_transition.core_backbone.authority_sync",
        "compliance_recalc_queue.enqueue_compliance_recalc",
        "risk_signal_regen_queue.enqueue_risk_signal_regen",
    }
)


def _resolve_bound_document_upload_activation_obligation_slice(
    requirement: Optional[Dict[str, Any]],
) -> Optional[str]:
    """
    Return obligation_slice key when requirement matches an explicit bounded DOCUMENT_UPLOAD slice.

    Order is gas_safety → eicr → epc per slice, and requirement_code → requirement_type per field,
    matching the previous chained detectors. Code-only; no dynamic registration.
    """
    if not requirement:
        return None
    from services.requirement_code_registry import normalize_requirement_code

    for obligation_slice in _BOUND_DOCUMENT_UPLOAD_ACTIVATION_SLICE_ORDER:
        codes = _BOUND_DOCUMENT_UPLOAD_ACTIVATION_SLICES[obligation_slice]["canonical_codes"]
        for req_key in ("requirement_code", "requirement_type"):
            canon = normalize_requirement_code(requirement.get(req_key))
            if canon and canon in codes:
                return obligation_slice
    return None


def _workflow_activation_observability_for_bounded_document_upload_slice(
    fanout: Mapping[str, Any],
    *,
    obligation_slice: str,
    document_upload_correlation_id: str,
) -> Dict[str, Any]:
    raw_targets = fanout.get("downstream_trigger_targets")
    if raw_targets is None:
        raw_targets = fanout.get("downstream_propagation") or []
    filtered: List[Dict[str, Any]] = []
    for row in raw_targets:
        if not isinstance(row, Mapping):
            continue
        dt = str(row.get("downstream_target") or "")
        if dt not in _DOCUMENT_UPLOAD_BOUND_SLICE_ACTIVATION_DOWNSTREAM_ALLOWLIST:
            continue
        filtered.append(dict(row))

    backbone = fanout.get("rst_core_backbone_activation")
    backbone_copy: Dict[str, Any] = dict(backbone) if isinstance(backbone, Mapping) else {}

    return {
        "workflow_class": "DOCUMENT_UPLOAD",
        "obligation_slice": obligation_slice,
        "document_upload_correlation_id": document_upload_correlation_id,
        "transition_id": fanout.get("transition_id"),
        "requirement_transition_correlation_id": fanout.get("correlation_id"),
        "transition_outcome": fanout.get("transition_outcome"),
        "rst_core_backbone_activation": backbone_copy,
        "approved_downstream_observations": filtered,
    }


def _workflow_activation_observability_for_gas_safety_client_upload(
    fanout: Mapping[str, Any],
    *,
    document_upload_correlation_id: str,
) -> Dict[str, Any]:
    return _workflow_activation_observability_for_bounded_document_upload_slice(
        fanout,
        obligation_slice="gas_safety",
        document_upload_correlation_id=document_upload_correlation_id,
    )


def _build_validation_result_persist(
    document_validation: Dict[str, Any],
    *,
    document_type_input: Optional[str],
    validated_at_iso: str,
) -> Dict[str, Any]:
    """Stable snapshot for Mongo + audit (re-validation)."""
    missing = document_validation.get("missing_metadata_fields")
    if missing is None:
        missing_list: List[Any] = []
    elif isinstance(missing, list):
        missing_list = list(missing)
    else:
        missing_list = [missing]
    return {
        "valid": bool(document_validation.get("valid")),
        "jurisdiction": document_validation.get("jurisdiction"),
        "validated_at": validated_at_iso,
        "missing_metadata_fields": missing_list,
        "reason": document_validation.get("reason"),
        "scoring_jurisdiction": document_validation.get("scoring_jurisdiction"),
        "portfolio_jurisdiction": document_validation.get("portfolio_jurisdiction"),
        "document_type_input": document_type_input,
    }


def _parse_upload_document_metadata(document_metadata: Optional[str]) -> Optional[Dict[str, Any]]:
    if not document_metadata or not str(document_metadata).strip():
        return None
    try:
        parsed = json.loads(document_metadata)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=structured_error(
                "INVALID_DOCUMENT_METADATA",
                "document_metadata must be a JSON object (e.g. {\"issue_date\":\"2024-01-15\",\"engineer_id\":\"REG123\"}).",
            ),
        )
    if not isinstance(parsed, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=structured_error(
                "INVALID_DOCUMENT_METADATA",
                "document_metadata must be a JSON object (e.g. {\"issue_date\":\"2024-01-15\",\"engineer_id\":\"REG123\"}).",
            ),
        )
    return dict(parsed)


async def _enforce_document_upload_rate_limit(client_id: str) -> None:
    key = f"document_upload:{client_id}"
    ok, msg = await rate_limiter.check_rate_limit(
        key,
        security_limits.document_upload_per_client_per_hour,
        60,
    )
    if not ok:
        log_rate_limit_event("document_upload", client_id, None)
        await create_audit_log(
            action=AuditAction.RATE_LIMIT_EXCEEDED,
            client_id=client_id,
            metadata={"scope": "document_upload", "client_id": client_id},
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=msg or "Upload limit reached for this hour. Try again later.",
        )


async def _validate_optional_work_order_document_link(
    db,
    *,
    work_order_id: Optional[str],
    client_id: str,
    property_id: str,
    requirement_id: Optional[str],
) -> Optional[str]:
    """If work_order_id is set, ensure it is a compliance WO for this client/property (and requirement when linked)."""
    # Direct calls (unit tests) may pass FastAPI Form(...) defaults instead of bound values
    if work_order_id is not None and not isinstance(work_order_id, str):
        work_order_id = None
    if not (work_order_id or "").strip():
        return None
    wid = work_order_id.strip()
    wo = await db.work_orders.find_one(
        {"work_order_id": wid, "client_id": client_id},
        {"_id": 0, "property_id": 1, "work_order_kind": 1, "linked_property_requirement_id": 1},
    )
    if not wo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Work order not found",
        )
    if wo.get("property_id") != property_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Work order property does not match the selected property",
        )
    if (wo.get("work_order_kind") or "").strip().upper() != WORK_ORDER_KIND_COMPLIANCE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only compliance execution work orders can be linked to document uploads",
        )
    link_req = (wo.get("linked_property_requirement_id") or "").strip()
    if link_req and requirement_id and link_req != str(requirement_id).strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This work order is tied to a different requirement than the one selected",
        )
    return wid


async def _append_document_evidence_to_work_order(document_id: str, work_order_id: Optional[str]) -> None:
    """Attach a stable document pointer to a compliance work order evidence list (idempotent via $addToSet)."""
    if not (work_order_id or "").strip():
        return
    wid = work_order_id.strip()
    db = database.get_db()
    wo = await db.work_orders.find_one({"work_order_id": wid}, {"_id": 0, "work_order_kind": 1})
    if not wo or (wo.get("work_order_kind") or "").strip().upper() != WORK_ORDER_KIND_COMPLIANCE:
        return
    from services import maintenance_service

    await maintenance_service.update_work_order(
        wid,
        evidence_keys_append=[f"document:{document_id}"],
    )


async def _finalize_active_compliance_jobs_after_certificate_verified(
    db,
    *,
    client_id: str,
    requirement_id: str,
    document_id: str,
    actor_id: Optional[str],
) -> None:
    """
    Link verified certificate to every active compliance job for this requirement and move jobs to VERIFIED.
    Idempotent: safe if work order already terminal.
    """
    from services import maintenance_service
    from services.work_order_execution_constants import WORK_ORDER_KIND_COMPLIANCE

    terminal = frozenset(
        {
            maintenance_service.STATUS_CANCELLED,
            maintenance_service.STATUS_COMPLETED,
            maintenance_service.STATUS_CLOSED,
            maintenance_service.STATUS_VERIFIED,
        }
    )
    key = f"document:{document_id.strip()}"
    cursor = db.work_orders.find(
        {
            "client_id": client_id.strip(),
            "work_order_kind": WORK_ORDER_KIND_COMPLIANCE,
            "linked_property_requirement_id": requirement_id.strip(),
            "status": {"$nin": list(terminal)},
        },
        {"_id": 0, "work_order_id": 1},
    )
    async for row in cursor:
        wid = (row.get("work_order_id") or "").strip()
        if not wid:
            continue
        try:
            await maintenance_service.update_work_order(
                wid,
                evidence_keys_append=[key],
                assigned_by=actor_id,
            )
            await maintenance_service.update_work_order(
                wid,
                status=maintenance_service.STATUS_VERIFIED,
                assigned_by=actor_id,
            )
        except Exception as ex:
            logger.warning("Finalize compliance job %s on document verify failed: %s", wid, ex)


async def _set_compliance_work_order_proof_verified(db, work_order_id: Optional[str]) -> None:
    """After a linked document is verified, mark compliance proof as policy-satisfied on the work order."""
    if not (work_order_id or "").strip():
        return
    wid = work_order_id.strip()
    now = datetime.now(timezone.utc).isoformat()
    await db.work_orders.update_one(
        {"work_order_id": wid, "work_order_kind": WORK_ORDER_KIND_COMPLIANCE},
        {"$set": {"compliance_proof_status": COMPLIANCE_PROOF_VERIFIED, "updated_at": now}},
    )


async def _reconcile_compliance_work_order_proof_after_document_removed(
    db,
    document_id: str,
    work_order_id: Optional[str],
) -> None:
    """
    When a document linked to a compliance work order is rejected or deleted:
    remove its evidence pointer, then set compliance_proof_status from remaining evidence and VERIFIED documents.
    """
    if not (work_order_id or "").strip() or not (document_id or "").strip():
        return
    wid = work_order_id.strip()
    did = document_id.strip()
    wo = await db.work_orders.find_one(
        {"work_order_id": wid, "work_order_kind": WORK_ORDER_KIND_COMPLIANCE},
        {"_id": 0, "work_order_id": 1},
    )
    if not wo:
        return
    now = datetime.now(timezone.utc).isoformat()
    key = f"document:{did}"
    await db.work_orders.update_one(
        {"work_order_id": wid, "work_order_kind": WORK_ORDER_KIND_COMPLIANCE},
        {"$pull": {"evidence_keys": key}, "$set": {"updated_at": now}},
    )
    wo2 = await db.work_orders.find_one({"work_order_id": wid}, {"_id": 0, "evidence_keys": 1})
    ev = [k for k in (wo2 or {}).get("evidence_keys") or [] if k]
    doc_refs: list[str] = []
    for k in ev:
        if isinstance(k, str) and k.startswith("document:"):
            rid = k[9:].strip()
            if rid:
                doc_refs.append(rid)
    # Exclude the removed document so pre-delete reconciliation does not count a soon-deleted VERIFIED row.
    verified_base: Dict[str, Any] = {
        "status": DocumentStatus.VERIFIED.value,
        "document_id": {"$ne": did},
    }
    if doc_refs:
        verified_q: Dict[str, Any] = {
            **verified_base,
            "$or": [
                {"work_order_id": wid},
                {"document_id": {"$in": doc_refs}},
            ],
        }
    else:
        verified_q = {**verified_base, "work_order_id": wid}
    has_verified = await db.documents.count_documents(verified_q) > 0
    if has_verified:
        proof = COMPLIANCE_PROOF_VERIFIED
    elif ev:
        proof = COMPLIANCE_PROOF_SUBMITTED
    else:
        proof = COMPLIANCE_PROOF_NOT_SUBMITTED
    await db.work_orders.update_one(
        {"work_order_id": wid, "work_order_kind": WORK_ORDER_KIND_COMPLIANCE},
        {"$set": {"compliance_proof_status": proof, "updated_at": datetime.now(timezone.utc).isoformat()}},
    )


def _normalize_and_parse_date(date_value) -> datetime:
    """Enterprise-safe date normalization and parsing.
    
    Handles:
    - ISO format: YYYY-MM-DD, YYYY-MM-DDTHH:MM:SS, YYYY-MM-DDTHH:MM:SSZ
    - UK format: DD/MM/YYYY
    - Unicode dash variants (en-dash, em-dash, figure dash, etc.)
    - Hidden whitespace characters
    - Already parsed datetime objects
    
    Returns:
        datetime object with UTC timezone
        
    Raises:
        ValueError if date cannot be parsed
    """
    import re
    import unicodedata
    
    # Handle datetime objects directly
    if isinstance(date_value, datetime):
        if date_value.tzinfo is None:
            return date_value.replace(tzinfo=timezone.utc)
        return date_value
    
    # Convert to string if needed
    date_str = str(date_value) if date_value else ""
    
    # Debug logging for troubleshooting
    logger.debug(f"Date normalization input: repr={repr(date_str)}, len={len(date_str)}")
    logger.debug(f"Date codepoints: {[f'U+{ord(c):04X}' for c in date_str]}")
    
    # Step 1: Strip whitespace and normalize unicode
    date_str = date_str.strip()
    date_str = unicodedata.normalize('NFKC', date_str)
    
    # Step 2: Replace unicode dash variants with ASCII hyphen
    # Common unicode dashes: en-dash (–), em-dash (—), minus (−), figure dash (‒)
    unicode_dashes = [
        '\u2010',  # Hyphen
        '\u2011',  # Non-breaking hyphen
        '\u2012',  # Figure dash
        '\u2013',  # En dash
        '\u2014',  # Em dash
        '\u2015',  # Horizontal bar
        '\u2212',  # Minus sign
        '\uFE58',  # Small em dash
        '\uFE63',  # Small hyphen-minus
        '\uFF0D',  # Fullwidth hyphen-minus
    ]
    for dash in unicode_dashes:
        date_str = date_str.replace(dash, '-')
    
    # Step 3: Remove any invisible/control characters
    date_str = re.sub(r'[\x00-\x1f\x7f-\x9f\u200b-\u200f\u2028-\u202f\u205f-\u206f]', '', date_str)
    
    # Step 4: Handle ISO format with time component
    if 'T' in date_str:
        date_str = date_str.split('T')[0]
    
    # Step 5: Remove timezone suffixes
    date_str = date_str.replace('Z', '')
    date_str = re.sub(r'[+-]\d{2}:?\d{2}$', '', date_str)
    
    # Step 6: Try parsing different formats
    date_str = date_str.strip()
    
    # Try ISO format: YYYY-MM-DD
    iso_match = re.match(r'^(\d{4})-(\d{1,2})-(\d{1,2})$', date_str)
    if iso_match:
        year, month, day = map(int, iso_match.groups())
        return datetime(year, month, day, tzinfo=timezone.utc)
    
    # Try UK format: DD/MM/YYYY
    uk_match = re.match(r'^(\d{1,2})/(\d{1,2})/(\d{4})$', date_str)
    if uk_match:
        day, month, year = map(int, uk_match.groups())
        return datetime(year, month, day, tzinfo=timezone.utc)
    
    # Try UK format with dashes: DD-MM-YYYY
    uk_dash_match = re.match(r'^(\d{1,2})-(\d{1,2})-(\d{4})$', date_str)
    if uk_dash_match:
        day, month, year = map(int, uk_dash_match.groups())
        return datetime(year, month, day, tzinfo=timezone.utc)
    
    # Try ISO format with slashes: YYYY/MM/DD
    iso_slash_match = re.match(r'^(\d{4})/(\d{1,2})/(\d{1,2})$', date_str)
    if iso_slash_match:
        year, month, day = map(int, iso_slash_match.groups())
        return datetime(year, month, day, tzinfo=timezone.utc)
    
    # Last resort: try standard datetime parsing
    for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%Y/%m/%d', '%d %b %Y', '%d %B %Y']:
        try:
            return datetime.strptime(date_str, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    
    # If all else fails, raise with details
    raise ValueError(
        f"Cannot parse date: '{date_str}' (repr={repr(date_str)}, "
        f"codepoints={[f'U+{ord(c):04X}' for c in date_str]})"
    )


# Request models for apply extraction
class EngineerDetails(BaseModel):
    name: Optional[str] = None
    registration_number: Optional[str] = None
    company_name: Optional[str] = None


class ResultSummary(BaseModel):
    overall_result: Optional[str] = None


class ExtractionApplyRequest(BaseModel):
    confirmed_data: Optional[Dict[str, Any]] = None


class DocumentLinkageReconcileRequest(BaseModel):
    """Client post-ingestion document↔requirement linkage reconciliation."""

    model_config = ConfigDict(extra="ignore")

    action: str
    requirement_id: Optional[str] = None
    property_id: Optional[str] = None
    reason: Optional[str] = None


class VerifyDocumentBody(BaseModel):
    """Admin verify: optional override when evidence match engine blocked verification."""

    model_config = ConfigDict(extra="ignore")

    evidence_mismatch_override: bool = False
    evidence_mismatch_override_reason: Optional[str] = None
    # Evidence Review V2: when validation_status=FAIL, require a non-empty reason to record supervised override
    validation_override_reason: Optional[str] = None


# Document storage directory (configurable via DATA_DIR or DOCUMENT_STORAGE_PATH)
DATA_DIR = resolve_data_dir()
DOCUMENT_STORAGE_PATH = resolve_document_storage_path()
DOCUMENT_STORAGE_PATH.mkdir(parents=True, exist_ok=True)


async def _run_analysis_after_upload(
    document_id: str,
    client_id: str,
    actor_id: Optional[str],
    file_path: str,
    mime_type: str,
) -> None:
    """Run AI document analysis in background after upload (PDF + images). Sets ai_extraction on doc."""
    db = database.get_db()
    try:
        from services.document_analysis import document_analysis_service
        result = await document_analysis_service.analyze_document(
            file_path=file_path,
            mime_type=mime_type,
            document_id=document_id,
            client_id=client_id,
            actor_id=actor_id,
        )
        if not result.get("success"):
            error_code = result.get("error_code") or "ANALYSIS_FAILED"
            await db.documents.update_one(
                {"document_id": document_id},
                {"$set": {
                    "ai_extraction": {
                        "extracted_at": datetime.now(timezone.utc).isoformat(),
                        "status": "failed",
                        "error": (result.get("error") or "Extraction failed — review manually.")[:500],
                        "error_code": error_code,
                    }
                }},
            )
            logger.info(
                "Document extraction failed: document_id=%s error_code=%s (set OPENAI_API_KEY or LLM_API_KEY for AI; manual entry always available)",
                document_id, error_code,
            )
        else:
            # Success: persist extraction only (analyze_document already wrote ai_extraction).
            # Requirement / compliance updates run only after the client confirms via apply-extraction
            # or an explicit admin flow — not on upload alone.
            extracted_data = result.get("extracted_data") or {}
            doc = await db.documents.find_one(
                {"document_id": document_id},
                {"_id": 0, "requirement_id": 1, "property_id": 1, "client_id": 1},
            )
            extra: Dict[str, Any] = {}
            if doc and doc.get("client_id"):
                req = None
                if doc.get("requirement_id"):
                    req = await db.requirements.find_one(
                        {"requirement_id": doc["requirement_id"], "client_id": doc["client_id"]},
                        {"_id": 0},
                    )
                mev = evaluate_document_requirement_match(
                    requirement=req,
                    filename=str(doc.get("file_name") or ""),
                    user_declared_document_type=doc.get("document_type"),
                    extracted_data=extracted_data,
                    upload_route_context="post_ai_extraction",
                )
                extra.update(match_evaluation_to_persisted_document_fields(mev))
                extra["requirement_evidence_mismatch"] = bool(mev.get("requirement_evidence_mismatch"))
                rtxt = mev.get("mismatch_reason_text")
                extra["requirement_evidence_mismatch_reason"] = (rtxt[:500] if isinstance(rtxt, str) else None)
                if mev.get("manual_review_flag_suggested"):
                    extra["manual_review_flag"] = True
            if extra:
                await db.documents.update_one({"document_id": document_id}, {"$set": extra})
            await sync_for_documents_touching(db, document_id=document_id)
    except Exception as e:
        logger.warning("Post-upload analysis failed for %s: %s", document_id, e)
        await db.documents.update_one(
            {"document_id": document_id},
            {"$set": {
                "ai_extraction": {
                    "extracted_at": datetime.now(timezone.utc).isoformat(),
                    "status": "failed",
                    "error": str(e)[:500],
                    "error_code": "AI_ERROR",
                }
            }},
        )


@router.post("/bulk-upload")
async def bulk_upload_documents(
    request: Request,
    files: list[UploadFile] = File(...),
    property_id: str = Form(...),
):
    """Bulk upload multiple documents for a property.
    
    Gated: PORTFOLIO and PROFESSIONAL only (zip_upload feature).
    Documents will be auto-matched to requirements based on AI analysis.
    """
    # Feature gating enforcement
    from middleware.feature_gating import require_feature
    gating_check = require_feature("zip_upload")
    await gating_check(lambda r: None)(request)
    
    user = await client_route_guard(request)
    await _enforce_document_upload_rate_limit(user["client_id"])
    db = database.get_db()
    
    try:
        # Verify property belongs to client
        property_doc = await db.properties.find_one(
            {"property_id": property_id, "client_id": user["client_id"]},
            {"_id": 0}
        )
        
        if not property_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Property not found"
            )
        if property_doc.get("is_active") is False:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error_code": "PLAN_LIMIT",
                    "message": "This property is archived. Activate it from property settings or upgrade your plan to add documents.",
                },
            )
        
        # Get all requirements for this property
        requirements = await db.requirements.find(
            {"property_id": property_id, "client_id": user["client_id"]},
            {"_id": 0}
        ).to_list(100)
        from services.requirement_client_runtime_surface import filter_requirement_rows_for_client_runtime_surfaces

        requirements = await filter_requirement_rows_for_client_runtime_surfaces(
            db,
            client_id=user["client_id"],
            requirements=requirements,
            client_doc=await db.clients.find_one({"client_id": user["client_id"]}, {"_id": 0}) or {},
            properties=[property_doc],
        )
        
        results = []
        bulk_authority_fanout_by_document_id: Dict[str, Dict[str, Any]] = {}

        for file in files:
            try:
                # Create unique filename
                file_extension = Path(file.filename).suffix
                unique_filename = f"{uuid.uuid4()}{file_extension}"
                file_path = DOCUMENT_STORAGE_PATH / user["client_id"] / unique_filename
                file_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Save file
                contents = await file.read()
                with open(file_path, "wb") as f:
                    f.write(contents)
                
                stored_path = f"{user['client_id']}/{unique_filename}"
                # Create document record (without requirement assignment initially)
                document = Document(
                    client_id=user["client_id"],
                    property_id=property_id,
                    requirement_id=None,  # Will be assigned after AI analysis
                    file_name=file.filename,
                    file_path=stored_path,
                    file_size=len(contents),
                    mime_type=file.content_type or "application/octet-stream",
                    status=DocumentStatus.UPLOADED,
                    uploaded_by=user["portal_user_id"]
                )
                
                doc = document.model_dump()
                doc["uploaded_at"] = doc["uploaded_at"].isoformat()
                apply_v2_defaults_to_new_upload(doc)
                
                await db.documents.insert_one(doc)
                
                # Try AI analysis + requirement-aware match engine (parity with single-upload validation)
                matched_requirement = None
                bulk_match_payload: Dict[str, Any] = {}
                try:
                    from services.document_analysis import document_analysis_service

                    analysis_result = await document_analysis_service.analyze_document(
                        file_path=str(file_path),
                        mime_type=file.content_type or "application/pdf",
                        document_id=document.document_id,
                        client_id=user["client_id"],
                        actor_id=user["portal_user_id"],
                    )

                    if analysis_result.get("success"):
                        extracted = analysis_result.get("extracted_data") or {}
                        best_ev: Optional[Dict[str, Any]] = None
                        best_req_id: Optional[str] = None
                        best_score = -1.0
                        from services.evidence_document_taxonomy import (
                            MATCH_OUTCOME_MATCH_CONFIRMED,
                            MATCH_OUTCOME_MATCH_LIKELY,
                        )

                        for req in requirements:
                            ev = evaluate_document_requirement_match(
                                requirement=req,
                                filename=file.filename or "",
                                user_declared_document_type=None,
                                extracted_data=extracted,
                                upload_route_context="bulk_upload_post_analysis",
                            )
                            mo = str(ev.get("match_outcome") or "")
                            if mo not in (MATCH_OUTCOME_MATCH_CONFIRMED, MATCH_OUTCOME_MATCH_LIKELY):
                                continue
                            if not ev.get("evidence_satisfies_requirement"):
                                continue
                            sc = float(ev.get("match_confidence") or 0.0)
                            if sc > best_score:
                                best_score = sc
                                best_ev = ev
                                best_req_id = str(req.get("requirement_id") or "")

                        if best_req_id and best_ev:
                            matched_requirement = best_req_id
                            bulk_match_payload = match_evaluation_to_persisted_document_fields(best_ev)
                            bulk_match_payload["requirement_id"] = best_req_id
                        else:
                            ev_unlinked = evaluate_document_requirement_match(
                                requirement=None,
                                filename=file.filename or "",
                                user_declared_document_type=None,
                                extracted_data=extracted,
                                upload_route_context="bulk_upload_post_analysis_unlinked",
                            )
                            bulk_match_payload = match_evaluation_to_persisted_document_fields(ev_unlinked)
                            if ev_unlinked.get("manual_review_flag_suggested"):
                                bulk_match_payload["manual_review_flag"] = True

                        if bulk_match_payload:
                            await db.documents.update_one(
                                {"document_id": document.document_id},
                                {"$set": bulk_match_payload},
                            )
                        if matched_requirement:
                            await safe_upsert_document_upload_evidence_for_linked_document(
                                db,
                                client_id=user["client_id"],
                                property_id=property_id,
                                requirement_id=matched_requirement,
                                document_id=document.document_id,
                                actor_user_id=user.get("portal_user_id"),
                                filename=file.filename,
                                context="bulk_upload",
                            )
                            tf_bulk: Dict[str, Any] = {}
                            await _document_path_sync_requirement_authority(
                                db,
                                matched_requirement,
                                property_id=property_id,
                                client_id=user["client_id"],
                                correlation_base=f"DOC_UPLOADED:{document.document_id}",
                                transition_origin="routes.documents.bulk_upload_documents",
                                transition_fanout=tf_bulk,
                                document_id=document.document_id,
                                stale_document_transition_possible=True,
                            )
                            bulk_authority_fanout_by_document_id[document.document_id] = tf_bulk
                except Exception as e:
                    logger.warning(f"AI analysis failed for {file.filename}: {e}")

                results.append(
                    {
                        "filename": file.filename,
                        "document_id": document.document_id,
                        "status": "uploaded",
                        "matched_requirement": matched_requirement,
                        "ai_analyzed": matched_requirement is not None,
                        "evidence_match": bulk_match_payload or None,
                    }
                )
                
            except Exception as e:
                logger.error(f"Failed to upload {file.filename}: {e}")
                results.append({
                    "filename": file.filename,
                    "status": "failed",
                    "error": str(e)
                })
        
        # Audit log
        await create_audit_log(
            action=AuditAction.DOCUMENT_UPLOADED,
            actor_id=user["portal_user_id"],
            client_id=user["client_id"],
            resource_type="documents_bulk",
            metadata={
                "property_id": property_id,
                "files_count": len(files),
                "successful": sum(1 for r in results if r["status"] == "uploaded"),
                "auto_matched": sum(1 for r in results if r.get("matched_requirement"))
            }
        )
        
        from services.compliance_recalc_queue import TRIGGER_DOC_UPLOADED, ACTOR_CLIENT

        for r in results:
            if r.get("status") == "uploaded" and r.get("document_id"):
                doc_id_b = str(r["document_id"])
                await _document_path_enqueue_recalc(
                    bulk_authority_fanout_by_document_id.get(doc_id_b),
                    property_id=property_id,
                    client_id=user["client_id"],
                    trigger_reason=TRIGGER_DOC_UPLOADED,
                    actor_type=ACTOR_CLIENT,
                    actor_id=user.get("portal_user_id"),
                    correlation_id=f"DOC_UPLOADED:{doc_id_b}",
                    trigger_origin="routes.documents.bulk_upload_documents",
                    propagation_stage="post_bulk_authority_sync",
                )
                try:
                    from services.score_events_service import write_score_event, EVENT_DOCUMENT_UPLOADED, ACTOR_ROLE_CLIENT
                    await write_score_event(
                        client_id=user["client_id"],
                        event_type=EVENT_DOCUMENT_UPLOADED,
                        actor_user_id=user.get("portal_user_id"),
                        actor_role=ACTOR_ROLE_CLIENT,
                        property_id=property_id,
                        requirement_id=r.get("requirement_id"),
                        document_id=r["document_id"],
                        metadata={"filename": r.get("filename")},
                    )
                except Exception as ev_err:
                    logger.debug("Score event DOCUMENT_UPLOADED (bulk) skip: %s", ev_err)

        top_pn_bulk = _finalize_bulk_zip_results_propagation_notices(results, bulk_authority_fanout_by_document_id)
        out_bulk: Dict[str, Any] = {
            "message": f"Processed {len(files)} files",
            "results": results,
            "summary": {
                "total": len(files),
                "successful": sum(1 for r in results if r["status"] == "uploaded"),
                "failed": sum(1 for r in results if r["status"] == "failed"),
                "auto_matched": sum(1 for r in results if r.get("matched_requirement")),
            },
        }
        if top_pn_bulk:
            out_bulk["propagation_notice"] = top_pn_bulk
        return out_bulk

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Bulk upload error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process bulk upload"
        )


@router.post("/zip-upload")
async def upload_zip_archive(
    request: Request,
    file: UploadFile = File(...),
    property_id: str = Form(...),
):
    """Upload a ZIP archive containing multiple documents.
    
    The ZIP file will be extracted and each document will be processed individually.
    Requires Portfolio plan (PLAN_6_15) or higher.
    
    Supported file types inside ZIP:
    - PDF (.pdf)
    - Images (.jpg, .jpeg, .png)
    - Word documents (.doc, .docx)
    """
    import zipfile
    import tempfile
    import shutil
    
    user = await client_route_guard(request)
    await _enforce_document_upload_rate_limit(user["client_id"])
    db = database.get_db()
    
    try:
        # Plan gating: zip_upload requires PLAN_2_PORTFOLIO (plan_registry)
        from services.plan_registry import plan_registry

        allowed, error_msg, error_details = await plan_registry.enforce_feature(
            user["client_id"],
            "zip_upload"
        )
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error_code": (error_details or {}).get("error_code", "PLAN_NOT_ELIGIBLE"),
                    "message": error_msg,
                    "feature": "zip_upload",
                    "upgrade_required": True,
                    **(error_details or {})
                }
            )
        
        # Verify file is a ZIP
        if not file.filename.lower().endswith('.zip'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File must be a ZIP archive (.zip)"
            )
        
        # Verify property belongs to client
        property_doc = await db.properties.find_one(
            {"property_id": property_id, "client_id": user["client_id"]},
            {"_id": 0}
        )
        
        if not property_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Property not found"
            )
        if property_doc.get("is_active") is False:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error_code": "PLAN_LIMIT",
                    "message": "This property is archived. Activate it from property settings or upgrade your plan to add documents.",
                },
            )
        
        # Get all requirements for this property
        requirements = await db.requirements.find(
            {"property_id": property_id, "client_id": user["client_id"]},
            {"_id": 0}
        ).to_list(100)
        from services.requirement_client_runtime_surface import filter_requirement_rows_for_client_runtime_surfaces

        requirements = await filter_requirement_rows_for_client_runtime_surfaces(
            db,
            client_id=user["client_id"],
            requirements=requirements,
            client_doc=await db.clients.find_one({"client_id": user["client_id"]}, {"_id": 0}) or {},
            properties=[property_doc],
        )
        
        # Save ZIP to temp location
        temp_dir = tempfile.mkdtemp()
        zip_path = os.path.join(temp_dir, file.filename)
        
        try:
            contents = await file.read()
            
            # Check file size (max 100MB)
            if len(contents) > 100 * 1024 * 1024:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="ZIP file too large. Maximum size is 100MB."
                )
            
            with open(zip_path, "wb") as f:
                f.write(contents)
            
            # Extract ZIP
            extract_dir = os.path.join(temp_dir, "extracted")
            os.makedirs(extract_dir, exist_ok=True)
            
            # Validate ZIP file
            if not zipfile.is_zipfile(zip_path):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid ZIP file"
                )
            
            results = []
            zip_authority_fanout_by_document_id: Dict[str, Dict[str, Any]] = {}
            supported_extensions = {'.pdf', '.jpg', '.jpeg', '.png', '.doc', '.docx'}

            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # Check for zip bomb (max 1000 files, max 500MB uncompressed)
                total_size = sum(info.file_size for info in zip_ref.infolist())
                if total_size > 500 * 1024 * 1024:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="ZIP contents too large. Maximum uncompressed size is 500MB."
                    )
                
                if len(zip_ref.namelist()) > 1000:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="ZIP contains too many files. Maximum is 1000 files."
                    )
                
                # Extract all files
                zip_ref.extractall(extract_dir)
            
            # Process each extracted file
            for root, dirs, files_list in os.walk(extract_dir):
                for filename in files_list:
                    # Skip hidden files and macOS metadata
                    if filename.startswith('.') or filename.startswith('__MACOSX'):
                        continue
                    
                    file_path = os.path.join(root, filename)
                    file_ext = os.path.splitext(filename)[1].lower()
                    
                    # Skip unsupported file types
                    if file_ext not in supported_extensions:
                        results.append({
                            "filename": filename,
                            "status": "skipped",
                            "reason": f"Unsupported file type: {file_ext}"
                        })
                        continue
                    
                    try:
                        # Create unique filename
                        unique_filename = f"{uuid.uuid4()}{file_ext}"
                        dest_path = DOCUMENT_STORAGE_PATH / user["client_id"] / unique_filename
                        dest_path.parent.mkdir(parents=True, exist_ok=True)
                        
                        # Copy file to document storage
                        shutil.copy2(file_path, dest_path)
                        
                        # Get file size
                        file_size = os.path.getsize(file_path)
                        stored_rel = f"{user['client_id']}/{unique_filename}"
                        
                        # Determine MIME type
                        mime_types = {
                            '.pdf': 'application/pdf',
                            '.jpg': 'image/jpeg',
                            '.jpeg': 'image/jpeg',
                            '.png': 'image/png',
                            '.doc': 'application/msword',
                            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
                        }
                        mime_type = mime_types.get(file_ext, 'application/octet-stream')
                        
                        # Create document record
                        document = Document(
                            client_id=user["client_id"],
                            property_id=property_id,
                            requirement_id=None,
                            file_name=filename,
                            file_path=stored_rel,
                            file_size=file_size,
                            mime_type=mime_type,
                            status=DocumentStatus.UPLOADED,
                            uploaded_by=user["portal_user_id"]
                        )
                        
                        doc = document.model_dump()
                        doc["uploaded_at"] = doc["uploaded_at"].isoformat()
                        apply_v2_defaults_to_new_upload(doc)
                        
                        await db.documents.insert_one(doc)
                        
                        matched_requirement = None
                        bulk_match_payload: Dict[str, Any] = {}
                        try:
                            from services.document_analysis import document_analysis_service

                            analysis_result = await document_analysis_service.analyze_document(
                                file_path=str(dest_path),
                                mime_type=mime_type,
                                document_id=document.document_id,
                                client_id=user["client_id"],
                                actor_id=user["portal_user_id"],
                            )

                            if analysis_result.get("success"):
                                extracted = analysis_result.get("extracted_data") or {}
                                best_ev: Optional[Dict[str, Any]] = None
                                best_req_id: Optional[str] = None
                                best_score = -1.0
                                from services.evidence_document_taxonomy import (
                                    MATCH_OUTCOME_MATCH_CONFIRMED,
                                    MATCH_OUTCOME_MATCH_LIKELY,
                                )

                                for req in requirements:
                                    ev = evaluate_document_requirement_match(
                                        requirement=req,
                                        filename=filename,
                                        user_declared_document_type=None,
                                        extracted_data=extracted,
                                        upload_route_context="zip_upload_post_analysis",
                                    )
                                    mo = str(ev.get("match_outcome") or "")
                                    if mo not in (MATCH_OUTCOME_MATCH_CONFIRMED, MATCH_OUTCOME_MATCH_LIKELY):
                                        continue
                                    if not ev.get("evidence_satisfies_requirement"):
                                        continue
                                    sc = float(ev.get("match_confidence") or 0.0)
                                    if sc > best_score:
                                        best_score = sc
                                        best_ev = ev
                                        best_req_id = str(req.get("requirement_id") or "")

                                if best_req_id and best_ev:
                                    matched_requirement = best_req_id
                                    bulk_match_payload = match_evaluation_to_persisted_document_fields(best_ev)
                                    bulk_match_payload["requirement_id"] = best_req_id
                                else:
                                    ev_unlinked = evaluate_document_requirement_match(
                                        requirement=None,
                                        filename=filename,
                                        user_declared_document_type=None,
                                        extracted_data=extracted,
                                        upload_route_context="zip_upload_post_analysis_unlinked",
                                    )
                                    bulk_match_payload = match_evaluation_to_persisted_document_fields(ev_unlinked)
                                    if ev_unlinked.get("manual_review_flag_suggested"):
                                        bulk_match_payload["manual_review_flag"] = True

                                if bulk_match_payload:
                                    await db.documents.update_one(
                                        {"document_id": document.document_id},
                                        {"$set": bulk_match_payload},
                                    )
                                if matched_requirement:
                                    await safe_upsert_document_upload_evidence_for_linked_document(
                                        db,
                                        client_id=user["client_id"],
                                        property_id=property_id,
                                        requirement_id=matched_requirement,
                                        document_id=document.document_id,
                                        actor_user_id=user.get("portal_user_id"),
                                        filename=filename,
                                        context="zip_upload",
                                    )
                                    tf_zip: Dict[str, Any] = {}
                                    await _document_path_sync_requirement_authority(
                                        db,
                                        matched_requirement,
                                        property_id=property_id,
                                        client_id=user["client_id"],
                                        correlation_base=f"DOC_UPLOADED:{document.document_id}",
                                        transition_origin="routes.documents.upload_zip_archive",
                                        transition_fanout=tf_zip,
                                        document_id=document.document_id,
                                        stale_document_transition_possible=True,
                                    )
                                    zip_authority_fanout_by_document_id[document.document_id] = tf_zip
                        except Exception as e:
                            logger.warning(f"AI analysis failed for {filename}: {e}")

                        results.append(
                            {
                                "filename": filename,
                                "document_id": document.document_id,
                                "status": "uploaded",
                                "matched_requirement": matched_requirement,
                                "ai_analyzed": matched_requirement is not None,
                                "evidence_match": bulk_match_payload or None,
                            }
                        )
                        
                    except Exception as e:
                        logger.error(f"Failed to process {filename}: {e}")
                        results.append({
                            "filename": filename,
                            "status": "failed",
                            "error": str(e)
                        })
            
            # Audit log
            await create_audit_log(
                action=AuditAction.DOCUMENT_UPLOADED,
                actor_id=user["portal_user_id"],
                client_id=user["client_id"],
                resource_type="zip_upload",
                metadata={
                    "property_id": property_id,
                    "zip_filename": file.filename,
                    "files_extracted": len(results),
                    "successful": sum(1 for r in results if r.get("status") == "uploaded"),
                    "auto_matched": sum(1 for r in results if r.get("matched_requirement")),
                    "skipped": sum(1 for r in results if r.get("status") == "skipped")
                }
            )
            
            from services.compliance_recalc_queue import TRIGGER_DOC_UPLOADED, ACTOR_CLIENT

            for r in results:
                if r.get("status") == "uploaded" and r.get("document_id"):
                    doc_id_z = str(r["document_id"])
                    await _document_path_enqueue_recalc(
                        zip_authority_fanout_by_document_id.get(doc_id_z),
                        property_id=property_id,
                        client_id=user["client_id"],
                        trigger_reason=TRIGGER_DOC_UPLOADED,
                        actor_type=ACTOR_CLIENT,
                        actor_id=user.get("portal_user_id"),
                        correlation_id=f"DOC_UPLOADED:{doc_id_z}",
                        trigger_origin="routes.documents.upload_zip_archive",
                        propagation_stage="post_zip_authority_sync",
                    )
                    try:
                        from services.score_events_service import write_score_event, EVENT_DOCUMENT_UPLOADED, ACTOR_ROLE_CLIENT
                        await write_score_event(
                            client_id=user["client_id"],
                            event_type=EVENT_DOCUMENT_UPLOADED,
                            actor_user_id=user.get("portal_user_id"),
                            actor_role=ACTOR_ROLE_CLIENT,
                            property_id=property_id,
                            requirement_id=r.get("matched_requirement"),
                            document_id=r["document_id"],
                            metadata={"filename": r.get("filename"), "zip": file.filename},
                        )
                    except Exception as ev_err:
                        logger.debug("Score event DOCUMENT_UPLOADED (zip) skip: %s", ev_err)

            top_pn_zip = _finalize_bulk_zip_results_propagation_notices(results, zip_authority_fanout_by_document_id)
            out_zip: Dict[str, Any] = {
                "message": f"Processed ZIP archive: {file.filename}",
                "results": results,
                "summary": {
                    "total_extracted": len(results),
                    "successful": sum(1 for r in results if r.get("status") == "uploaded"),
                    "failed": sum(1 for r in results if r.get("status") == "failed"),
                    "skipped": sum(1 for r in results if r.get("status") == "skipped"),
                    "auto_matched": sum(1 for r in results if r.get("matched_requirement")),
                },
            }
            if top_pn_zip:
                out_zip["propagation_notice"] = top_pn_zip
            return out_zip

        finally:
            # Clean up temp directory
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"ZIP upload error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process ZIP upload: {str(e)}"
        )


async def perform_client_document_upload(
    *,
    user: Dict[str, Any],
    file: UploadFile,
    property_id: str,
    requirement_id: Optional[str],
    work_order_id: Optional[str] = None,
    document_type: Optional[str] = None,
    notes: Optional[str] = None,
    source: Optional[str] = None,
    document_metadata: Optional[str] = None,
    evidence_scope_type: str = "PROPERTY",
) -> Dict[str, Any]:
    if str(evidence_scope_type or "PROPERTY").strip().upper() != "PROPERTY":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=structured_error(
                "EVIDENCE_SCOPE_NOT_SUPPORTED",
                "Only PROPERTY-scoped compliance evidence uploads are supported in client flows.",
            ),
        )

    """
    Persist a client compliance upload (shared by POST /api/documents/upload and requirement-scoped routes).
    Caller must enforce rate limits and authentication.
    """
    db = database.get_db()
    property_doc = await db.properties.find_one(
        {"property_id": property_id, "client_id": user["client_id"]},
        {"_id": 0},
    )

    if not property_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=structured_error(
                "PROPERTY_NOT_FOUND",
                "Property not found or not linked to your account.",
            ),
        )
    if property_doc.get("is_active") is False:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error_code": "PLAN_LIMIT",
                "message": "This property is archived. Activate it from property settings or upgrade your plan to add documents.",
            },
        )

    client_row = await db.clients.find_one(
        {"client_id": user["client_id"]},
        {"_id": 0, "default_jurisdiction": 1},
    ) or {}

    requirement = None
    rid = (requirement_id or "").strip()
    if rid:
        requirement = await db.requirements.find_one(
            {"requirement_id": rid, "client_id": user["client_id"]},
            {"_id": 0},
        )
        if not requirement:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Requirement not found",
            )
        from services.requirement_client_runtime_surface import requirement_row_eligible_on_client_runtime_surfaces

        if not await requirement_row_eligible_on_client_runtime_surfaces(
            db,
            client_id=user["client_id"],
            row=requirement,
            property_doc=property_doc,
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Requirement not found",
            )
        if (requirement.get("property_id") or "").strip() != (property_id or "").strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=structured_error(
                    "EVIDENCE_SCOPE_MISMATCH",
                    "Document property does not match the requirement's property; upload evidence for the correct property.",
                ),
            )
        requirement_id = rid
    else:
        requirement_id = None

    validated_wo = await _validate_optional_work_order_document_link(
        db,
        work_order_id=work_order_id,
        client_id=user["client_id"],
        property_id=property_id,
        requirement_id=requirement_id,
    )

    meta_dict = _parse_upload_document_metadata(document_metadata)

    document_validation: Optional[Dict[str, Any]] = None
    if requirement:
        from services.compliance_rules_registry import validate_document_upload_for_requirement

        document_validation = validate_document_upload_for_requirement(
            document_type,
            requirement,
            meta_dict,
            property_doc=property_doc,
            client_doc=client_row,
        )
        if not document_validation.get("valid"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=structured_error(
                    "DOCUMENT_VALIDATION_FAILED",
                    document_validation.get("reason") or "Document validation failed",
                    validation={
                        "valid": document_validation.get("valid"),
                        "reason": document_validation.get("reason"),
                        "jurisdiction": document_validation.get("jurisdiction"),
                        "scoring_jurisdiction": document_validation.get("scoring_jurisdiction"),
                        "portfolio_jurisdiction": document_validation.get("portfolio_jurisdiction"),
                        "missing_metadata_fields": document_validation.get("missing_metadata_fields") or [],
                    },
                ),
            )

    document_type_stored = document_type.strip() if isinstance(document_type, str) else None
    evidence_match_evaluation = evaluate_document_requirement_match(
        requirement=requirement,
        filename=file.filename or "",
        user_declared_document_type=document_type_stored,
        extracted_data=None,
        upload_route_context=(
            "client_upload_pre_analysis" if requirement else "client_upload_pre_analysis_no_requirement"
        ),
    )
    if requirement and evidence_match_evaluation.get("evidence_match_policy") == POLICY_BLOCK_UPLOAD:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=structured_error(
                "EVIDENCE_DOCUMENT_TYPE_MISMATCH",
                (evidence_match_evaluation.get("mismatch_reason_text") or "This file does not match the selected obligation."),
                evidence_match=evidence_match_evaluation,
            ),
        )

    file_extension = Path(file.filename).suffix
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    file_path = DOCUMENT_STORAGE_PATH / user["client_id"] / unique_filename
    file_path.parent.mkdir(parents=True, exist_ok=True)

    contents = await file.read()
    with open(file_path, "wb") as f:
        f.write(contents)

    stored_path = f"{user['client_id']}/{unique_filename}"

    validated_at_iso = datetime.now(timezone.utc).isoformat()
    validation_result_persist: Optional[Dict[str, Any]] = None
    if document_validation is not None:
        validation_result_persist = _build_validation_result_persist(
            document_validation,
            document_type_input=document_type_stored,
            validated_at_iso=validated_at_iso,
        )

    document = Document(
        client_id=user["client_id"],
        property_id=property_id,
        requirement_id=requirement_id,
        work_order_id=validated_wo,
        file_name=file.filename,
        file_path=stored_path,
        file_size=len(contents),
        mime_type=file.content_type or "application/octet-stream",
        status=DocumentStatus.UPLOADED,
        uploaded_by=user["portal_user_id"],
        document_type=document_type_stored,
        source=(source.strip() if isinstance(source, str) and source.strip() else None) or "portal",
        notes=notes.strip() if isinstance(notes, str) else None,
        document_metadata=meta_dict,
        validation_result=validation_result_persist,
    )

    source_stored = (source.strip() if isinstance(source, str) and source.strip() else None) or "portal"
    is_supporting_only_upload = source_stored == "supporting_evidence_attachment"

    doc = document.model_dump()
    doc["uploaded_at"] = doc["uploaded_at"].isoformat()
    doc.update(match_evaluation_to_persisted_document_fields(evidence_match_evaluation))
    if evidence_match_evaluation.get("manual_review_flag_suggested"):
        doc["manual_review_flag"] = True
    try:
        scope_payload = normalize_document_evidence_scope(
            property_id=property_id,
            client_id=user["client_id"],
            evidence_scope_type="PROPERTY",
        )
        doc.update(scope_payload)
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=structured_error("EVIDENCE_SCOPE_INVALID", str(ve)),
        ) from ve

    apply_v2_defaults_to_new_upload(doc)
    if is_supporting_only_upload:
        doc["source"] = source_stored
    from services.document_linkage_governance import (
        DocumentLinkageState,
        persist_fields_for_intentionally_unlinked,
        persist_fields_for_new_other_upload,
        persist_fields_for_upload_without_requirement,
    )

    if requirement_id:
        doc["document_linkage_state"] = DocumentLinkageState.LINKED.value
    elif document_type_stored == "Other":
        doc.update(persist_fields_for_new_other_upload())
    else:
        doc.update(persist_fields_for_upload_without_requirement())
    await db.documents.insert_one(doc)
    try:
        from services.workflow_timer_service import on_evidence_uploaded

        await on_evidence_uploaded(document.document_id, actor_id=user.get("portal_user_id"))
    except Exception as timer_exc:
        logger.warning("Workflow timer evidence_uploaded hook failed (non-fatal): %s", timer_exc)
    client_upload_fanout: Optional[Dict[str, Any]] = None
    if requirement_id and not is_supporting_only_upload:
        await safe_upsert_document_upload_evidence_for_linked_document(
            db,
            client_id=user["client_id"],
            property_id=property_id,
            requirement_id=requirement_id,
            document_id=document.document_id,
            actor_user_id=user.get("portal_user_id"),
            filename=file.filename,
            context="client_upload",
        )
        client_upload_fanout = {}
        await _document_path_sync_requirement_authority(
            db,
            requirement_id,
            property_id=property_id,
            client_id=user["client_id"],
            correlation_base=f"DOC_UPLOADED:{document.document_id}",
            transition_origin="routes.documents.perform_client_document_upload",
            transition_fanout=client_upload_fanout,
            document_id=document.document_id,
            stale_document_transition_possible=True,
        )

    asyncio.create_task(
        _run_analysis_after_upload(
            document_id=document.document_id,
            client_id=user["client_id"],
            actor_id=user.get("portal_user_id"),
            file_path=str(file_path),
            mime_type=file.content_type or "application/octet-stream",
        )
    )

    from services.provisioning import provisioning_service

    if not is_supporting_only_upload:
        await provisioning_service._update_property_compliance(property_id)
    from services.compliance_recalc_queue import TRIGGER_DOC_UPLOADED, ACTOR_CLIENT

    if not is_supporting_only_upload:
        await _document_path_enqueue_recalc(
            client_upload_fanout,
            property_id=property_id,
            client_id=user["client_id"],
            trigger_reason=TRIGGER_DOC_UPLOADED,
            actor_type=ACTOR_CLIENT,
            actor_id=user.get("portal_user_id"),
            correlation_id=f"DOC_UPLOADED:{document.document_id}",
            trigger_origin="routes.documents.perform_client_document_upload",
            propagation_stage="post_client_upload_authority_sync",
        )
    try:
        from services.score_events_service import write_score_event, EVENT_DOCUMENT_UPLOADED, ACTOR_ROLE_CLIENT

        await write_score_event(
            client_id=user["client_id"],
            event_type=EVENT_DOCUMENT_UPLOADED,
            actor_user_id=user.get("portal_user_id"),
            actor_role=ACTOR_ROLE_CLIENT,
            property_id=property_id,
            requirement_id=requirement_id,
            document_id=document.document_id,
            metadata={"filename": file.filename},
        )
    except Exception as ev_err:
        logger.debug("Score event DOCUMENT_UPLOADED skip: %s", ev_err)

    await create_audit_log(
        action=AuditAction.DOCUMENT_UPLOADED,
        actor_id=user["portal_user_id"],
        client_id=user["client_id"],
        resource_type="document",
        resource_id=document.document_id,
        metadata={
            "filename": file.filename,
            "requirement_id": requirement_id,
            "property_id": property_id,
        },
    )

    try:
        from services.analytics_service import log_event, log_first_doc_uploaded_once

        await log_event(
            "doc_uploaded",
            {"client_id": user["client_id"], "metadata": {"document_id": document.document_id, "property_id": property_id}},
        )
        await log_first_doc_uploaded_once(user["client_id"])
    except Exception:
        pass
    logger.info("Document uploaded: %s", document.document_id)
    outcome = None
    if not is_supporting_only_upload:
        try:
            from services.compliance_outcome_engine import (
                apply_action_outcome,
                EVENT_CERTIFICATE_UPLOADED,
            )

            outcome = await apply_action_outcome(
                {
                    "event_type": EVENT_CERTIFICATE_UPLOADED,
                    "client_id": user["client_id"],
                    "property_id": property_id,
                    "asset_id": None,
                    "requirement_type": (requirement or {}).get("requirement_type"),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "source_id": document.document_id,
                    "dedupe_key": f"{EVENT_CERTIFICATE_UPLOADED}:{document.document_id}",
                    "actor_id": user.get("portal_user_id"),
                    "actor_role": "CLIENT",
                    "metadata": {
                        "document_id": document.document_id,
                        "evidence_pending_user_confirmation": True,
                    },
                }
            )
        except Exception as outcome_err:
            logger.warning(
                "Action outcome skip for document upload: %s",
                outcome_err,
                extra=compliance_fanout_extra(
                    op="outcome_apply",
                    stage="failed",
                    client_id=str(user.get("client_id") or ""),
                    property_id=str(property_id or "") or None,
                    requirement_id=str(requirement_id) if requirement_id else None,
                    correlation_id=f"certificate_uploaded:{document.document_id}",
                    exc_type=type(outcome_err).__name__,
                ),
            )

    workflow_activation_observability: Optional[Dict[str, Any]] = None
    if requirement_id and client_upload_fanout is not None:
        doc_corr = f"DOC_UPLOADED:{document.document_id}"
        obligation_slice = _resolve_bound_document_upload_activation_obligation_slice(requirement)
        if obligation_slice is not None:
            workflow_activation_observability = _workflow_activation_observability_for_bounded_document_upload_slice(
                client_upload_fanout,
                obligation_slice=obligation_slice,
                document_upload_correlation_id=doc_corr,
            )

    out: Dict[str, Any] = {
        "message": (
            "Supporting file uploaded. Complete the requirement record to update compliance status."
            if is_supporting_only_upload
            else "Document uploaded successfully"
        ),
        "document_id": document.document_id,
        "outcome": outcome,
        "requirement_workflow_pending": bool(is_supporting_only_upload and requirement_id),
    }
    out["evidence_match"] = {
        "match_outcome": evidence_match_evaluation.get("match_outcome"),
        "match_confidence": evidence_match_evaluation.get("match_confidence"),
        "predicted_document_type": evidence_match_evaluation.get("predicted_document_type"),
        "mismatch_reason_code": evidence_match_evaluation.get("mismatch_reason_code"),
        "mismatch_reason_text": evidence_match_evaluation.get("mismatch_reason_text"),
        "user_messages": evidence_match_evaluation.get("user_messages") or [],
        "evidence_satisfies_requirement": evidence_match_evaluation.get("evidence_satisfies_requirement"),
    }
    if document_validation is not None:
        out["document_validation"] = {
            "valid": document_validation.get("valid"),
            "reason": document_validation.get("reason"),
            "jurisdiction": document_validation.get("jurisdiction"),
            "scoring_jurisdiction": document_validation.get("scoring_jurisdiction"),
            "portfolio_jurisdiction": document_validation.get("portfolio_jurisdiction"),
            "missing_metadata_fields": document_validation.get("missing_metadata_fields") or [],
        }
    out["document_metadata"] = meta_dict
    out["validation_result"] = validation_result_persist
    if workflow_activation_observability is not None:
        out["workflow_activation_observability"] = workflow_activation_observability
    if requirement_id and client_upload_fanout is not None:
        pn_client_upload = build_propagation_notice_from_transition_fanout(client_upload_fanout)
        if pn_client_upload:
            out["propagation_notice"] = pn_client_upload
    return out


@router.post("/upload")
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    property_id: str = Form(...),
    requirement_id: Optional[str] = Form(None),
    work_order_id: Optional[str] = Form(None),
    document_type: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    source: Optional[str] = Form(None),
    document_metadata: Optional[str] = Form(
        None,
        description='Optional JSON object for jurisdiction-aware checks, e.g. {"issue_date":"2024-06-01","engineer_id":"GAS123"}',
    ),
    evidence_scope_type: str = Form("PROPERTY"),
):
    """Upload a compliance document (client or admin). requirement_id optional for 'Other' docs (link later)."""
    user = await client_route_guard(request)
    await _enforce_document_upload_rate_limit(user["client_id"])

    try:
        return await perform_client_document_upload(
            user=user,
            file=file,
            property_id=property_id,
            requirement_id=requirement_id,
            work_order_id=work_order_id,
            document_type=document_type,
            notes=notes,
            source=source,
            document_metadata=document_metadata,
            evidence_scope_type=evidence_scope_type,
        )

    except HTTPException:
        raise
    except Exception as e:
        log_api_error(
            logger,
            endpoint="POST /api/documents/upload",
            error_type=type(e).__name__,
            message=str(e),
            user_id=user.get("portal_user_id"),
            exc=e,
            level=logging.ERROR,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=structured_error(
                "DOCUMENT_UPLOAD_FAILED",
                "We could not save your file. Check the file size and format, then try again.",
                retry_suggested=True,
            ),
        )


@router.post("/{document_id}/validate")
async def client_request_document_validation(request: Request, document_id: str):
    """
    Client requests review / validation of an uploaded document (audit trail only; does not approve).
    Sets manual_review_flag and client_validation_requested_at on the document row.
    """
    user = await client_route_guard(request)
    db = database.get_db()
    doc = await db.documents.find_one(
        {"document_id": document_id.strip(), "client_id": user["client_id"]},
        {"_id": 0, "document_id": 1},
    )
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    now = datetime.now(timezone.utc).isoformat()
    await db.documents.update_one(
        {"document_id": document_id.strip(), "client_id": user["client_id"]},
        {"$set": {"manual_review_flag": True, "client_validation_requested_at": now, "updated_at": now}},
    )
    await create_audit_log(
        action=AuditAction.DOCUMENT_VIEWED,
        actor_id=user.get("portal_user_id"),
        client_id=user["client_id"],
        resource_type="document",
        resource_id=document_id.strip(),
        metadata={"event": "client_validation_requested", "requested_at": now},
    )
    return {"ok": True, "document_id": document_id.strip(), "client_validation_requested_at": now}


@router.post("/admin/upload")
async def admin_upload_document(
    request: Request,
    file: UploadFile = File(...),
    client_id: str = Form(...),
    property_id: str = Form(...),
    requirement_id: str = Form(...),
    work_order_id: Optional[str] = Form(None),
    document_type: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    source: Optional[str] = Form(None),
):
    """Admin uploads document on behalf of client. Optional document_type, notes, source (default source=admin)."""
    user = await admin_route_guard(request)
    await _enforce_document_upload_rate_limit(client_id)
    db = database.get_db()
    
    try:
        # Verify property and requirement belong to client
        property_doc = await db.properties.find_one(
            {"property_id": property_id, "client_id": client_id},
            {"_id": 0}
        )
        
        if not property_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Property not found"
            )
        
        requirement = await db.requirements.find_one(
            {"requirement_id": requirement_id, "client_id": client_id},
            {"_id": 0}
        )
        
        if not requirement:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Requirement not found"
            )
        from services.requirement_client_runtime_surface import requirement_row_eligible_on_client_runtime_surfaces

        if not await requirement_row_eligible_on_client_runtime_surfaces(
            db,
            client_id=client_id,
            row=requirement,
            property_doc=property_doc,
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Requirement not found",
            )

        validated_wo = await _validate_optional_work_order_document_link(
            db,
            work_order_id=work_order_id,
            client_id=client_id,
            property_id=property_id,
            requirement_id=requirement_id,
        )

        document_type_stored = document_type.strip() if isinstance(document_type, str) else None
        admin_mev = evaluate_document_requirement_match(
            requirement=requirement,
            filename=file.filename or "",
            user_declared_document_type=document_type_stored,
            extracted_data=None,
            upload_route_context="admin_upload_pre_analysis",
        )
        if admin_mev.get("evidence_match_policy") == POLICY_BLOCK_UPLOAD:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=structured_error(
                    "EVIDENCE_DOCUMENT_TYPE_MISMATCH",
                    (admin_mev.get("mismatch_reason_text") or "This file does not match the selected obligation."),
                    evidence_match=admin_mev,
                ),
            )

        # Create unique filename
        file_extension = Path(file.filename).suffix
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        file_path = DOCUMENT_STORAGE_PATH / client_id / unique_filename
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save file
        contents = await file.read()
        with open(file_path, "wb") as f:
            f.write(contents)
        
        stored_path = f"{client_id}/{unique_filename}"
        # Create document record
        document = Document(
            client_id=client_id,
            property_id=property_id,
            requirement_id=requirement_id,
            work_order_id=validated_wo,
            file_name=file.filename,
            file_path=stored_path,
            file_size=len(contents),
            mime_type=file.content_type or "application/octet-stream",
            status=DocumentStatus.UPLOADED,
            uploaded_by=user["portal_user_id"],
            manual_review_flag=bool(admin_mev.get("manual_review_flag_suggested")),
            document_type=document_type_stored,
            source=(source.strip() if isinstance(source, str) and source.strip() else None) or "admin",
            notes=notes.strip() if isinstance(notes, str) else None,
        )
        
        doc = document.model_dump()
        doc["uploaded_at"] = doc["uploaded_at"].isoformat()
        doc.update(match_evaluation_to_persisted_document_fields(admin_mev))
        if admin_mev.get("manual_review_flag_suggested"):
            doc["manual_review_flag"] = True

        apply_v2_defaults_to_new_upload(doc)
        await db.documents.insert_one(doc)
        await safe_upsert_document_upload_evidence_for_linked_document(
            db,
            client_id=client_id,
            property_id=property_id,
            requirement_id=requirement_id,
            document_id=document.document_id,
            actor_user_id=user.get("portal_user_id"),
            filename=file.filename,
            context="admin_upload",
        )
        admin_upload_fanout: Dict[str, Any] = {}
        await _document_path_sync_requirement_authority(
            db,
            requirement_id,
            property_id=property_id,
            client_id=client_id,
            correlation_base=f"ADMIN_UPLOAD:{document.document_id}",
            transition_origin="routes.documents.admin_upload_document",
            transition_fanout=admin_upload_fanout,
            document_id=document.document_id,
            stale_document_transition_possible=True,
        )

        # Do not mark requirement as satisfied on upload; user/admin confirms via apply-extraction or modal
        from services.provisioning import provisioning_service
        await provisioning_service._update_property_compliance(property_id)
        from services.compliance_recalc_queue import TRIGGER_ADMIN_UPLOAD, ACTOR_ADMIN

        await _document_path_enqueue_recalc(
            admin_upload_fanout,
            property_id=property_id,
            client_id=client_id,
            trigger_reason=TRIGGER_ADMIN_UPLOAD,
            actor_type=ACTOR_ADMIN,
            actor_id=user.get("portal_user_id"),
            correlation_id=f"ADMIN_UPLOAD:{document.document_id}",
            trigger_origin="routes.documents.admin_upload_document",
            propagation_stage="post_admin_upload_authority_sync",
        )
        
        # Audit log
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_id=user["portal_user_id"],
            client_id=client_id,
            resource_type="document",
            resource_id=document.document_id,
            metadata={
                "action": "admin_document_upload",
                "filename": file.filename,
                "requirement_id": requirement_id,
                "property_id": property_id
            }
        )
        
        logger.info(f"Admin uploaded document for client {client_id}: {document.document_id}")
        try:
            from services.analytics_service import log_event, log_first_doc_uploaded_once
            await log_event("doc_uploaded", {"client_id": client_id, "metadata": {"document_id": document.document_id, "property_id": property_id, "admin_upload": True}})
            await log_first_doc_uploaded_once(client_id)
        except Exception:
            pass
        # Enqueue AI extraction (async; do not block or fail upload)
        try:
            from services.document_extraction_service import enqueue_extraction
            await enqueue_extraction(
                document_id=document.document_id,
                client_id=client_id,
                source="vault_upload",
                property_id=property_id,
            )
        except Exception as ext_err:
            logger.warning("Enqueue extraction after admin upload failed (non-blocking): %s", ext_err)

        out_admin_up: Dict[str, Any] = {
            "message": "Document uploaded successfully by admin",
            "document_id": document.document_id,
        }
        pn_adm_up = build_propagation_notice_from_transition_fanout(admin_upload_fanout)
        if pn_adm_up:
            out_admin_up["propagation_notice"] = pn_adm_up
        return out_admin_up

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin document upload error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload document"
        )


@router.get("/admin/extraction-queue")
async def admin_extraction_queue(
    request: Request,
    status_filter: Optional[str] = Query(None, description="Comma-separated: NEEDS_REVIEW, FAILED"),
    include_stale: bool = Query(True, description="Include stale queue rows (missing document)"),
):
    """Admin: list extractions for review (NEEDS_REVIEW, FAILED, STALE_QUEUE)."""
    await admin_route_guard(request)
    from services.extraction_queue_staleness import STALE_QUEUE_STATUS, enrich_extraction_queue_item

    db = database.get_db()
    statuses = ["NEEDS_REVIEW", "FAILED", STALE_QUEUE_STATUS]
    if status_filter:
        statuses = [s.strip() for s in status_filter.split(",") if s.strip()]
    cursor = db.extracted_documents.find(
        {"status": {"$in": statuses}},
        {"_id": 0, "extraction_id": 1, "document_id": 1, "client_id": 1, "file_name": 1, "status": 1, "extracted": 1, "errors": 1, "source": 1, "audit.updated_at": 1, "queue_stale": 1},
    ).sort("audit.updated_at", -1).limit(200)
    items = []
    async for row in cursor:
        enriched = await enrich_extraction_queue_item(db, row, auto_mark_stale=True)
        if not include_stale and enriched.get("queue_stale"):
            continue
        items.append({
            "extraction_id": enriched.get("extraction_id"),
            "document_id": enriched.get("document_id"),
            "client_id": enriched.get("client_id"),
            "file_name": enriched.get("file_name"),
            "status": enriched.get("status"),
            "extracted": enriched.get("extracted"),
            "errors": enriched.get("errors"),
            "source": enriched.get("source"),
            "updated_at": row.get("audit", {}).get("updated_at").isoformat() if row.get("audit", {}).get("updated_at") else None,
            "document_exists": enriched.get("document_exists"),
            "queue_stale": enriched.get("queue_stale"),
            "queue_actionable": enriched.get("queue_actionable"),
        })
    return {"items": items}


class AdminExtractionConfirmBody(BaseModel):
    document_id: str


class AdminExtractionRejectBody(BaseModel):
    document_id: str
    reason: Optional[str] = None


@router.post("/admin/extraction-queue/confirm")
async def admin_confirm_extraction(request: Request, body: AdminExtractionConfirmBody):
    """Admin: apply extraction for a document (sets CONFIRMED, updates requirement)."""
    await admin_route_guard(request)
    db = database.get_db()
    document_id = body.document_id
    document = await db.documents.find_one({"document_id": document_id}, {"_id": 0})
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    extraction_id = document.get("extraction_id")
    if not extraction_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No extraction record for this document")
    rec = await db.extracted_documents.find_one({"extraction_id": extraction_id}, {"_id": 0, "status": 1, "extracted": 1})
    if not rec or rec.get("status") not in ("EXTRACTED", "NEEDS_REVIEW"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Extraction not in a state that can be applied")
    ext = rec.get("extracted") or {}
    data = {
        "expiry_date": ext.get("expiry_date"),
        "issue_date": ext.get("issue_date"),
        "certificate_number": ext.get("certificate_number"),
        "document_type": ext.get("doc_type"),
        "engineer_details": {"name": ext.get("inspector_company") or ext.get("inspector_id"), "company_name": ext.get("inspector_company")},
    }
    requirement_id = document.get("requirement_id")
    extraction_fanout_for_notice: Optional[Dict[str, Any]] = None
    if requirement_id and data.get("expiry_date"):
        try:
            expiry_dt = _normalize_and_parse_date(data["expiry_date"])
            now = datetime.now(timezone.utc)
            update_fields = {
                "due_date": expiry_dt.isoformat(),
                "extracted_expiry_date": expiry_dt.isoformat(),
                "expiry_source": "EXTRACTED",
                "updated_at": now.isoformat(),
            }
            if expiry_dt < now:
                update_fields["status"] = "OVERDUE"
            elif expiry_dt < now + timedelta(days=30):
                update_fields["status"] = "EXPIRING_SOON"
            else:
                update_fields["status"] = "COMPLIANT"
            conf = (data.get("confidence_scores") or {}).get("overall") if isinstance(data.get("confidence_scores"), dict) else data.get("confidence")
            if conf is not None:
                try:
                    update_fields["extraction_confidence"] = float(conf)
                except (TypeError, ValueError):
                    pass
            await db.requirements.update_one({"requirement_id": requirement_id}, {"$set": update_fields})
            extraction_fanout_for_notice = {}
            await _document_path_sync_requirement_authority(
                db,
                requirement_id,
                property_id=str(document.get("property_id") or "") or None,
                client_id=str(document.get("client_id") or ""),
                correlation_base=f"ADMIN_EXTRACTION_CONFIRM:{document_id}",
                transition_origin="routes.documents.admin_confirm_extraction",
                transition_fanout=extraction_fanout_for_notice,
                document_id=document_id,
                stale_document_transition_possible=True,
            )
        except ValueError:
            extraction_fanout_for_notice = None
    now = datetime.now(timezone.utc)
    await db.extracted_documents.update_one(
        {"extraction_id": extraction_id},
        {"$set": {"status": "CONFIRMED", "audit.updated_at": now}}
    )
    await db.documents.update_one(
        {"document_id": document_id},
        {"$set": {"extraction_status": "CONFIRMED", "ai_extraction.review_status": "approved", "ai_extraction.applied_data": data, "ai_extracted_data": data}}
    )
    await create_audit_log(
        action=AuditAction.AI_EXTRACTION_APPLIED,
        actor_id=None,
        client_id=document["client_id"],
        resource_type="document",
        resource_id=document_id,
        metadata={"admin_confirm": True, "extraction_id": extraction_id},
    )
    out_confirm_ext: Dict[str, Any] = {"message": "Extraction applied", "document_id": document_id}
    if extraction_fanout_for_notice is not None:
        pn_ext_conf = build_propagation_notice_from_transition_fanout(extraction_fanout_for_notice)
        if pn_ext_conf:
            out_confirm_ext["propagation_notice"] = pn_ext_conf
    return out_confirm_ext


@router.post("/admin/extraction-queue/reject")
async def admin_reject_extraction(request: Request, body: AdminExtractionRejectBody):
    """Admin: reject extraction (sets REJECTED, no requirement change)."""
    await admin_route_guard(request)
    db = database.get_db()
    document_id = body.document_id
    document = await db.documents.find_one({"document_id": document_id}, {"_id": 0, "client_id": 1, "extraction_id": 1})
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    extraction_id = document.get("extraction_id")
    if extraction_id:
        now = datetime.now(timezone.utc)
    await db.extracted_documents.update_one(
        {"extraction_id": extraction_id},
        {"$set": {"status": "REJECTED", "audit.updated_at": now}}
    )
    await db.documents.update_one(
        {"document_id": document_id},
        {"$set": {"extraction_status": "REJECTED", "ai_extraction.review_status": "rejected", "ai_extraction.rejection_reason": body.reason or "Admin rejected"}}
    )
    reject_touch_fanout: Dict[str, Any] = {}
    await sync_for_documents_touching(
        db,
        document_id=document_id,
        transition_fanout_out=reject_touch_fanout,
        correlation_base=f"DOC_TOUCH_REJECT:{document_id}",
        transition_origin=transition_origin_document_touch("admin_extraction_reject"),
    )
    await create_audit_log(
        action=AuditAction.DOCUMENT_AI_ANALYZED,
        actor_id=None,
        client_id=document["client_id"],
        resource_type="document",
        resource_id=document_id,
        metadata={"action": "extraction_rejected", "reason": body.reason, "admin_reject": True},
    )
    out_reject_ext: Dict[str, Any] = {"message": "Extraction rejected", "document_id": document_id}
    pn_ext_rej = build_propagation_notice_from_transition_fanout(reject_touch_fanout)
    if pn_ext_rej:
        out_reject_ext["propagation_notice"] = pn_ext_rej
    return out_reject_ext


@router.post("/verify/{document_id}")
async def verify_document(
    request: Request,
    document_id: str,
    body: VerifyDocumentBody = Body(default_factory=VerifyDocumentBody),
):
    """Admin verifies a document."""
    user = await admin_route_guard(request)
    db = database.get_db()
    
    try:
        document = await db.documents.find_one({"document_id": document_id}, {"_id": 0})
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )

        if document.get("requirement_id") and document_blocks_verified_satisfaction(document):
            if not body.evidence_mismatch_override:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=structured_error(
                        "EVIDENCE_MATCH_VERIFICATION_BLOCKED",
                        "This document failed automated evidence matching against the linked obligation. "
                        "Use override only after manual review, or relink / reject instead.",
                        evidence_match={
                            "match_outcome": document.get("match_outcome"),
                            "predicted_document_type": document.get("predicted_document_type"),
                            "mismatch_reason_code": document.get("mismatch_reason_code"),
                            "mismatch_reason_text": document.get("mismatch_reason_text"),
                        },
                    ),
                )
            now_iso = datetime.now(timezone.utc).isoformat()
            await db.documents.update_one(
                {"document_id": document_id},
                {
                    "$set": {
                        "reviewed_match_outcome": MATCH_OUTCOME_MATCH_CONFIRMED,
                        "reviewed_match_actor_id": user.get("portal_user_id"),
                        "reviewed_match_at": now_iso,
                        "evidence_satisfies_requirement": True,
                        "match_outcome": MATCH_OUTCOME_MATCH_CONFIRMED,
                        "requirement_evidence_mismatch": False,
                        "requirement_evidence_mismatch_reason": None,
                    }
                },
            )
            document = await db.documents.find_one({"document_id": document_id}, {"_id": 0}) or document
            await create_audit_log(
                action=AuditAction.ADMIN_ACTION,
                actor_id=user.get("portal_user_id"),
                client_id=document.get("client_id"),
                resource_type="document",
                resource_id=document_id,
                metadata={
                    "action_type": "EVIDENCE_MATCH_OVERRIDE_VERIFY",
                    "reason": (body.evidence_mismatch_override_reason or "")[:2000] if body else None,
                },
            )
        
        old_status = document["status"]

        from services.evidence_review_config import is_feature_evidence_review_v2

        if is_feature_evidence_review_v2():
            from services.evidence_review_verify import execute_verify_document_v2

            return await execute_verify_document_v2(
                db,
                document_id=document_id,
                document=document,
                user=user,
                old_status=old_status,
                validation_override_reason=body.validation_override_reason if body else None,
            )
        
        # Update document status
        await db.documents.update_one(
            {"document_id": document_id},
            {"$set": {"status": DocumentStatus.VERIFIED.value}}
        )

        from services.evidence_extraction_supersession import (
            ADMIN_DECISION_ACCEPTED,
            supersede_extraction_confirmation_for_admin_decision,
        )

        await supersede_extraction_confirmation_for_admin_decision(
            db,
            document_id=document_id,
            decision=ADMIN_DECISION_ACCEPTED,
            actor_id=user.get("portal_user_id"),
        )
        
        # Update requirement status to COMPLIANT when linked
        verify_v1_fanout: Optional[Dict[str, Any]] = None
        if document.get("requirement_id"):
            await db.requirements.update_one(
                {"requirement_id": document["requirement_id"]},
                {
                    "$set": {
                        "status": RequirementStatus.COMPLIANT.value,
                        "date_source": "VERIFIED_DOCUMENT",
                        "evidence_state": "VERIFIED",
                        "confidence_state": "VERIFIED",
                        "compliance_state": "VALID",
                    }
                },
            )
            verify_v1_fanout = {}
            merge_pre_authority_optimistic_requirement_promotion_marker(
                verify_v1_fanout,
                applied=True,
                basis="VERIFIED_DOCUMENT_COMPLIANT_PROMOTION",
                transition_origin="routes.documents.verify_document",
                requirement_id=str(document["requirement_id"]),
            )
            await _document_path_sync_requirement_authority(
                db,
                str(document["requirement_id"]),
                property_id=str(document.get("property_id") or "") or None,
                client_id=str(document.get("client_id") or ""),
                correlation_base=f"DOC_STATUS_CHANGED:{document_id}:VERIFIED",
                transition_origin="routes.documents.verify_document",
                transition_fanout=verify_v1_fanout,
                document_id=document_id,
                verification_replay_possible=_document_verification_replay_heuristic(old_status),
                stale_document_transition_possible=True,
            )
            try:
                await _finalize_active_compliance_jobs_after_certificate_verified(
                    db,
                    client_id=str(document.get("client_id") or ""),
                    requirement_id=str(document["requirement_id"]),
                    document_id=document_id,
                    actor_id=user.get("portal_user_id"),
                )
            except Exception as fin_e:
                logger.warning("Active compliance job finalize on verify skipped: %s", fin_e)

        # Recompute property compliance (skip for client-level docs with no property_id)
        if document.get("property_id"):
            from services.provisioning import provisioning_service
            await provisioning_service._update_property_compliance(document["property_id"])
            from services.compliance_recalc_queue import TRIGGER_DOC_STATUS_CHANGED, ACTOR_ADMIN

            await _document_path_enqueue_recalc(
                verify_v1_fanout,
                property_id=document["property_id"],
                client_id=document["client_id"],
                trigger_reason=TRIGGER_DOC_STATUS_CHANGED,
                actor_type=ACTOR_ADMIN,
                actor_id=user.get("portal_user_id"),
                correlation_id=f"DOC_STATUS_CHANGED:{document_id}:VERIFIED",
                trigger_origin="routes.documents.verify_document",
                propagation_stage="post_verify_v1_authority_sync",
            )

        # Audit log
        verify_audit_meta = {}
        if document.get("work_order_id"):
            verify_audit_meta["work_order_id"] = document["work_order_id"]
        if document.get("requirement_id"):
            verify_audit_meta["pre_authority_optimistic_requirement_promotion"] = True
            verify_audit_meta["optimistic_promotion_basis"] = "VERIFIED_DOCUMENT_COMPLIANT_PROMOTION"
        await create_audit_log(
            action=AuditAction.DOCUMENT_VERIFIED,
            actor_id=user["portal_user_id"],
            client_id=document["client_id"],
            resource_type="document",
            resource_id=document_id,
            before_state={"status": old_status},
            after_state={"status": DocumentStatus.VERIFIED.value},
            metadata=verify_audit_meta or None,
        )
        
        # Enablement event
        try:
            from services.enablement_service import emit_enablement_event
            from models.enablement import EnablementEventType
            
            # Get property address for context (client-level docs may have property_id None)
            property_id = document.get("property_id")
            property_doc = await db.properties.find_one(
                {"property_id": property_id},
                {"_id": 0, "address": 1}
            ) if property_id else None
            property_address = property_doc.get("address", {}).get("line1", "") if property_doc else ""

            await emit_enablement_event(
                event_type=EnablementEventType.DOCUMENT_VERIFIED,
                client_id=document["client_id"],
                document_id=document_id,
                property_id=property_id,
                context_payload={
                    "document_name": document.get("document_name", document.get("requirement_name", "Document")),
                    "property_address": property_address,
                    "expiry_date": document.get("expiry_date", "N/A")
                }
            )
        except Exception as enable_err:
            logger.warning(f"Failed to emit enablement event: {enable_err}")

        if document.get("requirement_id"):
            try:
                from services.compliance_evidence_record_service import (
                    align_linked_document_upload_cer_on_document_verified,
                )

                await align_linked_document_upload_cer_on_document_verified(
                    db,
                    client_id=str(document.get("client_id") or ""),
                    requirement_id=str(document["requirement_id"]),
                    document_id=document_id,
                    actor_user_id=str(user.get("portal_user_id") or ""),
                )
            except Exception as cer_align_err:
                logger.warning(
                    "Linked DOCUMENT_UPLOAD CER alignment on verify skipped document_id=%s: %s",
                    document_id,
                    cer_align_err,
                )

        req_type_for_outcome = None
        if document.get("requirement_id"):
            rrow = await db.requirements.find_one(
                {"requirement_id": document["requirement_id"]},
                {"_id": 0, "requirement_type": 1, "requirement_code": 1},
            )
            if rrow:
                req_type_for_outcome = (
                    (rrow.get("requirement_code") or rrow.get("requirement_type") or "").strip() or None
                )

        outcome = None
        try:
            if document.get("property_id"):
                from services.compliance_outcome_engine import apply_action_outcome, EVENT_CERTIFICATE_VERIFIED

                meta = {
                    "document_id": document_id,
                    "requirement_id": document.get("requirement_id"),
                }
                woid = (document.get("work_order_id") or "").strip()
                if woid:
                    meta["work_order_id"] = woid
                outcome = await apply_action_outcome(
                    {
                        "event_type": EVENT_CERTIFICATE_VERIFIED,
                        "client_id": document["client_id"],
                        "property_id": document.get("property_id"),
                        "asset_id": None,
                        "requirement_type": req_type_for_outcome,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "source_id": document_id,
                        "dedupe_key": f"{EVENT_CERTIFICATE_VERIFIED}:{document_id}",
                        "actor_id": user.get("portal_user_id"),
                        "actor_role": "ADMIN",
                        "metadata": meta,
                    }
                )
        except Exception as outcome_err:
            logger.warning(
                "Action outcome certificate_verified skip: %s",
                outcome_err,
                extra=compliance_fanout_extra(
                    op="outcome_apply",
                    stage="failed",
                    client_id=str(document.get("client_id") or ""),
                    property_id=str(document.get("property_id") or "") or None,
                    requirement_id=str(document.get("requirement_id") or "") or None,
                    correlation_id=f"certificate_verified:{document_id}",
                    exc_type=type(outcome_err).__name__,
                ),
            )

        try:
            await _append_document_evidence_to_work_order(document_id, document.get("work_order_id"))
        except Exception as ev_err:
            logger.debug("Evidence append to work order skip: %s", ev_err)

        try:
            await _set_compliance_work_order_proof_verified(db, document.get("work_order_id"))
        except Exception as proof_err:
            logger.warning("Could not set compliance work order proof verified: %s", proof_err)

        out: Dict[str, Any] = {"message": "Document verified", "outcome": outcome}
        notice = build_propagation_notice_from_transition_fanout(
            verify_v1_fanout if document.get("requirement_id") else None
        )
        if notice:
            out["propagation_notice"] = notice
        return out
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Document verification error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify document"
        )

@router.post("/reject/{document_id}")
async def reject_document(request: Request, document_id: str, reason: str = Form(...)):
    """Admin rejects a document."""
    user = await admin_route_guard(request)
    db = database.get_db()
    
    try:
        document = await db.documents.find_one({"document_id": document_id}, {"_id": 0})
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        
        old_status = document["status"]
        
        # Update document status
        await db.documents.update_one(
            {"document_id": document_id},
            {"$set": {"status": DocumentStatus.REJECTED.value}}
        )

        from services.evidence_extraction_supersession import (
            ADMIN_DECISION_REJECTED,
            supersede_extraction_confirmation_for_admin_decision,
        )

        await supersede_extraction_confirmation_for_admin_decision(
            db,
            document_id=document_id,
            decision=ADMIN_DECISION_REJECTED,
            actor_id=user.get("portal_user_id"),
        )
        
        reject_fanout: Dict[str, Any] = {}
        # If this was the only verified doc for the requirement, revert requirement and sync property
        if document.get("requirement_id"):
            await _revert_requirement_if_no_verified_docs(
                db,
                str(document["requirement_id"]),
                document.get("property_id"),
                document_id=document_id,
                transition_observability_out=reject_fanout,
                correlation_base=f"DOC_STATUS_CHANGED:{document_id}:REJECTED",
                transition_origin="routes.documents.reject_document",
                client_id=str(document.get("client_id") or ""),
            )
        property_id = document.get("property_id")
        if property_id:
            from services.compliance_recalc_queue import TRIGGER_DOC_STATUS_CHANGED, ACTOR_ADMIN

            await _document_path_enqueue_recalc(
                reject_fanout if reject_fanout.get("transition_id") else None,
                property_id=property_id,
                client_id=document["client_id"],
                trigger_reason=TRIGGER_DOC_STATUS_CHANGED,
                actor_type=ACTOR_ADMIN,
                actor_id=user.get("portal_user_id"),
                correlation_id=f"DOC_STATUS_CHANGED:{document_id}:REJECTED",
                trigger_origin="routes.documents.reject_document",
                propagation_stage="post_reject_revert_authority_sync",
            )
        
        # Audit log
        await create_audit_log(
            action=AuditAction.DOCUMENT_REJECTED,
            actor_id=user["portal_user_id"],
            client_id=document["client_id"],
            resource_type="document",
            resource_id=document_id,
            before_state={"status": old_status},
            after_state={"status": DocumentStatus.REJECTED.value},
            metadata={"reason": reason}
        )

        try:
            await _reconcile_compliance_work_order_proof_after_document_removed(
                db, document_id, document.get("work_order_id")
            )
        except Exception as wo_proof_err:
            logger.warning("Compliance WO proof reconcile on document reject failed: %s", wo_proof_err)

        out_reject_doc: Dict[str, Any] = {"message": "Document rejected"}
        pn_rej_adm = build_propagation_notice_from_transition_fanout(reject_fanout)
        if pn_rej_adm:
            out_reject_doc["propagation_notice"] = pn_rej_adm
        return out_reject_doc

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Document rejection error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reject document"
        )


@router.delete("/{document_id}")
async def delete_document(request: Request, document_id: str):
    """Client deletes own document. Requirement reverted to PENDING if no other VERIFIED doc; property compliance synced."""
    user = await client_route_guard(request)
    db = database.get_db()
    try:
        document = await db.documents.find_one({"document_id": document_id}, {"_id": 0})
        if not document:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
        if document["client_id"] != user["client_id"]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to delete this document")
        requirement_id = document.get("requirement_id")
        property_id = document.get("property_id")
        try:
            await _reconcile_compliance_work_order_proof_after_document_removed(
                db, document_id, document.get("work_order_id")
            )
        except Exception as wo_proof_err:
            logger.warning("Compliance WO proof reconcile on client delete failed: %s", wo_proof_err)
        await db.documents.delete_one({"document_id": document_id})
        delete_fanout: Dict[str, Any] = {}
        if requirement_id:
            await _revert_requirement_if_no_verified_docs(
                db,
                requirement_id,
                property_id,
                document_id=document_id,
                transition_observability_out=delete_fanout,
                correlation_base=f"DOC_DELETED:{document_id}",
                transition_origin="routes.documents.delete_document",
                client_id=str(user.get("client_id") or ""),
            )
        if property_id:
            from services.compliance_recalc_queue import TRIGGER_DOC_DELETED, ACTOR_CLIENT

            await _document_path_enqueue_recalc(
                delete_fanout if delete_fanout.get("transition_id") else None,
                property_id=property_id,
                client_id=user["client_id"],
                trigger_reason=TRIGGER_DOC_DELETED,
                actor_type=ACTOR_CLIENT,
                actor_id=user.get("portal_user_id"),
                correlation_id=f"DOC_DELETED:{document_id}",
                trigger_origin="routes.documents.delete_document",
                propagation_stage="post_client_delete_revert_authority_sync",
            )
        try:
            fp = document.get("file_path", "")
            if fp:
                p = Path(fp)
                if not p.is_absolute():
                    p = (DOCUMENT_STORAGE_PATH / p).resolve()
                if p.is_file():
                    p.unlink(missing_ok=True)
        except Exception as file_err:
            logger.warning(f"Could not remove file for document {document_id}: {file_err}")
        await create_audit_log(
            action=AuditAction.DOCUMENT_DELETED_BY_CLIENT,
            actor_id=user["portal_user_id"],
            client_id=user["client_id"],
            resource_type="document",
            resource_id=document_id,
            metadata={"action": "document_deleted", "file_name": document.get("file_name")},
        )
        out_delete_client: Dict[str, Any] = {"message": "Document deleted"}
        pn_del_c = build_propagation_notice_from_transition_fanout(delete_fanout)
        if pn_del_c:
            out_delete_client["propagation_notice"] = pn_del_c
        return out_delete_client
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Document delete error: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete document")


@router.delete("/admin/{document_id}")
async def admin_delete_document(
    request: Request,
    document_id: str,
    reason: str = Query(..., min_length=10, max_length=2000),
):
    """Admin deletes a document on behalf of any client. Requirement reverted if no other VERIFIED doc; property compliance synced."""
    user = await admin_route_guard(request)
    from services.admin_action_governance import (
        enforce_governed_admin_action,
        normalized_admin_action_metadata,
    )

    support_reason = await enforce_governed_admin_action(
        request,
        user,
        "delete_admin_document",
        reason=reason,
        resource_key=document_id,
    )
    db = database.get_db()
    try:
        document = await db.documents.find_one({"document_id": document_id}, {"_id": 0})
        if not document:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
        requirement_id = document.get("requirement_id")
        property_id = document.get("property_id")
        client_id = document["client_id"]
        try:
            await _reconcile_compliance_work_order_proof_after_document_removed(
                db, document_id, document.get("work_order_id")
            )
        except Exception as wo_proof_err:
            logger.warning("Compliance WO proof reconcile on admin delete failed: %s", wo_proof_err)
        await db.documents.delete_one({"document_id": document_id})
        admin_delete_fanout: Dict[str, Any] = {}
        if requirement_id:
            await _revert_requirement_if_no_verified_docs(
                db,
                requirement_id,
                property_id,
                document_id=document_id,
                transition_observability_out=admin_delete_fanout,
                correlation_base=f"ADMIN_DELETE:{document_id}",
                transition_origin="routes.documents.admin_delete_document",
                client_id=str(client_id),
            )
        if property_id:
            from services.compliance_recalc_queue import TRIGGER_ADMIN_DELETE, ACTOR_ADMIN

            await _document_path_enqueue_recalc(
                admin_delete_fanout if admin_delete_fanout.get("transition_id") else None,
                property_id=property_id,
                client_id=client_id,
                trigger_reason=TRIGGER_ADMIN_DELETE,
                actor_type=ACTOR_ADMIN,
                actor_id=user.get("portal_user_id"),
                correlation_id=f"ADMIN_DELETE:{document_id}",
                trigger_origin="routes.documents.admin_delete_document",
                propagation_stage="post_admin_delete_revert_authority_sync",
            )
        try:
            fp = document.get("file_path", "")
            if fp:
                p = Path(fp)
                if not p.is_absolute():
                    p = (DOCUMENT_STORAGE_PATH / p).resolve()
                if p.is_file():
                    p.unlink(missing_ok=True)
        except Exception as file_err:
            logger.warning(f"Could not remove file for document {document_id}: {file_err}")
        await create_audit_log(
            action=AuditAction.DOCUMENT_DELETED_BY_ADMIN,
            actor_id=user["portal_user_id"],
            client_id=client_id,
            resource_type="document",
            resource_id=document_id,
            metadata={
                "action": "admin_document_deleted",
                "action_type": "ADMIN_DOCUMENT_DELETED",
                "file_name": document.get("file_name"),
                **normalized_admin_action_metadata("delete_admin_document", support_reason),
            },
        )
        out_admin_del: Dict[str, Any] = {"message": "Document deleted"}
        pn_adm_del = build_propagation_notice_from_transition_fanout(admin_delete_fanout)
        if pn_adm_del:
            out_admin_del["propagation_notice"] = pn_adm_del
        return out_admin_del
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin document delete error: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete document")


async def _revert_requirement_if_no_verified_docs(
    db,
    requirement_id: str,
    property_id: Optional[str],
    *,
    document_id: Optional[str] = None,
    transition_observability_out: Optional[Dict[str, Any]] = None,
    correlation_base: Optional[str] = None,
    transition_origin: str = "routes.documents._revert_requirement_if_no_verified_docs",
    client_id: Optional[str] = None,
) -> None:
    """If no VERIFIED document remains for this requirement, set requirement to PENDING, restore a baseline estimated due date, and sync property compliance.
    Avoids presenting a stale certificate date as fact while keeping reminders useful."""
    resolved_client_id = (client_id or "").strip()
    if transition_observability_out is not None and not resolved_client_id:
        fq: Dict[str, Any] = {"requirement_id": requirement_id}
        if property_id:
            fq["property_id"] = property_id
        req_lookup = await db.requirements.find_one(fq, {"_id": 0, "client_id": 1})
        resolved_client_id = str((req_lookup or {}).get("client_id") or "")

    cor_base = (correlation_base or "").strip() or f"REQ_REVERT_SYNC:{requirement_id}"

    async def _sync_authority_after_revert_state() -> None:
        if transition_observability_out is not None and resolved_client_id:
            cid = ensure_requirement_transition_correlation_id(
                requirement_id=str(requirement_id),
                property_id=property_id,
                client_id=resolved_client_id,
                correlation_id=cor_base,
            )
            await sync_requirement_evidence_authority(
                db,
                requirement_id,
                property_id_hint=property_id,
                correlation_id=cid,
                transition_origin=transition_origin,
                transition_observability_out=transition_observability_out,
            )
            if document_id:
                merge_document_path_lineage_flags(
                    transition_observability_out,
                    document_id=document_id,
                    revert_retrigger_possible=True,
                    stale_document_transition_possible=True,
                )
        else:
            await sync_requirement_evidence_authority(db, requirement_id, property_id_hint=property_id)

    remaining = await db.documents.count_documents(
        {"requirement_id": requirement_id, "status": DocumentStatus.VERIFIED.value}
    )
    if remaining > 0:
        await _sync_authority_after_revert_state()
        return
    filter_query = {"requirement_id": requirement_id}
    if property_id:
        filter_query["property_id"] = property_id
    req_row = await db.requirements.find_one(filter_query, {"_id": 0, "frequency_days": 1})
    freq = int((req_row or {}).get("frequency_days") or 365)
    baseline_days = 30 if freq <= 0 else min(30, max(1, freq))
    new_due = datetime.now(timezone.utc) + timedelta(days=baseline_days)
    await db.requirements.update_one(
        filter_query,
        {
            "$set": {
                "status": RequirementStatus.PENDING.value,
                "due_date": new_due.isoformat(),
                "date_source": "SYSTEM_ESTIMATED",
                "evidence_state": "MISSING",
                "confidence_state": "ESTIMATED",
                "expiry_source": "NONE",
            },
            "$unset": {"extracted_expiry_date": "", "confirmed_expiry_date": ""},
        },
    )
    await _sync_authority_after_revert_state()
    if property_id:
        from services.provisioning import provisioning_service

        await provisioning_service._update_property_compliance(property_id)


async def regenerate_requirement_due_date(requirement_id: str, client_id: str):
    """Regenerate requirement due date after document upload."""
    db = database.get_db()
    
    requirement = await db.requirements.find_one(
        {"requirement_id": requirement_id},
        {"_id": 0}
    )
    
    if requirement:
        # Calculate new due date based on frequency
        new_due_date = datetime.now(timezone.utc) + timedelta(days=requirement["frequency_days"])
        
        await db.requirements.update_one(
            {"requirement_id": requirement_id},
            {
                "$set": {
                    "status": RequirementStatus.COMPLIANT.value,
                    "due_date": new_due_date.isoformat()
                }
            }
        )
        
        # Audit log
        await create_audit_log(
            action=AuditAction.REQUIREMENTS_EVALUATED,
            client_id=client_id,
            resource_type="requirement",
            resource_id=requirement_id,
            metadata={
                "action": "regenerate_due_date",
                "new_due_date": new_due_date.isoformat()
            }
        )


@router.post("/analyze/{document_id}")
async def analyze_document_ai(
    request: Request,
    document_id: str,
    return_advanced: bool = False,
):
    """Analyze a document using AI to extract metadata.
    
    - Basic extraction (all plans): document_type, issue_date, expiry_date.
    - Advanced extraction (Professional only): confidence scoring, Review & Apply UI.
    If return_advanced=True and client is not entitled to ai_extraction_advanced, returns 403.
    """
    user = await client_route_guard(request)
    db = database.get_db()
    from services.plan_registry import plan_registry

    try:
        # Get document
        document = await db.documents.find_one(
            {"document_id": document_id},
            {"_id": 0}
        )
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        if user.get("role") != "ROLE_ADMIN" and document["client_id"] != user["client_id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to analyze this document"
            )
        client_id = document["client_id"]

        # Hard gate: requesting advanced response without entitlement -> 403 (no silent downgrade)
        if return_advanced:
            allowed, error_msg, error_details = await plan_registry.enforce_feature(
                client_id, "ai_extraction_advanced"
            )
            if not allowed:
                await create_audit_log(
                    action=AuditAction.ADMIN_ACTION,
                    actor_id=user.get("portal_user_id"),
                    client_id=client_id,
                    metadata={
                        "action_type": "PLAN_GATE_DENIED",
                        "feature_key": "ai_extraction_advanced",
                        "endpoint": f"/api/documents/analyze/{document_id}",
                        "method": "POST",
                        "reason": error_msg,
                    }
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=error_details or {
                        "message": "Upgrade to Professional to use Advanced AI.",
                        "feature": "ai_extraction_advanced",
                        "upgrade_required": True,
                    }
                )

        # Check if already analyzed
        if document.get("ai_extraction", {}).get("status") == "completed":
            return {
                "message": "Document already analyzed",
                "extraction": document["ai_extraction"]
            }
        client = await db.clients.find_one(
            {"client_id": client_id},
            {"_id": 0, "billing_plan": 1}
        )
        plan_str = client.get("billing_plan", "PLAN_1_SOLO") if client else "PLAN_1_SOLO"
        has_advanced_extraction = plan_registry.get_features_by_string(plan_str).get("ai_extraction_advanced", False)
        # Perform AI analysis
        from services.document_analysis import document_analysis_service

        analysis_file_path = document["file_path"]
        if analysis_file_path and not Path(analysis_file_path).is_absolute():
            analysis_file_path = str((DOCUMENT_STORAGE_PATH / analysis_file_path).resolve())

        result = await document_analysis_service.analyze_document(
            file_path=analysis_file_path,
            mime_type=document.get("mime_type", "application/pdf"),
            document_id=document_id,
            client_id=document["client_id"],
            actor_id=user["portal_user_id"]
        )
        
        if result["success"]:
            extracted_data = result["extracted_data"]
            
            # For Basic plan (PLAN_1_SOLO): Filter to basic fields only, no confidence
            if not has_advanced_extraction:
                basic_data = {
                    "document_type": extracted_data.get("document_type"),
                    "issue_date": extracted_data.get("issue_date"),
                    "expiry_date": extracted_data.get("expiry_date"),
                    # Don't include confidence scores for basic plan
                }
                # Remove None values
                basic_data = {k: v for k, v in basic_data.items() if v is not None}
                
                return {
                    "message": "Document analyzed (Basic extraction)",
                    "extraction_mode": "basic",
                    "extraction": {
                        "status": "completed",
                        "data": basic_data
                    },
                    "auto_apply_enabled": True,  # Basic plan auto-applies
                    "review_ui_available": False
                }
            else:
                # Advanced extraction: Include all fields and confidence
                return {
                    "message": "Document analyzed successfully",
                    "extraction_mode": "advanced",
                    "extraction": {
                        "status": "completed",
                        "data": extracted_data,
                        "confidence": extracted_data.get("confidence", {}),
                    },
                    "auto_apply_enabled": False,  # Advanced requires review
                    "review_ui_available": True
                }
        else:
            return {
                "message": "Document analysis failed",
                "error": result["error"],
                "extraction": None
            }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Document AI analysis error: {e}")
        err_msg = str(e).strip()[:200] if e else ""
        detail = {
            "message": "Failed to analyze document.",
            "error_code": "ANALYSIS_ERROR",
        }
        if err_msg and not any(s in err_msg.lower() for s in ("key", "secret", "password", "token", "api_key")):
            detail["hint"] = err_msg
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail,
        )


@router.get("/{document_id}/file")
async def get_document_file(request: Request, document_id: str, download: bool = False):
    """Client views or downloads their uploaded document. Logged for admin monitoring."""
    user = await client_route_guard(request)
    db = database.get_db()
    document, file_path, media_type, filename = await _resolve_document_file_path(db, document_id)
    if document["client_id"] != user["client_id"]:
        try:
            from services.security_monitoring_service import record_security_event

            xf = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
            rip = xf or (request.headers.get("x-real-ip") or "").strip() or (
                request.client.host if request.client else "unknown"
            )
            await record_security_event(
                event_type="document.cross_user_access_attempt",
                user_id=user.get("portal_user_id"),
                ip=rip,
                details={
                    "document_id": document_id,
                    "actor_client_id": user.get("client_id"),
                    "resource_client_id": document.get("client_id"),
                },
                severity="medium",
            )
        except Exception:
            pass
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view this document")
    await create_audit_log(
        action=AuditAction.DOCUMENT_VIEWED,
        actor_id=user["portal_user_id"],
        client_id=user["client_id"],
        resource_type="document",
        resource_id=document_id,
        metadata={"file_name": document.get("file_name"), "download": download},
    )
    from fastapi.responses import FileResponse
    disposition = "attachment" if download else "inline"
    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=filename,
        headers={"Content-Disposition": f'{disposition}; filename="{filename}"'},
    )


async def _resolve_document_file_path(db, document_id: str):
    """Resolve document record and filesystem path for serving. Returns (document, path, media_type, filename). Raises HTTPException if not found."""
    try:
        DOCUMENT_STORAGE_PATH.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logger.warning("DOCUMENT_STORAGE_PATH mkdir failed: %s", e)
    document = await db.documents.find_one(
        {"document_id": document_id},
        {"_id": 0, "client_id": 1, "file_path": 1, "file_name": 1, "mime_type": 1}
    )
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    raw_path = (document.get("file_path") or "").strip().replace("\\", "/")
    file_path = Path(raw_path) if raw_path else Path()
    resolved_via_fallback = False
    client_id_val = document.get("client_id") or ""
    if not file_path.is_file():
        base_name = file_path.name if raw_path else None
        if base_name and base_name != "." and client_id_val:
            candidate = (DOCUMENT_STORAGE_PATH / client_id_val / base_name).resolve()
            if candidate.is_file():
                try:
                    candidate.relative_to(DOCUMENT_STORAGE_PATH.resolve())
                    file_path = candidate
                    resolved_via_fallback = True
                except ValueError:
                    pass
        if not file_path.is_file() and raw_path and not file_path.is_absolute():
            resolved = (DOCUMENT_STORAGE_PATH / raw_path).resolve()
            if resolved.is_file():
                try:
                    resolved.relative_to(DOCUMENT_STORAGE_PATH.resolve())
                    file_path = resolved
                    resolved_via_fallback = True
                except ValueError:
                    pass
        if not file_path.is_file() and raw_path:
            base_name = file_path.name
            if base_name and base_name != "." and client_id_val:
                resolved = (DOCUMENT_STORAGE_PATH / client_id_val / base_name).resolve()
                if resolved.is_file():
                    file_path = resolved
                    resolved_via_fallback = True
        if not file_path.is_file() and client_id_val:
            file_name = (document.get("file_name") or "").strip()
            ext = Path(file_name).suffix if file_name else ".pdf"
            if ext and not ext.startswith("."):
                ext = f".{ext}"
            if not ext or ext == ".":
                ext = ".pdf"
            candidate = (DOCUMENT_STORAGE_PATH / client_id_val / f"{document_id}{ext}").resolve()
            if candidate.is_file():
                try:
                    candidate.relative_to(DOCUMENT_STORAGE_PATH.resolve())
                    file_path = candidate
                    resolved_via_fallback = True
                except ValueError:
                    pass
        if not file_path.is_file():
            vault_root = DOCUMENT_STORAGE_PATH.resolve()
            storage_dir = (DOCUMENT_STORAGE_PATH / client_id_val).resolve() if client_id_val else vault_root
            vault_root_exists = vault_root.is_dir()
            client_dir_exists = storage_dir.is_dir() if client_id_val else vault_root_exists
            logger.warning(
                "Document file missing: document_id=%s stored_path=%s DOCUMENT_STORAGE_PATH=%s "
                "vault_root_exists=%s client_dir_exists=%s",
                document_id,
                raw_path,
                str(DOCUMENT_STORAGE_PATH),
                vault_root_exists,
                client_dir_exists,
            )
            _vault_s = str(vault_root).replace("\\", "/")
            hint_tmp = (
                " Document storage is under /tmp (or similar); restarts often clear those files while the database still lists the document. Set DOCUMENT_STORAGE_PATH to a persistent volume."
                if "/tmp/" in _vault_s
                else ""
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found. The document record exists but the file is missing from server storage. "
                "If uploads were done on another server or DOCUMENT_STORAGE_PATH differs, the file may not be available here."
                + hint_tmp,
            )
    if resolved_via_fallback:
        logger.info(
            "Document file resolved via fallback: document_id=%s stored_path=%s resolved_path=%s",
            document_id, raw_path, str(file_path),
        )
    media_type = document.get("mime_type") or "application/octet-stream"
    filename = document.get("file_name") or "document"
    return (document, file_path, media_type, filename)


@router.get("/{document_id}/extraction")
async def get_document_extraction(request: Request, document_id: str):
    """Get AI extraction results for a document (from extracted_documents or legacy ai_extraction)."""
    user = await client_route_guard(request)
    db = database.get_db()
    try:
        document = await db.documents.find_one(
            {"document_id": document_id},
            {
                "_id": 0,
                "client_id": 1,
                "extraction_id": 1,
                "extraction_status": 1,
                "ai_extraction": 1,
                "requirement_id": 1,
                "document_type": 1,
            },
        )
        if not document:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
        if user.get("role") != "ROLE_ADMIN" and document["client_id"] != user["client_id"]:
            try:
                from services.security_monitoring_service import record_security_event

                xf = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
                rip = xf or (request.headers.get("x-real-ip") or "").strip() or (
                    request.client.host if request.client else "unknown"
                )
                await record_security_event(
                    event_type="document.cross_user_access_attempt",
                    user_id=user.get("portal_user_id"),
                    ip=rip,
                    details={
                        "document_id": document_id,
                        "actor_client_id": user.get("client_id"),
                        "resource_client_id": document.get("client_id"),
                        "surface": "extraction",
                    },
                    severity="medium",
                )
            except Exception:
                pass
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view this document")

        extraction_id = document.get("extraction_id")
        requirement_row = None
        storage_slug = document.get("document_type")
        rid = document.get("requirement_id")
        if rid:
            requirement_row = await db.requirements.find_one(
                {"requirement_id": rid, "client_id": document.get("client_id")},
                {"_id": 0},
            )

        if extraction_id:
            rec = await db.extracted_documents.find_one(
                {"extraction_id": extraction_id},
                {"_id": 0, "extraction_id": 1, "status": 1, "extracted": 1, "mapping_suggestion": 1, "errors": 1, "audit": 1}
            )
            if rec:
                ext = rec.get("extracted") or {}
                if not storage_slug and ext.get("doc_type"):
                    storage_slug = ext.get("doc_type")
                # Unified shape for frontend (status, data with confidence)
                extraction = {
                    "status": rec.get("status"),
                    "data": {
                        "document_type": ext.get("doc_type"),
                        "certificate_number": ext.get("certificate_number"),
                        "issue_date": ext.get("issue_date"),
                        "expiry_date": ext.get("expiry_date"),
                        "inspector_company": ext.get("inspector_company"),
                        "inspector_id": ext.get("inspector_id"),
                        "address_line_1": ext.get("address_line_1"),
                        "postcode": ext.get("postcode"),
                        "confidence_scores": {"overall": ext.get("overall_confidence")},
                        "notes": ext.get("notes"),
                    },
                    "review_status": "approved" if rec.get("status") == "CONFIRMED" else ("rejected" if rec.get("status") == "REJECTED" else "pending"),
                    "mapping_suggestion": rec.get("mapping_suggestion"),
                    "errors": rec.get("errors"),
                }
                from services.lifecycle_confirm_contract import maybe_attach_lifecycle_confirm_contract

                payload = {"has_extraction": True, "extraction": extraction}
                return maybe_attach_lifecycle_confirm_contract(
                    payload,
                    requirement=requirement_row,
                    storage_slug=storage_slug,
                    surface="document_extraction",
                    requirement_id=rid,
                    document_id=document_id,
                )

        extraction = document.get("ai_extraction")
        if not extraction:
            from services.lifecycle_confirm_contract import maybe_attach_lifecycle_confirm_contract

            payload = {"has_extraction": False, "extraction": None}
            return maybe_attach_lifecycle_confirm_contract(
                payload,
                requirement=requirement_row,
                storage_slug=storage_slug,
                surface="document_extraction",
                requirement_id=rid,
                document_id=document_id,
            )
        if not storage_slug:
            data = extraction.get("data") if isinstance(extraction, dict) else None
            if isinstance(data, dict) and data.get("document_type"):
                storage_slug = data.get("document_type")
        from services.lifecycle_confirm_contract import maybe_attach_lifecycle_confirm_contract

        payload = {"has_extraction": True, "extraction": extraction}
        return maybe_attach_lifecycle_confirm_contract(
            payload,
            requirement=requirement_row,
            storage_slug=storage_slug,
            surface="document_extraction",
            requirement_id=rid,
            document_id=document_id,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Get extraction error: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get extraction")


@router.get("")
async def list_documents(
    request: Request,
    property_id: str = None,
    requirement_id: str = None,
    visibility_state: str = None,
    queue: str = None,
    limit: int = Query(80, ge=1, le=200, description="Max documents returned (newest first)"),
    projection: str = Query(
        "list",
        description="list = operational badges only (faster first paint); full = linkage + visibility batch",
    ),
):
    """List documents for the client."""
    user = await client_route_guard(request)
    db = database.get_db()
    list_projection = str(projection or "full").strip().lower() == "list"
    
    try:
        query: Dict[str, Any] = {"client_id": user["client_id"]}
        if property_id:
            query["$or"] = [
                {"property_id": property_id},
                {
                    "authoritative_property_id": property_id,
                    "evidence_scope_type": {"$nin": ["INTAKE_STAGING", "PORTFOLIO", "UNRESOLVED"]},
                },
            ]
        if requirement_id:
            query["requirement_id"] = requirement_id
        
        documents = await db.documents.find(
            query,
            {"_id": 0, "file_path": 0}  # Don't expose file path
        ).sort("uploaded_at", -1).to_list(int(limit))
        from services.evidence_review_migration import effective_assurance_tier, effective_evidence_review_state
        from services.document_operational_state import attach_document_operational_projection
        from services.document_linkage_governance import (
            attach_document_linkage_projection_batch,
            load_runtime_requirements_for_client,
        )
        from services.document_visibility_governance import (
            attach_document_visibility_projection_batch,
            filter_documents_by_visibility,
        )

        runtime_ids: set = set()
        runtime_reqs: list = []
        if not list_projection:
            runtime_ids, runtime_reqs = await load_runtime_requirements_for_client(
                db, client_id=user["client_id"], property_id=property_id
            )

        for d in documents:
            d["evidence_review_state"] = effective_evidence_review_state(d)
            d["assurance_tier"] = effective_assurance_tier(d)
            attach_document_operational_projection(d)
            d.setdefault("latest_validation_snapshot", None)
            d.setdefault("review_required", None)
            d.setdefault("review_decision_at", None)
            d.setdefault("review_decision_by", None)
            d.setdefault("external_verification_method", None)
            d.setdefault("external_verification_reference", None)
            d.setdefault("ai_assistance", None)
        if not list_projection:
            attach_document_linkage_projection_batch(
                documents,
                runtime_requirement_ids=runtime_ids,
                runtime_requirements=runtime_reqs,
            )
            attach_document_visibility_projection_batch(
                documents,
                requirements=runtime_reqs,
            )
        else:
            for d in documents:
                d.setdefault("linkage_projection_deferred", True)
                d.setdefault("visibility_projection_deferred", True)

        vis_filter = visibility_state or queue
        filtered = filter_documents_by_visibility(documents, vis_filter)
        attention_count = sum(1 for d in documents if d.get("document_attention_required") is True)

        return {
            "documents": filtered,
            "total": len(filtered),
            "total_unfiltered": len(documents),
            "attention_required_count": attention_count,
            "visibility_filter": vis_filter,
        }
    
    except Exception as e:
        logger.error(f"List documents error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list documents"
        )



@router.post("/{document_id}/apply-extraction")
async def apply_ai_extraction(
    request: Request, 
    document_id: str,
    body: ExtractionApplyRequest = Body(default=None)
):
    """Apply reviewed AI-extracted data to the associated requirement.
    
    This endpoint allows users to:
    1. Review AI-extracted data
    2. Modify any incorrect values
    3. Apply the data to update the requirement's due date (user consent + accurate compliance score)
    
    Available on all plans (Solo, Portfolio, Professional) so users can explicitly confirm
    extracted data before it updates the requirement.
    
    Args:
        document_id: The document whose extraction to apply
        body: Request body containing optional confirmed_data (if user corrected AI extraction)
    
    Returns:
        Success message with changes applied, or descriptive error.
    """
    user = await client_route_guard(request)
    db = database.get_db()
    confirmed_data = body.confirmed_data if body else None
    try:
        document = await db.documents.find_one(
            {"document_id": document_id},
            {"_id": 0}
        )
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document not found: {document_id}"
            )
        
        # Verify ownership
        if user.get("role") != "ROLE_ADMIN" and document["client_id"] != user["client_id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to modify this document. You can only apply extraction to your own documents."
            )
        
        # Get AI extraction (from extracted_documents or legacy ai_extraction)
        extraction_id = document.get("extraction_id")
        if extraction_id:
            rec = await db.extracted_documents.find_one({"extraction_id": extraction_id}, {"_id": 0, "status": 1, "extracted": 1})
            if not rec:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Extraction record not found.")
            if rec.get("status") not in ("EXTRACTED", "NEEDS_REVIEW"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot apply extraction with status: {rec.get('status')}. Only EXTRACTED or NEEDS_REVIEW can be applied."
                )
            if confirmed_data:
                data = confirmed_data
            else:
                ext = rec.get("extracted") or {}
                data = {
                    "expiry_date": ext.get("expiry_date"),
                    "issue_date": ext.get("issue_date"),
                    "certificate_number": ext.get("certificate_number"),
                    "document_type": ext.get("doc_type"),
                    "engineer_details": {"name": ext.get("inspector_company") or ext.get("inspector_id"), "company_name": ext.get("inspector_company")},
                }
        else:
            extraction = document.get("ai_extraction", {})
            extraction_status = extraction.get("status")
            if extraction_status != "completed":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Document has not been analyzed yet. Current extraction status: {extraction_status or 'none'}"
                )
            data = confirmed_data if confirmed_data else extraction.get("data", {})
        
        if not data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No extraction data available to apply. Please analyze the document first."
            )
        
        # Validate we have a requirement to update
        requirement_id = document.get("requirement_id")
        if not requirement_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Document is not linked to a requirement. Please link the document to a requirement before applying extraction."
            )
        
        # Get requirement
        requirement = await db.requirements.find_one(
            {"requirement_id": requirement_id},
            {"_id": 0}
        )
        
        if not requirement:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Associated requirement not found: {requirement_id}"
            )
        cid_apply = document.get("client_id")
        prop_apply = await db.properties.find_one(
            {"property_id": document.get("property_id"), "client_id": cid_apply},
            {"_id": 0},
        )
        if user.get("role") != "ROLE_ADMIN" and prop_apply:
            from services.requirement_client_runtime_surface import requirement_row_eligible_on_client_runtime_surfaces

            if not await requirement_row_eligible_on_client_runtime_surfaces(
                db,
                client_id=str(cid_apply),
                row=requirement,
                property_doc=prop_apply,
            ):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Associated requirement not found: {requirement_id}",
                )

        apply_mev = evaluate_document_requirement_match(
            requirement=requirement,
            filename=str(document.get("file_name") or ""),
            user_declared_document_type=document.get("document_type"),
            extracted_data=data,
            upload_route_context="apply_extraction_confirmation",
        )
        if not apply_mev.get("evidence_satisfies_requirement"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=structured_error(
                    "EVIDENCE_MATCH_BLOCKS_APPLY",
                    "The confirmed extraction does not match the linked obligation. Relink to the correct requirement or ask an administrator to review.",
                    evidence_match=apply_mev,
                ),
            )

        # Capture before state for audit
        before_state = {
            "due_date": requirement.get("due_date"),
            "status": requirement.get("status")
        }
        
        # Prepare update data
        update_fields = {}
        changes_made = []
        
        # Apply expiry date if provided (this affects due_date)
        expiry_date = data.get("expiry_date")
        if expiry_date:
            try:
                expiry_dt = _normalize_and_parse_date(expiry_date)
                update_fields["due_date"] = expiry_dt.isoformat()
                update_fields["extracted_expiry_date"] = expiry_dt.isoformat()
                update_fields["expiry_source"] = "EXTRACTED"
                changes_made.append(f"Due date set to {expiry_dt.strftime('%Y-%m-%d')}")
                conf = data.get("confidence_scores", {}).get("overall") if isinstance(data.get("confidence_scores"), dict) else data.get("confidence")
                if conf is not None:
                    try:
                        update_fields["extraction_confidence"] = float(conf)
                    except (TypeError, ValueError):
                        pass
                # Also update status based on date if needed
                now = datetime.now(timezone.utc)
                if expiry_dt < now:
                    update_fields["status"] = "OVERDUE"
                    changes_made.append("Status set to OVERDUE (past due date)")
                elif expiry_dt < now + timedelta(days=30):
                    update_fields["status"] = "EXPIRING_SOON"
                    changes_made.append("Status set to EXPIRING_SOON (expires within 30 days)")
                else:
                    update_fields["status"] = "COMPLIANT"
                    changes_made.append("Status set to COMPLIANT (valid certificate)")
            except ValueError as date_err:
                logger.warning(f"Failed to parse expiry date '{expiry_date}': {date_err}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid expiry date format: {expiry_date}. Expected formats: YYYY-MM-DD or DD/MM/YYYY."
                )
        else:
            logger.info(f"No expiry_date in extraction data for document {document_id}")
        
        # Store extracted data in document for reference
        now_iso = datetime.now(timezone.utc).isoformat()
        document_update = {
            "ai_extraction.review_status": "approved",
            "ai_extraction.reviewed_at": now_iso,
            "ai_extraction.reviewed_by": user["portal_user_id"],
            "ai_extraction.applied_data": data,
            "ai_extracted_data": data,  # Legacy field for compatibility
            "status": DocumentStatus.VERIFIED.value,
        }
        document_update.update(match_evaluation_to_persisted_document_fields(apply_mev))
        document_update["requirement_evidence_mismatch"] = bool(apply_mev.get("requirement_evidence_mismatch"))
        mrt = apply_mev.get("mismatch_reason_text")
        document_update["requirement_evidence_mismatch_reason"] = (mrt[:500] if isinstance(mrt, str) else None)
        if extraction_id:
            document_update["extraction_status"] = "CONFIRMED"
            await db.extracted_documents.update_one(
                {"extraction_id": extraction_id},
                {"$set": {"status": "CONFIRMED", "audit.updated_at": datetime.now(timezone.utc)}}
            )
        
        # Add certificate number if available
        cert_number = data.get("certificate_number")
        if cert_number:
            document_update["certificate_number"] = cert_number
            changes_made.append(f"Certificate number: {cert_number}")
        
        # Add confidence score if available
        confidence = data.get("confidence_scores", {}).get("overall") if isinstance(data.get("confidence_scores"), dict) else data.get("confidence")
        if confidence:
            document_update["confidence_score"] = confidence
        
        # Update document
        await db.documents.update_one(
            {"document_id": document_id},
            {"$set": document_update}
        )
        
        # Update requirement: merge expiry/status changes with truth fields (document is VERIFIED in this flow).
        after_state = before_state.copy()
        truth_set = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "date_source": "VERIFIED_DOCUMENT",
            "evidence_state": "VERIFIED",
            "confidence_state": "VERIFIED",
        }
        merged_req_update = {**update_fields, **truth_set}
        await db.requirements.update_one(
            {"requirement_id": requirement_id},
            {"$set": merged_req_update},
        )
        apply_ai_fanout: Dict[str, Any] = {}
        await _document_path_sync_requirement_authority(
            db,
            requirement_id,
            property_id=str(document.get("property_id") or "") or None,
            client_id=str(document.get("client_id") or ""),
            correlation_base=f"AI_APPLIED:{document_id}",
            transition_origin="routes.documents.apply_ai_extraction",
            transition_fanout=apply_ai_fanout,
            document_id=document_id,
            verification_replay_possible=_document_verification_replay_heuristic(str(before_state.get("status"))),
            document_replacement_detected=bool(confirmed_data),
            stale_document_transition_possible=True,
        )
        after_state["due_date"] = merged_req_update.get("due_date", after_state["due_date"])
        after_state["status"] = merged_req_update.get("status", after_state["status"])
        
        # Create specific audit action for extraction applied
        await create_audit_log(
            action=AuditAction.AI_EXTRACTION_APPLIED,
            actor_id=user["portal_user_id"],
            client_id=document["client_id"],
            resource_type="document",
            resource_id=document_id,
            before_state=before_state,
            after_state=after_state,
            metadata={
                "action": "extraction_applied",
                "requirement_id": requirement_id,
                "changes_made": changes_made,
                "expiry_date_set": expiry_date,
                "expiry_date_parsed": merged_req_update.get("due_date"),
                "certificate_number": cert_number,
                "engineer_name": data.get("engineer_details", {}).get("name") if isinstance(data.get("engineer_details"), dict) else data.get("engineer_name"),
                "user_confirmed": confirmed_data is not None,
                "document_status": "VERIFIED",
                "requirement_status_before": before_state.get("status"),
                "requirement_status_after": after_state.get("status")
            }
        )
        
        logger.info(f"AI extraction applied for document {document_id}: {changes_made}")
        
        property_id = document.get("property_id")
        if property_id:
            from services.compliance_recalc_queue import TRIGGER_AI_APPLIED, ACTOR_CLIENT

            await _document_path_enqueue_recalc(
                apply_ai_fanout,
                property_id=property_id,
                client_id=document["client_id"],
                trigger_reason=TRIGGER_AI_APPLIED,
                actor_type=ACTOR_CLIENT,
                actor_id=user.get("portal_user_id"),
                correlation_id=f"AI_APPLIED:{document_id}",
                trigger_origin="routes.documents.apply_ai_extraction",
                propagation_stage="post_apply_ai_extraction_authority_sync",
            )
            try:
                from services.property_assets_service import update_asset_last_service_from_requirement
                req_type = requirement.get("requirement_type") or requirement.get("requirement_code")
                last_date = update_fields.get("due_date") or (data.get("expiry_date") if data else None)
                if req_type and last_date:
                    last_date_str = last_date.isoformat() if hasattr(last_date, "isoformat") else (last_date if isinstance(last_date, str) else None)
                    if last_date_str:
                        await update_asset_last_service_from_requirement(
                            property_id=property_id,
                            client_id=document["client_id"],
                            requirement_type=req_type,
                            last_service_date=last_date_str,
                        )
            except Exception as asset_err:
                logger.debug("Evidence→asset update skip: %s", asset_err)
        try:
            from services.score_events_service import write_score_event, EVENT_DOCUMENT_CONFIRMED, ACTOR_ROLE_CLIENT
            req_doc = await db.requirements.find_one(
                {"requirement_id": requirement_id},
                {"_id": 0, "requirement_type": 1, "description": 1, "due_date": 1}
            ) if requirement_id else None
            prop_doc = await db.properties.find_one(
                {"property_id": document.get("property_id")},
                {"_id": 0, "nickname": 1, "address_line_1": 1}
            ) if document.get("property_id") else None
            await write_score_event(
                client_id=document["client_id"],
                event_type=EVENT_DOCUMENT_CONFIRMED,
                actor_user_id=user.get("portal_user_id"),
                actor_role=ACTOR_ROLE_CLIENT,
                property_id=document.get("property_id"),
                requirement_id=requirement_id,
                document_id=document_id,
                metadata={
                    "requirement_type": req_doc.get("requirement_type") if req_doc else None,
                    "requirement_description": req_doc.get("description") if req_doc else None,
                    "expiry_date": update_fields.get("due_date") or (req_doc.get("due_date") if req_doc else None),
                    "property_nickname": prop_doc.get("nickname") if prop_doc else None,
                    "property_name": prop_doc.get("address_line_1") if prop_doc else None,
                },
            )
        except Exception as ev_err:
            logger.debug("Score event DOCUMENT_CONFIRMED skip: %s", ev_err)
        outcome = None
        try:
            if document.get("property_id"):
                from services.compliance_outcome_engine import (
                    apply_action_outcome,
                    EVENT_CERTIFICATE_VERIFIED,
                )

                meta = {"document_id": document_id, "requirement_id": requirement_id}
                woid = (document.get("work_order_id") or "").strip()
                if woid:
                    meta["work_order_id"] = woid
                outcome = await apply_action_outcome(
                    {
                        "event_type": EVENT_CERTIFICATE_VERIFIED,
                        "client_id": document["client_id"],
                        "property_id": document.get("property_id"),
                        "asset_id": None,
                        "requirement_type": (requirement or {}).get("requirement_type")
                        or (requirement or {}).get("requirement_code"),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "source_id": document_id,
                        "dedupe_key": f"{EVENT_CERTIFICATE_VERIFIED}:{document_id}",
                        "actor_id": user.get("portal_user_id"),
                        "actor_role": "CLIENT",
                        "metadata": meta,
                    }
                )
        except Exception as outcome_err:
            logger.warning(
                "Action outcome skip for extraction apply: %s",
                outcome_err,
                extra=compliance_fanout_extra(
                    op="outcome_apply",
                    stage="failed",
                    client_id=str(document.get("client_id") or ""),
                    property_id=str(document.get("property_id") or "") or None,
                    requirement_id=str(requirement_id) if requirement_id else None,
                    correlation_id=f"certificate_verified:{document_id}",
                    exc_type=type(outcome_err).__name__,
                ),
            )

        try:
            await _append_document_evidence_to_work_order(document_id, document.get("work_order_id"))
        except Exception as ev_err:
            logger.debug("Evidence append to work order skip: %s", ev_err)

        try:
            await _set_compliance_work_order_proof_verified(db, document.get("work_order_id"))
        except Exception as proof_err:
            logger.warning("Could not set compliance work order proof verified: %s", proof_err)
        
        # Send email notification
        try:
            prefs = await db.notification_preferences.find_one(
                {"client_id": document["client_id"]},
                {"_id": 0, "document_updates": 1},
            )
            document_updates_enabled = prefs.get("document_updates", True) if prefs else True
            if not document_updates_enabled:
                logger.info("Skipping AI extraction applied email for client %s - document_updates disabled", document["client_id"])
            else:
                # Get client details for email
                client = await db.clients.find_one(
                    {"client_id": document["client_id"]},
                    {"_id": 0, "email": 1, "full_name": 1, "customer_reference": 1}
                )
                
                # Get property address for email
                property_doc = await db.properties.find_one(
                    {"property_id": document.get("property_id")},
                    {"_id": 0, "nickname": 1, "address_line_1": 1, "postcode": 1}
                )
                
                if client and client.get("email"):
                    property_address = property_doc.get("nickname") or property_doc.get("address_line_1", "N/A") if property_doc else "N/A"
                    if property_doc and property_doc.get("postcode"):
                        property_address += f", {property_doc.get('postcode')}"
                    
                    # Format expiry date for email
                    expiry_display = "N/A"
                    if update_fields.get("due_date"):
                        try:
                            expiry_dt = datetime.fromisoformat(update_fields["due_date"].replace('Z', '+00:00'))
                            expiry_display = expiry_dt.strftime("%d %B %Y")
                        except (ValueError, AttributeError):
                            expiry_display = update_fields.get("due_date", "N/A")
                    
                    from services.notification_orchestrator import notification_orchestrator
                    from utils.app_urls import get_app_base_url, client_portal_documents_evidence_url

                    base = get_app_base_url(for_email_links=True).rstrip("/")
                    prop_id = str(document.get("property_id") or "").strip()
                    req_id = str(requirement_id or "").strip()
                    if prop_id:
                        _portal = client_portal_documents_evidence_url(base, property_id=prop_id, requirement_id=req_id)
                    else:
                        _portal = f"{base}/documents"
                    result = await notification_orchestrator.send(
                        template_key="AI_EXTRACTION_APPLIED",
                        client_id=document["client_id"],
                        context={
                            "client_name": client.get("full_name", "there"),
                            "customer_reference": client.get("customer_reference", ""),
                            "property_address": property_address,
                            "document_type": data.get("document_type") or document.get("file_name", "Certificate"),
                            "certificate_number": cert_number or "N/A",
                            "expiry_date": expiry_display,
                            "requirement_status": after_state.get("status", "UPDATED"),
                            "portal_link": _portal,
                        },
                        idempotency_key=f"{document_id}_AI_EXTRACTION_APPLIED",
                        event_type="ai_extraction_applied",
                    )
                    if result.outcome in ("sent", "duplicate_ignored"):
                        logger.info(f"AI extraction email sent to {client['email']}")
        except Exception as email_err:
            # Don't fail the extraction if email fails
            logger.warning(f"Failed to send AI extraction email: {email_err}")

        out_apply: Dict[str, Any] = {
            "message": "Extraction applied successfully",
            "document_id": document_id,
            "requirement_id": requirement_id,
            "changes_applied": changes_made,
            "requirement_status": after_state.get("status"),
            "due_date": after_state.get("due_date"),
            "note": "Requirement status has been updated based on the certificate expiry date.",
            "outcome": outcome,
        }
        pn_apply = build_propagation_notice_from_transition_fanout(apply_ai_fanout)
        if pn_apply:
            out_apply["propagation_notice"] = pn_apply
        return out_apply
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Apply extraction error for document {document_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to apply extraction: {str(e)}"
        )


@router.post("/{document_id}/reject-extraction")
async def reject_ai_extraction(request: Request, document_id: str, reason: str = None):
    """Mark AI extraction as rejected (user will enter data manually)."""
    user = await client_route_guard(request)
    db = database.get_db()
    
    try:
        document = await db.documents.find_one(
            {"document_id": document_id},
            {"_id": 0}
        )
        
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        
        # Verify ownership
        if user.get("role") != "ROLE_ADMIN" and document["client_id"] != user["client_id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized"
            )
        
        now_iso = datetime.now(timezone.utc).isoformat()
        doc_update = {
            "ai_extraction.review_status": "rejected",
            "ai_extraction.reviewed_at": now_iso,
            "ai_extraction.reviewed_by": user["portal_user_id"],
            "ai_extraction.rejection_reason": reason,
        }
        extraction_id = document.get("extraction_id")
        if extraction_id:
            doc_update["extraction_status"] = "REJECTED"
            await db.extracted_documents.update_one(
                {"extraction_id": extraction_id},
                {"$set": {"status": "REJECTED", "audit.updated_at": datetime.now(timezone.utc)}}
            )
        await db.documents.update_one({"document_id": document_id}, {"$set": doc_update})
        
        await create_audit_log(
            action=AuditAction.DOCUMENT_AI_ANALYZED,
            actor_id=user["portal_user_id"],
            client_id=document["client_id"],
            resource_type="document",
            resource_id=document_id,
            metadata={
                "action": "extraction_rejected",
                "reason": reason
            }
        )
        
        return {"message": "Extraction marked as rejected"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Reject extraction error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reject extraction"
        )


@router.post("/{document_id}/reconcile-linkage")
async def reconcile_document_linkage(
    request: Request,
    document_id: str,
    body: DocumentLinkageReconcileRequest = Body(...),
):
    """Post-ingestion document↔requirement linkage reconciliation (client)."""
    user = await client_route_guard(request)
    db = database.get_db()
    from services.document_linkage_governance import (
        DocumentLinkageState,
        derive_document_linkage_state,
        load_runtime_requirements_for_client,
        persist_fields_for_intentionally_unlinked,
        persist_fields_for_linked_requirement,
    )
    from services.requirement_evidence_authority import document_evidence_compatible_with_requirement

    doc = await db.documents.find_one({"document_id": document_id, "client_id": user["client_id"]}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    action = str(body.action or "").strip().lower()
    if action not in ("link_requirement", "mark_intentionally_unlinked", "clear_broken_linkage", "update_property"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=structured_error("LINKAGE_ACTION_INVALID", "Unsupported reconciliation action."),
        )

    property_id = str(doc.get("property_id") or doc.get("authoritative_property_id") or "")
    runtime_ids, runtime_reqs = await load_runtime_requirements_for_client(
        db, client_id=user["client_id"], property_id=property_id or None
    )
    prior_state = derive_document_linkage_state(doc, runtime_requirement_ids=runtime_ids)
    prior_requirement_id = doc.get("requirement_id")

    if action == "update_property":
        new_pid = str(body.property_id or "").strip()
        if not new_pid:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="property_id is required")
        prop = await db.properties.find_one(
            {"property_id": new_pid, "client_id": user["client_id"]},
            {"_id": 0},
        )
        if not prop:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")
        await db.documents.update_one(
            {"document_id": document_id},
            {
                "$set": {
                    "property_id": new_pid,
                    "authoritative_property_id": new_pid,
                    **{
                        k: v
                        for k, v in {
                            "linkage_reconciliation_at": datetime.now(timezone.utc).isoformat(),
                            "linkage_reconciliation_by": user.get("portal_user_id"),
                            "linkage_reconciliation_action": action,
                            "linkage_reconciliation_reason": (body.reason or "").strip()[:500] or None,
                        }.items()
                        if v is not None
                    },
                }
            },
        )
    elif action == "mark_intentionally_unlinked":
        review = str(doc.get("evidence_review_state") or doc.get("status") or "").upper()
        if review in ("VERIFIED", "ACCEPTED_UNVERIFIED"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=structured_error(
                    "LINKAGE_CANNOT_UNLINK_VERIFIED",
                    "Verified evidence cannot be marked intentionally unlinked without admin review.",
                ),
            )
        await db.documents.update_one(
            {"document_id": document_id},
            {
                "$set": persist_fields_for_intentionally_unlinked(
                    actor_user_id=user.get("portal_user_id"),
                    reason=body.reason,
                    prior_requirement_id=str(prior_requirement_id) if prior_requirement_id else None,
                )
            },
        )
        if prior_requirement_id:
            unlink_fanout: Dict[str, Any] = {}
            await authority_sync_with_transition_observability(
                db,
                str(prior_requirement_id),
                property_id=property_id or None,
                client_id=user["client_id"],
                correlation_base=f"AUTHORITY_SYNC:CLIENT_UNLINK:{document_id}",
                transition_origin="routes.documents.reconcile_document_linkage",
                transition_fanout=unlink_fanout,
            )
            from services.compliance_recalc_queue import TRIGGER_DOC_UPLOADED, ACTOR_CLIENT

            await _document_path_enqueue_recalc(
                unlink_fanout,
                property_id=property_id,
                client_id=user["client_id"],
                trigger_reason=TRIGGER_DOC_UPLOADED,
                actor_type=ACTOR_CLIENT,
                actor_id=user.get("portal_user_id"),
                correlation_id=f"AUTHORITY_SYNC:CLIENT_UNLINK:{document_id}",
                trigger_origin="routes.documents.reconcile_document_linkage",
                propagation_stage="post_client_unlink_reconcile",
            )
    elif action == "clear_broken_linkage":
        if prior_state != DocumentLinkageState.BROKEN_LINKAGE.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=structured_error(
                    "LINKAGE_NOT_BROKEN",
                    "Document linkage is not broken; use link_requirement or mark_intentionally_unlinked.",
                ),
            )
        stale_rid = str(prior_requirement_id or "")
        await db.documents.update_one(
            {"document_id": document_id},
            {
                "$set": {
                    "requirement_id": None,
                    "document_linkage_state": DocumentLinkageState.RECONCILIATION_REQUIRED.value,
                    "linkage_intent": None,
                    "linkage_reconciliation_at": datetime.now(timezone.utc).isoformat(),
                    "linkage_reconciliation_by": user.get("portal_user_id"),
                    "linkage_reconciliation_action": action,
                    "linkage_reconciliation_reason": (body.reason or "Cleared stale requirement linkage")[:500],
                    "linkage_reconciliation_prior_requirement_id": stale_rid or None,
                }
            },
        )
        if stale_rid:
            clear_fanout: Dict[str, Any] = {}
            await authority_sync_with_transition_observability(
                db,
                stale_rid,
                property_id=property_id or None,
                client_id=user["client_id"],
                correlation_base=f"AUTHORITY_SYNC:CLIENT_CLEAR_BROKEN:{document_id}",
                transition_origin="routes.documents.reconcile_document_linkage",
                transition_fanout=clear_fanout,
            )
    elif action == "link_requirement":
        rid = str(body.requirement_id or "").strip()
        if not rid:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="requirement_id is required")
        req = await db.requirements.find_one(
            {"requirement_id": rid, "client_id": user["client_id"]},
            {"_id": 0},
        )
        if not req:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Requirement not found")
        from services.requirement_client_runtime_surface import requirement_row_eligible_on_client_runtime_surfaces

        prop_d = await db.properties.find_one(
            {"property_id": req.get("property_id") or property_id, "client_id": user["client_id"]},
            {"_id": 0},
        )
        if not prop_d or not await requirement_row_eligible_on_client_runtime_surfaces(
            db,
            client_id=user["client_id"],
            row=req,
            property_doc=prop_d,
        ):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Requirement not found")
        candidate = {**doc, "requirement_id": rid, "property_id": req.get("property_id") or property_id}
        if not document_evidence_compatible_with_requirement(candidate, req):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=structured_error(
                    "LINKAGE_SCOPE_INCOMPATIBLE",
                    "Document scope is incompatible with requirement scope.",
                ),
            )
        await db.documents.update_one(
            {"document_id": document_id},
            {
                "$set": persist_fields_for_linked_requirement(
                    rid,
                    actor_user_id=user.get("portal_user_id"),
                    reason=body.reason,
                    prior_requirement_id=str(prior_requirement_id) if prior_requirement_id else None,
                )
            },
        )
        await safe_upsert_document_upload_evidence_for_linked_document(
            db,
            client_id=user["client_id"],
            property_id=str(req.get("property_id") or property_id),
            requirement_id=rid,
            document_id=document_id,
            actor_user_id=user.get("portal_user_id"),
            filename=doc.get("file_name"),
            context="client_linkage_reconcile",
        )
        link_fanout: Dict[str, Any] = {}
        await _document_path_sync_requirement_authority(
            db,
            rid,
            property_id=str(req.get("property_id") or property_id),
            client_id=user["client_id"],
            correlation_base=f"AUTHORITY_SYNC:CLIENT_LINK_RECONCILE:{document_id}",
            transition_origin="routes.documents.reconcile_document_linkage",
            transition_fanout=link_fanout,
            document_id=document_id,
            stale_document_transition_possible=True,
        )
        from services.compliance_recalc_queue import TRIGGER_DOC_UPLOADED, ACTOR_CLIENT

        await _document_path_enqueue_recalc(
            link_fanout,
            property_id=str(req.get("property_id") or property_id),
            client_id=user["client_id"],
            trigger_reason=TRIGGER_DOC_UPLOADED,
            actor_type=ACTOR_CLIENT,
            actor_id=user.get("portal_user_id"),
            correlation_id=f"AUTHORITY_SYNC:CLIENT_LINK_RECONCILE:{document_id}",
            trigger_origin="routes.documents.reconcile_document_linkage",
            propagation_stage="post_client_link_reconcile",
        )

    updated = await db.documents.find_one({"document_id": document_id}, {"_id": 0, "file_path": 0})
    runtime_ids_after, runtime_reqs_after = await load_runtime_requirements_for_client(
        db, client_id=user["client_id"], property_id=str(updated.get("property_id") or "") or None
    )
    from services.document_operational_state import attach_document_operational_projection
    from services.document_linkage_governance import attach_document_linkage_projection
    from services.document_visibility_governance import attach_document_visibility_projection

    attach_document_operational_projection(updated)
    attach_document_linkage_projection(
        updated,
        runtime_requirement_ids=runtime_ids_after,
        runtime_requirements=runtime_reqs_after,
    )
    attach_document_visibility_projection(
        updated,
        requirements_by_id={str(r.get("requirement_id")): r for r in runtime_reqs_after if r.get("requirement_id")},
        primary_document_ids={
            str(r.get("evidence_doc_id") or r.get("document_id") or "").strip()
            for r in runtime_reqs_after
            if str(r.get("evidence_doc_id") or r.get("document_id") or "").strip()
        },
    )
    await create_audit_log(
        action=AuditAction.DOCUMENT_UPLOADED,
        actor_id=user.get("portal_user_id"),
        client_id=user["client_id"],
        resource_type="document",
        resource_id=document_id,
        metadata={
            "action_type": "DOCUMENT_LINKAGE_RECONCILED",
            "reconcile_action": action,
            "prior_linkage_state": prior_state,
            "new_linkage_state": updated.get("document_linkage_state"),
            "requirement_id": updated.get("requirement_id"),
            "reason": (body.reason or "")[:200] or None,
        },
    )
    return {
        "message": "Document linkage reconciled",
        "document_id": document_id,
        "document": updated,
    }


@router.get("/{document_id}/details")
async def get_document_details(request: Request, document_id: str):
    """Get full document details including AI extraction and requirement info."""
    user = await client_route_guard(request)
    db = database.get_db()
    
    try:
        document = await db.documents.find_one(
            {"document_id": document_id},
            {"_id": 0, "file_path": 0}
        )
        
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        
        # Verify ownership
        if user.get("role") != "ROLE_ADMIN" and document["client_id"] != user["client_id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized"
            )
        
        # Get associated requirement
        requirement = None
        if document.get("requirement_id"):
            requirement = await db.requirements.find_one(
                {"requirement_id": document["requirement_id"]},
                {"_id": 0}
            )
            if requirement and user.get("role") != "ROLE_ADMIN":
                prop_d = await db.properties.find_one(
                    {"property_id": document.get("property_id"), "client_id": user["client_id"]},
                    {"_id": 0},
                )
                if prop_d:
                    from services.requirement_client_runtime_surface import requirement_row_eligible_on_client_runtime_surfaces

                    if not await requirement_row_eligible_on_client_runtime_surfaces(
                        db,
                        client_id=user["client_id"],
                        row=requirement,
                        property_doc=prop_d,
                    ):
                        requirement = None
        
        # Get property info
        property_doc = None
        if document.get("property_id"):
            property_doc = await db.properties.find_one(
                {"property_id": document["property_id"]},
                {"_id": 0, "address_line_1": 1, "city": 1, "postcode": 1}
            )
        
        if document.get("property_id"):
            property_doc = await db.properties.find_one(
                {"property_id": document["property_id"]},
                {"_id": 0, "address_line_1": 1, "city": 1, "postcode": 1}
            )

        from services.evidence_review_migration import effective_assurance_tier, effective_evidence_review_state
        from services.document_operational_state import attach_document_operational_projection
        from services.document_linkage_governance import (
            attach_document_linkage_projection,
            load_runtime_requirements_for_client,
        )

        document["evidence_review_state"] = effective_evidence_review_state(document)
        document["assurance_tier"] = effective_assurance_tier(document)
        attach_document_operational_projection(document)
        runtime_ids, runtime_reqs = await load_runtime_requirements_for_client(
            db,
            client_id=user["client_id"],
            property_id=str(document.get("property_id") or "") or None,
        )
        attach_document_linkage_projection(
            document,
            runtime_requirement_ids=runtime_ids,
            runtime_requirements=runtime_reqs,
        )

        return {
            "document": document,
            "requirement": requirement,
            "property": property_doc
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get document details error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get document details"
        )
