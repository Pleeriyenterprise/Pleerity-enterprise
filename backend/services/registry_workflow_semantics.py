"""
Published-registry workflow semantics (validation + deterministic hints).

Read-only helpers for draft validation and normalization. Does not alter runtime engines.
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from services.compliance_evidence_record_service import (
    EVIDENCE_MODE_DOCUMENT_UPLOAD,
    EVIDENCE_MODE_STRUCTURED_DECLARATION,
    EXTERNAL_ASSESSMENT_EVIDENCE_WORKFLOW,
    GUIDED_DECLARATION_WORKFLOW,
    REGISTRATION_TRACKING_WORKFLOW,
    TENANT_DELIVERY_WORKFLOW,
)
from services.workflow_behaviour_governance import list_governance_workflow_keys

# primary_resolution_workflow values used in product defaults and resolver enrich (not an enum redesign).
ALLOWED_PRIMARY_RESOLUTION_WORKFLOWS: frozenset[str] = frozenset(
    {
        "GUIDED_EVIDENCE_RESOLUTION",
        "LEGACY_DOCUMENT_UPLOAD",
        "DIRECT_EVIDENCE_ACTION",
        GUIDED_DECLARATION_WORKFLOW,
        TENANT_DELIVERY_WORKFLOW,
        REGISTRATION_TRACKING_WORKFLOW,
        EXTERNAL_ASSESSMENT_EVIDENCE_WORKFLOW,
    }
)

# client_workflow_class / workflow_class reference strings (governance capability keys + MULTI_EVIDENCE).
_ALLOWED_CLIENT_WORKFLOW_CLASSES: frozenset[str] = frozenset(list_governance_workflow_keys()) | frozenset(
    {
        "GUIDED_EVIDENCE_RESOLUTION",
        "LEGACY_DOCUMENT_UPLOAD",
        "REMEDIATION_JOB",
        "EXTERNAL_REMEDIATION_TRACKING",
        "HIDDEN_SYSTEM",
        "UNKNOWN",
    }
)


def is_allowed_client_workflow_class(value: str) -> bool:
    v = str(value or "").strip().upper()
    return bool(v) and v in _ALLOWED_CLIENT_WORKFLOW_CLASSES


def validate_evidence_resolution_workflow_semantics(er: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    """
    Governance-aware checks for a draft ``evidence_resolution`` object (already structurally validated).

    Returns (errors, governance_warnings). Errors should block publish; warnings should flag needs_review.
    """
    errors: List[str] = []
    warnings: List[str] = []
    if not isinstance(er, dict):
        return errors, warnings

    prw = str(er.get("primary_resolution_workflow") or "").strip().upper()
    if prw and prw not in ALLOWED_PRIMARY_RESOLUTION_WORKFLOWS:
        errors.append(
            f"evidence_resolution.primary_resolution_workflow invalid: {prw!r} "
            f"(must be one of: {', '.join(sorted(ALLOWED_PRIMARY_RESOLUTION_WORKFLOWS))})"
        )

    modes_raw = er.get("allowed_evidence_modes")
    modes: List[str] = []
    if isinstance(modes_raw, list):
        modes = [str(m or "").strip().upper() for m in modes_raw if str(m or "").strip()]

    cwc = str(er.get("client_workflow_class") or "").strip().upper()
    if cwc and not is_allowed_client_workflow_class(cwc):
        errors.append(f"evidence_resolution.client_workflow_class is not a recognised governance class: {cwc!r}")

    structured_first = prw in (
        GUIDED_DECLARATION_WORKFLOW,
        TENANT_DELIVERY_WORKFLOW,
        REGISTRATION_TRACKING_WORKFLOW,
        EXTERNAL_ASSESSMENT_EVIDENCE_WORKFLOW,
    )
    if structured_first and modes and EVIDENCE_MODE_STRUCTURED_DECLARATION not in modes:
        errors.append(
            f"evidence_resolution.primary_resolution_workflow={prw} requires "
            f"{EVIDENCE_MODE_STRUCTURED_DECLARATION} in allowed_evidence_modes"
        )

    if prw == EXTERNAL_ASSESSMENT_EVIDENCE_WORKFLOW and modes == [EVIDENCE_MODE_DOCUMENT_UPLOAD]:
        errors.append(
            "evidence_resolution.external_assessment_workflow cannot be document-upload-only; "
            "use structured declaration + supporting upload pattern"
        )

    non_doc = [m for m in modes if m != EVIDENCE_MODE_DOCUMENT_UPLOAD]
    if cwc == "MULTI_EVIDENCE" and len(non_doc) == 0 and len(modes) <= 1:
        warnings.append(
            "evidence_resolution.client_workflow_class=MULTI_EVIDENCE but modes look certificate-only; "
            "verify multi-component intent"
        )

    if prw == "GUIDED_EVIDENCE_RESOLUTION" and modes and len(modes) >= 2 and cwc and cwc not in (
        "",
        "MULTI_EVIDENCE",
    ):
        warnings.append(
            "evidence_resolution.primary_resolution_workflow=GUIDED_EVIDENCE_RESOLUTION with multiple modes "
            "normally pairs with client_workflow_class=MULTI_EVIDENCE for governance parity"
        )

    return errors, warnings


def merge_registry_governance_review_fields(doc: Dict[str, Any], new_flags: List[str]) -> None:
    """Add ``new_flags`` into governance.needs_review_fields (deduped)."""
    if not new_flags:
        return
    gov = doc.get("governance") if isinstance(doc.get("governance"), dict) else {}
    nr = [str(x) for x in (gov.get("needs_review_fields") or []) if str(x).strip()]
    for f in new_flags:
        if f not in nr:
            nr.append(str(f))
    gov["needs_review_fields"] = nr
    doc["governance"] = gov

