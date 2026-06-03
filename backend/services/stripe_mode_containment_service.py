"""
Stripe mode containment — Phase 1 guardrails (no automatic migration or Stripe mutation).

Preflight validation uses persisted stripe_mode before any Stripe API retrieve.
Legacy rows without stripe_mode are blocked with customer-safe messaging.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from database import database
from services.stripe_mode_authority import configure_stripe_sdk, get_stripe_mode

REMEDIATION_MODE_UNVERIFIED = "MODE_UNVERIFIED"
REMEDIATION_REGENERATE_CHECKOUT = "REGENERATE_CHECKOUT_REQUIRED"
from utils.audit import create_audit_log
from models import AuditAction

logger = logging.getLogger(__name__)

CUSTOMER_BILLING_REFRESH_MESSAGE = (
    "Your billing record needs to be refreshed before plan changes can continue."
)

STRIPE_SUBSCRIPTION_MODE_DRIFT = "STRIPE_SUBSCRIPTION_MODE_DRIFT"
STRIPE_CUSTOMER_MODE_DRIFT = "STRIPE_CUSTOMER_MODE_DRIFT"
STRIPE_CHECKOUT_MODE_DRIFT = "STRIPE_CHECKOUT_MODE_DRIFT"
STRIPE_PORTAL_MODE_DRIFT = "STRIPE_PORTAL_MODE_DRIFT"
STRIPE_EVENT_MODE_DRIFT = "STRIPE_EVENT_MODE_DRIFT"

ALL_DRIFT_CODES = frozenset(
    {
        STRIPE_SUBSCRIPTION_MODE_DRIFT,
        STRIPE_CUSTOMER_MODE_DRIFT,
        STRIPE_CHECKOUT_MODE_DRIFT,
        STRIPE_PORTAL_MODE_DRIFT,
        STRIPE_EVENT_MODE_DRIFT,
    }
)

COL_DRIFT_METRICS = "stripe_mode_drift_metrics"
COL_DRIFT_EVENTS = "stripe_mode_drift_events"

MODE_UNVERIFIED = "MODE_UNVERIFIED"
CONFIDENCE_UNKNOWN = "unknown"
CONFIDENCE_AUTHORITATIVE = "authoritative"


def requires_deployment_checkout_for_plan_change(
    billing: Optional[Dict[str, Any]],
    *,
    recovery_case: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    Use deployment-mode Checkout (not upgrade/portal preflight) for drift / MODE_UNVERIFIED rows.
    Shared by billing recovery regeneration and client plan-change checkout.
    """
    if not billing:
        return True
    verification = (billing.get("stripe_mode_verification_status") or "").strip()
    if verification == MODE_UNVERIFIED:
        return True
    remediation = (recovery_case or {}).get("remediation_code") or ""
    if remediation in (REMEDIATION_MODE_UNVERIFIED, REMEDIATION_REGENERATE_CHECKOUT):
        return True
    dep = normalize_persisted_mode(get_stripe_mode())
    stored = normalize_persisted_mode(billing.get("stripe_mode"))
    if billing.get("stripe_subscription_id") and stored is None:
        return True
    if stored and dep and stored != dep:
        return True
    return False


class StripeModeDriftError(Exception):
    """Operational drift — customer-safe; never expose Stripe internals."""

    def __init__(
        self,
        error_code: str,
        *,
        customer_message: str = CUSTOMER_BILLING_REFRESH_MESSAGE,
        admin_reason: str = "",
        client_id: Optional[str] = None,
        operation: Optional[str] = None,
        inferred_mode: Optional[str] = None,
        recovery_action: str = "admin_billing_refresh",
    ):
        super().__init__(customer_message)
        self.error_code = error_code
        self.customer_message = customer_message
        self.admin_reason = admin_reason
        self.client_id = client_id
        self.operation = operation
        self.inferred_mode = inferred_mode
        self.recovery_action = recovery_action

    def to_customer_detail(self) -> Dict[str, Any]:
        return {
            "error_code": self.error_code,
            "message": self.customer_message,
            "recovery_action": self.recovery_action,
        }

    def to_admin_detail(self) -> Dict[str, Any]:
        return {
            "error_code": self.error_code,
            "admin_reason": self.admin_reason,
            "client_id": self.client_id,
            "operation": self.operation,
            "inferred_mode": self.inferred_mode,
            "recovery_action": self.recovery_action,
            "deployment_mode": None,  # filled by caller if needed
        }


