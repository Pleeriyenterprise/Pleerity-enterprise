"""
REPORTING-IMMUTABLE-ARTIFACT-GOVERNANCE-PHASE-03 — frozen PDF artifact storage and lineage.

Governed ReportLab PDFs (evidence readiness, professional compliance summary) are stored in GridFS
on first generation. Re-download serves identical bytes; explicit regeneration creates a new artifact.
"""
from __future__ import annotations

import hashlib
import io
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from bson import ObjectId

from database import database
from presentation.jurisdiction_reporting import portfolio_jurisdiction_summary_sentence
from services.reporting_semantics_v1 import (
    EXPORT_DETERMINISM_IMMUTABLE_ARTIFACT,
    EXPORT_GRADE_DEFINITIONS,
    GRADE_AUDIT_ARTIFACT,
    GRADE_REGULATORY,
    IMMUTABLE_ARTIFACT_DISCLOSURE,
    PDF_ENGINE_REPORTLAB,
    REPORTING_SEMANTICS_VERSION,
)
from services.scoring_semantics_v1 import SCORING_SEMANTICS_VERSION

logger = logging.getLogger(__name__)

GRIDFS_BUCKET = "governed_report_pdf_artifacts"
COLLECTION = "governed_report_pdf_artifacts"
GENERATION_ENGINE = PDF_ENGINE_REPORTLAB
IMMUTABLE_STATUS_FROZEN = "frozen"

IMMUTABLE_SCOPE: Dict[str, Dict[str, str]] = {
    "audit_evidence_pack": {
        "export_grade": GRADE_AUDIT_ARTIFACT,
        "determinism": EXPORT_DETERMINISM_IMMUTABLE_ARTIFACT,
        "storage": "compliance_audit_packs + compliance_audit_packs GridFS bucket",
    },
    "evidence_readiness": {
        "export_grade": GRADE_AUDIT_ARTIFACT,
        "determinism": EXPORT_DETERMINISM_IMMUTABLE_ARTIFACT,
    },
    "professional_compliance": {
        "export_grade": GRADE_REGULATORY,
        "determinism": EXPORT_DETERMINISM_IMMUTABLE_ARTIFACT,
    },
}


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def compute_snapshot_context_hash(
    *,
    client_id: str,
    report_type: str,
    scope: str,
    property_id: Optional[str],
    report_data: Optional[Dict[str, Any]] = None,
) -> str:
    """Deterministic hash of generation context (not PDF bytes)."""
    props = (report_data or {}).get("properties") or []
    reqs = (report_data or {}).get("requirements") or []
    payload = {
        "client_id": client_id,
        "report_type": report_type,
        "scope": scope,
        "property_id": property_id,
        "properties_count": len(props),
        "requirements_count": len(reqs),
        "semantics_version": REPORTING_SEMANTICS_VERSION,
        "scoring_semantics_version": SCORING_SEMANTICS_VERSION,
        "now_iso": (report_data or {}).get("now_iso"),
    }
    raw = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return _sha256_bytes(raw)


def _evidence_identifiers_summary(report_data: Optional[Dict[str, Any]], *, limit: int = 200) -> List[str]:
    out: List[str] = []
    for r in (report_data or {}).get("requirements") or []:
        rid = r.get("requirement_id")
        doc = r.get("evidence_doc_id") or r.get("document_id")
        if rid:
            out.append(f"{rid}:{doc or ''}")
        if len(out) >= limit:
            break
    return out


def build_lineage_metadata(
    *,
    artifact_id: str,
    client_id: str,
    report_type: str,
    scope: str,
    property_id: Optional[str],
    export_grade: str,
    original_generated_at: datetime,
    snapshot_context_hash: str,
    content_sha256: str,
    jurisdiction_scope: str,
    generation_metadata: Optional[Dict[str, Any]] = None,
    superseded_artifact_id: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "artifact_id": artifact_id,
        "artifact_version_id": artifact_id,
        "client_id": client_id,
        "report_type": report_type,
        "report_scope": scope,
        "property_id": property_id,
        "original_generated_at": _iso(original_generated_at),
        "regenerated_at": None,
        "source_snapshot_hash": snapshot_context_hash,
        "content_sha256": content_sha256,
        "export_grade": export_grade,
        "export_grade_label": (EXPORT_GRADE_DEFINITIONS.get(export_grade) or {}).get("label", export_grade),
        "semantics_version": REPORTING_SEMANTICS_VERSION,
        "scoring_semantics_version": SCORING_SEMANTICS_VERSION,
        "generation_engine": GENERATION_ENGINE,
        "jurisdiction_scope": (jurisdiction_scope or "")[:500],
        "determinism": EXPORT_DETERMINISM_IMMUTABLE_ARTIFACT,
        "immutable_status": IMMUTABLE_STATUS_FROZEN,
        "generation_metadata": generation_metadata or {},
        "superseded_artifact_id": superseded_artifact_id,
    }


