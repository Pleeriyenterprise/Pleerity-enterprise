"""Compliance Score Service - Calculate overall compliance health score
Provides a 0-100 score based on requirement statuses, expiry timelines, documents,
and property-specific risk factors.

**Stream B — score authority (reads vs writes)**

- **Authoritative property headline persistence** is only
  ``compliance_scoring_service.recalculate_and_persist`` (plus the job queue that
  drains into it). Admin ``validate-compliance-score`` with ``fix=true`` uses that
  same path with ``REASON_ADMIN_VALIDATOR_REPAIR``.
- **This module** aggregates **already-persisted** ``Property.compliance_score``
  for portfolio headline and builds live ``stats`` from the portal runtime
  projection — authoritative for **client reads**, not a substitute for the
  enterprise write path.
- **``_calculate_compliance_score_legacy_from_db``** — **non-authoritative**;
  full client recompute from DB; **no callers** in production code paths (grep
  audit 2026-04); kept for reference / emergencies only.

Enhanced Version (January 2026):
- Requirement type weighting (Gas Safety/EICR more critical than EPC)
- HMO property multiplier (stricter compliance requirements)
- Document verification status (only VERIFIED docs count)
- Historical trend factor (penalize repeated late renewals)
- Property risk tiers

Weighting Model:
- Requirement Status (35%): Based on weighted requirement statuses
- Expiry Timeline (25%): Days until next critical expiry
- Document Coverage (15%): Verified document upload rate
- Overdue Penalty (15%): Heavy penalty for overdue items
- Risk Factor (10%): HMO multiplier and historical issues
"""
from database import database
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List
from utils.risk_bands import (
    score_to_band_explanation,
    score_to_grade_color_message,
    risk_level_to_grade_color_message,
    score_to_risk_level,
    score_authority_fields,
)
from services.evidence_review_scoring_adapter import evidence_review_contributes_positive_credit
from services.scoring_semantics_v1 import (
    SCORING_SEMANTICS_VERSION,
    aggregate_persisted_portfolio_headline,
    attach_semantics_contract,
    resolve_property_score_status,
)
from services.portfolio_risk_override import derive_portfolio_risk_override
from services.portfolio_risk_override import (
    derive_policy_portfolio_risk_override,
    select_effective_portfolio_risk_override,
)
from services.portfolio_risk_override_flag import is_feature_policy_backed_portfolio_override_enabled
from services.portfolio_override_policy_health import get_tenant_policy_runtime_health
from services.portfolio_risk_override_latch import apply_persistent_critical_escalation_latch
from services.policy_reason_codes import PolicyReasonCode
from services.compliance_rules_registry import (
    build_jurisdiction_compliance_notice,
    build_portfolio_jurisdiction_attestation,
    property_jurisdiction_requirement_flags,
    resolve_portfolio_jurisdiction,
)
from services.requirement_code_registry import normalize_requirement_code
from services.requirement_read_model_guard import get_canonical_requirement_ids_map_for_properties
from services.requirement_truth import requirement_has_active_negative_actionability
from services.compliance_expiry_policy import resolve_expiring_soon_days_for_requirement
from services.semantic_state_precedence_adapter import PORTFOLIO_SCORE, observe_consumer_precedence_delta
import logging

logger = logging.getLogger(__name__)

# Tenant-scoped reads: no silent 100-property truncation (Batch 2). Hard cap guards runaway queries.
_MAX_TENANT_FETCH = 500_000


def _override_portfolio_message(effective_risk: Optional[str], reasons: List[str]) -> str:
    if effective_risk == "Critical Risk":
        return "Critical unresolved compliance risks require immediate operational action."
    if effective_risk == "High Risk":
        return "High unresolved compliance risks require prompt operational action."
    if effective_risk == "Moderate Risk":
        if PolicyReasonCode.UNKNOWN_OR_STALE_SUPPRESSION.value in reasons:
            return "Portfolio risk is moderated due to stale or unavailable property signals."
        return "Portfolio requires attention to unresolved compliance risk signals."
    return "Portfolio risk currently reflects low unresolved operational risk."


async def build_portfolio_override_outputs(
    *,
    db: Any,
    client_id: str,
    base_portfolio_risk_state: Optional[str],
    properties: List[Dict[str, Any]],
    property_breakdown: List[Dict[str, Any]],
    gap_engine: Dict[str, Any],
    policy_aggregate_unavailable: bool,
) -> Dict[str, Any]:
    legacy_override_output = derive_portfolio_risk_override(
        base_portfolio_risk_state=base_portfolio_risk_state,
        properties=properties,
        property_breakdown=property_breakdown,
        gap_engine=gap_engine,
    )
    try:
        runtime_health = await get_tenant_policy_runtime_health(db, client_id=client_id)
    except Exception:
        runtime_health = {}
    reconciliation_in_progress = bool(runtime_health.get("reconciliation_in_progress", True))
    drift_detected = bool(runtime_health.get("drift_detected"))

    policy_override_output = derive_policy_portfolio_risk_override(
        base_portfolio_risk_state=base_portfolio_risk_state,
        gap_engine=gap_engine,
    )
    gap_chk = runtime_health.get("gap_reconciliation_checkpoint")
    gap_reconciliation_checkpoint = gap_chk if isinstance(gap_chk, dict) else {}
    policy_override_output = await apply_persistent_critical_escalation_latch(
        db,
        client_id=client_id,
        policy_override_output=policy_override_output,
        gap_engine=gap_engine if isinstance(gap_engine, dict) else {},
        gap_reconciliation_checkpoint=gap_reconciliation_checkpoint,
    )
    policy_cov = float(((gap_engine.get("policy") or {}).get("policy_coverage_percent")) or 0.0)
    effective_override_output = select_effective_portfolio_risk_override(
        legacy_override_output=legacy_override_output,
        policy_override_output=policy_override_output,
        policy_switch_enabled=is_feature_policy_backed_portfolio_override_enabled(client_id),
        policy_coverage_percent=policy_cov,
        policy_coverage_threshold_percent=float(runtime_health.get("policy_coverage_threshold_percent") or 99.5),
        drift_detected=drift_detected,
        reconciliation_in_progress=reconciliation_in_progress,
        policy_aggregate_unavailable=policy_aggregate_unavailable,
    )
    return {
        "legacy_override_output": legacy_override_output,
        "policy_override_output": policy_override_output,
        "effective_override_output": effective_override_output,
    }


async def mongo_find_to_list(cursor, cap: int = _MAX_TENANT_FETCH) -> List[Dict[str, Any]]:
    """Drain a Motor cursor (or test mock with ``to_list``) up to ``cap`` documents."""
    if cursor is None:
        return []
    fn = getattr(cursor, "to_list", None)
    if callable(fn):
        return await fn(cap)
    out: List[Dict[str, Any]] = []
    async for doc in cursor:
        out.append(doc)
        if len(out) >= cap:
            break
    return out


