"""
Enablement Templates Seeder
Pre-built educational templates for the automation engine

IMPORTANT: These templates are EDUCATIONAL ONLY
- No sales language
- No upgrade CTAs (except for FEATURE_GATE_EXPLANATION)
- No persuasion
- Informational and helpful tone
"""
from datetime import datetime, timezone
from database import database
from models.enablement import (
    EnablementEventType, EnablementCategory, DeliveryChannel, EnablementTemplate
)
import uuid
import logging

logger = logging.getLogger(__name__)


def generate_template_id():
    return f"TPL-{uuid.uuid4().hex[:12].upper()}"


def now_utc():
    return datetime.now(timezone.utc)


# ============================================
# ONBOARDING GUIDANCE TEMPLATES
# ============================================

ONBOARDING_TEMPLATES = [
    {
        "template_code": "welcome_intake_complete",
        "category": EnablementCategory.ONBOARDING_GUIDANCE,
        "event_triggers": [EnablementEventType.CLIENT_INTAKE_COMPLETED],
        "title": "Welcome to Compliance Vault Pro",
        "body": "Hi {{first_name}}, thank you for completing your intake. We're now setting up your compliance dashboard. This typically takes just a few minutes. You'll receive another notification when everything is ready.",
        "email_subject": "Welcome to Compliance Vault Pro - Setting Up Your Dashboard",
        "email_body_html": """
        <h2>Welcome to Compliance Vault Pro</h2>
        <p>Hi {{first_name}},</p>
        <p>Thank you for completing your intake form. We're now setting up your personalized compliance dashboard.</p>
        <p><strong>What happens next:</strong></p>
        <ul>
            <li>Your dashboard is being configured (usually takes 2-3 minutes)</li>
            <li>Your compliance requirements are being calculated</li>
            <li>You'll receive a notification when everything is ready</li>
        </ul>
        <p>If you have any questions, our support team is here to help.</p>
        """,
        "assistant_context": "The client {{client_id}} has just completed their intake. They are waiting for provisioning to complete. Be helpful and explain what's happening during this setup phase.",
        "channels": [DeliveryChannel.IN_APP, DeliveryChannel.EMAIL, DeliveryChannel.ASSISTANT],
    },
    {
        "template_code": "dashboard_ready",
        "category": EnablementCategory.ONBOARDING_GUIDANCE,
        "event_triggers": [EnablementEventType.PROVISIONING_COMPLETED],
        "title": "Your Dashboard is Ready",
        "body": "Great news, {{first_name}}! Your compliance dashboard has been set up successfully. You can now log in to view your properties, compliance requirements, and upload documents.",
        "email_subject": "Your Compliance Dashboard is Ready",
        "email_body_html": """
        <h2>Your Dashboard is Ready!</h2>
        <p>Hi {{first_name}},</p>
        <p>Your compliance dashboard has been set up and is ready for you to use.</p>
        <p><strong>Here's what you can do now:</strong></p>
        <ul>
            <li>View your properties and their compliance status</li>
            <li>See which documents are required</li>
            <li>Upload compliance certificates</li>
            <li>Track upcoming renewal dates</li>
        </ul>
        <p>Log in to your dashboard to get started.</p>
        """,
        "assistant_context": "The client {{client_id}} has just had their dashboard provisioned. Help them understand what they can do in the platform and guide them through first steps.",
        "channels": [DeliveryChannel.IN_APP, DeliveryChannel.EMAIL, DeliveryChannel.ASSISTANT],
    },
    {
        "template_code": "password_set_success",
        "category": EnablementCategory.ONBOARDING_GUIDANCE,
        "event_triggers": [EnablementEventType.PASSWORD_SET],
        "title": "Account Security Configured",
        "body": "Your password has been set successfully. Your account is now secure and ready to use.",
        "channels": [DeliveryChannel.IN_APP],
    },
    {
        "template_code": "first_login_guide",
        "category": EnablementCategory.ONBOARDING_GUIDANCE,
        "event_triggers": [EnablementEventType.FIRST_LOGIN],
        "title": "Welcome Back! Here's How to Get Started",
        "body": "Welcome to your dashboard, {{first_name}}! Start by reviewing your compliance requirements. Click on any property to see what documents are needed.",
        "assistant_context": "The client {{client_id}} has just logged in for the first time. Guide them through the dashboard features and help them understand their compliance requirements.",
        "channels": [DeliveryChannel.IN_APP, DeliveryChannel.ASSISTANT],
    },
]


# ============================================
# VALUE CONFIRMATION TEMPLATES
# ============================================

