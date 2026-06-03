"""
Enterprise compliance scoring: single source of truth for property-level score.
Deterministic, event-driven recalculation, persisted on Property + history + audit.
Uses Compliance Score v1 (evidence-based, no legal verdicts) from compliance_scoring module.

All score changes must go through recalculate_and_persist(); no route implements
its own scoring. Dashboard and GET /compliance-score read stored property scores.

Admin ``validate-compliance-score`` with ``fix=true`` calls
``recalculate_and_persist`` with ``REASON_ADMIN_VALIDATOR_REPAIR`` (Stream B).
"""
from database import database
from datetime import datetime, timezone, date, timedelta
from typing import Dict, Any, Optional, List
import logging

from services.compliance_scoring_v2 import compute_property_score_v2
from utils.risk_bands import score_to_grade_color_message, score_to_risk_level
from services.scoring_semantics_v1 import (
    attach_semantics_contract,
    resolve_property_score_status,
    SCORE_AUTHORITY_PERSISTED_HEADLINE,
    SCORE_STATUS_RECONCILIATION_REQUIRED,
)

logger = logging.getLogger(__name__)

WEIGHTS_VERSION = "v2_jurisdictional"

# Reasons for score change (used in history and audit)
REASON_DOCUMENT_UPLOADED = "DOCUMENT_UPLOADED"
REASON_DOCUMENT_DELETED = "DOCUMENT_DELETED"
REASON_AI_APPLIED = "AI_APPLIED"
REASON_REQUIREMENT_CHANGED = "REQUIREMENT_CHANGED"
REASON_EXPIRY_ROLLOVER = "EXPIRY_ROLLOVER"
REASON_PROPERTY_CREATED = "PROPERTY_CREATED"
REASON_LAZY_BACKFILL = "LAZY_BACKFILL"
# First-time repair when a client reads property explainability and the row has no persisted score yet.
REASON_SCORE_READ_REPAIR = "SCORE_READ_REPAIR"
# Admin POST validate-compliance-score with fix=true (canonical persist via recalculate_and_persist).
REASON_ADMIN_VALIDATOR_REPAIR = "ADMIN_VALIDATOR_REPAIR"


def _parse_due_date(due_date_str) -> Optional[datetime]:
    if not due_date_str:
        return None
    try:
        if isinstance(due_date_str, datetime):
            return due_date_str.replace(tzinfo=timezone.utc) if due_date_str.tzinfo is None else due_date_str
        s = due_date_str.replace("Z", "+00:00") if isinstance(due_date_str, str) else str(due_date_str)
        return datetime.fromisoformat(s)
    except Exception:
        return None


