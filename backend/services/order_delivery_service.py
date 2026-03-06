"""
Order Delivery Service
Handles the delivery automation for the Orders system.

Flow: FINALISING → DELIVERING → (webhook Delivery) → COMPLETED, or (send failure / webhook Bounce) → DELIVERY_FAILED

Features:
- Auto-detects orders in FINALISING status with approved documents
- Sends delivery email with document links (token-based view-order URL for one-time users)
- Creates delivery record on send; order stays DELIVERING until Postmark webhook "Delivery"
- Webhook handler transitions DELIVERING → COMPLETED (or DELIVERY_FAILED on Bounce)
- Resolves document list from document_versions_v2 when order.document_versions is empty
"""

import os
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any
from database import database
from services.order_workflow import OrderStatus
from services.order_service import transition_order_state, get_order
from services.order_email_templates import build_order_delivered_email

logger = logging.getLogger(__name__)

# Frontend URL for portal links
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
BACKEND_URL = os.getenv("REACT_APP_BACKEND_URL", "http://localhost:8001")


class OrderDeliveryService:
    """
    Service for handling order delivery automation.
    """
    
    def __init__(self):
        self.email_service = None  # Lazy-load to avoid circular imports
    
    def _get_email_service(self):
        """Get email service instance (lazy loaded)"""
        if not self.email_service:
            from services.email_service import EmailService
            self.email_service = EmailService()
        return self.email_service
    
    async def process_finalising_orders(self) -> Dict[str, Any]:
        """
        Background job: Find all orders in FINALISING status and process them.
        
        Returns summary of processed orders.
        """
        db = database.get_db()
        
        # Find orders in FINALISING with approved documents
        finalising_orders = await db.orders.find({
            "status": OrderStatus.FINALISING.value,
            "version_locked": True,
            "approved_document_version": {"$exists": True, "$ne": None}
        }).to_list(length=100)
        
        results = {
            "processed": 0,
            "delivered": 0,
            "failed": 0,
            "skipped": 0,
            "errors": []
        }
        
        for order in finalising_orders:
            try:
                result = await self.deliver_order(order["order_id"])
                results["processed"] += 1
                if result.get("success"):
                    results["delivered"] += 1
                else:
                    results["failed"] += 1
                    results["errors"].append({
                        "order_id": order["order_id"],
                        "error": result.get("error", "Unknown error")
                    })
            except Exception as e:
                results["processed"] += 1
                results["failed"] += 1
                results["errors"].append({
                    "order_id": order["order_id"],
                    "error": str(e)
                })
                logger.error(f"Failed to deliver order {order['order_id']}: {e}")
        
        return results
    
    async def deliver_order(self, order_id: str) -> Dict[str, Any]:
        """
        Deliver a single order.
        
        Steps:
        1. Validate order is in FINALISING state with approved document
        2. Transition to DELIVERING
        3. Send delivery email with document links
        4. Transition to COMPLETED (or DELIVERY_FAILED on error)
        
        Returns dict with success status and details.
        """
        db = database.get_db()
        
        # Get order
        order = await get_order(order_id)
        if not order:
            return {"success": False, "error": "Order not found"}
        
        # Validate state
        if order["status"] != OrderStatus.FINALISING.value:
            return {"success": False, "error": f"Order not in FINALISING state (current: {order['status']})"}
        
        if not order.get("version_locked"):
            return {"success": False, "error": "Order document not approved/locked"}
        
        approved_version = order.get("approved_document_version")
        if not approved_version:
            return {"success": False, "error": "No approved document version"}
        
        # Get customer info
        customer = order.get("customer", {})
        customer_email = customer.get("email")
        customer_name = customer.get("full_name", "Valued Customer")
        
        if not customer_email:
            return {"success": False, "error": "No customer email"}
        
        # Transition to DELIVERING
        try:
            await transition_order_state(
                order_id=order_id,
                new_status=OrderStatus.DELIVERING,
                triggered_by_type="system",
                reason="Auto-delivery initiated",
                metadata={"delivery_attempt": 1}
            )
        except Exception as e:
            logger.error(f"Failed to transition order {order_id} to DELIVERING: {e}")
            return {"success": False, "error": f"State transition failed: {e}"}
        
        # Build document list for email (from order.document_versions or document_versions_v2)
        documents = []
        document_versions = order.get("document_versions", [])
        for doc in document_versions:
            if doc.get("version") == approved_version:
                if doc.get("filename_pdf"):
                    documents.append({
                        "name": f"{order.get('service_name', 'Document')} (PDF)",
                        "filename": doc["filename_pdf"],
                        "format": "pdf"
                    })
                if doc.get("filename_docx"):
                    documents.append({
                        "name": f"{order.get('service_name', 'Document')} (DOCX)",
                        "filename": doc["filename_docx"],
                        "format": "docx"
                    })
                break

        if not documents:
            # Resolve from document_versions_v2 when order has no or legacy document_versions
            from services.document_generator import get_document_versions
            versions_v2 = await get_document_versions(order_id)
            for dv in versions_v2:
                if getattr(dv, "version", None) == approved_version:
                    if getattr(dv, "filename_pdf", None):
                        documents.append({
                            "name": f"{order.get('service_name', 'Document')} (PDF)",
                            "filename": dv.filename_pdf,
                            "format": "pdf"
                        })
                    if getattr(dv, "filename_docx", None):
                        documents.append({
                            "name": f"{order.get('service_name', 'Document')} (DOCX)",
                            "filename": dv.filename_docx,
                            "format": "docx"
                        })
                    break

        if not documents:
            # Rollback to FINALISING
            await transition_order_state(
                order_id=order_id,
                new_status=OrderStatus.FINALISING,
                triggered_by_type="system",
                reason="No documents found for approved version",
            )
            return {"success": False, "error": "No documents found for approved version"}
        
        # Build email: use token-based view-order URL so one-time users can access without login
        from services.order_view_token import generate_order_view_token
        view_token = generate_order_view_token(order_id, customer_email)
        download_link = f"{FRONTEND_URL}/view-order?token={view_token}"
        portal_link = f"{FRONTEND_URL}/dashboard"
        
        email_content = build_order_delivered_email(
            client_name=customer_name,
            order_reference=order_id,
            service_name=order.get("service_name", "Document Service"),
            documents=documents,
            download_link=download_link,
            portal_link=portal_link,
        )
        
        from services.notification_orchestrator import notification_orchestrator
        from repositories.services_repositories import delivery_repository
        delivery_success = False
        delivery_error = None
        postmark_message_id = None
        client_id = order.get("client_id")
        idempotency_key = f"{order_id}_ORDER_DELIVERED"
        try:
            result = await notification_orchestrator.send(
                template_key="ORDER_DELIVERED",
                client_id=client_id,
                context={
                    "client_name": customer_name,
                    "order_reference": order_id,
                    "service_name": order.get("service_name", "Document Service"),
                    "download_link": download_link,
                    "portal_link": portal_link,
                    "subject": email_content["subject"],
                },
                idempotency_key=idempotency_key,
                event_type="order_delivered",
            )
            delivery_success = result.outcome in ("sent", "duplicate_ignored")
            postmark_message_id = (result.details or {}).get("provider_message_id") if result.details else None
            if delivery_success:
                logger.info(f"Delivery email sent for order {order_id} to {customer_email}")
        except Exception as e:
            delivery_error = str(e)
            logger.error(f"Failed to send delivery email for order {order_id}: {e}")
        
        delivery_timestamp = datetime.now(timezone.utc)
        
        if delivery_success:
            # Create delivery record; order stays DELIVERING until Postmark webhook "Delivery"
            if postmark_message_id:
                try:
                    await delivery_repository.insert({
                        "order_id": order_id,
                        "channel": "email",
                        "status": "SENT",
                        "recipient": customer_email,
                        "postmark_message_id": postmark_message_id,
                        "provider_message_id": postmark_message_id,
                        "sent_at": delivery_timestamp,
                        "idempotency_key": idempotency_key,
                    })
                except Exception as e:
                    logger.warning(f"Failed to create delivery record for {order_id}: {e}")
            return {
                "success": True,
                "order_id": order_id,
                "delivered_to": customer_email,
                "documents_count": len(documents),
                "status": "DELIVERING",
                "message": "Email sent; order will complete when delivery is confirmed (webhook)",
            }
        
        else:
            # Transition to DELIVERY_FAILED
            try:
                await transition_order_state(
                    order_id=order_id,
                    new_status=OrderStatus.DELIVERY_FAILED,
                    triggered_by_type="system",
                    reason=f"Email delivery failed: {delivery_error}",
                    metadata={
                        "delivery_error": delivery_error,
                        "attempted_at": delivery_timestamp.isoformat(),
                        "attempted_to": customer_email,
                    }
                )
                
                # Send notification for failed delivery
                try:
                    from services.order_notification_service import order_notification_service
                    await order_notification_service.notify_delivery_failed(
                        order_id=order_id,
                        error=delivery_error,
                        order=order,
                    )
                except Exception as notif_error:
                    logger.warning(f"Failed to send delivery failure notification for {order_id}: {notif_error}")
                
                return {
                    "success": False,
                    "order_id": order_id,
                    "error": delivery_error,
                    "status": "DELIVERY_FAILED"
                }
                
            except Exception as e:
                logger.error(f"Failed to mark order {order_id} as DELIVERY_FAILED: {e}")
                return {"success": False, "error": f"State update failed: {e}"}
    
    async def retry_delivery(self, order_id: str) -> Dict[str, Any]:
        """
        Retry delivery for a failed order.
        
        Only works for orders in DELIVERY_FAILED status.
        """
        order = await get_order(order_id)
        if not order:
            return {"success": False, "error": "Order not found"}
        
        if order["status"] != OrderStatus.DELIVERY_FAILED.value:
            return {"success": False, "error": f"Order not in DELIVERY_FAILED state (current: {order['status']})"}
        
        # Transition back to FINALISING first
        await transition_order_state(
            order_id=order_id,
            new_status=OrderStatus.FINALISING,
            triggered_by_type="system",
            reason="Retrying delivery",
        )
        
        # Now attempt delivery again
        return await self.deliver_order(order_id)
    
    async def manual_complete(
        self,
        order_id: str,
        admin_email: str,
        reason: str,
    ) -> Dict[str, Any]:
        """
        Manually mark an order as completed (admin override).
        
        Use when delivery was done through alternative means.
        """
        db = database.get_db()
        
        order = await get_order(order_id)
        if not order:
            return {"success": False, "error": "Order not found"}
        
        if order["status"] in [OrderStatus.COMPLETED.value, OrderStatus.CANCELLED.value]:
            return {"success": False, "error": f"Order already in terminal state: {order['status']}"}
        
        completion_timestamp = datetime.now(timezone.utc)
        
        # Transition to COMPLETED
        await transition_order_state(
            order_id=order_id,
            new_status=OrderStatus.COMPLETED,
            triggered_by_type="admin",
            triggered_by_email=admin_email,
            reason=f"[MANUAL COMPLETION] {reason}",
            metadata={
                "manual_completion": True,
                "completed_by": admin_email,
            }
        )
        
        # Update timestamps
        await db.orders.update_one(
            {"order_id": order_id},
            {
                "$set": {
                    "completed_at": completion_timestamp,
                }
            }
        )
        
        return {
            "success": True,
            "order_id": order_id,
            "status": "COMPLETED",
            "completed_by": admin_email,
        }


# Singleton instance
order_delivery_service = OrderDeliveryService()
