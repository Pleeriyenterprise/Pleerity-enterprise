"""Email Templates Management Routes - Admin only"""
from fastapi import APIRouter, HTTPException, Request, status
from database import database
from middleware import admin_route_guard
from models import EmailTemplate, EmailTemplateAlias, AuditAction
from utils.audit import create_audit_log
from datetime import datetime, timezone
from typing import Optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/templates", tags=["Admin - Email Templates"])

# Default email templates
DEFAULT_TEMPLATES = [
    {
        "alias": EmailTemplateAlias.PASSWORD_SETUP.value,
        "name": "Password Setup",
        "subject": "Set Your Password - Compliance Vault Pro",
        "available_variables": ["client_name", "setup_link", "company_name", "tagline"],
        "html_body": """
<html>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f9fafb;">
    <div style="background-color: white; border-radius: 8px; padding: 40px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
        <h1 style="color: #1a2744; margin-bottom: 24px;">Welcome to Compliance Vault Pro</h1>
        <p style="color: #374151; font-size: 16px; line-height: 1.6;">Hello {{client_name}},</p>
        <p style="color: #374151; font-size: 16px; line-height: 1.6;">Your compliance portal account has been created. Please set your password to get started.</p>
        <p style="margin: 30px 0; text-align: center;">
            <a href="{{setup_link}}" 
               style="background-color: #14b8a6; color: white; padding: 14px 32px; 
                      text-decoration: none; border-radius: 6px; display: inline-block; font-weight: 600;">
                Set Your Password
            </a>
        </p>
        <p style="color: #6b7280; font-size: 14px;">
            This link will expire in 24 hours. If you didn't request this, please ignore this email.
        </p>
    </div>
    <div style="text-align: center; margin-top: 24px;">
        <p style="color: #9ca3af; font-size: 12px;">
            {{company_name}}<br>
            {{tagline}}
        </p>
    </div>
</body>
</html>
        """,
        "text_body": """
Welcome to Compliance Vault Pro

Hello {{client_name}},

Your compliance portal account has been created. Please set your password to get started.

Set your password here: {{setup_link}}

This link will expire in 24 hours. If you didn't request this, please ignore this email.

--
{{company_name}}
{{tagline}}
        """
    },
    {
        "alias": EmailTemplateAlias.PORTAL_READY.value,
        "name": "Portal Ready",
        "subject": "Your Portal is Ready! - Compliance Vault Pro",
        "available_variables": ["client_name", "portal_link", "company_name", "tagline"],
        "html_body": """
<html>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f9fafb;">
    <div style="background-color: white; border-radius: 8px; padding: 40px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
        <h1 style="color: #1a2744; margin-bottom: 24px;">Your Portal is Ready!</h1>
        <p style="color: #374151; font-size: 16px; line-height: 1.6;">Hello {{client_name}},</p>
        <p style="color: #374151; font-size: 16px; line-height: 1.6;">Great news! Your Compliance Vault Pro portal is now ready to use. Access your dashboard to manage your property compliance requirements.</p>
        <p style="margin: 30px 0; text-align: center;">
            <a href="{{portal_link}}" 
               style="background-color: #14b8a6; color: white; padding: 14px 32px; 
                      text-decoration: none; border-radius: 6px; display: inline-block; font-weight: 600;">
                Access Your Portal
            </a>
        </p>
    </div>
    <div style="text-align: center; margin-top: 24px;">
        <p style="color: #9ca3af; font-size: 12px;">
            {{company_name}}<br>
            {{tagline}}
        </p>
    </div>
</body>
</html>
        """,
        "text_body": """
Your Portal is Ready!

Hello {{client_name}},

Great news! Your Compliance Vault Pro portal is now ready to use. Access your dashboard to manage your property compliance requirements.

Access your portal here: {{portal_link}}

--
{{company_name}}
{{tagline}}
        """
    },
    {
        "alias": EmailTemplateAlias.REMINDER.value,
        "name": "Compliance Reminder",
        "subject": "Action Required: {{requirement_name}} Due Soon",
        "available_variables": ["client_name", "requirement_name", "property_address", "due_date", "days_remaining", "portal_link", "company_name"],
        "html_body": """
<html>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f9fafb;">
    <div style="background-color: white; border-radius: 8px; padding: 40px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
        <div style="background-color: #fef3c7; border-left: 4px solid #f59e0b; padding: 16px; margin-bottom: 24px; border-radius: 4px;">
            <p style="color: #92400e; font-weight: 600; margin: 0;">Compliance Action Required</p>
        </div>
        <p style="color: #374151; font-size: 16px; line-height: 1.6;">Hello {{client_name}},</p>
        <p style="color: #374151; font-size: 16px; line-height: 1.6;">This is a reminder that <strong>{{requirement_name}}</strong> for your property at <strong>{{property_address}}</strong> is due on <strong>{{due_date}}</strong>.</p>
        <p style="color: #374151; font-size: 16px; line-height: 1.6;"><strong>{{days_remaining}} days remaining</strong> to complete this requirement.</p>
        <p style="margin: 30px 0; text-align: center;">
            <a href="{{portal_link}}" 
               style="background-color: #14b8a6; color: white; padding: 14px 32px; 
                      text-decoration: none; border-radius: 6px; display: inline-block; font-weight: 600;">
                View in Portal
            </a>
        </p>
    </div>
    <div style="text-align: center; margin-top: 24px;">
        <p style="color: #9ca3af; font-size: 12px;">{{company_name}}</p>
    </div>
</body>
</html>
        """,
        "text_body": """
Compliance Action Required

Hello {{client_name}},

This is a reminder that {{requirement_name}} for your property at {{property_address}} is due on {{due_date}}.

{{days_remaining}} days remaining to complete this requirement.

View in your portal: {{portal_link}}

--
{{company_name}}
        """
    },
    {
        "alias": EmailTemplateAlias.MONTHLY_DIGEST.value,
        "name": "Monthly Compliance Digest",
        "subject": "Your Monthly Compliance Summary - {{month_year}}",
        "available_variables": ["client_name", "month_year", "compliant_count", "pending_count", "overdue_count", "properties_count", "portal_link", "company_name"],
        "html_body": """
<html>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f9fafb;">
    <div style="background-color: white; border-radius: 8px; padding: 40px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
        <h1 style="color: #1a2744; margin-bottom: 24px;">Monthly Compliance Digest</h1>
        <p style="color: #374151; font-size: 16px; line-height: 1.6;">Hello {{client_name}},</p>
        <p style="color: #374151; font-size: 16px; line-height: 1.6;">Here's your compliance summary for {{month_year}}:</p>
        
        <div style="display: flex; gap: 16px; margin: 24px 0;">
            <div style="flex: 1; background-color: #ecfdf5; padding: 16px; border-radius: 8px; text-align: center;">
                <p style="font-size: 32px; font-weight: bold; color: #059669; margin: 0;">{{compliant_count}}</p>
                <p style="color: #065f46; font-size: 14px; margin: 4px 0 0 0;">Compliant</p>
            </div>
            <div style="flex: 1; background-color: #fef3c7; padding: 16px; border-radius: 8px; text-align: center;">
                <p style="font-size: 32px; font-weight: bold; color: #d97706; margin: 0;">{{pending_count}}</p>
                <p style="color: #92400e; font-size: 14px; margin: 4px 0 0 0;">Pending</p>
            </div>
            <div style="flex: 1; background-color: #fee2e2; padding: 16px; border-radius: 8px; text-align: center;">
                <p style="font-size: 32px; font-weight: bold; color: #dc2626; margin: 0;">{{overdue_count}}</p>
                <p style="color: #991b1b; font-size: 14px; margin: 4px 0 0 0;">Overdue</p>
            </div>
        </div>
        
        <p style="color: #6b7280; font-size: 14px;">Across {{properties_count}} properties</p>
        
        <p style="margin: 30px 0; text-align: center;">
            <a href="{{portal_link}}" 
               style="background-color: #14b8a6; color: white; padding: 14px 32px; 
                      text-decoration: none; border-radius: 6px; display: inline-block; font-weight: 600;">
                View Full Report
            </a>
        </p>
    </div>
    <div style="text-align: center; margin-top: 24px;">
        <p style="color: #9ca3af; font-size: 12px;">{{company_name}}</p>
    </div>
</body>
</html>
        """,
        "text_body": """
Monthly Compliance Digest

Hello {{client_name}},

Here's your compliance summary for {{month_year}}:

- Compliant: {{compliant_count}}
- Pending: {{pending_count}}
- Overdue: {{overdue_count}}

Across {{properties_count}} properties

View full report: {{portal_link}}

--
{{company_name}}
        """
    }
]


