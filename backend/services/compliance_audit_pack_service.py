"""
Single governed Compliance Vault Pro audit pack (ZIP + manifest + checksums + GridFS).

Assembles only **authority-synced** requirement evidence in ``VERIFIED_CURRENT`` with ``VERIFIED`` documents,
plus compliance summary PDF, audit timeline slice, and tenant delivery proof index.
"""
from __future__ import annotations

import hashlib
import io
import json
import logging
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from bson import ObjectId
from database import database
from models import AuditAction, UserRole
from utils.audit import create_audit_log
from utils.storage_paths import resolve_document_storage_path

from services.compliance_pack import compliance_pack_service
from services.requirement_evidence_authority import (
    AUTHORITY_VERSION,
    EA_VERIFIED_CURRENT,
    authority_state,
)
from services.requirement_client_runtime_surface import filter_requirement_rows_for_client_runtime_surfaces

logger = logging.getLogger(__name__)

GRIDFS_BUCKET = "compliance_audit_packs"
CONTRACT_VERSION = "cvp_audit_pack_v1"


def _actor_role(role: Optional[str]) -> Optional[UserRole]:
    if not role:
        return None
    try:
        return UserRole(str(role))
    except ValueError:
        return None


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe_filename(name: str) -> str:
    s = "".join(c if c.isalnum() or c in "._-" else "_" for c in (name or "file"))[:120]
    return s or "file"


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


