"""
Invoice creation: admin/manual and work-order-linked.
Invoices flow to the approval workspace (client approves/rejects/needs_info).
Every invoice links to client_id, property_id, contractor_id, work_order_id.
"""
import datetime as _dt_std
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
import os
import uuid
import logging

from auth import generate_secure_token, hash_token

from pymongo import ReturnDocument

from database import database
from models import AuditAction
from utils.audit import create_audit_log

logger = logging.getLogger(__name__)

STATUS_PENDING = "pending"
BENCHMARK_NONE = "none"
BENCHMARK_BELOW = "below"
BENCHMARK_WITHIN = "within"
BENCHMARK_ABOVE = "above"
SOURCE_ADMIN = "admin"
SOURCE_CLIENT = "client"
SOURCE_CONTRACTOR = "contractor"

# Align with approval_service invoice statuses
_INV_PENDING = "pending"
_INV_NEEDS_INFO = "needs_info"
_INV_REJECTED = "rejected"
_INV_APPROVED = "approved"
_INV_PAID = "paid"
_INV_DISPUTED = "disputed"
_INV_DRAFT = "draft"


def _invoice_state_rank(inv: Dict[str, Any]) -> int:
    s = (inv.get("status") or "").lower()
    return {
        _INV_PAID: 6,
        _INV_APPROVED: 5,
        _INV_PENDING: 4,
        _INV_DISPUTED: 3,
        _INV_NEEDS_INFO: 2,
        _INV_REJECTED: 1,
        _INV_DRAFT: 0,
    }.get(s, 0)


def _assert_work_order_eligible_for_invoicing(wo: Dict[str, Any]) -> None:
    """
    Invoices linked to a work order are only allowed when the job is verified/closed,
    or completed with completion proof rules satisfied (same as contractor completion gate).
    """
    from services import compliance_workflow_service as cws
    from services import maintenance_service as ms
    from services.work_order_pricing_service import assert_invoice_submission_allowed

    st = (wo.get("status") or "").strip().upper()
    if st in (ms.STATUS_VERIFIED, ms.STATUS_CLOSED):
        assert_invoice_submission_allowed(wo)
        return
    if st != ms.STATUS_COMPLETED:
        raise ValueError("Invoices can only be created when the work order is completed with proof or verified.")
    if cws.contractor_completion_proof_required(wo) and not cws.contractor_has_completion_proof(wo):
        raise ValueError("Upload completion proof for this job before creating or resubmitting an invoice.")
    assert_invoice_submission_allowed(wo)


def _contractor_job_token_ttl_days() -> int:
    raw = (os.getenv("CONTRACTOR_JOB_TOKEN_TTL_DAYS") or "").strip()
    if not raw:
        return 30
    try:
        n = int(raw)
        return max(1, min(n, 365))
    except ValueError:
        return 30


def _invoice_eligibility_timestamp_iso(raw: Any) -> str:
    """Normalize timestamps for idempotency keys (uses stdlib datetime module; safe if `datetime` is patched in tests)."""
    if raw is None:
        return _dt_std.datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    if isinstance(raw, _dt_std.datetime):
        return raw.astimezone(timezone.utc).replace(microsecond=0).isoformat()
    s = str(raw).strip()
    if not s:
        return _dt_std.datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    try:
        dt = _dt_std.datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat()
    except ValueError:
        return s


async def maybe_send_contractor_invoice_ready_notification(
    wo: Dict[str, Any],
    *,
    eligibility_timestamp_iso: str,
) -> None:
    """
    Notify assigned contractor when a work order becomes eligible for first invoice submission
    (orchestrator + message_logs). Idempotent per work_order_id + eligibility timestamp.
    """
    try:
        _assert_work_order_eligible_for_invoicing(wo)
    except ValueError:
        return

    from services.work_order_pricing_service import pricing_workflow_applies, quote_is_approved_for_api

    if pricing_workflow_applies(wo) and not quote_is_approved_for_api(wo):
        return

    cid = (wo.get("client_id") or "").strip()
    wid = (wo.get("work_order_id") or "").strip()
    ctr = (wo.get("contractor_id") or "").strip()
    if not cid or not wid or not ctr:
        return

    db = database.get_db()
    existing = await db.invoices.find_one(
        {"work_order_id": wid, "contractor_id": ctr},
        {"_id": 1},
    )
    if existing:
        return

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

    from services.work_order_pricing_constants import DEFAULT_PRICE_CURRENCY

    currency = (wo.get("price_currency") or DEFAULT_PRICE_CURRENCY).strip() or DEFAULT_PRICE_CURRENCY
    approved_price = wo.get("quoted_price")

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
        logger.warning("Contractor invoice-ready email: job token failed (non-fatal): %s", exc)

    ts_norm = _invoice_eligibility_timestamp_iso(eligibility_timestamp_iso)
    idem = f"contractor_invoice_ready:{wid}:{ts_norm}"

    from services.notification_orchestrator import notification_orchestrator

    await notification_orchestrator.send(
        template_key="CONTRACTOR_INVOICE_READY",
        client_id=cid,
        context={
            "recipient": str(to_email).strip(),
            "subject": "This job is ready for invoicing",
            "contractor_name": contractor_disp or "",
            "property_address": property_address,
            "job_title": (wo.get("description") or "Work order")[:200],
            "work_order_id": wid,
            "approved_price": approved_price,
            "price_currency": currency,
            "secure_job_link": job_link_final,
        },
        idempotency_key=idem,
        event_type="CONTRACTOR_INVOICE_READY",
    )


