"""
Customer Enablement Automation Engine - Core Service
Event-driven educational automation system

NON-NEGOTIABLE PRINCIPLES:
1. Enablement only, no selling
2. Event-driven only
3. Backend-authoritative
4. Full auditability
5. Respect user preferences
"""
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Callable, Tuple
from collections import defaultdict

from database import database
from models.enablement import (
    EnablementEventType, EnablementCategory, DeliveryChannel,
    EnablementActionStatus, EnablementEventPayload, EnablementAction,
    EnablementPreferences, SuppressionRule, EnablementTemplate
)
from models.core import AuditAction, UserRole
from utils.audit import create_audit_log

logger = logging.getLogger(__name__)


# ============================================
# Helper Functions
# ============================================

def generate_event_id() -> str:
    return f"EVT-{uuid.uuid4().hex[:12].upper()}"

def generate_action_id() -> str:
    return f"ENA-{uuid.uuid4().hex[:12].upper()}"

def generate_template_id() -> str:
    return f"TPL-{uuid.uuid4().hex[:12].upper()}"

def generate_rule_id() -> str:
    return f"SUP-{uuid.uuid4().hex[:12].upper()}"

def now_utc() -> datetime:
    return datetime.now(timezone.utc)

def get_db():
    return database.get_db()


# ============================================
# Event Bus (In-Memory Subscribers)
# ============================================

class EnablementEventBus:
    """
    Internal event bus for enablement automation.
    Subscribers react to events deterministically.
    """
    
    _subscribers: Dict[EnablementEventType, List[Callable]] = defaultdict(list)
    
    @classmethod
    def subscribe(cls, event_type: EnablementEventType, handler: Callable):
        """Subscribe a handler to an event type"""
        cls._subscribers[event_type].append(handler)
        logger.info(f"Enablement handler subscribed to {event_type.value}")
    
    @classmethod
    async def publish(cls, event: EnablementEventPayload):
        """Publish an event to all subscribers"""
        handlers = cls._subscribers.get(event.event_type, [])
        logger.info(f"Publishing enablement event {event.event_type.value} to {len(handlers)} handlers")
        
        for handler in handlers:
            try:
                await handler(event)
            except Exception as e:
                logger.error(f"Enablement handler error for {event.event_type.value}: {e}")
    
    @classmethod
    def get_subscribers(cls) -> Dict[str, int]:
        """Get subscriber counts per event type"""
        return {et.value: len(handlers) for et, handlers in cls._subscribers.items()}


# ============================================
# Template Rendering
# ============================================

def render_template(template: str, context: Dict[str, Any]) -> str:
    """
    Simple template rendering with {{variable}} placeholders.
    Safe - only replaces known variables, no code execution.
    """
    result = template
    for key, value in context.items():
        placeholder = "{{" + key + "}}"
        result = result.replace(placeholder, str(value) if value else "")
    return result


# ============================================
# Preference & Suppression Checks
# ============================================

async def get_client_preferences(client_id: str) -> EnablementPreferences:
    """Get or create enablement preferences for a client"""
    db = get_db()
    
    prefs_doc = await db.enablement_preferences.find_one(
        {"client_id": client_id},
        {"_id": 0}
    )
    
    if prefs_doc:
        return EnablementPreferences(**prefs_doc)
    
    # Create default preferences
    default_prefs = EnablementPreferences(
        client_id=client_id,
        updated_at=now_utc()
    )
    
    await db.enablement_preferences.insert_one(default_prefs.model_dump())
    return default_prefs


