"""
Normalized compliance evidence records (non-document modes + document metadata).

Phase-1 evidence modes only; no workflow engine. Policy is driven by published registry
``registry_metadata.evidence_resolution`` with safe defaults when absent.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

EVIDENCE_MODE_DOCUMENT_UPLOAD = "DOCUMENT_UPLOAD"
EVIDENCE_MODE_STRUCTURED_DECLARATION = "STRUCTURED_DECLARATION"
EVIDENCE_MODE_CONTRACTOR_CONFIRMATION = "CONTRACTOR_CONFIRMATION"
EVIDENCE_MODE_INSPECTION_CHECKLIST = "INSPECTION_CHECKLIST"

ALL_EVIDENCE_MODES = frozenset(
    {
        EVIDENCE_MODE_DOCUMENT_UPLOAD,
        EVIDENCE_MODE_STRUCTURED_DECLARATION,
        EVIDENCE_MODE_CONTRACTOR_CONFIRMATION,
        EVIDENCE_MODE_INSPECTION_CHECKLIST,
    }
)

VERIFICATION_PENDING = "PENDING_REVIEW"
VERIFICATION_VERIFIED = "VERIFIED"
VERIFICATION_REJECTED = "REJECTED"
VERIFICATION_NOT_REQUIRED = "NOT_REQUIRED"

CONFIDENCE_HIGH = "HIGH"
CONFIDENCE_MEDIUM = "MEDIUM"
CONFIDENCE_LOW = "LOW"

# Product defaults until registry publishes explicit evidence_resolution (policy data, not UI).
DEFAULT_EVIDENCE_RESOLUTION_BY_REQUIREMENT_TYPE: Dict[str, Dict[str, Any]] = {
    "smoke_heat_alarms": {
        "allowed_evidence_modes": [
            EVIDENCE_MODE_DOCUMENT_UPLOAD,
            EVIDENCE_MODE_STRUCTURED_DECLARATION,
            EVIDENCE_MODE_CONTRACTOR_CONFIRMATION,
            EVIDENCE_MODE_INSPECTION_CHECKLIST,
        ],
        "primary_resolution_workflow": "GUIDED_EVIDENCE_RESOLUTION",
        "allow_medium_non_document_satisfaction": True,
        "allow_low_non_document_satisfaction": False,
    },
    "right_to_rent": {
        "allowed_evidence_modes": [
            EVIDENCE_MODE_STRUCTURED_DECLARATION,
            EVIDENCE_MODE_DOCUMENT_UPLOAD,
        ],
        "primary_resolution_workflow": "GUIDED_EVIDENCE_RESOLUTION",
        "allow_medium_non_document_satisfaction": True,
        "allow_low_non_document_satisfaction": False,
    },
    "hmo_fire_risk": {
        "allowed_evidence_modes": [
            EVIDENCE_MODE_DOCUMENT_UPLOAD,
            EVIDENCE_MODE_CONTRACTOR_CONFIRMATION,
            EVIDENCE_MODE_INSPECTION_CHECKLIST,
        ],
        "primary_resolution_workflow": "GUIDED_EVIDENCE_RESOLUTION",
        "allow_medium_non_document_satisfaction": True,
        "allow_low_non_document_satisfaction": False,
    },
    "hmo_fire_risk_evidence": {
        "allowed_evidence_modes": [
            EVIDENCE_MODE_DOCUMENT_UPLOAD,
            EVIDENCE_MODE_CONTRACTOR_CONFIRMATION,
            EVIDENCE_MODE_INSPECTION_CHECKLIST,
        ],
        "primary_resolution_workflow": "GUIDED_EVIDENCE_RESOLUTION",
        "allow_medium_non_document_satisfaction": True,
        "allow_low_non_document_satisfaction": False,
    },
}


def _norm_modes_list(raw: Any) -> List[str]:
    if not isinstance(raw, list):
        return []
    out: List[str] = []
    for x in raw:
        s = str(x or "").strip().upper()
        if s and s in ALL_EVIDENCE_MODES:
            out.append(s)
    return out


def normalize_evidence_resolution_dict(er: Dict[str, Any]) -> Dict[str, Any]:
    modes = _norm_modes_list(er.get("allowed_evidence_modes"))
    if not modes:
        modes = [EVIDENCE_MODE_DOCUMENT_UPLOAD]
    out: Dict[str, Any] = {
        "allowed_evidence_modes": modes,
        "primary_resolution_workflow": str(er.get("primary_resolution_workflow") or "").strip()
        or "GUIDED_EVIDENCE_RESOLUTION",
        "allow_medium_non_document_satisfaction": bool(er.get("allow_medium_non_document_satisfaction")),
        "allow_low_non_document_satisfaction": bool(er.get("allow_low_non_document_satisfaction")),
    }
    gpl = str(er.get("guided_primary_cta_label") or "").strip()
    if gpl:
        out["guided_primary_cta_label"] = gpl
    return out


# Single source for guided selector copy (API + docs). Keys are ALL_EVIDENCE_MODES values.
GUIDED_EVIDENCE_MODE_UI_COPY: Dict[str, Dict[str, str]] = {
    EVIDENCE_MODE_DOCUMENT_UPLOAD: {
        "label": "Upload evidence document",
        "description": "Best for certificates, reports, licences, or official records.",
        "typical_confidence": "High when verified.",
        "verification_note": "Documents are reviewed before they can satisfy compliance.",
    },
    EVIDENCE_MODE_STRUCTURED_DECLARATION: {
        "label": "Submit compliance declaration",
        "description": "Use when compliance is confirmed by a structured signed declaration.",
        "typical_confidence": "Medium or low depending on supporting detail.",
        "verification_note": "Declarations are reviewed before they can satisfy compliance.",
    },
    EVIDENCE_MODE_CONTRACTOR_CONFIRMATION: {
        "label": "Add contractor confirmation",
        "description": "Use when a contractor or competent person has completed relevant work.",
        "typical_confidence": "Medium to high depending on detail.",
        "verification_note": "Confirmations are reviewed before they can satisfy compliance.",
    },
    EVIDENCE_MODE_INSPECTION_CHECKLIST: {
        "label": "Complete inspection checklist",
        "description": "Use when the obligation is evidenced by a structured inspection record.",
        "typical_confidence": "Medium.",
        "verification_note": "Checklists are reviewed before they can satisfy compliance.",
    },
}


def guided_method_ui_rows_for_modes(modes: Sequence[str]) -> List[Dict[str, Any]]:
    """Rich rows for GET evidence-resolution and clients (one source of truth for copy)."""
    rows: List[Dict[str, Any]] = []
    for m in modes or []:
        tok = str(m or "").strip().upper()
        if not tok or tok not in ALL_EVIDENCE_MODES:
            continue
        base = GUIDED_EVIDENCE_MODE_UI_COPY.get(tok, {})
        rows.append(
            {
                "evidence_mode": tok,
                "label": base.get("label") or tok.replace("_", " ").title(),
                "description": base.get("description") or "",
                "typical_confidence": base.get("typical_confidence") or "",
                "verification_note": base.get("verification_note") or "",
            }
        )
    return rows


def effective_evidence_resolution(requirement: Dict[str, Any]) -> Dict[str, Any]:
    meta = requirement.get("registry_metadata") if isinstance(requirement.get("registry_metadata"), dict) else {}
    er = meta.get("evidence_resolution")
    if isinstance(er, dict) and _norm_modes_list(er.get("allowed_evidence_modes")):
        return normalize_evidence_resolution_dict(er)
    rt = str(requirement.get("requirement_type") or "").strip().lower()
    if rt in DEFAULT_EVIDENCE_RESOLUTION_BY_REQUIREMENT_TYPE:
        return normalize_evidence_resolution_dict(DEFAULT_EVIDENCE_RESOLUTION_BY_REQUIREMENT_TYPE[rt])
    return normalize_evidence_resolution_dict(
        {
            "allowed_evidence_modes": [EVIDENCE_MODE_DOCUMENT_UPLOAD],
            "primary_resolution_workflow": "LEGACY_DOCUMENT_UPLOAD",
            "allow_medium_non_document_satisfaction": False,
            "allow_low_non_document_satisfaction": False,
        }
    )


def evidence_mode_allowed_for_requirement(requirement: Dict[str, Any], mode: str) -> bool:
    policy = effective_evidence_resolution(requirement)
    m = str(mode or "").strip().upper()
    return m in set(policy.get("allowed_evidence_modes") or [])


def assign_confidence_for_new_record(
    *,
    evidence_mode: str,
    verification_status: str,
    payload: Dict[str, Any],
) -> str:
    """Initial confidence at creation time (may change after verification)."""
    mode = str(evidence_mode or "").strip().upper()
    vs = str(verification_status or "").strip().upper()
    if mode == EVIDENCE_MODE_DOCUMENT_UPLOAD:
        return CONFIDENCE_HIGH if vs == VERIFICATION_VERIFIED else CONFIDENCE_MEDIUM
    if mode == EVIDENCE_MODE_CONTRACTOR_CONFIRMATION:
        return CONFIDENCE_HIGH if vs == VERIFICATION_VERIFIED else CONFIDENCE_MEDIUM
    if mode == EVIDENCE_MODE_STRUCTURED_DECLARATION:
        if _structured_declaration_well_supported(payload):
            return CONFIDENCE_MEDIUM
        return CONFIDENCE_LOW
    if mode == EVIDENCE_MODE_INSPECTION_CHECKLIST:
        if _inspection_checklist_complete(payload):
            return CONFIDENCE_MEDIUM
        return CONFIDENCE_LOW
    return CONFIDENCE_MEDIUM


def _structured_declaration_well_supported(payload: Dict[str, Any]) -> bool:
    fields = payload.get("structured_fields") if isinstance(payload.get("structured_fields"), dict) else {}
    stmt = str(payload.get("declaration_statement") or "").strip()
    return len(stmt) >= 20 and len(fields) >= 1


def _inspection_checklist_complete(payload: Dict[str, Any]) -> bool:
    answers = payload.get("checklist_answers")
    if not isinstance(answers, dict) or not answers:
        return False
    return bool(str(payload.get("responsible_person") or "").strip()) and bool(
        str(payload.get("inspection_date") or "").strip()
    )


def recompute_confidence_for_record(rec: Dict[str, Any]) -> str:
    return assign_confidence_for_new_record(
        evidence_mode=str(rec.get("evidence_mode") or ""),
        verification_status=str(rec.get("verification_status") or ""),
        payload=rec.get("evidence_payload") if isinstance(rec.get("evidence_payload"), dict) else {},
    )


def active_sorted_evidence_candidates(records: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Non-archived, active compliance, not rejected — newest first within tiers."""
    active: List[Dict[str, Any]] = []
    for r in records or []:
        if not isinstance(r, dict):
            continue
        if r.get("archived") is True:
            continue
        if r.get("included_in_active_compliance") is False:
            continue
        if str(r.get("verification_status") or "").upper() == VERIFICATION_REJECTED:
            continue
        active.append(r)

    def tier(rec: Dict[str, Any]) -> Tuple[int, int, str]:
        vs = str(rec.get("verification_status") or "").upper()
        v_rank = 2 if vs == VERIFICATION_VERIFIED else (1 if vs == VERIFICATION_PENDING else 0)
        lvl = str(rec.get("evidence_confidence_level") or "").upper()
        c_rank = 3 if lvl == CONFIDENCE_HIGH else (2 if lvl == CONFIDENCE_MEDIUM else 1)
        ca = str(rec.get("created_at") or "")
        return (v_rank, c_rank, ca)

    active.sort(key=tier, reverse=True)
    return active