async def maybe_send_client_invoice_review_required_notification(
    invoice: Dict[str, Any],
    work_order: Dict[str, Any],
    *,
    submitted_at: datetime,
) -> None:
    """Notify client when a contractor invoice is submitted (pending / awaiting approval)."""
    iid = (invoice.get("invoice_id") or "").strip()
    cid = (invoice.get("client_id") or "").strip()
    wid = (work_order.get("work_order_id") or "").strip()
    ctr = (invoice.get("contractor_id") or "").strip()
    if not iid or not cid or not wid:
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
    prop_id = work_order.get("property_id") or invoice.get("property_id")
    if prop_id:
        prop = await db.properties.find_one(
            {"property_id": prop_id, "client_id": cid},
            {"_id": 0, "address_line_1": 1, "city": 1, "postcode": 1},
        )
        if prop:
            parts = [prop.get("address_line_1"), prop.get("city"), prop.get("postcode")]
            property_address = ", ".join(p for p in parts if p) or property_address
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
    from services.work_order_pricing_constants import DEFAULT_PRICE_CURRENCY
    from services.work_order_pricing_service import pricing_workflow_applies, quote_is_approved_for_api

    base = get_frontend_base_url().rstrip("/")
    client_job_link = f"{base}/operations/jobs/{wid}"
    invoice_review_link = f"{base}/operations/approvals?invoice_id={iid}"

    currency = (invoice.get("currency") or DEFAULT_PRICE_CURRENCY).strip() or DEFAULT_PRICE_CURRENCY
    amt = invoice.get("submitted_amount")
    has_agreed_price = pricing_workflow_applies(work_order) and quote_is_approved_for_api(work_order)

    ts_norm = _invoice_eligibility_timestamp_iso(submitted_at)
    idem = f"client_invoice_review:{iid}:{ts_norm}"

    from services.notification_orchestrator import notification_orchestrator

    await notification_orchestrator.send(
        template_key="CLIENT_INVOICE_REVIEW_REQUIRED",
        client_id=cid,
        context={
            "recipient": to_email,
            "subject": "An invoice is ready for your review",
            "client_name": client_name or "",
            "property_address": property_address,
            "job_title": (work_order.get("description") or "Work order")[:200],
            "work_order_id": wid,
            "invoice_id": iid,
            "invoice_number": (str(invoice.get("invoice_number") or "").strip() or None),
            "invoice_amount": amt,
            "price_currency": currency,
            "contractor_name": contractor_name,
            "client_job_link": client_job_link,
            "secure_client_job_link": invoice_review_link,
            "portal_link": invoice_review_link,
            "invoice_review_link": invoice_review_link,
            "has_agreed_price": has_agreed_price,
            "customer_reference": client.get("customer_reference"),
        },
        idempotency_key=idem,
        event_type="CLIENT_INVOICE_REVIEW_REQUIRED",
    )


def work_order_cost_benchmark(wo: Dict[str, Any]) -> Tuple[Optional[float], Optional[float]]:
    """Estimate band from work order for invoice benchmark_fit."""
    mn = wo.get("cost_estimate_min")
    mx = wo.get("cost_estimate_max")
    mn_f: Optional[float] = None
    mx_f: Optional[float] = None
    try:
        if mn is not None:
            mn_f = float(mn)
    except (TypeError, ValueError):
        mn_f = None
    try:
        if mx is not None:
            mx_f = float(mx)
    except (TypeError, ValueError):
        mx_f = None
    return mn_f, mx_f


