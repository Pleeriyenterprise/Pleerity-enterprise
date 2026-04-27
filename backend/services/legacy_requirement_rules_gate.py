"""
Legacy Mongo ``requirement_rules`` admin CRUD is retired in favour of the published Compliance Policy Registry.

Mutations are gated by environment + owner role + confirmation header; reads remain available for audit.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List

from fastapi import HTTPException, Request, status

from models import UserRole

MAINTENANCE_ENV_VAR = "LEGACY_REQUIREMENT_RULES_MAINTENANCE"
MAINTENANCE_HEADER = "X-Legacy-Requirement-Rules-Maintenance"


def legacy_maintenance_enabled_in_environment() -> bool:
    val = (os.environ.get(MAINTENANCE_ENV_VAR) or "").strip().lower()
    return val in ("1", "true", "yes")


def assert_legacy_rule_mutations_allowed(request: Request, user: Dict[str, Any]) -> None:
    """
    Emergency-only edits to ungoverned legacy rows: infra enables LEGACY_REQUIREMENT_RULES_MAINTENANCE,
    caller must be ROLE_OWNER and send X-Legacy-Requirement-Rules-Maintenance: 1.
    """
    if not legacy_maintenance_enabled_in_environment():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Legacy requirement rule mutations are disabled (registry-first mode). "
                "Use Compliance Engine → Policy Registry to publish policy. "
                "Emergency Mongo fixes require LEGACY_REQUIREMENT_RULES_MAINTENANCE on the server "
                "plus Owner confirmation header."
            ),
        )
    role = str(user.get("role") or "").strip()
    if role != UserRole.ROLE_OWNER.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only ROLE_OWNER may perform legacy requirement rule mutations when maintenance mode is enabled.",
        )
    hdr = (request.headers.get(MAINTENANCE_HEADER) or "").strip()
    if hdr != "1":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Send header {MAINTENANCE_HEADER}: 1 with each legacy mutation request.",
        )


async def build_requirement_rules_conflict_summary(db) -> Dict[str, Any]:
    """
    Read-only aggregate for admins: overlap between governed published rows and legacy ungoverned rows,
    plus supplemental ungoverned rules that affect provisioning.
    """
    governed = await db.requirement_rules.find({"governed": True}, {"_id": 0, "rule_type": 1, "rule_id": 1, "name": 1}).to_list(2000)
    gov_by_type: Dict[str, Dict[str, Any]] = {}
    for g in governed:
        rt = str(g.get("rule_type") or "").strip().lower()
        if rt:
            gov_by_type[rt] = g

    ungov = await db.requirement_rules.find(
        {"$or": [{"governed": {"$exists": False}}, {"governed": {"$ne": True}}]},
        {"_id": 0},
    ).to_list(2000)

    overlap_rows: List[Dict[str, Any]] = []
    ungoverned_active_supplemental: List[Dict[str, Any]] = []
    types_blocking_publish: List[str] = []

    for row in ungov:
        rt = str(row.get("rule_type") or "").strip().lower()
        if not rt:
            continue
        active = bool(row.get("is_active", True))
        slim = {
            "rule_id": row.get("rule_id"),
            "rule_type": rt,
            "name": row.get("name"),
            "is_active": active,
            "governed": bool(row.get("governed")),
        }
        if rt in gov_by_type:
            overlap_rows.append({**slim, "governed_peer_name": gov_by_type[rt].get("name")})
        elif active:
            ungoverned_active_supplemental.append(slim)

        # First governed publish for this rule_type fails while any ungoverned row exists (see governed publish).
        if active:
            types_blocking_publish.append(rt)

    types_blocking_publish = sorted(set(types_blocking_publish))

    return {
        "governed_published_count": len(governed),
        "ungoverned_row_count": len(ungov),
        "overlap_governed_and_ungoverned": overlap_rows,
        "overlap_count": len(overlap_rows),
        "ungoverned_active_supplemental_count": len(ungoverned_active_supplemental),
        "ungoverned_active_supplemental_preview": ungoverned_active_supplemental[:50],
        "distinct_active_ungoverned_rule_types": types_blocking_publish,
        "publish_block_note": (
            "Publishing a governed version for rule_type T inserts/replaces requirement_rules with governed=true; "
            "if any ungoverned row exists for T, publish raises until that legacy row is resolved."
        ),
    }
