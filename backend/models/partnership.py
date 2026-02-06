from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4


class PartnershipStatus(str, Enum):
    """Status of partnership enquiry."""
    NEW = "NEW"
    REVIEWED = "REVIEWED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    ARCHIVED = "ARCHIVED"


class PartnershipEnquiry(BaseModel):
    """Partnership enquiry model."""
    enquiry_id: str = Field(default_factory=lambda: str(uuid4()))
    
    # Section 1: Basic Identification
    first_name: str
    last_name: str
    role_title: str
    work_email: EmailStr
    phone: Optional[str] = None
    
    # Section 2: Partnership Type
    partnership_type: str
    partnership_type_other: Optional[str] = None
    
    # Section 3: Organisation Info
    company_name: str
    country_region: str
    website_url: str
    organisation_type: str
    org_description: str
    primary_services: str
    typical_client_profile: Optional[str] = None
    
    # Section 4: Partnership Intent
    collaboration_type: str
    collaboration_other: Optional[str] = None
    problem_solved: str
    
    # Section 5: Readiness & Scale
    works_with_partners: bool
    org_size: str
    gdpr_compliant_status: str
    timeline: str
    additional_notes: Optional[str] = None
    
    # Declarations
    declaration_accepted: bool
    
    # Admin fields
    status: PartnershipStatus = PartnershipStatus.NEW
    admin_notes: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    
    # Email tracking
    ack_email_sent: bool = False
    ack_email_sent_at: Optional[datetime] = None
    
    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_by: Optional[str] = None
    
    class Config:
        use_enum_values = True
