from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum
import uuid

# ============================================================================
# ENUMS (System Constants)
# ============================================================================

class ClientType(str, Enum):
    INDIVIDUAL = "INDIVIDUAL"
    COMPANY = "COMPANY"
    AGENT = "AGENT"

class PreferredContact(str, Enum):
    EMAIL = "EMAIL"
    SMS = "SMS"
    BOTH = "BOTH"

class BillingPlan(str, Enum):
    PLAN_1 = "PLAN_1"
    PLAN_2_5 = "PLAN_2_5"
    PLAN_6_15 = "PLAN_6_15"

class SubscriptionStatus(str, Enum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    CANCELLED = "CANCELLED"

class OnboardingStatus(str, Enum):
    INTAKE_PENDING = "INTAKE_PENDING"
    PROVISIONING = "PROVISIONING"
    PROVISIONED = "PROVISIONED"
    FAILED = "FAILED"

class ServiceCode(str, Enum):
    VAULT_PRO = "VAULT_PRO"

class UserRole(str, Enum):
    ROLE_CLIENT = "ROLE_CLIENT"
    ROLE_CLIENT_ADMIN = "ROLE_CLIENT_ADMIN"
    ROLE_ADMIN = "ROLE_ADMIN"
    ROLE_TENANT = "ROLE_TENANT"  # Read-only access to property compliance status

class UserStatus(str, Enum):
    INVITED = "INVITED"
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"

class PasswordStatus(str, Enum):
    NOT_SET = "NOT_SET"
    SET = "SET"

class ComplianceStatus(str, Enum):
    GREEN = "GREEN"
    AMBER = "AMBER"
    RED = "RED"

class DocumentStatus(str, Enum):
    PENDING = "PENDING"
    UPLOADED = "UPLOADED"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"

class RequirementStatus(str, Enum):
    PENDING = "PENDING"
    COMPLIANT = "COMPLIANT"
    OVERDUE = "OVERDUE"
    EXPIRING_SOON = "EXPIRING_SOON"

class RuleCategory(str, Enum):
    SAFETY = "SAFETY"
    ELECTRICAL = "ELECTRICAL"
    ENERGY = "ENERGY"
    FIRE = "FIRE"
    HEALTH = "HEALTH"
    REGULATORY = "REGULATORY"
    OTHER = "OTHER"

class PropertyTypeApplicability(str, Enum):
    ALL = "ALL"
    RESIDENTIAL = "RESIDENTIAL"
    COMMERCIAL = "COMMERCIAL"
    HMO = "HMO"

class AuditAction(str, Enum):
    # Intake
    INTAKE_SUBMITTED = "INTAKE_SUBMITTED"
    INTAKE_PROPERTY_ADDED = "INTAKE_PROPERTY_ADDED"
    INTAKE_DOCUMENT_UPLOADED = "INTAKE_DOCUMENT_UPLOADED"
    
    # Provisioning
    PROVISIONING_STARTED = "PROVISIONING_STARTED"
    PROVISIONING_COMPLETE = "PROVISIONING_COMPLETE"
    PROVISIONING_FAILED = "PROVISIONING_FAILED"
    
    # Requirements
    REQUIREMENTS_GENERATED = "REQUIREMENTS_GENERATED"
    REQUIREMENTS_EVALUATED = "REQUIREMENTS_EVALUATED"
    COMPLIANCE_STATUS_UPDATED = "COMPLIANCE_STATUS_UPDATED"
    
    # Password
    PASSWORD_TOKEN_GENERATED = "PASSWORD_TOKEN_GENERATED"
    PASSWORD_TOKEN_VALIDATED = "PASSWORD_TOKEN_VALIDATED"
    PASSWORD_SET_SUCCESS = "PASSWORD_SET_SUCCESS"
    PASSWORD_SETUP_LINK_RESENT = "PASSWORD_SETUP_LINK_RESENT"
    
    # Auth - General
    USER_LOGIN_SUCCESS = "USER_LOGIN_SUCCESS"
    USER_LOGIN_FAILED = "USER_LOGIN_FAILED"
    USER_AUTHENTICATED_POST_SETUP = "USER_AUTHENTICATED_POST_SETUP"
    
    # Auth - Admin Specific
    ADMIN_LOGIN_SUCCESS = "ADMIN_LOGIN_SUCCESS"
    ADMIN_LOGIN_FAILED = "ADMIN_LOGIN_FAILED"
    ADMIN_INVITED = "ADMIN_INVITED"
    ADMIN_INVITE_ACCEPTED = "ADMIN_INVITE_ACCEPTED"
    
    # Route Guards
    ROUTE_GUARD_REDIRECT = "ROUTE_GUARD_REDIRECT"
    ADMIN_ROUTE_GUARD_BLOCK = "ADMIN_ROUTE_GUARD_BLOCK"
    
    # Email
    EMAIL_SENT = "EMAIL_SENT"
    EMAIL_FAILED = "EMAIL_FAILED"
    REMINDER_SENT = "REMINDER_SENT"
    DIGEST_SENT = "DIGEST_SENT"
    
    # Documents
    DOCUMENT_UPLOADED = "DOCUMENT_UPLOADED"
    DOCUMENT_VERIFIED = "DOCUMENT_VERIFIED"
    DOCUMENT_REJECTED = "DOCUMENT_REJECTED"
    DOCUMENT_AI_ANALYZED = "DOCUMENT_AI_ANALYZED"
    
    # Admin Actions
    ADMIN_ACTION = "ADMIN_ACTION"

class EmailTemplateAlias(str, Enum):
    PASSWORD_SETUP = "password-setup"
    PASSWORD_RESET = "password-reset"
    PORTAL_READY = "portal-ready"
    MONTHLY_DIGEST = "monthly-digest"
    ADMIN_MANUAL = "admin-manual"
    PAYMENT_RECEIPT = "payment-receipt"
    REMINDER = "reminder"
    WELCOME = "welcome"
    COMPLIANCE_ALERT = "compliance-alert"  # Status change notifications
    TENANT_INVITE = "tenant-invite"  # Tenant portal invitation
    SCHEDULED_REPORT = "scheduled-report"  # Scheduled compliance reports


class ReportScheduleFrequency(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class ReportSchedule(BaseModel):
    """Scheduled report configuration for a client."""
    model_config = ConfigDict(extra="ignore")
    
    schedule_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_id: str
    report_type: str  # compliance_summary, requirements
    frequency: ReportScheduleFrequency
    recipients: List[str] = Field(default_factory=list)  # Email addresses
    include_details: bool = True
    is_active: bool = True
    last_sent: Optional[str] = None
    next_scheduled: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(datetime.now().astimezone().tzinfo))
    created_by: Optional[str] = None


class WebhookEventType(str, Enum):
    COMPLIANCE_STATUS_CHANGED = "compliance.status_changed"
    REQUIREMENT_STATUS_CHANGED = "requirement.status_changed"
    DOCUMENT_VERIFICATION_CHANGED = "document.verification_changed"
    DIGEST_SENT = "digest.sent"
    REMINDER_SENT = "reminder.sent"


class Webhook(BaseModel):
    """Webhook configuration for external integrations."""
    model_config = ConfigDict(extra="ignore")
    
    webhook_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_id: str
    name: str
    url: str  # Target URL to POST to
    secret: Optional[str] = None  # Signing secret for HMAC-SHA256 verification
    event_types: List[str] = Field(default_factory=list)
    is_active: bool = True
    is_deleted: bool = False  # Soft delete flag
    last_triggered: Optional[str] = None
    last_status: Optional[int] = None  # Last HTTP response code
    last_response_body: Optional[str] = None  # Last response (truncated)
    last_error: Optional[str] = None  # Last error message if failed
    failure_count: int = 0
    total_deliveries: int = 0
    successful_deliveries: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(datetime.now().astimezone().tzinfo))
    created_by: Optional[str] = None
    deleted_at: Optional[str] = None


