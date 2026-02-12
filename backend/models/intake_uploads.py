"""
Intake Uploads - Temporary document storage during intake
Files are stored separately from final document vault
Migrated to Documents collection after successful payment + provisioning
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4


class IntakeUploadStatus(str, Enum):
    """Status of intake upload file."""
    PENDING = "PENDING"
    CLEAN = "CLEAN"
    QUARANTINED = "QUARANTINED"
    SKIPPED = "SKIPPED"  # No scan performed
    MIGRATED = "MIGRATED"  # Moved to permanent vault


class IntakeUpload(BaseModel):
    """Temporary upload during intake process."""
    upload_id: str = Field(default_factory=lambda: str(uuid4()))
    intake_session_id: str  # Links to intake draft
    
    # File info
    filename: str
    original_filename: str
    file_size: int  # bytes
    content_type: str
    storage_path: str
    
    # Security
    scan_status: IntakeUploadStatus = IntakeUploadStatus.SKIPPED
    scan_error: Optional[str] = None
    
    # Migration
    migrated_to_document_id: Optional[str] = None
    migrated_at: Optional[datetime] = None
    
    # Metadata
    uploaded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    uploaded_by_email: Optional[str] = None
    
    class Config:
        use_enum_values = True
