"""
Client-facing document visibility governance — operational queue vs evidence registry.

Additive projection only. One authoritative document row; visibility state is derived
from operational + linkage + expiry context. Does not weaken evidence review authority.
"""
from __future__ import annotations

import os
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from services.document_linkage_governance import DocumentLinkageState
from services.document_operational_state import DocumentOperationalState

_ENV_RESURFACE_DAYS = "DOCUMENT_ATTENTION_EXPIRY_RESURFACE_DAYS"


class DocumentClientVisibilityState(str, Enum):
    ATTENTION_REQUIRED = "ATTENTION_REQUIRED"
    ACTIVE_EVIDENCE = "ACTIVE_EVIDENCE"
    HISTORICAL_OR_SUPERSEDED = "HISTORICAL_OR_SUPERSEDED"
    OPERATIONAL_ATTACHMENT = "OPERATIONAL_ATTACHMENT"


class DocumentRegistrySection(str, Enum):
    ACTIVE_EVIDENCE = "active_evidence"
    PENDING_REVIEW = "pending_review"
    EXPIRING_SOON = "expiring_soon"
    RECONCILIATION_REQUIRED = "reconciliation_required"
    HISTORICAL_SUPERSEDED = "historical_superseded"
    OPERATIONAL_ATTACHMENTS = "operational_attachments"


VISIBILITY_LABELS: Dict[str, str] = {
    DocumentClientVisibilityState.ATTENTION_REQUIRED.value: "Attention required",
    DocumentClientVisibilityState.ACTIVE_EVIDENCE.value: "Active evidence",
    DocumentClientVisibilityState.HISTORICAL_OR_SUPERSEDED.value: "Historical / superseded",
    DocumentClientVisibilityState.OPERATIONAL_ATTACHMENT.value: "Operational attachment",
}

REGISTRY_SECTION_LABELS: Dict[str, str] = {
    DocumentRegistrySection.ACTIVE_EVIDENCE.value: "Active evidence",
    DocumentRegistrySection.PENDING_REVIEW.value: "Pending review",
    DocumentRegistrySection.EXPIRING_SOON.value: "Expiring soon",
    DocumentRegistrySection.RECONCILIATION_REQUIRED.value: "Reconciliation required",
    DocumentRegistrySection.HISTORICAL_SUPERSEDED.value: "Historical / superseded",
    DocumentRegistrySection.OPERATIONAL_ATTACHMENTS.value: "Operational attachments",
}

ATTENTION_OPERATIONAL_STATES = frozenset(
    {
        DocumentOperationalState.EVIDENCE_REJECTED.value,
        DocumentOperationalState.EVIDENCE_EXPIRED.value,
        DocumentOperationalState.ADMIN_REVIEW_PENDING.value,
        DocumentOperationalState.MATCH_RESOLVED_VERIFICATION_PENDING.value,
        DocumentOperationalState.EXTRACTION_CONFIRMATION_PENDING.value,
        DocumentOperationalState.EXTRACTION_IN_PROGRESS.value,
        DocumentOperationalState.EXTRACTION_FAILED.value,
        DocumentOperationalState.UPLOADED_AWAITING_REVIEW.value,
    }
)

SETTLED_OPERATIONAL_STATES = frozenset(
    {
        DocumentOperationalState.EXTERNALLY_VERIFIED.value,
        DocumentOperationalState.EVIDENCE_VERIFIED.value,
        DocumentOperationalState.EVIDENCE_ACCEPTED_ON_FILE.value,
    }
)


def get_document_expiry_resurface_days() -> int:
    """Days before expiry when settled evidence re-enters attention (default 90)."""
    return int(os.environ.get(_ENV_RESURFACE_DAYS, "90"))


def _parse_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        if "T" in text:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
        return date.fromisoformat(text[:10])
    except (ValueError, TypeError):
        return None