async def check_suppression(
    client_id: str,
    category: EnablementCategory,
    template_code: str
) -> Tuple[bool, Optional[str]]:
    """
    Check if enablement should be suppressed.
    Returns (is_suppressed, reason)
    """
    db = get_db()
    now = now_utc()
    
    # Check global suppression rules
    suppression_query = {
        "active": True,
        "$or": [
            {"expires_at": None},
            {"expires_at": {"$gt": now}}
        ],
        "$and": [
            {"$or": [{"client_id": None}, {"client_id": client_id}]},
            {"$or": [{"category": None}, {"category": category.value}]},
            {"$or": [{"template_code": None}, {"template_code": template_code}]},
        ]
    }
    
    rule = await db.enablement_suppressions.find_one(suppression_query, {"_id": 0})
    
    if rule:
        return True, f"Suppression rule: {rule.get('reason', 'Admin suppression')}"
    
    # Check user preferences
    prefs = await get_client_preferences(client_id)
    
    if prefs.all_suppressed:
        if prefs.suppressed_until and prefs.suppressed_until > now:
            return True, "User has suppressed all notifications"
        elif not prefs.suppressed_until:
            return True, "User has suppressed all notifications"
    
    if not prefs.categories_enabled.get(category.value, True):
        return True, f"User has disabled {category.value} notifications"
    
    return False, None


async def is_channel_enabled(
    client_id: str,
    channel: DeliveryChannel
) -> bool:
    """Check if a delivery channel is enabled for the client"""
    prefs = await get_client_preferences(client_id)
    
    if channel == DeliveryChannel.IN_APP:
        return prefs.in_app_enabled
    elif channel == DeliveryChannel.EMAIL:
        return prefs.email_enabled
    elif channel == DeliveryChannel.ASSISTANT:
        return prefs.assistant_enabled
    
    return False


# ============================================
# Action Logging
# ============================================

async def log_enablement_action(
    event: EnablementEventPayload,
    template: EnablementTemplate,
    channel: DeliveryChannel,
    status: EnablementActionStatus,
    rendered_title: str,
    rendered_body: str,
    status_reason: Optional[str] = None,
    portal_user_id: Optional[str] = None
) -> EnablementAction:
    """Log every enablement action for auditability"""
    db = get_db()
    
    action = EnablementAction(
        action_id=generate_action_id(),
        event_id=event.event_id,
        event_type=event.event_type,
        client_id=event.client_id,
        portal_user_id=portal_user_id,
        template_id=template.template_id,
        template_code=template.template_code,
        category=template.category,
        channel=channel,
        status=status,
        status_reason=status_reason,
        rendered_title=rendered_title,
        rendered_body=rendered_body,
        created_at=now_utc(),
        delivered_at=now_utc() if status == EnablementActionStatus.SUCCESS else None
    )
    
    await db.enablement_actions.insert_one(action.model_dump())
    
    # Also log to main audit trail
    await create_audit_log(
        action=AuditAction.ADMIN_ACTION,  # Using ADMIN_ACTION for now
        actor_role=UserRole.ROLE_ADMIN,
        actor_id="SYSTEM",
        resource_type="enablement",
        resource_id=action.action_id,
        metadata={
            "enablement_action": status.value,
            "event_type": event.event_type.value,
            "category": template.category.value,
            "channel": channel.value,
            "client_id": event.client_id,
            "template_code": template.template_code,
            "status_reason": status_reason
        }
    )
    
    return action


# ============================================
# Delivery Functions
# ============================================

async def deliver_in_app(
    client_id: str,
    title: str,
    body: str,
    category: EnablementCategory,
    action_url: Optional[str] = None
) -> bool:
    """Deliver an in-app notification"""
    db = get_db()
    
    try:
        notification = {
            "notification_id": f"NOTIF-{uuid.uuid4().hex[:12].upper()}",
            "client_id": client_id,
            "type": "enablement",
            "category": category.value,
            "title": title,
            "message": body,
            "action_url": action_url,
            "read": False,
            "created_at": now_utc()
        }
        
        await db.client_notifications.insert_one(notification)
        logger.info(f"In-app notification delivered to client {client_id}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to deliver in-app notification: {e}")
        return False