async def build_compliance_audit_pack(
    *,
    client_id: str,
    property_id: str,
    initiated_by_user_id: str,
    initiated_by_role: Optional[str],
    purpose: str = "governed_audit_export",
    ip_address: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Build ZIP, persist manifest + checksums + GridFS blob; audit COMPLIANCE_AUDIT_PACK_GENERATED.
    Returns summary suitable for API JSON (no raw bytes).
    """
    db = database.get_db()
    prop = await db.properties.find_one({"property_id": property_id, "client_id": client_id}, {"_id": 0})
    if not prop:
        raise ValueError("property_not_found")

    client_full = await db.clients.find_one({"client_id": client_id}, {"_id": 0}) or {}
    req_filter = {"property_id": property_id, "client_id": client_id}
    requirements = await db.requirements.find(req_filter, {"_id": 0}).to_list(500)
    requirements = await filter_requirement_rows_for_client_runtime_surfaces(
        db,
        client_id=client_id,
        requirements=requirements,
        client_doc=client_full,
        properties=[prop],
    )

    authority_req_ids: List[str] = []
    truth_notes: Dict[str, Any] = {
        "authority_version": AUTHORITY_VERSION,
        "included_requirements_rule": "evidence_authority_synced AND state==VERIFIED_CURRENT",
        "document_rule": "status==VERIFIED AND requirement_id in included set",
    }
    for r in requirements:
        ea = r.get("evidence_authority") or {}
        if not r.get("evidence_authority_synced_at"):
            continue
        if int(ea.get("version") or 0) < AUTHORITY_VERSION:
            continue
        if authority_state(r) == EA_VERIFIED_CURRENT:
            rid = r.get("requirement_id")
            if rid:
                authority_req_ids.append(str(rid))

    docs_in_pack: List[Dict[str, Any]] = []
    if authority_req_ids:
        doc_cursor = await db.documents.find(
            {
                "client_id": client_id,
                "property_id": property_id,
                "requirement_id": {"$in": authority_req_ids},
                "status": "VERIFIED",
            },
            {"_id": 0},
        ).to_list(500)
        docs_in_pack = list(doc_cursor)

    pdf_bytes = await compliance_pack_service.generate_compliance_pack(
        property_id=property_id,
        client_id=client_id,
        include_expired=False,
        requested_by=initiated_by_user_id,
        requested_by_role=initiated_by_role,
    )

    timeline_query = {
        "client_id": client_id,
        "$or": [
            {"resource_id": property_id},
            {"metadata.property_id": property_id},
        ],
    }
    raw_events = await db.audit_logs.find(timeline_query, {"_id": 0}).sort("timestamp", -1).limit(500).to_list(500)

    def _norm_ts(ts: Any) -> str:
        if ts is None:
            return ""
        if hasattr(ts, "isoformat"):
            return ts.isoformat()
        return str(ts)

    timeline_slice = []
    for ev in raw_events:
        timeline_slice.append(
            {
                "action": ev.get("action"),
                "timestamp": _norm_ts(ev.get("timestamp")),
                "actor_id": ev.get("actor_id"),
                "actor_role": ev.get("actor_role"),
                "resource_type": ev.get("resource_type"),
                "resource_id": ev.get("resource_id"),
                "metadata": ev.get("metadata"),
            }
        )

    deliveries = await db.tenant_delivery_proofs.find(
        {"client_id": client_id, "property_id": property_id},
        {"_id": 0},
    ).sort("created_at", -1).limit(100).to_list(100)

    pack_id = f"cap_{uuid.uuid4().hex[:24]}"
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()

    file_entries: List[Dict[str, Any]] = []
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("report/compliance_summary.pdf", pdf_bytes)
        file_entries.append(
            {
                "path": "report/compliance_summary.pdf",
                "sha256": _sha256_bytes(pdf_bytes),
                "bytes": len(pdf_bytes),
                "role": "compliance_summary_pdf",
            }
        )

        for d in docs_in_pack:
            doc_id = str(d.get("document_id") or "")
            fn = _safe_filename(d.get("file_name") or "certificate.pdf")
            zp = f"certificates/{doc_id}_{fn}"
            path = _resolve_document_path_on_disk(client_id, d)
            if path and path.is_file():
                body = path.read_bytes()
                zf.writestr(zp, body)
                file_entries.append(
                    {
                        "path": zp,
                        "sha256": _sha256_bytes(body),
                        "bytes": len(body),
                        "role": "verified_certificate",
                        "document_id": doc_id,
                        "requirement_id": d.get("requirement_id"),
                    }
                )
            else:
                file_entries.append(
                    {
                        "path": zp,
                        "sha256": None,
                        "bytes": 0,
                        "role": "verified_certificate_missing_blob",
                        "document_id": doc_id,
                        "requirement_id": d.get("requirement_id"),
                    }
                )

        tl_json = json.dumps(timeline_slice, indent=2, default=str).encode("utf-8")
        zf.writestr("timeline/audit_timeline.json", tl_json)
        file_entries.append(
            {"path": "timeline/audit_timeline.json", "sha256": _sha256_bytes(tl_json), "bytes": len(tl_json), "role": "audit_timeline"}
        )

        del_json = json.dumps(deliveries, indent=2, default=str).encode("utf-8")
        zf.writestr("delivery/tenant_delivery_proofs.json", del_json)
        file_entries.append(
            {
                "path": "delivery/tenant_delivery_proofs.json",
                "sha256": _sha256_bytes(del_json),
                "bytes": len(del_json),
                "role": "tenant_delivery_proofs",
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
            "included_documents": [
                {
                    "path": fe["path"],
                    "sha256": fe["sha256"],
                    "document_id": fe.get("document_id"),
                    "requirement_id": fe.get("requirement_id"),
                    "on_disk": fe.get("role") == "verified_certificate",
                }
                for fe in file_entries
                if fe.get("role") in ("verified_certificate", "verified_certificate_missing_blob")
            ],
            "included_audit_slice": {
                "query": timeline_query,
                "event_count": len(timeline_slice),
            },
            "included_delivery_proof_summary": {
                "record_count": len(deliveries),
                "delivery_ids": [x.get("delivery_id") for x in deliveries if x.get("delivery_id")],
            },
            "authority_requirement_ids": authority_req_ids,
            "file_checksums": [{"path": x["path"], "sha256": x["sha256"], "bytes": x["bytes"]} for x in file_entries],
            "truth_snapshot_notes": truth_notes,
        }
        man_bytes = json.dumps(manifest_core, indent=2, sort_keys=True).encode("utf-8")
        zf.writestr("manifest.json", man_bytes)
        manifest_sha = _sha256_bytes(man_bytes)
        file_entries.append(
            {"path": "manifest.json", "sha256": manifest_sha, "bytes": len(man_bytes), "role": "manifest"}
        )

    zip_bytes = zip_buf.getvalue()
    package_sha256 = _sha256_bytes(zip_bytes)
    fname = f"{pack_id}.zip"
    grid_id = await _upload_zip_gridfs(
        fname,
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
        "filename": fname,
        "byte_size": len(zip_bytes),
        "package_sha256": package_sha256,
        "manifest_sha256": manifest_sha,
        "manifest": manifest_core,
        "included_file_checksums": [{"path": x["path"], "sha256": x["sha256"], "bytes": x["bytes"]} for x in file_entries],
        "timeline_event_count": len(timeline_slice),
        "delivery_proof_count": len(deliveries),
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
            "manifest_sha256": manifest_sha,
            "gridfs_id": grid_id,
            "byte_size": len(zip_bytes),
        },
        ip_address=ip_address,
    )

    return {
        "pack_id": pack_id,
        "generated_at": now_iso,
        "package_sha256": package_sha256,
        "manifest_sha256": manifest_sha,
        "gridfs_id": grid_id,
        "byte_size": len(zip_bytes),
        "filename": fname,
        "audit_log_id": audit_id,
        "timeline_event_count": len(timeline_slice),
        "delivery_proof_count": len(deliveries),
        "included_certificate_paths": [x["path"] for x in file_entries if x.get("role") == "verified_certificate"],
    }


async def get_audit_pack_record(*, client_id: str, pack_id: str) -> Optional[Dict[str, Any]]:
    db = database.get_db()
    row = await db.compliance_audit_packs.find_one(
        {"pack_id": pack_id, "client_id": client_id},
        {"_id": 0},
    )
    return row


async def list_audit_packs_for_scope(*, client_id: str, property_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    db = database.get_db()
    q: Dict[str, Any] = {"client_id": client_id}
    if property_id:
        q["property_id"] = property_id
    cur = db.compliance_audit_packs.find(q, {"_id": 0}).sort("generated_at", -1).limit(limit)
    return await cur.to_list(length=limit)
