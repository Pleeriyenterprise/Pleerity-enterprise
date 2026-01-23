"""
Enterprise Prompt Manager - Database Models & Pydantic Schemas

This module defines the data models for the Prompt Management System.
Key features:
- Prompt versioning with Draft -> Tested -> Active lifecycle
- Single {{INPUT_DATA_JSON}} injection pattern
- Schema validation for LLM outputs
- Full audit trail

NON-NEGOTIABLES:
- Never overwrite active history
- prompt_version_used stored permanently on documents
- Schema validation required before Test Passed and Activation
- Full audit log: who, what changed, when, evidence
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from enum import Enum
import re


# ============================================
# Prompt Status Lifecycle
# ============================================

class PromptStatus(str, Enum):
    """
    Prompt lifecycle status - enforces Draft -> Tested -> Active flow.
    
    DRAFT: Editable, not used in production
    TESTED: Has passed validation tests, awaiting activation
    ACTIVE: Currently in use for document generation
    DEPRECATED: Replaced by newer version, kept for audit
    ARCHIVED: Manually archived, not visible in normal views
    """
    DRAFT = "DRAFT"
    TESTED = "TESTED"
    ACTIVE = "ACTIVE"
    DEPRECATED = "DEPRECATED"
    ARCHIVED = "ARCHIVED"


class PromptTestStatus(str, Enum):
    """Test execution status for Prompt Playground."""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PASSED = "PASSED"
    FAILED = "FAILED"


# ============================================
# Output Schema Definition
# ============================================

class OutputSchemaField(BaseModel):
    """Definition of a single field in the output schema."""
    field_name: str = Field(..., min_length=1, max_length=100)
    field_type: Literal["string", "number", "boolean", "array", "object"] = "string"
    description: Optional[str] = None
    required: bool = True
    # For nested objects/arrays
    nested_fields: Optional[List["OutputSchemaField"]] = None
    # For arrays, the item type
    array_item_type: Optional[Literal["string", "number", "boolean", "object"]] = None


class OutputSchema(BaseModel):
    """
    Schema definition for validating LLM output.
    
    Schema validation is REQUIRED before:
    - Marking a test as PASSED
    - Activating a prompt version
    """
    schema_version: str = "1.0"
    root_type: Literal["object", "array"] = "object"
    fields: List[OutputSchemaField] = []
    strict_validation: bool = True  # Fail if extra fields present
    
    def to_json_schema(self) -> Dict[str, Any]:
        """Convert to JSON Schema format for validation."""
        def field_to_schema(f: OutputSchemaField) -> Dict[str, Any]:
            schema = {"type": f.field_type}
            if f.description:
                schema["description"] = f.description
            if f.field_type == "array" and f.array_item_type:
                if f.array_item_type == "object" and f.nested_fields:
                    schema["items"] = {
                        "type": "object",
                        "properties": {
                            nf.field_name: field_to_schema(nf)
                            for nf in f.nested_fields
                        }
                    }
                else:
                    schema["items"] = {"type": f.array_item_type}
            elif f.field_type == "object" and f.nested_fields:
                schema["properties"] = {
                    nf.field_name: field_to_schema(nf)
                    for nf in f.nested_fields
                }
            return schema
        
        properties = {f.field_name: field_to_schema(f) for f in self.fields}
        required = [f.field_name for f in self.fields if f.required]
        
        return {
            "type": self.root_type,
            "properties": properties,
            "required": required,
            "additionalProperties": not self.strict_validation
        }


# ============================================
# Prompt Template Model
# ============================================

class PromptTemplateCreate(BaseModel):
    """Create a new prompt template (creates as DRAFT)."""
    service_code: str = Field(..., min_length=1, max_length=50, description="Service code this prompt belongs to")
    doc_type: str = Field(..., min_length=1, max_length=100, description="Document type identifier")
    name: str = Field(..., min_length=1, max_length=200, description="Human-readable prompt name")
    description: Optional[str] = Field(None, max_length=1000)
    
    # The prompts - using single {{INPUT_DATA_JSON}} injection pattern
    system_prompt: str = Field(..., min_length=10, description="System prompt for the LLM")
    user_prompt_template: str = Field(
        ..., 
        min_length=10,
        description="User prompt template. Must contain {{INPUT_DATA_JSON}} placeholder."
    )
    
    # Output schema for validation
    output_schema: OutputSchema
    
    # LLM Configuration
    temperature: float = Field(default=0.3, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4000, ge=100, le=32000)
    
    # Metadata
    tags: List[str] = []
    
    @field_validator('user_prompt_template')
    @classmethod
    def validate_injection_pattern(cls, v: str) -> str:
        """Ensure user_prompt_template contains the required {{INPUT_DATA_JSON}} block."""
        if '{{INPUT_DATA_JSON}}' not in v:
            raise ValueError(
                "user_prompt_template MUST contain exactly one {{INPUT_DATA_JSON}} placeholder. "
                "This is the single injection point for runtime data."
            )
        # Ensure no scattered placeholders (legacy pattern)
        scattered_pattern = r'\{[a-z_]+\}'
        matches = re.findall(scattered_pattern, v)
        if matches:
            raise ValueError(
                f"Scattered placeholders detected: {matches}. "
                "Use the single {{INPUT_DATA_JSON}} pattern only."
            )
        return v


class PromptTemplateUpdate(BaseModel):
    """
    Update a prompt template.
    
    NOTE: Updates create a NEW VERSION if the prompt is not in DRAFT status.
    Active prompts are never overwritten - they get DEPRECATED when a new version activates.
    """
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    system_prompt: Optional[str] = Field(None, min_length=10)
    user_prompt_template: Optional[str] = Field(None, min_length=10)
    output_schema: Optional[OutputSchema] = None
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, ge=100, le=32000)
    tags: Optional[List[str]] = None
    
    @field_validator('user_prompt_template')
    @classmethod
    def validate_injection_pattern(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if '{{INPUT_DATA_JSON}}' not in v:
            raise ValueError(
                "user_prompt_template MUST contain exactly one {{INPUT_DATA_JSON}} placeholder."
            )
        scattered_pattern = r'\{[a-z_]+\}'
        matches = re.findall(scattered_pattern, v)
        if matches:
            raise ValueError(f"Scattered placeholders detected: {matches}.")
        return v


class PromptTemplateResponse(BaseModel):
    """Response model for prompt template."""
    template_id: str
    service_code: str
    doc_type: str
    name: str
    description: Optional[str]
    version: int
    status: PromptStatus
    
    system_prompt: str
    user_prompt_template: str
    output_schema: Dict[str, Any]
    
    temperature: float
    max_tokens: int
    tags: List[str]
    
    # Test status
    last_test_status: Optional[PromptTestStatus] = None
    last_test_at: Optional[str] = None
    test_count: int = 0
    
    # Audit fields
    created_at: str
    created_by: str
    updated_at: Optional[str] = None
    updated_by: Optional[str] = None
    activated_at: Optional[str] = None
    activated_by: Optional[str] = None
    deprecated_at: Optional[str] = None
    deprecated_by: Optional[str] = None


# ============================================
# Prompt Test Models (Playground)
# ============================================

class PromptTestRequest(BaseModel):
    """Request to test a prompt in the Playground."""
    template_id: str = Field(..., description="Template ID to test")
    test_input_data: Dict[str, Any] = Field(
        ..., 
        description="Test input data - will be injected as INPUT_DATA_JSON"
    )
    # Optional override for testing different configurations
    temperature_override: Optional[float] = Field(None, ge=0.0, le=2.0)
    max_tokens_override: Optional[int] = Field(None, ge=100, le=32000)


class PromptTestResult(BaseModel):
    """Result of a prompt test execution."""
    test_id: str
    template_id: str
    template_version: int
    status: PromptTestStatus
    
    # Input used
    input_data: Dict[str, Any]
    rendered_user_prompt: str  # The actual prompt sent to LLM
    
    # Output
    raw_output: Optional[str] = None
    parsed_output: Optional[Dict[str, Any]] = None
    
    # Validation results
    schema_validation_passed: bool = False
    schema_validation_errors: List[str] = []
    
    # Metrics
    execution_time_ms: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    
    # Error handling
    error_message: Optional[str] = None
    
    # Audit
    executed_at: str
    executed_by: str


# ============================================
# Prompt Activation Models
# ============================================

class PromptActivationRequest(BaseModel):
    """Request to activate a tested prompt version."""
    template_id: str = Field(..., description="Template ID to activate")
    activation_reason: str = Field(
        ..., 
        min_length=10, 
        max_length=500,
        description="Reason for activation (for audit trail)"
    )


class PromptActivationResponse(BaseModel):
    """Response after prompt activation."""
    success: bool
    template_id: str
    new_version: int
    status: PromptStatus
    previous_active_version: Optional[int] = None
    message: str
    activated_at: str
    activated_by: str


# ============================================
# Audit Log Models
# ============================================

class PromptAuditAction(str, Enum):
    """Actions logged in the audit trail."""
    CREATED = "CREATED"
    UPDATED = "UPDATED"
    TESTED = "TESTED"
    TEST_PASSED = "TEST_PASSED"
    TEST_FAILED = "TEST_FAILED"
    ACTIVATED = "ACTIVATED"
    DEPRECATED = "DEPRECATED"
    ARCHIVED = "ARCHIVED"
    RESTORED = "RESTORED"


class PromptAuditLogEntry(BaseModel):
    """Single entry in the prompt audit log."""
    audit_id: str
    template_id: str
    version: int
    action: PromptAuditAction
    
    # Change details
    changes_summary: str
    changes_detail: Optional[Dict[str, Any]] = None  # Field-level changes
    
    # Test evidence (for TEST_PASSED/TEST_FAILED)
    test_id: Optional[str] = None
    test_result_snapshot: Optional[Dict[str, Any]] = None
    
    # Activation evidence
    activation_reason: Optional[str] = None
    previous_active_version: Optional[int] = None
    
    # Audit metadata
    performed_by: str
    performed_at: str
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


# ============================================
# Version History Models
# ============================================

class PromptVersionSummary(BaseModel):
    """Summary of a prompt version for history views."""
    template_id: str
    version: int
    status: PromptStatus
    name: str
    
    created_at: str
    created_by: str
    
    # Status transition dates
    tested_at: Optional[str] = None
    activated_at: Optional[str] = None
    deprecated_at: Optional[str] = None
    
    # Test summary
    test_count: int = 0
    last_test_passed: bool = False


class PromptVersionHistory(BaseModel):
    """Full version history for a prompt template."""
    service_code: str
    doc_type: str
    current_active_version: Optional[int] = None
    versions: List[PromptVersionSummary] = []
    total_versions: int = 0


# ============================================
# List/Filter Models
# ============================================

class PromptListFilters(BaseModel):
    """Filters for listing prompts."""
    service_code: Optional[str] = None
    doc_type: Optional[str] = None
    status: Optional[List[PromptStatus]] = None
    tags: Optional[List[str]] = None
    search: Optional[str] = None  # Search in name/description
    
    # Pagination
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class PromptListResponse(BaseModel):
    """Response for listing prompts."""
    prompts: List[PromptTemplateResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