def _doc_expiry_date(doc: Dict[str, Any], requirement: Optional[Dict[str, Any]] = None) -> Optional[date]:
    for key in ("expiry_date", "confirmed_expiry_date"):
        parsed = _parse_date(doc.get(key))
        if parsed:
            return parsed
    ai = doc.get("ai_extraction")
    if isinstance(ai, dict):
        data = ai.get("data") if isinstance(ai.get("data"), dict) else {}
        for key in ("expiry_date", "certificate_expiry", "valid_until"):
            parsed = _parse_date(data.get(key))
            if parsed:
                return parsed
    if requirement:
        for key in ("confirmed_expiry_date", "extracted_expiry_date", "due_date"):
            parsed = _parse_date(requirement.get(key))
            if parsed:
                return parsed
    return None


def _days_to_expiry(expiry: Optional[date], *, now: Optional[date] = None) -> Optional[int]:
    if not expiry:
        return None
    today = now or datetime.now(timezone.utc).date()
    return (expiry - today).days


def _is_operational_attachment(doc: Dict[str, Any]) -> bool:
    linkage = str(doc.get("document_linkage_state") or "").upper()
    if linkage == DocumentLinkageState.INTENTIONALLY_UNLINKED.value:
        return True
    if str(doc.get("linkage_intent") or "").upper() == "INTENTIONAL":
        return True
    if str(doc.get("source") or "").lower() == "supporting_evidence_attachment":
        return True
    doc_type = str(doc.get("document_type") or "").strip().lower()
    if doc_type == "other" and not doc.get("requirement_id"):
        return True
    return False


def _is_historical_superseded(doc: Dict[str, Any], *, primary_document_ids: Set[str]) -> bool:
    op = str(doc.get("document_operational_state") or "").upper()
    if op == DocumentOperationalState.EVIDENCE_SUPERSEDED.value:
        return True
    review = str(doc.get("evidence_review_state") or "").upper()
    if review == "SUPERSEDED":
        return True
    did = str(doc.get("document_id") or "").strip()
    if did and doc.get("requirement_id") and did not in primary_document_ids:
        if op in SETTLED_OPERATIONAL_STATES or str(doc.get("status") or "").upper() == "VERIFIED":
            return True
    return False


def _linkage_needs_attention(doc: Dict[str, Any]) -> bool:
    linkage = str(doc.get("document_linkage_state") or "").upper()
    if doc.get("linkage_reconciliation_required") is True:
        return True
    return linkage in (
        DocumentLinkageState.RECONCILIATION_REQUIRED.value,
        DocumentLinkageState.BROKEN_LINKAGE.value,
    )


def _operational_needs_attention(doc: Dict[str, Any]) -> bool:
    op = str(doc.get("document_operational_state") or "").upper()
    if op in ATTENTION_OPERATIONAL_STATES:
        return True
    if doc.get("requirement_evidence_mismatch") is True:
        return True
    if doc.get("review_required") is True:
        return True
    return False


def _expiring_soon_attention(
    doc: Dict[str, Any],
    requirement: Optional[Dict[str, Any]],
    *,
    resurface_days: int,
    now: Optional[date] = None,
) -> Tuple[bool, Optional[int]]:
    op = str(doc.get("document_operational_state") or "").upper()
    if op in (
        DocumentOperationalState.EVIDENCE_REJECTED.value,
        DocumentOperationalState.EVIDENCE_EXPIRED.value,
        DocumentOperationalState.EVIDENCE_SUPERSEDED.value,
    ):
        return False, None
    expiry = _doc_expiry_date(doc, requirement)
    days = _days_to_expiry(expiry, now=now)
    if days is None:
        return False, None
    if days <= 0:
        return True, days
    if days <= resurface_days:
        return True, days
    return False, days


def derive_document_registry_section(
    doc: Dict[str, Any],
    *,
    requirement: Optional[Dict[str, Any]] = None,
    primary_document_ids: Optional[Set[str]] = None,
    resurface_days: Optional[int] = None,
    now: Optional[date] = None,
) -> str:
    """Property evidence registry section (operational grouping, not filesystem folders)."""
    window = resurface_days if resurface_days is not None else get_document_expiry_resurface_days()
    primary_ids = primary_document_ids or set()
    if _is_operational_attachment(doc):
        return DocumentRegistrySection.OPERATIONAL_ATTACHMENTS.value
    if _is_historical_superseded(doc, primary_document_ids=primary_ids):
        return DocumentRegistrySection.HISTORICAL_SUPERSEDED.value
    if _linkage_needs_attention(doc):
        return DocumentRegistrySection.RECONCILIATION_REQUIRED.value
    expiring, _ = _expiring_soon_attention(doc, requirement, resurface_days=window, now=now)
    if expiring:
        return DocumentRegistrySection.EXPIRING_SOON.value
    op = str(doc.get("document_operational_state") or "").upper()
    if op in SETTLED_OPERATIONAL_STATES:
        return DocumentRegistrySection.ACTIVE_EVIDENCE.value
    if _operational_needs_attention(doc):
        return DocumentRegistrySection.PENDING_REVIEW.value
    linkage = str(doc.get("document_linkage_state") or "").upper()
    if linkage == DocumentLinkageState.LINKED.value and doc.get("requirement_id"):
        return DocumentRegistrySection.ACTIVE_EVIDENCE.value
    return DocumentRegistrySection.PENDING_REVIEW.value


