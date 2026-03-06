"""
Operations & Compliance module feature flags.
Org-level (client_id) flags with defaults derived from plan.
Keys: COMPLIANCE_ENGINE, COMPLIANCE_PACKS, MAINTENANCE_WORKFLOWS,
PREDICTIVE_MAINTENANCE, CONTRACTOR_NETWORK, INVOICING.
"""
from typing import Dict, List, Optional, Any
from database import database
import logging

logger = logging.getLogger(__name__)

COLLECTION = "client_feature_flags"

# Module keys (spec)
COMPLIANCE_ENGINE = "COMPLIANCE_ENGINE"
COMPLIANCE_PACKS = "COMPLIANCE_PACKS"
MAINTENANCE_WORKFLOWS = "MAINTENANCE_WORKFLOWS"
PREDICTIVE_MAINTENANCE = "PREDICTIVE_MAINTENANCE"
CONTRACTOR_NETWORK = "CONTRACTOR_NETWORK"
INVOICING = "INVOICING"

ALL_FLAG_KEYS = [
    COMPLIANCE_ENGINE,
    COMPLIANCE_PACKS,
    MAINTENANCE_WORKFLOWS,
    PREDICTIVE_MAINTENANCE,
    CONTRACTOR_NETWORK,
    INVOICING,
]

# Plan codes (match plan_registry)
PLAN_1_SOLO = "PLAN_1_SOLO"
PLAN_2_PORTFOLIO = "PLAN_2_PORTFOLIO"
PLAN_3_PRO = "PLAN_3_PRO"

# Defaults by plan: Solo = compliance only; Portfolio = + optional maintenance; Pro = + maintenance on, contractor optional
DEFAULTS_BY_PLAN: Dict[str, Dict[str, bool]] = {
    PLAN_1_SOLO: {
        COMPLIANCE_ENGINE: True,
        COMPLIANCE_PACKS: True,
        MAINTENANCE_WORKFLOWS: False,
        PREDICTIVE_MAINTENANCE: False,
        CONTRACTOR_NETWORK: False,
        INVOICING: False,
    },
    PLAN_2_PORTFOLIO: {
        COMPLIANCE_ENGINE: True,
        COMPLIANCE_PACKS: True,
        MAINTENANCE_WORKFLOWS: False,  # optional flag
        PREDICTIVE_MAINTENANCE: False,
        CONTRACTOR_NETWORK: False,
        INVOICING: False,
    },
    PLAN_3_PRO: {
        COMPLIANCE_ENGINE: True,
        COMPLIANCE_PACKS: True,
        MAINTENANCE_WORKFLOWS: True,
        PREDICTIVE_MAINTENANCE: False,
        CONTRACTOR_NETWORK: False,  # optional
        INVOICING: False,
    },
}

# Human-readable labels for admin UI
FLAG_LABELS: Dict[str, str] = {
    COMPLIANCE_ENGINE: "Compliance Engine",
    COMPLIANCE_PACKS: "Compliance Packs",
    MAINTENANCE_WORKFLOWS: "Maintenance Workflows",
    PREDICTIVE_MAINTENANCE: "Predictive Maintenance",
    CONTRACTOR_NETWORK: "Contractor Network",
    INVOICING: "Invoicing",
}


def _defaults_for_plan(plan_code: Optional[str]) -> Dict[str, bool]:
    if not plan_code:
        return DEFAULTS_BY_PLAN[PLAN_1_SOLO].copy()
    return DEFAULTS_BY_PLAN.get(plan_code, DEFAULTS_BY_PLAN[PLAN_1_SOLO]).copy()


async def get_effective_flags(client_id: str, plan_code: Optional[str] = None) -> Dict[str, bool]:
    """
    Return effective feature flags for a client: plan defaults merged with overrides.
    If plan_code not provided, will try to read from client doc.
    """
    db = database.get_db()
    defaults = _defaults_for_plan(plan_code)
    overrides = await db[COLLECTION].find({"client_id": client_id}).to_list(100)
    result = defaults.copy()
    for row in overrides:
        key = row.get("flag_key")
        if key in result:
            result[key] = bool(row.get("enabled", False))
    return result


async def get_effective_flags_with_meta(
    client_id: str, plan_code: Optional[str] = None
) -> Dict[str, Any]:
    """Effective flags plus source (plan_default | override) per key for admin UI."""
    db = database.get_db()
    defaults = _defaults_for_plan(plan_code)
    overrides = await db[COLLECTION].find({"client_id": client_id}).to_list(100)
    override_map = {r["flag_key"]: r for r in overrides if r.get("flag_key") in defaults}
    result = []
    for key in ALL_FLAG_KEYS:
        if key in override_map:
            result.append({
                "flag_key": key,
                "label": FLAG_LABELS.get(key, key),
                "enabled": bool(override_map[key].get("enabled", False)),
                "source": override_map[key].get("source", "manual"),
                "updated_at": override_map[key].get("updated_at"),
                "updated_by": override_map[key].get("updated_by"),
            })
        else:
            result.append({
                "flag_key": key,
                "label": FLAG_LABELS.get(key, key),
                "enabled": defaults[key],
                "source": "plan_default",
                "updated_at": None,
                "updated_by": None,
            })
    return {"flags": result, "plan_code": plan_code}


async def set_flag(
    client_id: str,
    flag_key: str,
    enabled: bool,
    updated_by: str,
    source: str = "manual",
) -> None:
    """Set one flag override for a client. Only Owner/Admin should call."""
    if flag_key not in ALL_FLAG_KEYS:
        raise ValueError(f"Unknown flag_key: {flag_key}")
    db = database.get_db()
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    await db[COLLECTION].update_one(
        {"client_id": client_id, "flag_key": flag_key},
        {
            "$set": {
                "enabled": enabled,
                "source": source,
                "updated_by": updated_by,
                "updated_at": now,
            }
        },
        upsert=True,
    )
    logger.info("Feature flag set client_id=%s flag_key=%s enabled=%s", client_id, flag_key, enabled)
