"""Admin diagnostics: canonical compliance projection explain payloads."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from middleware import require_owner_or_admin
from services.compliance_explain_admin_service import build_admin_client_compliance_explain

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
