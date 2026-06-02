"""
Stripe mode backfill — Phase 2 authoritative mode resolution and safe persistence.

No automatic subscription mutation, cancellation, recreation, or environment switching.
Backfill only when confidence is authoritative; unverifiable rows become MODE_UNVERIFIED.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import stripe
from database import database
from models import AuditAction
from services.stripe_mode_authority import configure_stripe_sdk, get_stripe_mode
from services.stripe_mode_containment_service import (
    CUSTOMER_BILLING_REFRESH_MESSAGE,
    normalize_persisted_mode,
)
from utils.audit import create_audit_log

logger = logging.getLogger(__name__)

COL_BACKFILL_AUDIT = "stripe_mode_backfill_audit"
COL_INVENTORY_METRICS = "stripe_mode_inventory_metrics"

VERIFICATION_SOURCE_WEBHOOK = "webhook_livemode"
VERIFICATION_SOURCE_CHECKOUT = "checkout_session"
VERIFICATION_SOURCE_DEPLOYMENT = "deployment_at_creation"
VERIFICATION_SOURCE_STRIPE_API = "stripe_api_verify"
VERIFICATION_SOURCE_ADMIN = "admin_remediation"

CONFIDENCE_AUTHORITATIVE = "authoritative"
CONFIDENCE_UNKNOWN = "unknown"

MODE_UNVERIFIED = "MODE_UNVERIFIED"

REMEDIATION_REGENERATE_CHECKOUT = "REGENERATE_CHECKOUT_REQUIRED"
REMEDIATION_INVALID_SUBSCRIPTION = "INVALID_SUBSCRIPTION_REFERENCE"
REMEDIATION_LEGACY_TEST = "LEGACY_TEST_SUBSCRIPTION"
REMEDIATION_MODE_UNVERIFIED = "MODE_UNVERIFIED"
REMEDIATION_PORTAL_RELINK = "PORTAL_RELINK_REQUIRED"
REMEDIATION_CUSTOMER_RECONCILIATION = "CUSTOMER_RECONCILIATION_REQUIRED"

ALL_REMEDIATION_CODES = frozenset(
    {
        REMEDIATION_REGENERATE_CHECKOUT,
        REMEDIATION_INVALID_SUBSCRIPTION,
        REMEDIATION_LEGACY_TEST,
        REMEDIATION_MODE_UNVERIFIED,
        REMEDIATION_PORTAL_RELINK,
        REMEDIATION_CUSTOMER_RECONCILIATION,
    }
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _livemode_to_mode(livemode: Optional[bool]) -> Optional[str]:
    if livemode is None:
        return None
    return "live" if livemode else "test"


async def _resolve_from_webhook_events(
    db,
    *,
    client_id: str,
    subscription_id: Optional[str],
) -> Optional[Dict[str, Any]]:
    """Priority 1: verified webhook livemode on related events."""
    query: Dict[str, Any] = {"livemode": {"$exists": True, "$ne": None}}
    or_clauses: List[Dict[str, Any]] = [{"related_client_id": client_id}]
    if subscription_id:
        or_clauses.append({"related_subscription_id": subscription_id})
    query["$or"] = or_clauses

    event = await db.stripe_events.find_one(
        query,
        {"_id": 0, "livemode": 1, "event_id": 1, "created": 1, "environment_source": 1},
        sort=[("created", -1)],
    )
    if not event or event.get("livemode") is None:
        return None
    mode = _livemode_to_mode(event.get("livemode"))
    if not mode:
        return None
    return {
        "stripe_mode": mode,
        "stripe_mode_verification_source": VERIFICATION_SOURCE_WEBHOOK,
        "stripe_mode_confidence": CONFIDENCE_AUTHORITATIVE,
        "inferred_mode_source": "webhook_livemode",
        "evidence_event_id": event.get("event_id"),
    }


async def _resolve_from_checkout_sessions(
    db,
    *,
    client_id: str,
) -> Optional[Dict[str, Any]]:
    """Priority 2: persisted checkout creation context."""
    session = await db.checkout_sessions.find_one(
        {
            "client_id": client_id,
            "stripe_mode": {"$exists": True, "$nin": [None, ""]},
        },
        {"_id": 0, "stripe_mode": 1, "session_id": 1, "status": 1, "created_at": 1},
        sort=[("created_at", -1)],
    )
    if not session:
        return None
    mode = normalize_persisted_mode(session.get("stripe_mode"))
    if not mode:
        return None
    return {
        "stripe_mode": mode,
        "stripe_mode_verification_source": VERIFICATION_SOURCE_CHECKOUT,
        "stripe_mode_confidence": CONFIDENCE_AUTHORITATIVE,
        "inferred_mode_source": "checkout_session",
        "evidence_session_id": session.get("session_id"),
    }


def _resolve_from_deployment_at_creation(
    billing: Dict[str, Any],
    deployment_mode: str,
) -> Optional[Dict[str, Any]]:
    """Priority 3: explicit deployment mode stamped at creation (if present)."""
    created_mode = normalize_persisted_mode(billing.get("stripe_mode_at_creation"))
    if created_mode:
        return {
            "stripe_mode": created_mode,
            "stripe_mode_verification_source": VERIFICATION_SOURCE_DEPLOYMENT,
            "stripe_mode_confidence": CONFIDENCE_AUTHORITATIVE,
            "inferred_mode_source": "deployment_at_creation",
        }
    # Only use current deployment if billing row was created with stripe_mode field on write
    # and has never had a conflicting mode — not for legacy rows missing all verification.
    existing = normalize_persisted_mode(billing.get("stripe_mode"))
    confidence = (billing.get("stripe_mode_confidence") or "").strip().lower()
    if existing and confidence == CONFIDENCE_AUTHORITATIVE:
        return {
            "stripe_mode": existing,
            "stripe_mode_verification_source": billing.get("stripe_mode_verification_source")
            or VERIFICATION_SOURCE_DEPLOYMENT,
            "stripe_mode_confidence": CONFIDENCE_AUTHORITATIVE,
            "inferred_mode_source": "persisted_authoritative",
        }
    if existing and existing == deployment_mode and billing.get("stripe_mode_verified_at"):
        return {
            "stripe_mode": existing,
            "stripe_mode_verification_source": billing.get("stripe_mode_verification_source")
            or VERIFICATION_SOURCE_DEPLOYMENT,
            "stripe_mode_confidence": CONFIDENCE_AUTHORITATIVE,
            "inferred_mode_source": "verified_persisted",
        }
    return None


async def _resolve_from_stripe_api(
    billing: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """
    Priority 4: Stripe API verification using correct environment keys.
    Never infer mode from ID prefix — only successful retrieve in one environment.
    """
    sub_id = (billing.get("stripe_subscription_id") or "").strip()
    cust_id = (billing.get("stripe_customer_id") or "").strip()
    target_id = sub_id or cust_id
    if not target_id:
        return None

    found_modes: List[str] = []
    for mode in ("test", "live"):
        try:
            configure_stripe_sdk(mode=mode)
            if sub_id:
                stripe.Subscription.retrieve(sub_id)
            else:
                stripe.Customer.retrieve(cust_id)
            found_modes.append(mode)
        except Exception:
            continue

    if len(found_modes) == 1:
        return {
            "stripe_mode": found_modes[0],
            "stripe_mode_verification_source": VERIFICATION_SOURCE_STRIPE_API,
            "stripe_mode_confidence": CONFIDENCE_AUTHORITATIVE,
            "inferred_mode_source": "stripe_api_verify",
        }
    return None


def classify_remediation(
    billing: Dict[str, Any],
    resolution: Optional[Dict[str, Any]],
    *,
    deployment_mode: str,
) -> Tuple[str, str, str]:
    """
    Returns (remediation_code, operational_risk, recommended_path).
    """
    sub_id = (billing.get("stripe_subscription_id") or "").strip()
    cust_id = (billing.get("stripe_customer_id") or "").strip()
    stored = normalize_persisted_mode(billing.get("stripe_mode"))
    cust_mode = normalize_persisted_mode(
        billing.get("stripe_customer_mode") or billing.get("stripe_mode")
    )
    dep = normalize_persisted_mode(deployment_mode) or get_stripe_mode()
    verification_status = (billing.get("stripe_mode_verification_status") or "").strip()

    if verification_status == MODE_UNVERIFIED or (
        resolution and resolution.get("stripe_mode_confidence") == CONFIDENCE_UNKNOWN
    ):
        return (
            REMEDIATION_MODE_UNVERIFIED,
            "high",
            "Admin must verify Stripe environment and apply explicit remediation; "
            "plan changes remain blocked with customer-safe messaging.",
        )

    if not resolution or resolution.get("stripe_mode_confidence") != CONFIDENCE_AUTHORITATIVE:
        if sub_id or cust_id:
            return (
                REMEDIATION_MODE_UNVERIFIED,
                "high",
                "Run authoritative backfill or admin remediation; do not guess mode from ID prefix.",
            )
        return (REMEDIATION_MODE_UNVERIFIED, "none", "No Stripe identifiers — no action required.")

    resolved_mode = normalize_persisted_mode(resolution.get("stripe_mode"))

    if cust_mode and stored and cust_mode != stored:
        return (
            REMEDIATION_PORTAL_RELINK,
            "high",
            "Reconcile customer and subscription mode; regenerate checkout or relink portal in authoritative mode.",
        )

    if resolved_mode and resolved_mode != dep:
        if resolved_mode == "test" and dep == "live":
            return (
                REMEDIATION_LEGACY_TEST,
                "critical",
                "Legacy test subscription in live deployment — regenerate checkout in live mode; "
                "do not auto-migrate subscription.",
            )
        return (
            REMEDIATION_REGENERATE_CHECKOUT,
            "critical",
            "Regenerate checkout in deployment-authoritative mode; clear invalid legacy references.",
        )

    if sub_id and not stored:
        return (
            REMEDIATION_REGENERATE_CHECKOUT,
            "high",
            "Backfill authoritative stripe_mode or regenerate checkout if subscription reference is stale.",
        )

    if cust_id and not cust_mode:
        return (
            REMEDIATION_CUSTOMER_RECONCILIATION,
            "high",
            "Reconcile Stripe customer mode with subscription; relink if portal customer is wrong environment.",
        )

    if sub_id and resolution.get("stripe_mode_verification_source") == VERIFICATION_SOURCE_STRIPE_API:
        return ("VERIFIED_OPERATIONALLY", "none", "Authoritative mode verified via Stripe API.")

    return ("VERIFIED_OPERATIONALLY", "none", "No remediation required.")


async def resolve_authoritative_mode(
    client_id: str,
    *,
    billing: Optional[Dict[str, Any]] = None,
    admin_mode: Optional[str] = None,
    admin_actor: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Authoritative resolution order (never silent default):
    1. webhook livemode
    2. checkout session context
    3. deployment at creation / verified persisted
    4. Stripe API verify
    5. explicit admin remediation
    6. UNKNOWN
    """
    db = database.get_db()
    row = billing
    if row is None:
        row = await db.client_billing.find_one({"client_id": client_id}, {"_id": 0})
    if not row:
        return {
            "client_id": client_id,
            "found": False,
            "stripe_mode_confidence": CONFIDENCE_UNKNOWN,
            "stripe_mode_verification_status": MODE_UNVERIFIED,
        }

    deployment_mode = get_stripe_mode()
    sub_id = (row.get("stripe_subscription_id") or "").strip()
    now = _now()

    if admin_mode and admin_actor:
        mode = normalize_persisted_mode(admin_mode)
        if mode:
            return {
                "client_id": client_id,
                "found": True,
                "stripe_mode": mode,
                "stripe_mode_verification_source": VERIFICATION_SOURCE_ADMIN,
                "stripe_mode_confidence": CONFIDENCE_AUTHORITATIVE,
                "stripe_mode_verified_at": now,
                "stripe_mode_last_checked_at": now,
                "inferred_mode_source": "admin_remediation",
                "admin_actor": admin_actor,
            }

    resolution_candidates: List[Optional[Dict[str, Any]]] = [
        await _resolve_from_webhook_events(db, client_id=client_id, subscription_id=sub_id),
        await _resolve_from_checkout_sessions(db, client_id=client_id),
        _resolve_from_deployment_at_creation(row, deployment_mode),
        await _resolve_from_stripe_api(row),
    ]
    for result in resolution_candidates:
        if result and result.get("stripe_mode_confidence") == CONFIDENCE_AUTHORITATIVE:
            result.update(
                {
                    "client_id": client_id,
                    "found": True,
                    "stripe_mode_verified_at": now,
                    "stripe_mode_last_checked_at": now,
                }
            )
            code, risk, path = classify_remediation(row, result, deployment_mode=deployment_mode)
            result["remediation_code"] = code
            result["operational_risk"] = risk
            result["recommended_remediation_path"] = path
            return result

    code, risk, path = classify_remediation(row, None, deployment_mode=deployment_mode)
    return {
        "client_id": client_id,
        "found": True,
        "stripe_mode_confidence": CONFIDENCE_UNKNOWN,
        "stripe_mode_verification_status": MODE_UNVERIFIED,
        "stripe_mode_verification_source": "unknown",
        "stripe_mode_last_checked_at": now,
        "inferred_mode_source": "unknown",
        "remediation_code": code,
        "operational_risk": risk,
        "recommended_remediation_path": path,
        "customer_message": CUSTOMER_BILLING_REFRESH_MESSAGE,
    }


