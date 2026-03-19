"""
Admin manual generation retry: audit log, workflow metadata, QUEUED + WF2/WF3.

Canonical HTTP surface: /api/admin/orders/{order_id}/retry-generation (see admin_orders).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from database import database
from models import AuditAction, UserRole
from services.order_service import transition_order_state, get_order
from services.order_workflow import OrderStatus
from utils.audit import create_audit_log

logger = logging.getLogger(__name__)


def _normalize_provider(pref: Optional[str]) -> Optional[str]:
    if pref is None or pref == "":
        return None
    p = str(pref).strip().lower()
    if p not in ("openai", "gemini"):
        raise ValueError("preferred_provider must be 'openai', 'gemini', or null")
    return p


async def admin_retry_order_generation(
    *,
    order_id: str,
    admin_user: Dict[str, Any],
    reason: str,
    preferred_provider: Optional[str] = None,
    force_skip_auto_retry_guard: bool = False,
    workflow_event_code: str = "RETRY_TRIGGERED",
) -> Dict[str, Any]:
    """
    FAILED → QUEUED, optional admin_llm_preferred_provider on order, audit + workflow event metadata.
    Then WF2 + WF3 (same as legacy admin retry).
    """
    reason_clean = (reason or "").strip()
    if not reason_clean:
        raise ValueError("reason is required")

    order = await get_order(order_id)
    if not order:
        raise ValueError("Order not found")
    if order.get("status") != OrderStatus.FAILED.value:
        raise ValueError(f"Order must be FAILED (current: {order.get('status')})")

    db = database.get_db()
    # Admin manual retry supersedes a scheduled automatic retry (avoid duplicate runs).
    if order.get("automatic_retry_pending"):
        await db.orders.update_one(
            {"order_id": order_id},
            {"$set": {"automatic_retry_pending": False}},
        )

    pref = _normalize_provider(preferred_provider)

    set_fields: Dict[str, Any] = {}
    if pref:
        set_fields["admin_llm_preferred_provider"] = pref
    if set_fields:
        await db.orders.update_one({"order_id": order_id}, {"$set": set_fields})

    meta = {
        "workflow_event_code": workflow_event_code,
        "preferred_provider": pref,
        "reason": reason_clean[:500],
        "force_skip_auto_retry_guard": bool(force_skip_auto_retry_guard),
    }

    await create_audit_log(
        action=AuditAction.ADMIN_ORDER_GENERATION_MANUAL_RETRY,
        actor_role=UserRole.ROLE_ADMIN,
        actor_id=admin_user.get("user_id"),
        resource_type="order",
        resource_id=order_id,
        metadata={
            "preferred_provider": pref,
            "reason": reason_clean[:2000],
            "workflow_event_code": workflow_event_code,
        },
        reason_code="GENERATION_MANUAL_RETRY",
    )

    await transition_order_state(
        order_id=order_id,
        new_status=OrderStatus.QUEUED,
        triggered_by_type="admin",
        triggered_by_user_id=admin_user.get("user_id"),
        triggered_by_email=admin_user.get("email"),
        reason=reason_clean[:2000],
        metadata=meta,
    )

    from services.workflow_automation_service import workflow_automation_service

    try:
        gen = await workflow_automation_service.wf2_queue_to_generation(order_id)
        review = None
        if gen.get("success"):
            review = await workflow_automation_service.wf3_draft_to_review(order_id)
        # Clear override after run attempt
        await db.orders.update_one(
            {"order_id": order_id},
            {"$unset": {"admin_llm_preferred_provider": ""}},
        )
        return {
            "success": bool(gen.get("success")),
            "order_id": order_id,
            "status": (await get_order(order_id) or {}).get("status"),
            "generation": gen,
            "review": review,
            "message": gen.get("error") or ("Queued for review" if gen.get("success") else "Generation failed"),
        }
    except Exception as e:
        logger.exception("admin_retry_order_generation: WF2/WF3 error %s", order_id)
        await db.orders.update_one(
            {"order_id": order_id},
            {"$unset": {"admin_llm_preferred_provider": ""}},
        )
        return {
            "success": False,
            "order_id": order_id,
            "error": str(e),
            "message": "Retry started but pipeline raised an error",
        }
