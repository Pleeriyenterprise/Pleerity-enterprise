"""POST /documents/verify behaviour when FEATURE_EVIDENCE_REVIEW_V2 is enabled."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from database import database
from models import AuditAction, DocumentStatus, RequirementStatus
from models.evidence_review import AssuranceTier, EvidenceReviewState

from utils.audit import create_audit_log
from utils.compliance_fanout_log import compliance_fanout_extra

from services.evidence_review_actions import correlation_id_new, document_is_calendrically_expired, run_validation_for_document, transition_review_fields
from services.evidence_review_policy import promotions_allowed_for_accept_unverified
from services.provisioning import provisioning_service
from services.authority_mutation_fanout import (
    authority_sync_with_transition_observability,
    enqueue_compliance_recalc_with_fanout,
)
from services.compliance_recalc_queue import TRIGGER_DOC_STATUS_CHANGED, ACTOR_ADMIN
from services.requirement_transition_observability import (
    merge_document_path_lineage_flags,
    merge_pre_authority_optimistic_requirement_promotion_marker,
)
from services.work_order_execution_constants import COMPLIANCE_PROOF_VERIFIED, WORK_ORDER_KIND_COMPLIANCE

logger = logging.getLogger(__name__)


def _verify_replay_possible_for_observability(old_status: str) -> bool:
    """Match ``routes.documents._document_verification_replay_heuristic`` for lineage flags."""
    return str(old_status or "").strip().upper() == str(DocumentStatus.VERIFIED.value).upper()


async def execute_verify_document_v2(
    db,
    *,
    document_id: str,
    document: Dict[str, Any],
    user: Dict[str, Any],
    old_status: str,
    validation_override_reason: Optional[str],
) -> Dict[str, Any]:
    """
    Human acceptance of evidence (not external registry verification).
    Sets legacy DocumentStatus.VERIFIED for compatibility + evidence_review_state ACCEPTED_UNVERIFIED.
    """
    if document_is_calendrically_expired(document):
        raise _expired_http()

    snapshot = await run_validation_for_document(db, document)
    vs = str(snapshot.get("validation_status") or "").upper()
    override = str(validation_override_reason or "").strip()

    if vs == "FAIL" and not override:
        from fastapi import HTTPException, status
        from utils.api_errors import structured_error

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=structured_error(
                "EVIDENCE_VALIDATION_FAILED",
                "Validation failed for this evidence. Provide validation_override_reason to record a supervised override.",
                validation_result=snapshot,
            ),
        )

    promote_compliance = promotions_allowed_for_accept_unverified(
        validation_snapshot=snapshot,
        validation_override_reason=override,
    )

    report_id = str(uuid.uuid4())
    now_iso = datetime.now(timezone.utc).isoformat()
    corr = correlation_id_new()

    decision_reason = None
    if vs == "FAIL" and override:
        decision_reason = "VALIDATION_FAILURE_OVERRIDE"
    elif override:
        decision_reason = "VALIDATION_OVERRIDE_NOTES"

    patch: Dict[str, Any] = {
        "status": DocumentStatus.VERIFIED.value,
        "evidence_review_state": EvidenceReviewState.ACCEPTED_UNVERIFIED.value,
        "assurance_tier": AssuranceTier.HUMAN_ACCEPTED.value,
        "review_required": False,
        "review_notes_required": False,
        "validation_report_id": report_id,
        "latest_validation_snapshot": snapshot,
        "updated_at": now_iso,
        "review_decision_at": now_iso,
        "review_decision_by": user.get("portal_user_id"),
    }

    await transition_review_fields(
        db,
        document_id=document_id,
        patch=patch,
        reviewer_id=user.get("portal_user_id"),
        correlation_id=corr,
        prev_doc=document,
        validation_snapshot=snapshot,
        notes=override or None,
        decision_reason=decision_reason,
    )

    from services.evidence_extraction_supersession import (
        ADMIN_DECISION_ACCEPTED,
        supersede_extraction_confirmation_for_admin_decision,
    )

    await supersede_extraction_confirmation_for_admin_decision(
        db,
        document_id=document_id,
        decision=ADMIN_DECISION_ACCEPTED,
        actor_id=user.get("portal_user_id"),
    )

    document_after = await db.documents.find_one({"document_id": document_id}, {"_id": 0}) or {}

    recalc_correlation_id = f"DOC_STATUS_CHANGED:{document_id}:VERIFIED"
    transition_fanout: Dict[str, Any] = {}
    rid = str(document.get("requirement_id") or "")

    if rid and promote_compliance:
        await db.requirements.update_one(
            {"requirement_id": document["requirement_id"]},
            {
                "$set": {
                    "status": RequirementStatus.COMPLIANT.value,
                    "date_source": "VERIFIED_DOCUMENT",
                    "evidence_state": "VERIFIED",
                    "confidence_state": "VERIFIED",
                    "compliance_state": "VALID",
                }
            },
        )
        try:
            await _finalize_active_compliance_jobs_after_certificate_verified(
                db,
                client_id=str(document.get("client_id") or ""),
                requirement_id=str(document["requirement_id"]),
                document_id=document_id,
                actor_id=user.get("portal_user_id"),
            )
        except Exception as fin_e:
            logger.warning("Active compliance job finalize on verify skipped: %s", fin_e)
        merge_pre_authority_optimistic_requirement_promotion_marker(
            transition_fanout,
            applied=True,
            basis="VERIFIED_DOCUMENT_COMPLIANT_PROMOTION_V2",
            transition_origin="services.evidence_review_verify.execute_verify_document_v2",
            requirement_id=rid,
        )

    if rid:
        await authority_sync_with_transition_observability(
            db,
            rid,
            property_id=str(document.get("property_id") or "") or None,
            client_id=str(document.get("client_id") or ""),
            correlation_base=recalc_correlation_id,
            transition_origin="services.evidence_review_verify.execute_verify_document_v2",
            transition_fanout=transition_fanout,
        )
        merge_document_path_lineage_flags(
            transition_fanout,
            document_id=document_id,
            verification_replay_possible=_verify_replay_possible_for_observability(old_status),
            stale_document_transition_possible=True,
        )

    if document.get("property_id"):
        await provisioning_service._update_property_compliance(document["property_id"])
        await enqueue_compliance_recalc_with_fanout(
            transition_fanout if rid else None,
            property_id=document["property_id"],
            client_id=document["client_id"],
            trigger_reason=TRIGGER_DOC_STATUS_CHANGED,
            actor_type=ACTOR_ADMIN,
            actor_id=user.get("portal_user_id"),
            correlation_id=recalc_correlation_id,
            trigger_origin="services.evidence_review_verify.execute_verify_document_v2",
            propagation_stage="post_verify_v2_authority_sync",
            fanout_op="evidence_review_verify_transition_fanout",
        )

    verify_audit_meta: Dict[str, Any] = {}
    if document.get("work_order_id"):
        verify_audit_meta["work_order_id"] = document["work_order_id"]
    verify_audit_meta["evidence_review_v2"] = True
    verify_audit_meta["validation_status"] = vs
    if rid and promote_compliance:
        verify_audit_meta["pre_authority_optimistic_requirement_promotion"] = True
        verify_audit_meta["optimistic_promotion_basis"] = "VERIFIED_DOCUMENT_COMPLIANT_PROMOTION_V2"
    await create_audit_log(
        action=AuditAction.DOCUMENT_VERIFIED,
        actor_id=user["portal_user_id"],
        client_id=document["client_id"],
        resource_type="document",
        resource_id=document_id,
        before_state={"status": old_status, "evidence_review": (document.get("evidence_review_state"))},
        after_state={"status": DocumentStatus.VERIFIED.value, "evidence_review": EvidenceReviewState.ACCEPTED_UNVERIFIED.value},
        metadata=verify_audit_meta or None,
    )

    try:
        from services.enablement_service import emit_enablement_event
        from models.enablement import EnablementEventType

        pid_en = document.get("property_id")
        prop_row = (
            await db.properties.find_one({"property_id": pid_en}, {"_id": 0, "address": 1}) if pid_en else None
        )
        pa = ""
        if prop_row:
            addr = prop_row.get("address") if isinstance(prop_row.get("address"), dict) else {}
            pa = (addr.get("line1") if isinstance(addr, dict) else "") or ""
        await emit_enablement_event(
            event_type=EnablementEventType.DOCUMENT_VERIFIED,
            client_id=document["client_id"],
            document_id=document_id,
            property_id=pid_en,
            context_payload={
                "document_name": document.get("document_name", document.get("requirement_name", "Document")),
                "property_address": pa,
                "expiry_date": document.get("expiry_date", "N/A"),
            },
        )
    except Exception:
        pass

    outcome = None
    try:
        if document.get("property_id"):
            from services.compliance_outcome_engine import apply_action_outcome, EVENT_CERTIFICATE_VERIFIED

            rrow = await db.requirements.find_one(
                {"requirement_id": document["requirement_id"]},
                {"_id": 0, "requirement_type": 1, "requirement_code": 1},
            )
            req_type_for_outcome = None
            if rrow:
                req_type_for_outcome = (rrow.get("requirement_code") or rrow.get("requirement_type") or "").strip() or None
            meta = {
                "document_id": document_id,
                "requirement_id": document.get("requirement_id"),
            }
            woid = (document.get("work_order_id") or "").strip()
            if woid:
                meta["work_order_id"] = woid
            outcome = await apply_action_outcome(
                {
                    "event_type": EVENT_CERTIFICATE_VERIFIED,
                    "client_id": document["client_id"],
                    "property_id": document.get("property_id"),
                    "asset_id": None,
                    "requirement_type": req_type_for_outcome,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "source_id": document_id,
                    "dedupe_key": f"{EVENT_CERTIFICATE_VERIFIED}:{document_id}",
                    "actor_id": user.get("portal_user_id"),
                    "actor_role": "ADMIN",
                    "metadata": meta,
                }
            )
    except Exception as outcome_err:
        logger.warning(
            "evidence_review_verify: apply_action_outcome certificate_verified failed: %s",
            outcome_err,
            extra=compliance_fanout_extra(
                op="outcome_apply",
                stage="failed",
                client_id=str(document.get("client_id") or ""),
                property_id=str(document.get("property_id") or "") or None,
                requirement_id=str(document.get("requirement_id") or "") or None,
                correlation_id=f"certificate_verified:{document_id}",
                exc_type=type(outcome_err).__name__,
            ),
        )

    try:
        await _append_document_evidence_to_work_order(document_id, document.get("work_order_id"))
        await _set_compliance_work_order_proof_verified(db, document.get("work_order_id"))
    except Exception:
        pass

    from services.client_propagation_notice import build_propagation_notice_from_transition_fanout

    out: Dict[str, Any] = {
        "message": "Document verified (human accepted, not externally verified)",
        "outcome": outcome,
        "evidence_review_state": document_after.get("evidence_review_state"),
        "assurance_tier": document_after.get("assurance_tier"),
        "validation": snapshot,
    }
    notice = build_propagation_notice_from_transition_fanout(transition_fanout if rid else None)
    if notice:
        out["propagation_notice"] = notice
    return out


async def _append_document_evidence_to_work_order(document_id: str, work_order_id: Optional[str]) -> None:
    if not (work_order_id or "").strip():
        return
    wid = work_order_id.strip()
    db = database.get_db()
    wo = await db.work_orders.find_one({"work_order_id": wid}, {"_id": 0, "work_order_kind": 1})
    if not wo or (wo.get("work_order_kind") or "").strip().upper() != WORK_ORDER_KIND_COMPLIANCE:
        return
    from services import maintenance_service

    await maintenance_service.update_work_order(
        wid,
        evidence_keys_append=[f"document:{document_id}"],
    )


async def _finalize_active_compliance_jobs_after_certificate_verified(
    db,
    *,
    client_id: str,
    requirement_id: str,
    document_id: str,
    actor_id: Optional[str],
) -> None:
    from services import maintenance_service

    terminal = frozenset(
        {
            maintenance_service.STATUS_CANCELLED,
            maintenance_service.STATUS_COMPLETED,
            maintenance_service.STATUS_CLOSED,
            maintenance_service.STATUS_VERIFIED,
        }
    )
    key = f"document:{document_id.strip()}"
    cursor = db.work_orders.find(
        {
            "client_id": client_id.strip(),
            "work_order_kind": WORK_ORDER_KIND_COMPLIANCE,
            "linked_property_requirement_id": requirement_id.strip(),
            "status": {"$nin": list(terminal)},
        },
        {"_id": 0, "work_order_id": 1},
    )
    async for row in cursor:
        wid = (row.get("work_order_id") or "").strip()
        if not wid:
            continue
        try:
            await maintenance_service.update_work_order(
                wid,
                evidence_keys_append=[key],
                assigned_by=actor_id,
            )
            await maintenance_service.update_work_order(
                wid,
                status=maintenance_service.STATUS_VERIFIED,
                assigned_by=actor_id,
            )
        except Exception as ex:
            logger.warning("Finalize compliance job %s on document verify failed: %s", wid, ex)


async def _set_compliance_work_order_proof_verified(db, work_order_id: Optional[str]) -> None:
    if not (work_order_id or "").strip():
        return
    wid = work_order_id.strip()
    now = datetime.now(timezone.utc).isoformat()
    await db.work_orders.update_one(
        {"work_order_id": wid, "work_order_kind": WORK_ORDER_KIND_COMPLIANCE},
        {"$set": {"compliance_proof_status": COMPLIANCE_PROOF_VERIFIED, "updated_at": now}},
    )


def _expired_http():
    from fastapi import HTTPException, status
    from utils.api_errors import structured_error

    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=structured_error(
            "EVIDENCE_EXPIRED",
            "This document is past its effective expiry date and cannot be moved to a positive verification state.",
        ),
    )
