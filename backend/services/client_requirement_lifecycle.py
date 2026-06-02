"""
Client-facing canonical requirement lifecycle (additive read-model).

Computed once during `enrich_requirement_dict` for audience=client.
Legacy `status` / `evidence_state` fields are preserved; consumers should prefer
`client_lifecycle_state` + `client_lifecycle_reason_codes` for UX consistency.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from models.evidence_review import EvidenceReviewState
from services.evidence_review_config import is_feature_evidence_review_v2
from services.evidence_review_migration import effective_evidence_review_state
from services.requirement_code_registry import normalize_requirement_code
from services.requirement_evidence_authority import (
    EA_EXTRACTION_PENDING_CONFIRMATION,
    EA_MISMATCH_FLAGGED,
    EA_MISSING,
    EA_NOT_REQUIRED,
    EA_PENDING_ADMIN_REVIEW,
    EA_REJECTED,
    EA_UPLOADED_UNCONFIRMED,
    EA_VERIFIED_CURRENT,
    EA_VERIFIED_EXPIRED,
)

ACTION_REQUIRED = "ACTION_REQUIRED"
PENDING_REVIEW = "PENDING_REVIEW"
SATISFIED_UNVERIFIED = "SATISFIED_UNVERIFIED"
VERIFIED = "VERIFIED"
NOT_APPLICABLE = "NOT_APPLICABLE"

_CLIENT_LIFECYCLE_STATES = frozenset(
    {
        ACTION_REQUIRED,
        PENDING_REVIEW,
        SATISFIED_UNVERIFIED,
        VERIFIED,
        NOT_APPLICABLE,
    }
)


def _status_upper(st: Optional[str]) -> str:
    return (st or "").strip().upper()


def _ea_state(row: Dict[str, Any]) -> str:
    ea = row.get("evidence_authority") if isinstance(row.get("evidence_authority"), dict) else {}
    return _status_upper(ea.get("state"))


def _semantic_upper(row: Dict[str, Any]) -> str:
    s = row.get("semantic_state")
    if s is None and isinstance(row.get("evidence_authority"), dict):
        s = row["evidence_authority"].get("semantic_state")
    return _status_upper(s) if s is not None else ""


def _compliance_incomplete(row: Dict[str, Any]) -> bool:
    comp = row.get("evidence_completeness") if isinstance(row.get("evidence_completeness"), dict) else {}
    try:
        if int(comp.get("required_missing_count") or 0) > 0:
            return True
    except (TypeError, ValueError):
        pass
    try:
        pct = float(comp.get("completion_percent") or 100.0)
        if pct < 100.0:
            return True
    except (TypeError, ValueError):
        pass
    return False


def _v2_review_pending(linked_doc: Optional[Dict[str, Any]]) -> bool:
    if not linked_doc or not is_feature_evidence_review_v2():
        return False
    st = effective_evidence_review_state(linked_doc)
    if st in (
        EvidenceReviewState.UNDER_REVIEW.value,
        EvidenceReviewState.NEEDS_INFORMATION.value,
    ):
        return True
    if st == EvidenceReviewState.UPLOADED.value and linked_doc.get("review_required") is True:
        return True
    return False


def _tenancy_action_required(ta_text: str) -> bool:
    t = (ta_text or "").lower()
    return "agreement not recorded" in t or "action required" in t


def derive_client_lifecycle_fields(
    row: Dict[str, Any],
    *,
    linked_primary_document: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Returns keys: client_lifecycle_state, client_lifecycle_label, client_lifecycle_reason_codes
    """
    reasons: List[str] = []
    from services.client_applicability_coherence import row_applicability_for_client_coherence

    app = _status_upper(row_applicability_for_client_coherence(row))
    status = _status_upper(row.get("status"))
    compliance_state = _status_upper(row.get("compliance_state"))
    evidence_state = _status_upper(row.get("evidence_state"))
    ea = _ea_state(row)
    semantic = _semantic_upper(row)
    raw_code = str(row.get("requirement_code") or row.get("requirement_type") or "").strip()
    canon = normalize_requirement_code(raw_code) or raw_code.lower().replace(" ", "_")
    from services.requirement_truth import ACTIVE_STANDARD_CODES

    is_condition_standard = canon in ACTIVE_STANDARD_CODES

    def pack(state: str, label: str, rsn: List[str]) -> Dict[str, Any]:
        return {
            "client_lifecycle_state": state,
            "client_lifecycle_label": label,
            "client_lifecycle_reason_codes": list(rsn),
        }

    # --- NOT_APPLICABLE ---
    from services.client_applicability_coherence import is_stale_not_required_lifecycle_override

    stale_na_authority = ea == EA_NOT_REQUIRED and is_stale_not_required_lifecycle_override(row)
    if (
        not stale_na_authority
        and (
            app == "NOT_REQUIRED"
            or status in ("NOT_REQUIRED", "NOT_APPLICABLE", "WAIVED")
            or ea == EA_NOT_REQUIRED
        )
    ):
        if ea == EA_NOT_REQUIRED:
            reasons.append("EA_NOT_REQUIRED")
        elif app == "NOT_REQUIRED":
            reasons.append("APPLICABILITY_NOT_REQUIRED")
        else:
            reasons.append("STATUS_NOT_APPLICABLE")
        return pack(NOT_APPLICABLE, "Not applicable", reasons)

    ta_text = str(row.get("tenancy_agreement_status_text") or "").strip()

    if is_condition_standard:

        def _condition_standard_operational_pack() -> Optional[Dict[str, Any]]:
            summary = (
                row.get("active_standard_status_summary")
                if isinstance(row.get("active_standard_status_summary"), dict)
                else {}
            )
            signals = summary.get("signal_counts") if isinstance(summary.get("signal_counts"), dict) else {}
            if any(
                int(signals.get(k) or 0) > 0
                for k in ("open_issues", "open_work_orders", "open_risk_signals", "open_compliance_gaps")
            ):
                reasons.append("CONDITION_STANDARD_OPERATIONAL_SIGNALS_OPEN")
                state = str(summary.get("state") or "").strip().lower()
                if state == "remediation_in_progress":
                    return pack(ACTION_REQUIRED, "Remediation in progress", reasons)
                return pack(ACTION_REQUIRED, "Condition status needs review", reasons)
            if str(summary.get("state") or "").strip().lower() in ("", "unknown"):
                reasons.append("CONDITION_STANDARD_OPERATIONAL_SUMMARY_UNKNOWN")
                return pack(ACTION_REQUIRED, "Awaiting operational review", reasons)
            return None

        cs_pack = _condition_standard_operational_pack()
        if cs_pack is not None:
            return cs_pack

    # --- PENDING_REVIEW (admin / V2 queue) ---
    if ea == EA_PENDING_ADMIN_REVIEW:
        reasons.append("EA_PENDING_ADMIN_REVIEW")
        lbl = (
            "Evidence submitted — review pending"
            if (row.get("evidence_authority") or {}).get("state_reason") == "uploaded_pending_admin"
            else "Awaiting review"
        )
        return pack(PENDING_REVIEW, lbl, reasons)
    if linked_primary_document and _v2_review_pending(linked_primary_document):
        reasons.append("EVIDENCE_REVIEW_V2_PENDING")
        st = effective_evidence_review_state(linked_primary_document)
        reasons.append(f"DOC_REVIEW_STATE:{st}")
        return pack(PENDING_REVIEW, "Evidence submitted — review pending", reasons)

    # --- SATISFIED_UNVERIFIED before legacy urgency (non-document / declaration paths) ---
    if compliance_state == "ACCEPTED_UNVERIFIED":
        reasons.append("COMPLIANCE_ACCEPTED_UNVERIFIED")
        return pack(SATISFIED_UNVERIFIED, "Evidence recorded", reasons)
    if linked_primary_document:
        ers = effective_evidence_review_state(linked_primary_document)
        if ers == EvidenceReviewState.ACCEPTED_UNVERIFIED.value:
            reasons.append("DOC_ACCEPTED_UNVERIFIED")
            return pack(SATISFIED_UNVERIFIED, "Evidence recorded", reasons)
    if ea == EA_UPLOADED_UNCONFIRMED:
        reasons.append("EA_UPLOADED_UNCONFIRMED")
        return pack(SATISFIED_UNVERIFIED, "Evidence recorded", reasons)
    if semantic == "DECLARATION_RECORDED":
        reasons.append("SEMANTIC_DECLARATION_RECORDED")
        return pack(SATISFIED_UNVERIFIED, "Evidence recorded", reasons)

    # --- ACTION_REQUIRED (user-facing urgency) ---
    if status in ("OVERDUE", "EXPIRED", "FAILED", "MISSING", "MISSING_EVIDENCE", "NEEDS_REVIEW"):
        if status in ("OVERDUE", "EXPIRED"):
            from services.requirement_satisfaction_service import (
                document_upload_required,
                legacy_due_date_blocks_renewal_attention,
            )

            if not legacy_due_date_blocks_renewal_attention(row) and not document_upload_required(row):
                reasons.append("STALE_CALENDAR_OVERDUE_DEFERRED")
            else:
                reasons.append(f"STATUS:{status}")
                return pack(ACTION_REQUIRED, "Action required", reasons)
        else:
            reasons.append(f"STATUS:{status}")
            return pack(ACTION_REQUIRED, "Action required", reasons)
    if ea in (EA_MISSING, EA_REJECTED, EA_MISMATCH_FLAGGED):
        reasons.append(f"EA:{ea}")
        return pack(ACTION_REQUIRED, "Action required", reasons)
    if ea == EA_VERIFIED_EXPIRED:
        reasons.append("EA_VERIFIED_EXPIRED")
        return pack(ACTION_REQUIRED, "Action required", reasons)
    if ea == EA_EXTRACTION_PENDING_CONFIRMATION:
        reasons.append("EA_EXTRACTION_PENDING_CONFIRMATION")
        return pack(ACTION_REQUIRED, "Action required", reasons)
    if evidence_state in ("MISSING", "MISMATCH_FLAGGED", "AWAITING_USER_CONFIRM"):
        reasons.append(f"EVIDENCE_STATE:{evidence_state}")
        return pack(ACTION_REQUIRED, "Action required", reasons)
    if semantic in ("PARTIALLY_COMPLETE", "OPERATIONALLY_OPEN", "ASSESSMENT_FOLLOWUP_REQUIRED"):
        reasons.append(f"SEMANTIC:{semantic}")
        return pack(ACTION_REQUIRED, "Action required", reasons)
    if _compliance_incomplete(row):
        reasons.append("EVIDENCE_COMPLETENESS_INCOMPLETE")
        return pack(ACTION_REQUIRED, "Action required", reasons)
    if canon == "tenancy_agreement" and ta_text and _tenancy_action_required(ta_text):
        reasons.append("TENANCY_AGREEMENT_INCOMPLETE")
        return pack(ACTION_REQUIRED, "Action required", reasons)

    # --- VERIFIED (authority-backed current) ---
    if ea == EA_VERIFIED_CURRENT and not is_condition_standard:
        reasons.append("EA_VERIFIED_CURRENT")
        return pack(VERIFIED, "Verified", reasons)
    if not is_condition_standard and compliance_state == "VALID" and evidence_state == "VERIFIED":
        reasons.append("COMPLIANCE_VALID_VERIFIED")
        return pack(VERIFIED, "Verified", reasons)
    if not is_condition_standard and status in ("COMPLIANT", "VALID") and evidence_state == "VERIFIED":
        reasons.append("STATUS_SATISFIED_VERIFIED")
        return pack(VERIFIED, "Verified", reasons)

    # --- SATISFIED_UNVERIFIED (on file, not fully verified) ---
    if canon == "tenancy_agreement" and ta_text and not _tenancy_action_required(ta_text):
        reasons.append("TENANCY_AGREEMENT_ON_FILE")
        return pack(SATISFIED_UNVERIFIED, "Evidence recorded", reasons)
    if status in ("COMPLIANT", "VALID", "PENDING_VERIFICATION"):
        reasons.append(f"STATUS:{status}")
        return pack(SATISFIED_UNVERIFIED, "Evidence recorded", reasons)

    if status == "EXPIRING_SOON":
        reasons.append("STATUS_EXPIRING_SOON")
        if ea == EA_VERIFIED_CURRENT or evidence_state == "VERIFIED":
            return pack(VERIFIED, "Expiring soon", reasons)
        return pack(SATISFIED_UNVERIFIED, "Expiring soon", reasons)

    # --- Fallback from coarse status / evidence ---
    if status == "PENDING":
        has_doc = bool(row.get("evidence_doc_id") or str(row.get("document_id") or "").strip())
        if not has_doc and evidence_state in ("", "MISSING"):
            reasons.append("LEGACY_PENDING_NO_DOC")
            return pack(ACTION_REQUIRED, "Action required", reasons)
        if has_doc:
            reasons.append("LEGACY_PENDING_WITH_DOC")
            return pack(PENDING_REVIEW, "Awaiting review", reasons)
        reasons.append("LEGACY_PENDING")
        return pack(ACTION_REQUIRED, "Action required", reasons)

    if evidence_state == "UPLOADED_UNVERIFIED":
        reasons.append("EVIDENCE_UPLOADED_UNVERIFIED")
        return pack(SATISFIED_UNVERIFIED, "Evidence recorded", reasons)

    reasons.append("FALLBACK_UNKNOWN")
    return pack(ACTION_REQUIRED, "Action required", reasons)


def validate_client_lifecycle_state(value: str) -> bool:
    return _status_upper(value) in _CLIENT_LIFECYCLE_STATES