def non_document_record_satisfies_policy(
    *,
    record: Dict[str, Any],
    requirement: Dict[str, Any],
    policy: Dict[str, Any],
    is_critical_obligation: bool,
) -> bool:
    if str(record.get("verification_status") or "").upper() != VERIFICATION_VERIFIED:
        return False
    mode = str(record.get("evidence_mode") or "").upper()
    allowed = set(str(x).upper() for x in (policy.get("allowed_evidence_modes") or []) if x)
    if mode not in allowed:
        return False
    if mode == EVIDENCE_MODE_DOCUMENT_UPLOAD:
        return False
    level = str(record.get("evidence_confidence_level") or "").upper()
    if level == CONFIDENCE_HIGH:
        return True
    if level == CONFIDENCE_MEDIUM:
        if is_critical_obligation:
            return bool(policy.get("allow_medium_non_document_satisfaction"))
        return True
    if level == CONFIDENCE_LOW:
        if is_critical_obligation:
            return False
        return bool(policy.get("allow_low_non_document_satisfaction"))
    return False


def _evidence_coll(db: Any):
    """Motor accepts attribute access for this collection name."""
    return db.compliance_evidence_records


async def ensure_compliance_evidence_indexes(db) -> None:
    coll = _evidence_coll(db)
    await coll.create_index("evidence_record_id", unique=True)
    await coll.create_index([("client_id", 1), ("property_id", 1), ("requirement_id", 1)])
    await coll.create_index([("requirement_id", 1), ("archived", 1)])


