"""
Enterprise Audit Evidence Pack builder (governed ZIP + manifest + checksums + GridFS).
"""
from __future__ import annotations

import hashlib
import io
import json
import logging
import re
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from bson import ObjectId

from database import database
from models import AuditAction, UserRole
from services.branding_resolver_service import BrandingContext, resolve_branding
from services.compliance_status_authority import classify_compliance_status
from services.compliance_registry_publish_service import fetch_published_metadata
from services.requirement_client_runtime_surface import filter_requirement_rows_for_client_runtime_surfaces
from services.requirement_evidence_authority import AUTHORITY_VERSION, EA_VERIFIED_CURRENT, authority_state
from utils.audit import create_audit_log
from utils.storage_paths import resolve_document_storage_path

logger = logging.getLogger(__name__)

GRIDFS_BUCKET = "compliance_audit_packs"
CONTRACT_VERSION = "cvp_audit_evidence_pack_v2"
EXPORT_VERSION = "2026.04"
EVIDENCE_PACK_VERSION = "2.0.0"
ROOT_DIR = "Audit_Evidence_Pack"
NO_ACTIVE_EVIDENCE_MARKER_PATH = f"{ROOT_DIR}/03_COMPLIANCE_EVIDENCE/NO_ACTIVE_EVIDENCE_FOUND.json"
EXPORT_RULES_VERSION = "audit_evidence_pack_rules_2026.04.1"
COMPLIANCE_STATUS_RULES_VERSION = "compliance_status_authority_v1"
RUNTIME_VISIBILITY_RULES_VERSION = "requirement_client_runtime_surface_v1"
GENERATION_ENGINE_VERSION = "compliance_audit_evidence_pack_service_v2"


def _actor_role(role: Optional[str]) -> Optional[UserRole]:
    if not role:
        return None
    try:
        return UserRole(str(role))
    except ValueError:
        return None


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe_filename(name: str, max_len: int = 120) -> str:
    base = re.sub(r"[^A-Za-z0-9._-]+", "-", (name or "").strip()).strip("-._")
    if not base:
        base = "item"
    return base[:max_len]


def _json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True, default=str).encode("utf-8")


def _norm_ts(ts: Any) -> str:
    if ts is None:
        return ""
    if hasattr(ts, "isoformat"):
        return ts.isoformat()
    return str(ts)


def _iso_utc_or_none(value: Any) -> Optional[str]:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        raw = str(value).strip()
        if not raw:
            return None
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(raw)
        except Exception:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat()


def _build_export_identity(*, now_iso: str, pack_id: str, registry_version_used: str) -> Dict[str, str]:
    return {
        "export_id": f"exp_{uuid.uuid4().hex}",
        "export_generated_at": now_iso,
        "export_generation_id": pack_id,
        "export_rules_version": EXPORT_RULES_VERSION,
        "registry_version_used": str(registry_version_used),
    }


def _resolve_document_path_on_disk(client_id: str, doc: Dict[str, Any]) -> Optional[Path]:
    base = Path(resolve_document_storage_path())
    raw = (doc.get("file_path") or "").strip().replace("\\", "/")
    if not raw:
        return None
    p = Path(raw)
    if p.is_file():
        try:
            p.resolve().relative_to(base.resolve())
            return p
        except ValueError:
            pass
    base_name = p.name
    if base_name and client_id:
        cand = (base / client_id / base_name).resolve()
        if cand.is_file():
            try:
                cand.relative_to(base.resolve())
                return cand
            except ValueError:
                pass
    if raw and not p.is_absolute():
        cand2 = (base / raw).resolve()
        if cand2.is_file():
            try:
                cand2.relative_to(base.resolve())
                return cand2
            except ValueError:
                pass
    return None


async def _upload_zip_gridfs(filename: str, data: bytes, metadata: Dict[str, Any]) -> str:
    from motor.motor_asyncio import AsyncIOMotorGridFSBucket

    db = database.get_db()
    fs = AsyncIOMotorGridFSBucket(db, bucket_name=GRIDFS_BUCKET)
    grid_id = await fs.upload_from_stream(filename, io.BytesIO(data), metadata=metadata)
    return str(grid_id)


async def read_audit_pack_zip_bytes(gridfs_id: str) -> Optional[bytes]:
    from motor.motor_asyncio import AsyncIOMotorGridFSBucket

    try:
        db = database.get_db()
        fs = AsyncIOMotorGridFSBucket(db, bucket_name=GRIDFS_BUCKET)
        buf = io.BytesIO()
        await fs.download_to_stream(ObjectId(gridfs_id), buf)
        return buf.getvalue()
    except Exception as e:
        logger.error("read_audit_pack_zip_bytes failed gridfs_id=%s: %s", gridfs_id, e)
        return None


def _obligation_bucket(requirement_type: str) -> str:
    rt = str(requirement_type or "UNKNOWN").strip().upper()
    return _safe_filename(rt.replace(" ", "_"), max_len=40)


def _build_scope_statement_lines(*, generated_at: str, jurisdiction: str) -> List[str]:
    return [
        "Includes governance metadata, compliance evidence files, delivery proof, audit timeline, and exception reporting generated from Compliance Vault Pro records.",
        "Excludes hidden, deprecated, unpublished, and non-runtime-visible obligations from active compliance counts and status outcomes.",
        "Findings reflect records available in-system up to the generation boundary timestamp only; later updates are outside this export scope.",
        f"Jurisdiction assumptions are based on the property profile captured at generation time ({jurisdiction or 'Unknown jurisdiction'}).",
        "Evidence verification remains subject to independent review of source documents, issuing authorities, and external registries where applicable.",
        f"Generation timestamp boundary (UTC): {generated_at}.",
    ]