VALUE_CONFIRMATION_TEMPLATES = [
    {
        "template_code": "property_added_value",
        "category": EnablementCategory.VALUE_CONFIRMATION,
        "event_triggers": [EnablementEventType.PROPERTY_ADDED],
        "title": "Property Added Successfully",
        "body": "Your property at {{property_address}} has been added. We've automatically identified the compliance requirements based on your property type and location.",
        "email_subject": "Property Added: Compliance Requirements Identified",
        "email_body_html": """
        <h2>Property Added Successfully</h2>
        <p>Hi {{first_name}},</p>
        <p>Your property has been added to your compliance portfolio:</p>
        <p><strong>{{property_address}}</strong></p>
        <p>We've automatically identified the compliance requirements for this property based on:</p>
        <ul>
            <li>Property type</li>
            <li>Location and local regulations</li>
            <li>Tenancy type</li>
        </ul>
        <p>Log in to view the specific requirements and their due dates.</p>
        """,
        "channels": [DeliveryChannel.IN_APP, DeliveryChannel.EMAIL],
    },
    {
        "template_code": "document_uploaded_value",
        "category": EnablementCategory.VALUE_CONFIRMATION,
        "event_triggers": [EnablementEventType.DOCUMENT_UPLOADED],
        "title": "Document Received",
        "body": "Your document '{{document_name}}' has been uploaded successfully. We'll review it shortly to verify the compliance details.",
        "channels": [DeliveryChannel.IN_APP],
    },
    {
        "template_code": "document_verified_value",
        "category": EnablementCategory.VALUE_CONFIRMATION,
        "event_triggers": [EnablementEventType.DOCUMENT_VERIFIED],
        "title": "Document Verified ✓",
        "body": "Good news! Your '{{document_name}}' has been verified. This requirement is now marked as compliant until {{expiry_date}}.",
        "email_subject": "Document Verified - Compliance Updated",
        "email_body_html": """
        <h2>Document Verified</h2>
        <p>Hi {{first_name}},</p>
        <p>Your document has been reviewed and verified:</p>
        <p><strong>Document:</strong> {{document_name}}</p>
        <p><strong>Status:</strong> Verified ✓</p>
        <p><strong>Valid Until:</strong> {{expiry_date}}</p>
        <p>Your compliance status has been updated accordingly. We'll remind you before this document expires.</p>
        """,
        "channels": [DeliveryChannel.IN_APP, DeliveryChannel.EMAIL],
    },
    {
        "template_code": "compliance_score_calculated",
        "category": EnablementCategory.VALUE_CONFIRMATION,
        "event_triggers": [EnablementEventType.COMPLIANCE_SCORE_CALCULATED],
        "title": "Your Compliance Score",
        "body": "Your compliance score has been calculated: {{compliance_score}}%. This score reflects how many of your requirements are currently met.",
        "assistant_context": "The client {{client_id}} now has a compliance score of {{compliance_score}}%. Explain what this score means and how they can improve it if needed.",
        "channels": [DeliveryChannel.IN_APP, DeliveryChannel.ASSISTANT],
    },
    {
        "template_code": "report_generated_value",
        "category": EnablementCategory.VALUE_CONFIRMATION,
        "event_triggers": [EnablementEventType.REPORT_GENERATED],
        "title": "Report Ready",
        "body": "Your {{report_type}} report has been generated and is ready to download. You can access it from your reports section.",
        "channels": [DeliveryChannel.IN_APP],
    },
    {
        "template_code": "order_delivered_value",
        "category": EnablementCategory.VALUE_CONFIRMATION,
        "event_triggers": [EnablementEventType.ORDER_DELIVERED],
        "title": "Order Delivered",
        "body": "Your order ({{order_id}}) has been delivered. You should have received your documents. If you have any questions, please contact support.",
        "channels": [DeliveryChannel.IN_APP, DeliveryChannel.EMAIL],
    },
]


# ============================================
# COMPLIANCE AWARENESS TEMPLATES
# ============================================

