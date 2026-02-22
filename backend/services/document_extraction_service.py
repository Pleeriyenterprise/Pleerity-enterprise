"""
Document extraction pipeline: enqueue → extract text → AI → validate → store.
Deterministic and auditable: raw_response_json, model, prompt_version, timestamp.
Never overwrites user data without confirmation; status EXTRACTED/NEEDS_REVIEW/FAILED.
"""
import asyncio
import logging
import os
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from database import database
from models import AuditAction
from utils.audit import create_audit_log

from services.ai_provider import extract_compliance_fields

logger = logging.getLogger(__name__)

# Cap extracted text for cost control (task: 30k chars)
TEXT_CAP = 30_000

# Confidence threshold and rule (task: >= 0.85 and expiry_date present => EXTRACTED)
CONFIDENCE_THRESHOLD = 0.85

# Rate limits (task: max per minute globally, per client/day)
RATE_LIMIT_GLOBAL_PER_MINUTE = 60
RATE_LIMIT_CLIENT_PER_DAY = 200

# In-memory rate limit state (simple; reset on restart)
_rate_global: List[float] = []
_rate_by_client: Dict[str, List[float]] = {}


def _extract_text_from_file(file_path: str, mime_type: str) -> str:
    """Extract text from file. PDF via pypdf; else decode as text. Capped to TEXT_CAP."""
    path = Path(file_path)
    if not path.is_file():
        return ""
    try:
        if (mime_type or "").lower() == "application/pdf" or path.suffix.lower() == ".pdf":
            try:
                from pypdf import PdfReader
                reader = PdfReader(str(path))
                parts = []
                for page in reader.pages:
                    text = page.extract_text()
                    if text:
                        parts.append(text)
                    if sum(len(p) for p in parts) >= TEXT_CAP:
                        break
                out = "\n".join(parts)[:TEXT_CAP]
                return out or ""
            except Exception as e:
                logger.warning("PDF text extraction failed: %s", e)
                return ""
        # Plain text / fallback: read bytes and decode
        with open(path, "rb") as f:
            raw = f.read(1024 * 1024)  # max 1MB read
        for enc in ("utf-8", "latin-1", "cp1252"):
            try:
                return raw.decode(enc)[:TEXT_CAP]
            except UnicodeDecodeError:
                continue
        return ""
    except Exception as e:
        logger.warning("Text extraction failed for %s: %s", file_path, e)
        return ""


def _check_rate_limit(client_id: str) -> Optional[str]:
    """Returns error_code if rate limited, else None."""
    now = datetime.now(timezone.utc).timestamp()
    # Global per minute
    _rate_global[:] = [t for t in _rate_global if now - t < 60]
    if len(_rate_global) >= RATE_LIMIT_GLOBAL_PER_MINUTE:
        return "RATE_LIMITED"
    # Per client per day
    client_times = _rate_by_client.get(client_id, [])
    client_times[:] = [t for t in client_times if now - t < 86400]
    if len(client_times) >= RATE_LIMIT_CLIENT_PER_DAY:
        return "RATE_LIMITED"
    return None


def _record_rate(client_id: str) -> None:
    now = datetime.now(timezone.utc).timestamp()
    _rate_global.append(now)
    _rate_by_client.setdefault(client_id, []).append(now)


async def enqueue_extraction(
    document_id: str,
    client_id: str,
    source: str,
    property_id: Optional[str] = None,
    intake_session_id: Optional[str] = None,
) -> Optional[str]:
    """
    Create extraction record (PENDING), link to document, and run extraction in background.
    Returns extraction_id (extracted_documents._id) or None if skipped/error.
    Non-blocking: does not wait for AI.
    """
    db = database.get_db()
    doc = await db.documents.find_one(
        {"document_id": document_id, "client_id": client_id},
        {"_id": 0, "file_path": 1, "file_name": 1, "mime_type": 1},
    )
    if not doc:
        logger.warning("enqueue_extraction: document not found %s", document_id)
        return None
    rl = _check_rate_limit(client_id)
    if rl:
        logger.warning("enqueue_extraction: rate limited for client %s", client_id)
        return None
    extraction_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    record = {
        "extraction_id": extraction_id,
        "client_id": client_id,
        "property_id": property_id,
        "document_id": document_id,
        "intake_session_id": intake_session_id,
        "file_name": doc.get("file_name") or "",
        "mime_type": doc.get("mime_type") or "",
        "source": source,
        "extracted": None,
        "mapping_suggestion": None,
        "status": "PENDING",
        "errors": None,
        "audit": {
            "model": None,
            "prompt_version": None,
            "tokens_in": None,
            "tokens_out": None,
            "raw_response_json": None,
            "created_at": now,
            "updated_at": now,
        },
    }
    await db.extracted_documents.insert_one(record)
    await db.documents.update_one(
        {"document_id": document_id},
        {"$set": {"extraction_id": extraction_id, "extraction_status": "PENDING"}},
    )
    _record_rate(client_id)
    await create_audit_log(
        action=AuditAction.DOC_EXTRACT_REQUESTED,
        actor_id=None,
        client_id=client_id,
        resource_type="document",
        resource_id=document_id,
        metadata={"extraction_id": extraction_id, "source": source},
    )
    asyncio.create_task(run_extraction_job(extraction_id))
    return extraction_id


