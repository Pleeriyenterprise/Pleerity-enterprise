"""Central resolution for DATA_DIR, document vault, and intake upload paths.

Production defaults target a persistent volume mount (e.g. Render disk at ``/var/data``).
Override with ``DATA_DIR`` / ``DOCUMENT_STORAGE_PATH`` / ``INTAKE_UPLOAD_DIR`` as needed.

If ``/var/data`` (or an explicit ``DATA_DIR``) is not writable—common when a Render disk
is not attached—paths fall back to ``backend/runtime_local_data`` under the deploy tree
so the API can boot; ops should attach a disk and set ``DATA_DIR`` for persistence.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)


def _is_pytest() -> bool:
    return os.environ.get("PYTEST_RUNNING") == "1"


def is_production_env() -> bool:
    if _is_pytest():
        return False
    e = (os.environ.get("ENV") or os.environ.get("ENVIRONMENT") or "").strip().lower()
    return e in ("production", "prod")


def _package_backend_root() -> Path:
    """``backend/`` (parent of ``utils/``)."""
    return Path(__file__).resolve().parents[1]


def _runtime_local_data_root() -> Path:
    return _package_backend_root() / "runtime_local_data"


def _usable_writable_dir(path: Path) -> bool:
    """True if ``path`` can be created and is writable (used to pick a live data root)."""
    try:
        path.mkdir(parents=True, exist_ok=True)
        return os.access(path, os.W_OK)
    except (PermissionError, OSError):
        return False


def resolve_data_dir() -> str:
    explicit = (os.environ.get("DATA_DIR") or "").strip()
    if explicit:
        root = Path(explicit)
        if _usable_writable_dir(root):
            return str(root.resolve())
        logger.warning(
            "DATA_DIR %s is not writable or cannot be created; using deploy-local storage",
            explicit,
        )
        alt = _runtime_local_data_root()
        if _usable_writable_dir(alt):
            return str(alt.resolve())
        return "/tmp"
    if not is_production_env():
        return "/tmp"
    preferred = Path("/var/data")
    if _usable_writable_dir(preferred):
        return str(preferred.resolve())
    logger.warning(
        "/var/data is not writable or missing; using deploy-local storage until DATA_DIR is configured"
    )
    alt = _runtime_local_data_root()
    if _usable_writable_dir(alt):
        return str(alt.resolve())
    return "/tmp"


def resolve_document_storage_path() -> Path:
    explicit = (os.environ.get("DOCUMENT_STORAGE_PATH") or "").strip()
    if explicit:
        p = Path(explicit)
        if _usable_writable_dir(p):
            return p
        logger.warning(
            "DOCUMENT_STORAGE_PATH %s is not writable; using default under effective DATA_DIR",
            explicit,
        )
    return Path(resolve_data_dir()) / "data" / "documents"


def resolve_stored_document_file_path(raw_path: str) -> Path:
    """Resolve mongo ``file_path`` (relative vault key or absolute path) to a filesystem path."""
    p = Path(raw_path)
    if p.is_absolute():
        return p.resolve()
    return (resolve_document_storage_path() / raw_path).resolve()


def resolve_intake_upload_dir() -> Path:
    explicit = (os.environ.get("INTAKE_UPLOAD_DIR") or "").strip()
    if explicit:
        p = Path(explicit)
        if _usable_writable_dir(p):
            return p
        logger.warning(
            "INTAKE_UPLOAD_DIR %s is not writable; using default under effective DATA_DIR",
            explicit,
        )
    return Path(resolve_data_dir()) / "uploads" / "intake"


def resolve_intake_quarantine_dir() -> Path:
    explicit = (os.environ.get("INTAKE_QUARANTINE_DIR") or "").strip()
    if explicit:
        p = Path(explicit)
        if _usable_writable_dir(p):
            return p
        logger.warning(
            "INTAKE_QUARANTINE_DIR %s is not writable; using default under effective DATA_DIR",
            explicit,
        )
    return Path(resolve_data_dir()) / "uploads" / "intake_quarantine"


def is_unix_tmp_ephemeral_path(path: Path) -> bool:
    """True when resolved path lives under host ``/tmp`` (cleared on many Linux hosts / deploys)."""
    s = str(path.resolve()).replace("\\", "/").rstrip("/")
    return s == "/tmp" or s.startswith("/tmp/")


def is_runtime_local_fallback_path(path: Path) -> bool:
    """True when path lives under the deploy-tree fallback (lost on typical PaaS redeploy)."""
    s = str(path.resolve()).replace("\\", "/")
    return "runtime_local_data" in s


def _path_writable_entry(p: Path) -> Dict[str, Any]:
    try:
        resolved = p.resolve()
    except OSError:
        resolved = p
    exists = resolved.exists()
    is_dir = resolved.is_dir() if exists else False
    writable = False
    if exists and is_dir:
        writable = bool(os.access(resolved, os.W_OK))
    elif exists and resolved.is_file():
        writable = bool(os.access(resolved, os.W_OK))
    else:
        try:
            parent = resolved.parent
            if parent.exists():
                writable = bool(os.access(parent, os.W_OK))
        except OSError:
            writable = False
    return {
        "path": str(resolved),
        "exists": exists,
        "is_directory": is_dir,
        "writable": writable,
        "ephemeral_unix_tmp": is_unix_tmp_ephemeral_path(resolved),
        "deploy_runtime_fallback": is_runtime_local_fallback_path(resolved),
    }


def build_storage_health_report() -> Dict[str, Any]:
    """Effective paths + writability for ops (startup logs, GET …/observability/storage-paths)."""
    data_root = Path(resolve_data_dir())
    doc = resolve_document_storage_path()
    intake_ul = resolve_intake_upload_dir()
    intake_q = resolve_intake_quarantine_dir()
    return {
        "DATA_DIR": _path_writable_entry(data_root),
        "DOCUMENT_STORAGE_PATH": _path_writable_entry(doc),
        "INTAKE_UPLOAD_DIR": _path_writable_entry(intake_ul),
        "INTAKE_QUARANTINE_DIR": _path_writable_entry(intake_q),
        "env": {
            "DATA_DIR": bool((os.environ.get("DATA_DIR") or "").strip()),
            "DOCUMENT_STORAGE_PATH": bool((os.environ.get("DOCUMENT_STORAGE_PATH") or "").strip()),
            "INTAKE_UPLOAD_DIR": bool((os.environ.get("INTAKE_UPLOAD_DIR") or "").strip()),
            "INTAKE_QUARANTINE_DIR": bool((os.environ.get("INTAKE_QUARANTINE_DIR") or "").strip()),
        },
    }
