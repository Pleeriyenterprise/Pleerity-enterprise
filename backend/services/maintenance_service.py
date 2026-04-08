"""
Maintenance workflows: work orders (tenant report / client / admin).
Create, list, update, assign contractor. SLA fields optional.
Gated by MAINTENANCE_WORKFLOWS feature flag for client/tenant.
"""
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
import hashlib
import os
import uuid
from database import database
import logging
from auth import generate_secure_token, hash_token
from services.work_order_assignment_constants import (
    ASSIGNMENT_ROUTING_ASSIGNED,
    ASSIGNMENT_ROUTING_CONTRACTOR_DECLINED,
    ASSIGNMENT_ROUTING_UNASSIGNED,
)
from services.work_order_schedule_constants import SCHEDULE_STATUS_COMPLETED
from services.work_order_execution_constants import (
    COMPLIANCE_BOOKING_AWAITING_CONTRACTOR_RESPONSE,
    COMPLIANCE_BOOKING_BOOKING_REQUESTED,
    COMPLIANCE_BOOKING_IN_PROGRESS,
    COMPLIANCE_BOOKING_OPERATIONALLY_COMPLETE,
    COMPLIANCE_BOOKING_SCHEDULED,
    COMPLIANCE_PROOF_NOT_SUBMITTED,
    COMPLIANCE_PROOF_SUBMITTED,
    WORK_ORDER_CATEGORY_COMPLIANCE,
    WORK_ORDER_KIND_COMPLIANCE,
    WORK_ORDER_KIND_MAINTENANCE,
)
from services.work_order_pricing_constants import (
    PRICING_MODE_MAINTENANCE_INSPECTION_REQUIRED,
    PRICE_STATUS_AWAITING_QUOTE,
)

logger = logging.getLogger(__name__)

# Secure job-link token lifetime (days). Stored hashed; tied to work_order_id + contractor_id.
# Default 30 balances tighter exposure with typical windows; use CONTRACTOR_JOB_TOKEN_TTL_DAYS=90 for long-cycle work.
def _contractor_job_token_ttl_days() -> int:
    raw = (os.getenv("CONTRACTOR_JOB_TOKEN_TTL_DAYS") or "").strip()
    if not raw:
        return 30
    try:
        n = int(raw)
        return max(1, min(n, 365))
    except ValueError:
        return 30


def _proof_type_hint_for_contractor_email(wo: Dict[str, Any]) -> str:
    """Short label for the kind of evidence expected (email copy)."""
    kind = (wo.get("work_order_kind") or "").strip().upper() or WORK_ORDER_KIND_MAINTENANCE
    if kind == WORK_ORDER_KIND_COMPLIANCE:
        return "certificate"
    if (wo.get("expected_output_document_type") or "").strip():
        return "certificate or specified completion document"
    return "photos, report, or invoice evidence"