class EmailTemplate(BaseModel):
    """Customizable email template stored in the database."""
    model_config = ConfigDict(extra="ignore")
    
    template_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    alias: EmailTemplateAlias  # Which template type this is
    name: str  # Display name
    subject: str  # Email subject line
    html_body: str  # HTML content with placeholders like {{client_name}}
    text_body: str  # Plain text version
    is_active: bool = True
    available_variables: List[str] = Field(default_factory=list)  # e.g., ["client_name", "setup_link"]
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(datetime.now().astimezone().tzinfo))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(datetime.now().astimezone().tzinfo))
    created_by: Optional[str] = None

# ============================================================================
# CORE MODELS
# ============================================================================

class Client(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    client_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    customer_reference: Optional[str] = None  # PLE-CVP-YYYY-XXXXX format
    full_name: str
    email: EmailStr
    phone: Optional[str] = None
    company_name: Optional[str] = None
    client_type: ClientType
    preferred_contact: PreferredContact = PreferredContact.EMAIL
    billing_plan: BillingPlan = BillingPlan.PLAN_1
    subscription_status: SubscriptionStatus = SubscriptionStatus.PENDING
    onboarding_status: OnboardingStatus = OnboardingStatus.INTAKE_PENDING
    service_code: ServiceCode = ServiceCode.VAULT_PRO
    stripe_customer_id: Optional[str] = None
    stripe_subscription_id: Optional[str] = None
    # Document submission preference
    document_submission_method: Optional[str] = None  # "UPLOAD" or "EMAIL"
    email_upload_consent: bool = False  # Consent to Pleerity uploading on behalf
    # Consents
    consent_data_processing: bool = False
    consent_service_boundary: bool = False  # "Does not provide legal advice" acknowledgment
    created_at: datetime = Field(default_factory=lambda: datetime.now(datetime.now().astimezone().tzinfo))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(datetime.now().astimezone().tzinfo))

