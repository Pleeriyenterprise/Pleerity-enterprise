"""ClearForm Document Models

Phase 1 Document Types:
1. Formal Letter - Professional correspondence
2. Complaint Letter - Issue resolution letters
3. CV/Resume - Professional CV generation

Intent-based flow: User describes what they need, AI generates.
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from enum import Enum
import uuid


class ClearFormDocumentType(str, Enum):
    """Phase 1 document types"""
    FORMAL_LETTER = "formal_letter"
    COMPLAINT_LETTER = "complaint_letter"
    CV_RESUME = "cv_resume"


class ClearFormDocumentStatus(str, Enum):
    """Document generation status"""
    PENDING = "PENDING"        # Queued for generation
    GENERATING = "GENERATING"  # AI processing
    COMPLETED = "COMPLETED"    # Ready for download
    FAILED = "FAILED"          # Generation failed
    ARCHIVED = "ARCHIVED"      # Moved to archive


class ClearFormDocument(BaseModel):
    """Generated document record.
    
    Documents are stored in the vault for user access.
    """
    document_id: str = Field(default_factory=lambda: f"CFD-{uuid.uuid4().hex[:12].upper()}")
    user_id: str
    
    # Document metadata
    document_type: ClearFormDocumentType
    title: str  # User-provided or AI-generated title
    description: Optional[str] = None
    
    # Generation status
    status: ClearFormDocumentStatus = ClearFormDocumentStatus.PENDING
    
    # Intent data (what user asked for)
    intent_data: Dict[str, Any] = Field(default_factory=dict)
    
    # Generated content
    content_markdown: Optional[str] = None  # Markdown version
    content_html: Optional[str] = None      # HTML version
    content_plain: Optional[str] = None     # Plain text
    
    # File outputs
    pdf_file_id: Optional[str] = None      # GridFS file ID
    docx_file_id: Optional[str] = None     # GridFS file ID
    
    # Credit tracking
    credits_used: int = 0
    credit_transaction_id: Optional[str] = None
    
    # AI metadata
    ai_model_used: Optional[str] = None
    ai_prompt_version: Optional[str] = None
    generation_time_ms: Optional[int] = None
    
    # Error tracking
    error_message: Optional[str] = None
    retry_count: int = 0
    
    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    
    # User organization
    tags: List[str] = Field(default_factory=list)
    folder: Optional[str] = None  # Future: folder organization
    
    model_config = {"extra": "ignore"}


class DocumentGenerationRequest(BaseModel):
    """Request to generate a document.
    
    Intent-based: User provides context, AI generates.
    """
    document_type: ClearFormDocumentType
    
    # Intent description
    intent: str = Field(description="What the user wants to achieve with this document")
    
    # Type-specific fields (structured data for better generation)
    # These vary by document type
    
    # For Formal Letter
    recipient_name: Optional[str] = None
    recipient_title: Optional[str] = None
    recipient_organization: Optional[str] = None
    sender_name: Optional[str] = None
    subject: Optional[str] = None
    tone: Optional[str] = None  # formal, semi-formal, friendly
    
    # For Complaint Letter
    company_name: Optional[str] = None
    issue_date: Optional[str] = None
    issue_description: Optional[str] = None
    desired_resolution: Optional[str] = None
    order_reference: Optional[str] = None
    
    # For CV/Resume
    full_name: Optional[str] = None
    job_title_target: Optional[str] = None
    years_experience: Optional[int] = None
    skills: Optional[List[str]] = None
    work_history: Optional[List[Dict[str, Any]]] = None
    education: Optional[List[Dict[str, Any]]] = None
    
    # Output preferences
    output_format: str = "pdf"  # pdf, docx, both
    
    model_config = {"extra": "ignore"}


class DocumentVaultItem(BaseModel):
    """Document listing item for vault display"""
    document_id: str
    document_type: ClearFormDocumentType
    title: str
    status: ClearFormDocumentStatus
    created_at: datetime
    completed_at: Optional[datetime] = None
    tags: List[str] = Field(default_factory=list)
    
    # Quick access
    has_pdf: bool = False
    has_docx: bool = False
    
    model_config = {"extra": "ignore"}


class DocumentVaultResponse(BaseModel):
    """Paginated vault response"""
    items: List[DocumentVaultItem]
    total: int
    page: int
    page_size: int
    has_more: bool


# ============================================================================
# Document Type Configurations
# ============================================================================

DOCUMENT_TYPE_CONFIG = {
    ClearFormDocumentType.FORMAL_LETTER: {
        "name": "Formal Letter",
        "description": "Professional correspondence for any occasion",
        "credit_cost": 1,
        "icon": "mail",
        "examples": [
            "Request for information",
            "Application letter",
            "Thank you letter",
            "Resignation letter",
        ],
        "required_fields": ["intent"],
        "optional_fields": ["recipient_name", "recipient_title", "recipient_organization", "sender_name", "subject", "tone"],
    },
    ClearFormDocumentType.COMPLAINT_LETTER: {
        "name": "Complaint Letter",
        "description": "Professional complaints to businesses and organizations",
        "credit_cost": 1,
        "icon": "alert-triangle",
        "examples": [
            "Product defect complaint",
            "Service issue complaint",
            "Billing dispute",
            "Delivery problem",
        ],
        "required_fields": ["intent", "company_name"],
        "optional_fields": ["issue_date", "issue_description", "desired_resolution", "order_reference"],
    },
    ClearFormDocumentType.CV_RESUME: {
        "name": "CV / Resume",
        "description": "Professional CV tailored to your target role",
        "credit_cost": 2,
        "icon": "file-text",
        "examples": [
            "Career change CV",
            "Graduate CV",
            "Executive resume",
            "Industry-specific CV",
        ],
        "required_fields": ["intent", "full_name"],
        "optional_fields": ["job_title_target", "years_experience", "skills", "work_history", "education"],
    },
}
