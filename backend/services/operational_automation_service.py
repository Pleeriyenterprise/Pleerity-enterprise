"""
Backend-enforced operational automation: controlled issue creation from compliance + risk signals.
Explicit policy tiers: AUTO_CREATE, SUGGEST_ONLY, NONE. Work orders are never auto-created here
(issue-first; optional auto-WO categories are intentionally empty until product enables them).

All decisions are audit-logged (created, suggested, suppressed).
"""
from __future__ import annotations

import logging
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from database import database
from models import AuditAction
from utils.audit import create_audit_log

from services import maintenance_issues_service
from services.maintenance_issues_service import OPEN_ISSUE_STATUSES
from services.ops_compliance_feature_flags import get_effective_flags, MAINTENANCE_WORKFLOWS, PREDICTIVE_MAINTENANCE
from services import risk_signal_service as rss
from services.requirement_client_runtime_surface import filter_requirement_rows_for_client_runtime_surfaces

logger = logging.getLogger(__name__)

# --- Work order policy: auto-creation disabled (explicit empty allow-list) ---
AUTO_CREATE_WORK_ORDER_FOR_RISK_TYPES: Tuple[str, ...] = ()

CREATED_FROM_COMPLIANCE = "compliance"
CREATED_FROM_RISK_SIGNAL = "risk_signal"
CREATED_FROM_MANUAL = "manual"
CREATED_FROM_SYSTEM = "system"

SUGGESTION_STATUS_PENDING = "pending"
SUGGESTION_STATUS_DISMISSED = "dismissed"
SUGGESTION_STATUS_CONVERTED = "converted"

# One full evaluate per asyncio task chain; nested calls (e.g. issue create -> outcome -> sync regen) skip.
_operational_eval_depth: ContextVar[int] = ContextVar("operational_automation_eval_depth", default=0)
MAX_OPERATIONAL_EVAL_NESTING = 1

# High-risk obligation patterns (substring match on code/type/title)
_CRITICAL_COMPLIANCE_SUBSTRINGS = (
    "gas",
    "cp12",
    "eicr",
    "electrical",
    "fire risk",
    "smoke alarm",
    "carbon monoxide",
    "co alarm",
)

_BAD_REQ_STATUSES = frozenset({"OVERDUE", "EXPIRED", "MISSING", "PENDING"})


def _norm_level(level: Optional[str]) -> str:
    return (level or "").strip().lower()


def _operational_root_key_risk(risk_type: str, asset_id: Optional[str]) -> str:
    aid = (asset_id or "").strip() or "none"
    return f"risk:{risk_type}:{aid}"


def _operational_root_key_compliance(requirement_code: str) -> str:
    return f"compliance:{(requirement_code or 'unknown').strip().lower()}"


async def _flags_for_property(property_id: str, client_id: str) -> Tuple[Dict[str, bool], Optional[str]]:
    db = database.get_db()
    client_doc = await db.clients.find_one({"client_id": client_id}, {"_id": 0, "billing_plan": 1})
    billing = (client_doc or {}).get("billing_plan")
    flags = await get_effective_flags(client_id, billing)
    return flags, billing


async def _open_issue_exists_for_root(
    client_id: str, property_id: str, operational_root_key: str
) -> bool:
    db = database.get_db()
    n = await db.maintenance_issues.count_documents(
        {
            "client_id": client_id,
            "property_id": property_id,
            "operational_root_key": operational_root_key,
            "status": {"$in": list(OPEN_ISSUE_STATUSES)},
        }
    )
    return n > 0


async def _pending_suggestion_exists(client_id: str, property_id: str, root_key: str) -> bool:
    db = database.get_db()
    doc = await db.operational_issue_suggestions.find_one(
        {
            "client_id": client_id,
            "property_id": property_id,
            "operational_root_key": root_key,
            "status": SUGGESTION_STATUS_PENDING,
        },
        {"_id": 1},
    )
    return doc is not None


