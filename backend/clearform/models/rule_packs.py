"""ClearForm Rule Packs & Templates

Phase D: Compliance Rule Packs and Deterministic Document Generation

Rule Packs:
- Pre-defined document structures with required sections
- Compliance rules and validation
- Industry-standard templates

Templates:
- Deterministic generation with placeholders
- Faster than AI for structured documents
- Hybrid mode: Templates + AI enhancement
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from enum import Enum
import uuid


class RulePackCategory(str, Enum):
    """Categories for rule packs"""
    EMPLOYMENT = "employment"
    BUSINESS = "business"
    PERSONAL = "personal"
    LEGAL = "legal"
    PROPERTY = "property"


class GenerationMode(str, Enum):
    """Document generation modes"""
    AI_FULL = "ai_full"           # Full AI generation (current)
    TEMPLATE_ONLY = "template"     # Pure template fill
    HYBRID = "hybrid"              # Template structure + AI enhancement


class ValidationSeverity(str, Enum):
    """Validation rule severity"""
    ERROR = "error"       # Must be fixed
    WARNING = "warning"   # Should be reviewed
    INFO = "info"         # Informational


class SectionType(str, Enum):
    """Section types for templates"""
    HEADER = "header"
    ADDRESS = "address"
    SALUTATION = "salutation"
    SUBJECT = "subject"
    BODY = "body"
    BULLET_LIST = "bullet_list"
    SIGNATURE = "signature"
    DATE = "date"
    REFERENCE = "reference"
    CUSTOM = "custom"


# ============================================================================
# RULE PACKS
# ============================================================================

class ValidationRule(BaseModel):
    """Individual validation rule"""
    rule_id: str
    name: str
    description: str
    severity: ValidationSeverity
    
    # What to validate
    field: Optional[str] = None          # Field to check
    section: Optional[str] = None        # Section to check
    condition: str                        # Rule condition (e.g., "required", "min_length:50")
    
    # Error messaging
    error_message: str
    suggestion: Optional[str] = None


class RequiredSection(BaseModel):
    """Required section in a document"""
    section_id: str
    section_type: SectionType
    name: str
    description: str
    order: int
    is_required: bool = True
    
    # Content guidance
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    placeholder: Optional[str] = None
    example: Optional[str] = None


class RulePack(BaseModel):
    """Compliance rule pack for document generation"""
    pack_id: str = Field(default_factory=lambda: f"RP-{uuid.uuid4().hex[:8].upper()}")
    
    # Pack identity
    name: str
    description: str
    category: RulePackCategory
    
    # Applicable document types
    document_types: List[str]  # e.g., ["formal_letter", "complaint_letter"]
    
    # Required sections
    required_sections: List[RequiredSection]
    
    # Validation rules
    validation_rules: List[ValidationRule]
    
    # Compliance info
    compliance_standard: Optional[str] = None  # e.g., "UK Business Letter Standard"
    legal_disclaimer: Optional[str] = None
    
    # Metadata
    version: str = "1.0"
    is_active: bool = True
    is_premium: bool = False  # Premium packs for paid users
    
    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    model_config = {"extra": "ignore"}


# ============================================================================
# TEMPLATES
# ============================================================================

class TemplatePlaceholder(BaseModel):
    """Placeholder in a template"""
    key: str                     # e.g., "{{sender_name}}"
    label: str                   # e.g., "Your Name"
    field_type: str = "text"     # text, date, address, etc.
    required: bool = True
    default_value: Optional[str] = None
    
    # Profile mapping for auto-fill
    profile_field: Optional[str] = None  # e.g., "full_name" maps to SmartProfile.full_name


class TemplateSection(BaseModel):
    """Section of a document template"""
    section_id: str
    section_type: SectionType
    name: str
    order: int
    
    # Content
    content: str                 # Template text with placeholders
    is_ai_enhanced: bool = False # Whether to enhance with AI
    ai_prompt: Optional[str] = None  # Prompt for AI enhancement
    
    # Placeholders
    placeholders: List[TemplatePlaceholder] = []


class DocumentTemplate(BaseModel):
    """Document template for deterministic generation"""
    template_id: str = Field(default_factory=lambda: f"TPL-{uuid.uuid4().hex[:8].upper()}")
    
    # Template identity
    name: str
    description: str
    document_type: str           # e.g., "formal_letter"
    
    # Generation mode
    generation_mode: GenerationMode = GenerationMode.HYBRID
    
    # Template sections
    sections: List[TemplateSection]
    
    # Associated rule pack
    rule_pack_id: Optional[str] = None
    
    # Metadata
    category: RulePackCategory = RulePackCategory.BUSINESS
    tags: List[str] = []
    version: str = "1.0"
    is_active: bool = True
    is_system: bool = True       # System template vs user-created
    
    # Credit cost (templates are cheaper)
    credit_cost: int = 1
    
    # Usage stats
    use_count: int = 0
    
    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    model_config = {"extra": "ignore"}


# ============================================================================
# PRE-BUILT RULE PACKS
# ============================================================================

FORMAL_LETTER_RULE_PACK = RulePack(
    pack_id="RP-FORMAL-01",
    name="UK Formal Letter Standard",
    description="Standard structure for UK business and formal correspondence",
    category=RulePackCategory.BUSINESS,
    document_types=["formal_letter"],
    required_sections=[
        RequiredSection(
            section_id="sender_address",
            section_type=SectionType.ADDRESS,
            name="Sender's Address",
            description="Your postal address at the top right",
            order=1,
            placeholder="Your full postal address",
        ),
        RequiredSection(
            section_id="date",
            section_type=SectionType.DATE,
            name="Date",
            description="Today's date in formal format",
            order=2,
            example="25th January 2026",
        ),
        RequiredSection(
            section_id="recipient_address",
            section_type=SectionType.ADDRESS,
            name="Recipient's Address",
            description="The recipient's name and address",
            order=3,
        ),
        RequiredSection(
            section_id="salutation",
            section_type=SectionType.SALUTATION,
            name="Salutation",
            description="Formal greeting",
            order=4,
            example="Dear Mr/Mrs/Ms [Name], or Dear Sir/Madam",
        ),
        RequiredSection(
            section_id="subject",
            section_type=SectionType.SUBJECT,
            name="Subject Line",
            description="Clear subject or reference",
            order=5,
            is_required=False,
            placeholder="Re: [Subject of your letter]",
        ),
        RequiredSection(
            section_id="body",
            section_type=SectionType.BODY,
            name="Letter Body",
            description="Main content of your letter",
            order=6,
            min_length=50,
        ),
        RequiredSection(
            section_id="closing",
            section_type=SectionType.SIGNATURE,
            name="Closing & Signature",
            description="Formal closing and your signature",
            order=7,
            example="Yours sincerely/faithfully,\n\n[Your Name]",
        ),
    ],
    validation_rules=[
        ValidationRule(
            rule_id="formal-001",
            name="Formal Salutation",
            description="Check for appropriate formal greeting",
            severity=ValidationSeverity.WARNING,
            section="salutation",
            condition="pattern:^(Dear|Good morning|Good afternoon)",
            error_message="Use a formal greeting (Dear Sir/Madam, Dear Mr/Mrs...)",
            suggestion="Start with 'Dear' followed by the appropriate title",
        ),
        ValidationRule(
            rule_id="formal-002",
            name="Body Length",
            description="Ensure letter has sufficient content",
            severity=ValidationSeverity.ERROR,
            section="body",
            condition="min_length:50",
            error_message="Letter body is too short",
            suggestion="Add more detail to your letter",
        ),
        ValidationRule(
            rule_id="formal-003",
            name="Closing Match",
            description="Closing should match salutation formality",
            severity=ValidationSeverity.INFO,
            section="closing",
            condition="formal_closing",
            error_message="Consider using 'Yours sincerely' (if name known) or 'Yours faithfully' (if name unknown)",
        ),
    ],
    compliance_standard="UK Business Letter Convention",
)


COMPLAINT_LETTER_RULE_PACK = RulePack(
    pack_id="RP-COMPLAINT-01",
    name="Consumer Complaint Standard",
    description="Effective structure for consumer complaints under UK Consumer Rights",
    category=RulePackCategory.LEGAL,
    document_types=["complaint_letter"],
    required_sections=[
        RequiredSection(
            section_id="your_details",
            section_type=SectionType.ADDRESS,
            name="Your Contact Details",
            description="Your name, address, and contact information",
            order=1,
        ),
        RequiredSection(
            section_id="date",
            section_type=SectionType.DATE,
            name="Date",
            description="Today's date",
            order=2,
        ),
        RequiredSection(
            section_id="company_details",
            section_type=SectionType.ADDRESS,
            name="Company Details",
            description="Name and address of the company",
            order=3,
        ),
        RequiredSection(
            section_id="reference",
            section_type=SectionType.REFERENCE,
            name="Reference Numbers",
            description="Order number, account number, or other references",
            order=4,
            is_required=True,
            placeholder="Order/Reference: [Number]",
        ),
        RequiredSection(
            section_id="issue_summary",
            section_type=SectionType.BODY,
            name="Issue Summary",
            description="Clear, factual description of the problem",
            order=5,
            min_length=30,
        ),
        RequiredSection(
            section_id="timeline",
            section_type=SectionType.BODY,
            name="Timeline of Events",
            description="Chronological account of what happened",
            order=6,
        ),
        RequiredSection(
            section_id="resolution",
            section_type=SectionType.BODY,
            name="Desired Resolution",
            description="What you want them to do",
            order=7,
            placeholder="I am requesting [refund/replacement/compensation]...",
        ),
        RequiredSection(
            section_id="deadline",
            section_type=SectionType.BODY,
            name="Response Deadline",
            description="Reasonable deadline for response",
            order=8,
            example="Please respond within 14 days",
        ),
        RequiredSection(
            section_id="closing",
            section_type=SectionType.SIGNATURE,
            name="Signature",
            description="Your signature and printed name",
            order=9,
        ),
    ],
    validation_rules=[
        ValidationRule(
            rule_id="complaint-001",
            name="Reference Required",
            description="Complaint should include order/reference number",
            severity=ValidationSeverity.WARNING,
            section="reference",
            condition="required",
            error_message="Include your order or reference number for faster resolution",
            suggestion="Add your order number, account number, or any reference from your transaction",
        ),
        ValidationRule(
            rule_id="complaint-002",
            name="Resolution Clarity",
            description="Be specific about what you want",
            severity=ValidationSeverity.ERROR,
            section="resolution",
            condition="min_length:20",
            error_message="Be specific about what resolution you're seeking",
            suggestion="State clearly whether you want a refund, replacement, repair, or compensation",
        ),
        ValidationRule(
            rule_id="complaint-003",
            name="Professional Tone",
            description="Maintain professional language",
            severity=ValidationSeverity.WARNING,
            condition="no_profanity",
            error_message="Keep the letter professional and factual",
            suggestion="Remove emotional language and stick to facts",
        ),
        ValidationRule(
            rule_id="complaint-004",
            name="Deadline Included",
            description="Include a reasonable response deadline",
            severity=ValidationSeverity.INFO,
            section="deadline",
            condition="has_deadline",
            error_message="Consider adding a response deadline (typically 14-28 days)",
        ),
    ],
    compliance_standard="UK Consumer Rights Act 2015",
    legal_disclaimer="This letter is for guidance only and does not constitute legal advice.",
)


CV_RESUME_RULE_PACK = RulePack(
    pack_id="RP-CV-01",
    name="Modern UK CV Standard",
    description="ATS-friendly CV structure following modern UK conventions",
    category=RulePackCategory.EMPLOYMENT,
    document_types=["cv_resume"],
    required_sections=[
        RequiredSection(
            section_id="contact",
            section_type=SectionType.HEADER,
            name="Contact Information",
            description="Name, email, phone, LinkedIn (optional)",
            order=1,
        ),
        RequiredSection(
            section_id="summary",
            section_type=SectionType.BODY,
            name="Professional Summary",
            description="2-3 sentence overview of your experience and goals",
            order=2,
            min_length=50,
            max_length=300,
            example="Results-driven [role] with [X] years of experience in [industry]...",
        ),
        RequiredSection(
            section_id="experience",
            section_type=SectionType.BODY,
            name="Work Experience",
            description="Most recent roles with achievements",
            order=3,
            min_length=100,
        ),
        RequiredSection(
            section_id="education",
            section_type=SectionType.BODY,
            name="Education",
            description="Qualifications and certifications",
            order=4,
        ),
        RequiredSection(
            section_id="skills",
            section_type=SectionType.BULLET_LIST,
            name="Key Skills",
            description="Relevant technical and soft skills",
            order=5,
        ),
    ],
    validation_rules=[
        ValidationRule(
            rule_id="cv-001",
            name="Contact Info",
            description="Must include email and phone",
            severity=ValidationSeverity.ERROR,
            section="contact",
            condition="has_email_and_phone",
            error_message="Include your email and phone number",
        ),
        ValidationRule(
            rule_id="cv-002",
            name="Summary Length",
            description="Professional summary should be concise",
            severity=ValidationSeverity.WARNING,
            section="summary",
            condition="max_length:300",
            error_message="Professional summary is too long",
            suggestion="Keep your summary to 2-3 sentences",
        ),
        ValidationRule(
            rule_id="cv-003",
            name="Achievement Focus",
            description="Experience should include measurable achievements",
            severity=ValidationSeverity.INFO,
            section="experience",
            condition="has_numbers",
            error_message="Add quantifiable achievements where possible",
            suggestion="Include numbers, percentages, or specific outcomes",
        ),
        ValidationRule(
            rule_id="cv-004",
            name="No Photo",
            description="UK CVs typically don't include photos",
            severity=ValidationSeverity.INFO,
            condition="no_photo_mention",
            error_message="UK CVs usually don't include photos",
        ),
    ],
    compliance_standard="UK CV Best Practices 2025",
)


# ============================================================================
# PRE-BUILT TEMPLATES
# ============================================================================

FORMAL_LETTER_TEMPLATE = DocumentTemplate(
    template_id="TPL-FORMAL-01",
    name="Standard Formal Letter",
    description="Professional letter template for business correspondence",
    document_type="formal_letter",
    generation_mode=GenerationMode.HYBRID,
    rule_pack_id="RP-FORMAL-01",
    category=RulePackCategory.BUSINESS,
    tags=["formal", "business", "professional"],
    credit_cost=1,
    sections=[
        TemplateSection(
            section_id="sender",
            section_type=SectionType.ADDRESS,
            name="Sender Details",
            order=1,
            content="""{{sender_name}}
{{sender_address_line1}}
{{sender_city}}, {{sender_postcode}}
{{sender_email}}
{{sender_phone}}""",
            placeholders=[
                TemplatePlaceholder(key="sender_name", label="Your Full Name", profile_field="full_name"),
                TemplatePlaceholder(key="sender_address_line1", label="Address Line 1", profile_field="address_line1"),
                TemplatePlaceholder(key="sender_city", label="City", profile_field="city"),
                TemplatePlaceholder(key="sender_postcode", label="Postcode", profile_field="postcode"),
                TemplatePlaceholder(key="sender_email", label="Email", profile_field="email", required=False),
                TemplatePlaceholder(key="sender_phone", label="Phone", profile_field="phone", required=False),
            ],
        ),
        TemplateSection(
            section_id="date",
            section_type=SectionType.DATE,
            name="Date",
            order=2,
            content="{{date}}",
            placeholders=[
                TemplatePlaceholder(key="date", label="Date", field_type="date", default_value="[Today's Date]"),
            ],
        ),
        TemplateSection(
            section_id="recipient",
            section_type=SectionType.ADDRESS,
            name="Recipient Details",
            order=3,
            content="""{{recipient_name}}
{{recipient_title}}
{{recipient_organization}}
{{recipient_address}}""",
            placeholders=[
                TemplatePlaceholder(key="recipient_name", label="Recipient Name"),
                TemplatePlaceholder(key="recipient_title", label="Title/Position", required=False),
                TemplatePlaceholder(key="recipient_organization", label="Organization", required=False),
                TemplatePlaceholder(key="recipient_address", label="Address", required=False),
            ],
        ),
        TemplateSection(
            section_id="salutation",
            section_type=SectionType.SALUTATION,
            name="Salutation",
            order=4,
            content="Dear {{salutation}},",
            placeholders=[
                TemplatePlaceholder(key="salutation", label="Salutation", default_value="Sir/Madam"),
            ],
        ),
        TemplateSection(
            section_id="subject",
            section_type=SectionType.SUBJECT,
            name="Subject",
            order=5,
            content="**Re: {{subject}}**",
            placeholders=[
                TemplatePlaceholder(key="subject", label="Subject Line", required=False),
            ],
        ),
        TemplateSection(
            section_id="body",
            section_type=SectionType.BODY,
            name="Letter Body",
            order=6,
            content="{{letter_body}}",
            is_ai_enhanced=True,
            ai_prompt="Write the body of a formal letter based on this intent: {{intent}}. Keep it professional, clear, and appropriately formal.",
            placeholders=[
                TemplatePlaceholder(key="intent", label="Purpose of Letter"),
                TemplatePlaceholder(key="letter_body", label="Letter Content", required=False),
            ],
        ),
        TemplateSection(
            section_id="closing",
            section_type=SectionType.SIGNATURE,
            name="Closing",
            order=7,
            content="""{{closing}},

