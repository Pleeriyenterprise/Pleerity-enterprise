"""
Contractor service: CRUD for contractors (Ops & Compliance / Contractor Network).
Contractors can be system-wide (client_id None) or client-preferred (client_id set).
"""
from typing import Any, Dict, List, Optional
from database import database
import logging

logger = logging.getLogger(__name__)

try:
    from bson import ObjectId
except ImportError:
    ObjectId = None  # type: ignore[misc, assignment]


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
    skip: int = 0,
    limit: int = 100,
) -> Dict[str, Any]:
    """List contractors, optionally filtered by client_id and vetted status."""
    db = database.get_db()
    q = {}
    if client_id is not None:
        q["client_id"] = client_id
    if vetted_only:
        q["vetted"] = True
    cursor = db.contractors.find(q).sort("name", 1).skip(skip).limit(limit)
    items = await cursor.to_list(limit)
    total = await db.contractors.count_documents(q)
    return {
        "contractors": [_sanitize_doc(d) for d in items],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


async def list_contractors_for_client(
    client_id: str,
    vetted_only: bool = False,
    skip: int = 0,
    limit: int = 100,
) -> Dict[str, Any]:
    """List contractors visible to a client: those assigned to them or system-wide (client_id null)."""
    db = database.get_db()
    q = {"$or": [{"client_id": client_id}, {"client_id": None}]}
    if vetted_only:
        q["vetted"] = True
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
) -> Dict[str, Any]:
    """Create a new contractor."""
    from datetime import datetime, timezone
    import uuid

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
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    db = database.get_db()
    await db.contractors.insert_one(doc)
    # Return JSON-safe payload (PyMongo adds _id in place; avoid returning raw ObjectId)
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
