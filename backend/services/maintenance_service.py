"""
Maintenance workflows: work orders (tenant report / client / admin).
Create, list, update, assign contractor. SLA fields optional.
Gated by MAINTENANCE_WORKFLOWS feature flag for client/tenant.
"""
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
import uuid
from database import database
import logging
from auth import generate_secure_token, hash_token
from services.work_order_assignment_constants import (
    ASSIGNMENT_ROUTING_ASSIGNED,
    ASSIGNMENT_ROUTING_UNASSIGNED,
)
from services.work_order_execution_constants import (
    WORK_ORDER_CATEGORY_COMPLIANCE,
    WORK_ORDER_KIND_COMPLIANCE,
    WORK_ORDER_KIND_MAINTENANCE,
)

logger = logging.getLogger(__name__)

# Work order status lifecycle (existing + additive)
STATUS_OPEN = "OPEN"
STATUS_ASSIGNED = "ASSIGNED"
STATUS_IN_PROGRESS = "IN_PROGRESS"
STATUS_COMPLETED = "COMPLETED"
STATUS_CANCELLED = "CANCELLED"
# Additive statuses (Maintenance Intelligence Flow)
STATUS_DRAFT = "DRAFT"
STATUS_SCHEDULED = "SCHEDULED"
STATUS_AWAITING_PARTS = "AWAITING_PARTS"
STATUS_VERIFIED = "VERIFIED"
STATUS_CLOSED = "CLOSED"

ALL_STATUSES = (
    STATUS_OPEN,
    STATUS_ASSIGNED,
    STATUS_IN_PROGRESS,
    STATUS_COMPLETED,
    STATUS_CANCELLED,
    STATUS_DRAFT,
    STATUS_SCHEDULED,
    STATUS_AWAITING_PARTS,
    STATUS_VERIFIED,
    STATUS_CLOSED,
)

SOURCE_TENANT_REQUEST = "tenant_request"
SOURCE_CLIENT = "client"
SOURCE_ADMIN = "admin"

# Categories for rule-based categorisation (optional)
CATEGORY_PLUMBING = "plumbing"
CATEGORY_ELECTRICAL = "electrical"
CATEGORY_HEATING = "heating"
CATEGORY_GENERAL = "general"
SEVERITY_LOW = "low"
SEVERITY_MEDIUM = "medium"
SEVERITY_HIGH = "high"
SEVERITY_URGENT = "urgent"


