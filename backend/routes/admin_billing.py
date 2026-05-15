"""Admin Billing & Subscription Management Routes.

Enterprise-grade billing management for Compliance Vault Pro.

Endpoints:
- GET /api/admin/billing/clients/search - Search clients by email, CRN, client_id, postcode
- GET /api/admin/billing/clients/{client_id} - Get full billing snapshot
- POST /api/admin/billing/clients/{client_id}/sync - Force sync from Stripe
- POST /api/admin/billing/clients/{client_id}/portal-link - Create Stripe billing portal link
- POST /api/admin/billing/clients/{client_id}/change-plan - Change subscription plan (upgrade/downgrade)
- POST /api/admin/billing/clients/{client_id}/resend-setup - Resend password setup email
- POST /api/admin/billing/clients/{client_id}/force-provision - Re-run provisioning
- POST /api/admin/billing/clients/{client_id}/message - Send message to client
- POST /api/admin/billing/jobs/subscription-lifecycle - Run subscription lifecycle batch (same runner as scheduled job)
- POST /api/admin/billing/jobs/renewal-reminders - Alias of subscription lifecycle batch (backward compatible)
- POST /api/admin/billing/clients/{client_id}/receipts/subscription/{ref}/regenerate - Rebuild itemised CVP checkout PDF from Stripe (keeps invoice number)
- POST /api/admin/billing/clients/{client_id}/reconcile-payment-ledger - Hydrate paid-invoice payment ledger (+ optional last_payment mirror) from webhook pointers / Stripe

NON-NEGOTIABLE RULES:
1. Stripe is the billing authority. App is the entitlement authority.
2. No admin action may "pretend" a subscription is active.
3. Every admin billing action must be audit-logged.
4. Feature gating is server-side first.
"""
import stripe
import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Request, status, Depends, Query, Body
from fastapi.responses import Response
from pydantic import BaseModel, Field
from database import database
from middleware import admin_route_guard
from models import AuditAction, EmailTemplateAlias, UserRole, PasswordToken
from utils.audit import create_audit_log
from services.plan_registry import plan_registry, PlanCode, EntitlementStatus
from services.billing_period_utils import (
    period_end_from_stripe_subscription_dict,
    period_start_from_stripe_subscription_dict,
)
from services.billing_stripe_sync_service import stripe_subscription_to_dict
from services.billing_stripe_sync_service import persist_subscription_billing_from_stripe
from services.subscription_lifecycle_service import sync_subscription_lifecycle
from services.billing_reconciliation_service import mark_billing_reconciliation_needed
from services.provisioning import provisioning_service
from services.stripe_service import StripeService
from services.billing_audit_normalization import normalized_billing_audit_metadata
from services.admin_client_support_search import run_admin_client_support_search
from services.admin_action_governance import ensure_action_reason, normalized_admin_action_metadata
from services.subscription_payment_ledger_service import (
    PAYMENT_EVIDENCE_STRIPE_EVENT_TYPES,
    reconcile_client_subscription_payment_ledger,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/billing", tags=["admin-billing"], dependencies=[Depends(admin_route_guard)])

# Human-readable labels for stored Stripe webhook types (no invented events).
_STRIPE_EVENT_LABELS = {
    "checkout.session.completed": "Checkout completed",
    "checkout.session.expired": "Checkout expired",
    "customer.subscription.created": "Subscription created",
    "customer.subscription.updated": "Subscription updated",
    "customer.subscription.deleted": "Subscription ended",
    "customer.subscription.paused": "Subscription paused",
    "customer.subscription.resumed": "Subscription resumed",
    "invoice.paid": "Invoice paid",
    "invoice.payment_failed": "Invoice payment failed",
    "invoice.payment_action_required": "Payment requires action",
    "invoice.finalized": "Invoice finalized",
    "payment_intent.succeeded": "Payment succeeded",
    "payment_intent.payment_failed": "Payment failed",
}


def _stripe_timeline_summary(event_type: Optional[str]) -> str:
    if not event_type:
        return "Stripe event"
    return _STRIPE_EVENT_LABELS.get(
        event_type,
        event_type.replace(".", " ").replace("_", " ").title(),
    )

# Initialize Stripe
stripe.api_key = os.getenv("STRIPE_API_KEY", "")


# =============================================================================
# Request/Response Models
# =============================================================================

class MessageRequest(BaseModel):
    """Request to send message to client."""
    channels: List[str]  # ["in_app", "email", "sms"]
    template_id: Optional[str] = None
    custom_text: Optional[str] = None
    subject: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class ChangePlanRequest(BaseModel):
    """Request to change a client's subscription plan (admin support flow)."""
    plan_code: str  # PLAN_1_SOLO | PLAN_2_PORTFOLIO | PLAN_3_PRO
    apply_at_period_end: bool = True  # If True, new price applies at next billing; if False, prorate immediately
    reason: str = Field(..., min_length=10, max_length=2000)


class SupportGovernedActionReasonBody(BaseModel):
    reason: str = Field(..., min_length=10, max_length=2000)


class AdminReceiptResendBody(BaseModel):
    """Resend receipt email for a subscription ledger row or paid order."""
    source: str = Field(..., description="subscription | order")
    ref: str = Field(..., description="Invoice number / cs_ session id, or order_id")


class ReconcileSubscriptionPaymentLedgerBody(BaseModel):
    """Hydrate canonical paid-invoice ledger rows from webhook evidence / Stripe Invoice API."""

    from_stripe_events: bool = True
    from_stripe_invoice_api_limit: int = Field(
        default=0,
        ge=0,
        le=100,
        description="Stripe Invoice.list limit for this customer (0 = skip). Low values only — rate-limit safe.",
    )


# =============================================================================
# Search Clients
# =============================================================================

@router.get("/clients/search")
async def search_billing_clients(
    request: Request,
    q: str = "",
    limit: int = 20,
    include_archived: bool = Query(False, description="Include archived/suspended clients (same as /api/admin/search)"),
):
    """
    Search clients for billing management — delegates to canonical admin support search
    (GET /api/admin/search) implementation for consistent behaviour.
    """
    await admin_route_guard(request)
    db = database.get_db()

    if not q or len(q.strip()) < 2:
        return {"clients": [], "total": 0, "query": q, "search_source": "admin_support_search"}

    try:
        rows = await run_admin_client_support_search(
            db,
            search_term=q.strip(),
            limit=limit,
            include_archived=include_archived,
        )
        for client in rows:
            plan_code = client.get("billing_plan", "PLAN_1_SOLO")
            plan_def = plan_registry.get_plan_by_code_string(plan_code)
            client["max_properties"] = plan_def.get("max_properties", 2) if plan_def else 2
        return {
            "clients": rows,
            "total": len(rows),
            "query": q.strip(),
            "search_source": "admin_support_search",
        }

    except Exception as e:
        logger.error(f"Search billing clients error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Search failed",
        )


# =============================================================================
# Get Client Billing Snapshot
# =============================================================================

@router.get("/clients/{client_id}")
async def get_client_billing_snapshot(request: Request, client_id: str):
    """
    Get full billing snapshot for a client.
    
    Includes:
    - Client identifiers
    - Plan and entitlement status
    - Stripe billing details
    - Last sync and webhook info
    - Recent billing events
    """
    admin = await admin_route_guard(request)
    db = database.get_db()
    
    try:
        # Get client
        client = await db.clients.find_one(
            {"client_id": client_id},
            {"_id": 0}
        )
        
        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Client not found"
            )
        
        # Get billing record
        billing = await db.client_billing.find_one(
            {"client_id": client_id},
            {"_id": 0}
        )
        
        # Get portal user (use auth_email field)
        portal_user = await db.portal_users.find_one(
            {"client_id": client_id, "role": "ROLE_CLIENT_ADMIN"},
            {"_id": 0, "portal_user_id": 1, "auth_email": 1, "email": 1, "password_set": 1, "password_status": 1, "created_at": 1}
        )
        
        # Stripe webhook timeline (stored events only; labels are summaries of `type`)
        raw_timeline = await db.stripe_events.find(
            {"related_client_id": client_id}
        ).sort("created", -1).limit(25).to_list(25)

        stripe_timeline: List[Dict[str, Any]] = []
        for ev in raw_timeline:
            created = ev.get("created")
            if hasattr(created, "isoformat"):
                created_iso = created.isoformat()
            else:
                created_iso = str(created) if created else ""
            err = ev.get("error") or ""
            stripe_timeline.append(
                {
                    "event_id": ev.get("event_id"),
                    "type": ev.get("type"),
                    "summary": _stripe_timeline_summary(ev.get("type")),
                    "status": ev.get("status"),
                    "created": created_iso,
                    "error_preview": (err[:240] + "…") if len(err) > 240 else err if ev.get("status") == "FAILED" else None,
                }
            )

        checkout_receipt_count = await db.stripe_checkout_invoices.count_documents({"client_id": client_id})
        renewal_receipt_count = await db.cvp_subscription_renewal_receipts.count_documents({"client_id": client_id})
        subscription_ledger_paid_count = await db.subscription_payment_ledger.count_documents(
            {"client_id": client_id, "status": "paid"}
        )
        stripe_payment_evidence_event_count = await db.stripe_events.count_documents(
            {
                "related_client_id": client_id,
                "status": "PROCESSED",
                "type": {"$in": sorted(PAYMENT_EVIDENCE_STRIPE_EVENT_TYPES)},
            }
        )

        # Get property count
        property_count = await db.properties.count_documents({"client_id": client_id})
        
        # Build plan info
        plan_code = client.get("billing_plan", "PLAN_1_SOLO")
        plan_def = plan_registry.get_plan_by_code_string(plan_code)
        
        # Build snapshot
        snapshot = {
            # Client identifiers (clients collection: full_name, email, customer_reference)
            "client_id": client_id,
            "contact_name": client.get("full_name"),
            "contact_email": client.get("email"),
            "company_name": client.get("company_name"),
            "crn": client.get("customer_reference"),
            
            # Plan info
            "plan_code": plan_code,
            "plan_name": plan_def.get("name") if plan_def else plan_code,
            "max_properties": plan_def.get("max_properties", 2) if plan_def else 2,
            "current_property_count": property_count,
            "over_property_limit": property_count > (plan_def.get("max_properties", 2) if plan_def else 2),
            
            # Entitlement
            "subscription_status": client.get("subscription_status", "PENDING"),
            "entitlement_status": client.get("entitlement_status", "DISABLED"),
            "onboarding_status": client.get("onboarding_status", "PENDING"),
            
            # Stripe fields
            "stripe_customer_id": client.get("stripe_customer_id") or (billing.get("stripe_customer_id") if billing else None),
            "stripe_subscription_id": billing.get("stripe_subscription_id") if billing else None,
            "cancel_at_period_end": billing.get("cancel_at_period_end", False) if billing else False,
            "current_period_start": billing.get("current_period_start") if billing else None,
            "current_period_end": billing.get("current_period_end") if billing else None,
            "onboarding_fee_paid": billing.get("onboarding_fee_paid", False) if billing else False,
            "latest_invoice_id": billing.get("latest_invoice_id") if billing else None,
            "payment_failed_at": billing.get("payment_failed_at") if billing else None,
            
            # Sync info
            "last_synced_at": billing.get("updated_at") if billing else None,
            "billing_record_exists": billing is not None,
            
            # Portal user - include email from auth_email field
            "portal_user": {
                **portal_user,
                "email": portal_user.get("auth_email") or portal_user.get("email")
            } if portal_user else None,
            "password_setup_complete": (portal_user.get("password_set", False) or portal_user.get("password_status") == "SET") if portal_user else False,
            
            # Stripe activity & receipts (for admin UI)
            "stripe_timeline": stripe_timeline,
            "checkout_receipt_ledger_count": checkout_receipt_count,
            "renewal_receipt_ledger_count": renewal_receipt_count,
            "subscription_payment_ledger_paid_count": subscription_ledger_paid_count,
            "stripe_payment_evidence_webhook_count": stripe_payment_evidence_event_count,
            "next_billing_date": billing.get("current_period_end") if billing else None,
            "last_stripe_invoice_id": billing.get("latest_invoice_id") if billing else None,
            
            # Created
            "created_at": client.get("created_at"),
        }

        # Same subscription/lifecycle projection as tenant Billing API (Stripe + client_billing; may refresh period from Stripe)
        stripe_svc = StripeService()
        sub_status = await stripe_svc.get_subscription_status(client_id, client_facing=False)
        snapshot["subscription_lifecycle"] = sub_status
        snapshot["billing_operational_narrative_lines"] = sub_status.get("billing_operational_narrative_lines") or []
        snapshot["billing_sync_visibility_note"] = sub_status.get("billing_sync_visibility_note")
        snapshot["plan_status_display"] = sub_status.get("plan_status_display")
        snapshot["billing_status_display"] = sub_status.get("billing_status_display")
        snapshot["billing_last_synced_at"] = sub_status.get("billing_last_synced_at")
        snapshot["billing_sync_state"] = sub_status.get("billing_sync_state")
        snapshot["retry_state_label"] = (
            "Awaiting retry"
            if (sub_status.get("open_invoice_status") or "").lower() in {"open", "past_due", "unpaid"}
            else "No retry in progress"
        )
        snapshot["next_retry_at_utc"] = sub_status.get("stripe_next_payment_attempt_at")
        snapshot["grace_period_ends_at_utc"] = sub_status.get("grace_period_ends_at")
        _bss = (sub_status.get("billing_sync_state") or "").lower()
        snapshot["stripe_sync_state_label"] = (
            "Up to date"
            if _bss == "ok"
            else "Needs review — data may be incomplete; confirm in Stripe"
        )
        snapshot["stripe_sync_updated_at_utc"] = sub_status.get("billing_last_synced_at")
        snapshot["billing_reconciliation_needed"] = bool((billing or {}).get("billing_reconciliation_needed"))
        snapshot["billing_reconciliation_reason"] = (billing or {}).get("billing_reconciliation_reason")
        snapshot["billing_reconciliation_marked_at"] = (billing or {}).get("billing_reconciliation_marked_at")

        if sub_status.get("has_subscription"):
            cpe_iso = sub_status.get("current_period_end")
            if cpe_iso:
                try:
                    snapshot["next_billing_date"] = datetime.fromisoformat(
                        str(cpe_iso).replace("Z", "+00:00")
                    )
                except (ValueError, TypeError):
                    pass
            pfail_iso = sub_status.get("payment_failed_at")
            if pfail_iso:
                try:
                    snapshot["payment_failed_at"] = datetime.fromisoformat(
                        str(pfail_iso).replace("Z", "+00:00")
                    )
                except (ValueError, TypeError):
                    pass
            else:
                snapshot["payment_failed_at"] = None
            ss = sub_status.get("subscription_status")
            if ss:
                snapshot["stripe_subscription_status"] = ss
            snapshot["canonical_entitlement_state"] = sub_status.get("canonical_entitlement_state")
            snapshot["lifecycle_status_label"] = sub_status.get("lifecycle_status_label")
            snapshot["last_payment_at"] = sub_status.get("last_payment_at")
            snapshot["last_payment_amount_pence"] = sub_status.get("last_payment_amount_pence")
            snapshot["last_payment_status"] = sub_status.get("last_payment_status")
            snapshot["last_payment_stripe_invoice_id"] = sub_status.get("last_payment_stripe_invoice_id")
            snapshot["last_payment_invoice_number"] = sub_status.get("last_payment_invoice_number")
            snapshot["last_payment_currency"] = sub_status.get("last_payment_currency")
            snapshot["last_payment_source_event_id"] = sub_status.get("last_payment_source_event_id")
            snapshot["open_invoice_id"] = sub_status.get("open_invoice_id")
            snapshot["open_invoice_status"] = sub_status.get("open_invoice_status")
            snapshot["stripe_next_payment_attempt_at"] = sub_status.get("stripe_next_payment_attempt_at")
            snapshot["last_invoice_failure_message"] = sub_status.get("last_invoice_failure_message")
            snapshot["stripe_webhook_last_received_at"] = sub_status.get("stripe_webhook_last_received_at")
            snapshot["stripe_webhook_last_event_type"] = sub_status.get("stripe_webhook_last_event_type")
        else:
            snapshot["stripe_subscription_status"] = None

        sub_upper = str((billing or {}).get("subscription_status") or client.get("subscription_status") or "").upper()
        active_like_sub = sub_upper in ("ACTIVE", "TRIALING")
        stripe_ids_ok = bool((billing or {}).get("stripe_subscription_id") and (billing or {}).get("stripe_customer_id"))
        stripe_activity_no_ledger = (
            stripe_payment_evidence_event_count > 0 and subscription_ledger_paid_count == 0
        )
        subscription_active_without_ledger = active_like_sub and stripe_ids_ok and subscription_ledger_paid_count == 0
        snapshot["payment_reconciliation"] = {
            "subscription_payment_ledger_paid_row_count": subscription_ledger_paid_count,
            "stripe_payment_related_webhook_row_count": stripe_payment_evidence_event_count,
            "stripe_evidence_but_no_payment_ledger_rows": stripe_activity_no_ledger,
            "active_subscription_but_no_payment_ledger_rows": subscription_active_without_ledger,
            "action_hint": (
                "Run payment ledger reconciliation (admin) to materialize paid-invoice ledger rows from stored webhook pointers / Stripe invoices."
                if stripe_activity_no_ledger or subscription_active_without_ledger
                else None
            ),
        }

        last_renewal = await db.cvp_subscription_renewal_receipts.find_one(
            {"client_id": client_id},
            sort=[("paid_at", -1)],
        )
        if last_renewal:
            lr: Dict[str, Any] = {
                "stripe_invoice_id": last_renewal.get("stripe_invoice_id") or last_renewal.get("_id"),
                "pleerity_invoice_number": last_renewal.get("invoice_number"),
                "stripe_invoice_number": last_renewal.get("stripe_invoice_number"),
                "amount_total_pence": last_renewal.get("amount_total_pence"),
                "currency": last_renewal.get("currency"),
                "paid_at": last_renewal.get("paid_at"),
                "hosted_invoice_url": last_renewal.get("hosted_invoice_url"),
                "pleerity_pdf_available": bool(last_renewal.get("gridfs_id")),
                "billing_period_start": last_renewal.get("billing_period_start"),
                "billing_period_end": last_renewal.get("billing_period_end"),
                "payment_status": last_renewal.get("payment_status"),
                "billing_reason": last_renewal.get("billing_reason"),
            }
            if sub_status.get("has_subscription"):
                lr["canonical_entitlement_state"] = sub_status.get("canonical_entitlement_state")
            snapshot["last_renewal_receipt"] = lr

        # Per-client attention (rule-based; only flags we can justify from stored fields)
        attention: List[Dict[str, Any]] = []
        es = client.get("entitlement_status")
        if es == "LIMITED":
            attention.append(
                {
                    "code": "entitlement_limited",
                    "severity": "high",
                    "message": "Account access is limited - usually due to payment or compliance state.",
                }
            )
        elif es == "DISABLED":
            attention.append(
                {
                    "code": "entitlement_disabled",
                    "severity": "high",
                    "message": "Account access is disabled - subscription or billing is inactive.",
                }
            )
        ob = client.get("onboarding_status")
        if ob and ob not in ("PROVISIONED", "COMPLETE"):
            attention.append(
                {
                    "code": "onboarding_incomplete",
                    "severity": "medium",
                    "message": f"Onboarding not complete (status: {ob}).",
                }
            )
        if billing and billing.get("payment_failed_at"):
            attention.append(
                {
                    "code": "payment_failed_recorded",
                    "severity": "high",
                    "message": "Payment failure recorded - review payment method and outstanding invoice.",
                }
            )
        pwd_ok = (
            (portal_user.get("password_set", False) or portal_user.get("password_status") == "SET")
            if portal_user
            else True
        )
        if portal_user and ob == "PROVISIONED" and not pwd_ok:
            attention.append(
                {
                    "code": "password_setup_pending",
                    "severity": "medium",
                    "message": "Portal admin has not completed password setup.",
                }
            )
        if billing and billing.get("stripe_subscription_id") and checkout_receipt_count == 0:
            attention.append(
                {
                    "code": "no_subscription_checkout_receipt",
                    "severity": "low",
                    "message": "Subscription on file but no subscription checkout PDF in ledger (legacy or out-of-band Stripe).",
                }
            )

        lc_raw = (sub_status.get("billing_lifecycle_state") or "active").lower()
        if sub_status.get("has_subscription"):
            if lc_raw == "grace_period":
                attention.append(
                    {
                        "code": "billing_lifecycle_grace_period",
                        "severity": "high",
                        "message": "Subscription is in payment retry (grace period). Client should update payment method or pay the open invoice.",
                    }
                )
            elif lc_raw == "limited":
                if not any(x.get("code") == "entitlement_limited" for x in attention):
                    attention.append(
                        {
                            "code": "billing_lifecycle_limited",
                            "severity": "high",
                            "message": "Billing lifecycle is LIMITED — grace period ended; access is restricted until payment succeeds.",
                        }
                    )
            elif lc_raw == "renewing":
                attention.append(
                    {
                        "code": "billing_lifecycle_renewing",
                        "severity": "low",
                        "message": "Current period ends within 7 days — renewal billing is imminent (Stripe is billing authority).",
                    }
                )
            elif lc_raw == "past_due":
                attention.append(
                    {
                        "code": "billing_lifecycle_past_due",
                        "severity": "high",
                        "message": "Stripe subscription is past due; confirm open invoices, payment method, and recent webhooks.",
                    }
                )

        snapshot["billing_attention_items"] = attention
        snapshot["billing_anomaly_flags"] = [i.get("code") for i in attention] if attention else []
        
        return snapshot
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get billing snapshot error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get billing snapshot"
        )


