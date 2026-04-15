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
from services.requirement_action_resolver import infer_action_type, resolve_take_action_envelope

# --- Canonical enum values (stored on requirement documents and returned in APIs) ---

DATE_SOURCE_SYSTEM_ESTIMATED = "SYSTEM_ESTIMATED"
DATE_SOURCE_USER_PROVIDED = "USER_PROVIDED"
DATE_SOURCE_VERIFIED_DOCUMENT = "VERIFIED_DOCUMENT"

EVIDENCE_MISSING = "MISSING"
EVIDENCE_UPLOADED_UNVERIFIED = "UPLOADED_UNVERIFIED"
EVIDENCE_VERIFIED = "VERIFIED"

CONFIDENCE_ESTIMATED = "ESTIMATED"
CONFIDENCE_PARTIALLY_CONFIRMED = "PARTIALLY_CONFIRMED"
CONFIDENCE_VERIFIED = "VERIFIED"

ESTIMATED_NOTICE_TEXT = (
    "We've created estimated compliance dates based on standard regulatory cycles and your property setup. "
    "Upload your documents to confirm dates and improve accuracy."
)


def _status_upper(st: Optional[str]) -> str:
    return (st or "").strip().upper()


def evidence_state_from_document_statuses(statuses: List[str]) -> str:
    """Aggregate document statuses for one requirement_id."""
    if not statuses:
        return EVIDENCE_MISSING
    up = [_status_upper(s) for s in statuses]
    if any(s == "VERIFIED" for s in up):
        return EVIDENCE_VERIFIED
    if any(s not in ("REJECTED", "EXPIRED", "") for s in up):
        return EVIDENCE_UPLOADED_UNVERIFIED
    return EVIDENCE_MISSING


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
        {"_id": 0, "requirement_id": 1, "status": 1},
    )
    by_rid: Dict[str, List[str]] = {}
    async for doc in cursor:
        rid = doc.get("requirement_id")
        if not rid:
            continue
        by_rid.setdefault(rid, []).append(str(doc.get("status") or ""))
    return {rid: evidence_state_from_document_statuses(sts) for rid, sts in by_rid.items()}


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
    if evidence_state == EVIDENCE_UPLOADED_UNVERIFIED:
        return "Uploaded (awaiting verification)"
    return "Not uploaded"


def enrich_requirement_dict(
    requirement: Dict[str, Any],
    live_evidence_state: str,
    *,
    audience: str = "client",
) -> Dict[str, Any]:
    """
    Mutates a shallow copy: adds presentation + truth fields. Keeps all original keys.
    """
    out = dict(requirement)
    code = out.get("requirement_code") or out.get("requirement_type") or ""
    date_source, evidence_state, confidence_state = resolve_truth_triple(out, live_evidence_state)
    out["date_source"] = date_source
    out["evidence_state"] = evidence_state
    out["confidence_state"] = confidence_state

    status_raw = (out.get("status") or "").strip().upper()
    out["display_label"] = requirement_label(code, audience=audience)
    out["status_label"] = compliance_requirement_status_label(status_raw, audience=audience)
    date_label, helper = build_date_presentation(out, date_source, evidence_state)
    out["date_label"] = date_label
    out["date_explanation_helper"] = helper

    out["evidence_badge_label"] = evidence_badge_label(evidence_state)

    app = _status_upper(out.get("applicability"))
    if app == "NOT_REQUIRED" or status_raw == "NOT_REQUIRED":
        out["show_estimated_date_copy"] = False
    else:
        out["show_estimated_date_copy"] = date_source == DATE_SOURCE_SYSTEM_ESTIMATED

    eng = resolve_engine_payload_from_requirement_row(out)
    out.update(eng)

    out["action_type"] = infer_action_type(out)
    take = resolve_take_action_envelope(
        out,
        property_id=out.get("property_id"),
        property_jurisdiction=out.get("jurisdiction"),
    ).get("take_action")
    out["take_action"] = take
    out["action_links"] = list((take or {}).get("supporting_external_links") or [])

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
    from services.compliance_rules_registry import portfolio_jurisdiction_label

    ids = [r["requirement_id"] for r in requirements if r.get("requirement_id")]
    evidence_map = await load_evidence_state_by_requirement_id(db, client_id, ids)

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

    enriched = []
    for r in requirements:
        rid = r.get("requirement_id")
        ev = evidence_map.get(rid, EVIDENCE_MISSING)
        rc = dict(r)
        if not (str(rc.get("jurisdiction") or "").strip()):
            pid = rc.get("property_id")
            if pid and str(pid) in jur_by_prop:
                rc["jurisdiction"] = jur_by_prop[str(pid)]
        enriched.append(enrich_requirement_dict(rc, ev, audience="client"))
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
        out.append(enrich_requirement_dict(rc, ev, audience="admin"))
    return out


def evidence_state_for_documents_list(docs: List[Dict[str, Any]]) -> str:
    return evidence_state_from_document_statuses([str(d.get("status") or "") for d in docs])


def infer_date_source_for_scoring(
    requirement: Optional[Dict[str, Any]],
    evidence_state: str,
) -> str:
    if not requirement:
        if evidence_state == EVIDENCE_VERIFIED:
            return DATE_SOURCE_VERIFIED_DOCUMENT
        return DATE_SOURCE_SYSTEM_ESTIMATED
    return infer_date_source(requirement, evidence_state)