@router.get("")
async def list_templates(request: Request, active_only: bool = True):
    """List all email templates."""
    user = await admin_route_guard(request)
    db = database.get_db()
    
    try:
        query = {}
        if active_only:
            query["is_active"] = True
        
        templates = await db.email_templates.find(
            query,
            {"_id": 0}
        ).sort("alias", 1).to_list(100)
        
        total = await db.email_templates.count_documents(query)
        
        return {
            "templates": templates,
            "total": total
        }
    
    except Exception as e:
        logger.error(f"List templates error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list templates"
        )


@router.get("/aliases")
async def get_template_aliases(request: Request):
    """Get available template aliases."""
    await admin_route_guard(request)
    
    return {
        "aliases": [
            {"value": a.value, "label": a.value.replace("-", " ").title()}
            for a in EmailTemplateAlias
        ]
    }


@router.get("/{template_id}")
async def get_template(request: Request, template_id: str):
    """Get a specific template by ID."""
    user = await admin_route_guard(request)
    db = database.get_db()
    
    try:
        template = await db.email_templates.find_one(
            {"template_id": template_id},
            {"_id": 0}
        )
        
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Template not found"
            )
        
        return template
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get template error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get template"
        )


@router.post("")
async def create_template(request: Request):
    """Create a new email template."""
    user = await admin_route_guard(request)
    db = database.get_db()
    
    try:
        body = await request.json()
        
        # Check if template for this alias already exists
        existing = await db.email_templates.find_one(
            {"alias": body.get("alias")}
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Template for alias '{body.get('alias')}' already exists. Use update instead."
            )
        
        template = EmailTemplate(
            alias=EmailTemplateAlias(body.get("alias")),
            name=body.get("name"),
            subject=body.get("subject"),
            html_body=body.get("html_body"),
            text_body=body.get("text_body"),
            is_active=body.get("is_active", True),
            available_variables=body.get("available_variables", []),
            notes=body.get("notes"),
            created_by=user["portal_user_id"]
        )
        
        doc = template.model_dump()
        doc["alias"] = doc["alias"].value  # Convert enum to string
        for key in ["created_at", "updated_at"]:
            if doc.get(key):
                doc[key] = doc[key].isoformat()
        
        await db.email_templates.insert_one(doc)
        
        # Audit log
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_id=user["portal_user_id"],
            metadata={
                "action": "email_template_created",
                "template_id": template.template_id,
                "alias": template.alias.value,
                "admin_email": user["email"]
            }
        )
        
        logger.info(f"Email template created: {template.alias.value} by {user['email']}")
        
        return {
            "message": "Template created successfully",
            "template_id": template.template_id
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create template error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create template"
        )