# =============================================================================
# Receipts & Invoices (canonical GridFS + ledger collections)
# =============================================================================

def _parse_admin_date(q: Optional[str]) -> Optional[datetime]:
    if not q or not str(q).strip():
        return None
    s = str(q).strip()
    try:
        if len(s) == 10 and s[4] == "-" and s[7] == "-":
            dt = datetime.fromisoformat(s)
            return dt.replace(tzinfo=timezone.utc)
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


@router.get("/clients/{client_id}/receipts")
async def list_admin_client_receipts(
    client_id: str,
    type: str = Query(
        "all",
        description=(
            "all | subscription | subscription_checkout | subscription_renewal | subscription_ledger | "
            "order | intake_order | one_off_order | cvp_order"
        ),
    ),
    status: Optional[str] = Query(None, description="Filter by payment_status e.g. PAID"),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=500),
):
    """Merged subscription checkout receipts and paid orders for the selected client only."""
    from services.admin_billing_receipts import list_receipts_for_client

    df = _parse_admin_date(date_from)
    dt = _parse_admin_date(date_to)
    if dt and df and dt < df:
        raise HTTPException(status_code=400, detail="date_to must be on or after date_from")

    rows, meta = await list_receipts_for_client(
        client_id,
        type_filter=type,
        status_filter=status,
        date_from=df,
        date_to=dt,
        limit=limit,
    )
    if not rows and not meta.get("client_id"):
        raise HTTPException(status_code=404, detail="Client not found")
    return {"receipts": rows, "meta": meta}


