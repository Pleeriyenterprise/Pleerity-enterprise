"""
Portfolio compliance summary for Audit Intelligence Platform.
GET /api/portfolio/compliance-summary: catalog-driven when catalog present, else legacy.
GET /api/portfolio/properties/{id}/compliance-detail: matrix, score, risk (catalog-driven).
"""
from fastapi import APIRouter, Request, Depends, status, HTTPException
from fastapi import Query
from database import database
from middleware import client_route_guard
from utils.risk_bands import score_to_risk_level, score_authority_fields, risk_level_to_band_explanation
from services.catalog_compliance import (
    get_property_compliance_detail,
    get_portfolio_compliance_from_catalog,
)
from services.compliance_score import (
    get_persisted_portfolio_headline_for_summary,
    mongo_find_to_list,
    property_persisted_score_row_status,
    build_portfolio_override_outputs,
)
from services.scoring_semantics_v1 import attach_semantics_contract, SCORE_STATUS_CALCULATING
from services.score_cognition_service import portfolio_property_cognition_fields
from datetime import datetime, timezone
from typing import Any, Dict, Optional
import logging

from services.trust_surface_observability import (
    SURFACE_PORTFOLIO_SUMMARY_REFRESH,
    build_portfolio_summary_trust_surface_metadata,
    ensure_trust_surface_correlation_id,
)
from utils.compliance_fanout_log import compliance_fanout_extra
from services.requirement_client_runtime_surface import project_requirement_row_client_runtime

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/portfolio", tags=["portfolio"], dependencies=[Depends(client_route_guard)])

REQUIREMENT_POINTS = {
    "VALID": 100,
    "COMPLIANT": 100,
    "EXPIRING_SOON": 70,
    "PENDING": 30,
    "MISSING": 30,
    "OVERDUE": 0,
    "EXPIRED": 0,
}


