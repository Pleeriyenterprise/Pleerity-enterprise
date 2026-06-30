"""
Document Linkage Lifecycle Authority — canonical lifecycle for document linkage exceptions.

When the underlying linkage exception is resolved (requirement linked, gap closed, evidence
accepted), operational issues created from compliance gaps must auto-resolve while preserving
full audit history.

Does not alter RAOD requirement authority, PAA lifecycle copy, Today presentation semantics,
or compliance risk scoring rules.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)

AUTHORITY_ID = "DOCUMENT_LINKAGE_LIFECYCLE_AUTHORITY"

# Resolution sources (stored on issue.resolution_authority_source)
RESOLUTION_SOURCE_REQUIREMENT_LINKED = "requirement_linked"
RESOLUTION_SOURCE_GAP_RESOLVED = "gap_resolved"
RESOLUTION_SOURCE_EVIDENCE_ACCEPTED = "evidence_accepted"
RESOLUTION_SOURCE_MANUAL_OPERATOR = "manual_operator"
RESOLUTION_SOURCE_AI_RE_MATCH = "ai_re_match"
RESOLUTION_SOURCE_REQUIREMENT_ARCHIVED = "requirement_archived"
RESOLUTION_SOURCE_DUPLICATE_RECONCILED = "duplicate_reconciled"

# Gap kinds whose bridge-created issues auto-close when the gap resolves.
AUTO_RESOLVE_GAP_KINDS = frozenset(
    {
        "MISMATCHED_EVIDENCE",
        "MISSING_EVIDENCE",
        "DELIVERY_PROOF_MISSING",
        "TENANT_DELIVERY_PROOF_MISSING",
    }
)

COMPLIANCE_GAP_TRIGGER_PREFIX = "compliance_gap:"

TERMINAL_ISSUE_STATUSES = frozenset({"resolved", "closed", "cancelled"})


def is_terminal_issue_status(status: Optional[str]) -> bool:
    return str(status or "").lower() in TERMINAL_ISSUE_STATUSES


def is_open_issue_status(status: Optional[str]) -> bool:
    return not is_terminal_issue_status(status)


def gap_kind_from_issue(issue: Dict[str, Any]) -> Optional[str]:
    trig = str(issue.get("triggering_rule") or "")
    if trig.startswith(COMPLIANCE_GAP_TRIGGER_PREFIX):
        return trig.split(":", 1)[-1].strip().upper() or None
    return None


def issue_eligible_for_linkage_auto_resolve(issue: Dict[str, Any]) -> bool:
    """Bridge-created compliance issues tied to evidence/linkage gaps."""
    if not is_open_issue_status(issue.get("status")):
        return False
    if str(issue.get("created_from") or "") not in ("compliance", "system"):
        return False
    gk = gap_kind_from_issue(issue)
    if gk and gk in AUTO_RESOLVE_GAP_KINDS:
        return True
    root = str(issue.get("operational_root_key") or "")
    if root and str(issue.get("triggering_rule") or "").startswith(COMPLIANCE_GAP_TRIGGER_PREFIX):
        return True
    return False


def document_linkage_exception_resolved(
    document: Dict[str, Any],
    *,
    runtime_requirement_ids: Optional[Sequence[str]] = None,
) -> bool:
    from services.document_linkage_governance import DocumentLinkageState, derive_document_linkage_state

    state = derive_document_linkage_state(document, runtime_requirement_ids=runtime_requirement_ids)
    return state == DocumentLinkageState.LINKED.value


def resolution_note_for_source(
    source: str,
    *,
    gap_kind: Optional[str] = None,
    requirement_id: Optional[str] = None,
    document_id: Optional[str] = None,
) -> str:
    if source == RESOLUTION_SOURCE_REQUIREMENT_LINKED:
        return (
            "Automatically resolved: document linked to requirement "
            f"{requirement_id or '—'} (document {document_id or '—'}). Original linkage exception cleared."
        )
    if source == RESOLUTION_SOURCE_GAP_RESOLVED:
        return (
            f"Automatically resolved: compliance gap {gap_kind or '—'} closed. "
            "No actionable linkage problem remains."
        )
    if source == RESOLUTION_SOURCE_EVIDENCE_ACCEPTED:
        return "Automatically resolved: evidence accepted and linkage exception cleared."
    return f"Automatically resolved by {AUTHORITY_ID} ({source})."


async def resolve_operational_issues_for_gap_keys(
    db,
    client_id: str,
    gap_keys: Sequence[str],
    *,
    resolution_source: str,
    resolution_metadata: Optional[Dict[str, Any]] = None,
    actor_id: str = "system",
) -> List[str]:
    """
    Close open bridge issues keyed by operational_root_key when gaps resolve.
    Returns list of resolved issue_ids.
    """
    keys = [str(k).strip() for k in gap_keys if k and str(k).strip()]
    if not keys:
        return []

    from services import maintenance_issues_service as mis

    meta = dict(resolution_metadata or {})
    gap_kind = meta.get("gap_kind")
    note = resolution_note_for_source(
        resolution_source,
        gap_kind=gap_kind,
        requirement_id=meta.get("requirement_id"),
        document_id=meta.get("document_id"),
    )
    return await mis.auto_resolve_issues_by_operational_root_keys(
        client_id=str(client_id),
        operational_root_keys=keys,
        resolution_note=note,
        resolution_source=resolution_source,
        resolution_authority=AUTHORITY_ID,
        actor_id=actor_id,
        resolution_metadata=meta,
    )


async def resolve_linkage_issues_after_document_reconcile(
    db,
    *,
    client_id: str,
    document: Dict[str, Any],
    requirement_id: Optional[str],
    actor_id: Optional[str] = None,
    action: str = "link_requirement",
) -> List[str]:
    """
    After manual document linkage reconcile, resolve open bridge issues when linkage is LINKED.
    """
    from services.document_linkage_governance import (
        DocumentLinkageState,
        derive_document_linkage_state,
        load_runtime_requirements_for_client,
    )
    from services.compliance_gap_engine import stable_gap_key

    runtime_ids, _ = await load_runtime_requirements_for_client(db, client_id=client_id)
    state = derive_document_linkage_state(document, runtime_requirement_ids=runtime_ids)
    if state != DocumentLinkageState.LINKED.value:
        return []

    rid = str(requirement_id or document.get("requirement_id") or "").strip()
    pid = str(document.get("property_id") or "").strip()
    doc_id = str(document.get("document_id") or "").strip()
    if not rid or not pid:
        return []

    candidate_keys = [
        stable_gap_key(str(client_id), pid, rid, gk) for gk in AUTO_RESOLVE_GAP_KINDS
    ]
    open_issues = await db.maintenance_issues.find(
        {
            "client_id": str(client_id),
            "operational_root_key": {"$in": candidate_keys},
            "status": {"$nin": list(TERMINAL_ISSUE_STATUSES)},
        },
        {"_id": 0, "issue_id": 1, "operational_root_key": 1, "triggering_rule": 1, "created_from": 1, "status": 1},
    ).to_list(50)
    gap_keys = [
        str(i.get("operational_root_key"))
        for i in open_issues
        if i.get("operational_root_key") and issue_eligible_for_linkage_auto_resolve(i)
    ]
    if not gap_keys:
        return []

    return await resolve_operational_issues_for_gap_keys(
        db,
        client_id,
        gap_keys,
        resolution_source=RESOLUTION_SOURCE_REQUIREMENT_LINKED,
        resolution_metadata={
            "requirement_id": rid,
            "property_id": pid,
            "document_id": doc_id,
            "reconcile_action": action,
        },
        actor_id=actor_id or "system",
    )
