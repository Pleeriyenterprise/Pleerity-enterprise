"""
Document Template Service – server-side DOCX template store for the template renderer.

Stores .docx templates per (service_code, doc_type) in GridFS and metadata in document_templates.
Used by template_renderer to load a template when present and fall back to code-built DOCX otherwise.
"""
import io
import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from database import database

logger = logging.getLogger(__name__)

COLLECTION = "document_templates"
GRIDFS_BUCKET = "docx_templates"


def _generate_template_id() -> str:
    """Generate a unique template ID."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    rand = hashlib.sha256(f"{ts}{__import__('os').urandom(8).hex()}".encode()).hexdigest()[:8].upper()
    return f"DT-{ts}-{rand}"


async def get_template_bytes(service_code: str, doc_type: Optional[str] = None) -> Optional[bytes]:
    """
    Load stored .docx template bytes for (service_code, doc_type).
    Tries (service_code, doc_type) then (service_code, None) for generic service template.
    Returns None if no template found.
    """
    db = database.get_db()
    from motor.motor_asyncio import AsyncIOMotorGridFSBucket
    from bson import ObjectId

    candidates = [doc_type] if doc_type else [None]
    if doc_type is not None:
        candidates.append(None)  # fallback to generic service template
    for dt in candidates:
        q = {"service_code": service_code, "doc_type": dt}
        meta = await db[COLLECTION].find_one(q, {"_id": 0, "gridfs_id": 1})
        if not meta or not meta.get("gridfs_id"):
            continue
        try:
            fs = AsyncIOMotorGridFSBucket(db, bucket_name=GRIDFS_BUCKET)
            out = io.BytesIO()
            await fs.download_to_stream(ObjectId(meta["gridfs_id"]), out)
            return out.getvalue()
        except Exception as e:
            logger.warning("Failed to load template %s/%s: %s", service_code, dt, e)
            continue
    return None


async def list_templates(
    service_code: Optional[str] = None,
    doc_type: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """List template metadata (no file content)."""
    db = database.get_db()
    q = {}
    if service_code is not None:
        q["service_code"] = service_code
    if doc_type is not None:
        q["doc_type"] = doc_type
    cursor = db[COLLECTION].find(q, {"_id": 0}).sort("updated_at", -1)
    items = await cursor.to_list(length=200)
    for item in items:
        if isinstance(item.get("created_at"), datetime):
            item["created_at"] = item["created_at"].isoformat()
        if isinstance(item.get("updated_at"), datetime):
            item["updated_at"] = item["updated_at"].isoformat()
    return items


async def upload_template(
    service_code: str,
    doc_type: Optional[str],
    content: bytes,
    name: Optional[str] = None,
    uploaded_by: str = "admin",
) -> str:
    """
    Store a .docx template for (service_code, doc_type).
    Replaces any existing template for that key.
    Returns template_id.
    """
    import io
    from motor.motor_asyncio import AsyncIOMotorGridFSBucket
    from bson import ObjectId

    db = database.get_db()
    now = datetime.now(timezone.utc)
    template_id = _generate_template_id()
    content_hash = hashlib.sha256(content).hexdigest()[:16]

    fs = AsyncIOMotorGridFSBucket(db, bucket_name=GRIDFS_BUCKET)
    filename = f"{service_code}_{(doc_type or 'default')}_{template_id}.docx"
    gridfs_id = await fs.upload_from_stream(
        filename,
        io.BytesIO(content),
        metadata={
            "service_code": service_code,
            "doc_type": doc_type or "",
            "template_id": template_id,
            "uploaded_by": uploaded_by,
        },
    )

    existing = await db[COLLECTION].find_one(
        {"service_code": service_code, "doc_type": doc_type or None},
        {"template_id": 1, "gridfs_id": 1},
    )
    if existing:
        await db[COLLECTION].update_one(
            {"service_code": service_code, "doc_type": doc_type or None},
            {
                "$set": {
                    "template_id": template_id,
                    "gridfs_id": str(gridfs_id),
                    "name": name or existing.get("name", filename),
                    "content_hash": content_hash,
                    "updated_at": now,
                    "uploaded_by": uploaded_by,
                }
            },
        )
        logger.info("Updated document template %s for %s/%s", template_id, service_code, doc_type)
    else:
        await db[COLLECTION].insert_one({
            "template_id": template_id,
            "service_code": service_code,
            "doc_type": doc_type or None,
            "name": name or filename,
            "gridfs_id": str(gridfs_id),
            "content_hash": content_hash,
            "created_at": now,
            "updated_at": now,
            "uploaded_by": uploaded_by,
        })
        logger.info("Created document template %s for %s/%s", template_id, service_code, doc_type)
    return template_id


async def delete_template(service_code: str, doc_type: Optional[str] = None) -> bool:
    """Remove stored template for (service_code, doc_type). Returns True if deleted."""
    db = database.get_db()
    doc = await db[COLLECTION].find_one(
        {"service_code": service_code, "doc_type": doc_type or None},
        {"gridfs_id": 1},
    )
    if not doc:
        return False
    try:
        from motor.motor_asyncio import AsyncIOMotorGridFSBucket
        from bson import ObjectId
        fs = AsyncIOMotorGridFSBucket(db, bucket_name=GRIDFS_BUCKET)
        await fs.delete(ObjectId(doc["gridfs_id"]))
    except Exception as e:
        logger.warning("GridFS delete failed for template %s/%s: %s", service_code, doc_type, e)
    result = await db[COLLECTION].delete_one({"service_code": service_code, "doc_type": doc_type or None})
    return result.deleted_count > 0