async def backfill_client_billing_mode(
    client_id: str,
    *,
    dry_run: bool = True,
    admin_actor: Optional[str] = None,
    admin_mode: Optional[str] = None,
) -> Dict[str, Any]:
    """Safe backfill — only writes when confidence is authoritative."""
    db = database.get_db()
    billing = await db.client_billing.find_one({"client_id": client_id}, {"_id": 0})
    if not billing:
        return {"client_id": client_id, "found": False, "dry_run": dry_run, "action": "skipped"}

    resolution = await resolve_authoritative_mode(
        client_id, billing=billing, admin_mode=admin_mode, admin_actor=admin_actor
    )
    now = _now()
    result: Dict[str, Any] = {
        "client_id": client_id,
        "dry_run": dry_run,
        "resolution": resolution,
    }

    if resolution.get("stripe_mode_confidence") != CONFIDENCE_AUTHORITATIVE:
        unverified_doc = {
            "stripe_mode_verification_status": MODE_UNVERIFIED,
            "stripe_mode_confidence": CONFIDENCE_UNKNOWN,
            "stripe_mode_verification_source": resolution.get("stripe_mode_verification_source", "unknown"),
            "stripe_mode_last_checked_at": now,
        }
        result["action"] = "mark_mode_unverified"
        result["would_write"] = unverified_doc
        if not dry_run:
            await db.client_billing.update_one({"client_id": client_id}, {"$set": unverified_doc})
            await _record_backfill_audit(
                client_id=client_id,
                action="mark_mode_unverified",
                resolution=resolution,
                admin_actor=admin_actor,
            )
        return result

    mode = normalize_persisted_mode(resolution.get("stripe_mode"))
    write_doc: Dict[str, Any] = {
        "stripe_mode": mode,
        "stripe_mode_verification_source": resolution.get("stripe_mode_verification_source"),
        "stripe_mode_verified_at": resolution.get("stripe_mode_verified_at") or now,
        "stripe_mode_confidence": CONFIDENCE_AUTHORITATIVE,
        "stripe_mode_last_checked_at": now,
    }
    if (billing.get("stripe_customer_id") or "").strip():
        write_doc["stripe_customer_mode"] = mode
    write_doc.pop("stripe_mode_verification_status", None)

    result["action"] = "backfill_authoritative_mode"
    result["would_write"] = write_doc
    if not dry_run:
        await db.client_billing.update_one({"client_id": client_id}, {"$set": write_doc})
        await _record_backfill_audit(
            client_id=client_id,
            action="backfill_authoritative_mode",
            resolution=resolution,
            write_doc=write_doc,
            admin_actor=admin_actor,
        )
    return result