{{sender_name}}""",
            placeholders=[
                TemplatePlaceholder(key="closing", label="Closing", default_value="Yours faithfully"),
            ],
        ),
    ],
)


COMPLAINT_LETTER_TEMPLATE = DocumentTemplate(
    template_id="TPL-COMPLAINT-01",
    name="Consumer Complaint Letter",
    description="Effective complaint letter following UK consumer rights guidelines",
    document_type="complaint_letter",
    generation_mode=GenerationMode.HYBRID,
    rule_pack_id="RP-COMPLAINT-01",
    category=RulePackCategory.LEGAL,
    tags=["complaint", "consumer", "legal"],
    credit_cost=1,
    sections=[
        TemplateSection(
            section_id="your_details",
            section_type=SectionType.ADDRESS,
            name="Your Details",
            order=1,
            content="""{{your_name}}
{{your_address}}
{{your_email}}
{{your_phone}}""",
            placeholders=[
                TemplatePlaceholder(key="your_name", label="Your Full Name", profile_field="full_name"),
                TemplatePlaceholder(key="your_address", label="Your Address", profile_field="address_line1"),
                TemplatePlaceholder(key="your_email", label="Your Email", profile_field="email"),
                TemplatePlaceholder(key="your_phone", label="Your Phone", profile_field="phone"),
            ],
        ),
        TemplateSection(
            section_id="date",
            section_type=SectionType.DATE,
            name="Date",
            order=2,
            content="{{date}}",
            placeholders=[
                TemplatePlaceholder(key="date", label="Date", field_type="date"),
            ],
        ),
        TemplateSection(
            section_id="company",
            section_type=SectionType.ADDRESS,
            name="Company Details",
            order=3,
            content="""{{company_name}}
