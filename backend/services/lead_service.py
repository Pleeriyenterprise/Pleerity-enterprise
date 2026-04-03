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
from services.lead_scoring import (
    recalculate_lead_score as recalc_lead_score,
    should_update_stage,
    HOT_LEAD_SCORE_THRESHOLD,
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


def _initial_lead_tags(source_platform) -> List[str]:
    """Initial tags for nurture alignment (e.g. checklist_download, checklist_nurture_v1)."""
    if source_platform == LeadSourcePlatform.COMPLIANCE_CHECKLIST:
        return ["checklist_download", "checklist_nurture_v1"]
    return []


def _lead_display_name(request: LeadCreateRequest) -> Optional[str]:
    """Derive name from first_name/last_name, full_name, or name."""
    if request.name and str(request.name).strip():
        return request.name.strip()
    if request.full_name and str(request.full_name).strip():
        return request.full_name.strip()
    parts = [request.first_name, request.last_name]
    if any(p and str(p).strip() for p in parts):
        return " ".join((p or "").strip() for p in parts).strip() or None
    return None


class LeadService:
    """Service for lead management operations."""
    
    @staticmethod
    async def create_lead(
        request: LeadCreateRequest,
        actor_id: Optional[str] = None,
        actor_type: str = "system",
        ip_address: Optional[str] = None,
        upsert_by_email: bool = False,
    ) -> Dict[str, Any]:
        """
        Create a new lead with deduplication check.
        If upsert_by_email=True and duplicate found by email, update existing lead (tags, last_activity_at, new fields) and return it.
        Otherwise returns existing lead as is_duplicate without updating.
        """
        db = database.get_db()
        now = datetime.now(timezone.utc).isoformat()
        display_name = _lead_display_name(request) or request.name

        # Check for duplicates before creating
        existing = await LeadService.find_duplicate(
            email=request.email,
            phone=request.phone,
            source_metadata=request.source_metadata,
        )

        if existing:
            if upsert_by_email and request.email:
                # Update existing: append tags, set last_activity_at, merge source_metadata and optional fields
                lead_id = existing["lead_id"]
                tags = list(set((existing.get("tags") or []) + _initial_lead_tags(request.source_platform)))
                if request.source_metadata:
                    sm = dict(existing.get("source_metadata") or {})
                    sm.update(request.source_metadata)
                    source_metadata = sm
                else:
                    source_metadata = existing.get("source_metadata") or {}
                update_set = {
                    "last_activity_at": now,
                    "updated_at": now,
                    "tags": tags,
                    "source_metadata": source_metadata,
                }
                if request.risk_score is not None:
                    update_set["risk_score"] = request.risk_score
                if request.risk_level is not None:
                    update_set["risk_level"] = request.risk_level
                if request.portfolio_size is not None:
                    update_set["portfolio_size"] = request.portfolio_size
                if request.primary_interest is not None:
                    update_set["primary_interest"] = request.primary_interest
                if request.secondary_interest is not None:
                    update_set["secondary_interest"] = request.secondary_interest
                if request.user_type is not None:
                    update_set["user_type"] = request.user_type
                if display_name and not existing.get("name"):
                    update_set["name"] = display_name
                if request.phone and not existing.get("phone"):
                    update_set["phone"] = request.phone
                if request.company_name and not existing.get("company_name"):
                    update_set["company_name"] = request.company_name
                if request.service_interest != LeadServiceInterest.UNKNOWN and existing.get("service_interest") == LeadServiceInterest.UNKNOWN.value:
                    update_set["service_interest"] = request.service_interest.value
                await db[LEADS_COLLECTION].update_one(
                    {"lead_id": lead_id},
                    {"$set": update_set},
                )
                updated_lead = await LeadService.get_lead(lead_id)
                if updated_lead:
                    try:
                        await LeadService.recalculate_and_persist_lead_score(lead_id, "upsert_by_email")
                        updated_lead = await LeadService.get_lead(lead_id)
                    except Exception as e:
                        logger.warning("Lead score recalc after upsert failed: %s", e)
                    await LeadService.log_audit(
                        event=LeadAuditEvent.LEAD_UPDATED,
                        lead_id=lead_id,
                        actor_id=actor_id,
                        actor_type=actor_type,
                        details={"source": "upsert_by_email", "source_platform": request.source_platform.value},
                        ip_address=ip_address,
                    )
                    return {**(updated_lead or existing), "is_duplicate": True, "original_lead_id": lead_id}
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

        # Determine follow-up sequence (nurture by type; checklist uses lead_nurture_service)
        if request.source_platform == LeadSourcePlatform.INTAKE_ABANDONED:
            followup_sequence = "abandoned_intake"
        elif request.service_interest == LeadServiceInterest.DOCUMENT_PACKS:
            followup_sequence = "document_pack"
        elif request.service_interest == LeadServiceInterest.AUTOMATION:
            followup_sequence = "automation"
        elif request.service_interest == LeadServiceInterest.MARKET_RESEARCH:
            followup_sequence = "market_research"
        elif request.service_interest == LeadServiceInterest.CVP or request.source_platform == LeadSourcePlatform.COMPLIANCE_RISK_CHECK:
            followup_sequence = "compliance"
        else:
            followup_sequence = "default"

        lead_doc = {
            "lead_id": lead_id,
            "source_platform": request.source_platform.value,
            "service_interest": request.service_interest.value,

            # Contact info
            "name": display_name,
            "first_name": getattr(request, "first_name", None),
            "last_name": getattr(request, "last_name", None),
            "full_name": getattr(request, "full_name", None),
            "email": request.email,
            "phone": request.phone,
            "company_name": request.company_name,

            # Qualification (unified lead engine)
            "user_type": getattr(request, "user_type", None),
            "portfolio_size": getattr(request, "portfolio_size", None),
            "primary_interest": getattr(request, "primary_interest", None),
            "secondary_interest": getattr(request, "secondary_interest", None),
            "risk_score": getattr(request, "risk_score", None),
            "risk_level": getattr(request, "risk_level", None),
            "intent_score": intent_score.value,
            "stage": LeadStage.NEW.value,
            "status": LeadStatus.ACTIVE.value,
            "lead_status": "new",

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

            # Checklist nurture (source_platform COMPLIANCE_CHECKLIST)
            "nurture_stage": 0,
            "last_nurture_sent_at": None,
            "tags": _initial_lead_tags(request.source_platform),

            # Assignment
            "assigned_to": None,
            "assigned_at": None,

            # Timestamps
            "created_at": now,
            "updated_at": now,
            "last_activity_at": now,
            "last_contacted_at": None,
            "converted_at": None,
            "conversion_source": None,
            "time_to_convert_seconds": None,

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
            "sla_hours": 24,
        }
        # lead_score set after recalc below
        lead_doc["lead_score"] = getattr(request, "lead_score", None)

        # Calculate next follow-up time if consent given
        if request.marketing_consent:
            lead_doc["next_followup_at"] = (
                datetime.now(timezone.utc) + timedelta(hours=1)
            ).isoformat()

        await db[LEADS_COLLECTION].insert_one(lead_doc)

        # Remove MongoDB _id for response
        lead_doc.pop("_id", None)

        # Recalculate lead_score, persist, log, and trigger hot lead alert if score >= 80
        try:
            await LeadService.recalculate_and_persist_lead_score(lead_id, "lead_created")
        except Exception as e:
            logger.warning("Lead score recalc after create failed: %s", e)
        lead_doc = (await LeadService.get_lead(lead_id)) or lead_doc

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

        # Hot lead alert (score >= 80) is sent from recalculate_and_persist_lead_score. Otherwise HIGH intent at create.
        if (lead_doc.get("lead_score") or 0) < HOT_LEAD_SCORE_THRESHOLD and intent_score == LeadIntentScore.HIGH:
            await LeadService.notify_high_intent_lead(lead_doc)
        try:
            from services.lead_automation_service import record_event, EVENT_LEAD_CREATED
            await record_event(
                lead_id=lead_id,
                event_type=EVENT_LEAD_CREATED,
                source="lead_service.create_lead",
                metadata={"source_platform": request.source_platform.value},
            )
        except Exception as e:
            logger.warning("Lead created event log failed: %s", e)

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
            high_intent_keywords = ["pricing", "price", "cost", "quote", "demo", "buy", "purchase", "sign up"]
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
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        last_activity_from: Optional[str] = None,
        last_activity_to: Optional[str] = None,
        lead_score_min: Optional[int] = None,
        lead_score_max: Optional[int] = None,
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
        if date_from or date_to:
            created_q = {}
            if date_from:
                created_q["$gte"] = date_from if isinstance(date_from, str) and "T" in date_from else f"{date_from}T00:00:00.000Z"
            if date_to:
                created_q["$lte"] = date_to if isinstance(date_to, str) and "T" in date_to else f"{date_to}T23:59:59.999Z"
            if created_q:
                filter_query["created_at"] = created_q
        if last_activity_from or last_activity_to:
            act_q = {}
            if last_activity_from:
                act_q["$gte"] = last_activity_from if isinstance(last_activity_from, str) and "T" in last_activity_from else f"{last_activity_from}T00:00:00.000Z"
            if last_activity_to:
                act_q["$lte"] = last_activity_to if isinstance(last_activity_to, str) and "T" in last_activity_to else f"{last_activity_to}T23:59:59.999Z"
            if act_q:
                filter_query["last_activity_at"] = act_q
        if lead_score_min is not None or lead_score_max is not None:
            score_q = {}
            if lead_score_min is not None:
                score_q["$gte"] = lead_score_min
            if lead_score_max is not None:
                score_q["$lte"] = lead_score_max
            if score_q:
                filter_query["lead_score"] = score_q

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
        update_data = {"updated_at": now, "last_activity_at": now}
        
        if request.name is not None:
            update_data["name"] = request.name
        if getattr(request, "first_name", None) is not None:
            update_data["first_name"] = request.first_name
        if getattr(request, "last_name", None) is not None:
            update_data["last_name"] = request.last_name
        if getattr(request, "full_name", None) is not None:
            update_data["full_name"] = request.full_name
        if request.email is not None:
            update_data["email"] = request.email.lower()
        if request.phone is not None:
            update_data["phone"] = request.phone
        if request.company_name is not None:
            update_data["company_name"] = request.company_name
        if getattr(request, "user_type", None) is not None:
            update_data["user_type"] = request.user_type
        if getattr(request, "portfolio_size", None) is not None:
            update_data["portfolio_size"] = request.portfolio_size
        if getattr(request, "primary_interest", None) is not None:
            update_data["primary_interest"] = request.primary_interest
        if getattr(request, "secondary_interest", None) is not None:
            update_data["secondary_interest"] = request.secondary_interest
        if getattr(request, "risk_score", None) is not None:
            update_data["risk_score"] = request.risk_score
        if getattr(request, "risk_level", None) is not None:
            update_data["risk_level"] = request.risk_level
        if request.service_interest is not None:
            update_data["service_interest"] = request.service_interest.value
        if request.message_summary is not None:
            update_data["message_summary"] = request.message_summary
        if request.intent_score is not None:
            update_data["intent_score"] = request.intent_score.value
        if getattr(request, "lead_score", None) is not None:
            update_data["lead_score"] = request.lead_score
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

        # Recalc lead_score when scoring-relevant fields change
        scoring_keys = {"portfolio_size", "risk_level", "user_type", "service_interest", "intent_score", "followup_status", "marketing_consent"}
        if any(k in update_data for k in scoring_keys):
            try:
                await LeadService.recalculate_and_persist_lead_score(lead_id, "admin_update")
            except Exception as e:
                logger.warning("Lead score recalc after update failed: %s", e)
        
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
                    "last_activity_at": now,
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
        conversion_source: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Convert a lead to a client.
        Preserves lead record with link to client.
        """
        db = database.get_db()
        now = datetime.now(timezone.utc).isoformat()

        attribution: Dict[str, Any] = {}
        try:
            from services.lead_automation_service import apply_conversion_attribution

            attribution = await apply_conversion_attribution(
                lead_id=lead_id, client_id=client_id, converted_at_iso=now
            )
        except Exception:
            attribution = {}
        
        lead_before = await db[LEADS_COLLECTION].find_one({"lead_id": lead_id}, {"_id": 0, "created_at": 1, "source_platform": 1})
        time_to_convert_seconds = None
        try:
            created_raw = (lead_before or {}).get("created_at")
            if isinstance(created_raw, str):
                created_dt = datetime.fromisoformat(created_raw.replace("Z", "+00:00"))
                if created_dt.tzinfo is None:
                    created_dt = created_dt.replace(tzinfo=timezone.utc)
                time_to_convert_seconds = max(0, int((datetime.now(timezone.utc) - created_dt).total_seconds()))
        except Exception:
            time_to_convert_seconds = None
        resolved_conversion_source = (conversion_source or (lead_before or {}).get("source_platform") or "UNKNOWN")
        # Update lead
        await db[LEADS_COLLECTION].update_one(
            {"lead_id": lead_id},
            {
                "$set": {
                    "status": LeadStatus.CONVERTED.value,
                    "lead_status": "converted",
                    "stage": LeadStage.WON.value,
                    "client_id": client_id,
                    "converted_at": now,
                    "conversion_source": resolved_conversion_source,
                    "time_to_convert_seconds": time_to_convert_seconds,
                    "conversion_attribution": attribution or None,
                    "conversion_notes": conversion_notes,
                    "updated_at": now,
                    "followup_status": FollowUpStatus.STOPPED.value,
                }
            }
        )
        
        # Also update the client record with lead_id for attribution
        await db["clients"].update_one(
            {"client_id": client_id},
            {"$set": {"lead_id": lead_id, "lead_source": True, "conversion_source": resolved_conversion_source, "lead_converted_at": now, "lead_conversion_attribution": attribution or None}}
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
                "conversion_source": resolved_conversion_source,
                "time_to_convert_seconds": time_to_convert_seconds,
                "conversion_attribution": attribution or None,
            },
        )
        try:
            from services.lead_automation_service import record_event, EVENT_LEAD_CONVERTED
            await record_event(
                lead_id=lead_id,
                event_type=EVENT_LEAD_CONVERTED,
                source="lead_service.convert_lead",
                metadata={"client_id": client_id, "conversion_source": resolved_conversion_source},
                source_ref=client_id,
            )
        except Exception as e:
            logger.warning("Lead converted event log failed: %s", e)
        
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
                    "lead_status": "lost",
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
    async def recalculate_and_persist_lead_score(lead_id: str, reason: str) -> Optional[Dict[str, Any]]:
        """
        Recalculate lead_score from current lead document, persist to DB, log LEAD_SCORE_UPDATED,
        optionally advance stage (never overwrite WON/CONVERTED), and trigger hot lead alert if score >= 80.
        Returns updated lead or None if lead not found.
        """
        db = database.get_db()
        lead = await LeadService.get_lead(lead_id)
        if not lead:
            return None
        previous_score = lead.get("lead_score")
        recalc = await recalc_lead_score(lead)
        new_score = recalc["lead_score"]
        suggested_stage = recalc.get("suggested_stage")
        now = datetime.now(timezone.utc).isoformat()
        update_set = {"lead_score": new_score, "updated_at": now}
        if suggested_stage and should_update_stage(lead, suggested_stage):
            update_set["stage"] = suggested_stage
        await db[LEADS_COLLECTION].update_one(
            {"lead_id": lead_id},
            {"$set": update_set},
        )
        await LeadService.log_audit(
            event=LeadAuditEvent.LEAD_SCORE_UPDATED,
            lead_id=lead_id,
            actor_id="system",
            actor_type="automation",
            details={
                "previous_score": previous_score,
                "new_score": new_score,
                "reason": reason,
            },
        )
        if new_score >= HOT_LEAD_SCORE_THRESHOLD:
            updated_lead = await LeadService.get_lead(lead_id)
            if updated_lead:
                await LeadService.notify_hot_lead_alert(updated_lead)
        return await LeadService.get_lead(lead_id)

    @staticmethod
    async def notify_hot_lead_alert(lead: Dict[str, Any]):
        """
        Send internal admin alert when lead_score >= 80 (hot lead).
        Includes lead name, email, lead type, portfolio size, risk level, lead score, CRM link.
        Idempotent per lead per day.
        """
        import os
        ADMIN_NOTIFICATION_EMAILS = os.environ.get("ADMIN_NOTIFICATION_EMAILS", "admin@pleerity.com").split(",")
        from utils.app_urls import get_app_base_url

        _base = get_app_base_url(for_email_links=True).rstrip("/")
        ADMIN_DASHBOARD_URL = os.environ.get("ADMIN_DASHBOARD_URL", f"{_base}/admin/leads")
        try:
            from services.notification_orchestrator import notification_orchestrator
            lead_id = lead.get("lead_id")
            name = lead.get("name") or "Unknown"
            email = lead.get("email") or "No email"
            lead_type = (lead.get("service_interest") or "UNKNOWN").replace("_", " ")
            portfolio_size = lead.get("portfolio_size")
            portfolio_str = str(portfolio_size) if portfolio_size is not None else "—"
            risk_level = lead.get("risk_level") or "—"
            score = lead.get("lead_score", 0)
            subject = f"🔥 Hot Lead (score {score}): {name}"
            message = (
                f"<p><strong>Lead ID:</strong> {lead_id}<br><strong>Name:</strong> {name}<br>"
                f"<strong>Email:</strong> {email}<br><strong>Lead type:</strong> {lead_type}<br>"
                f"<strong>Portfolio size:</strong> {portfolio_str}<br><strong>Risk level:</strong> {risk_level}<br>"
                f"<strong>Lead score:</strong> {score}</p>"
                f"<p><a href=\"{ADMIN_DASHBOARD_URL}\">View in CRM →</a></p>"
            )
            date_key = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            for admin_email in ADMIN_NOTIFICATION_EMAILS:
                admin_email = admin_email.strip()
                if admin_email:
                    try:
                        idempotency_key = f"{lead_id}_LEAD_HOT_ALERT_{date_key}_{admin_email}"
                        result = await notification_orchestrator.send(
                            template_key="LEAD_HIGH_INTENT_ADMIN",
                            client_id=None,
                            context={"recipient": admin_email, "subject": subject, "message": message},
                            idempotency_key=idempotency_key,
                            event_type="lead_hot_alert",
                        )
                        if result.outcome in ("sent", "duplicate_ignored"):
                            logger.info(f"Hot lead alert sent to {admin_email} for lead {lead_id}")
                    except Exception as e:
                        logger.error(f"Failed to send hot lead alert to {admin_email}: {e}")
        except Exception as e:
            logger.error(f"Failed to send hot lead alert: {e}")

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
        from utils.app_urls import get_app_base_url

        _base = get_app_base_url(for_email_links=True).rstrip("/")
        ADMIN_DASHBOARD_URL = os.environ.get("ADMIN_DASHBOARD_URL", f"{_base}/admin/leads")
        
        try:
            from services.notification_orchestrator import notification_orchestrator
            from datetime import datetime, timezone
            lead_id = lead.get("lead_id")
            name = lead.get("name") or "Unknown"
            email = lead.get("email") or "No email"
            phone = lead.get("phone") or "No phone"
            service = lead.get("service_interest", "UNKNOWN").replace("_", " ")
            source = lead.get("source_platform", "UNKNOWN").replace("_", " ")
            msg = lead.get("message_summary") or "No message"
            subject = f"🔥 HIGH Intent Lead: {name} interested in {service}"
            message = (
                f"<p><strong>Lead ID:</strong> {lead_id}<br><strong>Name:</strong> {name}<br>"
                f"<strong>Email:</strong> {email}<br><strong>Phone:</strong> {phone}<br>"
                f"<strong>Service Interest:</strong> {service}<br><strong>Source:</strong> {source}</p>"
                f"<p><strong>Message:</strong> {msg}</p>"
                f"<p><a href=\"{ADMIN_DASHBOARD_URL}\">View Lead in Dashboard →</a></p>"
            )
            date_key = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            for admin_email in ADMIN_NOTIFICATION_EMAILS:
                admin_email = admin_email.strip()
                if admin_email:
                    try:
                        idempotency_key = f"{lead_id}_LEAD_HIGH_INTENT_ADMIN_{date_key}_{admin_email}"
                        result = await notification_orchestrator.send(
                            template_key="LEAD_HIGH_INTENT_ADMIN",
                            client_id=None,
                            context={"recipient": admin_email, "subject": subject, "message": message},
                            idempotency_key=idempotency_key,
                            event_type="lead_high_intent",
                        )
                        if result.outcome in ("sent", "duplicate_ignored"):
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
                try:
                    from services.lead_automation_service import record_event, EVENT_CHECKOUT_ABANDONED
                    await record_event(
                        lead_id=lead["lead_id"],
                        event_type=EVENT_CHECKOUT_ABANDONED,
                        source="abandoned_intake_detection",
                        metadata={"draft_id": draft.get("draft_id"), "service_code": service_code},
                        source_ref=draft.get("draft_id"),
                    )
                except Exception:
                    pass
                
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