@router.post("/clients/{client_id}/reconcile-payment-ledger")
async def reconcile_subscription_payment_ledger_admin(
    request: Request,
    client_id: str,
    payload: Optional[ReconcileSubscriptionPaymentLedgerBody] = Body(default=None),
):
    """Materialize paid Stripe invoices into ``subscription_payment_ledger`` (idempotent).

    Never mutates ``stripe_events``. Optional Stripe API listing is rate-limit conscious.
    """
    admin = await admin_route_guard(request)
    db = database.get_db()
    found = await db.clients.find_one({"client_id": client_id}, {"_id": 0, "client_id": 1})
    if not found:
        raise HTTPException(status_code=404, detail="Client not found")

    body = payload if payload is not None else ReconcileSubscriptionPaymentLedgerBody()
    result = await reconcile_client_subscription_payment_ledger(
        client_id,
        from_stripe_events=body.from_stripe_events,
        from_stripe_invoice_api_limit=body.from_stripe_invoice_api_limit,
    )
    await create_audit_log(
        action=AuditAction.ADMIN_ACTION,
        actor_role=UserRole.ROLE_ADMIN,
        actor_id=admin.get("portal_user_id"),
        client_id=client_id,
        metadata={
            "action_type": "SUBSCRIPTION_PAYMENT_LEDGER_RECONCILE",
            "result": {
                k: result.get(k)
                for k in ("upsert_count", "client_billing_last_payment_synced", "errors")
            },
            **normalized_admin_action_metadata(
                "reconcile_subscription_payment_ledger",
                "Admin ran subscription payment ledger reconciliation from stored webhook evidence.",
            ),
        },
    )
    return result


@router.get("/clients/{client_id}/receipts/subscription/{ref:path}/download")
async def download_admin_subscription_receipt(request: Request, client_id: str, ref: str):
    admin = await admin_route_guard(request)
    from services.admin_billing_receipts import get_subscription_receipt_doc_for_client
    from services.order_receipt_service import read_receipt_pdf_bytes

    doc = await get_subscription_receipt_doc_for_client(client_id, ref)
    if not doc or not doc.get("gridfs_id"):
        raise HTTPException(status_code=404, detail="Receipt not found or PDF unavailable")
    pdf = await read_receipt_pdf_bytes(str(doc["gridfs_id"]))
    if not pdf:
        raise HTTPException(status_code=404, detail="Receipt file not available")
    filename = doc.get("filename") or f"{doc.get('invoice_number', 'receipt')}.pdf"
    await create_audit_log(
        action=AuditAction.ADMIN_ACTION,
        actor_role=UserRole.ROLE_ADMIN,
        actor_id=admin.get("portal_user_id"),
        client_id=client_id,
        resource_type="subscription_receipt",
        resource_id=str(doc.get("invoice_number") or ref),
        metadata={
            "action_type": "ADMIN_RECEIPT_DOWNLOADED",
            "channel": "admin_billing",
            "stripe_session_id": str(doc.get("_id")),
            "path": str(request.url.path),
            **normalized_billing_audit_metadata(
                machine_event_type="billing.receipt.downloaded",
                human_label="Receipt downloaded",
                severity="info",
                actor_type="admin",
                actor_id=admin.get("portal_user_id"),
                client_id=client_id,
                stripe_checkout_session_id=str(doc.get("_id") or ""),
                support_explanation="Support downloaded a stored receipt PDF for a client.",
                occurred_at=datetime.now(timezone.utc),
            ),
        },
    )
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/clients/{client_id}/receipts/subscription/{ref:path}/regenerate")
async def regenerate_admin_subscription_checkout_pdf(request: Request, client_id: str, ref: str):
    """
    Rebuild the subscription checkout PDF from Stripe (expanded session + plan-aware lines).
    Requires a real ``stripe_checkout_invoices`` document (_id = cs_...). Keeps the same invoice number
    and original ``created_at``; sets ``pdf_regenerated_at`` and replaces GridFS bytes.
    """
    admin = await admin_route_guard(request)
    from services.admin_billing_receipts import get_subscription_receipt_doc_for_client
    from services.order_receipt_service import regenerate_subscription_checkout_invoice_pdf_for_client

    doc = await get_subscription_receipt_doc_for_client(client_id, ref)
    if not doc:
        raise HTTPException(status_code=404, detail="Receipt not found for this client")
    checkout_session_id = str(doc.get("_id") or "")
    if not checkout_session_id.startswith("cs_"):
        raise HTTPException(
            status_code=400,
            detail="Regeneration needs a Stripe checkout session id (cs_...). Open the receipt row from "
            "subscription checkout history, or pass the session id as ref.",
        )
    ok, inv_no, err = await regenerate_subscription_checkout_invoice_pdf_for_client(
        client_id, checkout_session_id
    )
    if not ok:
        raise HTTPException(status_code=500, detail=err or "Regeneration failed")
    await create_audit_log(
        action=AuditAction.ADMIN_ACTION,
        actor_role=UserRole.ROLE_ADMIN,
        actor_id=admin.get("portal_user_id"),
        client_id=client_id,
        resource_type="subscription_receipt",
        resource_id=str(inv_no or ref),
        metadata={
            "action_type": "ADMIN_SUBSCRIPTION_CHECKOUT_RECEIPT_REGENERATED",
            "channel": "admin_billing",
            "stripe_checkout_session_id": checkout_session_id,
            "invoice_number": inv_no,
            "path": str(request.url.path),
        },
    )
    return {
        "ok": True,
        "invoice_number": inv_no,
        "stripe_checkout_session_id": checkout_session_id,
    }