async def contractor_best_invoice_for_work_order(contractor_id: str, work_order_id: str) -> Optional[Dict[str, Any]]:
    """Highest-priority invoice for this contractor + work order (paid > approved > pending > …)."""
    db = database.get_db()
    cursor = db.invoices.find(
        {"contractor_id": contractor_id, "work_order_id": work_order_id},
        {"_id": 0},
    )
    items = await cursor.to_list(length=100)
    best: Optional[Dict[str, Any]] = None
    for inv in items:
        if not best or _invoice_state_rank(inv) > _invoice_state_rank(best):
            best = inv
    return best


def enrich_invoice_for_contractor_portal(inv: Dict[str, Any]) -> None:
    """Mutates invoice dict: ISO date strings + contractor-facing state labels for API JSON."""
    for key in ("submitted_at", "paid_at", "reviewed_at"):
        v = inv.get(key)
        if v and hasattr(v, "isoformat"):
            inv[key] = v.isoformat()
    raw = (inv.get("status") or "").strip().lower()
    if raw == _INV_PENDING:
        inv["contractor_invoice_state"] = "SUBMITTED"
    elif raw == _INV_NEEDS_INFO:
        inv["contractor_invoice_state"] = "UNDER_REVIEW"
    elif raw == _INV_APPROVED:
        inv["contractor_invoice_state"] = "APPROVED"
    elif raw == _INV_REJECTED:
        inv["contractor_invoice_state"] = "REJECTED"
    elif raw == _INV_PAID:
        inv["contractor_invoice_state"] = "PAID"
    elif raw == _INV_DISPUTED:
        inv["contractor_invoice_state"] = "DISPUTED"
    elif raw == _INV_DRAFT:
        inv["contractor_invoice_state"] = "DRAFT"
    else:
        inv["contractor_invoice_state"] = (raw or "unknown").upper()
    inv["contractor_correction_required"] = raw in (_INV_NEEDS_INFO, _INV_REJECTED)
    # UI-facing status (aligned with product spec); persisted status remains lowercase.
    inv["invoice_status_canonical"] = {
        _INV_DRAFT: "DRAFT",
        _INV_PENDING: "SUBMITTED",
        _INV_NEEDS_INFO: "SUBMITTED",
        _INV_REJECTED: "REJECTED",
        _INV_DISPUTED: "DISPUTED",
        _INV_APPROVED: "APPROVED",
        _INV_PAID: "PAID",
    }.get(raw, (raw or "UNKNOWN").upper())


