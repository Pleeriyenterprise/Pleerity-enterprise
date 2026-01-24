"""
Document Pack Webhook Handler

Specialized webhook processing for Document Pack orders.
Integrates Stripe payment confirmation with Document Pack Orchestrator.

Key Features:
- Validates service_code alignment before processing
- Creates document items from order selection
- Triggers generation workflow
- Handles pack tier inheritance
"""
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple

from database import database
from services.document_pack_orchestrator import (
    document_pack_orchestrator,
    SERVICE_CODE_TO_PACK_TIER,
    DOCUMENT_REGISTRY,
)

logger = logging.getLogger(__name__)


class DocumentPackWebhookHandler:
    """Handles webhook events for Document Pack orders."""
    
    # Valid document pack service codes
    VALID_PACK_CODES = {"DOC_PACK_ESSENTIAL", "DOC_PACK_PLUS", "DOC_PACK_PRO"}
    
    # Map intake field selections to doc_keys
    SELECTION_TO_DOC_KEY = {
        # Essential Pack
        "Rent Arrears Letter": "doc_rent_arrears_letter_template",
        "rent_arrears_letter": "doc_rent_arrears_letter_template",
        "Deposit Refund Letter": "doc_deposit_refund_letter_template",
        "deposit_refund_letter": "doc_deposit_refund_letter_template",
        "Tenant Reference Letter": "doc_tenant_reference_letter_template",
        "tenant_reference_letter": "doc_tenant_reference_letter_template",
        "Rent Receipt": "doc_rent_receipt_template",
        "rent_receipt": "doc_rent_receipt_template",
        "GDPR Notice": "doc_gdpr_notice_template",
        "gdpr_notice": "doc_gdpr_notice_template",
        
        # Plus Pack
        "AST Agreement": "doc_tenancy_agreement_ast_template",
        "tenancy_agreement_ast": "doc_tenancy_agreement_ast_template",
        "Tenancy Renewal": "doc_tenancy_renewal_template",
        "tenancy_renewal": "doc_tenancy_renewal_template",
        "Notice to Quit": "doc_notice_to_quit_template",
        "notice_to_quit": "doc_notice_to_quit_template",
        "Guarantor Agreement": "doc_guarantor_agreement_template",
        "guarantor_agreement": "doc_guarantor_agreement_template",
        "Rent Increase Notice": "doc_rent_increase_notice_template",
        "rent_increase_notice": "doc_rent_increase_notice_template",
        
        # Pro Pack
        "Inventory Report": "doc_inventory_condition_report",
        "inventory_condition_report": "doc_inventory_condition_report",
        "Deposit Information Pack": "doc_deposit_information_pack",
        "deposit_information_pack": "doc_deposit_information_pack",
        "Property Access Notice": "doc_property_access_notice",
        "property_access_notice": "doc_property_access_notice",
        "Additional Landlord Notice": "doc_additional_landlord_notice",
        "additional_landlord_notice": "doc_additional_landlord_notice",
    }
    
    async def handle_checkout_completed(
        self,
        session_data: Dict[str, Any],
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Handle checkout.session.completed event for Document Pack orders.
        
        Args:
            session_data: Stripe checkout session object
            
        Returns:
            Tuple of (success, message, details)
        """
        try:
            # Extract metadata
            metadata = session_data.get("metadata", {})
            order_id = metadata.get("order_id") or session_data.get("client_reference_id")
            service_code = metadata.get("service_code")
            
            if not order_id:
                return False, "Missing order_id in metadata", {}
            
            # Check if this is a document pack order
            if service_code not in self.VALID_PACK_CODES:
                logger.info(f"Not a document pack order: {service_code}")
                return True, "Not a document pack order, skipping", {"service_code": service_code}
            
            logger.info(f"Processing Document Pack order: {order_id} ({service_code})")
            
            # Get order from database
            db = database.get_db()
            order = await db.orders.find_one({"order_id": order_id}, {"_id": 0})
            
            if not order:
                return False, f"Order not found: {order_id}", {}
            
            # Update order with payment info
            now = datetime.now(timezone.utc)
            await db.orders.update_one(
                {"order_id": order_id},
                {
                    "$set": {
                        "status": "PAID",
                        "pricing.stripe_payment_intent_id": session_data.get("payment_intent"),
                        "pricing.stripe_checkout_session_id": session_data.get("id"),
                        "paid_at": now,
                        "updated_at": now,
                    }
                }
            )
            
            # Extract selected documents from order parameters
            selected_docs = await self._extract_selected_docs(order, service_code)
            
            if not selected_docs:
                logger.warning(f"No documents selected for order {order_id}, using all available")
                # Default to all docs for the pack tier
                selected_docs = document_pack_orchestrator.get_allowed_docs(
                    document_pack_orchestrator.get_pack_tier(service_code)
                )
            
            # Create document items
            input_data = self._prepare_input_data(order)
            
            items = await document_pack_orchestrator.create_document_items(
                order_id=order_id,
                service_code=service_code,
                selected_docs=selected_docs,
                input_data=input_data,
            )
            
            # Update order status to QUEUED
            await db.orders.update_one(
                {"order_id": order_id},
                {
                    "$set": {
                        "status": "QUEUED",
                        "queued_at": now,
                        "document_pack_info": {
                            "service_code": service_code,
                            "pack_tier": SERVICE_CODE_TO_PACK_TIER.get(service_code, "UNKNOWN").value,
                            "total_items": len(items),
                            "selected_docs": selected_docs,
                        },
                        "updated_at": now,
                    }
                }
            )
            
            logger.info(f"Document Pack order {order_id} processed: {len(items)} items created")
            
            return True, f"Document Pack order processed", {
                "order_id": order_id,
                "service_code": service_code,
                "items_created": len(items),
                "item_ids": [item.item_id for item in items],
            }
            
        except Exception as e:
            logger.error(f"Document Pack webhook handler error: {e}")
            return False, str(e), {}
    
    async def _extract_selected_docs(
        self,
        order: Dict[str, Any],
        service_code: str,
    ) -> list:
        """Extract selected document keys from order parameters."""
        selected_docs = []
        
        # Check order parameters for document selections
        parameters = order.get("parameters", {})
        
        # Handle "documents_required" field from intake
        documents_required = parameters.get("documents_required", [])
        if isinstance(documents_required, str):
            documents_required = [documents_required]
        
        for doc_selection in documents_required:
            doc_key = self.SELECTION_TO_DOC_KEY.get(doc_selection)
            if doc_key:
                selected_docs.append(doc_key)
        
        # Also check for individual document flags
        for field_name, doc_key in [
            ("include_rent_arrears", "doc_rent_arrears_letter_template"),
            ("include_deposit_letter", "doc_deposit_refund_letter_template"),
            ("include_reference_letter", "doc_tenant_reference_letter_template"),
            ("include_rent_receipt", "doc_rent_receipt_template"),
            ("include_gdpr_notice", "doc_gdpr_notice_template"),
            ("include_ast_agreement", "doc_tenancy_agreement_ast_template"),
            ("include_tenancy_renewal", "doc_tenancy_renewal_template"),
            ("include_notice_to_quit", "doc_notice_to_quit_template"),
            ("include_guarantor_agreement", "doc_guarantor_agreement_template"),
            ("include_rent_increase", "doc_rent_increase_notice_template"),
            ("include_inventory_report", "doc_inventory_condition_report"),
            ("include_deposit_info_pack", "doc_deposit_information_pack"),
            ("include_property_access", "doc_property_access_notice"),
            ("include_additional_notice", "doc_additional_landlord_notice"),
        ]:
            if parameters.get(field_name, False):
                if doc_key not in selected_docs:
                    selected_docs.append(doc_key)
        
        # If still no selections but order has selected_documents field
        if not selected_docs and order.get("selected_documents"):
            selected_docs = order.get("selected_documents", [])
        
        return selected_docs
    
    def _prepare_input_data(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare input data from order for document generation."""
        input_data = {}
        
        # Copy customer info
        customer = order.get("customer", {})
        input_data["customer_name"] = customer.get("full_name", "")
        input_data["customer_email"] = customer.get("email", "")
        input_data["customer_phone"] = customer.get("phone", "")
        input_data["customer_company"] = customer.get("company", "")
        
        # Copy all parameters
        parameters = order.get("parameters", {})
        input_data.update(parameters)
        
        # Add order metadata
        input_data["order_id"] = order.get("order_id")
        input_data["service_code"] = order.get("service_code")
        input_data["date_generated"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        
        return input_data
    
    async def validate_service_code(self, service_code: str) -> Tuple[bool, str]:
        """
        Validate that a service_code is valid for Document Pack processing.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not service_code:
            return False, "service_code is required"
        
        if service_code not in self.VALID_PACK_CODES:
            return False, f"Invalid document pack service_code: {service_code}. Must be one of: {', '.join(self.VALID_PACK_CODES)}"
        
        # Verify pack tier mapping exists
        if service_code not in SERVICE_CODE_TO_PACK_TIER:
            return False, f"service_code {service_code} not found in pack tier mapping"
        
        return True, ""
    
    async def get_pack_summary(self, service_code: str) -> Dict[str, Any]:
        """Get summary info about a document pack for checkout display."""
        is_valid, error = await self.validate_service_code(service_code)
        if not is_valid:
            return {"error": error}
        
        pack_info = document_pack_orchestrator.get_pack_info(service_code)
        
        return {
            "service_code": service_code,
            "pack_tier": pack_info.get("pack_tier"),
            "total_documents": pack_info.get("total_documents"),
            "documents": [
                {
                    "doc_key": doc["doc_key"],
                    "display_name": doc["display_name"],
                    "pack_tier": doc["pack_tier"],
                }
                for doc in pack_info.get("documents", [])
            ],
            "valid": True,
        }


# Singleton instance
document_pack_webhook_handler = DocumentPackWebhookHandler()