@router.get("/clients/{client_id}/receipts/order/{order_id}/download")
async def download_admin_order_receipt(request: Request, client_id: str, order_id: str):
    admin = await admin_route_guard(request)
    from services.admin_billing_receipts import get_order_for_client
    from services.order_receipt_service import get_receipt_for_order

    order = await get_order_for_client(client_id, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found for this client")
    order.pop("_id", None)
    pdf, filename = await get_receipt_for_order(order_id, order, allow_generate=True)
    if not pdf or not filename:
        raise HTTPException(status_code=404, detail="Receipt not available")
    await create_audit_log(
        action=AuditAction.ADMIN_ACTION,
        actor_role=UserRole.ROLE_ADMIN,
        actor_id=admin.get("portal_user_id"),
        client_id=client_id,
        resource_type="order",
        resource_id=order_id,
        metadata={
            "action_type": "ADMIN_RECEIPT_DOWNLOADED",
            "channel": "admin_billing",
            "invoice_number": order.get("invoice_number"),
            "path": str(request.url.path),
        },
    )
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/clients/{client_id}/receipts/resend")
async def admin_resend_client_receipt(request: Request, client_id: str, body: AdminReceiptResendBody):
    admin = await admin_route_guard(request)
    db = database.get_db()
    if not await db.clients.find_one({"client_id": client_id}, {"_id": 1}):
        raise HTTPException(status_code=404, detail="Client not found")

    src = (body.source or "").strip().lower()
    ref = (body.ref or "").strip()
    if not ref:
        raise HTTPException(status_code=400, detail="ref is required")

    from services.admin_billing_receipts import admin_resend_order_receipt_email, admin_resend_subscription_receipt_email

    if src == "subscription":
        ok, msg = await admin_resend_subscription_receipt_email(
            client_id=client_id,
            ref=ref,
            admin_portal_user_id=admin.get("portal_user_id"),
        )
    elif src == "order":
        ok, msg = await admin_resend_order_receipt_email(
            client_id=client_id,
            order_id=ref,
            admin_portal_user_id=admin.get("portal_user_id"),
        )
    else:
        raise HTTPException(status_code=400, detail="source must be subscription or order")

    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"success": True, "message": msg}


# =============================================================================
# Force Sync from Stripe
# =============================================================================

@router.post("/clients/{client_id}/sync")
async def sync_client_billing(request: Request, client_id: str):
    """
    Force sync billing data from Stripe.
    
    Fetches:
    - Customer details
    - Active subscriptions
    - Subscription status
    - Latest invoice and payment status
    
    Updates:
    - client_billing record
    - Entitlements
    - `sync_subscription_lifecycle` (aligns billing_lifecycle_state / entitlements with grace rules)
    - Triggers provisioning if entitlement becomes ENABLED
    
    Returns before/after diff.
    """
    admin = await admin_route_guard(request)
    db = database.get_db()
    
    try:
        # Get client
        client = await db.clients.find_one(
            {"client_id": client_id},
            {"_id": 0}
        )
        
        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Client not found"
            )
        
        # Get current billing state (before)
        billing_before = await db.client_billing.find_one(
            {"client_id": client_id},
            {"_id": 0}
        )
        
        before_state = {
            "subscription_status": billing_before.get("subscription_status") if billing_before else None,
            "entitlement_status": billing_before.get("entitlement_status") if billing_before else None,
            "current_plan_code": billing_before.get("current_plan_code") if billing_before else None,
        }
        
        # Get Stripe customer ID
        stripe_customer_id = client.get("stripe_customer_id") or (billing_before.get("stripe_customer_id") if billing_before else None)
        
        if not stripe_customer_id:
            # No Stripe customer - nothing to sync
            await create_audit_log(
                action=AuditAction.ADMIN_ACTION,
                actor_role=UserRole.ROLE_ADMIN,
                actor_id=admin.get("portal_user_id"),
                client_id=client_id,
                metadata={
                    "action_type": "BILLING_SYNC_ATTEMPTED",
                    "result": "NO_STRIPE_CUSTOMER",
                    "message": "Client has no Stripe customer ID"
                }
            )
            
            return {
                "success": False,
                "message": "Client has no Stripe customer ID. Cannot sync.",
                "has_stripe_customer": False,
            }
        
        # Fetch from Stripe
        try:
            customer = stripe.Customer.retrieve(stripe_customer_id)
        except stripe.error.InvalidRequestError:
            return {
                "success": False,
                "message": f"Stripe customer {stripe_customer_id} not found",
                "has_stripe_customer": False,
            }
        
        # Get subscriptions
        subscriptions = stripe.Subscription.list(
            customer=stripe_customer_id,
            status="all",
            limit=5,
            expand=["data.items.data.price", "data.latest_invoice"]
        )
        
        # Find active/relevant subscription
        active_subscription = None
        for sub in subscriptions.data:
            if sub.status in ("active", "trialing", "past_due"):
                active_subscription = sub
                break
        
        if not active_subscription and subscriptions.data:
            # Use most recent
            active_subscription = subscriptions.data[0]
        
        # Build billing update
        now_sync = datetime.now(timezone.utc)
        billing_update = {
            "client_id": client_id,
            "stripe_customer_id": stripe_customer_id,
            "updated_at": now_sync,
            "billing_last_synced_at": now_sync,
        }
        
        new_plan_code = None
        new_subscription_status = None
        new_entitlement_status = EntitlementStatus.DISABLED
        
        if active_subscription:
            # Determine plan from price_id
            for item in active_subscription.get("items", {}).get("data", []):
                price_id = item.get("price", {}).get("id")
                new_plan_code = plan_registry.get_plan_from_subscription_price_id(price_id)
                if new_plan_code:
                    break
            
            if not new_plan_code:
                new_plan_code = PlanCode.PLAN_1_SOLO
            
            new_subscription_status = active_subscription.status.upper()
            new_entitlement_status = plan_registry.get_entitlement_status_from_subscription(active_subscription.status)
            
            _sub_d = stripe_subscription_to_dict(active_subscription)
            cps = period_start_from_stripe_subscription_dict(_sub_d)
            cpe = period_end_from_stripe_subscription_dict(_sub_d)
            if not cpe:
                logger.warning(
                    "admin billing sync: invalid or missing current_period_end client_id=%s subscription_id=%s",
                    client_id,
                    getattr(active_subscription, "id", None),
                )
            billing_update.update({
                "stripe_subscription_id": active_subscription.id,
                "current_plan_code": new_plan_code.value if isinstance(new_plan_code, PlanCode) else new_plan_code,
                "subscription_status": new_subscription_status,
                "entitlement_status": new_entitlement_status.value,
                "cancel_at_period_end": active_subscription.cancel_at_period_end,
                "billing_sync_state": "ok" if cpe else "missing_period_end",
            })
            if cps:
                billing_update["current_period_start"] = cps
            if cpe:
                billing_update["current_period_end"] = cpe
            
            # Get invoice info
            latest_invoice = active_subscription.get("latest_invoice")
            if latest_invoice:
                if isinstance(latest_invoice, str):
                    latest_invoice = stripe.Invoice.retrieve(latest_invoice)
                
                billing_update["latest_invoice_id"] = latest_invoice.id
                billing_update["latest_invoice_status"] = latest_invoice.status
                
                if latest_invoice.status == "open" and latest_invoice.next_payment_attempt:
                    billing_update["next_payment_attempt"] = datetime.fromtimestamp(
                        latest_invoice.next_payment_attempt, tz=timezone.utc
                    )
        else:
            # No subscription
            billing_update.update({
                "subscription_status": "NONE",
                "entitlement_status": EntitlementStatus.DISABLED.value,
                "billing_sync_state": "no_subscription",
            })
        
        # Upsert billing record
        await db.client_billing.update_one(
            {"client_id": client_id},
            {"$set": billing_update, "$setOnInsert": {"created_at": datetime.now(timezone.utc)}},
            upsert=True
        )
        
        # Update client record
        client_update = {
            "stripe_customer_id": stripe_customer_id,
        }
        
        if new_plan_code:
            client_update["billing_plan"] = new_plan_code.value if isinstance(new_plan_code, PlanCode) else new_plan_code
        if new_subscription_status:
            client_update["subscription_status"] = "ACTIVE" if new_subscription_status in ("ACTIVE", "TRIALING") else new_subscription_status
        if new_entitlement_status:
            client_update["entitlement_status"] = new_entitlement_status.value
        
        await db.clients.update_one(
            {"client_id": client_id},
            {"$set": client_update}
        )
        
        # Check if entitlement flipped to ENABLED - trigger provisioning
        provisioning_triggered = False
        if (
            before_state.get("entitlement_status") != EntitlementStatus.ENABLED.value and
            new_entitlement_status == EntitlementStatus.ENABLED
        ):
            onboarding_status = client.get("onboarding_status")
            if onboarding_status != "PROVISIONED":
                success, message = await provisioning_service.provision_client_portal(client_id)
                provisioning_triggered = success
                logger.info(f"Provisioning triggered by sync for {client_id}: {success}")
        
        after_state = {
            "subscription_status": new_subscription_status,
            "entitlement_status": new_entitlement_status.value if new_entitlement_status else None,
            "current_plan_code": new_plan_code.value if isinstance(new_plan_code, PlanCode) else new_plan_code,
        }
        
        lifecycle_sync: Dict[str, Any] = {}
        try:
            from services.subscription_lifecycle_service import sync_subscription_lifecycle

            lifecycle_sync = await sync_subscription_lifecycle(client_id, bump_version=True)
        except Exception as lc_err:
            logger.warning(
                "sync_client_billing: sync_subscription_lifecycle failed for %s: %s",
                client_id,
                lc_err,
            )
            lifecycle_sync = {"updated": False, "error": str(lc_err)}

        # Audit log
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_role=UserRole.ROLE_ADMIN,
            actor_id=admin.get("portal_user_id"),
            client_id=client_id,
            metadata={
                "action_type": "BILLING_SYNC_COMPLETED",
                "before": before_state,
                "after": after_state,
                "provisioning_triggered": provisioning_triggered,
                "stripe_customer_id": stripe_customer_id,
                "stripe_subscription_id": active_subscription.id if active_subscription else None,
                "lifecycle_sync": lifecycle_sync,
            **normalized_billing_audit_metadata(
                machine_event_type="billing.sync.completed",
                human_label="Billing sync completed",
                severity="info",
                actor_type="admin",
                actor_id=admin.get("portal_user_id"),
                client_id=client_id,
                stripe_customer_id=stripe_customer_id,
                stripe_subscription_id=active_subscription.id if active_subscription else None,
                support_explanation="Support requested a manual Stripe sync for this client.",
                occurred_at=datetime.now(timezone.utc),
            ),
            }
        )
        try:
            from services.notification_orchestrator import notification_orchestrator

            await notification_orchestrator.send(
                template_key="ADMIN_MANUAL",
                client_id=client_id,
                context={
                    "subject": "Your subscription plan was updated",
                    "body": (
                        f"Your plan has been changed from {current_plan_code.value} to {new_plan_code.value}. "
                        + ("The new plan will apply at the end of your current billing period." if body.apply_at_period_end else "The new plan is now active.")
                    ),
                },
                idempotency_key=f"admin_plan_change_{client_id}_{new_plan_code.value}_{int(bool(body.apply_at_period_end))}",
                event_type="admin.billing.plan_change_confirmation",
            )
        except Exception as notify_err:
            logger.warning("change-plan confirmation notification hook failed for %s: %s", client_id, notify_err)
        
        return {
            "success": True,
            "message": "Billing synced from Stripe",
            "before": before_state,
            "after": after_state,
            "changes_detected": before_state != after_state,
            "provisioning_triggered": provisioning_triggered,
            "stripe_customer_id": stripe_customer_id,
            "stripe_subscription_id": active_subscription.id if active_subscription else None,
            "lifecycle_sync": lifecycle_sync,
        }
        
    except HTTPException:
        raise
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error during sync: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Stripe error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Sync billing error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Sync failed"
        )


