"""
Contractor service: CRUD for contractors (Ops & Compliance / Contractor Network).
Contractors can be system-wide (client_id None) or client-preferred (client_id set).
"""
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
from database import database
import logging

logger = logging.getLogger(__name__)

try:
    from bson import ObjectId
except ImportError:
    ObjectId = None  # type: ignore[misc, assignment]

# Entry path / visibility (task: three models)
SOURCE_LANDLORD_ADDED = "landlord_added"
SOURCE_PLATFORM_NETWORK = "platform_network"
SOURCE_SELF_REGISTERED = "self_registered"
STATUS_ACTIVE = "active"
STATUS_PENDING_REVIEW = "pending_review"
STATUS_SUSPENDED = "suspended"

# Rework: follow-up work order at same property within this many days of a prior completion counts as rework.
REWORK_DAYS = 30


def _make_json_safe(obj: Any) -> Any:
    """Convert MongoDB ObjectId and other non-JSON types so FastAPI can serialize responses."""
    if ObjectId is not None and isinstance(obj, ObjectId):
        return str(obj)
    if isinstance(obj, dict):
        return {k: _make_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_make_json_safe(x) for x in obj]
    return obj


def _sanitize_doc(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Return a JSON-safe copy of a contractor document (no raw ObjectId)."""
    out = dict(doc)
    out.pop("_id", None)
    return _make_json_safe(out)


async def list_contractors(
    client_id: Optional[str] = None,
    vetted_only: bool = False,
    source_type: Optional[str] = None,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
) -> Dict[str, Any]:
    """List contractors, optionally filtered by client_id, vetted, source_type, status."""
    db = database.get_db()
    q = {}
    if client_id is not None:
        q["client_id"] = client_id
    if vetted_only:
        q["vetted"] = True
    if source_type is not None:
        q["source_type"] = source_type
    if status is not None:
        q["status"] = status
    cursor = db.contractors.find(q).sort("name", 1).skip(skip).limit(limit)
    items = await cursor.to_list(limit)
    total = await db.contractors.count_documents(q)
    return {
        "contractors": [_sanitize_doc(d) for d in items],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


def _visibility_query(client_id: str) -> Dict[str, Any]:
    """Contractors visible to a client: org match, platform network, or approved self-registered. Only active (or legacy no status)."""
    return {
        "$or": [
            {"status": STATUS_ACTIVE, "client_id": client_id},
            {"status": STATUS_ACTIVE, "client_id": None, "source_type": SOURCE_PLATFORM_NETWORK},
            {"status": STATUS_ACTIVE, "client_id": None, "source_type": SOURCE_SELF_REGISTERED, "vetted": True},
            {"status": {"$exists": False}, "client_id": client_id},
            {"status": {"$exists": False}, "client_id": None},
        ],
    }


async def contractor_visible_to_client(contractor_id: str, client_id: str) -> bool:
    """Return True if the contractor is visible to the client (own private, network, or approved marketplace). Used to enforce assignment rules."""
    if not contractor_id or not client_id:
        return False
    db = database.get_db()
    q = {"contractor_id": contractor_id}
    q.update(_visibility_query(client_id))
    doc = await db.contractors.find_one(q, {"_id": 1})
    return doc is not None


async def list_contractors_for_client(
    client_id: str,
    vetted_only: bool = False,
    skip: int = 0,
    limit: int = 100,
    source_type: Optional[str] = None,
) -> Dict[str, Any]:
    """List contractors visible to a client: org-assigned, platform network, or approved marketplace. Only status=active."""
    db = database.get_db()
    q = _visibility_query(client_id)
    if vetted_only:
        q["vetted"] = True
    if source_type is not None:
        q["source_type"] = source_type
    cursor = db.contractors.find(q).sort("name", 1).skip(skip).limit(limit)
    items = await cursor.to_list(limit)
    total = await db.contractors.count_documents(q)
    return {
        "contractors": [_sanitize_doc(d) for d in items],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


async def get_contractor(contractor_id: str) -> Optional[Dict[str, Any]]:
    """Get a single contractor by id."""
    db = database.get_db()
    doc = await db.contractors.find_one({"contractor_id": contractor_id})
    if not doc:
        return None
    return _sanitize_doc(doc)


async def create_contractor(
    name: str,
    trade_types: Optional[List[str]] = None,
    vetted: bool = False,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    company_name: Optional[str] = None,
    client_id: Optional[str] = None,
    areas_served: Optional[List[str]] = None,
    notes: Optional[str] = None,
    source_type: Optional[str] = None,
    status: Optional[str] = None,
    credentials: Optional[List[str]] = None,
    insurance_details: Optional[str] = None,
    contact_name: Optional[str] = None,
    region: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a new contractor. Sets source_type/status when provided; defaults for backward compat."""
    from datetime import datetime, timezone
    import uuid

    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "contractor_id": str(uuid.uuid4()),
        "client_id": client_id,
        "name": name,
        "trade_types": trade_types or [],
        "vetted": vetted,
        "email": email,
        "phone": phone,
        "company_name": company_name,
        "areas_served": areas_served,
        "notes": notes,
        "created_at": now,
        "updated_at": now,
        "source_type": source_type or (SOURCE_LANDLORD_ADDED if client_id else SOURCE_PLATFORM_NETWORK),
        "status": status or STATUS_ACTIVE,
        "credentials": credentials or [],
        "insurance_details": insurance_details,
        "contact_name": contact_name,
        "region": region,
        "rating_average": None,
        "job_count": 0,
        "sla_compliance_rate": None,
        "rework_rate": None,
    }
    if client_id and (source_type or "").strip().lower() == SOURCE_LANDLORD_ADDED:
        doc["visibility_scope"] = "private"
    elif not client_id and (source_type or "").strip().lower() == SOURCE_PLATFORM_NETWORK:
        doc["visibility_scope"] = "network"
    elif not client_id and (source_type or "").strip().lower() == SOURCE_SELF_REGISTERED and vetted:
        doc["visibility_scope"] = "marketplace"
    db = database.get_db()
    await db.contractors.insert_one(doc)
    return _sanitize_doc(doc)


