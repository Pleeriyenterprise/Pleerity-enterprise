"""
Order Notification Service
Sends notifications (Email, SMS, In-app) for key order events.

Events that trigger notifications:
- New order received (PAID)
- Document ready for review (INTERNAL_REVIEW)
- Client input required (CLIENT_INPUT_REQUIRED)
- Document approved (FINALISING)
- Order delivered (COMPLETED)
- Delivery failed (DELIVERY_FAILED)
- Order failed (FAILED)
- High priority order flagged
- SLA breach warning
"""

import os
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any
from database import database
from models import EmailTemplateAlias

logger = logging.getLogger(__name__)

# Notification event types
class OrderNotificationEvent:
    NEW_ORDER = "new_order"
    DOCUMENT_READY = "document_ready"
    CLIENT_INPUT_REQUIRED = "client_input_required"
    DOCUMENT_APPROVED = "document_approved"
    ORDER_DELIVERED = "order_delivered"
    DELIVERY_FAILED = "delivery_failed"
    ORDER_FAILED = "order_failed"
    PRIORITY_FLAGGED = "priority_flagged"
    SLA_WARNING = "sla_warning"
    SLA_BREACH = "sla_breach"
    CLIENT_RESPONDED = "client_responded"
    REGENERATION_REQUESTED = "regeneration_requested"
    REGENERATION_COMPLETE = "regeneration_complete"


# Notification priorities
class NotificationPriority:
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


# Event configuration
EVENT_CONFIG = {
    OrderNotificationEvent.NEW_ORDER: {
        "title": "New Order Received",
        "icon": "📦",
        "priority": NotificationPriority.MEDIUM,
        "email_enabled": True,
        "sms_enabled": False,
        "in_app_enabled": True,
    },
    OrderNotificationEvent.DOCUMENT_READY: {
        "title": "Document Ready for Review",
        "icon": "📄",
        "priority": NotificationPriority.HIGH,
        "email_enabled": True,
        "sms_enabled": False,
        "in_app_enabled": True,
    },
    OrderNotificationEvent.CLIENT_INPUT_REQUIRED: {
        "title": "Waiting for Client Input",
        "icon": "⏳",
        "priority": NotificationPriority.MEDIUM,
        "email_enabled": False,
        "sms_enabled": False,
        "in_app_enabled": True,
    },
    OrderNotificationEvent.DOCUMENT_APPROVED: {
        "title": "Document Approved",
        "icon": "✅",
        "priority": NotificationPriority.LOW,
        "email_enabled": False,
        "sms_enabled": False,
        "in_app_enabled": True,
    },
    OrderNotificationEvent.ORDER_DELIVERED: {
        "title": "Order Delivered Successfully",
        "icon": "🎉",
        "priority": NotificationPriority.LOW,
        "email_enabled": False,
        "sms_enabled": False,
        "in_app_enabled": True,
    },
    OrderNotificationEvent.DELIVERY_FAILED: {
        "title": "Delivery Failed",
        "icon": "❌",
        "priority": NotificationPriority.HIGH,
        "email_enabled": True,
        "sms_enabled": True,
        "in_app_enabled": True,
    },
    OrderNotificationEvent.ORDER_FAILED: {
        "title": "Order Failed",
        "icon": "🚨",
        "priority": NotificationPriority.URGENT,
        "email_enabled": True,
        "sms_enabled": True,
        "in_app_enabled": True,
    },
    OrderNotificationEvent.PRIORITY_FLAGGED: {
        "title": "Priority Order Flagged",
        "icon": "🚩",
        "priority": NotificationPriority.HIGH,
        "email_enabled": True,
        "sms_enabled": False,
        "in_app_enabled": True,
    },
    OrderNotificationEvent.SLA_WARNING: {
        "title": "SLA Warning",
        "icon": "⚠️",
        "priority": NotificationPriority.HIGH,
        "email_enabled": True,
        "sms_enabled": False,
        "in_app_enabled": True,
    },
    OrderNotificationEvent.SLA_BREACH: {
        "title": "SLA Breached",
        "icon": "🔴",
        "priority": NotificationPriority.URGENT,
        "email_enabled": True,
        "sms_enabled": True,
        "in_app_enabled": True,
    },
    OrderNotificationEvent.CLIENT_RESPONDED: {
        "title": "Client Responded",
        "icon": "💬",
        "priority": NotificationPriority.MEDIUM,
        "email_enabled": True,
        "sms_enabled": False,
        "in_app_enabled": True,
    },
    OrderNotificationEvent.REGENERATION_REQUESTED: {
        "title": "Regeneration Requested",
        "icon": "🔄",
        "priority": NotificationPriority.MEDIUM,
        "email_enabled": False,
        "sms_enabled": False,
        "in_app_enabled": True,
    },
    OrderNotificationEvent.REGENERATION_COMPLETE: {
        "title": "Regeneration Complete",
        "icon": "✨",
        "priority": NotificationPriority.MEDIUM,
        "email_enabled": True,
        "sms_enabled": False,
        "in_app_enabled": True,
    },
}