async def create_work_order(
    client_id: str,
    property_id: str,
    description: str,
    source: str = SOURCE_CLIENT,
    reporter_id: Optional[str] = None,
    category: Optional[str] = None,
    severity: Optional[str] = None,
    asset_id: Optional[str] = None,
    issue_id: Optional[str] = None,
    risk_signal_id: Optional[str] = None,
    cost_estimate_min: Optional[float] = None,
    cost_estimate_max: Optional[float] = None,
    created_from: Optional[str] = None,
    triggering_rule: Optional[str] = None,
    operational_root_key: Optional[str] = None,
    initial_status: Optional[str] = None,
    sla_respond_by: Optional[str] = None,
    sla_complete_by: Optional[str] = None,
    use_triage: bool = True,
    *,
    work_order_kind: str = WORK_ORDER_KIND_MAINTENANCE,
    requirement_code: Optional[str] = None,
    compliance_purpose: Optional[str] = None,
    compliance_due_at: Optional[str] = None,
    compliance_generated_from: Optional[str] = None,
    expected_output_document_type: Optional[str] = None,
    linked_property_requirement_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a work order. source: tenant_request | client | admin.
    Optional: asset_id, issue_id, cost estimates, initial_status (default OPEN), SLA overrides.
    If use_triage is True and severity/sla are not provided, runs triage and applies result (stores reasoning).
    Compliance execution work orders (work_order_kind=COMPLIANCE) skip maintenance triage and use explicit metadata.
    """
    db = database.get_db()
    now = datetime.now(timezone.utc).isoformat()
    work_order_id = str(uuid.uuid4())
    sla_respond_hours = 24
    sla_complete_days = 5
    default_respond = (datetime.now(timezone.utc) + timedelta(hours=sla_respond_hours)).isoformat()
    default_complete = (datetime.now(timezone.utc) + timedelta(days=sla_complete_days)).isoformat()
    status = (initial_status or STATUS_OPEN).strip().upper() if initial_status else STATUS_OPEN
    if status not in ALL_STATUSES:
        status = STATUS_OPEN

    kind = (work_order_kind or WORK_ORDER_KIND_MAINTENANCE).strip().upper()
    if kind not in (WORK_ORDER_KIND_MAINTENANCE, WORK_ORDER_KIND_COMPLIANCE):
        kind = WORK_ORDER_KIND_MAINTENANCE
    use_triage_effective = use_triage and kind != WORK_ORDER_KIND_COMPLIANCE
    if kind == WORK_ORDER_KIND_COMPLIANCE:
        eff_category = WORK_ORDER_CATEGORY_COMPLIANCE
    else:
        eff_category = (category or "").strip() or CATEGORY_GENERAL

    triage_reasoning: Optional[List[str]] = None
    recommended_contractor_type: Optional[str] = None
    effective_severity = severity
    effective_respond = sla_respond_by
    effective_complete = sla_complete_by

    if use_triage_effective and (effective_severity is None or effective_respond is None or effective_complete is None):
        try:
            from services.maintenance_triage import triage_maintenance_issue_async
            triage = await triage_maintenance_issue_async(
                description=description,
                category=eff_category,
                source=source,
                property_id=property_id,
                client_id=client_id,
            )
            if effective_severity is None:
                effective_severity = triage.get("severity") or SEVERITY_MEDIUM
            if effective_respond is None or effective_complete is None:
                sla_hours = triage.get("sla_hours") or 72
                respond_dt = datetime.now(timezone.utc) + timedelta(hours=min(24, sla_hours))
                complete_dt = datetime.now(timezone.utc) + timedelta(hours=sla_hours)
                if effective_respond is None:
                    effective_respond = respond_dt.isoformat()
                if effective_complete is None:
                    effective_complete = complete_dt.isoformat()
            triage_reasoning = triage.get("reasoning") or []
            recommended_contractor_type = triage.get("recommended_contractor_type")
        except Exception as e:
            logger.warning("Triage failed for work order, using defaults: %s", e)

    doc = {
        "work_order_id": work_order_id,
        "client_id": client_id,
        "property_id": property_id,
        "description": (description or "").strip(),
        "source": source,
        "reporter_id": reporter_id,
        "category": eff_category,
        "work_order_kind": kind,
        "requirement_code": (requirement_code or "").strip().lower() or None,
        "compliance_purpose": (compliance_purpose or "").strip().lower() or None,
        "compliance_due_at": (compliance_due_at or "").strip() or None,
        "compliance_generated_from": (compliance_generated_from or "").strip().lower() or None,
        "expected_output_document_type": (expected_output_document_type or "").strip() or None,
        "linked_property_requirement_id": (linked_property_requirement_id or "").strip() or None,
        "severity": effective_severity or SEVERITY_MEDIUM,
        "status": status,
        "contractor_id": None,
        "created_at": now,
        "updated_at": now,
        "sla_respond_by": effective_respond or default_respond,
        "sla_complete_by": effective_complete or default_complete,
        "completed_at": None,
        "asset_id": asset_id,
        "issue_id": issue_id,
        "risk_signal_id": risk_signal_id,
        "cost_estimate_min": cost_estimate_min,
        "cost_estimate_max": cost_estimate_max,
        "resolution_outcome": None,
        "sla_breach_risk_at": None,
        "sla_breached_at": None,
        "triage_reasoning": triage_reasoning,
        "recommended_contractor_type": recommended_contractor_type,
        "contractor_notes": None,
        "completion_notes": None,
        "evidence_keys": [],
        "requires_client_assignment_confirmation": source != SOURCE_ADMIN,
        "assignment_routing_state": ASSIGNMENT_ROUTING_UNASSIGNED,
        "recommended_contractor_id": None,
        "recommendation_reason_summary": None,
        "recommended_at": None,
        "recommendation_id": None,
        "client_confirmation_deadline_at": None,
        "confirmation_reminder_sent_at": None,
        "confirmation_escalated_at": None,
        "routing_decline_note": None,
        "routing_pending_admin": False,
        "routing_invalidation_reason": None,
    }
    if created_from:
        doc["created_from"] = (created_from or "").strip()
    if triggering_rule:
        doc["triggering_rule"] = (triggering_rule or "").strip()
    if operational_root_key:
        doc["operational_root_key"] = (operational_root_key or "").strip()
    await db.work_orders.insert_one(doc)
    doc.pop("_id", None)
    return doc


def _apply_sla_state_query(q: dict, sla_state: Optional[str]) -> None:
    """Add SLA state filter to query. sla_state: 'breached' | 'near_breach' | 'on_track'."""
    if not sla_state:
        return
    s = sla_state.strip().lower()
    if s == "breached":
        q["sla_breached_at"] = {"$exists": True, "$ne": None}
    elif s == "near_breach":
        q["sla_breach_risk_at"] = {"$exists": True, "$ne": None}
        q["$or"] = [
            {"sla_breached_at": None},
            {"sla_breached_at": {"$exists": False}},
        ]
    elif s == "on_track":
        q["$and"] = [
            {"$or": [{"sla_breached_at": None}, {"sla_breached_at": {"$exists": False}}]},
            {"$or": [{"sla_breach_risk_at": None}, {"sla_breach_risk_at": {"$exists": False}}]},
        ]


async def list_work_orders(
    client_id: Optional[str] = None,
    property_id: Optional[str] = None,
    status: Optional[str] = None,
    contractor_id: Optional[str] = None,
    asset_id: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    sla_state: Optional[str] = None,
    work_order_kind: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
) -> Dict[str, Any]:
    """List work orders with optional filters."""
    db = database.get_db()
    q = {}
    if client_id is not None:
        q["client_id"] = client_id
    if property_id is not None:
        q["property_id"] = property_id
    if status is not None:
        q["status"] = status.strip().upper()
    if contractor_id is not None:
        q["contractor_id"] = contractor_id
    if asset_id is not None:
        q["asset_id"] = asset_id
    if from_date or to_date:
        q.setdefault("created_at", {})
        if from_date:
            q["created_at"]["$gte"] = (
                from_date + "T00:00:00.000Z" if "T" not in from_date else from_date
            )
        if to_date:
            q["created_at"]["$lte"] = (
                to_date + "T23:59:59.999Z" if "T" not in to_date else to_date
            )
    _apply_sla_state_query(q, sla_state)
    if work_order_kind is not None and str(work_order_kind).strip():
        wk = str(work_order_kind).strip().upper()
        if wk in (WORK_ORDER_KIND_MAINTENANCE, WORK_ORDER_KIND_COMPLIANCE):
            q["work_order_kind"] = wk
    cursor = db.work_orders.find(q).sort("created_at", -1).skip(skip).limit(limit)
    items = await cursor.to_list(limit)
    for d in items:
        d.pop("_id", None)
    total = await db.work_orders.count_documents(q)
    return {"work_orders": items, "total": total, "skip": skip, "limit": limit}


async def get_work_order(work_order_id: str) -> Optional[Dict[str, Any]]:
    """Get a single work order by id."""
    db = database.get_db()
    doc = await db.work_orders.find_one({"work_order_id": work_order_id})
    if doc:
        doc.pop("_id", None)
    return doc


async def update_work_order(
    work_order_id: str,
    status: Optional[str] = None,
    contractor_id: Optional[str] = None,
    resolution_outcome: Optional[str] = None,
    cost_estimate_min: Optional[float] = None,
    cost_estimate_max: Optional[float] = None,
    assigned_by: Optional[str] = None,
    contractor_notes: Optional[str] = None,
    completion_notes: Optional[str] = None,
    evidence_keys_append: Optional[List[str]] = None,
    accepted_at: Optional[str] = None,
    *,
    allow_direct_contractor_assignment: bool = False,
    assignment_profile: str = "standard",
) -> Optional[Dict[str, Any]]:
    """Update work order status, contractor, resolution outcome, notes, evidence. When contractor_id is set, records assignment and sets assigned_at. accepted_at set when contractor accepts (for response/completion metrics)."""
    db = database.get_db()
    prev_snapshot = await db.work_orders.find_one(
        {"work_order_id": work_order_id},
        {"_id": 0, "status": 1, "client_id": 1, "property_id": 1, "requires_client_assignment_confirmation": 1},
    )
    prev_status = (prev_snapshot or {}).get("status")
    if contractor_id is not None and prev_snapshot:
        wo_client = prev_snapshot.get("client_id")
        if not wo_client:
            raise ValueError("Work order has no client context; cannot assign a contractor")
        req_confirm = prev_snapshot.get("requires_client_assignment_confirmation", True)
        if req_confirm and not allow_direct_contractor_assignment:
            raise ValueError(
                "This work order requires client confirmation before a contractor can be assigned. "
                "Use the client portal contractor-routing actions, or assign from admin with elevated access."
            )
        from services import contractor_service

        await contractor_service.validate_contractor_for_work_order_assignment(
            contractor_id,
            str(wo_client).strip(),
            work_order_id,
            assignment_profile=assignment_profile,
        )
    now = datetime.now(timezone.utc).isoformat()
    set_fields = {"updated_at": now}
    if contractor_notes is not None:
        set_fields["contractor_notes"] = contractor_notes
    if completion_notes is not None:
        set_fields["completion_notes"] = completion_notes
    if status is not None:
        status = status.strip().upper()
        if status in ALL_STATUSES:
            set_fields["status"] = status
            if status == STATUS_COMPLETED:
                set_fields["completed_at"] = now
    if accepted_at is not None:
        set_fields["accepted_at"] = accepted_at
    if contractor_id is not None:
        set_fields["contractor_id"] = contractor_id
        set_fields["assigned_at"] = now
        set_fields["assignment_routing_state"] = ASSIGNMENT_ROUTING_ASSIGNED
        set_fields["recommended_contractor_id"] = None
        set_fields["recommendation_reason_summary"] = None
        set_fields["recommended_at"] = None
        set_fields["recommendation_id"] = None
        set_fields["client_confirmation_deadline_at"] = None
        set_fields["confirmation_reminder_sent_at"] = None
        set_fields["confirmation_escalated_at"] = None
        set_fields["routing_decline_note"] = None
        set_fields["routing_pending_admin"] = False
        if status is None:
            existing = await db.work_orders.find_one({"work_order_id": work_order_id}, {"status": 1})
            if existing and existing.get("status") == STATUS_OPEN:
                set_fields["status"] = STATUS_ASSIGNED
    if resolution_outcome is not None:
        set_fields["resolution_outcome"] = resolution_outcome
    if cost_estimate_min is not None:
        set_fields["cost_estimate_min"] = cost_estimate_min
    if cost_estimate_max is not None:
        set_fields["cost_estimate_max"] = cost_estimate_max
    update_doc = {"$set": set_fields}
    if evidence_keys_append:
        update_doc["$addToSet"] = {"evidence_keys": {"$each": evidence_keys_append}}
    result = await db.work_orders.find_one_and_update(
        {"work_order_id": work_order_id},
        update_doc,
        return_document=True,
    )
    if result:
        result.pop("_id", None)
        new_status = result.get("status")
        if status is not None and str(status).strip().upper() in (STATUS_CANCELLED, STATUS_COMPLETED):
            try:
                from services.work_order_contractor_routing_service import invalidate_pending_routing_for_work_order

                await invalidate_pending_routing_for_work_order(work_order_id, reason=str(status).strip().upper())
            except Exception as inv_e:
                logger.warning("Contractor routing invalidate on work order close failed: %s", inv_e)
        if (
            status is not None
            and prev_status
            and new_status
            and str(prev_status).upper() != str(new_status).upper()
            and result.get("client_id")
        ):
            try:
                from services.webhook_service import fire_work_order_status_changed

                await fire_work_order_status_changed(
                    client_id=result["client_id"],
                    work_order_id=work_order_id,
                    property_id=result.get("property_id"),
                    old_status=str(prev_status).upper(),
                    new_status=str(new_status).upper(),
                    completed_at=result.get("completed_at") if str(new_status).upper() == STATUS_COMPLETED else None,
                )
            except Exception as wh_e:
                logger.warning("Work order status webhook failed (non-fatal): %s", wh_e)
        if contractor_id is not None:
            try:
                await db.contractor_assignments.insert_one({
                    "work_order_id": work_order_id,
                    "contractor_id": contractor_id,
                    "assigned_at": now,
                    "assigned_by": assigned_by,
                    "assignment_profile": assignment_profile,
                })
            except Exception as e:
                logger.warning("Failed to record contractor assignment: %s", e)
            job_link = ""
            due_date = ""
            try:
                from utils.public_app_url import get_frontend_base_url
                from models import AuditAction
                from utils.audit import create_audit_log
                raw_token = generate_secure_token()
                token_hash = hash_token(raw_token)
                expires_at = (datetime.now(timezone.utc) + timedelta(days=90)).isoformat()
                await db.contractor_job_tokens.insert_one({
                    "token_hash": token_hash,
                    "work_order_id": work_order_id,
                    "contractor_id": contractor_id,
                    "created_at": now,
                    "expires_at": expires_at,
                    "revoked_at": None,
                })
                base_url = get_frontend_base_url().rstrip("/")
                job_link = f"{base_url}/job?token={raw_token}"
                due_date_raw = result.get("sla_complete_by")
                if due_date_raw:
                    try:
                        dt = due_date_raw if isinstance(due_date_raw, datetime) else datetime.fromisoformat(str(due_date_raw).replace("Z", "+00:00"))
                        due_date = dt.strftime("%d %b %Y") if hasattr(dt, "strftime") else str(due_date_raw)
                    except Exception:
                        due_date = str(due_date_raw)
                await create_audit_log(
                    action=AuditAction.CONTRACTOR_ASSIGNED_TO_WORK_ORDER,
                    actor_id=assigned_by,
                    client_id=result.get("client_id"),
                    resource_type="work_order",
                    resource_id=work_order_id,
                    metadata={"contractor_id": contractor_id, "job_token_created": True},
                )
            except Exception as e:
                logger.warning("Failed to create job token or audit for assignment: %s", e)
            try:
                contractor = await db.contractors.find_one(
                    {"contractor_id": contractor_id},
                    {"_id": 0, "email": 1},
                )
                to_email = (contractor or {}).get("email") if contractor else None
                if to_email and str(to_email).strip():
                    property_address = ""
                    if result.get("property_id") and result.get("client_id"):
                        prop = await db.properties.find_one(
                            {"property_id": result["property_id"], "client_id": result["client_id"]},
                            {"_id": 0, "address_line_1": 1, "city": 1, "postcode": 1},
                        )
                        if prop:
                            parts = [prop.get("address_line_1"), prop.get("city"), prop.get("postcode")]
                            property_address = ", ".join(p for p in parts if p) or "Property"
                    desc = (result.get("description") or "Work order")[:200]
                    due_date_str = due_date if due_date else "See job link"
                    job_link_final = job_link if job_link else "See portal"
                    wo_kind_mail = (result.get("work_order_kind") or WORK_ORDER_KIND_MAINTENANCE).strip().upper()
                    if wo_kind_mail == WORK_ORDER_KIND_COMPLIANCE:
                        subj = "Compliance work order assignment"
                        body = (
                            f"You have been assigned to a compliance execution work order (inspection/renewal/certification): "
                            f"{work_order_id}. Description: {desc}. Property: {property_address or 'See portal'}. "
                            f"Due: {due_date_str}. View and respond (no login required): {job_link_final}. "
                            f"This assignment is for compliance evidence work, not ad-hoc maintenance repair unless stated. "
                            f"Payment responsibility: Pleerity coordinates work orders and invoice approval but does not process "
                            f"contractor payments; follow up with the client for payment."
                        )
                    else:
                        subj = "Maintenance work order assignment"
                        body = (
                            f"You have been assigned to a maintenance repair work order: {work_order_id}. Description: {desc}. "
                            f"Property: {property_address or 'See portal'}. Due: {due_date_str}. "
                            f"View and respond (no login required): {job_link_final}. "
                            f"Payment responsibility: Pleerity coordinates work orders and invoice approval but does not process "
                            f"contractor payments. Payment responsibility lies with the client; please follow up with the client for payment."
                        )
                    from services.notification_orchestrator import notification_orchestrator
                    await notification_orchestrator.send(
                        template_key="CONTRACTOR_ASSIGNED",
                        client_id=result.get("client_id"),
                        context={
                            "recipient": str(to_email).strip(),
                            "subject": subj,
                            "body": body,
                            "job_link": job_link_final,
                            "due_date": due_date_str,
                        },
                        idempotency_key=f"contractor_assign_{work_order_id}_{contractor_id}",
                        event_type="CONTRACTOR_ASSIGNED",
                    )
                    try:
                        from models import AuditAction
                        from utils.audit import create_audit_log

                        await create_audit_log(
                            action=AuditAction.WORK_ORDER_CONTRACTOR_ASSIGNMENT_EMAIL_SENT,
                            actor_id=assigned_by,
                            client_id=result.get("client_id"),
                            resource_type="work_order",
                            resource_id=work_order_id,
                            metadata={"contractor_id": contractor_id, "recipient": str(to_email).strip()},
                        )
                    except Exception as aud_e:
                        logger.warning("Audit assignment email sent failed: %s", aud_e)
            except Exception as e:
                logger.warning("Failed to send contractor assignment notification: %s", e)
        if status == STATUS_COMPLETED and result.get("client_id") and result.get("property_id"):
            try:
                from services.predictive_maintenance_service import record_maintenance_event

                wo_kind_done = (result.get("work_order_kind") or WORK_ORDER_KIND_MAINTENANCE).strip().upper()
                evt = "inspection" if wo_kind_done == WORK_ORDER_KIND_COMPLIANCE else "repair"
                await record_maintenance_event(
                    client_id=result["client_id"],
                    property_id=result["property_id"],
                    event_type=evt,
                    asset_id=result.get("asset_id"),
                    notes=f"Work order {work_order_id} completed ({wo_kind_done}): {result.get('description', '')[:200]}",
                )
            except Exception as e:
                logger.warning("Failed to record maintenance event for completed work order: %s", e)
            if result.get("asset_id"):
                try:
                    from services.property_assets_service import add_asset_event, ASSET_EVENT_REPAIR_COMPLETED
                    await add_asset_event(
                        asset_id=result["asset_id"],
                        property_id=result["property_id"],
                        client_id=result["client_id"],
                        event_type=ASSET_EVENT_REPAIR_COMPLETED,
                        description=(result.get("description") or "Work completed")[:200],
                        source="work_order",
                        related_work_order_id=work_order_id,
                    )
                except Exception as e:
                    logger.warning("Failed to record asset event for completed work order: %s", e)
            if result.get("contractor_id"):
                try:
                    await _update_contractor_performance_on_completion(db, result)
                except Exception as e:
                    logger.warning("Failed to update contractor performance for completed work order: %s", e)
        if status == STATUS_VERIFIED and result.get("issue_id"):
            try:
                await db.maintenance_issues.update_one(
                    {"issue_id": result["issue_id"]},
                    {"$set": {"status": "closed", "updated_at": now}},
                )
                logger.info("Closed linked issue %s when work order %s set to VERIFIED", result["issue_id"], work_order_id)
            except Exception as e:
                logger.warning("Failed to close linked issue when work order verified: %s", e)
        if status == STATUS_COMPLETED:
            try:
                from services.compliance_outcome_engine import apply_action_outcome, EVENT_WORK_ORDER_COMPLETED

                wo_kind_out = (result.get("work_order_kind") or WORK_ORDER_KIND_MAINTENANCE).strip().upper()
                req_for_outcome = None
                if wo_kind_out == WORK_ORDER_KIND_COMPLIANCE:
                    req_for_outcome = (result.get("requirement_code") or "").strip() or None
                result["outcome"] = await apply_action_outcome(
                    {
                        "event_type": EVENT_WORK_ORDER_COMPLETED,
                        "client_id": result.get("client_id"),
                        "property_id": result.get("property_id"),
                        "asset_id": result.get("asset_id"),
                        "requirement_type": req_for_outcome,
                        "timestamp": result.get("completed_at") or now,
                        "source_id": work_order_id,
                        "dedupe_key": f"{EVENT_WORK_ORDER_COMPLETED}:{work_order_id}",
                        "actor_id": assigned_by,
                        "actor_role": "SYSTEM",
                        "metadata": {
                            "work_order_id": work_order_id,
                            "work_order_kind": wo_kind_out,
                            "requirement_code": req_for_outcome,
                            "execution_context": (
                                "compliance_inspection_or_renewal"
                                if wo_kind_out == WORK_ORDER_KIND_COMPLIANCE
                                else "maintenance_repair"
                            ),
                        },
                    }
                )
            except Exception as outcome_err:
                logger.debug("Action outcome work_order_completed skip: %s", outcome_err)
    return result


async def _update_contractor_performance_on_completion(db, work_order: Dict[str, Any]) -> None:
    """Increment contractor jobs_completed and jobs_on_time when work order is completed. Sync contractor doc (job_count, sla_compliance_rate)."""
    contractor_id = work_order.get("contractor_id")
    client_id = work_order.get("client_id")
    if not contractor_id:
        return
    now = datetime.now(timezone.utc).isoformat()
    completed_at = work_order.get("completed_at")
    sla_complete_by = work_order.get("sla_complete_by")
    on_time = False
    if completed_at and sla_complete_by:
        try:
            c_at = completed_at if isinstance(completed_at, datetime) else datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
            s_at = sla_complete_by if isinstance(sla_complete_by, datetime) else datetime.fromisoformat(sla_complete_by.replace("Z", "+00:00"))
            if getattr(c_at, "tzinfo", None) is None:
                c_at = c_at.replace(tzinfo=timezone.utc)
            if getattr(s_at, "tzinfo", None) is None:
                s_at = s_at.replace(tzinfo=timezone.utc)
            on_time = c_at <= s_at
        except Exception:
            pass
    doc = await db.contractor_performance.find_one({"contractor_id": contractor_id, "client_id": client_id or ""})
    if doc:
        await db.contractor_performance.update_one(
            {"contractor_id": contractor_id, "client_id": client_id or ""},
            {
                "$set": {"updated_at": now, "last_used_at": now},
                "$inc": {"jobs_completed": 1, "jobs_on_time": 1 if on_time else 0},
            },
        )
    else:
        await db.contractor_performance.insert_one({
            "contractor_id": contractor_id,
            "client_id": client_id or "",
            "jobs_completed": 1,
            "jobs_on_time": 1 if on_time else 0,
            "created_at": now,
            "updated_at": now,
            "last_used_at": now,
        })
    cursor = db.contractor_performance.find({"contractor_id": contractor_id}, {"_id": 0, "jobs_completed": 1, "jobs_on_time": 1})
    total_jobs = 0
    total_on_time = 0
    async for row in cursor:
        total_jobs += row.get("jobs_completed") or 0
        total_on_time += row.get("jobs_on_time") or 0
    rate = round(total_on_time / total_jobs, 4) if total_jobs else None
    await db.contractors.update_one(
        {"contractor_id": contractor_id},
        {"$set": {"job_count": total_jobs, "sla_compliance_rate": rate, "updated_at": now}},
    )
    try:
        from services.contractor_service import compute_rework_rate
        await compute_rework_rate(contractor_id, client_id or "")
    except Exception as e:
        logger.warning("Failed to compute rework rate for contractor %s: %s", contractor_id, e)
    try:
        from services.contractor_intelligence_service import update_contractor_performance_score
        await update_contractor_performance_score(contractor_id, audit=True)
    except Exception as e:
        logger.warning("Failed to update contractor performance score for %s: %s", contractor_id, e)


def _categorise_severity(description: str) -> str:
    """Simple heuristic: keyword-based severity. Can be replaced by AI later."""
    d = (description or "").lower()
    if any(w in d for w in ["leak", "no heat", "no water", "gas smell", "emergency"]):
        return SEVERITY_URGENT
    if any(w in d for w in ["broken", "not working", "fault"]):
        return SEVERITY_HIGH
    return SEVERITY_MEDIUM