async def _record_issue_suggestion(
    client_id: str,
    property_id: str,
    operational_root_key: str,
    rule_id: str,
    title: str,
    body: str,
    risk_signal_id: Optional[str],
    requirement_code: Optional[str],
) -> None:
    db = database.get_db()
    now = datetime.now(timezone.utc).isoformat()
    suggestion_id = f"sug_{uuid.uuid4().hex[:12]}"
    res = await db.operational_issue_suggestions.update_one(
        {
            "client_id": client_id,
            "property_id": property_id,
            "operational_root_key": operational_root_key,
            "status": SUGGESTION_STATUS_PENDING,
        },
        {
            "$set": {
                "rule_id": rule_id,
                "title": title,
                "body": body,
                "risk_signal_id": risk_signal_id,
                "source_requirement_code": requirement_code,
                "suggestion_type": "create_issue",
                "status": SUGGESTION_STATUS_PENDING,
                "updated_at": now,
            },
            "$setOnInsert": {
                "suggestion_id": suggestion_id,
                "client_id": client_id,
                "property_id": property_id,
                "operational_root_key": operational_root_key,
                "created_at": now,
            },
        },
        upsert=True,
    )
    if getattr(res, "upserted_id", None) is not None:
        await create_audit_log(
            action=AuditAction.OPERATIONAL_AUTOMATION_ISSUE_SUGGESTED,
            client_id=client_id,
            resource_type="property",
            resource_id=property_id,
            metadata={
                "rule_id": rule_id,
                "operational_root_key": operational_root_key,
                "risk_signal_id": risk_signal_id,
                "source_requirement_code": requirement_code,
                "suggestion_type": "create_issue",
                "suggestion_id": suggestion_id,
            },
        )