def _property_address_line(property_doc: Dict[str, Any]) -> str:
    return ", ".join(
        [x for x in [property_doc.get("address_line_1"), property_doc.get("city"), property_doc.get("postcode")] if x]
    )


def _audit_pack_gov_ctx(*, generated_at: str, export_identity: Dict[str, str], jurisdiction: str) -> Any:
    from services.report_layout_governance import GovernancePdfContext
    from services.reporting_semantics_v1 import (
        EXPORT_DETERMINISM_IMMUTABLE_ARTIFACT,
        GRADE_REGULATORY,
        EXPORT_GRADE_DEFINITIONS,
    )

    grade_def = EXPORT_GRADE_DEFINITIONS.get(GRADE_REGULATORY) or {}
    try:
        gen_dt = datetime.fromisoformat(str(generated_at).replace("Z", "+00:00"))
        if gen_dt.tzinfo is None:
            gen_dt = gen_dt.replace(tzinfo=timezone.utc)
    except Exception:
        gen_dt = datetime.now(timezone.utc)
    return GovernancePdfContext(
        export_grade=GRADE_REGULATORY,
        export_grade_label=grade_def.get("label") or "Regulatory / evidential",
        generated_at=gen_dt,
        determinism=EXPORT_DETERMINISM_IMMUTABLE_ARTIFACT,
        jurisdiction_summary=(jurisdiction or "")[:90],
        artifact_id=export_identity.get("export_id") or "",
        report_scope="property",
        immutable_status="frozen",
    )


def _build_pack_overview_pdf_bytes(
    *,
    branding: Dict[str, Any],
    generated_at: str,
    metadata: Dict[str, Any],
    export_identity: Dict[str, str],
    jurisdiction: str,
    property_doc: Optional[Dict[str, Any]] = None,
) -> bytes:
    from services.report_pdf_templates import FormalReportSpec, build_formal_report_pdf

    prop = property_doc or {}
    addr = _property_address_line(prop)
    gov = _audit_pack_gov_ctx(generated_at=generated_at, export_identity=export_identity, jurisdiction=jurisdiction)
    spec = FormalReportSpec(
        report_title="Audit Evidence Pack Overview",
        report_classification="Evidentiary Export",
        report_kind="audit_evidence_pack",
        branding=branding,
        gov_ctx=gov,
        generated_at_iso=generated_at,
        jurisdiction=jurisdiction,
        scope_line=f"<b>Property:</b> {addr or 'Property reference'}",
        export_id=export_identity.get("export_id") or "",
        export_generation_id=export_identity.get("export_generation_id") or "",
        include_matrix=False,
        include_executive_summary=False,
        include_readiness_indicators=False,
        include_action_priorities=False,
        include_exception_summaries=False,
    )
    metrics = [
        ("Export version", str(metadata.get("export_version") or "")),
        ("Evidence pack version", str(metadata.get("evidence_pack_version") or "")),
        ("Export rules version", str(export_identity.get("export_rules_version") or "")),
        ("Registry version used", str(export_identity.get("registry_version_used") or "")),
    ]
    return build_formal_report_pdf(
        spec,
        metrics=metrics,
        posture_lines=[
            f"Governed audit evidence pack for property review. "
            f"Contract version: {metadata.get('contract_version') or CONTRACT_VERSION}.",
        ],
        interpretation=[
            "Governance files (manifest, checksums, generation metadata) in folder 06_GOVERNANCE "
            "retain system provenance regardless of white-label presentation.",
        ],
        scope_lines=_build_scope_statement_lines(generated_at=generated_at, jurisdiction=jurisdiction),
    )