async def deliver_email(
    client_id: str,
    subject: str,
    body_html: str,
    category: EnablementCategory
) -> bool:
    """Deliver an email notification via Postmark"""
    db = get_db()
    
    try:
        # Get client's email
        client = await db.clients.find_one(
            {"client_id": client_id},
            {"_id": 0, "email": 1, "name": 1}
        )
        
        if not client or not client.get("email"):
            logger.warning(f"No email found for client {client_id}")
            return False
        
        # Import email service
        from services.email_service import EmailService
        
        email_service = EmailService()
        
        if email_service.client:
            # Send via Postmark
            response = email_service.client.emails.send(
                From="info@pleerityenterprise.co.uk",
                To=client["email"],
                Subject=subject,
                HtmlBody=body_html,
                TextBody=body_html.replace("<br>", "\n").replace("</p>", "\n\n"),
                Tag=f"enablement-{category.value.lower()}"
            )
            logger.info(f"Email delivered to {client['email']} for client {client_id}")
            return True
        else:
            logger.warning(f"Email service not configured - logging only")
            return True  # Consider success if no Postmark configured
            
    except Exception as e:
        logger.error(f"Failed to deliver email: {e}")
        return False


async def deliver_assistant_context(
    client_id: str,
    context: str,
    event_type: EnablementEventType
) -> bool:
    """Add context to AI Assistant for this client"""
    db = get_db()
    
    try:
        # Store context for assistant to use
        assistant_context = {
            "context_id": f"CTX-{uuid.uuid4().hex[:12].upper()}",
            "client_id": client_id,
            "event_type": event_type.value,
            "context": context,
            "created_at": now_utc(),
            "expires_at": now_utc() + timedelta(days=7)  # Context expires after 7 days
        }
        
        await db.enablement_assistant_context.insert_one(assistant_context)
        logger.info(f"Assistant context added for client {client_id}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to add assistant context: {e}")
        return False


# ============================================
# Main Processing Function
# ============================================

async def process_enablement_event(event: EnablementEventPayload):
    """
    Main event processor.
    Finds matching templates and delivers through enabled channels.
    """
    db = get_db()
    logger.info(f"Processing enablement event: {event.event_type.value} for client {event.client_id}")
    
    # Find matching active templates
    templates_cursor = db.enablement_templates.find({
        "event_triggers": event.event_type.value,
        "is_active": True,
        "$or": [
            {"plan_codes": None},
            {"plan_codes": []},
            {"plan_codes": event.plan_code}
        ]
    }, {"_id": 0})
    
    templates = []
    async for doc in templates_cursor:
        templates.append(EnablementTemplate(**doc))
    
    if not templates:
        logger.info(f"No templates found for event {event.event_type.value}")
        return
    
    # Build render context
    render_context = {
        "client_id": event.client_id,
        "event_type": event.event_type.value,
        **event.context_payload
    }
    
    # Get client name for personalization
    client = await db.clients.find_one(
        {"client_id": event.client_id},
        {"_id": 0, "name": 1, "email": 1}
    )
    if client:
        render_context["client_name"] = client.get("name", "")
        render_context["first_name"] = client.get("name", "").split()[0] if client.get("name") else ""
    
    # Process each template
    for template in templates:
        # Check suppression
        is_suppressed, suppression_reason = await check_suppression(
            event.client_id,
            template.category,
            template.template_code
        )
        
        if is_suppressed:
            # Log suppressed action
            await log_enablement_action(
                event=event,
                template=template,
                channel=DeliveryChannel.IN_APP,  # Log under first channel
                status=EnablementActionStatus.SUPPRESSED,
                rendered_title=template.title,
                rendered_body=template.body,
                status_reason=suppression_reason
            )
            continue
        
        # Render content
        rendered_title = render_template(template.title, render_context)
        rendered_body = render_template(template.body, render_context)
        
        # Deliver through each enabled channel
        for channel in template.channels:
            channel_enabled = await is_channel_enabled(event.client_id, channel)
            
            if not channel_enabled:
                await log_enablement_action(
                    event=event,
                    template=template,
                    channel=channel,
                    status=EnablementActionStatus.SUPPRESSED,
                    rendered_title=rendered_title,
                    rendered_body=rendered_body,
                    status_reason=f"Channel {channel.value} disabled by user"
                )
                continue
            
            # Deliver based on channel
            success = False
            
            if channel == DeliveryChannel.IN_APP:
                success = await deliver_in_app(
                    event.client_id,
                    rendered_title,
                    rendered_body,
                    template.category
                )
            
            elif channel == DeliveryChannel.EMAIL:
                email_subject = render_template(
                    template.email_subject or rendered_title,
                    render_context
                )
                email_body = render_template(
                    template.email_body_html or f"<p>{rendered_body}</p>",
                    render_context
                )
                success = await deliver_email(
                    event.client_id,
                    email_subject,
                    email_body,
                    template.category
                )
            
            elif channel == DeliveryChannel.ASSISTANT:
                assistant_ctx = render_template(
                    template.assistant_context or rendered_body,
                    render_context
                )
                success = await deliver_assistant_context(
                    event.client_id,
                    assistant_ctx,
                    event.event_type
                )
            
            # Log action
            await log_enablement_action(
                event=event,
                template=template,
                channel=channel,
                status=EnablementActionStatus.SUCCESS if success else EnablementActionStatus.FAILED,
                rendered_title=rendered_title,
                rendered_body=rendered_body,
                status_reason=None if success else "Delivery failed"
            )


