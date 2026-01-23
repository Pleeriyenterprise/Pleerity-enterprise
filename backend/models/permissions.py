"""
Team Permissions & Role Management Models
Supports Manager role and custom role builder with granular privileges
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from enum import Enum


# ============================================
# Permission Categories & Actions
# ============================================

class PermissionCategory(str, Enum):
    """Permission categories for granular access control"""
    DASHBOARD = "dashboard"
    CLIENTS = "clients"
    LEADS = "leads"
    ORDERS = "orders"
    REPORTS = "reports"
    CMS = "cms"
    SUPPORT = "support"
    BILLING = "billing"
    SETTINGS = "settings"
    TEAM = "team"
    ANALYTICS = "analytics"
    ENABLEMENT = "enablement"
    CONSENT = "consent"


class PermissionAction(str, Enum):
    """Actions that can be performed"""
    VIEW = "view"
    CREATE = "create"
    EDIT = "edit"
    DELETE = "delete"
    EXPORT = "export"
    MANAGE = "manage"  # Full control including settings


# ============================================
# Permission Definitions
# ============================================

# All available permissions in the system
ALL_PERMISSIONS = {
    "dashboard": {
        "label": "Dashboard",
        "actions": ["view"],
        "description": "Access main dashboard overview"
    },
    "clients": {
        "label": "Client Management",
        "actions": ["view", "create", "edit", "delete", "export"],
        "description": "Manage client accounts and properties"
    },
    "leads": {
        "label": "Lead Management",
        "actions": ["view", "create", "edit", "delete", "export"],
        "description": "Manage leads and conversions"
    },
    "orders": {
        "label": "Orders",
        "actions": ["view", "create", "edit", "delete", "export"],
        "description": "Manage orders and fulfillment"
    },
    "reports": {
        "label": "Reports",
        "actions": ["view", "create", "export"],
        "description": "Generate and schedule reports"
    },
    "cms": {
        "label": "Site Builder",
        "actions": ["view", "create", "edit", "delete", "manage"],
        "description": "Manage website pages and content"
    },
    "support": {
        "label": "Support",
        "actions": ["view", "edit", "manage"],
        "description": "Handle support tickets and chat"
    },
    "billing": {
        "label": "Billing & Pricing",
        "actions": ["view", "edit", "manage"],
        "description": "Manage pricing and invoices"
    },
    "settings": {
        "label": "System Settings",
        "actions": ["view", "edit", "manage"],
        "description": "Configure system settings"
    },
    "team": {
        "label": "Team Management",
        "actions": ["view", "create", "edit", "delete", "manage"],
        "description": "Manage admin users and roles"
    },
    "analytics": {
        "label": "Analytics",
        "actions": ["view", "export"],
        "description": "View analytics and insights"
    },
    "enablement": {
        "label": "Enablement Engine",
        "actions": ["view", "edit", "manage"],
        "description": "Manage customer enablement automation"
    },
    "consent": {
        "label": "Privacy & Consent",
        "actions": ["view", "export", "manage"],
        "description": "Manage consent and compliance"
    },
}


# ============================================
# Built-in Role Templates
# ============================================

BUILT_IN_ROLES = {
    "super_admin": {
        "name": "Super Admin",
        "description": "Full system access with all permissions",
        "is_system": True,
        "permissions": {cat: list(ALL_PERMISSIONS[cat]["actions"]) for cat in ALL_PERMISSIONS}
    },
    "manager": {
        "name": "Manager",
        "description": "Operational management without billing/team access",
        "is_system": True,
        "permissions": {
            "dashboard": ["view"],
            "clients": ["view", "create", "edit", "export"],
            "leads": ["view", "create", "edit", "export"],
            "orders": ["view", "create", "edit", "export"],
            "reports": ["view", "create", "export"],
            "cms": ["view", "edit"],
            "support": ["view", "edit"],
            "analytics": ["view", "export"],
            "enablement": ["view"],
            "consent": ["view"],
        }
    },
    "viewer": {
        "name": "Viewer",
        "description": "Read-only access to most areas",
        "is_system": True,
        "permissions": {
            "dashboard": ["view"],
            "clients": ["view"],
            "leads": ["view"],
            "orders": ["view"],
            "reports": ["view"],
            "analytics": ["view"],
        }
    },
    "support_agent": {
        "name": "Support Agent",
        "description": "Handle support tickets and view client info",
        "is_system": True,
        "permissions": {
            "dashboard": ["view"],
            "clients": ["view"],
            "orders": ["view"],
            "support": ["view", "edit", "manage"],
        }
    },
    "content_manager": {
        "name": "Content Manager",
        "description": "Manage website content and CMS",
        "is_system": True,
        "permissions": {
            "dashboard": ["view"],
            "cms": ["view", "create", "edit", "delete", "manage"],
            "support": ["view"],
        }
    },
}


# ============================================
# Request/Response Models
# ============================================

class PermissionSet(BaseModel):
    """Permission set for a category"""
    category: str
    actions: List[str] = []


class CustomRoleCreate(BaseModel):
    """Create a custom role"""
    name: str = Field(..., min_length=2, max_length=50)
    description: Optional[str] = Field(None, max_length=200)
    permissions: Dict[str, List[str]]  # category -> actions


class CustomRoleUpdate(BaseModel):
    """Update a custom role"""
    name: Optional[str] = Field(None, min_length=2, max_length=50)
    description: Optional[str] = Field(None, max_length=200)
    permissions: Optional[Dict[str, List[str]]] = None
    is_active: Optional[bool] = None


class RoleResponse(BaseModel):
    """Role response model"""
    role_id: str
    name: str
    description: Optional[str]
    is_system: bool
    is_active: bool
    permissions: Dict[str, List[str]]
    user_count: int = 0
    created_at: str
    updated_at: Optional[str] = None
    created_by: Optional[str] = None


class AdminUserCreate(BaseModel):
    """Create admin user with role"""
    email: str
    name: str
    role_id: str  # Role to assign
    send_invite: bool = True


class AdminUserUpdate(BaseModel):
    """Update admin user"""
    name: Optional[str] = None
    role_id: Optional[str] = None
    is_active: Optional[bool] = None


class AdminUserResponse(BaseModel):
    """Admin user response"""
    portal_user_id: str
    email: str
    name: str
    role_id: str
    role_name: str
    status: str
    last_login: Optional[str] = None
    created_at: str


# ============================================
# Permission Check Helpers
# ============================================

def has_permission(user_permissions: Dict[str, List[str]], category: str, action: str) -> bool:
    """Check if user has specific permission"""
    if category not in user_permissions:
        return False
    return action in user_permissions[category] or "manage" in user_permissions[category]


def get_role_permissions(role_id: str, custom_roles: Dict[str, Any] = None) -> Dict[str, List[str]]:
    """Get permissions for a role"""
    # Check built-in roles
    if role_id in BUILT_IN_ROLES:
        return BUILT_IN_ROLES[role_id]["permissions"]
    
    # Check custom roles
    if custom_roles and role_id in custom_roles:
        return custom_roles[role_id].get("permissions", {})
    
    return {}
