"""
Intake Upload Routes - Handle temporary document uploads during intake
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from database import database
from models.intake_uploads import IntakeUpload, IntakeUploadStatus
from datetime import datetime, timezone
from typing import List
import os
import uuid
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/intake/uploads", tags=["intake-uploads"])

# Storage configuration
INTAKE_UPLOAD_DIR = Path("/app/uploads/intake")
INTAKE_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_FILE_SIZE = 25 * 1024 * 1024  # 25MB
MAX_SESSION_SIZE = 250 * 1024 * 1024  # 250MB


@router.post("/upload")
async def upload_intake_documents(
    intake_session_id: str = Form(...),
    files: List[UploadFile] = File(...)
):
    """
    Upload documents during intake (before payment).
    
    Constraints:
    - Max 25MB per file
    - Max 250MB total per session
    - All file types allowed
    - Stored as IntakeUploads (temporary)
    """
    db = database.get_db()
    
    # Check session total size
    existing_uploads = await db.intake_uploads.find(
        {"intake_session_id": intake_session_id},
        {"_id": 0, "file_size": 1}
    ).to_list(1000)
    
    current_session_size = sum(u["file_size"] for u in existing_uploads)
    new_files_size = sum(f.size for f in files if f.size)
    
    if current_session_size + new_files_size > MAX_SESSION_SIZE:
        raise HTTPException(
            400,
            f"Session upload limit exceeded. Maximum 250MB per intake session."
        )
    
    uploaded_files = []
    
    for file in files:
        # Validate file size
        if file.size and file.size > MAX_FILE_SIZE:
            raise HTTPException(
                400,
                f"File '{file.filename}' exceeds 25MB limit"
            )
        
        # Generate safe filename
        file_ext = Path(file.filename).suffix.lower()
        safe_filename = f"{uuid.uuid4().hex}{file_ext}"
        storage_path = INTAKE_UPLOAD_DIR / safe_filename
        
        # Save file
        contents = await file.read()
        with open(storage_path, "wb") as f:
            f.write(contents)
        
        # Create upload record
        upload = IntakeUpload(
            intake_session_id=intake_session_id,
            filename=safe_filename,
            original_filename=file.filename,
            file_size=len(contents),
            content_type=file.content_type or "application/octet-stream",
            storage_path=str(storage_path),
            scan_status=IntakeUploadStatus.SKIPPED
        )
        
        doc = upload.dict()
        doc["uploaded_at"] = doc["uploaded_at"].isoformat() if hasattr(doc["uploaded_at"], "isoformat") else doc["uploaded_at"]
        
        await db.intake_uploads.insert_one(doc)
        
        uploaded_files.append({
            "upload_id": upload.upload_id,
            "filename": file.filename,
            "size": len(contents)
        })
        
        logger.info(f"Intake upload: {file.filename} ({len(contents)} bytes) for session {intake_session_id}")
    
    return {
        "success": True,
        "uploaded": uploaded_files,
        "session_size": current_session_size + new_files_size
    }


@router.get("/list/{intake_session_id}")
async def list_intake_uploads(intake_session_id: str):
    """List all uploads for an intake session."""
    db = database.get_db()
    
    uploads = await db.intake_uploads.find(
        {"intake_session_id": intake_session_id},
        {"_id": 0}
    ).to_list(1000)
    
    return uploads


@router.delete("/{upload_id}")
async def delete_intake_upload(upload_id: str):
    """Delete an intake upload."""
    db = database.get_db()
    
    upload = await db.intake_uploads.find_one({"upload_id": upload_id}, {"_id": 0})
    
    if upload:
        # Delete file
        try:
            os.remove(upload["storage_path"])
        except:
            pass
        
        # Delete record
        await db.intake_uploads.delete_one({"upload_id": upload_id})
    
    return {"success": True}