async def calculate_property_compliance(
    property_id: str,
    as_of_date: Optional[date] = None,
) -> Dict[str, Any]:
    """
    Compute compliance score for a single property from current DB state (Compliance Score v1).
    Deterministic: same DB state + same as_of_date -> same result.

    Requirements are filtered with ``filter_requirement_rows_for_client_runtime_surfaces``,
    projected with ``project_requirement_row_client_runtime``, then restricted to
    ``client_portal_surface_visible_row`` so persisted scores align with portal KPI universe.
    """
    db = database.get_db()
    now = datetime.now(timezone.utc)
    if as_of_date is not None:
        now = datetime.combine(as_of_date, now.time(), tzinfo=timezone.utc)

    property_doc = await db.properties.find_one(
        {"property_id": property_id},
        {"_id": 0, "property_id": 1, "client_id": 1, "is_hmo": 1, "bedrooms": 1, "occupancy": 1,
         "licence_required": 1, "licence_type": 1, "cert_gas_safety": 1, "cert_licence": 1,
         "has_gas_supply": 1, "has_gas": 1, "tenancy_active": 1, "deposit_taken": 1, "jurisdiction": 1}
    )
    if not property_doc:
        return {
            "score": 0,
            "breakdown": {},
            "weights_version": WEIGHTS_VERSION,
            "error": "property_not_found",
        }

    raw_requirements = await db.requirements.find(
        {"property_id": property_id},
        {"_id": 0}
    ).to_list(500)
    from services.requirement_truth import enrich_requirements_for_client

    client_id = str(property_doc.get("client_id") or "")
    raw_requirements, _ = await enrich_requirements_for_client(db, client_id, list(raw_requirements))
    documents = await db.documents.find(
        {"property_id": property_id},
        {"_id": 0}
    ).to_list(500)
    client_doc = await db.clients.find_one(
        {"client_id": property_doc.get("client_id")},
        {"_id": 0, "default_jurisdiction": 1, "enabled_jurisdictions": 1},
    ) or {}
    open_issues_count = await db.maintenance_issues.count_documents(
        {"property_id": property_id, "status": {"$nin": ["resolved", "closed", "completed"]}}
    )
    overdue_work_orders_count = await db.work_orders.count_documents(
        {"property_id": property_id, "status": {"$nin": ["completed", "closed"]}, "due_date": {"$lt": now.isoformat()}}
    )
    open_risks_count = await db.risk_signals.count_documents(
        {"property_id": property_id, "status": {"$nin": ["resolved"]}}
    )

    from services.compliance_rules_registry import (
        property_jurisdiction_requirement_flags,
        resolve_portfolio_jurisdiction,
    )

    _jr = resolve_portfolio_jurisdiction(property_doc, client_doc)
    _juris_flags = property_jurisdiction_requirement_flags(property_doc)

    from services.requirement_client_runtime_surface import (
        filter_requirement_rows_for_client_runtime_surfaces,
        client_portal_surface_visible_row,
        project_requirement_row_client_runtime,
        compute_client_portal_requirement_stats,
    )

    filtered = await filter_requirement_rows_for_client_runtime_surfaces(
        db,
        client_id=str(property_doc.get("client_id") or ""),
        requirements=list(raw_requirements),
        client_doc=client_doc,
        properties=[property_doc],
    )
    projected = [project_requirement_row_client_runtime(r) for r in filtered]
    requirements = [r for r in projected if client_portal_surface_visible_row(r)]

    result = compute_property_score_v2(
        property_doc=property_doc,
        client_doc=client_doc,
        requirements=requirements,
        documents=documents,
        open_issues_count=int(open_issues_count),
        overdue_work_orders_count=int(overdue_work_orders_count),
        open_risks_count=int(open_risks_count),
        as_of=now,
    )
    score = result.get("score_0_100", 0)
    risk_level = "Low risk" if score >= 90 else ("Moderate risk" if score >= 70 else ("Elevated risk" if score >= 50 else "High risk"))
    requirement_breakdown = result.get("requirement_breakdown", [])

    grade, color, _ = score_to_grade_color_message(score)
    status_score = score
    bucket_breakdown = result.get("bucket_breakdown") or {}
    breakdown_legacy = {
        "status_score": float((bucket_breakdown.get("legal_core") or {}).get("percent", score)),
        "expiry_score": float((bucket_breakdown.get("recency_maintenance_confidence") or {}).get("percent", score)),
        "document_score": float((bucket_breakdown.get("documentation_completeness") or {}).get("percent", score)),
        "overdue_penalty_score": float((bucket_breakdown.get("operational_responsiveness") or {}).get("percent", score)),
        "risk_score": 100.0 - min(100.0, float(open_risks_count) * 10.0),
    }
    projected_stats = compute_client_portal_requirement_stats(requirements)
    stats = {
        "total_requirements": projected_stats["total_requirements"],
        "compliant": projected_stats["compliant"],
        "pending": projected_stats["pending"],
        "missing_evidence": projected_stats["missing_evidence"],
        "expiring_soon": projected_stats["expiring_soon"],
        "overdue": projected_stats["overdue"],
        "open_issues": int(open_issues_count),
        "overdue_work_orders": int(overdue_work_orders_count),
        "open_risk_signals": int(open_risks_count),
    }
    return {
        "score": score,
        "grade": grade,
        "color": color,
        "risk_level": risk_level,
        "score_breakdown": requirement_breakdown,
        "bucket_breakdown": bucket_breakdown,
        "earned_points": result.get("earned_points"),
        "applicable_points": result.get("applicable_points"),
        "top_deficits": result.get("top_deficits") or [],
        "top_next_actions": result.get("top_next_actions") or [],
        # API naming: "jurisdiction" here is the scoring bucket (ENGLAND_WALES | SCOTLAND), not the property record label.
        # Prefer scoring_jurisdiction_bucket for new clients; keep "jurisdiction" until a versioned API deprecates it.
        "jurisdiction": result.get("jurisdiction"),
        "scoring_jurisdiction_bucket": result.get("jurisdiction"),
        "compliance_basis": _jr.compliance_basis,
        "effective_jurisdiction_label": _jr.effective_label,
        "jurisdiction_required": _juris_flags["jurisdiction_required"],
        "compliance_confidence": _juris_flags["compliance_confidence"],
        "breakdown": breakdown_legacy,
        "stats": stats,
        "weights_version": WEIGHTS_VERSION,
        "weights": {
            "legal_core": "60%",
            "documentation_completeness": "20%",
            "operational_responsiveness": "10%",
            "recency_maintenance_confidence": "10%",
        },
    }