async def _maybe_send_contractor_proof_required_email(
    wo: Dict[str, Any],
    *,
    proof_required_state: str,
) -> None:
    """Notify contractor when a job enters a state that requires completion proof (orchestrator + message_logs)."""
    from services import compliance_workflow_service as cws

    if not cws.contractor_completion_proof_required(wo) or cws.contractor_has_completion_proof(wo):
        return
    cid = (wo.get("client_id") or "").strip()
    wid = (wo.get("work_order_id") or "").strip()
    ctr = (wo.get("contractor_id") or "").strip()
    if not cid or not wid or not ctr:
        return
    db = database.get_db()
    contractor = await db.contractors.find_one(
        {"contractor_id": ctr},
        {"_id": 0, "email": 1, "name": 1, "company_name": 1},
    )
    to_email = (contractor or {}).get("email") if contractor else None
    if not to_email or not str(to_email).strip():
        return
    contractor_disp = (
        (str((contractor or {}).get("name") or "").strip())
        or (str((contractor or {}).get("company_name") or "").strip())
        or None
    )
    property_address = "Property"
    prop_id = wo.get("property_id")
    if prop_id:
        prop = await db.properties.find_one(
            {"property_id": prop_id, "client_id": cid},
            {"_id": 0, "address_line_1": 1, "city": 1, "postcode": 1},
        )
        if prop:
            parts = [prop.get("address_line_1"), prop.get("city"), prop.get("postcode")]
            property_address = ", ".join(p for p in parts if p) or property_address
    job_link_final = "See portal"
    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        from utils.public_app_url import get_frontend_base_url

        raw_token = generate_secure_token()
        token_hash = hash_token(raw_token)
        expires_at = (datetime.now(timezone.utc) + timedelta(days=_contractor_job_token_ttl_days())).isoformat()
        await db.contractor_job_tokens.insert_one(
            {
                "token_hash": token_hash,
                "work_order_id": wid,
                "contractor_id": ctr,
                "created_at": now_iso,
                "expires_at": expires_at,
                "revoked_at": None,
            }
        )
        base_url = get_frontend_base_url().rstrip("/")
        job_link_final = f"{base_url}/job?token={raw_token}"
    except Exception as exc:
        logger.warning("Contractor proof-required email: job token failed (non-fatal): %s", exc)

    kind = (wo.get("work_order_kind") or "").strip().upper()
    is_compliance = kind == WORK_ORDER_KIND_COMPLIANCE
    hint = _proof_type_hint_for_contractor_email(wo)
    state_key = (proof_required_state or "").strip().upper()
    from services.notification_orchestrator import notification_orchestrator

    await notification_orchestrator.send(
        template_key="CONTRACTOR_PROOF_REQUIRED",
        client_id=cid,
        context={
            "recipient": str(to_email).strip(),
            "subject": "Completion proof required for this job",
            "contractor_name": contractor_disp or "",
            "property_address": property_address,
            "job_title": (wo.get("description") or "Work order")[:200],
            "work_order_id": wid,
            "secure_job_link": job_link_final,
            "proof_type_hint": hint,
            "completion_proof_required": True,
            "completion_proof_satisfied": False,
            "is_compliance": is_compliance,
        },
        idempotency_key=f"contractor_proof_required:{wid}:{state_key}",
        event_type="CONTRACTOR_PROOF_REQUIRED",
    )


def _client_proof_upload_event_id(new_keys: List[str]) -> str:
    """Stable id for this upload batch (dedupe orchestrator / message_logs)."""
    clean = sorted({str(k).strip() for k in new_keys if k and str(k).strip()})
    if not clean:
        return ""
    return hashlib.sha256("|".join(clean).encode("utf-8")).hexdigest()[:32]


