"""
Intake Upload Routes - Preferences & Consents step uploads.
Temporary storage (IntakeUploads); ClamAV scan; migration to vault on provisioning success.
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query, Request, status
from database import database
from models.intake_uploads import IntakeUpload, IntakeUploadStatus
from utils.audit import create_audit_log
from models import AuditAction
from datetime import datetime, timezone
from typing import List
import os
import uuid
from pathlib import Path
import logging
import re
from utils.rate_limiter import rate_limiter, log_rate_limit_event
from utils.storage_paths import resolve_data_dir, resolve_intake_upload_dir

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/intake/uploads", tags=["intake-uploads"])

# Limits (safe defaults)
DATA_DIR = resolve_data_dir()
INTAKE_UPLOAD_DIR = resolve_intake_upload_dir()
INTAKE_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_FILE_BYTES = 20 * 1024 * 1024   # 20MB per file
MAX_SESSION_BYTES = 200 * 1024 * 1024  # 200MB per intake session
# No document count limit: only size limits apply (per file + per session)
SAFE_EXTENSIONS = {
    ".pdf", ".doc", ".docx", ".txt", ".rtf", ".odt",
    ".jpg", ".jpeg", ".png", ".webp", ".heic",
    ".xls", ".xlsx", ".csv",
}
INTAKE_SESSION_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("X-Forwarded-For")
    if fwd:
        return fwd.split(",")[0].strip()
    return (request.client and request.client.host) or "unknown"


def _validate_intake_session_id(value: str) -> str:
    v = (value or "").strip()
    if not INTAKE_SESSION_ID_RE.match(v):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_error_payload("Invalid intake session identifier.", error_code="INVALID_SESSION_ID"),
        )
    return v


def _error_payload(message: str, error_code: str = "UPLOAD_VALIDATION_FAILED", **extra) -> dict:
    """Consistent error payload for 400/413."""
    return {
        "error_code": error_code,
        "message": message,
        **extra,
    }


@router.post("/upload")
async def upload_intake_documents(
    request: Request,
    intake_session_id: str = Form(...),
    files: List[UploadFile] = File(...),
):
    """
    Upload documents during intake (Preferences & Consents step).
    - All file types allowed (no MIME/extension restriction). Max 20MB per file, 200MB per session.
    - Files are scanned with ClamAV; flagged/failed → QUARANTINED (not migrated).
    """
    intake_session_id = _validate_intake_session_id(intake_session_id)
    ip = _client_ip(request)
    allowed, err_msg = await rate_limiter.check_rate_limit(
        f"intake_upload_ip:{ip}",
        max_attempts=120,
        window_minutes=60,
    )
    if not allowed:
        log_rate_limit_event("intake_upload", ip, ip)
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=err_msg or "Rate limit exceeded")

    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_error_payload("At least one file is required."),
        )

    db = database.get_db()

    # Session total (no file count limit; only byte limit)
    existing = await db.intake_uploads.find(
        {"intake_session_id": intake_session_id},
        {"_id": 0, "file_size": 1},
    ).to_list(10000)
    current_session_bytes = sum(u.get("file_size", 0) for u in existing)
    new_bytes = 0
    for f in files:
        size = getattr(f, "size", None) or 0
        if not size:
            content = await f.read()
            size = len(content)
            await f.seek(0) if hasattr(f, "seek") else None
        new_bytes += size

    if current_session_bytes + new_bytes > MAX_SESSION_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=_error_payload(
                f"Session upload limit exceeded. Maximum {MAX_SESSION_BYTES // (1024*1024)}MB per intake session.",
                error_code="SESSION_LIMIT_EXCEEDED",
                current_bytes=current_session_bytes,
                requested_bytes=new_bytes,
                max_bytes=MAX_SESSION_BYTES,
            ),
        )

    uploaded_files = []
    for file in files:
        content = await file.read()
        file_size = len(content)
        if file_size > MAX_FILE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=_error_payload(
                    f"File '{file.filename}' exceeds {MAX_FILE_BYTES // (1024*1024)}MB limit.",
                    error_code="FILE_TOO_LARGE",
                    max_bytes=MAX_FILE_BYTES,
                    file_size=file_size,
                ),
            )
        file_ext = Path(file.filename or ".bin").suffix.lower()
        if not file_ext:
            file_ext = ".bin"
        if file_ext not in SAFE_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=_error_payload(
                    f"File type '{file_ext}' is not allowed.",
                    error_code="FILE_TYPE_NOT_ALLOWED",
                ),
            )
        safe_name = f"{uuid.uuid4().hex}{file_ext}"
        storage_path = INTAKE_UPLOAD_DIR / safe_name
        with open(storage_path, "wb") as fh:
            fh.write(content)

        upload = IntakeUpload(
            intake_session_id=intake_session_id,
            filename=safe_name,
            original_filename=file.filename or "unknown",
            file_size=file_size,
            content_type=file.content_type or "application/octet-stream",
            storage_path=str(storage_path),
            status=IntakeUploadStatus.SCANNING.value,
        )
        doc = upload.model_dump()
        doc["uploaded_at"] = doc["uploaded_at"].isoformat() if hasattr(doc["uploaded_at"], "isoformat") else doc["uploaded_at"]
        await db.intake_uploads.insert_one(doc)

        # ClamAV scan (sync). Only CLEAN if scan explicitly returns CLEAN; else QUARANTINED (scanner unavailable/failure = never CLEAN)
        from services.clamav_scanner import scan_file, move_to_quarantine
        scan_status, scan_error = scan_file(str(storage_path))
        if scan_status != "CLEAN":
            new_path = move_to_quarantine(str(storage_path), upload.upload_id, upload.filename)
            await db.intake_uploads.update_one(
                {"upload_id": upload.upload_id},
                {
                    "$set": {
                        "status": IntakeUploadStatus.QUARANTINED.value,
                        "storage_path": new_path,
                        "scan_error": scan_error,
                    }
                },
            )
            await create_audit_log(
                action=AuditAction.ADMIN_ACTION,
                actor_role="SYSTEM",
                client_id=None,
                resource_type="intake_upload",
                resource_id=upload.upload_id,
                metadata={
                    "action_type": "INTAKE_UPLOAD_QUARANTINED",
                    "intake_session_id": intake_session_id,
                    "original_filename": upload.original_filename,
                    "reason": scan_error,
                },
            )
            uploaded_files.append({
                "upload_id": upload.upload_id,
                "filename": file.filename,
                "size": file_size,
                "status": "QUARANTINED",
                "error": scan_error,
            })
        else:
            # Only set CLEAN when scanner explicitly returned CLEAN
            await db.intake_uploads.update_one(
                {"upload_id": upload.upload_id},
                {"$set": {"status": IntakeUploadStatus.CLEAN.value}},
            )
            uploaded_files.append({
                "upload_id": upload.upload_id,
                "filename": file.filename,
                "size": file_size,
                "status": "CLEAN",
            })

        logger.info(f"Intake upload: {file.filename} ({file_size} bytes) -> {scan_status} for session {intake_session_id}")

    session_size = current_session_bytes + new_bytes
    return {
        "success": True,
        "uploaded": uploaded_files,
        "session_size": session_size,
    }


@router.get("/list/{intake_session_id}")
async def list_intake_uploads(
    request: Request,
    intake_session_id: str,
):
    """List all uploads for an intake session (includes status)."""
    intake_session_id = _validate_intake_session_id(intake_session_id)
    ip = _client_ip(request)
    allowed, err_msg = await rate_limiter.check_rate_limit(
        f"intake_upload_list_ip:{ip}",
        max_attempts=300,
        window_minutes=60,
    )
    if not allowed:
        log_rate_limit_event("intake_upload_list", ip, ip)
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=err_msg or "Rate limit exceeded")
    db = database.get_db()
    cursor = db.intake_uploads.find(
        {"intake_session_id": intake_session_id},
        {"_id": 0, "storage_path": 0},
    )
    # Normalize legacy scan_status -> status
    items = []
    async for row in cursor:
        if "status" not in row and "scan_status" in row:
            row["status"] = row["scan_status"]
        if row.get("uploaded_at") and hasattr(row["uploaded_at"], "isoformat"):
            row["uploaded_at"] = row["uploaded_at"].isoformat()
        items.append(row)
    return items


@router.delete("/{upload_id}")
async def delete_intake_upload(
    request: Request,
    upload_id: str,
    intake_session_id: str = Query(..., min_length=8, max_length=128),
):
    """Delete an intake upload. Allowed only if not MIGRATED (QUARANTINED and CLEAN may be deleted)."""
    intake_session_id = _validate_intake_session_id(intake_session_id)
    ip = _client_ip(request)
    allowed, err_msg = await rate_limiter.check_rate_limit(
        f"intake_upload_delete_ip:{ip}",
        max_attempts=120,
        window_minutes=60,
    )
    if not allowed:
        log_rate_limit_event("intake_upload_delete", ip, ip)
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=err_msg or "Rate limit exceeded")
    db = database.get_db()
    upload = await db.intake_uploads.find_one(
        {"upload_id": upload_id, "intake_session_id": intake_session_id},
        {"_id": 0},
    )
    if not upload:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_error_payload("Upload not found.", error_code="UPLOAD_NOT_FOUND"),
        )
    if upload.get("status") == IntakeUploadStatus.MIGRATED.value or upload.get("migrated_to_document_id"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_error_payload("Cannot delete an upload that has been migrated to your vault.", error_code="ALREADY_MIGRATED"),
        )
    storage_path = upload.get("storage_path")
    if storage_path and os.path.isfile(storage_path):
        try:
            os.remove(storage_path)
        except OSError:
            pass
    await db.intake_uploads.delete_one({"upload_id": upload_id})
    return {"success": True}
