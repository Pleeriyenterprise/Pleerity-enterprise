"""Agreement management domain models (CVP service agreements — not legal_content)."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

# Mongo collection names (single source of truth)
COL_AGREEMENT_TEMPLATES = "agreement_templates"
COL_AGREEMENT_TEMPLATE_VERSIONS = "agreement_template_versions"
COL_AGREEMENT_ACCEPTANCES = "agreement_acceptances"
COL_ISSUED_AGREEMENTS = "issued_agreements"
COL_SYSTEM_DOCUMENT_SETTINGS = "system_document_settings"

GRIDFS_AGREEMENT_BUCKET = "agreement_files"

DEFAULT_TEMPLATE_CODE = "property_compliance_management_agreement"


class AgreementTemplateStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class AgreementVersionStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"


class AgreementAcceptanceStatus(str, Enum):
    RECORDED = "recorded"
    CHECKOUT_SESSION_CREATED = "checkout_session_created"
    PAYMENT_COMPLETED = "payment_completed"


class IssuedAgreementOutcome(str, Enum):
    ISSUED = "issued"
    ISSUANCE_FAILED = "issuance_failed"


class ContentBlock(BaseModel):
    model_config = {"extra": "ignore"}

    key: str
    label: str
    type: str = "rich_text"
    required: bool = True
    order: int = 0
    content: str = ""
    enabled: bool = True


class AgreementCurrentPublishedResponse(BaseModel):
    template_id: str
    template_code: str
    template_version_id: str
    version_number: int
    title: str
    subtitle: Optional[str] = None
    content_blocks: List[Dict[str, Any]] = Field(default_factory=list)
    document_structure: Optional[Dict[str, Any]] = None
    published_at: Optional[str] = None
    effective_from: Optional[str] = None
    acceptance_text_required: str


class AgreementAcceptanceCreateBody(BaseModel):
    client_id: str
    """Must match clients.intake_session_id for this client (same value used at intake submit)."""
    intake_session_id: str = Field(..., min_length=1)
    template_code: str = DEFAULT_TEMPLATE_CODE
    acceptance_text_snapshot: str = Field(..., min_length=1)
    accepted_by_name: str = Field(..., min_length=1)
    accepted_by_email: str = Field(..., min_length=3)
    document_submission_method: Optional[str] = None
    assisted_upload_consent_accepted: Optional[bool] = None
    assisted_upload_consent_timestamp: Optional[str] = None
    rendered_agreement_hash: Optional[str] = None
    rendered_agreement_snapshot: Optional[Dict[str, Any]] = None
    invite_code: Optional[str] = Field(default=None, max_length=64)
    invite_entry_channel: str = Field(
        default="manual",
        max_length=16,
        description="manual | link - keeps agreement commercial truth aligned with pilot checkout.",
    )

    @field_validator("invite_entry_channel")
    @classmethod
    def _invite_entry_ch(cls, v: Any) -> str:
        e = str(v or "manual").strip().lower()
        return e if e in ("manual", "link") else "manual"


class IntakeCheckoutBody(BaseModel):
    acceptance_id: str = Field(..., min_length=1)
    invite_code: Optional[str] = Field(default=None, max_length=64)
    invite_entry_channel: str = Field(
        default="manual",
        max_length=16,
        description="manual | link — must match how the user obtained the code (link skips is_publicly_enterable).",
    )

    @field_validator("invite_entry_channel")
    @classmethod
    def _invite_entry_ch(cls, v: Any) -> str:
        e = str(v or "manual").strip().lower()
        return e if e in ("manual", "link") else "manual"
