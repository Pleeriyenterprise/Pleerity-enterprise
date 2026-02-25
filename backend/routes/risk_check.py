"""
Compliance Risk Check – standalone conversion demo.
No client creation, no provisioning, no Stripe. Two endpoints: preview (no PII), report (persist + optional email).
"""
from fastapi import APIRouter, HTTPException, Request
from database import database
from datetime import datetime, timezone
from typing import Optional, List, Any
from pydantic import BaseModel, EmailStr, Field
import logging
import uuid
import os

from services.risk_check_scoring import (
    compute_risk_check_result,
    simulated_property_breakdown,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/risk-check", tags=["risk-check"])

COLLECTION = "risk_leads"


def _short_id() -> str:
    return uuid.uuid4().hex[:10].upper()


# --- Request models ---


class RiskCheckStep1(BaseModel):
    property_count: int = 1
    any_hmo: bool = False
    gas_status: str  # Valid | Expired | Not sure
    eicr_status: str  # Valid | Expired | Not sure
    tracking_method: str  # Manual reminders | Spreadsheet | No structured tracking | Automated system


class RiskCheckReportRequest(RiskCheckStep1):
    first_name: str = Field(..., min_length=1)
    email: EmailStr
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None


class RiskCheckActivateRequest(BaseModel):
    """Record CTA click: lead_id and optional selected plan. Idempotent."""
    lead_id: str
    selected_plan_code: Optional[str] = None


# --- Helpers ---


def _teaser_text(risk_band: str) -> str:
    if risk_band == "HIGH":
        return "Your responses suggest elevated monitoring risk."
    if risk_band == "MODERATE":
        return "Your responses suggest moderate monitoring risk."
    return "Your responses suggest lower monitoring risk."


def _blurred_hint(risk_band: str, score: int) -> str:
    if risk_band == "HIGH":
        return "Below optimal"
    if risk_band == "MODERATE":
        return "Moderate range"
    return "Good range"


async def _send_risk_report_email(lead: dict, activation_token: Optional[str] = None) -> bool:
    """Send Email 1 (Your Compliance Risk Snapshot). Uses risk_lead_email_service. Returns True if sent or duplicate."""
    from services.risk_lead_email_service import send_risk_lead_email
    ok, _ = await send_risk_lead_email(lead, 1, activation_token=activation_token)
    return ok


# --- Endpoints ---


@router.post("/preview")
async def risk_check_preview(body: RiskCheckStep1):
    """
    Step 1: answers only, no email. Returns risk_band, teaser_text, blurred_score_hint, flags_count.
    No persistence.
    """
    if body.property_count < 1:
        body.property_count = 1
    if body.property_count > 100:
        body.property_count = 100

    result = compute_risk_check_result(
        property_count=body.property_count,
        any_hmo=body.any_hmo,
        gas_status=body.gas_status or "unknown",
        eicr_status=body.eicr_status or "unknown",
        tracking_method=body.tracking_method or "manual",
    )
    return {
        "risk_band": result["risk_band"],
        "teaser_text": _teaser_text(result["risk_band"]),
        "blurred_score_hint": _blurred_hint(result["risk_band"], result["score"]),
        "flags_count": len(result["flags"]),
        "recommended_plan_code": result.get("recommended_plan_code", "PLAN_2_PORTFOLIO"),
    }


@router.post("/report")
async def risk_check_report(body: RiskCheckReportRequest, request: Request):
    """
    Step 1 + name + email. Upsert risk_leads by email, return full report + lead_id.
    Sends 'Your Compliance Risk Snapshot' email with Activate Monitoring link (lead_token for prefill).
    """
    if body.property_count < 1:
        body.property_count = 1
    if body.property_count > 100:
        body.property_count = 100

    result = compute_risk_check_result(
        property_count=body.property_count,
        any_hmo=body.any_hmo,
        gas_status=body.gas_status or "unknown",
        eicr_status=body.eicr_status or "unknown",
        tracking_method=body.tracking_method or "manual",
    )

    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    email_lower = body.email.strip().lower()

    doc = {
        "updated_at": now_iso,
        "first_name": (body.first_name or "").strip()[:200],
        "email": email_lower,
        "property_count": body.property_count,
        "any_hmo": body.any_hmo,
        "gas_status": body.gas_status,
        "eicr_status": body.eicr_status,
        "tracking_method": body.tracking_method,
        "computed_score": result["score"],
        "risk_band": result["risk_band"],
        "exposure_range_label": result["exposure_range_label"],
        "flags": result["flags"],
        "disclaimer_text": result["disclaimer_text"],
        "recommended_plan_code": result.get("recommended_plan_code", "PLAN_2_PORTFOLIO"),
        "status": "new",
        "email_sequence_step": 0,
        "last_email_sent_at": None,
    }
    if body.utm_source is not None:
        doc["utm_source"] = (str(body.utm_source) or "").strip()[:200]
    if body.utm_medium is not None:
        doc["utm_medium"] = (str(body.utm_medium) or "").strip()[:200]
    if body.utm_campaign is not None:
        doc["utm_campaign"] = (str(body.utm_campaign) or "").strip()[:200]
    doc["source"] = "homepage_risk_check"

    db = database.get_db()
    from utils.risk_lead_token import create_lead_token

    existing = await db[COLLECTION].find_one({"email": email_lower})
    if existing:
        lead_id = existing["lead_id"]
        update_fields = {k: v for k, v in doc.items() if k not in ("lead_id", "created_at")}
        await db[COLLECTION].update_one({"lead_id": lead_id}, {"$set": update_fields})
        doc["lead_id"] = lead_id
        doc["created_at"] = existing.get("created_at", now_iso)
    else:
        lead_id = f"RISK-{_short_id()}"
        doc["lead_id"] = lead_id
        doc["created_at"] = now_iso
        await db[COLLECTION].insert_one(doc)

    activation_token = create_lead_token(lead_id)
    sent = await _send_risk_report_email(doc, activation_token)
    if sent:
        await db[COLLECTION].update_one(
            {"lead_id": lead_id},
            {
                "$set": {
                    "email_sequence_step": 1,
                    "last_email_sent_at": now_iso,
                    "last_activation_link_sent_at": now_iso,
                    "status": "nurture_started",
                }
            },
        )

    # Simulated property breakdown for frontend
    property_breakdown = simulated_property_breakdown(
        body.property_count,
        result["score"],
        body.gas_status,
        body.eicr_status,
        body.tracking_method,
    )

    return {
        "lead_id": lead_id,
        "score": result["score"],
        "risk_band": result["risk_band"],
        "exposure_range_label": result["exposure_range_label"],
        "flags": result["flags"],
        "disclaimer_text": result["disclaimer_text"],
        "property_breakdown": property_breakdown,
        "recommended_plan_code": result.get("recommended_plan_code", "PLAN_2_PORTFOLIO"),
    }


@router.get("/lead-from-token")
async def risk_check_lead_from_token(lead_token: Optional[str] = None):
    """
    Verify lead_token (signed, expiry e.g. 7 days) and return sanitized lead payload for intake prefill only.
    Does not return risk score or exposure numbers. Returns 401 when token missing/invalid/expired.
    """
    from utils.risk_lead_token import verify_lead_token

    if not (lead_token or "").strip():
        raise HTTPException(status_code=400, detail="lead_token is required")
    lead_id = verify_lead_token(lead_token)
    if not lead_id:
        raise HTTPException(status_code=401, detail="Invalid or expired link. Request a new report from the risk check.")
    db = database.get_db()
    lead = await db[COLLECTION].find_one({"lead_id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    # Sanitized payload for intake prefill only (no score, no exposure)
    return {
        "lead_id": lead.get("lead_id"),
        "email": lead.get("email") or "",
        "first_name": lead.get("first_name"),
        "full_name": (lead.get("full_name") or lead.get("first_name") or "").strip() or None,
        "phone": lead.get("phone"),
        "property_count": lead.get("property_count"),
        "any_hmo": lead.get("any_hmo"),
        "gas_status": lead.get("gas_status"),
        "eicr_status": lead.get("eicr_status"),
        "tracking_method": lead.get("tracking_method"),
    }


@router.post("/activate")
async def risk_check_activate(body: RiskCheckActivateRequest):
    """
    Record that a lead clicked the CTA (Activate Monitoring). Sets status to activated_cta.
    Idempotent: only if current status is 'new' or 'activated_cta'.
    Does not create client or trigger provisioning.
    """
    db = database.get_db()
    result = await db[COLLECTION].update_one(
        {"lead_id": body.lead_id, "status": {"$in": ["new", "activated_cta", "nurture_started"]}},
        {"$set": {"status": "activated_cta", "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    if result.matched_count == 0:
        logger.warning("Risk check activate: lead not found or already past CTA lead_id=%s", body.lead_id)
    return {"ok": True}