async def run_backfill_batch(
    *,
    limit: int = 100,
    dry_run: bool = True,
    admin_actor: Optional[str] = None,
) -> Dict[str, Any]:
    """Batch backfill for legacy rows missing authoritative stripe_mode."""
    db = database.get_db()
    cursor = db.client_billing.find(
        {
            "$or": [
                {"stripe_mode": {"$in": [None, ""]}},
                {"stripe_mode_confidence": CONFIDENCE_UNKNOWN},
                {"stripe_mode_verification_status": MODE_UNVERIFIED},
            ],
            "$and": [
                {
                    "$or": [
                        {"stripe_subscription_id": {"$nin": [None, ""]}},
                        {"stripe_customer_id": {"$nin": [None, ""]}},
                    ]
                }
            ],
        },
        {"_id": 0, "client_id": 1},
    ).limit(limit)

    results: List[Dict[str, Any]] = []
    summary = {"verified": 0, "unverified": 0, "skipped": 0}

    async for doc in cursor:
        cid = doc.get("client_id")
        if not cid:
            continue
        r = await backfill_client_billing_mode(
            cid, dry_run=dry_run, admin_actor=admin_actor
        )
        results.append(r)
        action = r.get("action", "skipped")
        if action == "backfill_authoritative_mode":
            summary["verified"] += 1
        elif action == "mark_mode_unverified":
            summary["unverified"] += 1
        else:
            summary["skipped"] += 1

    batch_result = {
        "generated_at": _now().isoformat(),
        "dry_run": dry_run,
        "limit": limit,
        "summary": summary,
        "results": results[:50],
        "truncated": len(results) > 50,
        "total_processed": len(results),
    }
    await _update_inventory_metrics(batch_result)
    return batch_result