def _now() -> datetime:
    return datetime.now(timezone.utc)


def normalize_persisted_mode(mode: Optional[str]) -> Optional[str]:
    if not mode or not str(mode).strip():
        return None
    m = str(mode).strip().lower()
    return m if m in ("live", "test") else None


def classify_stripe_api_error_for_drift(exc: Exception) -> Optional[str]:
    """Map Stripe API text to drift code (post-call safety net only)."""
    msg = str(exc).lower()
    if "similar object exists in test mode" in msg and "live mode key" in msg:
        return STRIPE_SUBSCRIPTION_MODE_DRIFT
    if "similar object exists in live mode" in msg and "test mode key" in msg:
        return STRIPE_SUBSCRIPTION_MODE_DRIFT
    if "no such subscription" in msg and ("test mode" in msg or "live mode" in msg):
        return STRIPE_SUBSCRIPTION_MODE_DRIFT
    if "no such customer" in msg and ("test mode" in msg or "live mode" in msg):
        return STRIPE_CUSTOMER_MODE_DRIFT
    return None


def _assert_not_mode_unverified(
    *,
    error_code: str = STRIPE_SUBSCRIPTION_MODE_DRIFT,
    verification_status: Optional[str] = None,
    confidence: Optional[str] = None,
    client_id: Optional[str] = None,
    operation: str = "subscription_access",
) -> None:
    status = (verification_status or "").strip()
    conf = (confidence or "").strip().lower()
    if status == MODE_UNVERIFIED or conf == CONFIDENCE_UNKNOWN:
        raise StripeModeDriftError(
            error_code,
            admin_reason="mode_unverified_governance",
            client_id=client_id,
            operation=operation,
            recovery_action="MODE_UNVERIFIED",
        )


def validate_stripe_subscription_mode(
    stripe_subscription_id: Optional[str],
    deployment_mode: str,
    *,
    stored_mode: Optional[str] = None,
    trusted_mode: Optional[str] = None,
    verification_status: Optional[str] = None,
    confidence: Optional[str] = None,
    client_id: Optional[str] = None,
    operation: str = "subscription_access",
) -> Dict[str, Any]:
    """
    Preflight before Subscription.retrieve or portal subscription_update_confirm.
    Never calls Stripe API — uses persisted stripe_mode only.
    """
    sub_id = (stripe_subscription_id or "").strip()
    if not sub_id:
        return {"ok": True, "skipped": True}

    dep = normalize_persisted_mode(deployment_mode) or get_stripe_mode()
    persisted = normalize_persisted_mode(stored_mode)
    trusted = normalize_persisted_mode(trusted_mode)

    _assert_not_mode_unverified(
        verification_status=verification_status,
        confidence=confidence,
        client_id=client_id,
        operation=operation,
    )

    if persisted is None and trusted and trusted == dep:
        return {"ok": True, "stripe_mode": trusted, "trusted": True}
    if persisted is None:
        raise StripeModeDriftError(
            STRIPE_SUBSCRIPTION_MODE_DRIFT,
            admin_reason="missing_stripe_mode_on_billing_row",
            client_id=client_id,
            operation=operation,
            recovery_action="backfill_stripe_mode_or_regenerate_checkout",
        )
    if persisted != dep:
        raise StripeModeDriftError(
            STRIPE_SUBSCRIPTION_MODE_DRIFT,
            admin_reason="stored_stripe_mode_mismatch",
            client_id=client_id,
            operation=operation,
            inferred_mode=persisted,
        )
    return {"ok": True, "stripe_mode": persisted}


