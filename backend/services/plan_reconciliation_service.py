"""Plan change reconciliation – disable/revoke paid features on downgrade or subscription end.

Runs on Stripe subscription.updated / subscription.deleted (and plan change).
Applies corrective actions so paid features cannot persist after:
- plan downgrade
- subscription cancellation / past_due / unpaid
- trial expiry

All actions are idempotent and logged to AuditLog.
"""
from __future__ import annotations

import logging
from typing import Optional

from database import database
from services.plan_registry import (
    plan_registry,
    PlanCode,
    subscription_allows_feature_access,
)
from utils.audit import create_audit_log
from models import AuditAction

logger = logging.getLogger(__name__)

# Features that have stored state we must disable/revoke on downgrade
RECONCILIATION_FEATURES = [
    "scheduled_reports",
    "sms_reminders",
    "tenant_portal",
    "white_label_reports",
    "audit_log_export",  # runtime-only; no state change, but we log
]


async def reconcile_plan_change(
    client_id: str,
    old_plan: Optional[str],
    new_plan: Optional[str],
    reason: str,
    subscription_status: Optional[str] = None,
) -> dict:
    """
    Reconcile client state after plan change or subscription end.

    - If new_plan is None or subscription_status is not ACTIVE/TRIALING: treat as no paid features.
    - Otherwise compute allowed features for new_plan and disable/revoke anything no longer allowed.

    Idempotent: safe to call multiple times for the same transition.
    """
    db = database.get_db()

    # Resolve effective "allowed" features
    if new_plan is None or not subscription_allows_feature_access(subscription_status):
        allowed_features = {f: False for f in RECONCILIATION_FEATURES}
        effective_plan = None
    else:
        try:
            plan_code = plan_registry.resolve_plan_code(new_plan)
        except Exception:
            plan_code = PlanCode.PLAN_1_SOLO
        allowed_features = plan_registry.get_features(plan_code)
        effective_plan = new_plan

    summary = {
        "client_id": client_id,
        "old_plan": old_plan,
        "new_plan": new_plan,
        "subscription_status": subscription_status,
        "reason": reason,
        "actions": [],
    }

    # --- scheduled_reports: disable active schedules ---
    if not allowed_features.get("scheduled_reports", True):
        r = await db.report_schedules.update_many(
            {"client_id": client_id, "is_active": True},
            {"$set": {"is_active": False, "disabled_reason": "PLAN_DOWNGRADE"}},
        )
        if r.modified_count:
            summary["actions"].append(
                {"feature": "scheduled_reports", "action": "disabled", "count": r.modified_count}
            )
            await create_audit_log(
                action=AuditAction.ADMIN_ACTION,
                actor_role="SYSTEM",
                client_id=client_id,
                resource_type="report_schedule",
                metadata={
                    "action_type": "PLAN_RECONCILIATION_SCHEDULED_REPORTS_DISABLED",
                    "reason": reason,
                    "old_plan": old_plan,
                    "new_plan": new_plan,
                    "schedules_disabled": r.modified_count,
                },
            )
            logger.info(
                "Plan reconciliation: disabled %s scheduled report(s) for client %s",
                r.modified_count,
                client_id,
            )

    # --- sms_reminders: disable SMS preference so jobs skip ---
    if not allowed_features.get("sms_reminders", True):
        r = await db.notification_preferences.update_one(
            {"client_id": client_id},
            {"$set": {"sms_enabled": False, "sms_disabled_reason": "PLAN_DOWNGRADE"}},
        )
        if r.modified_count:
            summary["actions"].append({"feature": "sms_reminders", "action": "disabled_preference"})
            await create_audit_log(
                action=AuditAction.ADMIN_ACTION,
                actor_role="SYSTEM",
                client_id=client_id,
                resource_type="notification_preferences",
                metadata={
                    "action_type": "PLAN_RECONCILIATION_SMS_REMINDERS_DISABLED",
                    "reason": reason,
                    "old_plan": old_plan,
                    "new_plan": new_plan,
                },
            )
            logger.info(
                "Plan reconciliation: disabled SMS reminders preference for client %s",
                client_id,
            )

    # --- tenant_portal: revoke tenant view access (disable tenant users) ---
    if not allowed_features.get("tenant_portal", True):
        r = await db.portal_users.update_many(
            {"client_id": client_id, "role": "ROLE_TENANT"},
            {"$set": {"status": "DISABLED", "revoked_reason": "PLAN_DOWNGRADE"}},
        )
        if r.modified_count:
            summary["actions"].append(
                {"feature": "tenant_portal", "action": "tenants_revoked", "count": r.modified_count}
            )
            await create_audit_log(
                action=AuditAction.ADMIN_ACTION,
                actor_role="SYSTEM",
                client_id=client_id,
                resource_type="tenant_portal",
                metadata={
                    "action_type": "PLAN_RECONCILIATION_TENANT_ACCESS_REVOKED",
                    "reason": reason,
                    "old_plan": old_plan,
                    "new_plan": new_plan,
                    "tenants_revoked": r.modified_count,
                },
            )
            logger.info(
                "Plan reconciliation: revoked %s tenant(s) for client %s",
                r.modified_count,
                client_id,
            )

    # --- white_label_reports: mark branding inactive for plan (API still gates) ---
    if not allowed_features.get("white_label_reports", True):
        r = await db.branding_settings.update_one(
            {"client_id": client_id},
            {"$set": {"white_label_disabled_by_plan": True, "disabled_reason": "PLAN_DOWNGRADE"}},
        )
        if r.modified_count:
            summary["actions"].append({"feature": "white_label_reports", "action": "disabled"})
            await create_audit_log(
                action=AuditAction.ADMIN_ACTION,
                actor_role="SYSTEM",
                client_id=client_id,
                resource_type="branding_settings",
                metadata={
                    "action_type": "PLAN_RECONCILIATION_WHITE_LABEL_DISABLED",
                    "reason": reason,
                    "old_plan": old_plan,
                    "new_plan": new_plan,
                },
            )
            logger.info(
                "Plan reconciliation: disabled white-label for client %s",
                client_id,
            )

    # --- audit_log_export: no state change; runtime gating only ---
    if not allowed_features.get("audit_log_export", True):
        summary["actions"].append(
            {"feature": "audit_log_export", "action": "runtime_only", "note": "no state change"}
        )

    # Summary audit
    await create_audit_log(
        action=AuditAction.ADMIN_ACTION,
        actor_role="SYSTEM",
        client_id=client_id,
        metadata={
            "action_type": "PLAN_RECONCILIATION_SUMMARY",
            "reason": reason,
            "old_plan": old_plan,
            "new_plan": new_plan,
            "subscription_status": subscription_status,
            "effective_plan": effective_plan,
            "actions": summary["actions"],
        },
    )

    return summary