async def list_evidence_records_for_requirement(
    db,
    *,
    client_id: str,
    requirement_id: str,
    include_archived: bool = False,
) -> List[Dict[str, Any]]:
    q: Dict[str, Any] = {"client_id": client_id, "requirement_id": requirement_id}
    if not include_archived:
        q["archived"] = {"$ne": True}
    cur = _evidence_coll(db).find(q, {"_id": 0}).sort("created_at", -1).limit(500)
    return await cur.to_list(500)


async def create_compliance_evidence_record(
    db,
    *,
    requirement: Dict[str, Any],
    evidence_mode: str,
    created_by_user_id: str,
    evidence_payload: Dict[str, Any],
    linked_document_ids: Optional[List[str]] = None,
    verification_status: str = VERIFICATION_PENDING,
) -> Dict[str, Any]:
    from services.requirement_client_runtime_surface import filter_requirement_rows_for_client_runtime_surfaces

    mode = str(evidence_mode or "").strip().upper()
    if mode not in ALL_EVIDENCE_MODES or mode == EVIDENCE_MODE_DOCUMENT_UPLOAD:
        raise ValueError("invalid_evidence_mode_for_this_endpoint")

    client_id = str(requirement.get("client_id") or "")
    property_id = str(requirement.get("property_id") or "")
    req_id = str(requirement.get("requirement_id") or "")
    client_doc = await db.clients.find_one({"client_id": client_id}, {"_id": 0}) or {}
    property_doc = await db.properties.find_one({"property_id": property_id, "client_id": client_id}, {"_id": 0})
    filtered = await filter_requirement_rows_for_client_runtime_surfaces(
        db,
        client_id=client_id,
        requirements=[requirement],
        client_doc=client_doc,
        properties=[property_doc] if property_doc else [],
    )
    if not filtered:
        raise ValueError("requirement_not_eligible_for_runtime_evidence")

    if not evidence_mode_allowed_for_requirement(requirement, mode):
        raise ValueError("evidence_mode_not_allowed_for_requirement")

    vs = str(verification_status or "").strip().upper()
    if vs not in {VERIFICATION_PENDING, VERIFICATION_VERIFIED, VERIFICATION_NOT_REQUIRED}:
        raise ValueError("invalid_verification_status")

    if not isinstance(evidence_payload, dict):
        raise ValueError("evidence_payload_required")
    _validate_payload_for_mode(mode, evidence_payload)

    confidence = assign_confidence_for_new_record(
        evidence_mode=mode, verification_status=vs, payload=evidence_payload
    )
    now = datetime.now(timezone.utc).isoformat()
    eid = f"cer_{uuid.uuid4().hex}"
    doc = {
        "evidence_record_id": eid,
        "requirement_id": req_id,
        "client_id": client_id,
        "property_id": property_id,
        "evidence_mode": mode,
        "created_at": now,
        "created_by_user_id": created_by_user_id,
        "verification_status": vs,
        "verified_by_user_id": None,
        "verified_at": None,
        "evidence_confidence_level": confidence,
        "evidence_payload": evidence_payload,
        "linked_document_ids": [str(x) for x in (linked_document_ids or []) if x],
        "audit_metadata": {"created_via": "client_compliance_evidence_api"},
        "included_in_active_compliance": True,
        "archived": False,
        "archived_reason": None,
    }
    await _evidence_coll(db).insert_one(doc)
    out = {k: v for k, v in doc.items() if k != "_id"}
    return out


