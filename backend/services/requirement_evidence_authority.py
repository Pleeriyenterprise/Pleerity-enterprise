"""
Authoritative requirement evidence + expiry truth (Compliance Vault Pro).

Single writer: ``sync_requirement_evidence_authority``. All compliance flows that
mutate documents or requirement dates should call it after persistence.

**Legacy fields** (`confirmed_expiry_date`, `extracted_expiry_date`, `due_date`,
`status`, `evidence_state` on the requirement row) may still exist for backward
compatibility but are **non-authoritative** once ``evidence_authority.version`` >= 1
and ``evidence_authority_synced_at`` is set. Readers must use
``utils.expiry_utils.get_effective_expiry_date`` and this module's
``authority_dict_for_api`` / ``map_authority_to_scoring_status``.

Scope types on **documents** (``evidence_scope_type``):
- PROPERTY — normal vault evidence; ``authoritative_property_id`` == property_id.
- PORTFOLIO — explicit client-wide evidence; ``authoritative_property_id`` is null;
  ``evidence_scope_id`` == ``client_id``.
- INTAKE_STAGING — pre-provision wizard uploads; excluded from property compliance
  until reconciled to PROPERTY scope (not ambiguous null).

See ``scripts/backfill_evidence_authority.py`` for idempotent migration.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, date
from typing import Any, Dict, List, Optional, Tuple

from models import DocumentStatus, RequirementStatus
from services.evidence_document_match_engine import document_blocks_verified_satisfaction

logger = logging.getLogger(__name__)

AUTHORITY_VERSION = 1

# Canonical evidence states (requirement.evidence_authority.state)
EA_MISSING = "MISSING"
EA_UPLOADED_UNCONFIRMED = "UPLOADED_UNCONFIRMED"
EA_EXTRACTION_PENDING_CONFIRMATION = "EXTRACTION_COMPLETE_PENDING_CONFIRMATION"
EA_PENDING_ADMIN_REVIEW = "PENDING_ADMIN_REVIEW"
EA_VERIFIED_CURRENT = "VERIFIED_CURRENT"
EA_VERIFIED_EXPIRED = "VERIFIED_EXPIRED"
EA_REJECTED = "REJECTED"
EA_MISMATCH_FLAGGED = "MISMATCH_FLAGGED"
EA_NOT_REQUIRED = "NOT_REQUIRED"

SCOPE_PROPERTY = "PROPERTY"
SCOPE_PORTFOLIO = "PORTFOLIO"
SCOPE_INTAKE_STAGING = "INTAKE_STAGING"
# Backfill / ops: explicit quarantine when ownership cannot be inferred (never treat as property evidence)
SCOPE_UNRESOLVED = "UNRESOLVED"


def _parse_dt(val: Any) -> Optional[datetime]:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.replace(tzinfo=timezone.utc) if val.tzinfo is None else val.astimezone(timezone.utc)
    try:
        s = (val.replace("Z", "+00:00") if isinstance(val, str) else str(val)).strip()
        d = datetime.fromisoformat(s)
        if d.tzinfo is None:
            return d.replace(tzinfo=timezone.utc)
        return d.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def _doc_expiry(doc: Dict[str, Any]) -> Optional[datetime]:
    exp = doc.get("expiry_date")
    if exp is not None:
        d = _parse_dt(exp)
        if d:
            return d
    ai = doc.get("ai_extraction") or {}
    data = ai.get("data") or {}
    if data.get("expiry_date"):
        return _parse_dt(data.get("expiry_date"))
    ad = doc.get("ai_extracted_data") or {}
    if ad.get("expiry_date"):
        return _parse_dt(ad.get("expiry_date"))
    return None


def _doc_issue(doc: Dict[str, Any]) -> Optional[datetime]:
    for key in ("issue_date",):
        v = doc.get(key)
        if v:
            return _parse_dt(v)
    ai = doc.get("ai_extraction") or {}
    data = ai.get("data") or {}
    if data.get("issue_date"):
        return _parse_dt(data.get("issue_date"))
    ad = doc.get("ai_extracted_data") or {}
    if ad.get("issue_date"):
        return _parse_dt(ad.get("issue_date"))
    return None


def _verified_at(doc: Dict[str, Any]) -> Optional[datetime]:
    v = doc.get("verified_at")
    if v:
        return _parse_dt(v)
    if (doc.get("status") or "").upper() == DocumentStatus.VERIFIED.value:
        return _parse_dt(doc.get("updated_at") or doc.get("uploaded_at"))
    return None


def _doc_ts(d: Dict[str, Any]) -> datetime:
    return (
        _parse_dt(d.get("updated_at"))
        or _parse_dt(d.get("uploaded_at"))
        or datetime.min.replace(tzinfo=timezone.utc)
    )


def document_evidence_compatible_with_requirement(doc: Dict[str, Any], requirement: Dict[str, Any]) -> bool:
    """
    Property-scoped requirements may only be evidenced by PROPERTY-scoped documents
    whose authoritative property matches the requirement (legacy rows: empty scope + property_id).
    """
    st = (doc.get("evidence_scope_type") or "").strip().upper()
    if st in (SCOPE_PORTFOLIO, SCOPE_INTAKE_STAGING, SCOPE_UNRESOLVED):
        return False
    pid_req = (requirement.get("property_id") or "").strip()
    if not pid_req:
        return False
    if st == SCOPE_PROPERTY or st == "":
        ap = (doc.get("authoritative_property_id") or doc.get("property_id") or "").strip()
        return ap == pid_req
    return False


def _pick_primary_evidence_doc(docs: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Prefer newest VERIFIED; then mismatch-flagged; else newest non-rejected; else newest rejected."""
    active: List[Dict[str, Any]] = []
    for d in docs:
        if d.get("deleted") is True or d.get("quarantined") is True or d.get("malware_flagged") is True:
            continue
        active.append(d)
    if not active:
        return None

    def st_u(d: Dict[str, Any]) -> str:
        return (d.get("status") or "").upper()

    verified = [d for d in active if st_u(d) == DocumentStatus.VERIFIED.value]
    if verified:
        verified.sort(key=_doc_ts, reverse=True)
        return verified[0]
    mism = [d for d in active if d.get("requirement_evidence_mismatch") is True]
    if mism:
        mism.sort(key=_doc_ts, reverse=True)
        return mism[0]
    non_rej = [d for d in active if st_u(d) != DocumentStatus.REJECTED.value]
    if non_rej:
        non_rej.sort(key=_doc_ts, reverse=True)
        return non_rej[0]
    rejected = [d for d in active if st_u(d) == DocumentStatus.REJECTED.value]
    if rejected:
        rejected.sort(key=_doc_ts, reverse=True)
        return rejected[0]
    return None


