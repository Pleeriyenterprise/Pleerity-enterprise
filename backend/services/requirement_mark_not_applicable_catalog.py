"""
Shared catalog-based "mark not applicable" for a property requirement row.

Used by:
- POST /api/client/properties/{property_id}/requirements/mark-not-applicable
- POST /api/properties/{property_id}/requirements/mark-not-applicable

Keeps audit, evidence authority sync, and recalc enqueue aligned with workflow API behaviour
without changing scoring formulas or queue semantics.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

from models import AuditAction
from utils.audit import create_audit_log

logger = logging.getLogger(__name__)

NOT_REQUIRED_REASON_PRESETS = ("no_gas_supply", "exempt", "not_applicable", "other")

AUDIT_REASON_MIN_LEN = 10


def _validate_inputs(requirement_code: str, not_required_preset: str, audit_free_text: str) -> None:
    from fastapi import HTTPException, status

    code = (requirement_code or "").strip()
    if not code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="requirement_code is required")
    preset = (not_required_preset or "").strip()
    if not preset or preset not in NOT_REQUIRED_REASON_PRESETS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"not_required_reason must be one of: {list(NOT_REQUIRED_REASON_PRESETS)}",
        )
    text = (audit_free_text or "").strip()
    if len(text) < AUDIT_REASON_MIN_LEN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"reason must be at least {AUDIT_REASON_MIN_LEN} characters for the audit trail",
        )


def _matches_code(row: Dict[str, Any], code_lower: str) -> bool:
    rt = (row.get("requirement_type") or "").strip().lower()
    rc = (row.get("requirement_code") or "").strip().lower()
    return rt == code_lower or rc == code_lower


async def mark_catalog_requirement_not_applicable_for_property(
    db,
    *,
    client_id: str,
    property_id: str,
    requirement_code: str,
    not_required_preset: str,
    audit_free_text: str,
    portfolio_jurisdiction: str,
) -> Tuple[str, str, bool]:
    """
    Create or update the requirement row. Returns (requirement_id, normalized_code, created).
    """
    from fastapi import HTTPException, status

    _validate_inputs(requirement_code, not_required_preset, audit_free_text)
    code_lower = requirement_code.strip().lower()
    catalog_doc = await db.requirements_catalog.find_one({"code": requirement_code.strip()}, {"_id": 0, "code": 1, "title": 1})
    if not catalog_doc:
        catalog_doc = await db.requirements_catalog.find_one({"code": code_lower}, {"_id": 0, "code": 1, "title": 1})
    if not catalog_doc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown requirement_code: {requirement_code}",
        )
    code = catalog_doc.get("code", requirement_code.strip())
    title = catalog_doc.get("title") or code
    audit_trim = audit_free_text.strip()

    reqs = await db.requirements.find(
        {"client_id": client_id, "property_id": property_id},
        {"_id": 0, "requirement_id": 1, "requirement_type": 1, "requirement_code": 1},
    ).to_list(200)
    existing_row = next((r for r in reqs if _matches_code(r, code_lower)), None)
    now = datetime.now(timezone.utc)
    preset = not_required_preset.strip()

    if existing_row:
        requirement_id = existing_row["requirement_id"]
        await db.requirements.update_one(
            {"requirement_id": requirement_id, "property_id": property_id, "client_id": client_id},
            {
                "$set": {
                    "applicability": "NOT_REQUIRED",
                    "not_required_reason": preset,
                    "not_applicable_audit_reason": audit_trim,
                    "status": "NOT_REQUIRED",
                    "jurisdiction": portfolio_jurisdiction,
                    "updated_at": now.isoformat(),
                }
            },
        )
        created = False
    else:
        requirement_id = str(uuid.uuid4())
        due_far = now + timedelta(days=365 * 10)
        doc = {
            "requirement_id": requirement_id,
            "client_id": client_id,
            "property_id": property_id,
            "requirement_type": code,
            "requirement_code": code,
            "jurisdiction": portfolio_jurisdiction,
            "description": title,
            "frequency_days": 0,
            "due_date": due_far.isoformat(),
            "status": "NOT_REQUIRED",
            "applicability": "NOT_REQUIRED",
            "not_required_reason": preset,
            "not_applicable_audit_reason": audit_trim,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }
        await db.requirements.insert_one(doc)
        created = True

    return requirement_id, code, created


async def sync_audit_enqueue_after_catalog_not_applicable(
    db,
    *,
    client_id: str,
    property_id: str,
    requirement_id: str,
    requirement_code: str,
    not_required_preset: str,
    audit_free_text: str,
    created: bool,
    actor_portal_user_id: Optional[str],
    transition_origin: str,
) -> None:
    """Evidence authority sync, audit log, async recalc enqueue (same pattern as workflow API)."""
    from services.compliance_recalc_queue import ACTOR_CLIENT, TRIGGER_PROPERTY_UPDATED
    from services.compliance_recalc_lifecycle_transition import (
        enqueue_governed_compliance_recalc as enqueue_compliance_recalc,
    )
    from services.requirement_evidence_authority import sync_requirement_evidence_authority
    from services.requirement_transition_observability import (
        attach_downstream_trigger_observation,
        ensure_requirement_transition_correlation_id,
    )

    transition_fanout: Dict[str, Any] = {}
    recalc_correlation_id = f"MARK_NOT_APPLICABLE:{requirement_id}"
    sync_correlation_id = ensure_requirement_transition_correlation_id(
        requirement_id=str(requirement_id),
        property_id=str(property_id),
        client_id=str(client_id),
        correlation_id=recalc_correlation_id,
    )
    await sync_requirement_evidence_authority(
        db,
        requirement_id,
        property_id_hint=property_id,
        correlation_id=sync_correlation_id,
        transition_origin=transition_origin,
        transition_observability_out=transition_fanout,
    )
    await create_audit_log(
        action=AuditAction.REQUIREMENT_ACTION_TRIGGERED,
        actor_id=actor_portal_user_id,
        client_id=client_id,
        resource_type="requirement",
        resource_id=requirement_id,
        metadata={
            "event": "mark_not_applicable",
            "path": "property_catalog",
            "property_id": property_id,
            "requirement_code": requirement_code,
            "reason_code": not_required_preset,
            "reason": audit_free_text.strip()[:2000],
            "created": created,
            "correlation_id": recalc_correlation_id,
        },
    )
    recalc_result = None
    recalc_exc: Optional[Exception] = None
    try:
        recalc_result = await enqueue_compliance_recalc(
            property_id=property_id,
            client_id=client_id,
            trigger_reason=TRIGGER_PROPERTY_UPDATED,
            actor_type=ACTOR_CLIENT,
            actor_id=actor_portal_user_id,
            correlation_id=recalc_correlation_id,
        )
    except Exception as exc:
        recalc_exc = exc
        logger.warning("enqueue_compliance_recalc after catalog mark_not_applicable failed: %s", exc)
    if transition_fanout:
        attach_downstream_trigger_observation(
            transition_fanout,
            downstream_target="compliance_recalc_queue.enqueue_compliance_recalc",
            trigger_mode="async_queue",
            propagation_stage="post_authority_sync",
            downstream_correlation_id=getattr(recalc_result, "correlation_id", None) if recalc_result is not None else recalc_correlation_id,
            trigger_origin=transition_origin,
            enqueue_result=recalc_result,
            enqueue_exc=recalc_exc,
        )
