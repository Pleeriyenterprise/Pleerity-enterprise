"""Validate document_id ownership for rent operations links."""
from typing import Optional

from database import database


async def validate_document_for_property(
    client_id: str,
    property_id: str,
    document_id: Optional[str],
) -> None:
    if not document_id:
        return
    db = database.get_db()
    doc = await db.documents.find_one(
        {
            "document_id": document_id,
            "client_id": client_id,
            "property_id": property_id,
        },
        {"_id": 1},
    )
    if not doc:
        raise ValueError("DOCUMENT_NOT_FOUND")