async def update_contractor(
    contractor_id: str,
    name: Optional[str] = None,
    trade_types: Optional[List[str]] = None,
    vetted: Optional[bool] = None,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    company_name: Optional[str] = None,
    client_id: Optional[str] = None,
    areas_served: Optional[List[str]] = None,
    notes: Optional[str] = None,
    status: Optional[str] = None,
    credentials: Optional[List[str]] = None,
    insurance_details: Optional[str] = None,
    contact_name: Optional[str] = None,
    region: Optional[str] = None,
    submitted_to_network_at: Optional[str] = None,
    approved_for_network_at: Optional[str] = None,
    approved_by_admin_id: Optional[str] = None,
    network_submission_rejection_reason: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Update a contractor. Only provided fields are updated."""
    from datetime import datetime, timezone

    db = database.get_db()
    update = {"updated_at": datetime.now(timezone.utc).isoformat()}
    if name is not None:
        update["name"] = name
    if trade_types is not None:
        update["trade_types"] = trade_types
    if vetted is not None:
        update["vetted"] = vetted
    if email is not None:
        update["email"] = email
    if phone is not None:
        update["phone"] = phone
    if company_name is not None:
        update["company_name"] = company_name
    if client_id is not None:
        update["client_id"] = client_id
    if areas_served is not None:
        update["areas_served"] = areas_served
    if notes is not None:
        update["notes"] = notes
    if status is not None:
        update["status"] = status
    if credentials is not None:
        update["credentials"] = credentials
    if insurance_details is not None:
        update["insurance_details"] = insurance_details
    if contact_name is not None:
        update["contact_name"] = contact_name
    if region is not None:
        update["region"] = region
    if submitted_to_network_at is not None:
        update["submitted_to_network_at"] = submitted_to_network_at
    if approved_for_network_at is not None:
        update["approved_for_network_at"] = approved_for_network_at
    if approved_by_admin_id is not None:
        update["approved_by_admin_id"] = approved_by_admin_id
    if network_submission_rejection_reason is not None:
        update["network_submission_rejection_reason"] = network_submission_rejection_reason

    result = await db.contractors.find_one_and_update(
        {"contractor_id": contractor_id},
        {"$set": update},
        return_document=True,
    )
    if not result:
        return None
    return _sanitize_doc(result)


async def delete_contractor(contractor_id: str) -> bool:
    """Delete a contractor. Returns True if deleted."""
    db = database.get_db()
    result = await db.contractors.delete_one({"contractor_id": contractor_id})
    return result.deleted_count > 0


async def create_contractor_landlord(
    client_id: str,
    company_name: str,
    trade_types: List[str],
    phone: Optional[str] = None,
    email: Optional[str] = None,
    contact_name: Optional[str] = None,
    region: Optional[str] = None,
    credentials: Optional[List[str]] = None,
    insurance_details: Optional[str] = None,
    areas_served: Optional[List[str]] = None,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """Landlord adds a contractor: source_type=landlord_added, vetted=False, status=active. Visible only to that org."""
    name = contact_name or company_name
    return await create_contractor(
        name=name,
        company_name=company_name,
        trade_types=trade_types,
        vetted=False,
        phone=phone,
        email=email,
        client_id=client_id,
        areas_served=areas_served,
        notes=notes,
        source_type=SOURCE_LANDLORD_ADDED,
        status=STATUS_ACTIVE,
        credentials=credentials,
        insurance_details=insurance_details,
        contact_name=contact_name,
        region=region,
    )


async def create_contractor_network(
    company_name: str,
    trade_types: List[str],
    phone: Optional[str] = None,
    email: Optional[str] = None,
    region: Optional[str] = None,
    credentials: Optional[List[str]] = None,
    insurance_details: Optional[str] = None,
    areas_served: Optional[List[str]] = None,
    contact_name: Optional[str] = None,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """Admin adds to platform network: client_id=null, vetted=True, status=active, source_type=platform_network."""
    name = contact_name or company_name
    return await create_contractor(
        name=name,
        company_name=company_name,
        trade_types=trade_types,
        vetted=True,
        phone=phone,
        email=email,
        client_id=None,
        areas_served=areas_served,
        notes=notes,
        source_type=SOURCE_PLATFORM_NETWORK,
        status=STATUS_ACTIVE,
        credentials=credentials,
        insurance_details=insurance_details,
        contact_name=contact_name,
        region=region,
    )


async def create_contractor_self_registered(
    company_name: str,
    contact_name: str,
    trade_types: List[str],
    phone: Optional[str] = None,
    email: Optional[str] = None,
    coverage_regions: Optional[List[str]] = None,
    credentials: Optional[List[str]] = None,
    insurance_details: Optional[str] = None,
) -> Dict[str, Any]:
    """Self-registration: client_id=null, vetted=False, status=pending_review, source_type=self_registered."""
    return await create_contractor(
        name=contact_name,
        company_name=company_name,
        trade_types=trade_types,
        vetted=False,
        phone=phone,
        email=email,
        client_id=None,
        areas_served=coverage_regions,
        notes=None,
        source_type=SOURCE_SELF_REGISTERED,
        status=STATUS_PENDING_REVIEW,
        credentials=credentials,
        insurance_details=insurance_details,
        contact_name=contact_name,
        region=coverage_regions[0] if coverage_regions else None,
    )


async def approve_contractor(contractor_id: str) -> Optional[Dict[str, Any]]:
    """Set contractor status=active and vetted=True (e.g. after admin review of self-registered)."""
    return await update_contractor(contractor_id, status=STATUS_ACTIVE, vetted=True)


async def submit_contractor_to_network(contractor_id: str, client_id: str) -> Optional[Dict[str, Any]]:
    """Landlord submits their private contractor for network review. Sets submitted_to_network_at. Contractor remains private until admin approves."""
    db = database.get_db()
    doc = await db.contractors.find_one({"contractor_id": contractor_id})
    if not doc:
        return None
    if doc.get("client_id") != client_id:
        return None
    if doc.get("source_type") != SOURCE_LANDLORD_ADDED:
        return None
    if doc.get("submitted_to_network_at"):
        return _sanitize_doc(doc)
    now = datetime.now(timezone.utc).isoformat()
    await db.contractors.update_one(
        {"contractor_id": contractor_id},
        {"$set": {"submitted_to_network_at": now, "updated_at": now}},
    )
    return await get_contractor(contractor_id)


async def approve_contractor_to_network(
    contractor_id: str,
    approved_by_admin_id: str,
) -> Optional[Dict[str, Any]]:
    """Admin approves a private contractor for the network. Creates a new platform_network contractor (copy) and marks the private record as approved. Private record is unchanged except approved_for_network_at and approved_by_admin_id."""
    db = database.get_db()
    private = await db.contractors.find_one({"contractor_id": contractor_id})
    if not private or private.get("source_type") != SOURCE_LANDLORD_ADDED or not private.get("submitted_to_network_at"):
        return None
    now = datetime.now(timezone.utc).isoformat()
    new_network = await create_contractor_network(
        company_name=private.get("company_name") or private.get("name") or "Contractor",
        trade_types=private.get("trade_types") or ["general"],
        phone=private.get("phone"),
        email=private.get("email"),
        region=private.get("region"),
        credentials=private.get("credentials"),
        insurance_details=private.get("insurance_details"),
        areas_served=private.get("areas_served"),
        contact_name=private.get("contact_name"),
        notes=private.get("notes"),
    )
    await db.contractors.update_one(
        {"contractor_id": contractor_id},
        {
            "$set": {
                "approved_for_network_at": now,
                "approved_by_admin_id": approved_by_admin_id,
                "updated_at": now,
                "promoted_to_network_contractor_id": new_network.get("contractor_id"),
            },
        },
    )
    return new_network


async def reject_contractor_network_submission(
    contractor_id: str,
    reason: Optional[str] = None,
    rejected_by_admin_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Admin rejects a network submission. Sets network_submission_rejection_reason; submitted_to_network_at is left for audit."""
    db = database.get_db()
    doc = await db.contractors.find_one({"contractor_id": contractor_id})
    if not doc or doc.get("source_type") != SOURCE_LANDLORD_ADDED:
        return None
    now = datetime.now(timezone.utc).isoformat()
    update = {"updated_at": now, "network_submission_rejection_reason": reason or ""}
    if rejected_by_admin_id is not None:
        update["network_submission_rejected_by_admin_id"] = rejected_by_admin_id
    await db.contractors.update_one(
        {"contractor_id": contractor_id},
        {"$set": update},
    )
    return await get_contractor(contractor_id)


RECOMMENDED_TYPE_TO_TRADES = {
    "gas_safe": ["heating", "gas", "gas_safe", "boiler"],
    "plumber": ["plumbing", "plumber"],
    "electrician": ["electrical", "electrician"],
    "damp_inspection": ["damp", "inspection", "damp_inspection"],
    "general": ["general", "handyman"],
}


async def load_price_books(client_id: Optional[str]) -> List[Dict[str, Any]]:
    """Load price_books for a client (client-specific + global). Returns list; empty if collection missing or no docs."""
    db = database.get_db()
    q = {"$or": [{"client_id": client_id}, {"client_id": None}]} if client_id else {"client_id": None}
    try:
        cursor = db.get_collection("price_books").find(q, {"_id": 0})
        return await cursor.to_list(100)
    except Exception:
        return []


async def recommend_contractors_for_work_order(
    work_order_id: str,
    client_id: Optional[str] = None,
    limit: int = 10,
) -> Dict[str, Any]:
    """Return suggested contractors for a work order: rule-based scoring (trade, region, credential, SLA, rating, rework). No auto-assign."""
    db = database.get_db()
    wo = await db.work_orders.find_one(
        {"work_order_id": work_order_id},
        {"_id": 0, "client_id": 1, "property_id": 1, "category": 1, "recommended_contractor_type": 1, "severity": 1, "work_order_id": 1},
    )
    if not wo:
        return {"contractors": [], "total": 0, "work_order_id": work_order_id, "no_strong_match": True}
    cid = client_id or wo.get("client_id")
    q = _visibility_query(cid) if cid else {"$or": [{"client_id": None}, {"status": {"$exists": False}}]}
    cursor = db.contractors.find(q)
    all_contractors = await cursor.to_list(500)
    property_doc = None
    if wo.get("property_id"):
        property_doc = await db.properties.find_one(
            {"property_id": wo["property_id"]},
            {"_id": 0, "postcode": 1, "region": 1},
        )
    perf_map: Dict[str, Tuple[int, int]] = {}
    if cid:
        perf_cursor = db.contractor_performance.find(
            {"client_id": cid},
            {"_id": 0, "contractor_id": 1, "jobs_completed": 1, "jobs_on_time": 1},
        )
        async for p in perf_cursor:
            j = p.get("jobs_completed") or 0
            o = p.get("jobs_on_time") or 0
            perf_map[p["contractor_id"]] = (j, o)
    price_books = await load_price_books(cid)
    from services.contractor_recommendation import recommend_contractors as rule_recommend
    result = rule_recommend(
        work_order=wo,
        property_doc=property_doc,
        contractors=all_contractors,
        performance_map=perf_map,
        price_books=price_books if price_books else None,
    )
    result["contractors"] = result["contractors"][:limit]
    result["total"] = len(result["contractors"])
    return result


async def create_contractor_rating(
    contractor_id: str,
    client_id: str,
    rating: int,
    work_order_id: Optional[str] = None,
    property_id: Optional[str] = None,
    completion_speed: Optional[int] = None,
    professionalism: Optional[int] = None,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """Record a rating for a contractor (e.g. after work order completion). Updates contractor.rating_average."""
    import uuid
    from datetime import datetime, timezone

    if not (1 <= rating <= 5):
        raise ValueError("rating must be between 1 and 5")
    db = database.get_db()
    contractor = await db.contractors.find_one({"contractor_id": contractor_id}, {"_id": 1})
    if not contractor:
        raise ValueError("Contractor not found")
    rating_id = f"rating_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "rating_id": rating_id,
        "contractor_id": contractor_id,
        "client_id": client_id,
        "rating": rating,
        "work_order_id": work_order_id,
        "property_id": property_id,
        "completion_speed": completion_speed,
        "professionalism": professionalism,
        "notes": (notes or "").strip()[:2000] or None,
        "created_at": now,
    }
    await db.contractor_ratings.insert_one(doc)
    await _update_contractor_rating_average(contractor_id)
    return _sanitize_doc(doc)


async def _update_contractor_rating_average(contractor_id: str) -> None:
    """Recompute contractor.rating_average from contractor_ratings and update the contractor doc."""
    db = database.get_db()
    cursor = db.contractor_ratings.find({"contractor_id": contractor_id}, {"_id": 0, "rating": 1})
    ratings = [r["rating"] for r in await cursor.to_list(1000)]
    if not ratings:
        return
    from datetime import datetime, timezone
    avg = round(sum(ratings) / len(ratings), 2)
    await db.contractors.update_one(
        {"contractor_id": contractor_id},
        {"$set": {"rating_average": avg, "updated_at": datetime.now(timezone.utc).isoformat()}},
    )


async def compute_rework_rate(contractor_id: str, client_id: str, rework_days: int = REWORK_DAYS) -> Optional[float]:
    """
    Compute rework rate for a contractor within a client: proportion of completed work orders
    that are follow-up jobs at the same property within rework_days of a prior completion.
    Returns value in [0, 1] or None if no completed jobs. Updates contractor.rework_rate.
    """
    db = database.get_db()
    cursor = db.work_orders.find(
        {"contractor_id": contractor_id, "client_id": client_id, "status": "COMPLETED"},
        {"_id": 0, "work_order_id": 1, "property_id": 1, "created_at": 1, "completed_at": 1},
    )
    wos = await cursor.to_list(500)
    if not wos:
        return None

    def _parse_dt(s: Any):
        if s is None:
            return None
        if isinstance(s, datetime):
            return s.replace(tzinfo=timezone.utc) if s.tzinfo is None else s
        try:
            dt = datetime.fromisoformat((s or "").replace("Z", "+00:00"))
            return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
        except Exception:
            return None

    rework_count = 0
    for wo in wos:
        prop_id = wo.get("property_id")
        created = _parse_dt(wo.get("created_at"))
        if not prop_id or not created:
            continue
        # This WO is rework if there exists another completed WO at same property whose completed_at
        # is before this WO's created_at and within rework_days of it.
        for other in wos:
            if other.get("work_order_id") == wo.get("work_order_id"):
                continue
            if other.get("property_id") != prop_id:
                continue
            other_completed = _parse_dt(other.get("completed_at"))
            if not other_completed or other_completed >= created:
                continue
            delta = (created - other_completed).total_seconds() / 86400
            if 0 < delta <= rework_days:
                rework_count += 1
                break

    rate = round(rework_count / len(wos), 4) if wos else None
    now = datetime.now(timezone.utc).isoformat()
    await db.contractors.update_one(
        {"contractor_id": contractor_id},
        {"$set": {"rework_rate": rate, "updated_at": now}},
    )
    return rate
