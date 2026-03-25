"""
Compliance evidence pack: ZIP with CSV manifests + JSON index (GridFS).

Tier-gated by plan_registry `audit_log_export`. Idempotent per (client_id, scope hash).
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import logging
import uuid
import zipfile
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

from bson import ObjectId
from database import database

logger = logging.getLogger(__name__)

COLLECTION_JOBS = "compliance_evidence_pack_jobs"
GRIDFS_BUCKET = "evidence_packs"
MAX_PERIOD_DAYS = 366
_FETCH_CAP_REQUIREMENTS = 8000
_FETCH_CAP_DOCUMENTS = 8000
_FETCH_CAP_WORK_ORDERS = 2000
_FETCH_CAP_SCORES = 800


def parse_export_period(
    period_start: Optional[str],
    period_end: Optional[str],
) -> Optional[Tuple[datetime, datetime]]:
    """
    Inclusive calendar dates (YYYY-MM-DD) → [lo, hi_exclusive) in UTC for row filtering.
    Returns None for a full (unfiltered) export.
    """
    ps = (period_start or "").strip()[:10]
    pe = (period_end or "").strip()[:10]
    if not ps and not pe:
        return None
    if not ps or not pe:
        raise ValueError("Both period_start and period_end are required when filtering by date")
    try:
        lo = datetime.fromisoformat(ps).replace(tzinfo=timezone.utc)
        hi_day = datetime.fromisoformat(pe).replace(tzinfo=timezone.utc)
    except ValueError as e:
        raise ValueError("Invalid period date (use YYYY-MM-DD)") from e
    if hi_day.date() < lo.date():
        raise ValueError("period_end must be on or after period_start")
    if (hi_day.date() - lo.date()).days > MAX_PERIOD_DAYS:
        raise ValueError(f"Period cannot exceed {MAX_PERIOD_DAYS} days")
    hi_excl = hi_day + timedelta(days=1)
    return (lo, hi_excl)


def _as_utc_datetime(val: Any) -> Optional[datetime]:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.replace(tzinfo=timezone.utc) if val.tzinfo is None else val.astimezone(timezone.utc)
    s = str(val).strip()
    if not s:
        return None
    try:
        s2 = s.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s2)
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
    except Exception:
        return None


def _score_row_in_period(row: Dict[str, Any], lo: datetime, hi_excl: datetime) -> bool:
    dk = row.get("date_key")
    if dk:
        try:
            d = datetime.fromisoformat(str(dk)[:10]).replace(tzinfo=timezone.utc)
            return lo <= d < hi_excl
        except Exception:
            pass
    ts = _as_utc_datetime(row.get("timestamp") or row.get("created_at"))
    if ts:
        return lo <= ts < hi_excl
    return False


def _filter_rows_by_time_field(
    rows: List[Dict[str, Any]],
    field_names: Tuple[str, ...],
    lo: datetime,
    hi_excl: datetime,
    cap: int,
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for r in rows:
        ts = None
        for f in field_names:
            ts = _as_utc_datetime(r.get(f))
            if ts:
                break
        if ts is None or not (lo <= ts < hi_excl):
            continue
        out.append(r)
        if len(out) >= cap:
            break
    return out


def _csv_from_rows(fieldnames: List[str], rows: List[Dict[str, Any]]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
    w.writeheader()
    for r in rows:
        flat = {}
        for k in fieldnames:
            v = r.get(k)
            if v is None:
                flat[k] = ""
            elif isinstance(v, (dict, list)):
                flat[k] = json.dumps(v, default=str)
            else:
                flat[k] = str(v)
        w.writerow(flat)
    return buf.getvalue()


async def _load_requirements(
    client_id: str,
    period: Optional[Tuple[datetime, datetime]] = None,
) -> List[Dict[str, Any]]:
    db = database.get_db()
    cap = _FETCH_CAP_REQUIREMENTS if period else 5000
    cur = db.requirements.find({"client_id": client_id}, {"_id": 0}).limit(cap)
    rows = await cur.to_list(length=cap)
    if period:
        lo, hi_excl = period
        rows = _filter_rows_by_time_field(rows, ("updated_at", "created_at"), lo, hi_excl, 5000)
    return rows[:5000]


async def _load_properties(client_id: str) -> List[Dict[str, Any]]:
    db = database.get_db()
    cur = db.properties.find({"client_id": client_id}, {"_id": 0}).limit(2000)
    return await cur.to_list(length=2000)


async def _load_documents_meta(
    client_id: str,
    period: Optional[Tuple[datetime, datetime]] = None,
) -> List[Dict[str, Any]]:
    db = database.get_db()
    cap = _FETCH_CAP_DOCUMENTS if period else 5000
    cur = (
        db.documents.find(
            {"client_id": client_id},
            {
                "_id": 0,
                "document_id": 1,
                "filename": 1,
                "property_id": 1,
                "requirement_id": 1,
                "status": 1,
                "uploaded_at": 1,
                "verified_at": 1,
                "content_type": 1,
            },
        )
        .sort("uploaded_at", -1)
        .limit(cap)
    )
    rows = await cur.to_list(length=cap)
    if period:
        lo, hi_excl = period
        rows = _filter_rows_by_time_field(rows, ("uploaded_at", "verified_at"), lo, hi_excl, 5000)
    return rows[:5000]


async def _load_score_history(
    client_id: str,
    limit: int = 400,
    period: Optional[Tuple[datetime, datetime]] = None,
) -> List[Dict[str, Any]]:
    db = database.get_db()
    fetch = _FETCH_CAP_SCORES if period else limit
    cur = (
        db.compliance_score_history.find({"client_id": client_id}, {"_id": 0})
        .sort("date_key", -1)
        .limit(fetch)
    )
    rows = await cur.to_list(length=fetch)
    if period:
        lo, hi_excl = period
        rows = [r for r in rows if _score_row_in_period(r, lo, hi_excl)][:limit]
    return rows[:limit]


async def _load_work_orders_timeline(
    client_id: str,
    limit: int = 500,
    period: Optional[Tuple[datetime, datetime]] = None,
) -> List[Dict[str, Any]]:
    db = database.get_db()
    cap = _FETCH_CAP_WORK_ORDERS if period else limit
    cur = (
        db.work_orders.find({"client_id": client_id}, {"_id": 0})
        .sort("updated_at", -1)
        .limit(cap)
    )
    rows = await cur.to_list(length=cap)
    if period:
        lo, hi_excl = period
        rows = _filter_rows_by_time_field(
            rows,
            ("updated_at", "created_at", "completed_at"),
            lo,
            hi_excl,
            limit,
        )
    return rows[:limit]


async def build_evidence_pack_zip_bytes(
    client_id: str,
    customer_reference: Optional[str],
    *,
    period_start: Optional[str] = None,
    period_end: Optional[str] = None,
) -> Tuple[bytes, Dict[str, Any]]:
    """Assemble ZIP in memory from live Mongo data. Optional period filters row-level tables; properties stay full-folio."""
    period = parse_export_period(period_start, period_end)
    props = await _load_properties(client_id)
    reqs = await _load_requirements(client_id, period)
    docs = await _load_documents_meta(client_id, period)
    scores = await _load_score_history(client_id, period=period)
    wos = await _load_work_orders_timeline(client_id, period=period)

    req_fields = [
        "requirement_id",
        "property_id",
        "requirement_type",
        "requirement_code",
        "description",
        "status",
        "due_date",
        "created_at",
        "updated_at",
    ]
    prop_fields = [
        "property_id",
        "nickname",
        "address_line_1",
        "city",
        "postcode",
        "compliance_status",
        "property_type",
    ]
    doc_fields = [
        "document_id",
        "filename",
        "property_id",
        "requirement_id",
        "status",
        "uploaded_at",
        "verified_at",
        "content_type",
    ]
    score_fields = ["date_key", "score", "grade", "timestamp", "created_at"]
    wo_fields = [
        "work_order_id",
        "property_id",
        "status",
        "created_at",
        "updated_at",
        "completed_at",
        "description",
        "severity",
    ]

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "client_id": client_id,
        "customer_reference": customer_reference or "",
        "export_filter": (
            {
                "mode": "period",
                "period_start": (period_start or "").strip()[:10],
                "period_end": (period_end or "").strip()[:10],
                "note": "Requirements, documents metadata, score history, and work orders are filtered to activity in this UTC date range (inclusive). Properties include the full portfolio for context.",
            }
            if period
            else {
                "mode": "all",
                "note": "Snapshot up to per-table row caps. Binary document files are not included.",
            }
        ),
        "counts": {
            "properties": len(props),
            "requirements": len(reqs),
            "documents": len(docs),
            "score_snapshots": len(scores),
            "work_orders": len(wos),
        },
        "note": "Manifest describes CSV files in this archive. Binary document files are not included; metadata and compliance rows are exportable from the portal.",
    }

    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest, indent=2))
        zf.writestr("properties.csv", _csv_from_rows(prop_fields, props))
        zf.writestr("requirements.csv", _csv_from_rows(req_fields, reqs))
        zf.writestr("documents_metadata.csv", _csv_from_rows(doc_fields, docs))
        zf.writestr("compliance_score_history.csv", _csv_from_rows(score_fields, scores))
        zf.writestr("work_orders.csv", _csv_from_rows(wo_fields, wos))

    data = bio.getvalue()
    return data, manifest


async def upload_pack_to_gridfs(filename: str, data: bytes, metadata: Dict[str, Any]) -> str:
    from motor.motor_asyncio import AsyncIOMotorGridFSBucket

    db = database.get_db()
    fs = AsyncIOMotorGridFSBucket(db, bucket_name=GRIDFS_BUCKET)
    grid_id = await fs.upload_from_stream(
        filename,
        io.BytesIO(data),
        metadata=metadata,
    )
    return str(grid_id)


async def create_evidence_pack_job(
    client_id: str,
    portal_user_id: str,
    customer_reference: Optional[str],
    *,
    period_start: Optional[str] = None,
    period_end: Optional[str] = None,
) -> Dict[str, Any]:
    """Build pack, store GridFS, persist job row. Returns job document."""
    db = database.get_db()
    ps = (period_start or "").strip()[:10] or "all"
    pe = (period_end or "").strip()[:10] or "all"
    day_key = datetime.now(timezone.utc).date().isoformat()
    scope_key = hashlib.sha256(f"{client_id}:{day_key}:{ps}:{pe}".encode()).hexdigest()[:16]
    job_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    zip_bytes, manifest = await build_evidence_pack_zip_bytes(
        client_id,
        customer_reference,
        period_start=period_start,
        period_end=period_end,
    )
    fname = f"evidence-pack_{client_id}_{scope_key}.zip"
    grid_id = await upload_pack_to_gridfs(
        fname,
        zip_bytes,
        metadata={
            "client_id": client_id,
            "job_id": job_id,
            "uploaded_at": now,
            "content_type": "application/zip",
        },
    )

    doc = {
        "job_id": job_id,
        "client_id": client_id,
        "portal_user_id": portal_user_id,
        "status": "completed",
        "created_at": now,
        "completed_at": now,
        "gridfs_id": grid_id,
        "filename": fname,
        "byte_size": len(zip_bytes),
        "manifest": manifest,
        "error": None,
        "period_start": ps if ps != "all" else None,
        "period_end": pe if pe != "all" else None,
    }
    await db[COLLECTION_JOBS].insert_one(doc)
    doc.pop("_id", None)
    return doc


async def create_processing_evidence_pack_job(
    client_id: str,
    portal_user_id: str,
    customer_reference: Optional[str],
    *,
    period_start: Optional[str] = None,
    period_end: Optional[str] = None,
) -> Dict[str, Any]:
    """Insert a processing job row; caller schedules `run_evidence_pack_job_in_background(job_id)`."""
    db = database.get_db()
    ps = (period_start or "").strip()[:10] or "all"
    pe = (period_end or "").strip()[:10] or "all"
    job_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    doc: Dict[str, Any] = {
        "job_id": job_id,
        "client_id": client_id,
        "portal_user_id": portal_user_id,
        "status": "processing",
        "created_at": now,
        "completed_at": None,
        "gridfs_id": None,
        "filename": None,
        "byte_size": None,
        "manifest": None,
        "error": None,
        "period_start": ps if ps != "all" else None,
        "period_end": pe if pe != "all" else None,
        "customer_reference": customer_reference,
    }
    await db[COLLECTION_JOBS].insert_one(doc)
    doc.pop("_id", None)
    return doc


async def run_evidence_pack_job_in_background(job_id: str) -> None:
    """Build ZIP, upload GridFS, mark job completed or failed; audit on success."""
    db = database.get_db()
    job = await db[COLLECTION_JOBS].find_one({"job_id": job_id})
    if not job or job.get("status") != "processing":
        return
    client_id = job["client_id"]
    portal_user_id = job.get("portal_user_id") or ""
    crn = job.get("customer_reference")
    period_start = job.get("period_start")
    period_end = job.get("period_end")
    ps = (period_start or "all") if period_start else "all"
    pe = (period_end or "all") if period_end else "all"
    day_key = datetime.now(timezone.utc).date().isoformat()
    scope_key = hashlib.sha256(f"{client_id}:{day_key}:{ps}:{pe}".encode()).hexdigest()[:16]
    try:
        zip_bytes, manifest = await build_evidence_pack_zip_bytes(
            client_id,
            crn,
            period_start=period_start,
            period_end=period_end,
        )
        fname = f"evidence-pack_{client_id}_{scope_key}.zip"
        now = datetime.now(timezone.utc).isoformat()
        grid_id = await upload_pack_to_gridfs(
            fname,
            zip_bytes,
            metadata={
                "client_id": client_id,
                "job_id": job_id,
                "uploaded_at": now,
                "content_type": "application/zip",
            },
        )
        await db[COLLECTION_JOBS].update_one(
            {"job_id": job_id},
            {
                "$set": {
                    "status": "completed",
                    "completed_at": now,
                    "gridfs_id": grid_id,
                    "filename": fname,
                    "byte_size": len(zip_bytes),
                    "manifest": manifest,
                    "error": None,
                }
            },
        )
        from models import AuditAction
        from utils.audit import create_audit_log

        await create_audit_log(
            action=AuditAction.REPORT_EXPORTED,
            client_id=client_id,
            actor_id=portal_user_id or None,
            metadata={
                "export_kind": "compliance_evidence_pack_v1",
                "job_id": job_id,
                "period_start": job.get("period_start"),
                "period_end": job.get("period_end"),
                "async": True,
            },
        )
    except Exception as e:
        logger.exception("evidence_pack background job %s failed", job_id)
        await db[COLLECTION_JOBS].update_one(
            {"job_id": job_id},
            {
                "$set": {
                    "status": "failed",
                    "error": str(e)[:500],
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                }
            },
        )


async def get_job(client_id: str, job_id: str) -> Optional[Dict[str, Any]]:
    db = database.get_db()
    doc = await db[COLLECTION_JOBS].find_one(
        {"job_id": job_id, "client_id": client_id},
        {"_id": 0},
    )
    return doc


async def read_pack_bytes(gridfs_id: str) -> Optional[bytes]:
    from motor.motor_asyncio import AsyncIOMotorGridFSBucket

    try:
        db = database.get_db()
        fs = AsyncIOMotorGridFSBucket(db, bucket_name=GRIDFS_BUCKET)
        buf = io.BytesIO()
        await fs.download_to_stream(ObjectId(gridfs_id), buf)
        return buf.getvalue()
    except Exception as e:
        logger.error("read_pack_bytes failed: %s", e)
        return None


async def recent_jobs(client_id: str, limit: int = 10) -> List[Dict[str, Any]]:
    db = database.get_db()
    cur = (
        db[COLLECTION_JOBS]
        .find({"client_id": client_id}, {"_id": 0, "manifest": 0})
        .sort("created_at", -1)
        .limit(limit)
    )
    rows = await cur.to_list(length=limit)
    return rows