Customer Services Department
{{company_address}}""",
            placeholders=[
                TemplatePlaceholder(key="company_name", label="Company Name"),
                TemplatePlaceholder(key="company_address", label="Company Address", required=False),
            ],
        ),
        TemplateSection(
            section_id="reference",
            section_type=SectionType.REFERENCE,
            name="Reference",
            order=4,
            content="**Reference:** {{order_reference}}",
            placeholders=[
                TemplatePlaceholder(key="order_reference", label="Order/Reference Number"),
            ],
        ),
        TemplateSection(
            section_id="opening",
            section_type=SectionType.SALUTATION,
            name="Opening",
            order=5,
            content="Dear Sir/Madam,",
            placeholders=[],
        ),
        TemplateSection(
            section_id="body",
            section_type=SectionType.BODY,
            name="Complaint Details",
            order=6,
            content="{{complaint_body}}",
            is_ai_enhanced=True,
            ai_prompt="""Write a professional complaint letter body that includes:
1. Opening stating this is a formal complaint
2. Clear description of the issue: {{issue_description}}
3. Timeline of events (issue date: {{issue_date}})
4. Impact on the customer
5. Desired resolution: {{desired_resolution}}
6. Reference to consumer rights if applicable
Keep it factual, professional, and firm but polite.""",
            placeholders=[
                TemplatePlaceholder(key="issue_description", label="Describe the Issue"),
                TemplatePlaceholder(key="issue_date", label="When did this happen?"),
                TemplatePlaceholder(key="desired_resolution", label="What resolution do you want?"),
            ],
        ),
        TemplateSection(
            section_id="deadline",
            section_type=SectionType.BODY,
            name="Deadline",
            order=7,
            content="\nI expect a response within {{response_days}} days. If I do not receive a satisfactory response, I will consider escalating this matter to the relevant ombudsman or trading standards.",
            placeholders=[
                TemplatePlaceholder(key="response_days", label="Response deadline (days)", default_value="14"),
            ],
        ),
        TemplateSection(
            section_id="closing",
            section_type=SectionType.SIGNATURE,
            name="Closing",
            order=8,
            content="""Yours faithfully,

