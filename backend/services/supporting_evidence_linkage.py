"""
Supporting-document linkage — audit-only linkage must not drive requirement satisfaction.

Used by reconcile-linkage, evidence authority sync, lifecycle presentation, and admin
pending-verification filters. Certificate-primary requirements (Gas, EPC, EICR, etc.)
are never treated as supporting-only.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from services.requirement_code_registry import normalize_requirement_code

SUPPORTING_EVIDENCE_ATTACHMENT_SOURCE = "supporting_evidence_attachment"
EVIDENCE_LINKAGE_ROLE_SUPPORTING = "SUPPORTING"


def is_supporting_evidence_attachment_document(doc: Dict[str, Any]) -> bool:
    source = str(doc.get("source") or "").strip().lower()
    if source == SUPPORTING_EVIDENCE_ATTACHMENT_SOURCE:
        return True
    role = str(doc.get("evidence_linkage_role") or "").strip().upper()
    return role == EVIDENCE_LINKAGE_ROLE_SUPPORTING


def is_certificate_primary_requirement(requirement: Dict[str, Any]) -> bool:
    """True for document-verification-primary families (Gas, EPC, EICR, PAT, etc.)."""
    from services.cer_governance_presentation import (
        DOCUMENT_PRIMARY_CODES,
        GF_PLATFORM_VER,
        resolve_governance_meta,
    )
    from services.compliance_evidence_record_service import effective_evidence_resolution

    meta = resolve_governance_meta(requirement)
    if str(meta.get("governance_family") or "") == GF_PLATFORM_VER:
        return True
    raw = str(requirement.get("requirement_code") or requirement.get("requirement_type") or "").strip()
    canon = normalize_requirement_code(raw) or raw.lower().replace(" ", "_")
    if canon in DOCUMENT_PRIMARY_CODES:
        return True
    pol = effective_evidence_resolution(requirement)
    pwf = str(pol.get("primary_resolution_workflow") or "").upper()
    wf = str(requirement.get("workflow_class") or "").upper()
    if pwf in ("DOCUMENT_UPLOAD", "LEGACY_DOCUMENT_UPLOAD"):
        return True
    if wf in ("DOCUMENT_UPLOAD", "LEGACY_DOCUMENT_UPLOAD"):
        return True
    return False


def find_authoritative_non_document_record(
    requirement: Dict[str, Any],
    evidence_records: Sequence[Dict[str, Any]],
    *,
    evidence_policy: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    from services.compliance_evidence_record_service import (
        active_sorted_evidence_candidates,
        effective_evidence_resolution,
        non_document_record_satisfies_policy,
    )
    from services.compliance_status_authority import is_critical_safety_or_legal_obligation

    if is_certificate_primary_requirement(requirement):
        return None
    policy = evidence_policy or effective_evidence_resolution(requirement)
    is_critical = is_critical_safety_or_legal_obligation(requirement)
    for rec in active_sorted_evidence_candidates(list(evidence_records or [])):
        if non_document_record_satisfies_policy(
            record=rec,
            requirement=requirement,
            policy=policy,
            is_critical_obligation=is_critical,
        ):
            return rec
    return None


def requirement_has_authoritative_non_document_satisfaction(
    requirement: Dict[str, Any],
    evidence_records: Sequence[Dict[str, Any]],
    *,
    evidence_policy: Optional[Dict[str, Any]] = None,
) -> bool:
    return find_authoritative_non_document_record(
        requirement,
        evidence_records,
        evidence_policy=evidence_policy,
    ) is not None


def should_treat_linked_document_as_supporting_only(
    doc: Dict[str, Any],
    requirement: Dict[str, Any],
    evidence_records: Sequence[Dict[str, Any]],
    *,
    evidence_policy: Optional[Dict[str, Any]] = None,
) -> bool:
    """True when this linked document must not drive authority / satisfaction."""
    if is_certificate_primary_requirement(requirement):
        return False
    if is_supporting_evidence_attachment_document(doc):
        return True
    from services.compliance_evidence_record_service import effective_evidence_resolution

    policy = evidence_policy or effective_evidence_resolution(requirement)
    if not policy.get("supporting_upload_recommended"):
        return False
    return requirement_has_authoritative_non_document_satisfaction(
        requirement,
        evidence_records,
        evidence_policy=policy,
    )


def documents_for_authority_primary_selection(
    documents: List[Dict[str, Any]],
    requirement: Dict[str, Any],
    evidence_records: Sequence[Dict[str, Any]],
    *,
    evidence_policy: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Exclude supporting-only linked documents from primary evidence selection when
    structured / non-document evidence already satisfies policy.
    """
    if is_certificate_primary_requirement(requirement):
        return documents
    if not requirement_has_authoritative_non_document_satisfaction(
        requirement,
        evidence_records,
        evidence_policy=evidence_policy,
    ):
        return documents
    filtered = [
        d
        for d in documents
        if not should_treat_linked_document_as_supporting_only(
            d,
            requirement,
            evidence_records,
            evidence_policy=evidence_policy,
        )
    ]
    return filtered


