"""
Public read API for governed legal/marketing page content.
No authentication required. Does not expose audit metadata or drafts.
"""
from fastapi import APIRouter, HTTPException, Response

from database import database
from services.legal_content_defaults import LEGAL_SLUGS
from services.legal_content_service import get_published_content

router = APIRouter(prefix="/api/public/legal-content", tags=["public-legal"])


@router.get("/{slug}")
async def read_published_legal_content(slug: str, response: Response):
    if slug not in LEGAL_SLUGS:
        raise HTTPException(status_code=404, detail="Page not found")
    db = database.get_db()
    payload = await get_published_content(db, slug)
    if payload.get("error"):
        raise HTTPException(status_code=404, detail="Page not found")
    version = payload.get("version") or 0
    response.headers["Cache-Control"] = "public, max-age=60"
    response.headers["X-Legal-Content-Version"] = str(version)
    response.headers["X-Legal-Content-Source"] = payload.get("source", "unknown")
    return payload


@router.get("")
async def list_published_legal_slugs():
    return {"slugs": list(LEGAL_SLUGS)}