async def _maybe_send_client_proof_uploaded_email(
    wo: Dict[str, Any],
    *,
    proof_event_id: str,
) -> None:
    """Notify client contact when new evidence keys are appended to a work order (orchestrator + message_logs)."""
    cid = (wo.get("client_id") or "").strip()
    wid = (wo.get("work_order_id") or "").strip()
    if not cid or not wid or not proof_event_id:
        return
    db = database.get_db()
    client = await db.clients.find_one(
        {"client_id": cid},
        {"_id": 0, "contact_email": 1, "email": 1, "full_name": 1, "contact_name": 1, "customer_reference": 1},
    )
    if not client:
        return
    to_email = (client.get("contact_email") or client.get("email") or "").strip()
    if not to_email:
        return
    property_address = "Property"
    prop_id = wo.get("property_id")
    if prop_id:
        prop = await db.properties.find_one(
            {"property_id": prop_id, "client_id": cid},
            {"_id": 0, "address_line_1": 1, "city": 1, "postcode": 1},
        )
        if prop:
            parts = [prop.get("address_line_1"), prop.get("city"), prop.get("postcode")]
            property_address = ", ".join(p for p in parts if p) or property_address
    ctr = (wo.get("contractor_id") or "").strip()
    contractor_name = "Contractor"
    if ctr:
        contractor_row = await db.contractors.find_one(
            {"contractor_id": ctr},
            {"_id": 0, "name": 1, "company_name": 1},
        )
        if contractor_row:
            contractor_name = (
                (str(contractor_row.get("name") or "").strip())
                or (str(contractor_row.get("company_name") or "").strip())
                or "Contractor"
            )
    client_name = (
        (str(client.get("full_name") or "").strip())
        or (str(client.get("contact_name") or "").strip())
        or None
    )
    from utils.public_app_url import get_frontend_base_url

    base = get_frontend_base_url().rstrip("/")
    client_job_link = f"{base}/operations/jobs/{wid}"

    kind = (wo.get("work_order_kind") or "").strip().upper()
    is_compliance = kind == WORK_ORDER_KIND_COMPLIANCE
    compliance_outcome_hint = ""
    if is_compliance:
        compliance_outcome_hint = (
            "This evidence will be used as part of compliance review. "
            "Formal compliance status is not final until validation is complete."
        )
    elif (wo.get("expected_output_document_type") or "").strip():
        compliance_outcome_hint = "Please confirm the upload matches what you expected for this job."

    from services.notification_orchestrator import notification_orchestrator

    await notification_orchestrator.send(
        template_key="CLIENT_PROOF_UPLOADED",
        client_id=cid,
        context={
            "recipient": to_email,
            "subject": "Evidence uploaded for your job",
            "client_name": client_name or "",
            "property_address": property_address,
            "job_title": (wo.get("description") or "Work order")[:200],
            "work_order_id": wid,
            "contractor_name": contractor_name,
            "client_job_link": client_job_link,
            "secure_client_job_link": client_job_link,
            "portal_link": client_job_link,
            "is_compliance": is_compliance,
            "compliance_outcome_hint": compliance_outcome_hint,
            "customer_reference": client.get("customer_reference"),
        },
        idempotency_key=f"client_proof_uploaded:{wid}:{proof_event_id}",
        event_type="CLIENT_PROOF_UPLOADED",
    )


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