def validate_stripe_customer_mode(
    stripe_customer_id: Optional[str],
    deployment_mode: str,
    *,
    stored_mode: Optional[str] = None,
    verification_status: Optional[str] = None,
    confidence: Optional[str] = None,
    client_id: Optional[str] = None,
    operation: str = "customer_access",
) -> Dict[str, Any]:
    cid = (stripe_customer_id or "").strip()
    if not cid:
        return {"ok": True, "skipped": True}

    dep = normalize_persisted_mode(deployment_mode) or get_stripe_mode()
    persisted = normalize_persisted_mode(stored_mode)

    _assert_not_mode_unverified(
        error_code=STRIPE_CUSTOMER_MODE_DRIFT,
        verification_status=verification_status,
        confidence=confidence,
        client_id=client_id,
        operation=operation,
    )

    if persisted is None:
        raise StripeModeDriftError(
            STRIPE_CUSTOMER_MODE_DRIFT,
            admin_reason="missing_stripe_customer_mode",
            client_id=client_id,
            operation=operation,
            recovery_action="backfill_stripe_mode_or_regenerate_checkout",
        )
    if persisted != dep:
        raise StripeModeDriftError(
            STRIPE_CUSTOMER_MODE_DRIFT,
            admin_reason="stored_customer_mode_mismatch",
            client_id=client_id,
            operation=operation,
            inferred_mode=persisted,
        )
    return {"ok": True, "stripe_mode": persisted}


def validate_checkout_session_mode(
    checkout_stripe_mode: Optional[str],
    deployment_mode: str,
    *,
    client_id: Optional[str] = None,
    operation: str = "checkout_regeneration",
) -> Dict[str, Any]:
    dep = normalize_persisted_mode(deployment_mode) or get_stripe_mode()
    persisted = normalize_persisted_mode(checkout_stripe_mode)
    if persisted is None:
        raise StripeModeDriftError(
            STRIPE_CHECKOUT_MODE_DRIFT,
            admin_reason="missing_checkout_stripe_mode",
            client_id=client_id,
            operation=operation,
            recovery_action="regenerate_checkout",
        )
    if persisted != dep:
        raise StripeModeDriftError(
            STRIPE_CHECKOUT_MODE_DRIFT,
            admin_reason="checkout_mode_mismatch",
            client_id=client_id,
            operation=operation,
            inferred_mode=persisted,
            recovery_action="regenerate_checkout",
        )
    return {"ok": True, "stripe_mode": persisted}


def validate_portal_billing_preflight(
    billing: Optional[Dict[str, Any]],
    deployment_mode: str,
    *,
    client_id: Optional[str] = None,
    operation: str = "billing_portal",
) -> Dict[str, Any]:
    """Combined customer + subscription preflight for portal flows."""
    if not billing:
        return {"ok": True, "skipped": True}
    dep = normalize_persisted_mode(deployment_mode) or get_stripe_mode()
    stored_customer_mode = billing.get("stripe_customer_mode") or billing.get("stripe_mode")
    stored_sub_mode = billing.get("stripe_mode")
    cust_m = normalize_persisted_mode(stored_customer_mode)
    sub_m = normalize_persisted_mode(stored_sub_mode)
    if cust_m and sub_m and cust_m != sub_m:
        raise StripeModeDriftError(
            STRIPE_PORTAL_MODE_DRIFT,
            admin_reason="mixed_customer_subscription_mode",
            client_id=client_id,
            operation=operation,
            recovery_action="admin_billing_refresh",
        )
    verification_status = billing.get("stripe_mode_verification_status")
    confidence = billing.get("stripe_mode_confidence")
    validate_stripe_customer_mode(
        billing.get("stripe_customer_id"),
        dep,
        stored_mode=stored_customer_mode,
        verification_status=verification_status,
        confidence=confidence,
        client_id=client_id,
        operation=operation,
    )
    validate_stripe_subscription_mode(
        billing.get("stripe_subscription_id"),
        dep,
        stored_mode=stored_sub_mode,
        verification_status=verification_status,
        confidence=confidence,
        client_id=client_id,
        operation=operation,
    )
    return {"ok": True}


def validate_webhook_event_mode(
    event_livemode: Optional[bool],
    deployment_mode: str,
    *,
    client_id: Optional[str] = None,
) -> Dict[str, Any]:
    dep = normalize_persisted_mode(deployment_mode) or get_stripe_mode()
    if event_livemode is None:
        return {"ok": True, "skipped": True}
    expected_live = dep == "live"
    if bool(event_livemode) != expected_live:
        raise StripeModeDriftError(
            STRIPE_EVENT_MODE_DRIFT,
            admin_reason="webhook_livemode_mismatch",
            client_id=client_id,
            operation="webhook_ingress",
            inferred_mode="live" if event_livemode else "test",
        )
    return {"ok": True}


