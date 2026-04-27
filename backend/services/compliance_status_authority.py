"""
Authoritative compliance status classification shared by reports/export surfaces.

Allowed status labels:
- COMPLIANT
- PARTIALLY COMPLIANT
- ACTION REQUIRED
- HIGH RISK
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List


CRITICAL_REQUIREMENT_TYPES = {
    "gas_safety",
    "eicr",
    "fire_safety",
    "fire_alarm",
    "fire_risk",
    "hmo_license",
    "legionella",
}


def _norm_status(raw: Any) -> str:
    return str(raw or "").strip().upper()


def _is_mandatory(row: Dict[str, Any]) -> bool:
    if bool(row.get("mandatory")) or bool(row.get("is_mandatory")):
        return True
    applicability = str(row.get("applicability") or "").strip().upper()
    if applicability in {"MANDATORY", "REQUIRED"}:
        return True
    requirement_class = str(row.get("compliance_requirement_class") or "").strip().upper()
    return requirement_class in {"MANDATORY", "LEGAL", "SAFETY_CRITICAL"}


def _is_critical(row: Dict[str, Any]) -> bool:
    explicit = str(row.get("risk_level") or row.get("severity") or "").strip().upper()
    if explicit in {"CRITICAL", "HIGH_RISK", "HIGH"}:
        return True
    rtype = str(row.get("requirement_type") or "").strip().lower()
    return rtype in CRITICAL_REQUIREMENT_TYPES


def is_critical_safety_or_legal_obligation(row: Dict[str, Any]) -> bool:
    """
    Public hook for evidence governance: critical obligations cannot be fully satisfied from
    LOW-confidence non-document evidence alone (see compliance_evidence_record_service).
    """
    return _is_critical(row)


@dataclass(frozen=True)
class ComplianceStatusResult:
    status: str
    total_requirements: int
    compliant_count: int
    overdue_count: int
    pending_count: int
    mandatory_missing_or_pending_count: int
    critical_missing_or_pending_count: int
    expiring_soon_count: int
    reasons: List[str]


def evidence_governance_summary_for_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """
    Reporting / exports: stable projection of evidence mode + verification + confidence + activity.
    """
    ea = row.get("evidence_authority") if isinstance(row.get("evidence_authority"), dict) else {}
    last = ea.get("evidence_last_updated_at") or row.get("updated_at")
    return {
        "primary_evidence_mode": ea.get("primary_evidence_mode"),
        "evidence_confidence_level": ea.get("evidence_confidence_level"),
        "non_document_verification_status": ea.get("non_document_verification_status"),
        "primary_evidence_record_id": ea.get("primary_evidence_record_id"),
        "last_evidence_update": last,
        "authority_state": ea.get("state"),
        "unresolved_or_missing_evidence": str(ea.get("state") or "").upper()
        in {
            "MISSING",
            "UPLOADED_UNCONFIRMED",
            "EXTRACTION_COMPLETE_PENDING_CONFIRMATION",
            "PENDING_ADMIN_REVIEW",
            "MISMATCH_FLAGGED",
            "REJECTED",
            "VERIFIED_EXPIRED",
        },
    }


def classify_compliance_status(requirements: Iterable[Dict[str, Any]]) -> ComplianceStatusResult:
    rows = list(requirements or [])
    total = len(rows)
    compliant = 0
    overdue = 0
    pending = 0
    mandatory_problem = 0
    critical_problem = 0
    expiring = 0

    problem_statuses = {"PENDING", "OVERDUE", "MISSING", "MISSING_EVIDENCE", "FAILED", "NON_COMPLIANT", "ACTION_REQUIRED"}
    minor_pending_statuses = {"PENDING", "EXPIRING_SOON"}

    for r in rows:
        st = _norm_status(r.get("status"))
        if st == "COMPLIANT":
            compliant += 1
        if st == "OVERDUE":
            overdue += 1
        if st == "EXPIRING_SOON":
            expiring += 1
            pending += 1
        if st in problem_statuses:
            pending += 1
            if _is_mandatory(r):
                mandatory_problem += 1
            if _is_critical(r):
                critical_problem += 1

    reasons: List[str] = []
    if critical_problem > 0:
        status = "HIGH RISK"
        reasons.append("Critical safety/legal obligations are missing, pending, or overdue.")
    elif mandatory_problem > 0 or overdue > 0:
        status = "ACTION REQUIRED"
        reasons.append("Mandatory obligations are unresolved or overdue.")
    elif pending > 0:
        # Only minor pending items should get PARTIALLY COMPLIANT.
        non_minor_pending = 0
        for r in rows:
            st = _norm_status(r.get("status"))
            if st in problem_statuses and st not in minor_pending_statuses:
                non_minor_pending += 1
        if non_minor_pending == 0:
            status = "PARTIALLY COMPLIANT"
            reasons.append("Minor pending or expiring items exist.")
        else:
            status = "ACTION REQUIRED"
            reasons.append("Unresolved obligations require action.")
    else:
        status = "COMPLIANT"
        reasons.append("No overdue, pending critical, or missing mandatory obligations.")

    return ComplianceStatusResult(
        status=status,
        total_requirements=total,
        compliant_count=compliant,
        overdue_count=overdue,
        pending_count=pending,
        mandatory_missing_or_pending_count=mandatory_problem,
        critical_missing_or_pending_count=critical_problem,
        expiring_soon_count=expiring,
        reasons=reasons,
    )

