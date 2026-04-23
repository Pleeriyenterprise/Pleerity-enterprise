"""Central resolution for DATA_DIR, document vault, and intake upload paths.

Production defaults target a persistent volume mount (e.g. Render disk at ``/var/data``).
Override with ``DATA_DIR`` / ``DOCUMENT_STORAGE_PATH`` / ``INTAKE_UPLOAD_DIR`` as needed.
"""
from __future__ import annotations

import os
from pathlib import Path


def _is_pytest() -> bool:
    return os.environ.get("PYTEST_RUNNING") == "1"


def is_production_env() -> bool:
    if _is_pytest():
        return False
    e = (os.environ.get("ENV") or os.environ.get("ENVIRONMENT") or "").strip().lower()
    return e in ("production", "prod")


def resolve_data_dir() -> str:
    explicit = (os.environ.get("DATA_DIR") or "").strip()
    if explicit:
        return explicit
    if is_production_env():
        return "/var/data"
    return "/tmp"


def resolve_document_storage_path() -> Path:
    explicit = (os.environ.get("DOCUMENT_STORAGE_PATH") or "").strip()
    if explicit:
        return Path(explicit)
    return Path(resolve_data_dir()) / "data" / "documents"


def resolve_intake_upload_dir() -> Path:
    explicit = (os.environ.get("INTAKE_UPLOAD_DIR") or "").strip()
    if explicit:
        return Path(explicit)
    return Path(resolve_data_dir()) / "uploads" / "intake"


def resolve_intake_quarantine_dir() -> Path:
    explicit = (os.environ.get("INTAKE_QUARANTINE_DIR") or "").strip()
    if explicit:
        return Path(explicit)
    return Path(resolve_data_dir()) / "uploads" / "intake_quarantine"


def is_unix_tmp_ephemeral_path(path: Path) -> bool:
    """True when resolved path lives under host ``/tmp`` (cleared on many Linux hosts / deploys)."""
    s = str(path.resolve()).replace("\\", "/").rstrip("/")
    return s == "/tmp" or s.startswith("/tmp/")