async def contractor_resubmit_invoice(
    invoice_id: str,
    contractor_id: str,
    *,
    reference: Optional[str] = None,
    contractor_reference: Optional[str] = None,
    description: Optional[str] = None,
    submitted_amount: float,
    currency: str = "GBP",
    attachment_storage_key: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Contractor updates and re-queues an invoice after needs_info or rejected.
    Resets status to pending and clears reviewer fields.
    """
    db = database.get_db()
    inv = await db.invoices.find_one({"invoice_id": invoice_id, "contractor_id": contractor_id})
    if not inv:
        return None
    st = (inv.get("status") or "").strip().lower()
    if st not in (_INV_NEEDS_INFO, _INV_REJECTED):
        raise ValueError("Invoice cannot be resubmitted in its current state")

    wo = await db.work_orders.find_one(
        {"work_order_id": inv.get("work_order_id"), "client_id": inv.get("client_id")},
        {"_id": 0},
    )
    if not wo:
        raise ValueError("Work order not found for this invoice")
    _assert_work_order_eligible_for_invoicing(wo)
    from services.work_order_pricing_service import assert_invoice_amount_within_approved_quote

    assert_invoice_amount_within_approved_quote(wo, float(submitted_amount))

    now = datetime.now(timezone.utc)
    benchmark_min = inv.get("benchmark_min")
    benchmark_max = inv.get("benchmark_max")
    benchmark_fit = _compute_benchmark_fit(submitted_amount, benchmark_min, benchmark_max)
    cref = ((contractor_reference if contractor_reference is not None else reference) or "").strip() or None

    set_doc: Dict[str, Any] = {
        "status": _INV_PENDING,
        "contractor_reference": cref,
        "reference": cref or inv.get("invoice_number") or inv.get("reference") or f"INV-{invoice_id[:8]}",
        "description": (description or "").strip() or None,
        "submitted_amount": submitted_amount,
        "currency": (currency or "GBP").strip(),
        "benchmark_fit": benchmark_fit,
        "submitted_at": now,
        "reviewed_at": None,
        "reviewer_id": None,
    }
    if attachment_storage_key is not None:
        set_doc["attachment_storage_key"] = attachment_storage_key

    await db.invoices.update_one({"invoice_id": invoice_id}, {"$set": set_doc})
    out = await db.invoices.find_one({"invoice_id": invoice_id}, {"_id": 0})
    if not out:
        return None
    if out.get("submitted_at") and hasattr(out["submitted_at"], "isoformat"):
        out["submitted_at"] = out["submitted_at"].isoformat()
    if out.get("paid_at") and hasattr(out["paid_at"], "isoformat"):
        out["paid_at"] = out["paid_at"].isoformat()
    if out.get("reviewed_at") and hasattr(out["reviewed_at"], "isoformat"):
        out["reviewed_at"] = out["reviewed_at"].isoformat()

    enrich_invoice_for_contractor_portal(out)

    await create_audit_log(
        action=AuditAction.CONTRACTOR_INVOICE_RESUBMITTED,
        actor_id=contractor_id,
        client_id=out.get("client_id"),
        resource_type="invoice",
        resource_id=invoice_id,
        metadata={
            "work_order_id": out.get("work_order_id"),
            "reference": out.get("reference"),
            "submitted_amount": submitted_amount,
        },
    )
    logger.info("Invoice resubmitted invoice_id=%s contractor_id=%s", invoice_id, contractor_id)
    try:
        await maybe_send_client_invoice_review_required_notification(out, wo, submitted_at=now)
    except Exception as em:
        logger.warning("Client invoice review email (resubmit) failed (non-fatal): %s", em)
    return out


async def allocate_public_invoice_number() -> str:
    """Monotonic display number per UTC year: PLE-INV-YYYY-######."""
    db = database.get_db()
    year = datetime.now(timezone.utc).year
    doc = await db.counters.find_one_and_update(
        {"_id": f"ple_contractor_invoice_{year}"},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    seq = int((doc or {}).get("seq") or 1)
    return f"PLE-INV-{year}-{seq:06d}"


async def contractor_submit_or_resubmit_for_work_order(
    work_order: Dict[str, Any],
    contractor_id: str,
    *,
    reference: Optional[str] = None,
    contractor_reference: Optional[str] = None,
    description: Optional[str] = None,
    submitted_amount: float,
    currency: str = "GBP",
    attachment_storage_key: Optional[str] = None,
) -> Tuple[Dict[str, Any], str]:
    """
    Portal/job-link: create a new invoice or resubmit after needs_info/rejected.
    Returns (invoice_document, "created" | "resubmitted").
    Raises ValueError on validation or business-rule errors.
    """
    client_id = work_order.get("client_id")
    property_id = work_order.get("property_id")
    work_order_id = work_order.get("work_order_id")
    if not client_id or not property_id or not work_order_id:
        raise ValueError("Work order missing property or client")
    cref = ((contractor_reference if contractor_reference is not None else reference) or "").strip()
    if submitted_amount is None or float(submitted_amount) <= 0:
        raise ValueError("Invoice amount must be greater than zero")
    amt = float(submitted_amount)

    bench_min, bench_max = work_order_cost_benchmark(work_order)
    best = await contractor_best_invoice_for_work_order(contractor_id, work_order_id)
    if best:
        st = (best.get("status") or "").lower()
        if st in (_INV_PENDING, _INV_APPROVED, _INV_PAID):
            raise ValueError("An invoice for this job is already with the client or settled.")
        if st in (_INV_NEEDS_INFO, _INV_REJECTED):
            iid = best.get("invoice_id")
            if not iid:
                raise ValueError("Invalid invoice record")
            out = await contractor_resubmit_invoice(
                iid,
                contractor_id,
                reference=cref or None,
                contractor_reference=cref or None,
                description=description,
                submitted_amount=amt,
                currency=currency,
                attachment_storage_key=attachment_storage_key,
            )
            if not out:
                raise ValueError("Invoice resubmit failed")
            return out, "resubmitted"

    inv_no = await allocate_public_invoice_number()
    doc = await create_invoice(
        client_id=client_id,
        property_id=property_id,
        contractor_id=contractor_id,
        work_order_id=work_order_id,
        reference=cref,
        contractor_reference=cref or None,
        invoice_number=inv_no,
        description=description,
        submitted_amount=amt,
        currency=currency,
        benchmark_min=bench_min,
        benchmark_max=bench_max,
        attachment_storage_key=attachment_storage_key,
        source=SOURCE_CONTRACTOR,
        created_by_id=contractor_id,
    )
    enrich_invoice_for_contractor_portal(doc)
    return doc, "created"


def _compute_benchmark_fit(
    submitted_amount: Optional[float],
    benchmark_min: Optional[float],
    benchmark_max: Optional[float],
) -> str:
    if submitted_amount is None or (benchmark_min is None and benchmark_max is None):
        return BENCHMARK_NONE
    if benchmark_min is not None and submitted_amount < benchmark_min:
        return BENCHMARK_BELOW
    if benchmark_max is not None and submitted_amount > benchmark_max:
        return BENCHMARK_ABOVE
    return BENCHMARK_WITHIN


async def create_invoice(
    client_id: str,
    property_id: str,
    contractor_id: str,
    work_order_id: str,
    reference: Optional[str] = None,
    description: Optional[str] = None,
    submitted_amount: Optional[float] = None,
    currency: str = "GBP",
    benchmark_min: Optional[float] = None,
    benchmark_max: Optional[float] = None,
    attachment_storage_key: Optional[str] = None,
    source: str = SOURCE_ADMIN,
    created_by_id: Optional[str] = None,
    *,
    contractor_reference: Optional[str] = None,
    invoice_number: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create an invoice linked to work order, contractor, property, client.
    Validates that work order and contractor exist and belong to client.
    Sets status=pending so it appears in Approvals. Audit INVOICE_CREATED.
    """
    db = database.get_db()

    # Validate work order belongs to client (full doc for pricing / proof rules)
    wo = await db.work_orders.find_one(
        {"work_order_id": work_order_id, "client_id": client_id},
        {"_id": 0},
    )
    if not wo:
        raise ValueError("Work order not found or does not belong to this client")

    if wo.get("property_id") != property_id:
        raise ValueError("Work order property_id does not match")

    # Validate contractor exists (and optionally is visible to client)
    contractor = await db.contractors.find_one(
        {"contractor_id": contractor_id},
        {"_id": 0, "contractor_id": 1, "client_id": 1},
    )
    if not contractor:
        raise ValueError("Contractor not found")

    # Property must belong to client
    prop = await db.properties.find_one(
        {"property_id": property_id, "client_id": client_id},
        {"_id": 1},
    )
    if not prop:
        raise ValueError("Property not found or does not belong to this client")

    _assert_work_order_eligible_for_invoicing(wo)

    from services.work_order_pricing_service import assert_invoice_amount_within_approved_quote

    if submitted_amount is not None:
        assert_invoice_amount_within_approved_quote(wo, float(submitted_amount))

    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    invoice_id = str(uuid.uuid4())
    inv_no = (invoice_number or "").strip() or None
    if source == SOURCE_CONTRACTOR and not inv_no:
        inv_no = await allocate_public_invoice_number()
    cref = ((contractor_reference if contractor_reference is not None else None) or "").strip() or None
    if cref is None and reference:
        cref = (reference or "").strip() or None
    ref_line = (reference or "").strip() or cref or inv_no

    benchmark_fit = _compute_benchmark_fit(submitted_amount, benchmark_min, benchmark_max)

    doc = {
        "invoice_id": invoice_id,
        "client_id": client_id,
        "property_id": property_id,
        "contractor_id": contractor_id,
        "work_order_id": work_order_id,
        "invoice_number": inv_no,
        "contractor_reference": cref,
        "reference": ref_line or f"INV-{invoice_id[:8]}",
        "description": (description or "").strip() or None,
        "submitted_amount": submitted_amount,
        "currency": (currency or "GBP").strip(),
        "benchmark_min": benchmark_min,
        "benchmark_max": benchmark_max,
        "benchmark_fit": benchmark_fit,
        "status": STATUS_PENDING,
        "submitted_at": now,
        "attachment_storage_key": attachment_storage_key,
        "source": source,
        "created_by_id": created_by_id,
        "reviewed_at": None,
        "reviewer_id": None,
    }
    await db.invoices.insert_one(doc)
    doc.pop("_id", None)
    if doc.get("submitted_at") and hasattr(doc["submitted_at"], "isoformat"):
        doc["submitted_at"] = doc["submitted_at"].isoformat()

    await create_audit_log(
        action=AuditAction.INVOICE_CREATED,
        actor_id=created_by_id or "system",
        client_id=client_id,
        resource_type="invoice",
        resource_id=invoice_id,
        metadata={
            "work_order_id": work_order_id,
            "contractor_id": contractor_id,
            "property_id": property_id,
            "reference": doc["reference"],
            "submitted_amount": submitted_amount,
            "source": source,
        },
    )
    logger.info("Invoice created invoice_id=%s client_id=%s work_order_id=%s", invoice_id, client_id, work_order_id)
    if source == SOURCE_CONTRACTOR:
        try:
            await maybe_send_client_invoice_review_required_notification(doc, wo, submitted_at=now)
        except Exception as em:
            logger.warning("Client invoice review email failed (non-fatal): %s", em)
    return doc
