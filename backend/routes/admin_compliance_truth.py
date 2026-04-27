"""Admin diagnostics: canonical compliance projection explain payloads."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from database import database
from middleware import require_owner_or_admin
from services.compliance_explain_admin_service import build_admin_client_compliance_explain
from services.published_registry_client_truth_migration_service import evaluate_client_truth_migration

router = APIRouter(
    prefix="/api/admin/compliance-truth",
    tags=["admin-compliance-truth"],
    dependencies=[Depends(require_owner_or_admin)],
)


@router.get("/clients/{client_id}/explain")
async def admin_client_compliance_explain(client_id: str):
    """Row-level explainability for portal KPI parity (admin / support only)."""
    try:
        return await build_admin_client_compliance_explain(client_id.strip())
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to build compliance explain payload",
        )


@router.get("/clients/{client_id}/published-registry-migration-report")
async def admin_published_registry_migration_report(client_id: str, limit: int = 10000):
    """Dry-run diagnostics for published-registry client-truth migration states."""
    try:
        return await evaluate_client_truth_migration(
            db=database.get_db(),
            client_id=client_id.strip(),
            limit=max(100, min(int(limit or 10000), 50000)),
            apply=False,
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to build migration diagnostics report",
        )