def derive_document_visibility_projection(
    doc: Dict[str, Any],
    *,
    requirement: Optional[Dict[str, Any]] = None,
    primary_document_ids: Optional[Set[str]] = None,
    resurface_days: Optional[int] = None,
    now: Optional[date] = None,
) -> Dict[str, Any]:
    """
    Derive client visibility bucket and registry section.
    Requires operational + linkage projections on doc when possible.
    """
    window = resurface_days if resurface_days is not None else get_document_expiry_resurface_days()
    primary_ids = primary_document_ids or set()
    reason_codes: List[str] = []

    if _is_operational_attachment(doc):
        reason_codes.append("INTENTIONALLY_UNLINKED_ATTACHMENT")
        return _visibility_payload(
            DocumentClientVisibilityState.OPERATIONAL_ATTACHMENT,
            DocumentRegistrySection.OPERATIONAL_ATTACHMENTS,
            reason_codes,
            attention_required=False,
            expiry_resurface=False,
            days_to_expiry=None,
        )

    if _is_historical_superseded(doc, primary_document_ids=primary_ids):
        reason_codes.append("HISTORICAL_OR_SUPERSEDED")
        return _visibility_payload(
            DocumentClientVisibilityState.HISTORICAL_OR_SUPERSEDED,
            DocumentRegistrySection.HISTORICAL_SUPERSEDED,
            reason_codes,
            attention_required=False,
            expiry_resurface=False,
            days_to_expiry=None,
        )

    if _linkage_needs_attention(doc):
        linkage = str(doc.get("document_linkage_state") or "").upper()
        reason_codes.append("LINKAGE_RECONCILIATION_REQUIRED" if linkage == DocumentLinkageState.RECONCILIATION_REQUIRED.value else "BROKEN_LINKAGE")
        return _visibility_payload(
            DocumentClientVisibilityState.ATTENTION_REQUIRED,
            DocumentRegistrySection.RECONCILIATION_REQUIRED,
            reason_codes,
            attention_required=True,
            expiry_resurface=False,
            days_to_expiry=None,
        )

    expiring, days = _expiring_soon_attention(doc, requirement, resurface_days=window, now=now)
    if expiring:
        reason_codes.append("EXPIRY_RESURFACE" if days is not None and days > 0 else "EXPIRED")
        section = DocumentRegistrySection.EXPIRING_SOON if days is not None and days > 0 else DocumentRegistrySection.PENDING_REVIEW
        return _visibility_payload(
            DocumentClientVisibilityState.ATTENTION_REQUIRED,
            section,
            reason_codes,
            attention_required=True,
            expiry_resurface=days is not None and days > 0,
            days_to_expiry=days,
        )

    if _operational_needs_attention(doc):
        op = str(doc.get("document_operational_state") or "").upper()
        reason_codes.append(f"OPERATIONAL_{op}" if op else "OPERATIONAL_ATTENTION")
        return _visibility_payload(
            DocumentClientVisibilityState.ATTENTION_REQUIRED,
            DocumentRegistrySection.PENDING_REVIEW,
            reason_codes,
            attention_required=True,
            expiry_resurface=False,
            days_to_expiry=days,
        )

    op = str(doc.get("document_operational_state") or "").upper()
    if op in SETTLED_OPERATIONAL_STATES or (
        str(doc.get("document_linkage_state") or "").upper() == DocumentLinkageState.LINKED.value
        and doc.get("requirement_id")
    ):
        reason_codes.append("SETTLED_ACTIVE_EVIDENCE")
        return _visibility_payload(
            DocumentClientVisibilityState.ACTIVE_EVIDENCE,
            DocumentRegistrySection.ACTIVE_EVIDENCE,
            reason_codes,
            attention_required=False,
            expiry_resurface=False,
            days_to_expiry=days,
        )

    reason_codes.append("DEFAULT_PENDING_REVIEW")
    return _visibility_payload(
        DocumentClientVisibilityState.ATTENTION_REQUIRED,
        DocumentRegistrySection.PENDING_REVIEW,
        reason_codes,
        attention_required=True,
        expiry_resurface=False,
        days_to_expiry=days,
    )


