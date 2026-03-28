"""Persist contractor work order evidence files and append storage keys to work orders."""
import logging
import os
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from database import database
from services import maintenance_service

logger = logging.getLogger(__name__)

_DATA_DIR = os.environ.get("DATA_DIR", os.getcwd())
DOCUMENT_STORAGE_PATH = Path(
    os.environ.get("DOCUMENT_STORAGE_PATH", str(Path(_DATA_DIR) / "data" / "documents"))
)

MAX_BYTES = 20 * 1024 * 1024
ALLOWED_EXTENSIONS = frozenset({".pdf", ".jpg", ".jpeg", ".png", ".doc", ".docx"})
CONTRACTOR_EVIDENCE_SEGMENT = "contractor_evidence"

MIME_BY_EXT = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def normalize_evidence_storage_key(key: str) -> str:
    return (key or "").strip().replace("\\", "/")


def is_contractor_file_evidence_key(storage_key: str) -> bool:
    k = normalize_evidence_storage_key(storage_key)
    if not k or k.startswith("document:"):
        return False
    parts = k.split("/")
    if len(parts) < 4:
        return False
    return parts[1] == CONTRACTOR_EVIDENCE_SEGMENT


def evidence_key_allowed_for_work_order(
    storage_key: str,
    *,
    work_order_id: str,
    client_id: str,
) -> bool:
    k = normalize_evidence_storage_key(storage_key)
    if not k or ".." in k or k.startswith("/"):
        return False
    prefix = f"{client_id.strip()}/contractor_evidence/{work_order_id.strip()}/"
    return k.startswith(prefix)


def evidence_key_on_work_order(normalized_key: str, evidence_keys: Optional[List[str]]) -> bool:
    for raw in evidence_keys or []:
        if normalize_evidence_storage_key(str(raw)) == normalized_key:
            return True
    return False


async def resolve_contractor_evidence_file(
    *,
    work_order_id: str,
    wo_client_id: str,
    evidence_keys: Optional[List[str]],
    storage_key: str,
) -> Tuple[Path, str, str]:
    """Resolve filesystem path for a contractor-uploaded evidence file. Raises LookupError / ValueError / FileNotFoundError."""
    key = normalize_evidence_storage_key(storage_key)
    if not key:
        raise ValueError("storage_key is required")
    if not evidence_key_on_work_order(key, evidence_keys):
        raise LookupError("Evidence key not found on this work order")
    if not evidence_key_allowed_for_work_order(key, work_order_id=work_order_id, client_id=wo_client_id):
        raise ValueError("Invalid evidence key for this work order")
    full = (DOCUMENT_STORAGE_PATH / key).resolve()
    try:
        full.relative_to(DOCUMENT_STORAGE_PATH.resolve())
    except ValueError as e:
        raise ValueError("Invalid storage path") from e
    if not full.is_file():
        raise FileNotFoundError("Evidence file not found")
    ext = full.suffix.lower()
    media = MIME_BY_EXT.get(ext, "application/octet-stream")
    return full, media, full.name


def _normalized_extension(filename: str | None) -> str:
    ext = Path(filename or "").suffix.lower()
    return ext


def validate_evidence_file(*, filename: str | None, content: bytes) -> str:
    if not content:
        raise ValueError("Empty file")
    if len(content) > MAX_BYTES:
        raise ValueError(f"File too large (max {MAX_BYTES // (1024 * 1024)}MB)")
    ext = _normalized_extension(filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError("Unsupported file type. Use PDF, JPG, PNG, DOC, or DOCX.")
    return ext


async def save_contractor_work_order_evidence(
    *,
    work_order_id: str,
    contractor_id: str,
    filename: str | None,
    content: bytes,
) -> Tuple[str, Dict[str, Any]]:
    """Write file under DOCUMENT_STORAGE_PATH, append relative key to work order evidence_keys."""
    ext = validate_evidence_file(filename=filename, content=content)
    db = database.get_db()
    wo = await db.work_orders.find_one({"work_order_id": work_order_id})
    if not wo:
        raise ValueError("Work order not found")
    if (wo.get("contractor_id") or "").strip() != (contractor_id or "").strip():
        raise ValueError("Work order not found or not assigned to you")
    client_id = (wo.get("client_id") or "").strip()
    if not client_id:
        raise ValueError("Work order has no client context")

    file_id = uuid.uuid4().hex
    rel_key = f"{client_id}/contractor_evidence/{work_order_id}/{file_id}{ext}"
    dest = DOCUMENT_STORAGE_PATH.joinpath(*rel_key.split("/"))
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(content)
    except OSError as e:
        logger.warning("Contractor evidence write failed: %s", e)
        raise ValueError("Could not store file") from e

    updated = await maintenance_service.update_work_order(
        work_order_id,
        evidence_keys_append=[rel_key],
    )
    if not updated:
        try:
            dest.unlink()
        except OSError:
            pass
        raise RuntimeError("Failed to attach evidence to work order")
    return rel_key, updated
