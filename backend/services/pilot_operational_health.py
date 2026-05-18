"""Deterministic pilot operational health scoring (no LLM)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from models.pilot_lifecycle import PilotStatus
from models.pilot_operational import PilotHealthBand
from services.pilot_conversion_risk import compute_conversion_risk_flags


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


async def _count_documents(client_id: str) -> int:
    try:
        from database import database

        db = database.get_db()
        return await db.documents.count_documents({"client_id": client_id})
    except Exception:
        return 0


async def _recent_activity(client_id: str, days: int = 30) -> bool:
    try:
        from database import database

        db = database.get_db()
        since = _utc_now().replace(hour=0, minute=0, second=0, microsecond=0)
        from datetime import timedelta

        since = since - timedelta(days=days)
        n = await db.compliance_activity_log.count_documents(
            {"client_id": client_id, "created_at": {"$gte": since.isoformat()}}
        )
        if n > 0:
            return True
        n2 = await db.analytics_events.count_documents(
            {"client_id": client_id, "timestamp": {"$gte": since}}
        )
        return n2 > 0
    except Exception:
        return False


def compute_pilot_health(
    client: Dict[str, Any],
    *,
    billing: Optional[Dict[str, Any]] = None,
    document_count: int = 0,
    has_recent_activity: bool = False,
) -> Dict[str, Any]:
    risk = compute_conversion_risk_flags(client, billing=billing)
    flags: List[str] = []
    score = 0

    onboarding_done = risk.get("onboarding_completed")
    if onboarding_done:
        score += 20
    else:
        flags.append("onboarding_incomplete")

    if document_count > 0:
        score += 15
    else:
        flags.append("no_documents_uploaded")

    if has_recent_activity:
        score += 20
    else:
        flags.append("no_recent_activity")

    if risk.get("payment_method_collected"):
        score += 20
    else:
        flags.append("missing_payment_method")

    status = str(client.get("pilot_status") or "").lower()
    if status in (PilotStatus.ACTIVE.value, PilotStatus.EXTENDED.value):
        score += 10

    if risk.get("likely_conversion"):
        score += 15
        flags.append("conversion_ready_signal")

    days = risk.get("days_remaining")
    if days is not None and days <= 7 and not has_recent_activity and status in (
        PilotStatus.ACTIVE.value,
        PilotStatus.EXTENDED.value,
    ):
        flags.append("expiring_without_engagement")
        score = max(0, score - 15)

    if risk.get("likely_churn") or risk.get("pilot_expired_without_conversion"):
        flags.append("conversion_at_risk")
        score = max(0, score - 20)

    band = PilotHealthBand.HEALTHY.value
    if risk.get("likely_conversion") and onboarding_done and risk.get("payment_method_collected"):
        band = PilotHealthBand.CONVERSION_READY.value
    elif score < 40 or risk.get("likely_churn"):
        band = PilotHealthBand.INACTIVE.value if score < 25 else PilotHealthBand.AT_RISK.value
    elif score < 60 or flags:
        band = PilotHealthBand.AT_RISK.value

    return {
        "pilot_health_score": min(100, max(0, score)),
        "pilot_health_band": band,
        "pilot_health_flags": flags,
        "conversion_risk": risk,
    }


async def compute_pilot_health_async(
    client: Dict[str, Any],
    *,
    billing: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    cid = str(client.get("client_id") or "")
    doc_count = await _count_documents(cid) if cid else 0
    activity = await _recent_activity(cid) if cid else False
    return compute_pilot_health(
        client,
        billing=billing,
        document_count=doc_count,
        has_recent_activity=activity,
    )
