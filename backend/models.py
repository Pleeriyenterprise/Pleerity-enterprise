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
    
    # Auth
    USER_LOGIN_SUCCESS = "USER_LOGIN_SUCCESS"
    USER_LOGIN_FAILED = "USER_LOGIN_FAILED"
    USER_AUTHENTICATED_POST_SETUP = "USER_AUTHENTICATED_POST_SETUP"
    
    # Route Guards
    ROUTE_GUARD_REDIRECT = "ROUTE_GUARD_REDIRECT"
    
    # Email
    EMAIL_SENT = "EMAIL_SENT"
    EMAIL_FAILED = "EMAIL_FAILED"
    REMINDER_SENT = "REMINDER_SENT"
    DIGEST_SENT = "DIGEST_SENT"
    
    # Documents
    DOCUMENT_UPLOADED = "DOCUMENT_UPLOADED"
    DOCUMENT_VERIFIED = "DOCUMENT_VERIFIED"
    DOCUMENT_REJECTED = "DOCUMENT_REJECTED"
    
    # Admin Actions
    ADMIN_ACTION = "ADMIN_ACTION"

class EmailTemplateAlias(str, Enum):
    PASSWORD_SETUP = "password-setup"
    PASSWORD_RESET = "password-reset"
    PORTAL_READY = "portal-ready"
    MONTHLY_DIGEST = "monthly-digest"
    ADMIN_MANUAL = "admin-manual"
    PAYMENT_RECEIPT = "payment-receipt"

# ============================================================================
# CORE MODELS
# ============================================================================

class Client(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    client_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
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
    created_at: datetime = Field(default_factory=lambda: datetime.now(datetime.now().astimezone().tzinfo))
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
    address_line_1: str
    address_line_2: Optional[str] = None
    city: str
    postcode: str
    property_type: str
    number_of_units: int = 1
    compliance_status: ComplianceStatus = ComplianceStatus.RED
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

class Document(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    document_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_id: str
    property_id: str
    requirement_id: str
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

class IntakeFormData(BaseModel):
    full_name: str
    email: EmailStr
    phone: Optional[str] = None
    company_name: Optional[str] = None
    client_type: ClientType
    preferred_contact: PreferredContact
    properties: List[Dict[str, Any]]
    billing_plan: BillingPlan
    consent_data_processing: bool
    consent_communications: bool

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
