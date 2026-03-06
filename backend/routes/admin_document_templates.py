"""
Admin API for server-side document templates (DOCX per service_code/doc_type).
Used by template renderer when present; otherwise code-built DOCX is used.
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field

from middleware import admin_route_guard
from services.document_template_service import (
    list_templates,
    upload_template,
    delete_template,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/document-templates", tags=["admin-document-templates"])


class TemplateListItem(BaseModel):
    template_id: str
    service_code: str
    doc_type: Optional[str]
    name: Optional[str]
    created_at: Optional[str]
    updated_at: Optional[str]


@router.get("")
async def get_templates(
    service_code: Optional[str] = None,
    doc_type: Optional[str] = None,
    current_user: dict = Depends(admin_route_guard),
):
    """List stored document templates (metadata only)."""
    items = await list_templates(service_code=service_code, doc_type=doc_type)
    return {"templates": items, "total": len(items)}


@router.post("")
async def post_template(
    current_user: dict = Depends(admin_route_guard),
    file: UploadFile = File(...),
    service_code: str = Form(...),
    doc_type: Optional[str] = Form(None),
    name: Optional[str] = Form(None),
):
    """
    Upload a .docx template for (service_code, doc_type).
    Replaces any existing template for that key.
    Template can use Jinja2 placeholders: {{ order.order_id }}, {{ output.executive_summary }}, {{ intake.customer_name }}, etc.
    """
    if not file.filename or not file.filename.lower().endswith(".docx"):
        raise HTTPException(status_code=400, detail="File must be a .docx document")
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="File is empty")
    try:
        template_id = await upload_template(
            service_code=service_code.strip(),
            doc_type=doc_type.strip() if doc_type else None,
            content=content,
            name=name.strip() if name else None,
            uploaded_by=current_user.get("email", "admin"),
        )
        return {"template_id": template_id, "service_code": service_code, "doc_type": doc_type, "message": "Template uploaded"}
    except Exception as e:
        logger.exception("Upload template failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("")
async def delete_template_route(
    service_code: str,
    doc_type: Optional[str] = None,
    current_user: dict = Depends(admin_route_guard),
):
    """Remove stored template for (service_code, doc_type). Renderer will fall back to code-built DOCX."""
    deleted = await delete_template(service_code=service_code, doc_type=doc_type or None)
    if not deleted:
        raise HTTPException(status_code=404, detail="Template not found")
    return {"deleted": True, "service_code": service_code, "doc_type": doc_type}