@router.get("/compliance-summary")
async def get_compliance_summary(request: Request):
    """
    Portfolio compliance summary. Headline ``portfolio_score`` / ``risk_level`` always use persisted
    property scores (``compliance_score`` aggregate). Catalog or legacy matrix lenses are returned only
    under explicitly non-authoritative preview keys for requirement KPIs / diagnostics.
    """
    user = await client_route_guard(request)
    client_id = user["client_id"]
    headline = await get_persisted_portfolio_headline_for_summary(client_id)
    db = database.get_db()
    corr = ensure_trust_surface_correlation_id(SURFACE_PORTFOLIO_SUMMARY_REFRESH, client_id, None)
    gap_engine_unavailable = False
    gap_exc: Optional[Exception] = None
    try:
        from services.compliance_gap_sync import aggregate_gap_counts_for_client

        gap_engine = await aggregate_gap_counts_for_client(db, client_id)
    except Exception as e:
        gap_exc = e
        gap_engine_unavailable = True
        logger.warning(
            "portfolio compliance-summary gap aggregate failed: %s",
            e,
            extra=compliance_fanout_extra(
                op="trust_surface",
                stage="gap_engine_failed",
                client_id=client_id,
                correlation_id=corr,
                surface_name=SURFACE_PORTFOLIO_SUMMARY_REFRESH,
                section_name="gap_engine_aggregate",
                degraded_reason=str(e),
                fallback_used=True,
                downstream_dependency="compliance_gap_sync.aggregate_gap_counts_for_client",
            ),
        )
        gap_engine = {
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
    portfolio_trust_meta = build_portfolio_summary_trust_surface_metadata(
        client_id=client_id,
        correlation_id=corr,
        gap_engine_unavailable=gap_engine_unavailable,
        headline=headline,
        gap_error=gap_exc,
    )

    def _with_portfolio_trust(payload: Dict[str, Any]) -> Dict[str, Any]:
        merged = dict(payload)
        merged["trust_surface_operational_metadata"] = portfolio_trust_meta
        return merged

    def _portfolio_score_presentation(portfolio_score, effective_risk_level: Optional[str] = None) -> Dict[str, Any]:
        if portfolio_score is None:
            return {}
        try:
            fields = score_authority_fields(int(round(float(portfolio_score))))
        except (TypeError, ValueError):
            return {}
        if effective_risk_level:
            fields["risk_level"] = effective_risk_level
            fields["band_explanation"] = risk_level_to_band_explanation(effective_risk_level)
        return fields

    def _property_row_score_presentation(persisted_score, risk_level: Optional[str]) -> Dict[str, Any]:
        if persisted_score is None:
            return {}
        try:
            fields = score_authority_fields(int(round(float(persisted_score))))
        except (TypeError, ValueError):
            return {}
        if risk_level:
            fields["risk_level"] = risk_level
        return fields

    catalog_result = await get_portfolio_compliance_from_catalog(client_id)
    if catalog_result:
        merged_props = []
        for p in catalog_result.get("properties", []):
            pid = p["property_id"]
            row = headline["properties_by_id"].get(pid, {})
            persisted = row.get("compliance_score")
            preview_matrix = p.get("score")
            st = property_persisted_score_row_status(row)
            if st == SCORE_STATUS_CALCULATING:
                risk_out = None
            elif row.get("risk_level") is not None:
                risk_out = row.get("risk_level")
            elif persisted is not None:
                risk_out = score_to_risk_level(int(round(float(persisted))))
            else:
                risk_out = None
            _lc = row.get("compliance_last_calculated_at")
            if hasattr(_lc, "isoformat"):
                _lc = _lc.isoformat()
            merged_props.append(
                {
                    "property_id": pid,
                    "name": p.get("name"),
                    "nickname": p.get("nickname"),
                    "address_line_1": p.get("address_line_1"),
                    "postcode": p.get("postcode"),
                    "score": persisted,
                    "property_score": persisted,
                    "preview_matrix_score": preview_matrix,
                    "risk_level": risk_out,
                    "score_status": st,
                    "score_authority": "persisted_property_score",
                    "last_calculated_at": _lc if isinstance(_lc, str) else None,
                    "overdue_count": p.get("overdue_count", 0),
                    "expiring_soon_count": p.get("expiring_30_count", 0),
                    "expiring_30_count": p.get("expiring_30_count", 0),
                    "missing_count": p.get("missing_count", 0),
                    **_property_row_score_presentation(persisted, risk_out),
                    **portfolio_property_cognition_fields(
                        row,
                        {
                            "overdue_count": p.get("overdue_count", 0),
                            "expiring_30_count": p.get("expiring_30_count", 0),
                            "missing_count": p.get("missing_count", 0),
                        },
                    ),
                }
            )
        override_outputs = await build_portfolio_override_outputs(
            db=db,
            client_id=client_id,
            base_portfolio_risk_state=headline.get("risk_level"),
            properties=headline.get("properties") or [],
            property_breakdown=merged_props,
            gap_engine=gap_engine,
            policy_aggregate_unavailable=gap_engine_unavailable,
        )
        risk_override = override_outputs["effective_override_output"]
        return attach_semantics_contract(
            _with_portfolio_trust(
                {
                    "portfolio_score": headline.get("portfolio_score"),
                    "risk_level": risk_override.get("effective_portfolio_risk_state"),
                    "portfolio_risk_level": risk_override.get("effective_portfolio_risk_state"),
                    **_portfolio_score_presentation(
                        headline.get("portfolio_score"),
                        risk_override.get("effective_portfolio_risk_state"),
                    ),
                    "base_portfolio_risk_state": risk_override.get("base_portfolio_risk_state"),
                    "effective_portfolio_risk_state": risk_override.get("effective_portfolio_risk_state"),
                    "risk_override_reasons": risk_override.get("risk_override_reasons"),
                    "critical_property_count": risk_override.get("critical_property_count"),
                    "high_risk_gap_count": risk_override.get("high_risk_gap_count"),
                    "unknown_or_stale_property_count": risk_override.get("unknown_or_stale_property_count"),
                    "attention_required": risk_override.get("attention_required"),
                    "critical_property_escalation": risk_override.get("critical_property_escalation"),
                    "suppress_positive_headline": risk_override.get("suppress_positive_headline"),
                    "legacy_override_output": override_outputs["legacy_override_output"],
                    "policy_override_output": override_outputs["policy_override_output"],
                    "effective_override_output": override_outputs["effective_override_output"],
                    "score_status": headline.get("score_status"),
                    "score_status_message": headline.get("score_status_message"),
                    "score_authority": "persisted_portfolio_aggregate",
                    "last_calculated_at": headline.get("portfolio_last_calculated_at"),
                    "score_coverage": headline.get("score_coverage"),
                    "updated_at": catalog_result.get("updated_at", datetime.now(timezone.utc).isoformat()),
                    "kpis": catalog_result.get("kpis", {}),
                    "gap_engine_diagnostics": {"policy": (gap_engine.get("policy") or {})},
                    "properties": merged_props,
                    "catalog_matrix_portfolio_preview": {
                        "score_authority": "non_authoritative_requirement_matrix",
                        "portfolio_score": catalog_result.get("portfolio_score"),
                        "portfolio_risk_level": catalog_result.get("portfolio_risk_level"),
                        "risk_level": catalog_result.get("risk_level"),
                        "updated_at": catalog_result.get("updated_at"),
                        "note": "Catalog-weighted matrix preview only; headline KPIs use persisted compliance scores.",
                    },
                }
            )
        )
    # Legacy matrix path (no catalog): operational preview only for matrix numbers.
    properties = headline.get("properties") or []
    if not properties:
        override_outputs = await build_portfolio_override_outputs(
            db=db,
            client_id=client_id,
            base_portfolio_risk_state=headline.get("risk_level"),
            properties=[],
            property_breakdown=[],
            gap_engine=gap_engine,
            policy_aggregate_unavailable=gap_engine_unavailable,
        )
        risk_override = override_outputs["effective_override_output"]
        return attach_semantics_contract(
            _with_portfolio_trust(
                {
                    "portfolio_score": headline.get("portfolio_score"),
                    "risk_level": risk_override.get("effective_portfolio_risk_state"),
                    "portfolio_risk_level": risk_override.get("effective_portfolio_risk_state"),
                    **_portfolio_score_presentation(
                        headline.get("portfolio_score"),
                        risk_override.get("effective_portfolio_risk_state"),
                    ),
                    "base_portfolio_risk_state": risk_override.get("base_portfolio_risk_state"),
                    "effective_portfolio_risk_state": risk_override.get("effective_portfolio_risk_state"),
                    "risk_override_reasons": risk_override.get("risk_override_reasons"),
                    "critical_property_count": risk_override.get("critical_property_count"),
                    "high_risk_gap_count": risk_override.get("high_risk_gap_count"),
                    "unknown_or_stale_property_count": risk_override.get("unknown_or_stale_property_count"),
                    "attention_required": risk_override.get("attention_required"),
                    "critical_property_escalation": risk_override.get("critical_property_escalation"),
                    "suppress_positive_headline": risk_override.get("suppress_positive_headline"),
                    "legacy_override_output": override_outputs["legacy_override_output"],
                    "policy_override_output": override_outputs["policy_override_output"],
                    "effective_override_output": override_outputs["effective_override_output"],
                    "score_status": headline.get("score_status"),
                    "score_status_message": headline.get("score_status_message"),
                    "score_authority": "persisted_portfolio_aggregate",
                    "last_calculated_at": headline.get("portfolio_last_calculated_at"),
                    "score_coverage": headline.get("score_coverage"),
                    "gap_engine_diagnostics": {"policy": (gap_engine.get("policy") or {})},
                    "properties": [],
                }
            )
        )
    client_doc = await db.clients.find_one({"client_id": client_id}, {"_id": 0, "default_jurisdiction": 1}) or {}
    requirements = await mongo_find_to_list(
        db.requirements.find({"client_id": client_id}, {"_id": 0}),
        cap=500_000,
    )
    from services.requirement_client_runtime_surface import filter_requirement_rows_for_client_runtime_surfaces

    requirements = await filter_requirement_rows_for_client_runtime_surfaces(
        db,
        client_id=client_id,
        requirements=requirements,
        client_doc=client_doc,
        properties=properties,
    )
    total_weighted_score = 0.0
    total_requirements = 0
    property_summaries = []
    for prop in properties:
        pid = prop["property_id"]
        prop_reqs = [
            project_requirement_row_client_runtime(r)
            for r in requirements
            if r.get("property_id") == pid
        ]
        overdue_count = sum(
            1
            for r in prop_reqs
            if (r.get("status") or "").upper().strip() in ("OVERDUE", "EXPIRED")
        )
        expiring_soon_count = sum(
            1
            for r in prop_reqs
            if (r.get("status") or "").upper().strip() == "EXPIRING_SOON"
        )
        if not prop_reqs:
            legacy_matrix_property_score = None
        else:
            points = []
            for r in prop_reqs:
                status_val = (r.get("status") or "PENDING").upper().strip()
                pt = REQUIREMENT_POINTS.get(status_val, REQUIREMENT_POINTS["PENDING"])
                points.append(pt)
            legacy_matrix_property_score = round(sum(points) / len(points))
            legacy_matrix_property_score = max(0, min(100, legacy_matrix_property_score))
        matrix_risk = (
            score_to_risk_level(legacy_matrix_property_score)
            if legacy_matrix_property_score is not None
            else None
        )
        total_weighted_score += (legacy_matrix_property_score or 0) * len(prop_reqs)
        total_requirements += len(prop_reqs)
        name = prop.get("nickname") or prop.get("address_line_1") or pid
        persisted = prop.get("compliance_score")
        st = property_persisted_score_row_status(prop)
        if st == SCORE_STATUS_CALCULATING:
            risk_out = None
        elif prop.get("risk_level") is not None:
            risk_out = prop.get("risk_level")
        elif persisted is not None:
            risk_out = score_to_risk_level(int(round(float(persisted))))
        else:
            risk_out = None
        _plc = prop.get("compliance_last_calculated_at")
        if hasattr(_plc, "isoformat"):
            _plc = _plc.isoformat()
        _plc_out = _plc if isinstance(_plc, str) else None
        property_summaries.append(
            {
                "property_id": pid,
                "name": name,
                "nickname": prop.get("nickname"),
                "address_line_1": prop.get("address_line_1"),
                "postcode": prop.get("postcode"),
                "score": persisted,
                "property_score": persisted,
                "preview_legacy_matrix_score": legacy_matrix_property_score,
                "preview_legacy_matrix_risk_level": matrix_risk,
                "risk_level": risk_out,
                "score_status": st,
                "last_calculated_at": _plc_out,
                "overdue_count": overdue_count,
                "expiring_soon_count": expiring_soon_count,
                "missing_count": 0,
                **portfolio_property_cognition_fields(
                    prop,
                    {"overdue_count": overdue_count, "expiring_soon_count": expiring_soon_count, "missing_count": 0},
                ),
            }
        )
    if total_requirements == 0:
        matrix_portfolio_score = None
        matrix_portfolio_risk = None
    else:
        matrix_portfolio_score = round(total_weighted_score / total_requirements)
        matrix_portfolio_score = max(0, min(100, matrix_portfolio_score))
        matrix_portfolio_risk = score_to_risk_level(matrix_portfolio_score)
    override_outputs = await build_portfolio_override_outputs(
        db=db,
        client_id=client_id,
        base_portfolio_risk_state=headline.get("risk_level"),
        properties=properties,
        property_breakdown=property_summaries,
        gap_engine=gap_engine,
        policy_aggregate_unavailable=gap_engine_unavailable,
    )
    risk_override = override_outputs["effective_override_output"]
    return attach_semantics_contract(
        _with_portfolio_trust(
            {
                "portfolio_score": headline.get("portfolio_score"),
                "risk_level": risk_override.get("effective_portfolio_risk_state"),
                "portfolio_risk_level": risk_override.get("effective_portfolio_risk_state"),
                **_portfolio_score_presentation(
                    headline.get("portfolio_score"),
                    risk_override.get("effective_portfolio_risk_state"),
                ),
                "base_portfolio_risk_state": risk_override.get("base_portfolio_risk_state"),
                "effective_portfolio_risk_state": risk_override.get("effective_portfolio_risk_state"),
                "risk_override_reasons": risk_override.get("risk_override_reasons"),
                "critical_property_count": risk_override.get("critical_property_count"),
                "high_risk_gap_count": risk_override.get("high_risk_gap_count"),
                "unknown_or_stale_property_count": risk_override.get("unknown_or_stale_property_count"),
                "attention_required": risk_override.get("attention_required"),
                "critical_property_escalation": risk_override.get("critical_property_escalation"),
                "suppress_positive_headline": risk_override.get("suppress_positive_headline"),
                "legacy_override_output": override_outputs["legacy_override_output"],
                "policy_override_output": override_outputs["policy_override_output"],
                "effective_override_output": override_outputs["effective_override_output"],
                "score_status": headline.get("score_status"),
                "score_status_message": headline.get("score_status_message"),
                "score_authority": "persisted_portfolio_aggregate",
                "last_calculated_at": headline.get("portfolio_last_calculated_at"),
                "score_coverage": headline.get("score_coverage"),
                "gap_engine_diagnostics": {"policy": (gap_engine.get("policy") or {})},
                "properties": property_summaries,
                "legacy_matrix_portfolio_preview": {
                    "score_authority": "non_authoritative_legacy_matrix",
                    "portfolio_score": matrix_portfolio_score,
                    "risk_level": matrix_portfolio_risk,
                    "note": "Legacy equal-weight matrix preview only; headline uses persisted compliance scores.",
                },
            }
        )
    )


@router.get("/properties/{property_id}/compliance-detail")
async def get_property_compliance_detail_route(request: Request, property_id: str):
    """
    Property-level compliance detail: requirement matrix (from catalog + state), property_score,
    risk_index, risk_level, score_delta, score_change_summary, last_updated_at. Evidence-based status only; not legal advice.
    """
    user = await client_route_guard(request)
    client_id = user["client_id"]
    db = database.get_db()
    prop = await db.properties.find_one(
        {"property_id": property_id, "client_id": client_id},
        {
            "_id": 0,
            "property_id": 1,
            "nickname": 1,
            "name": 1,
            "address_line_1": 1,
            "address_line_2": 1,
            "city": 1,
            "postcode": 1,
            "compliance_score": 1,
            "risk_level": 1,
            "compliance_last_calculated_at": 1,
            "jurisdiction": 1,
            "compliance_score_pending": 1,
        },
    )
    if not prop:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")
    preview_matrix = None
    detail = await get_property_compliance_detail(client_id, property_id)
    if detail is not None:
        response = dict(detail)
        preview_matrix = response.pop("property_score", None)
    else:
        # Fallback: no catalog or no applicable; return minimal from requirements
        client_doc = await db.clients.find_one({"client_id": client_id}, {"_id": 0, "default_jurisdiction": 1}) or {}
        prop_full = await db.properties.find_one(
            {"property_id": property_id, "client_id": client_id},
            {"_id": 0},
        ) or prop
        requirements = await db.requirements.find(
            {"client_id": client_id, "property_id": property_id},
            {"_id": 0},
        ).to_list(200)
        from services.requirement_client_runtime_surface import filter_requirement_rows_for_client_runtime_surfaces
        from services.requirement_read_model_guard import (
            filter_rows_to_canonical_requirement_ids,
            get_canonical_requirement_ids_for_property,
        )

        requirements = await filter_requirement_rows_for_client_runtime_surfaces(
            db,
            client_id=client_id,
            requirements=requirements,
            client_doc=client_doc,
            properties=[prop_full],
        )
        canonical_ids = await get_canonical_requirement_ids_for_property(client_id, property_id, db=db)
        requirements, dropped = filter_rows_to_canonical_requirement_ids(requirements, canonical_ids)
        for d in dropped:
            logger.warning(
                "portfolio.compliance-detail fallback: dropped non-canonical requirement row",
                extra={
                    "client_id": client_id,
                    "property_id": property_id,
                    "requirement_id": d.get("requirement_id"),
                    "requirement_code": d.get("requirement_code"),
                    "requirement_type": d.get("requirement_type"),
                    "source": d.get("source"),
                    "reason": d.get("reason"),
                },
            )
        from services.catalog_compliance import _days_to_expiry, _requirement_numeric_score
        from services.requirement_truth import enrich_requirements_for_client
        from services.requirement_satisfaction_service import row_counts_as_missing_evidence

        requirements, _fb_pres = await enrich_requirements_for_client(db, client_id, requirements)
        kpis = {"overdue": 0, "expiring_30": 0, "missing": 0, "compliant": 0, "status_valid": 0}
        matrix = []
        for r_raw in requirements:
            r = project_requirement_row_client_runtime(r_raw)
            due_raw = r.get("due_date")
            days = _days_to_expiry(due_raw)
            cs = (r.get("status") or "PENDING")
            s = str(cs).upper()
            if s in ("COMPLIANT", "VALID"):
                kpis["status_valid"] += 1
            if s in ("OVERDUE", "EXPIRED"):
                kpis["overdue"] += 1
            elif s == "EXPIRING_SOON" and (days or 0) <= 30:
                kpis["expiring_30"] += 1
            elif s in ("PENDING", "MISSING"):
                if row_counts_as_missing_evidence(r_raw):
                    kpis["missing"] += 1
                else:
                    kpis["compliant"] += 1
            else:
                kpis["compliant"] += 1
            rd = r_raw.get("requirement_display") if isinstance(r_raw.get("requirement_display"), dict) else {}
            legacy_title = r.get("description") or r.get("requirement_type")
            from services.catalog_compliance import _client_matrix_presentation_fields

            matrix.append({
                "requirement_code": r.get("requirement_type"),
                "title": (rd.get("canonical_name") or "").strip() or legacy_title,
                "display_name": (rd.get("short_name") or rd.get("canonical_name") or "").strip() or legacy_title,
                "requirement_display": rd if rd else None,
                "status": cs,
                "numeric_score": _requirement_numeric_score(cs, due_raw),
                "criticality": "MED",
                "weight": 1,
                "expiry_date": due_raw,
                "days_to_expiry": days,
                "evidence_doc_id": None,
                "requirement_id": r.get("requirement_id"),
                "property_id": property_id,
                "take_action": r_raw.get("take_action"),
                **_client_matrix_presentation_fields(r_raw),
            })
        if not matrix:
            property_score = None
        else:
            property_score = round(sum(m["numeric_score"] for m in matrix) / len(matrix))
        response = {
            "property_id": property_id,
            "property_name": prop.get("nickname") or prop.get("address_line_1") or property_id,
            "matrix": matrix,
            "property_score": property_score,
            "risk_index": 0.0,
            "risk_level": score_to_risk_level(property_score) if property_score is not None else None,
            "kpis": kpis,
        }
        preview_matrix = response.pop("property_score", None)
    # Client-visible headline score is always persisted; matrix is preview only.
    response["preview_matrix_score"] = preview_matrix
    response["score"] = prop.get("compliance_score")
    if prop.get("risk_level") is not None:
        response["risk_level"] = prop.get("risk_level")
    elif prop.get("compliance_score") is not None:
        response["risk_level"] = score_to_risk_level(int(round(float(prop["compliance_score"]))))
    else:
        response["risk_level"] = None
    response["score_status"] = property_persisted_score_row_status(prop)
    response["score_authority"] = "persisted_property_score"
    _plat = prop.get("compliance_last_calculated_at")
    if hasattr(_plat, "isoformat"):
        _plat = _plat.isoformat()
    response["last_calculated_at"] = _plat if isinstance(_plat, str) else None
    response["last_updated_at"] = response.get("last_updated_at") or prop.get("compliance_last_calculated_at")
    latest_log = await db.score_change_log.find_one(
        {"property_id": property_id, "client_id": client_id},
        sort=[("created_at", -1)],
        projection={"_id": 0, "delta": 1, "changed_requirements": 1, "created_at": 1},
    )
    if latest_log and latest_log.get("delta") is not None:
        response["score_delta"] = latest_log["delta"]
        changed = latest_log.get("changed_requirements") or []
        if changed:
            response["score_change_summary"] = f"{'Up' if latest_log['delta'] and latest_log['delta'] > 0 else 'Down'} {abs(latest_log['delta'])} pts; {len(changed)} requirement(s) changed"
        else:
            response["score_change_summary"] = f"{'Up' if latest_log['delta'] > 0 else 'Down'} {abs(latest_log['delta'])} pts" if latest_log["delta"] else "No change"
    else:
        response["score_delta"] = None
        response["score_change_summary"] = None
    prop_full = await db.properties.find_one(
        {"property_id": property_id, "client_id": client_id},
        {"_id": 0, "jurisdiction": 1},
    ) or {}
    client_doc = await db.clients.find_one(
        {"client_id": client_id},
        {"_id": 0, "default_jurisdiction": 1},
    ) or {}
    from services.compliance_rules_registry import (
        jurisdiction_attribution_for_property,
        log_jurisdiction_resolution_debug,
        resolve_portfolio_jurisdiction,
    )

    _jr = resolve_portfolio_jurisdiction(prop_full, client_doc)
    log_jurisdiction_resolution_debug(
        context="portfolio.compliance-detail",
        property_id=property_id,
        raw_property_jurisdiction=prop_full.get("jurisdiction"),
        raw_client_default_jurisdiction=client_doc.get("default_jurisdiction"),
        resolution=_jr,
    )
    _att = jurisdiction_attribution_for_property(prop_full, client_doc, _resolution=_jr)
    response["compliance_basis"] = _att["compliance_basis"]
    response["effective_jurisdiction_label"] = _att["effective_jurisdiction_label"]
    response["jurisdiction_source"] = _att["jurisdiction_source"]
    response["client_default_jurisdiction"] = client_doc.get("default_jurisdiction")
    from presentation.property_display_name import get_property_display_name

    response["nickname"] = prop.get("nickname")
    response["name"] = prop.get("name")
    response["address_line_1"] = prop.get("address_line_1")
    response["address_line_2"] = prop.get("address_line_2")
    response["city"] = prop.get("city")
    response["postcode"] = prop.get("postcode")
    response["property_name"] = get_property_display_name(prop)
    score_val = response.get("score")
    if score_val is not None:
        try:
            response.update(score_authority_fields(int(round(float(score_val)))))
        except (TypeError, ValueError):
            pass
    return attach_semantics_contract(response)


@router.get("/properties/{property_id}/score-history")
async def get_property_score_history_route(request: Request, property_id: str, limit: int = 20):
    """Return last N score change log entries for this property (client-scoped)."""
    user = await client_route_guard(request)
    db = database.get_db()
    prop = await db.properties.find_one(
        {"property_id": property_id, "client_id": user["client_id"]},
        {"_id": 0, "property_id": 1},
    )
    if not prop:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")
    limit = min(max(1, limit), 50)
    entries = await db.score_change_log.find(
        {"property_id": property_id, "client_id": user["client_id"]},
        {"_id": 0, "previous_score": 1, "new_score": 1, "delta": 1, "reason": 1, "changed_requirements": 1, "created_at": 1},
    ).sort("created_at", -1).limit(limit).to_list(limit)
    from services.property_timeline_service import present_score_change_reason

    for e in entries:
        pr = present_score_change_reason(e.get("reason"))
        e["reason_label"] = pr["title"]
        e["reason_detail"] = pr.get("description") or ""
    return {"property_id": property_id, "entries": entries}


@router.get("/properties/{property_id}/timeline")
async def get_property_timeline_route(
    request: Request,
    property_id: str,
    category: Optional[str] = Query(None, description="Filter by category: EVIDENCE, COMPLIANCE, MAINTENANCE, SCORE_RISK, SYSTEM"),
    actor_type: Optional[str] = Query(None, description="Filter by actor: user, admin, system"),
    from_date: Optional[str] = Query(None, description="From date YYYY-MM-DD"),
    to_date: Optional[str] = Query(None, description="To date YYYY-MM-DD"),
    limit: int = Query(50, ge=1, le=100),
    cursor: Optional[str] = Query(None, description="Pagination cursor (last timestamp)"),
):
    """Unified property timeline: evidence, compliance, maintenance, score events. Chronological, newest first."""
    user = await client_route_guard(request)
    db = database.get_db()
    prop = await db.properties.find_one(
        {"property_id": property_id, "client_id": user["client_id"]},
        {"_id": 0, "property_id": 1},
    )
    if not prop:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")
    try:
        from services.property_timeline_service import get_property_timeline
        data = await get_property_timeline(
            client_id=user["client_id"],
            property_id=property_id,
            category=category,
            actor_type=actor_type,
            from_date=from_date,
            to_date=to_date,
            limit=limit,
            cursor=cursor,
        )
        return data
    except Exception as e:
        logger.exception("Property timeline error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load timeline",
        )


@router.get("/properties/{property_id}/evidence")
async def get_property_evidence(request: Request, property_id: str):
    """
    Evidence vault data for the Property Evidence tab: summary, documents, recent events.
    Composes existing documents list + requirements + timeline (EVIDENCE category).
    Additive; does not replace GET /documents.
    """
    user = await client_route_guard(request)
    client_id = user["client_id"]
    db = database.get_db()
    prop = await db.properties.find_one(
        {"property_id": property_id, "client_id": client_id},
        {"_id": 0, "property_id": 1, "jurisdiction": 1},
    )
    if not prop:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")

    # Documents for this property (exclude file_path)
    documents = await db.documents.find(
        {"client_id": client_id, "property_id": property_id},
        {"_id": 0, "file_path": 0},
    ).sort("uploaded_at", -1).to_list(500)

    # Requirements for this property (for missing-critical count)
    client_doc_ev = await db.clients.find_one({"client_id": client_id}, {"_id": 0, "default_jurisdiction": 1}) or {}
    prop_evidence = await db.properties.find_one(
        {"property_id": property_id, "client_id": client_id},
        {"_id": 0},
    ) or prop
    requirements = await db.requirements.find(
        {"client_id": client_id, "property_id": property_id},
        {"_id": 0},
    ).to_list(200)
    from services.requirement_client_runtime_surface import filter_requirement_rows_for_client_runtime_surfaces

    requirements = await filter_requirement_rows_for_client_runtime_surfaces(
        db,
        client_id=client_id,
        requirements=requirements,
        client_doc=client_doc_ev,
        properties=[prop_evidence],
    )
    from services.requirement_truth import enrich_requirements_for_client
    from services.requirement_satisfaction_service import row_counts_as_missing_evidence

    requirements, _ev_pres = await enrich_requirements_for_client(db, client_id, requirements)

    # Linked: documents that have a requirement linked
    linked = sum(1 for d in documents if d.get("requirement_id"))
    missing_critical = 0
    for r in requirements:
        if (r.get("applicability") or "").upper() == "NOT_REQUIRED":
            continue
        if r.get("client_surface_visible") is False:
            continue
        if not row_counts_as_missing_evidence(r):
            continue
        crit = str(r.get("criticality") or r.get("risk") or "").upper()
        if crit in ("HIGH", "MED", "MEDIUM"):
            missing_critical += 1

    # Pending confirmation: has extraction but status != VERIFIED
    def _has_extraction(doc):
        if doc.get("extraction_id"):
            return True
        ai = doc.get("ai_extraction") or {}
        return ai.get("status") == "completed" and ai.get("data")
    pending_confirmation = sum(
        1 for d in documents
        if _has_extraction(d) and (d.get("status") or "").upper() != "VERIFIED"
    )

    last_uploaded_at = None
    for d in documents:
        u = d.get("uploaded_at")
        if u:
            last_uploaded_at = u
            break

    summary = {
        "totalDocuments": len(documents),
        "linked": linked,
        "pendingConfirmation": pending_confirmation,
        "missingCriticalEvidence": missing_critical,
        "lastUploadedAt": last_uploaded_at,
    }

    # Recent evidence events from timeline
    try:
        from services.property_timeline_service import get_property_timeline
        timeline_data = await get_property_timeline(
            client_id=client_id,
            property_id=property_id,
            category="EVIDENCE",
            limit=20,
        )
        recent_events = (timeline_data.get("items") or [])[:20]
    except Exception as e:
        logger.warning("Evidence timeline fallback: %s", e)
        recent_events = []

    from services.evidence_review_migration import effective_assurance_tier, effective_evidence_review_state
    from services.document_operational_state import attach_document_operational_projection
    from services.document_linkage_governance import (
        attach_document_linkage_projection_batch,
        load_runtime_requirements_for_client,
    )
    from services.document_visibility_governance import (
        attach_document_visibility_projection_batch,
        group_documents_by_registry_section,
    )

    runtime_ids, runtime_reqs = await load_runtime_requirements_for_client(
        db, client_id=client_id, property_id=property_id
    )
    for d in documents:
        d["evidence_review_state"] = effective_evidence_review_state(d)
        d["assurance_tier"] = effective_assurance_tier(d)
        attach_document_operational_projection(d)
    attach_document_linkage_projection_batch(
        documents,
        runtime_requirement_ids=runtime_ids,
        runtime_requirements=runtime_reqs,
    )
    attach_document_visibility_projection_batch(
        documents,
        requirements=runtime_reqs,
    )
    registry = group_documents_by_registry_section(documents)
    attention_required_count = sum(1 for d in documents if d.get("document_attention_required") is True)

    summary["attentionRequired"] = attention_required_count
    summary["activeEvidence"] = len(registry.get("active_evidence") or [])
    summary["operationalAttachments"] = len(registry.get("operational_attachments") or [])

    return {
        "summary": summary,
        "documents": documents,
        "registry": registry,
        "recentEvents": recent_events,
    }


# Client-visible audit timeline (same event types as admin timeline, excluding admin-only actions)
_TIMELINE_ACTIONS = [
    "INTAKE_SUBMITTED",
    "INTAKE_PROPERTY_ADDED",
    "INTAKE_DOCUMENT_UPLOADED",
    "PROVISIONING_STARTED",
    "PROVISIONING_COMPLETE",
    "PROVISIONING_FAILED",
    "PASSWORD_TOKEN_GENERATED",
    "PASSWORD_SET_SUCCESS",
    "PASSWORD_SETUP_LINK_RESENT",
    "PORTAL_INVITE_RESENT",
    "PORTAL_INVITE_EMAIL_FAILED",
    "USER_LOGIN_SUCCESS",
    "USER_LOGIN_FAILED",
    "DOCUMENT_UPLOADED",
    "DOCUMENT_VERIFIED",
    "DOCUMENT_REJECTED",
    "DOCUMENT_AI_ANALYZED",
    "EMAIL_SENT",
    "REMINDER_SENT",
    "DIGEST_SENT",
    "COMPLIANCE_STATUS_UPDATED",
]


@router.get("/audit-timeline")
async def get_portfolio_audit_timeline(request: Request, limit: int = 50):
    """
    Get audit timeline for the authenticated client (read-only).
    Key events: intake, provisioning, auth, documents, notifications, compliance.
    Does not include admin-only actions.
    """
    user = await client_route_guard(request)
    client_id = user["client_id"]
    db = database.get_db()
    limit = max(1, min(100, limit))
    logs = await db.audit_logs.find(
        {"client_id": client_id, "action": {"$in": _TIMELINE_ACTIONS}},
        {"_id": 0},
    ).sort("timestamp", -1).limit(limit).to_list(limit)
    categorized = {
        "intake": [],
        "provisioning": [],
        "authentication": [],
        "documents": [],
        "notifications": [],
        "compliance": [],
    }
    for log in logs:
        action = log.get("action", "")
        if action.startswith("INTAKE_"):
            categorized["intake"].append(log)
        elif action.startswith("PROVISIONING_"):
            categorized["provisioning"].append(log)
        elif action in [
            "PASSWORD_TOKEN_GENERATED", "PASSWORD_SET_SUCCESS", "PASSWORD_SETUP_LINK_RESENT",
            "PORTAL_INVITE_RESENT", "PORTAL_INVITE_EMAIL_FAILED", "USER_LOGIN_SUCCESS", "USER_LOGIN_FAILED",
        ]:
            categorized["authentication"].append(log)
        elif action.startswith("DOCUMENT_"):
            categorized["documents"].append(log)
        elif action in ["EMAIL_SENT", "REMINDER_SENT", "DIGEST_SENT"]:
            categorized["notifications"].append(log)
        elif action.startswith("COMPLIANCE_"):
            categorized["compliance"].append(log)
    return {
        "client_id": client_id,
        "timeline": logs,
        "categorized": categorized,
        "total_events": len(logs),
    }
