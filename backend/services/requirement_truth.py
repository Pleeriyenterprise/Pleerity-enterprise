"""
Requirement truth model: separates system-estimated dates from user-provided and
verified-document-backed compliance data. Used for API presentation and scoring honesty.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from presentation.label_service import (
    compliance_requirement_status_label,
    requirement_label,
)
from services.compliance_requirement_engine import resolve_engine_payload_from_requirement_row
from services.compliance_evidence_record_service import effective_evidence_resolution
from services.requirement_action_resolver import (
    enrich_take_action_envelope_for_client,
    infer_action_type,
    resolve_take_action_envelope,
)
from services.compliance_registry_publish_service import fetch_active_published_registry_entries
from services.compliance_requirement_registry import (
    resolve_effective_why_it_matters,
    resolve_published_entry_for_requirement,
)
from services.requirement_code_registry import normalize_requirement_code
from services.requirement_evidence_authority import external_assessment_structured_followup_status
from services.requirement_workflow_audit import (
    apply_workflow_reference_audit,
    strip_workflow_diagnostics_from_payload,
)
from services.maintenance_issues_service import OPEN_ISSUE_STATUSES
from services.compliance_expiry_policy import get_default_expiring_soon_days

# --- Canonical enum values (stored on requirement documents and returned in APIs) ---

DATE_SOURCE_SYSTEM_ESTIMATED = "SYSTEM_ESTIMATED"
DATE_SOURCE_USER_PROVIDED = "USER_PROVIDED"
DATE_SOURCE_VERIFIED_DOCUMENT = "VERIFIED_DOCUMENT"

EVIDENCE_MISSING = "MISSING"
EVIDENCE_UPLOADED_UNVERIFIED = "UPLOADED_UNVERIFIED"
EVIDENCE_AWAITING_USER_CONFIRM = "AWAITING_USER_CONFIRM"
EVIDENCE_MISMATCH_FLAGGED = "MISMATCH_FLAGGED"
EVIDENCE_VERIFIED = "VERIFIED"

CONFIDENCE_ESTIMATED = "ESTIMATED"
CONFIDENCE_PARTIALLY_CONFIRMED = "PARTIALLY_CONFIRMED"
CONFIDENCE_VERIFIED = "VERIFIED"

ESTIMATED_NOTICE_TEXT = (
    "We've created estimated compliance dates based on standard regulatory cycles and your property setup. "
    "Upload your documents to confirm dates and improve accuracy."
)

ACTIVE_STANDARD_CODES = frozenset(
    {
        "fitness_for_human_habitation",
        "repairing_standard",
    }
)
ACTIVE_STANDARD_DISCLOSURE = (
    "This standard is monitored through property condition, open issues, remediation work, and audit history. "
    "A single uploaded document does not prove this standard is met."
)
ACTIVE_STANDARD_STATE_ACTIVE_ISSUES_PRESENT = "active_issues_present"
ACTIVE_STANDARD_STATE_REMEDIATION_IN_PROGRESS = "remediation_in_progress"
ACTIVE_STANDARD_STATE_OPEN_RISK_SIGNALS_PRESENT = "open_risk_signals_present"
ACTIVE_STANDARD_STATE_OPEN_COMPLIANCE_GAPS_PRESENT = "open_compliance_gaps_present"
ACTIVE_STANDARD_STATE_NO_OPEN_CONDITION_SIGNALS = "no_open_condition_signals"
ACTIVE_STANDARD_STATE_UNKNOWN = "unknown"

OPS_VERIFICATION_FAMILY_CONDITION_STANDARD = "CONDITION_STANDARD_ACTIVE_STANDARD"

_ACTIVE_STANDARD_STATE_LABELS: Dict[str, str] = {
    ACTIVE_STANDARD_STATE_ACTIVE_ISSUES_PRESENT: "Open remediation affecting property standard",
    ACTIVE_STANDARD_STATE_REMEDIATION_IN_PROGRESS: "Remediation in progress",
    ACTIVE_STANDARD_STATE_OPEN_RISK_SIGNALS_PRESENT: "Condition signals require review",
    ACTIVE_STANDARD_STATE_OPEN_COMPLIANCE_GAPS_PRESENT: "Condition status needs review",
    ACTIVE_STANDARD_STATE_NO_OPEN_CONDITION_SIGNALS: "Operational review in progress",
    ACTIVE_STANDARD_STATE_UNKNOWN: "Awaiting operational review",
}

_ACTIVE_STANDARD_FORBIDDEN_CLIENT_TERMS = frozenset(
    {
        "property standard verified",
        "fully compliant",
        "requirement satisfied",
        "standard confirmed",
        "verified and current",
    }
)


def _is_active_standard_code(raw_code: str) -> bool:
    canon = normalize_requirement_code(raw_code) or str(raw_code or "").strip().lower().replace(" ", "_")
    return canon in ACTIVE_STANDARD_CODES


def _derive_active_standard_state(signal_counts: Dict[str, int]) -> str:
    if not isinstance(signal_counts, dict):
        return ACTIVE_STANDARD_STATE_UNKNOWN
    issue_count = int(signal_counts.get("open_issues", 0) or 0)
    gap_count = int(signal_counts.get("open_compliance_gaps", 0) or 0)
    wo_count = int(signal_counts.get("open_work_orders", 0) or 0)
    risk_count = int(signal_counts.get("open_risk_signals", 0) or 0)
    if issue_count > 0:
        return ACTIVE_STANDARD_STATE_ACTIVE_ISSUES_PRESENT
    if gap_count > 0:
        return ACTIVE_STANDARD_STATE_OPEN_COMPLIANCE_GAPS_PRESENT
    if risk_count > 0:
        return ACTIVE_STANDARD_STATE_OPEN_RISK_SIGNALS_PRESENT
    if wo_count > 0:
        return ACTIVE_STANDARD_STATE_REMEDIATION_IN_PROGRESS
    if issue_count == 0 and gap_count == 0 and wo_count == 0 and risk_count == 0:
        return ACTIVE_STANDARD_STATE_NO_OPEN_CONDITION_SIGNALS
    return ACTIVE_STANDARD_STATE_UNKNOWN


def build_active_standard_status_summary(signal_counts: Dict[str, int]) -> Dict[str, Any]:
    """Read-model synthesis for condition-standard rows (property-scoped counts)."""
    counts = {
        "open_issues": int((signal_counts or {}).get("open_issues", 0) or 0),
        "open_work_orders": int((signal_counts or {}).get("open_work_orders", 0) or 0),
        "open_risk_signals": int((signal_counts or {}).get("open_risk_signals", 0) or 0),
        "open_compliance_gaps": int((signal_counts or {}).get("open_compliance_gaps", 0) or 0),
    }
    state = _derive_active_standard_state(counts)
    return {
        "state": state,
        "state_label": _ACTIVE_STANDARD_STATE_LABELS.get(state, "Awaiting operational review"),
        "signal_counts": counts,
        "ops_verification_family": OPS_VERIFICATION_FAMILY_CONDITION_STANDARD,
        "read_only": True,
    }


def _active_standard_has_unresolved_operational_state(summary: Dict[str, Any]) -> bool:
    if not isinstance(summary, dict):
        return True
    state = str(summary.get("state") or "").strip().lower()
    if state in ("", ACTIVE_STANDARD_STATE_UNKNOWN):
        return True
    signals = summary.get("signal_counts") if isinstance(summary.get("signal_counts"), dict) else {}
    return any(
        int(signals.get(k) or 0) > 0 for k in ("open_issues", "open_work_orders", "open_risk_signals", "open_compliance_gaps")
    )


def _active_standard_runtime_copy(summary: Dict[str, Any], has_supporting_evidence: bool) -> Tuple[str, str]:
    state = str(summary.get("state") or "").strip().lower()
    state_label = str(summary.get("state_label") or "").strip()
    if state_label and state_label.lower() not in _ACTIVE_STANDARD_FORBIDDEN_CLIENT_TERMS:
        status_label = state_label
    elif _active_standard_has_unresolved_operational_state(summary):
        if state == ACTIVE_STANDARD_STATE_REMEDIATION_IN_PROGRESS:
            status_label = "Remediation in progress"
        elif state == ACTIVE_STANDARD_STATE_OPEN_RISK_SIGNALS_PRESENT:
            status_label = "Condition signals require review"
        elif state == ACTIVE_STANDARD_STATE_OPEN_COMPLIANCE_GAPS_PRESENT:
            status_label = "Condition status needs review"
        else:
            status_label = "Open remediation affecting property standard"
    else:
        status_label = "Operational review in progress"
    if has_supporting_evidence:
        return (status_label, "Supporting evidence on file")
    if _active_standard_has_unresolved_operational_state(summary):
        return (status_label, "Operational follow-up required")
    return (status_label, "Awaiting operational review")


def _multi_evidence_runtime_copy(is_complete: bool, has_uploaded_component: bool) -> Tuple[str, str]:
    if is_complete:
        return ("Evidence components complete", "Evidence complete")
    if has_uploaded_component:
        return ("Required evidence incomplete", "Partial evidence recorded")
    return ("Additional evidence still required", "Further evidence required before completion")


async def _load_active_standard_signal_summary_by_property(
    db,
    client_id: str,
    property_ids: List[str],
) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for pid in [str(x or "").strip() for x in property_ids if str(x or "").strip()]:
        open_issues = int(
            await db.maintenance_issues.count_documents(
                {"client_id": client_id, "property_id": pid, "status": {"$in": list(OPEN_ISSUE_STATUSES)}}
            )
        )
        open_work_orders = int(
            await db.work_orders.count_documents(
                {
                    "client_id": client_id,
                    "property_id": pid,
                    "status": {"$nin": ["completed", "closed", "cancelled", "COMPLETED", "CLOSED", "CANCELLED"]},
                }
            )
        )
        open_risk_signals = int(
            await db.risk_signals.count_documents(
                {
                    "client_id": client_id,
                    "property_id": pid,
                    "status": {"$nin": ["resolved", "RESOLVED"]},
                }
            )
        )
        open_compliance_gaps = int(
            await db.compliance_gaps.count_documents(
                {"client_id": client_id, "property_id": pid, "status": "open"}
            )
        )
        signal_counts = {
            "open_issues": open_issues,
            "open_work_orders": open_work_orders,
            "open_risk_signals": open_risk_signals,
            "open_compliance_gaps": open_compliance_gaps,
        }
        out[pid] = {
            "state": _derive_active_standard_state(signal_counts),
            "signal_counts": signal_counts,
            "read_only": True,
        }
    return out


def _status_upper(st: Optional[str]) -> str:
    return (st or "").strip().upper()


def _truthy_yes(v: Any) -> bool:
    return str(v or "").strip().lower() in {"yes", "true", "1", "y"}


def _structured_answer(structured_fields: Dict[str, Any], field_id: str) -> Any:
    if not isinstance(structured_fields, dict):
        return None
    node = structured_fields.get(field_id)
    if isinstance(node, dict):
        return node.get("answer")
    return None


def _derive_tenancy_agreement_status_text(records: List[Dict[str, Any]]) -> str:
    active = [r for r in (records or []) if str(r.get("status") or "").strip().upper() not in {"REJECTED", "ARCHIVED"}]
    has_upload = any(str(r.get("evidence_mode") or "").strip().upper() == "DOCUMENT_UPLOAD" for r in active)
    structured = [
        r
        for r in active
        if str(r.get("evidence_mode") or "").strip().upper() == "STRUCTURED_DECLARATION"
    ]
    if not structured:
        return "Agreement not recorded — action required"
    latest = structured[0]
    payload = latest.get("evidence_payload") if isinstance(latest.get("evidence_payload"), dict) else {}
    fields = payload.get("structured_fields") if isinstance(payload.get("structured_fields"), dict) else {}
    if not _truthy_yes(_structured_answer(fields, "agreement_exists")):
        return "Agreement not recorded — action required"
    if not has_upload:
        return "Supporting agreement not uploaded"
    if _truthy_yes(_structured_answer(fields, "signed_by_parties")):
        return "Agreement recorded — signed"
    return "Agreement recorded — unsigned"


def evidence_state_from_document_statuses(statuses: List[str]) -> str:
    """Aggregate document statuses for one requirement_id (status strings only; legacy callers)."""
    if not statuses:
        return EVIDENCE_MISSING
    up = [_status_upper(s) for s in statuses]
    if any(s == "VERIFIED" for s in up):
        return EVIDENCE_VERIFIED
    if any(s not in ("REJECTED", "EXPIRED", "") for s in up):
        return EVIDENCE_UPLOADED_UNVERIFIED
    return EVIDENCE_MISSING


def _extraction_review_is_approved(review_status: Optional[str]) -> bool:
    return _status_upper(review_status or "") in ("APPROVED", "APPROVE")


def evidence_state_from_documents(docs: List[Dict[str, Any]]) -> str:
    """
    Aggregate evidence for one requirement_id using document rows (status + extraction + mismatch flags).
    Precedence: verified evidence wins; then mismatch; then awaiting user confirmation on extracted uploads;
    then generic uploaded-unverified; missing only when nothing counts.
    """
    if not docs:
        return EVIDENCE_MISSING
    statuses = [_status_upper(d.get("status")) for d in docs]
    if any(s == "VERIFIED" for s in statuses):
        return EVIDENCE_VERIFIED

    active = [
        d
        for d in docs
        if _status_upper(d.get("status")) not in ("REJECTED", "EXPIRED", "")
    ]
    if not active:
        return EVIDENCE_MISSING

    if any(d.get("requirement_evidence_mismatch") is True for d in active):
        return EVIDENCE_MISMATCH_FLAGGED
    mo_bad = {"MISMATCH_SUSPECTED", "NEEDS_ADMIN_REVIEW", "UNKNOWN_TYPE"}
    if any(str(d.get("match_outcome") or "").strip() in mo_bad for d in active):
        return EVIDENCE_MISMATCH_FLAGGED

    for d in active:
        if _status_upper(d.get("status")) != "UPLOADED":
            continue
        ai = d.get("ai_extraction") if isinstance(d.get("ai_extraction"), dict) else {}
        if _status_upper(ai.get("status")) == "COMPLETED" and not _extraction_review_is_approved(ai.get("review_status")):
            return EVIDENCE_AWAITING_USER_CONFIRM

    return EVIDENCE_UPLOADED_UNVERIFIED


async def load_evidence_state_by_requirement_id(
    db,
    client_id: str,
    requirement_ids: List[str],
) -> Dict[str, str]:
    """Map requirement_id -> EVIDENCE_* from documents collection."""
    if not requirement_ids:
        return {}
    cursor = db.documents.find(
        {"client_id": client_id, "requirement_id": {"$in": requirement_ids}},
        {
            "_id": 0,
            "requirement_id": 1,
            "status": 1,
            "ai_extraction": 1,
            "requirement_evidence_mismatch": 1,
            "match_outcome": 1,
        },
    )
    by_rid: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    async for doc in cursor:
        rid = doc.get("requirement_id")
        if not rid:
            continue
        by_rid.setdefault(str(rid), []).append(doc)
    return {rid: evidence_state_from_documents(lst) for rid, lst in by_rid.items()}


async def load_linked_primary_documents_for_client_requirements(
    db,
    client_id: str,
    requirements: List[Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    """
    Map requirement_id -> primary linked document row (for Evidence Review V2 + lifecycle).
    Uses evidence_doc_id, then document_id, when set on the requirement row.
    """
    rid_to_doc_id: Dict[str, str] = {}
    for r in requirements or []:
        rid = r.get("requirement_id")
        if not rid:
            continue
        did = str(r.get("evidence_doc_id") or r.get("document_id") or "").strip()
        if did:
            rid_to_doc_id[str(rid)] = did
    if not rid_to_doc_id:
        return {}
    doc_ids = list({v for v in rid_to_doc_id.values() if v})
    cursor = db.documents.find(
        {"client_id": client_id, "document_id": {"$in": doc_ids}},
        {
            "_id": 0,
            "document_id": 1,
            "status": 1,
            "evidence_review_state": 1,
            "review_required": 1,
            "assurance_tier": 1,
        },
    )
    by_doc_id: Dict[str, Dict[str, Any]] = {}
    async for d in cursor:
        did = str(d.get("document_id") or "").strip()
        if did:
            by_doc_id[did] = d
    out: Dict[str, Dict[str, Any]] = {}
    for rid, did in rid_to_doc_id.items():
        doc = by_doc_id.get(did)
        if doc:
            out[rid] = doc
    return out


def infer_date_source(requirement: Dict[str, Any], evidence_state: str) -> str:
    """
    Derive date_source from expiry_source + verification state.
    Verified evidence always wins: document-backed truth for the active date.
    """
    if evidence_state == EVIDENCE_VERIFIED:
        return DATE_SOURCE_VERIFIED_DOCUMENT

    expiry_source = _status_upper(requirement.get("expiry_source") or "NONE")
    if expiry_source == "CONFIRMED":
        return DATE_SOURCE_USER_PROVIDED
    if expiry_source == "EXTRACTED":
        return DATE_SOURCE_USER_PROVIDED

    stored = _status_upper(requirement.get("date_source"))
    if stored in (DATE_SOURCE_USER_PROVIDED, DATE_SOURCE_SYSTEM_ESTIMATED):
        return stored

    return DATE_SOURCE_SYSTEM_ESTIMATED


def infer_confidence_state(date_source: str, evidence_state: str) -> str:
    if date_source == DATE_SOURCE_VERIFIED_DOCUMENT and evidence_state == EVIDENCE_VERIFIED:
        return CONFIDENCE_VERIFIED
    if date_source == DATE_SOURCE_SYSTEM_ESTIMATED:
        return CONFIDENCE_ESTIMATED
    return CONFIDENCE_PARTIALLY_CONFIRMED


def resolve_truth_triple(
    requirement: Dict[str, Any],
    live_evidence_state: str,
) -> Tuple[str, str, str]:
    """Live document evidence overrides stored evidence_state."""
    date_source = infer_date_source(requirement, live_evidence_state)
    confidence = infer_confidence_state(date_source, live_evidence_state)
    return date_source, live_evidence_state, confidence


def _parse_due_date_value(due: Any) -> Optional[date]:
    if due is None:
        return None
    try:
        if isinstance(due, datetime):
            return due.date() if due.tzinfo else due.replace(tzinfo=timezone.utc).date()
        if isinstance(due, date):
            return due
        s = str(due).replace("Z", "+00:00")
        return datetime.fromisoformat(s).date()
    except Exception:
        return None


def _format_gb_date(d: date) -> str:
    months = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
    return f"{d.day} {months[d.month - 1]} {d.year}"


def requirement_has_active_negative_actionability(
    requirement: Dict[str, Any],
    *,
    now: Optional[datetime] = None,
    expiring_window_days: Optional[int] = None,
) -> bool:
    """
    Read-model lifecycle predicate (not a scoring/status authority):
    True only when a requirement row has active negative actionability for
    Needs Attention / Today / Score Drivers surfaces.
    """
    row = dict(requirement or {})
    status = _status_upper(row.get("status"))
    if status in {"OVERDUE", "EXPIRED", "MISSING", "MISSING_EVIDENCE", "NEEDS_REVIEW"}:
        return True
    if status in {"PENDING", "EXPIRING_SOON", "AWAITING_USER_CONFIRM", "INCOMPLETE"}:
        return True

    ev = _status_upper(row.get("evidence_state"))
    if ev in {"MISSING", "AWAITING_USER_CONFIRM", "MISMATCH_FLAGGED", "UPLOADED_UNVERIFIED"}:
        return True

    comp = row.get("evidence_completeness") if isinstance(row.get("evidence_completeness"), dict) else {}
    try:
        if int(comp.get("required_missing_count") or 0) > 0:
            return True
    except Exception:
        pass
    try:
        if float(comp.get("completion_percent") or 100.0) < 100.0:
            return True
    except Exception:
        pass

    active_summary = row.get("active_standard_status_summary") if isinstance(row.get("active_standard_status_summary"), dict) else {}
    signals = active_summary.get("signal_counts") if isinstance(active_summary.get("signal_counts"), dict) else {}
    if any(int(signals.get(k) or 0) > 0 for k in ("open_issues", "open_work_orders", "open_risk_signals", "open_compliance_gaps")):
        return True

    if status in {"VALID", "COMPLIANT", "VERIFIED", "NOT_REQUIRED", "NOT_APPLICABLE", "RESOLVED"}:
        window = int(expiring_window_days if expiring_window_days is not None else get_default_expiring_soon_days())
        ref = now or datetime.now(timezone.utc)
        for key in ("due_date", "expiry_date", "follow_up_date", "next_review_date"):
            dt = _parse_due_date_value(row.get(key))
            if dt is None:
                continue
            days = (dt - ref.date()).days
            if 0 <= days <= window:
                return True
        return False

    return False


def build_date_presentation(
    requirement: Dict[str, Any],
    date_source: str,
    evidence_state: str,
) -> Tuple[str, Optional[str]]:
    """
    Returns (date_label, helper_text) for client-facing surfaces.
    """
    due_raw = requirement.get("due_date") or requirement.get("confirmed_expiry_date") or requirement.get("extracted_expiry_date")
    d = _parse_due_date_value(due_raw)
    formatted = _format_gb_date(d) if d else None

    if evidence_state == EVIDENCE_MISMATCH_FLAGGED:
        return (
            f"Review required — date on file: {formatted}" if formatted else "Review required — possible wrong document for this requirement",
            "The uploaded file does not look like the expected certificate type for this requirement. Upload the correct evidence or correct the extracted type and apply.",
        )
    if evidence_state == EVIDENCE_AWAITING_USER_CONFIRM:
        if formatted:
            return (
                f"Extracted date (not yet applied): {formatted}",
                "Confirm extracted details in Documents before your compliance score treats this certificate as final evidence.",
            )
        return (
            "Awaiting your confirmation",
            "Open Documents, review extracted dates, and apply them so renewals and scores update.",
        )

    if not formatted:
        if date_source == DATE_SOURCE_SYSTEM_ESTIMATED:
            return (
                "Due date estimated — upload your certificate to confirm",
                "Estimated from standard compliance cycles and your property setup.",
            )
        return ("No due date on file yet", "Upload your certificate or enter a date to track this item.")

    if date_source == DATE_SOURCE_SYSTEM_ESTIMATED:
        return (
            f"Estimated renewal date: {formatted}",
            "Estimated from standard compliance cycles and your property setup. Upload your certificate to confirm this date.",
        )

    if date_source == DATE_SOURCE_USER_PROVIDED:
        if evidence_state == EVIDENCE_VERIFIED:
            return (f"Next due: {formatted}", None)
        return (
            f"Planned renewal: {formatted}",
            "You entered this date or it came from an uploaded file — upload and verify your certificate to confirm it.",
        )

    # VERIFIED_DOCUMENT
    return (f"Next due: {formatted}", None)


def evidence_badge_label(evidence_state: str) -> str:
    if evidence_state == EVIDENCE_VERIFIED:
        return "Verified"
    if evidence_state == EVIDENCE_MISMATCH_FLAGGED:
        return "Possible wrong document (review required)"
    if evidence_state == EVIDENCE_AWAITING_USER_CONFIRM:
        return "Extracted — confirm dates to apply"
    if evidence_state == EVIDENCE_UPLOADED_UNVERIFIED:
        return "Uploaded (processing or awaiting verification)"
    return "Not uploaded"


def enrich_requirement_dict(
    requirement: Dict[str, Any],
    live_evidence_state: str,
    *,
    audience: str = "client",
    published_registry_entries: Optional[Dict[str, Any]] = None,
    property_doc: Optional[Dict[str, Any]] = None,
    compliance_evidence_records: Optional[List[Dict[str, Any]]] = None,
    linked_primary_document: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Mutates a shallow copy: adds presentation + truth fields. Keeps all original keys.

    Workflow drift diagnostics (``workflow_class_reference``, ``workflow_mismatch_*``) are
    attached only when ``audience == "admin"``; client surfaces never receive them.
    """
    out = dict(requirement)
    ea_blob = out.get("evidence_authority") if isinstance(out.get("evidence_authority"), dict) else {}
    if ea_blob.get("semantic_state") is not None:
        out["semantic_state"] = ea_blob.get("semantic_state")
    _raw_code = str(out.get("requirement_code") or out.get("requirement_type") or "").strip()
    _canon = normalize_requirement_code(_raw_code)
    _is_active_standard = _is_active_standard_code(_raw_code)
    if _canon:
        out["canonical_requirement_code"] = _canon
    code = out.get("requirement_code") or out.get("requirement_type") or ""
    _label_code = _canon or code
    date_source, evidence_state, confidence_state = resolve_truth_triple(out, live_evidence_state)
    out["date_source"] = date_source
    out["evidence_state"] = evidence_state
    out["confidence_state"] = confidence_state

    status_raw = (out.get("status") or "").strip().upper()
    out["display_label"] = requirement_label(_label_code, audience=audience)
    out["status_label"] = compliance_requirement_status_label(status_raw, audience=audience)
    date_label, helper = build_date_presentation(out, date_source, evidence_state)
    out["date_label"] = date_label
    out["date_explanation_helper"] = helper

    out["evidence_badge_label"] = evidence_badge_label(evidence_state)

    published_entry = resolve_published_entry_for_requirement(
        published_registry_entries=published_registry_entries,
        requirement_type=str(out.get("requirement_type") or out.get("requirement_code") or ""),
        portfolio_label=str(out.get("jurisdiction") or ""),
        property_doc=property_doc,
        # Read-time payloads should resolve published copy for already emitted rows even when
        # draft conditions depend on fields that are not persisted on property documents.
        enforce_conditions=False,
    )
    witm = resolve_effective_why_it_matters(entry=published_entry, portfolio_label=str(out.get("jurisdiction") or ""))
    out["why_it_matters_short"] = witm.get("why_it_matters_short")
    out["why_it_matters_long"] = witm.get("why_it_matters_long")
    if isinstance(published_entry, dict):
        meta = out.get("registry_metadata") if isinstance(out.get("registry_metadata"), dict) else {}
        if isinstance(published_entry.get("action_links"), list):
            from services.requirement_action_links import filter_action_links_for_region, portfolio_label_to_region

            region = portfolio_label_to_region(str(out.get("jurisdiction") or ""))
            raw_links = [dict(x) for x in published_entry.get("action_links") if isinstance(x, dict)]
            meta["action_links_published"] = filter_action_links_for_region(raw_links, region, max_links=24)
        if isinstance(published_entry.get("why_it_matters_by_jurisdiction"), dict):
            meta["why_it_matters_by_jurisdiction_published"] = published_entry.get("why_it_matters_by_jurisdiction")
        if witm.get("why_it_matters_short"):
            meta["why_it_matters_short_published"] = witm.get("why_it_matters_short")
        if witm.get("why_it_matters_long"):
            meta["why_it_matters_long_published"] = witm.get("why_it_matters_long")
        er_pub = published_entry.get("evidence_resolution")
        if isinstance(er_pub, dict) and er_pub:
            prior_er = meta.get("evidence_resolution") if isinstance(meta.get("evidence_resolution"), dict) else {}
            meta["evidence_resolution"] = {**prior_er, **er_pub}
        out["registry_metadata"] = meta

    app = _status_upper(out.get("applicability"))
    if app == "NOT_REQUIRED" or status_raw == "NOT_REQUIRED":
        out["show_estimated_date_copy"] = False
    else:
        out["show_estimated_date_copy"] = date_source == DATE_SOURCE_SYSTEM_ESTIMATED

    eng = resolve_engine_payload_from_requirement_row(out)
    out.update(eng)

    out["action_type"] = infer_action_type(out)
    env_client = enrich_take_action_envelope_for_client(
        resolve_take_action_envelope(
            out,
            property_id=out.get("property_id"),
            property_jurisdiction=out.get("jurisdiction"),
        ),
        out,
    )
    take = env_client.get("take_action")
    out["take_action"] = take
    out["action_links"] = list((take or {}).get("supporting_external_links") or [])
    for k in ("workflow_class", "guidance_target", "allowed_evidence_modes"):
        if env_client.get(k) is not None:
            out[k] = env_client[k]

    if (audience or "client").strip().lower() != "admin":
        _ced = str(effective_evidence_resolution(out).get("client_evidence_disclosure") or "").strip()
        if _ced:
            out["client_evidence_disclosure"] = _ced
        if _is_active_standard:
            out["client_evidence_disclosure"] = ACTIVE_STANDARD_DISCLOSURE

    from services.requirement_evidence_completeness import (
        evaluate_domestic_alarm_completeness,
        project_evidence_completeness_for_client,
    )

    if _canon == "smoke_heat_alarms":
        comp_eval = evaluate_domestic_alarm_completeness(
            out,
            property_doc,
            compliance_evidence_records if compliance_evidence_records is not None else [],
        )
        if (audience or "client").strip().lower() == "admin":
            out["evidence_completeness"] = comp_eval
        else:
            out["evidence_completeness"] = project_evidence_completeness_for_client(comp_eval)
        runtime_status_label, runtime_evidence_badge = _multi_evidence_runtime_copy(
            is_complete=bool(comp_eval.get("is_complete")),
            has_uploaded_component=bool((comp_eval.get("signals_detected") or {}).get("smoke_alarm_records") or 0)
            or bool((comp_eval.get("signals_detected") or {}).get("co_alarm_records") or 0),
        )
        if not bool(comp_eval.get("is_complete")):
            # Multi-evidence rows stay action-needed until required components are complete.
            out["status_label"] = runtime_status_label
            out["evidence_badge_label"] = runtime_evidence_badge
    else:
        out["evidence_completeness"] = None

    if _canon in ("legionella", "lead_testing"):
        pol = effective_evidence_resolution(out)
        fu_status = external_assessment_structured_followup_status(
            out,
            compliance_evidence_records if compliance_evidence_records is not None else [],
            evidence_policy=pol,
        )
        if fu_status is True or fu_status is None:
            if (audience or "client").strip().lower() != "admin":
                out["status_label"] = "Assessment recorded — follow-up required"
                out["evidence_badge_label"] = "Remediation or follow-up may remain open"

    if _canon == "tenancy_agreement":
        out["tenancy_agreement_status_text"] = _derive_tenancy_agreement_status_text(
            compliance_evidence_records if compliance_evidence_records is not None else []
        )

    _wc_upper = str(out.get("workflow_class") or "").strip().upper()
    _audience_lower = (audience or "client").strip().lower()
    if _wc_upper == "GUIDED_DECLARATION" and _audience_lower != "admin":
        recs = compliance_evidence_records if compliance_evidence_records is not None else []
        active_recs = [
            r
            for r in recs
            if str(r.get("archived") or "").lower() not in ("true", "1")
            and str(r.get("status") or "").upper() not in ("REJECTED", "ARCHIVED")
        ]
        if active_recs:
            skip_declaration_wording = False
            if _canon == "tenancy_agreement":
                ta_txt = _derive_tenancy_agreement_status_text(recs)
                ta_lower = ta_txt.lower()
                # Only skip when no declaration of agreement exists; "supporting … not uploaded" still means a declaration was recorded.
                if "agreement not recorded" in ta_lower or "action required" in ta_lower:
                    skip_declaration_wording = True
            if not skip_declaration_wording:
                out["status_label"] = "Declaration recorded"
                out["evidence_badge_label"] = "Supporting evidence on file — not externally verified"

    if _wc_upper == "REGISTRATION_TRACKING" and _audience_lower != "admin":
        recs = compliance_evidence_records if compliance_evidence_records is not None else []
        active_recs = [
            r
            for r in recs
            if str(r.get("archived") or "").lower() not in ("true", "1")
            and str(r.get("status") or "").upper() not in ("REJECTED", "ARCHIVED")
        ]
        if active_recs:
            out["status_label"] = "Registration details recorded"
            out["evidence_badge_label"] = "Authority confirmation not verified externally"

    if _wc_upper == "TENANT_DELIVERY" and _audience_lower != "admin":
        recs = compliance_evidence_records if compliance_evidence_records is not None else []
        active_recs = [
            r
            for r in recs
            if str(r.get("archived") or "").lower() not in ("true", "1")
            and str(r.get("status") or "").upper() not in ("REJECTED", "ARCHIVED")
        ]
        if active_recs:
            out["status_label"] = "Delivery recorded"
            out["evidence_badge_label"] = "Tenant receipt not independently confirmed"

    _ea_blob = out.get("evidence_authority") if isinstance(out.get("evidence_authority"), dict) else {}
    _ea_sr = str(_ea_blob.get("state_reason") or "")
    if (
        _wc_upper in ("DOCUMENT_UPLOAD", "LEGACY_DOCUMENT_UPLOAD")
        and _audience_lower != "admin"
        and _ea_sr == "document_upload_missing_required_expiry_semantics"
    ):
        out["status_label"] = "Certificate on file — expiry review required"
        out["evidence_badge_label"] = "Current validity not confirmed"

    if _is_active_standard:
        out["workflow_family"] = OPS_VERIFICATION_FAMILY_CONDITION_STANDARD
        out["ops_verification_family"] = OPS_VERIFICATION_FAMILY_CONDITION_STANDARD
        summary = out.get("active_standard_status_summary")
        if not isinstance(summary, dict):
            summary = build_active_standard_status_summary({})
            out["active_standard_status_summary"] = summary
        summary["read_only"] = True
        runtime_status_label, runtime_evidence_badge = _active_standard_runtime_copy(
            summary,
            has_supporting_evidence=evidence_state in (
                EVIDENCE_VERIFIED,
                EVIDENCE_UPLOADED_UNVERIFIED,
                EVIDENCE_AWAITING_USER_CONFIRM,
            ),
        )
        # Condition standards are operational-convergence workflows: uploads are supporting, not closure semantics.
        out["status_label"] = runtime_status_label
        out["evidence_badge_label"] = runtime_evidence_badge
        if _status_upper(out.get("status")) in ("COMPLIANT", "VALID") and _active_standard_has_unresolved_operational_state(
            summary
        ):
            out["status"] = "PENDING"
            out["status_label"] = runtime_status_label

    aud = (audience or "client").strip().lower()
    if aud == "admin":
        s_stored = str(requirement.get("requirement_code") or requirement.get("requirement_type") or "").strip()
        if s_stored:
            out["requirement_code_stored"] = s_stored
        apply_workflow_reference_audit(
            out,
            published_entry=published_entry if isinstance(published_entry, dict) else None,
        )
    else:
        strip_workflow_diagnostics_from_payload(out)
        from presentation.requirement_display_contract import build_requirement_display

        out["requirement_display"] = build_requirement_display(out, audience=audience)
        from services.client_requirement_lifecycle import derive_client_lifecycle_fields

        out.update(derive_client_lifecycle_fields(out, linked_primary_document=linked_primary_document))
        if not str(out.get("document_id") or "").strip() and str(out.get("evidence_doc_id") or "").strip():
            out["document_id"] = str(out.get("evidence_doc_id")).strip()

    return out