@router.put("/{template_id}")
async def update_template(request: Request, template_id: str):
    """Update an existing email template."""
    user = await admin_route_guard(request)
    db = database.get_db()
    
    try:
        body = await request.json()
        
        existing = await db.email_templates.find_one(
            {"template_id": template_id},
            {"_id": 0}
        )
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Template not found"
            )
        
        update_fields = {}
        allowed_fields = [
            "name", "subject", "html_body", "text_body", 
            "is_active", "available_variables", "notes"
        ]
        
        for field in allowed_fields:
            if field in body:
                update_fields[field] = body[field]
        
        update_fields["updated_at"] = datetime.now(timezone.utc).isoformat()
        
        await db.email_templates.update_one(
            {"template_id": template_id},
            {"$set": update_fields}
        )
        
        # Audit log
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_id=user["portal_user_id"],
            metadata={
                "action": "email_template_updated",
                "template_id": template_id,
                "updated_fields": list(update_fields.keys()),
                "admin_email": user["email"]
            }
        )
        
        logger.info(f"Email template updated: {template_id} by {user['email']}")
        
        updated = await db.email_templates.find_one(
            {"template_id": template_id},
            {"_id": 0}
        )
        
        return {
            "message": "Template updated successfully",
            "template": updated
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update template error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update template"
        )


