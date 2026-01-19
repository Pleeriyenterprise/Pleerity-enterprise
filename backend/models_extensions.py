"""User notification preferences model - Additive enhancement"""
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class NotificationPreferences(BaseModel):
    """User notification preferences (optional settings)."""
    portal_user_id: str
    
    # Preferences (users CAN opt out of these)
    compliance_reminders: bool = True
    monthly_digest: bool = True
    product_announcements: bool = True
    
    # Critical notifications (users CANNOT opt out)
    # These are always True and handled by backend
    # - password_setup_emails (always sent)
    # - password_reset_emails (always sent)
    # - security_alerts (always sent)
    
    # SMS preferences (if enabled)
    sms_reminders_enabled: bool = False
    sms_phone_verified: bool = False
    
    updated_at: datetime

class UserProfile(BaseModel):
    """Extended user profile data (read from PortalUser + Client)."""
    portal_user_id: str
    full_name: str
    email: str
    phone: Optional[str] = None
    company_name: Optional[str] = None
    client_type: str
    preferences: Optional[NotificationPreferences] = None
