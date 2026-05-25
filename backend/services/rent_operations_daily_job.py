"""Daily rent operations worker — recalc, period generation, reminders, risk signals."""
import logging
from typing import Any, Dict, Optional

from database import database
from services.ops_compliance_feature_flags import get_effective_flags, RENT_OPERATIONS
from services import rent_ledger_service
from services import rent_reminder_service
from services import rent_operations_risk_hooks
from services.rent_tenancy_authority_service import (
    COLLECTION_TENANCIES,
    TENANCY_STATUS_ACTIVE,
    TENANCY_STATUS_ENDING_SOON,
)
from services.job_run_service import OUTCOME_DEGRADED, OUTCOME_SUCCESS

logger = logging.getLogger(__name__)


async def run_rent_operations_daily_for_client(client_id: str) -> Dict[str, Any]:
    db = database.get_db()
    flags = await get_effective_flags(client_id)
    if not flags.get(RENT_OPERATIONS):
        return {"skipped": True, "reason": "RENT_OPERATIONS disabled"}

    recalc_result = await rent_ledger_service.recalculate_all_active_ledgers(
        client_id, write_audit=False
    )

    schedules = await db.rent_schedules.find(
        {"client_id": client_id, "is_active": True},
        {"_id": 0},
    ).to_list(500)
    periods_created = 0
    for schedule in schedules:
        tid = schedule.get("tenancy_id")
        if tid and not str(tid).startswith("ext_"):
            tenancy = await db[COLLECTION_TENANCIES].find_one(
                {"tenancy_id": tid, "client_id": client_id},
                {"_id": 0, "status": 1},
            )
            if tenancy and tenancy.get("status") not in (
                TENANCY_STATUS_ACTIVE,
                TENANCY_STATUS_ENDING_SOON,
            ):
                continue
        periods_created += await rent_ledger_service.ensure_future_periods_for_schedule(schedule)

    reminder_result = await rent_reminder_service.process_reminders_for_client(client_id)
    risk_result = await rent_operations_risk_hooks.generate_operational_risk_signals(client_id)

    return {
        "skipped": False,
        "recalculated": recalc_result,
        "periods_created": periods_created,
        "reminders": reminder_result,
        "risk_signals": risk_result,
    }


async def run_rent_operations_daily_job(client_id: Optional[str] = None) -> Dict[str, Any]:
    """Scheduled job entry point."""
    db = database.get_db()
    if client_id:
        clients = await db.clients.find({"client_id": client_id}, {"_id": 0, "client_id": 1}).to_list(1)
        if not clients:
            return {
                "message": "No client found",
                "outcome_status": "failed",
                "count": 0,
            }
    else:
        clients = await db.clients.find({}, {"_id": 0, "client_id": 1}).to_list(5000)

    processed = 0
    skipped = 0
    failed = 0
    errors: list = []

    for c in clients:
        cid = c["client_id"]
        try:
            result = await run_rent_operations_daily_for_client(cid)
            if result.get("skipped"):
                skipped += 1
            else:
                processed += 1
        except Exception as exc:
            failed += 1
            logger.exception("rent_operations_daily_job failed client_id=%s", cid)
            errors.append({"client_id": cid, "error": str(exc)[:500]})

    outcome_status = OUTCOME_SUCCESS
    if failed and processed:
        outcome_status = OUTCOME_DEGRADED
    elif failed and not processed:
        outcome_status = "failed"

    return {
        "message": (
            f"Rent operations daily: processed={processed} skipped={skipped} failed={failed}"
        ),
        "count": processed,
        "outcome_status": outcome_status,
        "outcome_metrics": {
            "processed": processed,
            "skipped_no_flag": skipped,
            "clients_failed": failed,
            "errors": errors[:20],
        },
    }