def lineage_for_pdf_embed(lineage: Dict[str, Any]) -> Dict[str, Any]:
    """Subset passed into PDF builders via report_data['artifact_lineage']."""
    return {
        "artifact_id": lineage.get("artifact_id"),
        "export_grade": lineage.get("export_grade"),
        "export_grade_label": lineage.get("export_grade_label"),
        "semantics_version": lineage.get("semantics_version"),
        "original_generated_at": lineage.get("original_generated_at"),
        "source_snapshot_hash": lineage.get("source_snapshot_hash"),
        "immutable_status": lineage.get("immutable_status"),
        "report_scope": lineage.get("report_scope"),
        "jurisdiction_scope": lineage.get("jurisdiction_scope"),
        "determinism": EXPORT_DETERMINISM_IMMUTABLE_ARTIFACT,
    }


async def _upload_pdf_gridfs(filename: str, data: bytes, metadata: Dict[str, Any]) -> str:
    from motor.motor_asyncio import AsyncIOMotorGridFSBucket

    db = database.get_db()
    fs = AsyncIOMotorGridFSBucket(db, bucket_name=GRIDFS_BUCKET)
    grid_id = await fs.upload_from_stream(filename, io.BytesIO(data), metadata=metadata)
    return str(grid_id)


async def read_pdf_artifact_bytes(gridfs_id: str) -> Optional[bytes]:
    if not gridfs_id:
        return None
    try:
        from motor.motor_asyncio import AsyncIOMotorGridFSBucket

        db = database.get_db()
        fs = AsyncIOMotorGridFSBucket(db, bucket_name=GRIDFS_BUCKET)
        stream = io.BytesIO()
        await fs.download_to_stream(ObjectId(gridfs_id), stream)
        return stream.getvalue()
    except Exception as e:
        logger.error("read_pdf_artifact_bytes failed gridfs_id=%s: %s", gridfs_id, e)
        return None


async def get_artifact_for_client(*, client_id: str, artifact_id: str) -> Optional[Dict[str, Any]]:
    db = database.get_db()
    return await db[COLLECTION].find_one(
        {"artifact_id": artifact_id, "client_id": client_id},
        {"_id": 0},
    )