class NotificationPreferences(BaseModel):
    """Client notification preferences."""
    model_config = ConfigDict(extra="ignore")
    
    client_id: str
    # Email notification types
    status_change_alerts: bool = True  # GREEN→AMBER→RED changes
    expiry_reminders: bool = True  # Daily expiry reminders
    monthly_digest: bool = True  # Monthly compliance summary
    document_updates: bool = True  # Document upload/verification notifications
    system_announcements: bool = True  # Platform updates and news
    
    # Timing preferences
    reminder_days_before: int = 30  # Days before expiry to start reminders
    digest_day_of_month: int = 1  # Day of month for digest (1-28)
    
    # Quiet hours (optional)
    quiet_hours_enabled: bool = False
    quiet_hours_start: Optional[str] = "22:00"  # HH:MM format
    quiet_hours_end: Optional[str] = "08:00"
    
    # SMS preferences (feature flagged)
    sms_enabled: bool = False  # Master SMS toggle
    sms_phone_number: Optional[str] = None  # Phone number for SMS
    sms_phone_verified: bool = False  # Whether phone is verified
    sms_urgent_alerts_only: bool = True  # Only send SMS for RED status
    
    # Email Digest Customization (Monthly Digest sections - all ON by default unless noted)
    digest_compliance_summary: bool = True
    digest_action_items: bool = True  # OVERDUE/MISSING/DUE_SOON
    digest_upcoming_expiries: bool = True  # Next 30/60/90 days
    digest_property_breakdown: bool = True
    digest_recent_documents: bool = True  # Recently uploaded/verified
    digest_recommendations: bool = True  # Next actions inside portal
    digest_audit_summary: bool = False  # Default OFF - optional activity summary
    
    # Daily reminder customization
    daily_reminder_enabled: bool = True  # Allow opting out if rules permit
    
    updated_at: datetime = Field(default_factory=lambda: datetime.now(datetime.now().astimezone().tzinfo))

class PortalUser(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    portal_user_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_id: str
    auth_email: EmailStr
    password_hash: Optional[str] = None
    role: UserRole = UserRole.ROLE_CLIENT_ADMIN
    status: UserStatus = UserStatus.INVITED
    password_status: PasswordStatus = PasswordStatus.NOT_SET
    must_set_password: bool = True
    last_login: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(datetime.now().astimezone().tzinfo))