async def recalculate_and_persist(
    property_id: str,
    reason: str,
    actor: Optional[Dict[str, Any]] = None,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Load DB state, compute score, persist to Property, write history snapshot, and audit.
    Safe to call concurrently (last write wins); single atomic Property update.
    """
    db = database.get_db()
    prop = await db.properties.find_one(
        {"property_id": property_id},
        {"_id": 0, "property_id": 1, "client_id": 1, "compliance_score": 1, "compliance_breakdown": 1, "score_breakdown": 1}
    )
    if not prop:
        logger.warning(f"recalculate_and_persist: property not found {property_id}")
        return {}

    client_id = prop["client_id"]
    previous_score = prop.get("compliance_score")
    previous_breakdown = prop.get("compliance_breakdown") or {}
    previous_score_breakdown = prop.get("score_breakdown") or []

    result = await calculate_property_compliance(property_id)
    if result.get("error"):
        logger.warning(f"recalculate_and_persist: calculation error for {property_id}: {result.get('error')}")
        return result

    new_score = result["score"]
    new_breakdown = result.get("breakdown", {})
    risk_level = result.get("risk_level")
    score_breakdown = result.get("score_breakdown", [])
    now = datetime.now(timezone.utc)

    # Persist scoring bucket separately from properties.jurisdiction (portfolio label: England/Wales/…).
    # v2's result["jurisdiction"] is SCOTLAND | ENGLAND_WALES — never write that into jurisdiction.
    set_fields = {
        "compliance_score": new_score,
        "compliance_breakdown": new_breakdown,
        "compliance_bucket_breakdown": result.get("bucket_breakdown") or {},
        "compliance_earned_points": result.get("earned_points"),
        "compliance_applicable_points": result.get("applicable_points"),
        "compliance_top_deficits": result.get("top_deficits") or [],
        "compliance_top_next_actions": result.get("top_next_actions") or [],
        "scoring_jurisdiction_bucket": result.get("jurisdiction"),
        "compliance_last_calculated_at": now.isoformat(),
        "compliance_version": result.get("weights_version", WEIGHTS_VERSION),
        "compliance_score_pending": False,
    }
    if risk_level is not None:
        set_fields["risk_level"] = risk_level
    if score_breakdown is not None:
        set_fields["score_breakdown"] = score_breakdown

    await db.properties.update_one(
        {"property_id": property_id},
        {"$set": set_fields}
    )

    breakdown_summary = {
        "status_score": new_breakdown.get("status_score"),
        "expiry_score": new_breakdown.get("expiry_score"),
        "document_score": new_breakdown.get("document_score"),
        "overdue_penalty_score": new_breakdown.get("overdue_penalty_score"),
        "risk_score": new_breakdown.get("risk_score"),
    }
    history_doc = {
        "property_id": property_id,
        "client_id": client_id,
        "score": new_score,
        "breakdown_summary": breakdown_summary,
        "created_at": now.isoformat(),
        "reason": reason,
        "actor": actor,
    }
    _cid = (context or {}).get("correlation_id")
    if _cid is not None and str(_cid).strip():
        history_doc["correlation_id"] = str(_cid).strip()
    await db.property_compliance_score_history.insert_one(history_doc)

    delta = (new_score - previous_score) if previous_score is not None else None
    prev_by_key = {r.get("requirement_key"): r.get("status") for r in previous_score_breakdown if r.get("requirement_key")}
    new_by_key = {r.get("requirement_key"): r.get("status") for r in score_breakdown if r.get("requirement_key")}
    changed_requirements = []
    all_keys = set(prev_by_key) | set(new_by_key)
    for key in all_keys:
        prev_s = prev_by_key.get(key)
        new_s = new_by_key.get(key)
        if prev_s != new_s:
            changed_requirements.append({"requirement_key": key, "previous_status": prev_s, "new_status": new_s})
    score_change_log_doc = {
        "property_id": property_id,
        "client_id": client_id,
        "previous_score": previous_score,
        "new_score": new_score,
        "delta": delta,
        "reason": reason,
        "changed_requirements": changed_requirements,
        "created_at": now.isoformat(),
        "actor": actor,
    }
    if _cid is not None and str(_cid).strip():
        score_change_log_doc["correlation_id"] = str(_cid).strip()
    await db.score_change_log.insert_one(score_change_log_doc)

    from services.score_ledger_service import log_score_change
    from utils.risk_bands import score_to_grade_color_message
    before_grade = None
    if previous_score is not None:
        g, _, _ = score_to_grade_color_message(int(round(previous_score)))
        before_grade = g
    after_grade_g, _, _ = score_to_grade_color_message(int(round(new_score)))
    drivers_before_ledger = {
        "status": previous_breakdown.get("status_score"),
        "timeline": previous_breakdown.get("expiry_score"),
        "documents": previous_breakdown.get("document_score"),
        "overdue_penalty": previous_breakdown.get("overdue_penalty_score"),
    }
    drivers_after_ledger = {
        "status": new_breakdown.get("status_score"),
        "timeline": new_breakdown.get("expiry_score"),
        "documents": new_breakdown.get("document_score"),
        "overdue_penalty": new_breakdown.get("overdue_penalty_score"),
    }
    await log_score_change(
        client_id=client_id,
        property_id=property_id,
        actor_type=(actor or {}).get("role") or "SYSTEM",
        actor_id=(actor or {}).get("id") or (actor or {}).get("portal_user_id"),
        trigger_reason=reason,
        before_score=previous_score,
        after_score=new_score,
        before_grade=before_grade,
        after_grade=after_grade_g,
        drivers_before=drivers_before_ledger,
        drivers_after=drivers_after_ledger,
        rule_version=result.get("weights_version", WEIGHTS_VERSION),
        requirement_id=(context or {}).get("requirement_id"),
        document_id=(context or {}).get("document_id"),
        correlation_id=(context or {}).get("correlation_id"),
    )

    from models import AuditAction
    from utils.audit import create_audit_log
    await create_audit_log(
        action=AuditAction.COMPLIANCE_SCORE_UPDATED,
        actor_id=(actor or {}).get("id") or (actor or {}).get("portal_user_id"),
        client_id=client_id,
        resource_type="property",
        resource_id=property_id,
        before_state={"compliance_score": previous_score} if previous_score is not None else None,
        after_state={"compliance_score": new_score},
        metadata={
            "reason": reason,
            "previous_score": previous_score,
            "new_score": new_score,
            "delta": delta,
            "actor_role": (actor or {}).get("role"),
            **(context or {}),
        },
    )
    logger.info(f"Compliance score updated property_id={property_id} reason={reason} previous={previous_score} new={new_score}")

    if not (context or {}).get("skip_risk_regen_enqueue"):
        try:
            from services.risk_signal_regen_queue import enqueue_risk_signal_regen

            await enqueue_risk_signal_regen(
                property_id,
                client_id,
                f"RECALC:{reason}",
            )
        except Exception as regen_err:
            logger.warning(
                "recalculate_and_persist: risk regen enqueue failed property_id=%s: %s",
                property_id,
                regen_err,
            )

    return result


def _merge_live_compliance_with_persisted_headline(
    live: Dict[str, Any],
    prop: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Split persisted headline (authoritative) from live engine snapshot (operational preview only).
    Client KPIs must read ``authoritative`` only; ``operational_preview`` is never a substitute score.
    """
    operational_preview: Dict[str, Any] = {
        "score_authority": "operational_preview_only",
        "live_engine_snapshot": dict(live),
    }
    authoritative: Dict[str, Any] = {
        "score_authority": SCORE_AUTHORITY_PERSISTED_HEADLINE,
        "property_id": prop.get("property_id"),
    }
    ps = prop.get("compliance_score")
    if ps is not None:
        try:
            score_int = int(round(float(ps)))
        except (TypeError, ValueError):
            score_int = None
        if score_int is not None:
            g, c, m = score_to_grade_color_message(score_int)
            authoritative["score"] = score_int
            authoritative["score_status"] = resolve_property_score_status(prop)
            authoritative["grade"] = g
            authoritative["color"] = c
            authoritative["message"] = m
        else:
            authoritative["score"] = None
            authoritative["score_status"] = SCORE_STATUS_RECONCILIATION_REQUIRED
            authoritative["grade"] = None
            authoritative["color"] = "gray"
            authoritative["message"] = (
                "Stored compliance score could not be read; reconciliation may be required."
            )
    else:
        st = "calculating" if prop.get("compliance_score_pending") else "reconciliation_required"
        authoritative["score"] = None
        authoritative["score_status"] = st
        authoritative["grade"] = None
        authoritative["color"] = "gray"
        authoritative["message"] = (
            "Compliance score is being calculated for this property."
            if st == "calculating"
            else "Compliance score is not yet available; reconciliation may be required."
        )
    if prop.get("risk_level") is not None:
        authoritative["risk_level"] = prop.get("risk_level")
    elif authoritative.get("score") is not None:
        authoritative["risk_level"] = score_to_risk_level(int(authoritative["score"]))
    if prop.get("compliance_bucket_breakdown"):
        authoritative["bucket_breakdown"] = prop.get("compliance_bucket_breakdown")
    if prop.get("score_breakdown") is not None:
        authoritative["score_breakdown"] = prop.get("score_breakdown")
    if prop.get("compliance_earned_points") is not None:
        authoritative["earned_points"] = prop.get("compliance_earned_points")
    if prop.get("compliance_applicable_points") is not None:
        authoritative["applicable_points"] = prop.get("compliance_applicable_points")
    if prop.get("compliance_top_deficits") is not None:
        authoritative["top_deficits"] = prop.get("compliance_top_deficits") or []
    if prop.get("compliance_top_next_actions") is not None:
        authoritative["top_next_actions"] = prop.get("compliance_top_next_actions") or []
    if prop.get("scoring_jurisdiction_bucket") is not None:
        authoritative["jurisdiction"] = prop.get("scoring_jurisdiction_bucket")
        authoritative["scoring_jurisdiction_bucket"] = prop.get("scoring_jurisdiction_bucket")
    if isinstance(prop.get("compliance_breakdown"), dict) and prop.get("compliance_breakdown"):
        authoritative["breakdown"] = prop.get("compliance_breakdown")
    authoritative["weights_version"] = prop.get("compliance_version") or live.get("weights_version") or WEIGHTS_VERSION
    _raw_lc = prop.get("compliance_last_calculated_at")
    authoritative["compliance_last_calculated_at"] = _raw_lc
    if hasattr(_raw_lc, "isoformat"):
        authoritative["last_calculated_at"] = _raw_lc.isoformat()
    elif isinstance(_raw_lc, str):
        authoritative["last_calculated_at"] = _raw_lc
    else:
        authoritative["last_calculated_at"] = None
    merged = {
        "explanation_contract_version": "batch2_authoritative_split_v1",
        "authoritative": authoritative,
        "operational_preview": operational_preview,
        "score_authority": authoritative.get("score_authority"),
        "score_status": authoritative.get("score_status"),
        "last_calculated_at": authoritative.get("last_calculated_at"),
    }
    return attach_semantics_contract(merged)


async def get_authoritative_property_compliance_for_client(
    property_id: str,
    client_id: str,
) -> Dict[str, Any]:
    """
    Client-facing property explainability: operational context from the same planner as scoring,
    headline score and breakdowns from Mongo fields updated only via recalculate_and_persist.

    If the property has never had a persisted score, runs one repair recalc (idempotent).
    """
    db = database.get_db()
    prop = await db.properties.find_one(
        {"property_id": property_id, "client_id": client_id},
        {
            "_id": 0,
            "property_id": 1,
            "client_id": 1,
            "compliance_score": 1,
            "compliance_score_pending": 1,
            "compliance_breakdown": 1,
            "compliance_bucket_breakdown": 1,
            "score_breakdown": 1,
            "compliance_earned_points": 1,
            "compliance_applicable_points": 1,
            "compliance_top_deficits": 1,
            "compliance_top_next_actions": 1,
            "scoring_jurisdiction_bucket": 1,
            "risk_level": 1,
            "compliance_version": 1,
            "compliance_last_calculated_at": 1,
        },
    )
    if not prop:
        return {"error": "property_not_found"}

    if prop.get("compliance_score") is None:
        await recalculate_and_persist(
            property_id,
            REASON_SCORE_READ_REPAIR,
            actor={"role": "SYSTEM"},
            context={"correlation_id": f"score_read_repair:{property_id}"},
        )
        prop = (
            await db.properties.find_one(
                {"property_id": property_id, "client_id": client_id},
                {"_id": 0},
            )
            or prop
        )

    live = await calculate_property_compliance(property_id)
    if live.get("error"):
        return live
    merged = _merge_live_compliance_with_persisted_headline(live, prop)
    return merged