@router.delete("/{template_id}")
async def delete_template(request: Request, template_id: str):
    """Soft-delete an email template (sets is_active to False)."""
    user = await admin_route_guard(request)
    db = database.get_db()
    
    try:
        existing = await db.email_templates.find_one(
            {"template_id": template_id},
            {"_id": 0}
        )
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Template not found"
            )
        
        await db.email_templates.update_one(
            {"template_id": template_id},
            {"$set": {
                "is_active": False,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        
        # Audit log
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_id=user["portal_user_id"],
            metadata={
                "action": "email_template_deleted",
                "template_id": template_id,
                "alias": existing["alias"],
                "admin_email": user["email"]
            }
        )
        
        logger.info(f"Email template deleted: {template_id} by {user['email']}")
        
        return {"message": "Template deleted successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete template error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete template"
        )


@router.post("/seed")
async def seed_default_templates(request: Request):
    """Seed the database with default email templates."""
    user = await admin_route_guard(request)
    db = database.get_db()
    
    try:
        created_count = 0
        skipped_count = 0
        
        for template_data in DEFAULT_TEMPLATES:
            existing = await db.email_templates.find_one(
                {"alias": template_data["alias"]}
            )
            
            if existing:
                skipped_count += 1
                continue
            
            template = EmailTemplate(
                alias=EmailTemplateAlias(template_data["alias"]),
                name=template_data["name"],
                subject=template_data["subject"],
                html_body=template_data["html_body"].strip(),
                text_body=template_data["text_body"].strip(),
                available_variables=template_data["available_variables"],
                created_by="SYSTEM"
            )
            
            doc = template.model_dump()
            doc["alias"] = doc["alias"].value
            for key in ["created_at", "updated_at"]:
                if doc.get(key):
                    doc[key] = doc[key].isoformat()
            
            await db.email_templates.insert_one(doc)
            created_count += 1
        
        # Audit log
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_id=user["portal_user_id"],
            metadata={
                "action": "email_templates_seeded",
                "created": created_count,
                "skipped": skipped_count,
                "admin_email": user["email"]
            }
        )
        
        logger.info(f"Email templates seeded: {created_count} created, {skipped_count} skipped")
        
        return {
            "message": "Default templates seeded",
            "created": created_count,
            "skipped": skipped_count
        }
    
    except Exception as e:
        logger.error(f"Seed templates error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to seed templates"
        )


@router.post("/{template_id}/preview")
async def preview_template(request: Request, template_id: str):
    """Preview a template with sample data."""
    user = await admin_route_guard(request)
    db = database.get_db()
    
    try:
        body = await request.json()
        sample_data = body.get("sample_data", {})
        
        template = await db.email_templates.find_one(
            {"template_id": template_id},
            {"_id": 0}
        )
        
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Template not found"
            )
        
        # Default sample data
        defaults = {
            "client_name": "John Smith",
            "setup_link": "https://example.com/set-password?token=abc123",
            "portal_link": "https://example.com/app/dashboard",
            "company_name": "Pleerity Enterprise Ltd",
            "tagline": "AI-Driven Solutions & Compliance",
            "requirement_name": "Gas Safety Certificate",
            "property_address": "123 Test Street, London",
            "due_date": "January 31, 2026",
            "days_remaining": "14",
            "month_year": "January 2026",
            "compliant_count": "8",
            "pending_count": "3",
            "overdue_count": "1",
            "properties_count": "5"
        }
        
        # Merge with provided sample data
        data = {**defaults, **sample_data}
        
        # Render HTML
        html = template["html_body"]
        text = template["text_body"]
        subject = template["subject"]
        
        for key, value in data.items():
            placeholder = "{{" + key + "}}"
            html = html.replace(placeholder, str(value))
            text = text.replace(placeholder, str(value))
            subject = subject.replace(placeholder, str(value))
        
        return {
            "subject": subject,
            "html_body": html,
            "text_body": text,
            "sample_data_used": data
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Preview template error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to preview template"
        )
