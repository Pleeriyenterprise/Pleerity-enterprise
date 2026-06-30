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

            from services.customer_operational_language_service import (
                derive_customer_safe_issue_detail,
                derive_customer_safe_issue_summary,
            )

            title = derive_customer_safe_issue_summary(
                {
                    "description": row.get("description") or row.get("title"),
                    "triggering_rule": f"compliance_gap:{row.get('gap_kind')}",
                    "created_from": "compliance",
                    "operational_root_key": str(gk),
                }
            )
            desc = derive_customer_safe_issue_detail(
                {
                    "description": row.get("description") or row.get("title"),
                    "triggering_rule": f"compliance_gap:{row.get('gap_kind')}",
                    "created_from": "compliance",
                }
            )
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


async def resolve_issues_for_resolved_gaps(
    db,
    client_id: str,
    resolved_gap_rows: List[Dict[str, Any]],
    *,
    requirement: Optional[Dict[str, Any]] = None,
    actor_id: str = "system",
) -> List[str]:
    """Auto-close bridge issues when compliance gaps transition to resolved."""
    from services.document_linkage_lifecycle_authority import (
        AUTO_RESOLVE_GAP_KINDS,
        RESOLUTION_SOURCE_GAP_RESOLVED,
        resolve_operational_issues_for_gap_keys,
    )

    gap_keys: List[str] = []
    meta_base: Dict[str, Any] = {}
    if requirement:
        meta_base["requirement_id"] = requirement.get("requirement_id")
        meta_base["property_id"] = requirement.get("property_id")

    for row in resolved_gap_rows or []:
        gk = str(row.get("gap_key") or "").strip()
        gk_kind = str(row.get("gap_kind") or "").strip().upper()
        if not gk:
            continue
        if gk_kind and gk_kind not in AUTO_RESOLVE_GAP_KINDS:
            continue
        gap_keys.append(gk)

    if not gap_keys:
        return []

    return await resolve_operational_issues_for_gap_keys(
        db,
        client_id,
        gap_keys,
        resolution_source=RESOLUTION_SOURCE_GAP_RESOLVED,
        resolution_metadata={**meta_base, "gap_kind": resolved_gap_rows[0].get("gap_kind") if resolved_gap_rows else None},
        actor_id=actor_id,
    )
