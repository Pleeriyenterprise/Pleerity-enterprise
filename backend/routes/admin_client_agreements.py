"""Admin visibility for CVP agreement acceptances and issued agreements."""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field

from database import database
from middleware import admin_route_guard
from models.agreements import COL_AGREEMENT_ACCEPTANCES, COL_ISSUED_AGREEMENTS, DEFAULT_TEMPLATE_CODE
from models import AuditAction
from services.agreement_issuance_service import issue_agreement_for_subscription_payment_retry, load_issued_pdf_bytes
from services.admin_action_governance import ensure_action_reason, normalized_admin_action_metadata
from utils.audit import create_audit_log

router = APIRouter(prefix="/api/admin/clients", tags=["admin-client-agreements"])


class AgreementRetryIssueBody(BaseModel):
    acceptance_id: str = Field(..., min_length=1)
    payment_reference: str = Field(..., min_length=1)
    reason: str = Field(..., min_length=10, max_length=2000)


@router.get("/{client_id}/agreements/summary")
async def get_client_agreements_summary(client_id: str, current_user: dict = Depends(admin_route_guard)):
    _ = current_user
    db = database.get_db()
    client = await db.clients.find_one({"client_id": client_id}, {"_id": 0, "client_id": 1, "customer_reference": 1})
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")

    acceptances: List[Dict[str, Any]] = await db[COL_AGREEMENT_ACCEPTANCES].find(
        {"client_id": client_id}, {"_id": 0}
    ).sort([("accepted_at", -1)]).to_list(100)

    issued: List[Dict[str, Any]] = await db[COL_ISSUED_AGREEMENTS].find({"client_id": client_id}, {"_id": 0}).sort(
        [("issued_at", -1)]
    ).to_list(100)

    def issued_public_row(row: Dict[str, Any]) -> Dict[str, Any]:
        pdf_id = (row.get("document_files") or {}).get("pdf_gridfs_id")
        return {
            "issued_id": row.get("issued_id"),
            "outcome": row.get("outcome"),
            "is_current": row.get("is_current"),
            "acceptance_id": row.get("acceptance_id"),
            "template_version_id": row.get("template_version_id"),
            "issued_at": row.get("issued_at"),
            "crn": row.get("crn"),
            "payment_reference": row.get("payment_reference"),
            "stripe_event_id": row.get("stripe_event_id"),
            "failure_reason": row.get("failure_reason"),
            "email_delivery": row.get("email_delivery"),
            "pdf_download_path": f"/api/admin/clients/{client_id}/agreements/issued/{row.get('issued_id')}/pdf"
            if row.get("outcome") == "issued" and pdf_id
            else None,
        }

    latest_failure = next((i for i in issued if i.get("outcome") == "issuance_failed"), None)
    retry_eligible = bool(
        latest_failure
        and str(latest_failure.get("acceptance_id") or "").strip()
        and str(latest_failure.get("payment_reference") or "").strip()
    )

    return {
        "client_id": client_id,
        "customer_reference": client.get("customer_reference"),
        "default_template_code": DEFAULT_TEMPLATE_CODE,
        "acceptances": acceptances,
        "issued_agreements": [issued_public_row(x) for x in issued],
        "latest_issuance_failure": latest_failure,
        "retry_eligible": retry_eligible,
    }


@router.get("/{client_id}/agreements/issued/{issued_id}/pdf")
async def download_issued_agreement_pdf(
    client_id: str,
    issued_id: str,
    current_user: dict = Depends(admin_route_guard),
):
    _ = current_user
    data = await load_issued_pdf_bytes(issued_id, client_id)
    if not data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PDF not found")
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="agreement_{issued_id}.pdf"'},
    )


@router.post("/{client_id}/agreements/retry-issue")
async def retry_agreement_issue(client_id: str, body: AgreementRetryIssueBody, current_user: dict = Depends(admin_route_guard)):
    actor_id = current_user.get("portal_user_id") or current_user.get("email") or current_user.get("user_id") or "admin"
    support_reason = ensure_action_reason("retry_agreement_issuance", body.reason)
    db = database.get_db()
    client = await db.clients.find_one({"client_id": client_id}, {"_id": 0, "customer_reference": 1})
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    crn = (client.get("customer_reference") or "").strip()
    if not crn:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Client has no CRN yet; agreement issuance retry requires post-payment CRN.",
        )
    ok, err, doc = await issue_agreement_for_subscription_payment_retry(
        client_id=client_id,
        acceptance_id=body.acceptance_id,
        payment_reference=body.payment_reference.strip(),
        crn=crn,
    )
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error": err})
    await create_audit_log(
        action=AuditAction.ADMIN_ACTION,
        actor_id=actor_id,
        client_id=client_id,
        resource_type="agreement",
        resource_id=str((doc or {}).get("issued_id") or body.acceptance_id),
        metadata={
            "event": "admin_retry_agreement_issue",
            **normalized_admin_action_metadata("retry_agreement_issuance", support_reason),
            "acceptance_id": body.acceptance_id,
            "payment_reference": body.payment_reference.strip(),
        },
    )
    return {"ok": True, "issued": doc}