class OrderNotificationService:
    """
    Service for sending order-related notifications to admins.
    """
    
    def __init__(self):
        self.email_service = None
        self.sms_service = None
    
    def _get_email_service(self):
        """Lazy load email service"""
        if not self.email_service:
            from services.email_service import EmailService
            self.email_service = EmailService()
        return self.email_service
    
    def _get_sms_service(self):
        """Lazy load SMS service"""
        if not self.sms_service:
            from services.sms_service import SMSService
            self.sms_service = SMSService()
        return self.sms_service
    
    async def _get_admin_preferences(self) -> List[Dict[str, Any]]:
        """Get all admins with their notification preferences."""
        db = database.get_db()
        
        admins = await db.portal_users.find(
            {"role": "ROLE_ADMIN"},
            {
                "_id": 0,
                "user_id": 1,
                "email": 1,
                "name": 1,
                "notification_preferences": 1,
            }
        ).to_list(length=100)
        
        return admins
    
    async def _create_in_app_notification(
        self,
        admin_id: str,
        event_type: str,
        title: str,
        message: str,
        order_id: str = None,
        priority: str = NotificationPriority.MEDIUM,
        metadata: Dict[str, Any] = None,
    ) -> str:
        """Create an in-app notification for an admin."""
        db = database.get_db()
        
        config = EVENT_CONFIG.get(event_type, {})
        icon = config.get("icon", "📌")
        
        notification = {
            "notification_id": f"NOTIF-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{admin_id[:8]}",
            "admin_id": admin_id,
            "event_type": event_type,
            "title": f"{icon} {title}",
            "message": message,
            "order_id": order_id,
            "priority": priority,
            "is_read": False,
            "created_at": datetime.now(timezone.utc),
            "metadata": metadata or {},
        }
        
        await db.admin_notifications.insert_one(notification)
        
        logger.debug(f"Created in-app notification for admin {admin_id}: {title}")
        
        return notification["notification_id"]
    
    async def notify_order_event(
        self,
        event_type: str,
        order_id: str,
        order: Dict[str, Any] = None,
        message: str = None,
        metadata: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Send notifications for an order event.
        
        Args:
            event_type: Type of event (from OrderNotificationEvent)
            order_id: The order ID
            order: Full order data (optional, will be fetched if not provided)
            message: Custom message (optional)
            metadata: Additional data to include in notification
            
        Returns:
            Summary of notifications sent
        """
        db = database.get_db()
        
        # Get event config
        config = EVENT_CONFIG.get(event_type)
        if not config:
            logger.warning(f"Unknown notification event type: {event_type}")
            return {"success": False, "error": "Unknown event type"}
        
        # Get order if not provided
        if not order:
            order = await db.orders.find_one({"order_id": order_id}, {"_id": 0})
        
        if not order:
            logger.warning(f"Order not found for notification: {order_id}")
            return {"success": False, "error": "Order not found"}
        
        # Build default message if not provided
        if not message:
            service_name = order.get("service_name", order.get("service_code", "Order"))
            customer_name = order.get("customer", {}).get("full_name", "Unknown")
            message = f"{service_name} for {customer_name}"
        
        title = config["title"]
        priority = config["priority"]
        
        # Get admin preferences
        admins = await self._get_admin_preferences()
        
        results = {
            "in_app": 0,
            "email": 0,
            "sms": 0,
            "errors": [],
        }
        
        for admin in admins:
            prefs = admin.get("notification_preferences", {})
            admin_id = admin.get("user_id")
            admin_email = admin.get("email")
            admin_phone = prefs.get("notification_phone")
            
            # In-app notification (always enabled by default)
            if config.get("in_app_enabled", True) and prefs.get("in_app_enabled", True):
                try:
                    await self._create_in_app_notification(
                        admin_id=admin_id,
                        event_type=event_type,
                        title=title,
                        message=message,
                        order_id=order_id,
                        priority=priority,
                        metadata=metadata,
                    )
                    results["in_app"] += 1
                except Exception as e:
                    logger.error(f"Failed to create in-app notification: {e}")
                    results["errors"].append(f"In-app ({admin_id}): {e}")
            
            # Email notification
            if config.get("email_enabled", False) and prefs.get("email_enabled", True):
                notification_email = prefs.get("notification_email") or admin_email
                if notification_email:
                    try:
                        email_service = self._get_email_service()
                        await email_service.send_email(
                            recipient=notification_email,
                            template_alias=EmailTemplateAlias.COMPLIANCE_ALERT,  # Generic alert template
                            template_model={
                                "client_name": admin.get("name", "Admin"),
                                "title": f"{config.get('icon', '')} {title}",
                                "message": f"Order: {order_id}\n\n{message}",
                                "portal_link": f"{os.environ.get('FRONTEND_URL', '')}/admin/orders",
                            },
                            subject=f"[Pleerity] {title}: {order_id}",
                        )
                        results["email"] += 1
                        logger.debug(f"Sent email notification to {notification_email}")
                    except Exception as e:
                        logger.error(f"Failed to send email notification: {e}")
                        results["errors"].append(f"Email ({notification_email}): {e}")
            
            # SMS notification (for urgent/high priority)
            if config.get("sms_enabled", False) and prefs.get("sms_enabled", False) and admin_phone:
                try:
                    sms_service = self._get_sms_service()
                    await sms_service.send_sms(
                        to=admin_phone,
                        message=f"[Pleerity] {title}\nOrder: {order_id}\n{message[:100]}",
                    )
                    results["sms"] += 1
                    logger.debug(f"Sent SMS notification to {admin_phone}")
                except Exception as e:
                    logger.error(f"Failed to send SMS notification: {e}")
                    results["errors"].append(f"SMS ({admin_phone}): {e}")
        
        logger.info(
            f"Order notification sent ({event_type}): "
            f"in_app={results['in_app']}, email={results['email']}, sms={results['sms']}"
        )
        
        return {
            "success": True,
            "event_type": event_type,
            "order_id": order_id,
            "notifications_sent": results,
        }
    
    # Convenience methods for specific events
    
    async def notify_new_order(self, order_id: str, order: Dict[str, Any] = None):
        """Notify admins of a new paid order."""
        return await self.notify_order_event(
            event_type=OrderNotificationEvent.NEW_ORDER,
            order_id=order_id,
            order=order,
        )
    
    async def notify_document_ready(self, order_id: str, version: int, order: Dict[str, Any] = None):
        """Notify admins that a document is ready for review."""
        return await self.notify_order_event(
            event_type=OrderNotificationEvent.DOCUMENT_READY,
            order_id=order_id,
            order=order,
            message=f"Document v{version} is ready for review",
            metadata={"version": version},
        )
    
    async def notify_delivery_failed(self, order_id: str, error: str, order: Dict[str, Any] = None):
        """Notify admins of a failed delivery."""
        return await self.notify_order_event(
            event_type=OrderNotificationEvent.DELIVERY_FAILED,
            order_id=order_id,
            order=order,
            message=f"Delivery failed: {error}",
            metadata={"error": error},
        )
    
    async def notify_order_failed(self, order_id: str, error: str, order: Dict[str, Any] = None):
        """Notify admins of a failed order."""
        return await self.notify_order_event(
            event_type=OrderNotificationEvent.ORDER_FAILED,
            order_id=order_id,
            order=order,
            message=f"Order processing failed: {error}",
            metadata={"error": error},
        )
    
    async def notify_priority_flagged(self, order_id: str, flagged_by: str, order: Dict[str, Any] = None):
        """Notify admins of a priority-flagged order."""
        return await self.notify_order_event(
            event_type=OrderNotificationEvent.PRIORITY_FLAGGED,
            order_id=order_id,
            order=order,
            message=f"Flagged as priority by {flagged_by}",
            metadata={"flagged_by": flagged_by},
        )
    
    async def notify_client_responded(self, order_id: str, order: Dict[str, Any] = None):
        """Notify admins that a client has responded to an info request."""
        return await self.notify_order_event(
            event_type=OrderNotificationEvent.CLIENT_RESPONDED,
            order_id=order_id,
            order=order,
            message="Client has submitted requested information",
        )
    
    async def notify_sla_warning(self, order_id: str, hours_remaining: float, order: Dict[str, Any] = None):
        """Notify admins of an SLA warning."""
        return await self.notify_order_event(
            event_type=OrderNotificationEvent.SLA_WARNING,
            order_id=order_id,
            order=order,
            message=f"SLA deadline approaching - {hours_remaining:.1f} hours remaining",
            metadata={"hours_remaining": hours_remaining},
        )
    
    async def notify_sla_breach(self, order_id: str, hours_overdue: float, order: Dict[str, Any] = None):
        """Notify admins of an SLA breach."""
        return await self.notify_order_event(
            event_type=OrderNotificationEvent.SLA_BREACH,
            order_id=order_id,
            order=order,
            message=f"SLA BREACHED - {hours_overdue:.1f} hours overdue",
            metadata={"hours_overdue": hours_overdue},
        )


# Singleton instance
order_notification_service = OrderNotificationService()
