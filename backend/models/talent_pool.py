from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4


class TalentPoolStatus(str, Enum):
    """Status of talent pool submission."""
    NEW = "NEW"
    REVIEWED = "REVIEWED"
    SHORTLISTED = "SHORTLISTED"
    ARCHIVED = "ARCHIVED"


class TalentPoolSubmission(BaseModel):
    """Talent Pool submission model."""
    submission_id: str = Field(default_factory=lambda: str(uuid4()))
    
    # Step 1: Personal Details
    full_name: str
    email: EmailStr
    country: str
    linkedin_url: Optional[str] = None
    phone: Optional[str] = None
    
    # Step 2: Areas of Interest
    interest_areas: List[str]
    other_interest_text: Optional[str] = None
    
    # Step 3: Experience
    professional_summary: str
    years_experience: str
    
    # Step 4: Skills & Preferences
    skills_tools: List[str]
    other_skills_text: Optional[str] = None
    availability: str
    work_style: List[str]
    cv_file_url: Optional[str] = None
    cv_filename: Optional[str] = None
    
    # Consent
    consent_accepted: bool
    
    # Admin fields
    status: TalentPoolStatus = TalentPoolStatus.NEW
    admin_notes: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    
    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_by: Optional[str] = None
    
    class Config:
        use_enum_values = True
