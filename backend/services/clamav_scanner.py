"""
ClamAV malware scanner for intake uploads.
Scans files; on virus or scan failure marks as QUARANTINED and moves file to quarantine dir.
Requires ClamAV daemon (clamd) or clamscan on PATH. See docs/INTAKE_UPLOADS_CLAMAV.md.
"""
import os
import shutil
import subprocess
import logging
from pathlib import Path
from typing import Tuple

logger = logging.getLogger(__name__)

# Quarantine directory for flagged/failed files (sibling to intake uploads)
INTAKE_UPLOAD_DIR = Path(os.environ.get("INTAKE_UPLOAD_DIR", "/app/uploads/intake"))
QUARANTINE_DIR = Path(os.environ.get("INTAKE_QUARANTINE_DIR", "/app/uploads/intake_quarantine"))


def _ensure_quarantine_dir() -> Path:
    QUARANTINE_DIR.mkdir(parents=True, exist_ok=True)
    return QUARANTINE_DIR


def scan_file(file_path: str) -> Tuple[str, str | None]:
    """
    Scan a file with ClamAV. Uses clamdscan if socket available, else clamscan.
    
    Returns:
        ("CLEAN", None) if no virus
        ("QUARANTINED", error_message) if virus or scan failure
    """
    path = Path(file_path)
    if not path.is_file():
        return "QUARANTINED", "File not found"

    # Use clamscan CLI (no python-clamd dependency). Set CLAMAV_SOCKET for clamdscan if desired.
    use_clamd_socket = os.environ.get("CLAMAV_SOCKET", "")
    if use_clamd_socket and os.path.exists(use_clamd_socket):
        try:
            r = subprocess.run(
                ["clamdscan", "--fdpass", "--no-summary", str(path)],
                env={**os.environ, "CLAM_SOCKET": use_clamd_socket},
                capture_output=True,
                text=True,
                timeout=60,
            )
            if r.returncode == 0:
                return "CLEAN", None
            return "QUARANTINED", (r.stderr or r.stdout or "Threat or error").strip()
        except FileNotFoundError:
            pass  # fallback to clamscan
        except Exception as e:
            logger.warning(f"clamdscan failed for {path}: {e}")
            return "QUARANTINED", str(e)

    # clamscan CLI
    try:
        r = subprocess.run(
            ["clamscan", "--no-summary", "--infected", str(path)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if r.returncode == 0:
            return "CLEAN", None
        if r.returncode == 1:
            # 1 = virus found
            return "QUARANTINED", (r.stdout or r.stderr or "Threat detected").strip() or "Threat detected"
        return "QUARANTINED", r.stderr or r.stdout or f"Scan failed (exit {r.returncode})"
    except FileNotFoundError:
        logger.warning("ClamAV (clamscan) not found; treating file as QUARANTINED for safety")
        return "QUARANTINED", "ClamAV not installed or not on PATH"
    except subprocess.TimeoutExpired:
        return "QUARANTINED", "Scan timed out"
    except Exception as e:
        logger.warning(f"ClamAV scan error for {path}: {e}")
        return "QUARANTINED", str(e)


def move_to_quarantine(original_path: str, upload_id: str, filename: str) -> str:
    """
    Move file from intake upload dir to quarantine dir. Returns new path.
    """
    src = Path(original_path)
    _ensure_quarantine_dir()
    safe_name = f"{upload_id}_{filename}"
    dest = QUARANTINE_DIR / safe_name
    if src.is_file():
        shutil.move(str(src), str(dest))
        return str(dest)
    return original_path