async def get_remediation_guidance(client_id: str) -> Dict[str, Any]:
    """Admin remediation guidance for a client — no destructive mutation."""
    db = database.get_db()
    billing = await db.client_billing.find_one({"client_id": client_id}, {"_id": 0})
    if not billing:
        return {"found": False, "client_id": client_id}

    resolution = await resolve_authoritative_mode(client_id, billing=billing)
    deployment_mode = get_stripe_mode()
    code, risk, path = classify_remediation(billing, resolution, deployment_mode=deployment_mode)

    return {
        "found": True,
        "client_id": client_id,
        "deployment_mode": deployment_mode,
        "billing_identifiers": {
            "stripe_subscription_id": (billing.get("stripe_subscription_id") or "").strip() or None,
            "stripe_customer_id": (billing.get("stripe_customer_id") or "").strip() or None,
        },
        "stored_stripe_mode": normalize_persisted_mode(billing.get("stripe_mode")),
        "stored_stripe_customer_mode": normalize_persisted_mode(
            billing.get("stripe_customer_mode") or billing.get("stripe_mode")
        ),
        "verification_status": billing.get("stripe_mode_verification_status"),
        "confidence": billing.get("stripe_mode_confidence"),
        "resolution": resolution,
        "remediation_code": code,
        "operational_risk": risk,
        "recommended_remediation_path": path,
        "allowed_admin_actions": [
            "regenerate_checkout_in_deployment_mode",
            "portal_relink",
            "explicit_admin_mode_remediation",
            "backfill_dry_run",
            "backfill_execute_authoritative_only",
        ],
        "forbidden_actions": [
            "automatic_subscription_migration",
            "automatic_cancellation",
            "automatic_recreation",
            "silent_environment_switch",
        ],
        "customer_message": CUSTOMER_BILLING_REFRESH_MESSAGE,
    }