async def _log_suppressed(
    client_id: str,
    property_id: str,
    rule_id: str,
    reason: str,
    **extra: Any,
) -> None:
    """One suppress audit per (client, property, rule, root, UTC day) to avoid log flooding on repeated jobs."""
    db = database.get_db()
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    root = str(extra.get("operational_root_key") or extra.get("requirement_code") or "")
    dedupe_id = f"suppress|{client_id}|{property_id}|{rule_id}|{root}|{day}"
    res = await db.operational_automation_suppress_audit.update_one(
        {"_id": dedupe_id},
        {"$setOnInsert": {"created_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )
    if getattr(res, "upserted_id", None) is None:
        return
    await create_audit_log(
        action=AuditAction.OPERATIONAL_AUTOMATION_SUPPRESSED,
        client_id=client_id,
        resource_type="property",
        resource_id=property_id,
        metadata={"rule_id": rule_id, "reason": reason, **extra},
    )


def _is_critical_compliance_row(req: Dict[str, Any]) -> bool:
    blob = " ".join(
        [
            str(req.get("requirement_code") or ""),
            str(req.get("requirement_type") or ""),
            str(req.get("title") or ""),
        ]
    ).lower()
    return any(s in blob for s in _CRITICAL_COMPLIANCE_SUBSTRINGS)


def _classify_risk_signal(sig: Dict[str, Any]) -> Tuple[str, str]:
    """
    Returns (tier, rule_id) where tier is auto | suggest | none.
    """
    rt = sig.get("risk_type") or ""
    lvl = _norm_level(sig.get("risk_level"))

    if rt == rss.RISK_TYPE_CERTIFICATE_EXPIRY_SOON:
        if lvl in (rss.RISK_LEVEL_HIGH, rss.RISK_LEVEL_CRITICAL):
            return "auto", "auto_cert_expiry_cluster"
        return "suggest", "suggest_cert_expiry"

    if rt == rss.RISK_TYPE_SLA_BREACH:
        if lvl in (rss.RISK_LEVEL_HIGH, rss.RISK_LEVEL_CRITICAL):
            return "auto", "auto_sla_breach_escalation"
        return "suggest", "suggest_sla_breach"

    if rt == rss.RISK_TYPE_RECURRING_REPAIRS:
        if lvl in (rss.RISK_LEVEL_HIGH, rss.RISK_LEVEL_CRITICAL):
            return "auto", "auto_recurring_repairs_pattern"
        return "suggest", "suggest_recurring_repairs"

    if rt == rss.RISK_TYPE_ELECTRICAL:
        return "suggest", "suggest_electrical_review"

    if rt in (
        rss.RISK_TYPE_COMPLIANCE_CHURN,
        rss.RISK_TYPE_BOILER_FAILURE,
        rss.RISK_TYPE_DAMP_MOISTURE,
        rss.RISK_TYPE_MAINTENANCE_FREQUENCY,
    ):
        return "suggest", f"suggest_{rt.replace(' ', '_').lower()}"

    return "none", "noop_informational"


async def _maybe_upgrade_electrical_to_auto(
    client_id: str, property_id: str, sig: Dict[str, Any]
) -> bool:
    """AUTO when electrical risk is present and a high-risk electrical obligation is overdue/missing."""
    if _norm_level(sig.get("risk_level")) not in (rss.RISK_LEVEL_HIGH, rss.RISK_LEVEL_CRITICAL):
        return False
    db = database.get_db()
    cursor = db.requirements.find(
        {"property_id": property_id, "client_id": client_id, "status": {"$in": list(_BAD_REQ_STATUSES)}},
        {"_id": 0},
    )
    reqs = await cursor.to_list(50)
    prop = await db.properties.find_one(
        {"property_id": property_id, "client_id": client_id},
        {"_id": 0},
    )
    client_row = await db.clients.find_one({"client_id": client_id}, {"_id": 0}) or {}
    reqs = await filter_requirement_rows_for_client_runtime_surfaces(
        db,
        client_id=client_id,
        requirements=reqs,
        client_doc=client_row,
        properties=[prop] if prop else [],
    )
    for r in reqs:
        if _is_critical_compliance_row(r) and "elec" in " ".join(
            [str(r.get("requirement_code")), str(r.get("requirement_type")), str(r.get("title"))]
        ).lower():
            return True
    return False


async def evaluate_compliance_driven_issues(client_id: str, property_id: str) -> None:
    """AUTO/SUGGEST from requirement rows (independent of stored risk signals)."""
    flags, _ = await _flags_for_property(property_id, client_id)
    if not flags.get(MAINTENANCE_WORKFLOWS):
        return

    db = database.get_db()
    cursor = db.requirements.find(
        {"property_id": property_id, "client_id": client_id, "status": {"$in": list(_BAD_REQ_STATUSES)}},
        {"_id": 0},
    )
    reqs = await cursor.to_list(200)
    prop = await db.properties.find_one(
        {"property_id": property_id, "client_id": client_id},
        {"_id": 0},
    )
    client_row = await db.clients.find_one({"client_id": client_id}, {"_id": 0}) or {}
    reqs = await filter_requirement_rows_for_client_runtime_surfaces(
        db,
        client_id=client_id,
        requirements=reqs,
        client_doc=client_row,
        properties=[prop] if prop else [],
    )

    for r in reqs:
        if not _is_critical_compliance_row(r):
            continue
        code = (r.get("requirement_code") or r.get("requirement_type") or "unknown").strip()
        root = _operational_root_key_compliance(code)
        st = (r.get("status") or "").upper()
        rid = r.get("requirement_id")
        # Gap engine + bridge own governed issue creation for material gaps — avoid duplicate legacy automation.
        if rid:
            try:
                gap_owned = await db.compliance_gaps.count_documents(
                    {
                        "client_id": client_id,
                        "property_id": property_id,
                        "requirement_id": str(rid),
                        "status": "open",
                        "gap_kind": {"$in": ["EXPIRED", "MISSING_EVIDENCE", "MISMATCHED_EVIDENCE", "EVIDENCE_UPLOADED_UNCONFIRMED"]},
                    }
                )
            except Exception:
                gap_owned = 0
            if gap_owned > 0:
                await _log_suppressed(
                    client_id,
                    property_id,
                    "compliance_critical_superseded",
                    "compliance_gap_engine_active",
                    operational_root_key=root,
                    requirement_code=code,
                    requirement_id=str(rid),
                )
                continue

        if await _open_issue_exists_for_root(client_id, property_id, root):
            await _log_suppressed(
                client_id,
                property_id,
                "compliance_critical_dedupe",
                "open_issue_same_root",
                operational_root_key=root,
                requirement_code=code,
            )
            continue
        if await _pending_suggestion_exists(client_id, property_id, root):
            continue

        title = f"Compliance action required: {r.get('title') or code}"
        body = (
            f"Obligation `{code}` is {st}. Upload valid evidence or schedule renewal. "
            f"This record was raised from live compliance state (automation_rule=compliance_critical_evidence)."
        )

        if st in ("OVERDUE", "EXPIRED", "MISSING"):
            await maintenance_issues_service.create_issue(
                client_id=client_id,
                property_id=property_id,
                description=body,
                source=maintenance_issues_service.SOURCE_SYSTEM,
                category="compliance",
                reported_urgency="high",
                created_from=CREATED_FROM_COMPLIANCE,
                source_requirement_code=code,
                operational_root_key=root,
                triggering_rule="compliance_critical_overdue_or_missing",
            )
            await create_audit_log(
                action=AuditAction.MAINTENANCE_ISSUE_CREATED,
                client_id=client_id,
                resource_type="property",
                resource_id=property_id,
                metadata={
                    "automation": True,
                    "created_from": CREATED_FROM_COMPLIANCE,
                    "rule_id": "compliance_critical_overdue_or_missing",
                    "source_requirement_code": code,
                    "operational_root_key": root,
                },
            )
        else:
            await _record_issue_suggestion(
                client_id,
                property_id,
                root,
                "compliance_pending_evidence_suggest",
                title,
                body,
                risk_signal_id=None,
                requirement_code=code,
            )


async def evaluate_risk_signal_driven_issues(client_id: str, property_id: str) -> None:
    flags, _ = await _flags_for_property(property_id, client_id)
    if not flags.get(MAINTENANCE_WORKFLOWS) or not flags.get(PREDICTIVE_MAINTENANCE):
        return

    db = database.get_db()
    cursor = db.risk_signals.find(
        {
            "client_id": client_id,
            "property_id": property_id,
            "status": rss.STATUS_ACTIVE,
            "source": rss.SOURCE_HEURISTIC,
        },
        {"_id": 0},
    )
    signals: List[Dict[str, Any]] = await cursor.to_list(50)

    for sig in signals:
        tier, rule_id = _classify_risk_signal(sig)
        rt = sig.get("risk_type") or ""
        signal_id = sig.get("signal_id")
        asset_id = sig.get("asset_id")
        root = _operational_root_key_risk(rt, asset_id)

        if rt == rss.RISK_TYPE_ELECTRICAL and tier == "suggest":
            if await _maybe_upgrade_electrical_to_auto(client_id, property_id, sig):
                tier, rule_id = "auto", "auto_electrical_with_compliance_gap"

        if tier == "none":
            continue

        if await _open_issue_exists_for_root(client_id, property_id, root):
            await _log_suppressed(
                client_id,
                property_id,
                rule_id,
                "open_issue_same_operational_root",
                risk_type=rt,
                operational_root_key=root,
                signal_id=signal_id,
            )
            continue

        desc = sig.get("description") or rt
        reasons = sig.get("reasons") or []
        body = desc if not reasons else f"{desc}. " + " ".join(str(x) for x in reasons[:5])

        if tier == "auto":
            issue = await maintenance_issues_service.create_issue(
                client_id=client_id,
                property_id=property_id,
                description=body,
                source=maintenance_issues_service.SOURCE_SYSTEM,
                category="risk",
                reported_urgency="high" if _norm_level(sig.get("risk_level")) == rss.RISK_LEVEL_CRITICAL else "medium",
                risk_signal_id=signal_id,
                created_from=CREATED_FROM_RISK_SIGNAL,
                operational_root_key=root,
                triggering_rule=rule_id,
            )
            await create_audit_log(
                action=AuditAction.MAINTENANCE_ISSUE_CREATED,
                client_id=client_id,
                resource_type="risk_signal",
                resource_id=signal_id or "",
                metadata={
                    "automation": True,
                    "created_from": CREATED_FROM_RISK_SIGNAL,
                    "rule_id": rule_id,
                    "issue_id": issue.get("issue_id"),
                    "operational_root_key": root,
                },
            )
            continue

        if tier == "suggest":
            if await _pending_suggestion_exists(client_id, property_id, root):
                continue
            await _record_issue_suggestion(
                client_id,
                property_id,
                root,
                rule_id,
                f"Suggested: {rt}",
                body,
                risk_signal_id=signal_id,
                requirement_code=None,
            )


async def evaluate_operational_automation_after_risk_refresh(client_id: str, property_id: str) -> None:
    """
    Run after risk signals were regenerated for the property. Safe to call multiple times (dedupe).
    Nested invocations in the same task (e.g. after auto issue -> outcome -> sync regen) are skipped
    to cap load and avoid deep re-entry.
    """
    depth = _operational_eval_depth.get()
    if depth >= MAX_OPERATIONAL_EVAL_NESTING:
        logger.debug(
            "operational_automation: skip nested evaluate property_id=%s client_id=%s depth=%s",
            property_id,
            client_id,
            depth,
        )
        return
    token = _operational_eval_depth.set(depth + 1)
    try:
        try:
            await evaluate_compliance_driven_issues(client_id, property_id)
            await evaluate_risk_signal_driven_issues(client_id, property_id)
        except Exception as e:
            logger.warning(
                "operational_automation evaluation failed property_id=%s: %s",
                property_id,
                e,
            )
            raise
    finally:
        _operational_eval_depth.reset(token)


def work_order_auto_creation_enabled() -> bool:
    """Explicit: no automatic work order creation until product enables allow-list."""
    return len(AUTO_CREATE_WORK_ORDER_FOR_RISK_TYPES) > 0
