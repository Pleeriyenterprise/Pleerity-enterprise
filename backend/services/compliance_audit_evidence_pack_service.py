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
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from database import database
from models import AuditAction, UserRole
from services.branding_resolver_service import BrandingContext, resolve_branding
from services.compliance_status_authority import classify_compliance_status
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


def _build_scope_statement_lines() -> List[str]:
    return [
        "This Audit Evidence Pack contains governance evidence generated from Compliance Vault Pro records at generation time.",
        "Included evidence is limited to published authoritative obligations visible to current runtime client surfaces.",
        "Excluded, hidden, deprecated, or non-runtime-visible obligations are not treated as active compliance obligations.",
        "Uploaded files and provider delivery telemetry may require independent verification for legal/regulatory proceedings.",
        "Compliance outcomes depend on source data accuracy, document validity, and authoritative registry alignment.",
    ]


def _build_pack_overview_pdf_bytes(*, branding: Dict[str, Any], generated_at: str, metadata: Dict[str, Any]) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=20 * mm, bottomMargin=20 * mm, leftMargin=18 * mm, rightMargin=18 * mm)
    styles = getSampleStyleSheet()
    title = ParagraphStyle("t", parent=styles["Title"], fontSize=20, textColor=colors.HexColor(branding.get("primary_color", "#0B1D3A")))
    body = ParagraphStyle("b", parent=styles["BodyText"], fontSize=10, leading=14)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=13, textColor=colors.HexColor(branding.get("primary_color", "#0B1D3A")))
    st = []
    st.append(Paragraph("Audit Evidence Pack Overview", title))
    st.append(Paragraph(f"Generated at (UTC): {generated_at}", body))
    st.append(Paragraph(f"Export version: {metadata.get('export_version')} • Evidence pack version: {metadata.get('evidence_pack_version')}", body))
    st.append(Spacer(1, 5 * mm))
    st.append(Paragraph("Scope and Limitations", h2))
    for ln in _build_scope_statement_lines():
        st.append(Paragraph(f"- {ln}", body))
    st.append(Spacer(1, 4 * mm))
    st.append(Paragraph("Branding and Provenance", h2))
    st.append(Paragraph(
        f"Document brand: {branding.get('brand_company_name') or branding.get('company_name')}. "
        "System provenance metadata is retained in governance files regardless of white-label presentation.",
        body,
    ))
    doc.build(st)
    return buf.getvalue()


def _build_compliance_summary_pdf_bytes(
    *,
    branding: Dict[str, Any],
    property_doc: Dict[str, Any],
    status_result: Any,
    generated_at: str,
    risk_summary: Dict[str, Any],
) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=18 * mm, bottomMargin=16 * mm, leftMargin=16 * mm, rightMargin=16 * mm)
    styles = getSampleStyleSheet()
    c_primary = colors.HexColor(branding.get("primary_color", "#0B1D3A"))
    body = ParagraphStyle("body", parent=styles["BodyText"], fontSize=10, leading=14)
    heading = ParagraphStyle("heading", parent=styles["Heading2"], textColor=c_primary, fontSize=13)
    title = ParagraphStyle("title", parent=styles["Title"], textColor=c_primary, fontSize=20)
    st: List[Any] = []

    addr = ", ".join([x for x in [property_doc.get("address_line_1"), property_doc.get("city"), property_doc.get("postcode")] if x])
    jurisdiction = str(property_doc.get("effective_jurisdiction_label") or property_doc.get("jurisdiction") or "Unknown")
    st.append(Paragraph("Compliance Summary", title))
    st.append(Paragraph(f"Property: {addr or 'Property reference unavailable'}", body))
    st.append(Paragraph(f"Jurisdiction: {jurisdiction}", body))
    st.append(Paragraph(f"Generated at (UTC): {generated_at}", body))
    st.append(Spacer(1, 3 * mm))
    st.append(Paragraph(f"Overall Compliance Status: <b>{status_result.status}</b>", body))
    st.append(Spacer(1, 4 * mm))

    table_data = [
        ["Metric", "Value"],
        ["Total obligations in scope", str(status_result.total_requirements)],
        ["Compliant obligations", str(status_result.compliant_count)],
        ["Overdue obligations", str(status_result.overdue_count)],
        ["Pending obligations", str(status_result.pending_count)],
        ["Mandatory unresolved", str(status_result.mandatory_missing_or_pending_count)],
        ["Critical unresolved", str(status_result.critical_missing_or_pending_count)],
        ["Expiring soon", str(status_result.expiring_soon_count)],
    ]
    t = Table(table_data, colWidths=[100 * mm, 55 * mm])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), c_primary),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#D1D5DB")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ALIGN", (1, 1), (1, -1), "RIGHT"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    st.append(t)
    st.append(Spacer(1, 4 * mm))
    st.append(Paragraph("Risk Summary", heading))
    st.append(Paragraph(f"- High-risk unresolved obligations: {risk_summary.get('high_risk_count', 0)}", body))
    st.append(Paragraph(f"- Action-required obligations: {risk_summary.get('action_required_count', 0)}", body))
    st.append(Paragraph(f"- Mandatory obligations unresolved: {risk_summary.get('mandatory_unresolved_count', 0)}", body))
    st.append(Spacer(1, 3 * mm))
    st.append(Paragraph("Evidence Scope Statement", heading))
    for ln in _build_scope_statement_lines():
        st.append(Paragraph(f"- {ln}", body))
    st.append(Spacer(1, 4 * mm))
    st.append(Paragraph("Footer", heading))
    st.append(Paragraph(
        f"{branding.get('pdf_footer_generated_by', 'Generated by Pleerity Enterprise Ltd')} • "
        f"{branding.get('pdf_footer_contact_line', 'pleerityenterprise.co.uk')}",
        body,
    ))
    doc.build(st)
    return buf.getvalue()


def _slug_for_filename(raw: str, max_len: int = 48) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "-", (raw or "").strip()).strip("-")
    if not s:
        s = "Unknown"
    return s[:max_len]


async def _build_enterprise_filename(*, db: Any, client_id: str, property_doc: Dict[str, Any], generated_at: datetime) -> str:
    client = await db.clients.find_one({"client_id": client_id}, {"_id": 0, "company_name": 1, "full_name": 1})
    client_name = _slug_for_filename((client or {}).get("company_name") or (client or {}).get("full_name") or client_id, max_len=44)
    property_ref_raw = property_doc.get("nickname") or property_doc.get("address_line_1") or property_doc.get("property_id") or "Property"
    property_ref = _slug_for_filename(str(property_ref_raw), max_len=44)
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

    overview_pdf = _build_pack_overview_pdf_bytes(branding=branding, generated_at=now_iso, metadata=generation_metadata)
    summary_pdf = _build_compliance_summary_pdf_bytes(
        branding=branding,
        property_doc=prop,
        status_result=status_result,
        generated_at=now_iso,
        risk_summary=risk_summary,
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
                }
            )

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

