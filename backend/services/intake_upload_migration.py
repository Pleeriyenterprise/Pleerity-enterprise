"""
Migrate CLEAN IntakeUploads to client document vault after successful provisioning.
Idempotent: only migrates uploads with status CLEAN and no migrated_to_document_id.
"""
import os
import shutil
import uuid
import logging
from pathlib import Path
from datetime import datetime, timezone
from database import database
from models import Document, DocumentStatus
from models.intake_uploads import IntakeUploadStatus

logger = logging.getLogger(__name__)

DATA_DIR = os.getenv("DATA_DIR", "/tmp")
DOCUMENT_STORAGE_PATH = Path(os.environ.get("DOCUMENT_STORAGE_PATH", str(Path(DATA_DIR) / "data" / "documents")))


async def migrate_intake_uploads_to_vault(client_id: str) -> dict:
    """
    Find CLEAN intake uploads for this client's intake session and copy them into
    the client's document vault, creating Document records. Idempotent.
    Returns {"migrated": count, "skipped": count of already-migrated in session, "errors": []}.
    """
    db = database.get_db()
    client = await db.clients.find_one(
        {"client_id": client_id},
        {"_id": 0, "intake_session_id": 1},
    )
    if not client or not client.get("intake_session_id"):
        return {"migrated": 0, "skipped": 0, "errors": []}

    intake_session_id = client["intake_session_id"]
    skipped = await db.intake_uploads.count_documents(
        {"intake_session_id": intake_session_id, "status": IntakeUploadStatus.MIGRATED.value}
    )
    # Only CLEAN and not already migrated (support legacy scan_status)
    uploads = await db.intake_uploads.find(
        {
            "intake_session_id": intake_session_id,
            "$and": [
                {"$or": [{"status": IntakeUploadStatus.CLEAN.value}, {"scan_status": "CLEAN"}]},
                {"$or": [{"migrated_to_document_id": None}, {"migrated_to_document_id": {"$exists": False}}]},
                {"$or": [{"status": {"$exists": False}}, {"status": {"$nin": [IntakeUploadStatus.QUARANTINED.value, IntakeUploadStatus.MIGRATED.value]}}]},
            ],
        },
        {"_id": 0},
    ).to_list(500)

    # property_id only when explicitly provided by intake data; else client-level (None)
    DOCUMENT_STORAGE_PATH.mkdir(parents=True, exist_ok=True)
    dest_dir = DOCUMENT_STORAGE_PATH / client_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    migrated = 0
    errors = []

    for upload in uploads:
        upload_id = upload.get("upload_id")
        storage_path = upload.get("storage_path")
        if not storage_path or not os.path.isfile(storage_path):
            errors.append(f"Upload {upload_id}: file not found at {storage_path}")
            continue
        original_filename = upload.get("original_filename", "document")
        ext = Path(original_filename).suffix or ""
        if not ext or ext.lower() not in {".pdf", ".jpg", ".jpeg", ".png", ".docx"}:
            ext = ".bin"
        unique_name = f"{uuid.uuid4().hex}{ext}"
        dest_path = dest_dir / unique_name
        try:
            shutil.copy2(storage_path, dest_path)
        except Exception as e:
            errors.append(f"Upload {upload_id}: copy failed: {e}")
            continue
        file_size = os.path.getsize(dest_path)
        document_id = str(uuid.uuid4())
        # Only set property_id when explicitly provided (e.g. from intake mapping); else client-level
        property_id = upload.get("property_id") or None
        doc = Document(
            document_id=document_id,
            client_id=client_id,
            property_id=property_id,
            file_name=original_filename,
            file_path=str(dest_path),
            file_size=file_size,
            mime_type=upload.get("content_type", "application/octet-stream"),
            status=DocumentStatus.PENDING,
            uploaded_by="INTAKE_MIGRATION",
            manual_review_flag=True,
        )
        doc_dict = doc.model_dump()
        doc_dict["uploaded_at"] = doc_dict["uploaded_at"].isoformat() if hasattr(doc_dict["uploaded_at"], "isoformat") else doc_dict["uploaded_at"]
        await db.documents.insert_one(doc_dict)
        now = datetime.now(timezone.utc).isoformat()
        await db.intake_uploads.update_one(
            {"upload_id": upload_id},
            {
                "$set": {
                    "status": IntakeUploadStatus.MIGRATED.value,
                    "migrated_to_document_id": document_id,
                    "migrated_at": now,
                }
            },
        )
        migrated += 1
        logger.info(f"Migrated intake upload {upload_id} -> document {document_id} for client {client_id}")

    return {"migrated": migrated, "skipped": skipped, "errors": errors}
