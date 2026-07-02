"""Governed evidence presentation for reports."""

from __future__ import annotations

import re
from typing import Any, Dict, Optional

from services.report_human_language_v1 import human_assurance_tier_label

_DOC_TYPE_PATTERNS = (
    (re.compile(r"gas.?safety|cp12", re.I), "Gas Safety Certificate"),
    (re.compile(r"\beicr\b|electrical.?install", re.I), "Electrical Installation Condition Report"),
    (re.compile(r"\bepc\b|energy.?perform", re.I), "Energy Performance Certificate"),
    (re.compile(r"legionella", re.I), "Legionella Risk Assessment"),
    (re.compile(r"fire.?risk|fra", re.I), "Fire Risk Assessment"),
    (re.compile(r"pat.?test", re.I), "Portable Appliance Testing"),
    (re.compile(r"tenancy|ast\b", re.I), "Tenancy Agreement"),
    (re.compile(r"deposit", re.I), "Deposit Protection Certificate"),
)


def infer_document_title(
    *,
    filename: Optional[str] = None,
    requirement_name: Optional[str] = None,
    requirement_type: Optional[str] = None,
    document_type: Optional[str] = None,
) -> str:
    """Prefer professional document titles over raw upload filenames."""
    for candidate in (document_type, requirement_name, requirement_type, filename):
        if not candidate:
            continue
        text = str(candidate).strip()
        for pattern, label in _DOC_TYPE_PATTERNS:
            if pattern.search(text):
                return label
        if text and not _looks_like_blob_name(text):
            return text[:80]
    if filename:
        return _clean_filename(filename)
    return "Compliance evidence"


def _looks_like_blob_name(text: str) -> bool:
    t = text.strip()
    if len(t) >= 32 and re.fullmatch(r"[a-f0-9\-]+", t, re.I):
        return True
    if t.startswith(("doc_", "req_", "rs_", "prop_")):
        return True
    return bool(re.fullmatch(r"[a-z0-9_]{8,}", t, re.I))


def _clean_filename(name: str) -> str:
    base = name.rsplit(".", 1)[0] if "." in name else name
    cleaned = base.replace("_", " ").replace("-", " ").strip()
    return cleaned.title()[:80] if cleaned else "Uploaded document"


def present_evidence_row(
    row: Dict[str, Any],
    *,
    doc: Optional[Dict[str, Any]] = None,
) -> Dict[str, str]:
    """Professional evidence cell labels for matrix tables."""
    doc = doc or {}
    title = infer_document_title(
        filename=doc.get("filename") or doc.get("original_filename") or row.get("evidence_file"),
        requirement_name=row.get("obligation") or row.get("requirement_name"),
        requirement_type=row.get("requirement_type"),
        document_type=doc.get("document_type"),
    )
    assurance = human_assurance_tier_label(row)
    verified = str(row.get("status") or "").upper() in ("VERIFIED", "COMPLIANT", "VALID")
    presence = "Verified" if verified else assurance if assurance != "—" else "On file"
    ref = doc.get("filename") or row.get("evidence_file") or ""
    return {
        "title": title,
        "presence": presence,
        "assurance": assurance,
        "reference": ref[:60] if ref else "",
    }
