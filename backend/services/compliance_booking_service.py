"""
Compliance execution booking: creates a COMPLIANCE work order (no calendar scheduling in v1).

Flows into the same contractor recommendation and client confirmation path as maintenance assignments,
with distinct semantics and payloads (inspection / renewal / certification).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from database import database
from models import AuditAction
from utils.audit import create_audit_log

from services import maintenance_service
from services.compliance_contractor_capability import default_expected_output_document_type
from services.requirement_code_registry import (
    is_bookable_compliance_requirement,
    normalize_requirement_code_strict,
)
from services.compliance_workflow_service import assert_max_one_active_compliance_job
from services.work_order_execution_constants import (
    ALLOWED_COMPLIANCE_GENERATED_FROM,
    ALLOWED_COMPLIANCE_PURPOSES,
    WORK_ORDER_KIND_COMPLIANCE,
)

logger = logging.getLogger(__name__)

_PURPOSE_LABEL = {
    "inspection": "Book compliance inspection",
    "renewal": "Renew compliance certificate",
    "certification": "Obtain compliance certification",
    "remedial": "Compliance remedial work",
}


async def create_compliance_execution_work_order(
    *,
    client_id: str,
    property_id: str,
    requirement_code_raw: str,
    compliance_purpose: str,
    compliance_generated_from: str,
    actor_portal_user_id: Optional[str],
    description_override: Optional[str] = None,
    compliance_due_at: Optional[str] = None,
    linked_property_requirement_id: Optional[str] = None,
    risk_signal_id: Optional[str] = None,
    issue_id: Optional[str] = None,
    source: str = maintenance_service.SOURCE_CLIENT,
) -> Dict[str, Any]:
    """
    Persist a compliance execution work order. Does not assign a contractor.
    Caller should invoke contractor-routing generate + confirm when ready.
    """
    purpose = (compliance_purpose or "").strip().lower()
    if purpose not in ALLOWED_COMPLIANCE_PURPOSES:
        raise ValueError(
            f"compliance_purpose must be one of: {', '.join(sorted(ALLOWED_COMPLIANCE_PURPOSES))}"
        )
    gen_from = (compliance_generated_from or "").strip().lower()
    if gen_from not in ALLOWED_COMPLIANCE_GENERATED_FROM:
        raise ValueError(
            f"compliance_generated_from must be one of: {', '.join(sorted(ALLOWED_COMPLIANCE_GENERATED_FROM))}"
        )
    canon, err = normalize_requirement_code_strict(requirement_code_raw)
    if err or not canon:
        raise ValueError(err or "Invalid requirement_code")
    if not is_bookable_compliance_requirement(canon):
        raise ValueError(
            f"Compliance execution booking is not enabled for requirement_code {canon!r}"
        )

    db = database.get_db()
    prop = await db.properties.find_one(
        {"property_id": property_id.strip(), "client_id": client_id.strip()},
        {"_id": 1},
    )
    if not prop:
        raise ValueError("Property not found for this client")

    lpr = (linked_property_requirement_id or "").strip()
    if not lpr:
        raise ValueError("linked_property_requirement_id is required for compliance execution booking")
    req_row = await db.requirements.find_one(
        {
            "requirement_id": lpr,
            "client_id": client_id.strip(),
            "property_id": property_id.strip(),
        },
        {"_id": 0, "requirement_code": 1, "requirement_type": 1},
    )
    if not req_row:
        raise ValueError("Linked property requirement not found for this property")
    row_code = normalize_requirement_code_strict(
        req_row.get("requirement_code") or req_row.get("requirement_type") or ""
    )[0]
    if row_code and row_code != canon:
        raise ValueError("requirement_code does not match linked property requirement")

    await assert_max_one_active_compliance_job(
        client_id=client_id.strip(),
        property_id=property_id.strip(),
        linked_property_requirement_id=lpr,
    )

    cat = await db.requirements_catalog.find_one({"code": canon}, {"_id": 0, "title": 1})
    title = (cat or {}).get("title") or canon.replace("_", " ").title()
    purpose_label = _PURPOSE_LABEL.get(purpose, purpose)
    default_desc = (
        f"{purpose_label}: {title} ({canon}). "
        f"This is a compliance execution work order — not a general maintenance repair."
    )
    description = (description_override or "").strip() or default_desc
    expected_doc = default_expected_output_document_type(canon)
    operational_root_key = f"compliance_execution:{canon}"

    wo = await maintenance_service.create_work_order(
        client_id=client_id.strip(),
        property_id=property_id.strip(),
        description=description,
        source=source,
        reporter_id=actor_portal_user_id,
        severity=maintenance_service.SEVERITY_MEDIUM,
        risk_signal_id=risk_signal_id,
        issue_id=issue_id,
        created_from=compliance_generated_from,
        triggering_rule="compliance_execution_booking",
        operational_root_key=operational_root_key,
        use_triage=False,
        work_order_kind=WORK_ORDER_KIND_COMPLIANCE,
        requirement_code=canon,
        compliance_purpose=purpose,
        compliance_due_at=compliance_due_at,
        compliance_generated_from=gen_from,
        expected_output_document_type=expected_doc,
        linked_property_requirement_id=linked_property_requirement_id,
    )

    try:
        await create_audit_log(
            action=AuditAction.COMPLIANCE_EXECUTION_BOOKING_REQUESTED,
            actor_id=actor_portal_user_id or "system",
            client_id=client_id,
            resource_type="work_order",
            resource_id=wo.get("work_order_id"),
            metadata={
                "work_order_kind": WORK_ORDER_KIND_COMPLIANCE,
                "requirement_code": canon,
                "compliance_purpose": purpose,
                "compliance_generated_from": gen_from,
                "property_id": property_id,
            },
        )
        await create_audit_log(
            action=AuditAction.COMPLIANCE_EXECUTION_WORK_ORDER_CREATED,
            actor_id=actor_portal_user_id or "system",
            client_id=client_id,
            resource_type="work_order",
            resource_id=wo.get("work_order_id"),
            metadata={
                "requirement_code": canon,
                "compliance_purpose": purpose,
                "property_id": property_id,
            },
        )
    except Exception as e:
        logger.warning("Compliance booking audit failed: %s", e)

    return wo


def describe_compliance_booking_action(compliance_purpose: str) -> str:
    """Stable external label for API responses (matches backend semantics)."""
    p = (compliance_purpose or "").strip().lower()
    return _PURPOSE_LABEL.get(p, "Compliance execution booking")
