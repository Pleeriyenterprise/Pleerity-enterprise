"""
Lead Management Service

Core business logic for lead capture, qualification, deduplication,
follow-up automation, and conversion tracking.

Handles:
- Lead CRUD operations
- Intent scoring
- Deduplication and merging
- Follow-up sequence management
- Lead → Client conversion
- Audit logging
"""
import logging
import uuid
import json
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Tuple
from database import database
from services.lead_models import (
    LeadSourcePlatform,
    LeadServiceInterest,
    LeadIntentScore,
    LeadStage,
    LeadStatus,
    FollowUpStatus,
    LeadAuditEvent,
    LeadCreateRequest,
    LeadUpdateRequest,
    FOLLOWUP_SEQUENCE,
    ABANDONED_INTAKE_SEQUENCE,
)

logger = logging.getLogger(__name__)

# Collections
LEADS_COLLECTION = "leads"
LEAD_AUDIT_COLLECTION = "lead_audit_logs"
LEAD_CONTACTS_COLLECTION = "lead_contacts"


def generate_lead_id() -> str:
    """Generate unique lead ID in format LEAD-XXXXXX."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    unique = uuid.uuid4().hex[:6].upper()
    return f"LEAD-{timestamp}-{unique}"


class LeadService:
    """Service for lead management operations."""
    
    @staticmethod
    async def create_lead(
        request: LeadCreateRequest,
        actor_id: Optional[str] = None,
        actor_type: str = "system",
        ip_address: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a new lead with deduplication check.
        Returns existing lead if duplicate found.
        """
        db = database.get_db()
        now = datetime.now(timezone.utc).isoformat()
        
        # Check for duplicates before creating
        existing = await LeadService.find_duplicate(
            email=request.email,
            phone=request.phone,
            source_metadata=request.source_metadata,
        )
        
        if existing:
            # Return existing lead instead of creating duplicate
            logger.info(f"Duplicate lead found: {existing['lead_id']} for email={request.email}")
            return {
                **existing,
                "is_duplicate": True,
                "original_lead_id": existing["lead_id"],
            }
        
        lead_id = generate_lead_id()
        
        # Calculate intent score if not provided
        intent_score = request.intent_score or await LeadService.calculate_intent_score(
            source_platform=request.source_platform,
            service_interest=request.service_interest,
            has_phone=bool(request.phone),
            message=request.message_summary,
        )
        
        # Determine follow-up sequence
        followup_sequence = "abandoned_intake" if request.source_platform == LeadSourcePlatform.INTAKE_ABANDONED else "default"
        
        lead_doc = {
            "lead_id": lead_id,
            "source_platform": request.source_platform.value,
            "service_interest": request.service_interest.value,
            
            # Contact info
            "name": request.name,
            "email": request.email,
            "phone": request.phone,
            "company_name": request.company_name,
            
            # Qualification
            "intent_score": intent_score.value,
            "stage": LeadStage.NEW.value,
            "status": LeadStatus.ACTIVE.value,
            
            # Context
            "message_summary": request.message_summary,
            "conversation_id": request.conversation_id,
            "intake_draft_id": request.intake_draft_id,
            "ai_summary": None,
            
            # Source metadata (social-ready)
            "source_metadata": request.source_metadata or {},
            
            # UTM tracking
            "utm_source": request.utm_source,
            "utm_medium": request.utm_medium,
            "utm_campaign": request.utm_campaign,
            "utm_content": request.utm_content,
            "utm_term": request.utm_term,
            "referrer_url": request.referrer_url,
            
            # Consent & follow-up
            "marketing_consent": request.marketing_consent,
            "followup_status": FollowUpStatus.PENDING.value if request.marketing_consent else FollowUpStatus.OPTED_OUT.value,
            "followup_sequence": followup_sequence,
            "followup_step": 0,
            "last_followup_at": None,
            "next_followup_at": None,
            
            # Assignment
            "assigned_to": None,
            "assigned_at": None,
            
            # Timestamps
            "created_at": now,
            "updated_at": now,
            "last_contacted_at": None,
            "converted_at": None,
            
            # Conversion tracking
            "client_id": None,
            "conversion_notes": None,
            
            # Lost tracking
            "lost_reason": None,
            "lost_competitor": None,
            "lost_at": None,
            
            # Merge tracking
            "merged_into_lead_id": None,
            "merged_from_lead_ids": [],
            
            # Admin
            "admin_notes": request.admin_notes,
            
            # SLA tracking
            "sla_breach": False,
            "sla_breach_at": None,
            "sla_hours": 24,  # Default 24 hours, can be changed to business hours later
        }
        
        # Calculate next follow-up time if consent given
        if request.marketing_consent:
            lead_doc["next_followup_at"] = (
                datetime.now(timezone.utc) + timedelta(hours=1)
            ).isoformat()
        
        await db[LEADS_COLLECTION].insert_one(lead_doc)
        
        # Remove MongoDB _id for response
        lead_doc.pop("_id", None)
        
        # Audit log
        await LeadService.log_audit(
            event=LeadAuditEvent.LEAD_CREATED,
            lead_id=lead_id,
            actor_id=actor_id,
            actor_type=actor_type,
            details={
                "source_platform": request.source_platform.value,
                "service_interest": request.service_interest.value,
                "intent_score": intent_score.value,
                "marketing_consent": request.marketing_consent,
                "email": request.email,
            },
            ip_address=ip_address,
        )
        
        logger.info(f"Lead created: {lead_id} from {request.source_platform.value}")
        
        # Send HIGH intent notification to admins
        if intent_score == LeadIntentScore.HIGH:
            await LeadService.notify_high_intent_lead(lead_doc)
        
        return {**lead_doc, "is_duplicate": False}
    
    @staticmethod
    async def find_duplicate(
        email: Optional[str] = None,
        phone: Optional[str] = None,
        source_metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Find existing lead by email, phone, or social platform ID.
        Returns None if no duplicate found.
        """
        db = database.get_db()
        
        # Build OR conditions for deduplication
        conditions = []
        
        if email:
            conditions.append({"email": email.lower()})
        
        if phone:
            # Normalize phone number
            normalized_phone = phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
            conditions.append({"phone": {"$regex": normalized_phone[-10:]}})  # Last 10 digits
        
        # Check social platform lead IDs
        if source_metadata:
            if source_metadata.get("facebook_lead_id"):
                conditions.append({"source_metadata.facebook_lead_id": source_metadata["facebook_lead_id"]})
            if source_metadata.get("instagram_lead_id"):
                conditions.append({"source_metadata.instagram_lead_id": source_metadata["instagram_lead_id"]})
            if source_metadata.get("linkedin_lead_id"):
                conditions.append({"source_metadata.linkedin_lead_id": source_metadata["linkedin_lead_id"]})
        
        if not conditions:
            return None
        
        # Find active leads only (not merged)
        existing = await db[LEADS_COLLECTION].find_one(
            {
                "$and": [
                    {"$or": conditions},
                    {"status": {"$ne": LeadStatus.MERGED.value}},
                ]
            },
            {"_id": 0}
        )
        
        return existing
    
    @staticmethod
    async def calculate_intent_score(
        source_platform: LeadSourcePlatform,
        service_interest: LeadServiceInterest,
        has_phone: bool = False,
        message: Optional[str] = None,
        property_count: int = 0,
        reached_payment: bool = False,
    ) -> LeadIntentScore:
        """
        Calculate lead intent score based on signals.
        """
        # HIGH intent conditions
        if service_interest == LeadServiceInterest.CVP and property_count >= 3:
            return LeadIntentScore.HIGH
        
        if source_platform == LeadSourcePlatform.INTAKE_ABANDONED and reached_payment:
            return LeadIntentScore.HIGH
        
        if message:
            message_lower = message.lower()
            high_intent_keywords = ["pricing", "price", "cost", "quote", "demo", "trial", "buy", "purchase", "sign up"]
            if any(kw in message_lower for kw in high_intent_keywords):
                return LeadIntentScore.HIGH
        
        # MEDIUM intent conditions
        if service_interest in [LeadServiceInterest.CVP, LeadServiceInterest.DOCUMENT_PACKS, LeadServiceInterest.COMPLIANCE_AUDITS]:
            return LeadIntentScore.MEDIUM
        
        if has_phone:
            return LeadIntentScore.MEDIUM
        
        if source_platform == LeadSourcePlatform.INTAKE_ABANDONED:
            return LeadIntentScore.MEDIUM
        
        # Default to LOW
        return LeadIntentScore.LOW
    
    @staticmethod
    async def get_lead(lead_id: str) -> Optional[Dict[str, Any]]:
        """Get a lead by ID."""
        db = database.get_db()
        return await db[LEADS_COLLECTION].find_one(
            {"lead_id": lead_id},
            {"_id": 0}
        )
    
    @staticmethod
    async def get_lead_by_email(email: str) -> Optional[Dict[str, Any]]:
        """Get a lead by email."""
        db = database.get_db()
        return await db[LEADS_COLLECTION].find_one(
            {"email": email.lower(), "status": {"$ne": LeadStatus.MERGED.value}},
            {"_id": 0}
        )
    
    @staticmethod
    async def list_leads(
        source_platform: Optional[str] = None,
        service_interest: Optional[str] = None,
        stage: Optional[str] = None,
        intent_score: Optional[str] = None,
        status: Optional[str] = None,
        assigned_to: Optional[str] = None,
        search: Optional[str] = None,
        sla_breach_only: bool = False,
        page: int = 1,
        limit: int = 50,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """List leads with filters and pagination."""
        db = database.get_db()
        
        # Build filter
        filter_query = {"status": {"$ne": LeadStatus.MERGED.value}}  # Exclude merged leads
        
        if source_platform:
            filter_query["source_platform"] = source_platform
        if service_interest:
            filter_query["service_interest"] = service_interest
        if stage:
            filter_query["stage"] = stage
        if intent_score:
            filter_query["intent_score"] = intent_score
        if status:
            filter_query["status"] = status
        if assigned_to:
            filter_query["assigned_to"] = assigned_to
        if sla_breach_only:
            filter_query["sla_breach"] = True
        
        if search:
            filter_query["$or"] = [
                {"name": {"$regex": search, "$options": "i"}},
                {"email": {"$regex": search, "$options": "i"}},
                {"phone": {"$regex": search, "$options": "i"}},
                {"company_name": {"$regex": search, "$options": "i"}},
                {"lead_id": {"$regex": search, "$options": "i"}},
            ]
        
        # Get leads
        skip = (page - 1) * limit
        cursor = db[LEADS_COLLECTION].find(
            filter_query,
            {"_id": 0}
        ).sort([("created_at", -1)]).skip(skip).limit(limit)
        
        leads = await cursor.to_list(length=limit)
        total = await db[LEADS_COLLECTION].count_documents(filter_query)
        
        return leads, total
    
    @staticmethod
    async def update_lead(
        lead_id: str,
        request: LeadUpdateRequest,
        actor_id: str,
        actor_type: str = "admin",
    ) -> Optional[Dict[str, Any]]:
        """Update a lead."""
        db = database.get_db()
        now = datetime.now(timezone.utc).isoformat()
        
        # Get current state for audit
        current = await db[LEADS_COLLECTION].find_one({"lead_id": lead_id}, {"_id": 0})
        if not current:
            return None
        
        # Build update
        update_data = {"updated_at": now}
        
        if request.name is not None:
            update_data["name"] = request.name
        if request.email is not None:
            update_data["email"] = request.email.lower()
        if request.phone is not None:
            update_data["phone"] = request.phone
        if request.company_name is not None:
            update_data["company_name"] = request.company_name
        if request.service_interest is not None:
            update_data["service_interest"] = request.service_interest.value
        if request.message_summary is not None:
            update_data["message_summary"] = request.message_summary
        if request.intent_score is not None:
            update_data["intent_score"] = request.intent_score.value
        if request.stage is not None:
            update_data["stage"] = request.stage.value
        if request.assigned_to is not None:
            update_data["assigned_to"] = request.assigned_to
            update_data["assigned_at"] = now
        if request.admin_notes is not None:
            update_data["admin_notes"] = request.admin_notes
        if request.marketing_consent is not None:
            update_data["marketing_consent"] = request.marketing_consent
            # Update follow-up status based on consent
            if not request.marketing_consent:
                update_data["followup_status"] = FollowUpStatus.OPTED_OUT.value
        
        await db[LEADS_COLLECTION].update_one(
            {"lead_id": lead_id},
            {"$set": update_data}
        )
        
        # Audit log
        await LeadService.log_audit(
            event=LeadAuditEvent.LEAD_UPDATED,
            lead_id=lead_id,
            actor_id=actor_id,
            actor_type=actor_type,
            details={
                "before": {k: current.get(k) for k in update_data.keys() if k != "updated_at"},
                "after": {k: v for k, v in update_data.items() if k != "updated_at"},
            },
        )
        
        return await LeadService.get_lead(lead_id)
    
    @staticmethod
    async def assign_lead(
        lead_id: str,
        admin_id: str,
        assigned_by: str,
        notify_admin: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """Assign a lead to an admin."""
        db = database.get_db()
        now = datetime.now(timezone.utc).isoformat()
        
        # Get current assignee for audit
        current = await db[LEADS_COLLECTION].find_one({"lead_id": lead_id}, {"_id": 0})
        if not current:
            return None
        
        previous_assignee = current.get("assigned_to")
        
        await db[LEADS_COLLECTION].update_one(
            {"lead_id": lead_id},
            {
                "$set": {
                    "assigned_to": admin_id,
                    "assigned_at": now,
                    "updated_at": now,
                }
            }
        )
        
        # Audit log
        await LeadService.log_audit(
            event=LeadAuditEvent.LEAD_ASSIGNED,
            lead_id=lead_id,
            actor_id=assigned_by,
            actor_type="admin",
            details={
                "previous_assignee": previous_assignee,
                "new_assignee": admin_id,
                "notify_admin": notify_admin,
            },
        )
        
        # TODO: Send notification email to assigned admin if notify_admin
        
        return await LeadService.get_lead(lead_id)
    
    @staticmethod
    async def log_contact(
        lead_id: str,
        contact_method: str,
        actor_id: str,
        notes: Optional[str] = None,
        outcome: Optional[str] = None,
    ) -> bool:
        """Log a contact attempt with a lead."""
        db = database.get_db()
        now = datetime.now(timezone.utc).isoformat()
        
        # Update lead
        await db[LEADS_COLLECTION].update_one(
            {"lead_id": lead_id},
            {
                "$set": {
                    "last_contacted_at": now,
                    "updated_at": now,
                    "sla_breach": False,  # Reset SLA breach on contact
                }
            }
        )
        
        # Create contact record
        contact_doc = {
            "lead_id": lead_id,
            "contact_method": contact_method,
            "contacted_by": actor_id,
            "contacted_at": now,
            "notes": notes,
            "outcome": outcome,
        }
        await db[LEAD_CONTACTS_COLLECTION].insert_one(contact_doc)
        
        # Audit log
        await LeadService.log_audit(
            event=LeadAuditEvent.LEAD_CONTACTED,
            lead_id=lead_id,
            actor_id=actor_id,
            actor_type="admin",
            details={
                "contact_method": contact_method,
                "outcome": outcome,
            },
        )
        
        return True
    
    @staticmethod
    async def convert_lead(
        lead_id: str,
        client_id: str,
        actor_id: str,
        conversion_notes: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Convert a lead to a client.
        Preserves lead record with link to client.
        """
        db = database.get_db()
        now = datetime.now(timezone.utc).isoformat()
        
        # Update lead
        await db[LEADS_COLLECTION].update_one(
            {"lead_id": lead_id},
            {
                "$set": {
                    "status": LeadStatus.CONVERTED.value,
                    "stage": LeadStage.WON.value,
                    "client_id": client_id,
                    "converted_at": now,
                    "conversion_notes": conversion_notes,
                    "updated_at": now,
                    "followup_status": FollowUpStatus.STOPPED.value,
                }
            }
        )
        
        # Also update the client record with lead_id for attribution
        await db["clients"].update_one(
            {"client_id": client_id},
            {"$set": {"lead_id": lead_id, "lead_source": True}}
        )
        
        # Audit log
        await LeadService.log_audit(
            event=LeadAuditEvent.LEAD_CONVERTED,
            lead_id=lead_id,
            actor_id=actor_id,
            actor_type="admin",
            details={
                "client_id": client_id,
                "conversion_notes": conversion_notes,
            },
        )
        
        logger.info(f"Lead {lead_id} converted to client {client_id}")
        
        return await LeadService.get_lead(lead_id)
    
    @staticmethod
    async def mark_lost(
        lead_id: str,
        reason: str,
        actor_id: str,
        competitor: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Mark a lead as lost."""
        db = database.get_db()
        now = datetime.now(timezone.utc).isoformat()
        
        await db[LEADS_COLLECTION].update_one(
            {"lead_id": lead_id},
            {
                "$set": {
                    "status": LeadStatus.LOST.value,
                    "stage": LeadStage.LOST.value,
                    "lost_reason": reason,
                    "lost_competitor": competitor,
                    "lost_at": now,
                    "updated_at": now,
                    "followup_status": FollowUpStatus.STOPPED.value,
                }
            }
        )
        
        # Audit log
        await LeadService.log_audit(
            event=LeadAuditEvent.LEAD_MARKED_LOST,
            lead_id=lead_id,
            actor_id=actor_id,
            actor_type="admin",
            details={
                "reason": reason,
                "competitor": competitor,
            },
        )
        
        return await LeadService.get_lead(lead_id)
    
    @staticmethod
    async def merge_leads(
        primary_lead_id: str,
        secondary_lead_id: str,
        actor_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Merge secondary lead into primary.
        Secondary lead is marked as merged, not deleted.
        """
        db = database.get_db()
        now = datetime.now(timezone.utc).isoformat()
        
        # Get both leads
        primary = await LeadService.get_lead(primary_lead_id)
        secondary = await LeadService.get_lead(secondary_lead_id)
        
        if not primary or not secondary:
            return None
        
        # Update secondary as merged
        await db[LEADS_COLLECTION].update_one(
            {"lead_id": secondary_lead_id},
            {
                "$set": {
                    "status": LeadStatus.MERGED.value,
                    "merged_into_lead_id": primary_lead_id,
                    "updated_at": now,
                    "followup_status": FollowUpStatus.STOPPED.value,
                }
            }
        )
        
        # Update primary with merge tracking
        merged_from = primary.get("merged_from_lead_ids", [])
        merged_from.append(secondary_lead_id)
        
        await db[LEADS_COLLECTION].update_one(
            {"lead_id": primary_lead_id},
            {
                "$set": {
                    "merged_from_lead_ids": merged_from,
                    "updated_at": now,
                },
                # Append secondary's message to primary if exists
                "$push": {
                    "merged_messages": {
                        "from_lead_id": secondary_lead_id,
                        "message": secondary.get("message_summary"),
                        "merged_at": now,
                    }
                } if secondary.get("message_summary") else {}
            }
        )
        
        # Audit log
        await LeadService.log_audit(
            event=LeadAuditEvent.LEAD_MERGED,
            lead_id=primary_lead_id,
            actor_id=actor_id,
            actor_type="admin",
            details={
                "merged_lead_id": secondary_lead_id,
                "secondary_email": secondary.get("email"),
            },
        )
        
        return await LeadService.get_lead(primary_lead_id)
    
    @staticmethod
    async def update_followup_status(
        lead_id: str,
        status: FollowUpStatus,
        step: int = None,
    ):
        """Update follow-up automation status."""
        db = database.get_db()
        now = datetime.now(timezone.utc).isoformat()
        
        update_data = {
            "followup_status": status.value,
            "updated_at": now,
        }
        
        if step is not None:
            update_data["followup_step"] = step
            update_data["last_followup_at"] = now
        
        await db[LEADS_COLLECTION].update_one(
            {"lead_id": lead_id},
            {"$set": update_data}
        )
    
    @staticmethod
    async def get_stats() -> Dict[str, Any]:
        """Get lead statistics."""
        db = database.get_db()
        
        # Base filter - exclude merged
        base_filter = {"status": {"$ne": LeadStatus.MERGED.value}}
        
        total = await db[LEADS_COLLECTION].count_documents(base_filter)
        new = await db[LEADS_COLLECTION].count_documents({**base_filter, "stage": LeadStage.NEW.value})
        contacted = await db[LEADS_COLLECTION].count_documents({**base_filter, "stage": LeadStage.CONTACTED.value})
        qualified = await db[LEADS_COLLECTION].count_documents({**base_filter, "stage": LeadStage.QUALIFIED.value})
        converted = await db[LEADS_COLLECTION].count_documents({**base_filter, "status": LeadStatus.CONVERTED.value})
        lost = await db[LEADS_COLLECTION].count_documents({**base_filter, "status": LeadStatus.LOST.value})
        
        # Conversion rate
        conversion_rate = (converted / total * 100) if total > 0 else 0
        
        # Leads by source
        source_pipeline = [
            {"$match": base_filter},
            {"$group": {"_id": "$source_platform", "count": {"$sum": 1}}},
        ]
        leads_by_source = {}
        async for doc in db[LEADS_COLLECTION].aggregate(source_pipeline):
            leads_by_source[doc["_id"]] = doc["count"]
        
        # Leads by service interest
        service_pipeline = [
            {"$match": base_filter},
            {"$group": {"_id": "$service_interest", "count": {"$sum": 1}}},
        ]
        leads_by_service = {}
        async for doc in db[LEADS_COLLECTION].aggregate(service_pipeline):
            leads_by_service[doc["_id"]] = doc["count"]
        
        # Leads by intent
        intent_pipeline = [
            {"$match": base_filter},
            {"$group": {"_id": "$intent_score", "count": {"$sum": 1}}},
        ]
        leads_by_intent = {}
        async for doc in db[LEADS_COLLECTION].aggregate(intent_pipeline):
            leads_by_intent[doc["_id"]] = doc["count"]
        
        # SLA breaches today
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0).isoformat()
        sla_breaches = await db[LEADS_COLLECTION].count_documents({
            **base_filter,
            "sla_breach": True,
            "sla_breach_at": {"$gte": today_start},
        })
        
        return {
            "total_leads": total,
            "new_leads": new,
            "contacted_leads": contacted,
            "qualified_leads": qualified,
            "converted_leads": converted,
            "lost_leads": lost,
            "conversion_rate": round(conversion_rate, 2),
            "avg_time_to_contact_hours": None,  # TODO: Calculate
            "leads_by_source": leads_by_source,
            "leads_by_service": leads_by_service,
            "leads_by_intent": leads_by_intent,
            "sla_breaches_today": sla_breaches,
        }
    
    @staticmethod
    async def log_audit(
        event: LeadAuditEvent,
        lead_id: str,
        actor_id: Optional[str],
        actor_type: str,
        details: Dict[str, Any],
        ip_address: Optional[str] = None,
    ):
        """Create audit log entry."""
        db = database.get_db()
        now = datetime.now(timezone.utc).isoformat()
        
        await db[LEAD_AUDIT_COLLECTION].insert_one({
            "event": event.value,
            "lead_id": lead_id,
            "actor_id": actor_id,
            "actor_type": actor_type,
            "details": details,
            "ip_address": ip_address,
            "created_at": now,
        })
    
    @staticmethod
    async def get_audit_log(lead_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get audit log for a lead."""
        db = database.get_db()
        
        cursor = db[LEAD_AUDIT_COLLECTION].find(
            {"lead_id": lead_id},
            {"_id": 0}
        ).sort("created_at", -1).limit(limit)
        
        return await cursor.to_list(length=limit)
    
    @staticmethod
    async def notify_high_intent_lead(lead: Dict[str, Any]):
        """
        Send immediate notification to admins when a HIGH intent lead is captured.
        Uses Postmark for email delivery.
        """
        import os
        
        POSTMARK_SERVER_TOKEN = os.environ.get("POSTMARK_SERVER_TOKEN")
        ADMIN_NOTIFICATION_EMAILS = os.environ.get(
            "ADMIN_NOTIFICATION_EMAILS", 
            "admin@pleerity.com"
        ).split(",")
        SUPPORT_EMAIL = os.environ.get("SUPPORT_EMAIL", "info@pleerityenterprise.co.uk")
        ADMIN_DASHBOARD_URL = os.environ.get(
            "ADMIN_DASHBOARD_URL",
            "https://leadsquared.preview.emergentagent.com/admin/leads"
        )
        
        if not POSTMARK_SERVER_TOKEN or POSTMARK_SERVER_TOKEN == "leadsquared":
            logger.warning("Postmark not properly configured, skipping HIGH intent notification")
            return
        
        try:
            from postmarker.core import PostmarkClient
            
            lead_id = lead.get("lead_id")
            name = lead.get("name") or "Unknown"
            email = lead.get("email") or "No email"
            phone = lead.get("phone") or "No phone"
            service = lead.get("service_interest", "UNKNOWN").replace("_", " ")
            source = lead.get("source_platform", "UNKNOWN").replace("_", " ")
            message = lead.get("message_summary") or "No message"
            
            subject = f"🔥 HIGH Intent Lead: {name} interested in {service}"
            
            html_body = f"""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <div style="background: linear-gradient(135deg, #10B981, #059669); color: white; padding: 20px; border-radius: 8px 8px 0 0;">
                        <h1 style="margin: 0; font-size: 24px;">🔥 High Intent Lead Alert</h1>
                        <p style="margin: 5px 0 0 0; opacity: 0.9;">Immediate follow-up recommended</p>
                    </div>
                    
                    <div style="background: #f8f9fa; padding: 20px; border: 1px solid #e9ecef; border-top: none;">
                        <h2 style="color: #1f2937; margin-top: 0;">Lead Details</h2>
                        <table style="width: 100%; border-collapse: collapse;">
                            <tr>
                                <td style="padding: 8px 0; font-weight: bold; color: #6b7280;">Lead ID:</td>
                                <td style="padding: 8px 0;">{lead_id}</td>
                            </tr>
                            <tr>
                                <td style="padding: 8px 0; font-weight: bold; color: #6b7280;">Name:</td>
                                <td style="padding: 8px 0;">{name}</td>
                            </tr>
                            <tr>
                                <td style="padding: 8px 0; font-weight: bold; color: #6b7280;">Email:</td>
                                <td style="padding: 8px 0;"><a href="mailto:{email}">{email}</a></td>
                            </tr>
                            <tr>
                                <td style="padding: 8px 0; font-weight: bold; color: #6b7280;">Phone:</td>
                                <td style="padding: 8px 0;"><a href="tel:{phone}">{phone}</a></td>
                            </tr>
                            <tr>
                                <td style="padding: 8px 0; font-weight: bold; color: #6b7280;">Service Interest:</td>
                                <td style="padding: 8px 0;"><strong style="color: #059669;">{service}</strong></td>
                            </tr>
                            <tr>
                                <td style="padding: 8px 0; font-weight: bold; color: #6b7280;">Source:</td>
                                <td style="padding: 8px 0;">{source}</td>
                            </tr>
                        </table>
                        
                        <div style="margin-top: 15px; padding: 15px; background: white; border-left: 4px solid #10B981; border-radius: 4px;">
                            <strong>Message:</strong>
                            <p style="margin: 10px 0 0 0; color: #4b5563;">{message}</p>
                        </div>
                        
                        <div style="margin-top: 20px; text-align: center;">
                            <a href="{ADMIN_DASHBOARD_URL}" style="display: inline-block; background: #10B981; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold;">
                                View Lead in Dashboard →
                            </a>
                        </div>
                    </div>
                    
                    <div style="padding: 15px; text-align: center; color: #6b7280; font-size: 12px;">
                        <p>This is an automated notification from Pleerity Lead Management System</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            text_body = f"""
HIGH INTENT LEAD ALERT
======================

Lead ID: {lead_id}
Name: {name}
Email: {email}
Phone: {phone}
Service Interest: {service}
Source: {source}

Message:
{message}

View in dashboard: {ADMIN_DASHBOARD_URL}

---
Pleerity Lead Management System
            """
            
            postmark_client = PostmarkClient(server_token=POSTMARK_SERVER_TOKEN)
            
            for admin_email in ADMIN_NOTIFICATION_EMAILS:
                admin_email = admin_email.strip()
                if admin_email:
                    try:
                        postmark_client.emails.send(
                            From=SUPPORT_EMAIL,
                            To=admin_email,
                            Subject=subject,
                            HtmlBody=html_body,
                            TextBody=text_body,
                            Tag="high_intent_lead_notification",
                            Metadata={
                                "lead_id": lead_id,
                                "intent_score": "HIGH",
                            },
                        )
                        logger.info(f"HIGH intent notification sent to {admin_email} for lead {lead_id}")
                    except Exception as e:
                        logger.error(f"Failed to send HIGH intent notification to {admin_email}: {e}")
            
            # Also log this notification
            await LeadService.log_audit(
                event=LeadAuditEvent.LEAD_CREATED,
                lead_id=lead_id,
                actor_id="system",
                actor_type="notification",
                details={
                    "notification_type": "high_intent_alert",
                    "recipients": ADMIN_NOTIFICATION_EMAILS,
                },
            )
            
        except ImportError:
            logger.warning("postmarker not available, skipping HIGH intent notification")
        except Exception as e:
            logger.error(f"Failed to send HIGH intent notification: {e}")


class AbandonedIntakeService:
    """Service for detecting and creating leads from abandoned intakes."""
    
    @staticmethod
    async def detect_abandoned_intakes(timeout_hours: float = 1.0) -> List[str]:
        """
        Detect intake drafts that are abandoned.
        Creates leads for each abandoned intake.
        
        Returns list of created lead IDs.
        """
        db = database.get_db()
        now = datetime.now(timezone.utc)
        cutoff = (now - timedelta(hours=timeout_hours)).isoformat()
        
        # Find drafts that:
        # 1. Were updated more than X hours ago
        # 2. Have DRAFT or in_progress status (not completed)
        # 3. Have not already been converted to leads
        # 4. Have some meaningful data (client_identity with email, or selected service)
        
        abandoned_drafts = await db["intake_drafts"].find({
            "updated_at": {"$lt": cutoff},
            "status": {"$in": ["DRAFT", "draft", "in_progress", "PENDING"]},
            "lead_created": {"$ne": True},
            "$or": [
                {"client_identity.email": {"$exists": True, "$nin": [None, ""]}},
                {"intake_payload.email": {"$exists": True, "$nin": [None, ""]}},
            ],
        }, {"_id": 0}).to_list(length=100)
        
        created_leads = []
        
        for draft in abandoned_drafts:
            # Extract info from draft - handle both structures
            client_identity = draft.get("client_identity", {})
            intake_payload = draft.get("intake_payload", {})
            
            # Try client_identity first, then intake_payload
            contact_email = client_identity.get("email") or intake_payload.get("email")
            contact_name = (
                client_identity.get("full_name") or 
                client_identity.get("name") or
                intake_payload.get("name") or 
                intake_payload.get("company_name")
            )
            contact_phone = client_identity.get("phone") or intake_payload.get("phone")
            company_name = client_identity.get("company_name") or intake_payload.get("company_name")
            
            # Get service info
            service_code = draft.get("service_code", "UNKNOWN")
            selected_plan = intake_payload.get("selected_plan")
            properties = intake_payload.get("properties", [])
            property_count = len(properties)
            
            if not contact_email:
                logger.debug(f"Skipping draft {draft.get('draft_id')}: no email found")
                continue  # Cannot create lead without email
            
            # Map service interest
            service_interest = LeadServiceInterest.UNKNOWN
            if "CVP" in service_code or "VAULT" in service_code:
                service_interest = LeadServiceInterest.CVP
            elif "DOC" in service_code or "PACK" in service_code:
                service_interest = LeadServiceInterest.DOCUMENT_PACKS
            elif "AI" in service_code or "AUTOMATION" in service_code:
                service_interest = LeadServiceInterest.AUTOMATION
            
            # Build message summary
            message_parts = [f"Abandoned intake for {service_code}"]
            if selected_plan:
                message_parts.append(f"Plan: {selected_plan}")
            if property_count > 0:
                message_parts.append(f"Properties: {property_count}")
            message_summary = ". ".join(message_parts)
            
            # Create lead
            request = LeadCreateRequest(
                source_platform=LeadSourcePlatform.INTAKE_ABANDONED,
                service_interest=service_interest,
                name=contact_name,
                email=contact_email,
                phone=contact_phone,
                company_name=company_name,
                intake_draft_id=draft.get("draft_id"),
                message_summary=message_summary,
                marketing_consent=intake_payload.get("marketing_consent", False) or 
                                  client_identity.get("marketing_consent", False),
            )
            
            lead = await LeadService.create_lead(
                request=request,
                actor_id="system",
                actor_type="automation",
            )
            
            if not lead.get("is_duplicate"):
                created_leads.append(lead["lead_id"])
                
                # Mark draft as lead_created to prevent duplicates
                await db["intake_drafts"].update_one(
                    {"draft_id": draft["draft_id"]},
                    {"$set": {"lead_created": True, "lead_id": lead["lead_id"]}}
                )
                
                logger.info(f"Created lead {lead['lead_id']} from abandoned intake {draft['draft_id']}")
            else:
                logger.debug(f"Duplicate lead found for abandoned intake {draft['draft_id']}")
        
        if created_leads:
            logger.info(f"Created {len(created_leads)} leads from abandoned intakes")
        
        return created_leads
