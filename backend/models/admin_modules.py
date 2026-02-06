from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

class ContactEnquiryStatus(str, Enum):
    NEW = "NEW"
    IN_PROGRESS = "IN_PROGRESS"
    RESPONDED = "RESPONDED"
    CLOSED = "CLOSED"
    SPAM = "SPAM"

class ContactEnquiry(BaseModel):
    enquiry_id: str = Field(default_factory=lambda: str(uuid4()))
    full_name: str
    email: EmailStr
    phone: Optional[str] = None
    subject: str
    message: str
    status: ContactEnquiryStatus = ContactEnquiryStatus.NEW
    admin_notes: Optional[str] = None
    admin_reply: Optional[str] = None
    replied_at: Optional[datetime] = None
    replied_by: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
class FAQItem(BaseModel):
    faq_id: str = Field(default_factory=lambda: str(uuid4()))
    category: str
    question: str
    answer: str
    is_active: bool = True
    display_order: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_by: Optional[str] = None

class NewsletterSubscriber(BaseModel):
    subscriber_id: str = Field(default_factory=lambda: str(uuid4()))
    email: EmailStr
    status: str = "SUBSCRIBED"  # SUBSCRIBED, UNSUBSCRIBED, BOUNCED, BLOCKED
    source: str = "website"
    subscribed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    unsubscribed_at: Optional[datetime] = None
    
class InsightFeedback(BaseModel):
    feedback_id: str = Field(default_factory=lambda: str(uuid4()))
    article_slug: str
    article_title: str
    was_helpful: bool
    comment: Optional[str] = None
    status: str = "NEW"  # NEW, REVIEWED, ACTIONED, ARCHIVED
    admin_notes: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_by: Optional[str] = None