async def record_stripe_mode_drift(
    drift: StripeModeDriftError,
    *,
    deployment_mode: Optional[str] = None,
    actor_id: str = "system",
    actor_role: str = "SYSTEM",
) -> None:
    """Audit + metrics for drift events (operational cognition safe)."""
    dep = deployment_mode or get_stripe_mode()
    now = _now()
    event_doc = {
        "error_code": drift.error_code,
        "client_id": drift.client_id,
        "operation": drift.operation,
        "admin_reason": drift.admin_reason,
        "inferred_mode": drift.inferred_mode,
        "deployment_mode": dep,
        "recovery_action": drift.recovery_action,
        "created_at": now,
    }
    try:
        db = database.get_db()
        await db[COL_DRIFT_EVENTS].insert_one(event_doc)
        await db[COL_DRIFT_METRICS].update_one(
            {"scope": "global"},
            {
                "$inc": {"event_count": 1, f"by_code.{drift.error_code}": 1},
                "$set": {"last_event_at": now, "deployment_mode": dep},
            },
            upsert=True,
        )
    except Exception as exc:
        logger.warning("stripe_mode_drift metrics write failed: %s", exc)

    try:
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_role=actor_role,
            actor_id=actor_id,
            client_id=drift.client_id,
            metadata={
                "action_type": "STRIPE_MODE_DRIFT_DETECTED",
                "error_code": drift.error_code,
                "operation": drift.operation,
                "admin_reason": drift.admin_reason,
                "deployment_mode": dep,
                "recovery_action": drift.recovery_action,
            },
        )
    except Exception as exc:
        logger.warning("stripe_mode_drift audit failed: %s", exc)

    logger.warning(
        "STRIPE_MODE_DRIFT code=%s client_id=%s operation=%s reason=%s deployment=%s",
        drift.error_code,
        drift.client_id,
        drift.operation,
        drift.admin_reason,
        dep,
    )


async def resolve_stripe_context(
    *,
    client_id: Optional[str] = None,
    billing: Optional[Dict[str, Any]] = None,
    operation: str = "stripe_api",
    legacy_caller: Optional[str] = None,
    require_preflight: bool = False,
) -> Dict[str, Any]:
    """
    Authoritative mode resolution for Stripe operations.
    Configures SDK for deployment mode; optional preflight when billing row supplied.
    """
    deployment_mode = get_stripe_mode()
    secret_key = configure_stripe_sdk(mode=deployment_mode)

    if legacy_caller:
        logger.warning(
            "Legacy Stripe caller bypass instrumented: caller=%s operation=%s client_id=%s",
            legacy_caller,
            operation,
            client_id,
        )
        try:
            await create_audit_log(
                action=AuditAction.ADMIN_ACTION,
                actor_role="SYSTEM",
                actor_id="stripe_mode_containment",
                client_id=client_id,
                metadata={
                    "action_type": "STRIPE_LEGACY_CALLER_INSTRUMENTED",
                    "legacy_caller": legacy_caller,
                    "operation": operation,
                    "deployment_mode": deployment_mode,
                },
            )
        except Exception:
            pass

    row = billing
    if row is None and client_id:
        db = database.get_db()
        row = await db.client_billing.find_one({"client_id": client_id}, {"_id": 0})

    ctx: Dict[str, Any] = {
        "deployment_mode": deployment_mode,
        "secret_key_configured": bool(secret_key),
        "client_id": client_id,
        "operation": operation,
        "billing": row,
        "legacy_caller": legacy_caller,
    }

    if require_preflight and row:
        validate_portal_billing_preflight(
            row, deployment_mode, client_id=client_id, operation=operation
        )
        ctx["preflight"] = {"ok": True}

    return ctx


