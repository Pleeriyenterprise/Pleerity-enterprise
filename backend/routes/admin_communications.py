"""
Admin Communications API: preview, send, history, reusable templates, system banners.
Mutations require Owner or Admin. List/read available to all admin roles (incl. Support, Auditor).
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from database import database
from middleware import admin_route_guard, require_owner_or_admin
from models import AuditAction
from services import admin_communications_service as acs
from utils.audit import create_audit_log

router = APIRouter(
    prefix="/api/admin/communications",
    tags=["admin-communications"],
    dependencies=[Depends(admin_route_guard)],
)


class TargetFilters(BaseModel):
    client_id: Optional[str] = None
    client_ids: Optional[List[str]] = None
    emails: Optional[List[str]] = None
    plan_codes: Optional[List[str]] = None
    plan_types: Optional[List[str]] = None
    subscription_statuses: Optional[List[str]] = None
    billing_statuses: Optional[List[str]] = None
    onboarding_statuses: Optional[List[str]] = None
    entitlement_statuses: Optional[List[str]] = None
    white_label_mode: Optional[str] = None  # white_label_only | non_white_label_only
    subscription_active_only: Optional[bool] = None


class PreviewRequest(BaseModel):
    target_scope: str
    target_filters: Optional[TargetFilters] = None
    message_type: str
    severity: str = "info"
    subject: str
    body_html: str
    body_text: Optional[str] = ""
    in_app_title: Optional[str] = ""
    in_app_body: Optional[str] = ""
    banner_title: Optional[str] = ""
    banner_message: Optional[str] = ""
    channels: List[str] = Field(default_factory=lambda: ["email"])


class SendRequest(PreviewRequest):
    preview_checksum: str
    expected_recipient_count: int
    confirm_send: bool = False
    acknowledge_high_risk: bool = False
    template_id: Optional[str] = None


class DraftUpsertRequest(PreviewRequest):
    draft_communication_id: Optional[str] = None
    draft_name: Optional[str] = None
    template_id: Optional[str] = None


class ScheduleRequest(PreviewRequest):
    preview_checksum: str
    expected_recipient_count: int
    acknowledge_high_risk: bool = False
    template_id: Optional[str] = None
    scheduled_at: datetime


class CommunicationTemplateCreate(BaseModel):
    template_id: Optional[str] = None
    name: str
    description: Optional[str] = ""
    default_message_type: str = "GENERAL_ANNOUNCEMENT"
    subject_template: str
    body_template: str
    in_app_title_template: Optional[str] = ""
    in_app_body_template: Optional[str] = ""
    banner_text_template: Optional[str] = ""


class CommunicationTemplateUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    default_message_type: Optional[str] = None
    subject_template: Optional[str] = None
    body_template: Optional[str] = None
    in_app_title_template: Optional[str] = None
    in_app_body_template: Optional[str] = None
    banner_text_template: Optional[str] = None


class SystemBannerCreate(BaseModel):
    title: str
    message: str
    severity: str = "warning"
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    target_all: bool = True
    target_client_ids: Optional[List[str]] = None
    target_scope: Optional[str] = None
    target_filters: Optional[TargetFilters] = None
    persistent_display: bool = False


class SystemBannerPatch(BaseModel):
    active: Optional[bool] = None
    title: Optional[str] = None
    message: Optional[str] = None
    end_at: Optional[datetime] = None


def _filters_dict(tf: Optional[TargetFilters]) -> Dict[str, Any]:
    if not tf:
        return {}
    return {k: v for k, v in tf.model_dump(exclude_none=True).items() if v is not None}


@router.post("/preview", dependencies=[Depends(require_owner_or_admin)])
async def preview_communication(request: Request, body: PreviewRequest):
    """Resolve recipients server-side and return count, sample rows, and checksum required to send."""
    user = await require_owner_or_admin(request)
    try:
        filters = _filters_dict(body.target_filters)
        sample, total = await acs.resolve_recipients(body.target_scope, filters, limit_sample=50)
        checksum_payload = {
            "message_type": body.message_type,
            "severity": body.severity,
            "target_scope": body.target_scope,
            "target_filters": acs._canonical_filters(filters),
            "subject": body.subject.strip(),
            "body_html": body.body_html,
            "body_text": body.body_text or "",
            "in_app_title": body.in_app_title or "",
            "in_app_body": body.in_app_body or "",
            "banner_title": body.banner_title or "",
            "banner_message": body.banner_message or "",
            "channels": sorted(body.channels),
        }
        preview_checksum = acs.compute_preview_checksum(checksum_payload)
        await create_audit_log(
            action=AuditAction.ADMIN_COMMUNICATION_PREVIEWED,
            actor_id=user.get("portal_user_id"),
            metadata={
                "target_scope": body.target_scope,
                "recipient_count": total,
                "message_type": body.message_type,
            },
        )
        return {
            "recipient_count": total,
            "sample_recipients": sample,
            "preview_checksum": preview_checksum,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/send", dependencies=[Depends(require_owner_or_admin)])
async def send_communication(request: Request, body: SendRequest):
    user = await require_owner_or_admin(request)
    filters = _filters_dict(body.target_filters)
    try:
        result = await acs.send_communication(
            admin_user=user,
            message_type=body.message_type,
            severity=body.severity,
            target_scope=body.target_scope,
            target_filters=filters,
            subject=body.subject,
            body_html=body.body_html,
            body_text=body.body_text,
            in_app_title=body.in_app_title,
            in_app_body=body.in_app_body,
            banner_title=body.banner_title,
            banner_message=body.banner_message,
            channels=body.channels,
            template_id=body.template_id,
            preview_checksum=body.preview_checksum,
            expected_recipient_count=body.expected_recipient_count,
            confirm_send=body.confirm_send,
            acknowledge_high_risk=body.acknowledge_high_risk,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/drafts", dependencies=[Depends(require_owner_or_admin)])
async def upsert_communication_draft_route(request: Request, body: DraftUpsertRequest):
    user = await require_owner_or_admin(request)
    filters = _filters_dict(body.target_filters)
    try:
        cid = await acs.upsert_communication_draft(
            user,
            draft_communication_id=body.draft_communication_id,
            target_scope=body.target_scope,
            target_filters=filters,
            message_type=body.message_type,
            severity=body.severity,
            subject=body.subject,
            body_html=body.body_html,
            channels=body.channels,
            in_app_title=body.in_app_title,
            in_app_body=body.in_app_body,
            banner_title=body.banner_title,
            banner_message=body.banner_message,
            template_id=body.template_id,
            draft_name=body.draft_name,
        )
        return {"communication_id": cid}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/drafts")
async def list_communication_drafts_route(request: Request):
    user = await admin_route_guard(request)
    items = await acs.list_communication_drafts(user.get("portal_user_id") or "")
    return {"items": items}


@router.delete("/drafts/{communication_id}", dependencies=[Depends(require_owner_or_admin)])
async def delete_communication_draft_route(request: Request, communication_id: str):
    user = await require_owner_or_admin(request)
    ok = await acs.delete_communication_draft(communication_id, user.get("portal_user_id") or "")
    if not ok:
        raise HTTPException(status_code=404, detail="Draft not found")
    return {"ok": True}


@router.post("/schedule", dependencies=[Depends(require_owner_or_admin)])
async def schedule_communication_route(request: Request, body: ScheduleRequest):
    user = await require_owner_or_admin(request)
    filters = _filters_dict(body.target_filters)
    try:
        cid = await acs.schedule_communication(
            user,
            target_scope=body.target_scope,
            target_filters=filters,
            message_type=body.message_type,
            severity=body.severity,
            subject=body.subject,
            body_html=body.body_html,
            body_text=body.body_text,
            in_app_title=body.in_app_title,
            in_app_body=body.in_app_body,
            banner_title=body.banner_title,
            banner_message=body.banner_message,
            channels=body.channels,
            template_id=body.template_id,
            preview_checksum=body.preview_checksum,
            expected_recipient_count=body.expected_recipient_count,
            acknowledge_high_risk=body.acknowledge_high_risk,
            scheduled_at=body.scheduled_at,
        )
        return {"communication_id": cid, "status": "SCHEDULED"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/messages")
async def list_communication_messages(
    request: Request,
    message_type: Optional[str] = None,
    sent_by: Optional[str] = None,
    target_scope: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    client_id: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    include_drafts_and_scheduled: bool = False,
    skip: int = 0,
    limit: int = 50,
):
    await admin_route_guard(request)
    df = None
    dt = None
    if date_from:
        try:
            df = datetime.fromisoformat(date_from.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date_from")
    if date_to:
        try:
            dt = datetime.fromisoformat(date_to.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date_to")
    rows, total = await acs.list_messages(
        message_type=message_type,
        sent_by=sent_by,
        target_scope=target_scope,
        status=status_filter,
        client_id=client_id,
        date_from=df,
        date_to=dt,
        include_drafts_and_scheduled=include_drafts_and_scheduled,
        skip=skip,
        limit=limit,
    )
    return {"items": rows, "total": total, "skip": skip, "limit": limit}


@router.get("/messages/{communication_id}")
async def get_communication_message(request: Request, communication_id: str):
    await admin_route_guard(request)
    doc = await acs.get_message_detail(communication_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Not found")
    return doc


@router.get("/templates")
async def list_communication_templates(request: Request):
    await admin_route_guard(request)
    db = database.get_db()
    cur = db.communication_templates.find({}, {"_id": 0}).sort("name", 1)
    items = await cur.to_list(length=500)
    return {"items": items}


@router.post("/templates", dependencies=[Depends(require_owner_or_admin)])
async def create_communication_template(request: Request, body: CommunicationTemplateCreate):
    user = await require_owner_or_admin(request)
    db = database.get_db()
    import uuid

    tid = (body.template_id or "").strip() or f"TPL-{uuid.uuid4().hex[:10].upper()}"
    now = datetime.now(timezone.utc)
    doc = {
        "template_id": tid,
        "name": body.name,
        "description": body.description or "",
        "default_message_type": body.default_message_type,
        "subject_template": body.subject_template,
        "body_template": body.body_template,
        "in_app_title_template": body.in_app_title_template or "",
        "in_app_body_template": body.in_app_body_template or "",
        "banner_text_template": body.banner_text_template or "",
        "is_system_seed": False,
        "created_at": now,
        "updated_at": now,
        "created_by_portal_user_id": user.get("portal_user_id"),
    }
    try:
        await db.communication_templates.insert_one(doc)
    except Exception:
        raise HTTPException(status_code=409, detail="template_id may already exist")
    doc.pop("_id", None)
    await create_audit_log(
        action=AuditAction.ADMIN_COMMUNICATION_TEMPLATE_SAVED,
        actor_id=user.get("portal_user_id"),
        metadata={"template_id": tid, "op": "create"},
    )
    return doc


@router.put("/templates/{template_id}", dependencies=[Depends(require_owner_or_admin)])
async def update_communication_template(
    request: Request, template_id: str, body: CommunicationTemplateUpdate
):
    user = await require_owner_or_admin(request)
    db = database.get_db()
    existing = await db.communication_templates.find_one({"template_id": template_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Template not found")
    if existing.get("is_system_seed"):
        pass  # allow editing seeded templates (operational need)
    updates = {k: v for k, v in body.model_dump(exclude_none=True).items()}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    updates["updated_at"] = datetime.now(timezone.utc)
    updates["updated_by_portal_user_id"] = user.get("portal_user_id")
    await db.communication_templates.update_one({"template_id": template_id}, {"$set": updates})
    await create_audit_log(
        action=AuditAction.ADMIN_COMMUNICATION_TEMPLATE_SAVED,
        actor_id=user.get("portal_user_id"),
        metadata={"template_id": template_id, "op": "update"},
    )
    out = await db.communication_templates.find_one({"template_id": template_id}, {"_id": 0})
    return out


@router.get("/banners")
async def list_system_banners(request: Request, active_only: bool = False):
    await admin_route_guard(request)
    db = database.get_db()
    q: Dict[str, Any] = {}
    if active_only:
        q["active"] = True
    cur = db.system_banners.find(q, {"_id": 0}).sort("created_at", -1).limit(200)
    items = await cur.to_list(length=200)
    return {"items": items}


@router.post("/banners", dependencies=[Depends(require_owner_or_admin)])
async def create_system_banner(request: Request, body: SystemBannerCreate):
    user = await require_owner_or_admin(request)
    db = database.get_db()
    import uuid

    now = datetime.now(timezone.utc)
    bid = f"BNR-{uuid.uuid4().hex[:10].upper()}"
    tscope = (body.target_scope or "").strip() or None
    tf_canon = acs._canonical_filters(_filters_dict(body.target_filters))
    doc = {
        "banner_id": bid,
        "title": body.title.strip(),
        "message": body.message.strip(),
        "severity": (body.severity or "warning").lower(),
        "start_at": body.start_at or now,
        "end_at": body.end_at,
        "active": True,
        "target_all": bool(body.target_all),
        "target_client_ids": list(body.target_client_ids or []),
        "target_scope": None,
        "target_filters": None,
        "persistent_display": body.persistent_display,
        "communication_id": None,
        "created_by_portal_user_id": user.get("portal_user_id"),
        "created_at": now,
        "updated_at": now,
    }
    if doc["target_all"]:
        doc["target_client_ids"] = []
    elif tscope == "SELECTED":
        doc["target_scope"] = "SELECTED"
        doc["target_filters"] = tf_canon
    elif doc["target_client_ids"]:
        pass
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Banner audience required: target_all, target_client_ids, or target_scope=SELECTED with filters",
        )
    await db.system_banners.insert_one(doc)
    await create_audit_log(
        action=AuditAction.ADMIN_SYSTEM_BANNER_UPDATED,
        actor_id=user.get("portal_user_id"),
        metadata={"banner_id": bid, "op": "create"},
    )
    doc.pop("_id", None)
    return doc


@router.patch("/banners/{banner_id}", dependencies=[Depends(require_owner_or_admin)])
async def patch_system_banner(request: Request, banner_id: str, body: SystemBannerPatch):
    user = await require_owner_or_admin(request)
    db = database.get_db()
    b = await db.system_banners.find_one({"banner_id": banner_id})
    if not b:
        raise HTTPException(status_code=404, detail="Banner not found")
    updates = {k: v for k, v in body.model_dump(exclude_none=True).items()}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields")
    updates["updated_at"] = datetime.now(timezone.utc)
    await db.system_banners.update_one({"banner_id": banner_id}, {"$set": updates})
    await create_audit_log(
        action=AuditAction.ADMIN_SYSTEM_BANNER_UPDATED,
        actor_id=user.get("portal_user_id"),
        metadata={"banner_id": banner_id, "op": "patch", **updates},
    )
    return await db.system_banners.find_one({"banner_id": banner_id}, {"_id": 0})
