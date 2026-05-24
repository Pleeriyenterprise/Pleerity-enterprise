"""
Post-ingestion document↔requirement linkage governance.

Distinguishes intentional unlinked property docs from reconciliation-required
and broken linkage (stale requirement targets). Additive — does not weaken
evidence review authority.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

QUARANTINE_SCOPES = frozenset({"INTAKE_STAGING", "PORTFOLIO", "UNRESOLVED"})


class DocumentLinkageState(str, Enum):
    LINKED = "LINKED"
    INTENTIONALLY_UNLINKED = "INTENTIONALLY_UNLINKED"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"
    BROKEN_LINKAGE = "BROKEN_LINKAGE"


LINKAGE_LABELS: Dict[str, str] = {
    DocumentLinkageState.LINKED.value: "Linked to requirement",
    DocumentLinkageState.INTENTIONALLY_UNLINKED.value: "Intentionally unlinked",
    DocumentLinkageState.RECONCILIATION_REQUIRED.value: "Linkage reconciliation required",
    DocumentLinkageState.BROKEN_LINKAGE.value: "Broken requirement linkage",
}


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def is_intentionally_unlinked_persisted(doc: Dict[str, Any]) -> bool:
    state = str(doc.get("document_linkage_state") or "").upper()
    if state == DocumentLinkageState.INTENTIONALLY_UNLINKED.value:
        return True
    return str(doc.get("linkage_intent") or "").upper() == "INTENTIONAL"


def derive_document_linkage_state(
    doc: Dict[str, Any],
    *,
    runtime_requirement_ids: Set[str],
) -> str:
    scope = str(doc.get("evidence_scope_type") or "PROPERTY").upper()
    if scope in QUARANTINE_SCOPES:
        return DocumentLinkageState.LINKED.value

    if is_intentionally_unlinked_persisted(doc):
        return DocumentLinkageState.INTENTIONALLY_UNLINKED.value

    rid = str(doc.get("requirement_id") or "").strip()
    if rid:
        if rid not in runtime_requirement_ids:
            return DocumentLinkageState.BROKEN_LINKAGE.value
        return DocumentLinkageState.LINKED.value

    return DocumentLinkageState.RECONCILIATION_REQUIRED.value


def suggest_requirement_ids_for_document(
    doc: Dict[str, Any],
    runtime_requirements: List[Dict[str, Any]],
    *,
    limit: int = 5,
) -> List[str]:
    pid = str(doc.get("property_id") or doc.get("authoritative_property_id") or "").strip()
    doc_type = str(doc.get("document_type") or "").strip().lower()
    predicted = str(doc.get("predicted_document_type") or "").strip().lower()
    out: List[str] = []
    for req in runtime_requirements:
        if pid and str(req.get("property_id") or "") != pid:
            continue
        modes = [str(m).upper() for m in (req.get("allowed_evidence_modes") or [])]
        if modes and "DOCUMENT_UPLOAD" not in modes:
            continue
        label = " ".join(
            str(req.get(k) or "")
            for k in ("display_label", "description", "requirement_type", "requirement_code")
        ).lower()
        if doc_type and doc_type in label:
            out.append(str(req.get("requirement_id")))
            continue
        if predicted and predicted != "unknown" and predicted in label:
            out.append(str(req.get("requirement_id")))
            continue
        lc = str(req.get("client_lifecycle_state") or "").upper()
        if lc in ("ACTION_REQUIRED", "PENDING_REVIEW"):
            out.append(str(req.get("requirement_id")))
        if len(out) >= limit:
            break
    seen: Set[str] = set()
    deduped: List[str] = []
    for rid in out:
        if rid and rid not in seen:
            seen.add(rid)
            deduped.append(rid)
    return deduped[:limit]


def derive_document_linkage_projection(
    doc: Dict[str, Any],
    *,
    runtime_requirement_ids: Set[str],
    runtime_requirements: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    state = derive_document_linkage_state(doc, runtime_requirement_ids=runtime_requirement_ids)
    label = LINKAGE_LABELS.get(state, state.replace("_", " ").title())
    reconciliation_required = state in (
        DocumentLinkageState.RECONCILIATION_REQUIRED.value,
        DocumentLinkageState.BROKEN_LINKAGE.value,
    )
    projection: Dict[str, Any] = {
        "document_linkage_state": state,
        "document_linkage_label": label,
        "linkage_reconciliation_required": reconciliation_required,
    }
    if runtime_requirements and reconciliation_required:
        projection["linkage_suggested_requirement_ids"] = suggest_requirement_ids_for_document(
            doc, runtime_requirements
        )
    return projection


def attach_document_linkage_projection(
    doc: Dict[str, Any],
    *,
    runtime_requirement_ids: Set[str],
    runtime_requirements: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    doc.update(
        derive_document_linkage_projection(
            doc,
            runtime_requirement_ids=runtime_requirement_ids,
            runtime_requirements=runtime_requirements,
        )
    )
    return doc


def attach_document_linkage_projection_batch(
    documents: List[Dict[str, Any]],
    *,
    runtime_requirement_ids: Set[str],
    runtime_requirements: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    for doc in documents:
        attach_document_linkage_projection(
            doc,
            runtime_requirement_ids=runtime_requirement_ids,
            runtime_requirements=runtime_requirements,
        )
    return documents


def linkage_reconciliation_audit_fields(
    *,
    action: str,
    actor_user_id: Optional[str],
    reason: Optional[str] = None,
    prior_requirement_id: Optional[str] = None,
    new_requirement_id: Optional[str] = None,
) -> Dict[str, Any]:
    fields: Dict[str, Any] = {
        "linkage_reconciliation_at": _utc_iso(),
        "linkage_reconciliation_by": actor_user_id,
        "linkage_reconciliation_action": action,
    }
    if reason:
        fields["linkage_reconciliation_reason"] = reason.strip()[:500]
    if prior_requirement_id:
        fields["linkage_reconciliation_prior_requirement_id"] = prior_requirement_id
    if new_requirement_id:
        fields["linkage_reconciliation_new_requirement_id"] = new_requirement_id
    return fields


def persist_fields_for_intentionally_unlinked(
    *,
    actor_user_id: Optional[str],
    reason: Optional[str] = None,
    prior_requirement_id: Optional[str] = None,
) -> Dict[str, Any]:
    fields = linkage_reconciliation_audit_fields(
        action="mark_intentionally_unlinked",
        actor_user_id=actor_user_id,
        reason=reason,
        prior_requirement_id=prior_requirement_id,
    )
    fields.update(
        {
            "document_linkage_state": DocumentLinkageState.INTENTIONALLY_UNLINKED.value,
            "linkage_intent": "INTENTIONAL",
            "requirement_id": None,
        }
    )
    return fields


def persist_fields_for_linked_requirement(
    requirement_id: str,
    *,
    actor_user_id: Optional[str],
    reason: Optional[str] = None,
    prior_requirement_id: Optional[str] = None,
) -> Dict[str, Any]:
    fields = linkage_reconciliation_audit_fields(
        action="link_requirement",
        actor_user_id=actor_user_id,
        reason=reason,
        prior_requirement_id=prior_requirement_id,
        new_requirement_id=requirement_id,
    )
    fields.update(
        {
            "document_linkage_state": DocumentLinkageState.LINKED.value,
            "linkage_intent": None,
            "requirement_id": requirement_id,
        }
    )
    return fields


def persist_fields_for_new_other_upload() -> Dict[str, Any]:
    return {
        "document_linkage_state": DocumentLinkageState.INTENTIONALLY_UNLINKED.value,
        "linkage_intent": "INTENTIONAL",
    }


def persist_fields_for_upload_without_requirement() -> Dict[str, Any]:
    return {
        "document_linkage_state": DocumentLinkageState.RECONCILIATION_REQUIRED.value,
        "linkage_intent": None,
    }


async def load_runtime_requirements_for_client(
    db,
    *,
    client_id: str,
    property_id: Optional[str] = None,
) -> Tuple[Set[str], List[Dict[str, Any]]]:
    from services.requirement_client_runtime_surface import requirement_row_eligible_on_client_runtime_surfaces

    query: Dict[str, Any] = {"client_id": client_id}
    if property_id:
        query["property_id"] = property_id
    rows = await db.requirements.find(query, {"_id": 0}).to_list(500)
    property_cache: Dict[str, Optional[Dict[str, Any]]] = {}
    runtime: List[Dict[str, Any]] = []
    for row in rows:
        pid = str(row.get("property_id") or "")
        if pid not in property_cache:
            property_cache[pid] = await db.properties.find_one(
                {"property_id": pid, "client_id": client_id},
                {"_id": 0},
            )
        prop = property_cache.get(pid)
        if not prop:
            continue
        if await requirement_row_eligible_on_client_runtime_surfaces(
            db,
            client_id=client_id,
            row=row,
            property_doc=prop,
        ):
            runtime.append(row)
    ids = {str(r.get("requirement_id")) for r in runtime if r.get("requirement_id")}
    return ids, runtime


def linkage_matrix_passes_g5(
    doc: Dict[str, Any],
    *,
    runtime_requirement_ids: Optional[Set[str]] = None,
) -> Tuple[bool, Optional[str]]:
    """Return (ok, failure_kind) for G5 linkage checks."""
    scope = str(doc.get("evidence_scope_type") or "PROPERTY").upper()
    if scope in QUARANTINE_SCOPES:
        return True, None
    runtime = runtime_requirement_ids if runtime_requirement_ids is not None else set()
    state = str(doc.get("document_linkage_state") or "").upper()
    if not state:
        state = derive_document_linkage_state(doc, runtime_requirement_ids=runtime)
    if state == DocumentLinkageState.INTENTIONALLY_UNLINKED.value:
        return True, None
    if state == DocumentLinkageState.LINKED.value:
        return True, None
    if state == DocumentLinkageState.BROKEN_LINKAGE.value:
        return False, "BROKEN_LINKAGE"
    if state == DocumentLinkageState.RECONCILIATION_REQUIRED.value:
        return False, "RECONCILIATION_REQUIRED"
    return False, "LEGACY_ORPHAN"
