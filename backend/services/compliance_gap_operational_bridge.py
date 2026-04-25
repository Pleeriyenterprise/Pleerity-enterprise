"""
Operational bridge: idempotent maintenance issues + audit from persisted compliance gaps.

Conservative automation — no silent work-order creation (booking stays client-led / routed URLs).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from models import AuditAction
from utils.audit import create_audit_log

logger = logging.getLogger(__name__)


async def _issue_exists_for_gap(db, client_id: str, gap_key: str) -> bool:
    n = await db.maintenance_issues.count_documents(
        {
            "client_id": client_id,
            "operational_root_key": gap_key,
            "status": {"$nin": ["resolved", "closed", "cancelled"]},
        }
    )
    return n > 0


async def apply_gap_operational_bridge(
    db,
    gap_rows: List[Dict[str, Any]],
    requirement: Dict[str, Any],
) -> None:
    """Create system-tracked issues when policy requests and gap is open; fully idempotent per gap_key."""
    cid = str(requirement.get("client_id") or "")
    pid = str(requirement.get("property_id") or "")
    if not cid or not pid:
        return

    for row in gap_rows:
        if (row.get("status") or "open") != "open":
            continue
        pol = row.get("policy") if isinstance(row.get("policy"), dict) else {}
        if not pol.get("create_issue_if_open"):
            continue
        gk = row.get("gap_key")
        if not gk:
            continue
        if await _issue_exists_for_gap(db, cid, str(gk)):
            continue
        try:
            from services import maintenance_issues_service as mis
            from services import maintenance_service as msrv

            title = row.get("title") or "Compliance gap"
            desc = f"{row.get('description') or ''}\n\nGap: {row.get('gap_kind')} ({row.get('severity')}). Key: {gk}"
            await mis.create_issue(
                client_id=cid,
                property_id=pid,
                description=desc[:4000],
                source=mis.SOURCE_SYSTEM,
                category=msrv.CATEGORY_GENERAL,
                created_from=mis.CREATED_FROM_COMPLIANCE,
                operational_root_key=str(gk),
                triggering_rule=f"compliance_gap:{row.get('gap_kind')}",
                reported_urgency=str(row.get("severity") or "medium").lower(),
            )
            await create_audit_log(
                action=AuditAction.COMPLIANCE_GAP_ISSUE_CREATED,
                actor_id=None,
                client_id=cid,
                resource_type="compliance_gap",
                resource_id=str(gk),
                metadata={
                    "requirement_id": requirement.get("requirement_id"),
                    "gap_kind": row.get("gap_kind"),
                    "severity": row.get("severity"),
                    "operational_root_key": str(gk),
                },
            )
        except Exception as e:
            logger.warning("gap bridge create_issue failed gap_key=%s: %s", gk, e)
