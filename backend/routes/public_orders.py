"""
Public Order Routes – token-based view and download for one-time users (no login).
"""

import os
import io
import logging
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from database import database
from services.order_view_token import validate_order_view_token
from services.order_service import get_order
from services.order_workflow import OrderStatus
from services.document_generator import get_document_versions

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/public/orders", tags=["public-orders"])


@router.get("/view")
async def view_order_public(token: str = Query(..., description="Order view token from delivery email")):
    """
    Get order summary and document download links for one-time users (no login).
    Token is sent in the delivery email.
    """
    payload = validate_order_view_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    order_id = payload.get("order_id")
    email = payload.get("email")
    if not order_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    order = await get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.get("customer", {}).get("email") != email:
        raise HTTPException(status_code=403, detail="Not authorized for this order")
    status = order.get("status")
    if status not in (OrderStatus.COMPLETED.value, OrderStatus.DELIVERING.value):
        return {
            "order_id": order_id,
            "status": status,
            "service_name": order.get("service_name"),
            "documents_available": False,
            "message": "Documents will be available once your order is completed.",
            "documents": [],
            "download_base_url": None,
        }
    approved_version = order.get("approved_document_version")
    versions = await get_document_versions(order_id)
    documents = []
    api_base = (os.getenv("BACKEND_URL") or os.getenv("API_URL") or "").rstrip("/")
    for v in versions:
        if getattr(v, "version", None) == approved_version:
            if getattr(v, "filename_pdf", None):
                path = f"/api/public/orders/download?token={token}&version={v.version}&format=pdf"
                documents.append({
                    "version": v.version,
                    "format": "pdf",
                    "label": f"{order.get('service_name', 'Document')} (PDF)",
                    "download_url": f"{api_base}{path}" if api_base else path,
                    "download_path": path,
                })
            if getattr(v, "filename_docx", None):
                path = f"/api/public/orders/download?token={token}&version={v.version}&format=docx"
                documents.append({
                    "version": v.version,
                    "format": "docx",
                    "label": f"{order.get('service_name', 'Document')} (DOCX)",
                    "download_url": f"{api_base}{path}" if api_base else path,
                    "download_path": path,
                })
            break
    return {
        "order_id": order_id,
        "status": status,
        "service_name": order.get("service_name"),
        "documents_available": len(documents) > 0,
        "documents": documents,
    }


@router.get("/download")
async def download_order_document_public(
    token: str = Query(..., description="Order view token"),
    version: int = Query(..., description="Document version"),
    format: str = Query("pdf", description="pdf or docx"),
):
    """
    Download a document for an order using the view token (no login).
    """
    payload = validate_order_view_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    order_id = payload.get("order_id")
    email = payload.get("email")
    if not order_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    order = await get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.get("customer", {}).get("email") != email:
        raise HTTPException(status_code=403, detail="Not authorized")
    if order.get("status") not in (OrderStatus.COMPLETED.value, OrderStatus.DELIVERING.value):
        raise HTTPException(status_code=403, detail="Documents are not yet available for this order")
    approved_version = order.get("approved_document_version")
    if version != approved_version:
        raise HTTPException(status_code=403, detail="Document version not available")
    format_lower = format.lower()
    if format_lower not in ("pdf", "docx"):
        raise HTTPException(status_code=400, detail="Invalid format. Use pdf or docx")
    db = database.get_db()
    version_record = await db.document_versions_v2.find_one(
        {"order_id": order_id, "version": version},
        {"_id": 0, "docx": 1, "pdf": 1},
    )
    if not version_record:
        raise HTTPException(status_code=404, detail="Document version not found")
    file_info = version_record.get("pdf" if format_lower == "pdf" else "docx", {})
    gridfs_id = file_info.get("gridfs_id")
    filename = file_info.get("filename", f"{order_id}_v{version}.{format_lower}")
    if not gridfs_id:
        raise HTTPException(status_code=404, detail=f"No {format.upper()} file for this version")
    try:
        from motor.motor_asyncio import AsyncIOMotorGridFSBucket
        from bson import ObjectId
        fs = AsyncIOMotorGridFSBucket(db, bucket_name="order_files")
        stream = io.BytesIO()
        await fs.download_to_stream(ObjectId(gridfs_id), stream)
        content = stream.getvalue()
        content_type = "application/pdf" if format_lower == "pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        return Response(
            content=content,
            media_type=content_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except Exception as e:
        logger.error(f"Public document download failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve document")
