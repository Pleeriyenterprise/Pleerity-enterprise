"""
Intake Upload Routes - Preferences & Consents step uploads.
Temporary storage (IntakeUploads); ClamAV scan; migration to vault on provisioning success.
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, status
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

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/intake/uploads", tags=["intake-uploads"])

# Limits (safe defaults)
DATA_DIR = os.getenv("DATA_DIR", "/tmp")
INTAKE_UPLOAD_DIR = Path(os.environ.get("INTAKE_UPLOAD_DIR", str(Path(DATA_DIR) / "uploads" / "intake")))
INTAKE_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_FILE_BYTES = 20 * 1024 * 1024   # 20MB
MAX_SESSION_BYTES = 200 * 1024 * 1024  # 200MB
MAX_FILES_PER_REQUEST = 20  # Per-request cap (no overall file count limit)

ALLOWED_MIMES = {
    "application/pdf",
    "image/jpeg",
    "image/jpg",
    "image/png",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # DOCX
}
ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".docx"}


def _error_payload(message: str, error_code: str = "UPLOAD_VALIDATION_FAILED", **extra) -> dict:
    """Consistent error payload for 400/413."""
    return {
        "error_code": error_code,
        "message": message,
        **extra,
    }


def _validate_file_type(filename: str, content_type: str | None) -> None:
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_error_payload(
                "Only PDF, JPG, PNG, and DOCX files are allowed.",
                allowed_types=list(ALLOWED_EXTENSIONS),
            ),
        )
    if content_type and content_type not in ALLOWED_MIMES:
        # Allow by extension if MIME is generic
        if content_type not in ("application/octet-stream",):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=_error_payload(
                    f"File type not allowed: {content_type}. Use PDF, JPG, PNG, or DOCX.",
                    allowed_types=list(ALLOWED_EXTENSIONS),
                ),
            )


@router.post("/upload")
async def upload_intake_documents(
    intake_session_id: str = Form(...),
    files: List[UploadFile] = File(...),
):
    """
    Upload documents during intake (Preferences & Consents step).
    - Allowed: PDF, JPG, PNG, DOCX. Max 20MB per file, 200MB per session.
    - Files are scanned with ClamAV; flagged/failed → QUARANTINED (not migrated).
    """
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_error_payload("At least one file is required."),
        )
    if len(files) > MAX_FILES_PER_REQUEST:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_error_payload(
                f"Too many files in one request. Maximum {MAX_FILES_PER_REQUEST} files per upload.",
                error_code="TOO_MANY_FILES",
                max_files=MAX_FILES_PER_REQUEST,
                received=len(files),
            ),
        )

    db = database.get_db()

    # Session total
    existing = await db.intake_uploads.find(
        {"intake_session_id": intake_session_id},
        {"_id": 0, "file_size": 1},
    ).to_list(1000)
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
        _validate_file_type(file.filename or "", file.content_type)

        file_ext = Path(file.filename or ".bin").suffix.lower()
        if not file_ext or file_ext not in ALLOWED_EXTENSIONS:
            file_ext = ".bin"
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
async def list_intake_uploads(intake_session_id: str):
    """List all uploads for an intake session (includes status)."""
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
async def delete_intake_upload(upload_id: str):
    """Delete an intake upload. Allowed only if not MIGRATED (QUARANTINED and CLEAN may be deleted)."""
    db = database.get_db()
    upload = await db.intake_uploads.find_one({"upload_id": upload_id}, {"_id": 0})
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