def _validate_payload_for_mode(mode: str, payload: Dict[str, Any]) -> None:
    if mode == EVIDENCE_MODE_STRUCTURED_DECLARATION:
        if not str(payload.get("declaration_statement") or "").strip():
            raise ValueError("declaration_statement_required")
        if not isinstance(payload.get("structured_fields"), dict):
            raise ValueError("structured_fields_object_required")
    elif mode == EVIDENCE_MODE_CONTRACTOR_CONFIRMATION:
        for k in ("contractor_name", "contractor_company", "completion_date", "work_summary"):
            if not str(payload.get(k) or "").strip():
                raise ValueError(f"{k}_required")
    elif mode == EVIDENCE_MODE_INSPECTION_CHECKLIST:
        if not str(payload.get("inspection_date") or "").strip():
            raise ValueError("inspection_date_required")
        if not isinstance(payload.get("checklist_answers"), dict) or not payload.get("checklist_answers"):
            raise ValueError("checklist_answers_required")
        if not str(payload.get("responsible_person") or "").strip():
            raise ValueError("responsible_person_required")


async def apply_verification_decision(
    db,
    *,
    evidence_record_id: str,
    client_id: str,
    decision: str,
    actor_user_id: str,
) -> Optional[Dict[str, Any]]:
    decision_u = str(decision or "").strip().upper()
    if decision_u not in {"VERIFY", "REJECT"}:
        raise ValueError("invalid_decision")
    coll = _evidence_coll(db)
    existing = await coll.find_one({"evidence_record_id": evidence_record_id, "client_id": client_id}, {"_id": 0})
    if not existing:
        return None
    now = datetime.now(timezone.utc).isoformat()
    if decision_u == "VERIFY":
        new_status = VERIFICATION_VERIFIED
    else:
        new_status = VERIFICATION_REJECTED
    payload = existing.get("evidence_payload") if isinstance(existing.get("evidence_payload"), dict) else {}
    conf = assign_confidence_for_new_record(
        evidence_mode=str(existing.get("evidence_mode")),
        verification_status=new_status,
        payload=payload,
    )
    await coll.update_one(
        {"evidence_record_id": evidence_record_id, "client_id": client_id},
        {
            "$set": {
                "verification_status": new_status,
                "verified_by_user_id": actor_user_id,
                "verified_at": now,
                "evidence_confidence_level": conf,
            }
        },
    )
    out = {**existing, "verification_status": new_status, "verified_by_user_id": actor_user_id, "verified_at": now}
    out["evidence_confidence_level"] = conf
    return out