COMPLIANCE_AWARENESS_TEMPLATES = [
    {
        "template_code": "status_changed_awareness",
        "category": EnablementCategory.COMPLIANCE_AWARENESS,
        "event_triggers": [EnablementEventType.COMPLIANCE_STATUS_CHANGED],
        "title": "Compliance Status Update",
        "body": "Your compliance status for {{property_address}} has changed from {{old_status}} to {{new_status}}. Log in to review the details.",
        "email_subject": "Compliance Status Update for Your Property",
        "email_body_html": """
        <h2>Compliance Status Update</h2>
        <p>Hi {{first_name}},</p>
        <p>There has been a change to your compliance status:</p>
        <p><strong>Property:</strong> {{property_address}}</p>
        <p><strong>Previous Status:</strong> {{old_status}}</p>
        <p><strong>Current Status:</strong> {{new_status}}</p>
        <p>Please log in to your dashboard to review the specific requirements that have changed.</p>
        <p><em>Note: This is a system-generated notification based on your tracked compliance data.</em></p>
        """,
        "assistant_context": "The client {{client_id}} property at {{property_address}} has changed compliance status from {{old_status}} to {{new_status}}. Explain what this means factually without giving legal advice.",
        "channels": [DeliveryChannel.IN_APP, DeliveryChannel.EMAIL, DeliveryChannel.ASSISTANT],
    },
    {
        "template_code": "requirement_expiring_soon",
        "category": EnablementCategory.COMPLIANCE_AWARENESS,
        "event_triggers": [EnablementEventType.REQUIREMENT_EXPIRING_SOON],
        "title": "Requirement Expiring Soon",
        "body": "Heads up: Your {{requirement_name}} for {{property_address}} expires on {{expiry_date}}. You may want to arrange renewal before then.",
        "email_subject": "Upcoming Expiry: {{requirement_name}}",
        "email_body_html": """
        <h2>Requirement Expiring Soon</h2>
        <p>Hi {{first_name}},</p>
        <p>This is a reminder that one of your compliance requirements is approaching its expiry date:</p>
        <p><strong>Requirement:</strong> {{requirement_name}}</p>
        <p><strong>Property:</strong> {{property_address}}</p>
        <p><strong>Expiry Date:</strong> {{expiry_date}}</p>
        <p>We recommend arranging for renewal before this date to maintain your compliance status.</p>
        <p><em>This is an automated reminder based on the expiry date recorded in your documents.</em></p>
        """,
        "channels": [DeliveryChannel.IN_APP, DeliveryChannel.EMAIL],
    },
    {
        "template_code": "requirement_overdue",
        "category": EnablementCategory.COMPLIANCE_AWARENESS,
        "event_triggers": [EnablementEventType.REQUIREMENT_OVERDUE],
        "title": "Requirement Overdue",
        "body": "Your {{requirement_name}} for {{property_address}} has expired as of {{expiry_date}}. Please arrange renewal at your earliest convenience.",
        "email_subject": "Action Needed: {{requirement_name}} Has Expired",
        "email_body_html": """
        <h2>Requirement Has Expired</h2>
        <p>Hi {{first_name}},</p>
        <p>One of your compliance requirements has passed its expiry date:</p>
        <p><strong>Requirement:</strong> {{requirement_name}}</p>
        <p><strong>Property:</strong> {{property_address}}</p>
        <p><strong>Expired On:</strong> {{expiry_date}}</p>
        <p>Please arrange for renewal and upload the new certificate when available.</p>
        <p><em>This notification is based on the expiry date recorded in your system. For guidance on specific legal requirements, please consult with appropriate authorities.</em></p>
        """,
        "channels": [DeliveryChannel.IN_APP, DeliveryChannel.EMAIL],
    },
]


# ============================================
# INACTIVITY SUPPORT TEMPLATES
# ============================================

INACTIVITY_SUPPORT_TEMPLATES = [
    {
        "template_code": "inactivity_gentle_nudge",
        "category": EnablementCategory.INACTIVITY_SUPPORT,
        "event_triggers": [EnablementEventType.INACTIVITY_DETECTED],
        "title": "We're Here to Help",
        "body": "Hi {{first_name}}, we noticed you haven't logged in recently. If you need any help with your compliance dashboard, our support team is available.",
        "email_subject": "Need Help with Your Compliance Dashboard?",
        "email_body_html": """
        <h2>We're Here to Help</h2>
        <p>Hi {{first_name}},</p>
        <p>We noticed it's been a while since you've visited your compliance dashboard.</p>
        <p>If you need any assistance, here are some helpful resources:</p>
        <ul>
            <li>Check your current compliance status</li>
            <li>Review upcoming renewal dates</li>
            <li>Access our help center</li>
        </ul>
        <p>If you have any questions, our support team is happy to help.</p>
        """,
        "channels": [DeliveryChannel.EMAIL],
        "delay_minutes": 0,
    },
    {
        "template_code": "no_action_after_reminder",
        "category": EnablementCategory.INACTIVITY_SUPPORT,
        "event_triggers": [EnablementEventType.NO_ACTION_AFTER_REMINDER],
        "title": "Friendly Reminder",
        "body": "Hi {{first_name}}, you have pending compliance items that may need attention. Log in when you have a moment to review them.",
        "channels": [DeliveryChannel.IN_APP],
    },
]


