"""
Contractor workflow usage (product / adoption analytics)

These events are written with ``create_audit_log`` (same ``audit_logs`` collection as operational
audits) but are **intended for adoption and funnel reporting**, not compliance proofs of work.

-----------------------------------------------------------------------------
1) CONTRACTOR_ACTION_TAKEN — semantics
-----------------------------------------------------------------------------
``CONTRACTOR_ACTION_TAKEN`` records **workflow usage**: that the contractor engaged a named
``action_id`` from the UI (portal or job link). It is **not** a guarantee that the underlying
operation succeeded.

- Placement is **fire-and-forget** and varies slightly by action: for many flows the beacon is sent
  **when the user commits** (e.g. after confirm dialogs for decline / cancel visit), or **just before**
  the API call (intent / initiation). For others it fires **after** a successful step (e.g. schedule
  propose / confirm / reschedule on the dashboard).
- Do **not** treat a count of ``CONTRACTOR_ACTION_TAKEN`` as equal to successful server-side
  outcomes; pair with operational actions (e.g. ``CONTRACTOR_WORK_ORDER_STATUS_CHANGED``) or API
  metrics when you need confirmed success.

-----------------------------------------------------------------------------
2) Distinction vs operational audit events
-----------------------------------------------------------------------------
**Operational / auditable events** (examples: ``CONTRACTOR_EVIDENCE_UPLOADED``,
``CONTRACTOR_WORK_ORDER_STATUS_CHANGED``, ``CONTRACTOR_ACCEPTED_ASSIGNMENT``) are emitted from
route handlers when the system **performs or records** a state change. They are authoritative for
“what happened” in the product.

**Workflow usage events** (``CONTRACTOR_JOB_OPENED``, ``CONTRACTOR_ACTION_TAKEN``,
``CONTRACTOR_PROOF_UPLOADED``, ``CONTRACTOR_JOB_COMPLETED``) are driven by **client beacons**
(``POST .../workflow-usage``) and measure **whether contractors are using** the portal / job link.
The same user journey may produce **both** (e.g. evidence upload → operational
``CONTRACTOR_EVIDENCE_UPLOADED`` plus beacon ``CONTRACTOR_PROOF_UPLOADED``). For reporting:

- **Adoption / engagement**: prefer usage actions + ``metadata.source`` (``contractor_portal`` |
  ``job_link``).
- **Operational truth / change history**: prefer the long-standing CONTRACTOR_* audit actions tied
  to successful handler execution.
- Avoid **double-counting** the same concept in one dashboard (e.g. do not sum “uploads” from both
  ``CONTRACTOR_EVIDENCE_UPLOADED`` and ``CONTRACTOR_PROOF_UPLOADED`` as one KPI without labeling).

-----------------------------------------------------------------------------
3) Future: failure / funnel telemetry
-----------------------------------------------------------------------------
No backend for this yet. If adoption analysis needs **attempted vs failed vs succeeded**, a later
phase could add explicit outcome beacons or derive from API error rates — keep
``CONTRACTOR_ACTION_TAKEN`` as “engagement” unless semantics are tightened in code and docs together.

HTTP handlers enqueue writes via ``BackgroundTasks``; failures are logged and must not block UX.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from models import AuditAction
from utils.audit import create_audit_log

logger = logging.getLogger(__name__)

# Shared by contractor portal and job-link usage beacons
WORKFLOW_USAGE_EVENT_TO_ACTION = {
    "job_opened": AuditAction.CONTRACTOR_JOB_OPENED,
    "action_taken": AuditAction.CONTRACTOR_ACTION_TAKEN,
    "proof_uploaded": AuditAction.CONTRACTOR_PROOF_UPLOADED,
    "job_completed": AuditAction.CONTRACTOR_JOB_COMPLETED,
}


async def log_contractor_workflow_usage(
    *,
    action: AuditAction,
    contractor_id: str,
    work_order_id: str,
    client_id: Optional[str],
    metadata: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    source: str = "unknown",
) -> None:
    """Persist one usage event. Call from BackgroundTasks so the API response is not delayed."""
    try:
        meta: Dict[str, Any] = {"source": source}
        if metadata:
            meta.update(metadata)
        await create_audit_log(
            action=action,
            actor_id=contractor_id,
            client_id=client_id,
            resource_type="work_order",
            resource_id=work_order_id,
            metadata=meta,
            ip_address=ip_address,
        )
    except Exception as e:
        logger.warning("contractor_workflow_usage log failed: %s", e, exc_info=True)