def should_show_compliance_estimates_notice(enriched_requirements: List[Dict[str, Any]]) -> bool:
    """True when any applicable row still relies on system-estimated dates."""
    for r in enriched_requirements:
        app = _status_upper(r.get("applicability"))
        if app == "NOT_REQUIRED" or (r.get("status") or "").upper() == "NOT_REQUIRED":
            continue
        if r.get("confidence_state") == CONFIDENCE_ESTIMATED:
            return True
    return False


def build_presentation_meta(enriched_requirements: List[Dict[str, Any]]) -> Dict[str, Any]:
    show = should_show_compliance_estimates_notice(enriched_requirements)
    return {
        "show_compliance_estimates_notice": show,
        "compliance_estimates_notice_text": ESTIMATED_NOTICE_TEXT if show else None,
    }


async def enrich_requirements_for_client(
    db,
    client_id: str,
    requirements: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    from services.client_applicability_coherence import (
        apply_client_applicability_presentation_overlay,
        refresh_stale_authority_for_client_requirements,
    )
    from services.compliance_rules_registry import portfolio_jurisdiction_label

    requirements = await refresh_stale_authority_for_client_requirements(db, requirements)

    ids = [r["requirement_id"] for r in requirements if r.get("requirement_id")]
    evidence_map = await load_evidence_state_by_requirement_id(db, client_id, ids)
    published_entries = await fetch_active_published_registry_entries(db)

    client_doc = await db.clients.find_one({"client_id": client_id}, {"_id": 0, "default_jurisdiction": 1})
    prop_ids = list({str(r.get("property_id") or "") for r in requirements if r.get("property_id")})
    jur_by_prop: Dict[str, str] = {}
    if prop_ids:
        cur = db.properties.find(
            {"client_id": client_id, "property_id": {"$in": prop_ids}},
            {"_id": 0, "property_id": 1, "jurisdiction": 1},
        )
        async for p in cur:
            pid = p.get("property_id")
            if pid:
                jur_by_prop[str(pid)] = portfolio_jurisdiction_label(p, client_doc or {})

    props_full: Dict[str, Dict[str, Any]] = {}
    if prop_ids:
        cur2 = db.properties.find(
            {"client_id": client_id, "property_id": {"$in": prop_ids}},
            {"_id": 0},
        )
        async for p in cur2:
            pid = p.get("property_id")
            if pid:
                props_full[str(pid)] = p
    active_standard_props = {
        str(r.get("property_id") or "")
        for r in requirements
        if _is_active_standard_code(str(r.get("requirement_code") or r.get("requirement_type") or ""))
        and str(r.get("property_id") or "").strip()
    }
    active_summary_by_prop = await _load_active_standard_signal_summary_by_property(
        db,
        client_id=client_id,
        property_ids=sorted(active_standard_props),
    ) if active_standard_props else {}

    evidence_rids = [
        str(r["requirement_id"])
        for r in requirements
        if r.get("requirement_id")
        and normalize_requirement_code(
            str(r.get("requirement_code") or r.get("requirement_type") or "").strip()
        )
        in {"smoke_heat_alarms", "tenancy_agreement"}
    ]
    cer_by_rid: Dict[str, List[Dict[str, Any]]] = {}
    if evidence_rids:
        from services.compliance_evidence_record_service import batch_list_evidence_records_for_requirements

        cer_by_rid = await batch_list_evidence_records_for_requirements(
            db, client_id=client_id, requirement_ids=evidence_rids
        )

    linked_by_rid = await load_linked_primary_documents_for_client_requirements(db, client_id, requirements)

    enriched = []
    for r in requirements:
        rid = r.get("requirement_id")
        ev = evidence_map.get(rid, EVIDENCE_MISSING)
        rc = dict(r)
        if not (str(rc.get("jurisdiction") or "").strip()):
            pid = rc.get("property_id")
            if pid and str(pid) in jur_by_prop:
                rc["jurisdiction"] = jur_by_prop[str(pid)]
        _cer = cer_by_rid.get(str(rid), []) if rid else []
        pid = str(rc.get("property_id") or "").strip()
        if pid and _is_active_standard_code(str(rc.get("requirement_code") or rc.get("requirement_type") or "")):
            rc["active_standard_status_summary"] = active_summary_by_prop.get(
                pid,
                {"state": ACTIVE_STANDARD_STATE_UNKNOWN, "signal_counts": {}, "read_only": True},
            )
        enriched.append(
            apply_client_applicability_presentation_overlay(
                enrich_requirement_dict(
                    rc,
                    ev,
                    audience="client",
                    published_registry_entries=published_entries,
                    property_doc=props_full.get(str(rc.get("property_id") or "")),
                    compliance_evidence_records=_cer,
                    linked_primary_document=linked_by_rid.get(str(rid)) if rid else None,
                )
            )
        )
    return enriched, build_presentation_meta(enriched)


async def enrich_requirements_for_admin(
    db,
    requirements: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Batch presentation + truth fields for admin APIs (may span multiple clients).
    Uses admin-facing status labels; keeps raw requirement_type / requirement_code for filters.
    """
    if not requirements:
        return []

    by_client: Dict[str, List[str]] = defaultdict(list)
    seen_pairs: set = set()
    published_entries = await fetch_active_published_registry_entries(db)
    for r in requirements:
        cid = r.get("client_id")
        rid = r.get("requirement_id")
        if cid and rid:
            key = (cid, rid)
            if key not in seen_pairs:
                seen_pairs.add(key)
                by_client[cid].append(rid)

    evidence_nested: Dict[str, Dict[str, str]] = {}
    for cid, ids in by_client.items():
        evidence_nested[cid] = await load_evidence_state_by_requirement_id(db, cid, ids)

    from services.compliance_rules_registry import portfolio_jurisdiction_label

    by_client_props: Dict[str, Dict[str, str]] = defaultdict(dict)
    client_docs: Dict[str, Any] = {}
    for r in requirements:
        cid = r.get("client_id")
        pid = r.get("property_id")
        if cid and pid:
            by_client_props[str(cid)][str(pid)] = ""

    for cid, pmap in by_client_props.items():
        client_docs[cid] = await db.clients.find_one({"client_id": cid}, {"_id": 0, "default_jurisdiction": 1})
        pids = list(pmap.keys())
        cur = db.properties.find(
            {"client_id": cid, "property_id": {"$in": pids}},
            {"_id": 0, "property_id": 1, "jurisdiction": 1},
        )
        async for p in cur:
            pid = p.get("property_id")
            if pid:
                by_client_props[cid][str(pid)] = portfolio_jurisdiction_label(p, client_docs.get(cid) or {})

    props_full_by_key: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for cid, pmap in by_client_props.items():
        pids = list(pmap.keys())
        cur_full = db.properties.find({"client_id": cid, "property_id": {"$in": pids}}, {"_id": 0})
        async for p in cur_full:
            pid = p.get("property_id")
            if pid:
                props_full_by_key[(str(cid), str(pid))] = p
    active_props_by_client: Dict[str, set[str]] = defaultdict(set)
    for r in requirements:
        cid = str(r.get("client_id") or "").strip()
        pid = str(r.get("property_id") or "").strip()
        code = str(r.get("requirement_code") or r.get("requirement_type") or "")
        if cid and pid and _is_active_standard_code(code):
            active_props_by_client[cid].add(pid)
    active_summary_by_client_prop: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for cid, pids in active_props_by_client.items():
        rows = await _load_active_standard_signal_summary_by_property(
            db,
            client_id=cid,
            property_ids=sorted(pids),
        )
        for pid, summary in rows.items():
            active_summary_by_client_prop[(cid, pid)] = summary

    evidence_by_client: Dict[str, List[str]] = defaultdict(list)
    for r in requirements:
        cid = r.get("client_id")
        rid = r.get("requirement_id")
        code = str(r.get("requirement_code") or r.get("requirement_type") or "").strip()
        if cid and rid and normalize_requirement_code(code) in {"smoke_heat_alarms", "tenancy_agreement"}:
            evidence_by_client[str(cid)].append(str(rid))

    cer_by_client_rid: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
    if evidence_by_client:
        from services.compliance_evidence_record_service import batch_list_evidence_records_for_requirements

        for cid, rids in evidence_by_client.items():
            cer_by_client_rid[cid] = await batch_list_evidence_records_for_requirements(
                db, client_id=cid, requirement_ids=rids
            )

    out: List[Dict[str, Any]] = []
    for r in requirements:
        cid = r.get("client_id")
        rid = r.get("requirement_id")
        if cid and rid:
            ev = evidence_nested.get(cid, {}).get(rid, EVIDENCE_MISSING)
        else:
            ev = EVIDENCE_MISSING
        rc = dict(r)
        if cid and r.get("property_id") and not (str(rc.get("jurisdiction") or "").strip()):
            jl = by_client_props.get(str(cid), {}).get(str(r.get("property_id")), "")
            if jl:
                rc["jurisdiction"] = jl
        cid_s = str(cid or "")
        pid_s = str(r.get("property_id") or "")
        _prop_doc = props_full_by_key.get((cid_s, pid_s)) if cid_s and pid_s else None
        _cer = cer_by_client_rid.get(cid_s, {}).get(str(rid), []) if cid_s and rid else []
        if cid_s and pid_s and _is_active_standard_code(str(rc.get("requirement_code") or rc.get("requirement_type") or "")):
            rc["active_standard_status_summary"] = active_summary_by_client_prop.get(
                (cid_s, pid_s),
                {"state": ACTIVE_STANDARD_STATE_UNKNOWN, "signal_counts": {}, "read_only": True},
            )
        out.append(
            enrich_requirement_dict(
                rc,
                ev,
                audience="admin",
                published_registry_entries=published_entries,
                property_doc=_prop_doc,
                compliance_evidence_records=_cer,
            )
        )
    return out


def evidence_state_for_documents_list(docs: List[Dict[str, Any]]) -> str:
    return evidence_state_from_documents(docs)


def infer_date_source_for_scoring(
    requirement: Optional[Dict[str, Any]],
    evidence_state: str,
) -> str:
    if not requirement:
        if evidence_state == EVIDENCE_VERIFIED:
            return DATE_SOURCE_VERIFIED_DOCUMENT
        return DATE_SOURCE_SYSTEM_ESTIMATED
    return infer_date_source(requirement, evidence_state)