# Optional operational holds (persisted on work_orders.operational_exception)
OPERATIONAL_EXCEPTION_NO_ACCESS = "NO_ACCESS"
OPERATIONAL_EXCEPTION_RESCHEDULE_REQUIRED = "RESCHEDULE_REQUIRED"
OPERATIONAL_EXCEPTION_FOLLOW_UP_REQUIRED = "FOLLOW_UP_REQUIRED"
ALLOWED_OPERATIONAL_EXCEPTIONS = frozenset(
    {
        OPERATIONAL_EXCEPTION_NO_ACCESS,
        OPERATIONAL_EXCEPTION_RESCHEDULE_REQUIRED,
        OPERATIONAL_EXCEPTION_FOLLOW_UP_REQUIRED,
    }
)

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
    jurisdiction: Optional[str] = None,
    inspection_required: bool = False,
) -> Dict[str, Any]:
    """Create a work order. source: tenant_request | client | admin.
    Optional: asset_id, issue_id, cost estimates, initial_status (default OPEN), SLA overrides.
    If use_triage is True and severity/sla are not provided, runs triage and applies result (stores reasoning).
    Compliance execution work orders (work_order_kind=COMPLIANCE) skip maintenance triage and use explicit metadata.
    """
    db = database.get_db()
    now_dt = datetime.now(timezone.utc)
    now = now_dt.isoformat()
    work_order_id = str(uuid.uuid4())
    kind = (work_order_kind or WORK_ORDER_KIND_MAINTENANCE).strip().upper()
    if kind not in (WORK_ORDER_KIND_MAINTENANCE, WORK_ORDER_KIND_COMPLIANCE):
        kind = WORK_ORDER_KIND_MAINTENANCE
    if kind == WORK_ORDER_KIND_COMPLIANCE:
        rc = (requirement_code or "").strip()
        lpr = (linked_property_requirement_id or "").strip()
        if not rc:
            raise ValueError("COMPLIANCE work orders require requirement_code")
        if not lpr:
            raise ValueError("COMPLIANCE work orders require linked_property_requirement_id")

    jurisdiction_for_wo = (jurisdiction or "").strip() or None
    if not jurisdiction_for_wo and linked_property_requirement_id:
        r = await db.requirements.find_one(
            {"requirement_id": linked_property_requirement_id.strip()},
            {"_id": 0, "jurisdiction": 1},
        )
        jurisdiction_for_wo = (r or {}).get("jurisdiction")
    if not jurisdiction_for_wo:
        from services.compliance_rules_registry import portfolio_jurisdiction_label

        p = await db.properties.find_one(
            {"property_id": property_id, "client_id": client_id},
            {"_id": 0, "jurisdiction": 1},
        )
        c = await db.clients.find_one({"client_id": client_id}, {"_id": 0, "default_jurisdiction": 1})
        jurisdiction_for_wo = portfolio_jurisdiction_label(p or {}, c or {})

    sla_respond_hours = 24
    sla_complete_days = 5
    compliance_sla_meta: Dict[str, Any] = {}
    if kind == WORK_ORDER_KIND_COMPLIANCE:
        from services.compliance_rules_registry import compliance_execution_sla_policy

        pol = compliance_execution_sla_policy(jurisdiction_for_wo, requirement_code)
        sla_respond_hours = pol["respond_hours"]
        sla_complete_days = pol["complete_days"]
        compliance_sla_meta = {
            "compliance_sla_complete_days": pol["complete_days"],
            "compliance_sla_respond_hours": pol["respond_hours"],
            "compliance_sla_risk_days_before_complete": pol["risk_days_before_complete"],
            "compliance_sla_risk_hours_before_respond": pol["risk_hours_before_respond"],
        }

    default_respond = (now_dt + timedelta(hours=sla_respond_hours)).isoformat()
    default_complete = (now_dt + timedelta(days=sla_complete_days)).isoformat()
    status = (initial_status or STATUS_OPEN).strip().upper() if initial_status else STATUS_OPEN
    if status not in ALL_STATUSES:
        status = STATUS_OPEN

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
        "scheduled_at": None,
        "scheduled_timezone": None,
        "schedule_status": None,
        "scheduled_by": None,
        "schedule_notes": None,
        "schedule_reschedule_reason": None,
        "last_schedule_update_at": None,
        "reminder_sent": False,
    }
    if kind == WORK_ORDER_KIND_COMPLIANCE:
        doc["compliance_booking_status"] = COMPLIANCE_BOOKING_BOOKING_REQUESTED
        doc["compliance_proof_status"] = COMPLIANCE_PROOF_NOT_SUBMITTED
        doc.update(compliance_sla_meta)
    if created_from:
        doc["created_from"] = (created_from or "").strip()
    if triggering_rule:
        doc["triggering_rule"] = (triggering_rule or "").strip()
    if operational_root_key:
        doc["operational_root_key"] = (operational_root_key or "").strip()

    if jurisdiction_for_wo:
        doc["jurisdiction"] = jurisdiction_for_wo

    from services.work_order_pricing_service import default_pricing_fields_for_create

    doc.update(
        default_pricing_fields_for_create(
            work_order_kind=kind,
            inspection_required=bool(inspection_required) if kind == WORK_ORDER_KIND_MAINTENANCE else False,
        )
    )

    await db.work_orders.insert_one(doc)
    doc.pop("_id", None)
    from services.compliance_workflow_service import client_job_sla_policy

    doc["sla_policy"] = client_job_sla_policy(doc)
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
    from services.compliance_workflow_service import client_job_sla_policy

    for d in items:
        d.pop("_id", None)
        d["sla_policy"] = client_job_sla_policy(d)
    total = await db.work_orders.count_documents(q)
    return {"work_orders": items, "total": total, "skip": skip, "limit": limit}