# =============================================================================
# Create Billing Portal Link
# =============================================================================

@router.post("/clients/{client_id}/portal-link")
async def create_billing_portal_link(request: Request, client_id: str):
    """
    Generate a Stripe Billing Portal session for the customer.
    
    Returns a one-time URL that can be shared with the client.
    """
    admin = await admin_route_guard(request)
    db = database.get_db()
    
    try:
        # Get client
        client = await db.clients.find_one(
            {"client_id": client_id},
            {"_id": 0}
        )
        
        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Client not found"
            )
        
        # Get Stripe customer ID
        billing = await db.client_billing.find_one(
            {"client_id": client_id},
            {"_id": 0, "stripe_customer_id": 1}
        )
        
        stripe_customer_id = client.get("stripe_customer_id") or (billing.get("stripe_customer_id") if billing else None)
        
        if not stripe_customer_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Client has no Stripe customer ID"
            )
        
        # Get return URL (public frontend base)
        from utils.public_app_url import get_public_app_url
        base_url = get_public_app_url(for_email_links=False)
        portal_session = stripe.billing_portal.Session.create(
            customer=stripe_customer_id,
            return_url=f"{base_url}/app/billing",
        )
        
        # Audit log
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_role=UserRole.ROLE_ADMIN,
            actor_id=admin.get("portal_user_id"),
            client_id=client_id,
            metadata={
                "action_type": "BILLING_PORTAL_LINK_CREATED",
                "stripe_customer_id": stripe_customer_id,
                "portal_url_created": True,
            **normalized_billing_audit_metadata(
                machine_event_type="billing.portal_link.created",
                human_label="Billing portal link created",
                severity="info",
                actor_type="admin",
                actor_id=admin.get("portal_user_id"),
                client_id=client_id,
                stripe_customer_id=stripe_customer_id,
                support_explanation="Support generated a Stripe billing portal link.",
                occurred_at=datetime.now(timezone.utc),
            ),
            }
        )
        
        return {
            "success": True,
            "portal_url": portal_session.url,
            "expires_at": None,  # Stripe portal sessions don't have explicit expiry
            "client_email": client.get("contact_email"),
            "message": "Billing portal link created. Share with client to manage subscription.",
        }
        
    except HTTPException:
        raise
    except stripe.error.StripeError as e:
        logger.error(f"Stripe portal error: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Stripe error: {str(e)}",
        )
    except Exception as e:
        logger.error(f"Portal link error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create portal link",
        )


# =============================================================================
# Change Plan (admin-initiated upgrade/downgrade)
# =============================================================================