async def run_extraction_job(extraction_id: str) -> None:
    """Load extraction record, read file, extract text, call AI, validate, store result."""
    db = database.get_db()
    record = await db.extracted_documents.find_one({"extraction_id": extraction_id})
    if not record:
        logger.warning("run_extraction_job: record not found %s", extraction_id)
        return
    if record.get("status") != "PENDING":
        return
    document_id = record["document_id"]
    client_id = record["client_id"]
    doc = await db.documents.find_one({"document_id": document_id}, {"_id": 0, "file_path": 1, "file_name": 1, "mime_type": 1})
    if not doc:
        await _set_failed(db, extraction_id, document_id, client_id, "DOCUMENT_NOT_FOUND", "Document no longer exists")
        return
    file_path = doc.get("file_path")
    if not file_path or not Path(file_path).is_file():
        await _set_failed(db, extraction_id, document_id, client_id, "FILE_NOT_FOUND", "File not found on storage")
        return
    file_name = doc.get("file_name") or "document"
    mime_type = doc.get("mime_type") or ""
    text = _extract_text_from_file(file_path, mime_type)
    if not text.strip():
        await _set_failed(db, extraction_id, document_id, client_id, "NO_TEXT", "Could not extract text from file")
        return
    # Call AI (sync) in thread to not block
    result = await asyncio.to_thread(
        extract_compliance_fields,
        text,
        file_name,
        hints={"source": record.get("source")},
    )
    now = datetime.now(timezone.utc)
    if not result.get("success"):
        error_code = result.get("error_code") or "AI_ERROR"
        error_message = result.get("error_message") or "Extraction failed"
        await _set_failed(
            db,
            extraction_id,
            document_id,
            client_id,
            error_code,
            error_message,
            audit_extra={
                "raw_response_json": result.get("raw_response_json"),
                "model": result.get("model"),
                "prompt_version": result.get("prompt_version"),
            },
        )
        return
    extracted = result.get("extracted") or {}
    raw_json = result.get("raw_response_json")
    model = result.get("model") or ""
    prompt_version = result.get("prompt_version") or ""
    tokens_in = result.get("tokens_in")
    tokens_out = result.get("tokens_out")
    confidence = extracted.get("confidence") or {}
    overall = float(confidence.get("overall") or 0)
    expiry_date = extracted.get("expiry_date")
    # Task: if overall_confidence >= 0.85 AND expiry_date present => EXTRACTED, else => NEEDS_REVIEW
    if overall >= CONFIDENCE_THRESHOLD and expiry_date:
        status = "EXTRACTED"
        audit_action = AuditAction.DOC_EXTRACT_SUCCEEDED
    else:
        status = "NEEDS_REVIEW"
        audit_action = AuditAction.DOC_EXTRACT_NEEDS_REVIEW
    mapping_suggestion = None
    req_key = extracted.get("requirement_key")
    if req_key or extracted.get("doc_type"):
        mapping_suggestion = {
            "requirement_key": req_key or _doc_type_to_requirement_key(extracted.get("doc_type")),
            "suggested_property_id": record.get("property_id"),
        }
    extracted_for_storage = {
        "doc_type": extracted.get("doc_type") or "UNKNOWN",
        "certificate_number": extracted.get("certificate_number"),
        "issue_date": extracted.get("issue_date"),
        "expiry_date": extracted.get("expiry_date"),
        "inspector_company": extracted.get("inspector_company"),
        "inspector_id": extracted.get("inspector_id"),
        "address_line_1": extracted.get("address_line_1"),
        "postcode": extracted.get("postcode"),
        "property_match_confidence": overall,
        "overall_confidence": overall,
        "notes": extracted.get("notes"),
    }
    await db.extracted_documents.update_one(
        {"extraction_id": extraction_id},
        {
            "$set": {
                "extracted": extracted_for_storage,
                "mapping_suggestion": mapping_suggestion,
                "status": status,
                "errors": None,
                "audit.model": model,
                "audit.prompt_version": prompt_version,
                "audit.tokens_in": tokens_in,
                "audit.tokens_out": tokens_out,
                "audit.raw_response_json": raw_json,
                "audit.updated_at": now,
            }
        },
    )
    await db.documents.update_one(
        {"document_id": document_id},
        {"$set": {"extraction_status": status}},
    )
    await create_audit_log(
        action=audit_action,
        actor_id=None,
        client_id=client_id,
        resource_type="document",
        resource_id=document_id,
        metadata={
            "extraction_id": extraction_id,
            "status": status,
            "overall_confidence": overall,
            "has_expiry_date": bool(expiry_date),
        },
    )
    logger.info("Extraction %s completed for document %s: %s", extraction_id, document_id, status)


def _doc_type_to_requirement_key(doc_type: Optional[str]) -> Optional[str]:
    if not doc_type:
        return None
    m = {"GAS_SAFETY": "gas_safety", "EICR": "eicr", "EPC": "epc", "HMO_LICENCE": "hmo_licence", "TENANCY": "tenancy", "INSURANCE": "insurance"}
    return m.get((doc_type or "").upper())


async def _set_failed(
    db,
    extraction_id: str,
    document_id: str,
    client_id: str,
    error_code: str,
    error_message: str,
    audit_extra: Optional[Dict[str, Any]] = None,
) -> None:
    now = datetime.now(timezone.utc)
    set_fields = {
        "status": "FAILED",
        "errors": {"code": error_code, "message": error_message},
        "audit.updated_at": now,
    }
    if audit_extra:
        for k, v in audit_extra.items():
            set_fields[f"audit.{k}"] = v
    await db.extracted_documents.update_one(
        {"extraction_id": extraction_id},
        {"$set": set_fields},
    )
    await db.documents.update_one(
        {"document_id": document_id},
        {"$set": {"extraction_status": "FAILED"}},
    )
    await create_audit_log(
        action=AuditAction.DOC_EXTRACT_FAILED,
        actor_id=None,
        client_id=client_id,
        resource_type="document",
        resource_id=document_id,
        metadata={"extraction_id": extraction_id, "error_code": error_code, "error_message": error_message},
    )