def prepare_artifact_identity(
    *,
    client_id: str,
    report_type: str,
    scope: str,
    property_id: Optional[str] = None,
    report_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Pre-assign artifact id + lineage fields for PDF embedding before bytes exist."""
    scope_cfg = IMMUTABLE_SCOPE.get(report_type) or IMMUTABLE_SCOPE["evidence_readiness"]
    artifact_id = f"rpt_{uuid.uuid4().hex}"
    client_doc = (report_data or {}).get("client") or {}
    properties = (report_data or {}).get("properties") or []
    jurisdiction_scope = portfolio_jurisdiction_summary_sentence(client_doc, properties)
    snapshot_hash = compute_snapshot_context_hash(
        client_id=client_id,
        report_type=report_type,
        scope=scope,
        property_id=property_id,
        report_data=report_data,
    )
    now = _utc_now()
    lineage = build_lineage_metadata(
        artifact_id=artifact_id,
        client_id=client_id,
        report_type=report_type,
        scope=scope,
        property_id=property_id,
        export_grade=scope_cfg["export_grade"],
        original_generated_at=now,
        snapshot_context_hash=snapshot_hash,
        content_sha256="",
        jurisdiction_scope=jurisdiction_scope,
    )
    return lineage_for_pdf_embed(lineage)


async def store_pdf_artifact(
    *,
    client_id: str,
    report_type: str,
    pdf_bytes: bytes,
    filename: str,
    scope: str,
    property_id: Optional[str] = None,
    report_data: Optional[Dict[str, Any]] = None,
    reports_mongo_id: Optional[str] = None,
    superseded_artifact_id: Optional[str] = None,
    extra_metadata: Optional[Dict[str, Any]] = None,
    preset_artifact_id: Optional[str] = None,
    preset_lineage: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Persist immutable PDF bytes (no overwrite). Returns lineage + storage ids.
    """
    scope_cfg = IMMUTABLE_SCOPE.get(report_type) or IMMUTABLE_SCOPE["evidence_readiness"]
    export_grade = scope_cfg["export_grade"]
    now = _utc_now()
    artifact_id = preset_artifact_id or f"rpt_{uuid.uuid4().hex}"
    content_sha256 = _sha256_bytes(pdf_bytes)
    client_doc = (report_data or {}).get("client") or {}
    properties = (report_data or {}).get("properties") or []
    jurisdiction_scope = portfolio_jurisdiction_summary_sentence(client_doc, properties)
    snapshot_hash = compute_snapshot_context_hash(
        client_id=client_id,
        report_type=report_type,
        scope=scope,
        property_id=property_id,
        report_data=report_data,
    )
    generation_metadata = {
        "byte_size": len(pdf_bytes),
        "properties_count": len(properties),
        "requirements_count": len((report_data or {}).get("requirements") or []),
        "evidence_identifiers_sample": _evidence_identifiers_summary(report_data),
        **(extra_metadata or {}),
    }
    if preset_lineage and preset_lineage.get("original_generated_at"):
        try:
            og = datetime.fromisoformat(str(preset_lineage["original_generated_at"]).replace("Z", "+00:00"))
            if og.tzinfo is None:
                og = og.replace(tzinfo=timezone.utc)
            now = og
        except Exception:
            pass
    lineage = build_lineage_metadata(
        artifact_id=artifact_id,
        client_id=client_id,
        report_type=report_type,
        scope=scope,
        property_id=property_id,
        export_grade=preset_lineage.get("export_grade") if preset_lineage else export_grade,
        original_generated_at=now,
        snapshot_context_hash=preset_lineage.get("source_snapshot_hash") if preset_lineage else snapshot_hash,
        content_sha256=content_sha256,
        jurisdiction_scope=preset_lineage.get("jurisdiction_scope") if preset_lineage else jurisdiction_scope,
        generation_metadata=generation_metadata,
        superseded_artifact_id=superseded_artifact_id,
    )
    gridfs_id = await _upload_pdf_gridfs(
        filename,
        pdf_bytes,
        metadata={
            "artifact_id": artifact_id,
            "client_id": client_id,
            "report_type": report_type,
            "content_sha256": content_sha256,
            "export_grade": export_grade,
        },
    )
    mongo_doc = {
        **lineage,
        "gridfs_id": gridfs_id,
        "filename": filename,
        "byte_size": len(pdf_bytes),
        "reports_mongo_id": reports_mongo_id,
        "created_at": _iso(now),
    }
    db = database.get_db()
    await db[COLLECTION].insert_one(mongo_doc)
    return {**lineage, "gridfs_id": gridfs_id, "filename": filename, "byte_size": len(pdf_bytes)}


def artifact_http_headers(lineage: Dict[str, Any], *, filename: str) -> Dict[str, str]:
    aid = lineage.get("artifact_id") or ""
    grade = lineage.get("export_grade") or ""
    return {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "X-Report-Determinism": EXPORT_DETERMINISM_IMMUTABLE_ARTIFACT,
        "X-Report-Disclosure": IMMUTABLE_ARTIFACT_DISCLOSURE[:200],
        "X-Artifact-Id": aid,
        "X-Export-Grade": grade,
        "X-Export-Grade-Label": str(lineage.get("export_grade_label") or grade),
        "X-Report-Engine": GENERATION_ENGINE,
        "X-Content-SHA256": str(lineage.get("content_sha256") or ""),
        "X-Immutable-Status": IMMUTABLE_STATUS_FROZEN,
    }


async def serve_artifact_pdf(*, client_id: str, artifact_id: str) -> Optional[tuple]:
    """Returns (bytes, headers_dict, lineage) or None if not found / wrong tenant."""
    rec = await get_artifact_for_client(client_id=client_id, artifact_id=artifact_id)
    if not rec or not rec.get("gridfs_id"):
        return None
    data = await read_pdf_artifact_bytes(str(rec["gridfs_id"]))
    if not data:
        return None
    expected = rec.get("content_sha256")
    if expected and _sha256_bytes(data) != expected:
        logger.error("artifact checksum mismatch artifact_id=%s", artifact_id)
        return None
    fname = rec.get("filename") or f"report_{artifact_id}.pdf"
    return data, artifact_http_headers(rec, filename=fname), rec


async def link_reports_row_immutable(
    *,
    reports_mongo_id: str,
    client_id: str,
    artifact_id: str,
    gridfs_id: str,
    content_sha256: str,
    lineage: Dict[str, Any],
) -> None:
    from bson import ObjectId

    db = database.get_db()
    await db.reports.update_one(
        {"_id": ObjectId(reports_mongo_id), "client_id": client_id},
        {
            "$set": {
                "artifact_id": artifact_id,
                "gridfs_id": gridfs_id,
                "content_sha256": content_sha256,
                "immutable": True,
                "determinism": EXPORT_DETERMINISM_IMMUTABLE_ARTIFACT,
                "export_grade": lineage.get("export_grade"),
                "lineage": {
                    k: lineage.get(k)
                    for k in (
                        "artifact_id",
                        "original_generated_at",
                        "source_snapshot_hash",
                        "export_grade",
                        "semantics_version",
                        "jurisdiction_scope",
                    )
                },
            }
        },
    )