@router.post("/clients/{client_id}/change-plan")
async def change_client_plan(request: Request, client_id: str, body: ChangePlanRequest):
    """
    Change a client's subscription plan (upgrade or downgrade).
    
    Requires an active Stripe subscription. Optionally apply at period end to avoid
    proration (recommended for downgrades). Updates Stripe then syncs app state.
    """
    admin = await admin_route_guard(request)
    support_reason = ensure_action_reason("change_plan", body.reason)
    db = database.get_db()

    try:
        # Resolve plan code
        try:
            new_plan_code = PlanCode(body.plan_code)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid plan_code. Use one of: {', '.join(p.value for p in PlanCode)}",
            )

        # Get client and billing
        client = await db.clients.find_one(
            {"client_id": client_id},
            {"_id": 0, "client_id": 1, "stripe_customer_id": 1, "billing_plan": 1},
        )
        if not client:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")

        billing = await db.client_billing.find_one(
            {"client_id": client_id},
            {"_id": 0, "stripe_customer_id": 1, "stripe_subscription_id": 1, "current_plan_code": 1},
        )
        stripe_customer_id = client.get("stripe_customer_id") or (billing.get("stripe_customer_id") if billing else None)
        stripe_subscription_id = billing.get("stripe_subscription_id") if billing else None

        if not stripe_subscription_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Client has no active Stripe subscription. Cannot change plan.",
            )

        # Current plan from our record (may differ from Stripe until sync)
        current_plan_str = billing.get("current_plan_code") or client.get("billing_plan") or "PLAN_1_SOLO"
        current_plan_code = plan_registry.resolve_plan_code(current_plan_str)
        if current_plan_code == new_plan_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Client is already on {new_plan_code.value}. No change made.",
            )

        # Get new price ID
        price_ids = plan_registry.get_stripe_price_ids(new_plan_code)
        new_price_id = price_ids.get("subscription_price_id")
        if not new_price_id:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Stripe price not configured for this plan.",
            )

        # Retrieve subscription and find the recurring (plan) subscription item
        subscription = stripe.Subscription.retrieve(
            stripe_subscription_id,
            expand=["items.data.price"],
        )
        subscription_item_id = None
        for item in subscription.get("items", {}).get("data", []):
            price_id = (item.get("price") or {}).get("id") if isinstance(item.get("price"), dict) else getattr(item.get("price"), "id", None)
            if price_id and plan_registry.get_plan_from_subscription_price_id(price_id):
                subscription_item_id = item.get("id")
                break

        if not subscription_item_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Could not find a recurring plan item on this subscription.",
            )

        # Update subscription in Stripe
        proration_behavior = "none" if body.apply_at_period_end else "create_prorations"
        stripe.Subscription.modify(
            stripe_subscription_id,
            items=[{"id": subscription_item_id, "price": new_price_id}],
            proration_behavior=proration_behavior,
        )

        # Re-retrieve subscription and update app state so admin sees new plan immediately
        updated_sub = stripe.Subscription.retrieve(
            stripe_subscription_id,
            expand=["items.data.price"],
        )
        derived_plan = None
        for item in updated_sub.get("items", {}).get("data", []):
            price_id = (item.get("price") or {}).get("id") if isinstance(item.get("price"), dict) else getattr(item.get("price"), "id", None)
            if price_id:
                derived_plan = plan_registry.get_plan_from_subscription_price_id(price_id)
                if derived_plan:
                    break
        # Use requested plan as fallback if price-to-plan lookup fails (keeps DB in sync with what we set in Stripe)
        if not derived_plan:
            derived_plan = new_plan_code
        new_status = (updated_sub.status or "").upper()
        new_entitlement = plan_registry.get_entitlement_status_from_subscription(updated_sub.status)

        _upd_d = stripe_subscription_to_dict(updated_sub)
        _upd_ps = period_start_from_stripe_subscription_dict(_upd_d)
        _upd_pe = period_end_from_stripe_subscription_dict(_upd_d)

        # When apply_at_period_end is True, Stripe applies the new price at period end; do not change
        # app plan now.
        if body.apply_at_period_end:
            # Only update period metadata; leave current_plan_code and entitlement unchanged
            billing_update = {
                "client_id": client_id,
                "stripe_customer_id": stripe_customer_id,
                "updated_at": datetime.now(timezone.utc),
                "stripe_subscription_id": stripe_subscription_id,
                "cancel_at_period_end": updated_sub.cancel_at_period_end,
            }
            if _upd_ps:
                billing_update["current_period_start"] = _upd_ps
            if _upd_pe:
                billing_update["current_period_end"] = _upd_pe
            await db.client_billing.update_one(
                {"client_id": client_id},
                {"$set": billing_update, "$setOnInsert": {"created_at": datetime.now(timezone.utc)}},
                upsert=True,
            )
            # Do not update clients.billing_plan now; lifecycle sync will compute entitlement/status.
            after_state = {
                "subscription_status": new_status,
                "entitlement_status": (billing or {}).get("entitlement_status") or "ENABLED",
                "current_plan_code": current_plan_code.value,
                "scheduled_plan_at_period_end": new_plan_code.value,
            }
        else:
            await persist_subscription_billing_from_stripe(
                client_id,
                updated_sub,
                event_source="admin_change_plan",
                update_plan=True,
                increment_entitlements_version=1,
            )
            after_state = {
                "subscription_status": new_status,
                "entitlement_status": new_entitlement.value,
                "current_plan_code": derived_plan.value,
            }

        try:
            await sync_subscription_lifecycle(client_id, bump_version=False)
        except Exception as sync_err:
            await mark_billing_reconciliation_needed(
                client_id=client_id,
                reason="admin_change_plan_lifecycle_sync_failed",
                context={
                    "error": str(sync_err)[:500],
                    "apply_at_period_end": bool(body.apply_at_period_end),
                    "target_plan": new_plan_code.value,
                },
            )
            raise

        # Audit log
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_role=UserRole.ROLE_ADMIN,
            actor_id=admin.get("portal_user_id"),
            client_id=client_id,
            metadata={
                "action_type": "BILLING_PLAN_CHANGED",
                **normalized_admin_action_metadata("change_plan", support_reason),
                "previous_plan": current_plan_code.value,
                "new_plan": new_plan_code.value,
                "apply_at_period_end": body.apply_at_period_end,
                "stripe_subscription_id": stripe_subscription_id,
                **normalized_billing_audit_metadata(
                    machine_event_type="billing.plan.changed",
                    human_label="Subscription plan changed",
                    severity="warning",
                    actor_type="admin",
                    actor_id=admin.get("portal_user_id"),
                    client_id=client_id,
                    stripe_customer_id=stripe_customer_id,
                    stripe_subscription_id=stripe_subscription_id,
                    support_explanation="Support changed the client's plan through admin billing controls.",
                    occurred_at=datetime.now(timezone.utc),
                ),
            },
        )
        try:
            from services.plan_reconciliation_service import reconcile_plan_change

            await reconcile_plan_change(
                client_id=client_id,
                old_plan=current_plan_code.value,
                new_plan=new_plan_code.value,
                reason="admin_change_plan",
                subscription_status=new_status,
            )
        except Exception as reconcile_err:
            await mark_billing_reconciliation_needed(
                client_id=client_id,
                reason="admin_change_plan_reconcile_failed",
                context={"error": str(reconcile_err)[:500]},
            )
            logger.warning("change-plan reconcile failed for %s: %s", client_id, reconcile_err)

        plan_rank = {"PLAN_1_SOLO": 1, "PLAN_2_PORTFOLIO": 2, "PLAN_3_PRO": 3}
        from_rank = plan_rank.get(current_plan_code.value, 0)
        to_rank = plan_rank.get(new_plan_code.value, 0)
        plan_change_type = "upgrade" if to_rank > from_rank else "downgrade"

        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_role=UserRole.SYSTEM,
            client_id=client_id,
            metadata={
                "action_type": "BILLING_EMAIL_TRIGGER_HOOK",
                "trigger_key": "subscription_plan_change_confirmation",
                "plan_change_type": plan_change_type,
                "apply_at_period_end": bool(body.apply_at_period_end),
                "source": "admin_billing.change_client_plan",
            },
        )

        return {
            "success": True,
            "message": "Plan change applied. Billing synced.",
            "previous_plan": current_plan_code.value,
            "new_plan": new_plan_code.value,
            "apply_at_period_end": body.apply_at_period_end,
            "after": after_state,
        }
    except HTTPException:
        raise
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error during change-plan: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Stripe error: {str(e)}",
        )
    except Exception as e:
        logger.error(f"Change plan error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to change plan",
        )


# =============================================================================
# Resend Password Setup Link
# =============================================================================

@router.post("/clients/{client_id}/resend-setup")
async def resend_password_setup(request: Request, client_id: str):
    """
    Resend password setup email to client.
    
    Works even if user never completed setup previously.
    """
    admin = await admin_route_guard(request)
    db = database.get_db()
    
    try:
        # Get portal user
        portal_user = await db.portal_users.find_one(
            {"client_id": client_id, "role": "ROLE_CLIENT_ADMIN"},
            {"_id": 0}
        )
        
        if not portal_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No portal user found for this client"
            )

        from auth import generate_secure_token, hash_token
        from utils.public_app_url import get_frontend_base_url

        # Use same token flow as /set-password: store hashed token in password_tokens
        await db.password_tokens.update_many(
            {"portal_user_id": portal_user["portal_user_id"], "used_at": None, "revoked_at": None},
            {"$set": {"revoked_at": datetime.now(timezone.utc).isoformat()}},
        )
        raw_token = generate_secure_token()
        token_hash = hash_token(raw_token)
        now = datetime.now(timezone.utc)
        password_token = PasswordToken(
            token_hash=token_hash,
            portal_user_id=portal_user["portal_user_id"],
            client_id=client_id,
            expires_at=now + timedelta(hours=24),
            created_by="ADMIN",
            send_count=0,
        )
        doc = password_token.model_dump()
        for key in ("expires_at", "used_at", "revoked_at", "created_at"):
            if doc.get(key) and hasattr(doc[key], "isoformat"):
                doc[key] = doc[key].isoformat()
        await db.password_tokens.insert_one(doc)

        try:
            base_url = get_frontend_base_url()
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"error_code": "APP_URL_NOT_CONFIGURED", "message": str(e)},
            )
        setup_url = f"{base_url}/set-password?token={raw_token}"
        user_email = (portal_user.get("auth_email") or portal_user.get("email") or "").strip()
        if not user_email or not setup_url:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error_code": "EMAIL_INPUT_INVALID", "message": "Missing recipient email or setup link"},
            )
        
        from services.notification_orchestrator import notification_orchestrator
        client = await db.clients.find_one({"client_id": client_id}, {"_id": 0, "onboarding_status": 1})
        if client and client.get("onboarding_status") != "PROVISIONED":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error_code": "ACCOUNT_NOT_READY", "message": "Provisioning not completed."},
            )
        idempotency_key = f"{client_id}_WELCOME_EMAIL_resend_{portal_user.get('portal_user_id', '')}_{raw_token[:8]}"
        try:
            result = await notification_orchestrator.send(
                template_key="WELCOME_EMAIL",
                client_id=client_id,
                context={
                    "recipient": user_email,
                    "setup_link": setup_url,
                    "client_name": portal_user.get("full_name") or portal_user.get("name", "Customer"),
                    "company_name": "Pleerity Enterprise Ltd",
                    "tagline": "AI-Driven Solutions & Compliance",
                },
                idempotency_key=idempotency_key,
                event_type="admin_resend_billing",
            )
        except Exception as e:
            logger.error(f"Resend setup send error: {e}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={"error_code": "EMAIL_SEND_FAILED", "message": str(e), "template": EmailTemplateAlias.PASSWORD_SETUP.value},
            )
        if result.status_code == 403:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=result.details or {"error_code": "ACCOUNT_NOT_READY"})
        if result.outcome == "blocked":
            reason = result.block_reason or "Email provider not configured"
            if reason == "BLOCKED_PROVIDER_NOT_CONFIGURED":
                reason = "Email provider (Postmark) is not configured. Set POSTMARK_SERVER_TOKEN to send password setup emails."
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"error_code": "EMAIL_NOT_CONFIGURED", "message": reason},
            )
        if result.outcome == "failed":
            msg = (result.error_message or "Email delivery failed")[:500]
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={"error_code": "EMAIL_SEND_FAILED", "message": msg, "template": EmailTemplateAlias.PASSWORD_SETUP.value},
            )
        
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_role=UserRole.ROLE_ADMIN,
            actor_id=admin.get("portal_user_id"),
            client_id=client_id,
            metadata={
                "action_type": "PASSWORD_SETUP_RESENT",
                "reason": "Admin requested resend",
            }
        )
        
        return {
            "success": True,
            "message": "Password setup email sent",
            "email": user_email,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Resend setup error: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error_code": "EMAIL_SEND_FAILED", "template": EmailTemplateAlias.PASSWORD_SETUP.value},
        )