def requirement_structured_satisfaction_suppresses_document_escalation(
    requirement: Dict[str, Any],
    evidence_records: Optional[Sequence[Dict[str, Any]]] = None,
) -> bool:
    """
    True when linked supporting documents must not trigger escalation / review pending
    on the requirement row.
    """
    if is_certificate_primary_requirement(requirement):
        return False
    ea = requirement.get("evidence_authority") if isinstance(requirement.get("evidence_authority"), dict) else {}
    if str(ea.get("state_reason") or "") == "verified_non_document_evidence":
        return True
    if str(ea.get("state") or "").upper() in ("VERIFIED_CURRENT", "EA_VERIFIED_CURRENT"):
        mode = str(ea.get("primary_evidence_mode") or "").upper()
        if mode and mode != "DOCUMENT_UPLOAD":
            return True
    if evidence_records is not None:
        return requirement_has_authoritative_non_document_satisfaction(requirement, evidence_records)
    rec_id = str(ea.get("primary_evidence_record_id") or requirement.get("evidence_record_id") or "").strip()
    if rec_id and str(ea.get("primary_evidence_mode") or "").upper() not in ("", "DOCUMENT_UPLOAD"):
        return True
    return False


def persist_supporting_linkage_document_fields(base_fields: Dict[str, Any]) -> Dict[str, Any]:
    """Augment linkage persist payload for audit-only supporting evidence."""
    out = dict(base_fields)
    out["evidence_linkage_role"] = EVIDENCE_LINKAGE_ROLE_SUPPORTING
    out["admin_verification_pending_suppressed"] = True
    return out


async def should_skip_primary_document_pipeline_on_link(
    db,
    *,
    doc: Dict[str, Any],
    requirement: Dict[str, Any],
    client_id: str,
) -> bool:
    from services.compliance_evidence_record_service import (
        effective_evidence_resolution,
        load_records_for_requirement_sync,
    )

    if is_certificate_primary_requirement(requirement):
        return False
    if is_supporting_evidence_attachment_document(doc):
        return True
    rid = str(requirement.get("requirement_id") or "").strip()
    if not rid:
        return False
    records = await load_records_for_requirement_sync(db, rid, client_id)
    policy = effective_evidence_resolution(requirement)
    return requirement_has_authoritative_non_document_satisfaction(requirement, records, evidence_policy=policy)


async def document_excluded_from_admin_verification_pending(
    db,
    doc: Dict[str, Any],
) -> bool:
    """True when a UPLOADED document should not count toward admin verification reminders."""
    if str(doc.get("status") or "").upper() != "UPLOADED":
        return False
    if doc.get("admin_verification_pending_suppressed") is True:
        return True
    if not is_supporting_evidence_attachment_document(doc):
        return False
    rid = str(doc.get("requirement_id") or "").strip()
    if not rid:
        return False
    cid = str(doc.get("client_id") or "").strip()
    if not cid:
        return False
    req = await db.requirements.find_one(
        {"requirement_id": rid, "client_id": cid},
        {"_id": 0},
    )
    if not req or is_certificate_primary_requirement(req):
        return False
    from services.compliance_evidence_record_service import (
        effective_evidence_resolution,
        load_records_for_requirement_sync,
    )

    records = await load_records_for_requirement_sync(db, rid, cid)
    policy = effective_evidence_resolution(req)
    return requirement_has_authoritative_non_document_satisfaction(req, records, evidence_policy=policy)