def billing_mode_fields_for_write(deployment_mode: Optional[str] = None) -> Dict[str, str]:
    """Fields to set on new billing/checkout writes."""
    mode = normalize_persisted_mode(deployment_mode) or get_stripe_mode()
    return {"stripe_mode": mode, "stripe_customer_mode": mode}


async def assess_billing_stripe_mode_drift(client_id: str) -> Dict[str, Any]:
    """
    Read-only billing mode drift for commercial entitlement / admin surfaces.
    Does not mutate entitlement or suspend access from drift alone.
    """
    db = database.get_db()
    billing = await db.client_billing.find_one({"client_id": client_id}, {"_id": 0})
    if not billing:
        return {"found": False, "drift_detected": False}

    deployment_mode = get_stripe_mode()
    issues: List[Dict[str, Any]] = []
    severity = "none"

    sub_id = (billing.get("stripe_subscription_id") or "").strip()
    cust_id = (billing.get("stripe_customer_id") or "").strip()
    stored_mode = normalize_persisted_mode(billing.get("stripe_mode"))
    cust_mode = normalize_persisted_mode(billing.get("stripe_customer_mode") or billing.get("stripe_mode"))

    if sub_id and stored_mode is None:
        issues.append({"code": STRIPE_SUBSCRIPTION_MODE_DRIFT, "reason": "missing_stripe_mode", "severity": "high"})
        severity = "high"
    elif sub_id and stored_mode and stored_mode != deployment_mode:
        issues.append(
            {
                "code": STRIPE_SUBSCRIPTION_MODE_DRIFT,
                "reason": "deployment_mismatch",
                "stored_mode": stored_mode,
                "severity": "critical",
            }
        )
        severity = "critical"

    if cust_id and cust_mode is None:
        issues.append({"code": STRIPE_CUSTOMER_MODE_DRIFT, "reason": "missing_stripe_customer_mode", "severity": "high"})
        if severity == "none":
            severity = "high"
    elif cust_id and cust_mode and cust_mode != deployment_mode:
        issues.append(
            {
                "code": STRIPE_CUSTOMER_MODE_DRIFT,
                "reason": "deployment_mismatch",
                "stored_mode": cust_mode,
                "severity": "critical",
            }
        )
        severity = "critical"

    if cust_mode and stored_mode and cust_mode != stored_mode:
        issues.append({"code": STRIPE_PORTAL_MODE_DRIFT, "reason": "mixed_customer_subscription_mode", "severity": "high"})
        if severity not in ("critical",):
            severity = "high"

    remediation_code = None
    remediation_path = None
    if issues:
        try:
            from services.stripe_mode_backfill_service import (
                classify_remediation,
                resolve_authoritative_mode,
            )

            resolution = await resolve_authoritative_mode(client_id, billing=billing)
            remediation_code, _, remediation_path = classify_remediation(
                billing, resolution, deployment_mode=deployment_mode
            )
        except Exception:
            remediation_code = "MODE_UNVERIFIED"

    return {
        "found": True,
        "client_id": client_id,
        "drift_detected": bool(issues),
        "severity": severity,
        "deployment_mode": deployment_mode,
        "stored_stripe_mode": stored_mode,
        "issues": issues,
        "remediation_code": remediation_code,
        "recommended_remediation_path": remediation_path,
        "recovery_action": "admin_billing_refresh" if issues else None,
        "entitlement_note": (
            "Billing mode drift does not invalidate platform governance alone; "
            "Stripe billing operations are blocked until refresh."
        ),
    }