class Property(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    property_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_id: str
    nickname: Optional[str] = None  # User-friendly name for the property
    address_line_1: str
    address_line_2: Optional[str] = None
    city: str
    postcode: str
    property_type: str  # residential, hmo, commercial, flat, house, bungalow
    number_of_units: int = 1
    bedrooms: Optional[int] = None
    occupancy: Optional[str] = None  # single_family, multi_family, student, professional
    compliance_status: ComplianceStatus = ComplianceStatus.RED
    
    # Enhanced property attributes for dynamic requirement generation
    is_hmo: bool = False  # House in Multiple Occupation
    hmo_license_required: bool = False  # Selective/additional licensing
    has_gas_supply: bool = True  # If false, skip gas safety requirement
    building_age_years: Optional[int] = None  # For EICR frequency
    has_communal_areas: bool = False  # For fire safety requirements
    local_authority: Optional[str] = None  # For location-specific rules (council name)
    local_authority_code: Optional[str] = None  # Council code for lookup
    
    # Licensing information
    licence_required: Optional[str] = None  # "YES", "NO", "UNSURE"
    licence_type: Optional[str] = None  # selective, additional, mandatory_hmo
    licence_status: Optional[str] = None  # applied, pending, approved, expired, unknown
    
    # Management
    managed_by: Optional[str] = None  # "LANDLORD" or "AGENT"
    send_reminders_to: Optional[str] = None  # "LANDLORD", "AGENT", "BOTH"
    agent_name: Optional[str] = None
    agent_email: Optional[str] = None
    agent_phone: Optional[str] = None
    
    # Certificate availability flags (collected at intake for deterministic compliance)
    cert_gas_safety: Optional[str] = None  # "YES", "NO", "UNSURE"
    cert_eicr: Optional[str] = None
    cert_epc: Optional[str] = None
    cert_licence: Optional[str] = None  # Only if licence_required = YES
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(datetime.now().astimezone().tzinfo))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(datetime.now().astimezone().tzinfo))

class Requirement(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    requirement_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_id: str
    property_id: str
    requirement_type: str
    description: str
    frequency_days: int
    due_date: datetime
    status: RequirementStatus = RequirementStatus.PENDING
    created_at: datetime = Field(default_factory=lambda: datetime.now(datetime.now().astimezone().tzinfo))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(datetime.now().astimezone().tzinfo))

class RequirementRule(BaseModel):
    """Defines a compliance requirement rule that can be applied to properties."""
    model_config = ConfigDict(extra="ignore")
    
    rule_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    rule_type: str  # e.g., "gas_safety", "eicr", "epc"
    name: str  # Human-readable name
    description: str  # Detailed description
    category: RuleCategory = RuleCategory.OTHER
    frequency_days: int  # How often this must be renewed
    warning_days: int = 30  # Days before due date to show warning
    applicable_to: PropertyTypeApplicability = PropertyTypeApplicability.ALL
    is_mandatory: bool = True
    is_active: bool = True
    risk_weight: int = Field(default=1, ge=1, le=5)  # 1-5, higher = more critical
    regulatory_reference: Optional[str] = None  # Link to regulation
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(datetime.now().astimezone().tzinfo))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(datetime.now().astimezone().tzinfo))
    created_by: Optional[str] = None

