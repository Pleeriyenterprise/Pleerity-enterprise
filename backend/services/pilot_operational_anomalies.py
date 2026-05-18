"""Persisted pilot operational anomalies — governance inconsistencies."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from database import database
from models.pilot_lifecycle import PilotStatus
from models.pilot_operational import (
    DEFAULT_MAX_COMP_DAYS_WITHOUT_REVIEW,
    DEFAULT_MAX_PILOT_GOVERNANCE_MONTHS,
    PilotAnomalyCode,
    PilotAnomalySeverity,
    PilotGovernanceStatus,
)
from services.pilot_lifecycle_domains import detect_domain_inconsistencies

logger = logging.getLogger(__name__)

COL_PILOT_ANOMALIES = "pilot_operational_anomalies"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_dt(v: Any) -> Optional[datetime]:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except ValueError:
        return None


def _severity_for_code(code: str) -> str:
    critical = {
        PilotAnomalyCode.ENTITLEMENT_WITHOUT_BILLING_BASIS.value,
        PilotAnomalyCode.INVALID_STATE_COMBINATION.value,
    }
    if code in critical:
        return PilotAnomalySeverity.CRITICAL.value
    warning = {
        PilotAnomalyCode.EXPIRED_PILOT_ACTIVE_PAID_SUB.value,
        PilotAnomalyCode.CONVERTED_WITHOUT_PAYMENT_METHOD.value,
        PilotAnomalyCode.MISSING_PAYMENT_METHOD_NEAR_CONVERSION.value,
        PilotAnomalyCode.PILOT_EXPIRED_WITHOUT_CONVERSION.value,
        PilotAnomalyCode.COMP_REVIEW_OVERDUE.value,
    }
    if code in warning:
        return PilotAnomalySeverity.WARNING.value
    return PilotAnomalySeverity.INFO.value


def _extra_anomaly_candidates(client: Dict[str, Any], billing: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    billing = billing or {}
    out: List[Dict[str, Any]] = []
    gov = str(client.get("pilot_governance_status") or client.get("pilot_status") or "").lower()

    ext_count = int(client.get("pilot_extension_count") or 0)
    if client.get("pilot_extended_until") and ext_count == 0:
        ext_count = 1
    if ext_count >= 3:
        out.append(
            {
                "code": PilotAnomalyCode.MULTIPLE_EXTENSIONS.value,
                "message": f"Pilot extended {ext_count} times",
                "extension_count": ext_count,
            }
        )

    started = _parse_dt(client.get("pilot_started_at"))
    if started:
        from services.pilot_lifecycle_service import _add_months

        max_end = _add_months(started, DEFAULT_MAX_PILOT_GOVERNANCE_MONTHS)
        if _utc_now() > max_end and gov not in (
            PilotGovernanceStatus.CONVERTED.value,
            PilotStatus.CONVERTED_TO_PAID.value,
            PilotGovernanceStatus.CANCELLED.value,
        ):
            out.append(
                {
                    "code": PilotAnomalyCode.PILOT_BEYOND_MAX_GOVERNANCE_DURATION.value,
                    "message": f"Pilot active beyond {DEFAULT_MAX_PILOT_GOVERNANCE_MONTHS} month governance window",
                }
            )

    if gov == PilotGovernanceStatus.COMPED.value or str(client.get("pilot_status") or "").lower() == PilotStatus.COMPED.value:
        comped_at = _parse_dt(client.get("pilot_comped_at"))
        review = _parse_dt(client.get("pilot_comp_review_expires_at"))
        if review and review < _utc_now():
            out.append(
                {
                    "code": PilotAnomalyCode.COMP_REVIEW_OVERDUE.value,
                    "message": "Comp governance review date has passed",
                }
            )
        elif comped_at and not review:
            if (_utc_now() - comped_at).days > DEFAULT_MAX_COMP_DAYS_WITHOUT_REVIEW:
                out.append(
                    {
                        "code": PilotAnomalyCode.EXCESSIVE_COMP_DURATION.value,
                        "message": "Comped account without review expiry exceeds policy threshold",
                    }
                )

    risk = client.get("pilot_conversion_risk") or {}
    if risk.get("missing_payment_method") and risk.get("approaching_paid_transition"):
        out.append(
            {
                "code": PilotAnomalyCode.MISSING_PAYMENT_METHOD_NEAR_CONVERSION.value,
                "message": "Payment method missing with paid transition approaching",
            }
        )

    return out


async def upsert_anomaly(
    *,
    client_id: str,
    anomaly_code: str,
    severity: str,
    context: Optional[Dict[str, Any]] = None,
    message: Optional[str] = None,
) -> str:
    db = database.get_db()
    now = _utc_now()
    idem = f"{client_id}:{anomaly_code}"
    existing = await db[COL_PILOT_ANOMALIES].find_one(
        {"idempotency_key": idem, "resolved_at": None},
        {"_id": 0, "anomaly_id": 1},
    )
    if existing:
        await db[COL_PILOT_ANOMALIES].update_one(
            {"anomaly_id": existing["anomaly_id"]},
            {
                "$set": {
                    "severity": severity,
                    "context": context or {},
                    "message": message,
                    "last_detected_at": now,
                }
            },
        )
        return str(existing["anomaly_id"])

    anomaly_id = str(uuid.uuid4())
    doc = {
        "anomaly_id": anomaly_id,
        "client_id": client_id,
        "anomaly_code": anomaly_code,
        "severity": severity,
        "message": message,
        "context": context or {},
        "detected_at": now,
        "last_detected_at": now,
        "resolved_at": None,
        "resolution_notes": None,
        "idempotency_key": idem,
    }
    await db[COL_PILOT_ANOMALIES].insert_one(doc)
    return anomaly_id


async def detect_and_persist_anomalies(
    client_id: str,
    *,
    client: Optional[Dict[str, Any]] = None,
    billing: Optional[Dict[str, Any]] = None,
) -> List[str]:
    db = database.get_db()
    if client is None:
        client = await db.clients.find_one({"client_id": client_id}, {"_id": 0})
    if not client:
        return []
    if billing is None:
        billing = await db.client_billing.find_one({"client_id": client_id}, {"_id": 0}) or {}

    candidates = detect_domain_inconsistencies(client, billing) + _extra_anomaly_candidates(client, billing)
    created: List[str] = []
    for item in candidates:
        code = str(item.get("code") or "")
        if not code:
            continue
        sev = _severity_for_code(code)
        aid = await upsert_anomaly(
            client_id=client_id,
            anomaly_code=code,
            severity=sev,
            context=item,
            message=item.get("message"),
        )
        created.append(aid)
        try:
            from services.pilot_operational_notifications import emit_pilot_operational_event

            await emit_pilot_operational_event(
                event_type="anomaly_detected",
                client_id=client_id,
                context={"anomaly_code": code, "severity": sev, "message": item.get("message")},
            )
        except Exception:
            pass
    return created


async def list_open_anomalies(
    client_id: Optional[str] = None,
    *,
    limit: int = 200,
) -> List[Dict[str, Any]]:
    db = database.get_db()
    q: Dict[str, Any] = {"resolved_at": None}
    if client_id:
        q["client_id"] = client_id
    cursor = db[COL_PILOT_ANOMALIES].find(q, {"_id": 0}).sort("detected_at", -1).limit(limit)
    return [doc async for doc in cursor]


async def resolve_anomaly(
    anomaly_id: str,
    *,
    resolution_notes: str,
    resolved_by: Optional[str] = None,
) -> bool:
    db = database.get_db()
    res = await db[COL_PILOT_ANOMALIES].update_one(
        {"anomaly_id": anomaly_id, "resolved_at": None},
        {
            "$set": {
                "resolved_at": _utc_now(),
                "resolution_notes": resolution_notes,
                "resolved_by": resolved_by,
            }
        },
    )
    return res.modified_count > 0