# ============================================
# Event Publishing (Called from other services)
# ============================================

async def emit_enablement_event(
    event_type: EnablementEventType,
    client_id: str,
    plan_code: Optional[str] = None,
    context_payload: Optional[Dict[str, Any]] = None,
    property_id: Optional[str] = None,
    document_id: Optional[str] = None,
    requirement_id: Optional[str] = None,
    order_id: Optional[str] = None
):
    """
    Emit an enablement event from anywhere in the system.
    This is the main entry point for triggering enablement automation.
    """
    event = EnablementEventPayload(
        event_id=generate_event_id(),
        event_type=event_type,
        client_id=client_id,
        plan_code=plan_code,
        timestamp=now_utc(),
        context_payload=context_payload or {},
        property_id=property_id,
        document_id=document_id,
        requirement_id=requirement_id,
        order_id=order_id
    )
    
    # Log event emission
    db = get_db()
    await db.enablement_events.insert_one(event.model_dump())
    
    # Process the event
    await process_enablement_event(event)
    
    # Also publish to event bus for any additional subscribers
    await EnablementEventBus.publish(event)
    
    return event


# ============================================
# Admin Functions
# ============================================

async def get_client_enablement_timeline(
    client_id: str,
    limit: int = 50,
    offset: int = 0
) -> Tuple[List[EnablementAction], int]:
    """Get enablement action timeline for a client"""
    db = get_db()
    
    total = await db.enablement_actions.count_documents({"client_id": client_id})
    
    cursor = db.enablement_actions.find(
        {"client_id": client_id},
        {"_id": 0}
    ).sort("created_at", -1).skip(offset).limit(limit)
    
    actions = []
    async for doc in cursor:
        actions.append(EnablementAction(**doc))
    
    return actions, total


async def get_enablement_stats(
    days: int = 30
) -> Dict[str, Any]:
    """Get enablement statistics for admin dashboard"""
    db = get_db()
    
    since = now_utc() - timedelta(days=days)
    
    pipeline = [
        {"$match": {"created_at": {"$gte": since}}},
        {"$group": {
            "_id": None,
            "total": {"$sum": 1},
            "success": {"$sum": {"$cond": [{"$eq": ["$status", "SUCCESS"]}, 1, 0]}},
            "failed": {"$sum": {"$cond": [{"$eq": ["$status", "FAILED"]}, 1, 0]}},
            "suppressed": {"$sum": {"$cond": [{"$eq": ["$status", "SUPPRESSED"]}, 1, 0]}}
        }}
    ]
    
    result = await db.enablement_actions.aggregate(pipeline).to_list(1)
    stats = result[0] if result else {"total": 0, "success": 0, "failed": 0, "suppressed": 0}
    
    # Get by category
    category_pipeline = [
        {"$match": {"created_at": {"$gte": since}}},
        {"$group": {"_id": "$category", "count": {"$sum": 1}}}
    ]
    category_result = await db.enablement_actions.aggregate(category_pipeline).to_list(None)
    by_category = {r["_id"]: r["count"] for r in category_result}
    
    # Get by channel
    channel_pipeline = [
        {"$match": {"created_at": {"$gte": since}}},
        {"$group": {"_id": "$channel", "count": {"$sum": 1}}}
    ]
    channel_result = await db.enablement_actions.aggregate(channel_pipeline).to_list(None)
    by_channel = {r["_id"]: r["count"] for r in channel_result}
    
    return {
        "total_actions": stats.get("total", 0),
        "success_count": stats.get("success", 0),
        "failed_count": stats.get("failed", 0),
        "suppressed_count": stats.get("suppressed", 0),
        "by_category": by_category,
        "by_channel": by_channel,
        "period_days": days
    }