class Document(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    document_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_id: str
    property_id: str
    requirement_id: Optional[str] = None  # Optional for bulk uploads without auto-matching
    file_name: str
    file_path: str
    file_size: int
    mime_type: str
    status: DocumentStatus = DocumentStatus.PENDING
    uploaded_by: str
    ai_extracted_data: Optional[Dict[str, Any]] = None
    confidence_score: Optional[float] = None
    manual_review_flag: bool = False
    uploaded_at: datetime = Field(default_factory=lambda: datetime.now(datetime.now().astimezone().tzinfo))

class AuditLog(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    audit_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    action: AuditAction
    actor_role: Optional[UserRole] = None
    actor_id: Optional[str] = None
    client_id: Optional[str] = None
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    before_state: Optional[Dict[str, Any]] = None
    after_state: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    reason_code: Optional[str] = None
    ip_address: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(datetime.now().astimezone().tzinfo))

class MessageLog(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    postmark_message_id: Optional[str] = None
    client_id: Optional[str] = None
    recipient: EmailStr
    template_alias: EmailTemplateAlias
    subject: str
    status: str = "queued"
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    opened_at: Optional[datetime] = None
    bounced_at: Optional[datetime] = None
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(datetime.now().astimezone().tzinfo))

class DigestLog(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    digest_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_id: str
    digest_period_start: datetime
    digest_period_end: datetime
    content: Dict[str, Any]
    sent_at: datetime
    created_at: datetime = Field(default_factory=lambda: datetime.now(datetime.now().astimezone().tzinfo))

class PasswordToken(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    token_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    token_hash: str
    portal_user_id: str
    client_id: str
    expires_at: datetime
    used_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    created_by: str = "SYSTEM"
    send_count: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(datetime.now().astimezone().tzinfo))

class PaymentTransaction(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    transaction_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_id: str
    stripe_session_id: str
    stripe_payment_intent_id: Optional[str] = None
    amount: float
    currency: str = "gbp"
    billing_plan: BillingPlan
    payment_status: str = "pending"
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(datetime.now().astimezone().tzinfo))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(datetime.now().astimezone().tzinfo))

# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

# ============================================================================
# INTAKE WIZARD MODELS
# ============================================================================

class CertificateAvailability(str, Enum):
    YES = "YES"
    NO = "NO"
    UNSURE = "UNSURE"


class LicenceStatus(str, Enum):
    APPLIED = "APPLIED"
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    EXPIRED = "EXPIRED"
    UNKNOWN = "UNKNOWN"


class IntakePropertyData(BaseModel):
    """Property data collected during intake wizard."""
    nickname: Optional[str] = None
    postcode: str
    address_line_1: str
    address_line_2: Optional[str] = None
    city: str
    property_type: str  # flat, house, bungalow, commercial
    is_hmo: bool = False
    bedrooms: Optional[int] = None
    occupancy: Optional[str] = None  # single_family, multi_family, student, professional
    
    # Council
    council_name: Optional[str] = None
    council_code: Optional[str] = None
    
    # Licensing
    licence_required: Optional[str] = None  # YES, NO, UNSURE
    licence_type: Optional[str] = None  # selective, additional, mandatory_hmo
    licence_status: Optional[str] = None  # applied, pending, approved, expired, unknown
    
    # Management & Reminders
    managed_by: Optional[str] = None  # LANDLORD, AGENT
    send_reminders_to: Optional[str] = None  # LANDLORD, AGENT, BOTH
    agent_name: Optional[str] = None
    agent_email: Optional[str] = None
    agent_phone: Optional[str] = None
    
    # Certificate availability (for deterministic compliance calculation)
    cert_gas_safety: Optional[str] = None  # YES, NO, UNSURE
    cert_eicr: Optional[str] = None
    cert_epc: Optional[str] = None
    cert_licence: Optional[str] = None  # Only applicable if licence_required = YES


class IntakeFormData(BaseModel):
    """Universal intake wizard form data - 5-step wizard submission."""
    # Step 1: Your Details
    full_name: str
    email: EmailStr
    client_type: ClientType
    company_name: Optional[str] = None  # Required if COMPANY or AGENT
    preferred_contact: PreferredContact
    phone: Optional[str] = None  # Required if SMS or BOTH
    
    # Step 2: Plan selection
    billing_plan: BillingPlan
    
    # Step 3: Properties (plan-limited)
    properties: List[IntakePropertyData]
    
    # Step 4: Preferences & Consents
    document_submission_method: str  # "UPLOAD" or "EMAIL"
    email_upload_consent: bool = False  # Required if method is EMAIL
    consent_data_processing: bool  # GDPR consent - required
    consent_service_boundary: bool  # "Does not provide legal advice" - required
    
    # Temp key for linking uploaded documents before properties exist
    intake_session_id: Optional[str] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class SetPasswordRequest(BaseModel):
    token: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: Dict[str, Any]
