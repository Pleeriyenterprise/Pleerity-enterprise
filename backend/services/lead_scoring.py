"""
Lead Scoring Engine

Numeric lead_score (0-100) from engagement, urgency, and portfolio value signals.
Stage advancement by score bands. Used by lead_service after create/update; recalc on activity.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional

from services.lead_models import (
    LeadSourcePlatform,
    LeadServiceInterest,
    LeadStage,
    LeadIntentScore,
    LeadStatus,
    FollowUpStatus,
)

logger = logging.getLogger(__name__)

# ---- Engagement ----
SCORE_WEBSITE_FORM = 10
SCORE_COMPLIANCE_RISK_CHECK = 20
SCORE_CHATBOT_CAPTURE = 8
SCORE_CONSULTATION_REQUEST = 25
SCORE_PRICING_PAGE = 10
SCORE_DOCUMENT_PACK = 15
SCORE_EMAIL_OPENED = 3
SCORE_EMAIL_LINK_CLICKED = 8
SCORE_AUTOMATION_ENQUIRY = 20
# Intent base (when no other engagement is as strong)
SCORE_INTENT_HIGH = 40
SCORE_INTENT_MEDIUM = 25
SCORE_INTENT_LOW = 10

# ---- Urgency ----
SCORE_HIGH_RISK = 30
SCORE_MEDIUM_RISK = 20

# ---- Portfolio value ----
SCORE_PORTFOLIO_1 = 5
SCORE_PORTFOLIO_2_5 = 15
SCORE_PORTFOLIO_6_20 = 30
SCORE_PORTFOLIO_20_PLUS = 50
SCORE_USER_TYPE_AGENT_OR_PM = 40

# ---- Negative ----
SCORE_NO_ACTIVITY_30_DAYS = -15
SCORE_UNSUBSCRIBE = -10

# Stage bands (task: 0-19 new, 20-39 qualified, 40-59 nurturing, 60-79 sales_ready, 80+ hot as alert only)
SCORE_BAND_NEW = (0, 19)
SCORE_BAND_QUALIFIED = (20, 39)
SCORE_BAND_NURTURING = (40, 59)
SCORE_BAND_SALES_READY = (60, 100)

# Hot lead alert threshold (trigger internal alert; stage remains SALES_READY)
HOT_LEAD_SCORE_THRESHOLD = 80


def _parse_source_platform(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return getattr(value, "value", None)


def _parse_service_interest(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return getattr(value, "value", None)


def _parse_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except Exception:
            return None
    return None


def calculate_lead_score_from_signals(
    source_platform: Optional[str] = None,
    service_interest: Optional[str] = None,
    intent_score: Optional[str] = None,
    portfolio_size: Optional[int] = None,
    risk_level: Optional[str] = None,
    risk_score: Optional[int] = None,
    user_type: Optional[str] = None,
    source_metadata: Optional[Dict[str, Any]] = None,
    tags: Optional[list] = None,
    last_activity_at: Any = None,
    followup_status: Optional[str] = None,
    status: Optional[str] = None,
) -> int:
    """
    Compute numeric lead_score 0-100 from stored signals.
    Does not persist; returns the score only.
    """
    score = 0
    tags = tags or []
    source_metadata = source_metadata or {}

    # --- Engagement ---
    # Intent base (applied when we have intent_score; other signals add on top)
    if intent_score:
        intent_map = {
            LeadIntentScore.HIGH.value: SCORE_INTENT_HIGH,
            LeadIntentScore.MEDIUM.value: SCORE_INTENT_MEDIUM,
            LeadIntentScore.LOW.value: SCORE_INTENT_LOW,
        }
        score += intent_map.get(str(intent_score).upper(), SCORE_INTENT_LOW)

    if source_platform == LeadSourcePlatform.COMPLIANCE_RISK_CHECK.value:
        score += SCORE_COMPLIANCE_RISK_CHECK
    if source_platform == LeadSourcePlatform.CONTACT_FORM.value:
        score += SCORE_WEBSITE_FORM
    if source_platform == LeadSourcePlatform.WEB_CHAT.value:
        score += SCORE_CHATBOT_CAPTURE
    if source_platform == LeadSourcePlatform.PRICING_PAGE.value:
        score += SCORE_PRICING_PAGE
    if service_interest == LeadServiceInterest.DOCUMENT_PACKS.value:
        score += SCORE_DOCUMENT_PACK
    if service_interest == LeadServiceInterest.AUTOMATION.value or source_platform == LeadSourcePlatform.AUTOMATION_ENQUIRY.value:
        score += SCORE_AUTOMATION_ENQUIRY

    if "pricing_requested" in tags:
        score += SCORE_PRICING_PAGE
    if "consultation_request" in tags:
        score += SCORE_CONSULTATION_REQUEST
    if "nurture_cta_clicked" in tags:
        score += SCORE_EMAIL_LINK_CLICKED
    if "nurture_email_opened" in tags:
        score += SCORE_EMAIL_OPENED

    # --- Urgency ---
    if risk_level:
        rl = str(risk_level).upper()
        if rl == "HIGH":
            score += SCORE_HIGH_RISK
        elif rl in ("MODERATE", "MEDIUM"):
            score += SCORE_MEDIUM_RISK

    # --- Portfolio value ---
    if portfolio_size is not None:
        try:
            p = int(portfolio_size)
            if p >= 20:
                score += SCORE_PORTFOLIO_20_PLUS
            elif p >= 6:
                score += SCORE_PORTFOLIO_6_20
            elif p >= 2:
                score += SCORE_PORTFOLIO_2_5
            elif p >= 1:
                score += SCORE_PORTFOLIO_1
        except (TypeError, ValueError):
            pass

    ut = (user_type or "").strip().lower()
    if ut in ("agent", "property manager", "property_manager", "pm"):
        score += SCORE_USER_TYPE_AGENT_OR_PM

    # --- Negative ---
    if followup_status == FollowUpStatus.OPTED_OUT.value or status == LeadStatus.UNSUBSCRIBED.value:
        score += SCORE_UNSUBSCRIBE

    last_activity = _parse_datetime(last_activity_at)
    if last_activity is not None:
        now = datetime.now(timezone.utc)
        if last_activity.tzinfo is None:
            last_activity = last_activity.replace(tzinfo=timezone.utc)
        if (now - last_activity).days >= 30:
            score += SCORE_NO_ACTIVITY_30_DAYS

    return min(100, max(0, score))


def stage_from_lead_score(score: int) -> str:
    """Map numeric lead_score to suggested stage. 80+ is SALES_READY; hot alert is separate."""
    if score >= SCORE_BAND_SALES_READY[0]:
        return LeadStage.SALES_READY.value
    if score >= SCORE_BAND_NURTURING[0]:
        return LeadStage.NURTURING.value
    if score >= SCORE_BAND_QUALIFIED[0]:
        return LeadStage.QUALIFIED.value
    return LeadStage.NEW.value


def should_update_stage(lead: Dict[str, Any], suggested_stage: str) -> bool:
    """
    Return False if lead is already converted/won — never overwrite stage for converted leads.
    """
    stage = lead.get("stage")
    status = lead.get("status")
    if stage == LeadStage.WON.value or status == LeadStatus.CONVERTED.value:
        return False
    if stage == LeadStage.LOST.value:
        return False
    return True


async def recalculate_lead_score(lead: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recalculate lead_score from lead document.
    Returns dict with keys: lead_score, suggested_stage.
    Does not write to DB; caller should persist and log LEAD_SCORE_UPDATED.
    """
    source_platform = _parse_source_platform(lead.get("source_platform"))
    service_interest = _parse_service_interest(lead.get("service_interest"))
    intent_score = lead.get("intent_score")
    portfolio_size = lead.get("portfolio_size")
    if isinstance(portfolio_size, str) and portfolio_size.isdigit():
        portfolio_size = int(portfolio_size)
    risk_level = lead.get("risk_level")
    risk_score = lead.get("risk_score")
    user_type = lead.get("user_type")
    source_metadata = lead.get("source_metadata") or {}
    tags = lead.get("tags") or []
    last_activity_at = lead.get("last_activity_at")
    followup_status = lead.get("followup_status")
    status = lead.get("status")

    score = calculate_lead_score_from_signals(
        source_platform=source_platform,
        service_interest=service_interest,
        intent_score=intent_score,
        portfolio_size=portfolio_size,
        risk_level=risk_level,
        risk_score=risk_score,
        user_type=user_type,
        source_metadata=source_metadata,
        tags=tags,
        last_activity_at=last_activity_at,
        followup_status=followup_status,
        status=status,
    )
    suggested_stage = stage_from_lead_score(score)

    return {"lead_score": score, "suggested_stage": suggested_stage}