{{your_name}}""",
            placeholders=[],
        ),
    ],
)


# ============================================================================
# REGISTRY
# ============================================================================

RULE_PACKS = {
    "RP-FORMAL-01": FORMAL_LETTER_RULE_PACK,
    "RP-COMPLAINT-01": COMPLAINT_LETTER_RULE_PACK,
    "RP-CV-01": CV_RESUME_RULE_PACK,
}

DOCUMENT_TEMPLATES = {
    "TPL-FORMAL-01": FORMAL_LETTER_TEMPLATE,
    "TPL-COMPLAINT-01": COMPLAINT_LETTER_TEMPLATE,
}


def get_rule_pack(pack_id: str) -> Optional[RulePack]:
    """Get rule pack by ID."""
    return RULE_PACKS.get(pack_id)


def get_template(template_id: str) -> Optional[DocumentTemplate]:
    """Get template by ID."""
    return DOCUMENT_TEMPLATES.get(template_id)


def get_templates_for_type(document_type: str) -> List[DocumentTemplate]:
    """Get all templates for a document type."""
    return [t for t in DOCUMENT_TEMPLATES.values() if t.document_type == document_type]


def get_rule_packs_for_type(document_type: str) -> List[RulePack]:
    """Get all rule packs for a document type."""
    return [p for p in RULE_PACKS.values() if document_type in p.document_types]
