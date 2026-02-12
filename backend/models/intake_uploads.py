"""
Intake Uploads - Temporary document storage during intake (Preferences & Consents step).
Files are stored separately from final document vault.
Scanned with ClamAV; CLEAN files are migrated to Documents after successful payment + provisioning.
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4


class IntakeUploadStatus(str, Enum):
    """Status of intake upload file."""
    UPLOADED = "UPLOADED"    # Just saved, scan not yet run
    SCANNING = "SCANNING"    # Scan in progress
    CLEAN = "CLEAN"          # Scan passed
    QUARANTINED = "QUARANTINED"  # Virus or scan failure; file moved to quarantine
    FAILED = "FAILED"        # Scan or processing error
    MIGRATED = "MIGRATED"    # Moved to permanent vault


class IntakeUpload(BaseModel):
    """Temporary upload during intake process."""
    upload_id: str = Field(default_factory=lambda: str(uuid4()))
    intake_session_id: str  # Links to intake session (stored on client at submit)
    client_id: Optional[str] = None  # Set when client is known (after submit)

    # File info
    filename: str           # Safe storage filename
    original_filename: str
    file_size: int  # bytes
    content_type: str
    storage_path: str       # Path on disk (or quarantine path if QUARANTINED)

    # Status (authoritative)
    status: str = IntakeUploadStatus.UPLOADED.value
    scan_error: Optional[str] = None  # If QUARANTINED/FAILED, reason

    # Migration
    migrated_to_document_id: Optional[str] = None
    migrated_at: Optional[datetime] = None

    # Metadata
    uploaded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    uploaded_by_email: Optional[str] = None

    class Config:
        use_enum_values = True