def portfolio_pending_score_recalc_snapshot(properties: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Tenant-scoped honesty fields for Stream B: ``compliance_score_pending`` marks properties whose
    stored headline will refresh after the compliance recalc queue drains. Exposed on compliance-score
    payloads so KPI/live requirement rows are not confused with persisted headline timing.
    """
    n = sum(1 for p in properties if bool(p.get("compliance_score_pending")))
    if n <= 0:
        return {"properties_pending_score_recalc_count": 0, "portfolio_score_recalc_pending_note": None}
    subj_have = "properties have" if n != 1 else "property has"
    note = (
        f"{n} {subj_have} a stored compliance score update queued after recent changes. "
        "The headline uses the last completed calculation until processing finishes; requirement summaries reflect current portal records."
    )
    return {"properties_pending_score_recalc_count": n, "portfolio_score_recalc_pending_note": note}


def property_persisted_score_row_status(prop: Dict[str, Any]) -> str:
    """Client-visible persisted headline status for one property row (SCORING_SEMANTICS_V1)."""
    return resolve_property_score_status(prop)


async def get_persisted_portfolio_headline_for_summary(
    client_id: str,
    *,
    skip_lazy_backfill: bool = False,
) -> Dict[str, Any]:
    """
    Authoritative persisted headline for portfolio summary routes (all properties for client_id).
    Enqueues lazy backfill for rows missing ``compliance_score`` (same semantics as dashboard path).
    """
    db = database.get_db()
    # Full property rows (tenant-scoped) so portfolio legacy matrix + runtime filters match DB truth.
    properties = await mongo_find_to_list(
        db.properties.find({"client_id": client_id}, {"_id": 0}),
        cap=_MAX_TENANT_FETCH,
    )
    if not skip_lazy_backfill:
        from services.compliance_recalc_queue import enqueue_compliance_recalc, TRIGGER_LAZY_BACKFILL, ACTOR_SYSTEM

        for p in properties:
            if p.get("compliance_score") is None:
                await enqueue_compliance_recalc(
                    property_id=p["property_id"],
                    client_id=client_id,
                    trigger_reason=TRIGGER_LAZY_BACKFILL,
                    actor_type=ACTOR_SYSTEM,
                    actor_id=None,
                    correlation_id=f"LAZY_BACKFILL:{p['property_id']}",
                )
    headline = aggregate_persisted_portfolio_headline(properties)
    by_id = {p["property_id"]: p for p in properties if p.get("property_id")}
    return {**headline, "properties": properties, "properties_by_id": by_id}


def _jurisdiction_api_fields(client_row: Dict[str, Any], properties: List[Dict[str, Any]]) -> Dict[str, Any]:
    att = build_portfolio_jurisdiction_attestation(client_row, properties)
    return {
        "jurisdiction_required": att["jurisdiction_required"],
        "compliance_confidence": att["compliance_confidence"],
        "jurisdiction_required_property_ids": att["jurisdiction_required_property_ids"],
        "jurisdiction_required_property_count": att["jurisdiction_required_property_count"],
        "jurisdiction_fallback_acknowledged": bool((client_row or {}).get("jurisdiction_fallback_acknowledged_at")),
        # Raw DB value (may be null); resolution uses canonicalize_uk_portfolio_label in resolve_portfolio_jurisdiction.
        "client_default_jurisdiction": (client_row or {}).get("default_jurisdiction"),
    }


# ============================================================================
# REQUIREMENT TYPE WEIGHTS
# ============================================================================
# Critical legal requirements have higher weights
REQUIREMENT_TYPE_WEIGHTS = {
    # Critical (Legal Requirement)
    "GAS_SAFETY": 1.5,           # Gas Safety Certificate - legally required
    "EICR": 1.4,                 # Electrical Installation - legally required
    "EPC": 1.2,                  # Energy Performance Certificate - required for lettings
    "SMOKE_ALARM": 1.3,          # Smoke/CO alarms - legally required
    "CO_ALARM": 1.3,             # Carbon monoxide alarm
    
    # HMO Specific (Higher risk)
    "HMO_LICENCE": 1.6,          # HMO Licence - critical for HMO properties
    "FIRE_RISK_ASSESSMENT": 1.5, # Fire risk assessment for HMOs
    "FIRE_DOORS": 1.4,           # Fire doors
    "EMERGENCY_LIGHTING": 1.3,   # Emergency lighting
    
    # Standard
    "LANDLORD_INSURANCE": 1.0,   # Insurance
    "DEPOSIT_PROTECTION": 1.1,   # Deposit protection - legally required
    "RIGHT_TO_RENT": 1.2,        # Right to rent checks
    "LEGIONELLA_RISK": 1.1,      # Legionella risk assessment
    
    # Documentation
    "TENANCY_AGREEMENT": 1.0,    # Tenancy agreement
    "INVENTORY": 0.8,            # Property inventory
    "HOW_TO_RENT": 1.0,          # How to Rent guide
}

# Default weight for unknown requirement types
DEFAULT_REQUIREMENT_WEIGHT = 1.0

# HMO multiplier for properties marked as HMO
HMO_SCORE_MULTIPLIER = 0.9  # HMO properties have stricter scoring (90% of normal score)


def get_requirement_weight(requirement_type: str) -> float:
    """
    Map Phase-1 storage slugs (registry-canonical) to the same weight as their canonical type.
    Legacy uppercase keys in REQUIREMENT_TYPE_WEIGHTS win first so smoke_alarm / co_alarm /
    emergency_lighting behaviour stays unchanged.
    """
    from services.requirement_code_registry import normalize_requirement_code as reg_norm

    raw = (requirement_type or "").strip()
    if not raw:
        return DEFAULT_REQUIREMENT_WEIGHT
    raw_key = raw.upper().replace(" ", "_").replace("-", "_")
    if raw_key in REQUIREMENT_TYPE_WEIGHTS:
        return REQUIREMENT_TYPE_WEIGHTS[raw_key]
    canon = reg_norm(raw)
    if canon:
        return REQUIREMENT_TYPE_WEIGHTS.get(canon.upper(), DEFAULT_REQUIREMENT_WEIGHT)
    return DEFAULT_REQUIREMENT_WEIGHT


async def calculate_compliance_score(client_id: str) -> Dict[str, Any]:
    """Return client-level compliance score from stored property scores (fast).

    Uses persisted compliance_score/compliance_breakdown on each Property.
    Legacy properties without a stored score get one recalc and persist (lazy backfill).
    Single source of truth for headline score: persisted ``compliance_scoring_service`` output.

    ``stats`` / ``drivers`` / ``property_breakdown`` use the portal runtime projection
    (``project_requirement_row_client_runtime`` + visibility). When a catalog portfolio
    exists, an alternate lens is attached as ``catalog_portfolio_view`` only — it does
    not replace ``score`` or ``stats``.
    """
    db = database.get_db()
    try:
        properties = await mongo_find_to_list(
            db.properties.find(
                {"client_id": client_id},
                {
                    "_id": 0,
                    "property_id": 1,
                    "compliance_score": 1,
                    "compliance_score_pending": 1,
                    "compliance_breakdown": 1,
                    "compliance_bucket_breakdown": 1,
                    "score_breakdown": 1,
                    "compliance_earned_points": 1,
                    "compliance_applicable_points": 1,
                    "compliance_top_deficits": 1,
                    "compliance_top_next_actions": 1,
                    "compliance_last_calculated_at": 1,
                    "is_hmo": 1,
                    "nickname": 1,
                    "address_line_1": 1,
                    "postcode": 1,
                    "jurisdiction": 1,
                    "scoring_jurisdiction_bucket": 1,
                },
            ),
            cap=_MAX_TENANT_FETCH,
        )
        if not properties:
            client_row_empty = await db.clients.find_one(
                {"client_id": client_id},
                {"_id": 0, "default_jurisdiction": 1, "jurisdiction_fallback_acknowledged_at": 1},
            ) or {}
            _agg_empty = aggregate_persisted_portfolio_headline([])
            _override_empty = await build_portfolio_override_outputs(
                db=db,
                client_id=client_id,
                base_portfolio_risk_state=_agg_empty.get("risk_level"),
                properties=[],
                property_breakdown=[],
                gap_engine={},
                policy_aggregate_unavailable=False,
            )
            _risk_empty = _override_empty["effective_override_output"]
            _pending_empty = portfolio_pending_score_recalc_snapshot([])
            return attach_semantics_contract(
                {
                    "score": None,
                    "grade": None,
                    "color": "gray",
                    "message": _agg_empty.get("score_status_message") or "No properties to evaluate",
                    "score_status": _agg_empty["score_status"],
                    "breakdown": {},
                    "recommendations": [],
                    "enhanced_model": True,
                    "stats": {},
                    "properties_count": 0,
                    "score_last_calculated_at": None,
                    "last_calculated_at": None,
                    "score_model_version": "1.2",
                    "model_updated_at": "2026-01-15",
                    "data_completeness_percent": None,
                    "components": {},
                    "property_breakdown": [],
                    "drivers": [],
                    "score_authority": "persisted_portfolio_aggregate",
                    "risk_level": _risk_empty["effective_portfolio_risk_state"],
                    "portfolio_risk_level": _risk_empty["effective_portfolio_risk_state"],
                    "base_portfolio_risk_state": _risk_empty["base_portfolio_risk_state"],
                    "effective_portfolio_risk_state": _risk_empty["effective_portfolio_risk_state"],
                    "risk_override_reasons": _risk_empty["risk_override_reasons"],
                    "critical_property_count": _risk_empty["critical_property_count"],
                    "high_risk_gap_count": _risk_empty["high_risk_gap_count"],
                    "unknown_or_stale_property_count": _risk_empty["unknown_or_stale_property_count"],
                    "attention_required": _risk_empty["attention_required"],
                    "critical_property_escalation": _risk_empty["critical_property_escalation"],
                    "suppress_positive_headline": _risk_empty["suppress_positive_headline"],
                    "legacy_override_output": _override_empty["legacy_override_output"],
                    "policy_override_output": _override_empty["policy_override_output"],
                    "effective_override_output": _override_empty["effective_override_output"],
                    "properties_missing_persisted_score": 0,
                    "score_coverage": _agg_empty.get("score_coverage"),
                    "portfolio_last_calculated_at": _agg_empty.get("portfolio_last_calculated_at"),
                    **_pending_empty,
                    **_jurisdiction_api_fields(client_row_empty, []),
                }
            )
        from services.compliance_recalc_queue import enqueue_compliance_recalc, TRIGGER_LAZY_BACKFILL, ACTOR_SYSTEM

        need_backfill = [p for p in properties if p.get("compliance_score") is None]
        for p in need_backfill:
            await enqueue_compliance_recalc(
                property_id=p["property_id"],
                client_id=client_id,
                trigger_reason=TRIGGER_LAZY_BACKFILL,
                actor_type=ACTOR_SYSTEM,
                actor_id=None,
                correlation_id=f"LAZY_BACKFILL:{p['property_id']}",
            )
        scores = [p.get("compliance_score") for p in properties if p.get("compliance_score") is not None]
        if not scores:
            client_row_nr = await db.clients.find_one(
                {"client_id": client_id},
                {"_id": 0, "default_jurisdiction": 1, "jurisdiction_fallback_acknowledged_at": 1},
            ) or {}
            _notice_nr = build_jurisdiction_compliance_notice(client_row_nr, properties)
            _agg_nr = aggregate_persisted_portfolio_headline(properties)
            _override_nr = await build_portfolio_override_outputs(
                db=db,
                client_id=client_id,
                base_portfolio_risk_state=_agg_nr.get("risk_level"),
                properties=properties,
                property_breakdown=[],
                gap_engine={},
                policy_aggregate_unavailable=False,
            )
            _risk_nr = _override_nr["effective_override_output"]
            _pending_nr = portfolio_pending_score_recalc_snapshot(properties)
            return attach_semantics_contract(
                {
                    "score": None,
                    "grade": None,
                    "color": "gray",
                    "message": _agg_nr.get("score_status_message") or "Persisted compliance scores are not available yet.",
                    "score_status": _agg_nr["score_status"],
                    "breakdown": {},
                    "recommendations": [],
                    "enhanced_model": True,
                    "stats": {},
                    "properties_count": len(properties),
                    "score_last_calculated_at": None,
                    "last_calculated_at": None,
                    "score_model_version": "1.2",
                    "model_updated_at": "2026-01-15",
                    "data_completeness_percent": None,
                    "components": {},
                    "property_breakdown": [],
                    "drivers": [],
                    "score_authority": "persisted_portfolio_aggregate",
                    "jurisdiction_compliance_notice": _notice_nr,
                    "risk_level": _risk_nr["effective_portfolio_risk_state"],
                    "portfolio_risk_level": _risk_nr["effective_portfolio_risk_state"],
                    "base_portfolio_risk_state": _risk_nr["base_portfolio_risk_state"],
                    "effective_portfolio_risk_state": _risk_nr["effective_portfolio_risk_state"],
                    "risk_override_reasons": _risk_nr["risk_override_reasons"],
                    "critical_property_count": _risk_nr["critical_property_count"],
                    "high_risk_gap_count": _risk_nr["high_risk_gap_count"],
                    "unknown_or_stale_property_count": _risk_nr["unknown_or_stale_property_count"],
                    "attention_required": _risk_nr["attention_required"],
                    "critical_property_escalation": _risk_nr["critical_property_escalation"],
                    "suppress_positive_headline": _risk_nr["suppress_positive_headline"],
                    "legacy_override_output": _override_nr["legacy_override_output"],
                    "policy_override_output": _override_nr["policy_override_output"],
                    "effective_override_output": _override_nr["effective_override_output"],
                    "properties_missing_persisted_score": _agg_nr.get("properties_missing_score", len(properties)),
                    "score_coverage": _agg_nr.get("score_coverage"),
                    "portfolio_last_calculated_at": _agg_nr.get("portfolio_last_calculated_at"),
                    **_pending_nr,
                    **_jurisdiction_api_fields(client_row_nr, properties),
                }
            )
        client_score = round(sum(scores) / len(scores))
        _head_agg = aggregate_persisted_portfolio_headline(properties)
        breakdowns = [p.get("compliance_breakdown") or {} for p in properties if isinstance(p.get("compliance_breakdown"), dict)]
        if breakdowns:
            def avg(key):
                vals = [b.get(key) for b in breakdowns if b.get(key) is not None]
                return round(sum(vals) / len(vals), 1) if vals else 0
            breakdown = {
                "status_score": avg("status_score"),
                "expiry_score": avg("expiry_score"),
                "document_score": avg("document_score"),
                "overdue_penalty_score": avg("overdue_penalty_score"),
                "risk_score": avg("risk_score"),
            }
        else:
            breakdown = {}
        grade, color, message = score_to_grade_color_message(client_score)
        band_explanation = score_to_band_explanation(client_score)
        client_row = await db.clients.find_one(
            {"client_id": client_id},
            {"_id": 0, "default_jurisdiction": 1, "jurisdiction_fallback_acknowledged_at": 1},
        ) or {}
        property_ids = [p["property_id"] for p in properties]
        raw_requirements = await mongo_find_to_list(
            db.requirements.find({"client_id": client_id}, {"_id": 0}),
            cap=_MAX_TENANT_FETCH,
        )
        from services.requirement_client_runtime_surface import (
            filter_requirement_rows_for_client_runtime_surfaces,
            client_portal_surface_visible_row,
            project_requirement_row_client_runtime,
            compute_client_portal_requirement_stats,
        )

        raw_requirements = await filter_requirement_rows_for_client_runtime_surfaces(
            db,
            client_id=client_id,
            requirements=raw_requirements,
            client_doc=client_row,
            properties=properties,
        )
        from services.requirement_truth import enrich_requirements_for_client

        enriched_portal, _portal_pres = await enrich_requirements_for_client(db, client_id, list(raw_requirements))
        requirements = [project_requirement_row_client_runtime(r) for r in enriched_portal]
        portal_reqs = [r for r in requirements if client_portal_surface_visible_row(r)]
        portal_req_ids = {r.get("requirement_id") for r in portal_reqs if r.get("requirement_id")}
        _counts = compute_client_portal_requirement_stats(portal_reqs)
        total_reqs = _counts["total_requirements"]
        compliant = _counts["compliant"]
        pending = _counts["pending"]
        expiring_soon = _counts["expiring_soon"]
        overdue = _counts["overdue"]
        missing_evidence = _counts["missing_evidence"]
        documents = await mongo_find_to_list(
            db.documents.find(
                {"client_id": client_id},
                {"_id": 0, "property_id": 1, "requirement_id": 1, "status": 1, "evidence_review_state": 1, "assurance_tier": 1},
            ),
            cap=_MAX_TENANT_FETCH,
        )
        req_ids_with_verified = set()
        req_ids_with_any_doc = set()
        for d in documents:
            rid = d.get("requirement_id")
            if not rid or rid not in portal_req_ids:
                continue
            req_ids_with_any_doc.add(rid)
            if evidence_review_contributes_positive_credit(d):
                req_ids_with_verified.add(rid)
        verified_coverage = (len(req_ids_with_verified) / total_reqs * 100) if total_reqs > 0 else 0
        total_coverage = (len(req_ids_with_any_doc) / total_reqs * 100) if total_reqs > 0 else 0
        now = datetime.now(timezone.utc)
        days_until_next = None
        nearest_type = None
        for r in portal_reqs:
            if r.get("status") in ("COMPLIANT", "VALID", "PENDING", "EXPIRING_SOON"):
                due = r.get("due_date")
                if due:
                    try:
                        dt = datetime.fromisoformat(due.replace("Z", "+00:00")) if isinstance(due, str) else due
                        days = (dt - now).days
                        if days >= 0 and (days_until_next is None or days < days_until_next):
                            days_until_next = days
                            nearest_type = r.get("requirement_type")
                    except Exception:
                        pass
        score_last_calculated_at = None
        for p in properties:
            t = p.get("compliance_last_calculated_at")
            if t:
                if score_last_calculated_at is None or (t > score_last_calculated_at):
                    score_last_calculated_at = t
        if isinstance(score_last_calculated_at, datetime) and score_last_calculated_at.tzinfo is None:
            score_last_calculated_at = score_last_calculated_at.replace(tzinfo=timezone.utc)
        _critical_req_types = frozenset(
            {
                "GAS_SAFETY",
                "EICR",
                "SMOKE_ALARM",
                "CO_ALARM",
                "HMO_LICENCE",
                "FIRE_RISK_ASSESSMENT",
                "FIRE_DOORS",
                "EMERGENCY_LIGHTING",
            }
        )
        critical_overdue_count = sum(
            1
            for r in portal_reqs
            if r.get("status") in ("OVERDUE", "EXPIRED")
            and (r.get("requirement_type") or "").upper() in _critical_req_types
        )
        stats = {
            "total_requirements": total_reqs,
            "compliant": compliant,
            "satisfied": _counts.get("satisfied", compliant),
            "pending": pending,
            "missing_evidence": missing_evidence,
            "expiring_soon": expiring_soon,
            "overdue": overdue,
            "critical_overdue": critical_overdue_count,
            "documents_uploaded": len(documents),
            "documents_verified": len([d for d in documents if evidence_review_contributes_positive_credit(d)]),
            "verified_coverage_percent": round(verified_coverage, 1),
            "total_coverage_percent": round(total_coverage, 1),
            "document_coverage_percent": round(total_coverage, 1),
            "days_until_next_expiry": int(days_until_next) if days_until_next is not None else None,
            "nearest_expiry_type": nearest_type,
            "hmo_properties": sum(1 for p in properties if p.get("is_hmo")),
        }
        gap_engine_unavailable = False
        try:
            from services.compliance_gap_sync import aggregate_gap_counts_for_client

            stats["gap_engine"] = await aggregate_gap_counts_for_client(db, client_id)
        except Exception:
            gap_engine_unavailable = True
            stats["gap_engine"] = {
                "by_kind": {},
                "by_severity": {},
                "total_open": 0,
                "policy": {
                    "critical_mandatory_breach_count": 0,
                    "high_risk_gap_count": 0,
                    "attention_only_gap_count": 0,
                    "unknown_or_stale_signal_count": 0,
                    "policy_fields_present_count": 0,
                    "policy_coverage_percent": 0.0,
                    "top_reason_codes": {},
                    "policy_versions": {},
                    "total_open": 0,
                },
            }
        prop_map = {p["property_id"]: p for p in properties}
        jurisdiction_compliance_notice = build_jurisdiction_compliance_notice(client_row, properties)
        res_by_pid = {
            p["property_id"]: resolve_portfolio_jurisdiction(p, client_row)
            for p in properties
            if p.get("property_id")
        }
        by_property = {}
        from services.requirement_satisfaction_service import row_counts_as_missing_evidence

        for r in portal_reqs:
            pid = r.get("property_id")
            if pid not in by_property:
                by_property[pid] = {"valid": 0, "expiring": 0, "overdue": 0, "missing_evidence": 0}
            s = r.get("status")
            if s in ("COMPLIANT", "VALID"):
                by_property[pid]["valid"] += 1
            elif s == "EXPIRING_SOON":
                by_property[pid]["expiring"] += 1
            elif s in ("OVERDUE", "EXPIRED"):
                by_property[pid]["overdue"] += 1
            elif s in ("PENDING", "MISSING"):
                if row_counts_as_missing_evidence(r):
                    by_property[pid]["missing_evidence"] += 1
        property_breakdown = []
        for p in properties:
            pid = p["property_id"]
            bp = by_property.get(pid, {})
            jr = res_by_pid.get(pid)
            jf = property_jurisdiction_requirement_flags(p)
            _lc = p.get("compliance_last_calculated_at")
            if isinstance(_lc, datetime):
                _lc_out = _lc.isoformat()
            else:
                _lc_out = _lc if isinstance(_lc, str) else None
            row = {
                "property_id": pid,
                "name": p.get("nickname") or p.get("address_line_1") or "Property",
                "postcode": p.get("postcode") or "",
                "score": p.get("compliance_score"),
                "score_status": resolve_property_score_status(p),
                "last_calculated_at": _lc_out,
                "valid": bp.get("valid", 0),
                "expiring": bp.get("expiring", 0),
                "overdue": bp.get("overdue", 0),
                "missing_evidence": bp.get("missing_evidence", 0),
                "compliance_basis": jr.compliance_basis if jr else None,
                "effective_jurisdiction_label": jr.effective_label if jr else None,
                "jurisdiction_required": jf["jurisdiction_required"],
                "compliance_confidence": jf["compliance_confidence"],
            }
            _ps = p.get("compliance_score")
            if _ps is not None:
                try:
                    row.update(score_authority_fields(int(round(float(_ps)))))
                except (TypeError, ValueError):
                    pass
            property_breakdown.append(row)
        stats["properties_at_risk_count"] = sum(
            1
            for row in property_breakdown
            if int(row.get("overdue") or 0) > 0
            or (row.get("score") is not None and float(row.get("score") or 0) < 60)
        )
        base_risk_state = _head_agg.get("risk_level") or score_to_risk_level(client_score)
        override_outputs = await build_portfolio_override_outputs(
            db=db,
            client_id=client_id,
            base_portfolio_risk_state=base_risk_state,
            properties=properties,
            property_breakdown=property_breakdown,
            gap_engine=stats.get("gap_engine") or {},
            policy_aggregate_unavailable=gap_engine_unavailable,
        )
        risk_override = override_outputs["effective_override_output"]
        due_0_30 = due_31_60 = due_61_90 = 0
        for r in portal_reqs:
            if r.get("status") in ("COMPLIANT", "VALID", "PENDING", "EXPIRING_SOON"):
                due = r.get("due_date")
                if due:
                    try:
                        dt = datetime.fromisoformat(due.replace("Z", "+00:00")) if isinstance(due, str) else due
                        days = (dt - now).days
                        if 0 <= days <= 30:
                            due_0_30 += 1
                        elif 31 <= days <= 60:
                            due_31_60 += 1
                        elif 61 <= days <= 90:
                            due_61_90 += 1
                    except Exception:
                        pass
        weights_map = {"status": 0.35, "expiry": 0.25, "documents": 0.15, "overdue_penalty": 0.15, "risk_factor": 0.10}
        components = {
            "status": {
                "weight": weights_map["status"],
                "score": round(breakdown.get("status_score", 0), 0),
                "valid": compliant,
                "expiring": expiring_soon,
                "overdue": overdue,
            },
            "timeline": {
                "weight": weights_map["expiry"],
                "score": round(breakdown.get("expiry_score", 0), 0),
                "due_0_30": due_0_30,
                "due_31_60": due_31_60,
                "due_61_90": due_61_90,
                "overdue": overdue,
            },
            "documents": {
                "weight": weights_map["documents"],
                "score": round(breakdown.get("document_score", 0), 0),
                "evidence_coverage_percent": round(verified_coverage, 0),
            },
            "urgency": {
                "weight": weights_map["overdue_penalty"],
                "score": round(breakdown.get("overdue_penalty_score", 0), 0),
                "overdue": overdue,
            },
        }
        property_ids_set = {str(p.get("property_id") or "").strip() for p in properties if str(p.get("property_id") or "").strip()}
        canonical_ids_map = await get_canonical_requirement_ids_map_for_properties(
            client_id,
            property_ids_set,
            db=db,
        )
        canonical_rows_by_property: Dict[str, List[Dict[str, Any]]] = {}
        for rr in portal_reqs:
            pid = str(rr.get("property_id") or "").strip()
            rid = str(rr.get("requirement_id") or "").strip()
            if not pid or not rid:
                continue
            if rid not in (canonical_ids_map.get(pid) or set()):
                continue
            canonical_rows_by_property.setdefault(pid, []).append(rr)

        drivers = []
        seen_driver_keys = set()
        for r in portal_reqs:
            pid = str(r.get("property_id") or "").strip()
            rid = str(r.get("requirement_id") or "").strip()
            if not pid:
                logger.warning(
                    "compliance_score: dropped driver row without property_id",
                    extra={
                        "client_id": client_id,
                        "property_id": None,
                        "raw_requirement_code": r.get("requirement_code") or r.get("canonical_code") or r.get("requirement_type"),
                        "requirement_type": r.get("requirement_type"),
                        "reason": "missing_property_id_for_driver",
                    },
                )
                continue

            canonical_ids_for_property = canonical_ids_map.get(pid) or set()
            if rid:
                if rid not in canonical_ids_for_property:
                    logger.warning(
                        "compliance_score: dropped non-canonical score driver row",
                        extra={
                            "client_id": client_id,
                            "property_id": pid,
                            "requirement_id": rid,
                            "raw_requirement_code": r.get("requirement_code") or r.get("canonical_code") or r.get("requirement_type"),
                            "requirement_type": r.get("requirement_type"),
                            "reason": "noncanonical_requirement_id",
                        },
                    )
                    continue
            else:
                code = normalize_requirement_code(
                    r.get("canonical_code") or r.get("requirement_code") or r.get("requirement_type")
                )
                code_matches = set()
                for cand in canonical_rows_by_property.get(pid, []):
                    cand_code = normalize_requirement_code(
                        cand.get("canonical_code") or cand.get("requirement_code") or cand.get("requirement_type")
                    )
                    cand_rid = str(cand.get("requirement_id") or "").strip()
                    if cand_code and cand_rid and cand_code == code:
                        code_matches.add(cand_rid)
                if len(code_matches) == 1:
                    rid = next(iter(code_matches))
                elif len(code_matches) == 0:
                    logger.warning(
                        "compliance_score: dropped score driver row without canonical match",
                        extra={
                            "client_id": client_id,
                            "property_id": pid,
                            "requirement_id": None,
                            "raw_requirement_code": r.get("requirement_code") or r.get("canonical_code") or r.get("requirement_type"),
                            "requirement_type": r.get("requirement_type"),
                            "reason": "no_canonical_match",
                        },
                    )
                    continue
                else:
                    logger.warning(
                        "compliance_score: dropped score driver row with ambiguous canonical matches",
                        extra={
                            "client_id": client_id,
                            "property_id": pid,
                            "requirement_id": None,
                            "raw_requirement_code": r.get("requirement_code") or r.get("canonical_code") or r.get("requirement_type"),
                            "requirement_type": r.get("requirement_type"),
                            "reason": "ambiguous_match",
                        },
                    )
                    continue

            key = (pid, rid)
            if key in seen_driver_keys:
                continue

            prop = prop_map.get(pid, {})
            s = r.get("status")
            rd = r.get("requirement_display") if isinstance(r.get("requirement_display"), dict) else {}
            req_name = (
                (rd.get("short_name") or rd.get("canonical_name") or "").strip()
                or r.get("description")
                or (r.get("requirement_type") or "Requirement").replace("_", " ")
            )
            evidence = rid in req_ids_with_any_doc
            window_days = resolve_expiring_soon_days_for_requirement(
                r,
                property_doc=prop if isinstance(prop, dict) else None,
                client_doc=client_row if isinstance(client_row, dict) else None,
            )
            if not requirement_has_active_negative_actionability(
                r,
                now=now,
                expiring_window_days=window_days,
            ):
                continue

            take_action = r.get("take_action") if isinstance(r.get("take_action"), dict) else None
            workflow_class = r.get("workflow_class")
            semantic_state = r.get("semantic_state")
            try:
                if semantic_state:
                    observe_consumer_precedence_delta(
                        PORTFOLIO_SCORE,
                        str(semantic_state),
                        property_id=pid,
                        requirement_id=rid or None,
                    )
            except Exception:
                # Observe-only hook: scoring behavior must remain unchanged.
                pass
            evidence_authority = r.get("evidence_authority") if isinstance(r.get("evidence_authority"), dict) else None
            evidence_completeness = (
                r.get("evidence_completeness") if isinstance(r.get("evidence_completeness"), dict) else None
            )
            actions = []
            if take_action and isinstance(take_action.get("primary"), dict):
                primary_kind = str((take_action.get("primary") or {}).get("kind") or "").strip().lower()
                kind_to_action = {
                    "upload_document": "UPLOAD",
                    "view_requirement": "VIEW",
                    "guided_evidence_resolution": "VIEW",
                    "record_external_assessment": "VIEW",
                    "log_maintenance_issue": "VIEW",
                    "open_guidance": "VIEW",
                }
                mapped = kind_to_action.get(primary_kind)
                if mapped:
                    actions.append(mapped)
            else:
                if not evidence:
                    actions.append("UPLOAD")
                if s in ("OVERDUE", "EXPIRED"):
                    actions.append("VIEW")
                elif s == "EXPIRING_SOON":
                    actions.append("VIEW")
                if evidence and s in ("PENDING", "EXPIRING_SOON"):
                    actions.append("CONFIRM")
                if not actions and s not in ("COMPLIANT",):
                    actions.append("VIEW")

            display_status = s
            if s == "EXPIRED":
                display_status = "OVERDUE"
            elif s == "PENDING" and not evidence:
                display_status = "MISSING_EVIDENCE"
            elif s == "PENDING" and evidence:
                display_status = "NEEDS_CONFIRMATION"

            from services.compliance_timeline_presentation import (
                ensure_compliance_timeline_on_requirement,
                timeline_report_date_display,
                timeline_report_date_kind,
                timeline_sort_date_iso,
            )

            tl_row = ensure_compliance_timeline_on_requirement(r)
            date_sort_iso = timeline_sort_date_iso(tl_row)
            date_confidence = timeline_report_date_kind(tl_row).upper()
            drivers.append({
                "property_id": pid,
                "property_name": prop.get("nickname") or prop.get("address_line_1") or pid,
                "requirement_id": rid,
                "requirement_name": req_name,
                "requirement_display": rd if rd else None,
                "semantic_state": semantic_state,
                "workflow_class": workflow_class,
                "status": display_status,
                "date_used": date_sort_iso or r.get("due_date"),
                "date_display": timeline_report_date_display(tl_row),
                "date_confidence": date_confidence if date_confidence != "UNKNOWN" else "UNKNOWN",
                "evidence_uploaded": evidence,
                "actions": list(dict.fromkeys(actions)) if actions else ["VIEW"],
                "take_action": take_action,
                "evidence_authority": evidence_authority,
                "evidence_completeness": evidence_completeness,
                "guidance_target": r.get("guidance_target"),
                "allowed_evidence_modes": r.get("allowed_evidence_modes"),
            })
            seen_driver_keys.add(key)
        if not drivers and portal_reqs:
            logger.warning(
                "compliance_score: all candidate score drivers filtered by canonical guard",
                extra={"client_id": client_id, "reason": "all_drivers_filtered_noncanonical_or_nonnegative"},
            )
        aggregated_actions = []
        for p in properties:
            for action in (p.get("compliance_top_next_actions") or []):
                if isinstance(action, dict):
                    aggregated_actions.append({**action, "property_id": action.get("property_id") or p.get("property_id")})
        aggregated_actions.sort(key=lambda a: float(a.get("impact_points") or 0), reverse=True)
        req_by_id = {
            (str(r.get("property_id") or ""), str(r.get("requirement_id") or "")): r
            for r in portal_reqs
            if r.get("requirement_id")
        }
        req_by_code = {}
        for r in portal_reqs:
            code_key = str(r.get("requirement_code") or r.get("requirement_type") or "").strip().lower()
            if code_key:
                req_by_code.setdefault((str(r.get("property_id") or ""), code_key), r)
        from services.assurance_actionability_service import (
            build_score_confidence_explanation,
            partition_score_recommendations,
        )

        recommendations, assurance_opportunities = partition_score_recommendations(
            aggregated_actions,
            req_by_id,
            req_by_code,
        )
        if not recommendations:
            if overdue > 0:
                recommendations.append({"priority": "high", "action": f"Address {overdue} overdue requirement(s)", "impact": "+10-20 points"})
            if expiring_soon > 0:
                recommendations.append({"priority": "medium", "action": f"Renew {expiring_soon} certificate(s) expiring soon", "impact": "+10-15 points"})

        bucket_entries = [p.get("compliance_bucket_breakdown") or {} for p in properties if p.get("compliance_bucket_breakdown")]
        if bucket_entries:
            def bucket_avg(bucket_name: str) -> float:
                vals = []
                for b in bucket_entries:
                    vals.append(float((b.get(bucket_name) or {}).get("percent") or 0))
                return round(sum(vals) / len(vals), 1) if vals else 0.0
            bucket_breakdown = {
                "legal_core": {"percent": bucket_avg("legal_core")},
                "documentation_completeness": {"percent": bucket_avg("documentation_completeness")},
                "operational_responsiveness": {"percent": bucket_avg("operational_responsiveness")},
                "recency_maintenance_confidence": {"percent": bucket_avg("recency_maintenance_confidence")},
            }
        else:
            bucket_breakdown = {}

        earned_points = sum(float(p.get("compliance_earned_points") or 0) for p in properties)
        applicable_points = sum(float(p.get("compliance_applicable_points") or 0) for p in properties)
        _pending_snap = portfolio_pending_score_recalc_snapshot(properties)
        from services.reporting_semantics_v1 import (
            METRIC_LIFECYCLE_SATISFIED,
            METRIC_SCORE_TRACKED,
            METRIC_TRACKED,
            METRIC_VISIBLE,
            apply_registry_display_semantics,
            build_reporting_semantics_payload,
            compute_reporting_semantic_counts,
        )
        from services.requirement_satisfaction_service import is_requirement_satisfied

        # Registry display semantics use full client + property context (dashboard/Requirements parity).
        # Score-scoped portal_reqs above stay unchanged for score_tracked obligation counts.
        full_client_row = await db.clients.find_one({"client_id": client_id}, {"_id": 0}) or client_row
        registry_properties = await mongo_find_to_list(
            db.properties.find({"client_id": client_id}, {"_id": 0}),
            cap=_MAX_TENANT_FETCH,
        )
        registry_raw = await mongo_find_to_list(
            db.requirements.find({"client_id": client_id}, {"_id": 0}),
            cap=_MAX_TENANT_FETCH,
        )
        registry_raw = await filter_requirement_rows_for_client_runtime_surfaces(
            db,
            client_id=client_id,
            requirements=registry_raw,
            client_doc=full_client_row,
            properties=registry_properties,
        )
        registry_enriched, _registry_pres = await enrich_requirements_for_client(
            db, client_id, list(registry_raw)
        )

        _semantic_counts = apply_registry_display_semantics(
            compute_reporting_semantic_counts(portal_reqs),
            registry_enriched,
        )
        _reporting_semantics = build_reporting_semantics_payload(_semantic_counts)
        stats["visible_requirement_count"] = int(_semantic_counts.get(METRIC_VISIBLE) or total_reqs)
        stats["tracked_requirement_count"] = int(_semantic_counts.get(METRIC_TRACKED) or 0)
        stats["score_tracked_requirement_count"] = int(_semantic_counts.get(METRIC_SCORE_TRACKED) or total_reqs)
        stats["lifecycle_satisfied_count"] = int(
            _semantic_counts.get(METRIC_LIFECYCLE_SATISFIED)
            or sum(1 for r in portal_reqs if is_requirement_satisfied(r))
        )
        from services.lifecycle_kpi_gates import attach_additive_lifecycle_kpi_fields

        attach_additive_lifecycle_kpi_fields(stats, portal_reqs)
        _score_confidence = build_score_confidence_explanation(
            score=client_score,
            semantic_counts=_semantic_counts,
        )
        result = {
            "score": client_score,
            "grade": grade,
            "color": color,
            "message": message,
            "band_explanation": band_explanation,
            "base_portfolio_risk_state": risk_override["base_portfolio_risk_state"],
            "effective_portfolio_risk_state": risk_override["effective_portfolio_risk_state"],
            "risk_override_reasons": risk_override["risk_override_reasons"],
            "critical_property_count": risk_override["critical_property_count"],
            "high_risk_gap_count": risk_override["high_risk_gap_count"],
            "unknown_or_stale_property_count": risk_override["unknown_or_stale_property_count"],
            "attention_required": risk_override["attention_required"],
            "critical_property_escalation": risk_override["critical_property_escalation"],
            "suppress_positive_headline": risk_override["suppress_positive_headline"],
            "legacy_override_output": override_outputs["legacy_override_output"],
            "policy_override_output": override_outputs["policy_override_output"],
            "effective_override_output": override_outputs["effective_override_output"],
            "risk_level": risk_override["effective_portfolio_risk_state"],
            "portfolio_risk_level": risk_override["effective_portfolio_risk_state"],
            "enhanced_model": True,
            "breakdown": breakdown,
            "weights": {
                "status": "35%",
                "expiry": "25%",
                "documents": "15%",
                "overdue_penalty": "15%",
                "risk_factor": "10%",
            },
            "stats": stats,
            "reporting_semantics": _reporting_semantics,
            "recommendations": recommendations[:5],
            "assurance_opportunities": assurance_opportunities[:5],
            "score_confidence": _score_confidence,
            "properties_count": len(properties),
            "score_last_calculated_at": score_last_calculated_at.isoformat() if isinstance(score_last_calculated_at, datetime) else score_last_calculated_at,
            "score_model_version": "1.2",
            "model_updated_at": "2026-01-15",
            "data_completeness_percent": round(verified_coverage, 0) if total_reqs > 0 else None,
            "components": components,
            "gap_engine_policy": (stats.get("gap_engine") or {}).get("policy") or {},
            "property_breakdown": property_breakdown,
            "drivers": drivers,
            "bucket_breakdown": bucket_breakdown,
            "earned_points": round(earned_points, 2),
            "applicable_points": round(applicable_points, 2),
            "top_next_actions": aggregated_actions[:5],
            "top_deficits": [d for p in properties for d in (p.get("compliance_top_deficits") or [])][:10],
            "jurisdictions": sorted(list({p.get("jurisdiction") for p in properties if p.get("jurisdiction")})),
            "score_breakdown_by_property": [
                {
                    "property_id": p.get("property_id"),
                    "name": p.get("nickname") or p.get("address_line_1") or p.get("property_id"),
                    "jurisdiction": p.get("jurisdiction"),
                    "scoring_jurisdiction_bucket": p.get("scoring_jurisdiction_bucket"),
                    "compliance_basis": (
                        res_by_pid.get(p.get("property_id")).compliance_basis
                        if p.get("property_id") in res_by_pid
                        else None
                    ),
                    "effective_jurisdiction_label": (
                        res_by_pid.get(p.get("property_id")).effective_label
                        if p.get("property_id") in res_by_pid
                        else None
                    ),
                    **property_jurisdiction_requirement_flags(p),
                    "score_breakdown": p.get("score_breakdown") or [],
                }
                for p in properties
            ],
            "jurisdiction_compliance_notice": jurisdiction_compliance_notice,
            **_pending_snap,
            **_jurisdiction_api_fields(client_row, properties),
        }
        result["score_status"] = _head_agg.get("score_status")
        result["score_status_message"] = _head_agg.get("score_status_message")
        result["score_coverage"] = _head_agg.get("score_coverage")
        result["portfolio_last_calculated_at"] = _head_agg.get("portfolio_last_calculated_at")
        result["last_calculated_at"] = result.get("score_last_calculated_at")
        result["score_authority"] = "persisted_portfolio_aggregate"
        result["properties_missing_persisted_score"] = _head_agg.get("properties_missing_score", 0)
        if result.get("suppress_positive_headline"):
            _rg, _rc, _rm = risk_level_to_grade_color_message(
                result.get("effective_portfolio_risk_state"),
                score=client_score,
            )
            result["color"] = _rc
            result["message"] = _override_portfolio_message(
                result.get("effective_portfolio_risk_state"),
                result.get("risk_override_reasons") or [],
            )
            result["band_explanation"] = score_to_band_explanation(client_score)
        result = attach_semantics_contract(result)
        # Catalog matrix: optional alternate view only — headline score/grade stay persisted-scoring average.
        try:
            from services.catalog_compliance import get_portfolio_compliance_from_catalog
            catalog = await get_portfolio_compliance_from_catalog(client_id)
            if catalog:
                ps_cat = catalog.get("portfolio_score")
                portfolio_score_int = int(ps_cat) if ps_cat is not None else None
                risk_level = catalog.get("risk_level") or catalog.get("portfolio_risk_level")
                if portfolio_score_int is not None and risk_level:
                    if str(risk_level).strip() == "Low Risk":
                        cg, cc, cm = score_to_grade_color_message(portfolio_score_int)
                    else:
                        cg, cc, cm = risk_level_to_grade_color_message(risk_level)
                elif portfolio_score_int is not None:
                    cg, cc, cm = score_to_grade_color_message(portfolio_score_int)
                else:
                    cg, cc, cm = None, "gray", "Catalog matrix preview has no aggregate score for this portfolio shape."
                result["catalog_portfolio_view"] = {
                    "score_authority": "non_authoritative_requirement_matrix",
                    "portfolio_score": portfolio_score_int,
                    "risk_level": risk_level,
                    "grade": cg,
                    "color": cc,
                    "message": cm,
                    "updated_at": catalog.get("updated_at"),
                    "note": "Catalog-weighted requirement matrix preview only. Headline score and KPI cards must use persisted portfolio aggregate.",
                }
        except Exception as cat_err:
            logger.debug("Catalog compliance optional view not attached: %s", cat_err)
        return result
    except Exception as e:
        logger.error(f"Error calculating compliance score: {e}")
        _pending_err = portfolio_pending_score_recalc_snapshot([])
        return attach_semantics_contract(
            {
                "score": None,
                "grade": None,
                "color": "gray",
                "message": "Unable to calculate score",
                "score_status": "unavailable",
                "breakdown": {},
                "recommendations": [],
                "error": str(e),
                "enhanced_model": True,
                "stats": {},
                "properties_count": 0,
                "score_last_calculated_at": None,
                "last_calculated_at": None,
                "score_model_version": "1.2",
                "model_updated_at": "2026-01-15",
                "data_completeness_percent": None,
                "components": {},
                "property_breakdown": [],
                "drivers": [],
                "score_authority": "unavailable",
                **_pending_err,
                "risk_level": "Moderate Risk",
                "portfolio_risk_level": "Moderate Risk",
                "base_portfolio_risk_state": None,
                "effective_portfolio_risk_state": "Moderate Risk",
                "risk_override_reasons": [PolicyReasonCode.UNKNOWN_OR_STALE_SUPPRESSION.value],
                "critical_property_count": 0,
                "high_risk_gap_count": 0,
                "unknown_or_stale_property_count": 0,
                "attention_required": False,
                "critical_property_escalation": False,
                "suppress_positive_headline": True,
                "legacy_override_output": {
                    "base_portfolio_risk_state": None,
                    "effective_portfolio_risk_state": "Moderate Risk",
                    "risk_override_reasons": [PolicyReasonCode.UNKNOWN_OR_STALE_SUPPRESSION.value],
                    "critical_property_count": 0,
                    "high_risk_gap_count": 0,
                    "unknown_or_stale_property_count": 0,
                    "attention_required": False,
                    "critical_property_escalation": False,
                    "suppress_positive_headline": True,
                },
                "policy_override_output": {
                    "base_portfolio_risk_state": None,
                    "effective_portfolio_risk_state": "Moderate Risk",
                    "risk_override_reasons": [PolicyReasonCode.UNKNOWN_OR_STALE_SUPPRESSION.value],
                    "critical_property_count": 0,
                    "high_risk_gap_count": 0,
                    "unknown_or_stale_property_count": 0,
                    "attention_required": False,
                    "critical_property_escalation": False,
                    "suppress_positive_headline": True,
                },
                "effective_override_output": {
                    "base_portfolio_risk_state": None,
                    "effective_portfolio_risk_state": "Moderate Risk",
                    "risk_override_reasons": [PolicyReasonCode.UNKNOWN_OR_STALE_SUPPRESSION.value],
                    "critical_property_count": 0,
                    "high_risk_gap_count": 0,
                    "unknown_or_stale_property_count": 0,
                    "attention_required": False,
                    "critical_property_escalation": False,
                    "suppress_positive_headline": True,
                    "override_output_source": "legacy",
                    "fallback_applied": False,
                    "fallback_reason_codes": [],
                },
                "jurisdiction_compliance_notice": {
                    "active": False,
                    "compliance_basis": None,
                    "affected_property_ids": [],
                    "affected_property_count": 0,
                },
                **_jurisdiction_api_fields({}, []),
            }
        )


async def _calculate_compliance_score_legacy_from_db(client_id: str) -> Dict[str, Any]:
    """**NON-AUTHORITATIVE / LEGACY — diagnostic or reference only.**

    Computes a client-level score by walking requirements in Mongo without using
    the persisted enterprise headline. **Not** invoked by routes or jobs in the
    current tree; ``calculate_compliance_score`` is the supported read path.

    Do not wire this to client-visible KPIs without product + Stream B tracker
    approval. Prefer ``recalculate_and_persist`` per property, then aggregate
    stored scores.
    """
    db = database.get_db()
    try:
        properties = await db.properties.find(
            {"client_id": client_id},
            {"_id": 0}
        ).to_list(100)
        if not properties:
            return {
                "score": 100,
                "grade": "A",
                "color": "green",
                "message": "No properties to evaluate",
                "breakdown": {},
                "recommendations": [],
                "enhanced_model": True,
            }
        property_ids = [p["property_id"] for p in properties]
        hmo_property_ids = [p["property_id"] for p in properties if p.get("is_hmo", False)]
        hmo_count = len(hmo_property_ids)
        requirements = await db.requirements.find(
            {"property_id": {"$in": property_ids}},
            {"_id": 0}
        ).to_list(500)
        if not requirements:
            return {
                "score": 100,
                "grade": "A",
                "color": "green",
                "message": "No requirements to evaluate",
                "breakdown": {},
                "recommendations": [],
                "enhanced_model": True,
            }
        client_row_l = await db.clients.find_one(
            {"client_id": client_id},
            {"_id": 0, "default_jurisdiction": 1, "jurisdiction_fallback_acknowledged_at": 1},
        ) or {}
        from services.requirement_client_runtime_surface import filter_requirement_rows_for_client_runtime_surfaces

        requirements = await filter_requirement_rows_for_client_runtime_surfaces(
            db,
            client_id=client_id,
            requirements=requirements,
            client_doc=client_row_l,
            properties=properties,
        )
        if not requirements:
            return {
                "score": 100,
                "grade": "A",
                "color": "green",
                "message": "No requirements to evaluate",
                "breakdown": {},
                "recommendations": [],
                "enhanced_model": True,
            }
        documents = await db.documents.find(
            {"property_id": {"$in": property_ids}},
            {"_id": 0}
        ).to_list(500)
        verified_documents = [
            d for d in documents if evidence_review_contributes_positive_credit(d)
        ]
        now = datetime.now(timezone.utc)
        
        # ============================================
        # 1. WEIGHTED REQUIREMENT STATUS SCORE (35%)
        # ============================================
        total_weight = 0
        weighted_points = 0
        
        status_counts = {"COMPLIANT": 0, "PENDING": 0, "EXPIRING_SOON": 0, "OVERDUE": 0, "EXPIRED": 0}
        critical_overdue = []
        
        for req in requirements:
            status = req.get("status", "PENDING")
            req_type = req.get("requirement_type", "UNKNOWN")
            weight = get_requirement_weight(req_type)
            
            # HMO properties have higher weight for HMO-specific requirements
            if req.get("property_id") in hmo_property_ids:
                if req_type.upper() in ["HMO_LICENCE", "FIRE_RISK_ASSESSMENT", "FIRE_DOORS", "EMERGENCY_LIGHTING"]:
                    weight *= 1.2  # Extra 20% weight for HMO requirements on HMO properties
            
            total_weight += weight
            
            # Track status counts
            if status in status_counts:
                status_counts[status] += 1
            else:
                status_counts["PENDING"] += 1
            
            # Calculate weighted points
            # Compliant = 100%, Pending = 70%, Expiring Soon = 40%, Overdue = 0%
            if status == "COMPLIANT":
                weighted_points += weight * 100
            elif status == "PENDING":
                weighted_points += weight * 70
            elif status == "EXPIRING_SOON":
                weighted_points += weight * 40
            else:  # OVERDUE, EXPIRED
                weighted_points += 0
                # Track critical overdue items
                if weight >= 1.3:  # Critical requirement
                    critical_overdue.append({
                        "type": req_type,
                        "property_id": req.get("property_id"),
                        "weight": weight,
                    })
        
        status_score = (weighted_points / (total_weight * 100)) * 100 if total_weight > 0 else 100
        
        total_reqs = len(requirements)
        compliant_count = status_counts["COMPLIANT"]
        pending_count = status_counts["PENDING"]
        expiring_soon_count = status_counts["EXPIRING_SOON"]
        overdue_count = status_counts["OVERDUE"] + status_counts["EXPIRED"]
        
        # ============================================
        # 2. EXPIRY TIMELINE SCORE (25%)
        # ============================================
        # Based on days until next CRITICAL expiry (weighted)
        min_days_until_critical = float('inf')
        min_days_until_any = float('inf')
        nearest_expiry_type = None
        
        for req in requirements:
            if req.get("status") in ["COMPLIANT", "VALID", "PENDING", "EXPIRING_SOON"]:
                due_date_str = req.get("due_date")
                if due_date_str:
                    try:
                        due_date = datetime.fromisoformat(due_date_str.replace('Z', '+00:00')) if isinstance(due_date_str, str) else due_date_str
                        days_until = (due_date - now).days
                        
                        # Track minimum for any requirement
                        if days_until < min_days_until_any:
                            min_days_until_any = days_until
                            nearest_expiry_type = req.get("requirement_type")
                        
                        # Track minimum for critical requirements (weight >= 1.3)
                        req_type = req.get("requirement_type", "UNKNOWN")
                        weight = get_requirement_weight(req_type)
                        if weight >= 1.3 and days_until < min_days_until_critical:
                            min_days_until_critical = days_until
                    except Exception:
                        pass
        
        # Use critical expiry if available, otherwise use any expiry
        effective_min_days = min_days_until_critical if min_days_until_critical != float('inf') else min_days_until_any
        
        # Score based on nearest expiry (more granular)
        if effective_min_days == float('inf'):
            expiry_score = 100
        elif effective_min_days >= 90:
            expiry_score = 100
        elif effective_min_days >= 60:
            expiry_score = 90
        elif effective_min_days >= 30:
            expiry_score = 75
        elif effective_min_days >= 14:
            expiry_score = 50
        elif effective_min_days >= 7:
            expiry_score = 30
        elif effective_min_days >= 0:
            expiry_score = 15
        else:
            expiry_score = 0  # Already expired
        
        # ============================================
        # 3. VERIFIED DOCUMENT COVERAGE (15%)
        # ============================================
        # Only count VERIFIED documents (not UNVERIFIED uploads)
        requirements_with_verified_docs = set()
        for doc in verified_documents:
            if doc.get("requirement_id"):
                requirements_with_verified_docs.add(doc["requirement_id"])
        
        verified_doc_rate = (len(requirements_with_verified_docs) / total_reqs * 100) if total_reqs > 0 else 0
        
        # Also track total doc rate for reference
        requirements_with_any_docs = set()
        for doc in documents:
            if doc.get("requirement_id"):
                requirements_with_any_docs.add(doc["requirement_id"])
        
        any_doc_rate = (len(requirements_with_any_docs) / total_reqs * 100) if total_reqs > 0 else 0
        
        doc_score = min(verified_doc_rate, 100)  # Cap at 100
        
        # ============================================
        # 4. OVERDUE PENALTY (15%)
        # ============================================
        # Heavy penalty for overdue items, especially critical ones
        overdue_penalty_base = 100 - (overdue_count / total_reqs * 100) if total_reqs > 0 else 100
        
        # Extra penalty for critical overdue items
        critical_penalty = len(critical_overdue) * 10  # -10 points per critical overdue
        overdue_penalty_score = max(0, overdue_penalty_base - critical_penalty)
        
        # ============================================
        # 5. RISK FACTOR (10%)
        # ============================================
        # Considers HMO properties and historical issues
        risk_score = 100
        
        # HMO penalty: Each HMO property reduces risk score slightly
        # (HMO properties have stricter compliance requirements)
        if hmo_count > 0:
            hmo_penalty = min(hmo_count * 5, 25)  # Max 25 point penalty for HMOs
            risk_score -= hmo_penalty
        
        # Future: Historical late renewal penalty could be added here
        # by checking past requirement records for late renewals
        
        risk_score = max(0, risk_score)
        
        # ============================================
        # CALCULATE FINAL SCORE
        # ============================================
        # Weights: Status 35%, Expiry 25%, Docs 15%, Overdue 15%, Risk 10%
        final_score = (
            (status_score * 0.35) +
            (expiry_score * 0.25) +
            (doc_score * 0.15) +
            (overdue_penalty_score * 0.15) +
            (risk_score * 0.10)
        )
        
        final_score = round(max(0, min(100, final_score)))
        grade, color, message = score_to_grade_color_message(final_score)
        
        # Generate prioritized recommendations
        recommendations = []
        
        # Critical overdue items first
        if critical_overdue:
            for item in critical_overdue[:2]:  # Top 2 critical
                recommendations.append({
                    "priority": "critical",
                    "action": f"Immediately address overdue {item['type'].replace('_', ' ')}",
                    "impact": "+15-25 points",
                    "type": item["type"],
                })
        
        # Regular overdue items
        if overdue_count > len(critical_overdue):
            other_overdue = overdue_count - len(critical_overdue)
            recommendations.append({
                "priority": "high",
                "action": f"Address {other_overdue} overdue requirement(s)",
                "impact": "+10-20 points",
            })
        
        # Expiring soon
        if expiring_soon_count > 0:
            recommendations.append({
                "priority": "medium",
                "action": f"Renew {expiring_soon_count} certificate(s) expiring soon",
                "impact": "+10-15 points",
            })
        
        # Document verification
        unverified_count = len(requirements_with_any_docs) - len(requirements_with_verified_docs)
        if unverified_count > 0:
            recommendations.append({
                "priority": "medium",
                "action": f"Verify {unverified_count} uploaded document(s) awaiting verification",
                "impact": "+5-10 points",
            })
        
        # Low document coverage
        if verified_doc_rate < 50:
            recommendations.append({
                "priority": "low",
                "action": "Upload and verify more supporting documents",
                "impact": "+5-10 points",
            })
        
        # Next expiry warning
        if 0 < effective_min_days < 30:
            recommendations.append({
                "priority": "medium",
                "action": f"Next expiry ({nearest_expiry_type or 'requirement'}) in {int(effective_min_days)} days - schedule renewal",
                "impact": "+10 points",
            })
        
        return {
            "score": final_score,
            "grade": grade,
            "color": color,
            "message": message,
            "enhanced_model": True,  # Flag for enhanced scoring
            "breakdown": {
                "status_score": round(status_score, 1),
                "expiry_score": round(expiry_score, 1),
                "document_score": round(doc_score, 1),
                "overdue_penalty_score": round(overdue_penalty_score, 1),
                "risk_score": round(risk_score, 1),
            },
            "weights": {
                "status": "35%",
                "expiry": "25%",
                "documents": "15%",
                "overdue_penalty": "15%",
                "risk_factor": "10%",
            },
            "stats": {
                "total_requirements": total_reqs,
                "compliant": compliant_count,
                "pending": pending_count,
                "expiring_soon": expiring_soon_count,
                "overdue": overdue_count,
                "critical_overdue": len(critical_overdue),
                "documents_uploaded": len(documents),
                "documents_verified": len(verified_documents),
                "verified_coverage_percent": round(verified_doc_rate, 1),
                "total_coverage_percent": round(any_doc_rate, 1),
                "days_until_next_expiry": int(effective_min_days) if effective_min_days != float('inf') else None,
                "nearest_expiry_type": nearest_expiry_type,
                "hmo_properties": hmo_count,
            },
            "recommendations": recommendations[:5],  # Top 5 recommendations
            "properties_count": len(properties),
        }
    
    except Exception as e:
        logger.error(f"Error calculating compliance score: {e}")
        return {
            "score": 0,
            "grade": "?",
            "color": "gray",
            "message": "Unable to calculate score",
            "breakdown": {},
            "recommendations": [],
            "error": str(e),
            "enhanced_model": True,
        }


async def get_requirement_type_breakdown(client_id: str) -> Dict[str, Any]:
    """Get compliance breakdown by requirement type with weights."""
    db = database.get_db()
    
    properties = await db.properties.find(
        {"client_id": client_id},
        {"_id": 0},
    ).to_list(100)
    
    if not properties:
        return {"breakdown": [], "total": 0}
    
    property_ids = [p["property_id"] for p in properties]
    
    requirements = await db.requirements.find(
        {"property_id": {"$in": property_ids}},
        {"_id": 0}
    ).to_list(500)
    client_row_b = await db.clients.find_one(
        {"client_id": client_id},
        {"_id": 0, "default_jurisdiction": 1, "jurisdiction_fallback_acknowledged_at": 1},
    ) or {}
    from services.requirement_client_runtime_surface import filter_requirement_rows_for_client_runtime_surfaces

    requirements = await filter_requirement_rows_for_client_runtime_surfaces(
        db,
        client_id=client_id,
        requirements=requirements,
        client_doc=client_row_b,
        properties=properties,
    )
    
    type_breakdown = {}
    
    for req in requirements:
        req_type = req.get("requirement_type", "UNKNOWN")
        status = req.get("status", "PENDING")
        weight = get_requirement_weight(req_type)
        
        if req_type not in type_breakdown:
            type_breakdown[req_type] = {
                "type": req_type,
                "weight": weight,
                "total": 0,
                "compliant": 0,
                "pending": 0,
                "expiring_soon": 0,
                "overdue": 0,
            }
        
        type_breakdown[req_type]["total"] += 1
        
        if status == "COMPLIANT":
            type_breakdown[req_type]["compliant"] += 1
        elif status == "PENDING":
            type_breakdown[req_type]["pending"] += 1
        elif status == "EXPIRING_SOON":
            type_breakdown[req_type]["expiring_soon"] += 1
        else:
            type_breakdown[req_type]["overdue"] += 1
    
    # Calculate compliance rate per type
    breakdown_list = []
    for type_data in type_breakdown.values():
        if type_data["total"] > 0:
            type_data["compliance_rate"] = round(
                (type_data["compliant"] / type_data["total"]) * 100, 1
            )
        else:
            type_data["compliance_rate"] = 100
        breakdown_list.append(type_data)
    
    # Sort by weight (highest first)
    breakdown_list.sort(key=lambda x: x["weight"], reverse=True)
    
    return {
        "breakdown": breakdown_list,
        "total": len(requirements),
        "weights_explanation": {
            "critical": "1.3+ weight (Gas Safety, EICR, HMO Licence, Fire Safety)",
            "standard": "1.0-1.2 weight (EPC, Deposit Protection, Right to Rent)",
            "documentation": "0.8-1.0 weight (Inventory, Tenancy Agreement)",
        }
    }
