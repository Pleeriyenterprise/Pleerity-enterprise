"""ClearForm Document Type Configuration Models

Admin-configurable document types system.
Types can be added/modified without code changes.
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from enum import Enum
import uuid


class DocumentCategory(str, Enum):
    """Document categories"""
    EXPLAIN_APPEAL_REQUEST = "EXPLAIN_APPEAL_REQUEST"
    INTRODUCE_SUPPORT = "INTRODUCE_SUPPORT"
    NOTIFY_DECLARE_AUTHORISE = "NOTIFY_DECLARE_AUTHORISE"


class FieldType(str, Enum):
    """Field input types"""
    TEXT = "text"
    TEXTAREA = "textarea"
    DATE = "date"
    NUMBER = "number"
    EMAIL = "email"
    SELECT = "select"
    MULTISELECT = "multiselect"


class DocumentTypeField(BaseModel):
    """Field definition for document type"""
    field_code: str
    label: str
    field_type: FieldType = FieldType.TEXT
    required: bool = False
    placeholder: Optional[str] = None
    help_text: Optional[str] = None
    options: Optional[List[str]] = None  # For select/multiselect
    validation_regex: Optional[str] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    order: int = 0


class DocumentCategoryConfig(BaseModel):
    """Category configuration"""
    category_id: str = Field(default_factory=lambda: f"CAT-{uuid.uuid4().hex[:8].upper()}")
    code: DocumentCategory
    name: str
    description: str
    tone: str  # e.g., "calm, factual, respectful"
    shared_validations: List[str] = Field(default_factory=list)
    system_prompt_additions: Optional[str] = None
    
    # Admin metadata
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    model_config = {"extra": "ignore"}


class DocumentTypeConfig(BaseModel):
    """Admin-configurable document type"""
    type_id: str = Field(default_factory=lambda: f"DT-{uuid.uuid4().hex[:8].upper()}")
    code: str  # e.g., "COMPLAINT_APPEAL_LETTER"
    name: str  # Display name
    category: DocumentCategory
    description: str
    
    # Credit cost
    credit_cost: int = 1
    
    # Icon (lucide icon name)
    icon: str = "file-text"
    
    # Fields
    required_fields: List[DocumentTypeField] = Field(default_factory=list)
    optional_fields: List[DocumentTypeField] = Field(default_factory=list)
    
    # AI Generation config
    system_prompt: Optional[str] = None
    example_outputs: List[str] = Field(default_factory=list)
    
    # Display
    examples: List[str] = Field(default_factory=list)  # Use case examples
    
    # Status
    is_active: bool = True
    is_featured: bool = False
    display_order: int = 0
    
    # Admin metadata
    created_by: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    model_config = {"extra": "ignore"}


class DocumentTemplate(BaseModel):
    """User-saved document template (reusable intent)"""
    template_id: str = Field(default_factory=lambda: f"TPL-{uuid.uuid4().hex[:8].upper()}")
    user_id: str
    workspace_id: Optional[str] = None  # For workspace-level templates
    
    # Template info
    name: str
    description: Optional[str] = None
    document_type_code: str
    
    # Saved field values
    saved_fields: Dict[str, Any] = Field(default_factory=dict)
    saved_intent: Optional[str] = None
    
    # Usage tracking
    use_count: int = 0
    last_used_at: Optional[datetime] = None
    
    # Metadata
    is_favorite: bool = False
    tags: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    model_config = {"extra": "ignore"}


# ============================================================================
# Default Category Configurations
# ============================================================================

DEFAULT_CATEGORIES = [
    DocumentCategoryConfig(
        code=DocumentCategory.EXPLAIN_APPEAL_REQUEST,
        name="Explain, Appeal & Request",
        description="Documents where a user explains a situation, makes a complaint, appeals a decision, or formally requests action.",
        tone="calm, factual, respectful",
        shared_validations=["required_recipient", "required_issue_description", "no_emotional_language", "timeline_consistency"],
        system_prompt_additions="Maintain a calm, factual, and respectful tone throughout. Avoid emotional language. Ensure all dates and timelines are consistent.",
    ),
    DocumentCategoryConfig(
        code=DocumentCategory.INTRODUCE_SUPPORT,
        name="Introduce & Support",
        description="Documents that introduce a request or provide supporting narrative for an application, evidence, or person.",
        tone="professional, supportive, neutral",
        shared_validations=["required_context", "supporting_facts_present", "no_guarantee_language"],
        system_prompt_additions="Be professional and supportive. Present facts clearly without making guarantees or promises. Provide context for any claims made.",
    ),
    DocumentCategoryConfig(
        code=DocumentCategory.NOTIFY_DECLARE_AUTHORISE,
        name="Notify, Declare & Authorise",
        description="Documents that notify another party, make a declaration, or authorise an action.",
        tone="clear, direct, professional",
        shared_validations=["required_notice_reason", "date_present", "sender_identity_present"],
        system_prompt_additions="Be clear and direct. Include specific dates and clear identification of the sender. State the purpose explicitly.",
    ),
]


# ============================================================================
# Default Document Type Configurations
# ============================================================================

DEFAULT_DOCUMENT_TYPES = [
    # Category: EXPLAIN_APPEAL_REQUEST
    DocumentTypeConfig(
        code="COMPLAINT_APPEAL_LETTER",
        name="Complaint or Appeal Letter",
        category=DocumentCategory.EXPLAIN_APPEAL_REQUEST,
        description="A formal letter to raise a complaint or appeal a decision with an organisation or authority.",
        credit_cost=1,
        icon="alert-triangle",
        required_fields=[
            DocumentTypeField(field_code="recipient_name", label="Recipient Name", required=True, placeholder="Customer Service Manager", order=1),
            DocumentTypeField(field_code="issue_summary", label="Issue Summary", field_type=FieldType.TEXTAREA, required=True, placeholder="Brief summary of your complaint or appeal", order=2),
            DocumentTypeField(field_code="relevant_dates", label="Relevant Dates", required=True, placeholder="e.g., January 15, 2026", order=3),
            DocumentTypeField(field_code="desired_outcome", label="Desired Outcome", required=True, placeholder="What resolution are you seeking?", order=4),
        ],
        optional_fields=[
            DocumentTypeField(field_code="reference_numbers", label="Reference Numbers", placeholder="Order #, Case #, etc.", order=5),
            DocumentTypeField(field_code="previous_contact_details", label="Previous Contact Details", field_type=FieldType.TEXTAREA, placeholder="Details of any previous communications", order=6),
        ],
        examples=["Product defect complaint", "Service issue appeal", "Billing dispute", "Insurance claim appeal"],
    ),
    DocumentTypeConfig(
        code="STATEMENT_OF_CIRCUMSTANCES",
        name="Statement of Circumstances",
        category=DocumentCategory.EXPLAIN_APPEAL_REQUEST,
        description="A clear explanation of personal or situational circumstances written in a professional and factual tone.",
        credit_cost=1,
        icon="file-text",
        required_fields=[
            DocumentTypeField(field_code="situation_description", label="Situation Description", field_type=FieldType.TEXTAREA, required=True, placeholder="Describe your circumstances clearly and factually", order=1),
            DocumentTypeField(field_code="relevant_dates", label="Relevant Dates", required=True, placeholder="Key dates related to your situation", order=2),
        ],
        optional_fields=[
            DocumentTypeField(field_code="supporting_context", label="Supporting Context", field_type=FieldType.TEXTAREA, placeholder="Additional background information", order=3),
            DocumentTypeField(field_code="impact_explanation", label="Impact Explanation", field_type=FieldType.TEXTAREA, placeholder="How has this situation affected you?", order=4),
        ],
        examples=["Housing application statement", "Benefits appeal statement", "Immigration circumstances", "Academic extenuating circumstances"],
    ),
    
    # Category: INTRODUCE_SUPPORT
    DocumentTypeConfig(
        code="APPLICATION_COVER_LETTER",
        name="Application Cover Letter",
        category=DocumentCategory.INTRODUCE_SUPPORT,
        description="A professional cover letter to accompany an application for housing, education, grants, or services.",
        credit_cost=1,
        icon="mail",
        required_fields=[
            DocumentTypeField(field_code="application_purpose", label="Application Purpose", required=True, placeholder="What are you applying for?", order=1),
            DocumentTypeField(field_code="applicant_details", label="Your Details", field_type=FieldType.TEXTAREA, required=True, placeholder="Your name, background, and relevant qualifications", order=2),
        ],
        optional_fields=[
            DocumentTypeField(field_code="supporting_background", label="Supporting Background", field_type=FieldType.TEXTAREA, placeholder="Additional experience or qualifications", order=3),
            DocumentTypeField(field_code="reference_information", label="Reference Information", placeholder="Names of referees or reference numbers", order=4),
        ],
        examples=["Job application cover letter", "University application", "Grant application", "Housing application"],
    ),
    DocumentTypeConfig(
        code="REFERENCE_LETTER",
        name="Reference Letter",
        category=DocumentCategory.INTRODUCE_SUPPORT,
        description="A professional reference letter written on behalf of an individual for work, housing, or other purposes.",
        credit_cost=2,
        icon="users",
        required_fields=[
            DocumentTypeField(field_code="subject_name", label="Person's Name", required=True, placeholder="Name of the person you're recommending", order=1),
            DocumentTypeField(field_code="relationship_to_subject", label="Your Relationship", required=True, placeholder="e.g., Line Manager, Landlord, Professor", order=2),
            DocumentTypeField(field_code="reference_purpose", label="Purpose of Reference", required=True, placeholder="What is this reference for?", order=3),
        ],
        optional_fields=[
            DocumentTypeField(field_code="duration_of_relationship", label="Duration of Relationship", placeholder="How long have you known them?", order=4),
            DocumentTypeField(field_code="specific_qualities", label="Specific Qualities", field_type=FieldType.TEXTAREA, placeholder="Key qualities or achievements to highlight", order=5),
            DocumentTypeField(field_code="contact_details", label="Your Contact Details", placeholder="For verification purposes", order=6),
        ],
        examples=["Employment reference", "Landlord reference", "Academic reference", "Character reference"],
    ),
    
    # Category: NOTIFY_DECLARE_AUTHORISE
    DocumentTypeConfig(
        code="NOTICE_TO_LANDLORD",
        name="Notice to Landlord",
        category=DocumentCategory.NOTIFY_DECLARE_AUTHORISE,
        description="A formal notice to a landlord or property manager regarding repairs, complaints, or tenancy matters.",
        credit_cost=1,
        icon="home",
        required_fields=[
            DocumentTypeField(field_code="property_address", label="Property Address", field_type=FieldType.TEXTAREA, required=True, placeholder="Full address of the property", order=1),
            DocumentTypeField(field_code="notice_reason", label="Reason for Notice", field_type=FieldType.TEXTAREA, required=True, placeholder="What is this notice about?", order=2),
            DocumentTypeField(field_code="notice_date", label="Date of Notice", field_type=FieldType.DATE, required=True, order=3),
        ],
        optional_fields=[
            DocumentTypeField(field_code="tenancy_reference", label="Tenancy Reference", placeholder="Tenancy agreement reference number", order=4),
            DocumentTypeField(field_code="previous_communications", label="Previous Communications", field_type=FieldType.TEXTAREA, placeholder="Previous attempts to resolve this matter", order=5),
        ],
        examples=["Repair request notice", "Notice to quit", "Rent dispute notice", "Deposit return request"],
    ),
    
    # Keep original types for backwards compatibility
    DocumentTypeConfig(
        code="formal_letter",
        name="Formal Letter",
        category=DocumentCategory.NOTIFY_DECLARE_AUTHORISE,
        description="Professional correspondence for any occasion",
        credit_cost=1,
        icon="mail",
        required_fields=[
            DocumentTypeField(field_code="intent", label="What is this letter for?", field_type=FieldType.TEXTAREA, required=True, placeholder="Describe your purpose clearly", order=1),
        ],
        optional_fields=[
            DocumentTypeField(field_code="recipient_name", label="Recipient Name", placeholder="John Doe", order=2),
            DocumentTypeField(field_code="recipient_organization", label="Organization", placeholder="ABC Company", order=3),
            DocumentTypeField(field_code="sender_name", label="Your Name", placeholder="Jane Smith", order=4),
            DocumentTypeField(field_code="subject", label="Subject", placeholder="Subject line", order=5),
        ],
        examples=["Request for information", "Application letter", "Thank you letter", "Resignation letter"],
        display_order=1,
    ),
    DocumentTypeConfig(
        code="complaint_letter",
        name="Complaint Letter",
        category=DocumentCategory.EXPLAIN_APPEAL_REQUEST,
        description="Professional complaints to businesses and organizations",
        credit_cost=1,
        icon="alert-triangle",
        required_fields=[
            DocumentTypeField(field_code="intent", label="What is your complaint about?", field_type=FieldType.TEXTAREA, required=True, placeholder="Describe the issue clearly", order=1),
            DocumentTypeField(field_code="company_name", label="Company Name", required=True, placeholder="TechStore Ltd", order=2),
        ],
        optional_fields=[
            DocumentTypeField(field_code="issue_date", label="Issue Date", placeholder="January 15, 2026", order=3),
            DocumentTypeField(field_code="desired_resolution", label="Desired Resolution", placeholder="Full refund", order=4),
            DocumentTypeField(field_code="order_reference", label="Order Reference", placeholder="ORD-12345", order=5),
        ],
        examples=["Product defect", "Service issue", "Billing dispute", "Delivery problem"],
        display_order=2,
    ),
    DocumentTypeConfig(
        code="cv_resume",
        name="CV / Resume",
        category=DocumentCategory.INTRODUCE_SUPPORT,
        description="Professional CV tailored to your target role",
        credit_cost=2,
        icon="file-user",
        required_fields=[
            DocumentTypeField(field_code="intent", label="Career objective", field_type=FieldType.TEXTAREA, required=True, placeholder="What role are you targeting?", order=1),
            DocumentTypeField(field_code="full_name", label="Full Name", required=True, placeholder="John Smith", order=2),
        ],
        optional_fields=[
            DocumentTypeField(field_code="job_title_target", label="Target Role", placeholder="Senior Software Engineer", order=3),
            DocumentTypeField(field_code="years_experience", label="Years of Experience", field_type=FieldType.NUMBER, placeholder="5", order=4),
            DocumentTypeField(field_code="skills", label="Key Skills", placeholder="Python, JavaScript, Leadership", order=5),
        ],
        examples=["Career change CV", "Graduate CV", "Executive resume", "Industry-specific CV"],
        display_order=3,
    ),
]