async def get_work_order(work_order_id: str) -> Optional[Dict[str, Any]]:
    """Get a single work order by id."""
    db = database.get_db()
    doc = await db.work_orders.find_one({"work_order_id": work_order_id})
    if doc:
        doc.pop("_id", None)
        from services.compliance_workflow_service import client_job_sla_policy

        doc["sla_policy"] = client_job_sla_policy(doc)
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
    scheduled_at: Optional[str] = None,
    operational_exception: Optional[str] = None,
    *,
    allow_direct_contractor_assignment: bool = False,
    assignment_profile: str = "standard",
) -> Optional[Dict[str, Any]]:
    """Update work order status, contractor, resolution outcome, notes, evidence. When contractor_id is set, records assignment and sets assigned_at. accepted_at set when contractor accepts (for response/completion metrics)."""
    db = database.get_db()
    prev_snapshot = await db.work_orders.find_one(
        {"work_order_id": work_order_id},
        {
            "_id": 0,
            "status": 1,
            "client_id": 1,
            "property_id": 1,
            "requires_client_assignment_confirmation": 1,
            "work_order_kind": 1,
            "evidence_keys": 1,
            "requirement_code": 1,
            "linked_property_requirement_id": 1,
            "expected_output_document_type": 1,
            "scheduled_at": 1,
            "schedule_status": 1,
            "scheduled_timezone": 1,
        },
    )
    prev_status = (prev_snapshot or {}).get("status")
    prev_kind = ((prev_snapshot or {}).get("work_order_kind") or WORK_ORDER_KIND_MAINTENANCE).strip().upper()
    merged_evidence = list((prev_snapshot or {}).get("evidence_keys") or [])
    if evidence_keys_append:
        for k in evidence_keys_append:
            if k and k not in merged_evidence:
                merged_evidence.append(k)
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
    if operational_exception is not None:
        raw_oe = (operational_exception or "").strip().upper()
        if raw_oe == "" or raw_oe in ("NONE", "CLEAR", "NULL"):
            set_fields["operational_exception"] = None
        elif raw_oe in ALLOWED_OPERATIONAL_EXCEPTIONS:
            set_fields["operational_exception"] = raw_oe
        else:
            raise ValueError(
                f"operational_exception must be one of: {', '.join(sorted(ALLOWED_OPERATIONAL_EXCEPTIONS))} or empty to clear"
            )
    if contractor_notes is not None:
        set_fields["contractor_notes"] = contractor_notes
    if completion_notes is not None:
        set_fields["completion_notes"] = completion_notes
    if status is not None:
        status = status.strip().upper()
        if status in ALL_STATUSES:
            if status == STATUS_IN_PROGRESS:
                wo_full = await db.work_orders.find_one({"work_order_id": work_order_id}, {"_id": 0})
                if wo_full:
                    wm = dict(wo_full)
                    wm["evidence_keys"] = merged_evidence
                    from services.work_order_pricing_service import assert_may_transition_to_in_progress

                    assert_may_transition_to_in_progress(wm)
            if status == STATUS_COMPLETED and prev_snapshot:
                try:
                    from services.work_order_schedule_service import assert_completion_schedule_policy

                    assert_completion_schedule_policy(dict(prev_snapshot))
                except ValueError as e:
                    raise ValueError(str(e)) from e
                from services import compliance_workflow_service as _cws

                wo_for_proof = dict(prev_snapshot)
                wo_for_proof["evidence_keys"] = merged_evidence
                if _cws.contractor_completion_proof_required(wo_for_proof) and not _cws.contractor_has_completion_proof(
                    wo_for_proof
                ):
                    raise ValueError(
                        "Completion proof is required for this job. Upload evidence before marking complete."
                    )
                wo_full = await db.work_orders.find_one({"work_order_id": work_order_id}, {"_id": 0})
                if wo_full:
                    wm = dict(wo_full)
                    wm["evidence_keys"] = merged_evidence
                    from services.work_order_pricing_service import assert_may_transition_to_completed

                    assert_may_transition_to_completed(wm)
            set_fields["status"] = status
            if status == STATUS_COMPLETED:
                set_fields["completed_at"] = now
                if prev_snapshot and (
                    (prev_snapshot.get("scheduled_at") or "").strip()
                    or (prev_snapshot.get("schedule_status") or "").strip()
                ):
                    set_fields["schedule_status"] = SCHEDULE_STATUS_COMPLETED
                    set_fields["last_schedule_update_at"] = now
    if accepted_at is not None:
        set_fields["accepted_at"] = accepted_at
    if scheduled_at is not None:
        set_fields["scheduled_at"] = (scheduled_at or "").strip() or None
        if prev_kind == WORK_ORDER_KIND_COMPLIANCE and (scheduled_at or "").strip():
            set_fields["compliance_booking_status"] = COMPLIANCE_BOOKING_SCHEDULED
    if prev_kind == WORK_ORDER_KIND_COMPLIANCE and status is not None and status in ALL_STATUSES:
        if status == STATUS_IN_PROGRESS:
            set_fields["compliance_booking_status"] = COMPLIANCE_BOOKING_IN_PROGRESS
        elif status == STATUS_SCHEDULED:
            set_fields["compliance_booking_status"] = COMPLIANCE_BOOKING_SCHEDULED
        elif status == STATUS_COMPLETED:
            set_fields["compliance_booking_status"] = COMPLIANCE_BOOKING_OPERATIONALLY_COMPLETE
            set_fields["compliance_proof_status"] = (
                COMPLIANCE_PROOF_SUBMITTED if merged_evidence else COMPLIANCE_PROOF_NOT_SUBMITTED
            )
    if prev_kind == WORK_ORDER_KIND_COMPLIANCE and evidence_keys_append and any(evidence_keys_append):
        set_fields["compliance_proof_status"] = COMPLIANCE_PROOF_SUBMITTED
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
        if prev_kind == WORK_ORDER_KIND_COMPLIANCE:
            # Assigned and client-notify path will run after this update; awaiting schedule / accept / progress.
            set_fields["compliance_booking_status"] = COMPLIANCE_BOOKING_AWAITING_CONTRACTOR_RESPONSE
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
        if (
            status is not None
            and new_status
            and str(new_status).upper() in (STATUS_IN_PROGRESS, STATUS_AWAITING_PARTS)
            and str(prev_status or "").upper() != str(new_status).upper()
            and result.get("contractor_id")
            and result.get("client_id")
        ):
            try:
                await _maybe_send_contractor_proof_required_email(
                    dict(result),
                    proof_required_state=str(new_status).upper(),
                )
            except Exception as pr_e:
                logger.warning("Contractor proof-required email failed: %s", pr_e)
        if (
            status is not None
            and new_status
            and result.get("contractor_id")
            and result.get("client_id")
        ):
            ns = str(new_status).upper()
            ps = str(prev_status or "").upper()
            if ns in (STATUS_COMPLETED, STATUS_VERIFIED, STATUS_CLOSED) and ps != ns:
                skip_invoice_ready = ns in (STATUS_VERIFIED, STATUS_CLOSED) and ps == STATUS_COMPLETED
                if not skip_invoice_ready:
                    try:
                        from services.invoice_service import maybe_send_contractor_invoice_ready_notification

                        el_ts = result.get("completed_at") if ns == STATUS_COMPLETED else now
                        await maybe_send_contractor_invoice_ready_notification(
                            dict(result),
                            eligibility_timestamp_iso=str(el_ts or now),
                        )
                    except Exception as ir_e:
                        logger.warning("Contractor invoice-ready email failed: %s", ir_e)
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
                expires_at = (datetime.now(timezone.utc) + timedelta(days=_contractor_job_token_ttl_days())).isoformat()
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
                    {"_id": 0, "email": 1, "name": 1, "company_name": 1},
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
                    price_status_upper = (str(result.get("price_status") or "")).strip().upper()
                    from services.notification_orchestrator import notification_orchestrator

                    if price_status_upper == PRICE_STATUS_AWAITING_QUOTE:
                        job_kind_label = "COMPLIANCE" if wo_kind_mail == WORK_ORDER_KIND_COMPLIANCE else "MAINTENANCE"
                        contractor_disp = (
                            (str((contractor or {}).get("name") or "").strip())
                            or (str((contractor or {}).get("company_name") or "").strip())
                            or None
                        )
                        jurisdiction_val = (str(result.get("jurisdiction") or "")).strip()
                        await notification_orchestrator.send(
                            template_key="CONTRACTOR_JOB_ASSIGNMENT_QUOTE_REQUIRED",
                            client_id=result.get("client_id"),
                            context={
                                "recipient": str(to_email).strip(),
                                "subject": "You've been assigned a job — submit your quote",
                                "contractor_name": contractor_disp or "",
                                "property_address": property_address or "See portal",
                                "job_title": desc,
                                "work_order_id": work_order_id,
                                "secure_job_link": job_link_final,
                                "due_date": due_date_str if due_date else "",
                                "sla_summary": "",
                                "job_kind": job_kind_label,
                                "jurisdiction": jurisdiction_val,
                                "is_compliance": wo_kind_mail == WORK_ORDER_KIND_COMPLIANCE,
                            },
                            idempotency_key=f"contractor_quote_required:{work_order_id}:{contractor_id}",
                            event_type="CONTRACTOR_JOB_ASSIGNMENT_QUOTE_REQUIRED",
                        )
                    elif wo_kind_mail == WORK_ORDER_KIND_COMPLIANCE:
                        subj = "Compliance work order assignment"
                        body = (
                            f"You have been assigned to a compliance execution work order (inspection/renewal/certification): "
                            f"{work_order_id}. Description: {desc}. Property: {property_address or 'See portal'}. "
                            f"Due: {due_date_str}. Use your secure access link to view and respond: {job_link_final}. "
                            f"This assignment is for compliance evidence work, not ad-hoc maintenance repair unless stated. "
                            f"Payment responsibility: Pleerity coordinates work orders and invoice approval but does not process "
                            f"contractor payments; follow up with the client for payment."
                        )
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
                    else:
                        subj = "Maintenance work order assignment"
                        inspect_first = (
                            (result.get("pricing_mode") or "").strip().upper()
                            == PRICING_MODE_MAINTENANCE_INSPECTION_REQUIRED
                        )
                        inspect_note = (
                            " This job is inspection-first: you can attend to inspect before a final repair price is agreed, "
                            "but do not carry out billable repair work until the client has approved your quote in writing in the platform. "
                            if inspect_first
                            else ""
                        )
                        body = (
                            f"You have been assigned to a maintenance repair work order: {work_order_id}. Description: {desc}. "
                            f"Property: {property_address or 'See portal'}. Due: {due_date_str}. "
                            f"Use your secure access link to view and respond: {job_link_final}.{inspect_note} "
                            f"Payment responsibility: Pleerity coordinates work orders and invoice approval but does not process "
                            f"contractor payments. Payment responsibility lies with the client; please follow up with the client for payment."
                        )
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
                            metadata={
                                "contractor_id": contractor_id,
                                "recipient": str(to_email).strip(),
                                "template_key": "CONTRACTOR_JOB_ASSIGNMENT_QUOTE_REQUIRED"
                                if price_status_upper == PRICE_STATUS_AWAITING_QUOTE
                                else "CONTRACTOR_ASSIGNED",
                            },
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
                ev_keys = list(result.get("evidence_keys") or [])
                closure_ready = wo_kind_out == WORK_ORDER_KIND_COMPLIANCE and bool(ev_keys)
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
                            "compliance_proof_submitted": bool(ev_keys),
                            "resolve_linked_compliance_risks": closure_ready,
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
        if evidence_keys_append and prev_kind == WORK_ORDER_KIND_COMPLIANCE and result.get("client_id"):
            try:
                from services.compliance_outcome_engine import (
                    apply_action_outcome,
                    EVENT_CERTIFICATE_UPLOADED,
                )

                req_code = (result.get("requirement_code") or "").strip() or None
                await apply_action_outcome(
                    {
                        "event_type": EVENT_CERTIFICATE_UPLOADED,
                        "client_id": result["client_id"],
                        "property_id": result.get("property_id"),
                        "asset_id": result.get("asset_id"),
                        "requirement_type": req_code,
                        "timestamp": now,
                        "source_id": work_order_id,
                        "dedupe_key": f"{EVENT_CERTIFICATE_UPLOADED}:{work_order_id}:{len(result.get('evidence_keys') or [])}",
                        "actor_id": assigned_by or result.get("contractor_id"),
                        "actor_role": "CONTRACTOR",
                        "metadata": {
                            "work_order_id": work_order_id,
                            "linked_property_requirement_id": result.get("linked_property_requirement_id"),
                            "expected_output_document_type": result.get("expected_output_document_type"),
                        },
                    }
                )
            except Exception as cert_e:
                logger.debug("Compliance certificate_uploaded outcome skip: %s", cert_e)
        if evidence_keys_append and result and result.get("client_id"):
            prev_keys = set((prev_snapshot or {}).get("evidence_keys") or [])
            newly_added = [k for k in (evidence_keys_append or []) if k and str(k).strip() and k not in prev_keys]
            if newly_added:
                try:
                    peid = _client_proof_upload_event_id(newly_added)
                    if peid:
                        await _maybe_send_client_proof_uploaded_email(dict(result), proof_event_id=peid)
                except Exception as cpu_e:
                    logger.warning("Client proof-uploaded email failed: %s", cpu_e)
    return result