def _visibility_payload(
    visibility: DocumentClientVisibilityState,
    section: DocumentRegistrySection,
    reason_codes: List[str],
    *,
    attention_required: bool,
    expiry_resurface: bool,
    days_to_expiry: Optional[int],
) -> Dict[str, Any]:
    return {
        "document_client_visibility_state": visibility.value,
        "document_client_visibility_label": VISIBILITY_LABELS.get(visibility.value, visibility.value),
        "document_attention_required": attention_required,
        "document_registry_section": section.value,
        "document_registry_section_label": REGISTRY_SECTION_LABELS.get(section.value, section.value),
        "document_expiry_resurface": expiry_resurface,
        "document_days_to_expiry": days_to_expiry,
        "document_visibility_reason_codes": reason_codes,
    }


def build_primary_document_ids(requirements: List[Dict[str, Any]]) -> Set[str]:
    out: Set[str] = set()
    for req in requirements:
        for key in ("evidence_doc_id", "document_id"):
            did = str(req.get(key) or "").strip()
            if did:
                out.add(did)
                break
    return out


def build_requirements_by_id(requirements: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {str(r.get("requirement_id")): r for r in requirements if r.get("requirement_id")}


def attach_document_visibility_projection(
    doc: Dict[str, Any],
    *,
    requirements_by_id: Optional[Dict[str, Dict[str, Any]]] = None,
    primary_document_ids: Optional[Set[str]] = None,
    resurface_days: Optional[int] = None,
) -> Dict[str, Any]:
    req = None
    rid = str(doc.get("requirement_id") or "").strip()
    if rid and requirements_by_id:
        req = requirements_by_id.get(rid)
    doc.update(
        derive_document_visibility_projection(
            doc,
            requirement=req,
            primary_document_ids=primary_document_ids or set(),
            resurface_days=resurface_days,
        )
    )
    return doc


def attach_document_visibility_projection_batch(
    documents: List[Dict[str, Any]],
    *,
    requirements: Optional[List[Dict[str, Any]]] = None,
    resurface_days: Optional[int] = None,
) -> List[Dict[str, Any]]:
    reqs = requirements or []
    by_id = build_requirements_by_id(reqs)
    primary_ids = build_primary_document_ids(reqs)
    for doc in documents:
        attach_document_visibility_projection(
            doc,
            requirements_by_id=by_id,
            primary_document_ids=primary_ids,
            resurface_days=resurface_days,
        )
    return documents


def group_documents_by_registry_section(documents: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {s.value: [] for s in DocumentRegistrySection}
    for doc in documents:
        section = str(doc.get("document_registry_section") or DocumentRegistrySection.PENDING_REVIEW.value)
        if section not in grouped:
            section = DocumentRegistrySection.PENDING_REVIEW.value
        grouped[section].append(doc)
    return grouped


def filter_documents_by_visibility(
    documents: List[Dict[str, Any]],
    visibility_state: Optional[str],
) -> List[Dict[str, Any]]:
    if not visibility_state:
        return documents
    target = str(visibility_state).strip().upper()
    if target in ("ATTENTION", "ATTENTION_QUEUE", "QUEUE"):
        target = DocumentClientVisibilityState.ATTENTION_REQUIRED.value
    return [
        d
        for d in documents
        if str(d.get("document_client_visibility_state") or "").upper() == target
        or (target == DocumentClientVisibilityState.ATTENTION_REQUIRED.value and d.get("document_attention_required") is True)
    ]