# =============================================================================
# Force Provisioning
# =============================================================================

class TestProvisionBody(BaseModel):
    """Set onboarding_status and billing_plan for test clients (admin only)."""
    onboarding_status: str = "PROVISIONED"
    billing_plan: Optional[str] = "PLAN_1_SOLO"


@router.patch("/clients/{client_id}/test-provision")
async def set_test_client_provisioned(request: Request, client_id: str, body: TestProvisionBody):
    """
    Set onboarding_status and billing_plan for a client (test/seed accounts).
    Use so test clients can access /app/dashboard without full Stripe provisioning.
    Admin only.
    """
    admin = await admin_route_guard(request)
    db = database.get_db()
    client = await db.clients.find_one({"client_id": client_id}, {"_id": 1})
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    update = {}
    if body.onboarding_status in ("PROVISIONED", "PENDING_PAYMENT", "PROVISIONING", "FAILED", "INTAKE_PENDING"):
        update["onboarding_status"] = body.onboarding_status
    if body.billing_plan and body.billing_plan in ("PLAN_1_SOLO", "PLAN_2_PORTFOLIO", "PLAN_3_PRO"):
        update["billing_plan"] = body.billing_plan
    if not update:
        return {"updated": False, "client_id": client_id}
    await db.clients.update_one({"client_id": client_id}, {"$set": update})
    await create_audit_log(
        action=AuditAction.ADMIN_ACTION,
        actor_role=UserRole.ROLE_ADMIN,
        actor_id=admin.get("portal_user_id"),
        client_id=client_id,
        metadata={"action_type": "TEST_PROVISION_UPDATE", "update": update}
    )
    return {"updated": True, "client_id": client_id, "update": update}


@router.post("/clients/{client_id}/force-provision")
async def force_provision_client(
    request: Request,
    client_id: str,
    body: SupportGovernedActionReasonBody = Body(...),
):
    """
    Re-run provisioning pipeline for a client.
    
    Only allowed if entitlement is ENABLED.
    Idempotent and safe to rerun.
    """
    admin = await admin_route_guard(request)
    support_reason = ensure_action_reason("force_provision", body.reason)
    db = database.get_db()
    
    try:
        # Get client
        client = await db.clients.find_one(
            {"client_id": client_id},
            {"_id": 0}
        )
        
        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Client not found"
            )
        
        # Check entitlement
        entitlement_status = client.get("entitlement_status", "DISABLED")
        
        if entitlement_status != "ENABLED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot provision: entitlement is {entitlement_status}. Sync billing first."
            )
        
        # Run provisioning
        success, message = await provisioning_service.provision_client_portal(client_id)
        
        # Audit log
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_role=UserRole.ROLE_ADMIN,
            actor_id=admin.get("portal_user_id"),
            client_id=client_id,
            metadata={
                "action_type": "FORCE_PROVISIONING",
                **normalized_admin_action_metadata("force_provision", support_reason),
                "success": success,
                "message": message,
                "previous_onboarding_status": client.get("onboarding_status"),
            }
        )
        
        return {
            "success": success,
            "message": message,
            "client_id": client_id,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Force provision error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Provisioning failed"
        )


# =============================================================================
# Send Message to Client
# =============================================================================

@router.post("/clients/{client_id}/message")
async def send_client_message(request: Request, client_id: str, data: MessageRequest):
    """
    Send message to client via specified channels.
    
    Channels:
    - in_app: Always available
    - email: Always available
    - sms: Only if plan entitled + Twilio configured
    
    Templates:
    - payment_received
    - provisioning_complete
    - payment_failed
    - subscription_canceled
    """
    admin = await admin_route_guard(request)
    db = database.get_db()
    
    try:
        # Get client
        client = await db.clients.find_one(
            {"client_id": client_id},
            {"_id": 0}
        )
        
        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Client not found"
            )
        
        results = {
            "in_app": None,
            "email": None,
            "sms": None,
        }
        
        # Check SMS entitlement
        sms_entitled = False
        if "sms" in data.channels:
            plan_code = client.get("billing_plan", "PLAN_1_SOLO")
            features = plan_registry.get_features_by_string(plan_code)
            sms_entitled = features.get("sms_reminders", False)
            
            if not sms_entitled:
                results["sms"] = {
                    "sent": False,
                    "reason": "PLAN_NOT_ENTITLED",
                    "message": "SMS requires Portfolio plan or higher",
                }
        
        # Template content
        templates = {
            "payment_received": {
                "subject": "Payment Received - Compliance Vault Pro",
                "body": "Thank you for your payment. Your subscription is now active and provisioning has started. You'll receive another email shortly with your login details.",
            },
            "provisioning_complete": {
                "subject": "Your Account is Ready - Compliance Vault Pro",
                "body": "Great news! Your Compliance Vault Pro account is ready. Please check your email for the password setup link to get started.",
            },
            "payment_failed": {
                "subject": "Payment Failed - Action Required",
                "body": "We were unable to process your payment. Please update your payment method to maintain access to your account.",
            },
            "subscription_canceled": {
                "subject": "Subscription Cancelled - Compliance Vault Pro",
                "body": "Your subscription has been cancelled. You'll continue to have access until the end of your current billing period.",
            },
        }
        
        template = templates.get(data.template_id, {})
        subject = data.subject or template.get("subject", "Message from Compliance Vault Pro")
        body = data.custom_text or template.get("body", "")
        
        # Send in-app message
        if "in_app" in data.channels:
            import uuid
            message_record = {
                "message_id": str(uuid.uuid4()),
                "client_id": client_id,
                "channel": "in_app",
                "subject": subject,
                "body": body,
                "template_id": data.template_id,
                "sent_by": admin.get("portal_user_id"),
                "sent_at": datetime.now(timezone.utc),
                "read": False,
            }
            await db.client_messages.insert_one(message_record)
            results["in_app"] = {"sent": True, "message_id": message_record["message_id"]}
        
        # Send email via orchestrator
        if "email" in data.channels:
            from services.notification_orchestrator import notification_orchestrator
            import uuid
            msg_id = str(uuid.uuid4())
            idempotency_key = f"{client_id}_ADMIN_MANUAL_{msg_id}"
            result = await notification_orchestrator.send(
                template_key="ADMIN_MANUAL",
                client_id=client_id,
                context={
                    "subject": subject,
                    "message": body,
                    "client_name": client.get("full_name", "Client"),
                    "customer_reference": client.get("customer_reference", "N/A"),
                    "company_name": "Pleerity Enterprise Ltd",
                    "tagline": "AI-Driven Solutions & Compliance",
                },
                idempotency_key=idempotency_key,
                event_type="admin_billing_message",
            )
            results["email"] = {"sent": result.outcome in ("sent", "duplicate_ignored")}
        
        # Send SMS via orchestrator
        if "sms" in data.channels and sms_entitled:
            from services.notification_orchestrator import notification_orchestrator
            phone = client.get("phone")
            if phone:
                import uuid
                sms_id = str(uuid.uuid4())
                idempotency_key = f"{client_id}_ADMIN_MANUAL_SMS_{sms_id}"
                result = await notification_orchestrator.send(
                    template_key="ADMIN_MANUAL_SMS",
                    client_id=client_id,
                    context={"body": body[:160]},
                    idempotency_key=idempotency_key,
                    event_type="admin_billing_sms",
                )
                results["sms"] = {"sent": result.outcome in ("sent", "duplicate_ignored")}
            else:
                results["sms"] = {"sent": False, "reason": "NO_PHONE_NUMBER"}
        
        # Audit log
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_role=UserRole.ROLE_ADMIN,
            actor_id=admin.get("portal_user_id"),
            client_id=client_id,
            metadata={
                "action_type": "CLIENT_MESSAGE_SENT",
                "channels": data.channels,
                "template_id": data.template_id,
                "results": results,
            }
        )
        
        return {
            "success": True,
            "results": results,
            "client_email": client.get("contact_email"),
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Send message error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send message"
        )


# =============================================================================
# Get Billing Statistics (Dashboard)
# =============================================================================

