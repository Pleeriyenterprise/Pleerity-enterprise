"""
Cookie Consent Service

Server-authoritative consent management with:
- Event stream (append-only)
- Materialized state
- Integration with lead/automation systems
"""
import hashlib
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List, Tuple
import database
from models.consent import (
    ConsentEventType,
    ConsentActionTaken,
    ConsentPreferences,
    ConsentCaptureRequest,
    ConsentEvent,
    ConsentState,
    ConsentStatsResponse,
    ConsentLogItem,
    ConsentLogDetailResponse,
    UTMData,
)

logger = logging.getLogger(__name__)

# Collection names
CONSENT_EVENTS_COLLECTION = "consent_events"
CONSENT_STATE_COLLECTION = "consent_state"

# Retention configuration (months)
CONSENT_RETENTION_MONTHS = int(__import__('os').environ.get('CONSENT_RETENTION_MONTHS', '24'))


def mask_email(email: str) -> str:
    """Mask email for privacy: jo***@domain.com"""
    if not email or '@' not in email:
        return "***@***.***"
    local, domain = email.rsplit('@', 1)
    if len(local) <= 2:
        masked_local = local[0] + "***"
    else:
        masked_local = local[:2] + "***"
    return f"{masked_local}@{domain}"


def hash_ip(ip: str) -> str:
    """Hash IP address for privacy - never store raw IP."""
    if not ip:
        return None
    return hashlib.sha256(ip.encode()).hexdigest()[:16]


def generate_banner_text_hash(version: str) -> str:
    """Generate hash for banner text version."""
    # In production, this would hash the actual banner content
    return hashlib.sha256(f"banner-{version}".encode()).hexdigest()[:12]