def _classify_billing_row(
    billing: Dict[str, Any],
    deployment_mode: str,
) -> Dict[str, Any]:
    client_id = billing.get("client_id")
    sub_id = (billing.get("stripe_subscription_id") or "").strip()
    cust_id = (billing.get("stripe_customer_id") or "").strip()
    stored = normalize_persisted_mode(billing.get("stripe_mode"))
    cust_mode = normalize_persisted_mode(billing.get("stripe_customer_mode") or billing.get("stripe_mode"))

    risk = "none"
    findings: List[str] = []
    recovery = None

    if sub_id and stored is None:
        findings.append("missing_stripe_mode")
        risk = "high"
        recovery = "backfill_stripe_mode_or_regenerate_checkout"
    elif stored and stored != deployment_mode:
        findings.append(f"subscription_mode_{stored}_in_{deployment_mode}_deployment")
        risk = "critical"
        recovery = "regenerate_checkout_in_deployment_mode"

    if cust_id and cust_mode and stored and cust_mode != stored:
        findings.append("mixed_customer_subscription_mode")
        risk = "high" if risk != "critical" else risk
        recovery = recovery or "admin_billing_refresh"

    if cust_id and cust_mode and cust_mode != deployment_mode:
        findings.append(f"customer_mode_{cust_mode}_in_{deployment_mode}_deployment")
        risk = "critical"

    return {
        "client_id": client_id,
        "stripe_subscription_id_present": bool(sub_id),
        "stripe_customer_id_present": bool(cust_id),
        "stored_stripe_mode": stored,
        "stored_stripe_customer_mode": cust_mode,
        "deployment_mode": deployment_mode,
        "inferred_mode": stored or cust_mode,
        "findings": findings,
        "risk_severity": risk,
        "recommended_recovery_action": recovery,
    }


async def build_stripe_mode_inventory(*, limit: int = 500, expanded: bool = False) -> Dict[str, Any]:
    """Read-only ops inventory — no automatic repair."""
    if expanded:
        from services.stripe_mode_backfill_service import build_expanded_stripe_mode_inventory

        return await build_expanded_stripe_mode_inventory(limit=limit)

    db = database.get_db()
    deployment_mode = get_stripe_mode()
    now = _now()

    billing_cursor = db.client_billing.find(
        {
            "$or": [
                {"stripe_subscription_id": {"$nin": [None, ""]}},
                {"stripe_customer_id": {"$nin": [None, ""]}},
            ]
        },
        {"_id": 0},
    ).limit(limit)

    rows: List[Dict[str, Any]] = []
    summary = {
        "missing_stripe_mode": 0,
        "mode_mismatch": 0,
        "mixed_customer_subscription": 0,
        "critical": 0,
        "high": 0,
    }

    async for doc in billing_cursor:
        classified = _classify_billing_row(doc, deployment_mode)
        if classified["findings"]:
            rows.append(classified)
            for f in classified["findings"]:
                if f == "missing_stripe_mode":
                    summary["missing_stripe_mode"] += 1
                elif f == "mixed_customer_subscription_mode":
                    summary["mixed_customer_subscription"] += 1
                elif "mode_" in f:
                    summary["mode_mismatch"] += 1
            if classified["risk_severity"] == "critical":
                summary["critical"] += 1
            elif classified["risk_severity"] == "high":
                summary["high"] += 1

    orphaned_checkouts = await db.checkout_sessions.count_documents(
        {
            "status": "pending",
            "$or": [{"stripe_mode": {"$exists": False}}, {"stripe_mode": None}],
        }
    )
    pending_wrong_mode = 0
    async for ch in db.checkout_sessions.find(
        {"status": "pending", "stripe_mode": {"$exists": True, "$ne": None}},
        {"_id": 0, "stripe_mode": 1},
    ).limit(limit):
        if normalize_persisted_mode(ch.get("stripe_mode")) != deployment_mode:
            pending_wrong_mode += 1

    return {
        "generated_at": now.isoformat(),
        "deployment_mode": deployment_mode,
        "read_only": True,
        "summary": {
            **summary,
            "affected_clients": len(rows),
            "orphaned_checkout_sessions_missing_mode": orphaned_checkouts,
            "pending_checkout_sessions_wrong_mode": pending_wrong_mode,
        },
        "affected_billing_rows": rows[:100],
        "truncated": len(rows) > 100,
    }


async def handle_stripe_api_drift_safe(
    exc: Exception,
    *,
    client_id: Optional[str] = None,
    operation: str = "stripe_api",
) -> StripeModeDriftError:
    """Convert Stripe API mode errors to customer-safe drift (post-call safety net)."""
    code = classify_stripe_api_error_for_drift(exc) or STRIPE_SUBSCRIPTION_MODE_DRIFT
    drift = StripeModeDriftError(
        code,
        admin_reason="stripe_api_mode_error",
        client_id=client_id,
        operation=operation,
    )
    await record_stripe_mode_drift(drift)
    return drift