async def build_expanded_stripe_mode_inventory(*, limit: int = 500) -> Dict[str, Any]:
    """Read-only expanded inventory with Phase 2 categories."""
    db = database.get_db()
    deployment_mode = get_stripe_mode()
    now = _now()

    categories: Dict[str, List[Dict[str, Any]]] = {
        "missing_stripe_mode": [],
        "mixed_customer_subscription_mode": [],
        "test_rows_in_live": [],
        "live_rows_in_test": [],
        "orphaned_checkout_sessions": [],
        "webhook_mode_conflicts": [],
        "unknown_mode_rows": [],
        "legacy_unclassified_rows": [],
    }
    counts = {k: 0 for k in categories}

    billing_cursor = db.client_billing.find(
        {
            "$or": [
                {"stripe_subscription_id": {"$nin": [None, ""]}},
                {"stripe_customer_id": {"$nin": [None, ""]}},
            ]
        },
        {"_id": 0},
    ).limit(limit)

    async for billing in billing_cursor:
        client_id = billing.get("client_id")
        stored = normalize_persisted_mode(billing.get("stripe_mode"))
        cust_mode = normalize_persisted_mode(
            billing.get("stripe_customer_mode") or billing.get("stripe_mode")
        )
        sub_id = (billing.get("stripe_subscription_id") or "").strip()
        confidence = (billing.get("stripe_mode_confidence") or "").strip().lower()
        verification_status = (billing.get("stripe_mode_verification_status") or "").strip()

        resolution = await resolve_authoritative_mode(client_id, billing=billing)
        code, risk, path = classify_remediation(
            billing, resolution, deployment_mode=deployment_mode
        )

        entry = {
            "client_id": client_id,
            "billing_identifiers": {
                "stripe_subscription_id": sub_id or None,
                "stripe_customer_id": (billing.get("stripe_customer_id") or "").strip() or None,
            },
            "inferred_mode_source": resolution.get("inferred_mode_source"),
            "confidence": resolution.get("stripe_mode_confidence") or confidence or "unknown",
            "operational_risk": risk,
            "recommended_remediation_path": path,
            "remediation_code": code,
        }

        if sub_id and stored is None:
            categories["missing_stripe_mode"].append(entry)
            counts["missing_stripe_mode"] += 1
        elif verification_status == MODE_UNVERIFIED or confidence == CONFIDENCE_UNKNOWN:
            categories["unknown_mode_rows"].append(entry)
            counts["unknown_mode_rows"] += 1
        elif not billing.get("stripe_mode_verification_source") and (sub_id or cust_mode is None):
            categories["legacy_unclassified_rows"].append(entry)
            counts["legacy_unclassified_rows"] += 1

        if cust_mode and stored and cust_mode != stored:
            categories["mixed_customer_subscription_mode"].append(entry)
            counts["mixed_customer_subscription_mode"] += 1

        if deployment_mode == "live" and stored == "test":
            categories["test_rows_in_live"].append(entry)
            counts["test_rows_in_live"] += 1
        elif deployment_mode == "test" and stored == "live":
            categories["live_rows_in_test"].append(entry)
            counts["live_rows_in_test"] += 1

    orphaned = []
    async for ch in db.checkout_sessions.find(
        {
            "$or": [
                {"stripe_mode": {"$exists": False}},
                {"stripe_mode": None},
                {"status": "pending"},
            ]
        },
        {"_id": 0, "session_id": 1, "client_id": 1, "status": 1, "stripe_mode": 1},
    ).limit(limit):
        if not normalize_persisted_mode(ch.get("stripe_mode")) or ch.get("status") == "pending":
            orphaned.append(
                {
                    "session_id": ch.get("session_id"),
                    "client_id": ch.get("client_id"),
                    "status": ch.get("status"),
                    "stripe_mode": ch.get("stripe_mode"),
                }
            )
    categories["orphaned_checkout_sessions"] = orphaned[:100]
    counts["orphaned_checkout_sessions"] = len(orphaned)

    dep_live = deployment_mode == "live"
    async for ev in db.stripe_events.find(
        {"livemode": {"$exists": True, "$ne": None}},
        {"_id": 0, "event_id": 1, "livemode": 1, "related_client_id": 1},
    ).limit(limit):
        ev_live = bool(ev.get("livemode"))
        if ev_live != dep_live:
            categories["webhook_mode_conflicts"].append(
                {
                    "event_id": ev.get("event_id"),
                    "client_id": ev.get("related_client_id"),
                    "event_livemode": ev_live,
                    "deployment_mode": deployment_mode,
                }
            )
            counts["webhook_mode_conflicts"] += 1

    for key in categories:
        if key != "orphaned_checkout_sessions" and len(categories[key]) > 100:
            categories[key] = categories[key][:100]

    total_billing = await db.client_billing.count_documents(
        {
            "$or": [
                {"stripe_subscription_id": {"$nin": [None, ""]}},
                {"stripe_customer_id": {"$nin": [None, ""]}},
            ]
        }
    )
    authoritative_count = await db.client_billing.count_documents(
        {"stripe_mode_confidence": CONFIDENCE_AUTHORITATIVE}
    )

    metrics = {
        "authoritative_mode_coverage": round(authoritative_count / max(total_billing, 1), 4),
        "unknown_mode_percentage": round(
            counts["unknown_mode_rows"] / max(total_billing, 1), 4
        ),
        "mixed_mode_risk_count": counts["mixed_customer_subscription_mode"],
        "remediation_required_clients": sum(
            counts[cat]
            for cat in (
                "missing_stripe_mode",
                "mixed_customer_subscription_mode",
                "test_rows_in_live",
                "live_rows_in_test",
                "unknown_mode_rows",
            )
        ),
    }

    await _update_inventory_metrics({"inventory": counts, "metrics": metrics})

    return {
        "generated_at": now.isoformat(),
        "deployment_mode": deployment_mode,
        "read_only": True,
        "summary": counts,
        "metrics": metrics,
        "categories": categories,
        "total_billing_rows_with_stripe_ids": total_billing,
    }


