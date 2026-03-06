"""
MongoDB models and schemas for the four services (AI automation, Market research,
Compliance services, Document packs). Used for validation and typed repositories.

Collection mapping (task name -> actual collection):
  services                 -> service_catalogue_v2
  intake_submissions       -> intake_drafts
  orders                   -> orders
  prompt_templates         -> prompt_templates
  generation_runs          -> generation_runs
  documents (generated)    -> document_pack_items + generated_documents (versioned; never overwrite)
  document_pack_definitions-> document_pack_definitions
  workflow_events          -> workflow_events
  deliveries               -> deliveries
  audit_logs               -> audit_logs (shared with CVP)

Rules: Orders are immutable (no hard delete). Documents are versioned (never overwrite).
Every state change should create a workflow_event. Every admin action should create an audit_log.

CVP: The shared audit_logs collection and CVP-specific documents collection
are not modified by these schemas.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, ConfigDict


# =============================================================================
# Enums (align with order_workflow and existing code)
# =============================================================================

class OrderStatus(str, Enum):
    CREATED = "CREATED"
    PAID = "PAID"
    QUEUED = "QUEUED"
    IN_PROGRESS = "IN_PROGRESS"
    DRAFT_READY = "DRAFT_READY"
    INTERNAL_REVIEW = "INTERNAL_REVIEW"
    REGEN_REQUESTED = "REGEN_REQUESTED"
    REGENERATING = "REGENERATING"
    CLIENT_INPUT_REQUIRED = "CLIENT_INPUT_REQUIRED"
    FINALISING = "FINALISING"
    DELIVERING = "DELIVERING"
    COMPLETED = "COMPLETED"
    DELIVERY_FAILED = "DELIVERY_FAILED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class DraftStatus(str, Enum):
    DRAFT = "DRAFT"
    READY_FOR_PAYMENT = "READY_FOR_PAYMENT"
    ABANDONED = "ABANDONED"
    CONVERTED = "CONVERTED"


# =============================================================================
# Services (collection: service_catalogue_v2)
# =============================================================================

class ServiceSchema(BaseModel):
    """Schema for service catalogue document. Collection: service_catalogue_v2."""
    model_config = ConfigDict(extra="allow")

    service_code: str = Field(..., description="Unique service code")
    service_name: str = ""
    description: str = ""
    category: str = Field(..., description="ai_automation | market_research | compliance | document_pack")
    active: bool = True
    display_order: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None  # Soft delete


# =============================================================================
# Intake submissions (collection: intake_drafts)
# =============================================================================

class IntakeDraftSchema(BaseModel):
    """Schema for intake draft. Collection: intake_drafts (task: intake_submissions)."""
    model_config = ConfigDict(extra="allow")

    draft_id: str = Field(..., description="Unique draft ID")
    draft_ref: str = Field(..., description="Human-readable ref e.g. INT-YYYYMMDD-0001")
    service_code: str = Field(...)
    category: str = ""
    status: str = Field(..., description="DRAFT | READY_FOR_PAYMENT | ABANDONED | CONVERTED")
    client_identity: Dict[str, Any] = Field(default_factory=dict)
    intake_payload: Dict[str, Any] = Field(default_factory=dict)
    intake_schema_version: str = "1.0"
    pricing_snapshot: Optional[Dict[str, Any]] = None
    selected_addons: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    deleted_at: Optional[datetime] = None  # Soft delete (e.g. abandoned cleanup)


# =============================================================================
# Orders (collection: orders) — immutable, no hard delete
# =============================================================================

class OrderSchema(BaseModel):
    """Schema for order. Collection: orders. Orders are immutable (no hard delete)."""
    model_config = ConfigDict(extra="allow")

    order_id: str = Field(...)
    order_ref: str = Field(..., description="PLE-YYYYMMDD-XXXX")
    source_draft_id: str = Field(...)
    source_draft_ref: Optional[str] = None
    service_code: str = Field(...)
    category: Optional[str] = None
    service_name: Optional[str] = None
    status: str = Field(..., description="PAID | QUEUED | IN_PROGRESS | ...")
    workflow_state: Optional[str] = None
    pricing_snapshot: Optional[Dict[str, Any]] = None
    pricing: Optional[Dict[str, Any]] = None  # stripe_payment_intent_id, stripe_checkout_session_id
    customer: Optional[Dict[str, Any]] = None
    intake_snapshot: Optional[Dict[str, Any]] = None
    client_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    paid_at: Optional[datetime] = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# =============================================================================
# Prompt templates (collection: prompt_templates)
# =============================================================================

class PromptTemplateSchema(BaseModel):
    """Schema for prompt template. Collection: prompt_templates."""
    model_config = ConfigDict(extra="allow")

    template_id: str = Field(...)
    service_code: str = Field(...)
    doc_type: str = Field(...)
    status: str = Field(..., description="active | inactive | draft")
    version: int = 1
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None  # Soft delete


# =============================================================================
# Generation runs (collection: generation_runs) — NEW
# =============================================================================

class GenerationRunStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class GenerationRunSchema(BaseModel):
    """Schema for a single LLM/generation run. Collection: generation_runs."""
    model_config = ConfigDict(extra="allow")

    run_id: str = Field(...)
    order_id: str = Field(...)
    template_id: Optional[str] = None
    doc_key: Optional[str] = None
    doc_type: Optional[str] = None
    status: str = Field(..., description="PENDING | RUNNING | COMPLETED | FAILED | CANCELLED")
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# =============================================================================
# Documents — pack items (collection: document_pack_items), versioned
# =============================================================================

class DocumentPackItemSchema(BaseModel):
    """Schema for a document pack item. Collection: document_pack_items. Versioned (never overwrite)."""
    model_config = ConfigDict(extra="allow")

    item_id: str = Field(...)
    order_id: str = Field(...)
    doc_key: str = Field(...)
    doc_type: str = Field(...)
    canonical_index: int = 0
    version: int = Field(1, description="Version number; new version = new doc or incremented")
    status: str = Field(..., description="PENDING | GENERATING | READY | FAILED")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# =============================================================================
# Generated documents (collection: generated_documents) — versioned, never overwrite
# =============================================================================

class GeneratedDocumentSchema(BaseModel):
    """Schema for a generated document (non-pack or unified). Versioned; never overwrite."""
    model_config = ConfigDict(extra="allow")

    document_id: str = Field(...)
    order_id: str = Field(...)
    run_id: Optional[str] = None
    doc_type: str = Field(...)
    version: int = Field(1, description="Increment for each new version; never overwrite")
    file_path: Optional[str] = None
    status: str = Field(..., description="PENDING | READY | FAILED")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# =============================================================================
# Document pack definitions (collection: document_pack_definitions) — NEW
# =============================================================================

class DocumentPackDefinitionSchema(BaseModel):
    """Schema for pack document definition. Collection: document_pack_definitions."""
    model_config = ConfigDict(extra="allow")

    doc_key: str = Field(...)
    doc_type: str = Field(...)
    pack_tier: str = Field(..., description="ESSENTIAL | PLUS | PRO")
    display_name: str = Field(...)
    canonical_index: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    deleted_at: Optional[datetime] = None  # Soft delete


# =============================================================================
# Workflow events (collection: workflow_events) — every state change
# =============================================================================

class WorkflowEventSchema(BaseModel):
    """Schema for order workflow state change. Collection: workflow_events."""
    model_config = ConfigDict(extra="allow")

    event_id: str = Field(...)
    order_id: str = Field(...)
    from_status: Optional[str] = None
    to_status: str = Field(...)
    transition_type: Optional[str] = None  # system | admin_manual | customer_action
    actor_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


# =============================================================================
# Deliveries (collection: deliveries) — delivery attempts
# =============================================================================

class DeliveryStatus(str, Enum):
    PENDING = "PENDING"
    SENT = "SENT"
    DELIVERED = "DELIVERED"
    FAILED = "FAILED"
    BOUNCED = "BOUNCED"


class DeliverySchema(BaseModel):
    """Schema for a delivery attempt (email, link, etc.). Collection: deliveries."""
    model_config = ConfigDict(extra="allow")

    delivery_id: str = Field(...)
    order_id: str = Field(...)
    channel: str = Field(..., description="email | download_link | postal")
    status: str = Field(..., description="PENDING | SENT | DELIVERED | FAILED | BOUNCED")
    recipient: Optional[str] = None
    provider_message_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None


# =============================================================================
# Audit logs (collection: audit_logs) — shared with CVP; every admin action
# =============================================================================

class AuditLogSchema(BaseModel):
    """Schema for audit log entry. Collection: audit_logs (shared with CVP)."""
    model_config = ConfigDict(extra="allow")

    audit_id: str = Field(...)
    action: str = Field(...)
    actor_id: Optional[str] = None
    actor_role: Optional[str] = None
    client_id: Optional[str] = None
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    before_state: Optional[Dict[str, Any]] = None
    after_state: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    reason_code: Optional[str] = None
    ip_address: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
