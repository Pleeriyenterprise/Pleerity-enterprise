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
