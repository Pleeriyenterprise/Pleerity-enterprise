"""
Append-only audit log for applicability resolution (PR2 spine).

Only insert_one is supported — no updates or deletes from application code.
Not wired to reconciliation or operator APIs in PR2.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional

from services.applicability_provenance_constants import validate_resolution_source_for_persist

COLLECTION_NAME = "applicability_resolution_audit"

# Required on every audit row (PR2 contract)
REQUIRED_AUDIT_KEYS: List[str] = [
    "client_id",
    "property_id",
    "requirement_id",
    "event_type",
    "pipeline_applicability_state",
    "effective_applicability_state",
    "applicability_resolution_source",
    "actor",
    "created_at",
    "event_id",
]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _validate_actor(actor: Any) -> Dict[str, Any]:
    if not isinstance(actor, dict):
        raise ValueError("actor must be a dict")
    at = str(actor.get("type") or "").strip().lower()
    if at not in ("system", "user", "service"):
        raise ValueError("actor.type must be one of: system, user, service")
    out: Dict[str, Any] = {"type": at}
    if actor.get("id") is not None:
        out["id"] = str(actor.get("id"))
    if actor.get("email") is not None:
        out["email"] = str(actor.get("email"))
    return out


def build_applicability_resolution_audit_document(
    *,
    client_id: str,
    property_id: Optional[str],
    requirement_id: str,
    event_type: str,
    pipeline_applicability_state: str,
    effective_applicability_state: str,
    applicability_resolution_source: str,
    actor: Mapping[str, Any],
    created_at: Optional[datetime] = None,
    event_id: Optional[str] = None,
    resolution_reason_code: Optional[str] = None,
    notes: Optional[str] = None,
    extra: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Build a single audit document. Validates required fields and v1 resolution source.
    """
    if not str(client_id or "").strip():
        raise ValueError("client_id is required")
    if not str(requirement_id or "").strip():
        raise ValueError("requirement_id is required")
    et = str(event_type or "").strip()
    if not et:
        raise ValueError("event_type is required")
    ok, err = validate_resolution_source_for_persist(applicability_resolution_source)
    if not ok:
        raise ValueError(err)
    ps = str(pipeline_applicability_state or "").strip().upper()
    es = str(effective_applicability_state or "").strip().upper()
    if ps not in ("REQUIRED", "NOT_REQUIRED", "UNKNOWN"):
        raise ValueError("pipeline_applicability_state must be REQUIRED, NOT_REQUIRED, or UNKNOWN")
    if es not in ("REQUIRED", "NOT_REQUIRED", "UNKNOWN"):
        raise ValueError("effective_applicability_state must be REQUIRED, NOT_REQUIRED, or UNKNOWN")
    doc: Dict[str, Any] = {
        "event_id": str(event_id or uuid.uuid4()),
        "created_at": created_at or _utcnow(),
        "client_id": str(client_id).strip(),
        "property_id": str(property_id).strip() if property_id is not None and str(property_id).strip() else None,
        "requirement_id": str(requirement_id).strip(),
        "event_type": et,
        "pipeline_applicability_state": ps,
        "effective_applicability_state": es,
        "applicability_resolution_source": str(applicability_resolution_source).strip().upper(),
        "actor": _validate_actor(actor),
    }
    if resolution_reason_code is not None:
        doc["resolution_reason_code"] = str(resolution_reason_code).strip()
    if notes is not None:
        doc["notes"] = str(notes)
    if extra:
        for k, v in extra.items():
            if k in doc:
                raise ValueError(f"extra key {k!r} collides with reserved field")
            doc[str(k)] = v
    for k in REQUIRED_AUDIT_KEYS:
        if k not in doc:
            raise ValueError(f"missing required audit field: {k}")
        if k == "property_id":
            continue
        if doc[k] is None:
            raise ValueError(f"missing required audit field value: {k}")
    return doc


async def append_applicability_resolution_audit(
    db: Any,
    *,
    client_id: str,
    property_id: Optional[str],
    requirement_id: str,
    event_type: str,
    pipeline_applicability_state: str,
    effective_applicability_state: str,
    applicability_resolution_source: str,
    actor: Mapping[str, Any],
    created_at: Optional[datetime] = None,
    event_id: Optional[str] = None,
    resolution_reason_code: Optional[str] = None,
    notes: Optional[str] = None,
    extra: Optional[Mapping[str, Any]] = None,
) -> str:
    """
    Append one audit row (insert_one only). Returns inserted event_id string.
    """
    doc = build_applicability_resolution_audit_document(
        client_id=client_id,
        property_id=property_id,
        requirement_id=requirement_id,
        event_type=event_type,
        pipeline_applicability_state=pipeline_applicability_state,
        effective_applicability_state=effective_applicability_state,
        applicability_resolution_source=applicability_resolution_source,
        actor=actor,
        created_at=created_at,
        event_id=event_id,
        resolution_reason_code=resolution_reason_code,
        notes=notes,
        extra=extra,
    )
    res = await getattr(db, COLLECTION_NAME).insert_one(doc)
    if not res.inserted_id:
        raise RuntimeError("applicability_resolution_audit insert failed")
    return str(doc["event_id"])


__all__ = [
    "COLLECTION_NAME",
    "append_applicability_resolution_audit",
    "build_applicability_resolution_audit_document",
    "REQUIRED_AUDIT_KEYS",
]
