"""
Provisioning status hook: after property create/update, write provisioning_status per module.
Does NOT generate obligations; only records not_configured | configured | blocked and missing_fields[].
"""
from typing import List
from database import database
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

COLLECTION = "provisioning_status"
MODULE_COMPLIANCE = "compliance"
MODULE_MAINTENANCE = "maintenance"


def _property_missing_fields(prop: dict) -> List[str]:
    """Return list of missing field names for compliance/module readiness."""
    missing = []
    if not prop.get("jurisdiction") and not prop.get("local_authority"):
        missing.append("jurisdiction")
    # has_gas_supply, floors, property_type optional for MVP
    return missing


async def update_provisioning_status_for_property(client_id: str, property_id: str) -> None:
    """
    Called after property create or update. Writes provisioning_status for compliance and maintenance.
    status: not_configured | configured | blocked. missing_fields: list of field names.
    """
    db = database.get_db()
    prop = await db.properties.find_one(
        {"property_id": property_id, "client_id": client_id},
        {"_id": 0, "property_id": 1, "client_id": 1, "jurisdiction": 1, "local_authority": 1, "has_gas_supply": 1},
    )
    if not prop:
        return
    now = datetime.now(timezone.utc).isoformat()
    missing = _property_missing_fields(prop)
    status = "blocked" if missing else "configured"
    for module_name in (MODULE_COMPLIANCE, MODULE_MAINTENANCE):
        await db[COLLECTION].update_one(
            {"client_id": client_id, "property_id": property_id, "module_name": module_name},
            {
                "$set": {
                    "status": status,
                    "missing_fields": missing,
                    "updated_at": now,
                }
            },
            upsert=True,
        )
    logger.debug("Provisioning status updated client_id=%s property_id=%s status=%s", client_id, property_id, status)
