"""
Phase 3 — client-by-client MODE_UNVERIFIED remediation worklist and safe classification.

No bulk mode assignment. No deployment-mode inference. No automatic Stripe mutation.
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from database import database
from services.stripe_mode_authority import get_stripe_mode
from services.stripe_mode_backfill_service import (
    CONFIDENCE_AUTHORITATIVE,
    MODE_UNVERIFIED,
    REMEDIATION_CUSTOMER_RECONCILIATION,
    REMEDIATION_LEGACY_TEST,
    REMEDIATION_MODE_UNVERIFIED,
    REMEDIATION_REGENERATE_CHECKOUT,
    REMEDIATION_PORTAL_RELINK,
    classify_remediation,
    resolve_authoritative_mode,
)
from services.stripe_mode_containment_service import CUSTOMER_BILLING_REFRESH_MESSAGE

VERIFICATION_SOURCE_ADMIN_VERIFIED = "admin_verified"

RECOMMENDED_ACTION_ADMIN_SET_MODE = "ADMIN_SET_MODE_REQUIRED"
RECOMMENDED_ACTION_REGENERATE_CHECKOUT = "REGENERATE_CHECKOUT_REQUIRED"
RECOMMENDED_ACTION_LEGACY_TEST = "LEGACY_TEST_SUBSCRIPTION"
RECOMMENDED_ACTION_INVALID_SUBSCRIPTION = "INVALID_SUBSCRIPTION_REFERENCE"
RECOMMENDED_ACTION_PORTAL_RELINK = "PORTAL_RELINK_REQUIRED"
RECOMMENDED_ACTION_CUSTOMER_RECONCILIATION = "CUSTOMER_RECONCILIATION_REQUIRED"
RECOMMENDED_ACTION_NO_ACTION_INACTIVE = "NO_ACTION_IF_INACTIVE"

INACTIVE_STATUSES = frozenset(
    {
        "CANCELED",
        "CANCELLED",
        "UNPAID",
        "INCOMPLETE_EXPIRED",
        "INCOMPLETE",
        "PAUSED",
    }
)

REMEDIATION_POLICY: Dict[str, Any] = {
    "version": "phase3_stripe_mode_client_remediation_01",
    "admin_set_mode_allowed_when": [
        "Stripe subscription or customer manually verified in the correct Stripe dashboard (test vs live)",
        "Webhook livemode evidence exists for the client or subscription",
        "Checkout session with persisted stripe_mode exists for the client",
        "Admin documents source of truth in remediation reason (min 10 chars)",
    ],
    "admin_set_mode_forbidden": [
        "Deployment STRIPE_MODE alone",
        "Object ID prefix (sub_, cus_, cs_)",
        "Assumption from current app environment without Stripe dashboard confirmation",
        "Bulk assignment across clients",
        "Automatic subscription migration, cancellation, or recreation",
    ],
    "regenerate_checkout_when": [
        "MODE_UNVERIFIED with active subscription intent",
        "No authoritative webhook or checkout evidence",
        "Invalid or stale subscription reference after admin review",
    ],
    "customer_safe_message": CUSTOMER_BILLING_REFRESH_MESSAGE,
    "regeneration_customer_copy": (
        "We need to refresh your billing record before plan changes can continue. "
        "Use the secure payment link we provide to complete checkout — your account and "
        "reference number stay the same."
    ),
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _redact_client_id(client_id: Optional[str]) -> Optional[str]:
    if not client_id:
        return None
    s = str(client_id).strip()
    return f"{s[:8]}…{hashlib.sha256(s.encode()).hexdigest()[:8]}"


def _redact_email(email: Optional[str]) -> Optional[str]:
    if not email or "@" not in str(email):
        return None
    local, domain = str(email).split("@", 1)
    return f"{local[:2]}…@{domain}"


def _redact_stripe_id(sid: Optional[str]) -> Optional[str]:
    if not sid:
        return None
    s = str(sid).strip()
    return f"{s[:8]}…{hashlib.sha256(s.encode()).hexdigest()[:6]}"


def remediation_code_to_recommended_action(
    remediation_code: str,
    *,
    subscription_status: Optional[str],
    has_webhook: bool,
    has_checkout: bool,
) -> str:
    status = (subscription_status or "").strip().upper()
    if status in INACTIVE_STATUSES and not has_webhook and not has_checkout:
        return RECOMMENDED_ACTION_NO_ACTION_INACTIVE

    mapping = {
        REMEDIATION_MODE_UNVERIFIED: RECOMMENDED_ACTION_ADMIN_SET_MODE,
        REMEDIATION_REGENERATE_CHECKOUT: RECOMMENDED_ACTION_REGENERATE_CHECKOUT,
        REMEDIATION_LEGACY_TEST: RECOMMENDED_ACTION_LEGACY_TEST,
        "INVALID_SUBSCRIPTION_REFERENCE": RECOMMENDED_ACTION_INVALID_SUBSCRIPTION,
        REMEDIATION_PORTAL_RELINK: RECOMMENDED_ACTION_PORTAL_RELINK,
        REMEDIATION_CUSTOMER_RECONCILIATION: RECOMMENDED_ACTION_CUSTOMER_RECONCILIATION,
        "VERIFIED_OPERATIONALLY": "VERIFIED_NO_ACTION",
    }
    code = remediation_code or REMEDIATION_MODE_UNVERIFIED
    if code == REMEDIATION_MODE_UNVERIFIED:
        if has_webhook or has_checkout:
            return RECOMMENDED_ACTION_ADMIN_SET_MODE
        return RECOMMENDED_ACTION_REGENERATE_CHECKOUT
    return mapping.get(code, RECOMMENDED_ACTION_ADMIN_SET_MODE)


async def _client_evidence_flags(
    db,
    *,
    client_id: str,
    subscription_id: Optional[str],
) -> Dict[str, bool]:
    sub_id = (subscription_id or "").strip()
    wh_query: Dict[str, Any] = {"livemode": {"$exists": True, "$ne": None}}
    or_clauses: List[Dict[str, Any]] = [{"related_client_id": client_id}]
    if sub_id:
        or_clauses.append({"related_subscription_id": sub_id})
    wh_query["$or"] = or_clauses
    webhook = await db.stripe_events.find_one(wh_query, {"_id": 1})
    checkout = await db.checkout_sessions.find_one(
        {"client_id": client_id},
        {"_id": 1},
    )
    checkout_with_mode = await db.checkout_sessions.find_one(
        {"client_id": client_id, "stripe_mode": {"$in": ["test", "live"]}},
        {"_id": 1},
    )
    return {
        "webhook_evidence_present": bool(webhook),
        "checkout_session_present": bool(checkout),
        "checkout_with_stripe_mode_present": bool(checkout_with_mode),
    }


async def build_client_remediation_worklist(*, limit: int = 500) -> Dict[str, Any]:
    """Redacted per-client remediation worklist from staging/production Mongo."""
    db = database.get_db()
    deployment_mode = get_stripe_mode()
    now = _now()

    cursor = db.client_billing.find(
        {
            "$or": [
                {"stripe_subscription_id": {"$nin": [None, ""]}},
                {"stripe_customer_id": {"$nin": [None, ""]}},
            ]
        },
        {"_id": 0},
    ).limit(limit)

    rows: List[Dict[str, Any]] = []
    action_counts: Dict[str, int] = {}

    async for billing in cursor:
        client_id = billing.get("client_id")
        if not client_id:
            continue

        client_doc = await db.clients.find_one(
            {"client_id": client_id},
            {"_id": 0, "email": 1, "customer_reference": 1},
        )
        evidence = await _client_evidence_flags(
            db,
            client_id=client_id,
            subscription_id=billing.get("stripe_subscription_id"),
        )
        resolution = await resolve_authoritative_mode(client_id, billing=billing)
        remediation_code, risk, path = classify_remediation(
            billing, resolution, deployment_mode=deployment_mode
        )
        sub_status = (billing.get("subscription_status") or "").strip()
        recommended = remediation_code_to_recommended_action(
            remediation_code,
            subscription_status=sub_status,
            has_webhook=evidence["webhook_evidence_present"],
            has_checkout=evidence["checkout_with_stripe_mode_present"],
        )
        action_counts[recommended] = action_counts.get(recommended, 0) + 1

        rows.append(
            {
                "client_id_redacted": _redact_client_id(client_id),
                "email_redacted": _redact_email((client_doc or {}).get("email")),
                "customer_reference_redacted": _redact_client_id((client_doc or {}).get("customer_reference")),
                "stripe_customer_id_present": bool((billing.get("stripe_customer_id") or "").strip()),
                "stripe_subscription_id_present": bool((billing.get("stripe_subscription_id") or "").strip()),
                "stripe_customer_id_redacted": _redact_stripe_id(billing.get("stripe_customer_id")),
                "stripe_subscription_id_redacted": _redact_stripe_id(billing.get("stripe_subscription_id")),
                "checkout_sessions_present": evidence["checkout_session_present"],
                "checkout_with_stripe_mode_present": evidence["checkout_with_stripe_mode_present"],
                "webhook_evidence_present": evidence["webhook_evidence_present"],
                "subscription_status": sub_status or None,
                "stored_stripe_mode": billing.get("stripe_mode"),
                "verification_status": billing.get("stripe_mode_verification_status"),
                "confidence": billing.get("stripe_mode_confidence"),
                "remediation_code": remediation_code,
                "recommended_action": recommended,
                "risk_level": risk,
                "recommended_remediation_path": path,
                "resolution_confidence": resolution.get("stripe_mode_confidence"),
            }
        )

    return {
        "generated_at": now.isoformat(),
        "deployment_mode": deployment_mode,
        "read_only": True,
        "total_clients": len(rows),
        "recommended_action_counts": action_counts,
        "clients": rows,
    }


async def classify_orphaned_checkout_sessions(*, limit: int = 200) -> Dict[str, Any]:
    """Classify checkout sessions missing authoritative stripe_mode — no deletes."""
    db = database.get_db()
    deployment_mode = get_stripe_mode()
    now = _now()

    categories: Dict[str, List[Dict[str, Any]]] = {
        "expired_abandoned_checkout": [],
        "linked_client_no_subscription": [],
        "duplicate_checkout": [],
        "recovery_checkout": [],
        "safe_to_ignore": [],
        "requires_regeneration": [],
    }
    counts = {k: 0 for k in categories}

    seen_client_pending: Dict[str, int] = {}

    async for ch in db.checkout_sessions.find(
        {},
        {"_id": 0},
    ).limit(limit * 2):
        mode = (ch.get("stripe_mode") or "").strip().lower()
        status = (ch.get("status") or "").strip().lower()
        client_id = ch.get("client_id")
        session_id = ch.get("session_id") or ch.get("stripe_session_id")

        missing_mode = mode not in ("test", "live")
        is_pending = status == "pending"
        if not missing_mode and not is_pending:
            continue

        billing = None
        if client_id:
            billing = await db.client_billing.find_one({"client_id": client_id}, {"_id": 0})
            seen_client_pending[client_id] = seen_client_pending.get(client_id, 0) + 1

        classification = "requires_regeneration"
        if status in ("expired", "complete", "completed") and missing_mode:
            classification = "expired_abandoned_checkout"
        elif is_pending and missing_mode:
            classification = "requires_regeneration"
        elif client_id and billing and not (billing.get("stripe_subscription_id") or "").strip():
            classification = "linked_client_no_subscription"
        elif client_id and seen_client_pending.get(client_id, 0) > 1:
            classification = "duplicate_checkout"
        elif ch.get("recovery") or ch.get("metadata", {}).get("recovery"):
            classification = "recovery_checkout"
        elif status in ("expired",) and not client_id:
            classification = "safe_to_ignore"

        entry = {
            "session_id_redacted": _redact_stripe_id(session_id),
            "client_id_redacted": _redact_client_id(client_id),
            "status": status,
            "stripe_mode": ch.get("stripe_mode"),
            "classification": classification,
        }
        if len(categories.get(classification, [])) < 50:
            categories[classification].append(entry)
        counts[classification] = counts.get(classification, 0) + 1

    return {
        "generated_at": now.isoformat(),
        "deployment_mode": deployment_mode,
        "read_only": True,
        "no_automatic_deletion": True,
        "summary": counts,
        "categories": categories,
        "total_classified": sum(counts.values()),
    }


def get_remediation_policy() -> Dict[str, Any]:
    return {**REMEDIATION_POLICY, "generated_at": _now().isoformat()}


def get_regenerate_checkout_flow_spec() -> Dict[str, Any]:
    """Document safe regenerate-checkout path (no automatic execution)."""
    return {
        "generated_at": _now().isoformat(),
        "endpoint": "POST /api/billing/checkout",
        "preflight": "validate_portal_billing_preflight / upgrade preflight via stripe_service",
        "stripe_mode_persistence": "checkout_sessions.stripe_mode set on insert (stripe_service)",
        "preserves": ["client_id", "customer_reference (CRN on clients row)", "client_billing row"],
        "forbidden": [
            "duplicate_subscription_automatic_creation",
            "silent_mode_from_deployment_only",
            "delete_client_billing_row",
        ],
        "steps": [
            "Admin confirms MODE_UNVERIFIED and REGENERATE_CHECKOUT_REQUIRED classification",
            "Customer sees billing refresh message (no Stripe jargon)",
            "Admin or customer triggers POST /api/billing/checkout with target plan",
            "resolve_stripe_context + configure_stripe_sdk use deployment STRIPE_MODE for new session only",
            "New checkout_sessions row persists stripe_mode from billing_mode_fields_for_write",
            "Webhook checkout.session.completed provides authoritative livemode evidence",
            "Optional admin-set-mode only after dashboard verification if webhook delayed",
        ],
        "customer_copy": REMEDIATION_POLICY["regeneration_customer_copy"],
    }


def get_customer_copy_runtime() -> Dict[str, Any]:
    return {
        "generated_at": _now().isoformat(),
        "blocked_plan_change_message": CUSTOMER_BILLING_REFRESH_MESSAGE,
        "regeneration_message": REMEDIATION_POLICY["regeneration_customer_copy"],
        "forbidden_in_customer_ui": ["livemode", "test mode", "sk_", "webhook", "STRIPE_"],
        "source": "services/stripe_mode_containment_service.CUSTOMER_BILLING_REFRESH_MESSAGE",
    }