@router.get("/statistics")
async def get_billing_statistics(request: Request):
    """Get billing statistics for admin dashboard."""
    admin = await admin_route_guard(request)
    db = database.get_db()
    
    try:
        # Count by entitlement status
        enabled_count = await db.clients.count_documents({"entitlement_status": "ENABLED"})
        limited_count = await db.clients.count_documents({"entitlement_status": "LIMITED"})
        disabled_count = await db.clients.count_documents({"entitlement_status": "DISABLED"})
        
        # Count by plan
        plan_counts = {}
        for plan in ["PLAN_1_SOLO", "PLAN_2_PORTFOLIO", "PLAN_3_PRO"]:
            plan_counts[plan] = await db.clients.count_documents({"billing_plan": plan})
        
        # Recent webhook events
        recent_events = await db.stripe_events.find(
            {"status": {"$in": ["PROCESSED", "FAILED"]}}
        ).sort("created", -1).limit(10).to_list(10)
        
        for event in recent_events:
            if "_id" in event:
                del event["_id"]
        
        # Clients needing attention (include name and CRN for display)
        attention_needed = await db.clients.find(
            {
                "$or": [
                    {"entitlement_status": "LIMITED"},
                    {"onboarding_status": {"$nin": ["PROVISIONED", "COMPLETE"]}},
                ]
            },
            {"_id": 0, "client_id": 1, "contact_email": 1, "full_name": 1, "customer_reference": 1, "entitlement_status": 1, "onboarding_status": 1}
        ).limit(20).to_list(20)
        for c in attention_needed:
            c["crn"] = c.get("customer_reference")

        lifecycle_state_counts: Dict[str, int] = {}
        for st in (
            "active",
            "renewing",
            "past_due",
            "grace_period",
            "limited",
            "cancelled",
            "expired",
        ):
            lifecycle_state_counts[st] = await db.client_billing.count_documents(
                {"billing_lifecycle_state": st}
            )

        grace_billing_rows = await db.client_billing.find(
            {"billing_lifecycle_state": "grace_period"},
            {"_id": 0, "client_id": 1, "grace_period_ends_at": 1, "payment_failed_at": 1},
        ).limit(40).to_list(40)
        clients_in_grace: List[Dict[str, Any]] = []
        if grace_billing_rows:
            gcids = [r["client_id"] for r in grace_billing_rows]
            gclients = await db.clients.find(
                {"client_id": {"$in": gcids}},
                {"_id": 0, "client_id": 1, "full_name": 1, "email": 1, "customer_reference": 1},
            ).to_list(len(gcids))
            gc_map = {x["client_id"]: x for x in gclients}

            def _iso(d: Any) -> Optional[str]:
                if d is None:
                    return None
                if hasattr(d, "isoformat"):
                    return d.isoformat()
                return str(d)

            for row in grace_billing_rows:
                cid = row["client_id"]
                cu = gc_map.get(cid, {})
                clients_in_grace.append(
                    {
                        "client_id": cid,
                        "full_name": cu.get("full_name"),
                        "contact_email": cu.get("email"),
                        "crn": cu.get("customer_reference"),
                        "grace_period_ends_at": _iso(row.get("grace_period_ends_at")),
                        "payment_failed_at": _iso(row.get("payment_failed_at")),
                    }
                )
        
        return {
            "entitlement_counts": {
                "enabled": enabled_count,
                "limited": limited_count,
                "disabled": disabled_count,
            },
            "plan_counts": plan_counts,
            "billing_lifecycle_state_counts": lifecycle_state_counts,
            "clients_in_grace": clients_in_grace,
            "recent_webhook_events": recent_events,
            "clients_needing_attention": attention_needed,
        }
        
    except Exception as e:
        logger.error(f"Get billing statistics error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get statistics"
        )


# =============================================================================
# Background Job Triggers (Admin Only)
# =============================================================================

async def _run_subscription_lifecycle_batch_job() -> Dict[str, Any]:
    """Post-grace enforcement, mid-grace nudges, 7d/3d renewal reminders — same as scheduler `subscription_lifecycle`."""
    from services.jobs import run_renewal_reminders

    return await run_renewal_reminders()


@router.post("/jobs/subscription-lifecycle")
async def trigger_subscription_lifecycle_job(request: Request, body: SupportGovernedActionReasonBody = Body(...)):
    """Manually run the subscription lifecycle batch job (`process_subscription_lifecycle_and_reminders`)."""
    admin = await admin_route_guard(request)
    support_reason = ensure_action_reason("run_subscription_lifecycle_batch", body.reason)

    try:
        result = await _run_subscription_lifecycle_batch_job()
        count = result.get("count") if isinstance(result, dict) else result
        metrics = result.get("outcome_metrics") if isinstance(result, dict) else None

        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_role=UserRole.ROLE_ADMIN,
            actor_id=admin.get("portal_user_id"),
            metadata={
                "action_type": "JOB_TRIGGERED",
                **normalized_admin_action_metadata("run_subscription_lifecycle_batch", support_reason),
                "job_name": "subscription_lifecycle",
                "items_processed": count,
                "outcome_metrics": metrics,
            },
        )

        return {
            "success": True,
            "job": "subscription_lifecycle",
            "items_processed": count,
            "message": result.get("message") if isinstance(result, dict) else None,
            "outcome_metrics": metrics,
        }

    except Exception as e:
        logger.error(f"Subscription lifecycle job error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to run subscription lifecycle job",
        )


@router.post("/jobs/renewal-reminders")
async def trigger_renewal_reminders(request: Request):
    """
    Backward-compatible alias: same batch as POST /jobs/subscription-lifecycle.

    Runs post-grace entitlement updates, mid-grace payment nudges, and renewal reminder emails.
    """
    admin = await admin_route_guard(request)
    
    try:
        result = await _run_subscription_lifecycle_batch_job()
        count = result.get("count") if isinstance(result, dict) else result
        metrics = result.get("outcome_metrics") if isinstance(result, dict) else None

        # Audit log
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_role=UserRole.ROLE_ADMIN,
            actor_id=admin.get("portal_user_id"),
            metadata={
                "action_type": "JOB_TRIGGERED",
                "job_name": "renewal_reminders",
                "reminders_sent": count,
                "outcome_metrics": metrics,
            }
        )

        return {
            "success": True,
            "job": "renewal_reminders",
            "reminders_sent": count,
            "message": result.get("message") if isinstance(result, dict) else None,
            "outcome_metrics": metrics,
        }
        
    except Exception as e:
        logger.error(f"Renewal reminder job error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to run renewal reminder job"
        )


@router.post("/jobs/stripe-subscription-reconcile")
async def trigger_stripe_subscription_reconcile_job(request: Request, body: SupportGovernedActionReasonBody = Body(...)):
    """Run the Stripe subscription reconcile batch (same as scheduled `stripe_subscription_reconcile`)."""
    admin = await admin_route_guard(request)
    support_reason = ensure_action_reason("run_stripe_reconcile_batch", body.reason)
    try:
        from services.jobs import run_stripe_subscription_reconcile

        result = await run_stripe_subscription_reconcile()
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_role=UserRole.ROLE_ADMIN,
            actor_id=admin.get("portal_user_id"),
            metadata={
                "action_type": "JOB_TRIGGERED",
                **normalized_admin_action_metadata("run_stripe_reconcile_batch", support_reason),
                "job_name": "stripe_subscription_reconcile",
                "result": result,
            },
        )
        return {"success": True, "job": "stripe_subscription_reconcile", **(result or {})}
    except Exception as e:
        logger.error("Stripe subscription reconcile job error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to run Stripe subscription reconcile job",
        )


@router.get("/jobs/status")
async def get_job_status(request: Request):
    """
    Get status of background jobs and entitlement-based blocking info.
    
    Returns:
    - Job scheduler status
    - Clients blocked from background jobs (LIMITED/DISABLED)
    """
    admin = await admin_route_guard(request)
    db = database.get_db()
    
    try:
        # Count clients by entitlement for job blocking status
        blocked_limited = await db.clients.count_documents({"entitlement_status": "LIMITED"})
        blocked_disabled = await db.clients.count_documents({"entitlement_status": "DISABLED"})
        
        return {
            "job_blocking": {
                "limited_clients": blocked_limited,
                "disabled_clients": blocked_disabled,
                "message": f"{blocked_limited + blocked_disabled} clients blocked from background jobs (reminders, digests, scheduled reports)"
            },
            "job_types": [
                {"name": "daily_reminders", "schedule": "Daily at 8 AM", "description": "Compliance expiry reminders"},
                {"name": "monthly_digest", "schedule": "1st of month", "description": "Monthly compliance digest"},
                {"name": "compliance_check", "schedule": "Hourly", "description": "Status change detection"},
                {"name": "subscription_lifecycle", "schedule": "Daily ~9:15 UTC", "description": "Post-grace enforcement, grace nudges, 7d/3d renewal emails"},
                {"name": "renewal_reminders", "schedule": "Alias", "description": "Same batch as subscription_lifecycle (API alias)"},
                {"name": "scheduled_reports", "schedule": "Per schedule", "description": "Automated report delivery"},
            ],
        }
        
    except Exception as e:
        logger.error(f"Get job status error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get job status"
        )