class ConsentService:
    """Service for managing cookie consent."""
    
    @staticmethod
    async def capture_consent(
        request: ConsentCaptureRequest,
        ip_address: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Capture consent from frontend.
        - Creates append-only event
        - Upserts materialized state
        """
        db = database.get_db()
        now = datetime.now(timezone.utc)
        
        # Force necessary=True
        request.preferences.necessary = True
        
        # Generate event ID
        event_id = f"CE-{now.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8].upper()}"
        
        # Determine action taken
        if request.event_type == ConsentEventType.ACCEPT_ALL:
            action_taken = ConsentActionTaken.ACCEPT_ALL
        elif request.event_type == ConsentEventType.REJECT_NON_ESSENTIAL:
            action_taken = ConsentActionTaken.REJECT_NON_ESSENTIAL
        elif request.event_type == ConsentEventType.CUSTOM:
            action_taken = ConsentActionTaken.CUSTOM
        else:
            action_taken = ConsentActionTaken.UNKNOWN
        
        # Build event document
        event_doc = {
            "event_id": event_id,
            "created_at": now.isoformat(),
            "event_type": request.event_type.value,
            "consent_version": request.consent_version,
            "banner_text_hash": request.banner_text_hash or generate_banner_text_hash(request.consent_version),
            "session_id": request.session_id,
            "user_id": None,
            "portal_user_id": None,
            "client_id": None,
            "crn": None,
            "email_masked": None,
            "country": request.country,
            "ip_hash": hash_ip(ip_address) if ip_address else None,
            "user_agent": request.user_agent,
            "page_path": request.page_path,
            "referrer": request.referrer,
            "utm": request.utm.dict() if request.utm else None,
            "preferences": request.preferences.dict(),
        }
        
        # Insert event (append-only)
        await db[CONSENT_EVENTS_COLLECTION].insert_one(event_doc)
        
        # Upsert state
        state_doc = {
            "updated_at": now.isoformat(),
            "session_id": request.session_id,
            "user_id": None,
            "portal_user_id": None,
            "client_id": None,
            "crn": None,
            "email_masked": None,
            "action_taken": action_taken.value,
            "consent_version": request.consent_version,
            "banner_text_hash": event_doc["banner_text_hash"],
            "preferences": request.preferences.dict(),
            "page_path": request.page_path,
            "country": request.country,
            "is_logged_in": False,
            "outreach_eligible": request.preferences.marketing,
        }
        
        await db[CONSENT_STATE_COLLECTION].update_one(
            {"session_id": request.session_id},
            {"$set": state_doc, "$setOnInsert": {"state_id": f"CS-{uuid.uuid4().hex[:12].upper()}"}},
            upsert=True,
        )
        
        logger.info(f"Consent captured: {event_id} - {request.event_type.value}")
        
        return {
            "success": True,
            "event_id": event_id,
            "preferences": request.preferences.dict(),
        }
    
    @staticmethod
    async def link_consent_to_user(
        session_id: str,
        user_id: Optional[str] = None,
        portal_user_id: Optional[str] = None,
        client_id: Optional[str] = None,
        crn: Optional[str] = None,
        email: Optional[str] = None,
    ) -> bool:
        """
        Link consent state to authenticated user.
        Creates UPDATE event to preserve history.
        """
        db = database.get_db()
        now = datetime.now(timezone.utc)
        
        # Find existing state
        state = await db[CONSENT_STATE_COLLECTION].find_one(
            {"session_id": session_id},
            {"_id": 0}
        )
        
        if not state:
            logger.warning(f"No consent state found for session {session_id}")
            return False
        
        # Create UPDATE event
        event_id = f"CE-{now.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8].upper()}"
        
        event_doc = {
            "event_id": event_id,
            "created_at": now.isoformat(),
            "event_type": ConsentEventType.UPDATE.value,
            "consent_version": state.get("consent_version", "v1"),
            "banner_text_hash": state.get("banner_text_hash"),
            "session_id": session_id,
            "user_id": user_id,
            "portal_user_id": portal_user_id,
            "client_id": client_id,
            "crn": crn,
            "email_masked": mask_email(email) if email else None,
            "country": state.get("country"),
            "ip_hash": None,
            "user_agent": None,
            "page_path": state.get("page_path"),
            "referrer": None,
            "utm": None,
            "preferences": state.get("preferences", {"necessary": True, "analytics": False, "marketing": False, "functional": False}),
            "linkage_note": "User authenticated - consent linked to account",
        }
        
        await db[CONSENT_EVENTS_COLLECTION].insert_one(event_doc)
        
        # Update state
        await db[CONSENT_STATE_COLLECTION].update_one(
            {"session_id": session_id},
            {"$set": {
                "updated_at": now.isoformat(),
                "user_id": user_id,
                "portal_user_id": portal_user_id,
                "client_id": client_id,
                "crn": crn,
                "email_masked": mask_email(email) if email else None,
                "is_logged_in": True,
            }}
        )
        
        logger.info(f"Consent linked: session={session_id}, crn={crn}")
        return True
    
    @staticmethod
    async def get_consent_state(session_id: str) -> Optional[Dict[str, Any]]:
        """Get current consent state for a session."""
        db = database.get_db()
        state = await db[CONSENT_STATE_COLLECTION].find_one(
            {"session_id": session_id},
            {"_id": 0}
        )
        return state
    
    @staticmethod
    async def check_marketing_consent(session_id: str) -> bool:
        """Check if marketing consent is granted for a session."""
        state = await ConsentService.get_consent_state(session_id)
        if not state:
            return False
        prefs = state.get("preferences", {})
        return prefs.get("marketing", False)
    
    @staticmethod
    async def check_analytics_consent(session_id: str) -> bool:
        """Check if analytics consent is granted for a session."""
        state = await ConsentService.get_consent_state(session_id)
        if not state:
            return False
        prefs = state.get("preferences", {})
        return prefs.get("analytics", False)
    
    @staticmethod
    async def check_functional_consent(session_id: str) -> bool:
        """Check if functional consent is granted for a session."""
        state = await ConsentService.get_consent_state(session_id)
        if not state:
            return False
        prefs = state.get("preferences", {})
        return prefs.get("functional", False)
    
    @staticmethod
    async def is_outreach_eligible(session_id: str = None, crn: str = None, client_id: str = None) -> bool:
        """
        Check if a user is eligible for marketing outreach.
        Can check by session_id, crn, or client_id.
        """
        db = database.get_db()
        
        query = {}
        if session_id:
            query["session_id"] = session_id
        elif crn:
            query["crn"] = crn
        elif client_id:
            query["client_id"] = client_id
        else:
            return False
        
        state = await db[CONSENT_STATE_COLLECTION].find_one(query, {"_id": 0})
        
        if not state:
            return False
        
        return state.get("outreach_eligible", False)
    
    @staticmethod
    async def withdraw_consent(
        session_id: str,
        categories: List[str] = None,  # If None, withdraw all non-essential
    ) -> Dict[str, Any]:
        """
        Withdraw consent for specified categories.
        Creates WITHDRAW event.
        """
        db = database.get_db()
        now = datetime.now(timezone.utc)
        
        state = await db[CONSENT_STATE_COLLECTION].find_one(
            {"session_id": session_id},
            {"_id": 0}
        )
        
        if not state:
            return {"success": False, "error": "No consent state found"}
        
        old_prefs = state.get("preferences", {})
        new_prefs = {
            "necessary": True,
            "analytics": old_prefs.get("analytics", False),
            "marketing": old_prefs.get("marketing", False),
            "functional": old_prefs.get("functional", False),
        }
        
        # Withdraw specified categories or all non-essential
        if categories:
            for cat in categories:
                if cat in new_prefs and cat != "necessary":
                    new_prefs[cat] = False
        else:
            new_prefs["analytics"] = False
            new_prefs["marketing"] = False
            new_prefs["functional"] = False
        
        # Create WITHDRAW event
        event_id = f"CE-{now.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8].upper()}"
        
        event_doc = {
            "event_id": event_id,
            "created_at": now.isoformat(),
            "event_type": ConsentEventType.WITHDRAW.value,
            "consent_version": state.get("consent_version", "v1"),
            "banner_text_hash": state.get("banner_text_hash"),
            "session_id": session_id,
            "user_id": state.get("user_id"),
            "portal_user_id": state.get("portal_user_id"),
            "client_id": state.get("client_id"),
            "crn": state.get("crn"),
            "email_masked": state.get("email_masked"),
            "country": state.get("country"),
            "ip_hash": None,
            "user_agent": None,
            "page_path": None,
            "referrer": None,
            "utm": None,
            "preferences": new_prefs,
            "withdrawn_categories": categories or ["analytics", "marketing", "functional"],
            "previous_preferences": old_prefs,
        }
        
        await db[CONSENT_EVENTS_COLLECTION].insert_one(event_doc)
        
        # Update state
        await db[CONSENT_STATE_COLLECTION].update_one(
            {"session_id": session_id},
            {"$set": {
                "updated_at": now.isoformat(),
                "preferences": new_prefs,
                "outreach_eligible": new_prefs.get("marketing", False),
                "action_taken": ConsentActionTaken.REJECT_NON_ESSENTIAL.value if not any([new_prefs["analytics"], new_prefs["marketing"], new_prefs["functional"]]) else ConsentActionTaken.CUSTOM.value,
            }}
        )
        
        logger.info(f"Consent withdrawn: session={session_id}, categories={categories}")
        
        return {
            "success": True,
            "event_id": event_id,
            "preferences": new_prefs,
        }


class ConsentAdminService:
    """Admin service for consent dashboard."""
    
    @staticmethod
    async def get_stats(
        from_date: datetime,
        to_date: datetime,
    ) -> Dict[str, Any]:
        """Get consent statistics for admin dashboard."""
        db = database.get_db()
        
        from_iso = from_date.isoformat()
        to_iso = to_date.isoformat()
        
        pipeline = [
            {
                "$match": {
                    "created_at": {"$gte": from_iso, "$lte": to_iso},
                    "event_type": {"$ne": ConsentEventType.UPDATE.value},  # Exclude linkage updates
                }
            },
            {
                "$group": {
                    "_id": None,
                    "total_sessions": {"$addToSet": "$session_id"},
                    "banner_shown": {
                        "$sum": {"$cond": [{"$eq": ["$event_type", ConsentEventType.BANNER_SHOWN.value]}, 1, 0]}
                    },
                    "accept_all": {
                        "$sum": {"$cond": [{"$eq": ["$event_type", ConsentEventType.ACCEPT_ALL.value]}, 1, 0]}
                    },
                    "reject": {
                        "$sum": {"$cond": [{"$eq": ["$event_type", ConsentEventType.REJECT_NON_ESSENTIAL.value]}, 1, 0]}
                    },
                    "custom": {
                        "$sum": {"$cond": [{"$eq": ["$event_type", ConsentEventType.CUSTOM.value]}, 1, 0]}
                    },
                    "analytics_allowed": {
                        "$sum": {"$cond": [{"$eq": ["$preferences.analytics", True]}, 1, 0]}
                    },
                    "marketing_allowed": {
                        "$sum": {"$cond": [{"$eq": ["$preferences.marketing", True]}, 1, 0]}
                    },
                    "functional_allowed": {
                        "$sum": {"$cond": [{"$eq": ["$preferences.functional", True]}, 1, 0]}
                    },
                }
            }
        ]
        
        result = await db[CONSENT_EVENTS_COLLECTION].aggregate(pipeline).to_list(1)
        
        if result:
            stats = result[0]
            total_sessions = len(stats.get("total_sessions", []))
        else:
            stats = {}
            total_sessions = 0
        
        # Get trend data (daily buckets)
        trend_pipeline = [
            {
                "$match": {
                    "created_at": {"$gte": from_iso, "$lte": to_iso},
                    "event_type": {"$in": [
                        ConsentEventType.ACCEPT_ALL.value,
                        ConsentEventType.REJECT_NON_ESSENTIAL.value,
                        ConsentEventType.CUSTOM.value,
                    ]},
                }
            },
            {
                "$addFields": {
                    "date": {"$substr": ["$created_at", 0, 10]}
                }
            },
            {
                "$group": {
                    "_id": "$date",
                    "sessions": {"$addToSet": "$session_id"},
                    "marketing_allowed": {
                        "$sum": {"$cond": [{"$eq": ["$preferences.marketing", True]}, 1, 0]}
                    },
                    "analytics_allowed": {
                        "$sum": {"$cond": [{"$eq": ["$preferences.analytics", True]}, 1, 0]}
                    },
                }
            },
            {"$sort": {"_id": 1}},
        ]
        
        trend_result = await db[CONSENT_EVENTS_COLLECTION].aggregate(trend_pipeline).to_list(100)
        trend = [
            {
                "date": r["_id"],
                "sessions": len(r["sessions"]),
                "marketing_allowed": r["marketing_allowed"],
                "analytics_allowed": r["analytics_allowed"],
            }
            for r in trend_result
        ]
        
        return {
            "kpis": {
                "total_sessions_shown": total_sessions,
                "accept_all_count": stats.get("accept_all", 0),
                "reject_count": stats.get("reject", 0),
                "custom_count": stats.get("custom", 0),
            },
            "categories": {
                "analytics_allowed_count": stats.get("analytics_allowed", 0),
                "marketing_allowed_count": stats.get("marketing_allowed", 0),
                "functional_allowed_count": stats.get("functional_allowed", 0),
            },
            "trend": trend,
        }
    
    @staticmethod
    async def get_logs(
        from_date: datetime,
        to_date: datetime,
        page: int = 1,
        page_size: int = 25,
        filters: Dict[str, Any] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Get paginated consent logs for admin dashboard."""
        db = database.get_db()
        
        from_iso = from_date.isoformat()
        to_iso = to_date.isoformat()
        
        query = {
            "created_at": {"$gte": from_iso, "$lte": to_iso},
            "event_type": {"$in": [
                ConsentEventType.ACCEPT_ALL.value,
                ConsentEventType.REJECT_NON_ESSENTIAL.value,
                ConsentEventType.CUSTOM.value,
                ConsentEventType.WITHDRAW.value,
            ]},
        }
        
        if filters:
            if filters.get("action_taken") and filters["action_taken"] != "all":
                action_map = {
                    "ACCEPT_ALL": ConsentEventType.ACCEPT_ALL.value,
                    "REJECT_NON_ESSENTIAL": ConsentEventType.REJECT_NON_ESSENTIAL.value,
                    "CUSTOM": ConsentEventType.CUSTOM.value,
                }
                query["event_type"] = action_map.get(filters["action_taken"], filters["action_taken"])
            
            if filters.get("marketing") == "allowed":
                query["preferences.marketing"] = True
            elif filters.get("marketing") == "not_allowed":
                query["preferences.marketing"] = False
            
            if filters.get("analytics") == "allowed":
                query["preferences.analytics"] = True
            elif filters.get("analytics") == "not_allowed":
                query["preferences.analytics"] = False
            
            if filters.get("user_type") == "anonymous":
                query["crn"] = None
            elif filters.get("user_type") == "logged_in":
                query["crn"] = {"$ne": None}
            
            if filters.get("crn"):
                query["crn"] = filters["crn"]
            
            if filters.get("email"):
                query["email_masked"] = {"$regex": filters["email"], "$options": "i"}
            
            if filters.get("session_id"):
                query["session_id"] = filters["session_id"]
            
            if filters.get("country"):
                query["country"] = filters["country"]
            
            if filters.get("consent_version"):
                query["consent_version"] = filters["consent_version"]
        
        # Get total count
        total = await db[CONSENT_EVENTS_COLLECTION].count_documents(query)
        
        # Get paginated results
        skip = (page - 1) * page_size
        cursor = db[CONSENT_EVENTS_COLLECTION].find(
            query,
            {"_id": 0}
        ).sort("created_at", -1).skip(skip).limit(page_size)
        
        logs = await cursor.to_list(length=page_size)
        
        # Transform for frontend
        items = []
        for log in logs:
            event_type = log.get("event_type")
            if event_type == ConsentEventType.ACCEPT_ALL.value:
                action = ConsentActionTaken.ACCEPT_ALL.value
            elif event_type == ConsentEventType.REJECT_NON_ESSENTIAL.value:
                action = ConsentActionTaken.REJECT_NON_ESSENTIAL.value
            elif event_type in [ConsentEventType.CUSTOM.value, ConsentEventType.WITHDRAW.value]:
                action = ConsentActionTaken.CUSTOM.value
            else:
                action = ConsentActionTaken.UNKNOWN.value
            
            crn = log.get("crn")
            email = log.get("email_masked")
            user_display = "Anonymous"
            if crn:
                user_display = f"{crn}"
                if email:
                    user_display += f" ({email})"
            
            items.append({
                "event_id": log.get("event_id"),
                "created_at": log.get("created_at"),
                "event_type": event_type,
                "action_taken": action,
                "preferences": log.get("preferences", {}),
                "session_id": log.get("session_id"),
                "user_display": user_display,
                "crn": crn,
                "country": log.get("country"),
                "page_path": log.get("page_path"),
                "consent_version": log.get("consent_version"),
                "is_logged_in": crn is not None,
            })
        
        return items, total
    
    @staticmethod
    async def get_log_detail(event_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed consent record for admin drawer."""
        db = database.get_db()
        
        event = await db[CONSENT_EVENTS_COLLECTION].find_one(
            {"event_id": event_id},
            {"_id": 0}
        )
        
        if not event:
            return None
        
        # Get timeline (all events for this session)
        timeline_cursor = db[CONSENT_EVENTS_COLLECTION].find(
            {"session_id": event.get("session_id")},
            {"_id": 0, "event_id": 1, "event_type": 1, "created_at": 1, "preferences": 1}
        ).sort("created_at", 1)
        
        timeline = await timeline_cursor.to_list(length=50)
        
        # Get current state
        state = await db[CONSENT_STATE_COLLECTION].find_one(
            {"session_id": event.get("session_id")},
            {"_id": 0}
        )
        
        prefs = event.get("preferences", {})
        
        return {
            "event_id": event.get("event_id"),
            "session_id": event.get("session_id"),
            "crn": event.get("crn"),
            "user_id": event.get("user_id"),
            "portal_user_id": event.get("portal_user_id"),
            "client_id": event.get("client_id"),
            "action_taken": event.get("event_type"),
            "preferences": prefs,
            "created_at": event.get("created_at"),
            "updated_at": state.get("updated_at") if state else None,
            "consent_version": event.get("consent_version"),
            "banner_text_hash": event.get("banner_text_hash"),
            "page_path": event.get("page_path"),
            "referrer": event.get("referrer"),
            "utm": event.get("utm"),
            "country": event.get("country"),
            "user_agent": event.get("user_agent"),
            "is_logged_in": event.get("crn") is not None,
            "outreach_eligible": prefs.get("marketing", False),
            "timeline": timeline,
        }


async def ensure_consent_indexes():
    """Create indexes for consent collections."""
    db = database.get_db()
    
    # consent_events indexes
    await db[CONSENT_EVENTS_COLLECTION].create_index("created_at")
    await db[CONSENT_EVENTS_COLLECTION].create_index("session_id")
    await db[CONSENT_EVENTS_COLLECTION].create_index("client_id")
    await db[CONSENT_EVENTS_COLLECTION].create_index("crn")
    await db[CONSENT_EVENTS_COLLECTION].create_index("event_type")
    await db[CONSENT_EVENTS_COLLECTION].create_index("preferences.marketing")
    await db[CONSENT_EVENTS_COLLECTION].create_index("preferences.analytics")
    
    # consent_state indexes
    await db[CONSENT_STATE_COLLECTION].create_index("session_id", unique=True)
    await db[CONSENT_STATE_COLLECTION].create_index("updated_at")
    await db[CONSENT_STATE_COLLECTION].create_index("client_id")
    await db[CONSENT_STATE_COLLECTION].create_index("crn")
    await db[CONSENT_STATE_COLLECTION].create_index("action_taken")
    await db[CONSENT_STATE_COLLECTION].create_index("preferences.marketing")
    await db[CONSENT_STATE_COLLECTION].create_index("preferences.analytics")
    
    logger.info("Consent indexes created")
