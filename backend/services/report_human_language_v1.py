"""
REPORTING-HUMAN-LANGUAGE-CONVERGENCE-01 — customer-facing report/export language.

Maps internal enums and implementation tokens to regulator-defensible human phrases.
Internal API keys and scoring semantics are unchanged; only presentation strings converge here.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

REPORT_HUMAN_LANGUAGE_VERSION = "v1"

# --- Assurance tiers ---
ASSURANCE_TIER_LABELS: Dict[str, str] = {
    "SELF_RECORDED": "Self-recorded assurance",
    "PLATFORM_REVIEWED": "Awaiting review",
    "VERIFIED_DOCUMENT": "Document verified",
    "VERIFIED": "Verified",
    "PLATFORM_VERIFIED": "Verified",
    "ASSURANCE_PENDING": "Assurance pending",
}

# --- Client lifecycle ---
LIFECYCLE_LABELS: Dict[str, str] = {
    "ACTION_REQUIRED": "Action required",
    "PENDING_REVIEW": "Awaiting review",
    "SATISFIED_UNVERIFIED": "Recorded on file",
    "VERIFIED": "Verified",
    "NOT_APPLICABLE": "Not applicable",
}

# --- Projected compliance status (score/export) ---
COMPLIANCE_STATUS_LABELS: Dict[str, str] = {
    "EXPIRING_SOON": "Renewal approaching",
    "OVERDUE": "Overdue",
    "EXPIRED": "Expired",
    "MISSING": "Missing evidence",
    "PENDING": "Pending confirmation",
    "COMPLIANT": "Compliant",
    "VALID": "Valid",
    "NOT_REQUIRED": "Not required",
}

# --- Score status (headline) ---
SCORE_STATUS_LABELS: Dict[str, str] = {
    "calculating": "Score updating",
    "partial": "Partially calculated",
    "stale": "Score may be out of date",
    "ok": "Current",
    "reconciliation_required": "Reconciliation in progress",
    "unavailable": "Not available",
    "unknown": "Status unclear",
    "pending_recalc": "Score updating",
}

SCORE_AUTHORITY_LABELS: Dict[str, str] = {
    "persisted_property_score": "Stored property scores",
    "live_projection": "Live projection",
}

# --- Export determinism (presentation only) ---
DETERMINISM_LABELS: Dict[str, str] = {
    "live_regenerated": (
        "This export reflects the latest portfolio information and may differ from previous downloads."
    ),
    "point_in_time_snapshot": "Point-in-time export — data as at generation.",
    "immutable_artifact": (
        "Frozen governance record — re-download returns the same file bytes as at generation."
    ),
}

IMMUTABLE_SECTION_TITLE = "Frozen governance record"
LIVE_EXPORT_SECTION_TITLE = "Current portfolio export"

# --- Disclosure phrases (replace engineering vocabulary) ---
DISCLOSURE_SCORE_UPDATING = "Recent compliance updates are still being processed."
DISCLOSURE_SCORE_STALE = "The headline score may not yet reflect the latest recalculation."
DISCLOSURE_SELF_RECORDED_SCORE = (
    "Some recorded obligations may not affect the compliance score directly."
)
DISCLOSURE_ASYNC_PORTFOLIO = (
    "Portfolio compliance score may be updating; requirement rows reflect current records."
)

ACCESSIBILITY_EXPORT_NOTICE = (
    "Accessibility-enhanced PDF: logical section headings, improved table contrast, and selectable text. "
    "Not PDF/UA certified."
)

# Patterns that must not appear in customer-facing export/PDF body text
_FORBIDDEN_LEAK_RE = re.compile(
    r"\b("
    r"SATISFIED_UNVERIFIED|VERIFIED_DOCUMENT|SELF_RECORDED|PLATFORM_REVIEW_PENDING|"
    r"EXPIRING_SOON|live_regenerated|immutable_artifact|AUDIT_ARTIFACT|OPERATIONAL_EXPORT|"
    r"reporting_semantics_v1|persisted_property_score|async_score_note|score_status=|"
    r"SELF-REC|SAT-UNVER|ASPEND|queue_backed|reconciliation_required_count|"
    r"truth_presentation_stage|governance_family|semantic_state"
    r")\b",
    re.I,
)
_SNAKE_CASE_LEAK_RE = re.compile(r"\b[a-z]+_[a-z]{2,}\b")


def human_label(mapping: Dict[str, str], raw: Optional[str], *, fallback_humanize: bool = True) -> str:
    key = str(raw or "").strip().upper()
    if not key:
        return "—"
    if key in mapping:
        return mapping[key]
    lower = str(raw or "").strip().lower()
    if lower in mapping:
        return mapping[lower]
    if fallback_humanize and "_" in key:
        return " ".join(w.capitalize() for w in key.lower().split("_"))
    return str(raw)[:40] if raw else "—"


def human_assurance_tier_label(row: Dict[str, Any]) -> str:
    tier = str(row.get("assurance_tier") or "").strip().upper()
    if tier:
        return human_label(ASSURANCE_TIER_LABELS, tier)
    life = str(row.get("client_lifecycle_state") or row.get("lifecycle_state") or "").strip().upper()
    if life == "SATISFIED_UNVERIFIED":
        return LIFECYCLE_LABELS["SATISFIED_UNVERIFIED"]
    if life == "PENDING_REVIEW":
        return LIFECYCLE_LABELS["PENDING_REVIEW"]
    if life == "VERIFIED":
        return LIFECYCLE_LABELS["VERIFIED"]
    return "—"


def human_lifecycle_label(row: Dict[str, Any]) -> str:
    life = str(row.get("client_lifecycle_state") or row.get("lifecycle_state") or "").strip().upper()
    return human_label(LIFECYCLE_LABELS, life) if life else "—"


def human_compliance_status_label(status: Optional[str]) -> str:
    return human_label(COMPLIANCE_STATUS_LABELS, status)


def human_score_status_label(score_status: Optional[str]) -> str:
    return human_label(SCORE_STATUS_LABELS, score_status, fallback_humanize=False) if score_status else "—"


def human_score_authority_label(authority: Optional[str]) -> str:
    return human_label(SCORE_AUTHORITY_LABELS, authority, fallback_humanize=False) if authority else "—"


def human_date_confidence_label(row: Dict[str, Any]) -> str:
    dc = str(row.get("date_confidence") or "").strip().upper()
    if dc in ("CONFIRMED", "VERIFIED", "USER_CONFIRMED"):
        return "Confirmed"
    if dc in ("ESTIMATED", "SYSTEM_ESTIMATED", "PROVISIONAL"):
        return "Estimated"
    if row.get("date_source") == "SYSTEM_ESTIMATED":
        return "Estimated"
    ea = row.get("evidence_authority") if isinstance(row.get("evidence_authority"), dict) else {}
    if ea.get("effective_expiry_is_estimated"):
        return "Estimated"
    if not row.get("confirmed_expiry_date") and (row.get("due_date") or row.get("extracted_expiry_date")):
        return "Estimated"
    if dc:
        return human_label({"UNK": "Unknown"}, dc[:8], fallback_humanize=True)
    return "Unknown"


def human_evidence_presence_label(row: Dict[str, Any]) -> str:
    if row.get("evidence_doc_id") or row.get("document_id"):
        return "Linked"
    es = str(row.get("evidence_state") or "").strip().upper()
    if es in ("VERIFIED", "UPLOADED_UNVERIFIED"):
        return "On file"
    if es in ("MISSING", ""):
        return "None"
    if es == "UPLOADED_UNVERIFIED":
        return "On file"
    return human_label({"UPLOADED_UNVERIFIED": "On file"}, es) if es else "—"


def human_operational_renewal_date(row: Dict[str, Any]) -> str:
    """Customer-facing obligation date — Compliance Timeline when enriched."""
    from services.compliance_timeline_presentation import (
        ensure_compliance_timeline_on_requirement,
        timeline_report_date_display,
    )

    enriched = ensure_compliance_timeline_on_requirement(row)
    display = timeline_report_date_display(enriched)
    if display != "No date on file":
        return display

    from utils.expiry_utils import get_effective_expiry_date

    eff = get_effective_expiry_date(row)
    if eff is not None and hasattr(eff, "date"):
        return eff.date().isoformat()
    raw = row.get("due_date") or row.get("confirmed_expiry_date") or row.get("extracted_expiry_date")
    if raw is None or str(raw).strip() == "":
        return "No date on file"
    s = str(raw).strip().upper()
    if s in ("N/A", "UNKNOWN", "UNKNOWN_DATE", "NONE", "—"):
        return "No date on file"
    try:
        from datetime import datetime

        d = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        return d.date().isoformat()
    except Exception:
        cleaned = str(raw)[:10]
        if cleaned.upper() in ("UNKNOWN_D", "UNKNOWN"):
            return "No date on file"
        return cleaned


def human_requirements_evidence_posture(row: Dict[str, Any], interp: Optional[Dict[str, Any]] = None) -> str:
    """Operational evidence posture for Requirements Report."""
    interp = interp or {}
    label = str(interp.get("audience_status_label") or "").strip()
    if label == "Recorded on file":
        return "Recorded on file (not independently verified)"
    if label == "Action required":
        return "Review recommended"
    if label:
        return label
    es = human_evidence_presence_label(row)
    if es == "On file":
        return "Evidence on file"
    if es == "None":
        return "No evidence on file"
    return es if es != "—" else "Status unclear"


def human_requirements_recommended_action(
    row: Dict[str, Any],
    interp: Dict[str, Any],
    *,
    bucket: str,
) -> str:
    """Concise remediation guidance — no legal advice."""
    action = str(interp.get("landlord_next_action") or "").strip()
    if action and action != "Review requirement details in the portal":
        if "action required" not in action.lower():
            return action[:80]
    cs = str(row.get("status") or "").upper()
    if bucket == "immediate_attention":
        if cs in ("OVERDUE", "EXPIRED"):
            return "Renew or replace evidence promptly"
        return "Upload or confirm required evidence"
    if bucket == "upcoming_renewals":
        return "Schedule renewal before expiry"
    if bucket == "evidence_review_required":
        return "Await platform review — no upload unless rejected"
    if bucket == "recorded_not_verified":
        return "Optional: strengthen with verified evidence"
    if bucket == "fully_compliant":
        return "No immediate action"
    return "Continue routine monitoring"


def human_requirements_urgency_label(bucket: str, computed_status: Optional[str]) -> str:
    if bucket == "immediate_attention":
        cs = (computed_status or "").upper()
        if cs in ("OVERDUE", "EXPIRED"):
            return "Urgent"
        return "High"
    if bucket == "upcoming_renewals":
        return "Medium"
    if bucket == "evidence_review_required":
        return "Medium"
    if bucket == "recorded_not_verified":
        return "Low"
    return "Routine"


def human_review_state_label(row: Dict[str, Any]) -> str:
    life = str(row.get("client_lifecycle_state") or "").strip().upper()
    if life == "PENDING_REVIEW":
        return "Awaiting review"
    ea = row.get("evidence_authority") if isinstance(row.get("evidence_authority"), dict) else {}
    ndv = str(ea.get("non_document_verification_status") or "").strip().upper()
    if ndv == "PENDING_ADMIN_REVIEW":
        return "Awaiting review"
    return "—"


def human_governance_chip_line(row: Dict[str, Any]) -> str:
    """Single concise governance column for matrix tables (human-readable)."""
    parts = [
        human_assurance_tier_label(row),
        human_lifecycle_label(row),
        human_date_confidence_label(row),
        human_evidence_presence_label(row),
    ]
    rev = human_review_state_label(row)
    if rev != "—":
        parts.append(rev)
    return " · ".join(p for p in parts if p and p != "—")


def human_export_footer_grade(export_grade: str, export_grade_label: str) -> str:
    label = (export_grade_label or "").strip()
    if label and label.upper() != str(export_grade or "").strip().upper():
        return label
    from services.reporting_semantics_v1 import EXPORT_GRADE_DEFINITIONS

    defn = EXPORT_GRADE_DEFINITIONS.get(str(export_grade or "").strip(), {})
    return defn.get("label") or human_label(
        {
            "AUDIT_ARTIFACT": "Governed audit evidence pack",
            "OPERATIONAL_EXPORT": "Operational portfolio export",
            "REGULATORY_SUBMISSION": "Regulatory submission",
            "CLIENT_PRESENTATION": "Client presentation",
            "EXECUTIVE_SUMMARY": "Executive summary",
        },
        export_grade,
    )


def human_async_disclosure_lines(
    *,
    score_status: Optional[str],
    score_status_message: Optional[str],
) -> List[str]:
    """Customer-safe disclosure lines for exports (no raw status keys)."""
    st = (score_status or "").strip().lower()
    lines: List[str] = []
    if st in ("calculating", "partial", "reconciliation_required", "pending_recalc"):
        lines.append(DISCLOSURE_ASYNC_PORTFOLIO)
        if st == "calculating":
            lines.append(DISCLOSURE_SCORE_UPDATING)
    if st == "stale":
        lines.append(DISCLOSURE_SCORE_STALE)
    if score_status_message:
        msg = str(score_status_message).strip()
        if msg and not contains_internal_language_leak(msg):
            lines.append(msg)
    return lines


def sanitize_customer_export_text(text: str) -> str:
    """Best-effort customer-safe export string; never raises."""
    t = (text or "").strip()
    if not t:
        return "—"
    if contains_internal_language_leak(t) or _SNAKE_CASE_LEAK_RE.search(t):
        return human_label({}, t)
    return t


def contains_internal_language_leak(text: str) -> bool:
    """True when text likely exposes implementation vocabulary to customers."""
    t = str(text or "")
    if not t.strip():
        return False
    if _FORBIDDEN_LEAK_RE.search(t):
        return True
    if "score_status=" in t.lower():
        return True
    return False


def audit_text_surfaces_customer_safe(text: str) -> str:
    """REGULATOR_READY_LANGUAGE | CLIENT_SAFE_LANGUAGE | INTERNAL_LANGUAGE_LEAK"""
    if contains_internal_language_leak(text):
        return "INTERNAL_LANGUAGE_LEAK"
    if _SNAKE_CASE_LEAK_RE.search(text):
        return "INTERNAL_LANGUAGE_LEAK"
    return "CLIENT_SAFE_LANGUAGE"


def mapping_matrix_export() -> Dict[str, Any]:
    return {
        "version": REPORT_HUMAN_LANGUAGE_VERSION,
        "assurance_tier": ASSURANCE_TIER_LABELS,
        "lifecycle": LIFECYCLE_LABELS,
        "compliance_status": COMPLIANCE_STATUS_LABELS,
        "score_status": SCORE_STATUS_LABELS,
        "score_authority": SCORE_AUTHORITY_LABELS,
        "determinism": DETERMINISM_LABELS,
    }