async def contractor_decline_assignment(work_order_id: str, contractor_id: str) -> Optional[Dict[str, Any]]:
    """Unassign contractor: OPEN, routing CONTRACTOR_DECLINED, revoke job tokens, optional routing invalidate + status webhook."""
    db = database.get_db()
    cid = (contractor_id or "").strip()
    filt = {"work_order_id": work_order_id, "contractor_id": cid}
    wo = await db.work_orders.find_one(filt)
    if not wo:
        return None
    prev_status = wo.get("status")
    now = datetime.now(timezone.utc).isoformat()
    result = await db.work_orders.find_one_and_update(
        filt,
        {
            "$set": {
                "contractor_id": None,
                "status": STATUS_OPEN,
                "updated_at": now,
                "assignment_routing_state": ASSIGNMENT_ROUTING_CONTRACTOR_DECLINED,
                "accepted_at": None,
            }
        },
        return_document=True,
    )
    if not result:
        return None
    result.pop("_id", None)
    await db.contractor_job_tokens.update_many(
        {"work_order_id": work_order_id, "contractor_id": cid, "revoked_at": None},
        {"$set": {"revoked_at": now, "revoked_reason": "contractor_declined_assignment"}},
    )
    try:
        from services.work_order_contractor_routing_service import invalidate_pending_routing_for_work_order

        await invalidate_pending_routing_for_work_order(work_order_id, "CONTRACTOR_DECLINED")
    except Exception as inv_e:
        logger.warning("Routing invalidate on contractor decline failed: %s", inv_e)
    new_status = result.get("status")
    if (
        prev_status
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
                completed_at=None,
            )
        except Exception as wh_e:
            logger.warning("Work order status webhook on contractor decline failed (non-fatal): %s", wh_e)
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
