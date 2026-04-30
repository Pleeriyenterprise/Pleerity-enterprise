"""Runtime health checks for policy-backed portfolio override selection."""

from __future__ import annotations

from typing import Any, Dict


CHECKPOINT_COLLECTION = "compliance_policy_backfill_checkpoints"
JOB_REQUIREMENT_FIELDS = "requirement_policy_fields"
JOB_GAP_RECONCILIATION = "gap_policy_reconciliation"
PR5_GAP_COVERAGE_GATE_PERCENT = 99.5


async def get_tenant_policy_runtime_health(db: Any, *, client_id: str) -> Dict[str, Any]:
    cp_req = await db[CHECKPOINT_COLLECTION].find_one(
        {"job_name": JOB_REQUIREMENT_FIELDS, "client_id": client_id},
        {"_id": 0, "status": 1, "failed": 1, "completed_at": 1, "updated_at": 1},
    ) or {}
    cp_gap = await db[CHECKPOINT_COLLECTION].find_one(
        {"job_name": JOB_GAP_RECONCILIATION, "client_id": client_id},
        {"_id": 0, "status": 1, "failed": 1, "completed_at": 1, "updated_at": 1},
    ) or {}
    gap_completed = str(cp_gap.get("status") or "").lower() == "completed"
    req_completed = str(cp_req.get("status") or "").lower() == "completed"
    return {
        "reconciliation_completed": gap_completed,
        "reconciliation_in_progress": not gap_completed,
        "drift_detected": int(cp_gap.get("failed") or 0) > 0 or int(cp_req.get("failed") or 0) > 0,
        "policy_coverage_threshold_percent": PR5_GAP_COVERAGE_GATE_PERCENT,
        "policy_jobs_completed": gap_completed and req_completed,
        "gap_reconciliation_checkpoint": {
            "job_name": JOB_GAP_RECONCILIATION,
            "status": cp_gap.get("status"),
            "failed": int(cp_gap.get("failed") or 0),
            "completed_at": cp_gap.get("completed_at"),
            "updated_at": cp_gap.get("updated_at"),
        },
    }