def _compute_authority(
    requirement: Dict[str, Any],
    documents: List[Dict[str, Any]],
    *,
    property_doc: Optional[Dict[str, Any]],
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Returns (evidence_authority_blob, legacy_mirror_updates_for_requirement).
    legacy_mirror keeps workflow jobs working until all readers use authority.
    """
    rid = requirement.get("requirement_id")
    now = datetime.now(timezone.utc)
    today = now.date()

    applicability = (requirement.get("applicability") or "UNKNOWN").strip().upper()
    if applicability == "NOT_REQUIRED":
        blob = {
            "version": AUTHORITY_VERSION,
            "state": EA_NOT_REQUIRED,
            "state_reason": "applicability_not_required",
            "effective_expiry_date": None,
            "effective_expiry_is_null": True,
            "effective_issue_date": None,
            "effective_verified_document_id": None,
            "expiry_source": "NONE",
            "evidence_last_verified_at": None,
            "evidence_last_updated_at": now.isoformat(),
            "mismatch_flag": False,
            "mismatch_reason": None,
            "evidence_confidence": None,
            "authoritative_property_id": requirement.get("property_id"),
            "evidence_scope_type": SCOPE_PROPERTY,
            "evidence_scope_id": requirement.get("property_id"),
        }
        mirror = {
            "status": RequirementStatus.NOT_REQUIRED.value,
            "evidence_state": "NOT_REQUIRED",
            "expiry_source": "NONE",
        }
        return blob, mirror

    linked = [d for d in documents if (d.get("requirement_id") or "") == rid]
    linked_compatible = [d for d in linked if document_evidence_compatible_with_requirement(d, requirement)]
    scope_mismatch = bool(linked) and not linked_compatible
    primary = _pick_primary_evidence_doc(linked_compatible)
    evidence_match_blocks_satisfaction = bool(
        primary and document_blocks_verified_satisfaction(primary)
    )

    mismatch_flag = False
    mismatch_reason: Optional[str] = None
    if scope_mismatch:
        mismatch_flag = True
        mismatch_reason = "evidence_scope_incompatible_with_requirement"
    elif evidence_match_blocks_satisfaction:
        mismatch_flag = True
        mismatch_reason = (
            (primary.get("mismatch_reason_text") if primary else None)
            or (primary.get("requirement_evidence_mismatch_reason") if primary else None)
            or "evidence_document_match_blocks_satisfaction"
        )
        if isinstance(mismatch_reason, str):
            mismatch_reason = mismatch_reason.strip()[:500]
    elif primary and primary.get("requirement_evidence_mismatch") is True:
        mismatch_flag = True
        mismatch_reason = (primary.get("requirement_evidence_mismatch_reason") or "mismatch").strip()[:500]

    state = EA_MISSING
    state_reason = "no_evidence_document"
    eff_expiry: Optional[datetime] = None
    eff_issue: Optional[datetime] = None
    eff_doc_id: Optional[str] = None
    expiry_src = "NONE"
    confidence: Optional[float] = None
    last_verified: Optional[str] = None

    if scope_mismatch:
        state = EA_MISMATCH_FLAGGED
        state_reason = "evidence_scope_incompatible_with_requirement"
        eff_doc_id = (linked[0].get("document_id") if linked else None)
    elif not primary:
        state = EA_MISSING
        state_reason = "no_evidence_document"
    elif mismatch_flag:
        state = EA_MISMATCH_FLAGGED
        state_reason = (
            "evidence_document_match_blocks_satisfaction"
            if evidence_match_blocks_satisfaction
            else "requirement_document_type_mismatch"
        )
        eff_doc_id = primary.get("document_id")
    elif (primary.get("status") or "").upper() == DocumentStatus.REJECTED.value:
        state = EA_REJECTED
        state_reason = "evidence_rejected"
        eff_doc_id = primary.get("document_id")
    elif (primary.get("status") or "").upper() == DocumentStatus.VERIFIED.value and not evidence_match_blocks_satisfaction:
        eff_doc_id = primary.get("document_id")
        eff_expiry = _doc_expiry(primary)
        eff_issue = _doc_issue(primary)
        va = _verified_at(primary)
        last_verified = va.isoformat() if va else None
        confidence = primary.get("confidence_score")
        if isinstance(confidence, str):
            try:
                confidence = float(confidence)
            except ValueError:
                confidence = None
        if eff_expiry is None:
            # Verified but no machine-readable expiry on document — use confirmed requirement path
            eff_expiry = _parse_dt(requirement.get("confirmed_expiry_date")) or _parse_dt(
                requirement.get("extracted_expiry_date")
            )
            expiry_src = "CONFIRMED" if requirement.get("confirmed_expiry_date") else (
                "EXTRACTED" if requirement.get("extracted_expiry_date") else "NONE"
            )
        else:
            expiry_src = "VERIFIED_DOCUMENT"
        if eff_expiry is None:
            state = EA_VERIFIED_CURRENT
            state_reason = "verified_no_expiry_on_file"
        else:
            if eff_expiry.date() < today:
                state = EA_VERIFIED_EXPIRED
                state_reason = "verified_document_expired"
            else:
                state = EA_VERIFIED_CURRENT
                state_reason = "verified_current"
    elif (primary.get("status") or "").upper() == DocumentStatus.UPLOADED.value:
        ext_st = (primary.get("extraction_status") or (primary.get("ai_extraction") or {}).get("status") or "").lower()
        if ext_st in ("extracted", "completed", "needs_review"):
            state = EA_EXTRACTION_PENDING_CONFIRMATION
            state_reason = "awaiting_client_apply_or_review"
        else:
            state = EA_PENDING_ADMIN_REVIEW
            state_reason = "uploaded_pending_admin"
        eff_doc_id = primary.get("document_id")
    elif (primary.get("status") or "").upper() == DocumentStatus.PENDING.value:
        ext_st = (primary.get("extraction_status") or (primary.get("ai_extraction") or {}).get("status") or "").lower()
        if ext_st in ("extracted", "completed", "needs_review"):
            state = EA_EXTRACTION_PENDING_CONFIRMATION
            state_reason = "awaiting_client_apply_or_review"
        else:
            state = EA_PENDING_ADMIN_REVIEW
            state_reason = "uploaded_pending_admin"
        eff_doc_id = primary.get("document_id")
    else:
        state = EA_UPLOADED_UNCONFIRMED
        state_reason = "uploaded_not_verified"
        eff_doc_id = primary.get("document_id")

    # If we have confirmed requirement expiry (user/admin) and no verified doc expiry, prefer it
    if eff_expiry is None and not mismatch_flag and state not in (EA_REJECTED, EA_MISSING, EA_MISMATCH_FLAGGED):
        cexp = _parse_dt(requirement.get("confirmed_expiry_date"))
        if cexp:
            eff_expiry = cexp
            expiry_src = "CONFIRMED"
        else:
            eexp = _parse_dt(requirement.get("extracted_expiry_date"))
            if eexp:
                eff_expiry = eexp
                expiry_src = "EXTRACTED"

    blob = {
        "version": AUTHORITY_VERSION,
        "state": state,
        "state_reason": state_reason,
        "effective_expiry_date": eff_expiry.isoformat() if eff_expiry else None,
        "effective_expiry_is_null": eff_expiry is None,
        "effective_issue_date": eff_issue.isoformat() if eff_issue else None,
        "effective_verified_document_id": eff_doc_id,
        "expiry_source": expiry_src,
        "evidence_last_verified_at": last_verified,
        "evidence_last_updated_at": now.isoformat(),
        "mismatch_flag": mismatch_flag,
        "mismatch_reason": mismatch_reason,
        "evidence_confidence": confidence,
        "authoritative_property_id": requirement.get("property_id"),
        "evidence_scope_type": SCOPE_PROPERTY,
        "evidence_scope_id": requirement.get("property_id"),
        "predicted_document_type": (primary.get("predicted_document_type") if primary else None),
        "match_outcome": (primary.get("match_outcome") if primary else None),
        "match_confidence": (primary.get("match_confidence") if primary else None),
        "mismatch_reason_code": (primary.get("mismatch_reason_code") if primary else None),
        "evidence_match_blocks_satisfaction": evidence_match_blocks_satisfaction,
    }

    # Legacy mirror: map authority to existing requirement.status + due_date for jobs/scoring v2
    mirror_status = RequirementStatus.PENDING.value
    mirror_due: Optional[str] = None
    if state == EA_NOT_REQUIRED:
        mirror_status = RequirementStatus.NOT_REQUIRED.value
    elif state in (EA_MISSING, EA_UPLOADED_UNCONFIRMED, EA_EXTRACTION_PENDING_CONFIRMATION, EA_PENDING_ADMIN_REVIEW):
        mirror_status = RequirementStatus.PENDING.value
    elif state == EA_MISMATCH_FLAGGED:
        mirror_status = RequirementStatus.PENDING.value
    elif state == EA_REJECTED:
        mirror_status = RequirementStatus.PENDING.value
    elif state == EA_VERIFIED_EXPIRED:
        mirror_status = RequirementStatus.OVERDUE.value
    elif state == EA_VERIFIED_CURRENT:
        if eff_expiry:
            days = (eff_expiry - now).days
            from services.compliance_expiry_policy import resolve_expiring_soon_days_for_requirement

            window = resolve_expiring_soon_days_for_requirement(requirement, property_doc, None)
            if days < 0:
                mirror_status = RequirementStatus.OVERDUE.value
            elif days <= window:
                mirror_status = RequirementStatus.EXPIRING_SOON.value
            else:
                mirror_status = RequirementStatus.COMPLIANT.value
        else:
            mirror_status = RequirementStatus.COMPLIANT.value
    if eff_expiry:
        mirror_due = eff_expiry.isoformat()

    mirror = {
        "status": mirror_status,
        "due_date": mirror_due or requirement.get("due_date"),
        "evidence_state": state,
        "expiry_source": expiry_src if expiry_src != "NONE" else (requirement.get("expiry_source") or "NONE"),
    }
    if eff_expiry and expiry_src == "VERIFIED_DOCUMENT":
        mirror["confirmed_expiry_date"] = eff_expiry.isoformat()

    return blob, mirror


async def sync_requirement_evidence_authority(
    db,
    requirement_id: str,
    *,
    property_id_hint: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Recompute and persist evidence_authority (+ legacy mirror). Returns blob or None."""
    q: Dict[str, Any] = {"requirement_id": requirement_id}
    if property_id_hint:
        q["property_id"] = property_id_hint
    requirement = await db.requirements.find_one(q, {"_id": 0})
    if not requirement:
        requirement = await db.requirements.find_one({"requirement_id": requirement_id}, {"_id": 0})
    if not requirement:
        logger.warning("sync_requirement_evidence_authority: requirement not found %s", requirement_id)
        return None

    pid = requirement.get("property_id") or property_id_hint
    property_doc = None
    if pid:
        property_doc = await db.properties.find_one({"property_id": pid}, {"_id": 0})

    docs = await db.documents.find(
        {"requirement_id": requirement_id, "client_id": requirement.get("client_id")},
        {"_id": 0},
    ).to_list(200)

    blob, mirror = _compute_authority(requirement, docs, property_doc=property_doc)
    now = datetime.now(timezone.utc).isoformat()
    await db.requirements.update_one(
        {"requirement_id": requirement_id},
        {
            "$set": {
                "evidence_authority": blob,
                "evidence_authority_synced_at": now,
                **mirror,
            }
        },
    )
    merged = {**requirement, "evidence_authority": blob, "evidence_authority_synced_at": now, **mirror}
    try:
        from services.compliance_gap_sync import sync_compliance_gaps_for_requirement

        sync_out = await sync_compliance_gaps_for_requirement(db, merged, property_doc=property_doc)
        if sync_out.get("errors"):
            logger.warning(
                "sync_compliance_gaps_for_requirement reported errors requirement_id=%s: %s",
                requirement_id,
                sync_out["errors"],
            )
    except Exception as gap_exc:
        logger.warning("sync_compliance_gaps_for_requirement failed requirement_id=%s: %s", requirement_id, gap_exc)
    return blob


async def sync_for_documents_touching(db, *, document_id: Optional[str] = None, requirement_id: Optional[str] = None):
    """Convenience: sync after a document mutation."""
    if requirement_id:
        await sync_requirement_evidence_authority(db, requirement_id)
        return
    if not document_id:
        return
    doc = await db.documents.find_one({"document_id": document_id}, {"_id": 0, "requirement_id": 1})
    rid = (doc or {}).get("requirement_id")
    if rid:
        await sync_requirement_evidence_authority(db, str(rid))


def map_authority_to_scoring_status(requirement: Dict[str, Any]) -> Optional[str]:
    """Map canonical authority state to compliance_scoring_v2 status strings."""
    ea = requirement.get("evidence_authority") or {}
    if int(ea.get("version") or 0) < AUTHORITY_VERSION:
        return None
    st = (ea.get("state") or "").upper()
    mapping = {
        EA_NOT_REQUIRED: "NOT_APPLICABLE",
        EA_MISSING: "MISSING",
        EA_UPLOADED_UNCONFIRMED: "NEEDS_REVIEW",
        EA_EXTRACTION_PENDING_CONFIRMATION: "NEEDS_REVIEW",
        EA_PENDING_ADMIN_REVIEW: "NEEDS_REVIEW",
        EA_MISMATCH_FLAGGED: "NEEDS_REVIEW",
        EA_REJECTED: "MISSING",
        EA_VERIFIED_CURRENT: "VALID",
        EA_VERIFIED_EXPIRED: "EXPIRED",
    }
    return mapping.get(st)


def authority_state(requirement: Dict[str, Any]) -> Optional[str]:
    """Return canonical evidence authority state when synced and versioned."""
    ea = requirement.get("evidence_authority") or {}
    if requirement.get("evidence_authority_synced_at") and int(ea.get("version") or 0) >= AUTHORITY_VERSION:
        st = str(ea.get("state") or "").strip().upper()
        return st or None
    return None


def authority_runtime_requirement_status(requirement: Dict[str, Any]) -> Optional[str]:
    """
    Authoritative runtime status projection for consumers that previously read requirement.status.
    Returns None for unsynced legacy rows (caller may fall back temporarily).
    """
    st = authority_state(requirement)
    if not st:
        return None
    if st == EA_NOT_REQUIRED:
        return RequirementStatus.NOT_REQUIRED.value
    if st == EA_VERIFIED_CURRENT:
        return RequirementStatus.COMPLIANT.value
    if st == EA_VERIFIED_EXPIRED:
        return RequirementStatus.OVERDUE.value
    if st in (
        EA_MISSING,
        EA_UPLOADED_UNCONFIRMED,
        EA_EXTRACTION_PENDING_CONFIRMATION,
        EA_PENDING_ADMIN_REVIEW,
        EA_REJECTED,
        EA_MISMATCH_FLAGGED,
    ):
        return RequirementStatus.PENDING.value
    return RequirementStatus.PENDING.value


def detect_requirement_mirror_drift(requirement: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compare authority snapshot with mirrored legacy fields and return drift diagnostics.
    """
    st = authority_state(requirement)
    if not st:
        return {"has_authority": False, "drift": False, "reasons": []}
    expected_status = authority_runtime_requirement_status(requirement)
    expected_evidence_state = st
    due = requirement.get("due_date")
    ea = requirement.get("evidence_authority") or {}
    exp_due = ea.get("effective_expiry_date")
    reasons: List[str] = []
    if expected_status and str(requirement.get("status") or "").upper() != str(expected_status).upper():
        reasons.append("status_mismatch")
    if str(requirement.get("evidence_state") or "").upper() != str(expected_evidence_state).upper():
        reasons.append("evidence_state_mismatch")
    if exp_due:
        # normalize string compare without timezone coercion side-effects
        if str(due or "")[:19] != str(exp_due or "")[:19]:
            reasons.append("due_date_mismatch")
    return {
        "has_authority": True,
        "drift": len(reasons) > 0,
        "reasons": reasons,
        "expected": {
            "status": expected_status,
            "evidence_state": expected_evidence_state,
            "due_date": exp_due,
        },
    }


async def count_mirror_drift_rows(db: Any) -> int:
    """Count requirements with synced authority where mirror fields disagree (ops / staging metric)."""
    n = 0
    async for req in db.requirements.find(
        {
            "evidence_authority_synced_at": {"$ne": None},
            "evidence_authority.version": {"$gte": AUTHORITY_VERSION},
        },
        {"_id": 0},
    ):
        if detect_requirement_mirror_drift(req).get("drift"):
            n += 1
    return n


def authority_gap_missing_states() -> List[str]:
    """Mongo query helper: states treated as missing / attention for gap automation."""
    return [
        EA_MISSING,
        EA_UPLOADED_UNCONFIRMED,
        EA_EXTRACTION_PENDING_CONFIRMATION,
        EA_PENDING_ADMIN_REVIEW,
        EA_MISMATCH_FLAGGED,
        EA_REJECTED,
        EA_VERIFIED_EXPIRED,
    ]


def normalize_document_evidence_scope(
    *,
    property_id: Optional[str],
    client_id: str,
    evidence_scope_type: str,
    intake_session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Returns fields to $set on a compliance document.
    Raises ValueError if invalid.
    """
    t = (evidence_scope_type or SCOPE_PROPERTY).strip().upper()
    if t == SCOPE_PROPERTY:
        if not (property_id or "").strip():
            raise ValueError("PROPERTY scope requires property_id")
        pid = str(property_id).strip()
        return {
            "evidence_scope_type": SCOPE_PROPERTY,
            "evidence_scope_id": pid,
            "authoritative_property_id": pid,
            "property_id": pid,
        }
    if t == SCOPE_PORTFOLIO:
        cid = str(client_id).strip()
        return {
            "evidence_scope_type": SCOPE_PORTFOLIO,
            "evidence_scope_id": cid,
            "authoritative_property_id": None,
            "property_id": None,
        }
    if t == SCOPE_INTAKE_STAGING:
        sid = (intake_session_id or "").strip()
        if not sid:
            raise ValueError("INTAKE_STAGING scope requires intake_session_id")
        return {
            "evidence_scope_type": SCOPE_INTAKE_STAGING,
            "evidence_scope_id": sid,
            "authoritative_property_id": None,
            "property_id": None,
        }
    raise ValueError("evidence_scope_type must be PROPERTY, PORTFOLIO, or INTAKE_STAGING")


def authority_dict_for_api(requirement: Dict[str, Any]) -> Dict[str, Any]:
    """Stable shape for API extensions (read-only projection)."""
    ea = requirement.get("evidence_authority") or {}
    return {
        "evidence_authority": ea,
        "evidence_authority_synced_at": requirement.get("evidence_authority_synced_at"),
    }


def preview_authority(
    requirement: Dict[str, Any],
    documents: List[Dict[str, Any]],
    *,
    property_doc: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Test / admin helper: compute authority blob + legacy mirror without persisting."""
    blob, mirror = _compute_authority(requirement, documents, property_doc=property_doc)
    return {"evidence_authority": blob, "mirror": mirror}
