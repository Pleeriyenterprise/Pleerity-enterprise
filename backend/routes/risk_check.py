"""
Compliance Risk Check – standalone conversion demo.
No client creation, no provisioning, no Stripe. Two endpoints: preview (no PII), report (persist + optional email).
"""
from fastapi import APIRouter, HTTPException, Request
from database import database
from datetime import datetime, timezone
from typing import Optional, List, Any
from pydantic import BaseModel, EmailStr
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
    first_name: str
    email: EmailStr
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None


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


async def _send_risk_report_email(lead: dict) -> bool:
    """Send 'Your Compliance Risk Snapshot' email. Returns True if sent or duplicate."""
    first_name = lead.get("first_name") or "there"
    email = lead.get("email")
    score = lead.get("computed_score", 0)
    risk_band = lead.get("risk_band", "MODERATE")
    lead_id = lead.get("lead_id", "")
    base_url = os.environ.get("FRONTEND_URL", os.environ.get("ADMIN_DASHBOARD_URL", "")).rstrip("/").replace("/admin/leads", "")
    activate_url = f"{base_url}/intake/start" if base_url else "/intake/start"

    body_html = f"""
<p>Hello {first_name},</p>
<p>Thank you for using the Pleerity Compliance Risk Check.</p>
<p>Based on your responses, your monitoring posture is currently assessed as:</p>
<ul>
<li><strong>Compliance Score:</strong> {score}%</li>
<li><strong>Risk Level:</strong> {risk_band}</li>
</ul>
<p>Your structured report indicates areas where monitoring gaps may exist.</p>
<p>Continuous compliance monitoring helps reduce missed renewals and documentation vulnerabilities by providing structured tracking across your portfolio.</p>
<p>You can activate monitoring at any time here:</p>
<p><a href="{activate_url}">Activate Monitoring</a></p>
<p>This report is an informational indicator only and does not replace professional or legal advice.</p>
<p>Regards,<br/>Pleerity Compliance Vault Pro</p>
""".strip()

    try:
        from services.notification_orchestrator import notification_orchestrator
        idempotency_key = f"risk_report_{lead_id}_{datetime.now(timezone.utc).strftime('%Y-%m-%d')}"
        result = await notification_orchestrator.send(
            template_key="LEAD_FOLLOWUP",
            client_id=None,
            context={
                "recipient": email,
                "subject": "Your Compliance Risk Snapshot",
                "message": body_html,
            },
            idempotency_key=idempotency_key,
            event_type="risk_check_report",
        )
        return result.outcome in ("sent", "duplicate_ignored")
    except Exception as e:
        logger.warning("Risk report email not sent: %s", e)
        return False


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
    }


@router.post("/report")
async def risk_check_report(body: RiskCheckReportRequest, request: Request):
    """
    Step 1 + name + email. Persist to risk_leads, return full report + lead_id.
    Optionally send 'Your Compliance Risk Snapshot' email.
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

    lead_id = f"RISK-{_short_id()}"
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()

    doc = {
        "lead_id": lead_id,
        "created_at": now_iso,
        "first_name": (body.first_name or "").strip()[:200],
        "email": body.email.strip().lower(),
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
    }
    if body.utm_source is not None:
        doc["utm_source"] = (str(body.utm_source) or "").strip()[:200]
    if body.utm_medium is not None:
        doc["utm_medium"] = (str(body.utm_medium) or "").strip()[:200]
    if body.utm_campaign is not None:
        doc["utm_campaign"] = (str(body.utm_campaign) or "").strip()[:200]

    db = database.get_db()
    await db[COLLECTION].insert_one(doc)

    # Optional: send report email
    await _send_risk_report_email(doc)

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
    }