def _build_compliance_summary_pdf_bytes(
    *,
    branding: Dict[str, Any],
    property_doc: Dict[str, Any],
    status_result: Any,
    generated_at: str,
    risk_summary: Dict[str, Any],
    export_identity: Dict[str, str],
    visible_reqs: List[Dict[str, Any]],
    docs_in_pack: List[Dict[str, Any]],
    deliveries: List[Dict[str, Any]],
    client_doc: Dict[str, Any],
) -> bytes:
    from services.report_pdf_templates import (
        FormalReportSpec,
        build_formal_report_pdf,
        build_matrix_rows,
        classify_exceptions,
        compute_readiness_indicators,
        delivery_proof_by_requirement,
        docs_by_requirement,
        group_by_action_priority,
    )

    jurisdiction = str(property_doc.get("effective_jurisdiction_label") or property_doc.get("jurisdiction") or "Unknown")
    addr = _property_address_line(property_doc)
    now = datetime.now(timezone.utc)
    docs_map = docs_by_requirement(docs_in_pack)
    delivery_map = delivery_proof_by_requirement(deliveries)
    matrix_rows = build_matrix_rows(
        requirements=visible_reqs,
        properties=[property_doc],
        client_doc=client_doc,
        docs_by_req=docs_map,
        delivery_by_req=delivery_map,
        now=now,
        property_filter_id=str(property_doc.get("property_id") or ""),
    )
    readiness = compute_readiness_indicators(
        requirements=visible_reqs,
        properties=[property_doc],
        client_doc=client_doc,
        deliveries=deliveries,
        docs_by_req=docs_map,
        now=now,
    )
    exceptions = classify_exceptions(
        requirements=visible_reqs,
        properties=[property_doc],
        client_doc=client_doc,
        docs_by_req=docs_map,
        deliveries=deliveries,
        now=now,
    )
    action_groups = group_by_action_priority(matrix_rows)
    gov = _audit_pack_gov_ctx(generated_at=generated_at, export_identity=export_identity, jurisdiction=jurisdiction)
    spec = FormalReportSpec(
        report_title="Compliance Summary",
        report_classification="Compliance Summary",
        report_kind="compliance_summary",
        branding=branding,
        gov_ctx=gov,
        generated_at_iso=generated_at,
        jurisdiction=jurisdiction,
        scope_line=f"<b>Property:</b> {addr or 'Property reference'}",
        export_id=export_identity.get("export_id") or "",
        export_generation_id=export_identity.get("export_generation_id") or "",
    )
    action_required = (
        status_result.overdue_count > 0
        or status_result.mandatory_missing_or_pending_count > 0
        or status_result.critical_missing_or_pending_count > 0
    )
    if action_required:
        posture = (
            f"Overall compliance status: <b>{status_result.status}</b>. "
            "Mandatory or time-critical obligations require attention within export scope."
        )
    else:
        posture = (
            f"Overall compliance status: <b>{status_result.status}</b>. "
            "No mandatory compliance gaps were detected within the export scope at generation time."
        )
    metrics = [
        ("Total obligations in scope", str(status_result.total_requirements)),
        ("Compliant obligations", str(status_result.compliant_count)),
        ("Overdue obligations", str(status_result.overdue_count)),
        ("Pending obligations", str(status_result.pending_count)),
        ("Mandatory unresolved", str(status_result.mandatory_missing_or_pending_count)),
        ("Critical unresolved", str(status_result.critical_missing_or_pending_count)),
        ("Expiring soon", str(status_result.expiring_soon_count)),
        ("High-risk unresolved", str(risk_summary.get("high_risk_count", 0))),
    ]
    interpretation = [
        "Compliance metrics above reflect runtime-visible obligations at the generation boundary.",
        "The evidence matrix below maps each obligation to evidentiary records and delivery proof.",
        "Evidence remains subject to independent verification of source documents and issuing authorities.",
    ]
    if action_required:
        interpretation.append("Immediate action is recommended for critical or overdue obligations listed in the matrix.")
    else:
        interpretation.append("No immediate mandatory action is indicated from export-scope metrics alone.")
    return build_formal_report_pdf(
        spec,
        posture_lines=[posture],
        metrics=metrics,
        interpretation=interpretation,
        matrix_rows=matrix_rows,
        readiness=readiness,
        exceptions=exceptions,
        action_groups=action_groups,
        scope_lines=_build_scope_statement_lines(generated_at=generated_at, jurisdiction=jurisdiction),
    )


def _build_audit_trail_pdf_bytes(
    *,
    branding: Dict[str, Any],
    generated_at: str,
    export_identity: Dict[str, str],
    jurisdiction: str,
    property_doc: Dict[str, Any],
    timeline_slice: List[Dict[str, Any]],
) -> bytes:
    from services.report_pdf_templates import FormalReportSpec, build_formal_report_pdf

    addr = _property_address_line(property_doc)
    gov = _audit_pack_gov_ctx(generated_at=generated_at, export_identity=export_identity, jurisdiction=jurisdiction)
    spec = FormalReportSpec(
        report_title="Audit Trail",
        report_classification="Regulatory Review",
        report_kind="audit_trail",
        branding=branding,
        gov_ctx=gov,
        generated_at_iso=generated_at,
        jurisdiction=jurisdiction,
        scope_line=f"<b>Property:</b> {addr or 'Property reference'}",
        export_id=export_identity.get("export_id") or "",
        export_generation_id=export_identity.get("export_generation_id") or "",
        include_matrix=False,
        include_executive_summary=False,
        include_readiness_indicators=False,
        include_action_priorities=False,
        include_exception_summaries=False,
        include_audit_trail=True,
    )
    return build_formal_report_pdf(
        spec,
        audit_events=timeline_slice,
        scope_lines=_build_scope_statement_lines(generated_at=generated_at, jurisdiction=jurisdiction),
    )


def _slug_for_filename(raw: str, max_len: int = 48) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "-", (raw or "").strip()).strip("-")
    if not s:
        s = "Unknown"
    return s[:max_len]


def _client_label_for_export_filename(client: Optional[Dict[str, Any]]) -> str:
    if not client:
        return ""
    for key in ("company_name", "trading_name", "business_name", "full_name", "display_name", "name"):
        val = client.get(key)
        if val and str(val).strip():
            return str(val).strip()
    return ""


def _property_label_for_export_filename(property_doc: Dict[str, Any]) -> str:
    """Prefer postal address composite; then nickname; then property_id (never internal debug tokens)."""
    parts = [
        property_doc.get("address_line_1"),
        property_doc.get("address_line_2"),
        property_doc.get("city"),
        property_doc.get("postcode"),
    ]
    addr = ", ".join(str(p).strip() for p in parts if p and str(p).strip())
    if addr:
        return addr
    nick = str(property_doc.get("nickname") or "").strip()
    if nick:
        return nick
    return str(property_doc.get("property_id") or "").strip()


