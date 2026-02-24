"""
Admin Submissions API - Unified list, get, PATCH, notes, mark-spam, export for
contact, talent, partnership, and lead submissions.
Uses composite id: contact-{id}, talent-{id}, partnership-{id}, lead-{id}.
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import StreamingResponse
from database import database
from middleware import admin_route_guard
from datetime import datetime, timezone
from typing import Optional, List
from pydantic import BaseModel
import csv
import io
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/submissions", tags=["admin-submissions"])

SUBMISSION_TYPES = ("contact", "talent", "partnership", "lead")
COLLECTION_MAP = {
    "contact": "contact_submissions",
    "talent": "talent_pool",
    "partnership": "partnership_enquiries",
    "lead": "leads",
}
ID_FIELD_MAP = {
    "contact": "submission_id",
    "talent": "submission_id",
    "partnership": "enquiry_id",
    "lead": "lead_id",
}
CREATED_AT_MAP = {
    "contact": "created_at",
    "talent": "created_at",
    "partnership": "created_at",
    "lead": "created_at",
}


def _parse_composite_id(composite_id: str) -> tuple:
    """Return (type, id) e.g. ('contact', 'CONTACT-ABC123')."""
    for t in SUBMISSION_TYPES:
        if composite_id.startswith(t + "-"):
            return t, composite_id[len(t) + 1:]
    raise HTTPException(status_code=400, detail="Invalid submission id format. Use type-id e.g. contact-CONTACT-ABC123.")


def _get_collection_and_id_field(submission_type: str):
    if submission_type not in COLLECTION_MAP:
        raise HTTPException(status_code=400, detail="Invalid type")
    return COLLECTION_MAP[submission_type], ID_FIELD_MAP[submission_type]


class PATCHBody(BaseModel):
    status: Optional[str] = None
    priority: Optional[str] = None
    assigned_to: Optional[str] = None
    tags: Optional[List[str]] = None


class NoteBody(BaseModel):
    note: str


@router.get("/export/csv", dependencies=[Depends(admin_route_guard)])
async def export_submissions_csv(
    type: str = Query(..., description="contact | talent | partnership | lead"),
    status: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    current_user: dict = Depends(admin_route_guard),
):
    """Export submissions as CSV for the given type and filters."""
    if type not in SUBMISSION_TYPES:
        raise HTTPException(status_code=400, detail="type must be one of: contact, talent, partnership, lead")
    db = database.get_db()
    coll_name, id_field = _get_collection_and_id_field(type)
    created_field = CREATED_AT_MAP[type]
    coll = db[coll_name]

    query = {}
    if status:
        query["status"] = status
    if from_date:
        query[created_field] = query.get(created_field) or {}
        query[created_field]["$gte"] = from_date
    if to_date:
        query[created_field] = query.get(created_field) or {}
        query[created_field]["$lte"] = to_date

    cursor = coll.find(query, {"_id": 0}).sort(created_field, -1)
    items = await cursor.to_list(5000)

    output = io.StringIO()
    if type == "contact":
        writer = csv.DictWriter(output, fieldnames=["submission_id", "created_at", "full_name", "email", "phone", "subject", "status"])
        writer.writeheader()
        for it in items:
            writer.writerow({k: (it.get(k) or "") for k in ["submission_id", "created_at", "full_name", "email", "phone", "subject", "status"]})
    elif type == "talent":
        writer = csv.DictWriter(output, fieldnames=["submission_id", "created_at", "full_name", "email", "phone", "status"])
        writer.writeheader()
        for it in items:
            writer.writerow({k: (it.get(k) or "") for k in ["submission_id", "created_at", "full_name", "email", "phone", "status"]})
    elif type == "partnership":
        writer = csv.DictWriter(output, fieldnames=["enquiry_id", "created_at", "first_name", "last_name", "work_email", "company_name", "status"])
        writer.writeheader()
        for it in items:
            writer.writerow({k: (it.get(k) or "") for k in ["enquiry_id", "created_at", "first_name", "last_name", "work_email", "company_name", "status"]})
    else:
        writer = csv.DictWriter(output, fieldnames=["lead_id", "created_at", "name", "email", "phone", "status", "source_platform"])
        writer.writeheader()
        for it in items:
            writer.writerow({k: (it.get(k) or "") for k in ["lead_id", "created_at", "name", "email", "phone", "status", "source_platform"]})

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=submissions_{}.csv".format(type)},
    )


@router.get("", dependencies=[Depends(admin_route_guard)])
async def list_submissions(
    type: str = Query(..., description="contact | talent | partnership | lead"),
    status: Optional[str] = None,
    q: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(admin_route_guard),
):
    """List submissions for a given type with optional filters."""
    if type not in SUBMISSION_TYPES:
        raise HTTPException(status_code=400, detail="type must be one of: contact, talent, partnership, lead")
    db = database.get_db()
    coll_name, id_field = _get_collection_and_id_field(type)
    coll = db[coll_name]
    created_field = CREATED_AT_MAP[type]

    query = {}
    if status:
        query["status"] = status
    if q:
        if type == "contact":
            query["$or"] = [
                {"full_name": {"$regex": q, "$options": "i"}},
                {"email": {"$regex": q, "$options": "i"}},
                {"subject": {"$regex": q, "$options": "i"}},
            ]
        elif type == "talent":
            query["$or"] = [
                {"full_name": {"$regex": q, "$options": "i"}},
                {"email": {"$regex": q, "$options": "i"}},
            ]
        elif type == "partnership":
            query["$or"] = [
                {"first_name": {"$regex": q, "$options": "i"}},
                {"last_name": {"$regex": q, "$options": "i"}},
                {"company_name": {"$regex": q, "$options": "i"}},
                {"work_email": {"$regex": q, "$options": "i"}},
            ]
        else:
            query["$or"] = [
                {"name": {"$regex": q, "$options": "i"}},
                {"email": {"$regex": q, "$options": "i"}},
            ]
    if from_date:
        query[created_field] = query.get(created_field) or {}
        query[created_field]["$gte"] = from_date
    if to_date:
        query[created_field] = query.get(created_field) or {}
        query[created_field]["$lte"] = to_date

    skip = (page - 1) * page_size
    cursor = coll.find(query, {"_id": 0}).sort(created_field, -1).skip(skip).limit(page_size)
    items = await cursor.to_list(page_size)
    total = await coll.count_documents(query)

    rows = []
    for it in items:
        sid = it.get(id_field)
        composite = f"{type}-{sid}"
        if type == "contact":
            rows.append({
                "composite_id": composite,
                "date": it.get("created_at"),
                "name": it.get("full_name"),
                "email": it.get("email"),
                "phone": it.get("phone"),
                "status": it.get("status"),
                "source": (it.get("source") or {}).get("page"),
                "assigned_to": None,
                "priority": None,
            })
        elif type == "talent":
            rows.append({
                "composite_id": composite,
                "date": it.get("created_at"),
                "name": it.get("full_name"),
                "email": it.get("email"),
                "phone": it.get("phone"),
                "status": it.get("status"),
                "source": None,
                "assigned_to": None,
                "priority": None,
            })
        elif type == "partnership":
            rows.append({
                "composite_id": composite,
                "date": it.get("created_at"),
                "name": f"{it.get('first_name', '')} {it.get('last_name', '')}".strip(),
                "email": it.get("work_email"),
                "phone": it.get("phone"),
                "status": it.get("status"),
                "source": None,
                "assigned_to": it.get("updated_by"),
                "priority": None,
            })
        else:
            rows.append({
                "composite_id": composite,
                "date": it.get("created_at"),
                "name": it.get("name"),
                "email": it.get("email"),
                "phone": it.get("phone"),
                "status": it.get("status"),
                "source": it.get("source_platform"),
                "assigned_to": it.get("assigned_to"),
                "priority": None,
            })

    return {"items": rows, "total": total, "page": page, "page_size": page_size}


@router.get("/{composite_id}", dependencies=[Depends(admin_route_guard)])
async def get_submission(
    composite_id: str,
    current_user: dict = Depends(admin_route_guard),
):
    """Get one submission by composite id."""
    sub_type, sid = _parse_composite_id(composite_id)
    db = database.get_db()
    coll_name, id_field = _get_collection_and_id_field(sub_type)
    doc = await db[coll_name].find_one({id_field: sid}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Submission not found")
    doc["composite_id"] = composite_id
    doc["_type"] = sub_type
    return doc


@router.patch("/{composite_id}", dependencies=[Depends(admin_route_guard)])
async def patch_submission(
    composite_id: str,
    body: PATCHBody,
    current_user: dict = Depends(admin_route_guard),
):
    """Update status/assigned_to/tags and append audit entry."""
    sub_type, sid = _parse_composite_id(composite_id)
    db = database.get_db()
    coll_name, id_field = _get_collection_and_id_field(sub_type)
    coll = db[coll_name]

    doc = await coll.find_one({id_field: sid})
    if not doc:
        raise HTTPException(status_code=404, detail="Submission not found")

    now = datetime.now(timezone.utc)
    update = {"updated_at": now}
    if body.status is not None:
        update["status"] = body.status
    if body.assigned_to is not None and sub_type == "lead":
        update["assigned_to"] = body.assigned_to
        update["assigned_at"] = now
    if body.tags is not None:
        update["tags"] = body.tags

    audit_entry = {
        "at": now.isoformat(),
        "by": current_user.get("email") or current_user.get("user_id") or "admin",
        "changes": {k: v for k, v in update.items() if k != "updated_at"},
    }
    await coll.update_one(
        {id_field: sid},
        {"$set": update, "$push": {"audit": audit_entry}},
    )

    return {"ok": True, "message": "Updated"}


@router.post("/{composite_id}/notes", dependencies=[Depends(admin_route_guard)])
async def add_note(
    composite_id: str,
    body: NoteBody,
    current_user: dict = Depends(admin_route_guard),
):
    """Append an admin note to the submission."""
    sub_type, sid = _parse_composite_id(composite_id)
    db = database.get_db()
    coll_name, id_field = _get_collection_and_id_field(sub_type)
    coll = db[coll_name]

    doc = await coll.find_one({id_field: sid})
    if not doc:
        raise HTTPException(status_code=404, detail="Submission not found")

    now = datetime.now(timezone.utc)
    note_entry = {
        "at": now.isoformat(),
        "by": current_user.get("email") or current_user.get("user_id") or "admin",
        "note": (body.note or "")[:5000],
    }
    await coll.update_one(
        {id_field: sid},
        {"$push": {"notes": note_entry}, "$set": {"updated_at": now}},
    )
    return {"ok": True}


@router.post("/{composite_id}/mark-spam", dependencies=[Depends(admin_route_guard)])
async def mark_spam(
    composite_id: str,
    current_user: dict = Depends(admin_route_guard),
):
    """Set status to SPAM and record in audit."""
    sub_type, sid = _parse_composite_id(composite_id)
    db = database.get_db()
    coll_name, id_field = _get_collection_and_id_field(sub_type)
    coll = db[coll_name]

    doc = await coll.find_one({id_field: sid})
    if not doc:
        raise HTTPException(status_code=404, detail="Submission not found")

    now = datetime.now(timezone.utc)
    await coll.update_one(
        {id_field: sid},
        {
            "$set": {"status": "SPAM", "updated_at": now},
            "$push": {"audit": {"at": now.isoformat(), "by": current_user.get("email") or "admin", "action": "mark_spam"}},
        },
    )
    return {"ok": True, "message": "Marked as spam"}
