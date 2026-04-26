"""
Authoritative compliance gap engine (Compliance Vault Pro).

Consumes requirement rows + property context. When ``evidence_authority`` is versioned and
synced, gaps are derived **only** from ``evidence_authority`` + requirement metadata (not
from legacy ``status`` as a parallel truth). Unsynced requirements use a narrow legacy
bridge so portfolios still see actionable items until authority backfill completes.

Downstream: ``compliance_gap_sync`` persists; ``client_priority_stream`` maps gaps to
priority actions; operational bridge uses stable ``gap_key`` for idempotency.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from presentation.label_service import requirement_label
from services.compliance_expiry_policy import resolve_expiring_soon_days_for_requirement
from services.compliance_score import get_requirement_weight
from services.requirement_evidence_authority import (
    AUTHORITY_VERSION,
    authority_state,
    EA_EXTRACTION_PENDING_CONFIRMATION,
    EA_MISSING,
    EA_MISMATCH_FLAGGED,
    EA_NOT_REQUIRED,
    EA_PENDING_ADMIN_REVIEW,
    EA_REJECTED,
    EA_UPLOADED_UNCONFIRMED,
    EA_VERIFIED_CURRENT,
    EA_VERIFIED_EXPIRED,
)

# --- Canonical gap kinds (stable contract) ---
GAP_MISSING_EVIDENCE = "MISSING_EVIDENCE"
GAP_EVIDENCE_UPLOADED_UNCONFIRMED = "EVIDENCE_UPLOADED_UNCONFIRMED"
GAP_MISMATCHED_EVIDENCE = "MISMATCHED_EVIDENCE"
GAP_EXPIRED = "EXPIRED"
GAP_EXPIRING_SOON = "EXPIRING_SOON"
GAP_DELIVERY_PROOF_MISSING = "DELIVERY_PROOF_MISSING"  # WO / ops completion proof
GAP_TENANT_DELIVERY_PROOF_MISSING = "TENANT_DELIVERY_PROOF_MISSING"  # governed tenant push receipt not on record
GAP_ACTION_REQUIRED = "ACTION_REQUIRED"
GAP_AUTHORITY_UNSYNCED = "AUTHORITY_UNSYNCED"  # transitional only

# --- Severity ---
SEVERITY_LOW = "LOW"
SEVERITY_MEDIUM = "MEDIUM"
SEVERITY_HIGH = "HIGH"
SEVERITY_CRITICAL = "CRITICAL"


def stable_gap_key(client_id: str, property_id: str, requirement_id: str, gap_kind: str) -> str:
    return f"{client_id}:{property_id or 'none'}:{requirement_id}:{gap_kind}"


def _parse_dt(val: Any) -> Optional[datetime]:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.replace(tzinfo=timezone.utc) if val.tzinfo is None else val.astimezone(timezone.utc)
    try:
        s = str(val).replace("Z", "+00:00")
        d = datetime.fromisoformat(s)
        return d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d.astimezone(timezone.utc)
    except Exception:
        return None


def _req_code(r: Dict[str, Any]) -> str:
    return (r.get("requirement_code") or r.get("code") or r.get("requirement_type") or "").strip()


def _base_severity_from_requirement(r: Dict[str, Any]) -> str:
    w = float(get_requirement_weight(_req_code(r) or "UNKNOWN"))
    if w >= 1.45:
        return SEVERITY_HIGH
    if w >= 1.15:
        return SEVERITY_MEDIUM
    return SEVERITY_LOW


def _escalate_severity(base: str, bump: int) -> str:
    order = [SEVERITY_LOW, SEVERITY_MEDIUM, SEVERITY_HIGH, SEVERITY_CRITICAL]
    try:
        i = order.index(base)
    except ValueError:
        i = 0
    return order[min(len(order) - 1, i + bump)]


@dataclass
class ComplianceGap:
    gap_kind: str
    severity: str
    title: str
    description: str
    why_matters: str
    recommended_action_detail: str
    priority_score: int
    action_type: str  # client_priority_stream ACTION_* string
    recommended_url: str
    recommended_action_label: str
    due_at: Optional[str] = None
    surfaces: Dict[str, bool] = field(default_factory=lambda: {"today": True, "command_center": True})
    policy: Dict[str, Any] = field(default_factory=dict)
    authority_snapshot: Dict[str, Any] = field(default_factory=dict)

    def to_mongo(self, *, client_id: str, property_id: str, requirement_id: str, requirement_code: str) -> Dict[str, Any]:
        gk = stable_gap_key(client_id, property_id, requirement_id, self.gap_kind)
        return {
            "gap_key": gk,
            "gap_kind": self.gap_kind,
            "severity": self.severity,
            "client_id": client_id,
            "property_id": property_id,
            "requirement_id": requirement_id,
            "requirement_code": requirement_code or None,
            "title": self.title,
            "description": self.description,
            "why_matters": self.why_matters,
            "recommended_action_detail": self.recommended_action_detail,
            "priority_score": self.priority_score,
            "action_type": self.action_type,
            "recommended_url": self.recommended_url,
            "recommended_action_label": self.recommended_action_label,
            "due_at": self.due_at,
            "surfaces": dict(self.surfaces),
            "policy": dict(self.policy),
            "authority_snapshot": dict(self.authority_snapshot),
        }


def _url_frag_property_req(property_id: str, req_code: str) -> str:
    from urllib.parse import quote

    if not property_id or not req_code:
        return ""
    return f"/properties/{property_id}#req={quote(req_code, safe='')}"


def derive_gaps_from_legacy_requirement_row(
    requirement: Dict[str, Any],
    *,
    property_doc: Optional[Dict[str, Any]],
    now: Optional[datetime] = None,
) -> List[ComplianceGap]:
    """Narrow legacy bridge when evidence_authority is not yet synced (migration window)."""
    now = now or datetime.now(timezone.utc)
    st = (requirement.get("status") or "").upper()
    rid = requirement.get("requirement_id") or ""
    pid = requirement.get("property_id") or ""
    cid = requirement.get("client_id") or ""
    code = _req_code(requirement)
    disp = requirement_label(code) if code else "Compliance item"
    req_url = _url_frag_property_req(pid, code) or "/documents"
    due = requirement.get("due_date")
    due_s = str(due) if due else None

    gaps: List[ComplianceGap] = []
    if st in ("NOT_REQUIRED",):
        return gaps

    if st in ("OVERDUE", "EXPIRED"):
        sev = _escalate_severity(_base_severity_from_requirement(requirement), 1)
        gaps.append(
            ComplianceGap(
                gap_kind=GAP_EXPIRED,
                severity=sev,
                title=f"Overdue (legacy read): {disp}",
                description=f"{disp} is overdue until evidence authority is synchronised for this obligation.",
                why_matters="Statutory and insurance exposure increases while renewal evidence is not confirmed on the authoritative record.",
                recommended_action_detail="Upload renewed evidence and confirm extracted dates, or wait for authority sync after verification.",
                priority_score=88,
                action_type="overdue_compliance",
                recommended_url=req_url,
                recommended_action_label="Review compliance",
                due_at=due_s,
                policy={
                    "create_issue_if_open": sev in (SEVERITY_HIGH, SEVERITY_CRITICAL),
                    "escalation_ready": sev == SEVERITY_CRITICAL,
                },
                authority_snapshot={"legacy_status": st, "mode": "legacy_mirror"},
            )
        )
    elif st == "EXPIRING_SOON":
        gaps.append(
            ComplianceGap(
                gap_kind=GAP_EXPIRING_SOON,
                severity=_base_severity_from_requirement(requirement),
                title=f"Due soon (legacy read): {disp}",
                description=f"{disp} is approaching expiry on the legacy calendar view.",
                why_matters="Renewal lead time reduces void-risk and enforcement exposure.",
                recommended_action_detail="Schedule renewal and upload evidence with confirmed expiry.",
                priority_score=72,
                action_type="certificate_expiring_soon",
                recommended_url=req_url,
                recommended_action_label="Review compliance",
                due_at=due_s,
                policy={"create_issue_if_open": False, "escalation_ready": False},
                authority_snapshot={"legacy_status": st, "mode": "legacy_mirror"},
            )
        )
    elif st in ("PENDING", "MISSING"):
        gaps.append(
            ComplianceGap(
                gap_kind=GAP_MISSING_EVIDENCE,
                severity=_escalate_severity(_base_severity_from_requirement(requirement), 0),
                title=f"Evidence needed (legacy read): {disp}",
                description=f"Required evidence for {disp} is not yet confirmed on the authoritative record.",
                why_matters="Without verified evidence, compliance cannot be attested for this obligation.",
                recommended_action_detail="Upload evidence and confirm extracted dates, or wait for evidence authority sync.",
                priority_score=44,
                action_type="missing_document",
                recommended_url=f"/documents?property_id={pid}" if pid else "/documents",
                recommended_action_label="Upload document",
                due_at=due_s,
                policy={"create_issue_if_open": False},
                authority_snapshot={"legacy_status": st, "mode": "legacy_mirror"},
            )
        )
    return gaps


def derive_gaps_from_authority(
    requirement: Dict[str, Any],
    *,
    property_doc: Optional[Dict[str, Any]],
    now: Optional[datetime] = None,
) -> List[ComplianceGap]:
    """Derive gaps from ``evidence_authority`` (versioned) + requirement/property context."""
    now = now or datetime.now(timezone.utc)
    ea = requirement.get("evidence_authority") or {}
    st = authority_state(requirement)
    rid = str(requirement.get("requirement_id") or "")
    pid = str(requirement.get("property_id") or "")
    cid = str(requirement.get("client_id") or "")
    code = _req_code(requirement)
    disp = requirement_label(code) if code else "Compliance item"
    req_url = _url_frag_property_req(pid, code) or "/documents"
    eff_exp = _parse_dt(ea.get("effective_expiry_date"))
    eff_exp_s = ea.get("effective_expiry_date")
    base = _base_severity_from_requirement(requirement)

    gaps: List[ComplianceGap] = []

    if (requirement.get("status") or "").upper() == "NOT_REQUIRED" or st == EA_NOT_REQUIRED:
        return gaps

    snap = {
        "state": st,
        "state_reason": ea.get("state_reason"),
        "version": ea.get("version"),
        "mismatch_flag": ea.get("mismatch_flag"),
        "mismatch_reason": ea.get("mismatch_reason"),
        "effective_expiry_date": ea.get("effective_expiry_date"),
    }

    # Delivery proof: only when explicit WO fields exist on requirement (optional extension point)
    wo_proof = requirement.get("compliance_delivery_proof_status") or requirement.get("delivery_proof_status")
    td_req = bool(requirement.get("tenant_delivery_required"))
    td_proof = (requirement.get("tenant_delivery_proof_status") or "").upper() or None
    # SENT = accepted by email provider only; gap closes on provider DELIVERED or tenant ACK (see tenant_delivery_reconciliation).
    if td_req and td_proof not in ("SUBMITTED", "DELIVERED", "ACKNOWLEDGED"):
        gaps.append(
            ComplianceGap(
                gap_kind=GAP_TENANT_DELIVERY_PROOF_MISSING,
                severity=_escalate_severity(base, 0),
                title=f"Tenant delivery proof required: {disp}",
                description="A governed compliance pack must be pushed to the tenant and recorded; no completed delivery is on file.",
                why_matters="Disputes and tribunal bundles require proof of what was sent, when, and to whom.",
                recommended_action_detail="Send the compliance pack to the tenant from the portal and retain the delivery record.",
                priority_score=50,
                action_type="missing_document",
                recommended_url=req_url,
                recommended_action_label="Send tenant pack",
                policy={"create_issue_if_open": False, "tenant_delivery_required": True},
                authority_snapshot={**snap, "tenant_delivery_proof_status": td_proof or "MISSING"},
            )
        )

    if wo_proof in ("MISSING", "REQUIRED", "NOT_SUBMITTED"):
        gaps.append(
            ComplianceGap(
                gap_kind=GAP_DELIVERY_PROOF_MISSING,
                severity=_escalate_severity(base, 0),
                title=f"Delivery proof required: {disp}",
                description="Operational delivery or inspection proof is required for this obligation but is not on record.",
                why_matters="Some jurisdictions or insurers require demonstrable completion, not only certificate evidence.",
                recommended_action_detail="Upload contractor completion pack or inspection sign-off where your playbook requires it.",
                priority_score=48,
                action_type="missing_document",
                recommended_url=req_url,
                recommended_action_label="Add proof",
                policy={"create_issue_if_open": base in (SEVERITY_HIGH, SEVERITY_CRITICAL)},
                authority_snapshot={**snap, "delivery_proof_status": wo_proof},
            )
        )

    if st == EA_MISSING:
        gaps.append(
            ComplianceGap(
                gap_kind=GAP_MISSING_EVIDENCE,
                severity=_escalate_severity(base, 0),
                title=f"Evidence missing: {disp}",
                description=f"No acceptable evidence is linked for {disp} at this property.",
                why_matters="Without evidence the obligation cannot be shown as satisfied.",
                recommended_action_detail="Upload the correct certificate or statutory record and confirm extracted dates.",
                priority_score=50 if base == SEVERITY_LOW else 58,
                action_type="missing_document",
                recommended_url=f"/documents?property_id={pid}" if pid else "/documents",
                recommended_action_label="Upload document",
                policy={"create_issue_if_open": base in (SEVERITY_HIGH, SEVERITY_CRITICAL)},
                authority_snapshot=snap,
            )
        )
        return gaps

    if st == EA_MISMATCH_FLAGGED:
        sev = _escalate_severity(base, 1)
        gaps.append(
            ComplianceGap(
                gap_kind=GAP_MISMATCHED_EVIDENCE,
                severity=sev,
                title=f"Evidence review required: {disp}",
                description=ea.get("mismatch_reason") or "Linked evidence does not satisfy this obligation under automated checks.",
                why_matters="Wrong-type or blocked evidence can create false confidence; resolve before renewal enforcement.",
                recommended_action_detail="Replace the file, confirm extraction, or ask an administrator to approve a governed override.",
                priority_score=62 if sev == SEVERITY_MEDIUM else 78,
                action_type="missing_document",
                recommended_url=f"/documents?property_id={pid}" if pid else "/documents",
                recommended_action_label="Review evidence",
                policy={"create_issue_if_open": sev in (SEVERITY_HIGH, SEVERITY_CRITICAL), "review_mismatch": True},
                authority_snapshot=snap,
            )
        )
        return gaps

    if st == EA_REJECTED:
        gaps.append(
            ComplianceGap(
                gap_kind=GAP_MISMATCHED_EVIDENCE,
                severity=_escalate_severity(base, 1),
                title=f"Evidence rejected: {disp}",
                description="Submitted evidence was rejected and cannot satisfy this obligation until replaced.",
                why_matters="Rejected files do not count toward compliance and may leave the property exposed.",
                recommended_action_detail="Upload a compliant replacement and confirm extracted dates.",
                priority_score=70,
                action_type="missing_document",
                recommended_url=f"/documents?property_id={pid}" if pid else "/documents",
                recommended_action_label="Replace document",
                policy={"create_issue_if_open": True},
                authority_snapshot=snap,
            )
        )
        return gaps

    if st in (EA_UPLOADED_UNCONFIRMED, EA_PENDING_ADMIN_REVIEW):
        gaps.append(
            ComplianceGap(
                gap_kind=GAP_EVIDENCE_UPLOADED_UNCONFIRMED,
                severity=_escalate_severity(base, 0),
                title=f"Evidence awaiting confirmation: {disp}",
                description="A file is uploaded but not yet verified or extraction is not confirmed.",
                why_matters="Dates and obligation satisfaction are not final until confirmation or verification completes.",
                recommended_action_detail="Confirm extracted dates in the vault or wait for administrator verification.",
                priority_score=46,
                action_type="missing_document",
                recommended_url=req_url,
                recommended_action_label="Confirm details",
                policy={"create_issue_if_open": False},
                authority_snapshot=snap,
            )
        )
        return gaps

    if st == EA_EXTRACTION_PENDING_CONFIRMATION:
        gaps.append(
            ComplianceGap(
                gap_kind=GAP_EVIDENCE_UPLOADED_UNCONFIRMED,
                severity=_escalate_severity(base, 0),
                title=f"Confirm extracted details: {disp}",
                description="Extraction is ready; confirm dates before they apply to renewal and scoring logic.",
                why_matters="Unconfirmed extraction leaves obligation dates uncertain.",
                recommended_action_detail="Open the document review flow and apply or correct extracted fields.",
                priority_score=52,
                action_type="missing_document",
                recommended_url=req_url,
                recommended_action_label="Confirm extraction",
                policy={"create_issue_if_open": False, "confirm_extraction": True},
                authority_snapshot=snap,
            )
        )
        return gaps

    if st == EA_VERIFIED_EXPIRED:
        overdue_days = 0
        if eff_exp:
            overdue_days = max(0, (now.date() - eff_exp.date()).days)
        sev = SEVERITY_CRITICAL if overdue_days >= 30 else SEVERITY_HIGH if overdue_days >= 7 else _escalate_severity(base, 1)
        gaps.append(
            ComplianceGap(
                gap_kind=GAP_EXPIRED,
                severity=sev,
                title=f"Expired: {disp}",
                description=f"Verified evidence for {disp} is past its effective expiry date.",
                why_matters="Expired statutory certificates invalidate compliance posture and common insurance conditions.",
                recommended_action_detail="Renew the obligation and upload fresh verified evidence with confirmed expiry.",
                priority_score=92 if sev == SEVERITY_CRITICAL else 86,
                action_type="overdue_compliance",
                recommended_url=req_url,
                recommended_action_label="Renew evidence",
                due_at=eff_exp_s,
                policy={"create_issue_if_open": sev in (SEVERITY_HIGH, SEVERITY_CRITICAL), "escalation_ready": sev == SEVERITY_CRITICAL},
                authority_snapshot=snap,
            )
        )
        return gaps

    if st == EA_VERIFIED_CURRENT and eff_exp:
        window = resolve_expiring_soon_days_for_requirement(requirement, property_doc, None)
        days = (eff_exp.date() - now.date()).days
        if 0 <= days <= window:
            gaps.append(
                ComplianceGap(
                    gap_kind=GAP_EXPIRING_SOON,
                    severity=_escalate_severity(base, 0),
                    title=f"Renewal window: {disp}",
                    description=f"{disp} expires within the configured renewal window ({window} days).",
                    why_matters="Renewing inside the window avoids last-minute void-risk and enforcement exposure.",
                    recommended_action_detail="Schedule renewal and upload updated evidence before expiry.",
                    priority_score=74,
                    action_type="certificate_expiring_soon",
                    recommended_url=req_url,
                    recommended_action_label="Plan renewal",
                    due_at=eff_exp_s,
                    policy={"create_issue_if_open": False},
                    authority_snapshot=snap,
                )
            )
        return gaps

    # EA_VERIFIED_CURRENT without near expiry → compliant (no gap)
    if st == EA_VERIFIED_CURRENT:
        return gaps

    # Unknown / future authority states → single actionable gap
    gaps.append(
        ComplianceGap(
            gap_kind=GAP_ACTION_REQUIRED,
            severity=SEVERITY_MEDIUM,
            title=f"Compliance attention: {disp}",
            description=f"Evidence authority state '{st or 'UNKNOWN'}' needs operator or product review.",
            why_matters="Unexpected authority states should be reviewed so dashboards stay trustworthy.",
            recommended_action_detail="Review the requirement, linked evidence, and authority sync logs.",
            priority_score=40,
            action_type="missing_document",
            recommended_url=req_url,
            recommended_action_label="Review",
            policy={"create_issue_if_open": False},
            authority_snapshot=snap,
        )
    )
    return gaps


def infer_compliance_gaps_for_requirement(
    requirement: Dict[str, Any],
    *,
    property_doc: Optional[Dict[str, Any]],
    now: Optional[datetime] = None,
) -> List[ComplianceGap]:
    """
    Single entry: prefer versioned evidence_authority; otherwise legacy mirror bridge
    or transitional AUTHORITY_UNSYNCED gap (low severity, Command Centre only).
    """
    now = now or datetime.now(timezone.utc)
    ea = requirement.get("evidence_authority") or {}
    synced = bool(requirement.get("evidence_authority_synced_at")) and int(ea.get("version") or 0) >= AUTHORITY_VERSION
    if synced and authority_state(requirement):
        return derive_gaps_from_authority(requirement, property_doc=property_doc, now=now)
    if synced:
        return []

    # Migration: legacy status bridge
    legacy = derive_gaps_from_legacy_requirement_row(requirement, property_doc=property_doc, now=now)
    if legacy:
        return legacy

    st = (requirement.get("status") or "").upper()
    if st in ("NOT_REQUIRED",):
        return []
    code = _req_code(requirement)
    disp = requirement_label(code) if code else "Compliance item"
    pid = str(requirement.get("property_id") or "")
    cid = str(requirement.get("client_id") or "")
    return [
        ComplianceGap(
            gap_kind=GAP_AUTHORITY_UNSYNCED,
            severity=SEVERITY_LOW,
            title=f"Evidence record pending sync: {disp}",
            description="This obligation does not yet have a versioned evidence authority snapshot.",
            why_matters="Once synchronised, gaps and renewals derive from a single auditable truth.",
            recommended_action_detail="Trigger a property compliance recalculation or wait for the next authority sync after document activity.",
            priority_score=22,
            action_type="missing_document",
            recommended_url="/compliance-score",
            recommended_action_label="View compliance overview",
            due_at=None,
            surfaces={"today": False, "command_center": True},
            policy={"create_issue_if_open": False},
            authority_snapshot={"mode": "authority_unsynced"},
        )
    ]


def gaps_to_priority_actions(gaps: List[ComplianceGap], requirement: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Map engine gaps to priority-action dicts (same shape as ``client_priority_stream._action``)."""
    ACTION_OVERDUE_COMPLIANCE = "overdue_compliance"
    ACTION_CERT_EXPIRING_SOON = "certificate_expiring_soon"
    ACTION_MISSING_DOCUMENT = "missing_document"

    cid = requirement.get("client_id")
    rid = requirement.get("requirement_id")
    pid = requirement.get("property_id")
    code = _req_code(requirement)
    src_upd = requirement.get("updated_at")
    if isinstance(src_upd, datetime):
        src_upd = src_upd.isoformat()
    out: List[Dict[str, Any]] = []
    for g in gaps:
        at = g.action_type
        if g.gap_kind == GAP_EXPIRING_SOON:
            at = ACTION_CERT_EXPIRING_SOON
        elif g.gap_kind == GAP_EXPIRED:
            at = ACTION_OVERDUE_COMPLIANCE
        elif g.gap_kind in (
            GAP_MISSING_EVIDENCE,
            GAP_MISMATCHED_EVIDENCE,
            GAP_EVIDENCE_UPLOADED_UNCONFIRMED,
            GAP_ACTION_REQUIRED,
            GAP_DELIVERY_PROOF_MISSING,
            GAP_TENANT_DELIVERY_PROOF_MISSING,
            GAP_AUTHORITY_UNSYNCED,
        ):
            at = ACTION_MISSING_DOCUMENT
        sev = (g.severity or SEVERITY_MEDIUM).lower()
        if sev not in ("high", "medium", "low", "critical"):
            sev = "medium"
        row: Dict[str, Any] = {
            "action_type": at,
            "title": g.title,
            "description": g.description,
            "priority": int(g.priority_score),
            "severity": sev,
            "related_property_id": pid,
            "related_requirement_id": rid,
            "recommended_url": g.recommended_url,
            "recommended_action_label": g.recommended_action_label,
            "requirement_code": code or None,
            "due_at": g.due_at,
            "source_updated_at": src_upd,
            "why_matters": g.why_matters,
            "recommended_action_detail": g.recommended_action_detail,
            "jurisdiction": requirement.get("jurisdiction"),
            "gap_kind": g.gap_kind,
            "gap_key": stable_gap_key(str(cid), str(pid), str(rid), g.gap_kind),
            "gap_severity": g.severity,
            "gap_surfaces": g.surfaces,
            "gap_policy": g.policy,
        }
        # Gap engine recommended_* are diagnostic / legacy alignment only — client CTAs follow
        # enriched requirement take_action (see client_priority_stream + unified_tasks_service).
        row["diagnostic_gap_recommended_url"] = g.recommended_url
        row["diagnostic_gap_recommended_action_label"] = g.recommended_action_label
        row["recommended_client_authority"] = "gap_engine_diagnostic"
        ta = requirement.get("take_action") if isinstance(requirement.get("take_action"), dict) else {}
        pri = ta.get("primary") if isinstance(ta.get("primary"), dict) else None
        if pri and pri.get("route"):
            row["recommended_url"] = str(pri.get("route") or "").strip() or g.recommended_url
        if pri and pri.get("label"):
            row["recommended_action_label"] = str(pri.get("label") or "").strip() or g.recommended_action_label
        if ta:
            row["canonical_take_action"] = ta
            row["recommended_client_authority"] = "canonical_take_action"
        if requirement.get("action_type"):
            row["canonical_requirement_action_type"] = requirement.get("action_type")
        rm_req = requirement.get("registry_metadata")
        if isinstance(rm_req, dict) and rm_req:
            row["registry_metadata"] = rm_req
        if requirement.get("display_label") is not None:
            row["display_label"] = requirement.get("display_label")
        out.append(row)
    return out