# ============================================
# FEATURE GATE EXPLANATION TEMPLATES
# ============================================

FEATURE_GATE_TEMPLATES = [
    {
        "template_code": "feature_blocked_explanation",
        "category": EnablementCategory.FEATURE_GATE_EXPLANATION,
        "event_triggers": [EnablementEventType.FEATURE_BLOCKED_BY_PLAN],
        "title": "Feature Not Available",
        "body": "The {{feature_name}} feature is not included in your current plan ({{current_plan}}). This feature allows you to {{feature_description}}.",
        "assistant_context": "The client {{client_id}} tried to access {{feature_name}} which is not available on their {{current_plan}} plan. Explain what the feature does factually. Only mention upgrade if they explicitly ask how to get access.",
        "channels": [DeliveryChannel.IN_APP, DeliveryChannel.ASSISTANT],
    },
]


# ============================================
# SEEDING FUNCTION
# ============================================

async def seed_enablement_templates():
    """Seed default enablement templates into the database"""
    db = database.get_db()
    
    all_templates = (
        ONBOARDING_TEMPLATES +
        VALUE_CONFIRMATION_TEMPLATES +
        COMPLIANCE_AWARENESS_TEMPLATES +
        INACTIVITY_SUPPORT_TEMPLATES +
        FEATURE_GATE_TEMPLATES
    )
    
    seeded_count = 0
    updated_count = 0
    
    for template_data in all_templates:
        template_code = template_data["template_code"]
        
        # Check if template exists
        existing = await db.enablement_templates.find_one(
            {"template_code": template_code}
        )
        
        template = {
            "template_id": existing["template_id"] if existing else generate_template_id(),
            "template_code": template_code,
            "category": template_data["category"].value,
            "event_triggers": [et.value for et in template_data["event_triggers"]],
            "title": template_data["title"],
            "body": template_data["body"],
            "email_subject": template_data.get("email_subject"),
            "email_body_html": template_data.get("email_body_html"),
            "assistant_context": template_data.get("assistant_context"),
            "channels": [ch.value for ch in template_data["channels"]],
            "delay_minutes": template_data.get("delay_minutes", 0),
            "plan_codes": template_data.get("plan_codes"),
            "version": (existing["version"] + 1) if existing else 1,
            "is_active": True,
            "created_at": existing["created_at"] if existing else now_utc(),
            "updated_at": now_utc(),
        }
        
        if existing:
            await db.enablement_templates.replace_one(
                {"template_code": template_code},
                template
            )
            updated_count += 1
        else:
            await db.enablement_templates.insert_one(template)
            seeded_count += 1
    
    logger.info(f"Enablement templates seeded: {seeded_count} new, {updated_count} updated")
    return {"seeded": seeded_count, "updated": updated_count}


async def ensure_enablement_indexes():
    """Create indexes for enablement collections"""
    db = database.get_db()
    
    # Events
    await db.enablement_events.create_index("event_id", unique=True)
    await db.enablement_events.create_index("client_id")
    await db.enablement_events.create_index("event_type")
    await db.enablement_events.create_index("timestamp")
    
    # Actions
    await db.enablement_actions.create_index("action_id", unique=True)
    await db.enablement_actions.create_index("client_id")
    await db.enablement_actions.create_index("event_id")
    await db.enablement_actions.create_index("status")
    await db.enablement_actions.create_index("created_at")
    
    # Templates
    await db.enablement_templates.create_index("template_id", unique=True)
    await db.enablement_templates.create_index("template_code", unique=True)
    await db.enablement_templates.create_index("event_triggers")
    await db.enablement_templates.create_index("is_active")
    
    # Preferences
    await db.enablement_preferences.create_index("client_id", unique=True)
    
    # Suppressions
    await db.enablement_suppressions.create_index("rule_id", unique=True)
    await db.enablement_suppressions.create_index("active")
    await db.enablement_suppressions.create_index("client_id")
    
    # Assistant context
    await db.enablement_assistant_context.create_index("context_id", unique=True)
    await db.enablement_assistant_context.create_index("client_id")
    await db.enablement_assistant_context.create_index("expires_at")
    
    # Client notifications
    await db.client_notifications.create_index("notification_id", unique=True)
    await db.client_notifications.create_index("client_id")
    await db.client_notifications.create_index("read")
    
    logger.info("Enablement indexes created")