async def load_records_for_requirement_sync(db, requirement_id: str, client_id: str) -> List[Dict[str, Any]]:
    return await _evidence_coll(db).find(
        {"requirement_id": requirement_id, "client_id": client_id},
        {"_id": 0},
    ).to_list(500)


async def upsert_document_upload_evidence_for_linked_document(
    db,
    *,
    client_id: str,
    property_id: str,
    requirement_id: str,
    document_id: str,
    actor_user_id: Optional[str] = None,
    filename: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    When a document is stored with requirement_id, ensure a DOCUMENT_UPLOAD compliance_evidence_records
    row exists and references the document (idempotent per document_id).
    """
    doc_id = str(document_id or "").strip()
    rid = str(requirement_id or "").strip()
    cid = str(client_id or "").strip()
    if not doc_id or not rid or not cid:
        return None
    coll = _evidence_coll(db)
    existing = await coll.find_one(
        {
            "client_id": cid,
            "requirement_id": rid,
            "evidence_mode": EVIDENCE_MODE_DOCUMENT_UPLOAD,
            "linked_document_ids": doc_id,
            "archived": {"$ne": True},
        },
        {"_id": 0},
    )
    if existing:
        return existing
    requirement = await db.requirements.find_one({"requirement_id": rid, "client_id": cid}, {"_id": 0})
    if not requirement:
        return None
    pid = str(property_id or requirement.get("property_id") or "").strip()
    payload: Dict[str, Any] = {"document_id": doc_id, "source": "linked_document_upload"}
    if filename:
        payload["filename"] = str(filename)
    confidence = assign_confidence_for_new_record(
        evidence_mode=EVIDENCE_MODE_DOCUMENT_UPLOAD,
        verification_status=VERIFICATION_PENDING,
        payload=payload,
    )
    now = datetime.now(timezone.utc).isoformat()
    eid = f"cer_{uuid.uuid4().hex}"
    rec = {
        "evidence_record_id": eid,
        "requirement_id": rid,
        "client_id": cid,
        "property_id": pid,
        "evidence_mode": EVIDENCE_MODE_DOCUMENT_UPLOAD,
        "created_at": now,
        "created_by_user_id": str(actor_user_id or ""),
        "verification_status": VERIFICATION_PENDING,
        "verified_by_user_id": None,
        "verified_at": None,
        "evidence_confidence_level": confidence,
        "evidence_payload": payload,
        "linked_document_ids": [doc_id],
        "audit_metadata": {"created_via": "document_upload_normalization"},
        "included_in_active_compliance": True,
        "archived": False,
        "archived_reason": None,
    }
    await coll.insert_one(rec)
    return {k: v for k, v in rec.items() if k != "_id"}


async def safe_upsert_document_upload_evidence_for_linked_document(
    db,
    *,
    client_id: str,
    property_id: str,
    requirement_id: str,
    document_id: str,
    actor_user_id: Optional[str] = None,
    filename: Optional[str] = None,
    context: str = "document_link",
) -> None:
    """
    Same normalized DOCUMENT_UPLOAD evidence row as upsert_document_upload_evidence_for_linked_document,
    but swallows errors so upload/link flows never fail on evidence-record normalization.
    """
    try:
        await upsert_document_upload_evidence_for_linked_document(
            db,
            client_id=client_id,
            property_id=property_id,
            requirement_id=requirement_id,
            document_id=document_id,
            actor_user_id=actor_user_id,
            filename=filename,
        )
    except Exception as e:
        logger.warning(
            "DOCUMENT_UPLOAD evidence normalization skipped [%s] document_id=%s requirement_id=%s: %s",
            context,
            document_id,
            requirement_id,
            e,
        )