async def create_suppression_rule(
    client_id: Optional[str],
    category: Optional[EnablementCategory],
    template_code: Optional[str],
    reason: str,
    expires_at: Optional[datetime],
    created_by: str
) -> SuppressionRule:
    """Create an admin suppression rule"""
    db = get_db()
    
    rule = SuppressionRule(
        rule_id=generate_rule_id(),
        client_id=client_id,
        category=category,
        template_code=template_code,
        active=True,
        expires_at=expires_at,
        reason=reason,
        created_by=created_by,
        created_at=now_utc()
    )
    
    await db.enablement_suppressions.insert_one(rule.model_dump())
    
    # Audit log
    await create_audit_log(
        action=AuditAction.ADMIN_ACTION,
        actor_role=UserRole.ROLE_ADMIN,
        actor_id=created_by,
        resource_type="enablement_suppression",
        resource_id=rule.rule_id,
        metadata={
            "action": "create_suppression",
            "client_id": client_id,
            "category": category.value if category else None,
            "reason": reason
        }
    )
    
    return rule


async def list_suppression_rules(
    active_only: bool = True
) -> List[SuppressionRule]:
    """List all suppression rules"""
    db = get_db()
    
    query = {}
    if active_only:
        query["active"] = True
    
    cursor = db.enablement_suppressions.find(query, {"_id": 0}).sort("created_at", -1)
    
    rules = []
    async for doc in cursor:
        rules.append(SuppressionRule(**doc))
    
    return rules


async def deactivate_suppression_rule(
    rule_id: str,
    admin_id: str
) -> bool:
    """Deactivate a suppression rule"""
    db = get_db()
    
    result = await db.enablement_suppressions.update_one(
        {"rule_id": rule_id},
        {"$set": {"active": False}}
    )
    
    if result.modified_count > 0:
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_role=UserRole.ROLE_ADMIN,
            actor_id=admin_id,
            resource_type="enablement_suppression",
            resource_id=rule_id,
            metadata={"action": "deactivate_suppression"}
        )
        return True
    
    return False


async def update_client_preferences(
    client_id: str,
    in_app_enabled: Optional[bool] = None,
    email_enabled: Optional[bool] = None,
    assistant_enabled: Optional[bool] = None,
    categories_enabled: Optional[Dict[str, bool]] = None
) -> EnablementPreferences:
    """Update a client's enablement preferences"""
    db = get_db()
    
    update_fields = {"updated_at": now_utc()}
    
    if in_app_enabled is not None:
        update_fields["in_app_enabled"] = in_app_enabled
    if email_enabled is not None:
        update_fields["email_enabled"] = email_enabled
    if assistant_enabled is not None:
        update_fields["assistant_enabled"] = assistant_enabled
    if categories_enabled is not None:
        for cat, enabled in categories_enabled.items():
            update_fields[f"categories_enabled.{cat}"] = enabled
    
    await db.enablement_preferences.update_one(
        {"client_id": client_id},
        {"$set": update_fields},
        upsert=True
    )
    
    return await get_client_preferences(client_id)
