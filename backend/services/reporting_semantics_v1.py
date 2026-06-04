"""
REPORTING_SEMANTICS_V1 — canonical definitions for requirement counts on reporting surfaces.

Surfaces may intentionally show different numbers when they represent different concepts.
This module makes those concepts explicit and provides shared loaders so accidental drift
(e.g. missing enrich_requirements_for_client on exports) is eliminated.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from services.requirement_client_runtime_surface import (
    client_portal_surface_visible_row,
    compute_client_portal_requirement_stats,
    filter_requirement_rows_for_client_runtime_surfaces,
    project_requirement_row_client_runtime,
)
from services.scoring_semantics_v1 import SCORING_SEMANTICS_VERSION

REPORTING_SEMANTICS_VERSION = "v1"

# --- Metric identifiers (stable API keys) ---
METRIC_TRACKED = "tracked_requirement_count"
METRIC_SCORE_TRACKED = "score_tracked_requirement_count"
METRIC_COMPLIANT_SCORING = "compliant_requirement_count"
METRIC_SATISFIED = "satisfied_requirement_count"
METRIC_VERIFIED = "verified_requirement_count"
METRIC_MISSING_DOCUMENT = "missing_document_count"
METRIC_EXPIRING = "expiring_requirement_count"
METRIC_PLATFORM_REVIEW_PENDING = "platform_review_pending_count"
METRIC_SELF_RECORDED = "self_recorded_count"

REPORTING_METRIC_DEFINITIONS: Dict[str, Dict[str, str]] = {
    METRIC_TRACKED: {
        "label": "Tracked requirements",
        "short_help": (
            "Registry rows in scope on the Requirements page (tracked DOCUMENT/JOB items, "
            "excluding not-applicable lifecycle)."
        ),
        "authority": "tracked_registry_projection",
    },
    METRIC_SCORE_TRACKED: {
        "label": "Score-tracked obligations",
        "short_help": (
            "Obligations counted in the compliance score projection after runtime filtering "
            "and portal visibility."
        ),
        "authority": "score_projection_pipeline",
    },
    METRIC_COMPLIANT_SCORING: {
        "label": "Valid for scoring",
        "short_help": "Rows with projected compliance status COMPLIANT or VALID (score KPI bucket).",
        "authority": "score_projection_pipeline",
    },
    METRIC_SATISFIED: {
        "label": "Lifecycle satisfied (unverified)",
        "short_help": "Client lifecycle SATISFIED_UNVERIFIED — recorded evidence not yet fully verified.",
        "authority": "client_lifecycle_state",
    },
    METRIC_VERIFIED: {
        "label": "Lifecycle verified",
        "short_help": "Client lifecycle VERIFIED — platform-accepted evidence state.",
        "authority": "client_lifecycle_state",
    },
    METRIC_MISSING_DOCUMENT: {
        "label": "Missing document (score view)",
        "short_help": (
            "Score projection: pending/missing rows that still count as missing required evidence "
            "(satisfied-without-doc excluded)."
        ),
        "authority": "score_projection_pipeline",
    },
    METRIC_EXPIRING: {
        "label": "Expiring soon (score view)",
        "short_help": "Projected status EXPIRING_SOON in score-tracked set.",
        "authority": "score_projection_pipeline",
    },
    METRIC_PLATFORM_REVIEW_PENDING: {
        "label": "Awaiting platform review",
        "short_help": "Client lifecycle PENDING_REVIEW — evidence submitted, not yet verified.",
        "authority": "client_lifecycle_state",
    },
    METRIC_SELF_RECORDED: {
        "label": "Self-recorded assurance",
        "short_help": (
            "Rows with assurance_tier SELF_RECORDED or lifecycle SATISFIED_UNVERIFIED "
            "without verified assurance."
        ),
        "authority": "assurance_tier_and_lifecycle",
    },
}

# Export grades (report surfaces)
GRADE_OPERATIONAL = "OPERATIONAL_EXPORT"
GRADE_CLIENT_PRESENTATION = "CLIENT_PRESENTATION"
GRADE_AUDIT_ARTIFACT = "AUDIT_ARTIFACT"
GRADE_REGULATORY = "REGULATORY_SUBMISSION"
GRADE_EXECUTIVE = "EXECUTIVE_SUMMARY"

EXPORT_GRADE_DEFINITIONS: Dict[str, Dict[str, str]] = {
    GRADE_OPERATIONAL: {
        "label": "Operational export",
        "disclaimer": "For internal operations and data handoff — not an immutable audit artifact.",
    },
    GRADE_CLIENT_PRESENTATION: {
        "label": "Client presentation",
        "disclaimer": "Structured summary for clients; informational only — not legal advice.",
    },
    GRADE_AUDIT_ARTIFACT: {
        "label": "Audit artifact",
        "disclaimer": "Governed bundle with manifest and checksums; intended for evidentiary review.",
    },
    GRADE_REGULATORY: {
        "label": "Regulatory submission",
        "disclaimer": "Only the governed audit evidence pack meets regulatory submission grade.",
    },
    GRADE_EXECUTIVE: {
        "label": "Executive summary",
        "disclaimer": "High-level headline metrics; may omit requirement-level assurance detail.",
    },
}

EXPORT_DETERMINISM_LIVE_REGENERATED = "live_regenerated"
EXPORT_DETERMINISM_POINT_IN_TIME = "point_in_time_snapshot"
EXPORT_DETERMINISM_IMMUTABLE_ARTIFACT = "immutable_artifact"

LIVE_REGENERATED_DISCLOSURE = (
    "This report reflects current portfolio state at generation time and may differ from prior downloads."
)
IMMUTABLE_ARTIFACT_DISCLOSURE = (
    "This artifact is stored at generation time with manifest checksums; re-download returns the same bytes."
)

PDF_ENGINE_REPORTLAB = "reportlab_server"
PDF_ENGINE_JSPDF = "jspdf_client"

PDF_ENGINE_RULES: Dict[str, Dict[str, Any]] = {
    PDF_ENGINE_REPORTLAB: {
        "allowed_grades": [GRADE_CLIENT_PRESENTATION, GRADE_AUDIT_ARTIFACT, GRADE_REGULATORY, GRADE_EXECUTIVE],
        "deterministic": True,
    },
    PDF_ENGINE_JSPDF: {
        "allowed_grades": [GRADE_OPERATIONAL, GRADE_CLIENT_PRESENTATION],
        "prohibited_grades": [GRADE_AUDIT_ARTIFACT, GRADE_REGULATORY],
        "deterministic": False,
        "note": "Client-rendered; governance metadata may be thinner than server PDFs.",
    },
}

SURFACE_EXPORT_REGISTRY: Dict[str, Dict[str, str]] = {
    "compliance_summary_csv": {
        "export_grade": GRADE_CLIENT_PRESENTATION,
        "determinism": EXPORT_DETERMINISM_POINT_IN_TIME,
        "pdf_engine": "",
    },
    "requirements_report_csv": {
        "export_grade": GRADE_CLIENT_PRESENTATION,
        "determinism": EXPORT_DETERMINISM_POINT_IN_TIME,
        "pdf_engine": "",
    },
    "score_drivers_csv": {
        "export_grade": GRADE_OPERATIONAL,
        "determinism": EXPORT_DETERMINISM_POINT_IN_TIME,
        "pdf_engine": "",
    },
    "evidence_readiness_pdf": {
        "export_grade": GRADE_CLIENT_PRESENTATION,
        "determinism": EXPORT_DETERMINISM_LIVE_REGENERATED,
        "pdf_engine": PDF_ENGINE_REPORTLAB,
    },
    "evidence_readiness_redownload": {
        "export_grade": GRADE_CLIENT_PRESENTATION,
        "determinism": EXPORT_DETERMINISM_LIVE_REGENERATED,
        "pdf_engine": PDF_ENGINE_REPORTLAB,
        "disclosure": LIVE_REGENERATED_DISCLOSURE,
    },
    "audit_evidence_pack_zip": {
        "export_grade": GRADE_AUDIT_ARTIFACT,
        "determinism": EXPORT_DETERMINISM_IMMUTABLE_ARTIFACT,
        "pdf_engine": PDF_ENGINE_REPORTLAB,
        "disclosure": IMMUTABLE_ARTIFACT_DISCLOSURE,
    },
    "evidence_pack_jobs_zip": {
        "export_grade": GRADE_OPERATIONAL,
        "determinism": EXPORT_DETERMINISM_POINT_IN_TIME,
        "pdf_engine": "",
        "disclosure": "Operational CSV/ZIP export — not regulator-grade audit artifact.",
    },
    "compliance_summary_pdf_jspdf": {
        "export_grade": GRADE_OPERATIONAL,
        "determinism": EXPORT_DETERMINISM_POINT_IN_TIME,
        "pdf_engine": PDF_ENGINE_JSPDF,
        "disclosure": "Internal fallback when reports_pdf unavailable — not for external regulator handoff.",
    },
    "professional_requirements_pdf": {
        "export_grade": GRADE_CLIENT_PRESENTATION,
        "determinism": EXPORT_DETERMINISM_POINT_IN_TIME,
        "pdf_engine": PDF_ENGINE_REPORTLAB,
    },
    "monthly_digest_pdf_jspdf": {
        "export_grade": GRADE_EXECUTIVE,
        "determinism": EXPORT_DETERMINISM_POINT_IN_TIME,
        "pdf_engine": PDF_ENGINE_JSPDF,
    },
    "professional_compliance_pdf": {
        "export_grade": GRADE_CLIENT_PRESENTATION,
        "determinism": EXPORT_DETERMINISM_POINT_IN_TIME,
        "pdf_engine": PDF_ENGINE_REPORTLAB,
    },
    "score_explanation_pdf": {
        "export_grade": GRADE_EXECUTIVE,
        "determinism": EXPORT_DETERMINISM_LIVE_REGENERATED,
        "pdf_engine": PDF_ENGINE_REPORTLAB,
    },
}


def _lifecycle_state(row: Dict[str, Any]) -> str:
    return str(row.get("client_lifecycle_state") or row.get("lifecycle_state") or "").strip().upper()


def requirement_row_in_tracked_attention_views(row: Dict[str, Any]) -> bool:
    """Mirror frontend isRequirementIncludedInAttentionViews (backend parity)."""
    if not row or row.get("client_surface_visible") is False:
        return False
    life = _lifecycle_state(row)
    if life == "NOT_APPLICABLE":
        return False
    if row.get("is_tracked") is False or row.get("tracked") is False:
        return False
    cls = str(row.get("compliance_requirement_class") or row.get("requirement_class") or "").upper()
    if cls in ("OBLIGATION", "SYSTEM"):
        return False
    if cls and cls not in ("DOCUMENT", "JOB"):
        return False
    app = str(row.get("applicability") or "").upper().strip()
    if app == "NOT_REQUIRED":
        return False
    st = str(row.get("status") or "").upper()
    if st == "NOT_REQUIRED":
        return False
    return True


async def load_score_projection_portal_rows(
    db: Any,
    *,
    client_id: str,
    client_doc: Optional[Dict[str, Any]] = None,
    properties: Optional[List[Dict[str, Any]]] = None,
    requirements: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """
    Same pipeline as ``calculate_compliance_score`` stats: filter → enrich → project → portal-visible.
    """
    from services.requirement_truth import enrich_requirements_for_client

    if client_doc is None:
        client_doc = await db.clients.find_one({"client_id": client_id}, {"_id": 0}) or {}
    if properties is None:
        properties = await db.properties.find({"client_id": client_id}, {"_id": 0}).to_list(1000)
    if requirements is None:
        requirements = await db.requirements.find({"client_id": client_id}, {"_id": 0}).to_list(10000)
    requirements = await filter_requirement_rows_for_client_runtime_surfaces(
        db,
        client_id=client_id,
        requirements=requirements,
        client_doc=client_doc,
        properties=properties,
    )
    enriched, _ = await enrich_requirements_for_client(db, client_id, list(requirements))
    projected = [project_requirement_row_client_runtime(r) for r in enriched]
    return [r for r in projected if client_portal_surface_visible_row(r)]


def compute_reporting_semantic_counts(
    enriched_portal_rows: List[Dict[str, Any]],
) -> Dict[str, int]:
    """Canonical counts A–I from enriched + projected portal-visible rows."""
    score_rows = list(enriched_portal_rows)
    tracked_rows = [r for r in enriched_portal_rows if requirement_row_in_tracked_attention_views(r)]
    buckets = compute_client_portal_requirement_stats(score_rows)

    satisfied = 0
    verified = 0
    pending_review = 0
    self_recorded = 0
    for r in tracked_rows:
        life = _lifecycle_state(r)
        if life == "SATISFIED_UNVERIFIED":
            satisfied += 1
        elif life == "VERIFIED":
            verified += 1
        elif life == "PENDING_REVIEW":
            pending_review += 1
        tier = str(r.get("assurance_tier") or "").strip().upper()
        if tier == "SELF_RECORDED" or (life == "SATISFIED_UNVERIFIED" and tier != "VERIFIED"):
            self_recorded += 1

    return {
        METRIC_TRACKED: len(tracked_rows),
        METRIC_SCORE_TRACKED: buckets["total_requirements"],
        METRIC_COMPLIANT_SCORING: buckets["compliant"],
        METRIC_MISSING_DOCUMENT: buckets["missing_evidence"],
        METRIC_EXPIRING: buckets["expiring_soon"],
        METRIC_SATISFIED: satisfied,
        METRIC_VERIFIED: verified,
        METRIC_PLATFORM_REVIEW_PENDING: pending_review,
        METRIC_SELF_RECORDED: self_recorded,
        # Legacy bucket aliases for reporting_service / stats parity
        "pending": buckets["pending"],
        "overdue": buckets["overdue"],
    }


def build_reporting_semantics_payload(counts: Dict[str, int]) -> Dict[str, Any]:
    return {
        "version": REPORTING_SEMANTICS_VERSION,
        "scoring_semantics_version": SCORING_SEMANTICS_VERSION,
        "counts": counts,
        "definitions": REPORTING_METRIC_DEFINITIONS,
        "convergence_note": (
            "score_tracked_requirement_count and compliant_requirement_count align with dashboard "
            "compliance-score stats when the same enrich+projection pipeline is used."
        ),
    }


def legacy_stats_from_semantic_counts(counts: Dict[str, int]) -> Dict[str, int]:
    """Map semantic counts to legacy compliance-score stats keys."""
    return {
        "total_requirements": counts.get(METRIC_SCORE_TRACKED, 0),
        "compliant": counts.get(METRIC_COMPLIANT_SCORING, 0),
        "pending": counts.get("pending", 0),
        "missing_evidence": counts.get(METRIC_MISSING_DOCUMENT, 0),
        "expiring_soon": counts.get(METRIC_EXPIRING, 0),
        "overdue": counts.get("overdue", 0),
    }


def csv_semantics_preamble_rows(counts: Dict[str, int], *, generated_at: str) -> List[List[str]]:
    """Rows appended after headline block in compliance/requirements CSV exports."""
    rows: List[List[str]] = [
        ["# reporting_semantics_version", REPORTING_SEMANTICS_VERSION],
        ["# reporting_semantics_generated_at", generated_at],
    ]
    for metric_id, definition in REPORTING_METRIC_DEFINITIONS.items():
        val = counts.get(metric_id, "")
        rows.append([f"# metric_{metric_id}", str(val), definition.get("label", ""), definition.get("short_help", "")])
    rows.append([
        "# semantic_convergence_note",
        "Score-tracked metrics use enrich+projection pipeline. Tracked registry count may differ — see definitions.",
    ])
    return rows


def async_reporting_disclosure(
    *,
    score_status: Optional[str],
    score_status_message: Optional[str],
    last_calculated_at: Optional[str],
) -> Dict[str, Any]:
    """Disclosure block for exports during async recalc / stale headline."""
    st = (score_status or "").strip().lower()
    pending = st in ("calculating", "partial", "reconciliation_required")
    stale = st == "stale"
    lines = []
    if pending:
        lines.append("Portfolio compliance score may be updating; requirement rows reflect current records.")
    if stale:
        lines.append("Persisted compliance score is stale; headline may not reflect latest recalculation.")
    if score_status_message:
        lines.append(str(score_status_message))
    return {
        "score_status": score_status,
        "score_pending_recalculation": pending,
        "score_stale": stale,
        "last_calculated_at": last_calculated_at,
        "messages": lines,
    }