def _slug_audit_pack_segment(raw: str, *, neutral: str, max_len: int = 44) -> str:
    """Sanitize a single filename segment; use neutral label when source text is unusable or UUID-like."""
    s = re.sub(r"[^A-Za-z0-9]+", "-", str(raw or "").strip()).strip("-")
    if not s:
        return neutral
    low = s.lower()
    if low in {"", "unknown", "na", "n-a", "tbd", "tbc", "none"}:
        return neutral
    if re.fullmatch(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", s):
        return neutral
    compact = s.replace("-", "")
    if re.fullmatch(r"[0-9a-fA-F]{24,}", compact):
        return neutral
    return s[:max_len]


async def _build_enterprise_filename(*, db: Any, client_id: str, property_doc: Dict[str, Any], generated_at: datetime) -> str:
    client = await db.clients.find_one(
        {"client_id": client_id},
        {
            "_id": 0,
            "company_name": 1,
            "full_name": 1,
            "trading_name": 1,
            "business_name": 1,
            "display_name": 1,
            "name": 1,
        },
    )
    client_raw = _client_label_for_export_filename(client)
    client_name = _slug_audit_pack_segment(client_raw, neutral="Client", max_len=44)
    property_raw = _property_label_for_export_filename(property_doc)
    property_ref = _slug_audit_pack_segment(property_raw, neutral="Property", max_len=44)
    date_part = generated_at.strftime("%Y-%m-%d")
    base = f"CVP_Audit_Evidence_Pack_{client_name}_{property_ref}_{date_part}"
    base = base[:150]
    candidate = f"{base}.zip"
    suffix = 2
    while await db.compliance_audit_packs.find_one({"filename": candidate}, {"_id": 1}):
        candidate = f"{base}_{suffix}.zip"
        suffix += 1
    return candidate


def _deterministic_sorted(items: Iterable[Dict[str, Any]], keys: Tuple[str, ...]) -> List[Dict[str, Any]]:
    def _k(row: Dict[str, Any]) -> Tuple[Any, ...]:
        return tuple(str(row.get(x) or "") for x in keys)

    return sorted((dict(x) for x in (items or [])), key=_k)


async def build_compliance_audit_pack(
    *,
    client_id: str,
    property_id: str,
    initiated_by_user_id: str,
    initiated_by_role: Optional[str],
    purpose: str = "governed_audit_export",
    ip_address: Optional[str] = None,
) -> Dict[str, Any]:
    db = database.get_db()
    prop = await db.properties.find_one({"property_id": property_id, "client_id": client_id}, {"_id": 0})
    if not prop:
        raise ValueError("property_not_found")

    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    pack_id = f"cap_{uuid.uuid4().hex[:24]}"
    published_meta = await fetch_published_metadata(db) or {}
    registry_version_used = str(published_meta.get("version") or "unknown")
    export_identity = _build_export_identity(now_iso=now_iso, pack_id=pack_id, registry_version_used=registry_version_used)

    all_reqs = await db.requirements.find({"property_id": property_id, "client_id": client_id}, {"_id": 0}).to_list(1000)
    client_doc = await db.clients.find_one({"client_id": client_id}, {"_id": 0}) or {}
    visible_reqs = await filter_requirement_rows_for_client_runtime_surfaces(
        db,
        client_id=client_id,
        requirements=all_reqs,
        client_doc=client_doc,
        properties=[prop],
    )

    excluded_ids = sorted(
        {
            str(r.get("requirement_id"))
            for r in all_reqs
            if r.get("requirement_id")
        }
        - {
            str(r.get("requirement_id"))
            for r in visible_reqs
            if r.get("requirement_id")
        }
    )

    active_reqs: List[Dict[str, Any]] = []
    for r in visible_reqs:
        ea = r.get("evidence_authority") or {}
        if not r.get("evidence_authority_synced_at"):
            continue
        if int(ea.get("version") or 0) < AUTHORITY_VERSION:
            continue
        if authority_state(r) == EA_VERIFIED_CURRENT:
            active_reqs.append(r)
    active_reqs = _deterministic_sorted(active_reqs, ("requirement_type", "requirement_id"))
    active_req_ids = [str(r.get("requirement_id")) for r in active_reqs if r.get("requirement_id")]

    docs_in_pack = await db.documents.find(
        {
            "client_id": client_id,
            "property_id": property_id,
            "requirement_id": {"$in": active_req_ids},
            "status": "VERIFIED",
        },
        {"_id": 0},
    ).to_list(2000)
    docs_in_pack = _deterministic_sorted(docs_in_pack, ("requirement_id", "document_id", "file_name"))

    evidence_in_pack = await db.compliance_evidence_records.find(
        {
            "client_id": client_id,
            "property_id": property_id,
            "requirement_id": {"$in": active_req_ids},
            "included_in_active_compliance": True,
            "archived": {"$ne": True},
        },
        {"_id": 0},
    ).to_list(2000)
    evidence_in_pack = _deterministic_sorted(evidence_in_pack, ("requirement_id", "evidence_record_id"))
    supporting_doc_ids: List[str] = []
    for ev in evidence_in_pack:
        for did in ev.get("linked_document_ids") or []:
            tok = str(did or "").strip()
            if tok:
                supporting_doc_ids.append(tok)
    supporting_doc_ids = sorted(set(supporting_doc_ids))
    supporting_docs_by_id: Dict[str, Dict[str, Any]] = {}
    if supporting_doc_ids:
        supporting_docs = await db.documents.find(
            {
                "client_id": client_id,
                "property_id": property_id,
                "document_id": {"$in": supporting_doc_ids},
            },
            {"_id": 0},
        ).to_list(2000)
        for d in supporting_docs:
            did = str(d.get("document_id") or "")
            if did:
                supporting_docs_by_id[did] = d

    raw_events = await db.audit_logs.find(
        {"client_id": client_id, "$or": [{"resource_id": property_id}, {"metadata.property_id": property_id}]},
        {"_id": 0},
    ).sort("timestamp", -1).limit(1000).to_list(1000)
    timeline_slice: List[Dict[str, Any]] = []
    for ev in raw_events:
        md = ev.get("metadata") or {}
        rid = str(md.get("requirement_id") or "")
        historical_exclusion = bool(rid and rid in excluded_ids)
        timeline_slice.append(
            {
                "action": ev.get("action"),
                "timestamp": _norm_ts(ev.get("timestamp")),
                "actor_role": ev.get("actor_role"),
                "resource_type": ev.get("resource_type"),
                "resource_id": ev.get("resource_id"),
                "metadata": md,
                "excluded_historical_reference": historical_exclusion,
                "exclusion_reason": "requirement_non_runtime_visible_or_hidden" if historical_exclusion else None,
            }
        )
    timeline_slice = _deterministic_sorted(timeline_slice, ("timestamp", "action", "resource_type", "resource_id"))

    deliveries = await db.tenant_delivery_proofs.find(
        {"client_id": client_id, "property_id": property_id},
        {"_id": 0},
    ).sort("created_at", -1).limit(300).to_list(300)
    deliveries = _deterministic_sorted(deliveries, ("created_at", "delivery_id"))

    status_result = classify_compliance_status(active_reqs)

    branding_profile = await resolve_branding(client_id, BrandingContext.CLIENT_DOCUMENT_PDF, asset_path="audit_evidence_pack")
    branding = branding_profile.to_report_dict()

    generation_metadata = {
        **export_identity,
        "generated_at_utc": now_iso,
        "generated_by_user_id": initiated_by_user_id,
        "generated_by_role": initiated_by_role,
        "property_id": property_id,
        "property_reference": prop.get("nickname") or prop.get("address_line_1") or property_id,
        "client_id": client_id,
        "jurisdiction": prop.get("effective_jurisdiction_label") or prop.get("jurisdiction") or None,
        "export_version": EXPORT_VERSION,
        "evidence_pack_version": EVIDENCE_PACK_VERSION,
        "timezone": "UTC",
        "generation_id": pack_id,
        "source_registry_version": str(AUTHORITY_VERSION),
        "registry_version_used": registry_version_used,
        "export_rules_version": EXPORT_RULES_VERSION,
        "compliance_status_rules_version": COMPLIANCE_STATUS_RULES_VERSION,
        "runtime_visibility_rules_version": RUNTIME_VISIBILITY_RULES_VERSION,
        "generation_engine_version": GENERATION_ENGINE_VERSION,
        "contract_version": CONTRACT_VERSION,
        "branding_source": branding_profile.source,
        "branding_company_name": branding_profile.company_name,
        "system_provenance": {
            "platform": "Compliance Vault Pro",
            "operator": "Pleerity Enterprise Ltd",
        },
    }

    risk_summary = {
        "high_risk_count": status_result.critical_missing_or_pending_count,
        "action_required_count": status_result.overdue_count + status_result.mandatory_missing_or_pending_count,
        "mandatory_unresolved_count": status_result.mandatory_missing_or_pending_count,
    }

    overview_pdf = _build_pack_overview_pdf_bytes(
        branding=branding,
        generated_at=now_iso,
        metadata=generation_metadata,
        export_identity=export_identity,
        jurisdiction=str(generation_metadata.get("jurisdiction") or ""),
        property_doc=prop,
    )
    summary_pdf = _build_compliance_summary_pdf_bytes(
        branding=branding,
        property_doc=prop,
        status_result=status_result,
        generated_at=now_iso,
        risk_summary=risk_summary,
        export_identity=export_identity,
        visible_reqs=visible_reqs,
        docs_in_pack=docs_in_pack,
        deliveries=deliveries,
        client_doc=client_doc,
    )
    audit_trail_pdf = _build_audit_trail_pdf_bytes(
        branding=branding,
        generated_at=now_iso,
        export_identity=export_identity,
        jurisdiction=str(generation_metadata.get("jurisdiction") or ""),
        property_doc=prop,
        timeline_slice=timeline_slice,
    )

    property_profile = {
        "property_reference": generation_metadata["property_reference"],
        "address_line_1": prop.get("address_line_1"),
        "address_line_2": prop.get("address_line_2"),
        "city": prop.get("city"),
        "postcode": prop.get("postcode"),
        "jurisdiction": generation_metadata["jurisdiction"],
    }

    exceptions_payload = {
        "missing_obligations": [],
        "pending_requirements": [],
        "excluded_evidence": [],
        "unresolved_items": [],
        "excluded_historical_items": [],
    }
    for r in active_reqs:
        st = str(r.get("status") or "").upper()
        item = {
            "requirement_code": r.get("requirement_code"),
            "requirement_type": r.get("requirement_type"),
            "status": st,
            "reason": "pending_or_missing_runtime_obligation",
        }
        if st in {"PENDING", "MISSING", "MISSING_EVIDENCE"}:
            exceptions_payload["missing_obligations"].append(item)
            exceptions_payload["pending_requirements"].append(item)
            exceptions_payload["unresolved_items"].append(item)
        elif st in {"OVERDUE", "FAILED", "NON_COMPLIANT", "ACTION_REQUIRED"}:
            exceptions_payload["unresolved_items"].append(item)

    for rid in excluded_ids:
        exceptions_payload["excluded_historical_items"].append(
            {
                "requirement_id": rid,
                "reason_for_exclusion": "hidden_deprecated_or_non_runtime_visible",
                "counted_as_active_compliance": False,
            }
        )

    manifest_entries: List[Dict[str, Any]] = []
    file_payloads: Dict[str, bytes] = {
        f"{ROOT_DIR}/00_README/pack_overview.pdf": overview_pdf,
        f"{ROOT_DIR}/01_EXECUTIVE_SUMMARY/compliance_summary.pdf": summary_pdf,
        f"{ROOT_DIR}/02_PROPERTY_PROFILE/property_profile.json": _json_bytes(property_profile),
        f"{ROOT_DIR}/04_DELIVERY_PROOF/tenant_delivery_records.json": _json_bytes(deliveries),
        f"{ROOT_DIR}/05_AUDIT_TIMELINE/audit_timeline.json": _json_bytes(timeline_slice),
        f"{ROOT_DIR}/05_AUDIT_TIMELINE/audit_trail.pdf": audit_trail_pdf,
        f"{ROOT_DIR}/06_GOVERNANCE/generation_metadata.json": _json_bytes(generation_metadata),
        f"{ROOT_DIR}/07_EXCEPTIONS/missing_or_pending_items.json": _json_bytes(exceptions_payload),
    }

    for d in docs_in_pack:
        rid = str(d.get("requirement_id") or "")
        req = next((r for r in active_reqs if str(r.get("requirement_id")) == rid), None)
        bucket = _obligation_bucket((req or {}).get("requirement_type") or d.get("requirement_type") or "UNKNOWN")
        fname = _safe_filename(d.get("file_name") or f"{d.get('document_id')}.bin", max_len=90)
        doc_path = _resolve_document_path_on_disk(client_id, d)
        zpath = f"{ROOT_DIR}/03_COMPLIANCE_EVIDENCE/{bucket}/{fname}"
        if doc_path and doc_path.is_file():
            body = doc_path.read_bytes()
            file_payloads[zpath] = body
        else:
            exceptions_payload["excluded_evidence"].append(
                {
                    "document_id": d.get("document_id"),
                    "requirement_id": rid,
                    "reason_for_exclusion": "verified_document_blob_missing_on_disk",
                    "included_in_active_compliance": False,
                }
            )

    if excluded_ids:
        excluded_docs = await db.documents.find(
            {
                "client_id": client_id,
                "property_id": property_id,
                "requirement_id": {"$in": excluded_ids},
                "status": "VERIFIED",
            },
            {"_id": 0},
        ).to_list(2000)
        excluded_docs = _deterministic_sorted(excluded_docs, ("requirement_id", "document_id", "file_name"))
        for d in excluded_docs:
            exceptions_payload["excluded_evidence"].append(
                {
                    "document_id": d.get("document_id"),
                    "requirement_id": str(d.get("requirement_id") or ""),
                    "reason_for_exclusion": "requirement_hidden_or_non_runtime_visible",
                    "included_in_active_compliance": False,
                }
            )

    for ev in evidence_in_pack:
        rid = str(ev.get("requirement_id") or "")
        req = next((r for r in active_reqs if str(r.get("requirement_id")) == rid), None)
        if not req:
            continue
        bucket = _obligation_bucket((req or {}).get("requirement_type") or "UNKNOWN")
        mode_slug = str(ev.get("evidence_mode") or "evidence").strip().lower()
        fname = _safe_filename(f"{mode_slug}_{ev.get('evidence_record_id')}.json", max_len=120)
        zpath = f"{ROOT_DIR}/03_COMPLIANCE_EVIDENCE/{bucket}/{fname}"
        file_payloads[zpath] = _json_bytes({k: v for k, v in ev.items() if k != "_id"})
        for did in ev.get("linked_document_ids") or []:
            did_tok = str(did or "").strip()
            linked_doc = supporting_docs_by_id.get(did_tok)
            if not linked_doc:
                continue
            doc_path = _resolve_document_path_on_disk(client_id, linked_doc)
            if not (doc_path and doc_path.is_file()):
                continue
            sfname = _safe_filename(linked_doc.get("file_name") or linked_doc.get("filename") or f"{did_tok}.bin", max_len=90)
            spath = f"{ROOT_DIR}/03_COMPLIANCE_EVIDENCE/{bucket}/supporting_{sfname}"
            file_payloads[spath] = doc_path.read_bytes()

    has_exported_compliance_evidence = any(
        p.startswith(f"{ROOT_DIR}/03_COMPLIANCE_EVIDENCE/") and p != NO_ACTIVE_EVIDENCE_MARKER_PATH for p in file_payloads
    )
    if not has_exported_compliance_evidence:
        marker_payload = {
            "message": (
                "No qualifying active evidence files were available at generation time for export under "
                "03_COMPLIANCE_EVIDENCE."
            ),
            "generated_at": now_iso,
            "property_id": property_id,
            "requirements_reviewed_count": len(all_reqs),
            "hidden_and_non_runtime_visible_exclusion": (
                "Evidence tied to hidden, deprecated, or non-runtime-visible obligations is excluded from active "
                "compliance counts and status outcomes in this Audit Evidence Pack."
            ),
        }
        file_payloads[NO_ACTIVE_EVIDENCE_MARKER_PATH] = _json_bytes(marker_payload)

    file_payloads[f"{ROOT_DIR}/07_EXCEPTIONS/missing_or_pending_items.json"] = _json_bytes(exceptions_payload)

    # Build checksums and manifest from deterministic sorted paths.
    sorted_paths = sorted(file_payloads.keys())
    checksum_lines: List[str] = []
    for p in sorted_paths:
        b = file_payloads[p]
        sha = _sha256_bytes(b)
        checksum_lines.append(f"{sha}  {p}")
        manifest_entries.append(
            {
                "filename": p,
                "size": len(b),
                "checksum": sha,
                "sha256": sha,
                "generated_at": now_iso,
            }
        )

    checksums_path = f"{ROOT_DIR}/06_GOVERNANCE/checksums.sha256"
    file_payloads[checksums_path] = ("\n".join(checksum_lines) + "\n").encode("utf-8")
    manifest_entries.append(
        {
            "filename": checksums_path,
            "size": len(file_payloads[checksums_path]),
            "checksum": _sha256_bytes(file_payloads[checksums_path]),
            "generated_at": now_iso,
        }
    )

    manifest_core = {
        **export_identity,
        "pack_id": pack_id,
        "contract_version": CONTRACT_VERSION,
        "generated_at": now_iso,
        "generated_by_user_id": initiated_by_user_id,
        "generated_by_role": initiated_by_role,
        "purpose": purpose,
        "client_id": client_id,
        "property_id": property_id,
        "overall_compliance_status": status_result.status,
        "status_reasons": status_result.reasons,
        "authority_requirement_ids": active_req_ids,
        "excluded_non_runtime_visible_requirement_ids": excluded_ids,
        "files": sorted(manifest_entries, key=lambda x: x["filename"]),
    }

    provenance_by_path: Dict[str, Dict[str, Any]] = {}
    for d in docs_in_pack:
        rid = str(d.get("requirement_id") or "")
        req = next((r for r in active_reqs if str(r.get("requirement_id")) == rid), None)
        bucket = _obligation_bucket((req or {}).get("requirement_type") or d.get("requirement_type") or "UNKNOWN")
        fname = _safe_filename(d.get("file_name") or f"{d.get('document_id')}.bin", max_len=90)
        zpath = f"{ROOT_DIR}/03_COMPLIANCE_EVIDENCE/{bucket}/{fname}"
        provenance_by_path[zpath] = {
            "source_document_id": str(d.get("document_id")) if d.get("document_id") is not None else None,
            "uploaded_by_user_id": d.get("uploaded_by") or d.get("uploaded_by_user_id"),
            "uploaded_at": _iso_utc_or_none(d.get("uploaded_at") or d.get("created_at")),
            "verification_status": d.get("status"),
            "verified_by_user_id": d.get("verified_by") or d.get("verified_by_user_id"),
            "verified_at": _iso_utc_or_none(d.get("verified_at")),
            "evidence_source_type": d.get("source_type") or d.get("document_source_type"),
            "evidence_mode": "DOCUMENT_UPLOAD",
            "evidence_confidence_level": None,
            "included_in_active_compliance": True,
        }
    for ev in evidence_in_pack:
        rid = str(ev.get("requirement_id") or "")
        req = next((r for r in active_reqs if str(r.get("requirement_id")) == rid), None)
        if not req:
            continue
        bucket = _obligation_bucket((req or {}).get("requirement_type") or "UNKNOWN")
        mode_slug = str(ev.get("evidence_mode") or "evidence").strip().lower()
        fname = _safe_filename(f"{mode_slug}_{ev.get('evidence_record_id')}.json", max_len=120)
        zpath = f"{ROOT_DIR}/03_COMPLIANCE_EVIDENCE/{bucket}/{fname}"
        provenance_by_path[zpath] = {
            "source_document_id": None,
            "uploaded_by_user_id": ev.get("created_by_user_id"),
            "uploaded_at": _iso_utc_or_none(ev.get("created_at")),
            "verification_status": ev.get("verification_status"),
            "verified_by_user_id": ev.get("verified_by_user_id"),
            "verified_at": _iso_utc_or_none(ev.get("verified_at")),
            "evidence_source_type": "compliance_evidence_record",
            "evidence_mode": ev.get("evidence_mode"),
            "evidence_confidence_level": ev.get("evidence_confidence_level"),
            "included_in_active_compliance": bool(ev.get("included_in_active_compliance", True)),
        }
        for did in ev.get("linked_document_ids") or []:
            did_tok = str(did or "").strip()
            linked_doc = supporting_docs_by_id.get(did_tok)
            if not linked_doc:
                continue
            sfname = _safe_filename(linked_doc.get("file_name") or linked_doc.get("filename") or f"{did_tok}.bin", max_len=90)
            spath = f"{ROOT_DIR}/03_COMPLIANCE_EVIDENCE/{bucket}/supporting_{sfname}"
            provenance_by_path[spath] = {
                "source_document_id": did_tok,
                "uploaded_by_user_id": linked_doc.get("uploaded_by") or linked_doc.get("uploaded_by_user_id"),
                "uploaded_at": _iso_utc_or_none(linked_doc.get("uploaded_at") or linked_doc.get("created_at")),
                "verification_status": linked_doc.get("status"),
                "verified_by_user_id": linked_doc.get("verified_by") or linked_doc.get("verified_by_user_id"),
                "verified_at": _iso_utc_or_none(linked_doc.get("verified_at")),
                "evidence_source_type": "supporting_evidence_attachment",
                "evidence_mode": ev.get("evidence_mode"),
                "evidence_confidence_level": ev.get("evidence_confidence_level"),
                "included_in_active_compliance": bool(ev.get("included_in_active_compliance", True)),
            }
    if NO_ACTIVE_EVIDENCE_MARKER_PATH in file_payloads:
        provenance_by_path[NO_ACTIVE_EVIDENCE_MARKER_PATH] = {
            "source_document_id": None,
            "uploaded_by_user_id": None,
            "uploaded_at": None,
            "verification_status": None,
            "verified_by_user_id": None,
            "verified_at": None,
            "evidence_source_type": "no_active_evidence_marker",
            "included_in_active_compliance": False,
        }
    for row in manifest_core["files"]:
        entry = dict(row)
        if str(entry.get("filename", "")).startswith(f"{ROOT_DIR}/03_COMPLIANCE_EVIDENCE/"):
            prov = provenance_by_path.get(entry["filename"], {})
            entry.update(
                {
                    "source_document_id": prov.get("source_document_id"),
                    "uploaded_by_user_id": prov.get("uploaded_by_user_id"),
                    "uploaded_at": prov.get("uploaded_at"),
                    "verification_status": prov.get("verification_status"),
                    "verified_by_user_id": prov.get("verified_by_user_id"),
                    "verified_at": prov.get("verified_at"),
                    "evidence_source_type": prov.get("evidence_source_type"),
                    "evidence_mode": prov.get("evidence_mode"),
                    "evidence_confidence_level": prov.get("evidence_confidence_level"),
                    "included_in_active_compliance": bool(prov.get("included_in_active_compliance", False)),
                }
            )
        row.clear()
        row.update(entry)

    manifest_path = f"{ROOT_DIR}/06_GOVERNANCE/manifest.json"
    file_payloads[manifest_path] = _json_bytes(manifest_core)

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for zp in sorted(file_payloads.keys()):
            zf.writestr(zp, file_payloads[zp])

    zip_bytes = zip_buf.getvalue()
    package_sha256 = _sha256_bytes(zip_bytes)
    filename = await _build_enterprise_filename(db=db, client_id=client_id, property_doc=prop, generated_at=now)
    grid_id = await _upload_zip_gridfs(
        filename,
        zip_bytes,
        metadata={
            "pack_id": pack_id,
            **export_identity,
            "client_id": client_id,
            "property_id": property_id,
            "content_type": "application/zip",
            "contract_version": CONTRACT_VERSION,
            "generated_at": now_iso,
        },
    )

    manifest_sha256 = _sha256_bytes(file_payloads[manifest_path])
    mongo_doc = {
        "pack_id": pack_id,
        "export_identity": export_identity,
        "contract_version": CONTRACT_VERSION,
        "client_id": client_id,
        "property_id": property_id,
        "generated_at": now_iso,
        "initiated_by_user_id": initiated_by_user_id,
        "initiated_by_role": initiated_by_role,
        "purpose": purpose,
        "gridfs_id": grid_id,
        "filename": filename,
        "byte_size": len(zip_bytes),
        "package_sha256": package_sha256,
        "manifest_sha256": manifest_sha256,
        "manifest": manifest_core,
        "generation_metadata": generation_metadata,
        "timeline_event_count": len(timeline_slice),
        "delivery_proof_count": len(deliveries),
        "overall_compliance_status": status_result.status,
    }
    await db.compliance_audit_packs.insert_one(mongo_doc)

    audit_id = await create_audit_log(
        action=AuditAction.COMPLIANCE_AUDIT_PACK_GENERATED,
        actor_role=_actor_role(initiated_by_role),
        actor_id=initiated_by_user_id,
        client_id=client_id,
        resource_type="compliance_audit_pack",
        resource_id=pack_id,
        metadata={
            "property_id": property_id,
            "package_sha256": package_sha256,
            "manifest_sha256": manifest_sha256,
            "gridfs_id": grid_id,
            "byte_size": len(zip_bytes),
            "overall_compliance_status": status_result.status,
        },
        ip_address=ip_address,
    )

    return {
        "pack_id": pack_id,
        "generated_at": now_iso,
        "package_sha256": package_sha256,
        "manifest_sha256": manifest_sha256,
        "gridfs_id": grid_id,
        "byte_size": len(zip_bytes),
        "filename": filename,
        "audit_log_id": audit_id,
        "timeline_event_count": len(timeline_slice),
        "delivery_proof_count": len(deliveries),
        "included_certificate_paths": sorted(
            [p for p in file_payloads.keys() if p.startswith(f"{ROOT_DIR}/03_COMPLIANCE_EVIDENCE/")]
        ),
        "overall_compliance_status": status_result.status,
    }


async def get_audit_pack_record(*, client_id: str, pack_id: str) -> Optional[Dict[str, Any]]:
    db = database.get_db()
    row = await db.compliance_audit_packs.find_one({"pack_id": pack_id, "client_id": client_id}, {"_id": 0})
    return row


async def list_audit_packs_for_scope(*, client_id: str, property_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    db = database.get_db()
    q: Dict[str, Any] = {"client_id": client_id}
    if property_id:
        q["property_id"] = property_id
    cur = db.compliance_audit_packs.find(q, {"_id": 0}).sort("generated_at", -1).limit(limit)
    return await cur.to_list(length=limit)