def audit_legacy_stripe_callers() -> Dict[str, Any]:
    """Static audit of known legacy Stripe caller sites (for convergence tracking)."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    patterns = [
        ("STRIPE_SECRET_KEY", "raw legacy key env"),
        ("STRIPE_API_KEY", "raw legacy API key env"),
        ("stripe.api_key =", "direct global stripe.api_key assignment"),
    ]
    findings: List[Dict[str, Any]] = []
    skip_dirs = {"node_modules", ".git", "__pycache__", "venv", ".venv", "scripts"}

    for py_path in root.rglob("*.py"):
        if any(part in skip_dirs for part in py_path.parts):
            continue
        rel = str(py_path.relative_to(root)).replace("\\", "/")
        if "stripe_mode_backfill_service.py" in rel:
            continue
        try:
            text = py_path.read_text(encoding="utf-8")
        except Exception:
            continue
        for pattern, kind in patterns:
            if pattern in text and "stripe_mode_authority" not in text:
                if rel.startswith("services/stripe_mode_authority.py"):
                    continue
                if rel.startswith("tests/"):
                    continue
                converged = "resolve_stripe_context" in text or "configure_stripe_sdk" in text
                entry = {
                    "file": rel,
                    "pattern": pattern,
                    "kind": kind,
                    "converged": converged,
                    "operational": not rel.startswith("scripts/"),
                }
                findings.append(entry)
                break

    operational_unconverged = [
        f for f in findings if f.get("operational") and not f.get("converged")
    ]

    converged_targets = [
        "services/intake_draft_service.py",
        "services/jobs.py",
        "clearform/routes/subscriptions.py",
        "routes/admin_billing.py",
    ]
    target_status = []
    for target in converged_targets:
        p = root / target
        if p.is_file():
            text = p.read_text(encoding="utf-8")
            target_status.append(
                {
                    "file": target,
                    "uses_resolve_stripe_context": "resolve_stripe_context" in text,
                    "uses_configure_stripe_sdk": "configure_stripe_sdk" in text,
                    "raw_stripe_secret_key": 'os.getenv("STRIPE_SECRET_KEY")' in text
                    or 'os.environ.get("STRIPE_SECRET_KEY")' in text,
                }
            )

    return {
        "generated_at": _now().isoformat(),
        "legacy_caller_findings": findings,
        "convergence_targets": target_status,
        "legacy_caller_count": len(operational_unconverged),
        "operational_unconverged": operational_unconverged,
    }


async def _record_backfill_audit(
    *,
    client_id: str,
    action: str,
    resolution: Dict[str, Any],
    write_doc: Optional[Dict[str, Any]] = None,
    admin_actor: Optional[str] = None,
) -> None:
    db = database.get_db()
    doc = {
        "client_id": client_id,
        "action": action,
        "resolution": resolution,
        "write_doc": write_doc,
        "admin_actor": admin_actor or "system",
        "created_at": _now(),
    }
    try:
        await db[COL_BACKFILL_AUDIT].insert_one(doc)
    except Exception as exc:
        logger.warning("stripe_mode_backfill_audit write failed: %s", exc)

    try:
        await create_audit_log(
            action=AuditAction.ADMIN_ACTION,
            actor_role="ROLE_ADMIN" if admin_actor else "SYSTEM",
            actor_id=admin_actor or "stripe_mode_backfill",
            client_id=client_id,
            metadata={
                "action_type": "STRIPE_MODE_BACKFILL",
                "backfill_action": action,
                "confidence": resolution.get("stripe_mode_confidence"),
                "verification_source": resolution.get("stripe_mode_verification_source"),
            },
        )
    except Exception as exc:
        logger.warning("stripe_mode_backfill audit log failed: %s", exc)


async def _update_inventory_metrics(payload: Dict[str, Any]) -> None:
    db = database.get_db()
    try:
        await db[COL_INVENTORY_METRICS].update_one(
            {"scope": "global"},
            {"$set": {"last_run": _now(), "payload": payload}},
            upsert=True,
        )
    except Exception as exc:
        logger.warning("stripe_mode_inventory_metrics write failed: %s", exc)
