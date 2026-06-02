"""
Review queue read models — discovery + operational visibility only.

Queue inclusion derives from governance truth (family, review_owner, queue_backed_review,
semantic_state). Lifecycle states alone must never determine queue visibility.

Verification mutations remain on existing compliance-evidence endpoints.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from services.cer_governance_presentation import GF_ORG  # deprecated alias of GF_SELF
from services.compliance_evidence_record_service import VERIFICATION_PENDING, batch_list_evidence_records_for_requirements
from services.requirement_client_runtime_surface import filter_requirement_rows_for_client_runtime_surfaces
from services.requirement_truth import enrich_requirements_for_client

ORG_REVIEW_OWNER = "org_admin"
ESCALATION_REVIEW_OWNER = "platform_admin_escalation"
PLATFORM_REVIEW_OWNER = "platform_admin"

# Role governance: org queue surfaces are for org reviewers, not every landlord operator.
ORG_REVIEWER_ROLES = frozenset({"ROLE_CLIENT_ADMIN"})


def is_org_reviewer_role(role: str) -> bool:
    return str(role or "").strip().upper() in ORG_REVIEWER_ROLES


def matches_org_review_queue(row: Dict[str, Any]) -> bool:
    """Deprecated — org review queue removed (REVIEW-ASSURANCE-SIMPLIFICATION-01)."""
    _ = row  # audit callers still pass rows for orphan detection
    return False


def matches_escalation_queue(row: Dict[str, Any]) -> bool:
    """Escalation queue inclusion — separate from platform document verification."""
    if row.get("queue_backed_review") is not True:
        return False
    if str(row.get("review_owner") or "") != ESCALATION_REVIEW_OWNER:
        return False
    return True


def _primary_pending_cer(records: List[Dict[str, Any]], requirement: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    ea = requirement.get("evidence_authority") if isinstance(requirement.get("evidence_authority"), dict) else {}
    primary_id = str(ea.get("primary_evidence_record_id") or requirement.get("evidence_record_id") or "").strip()
    active = [
        r
        for r in records or []
        if str(r.get("archived") or "").lower() not in ("true", "1")
        and str(r.get("status") or "").upper() not in ("REJECTED", "ARCHIVED")
    ]
    if primary_id:
        for rec in active:
            if str(rec.get("evidence_record_id") or "") == primary_id:
                return rec
    for rec in active:
        if str(rec.get("verification_status") or "").upper() == VERIFICATION_PENDING:
            return rec
    return active[0] if active else None


def _submitted_at(rec: Optional[Dict[str, Any]], requirement: Dict[str, Any]) -> Optional[str]:
    if rec:
        for key in ("submitted_at", "created_at", "updated_at"):
            val = str(rec.get(key) or "").strip()
            if val:
                return val
    ea = requirement.get("evidence_authority") if isinstance(requirement.get("evidence_authority"), dict) else {}
    return str(ea.get("evidence_last_submitted_at") or requirement.get("updated_at") or "").strip() or None


def build_queue_row_payload(
    requirement: Dict[str, Any],
    *,
    property_label: Optional[str] = None,
    cer_record: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    pid = str(requirement.get("property_id") or "")
    rid = str(requirement.get("requirement_id") or "")
    req_type = str(requirement.get("requirement_type") or requirement.get("requirement_code") or "")
    submitted = _submitted_at(cer_record, requirement)
    deeplink = f"/properties/{pid}?resolve_requirement={rid}" if pid and rid else None
    stale = False
    try:
        from services.cer_governance_presentation import stale_allowed_for_requirement

        stale = stale_allowed_for_requirement(requirement)
    except Exception:
        stale = False
    return {
        "requirement_id": rid,
        "property_id": pid,
        "property_label": property_label,
        "requirement_type": req_type,
        "display_label": requirement.get("display_label"),
        "truth_presentation_label": requirement.get("truth_presentation_label"),
        "truth_presentation_stage": requirement.get("truth_presentation_stage"),
        "semantic_state": requirement.get("semantic_state"),
        "governance_family": requirement.get("governance_family"),
        "review_owner": requirement.get("review_owner"),
        "queue_backed_review": requirement.get("queue_backed_review"),
        "stale_owner": requirement.get("stale_owner"),
        "stale_review": stale,
        "submitted_at": submitted,
        "evidence_record_id": (cer_record or {}).get("evidence_record_id"),
        "verification_status": (cer_record or {}).get("verification_status"),
        "review_deeplink": deeplink,
        "review_route": deeplink,
    }


def audit_orphan_queue_states(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Detect queue-backed semantics without valid review authority (presentation audit)."""
    orphans: List[Dict[str, Any]] = []
    for row in rows:
        qbr = row.get("queue_backed_review") is True
        owner = str(row.get("review_owner") or "").strip()
        family = str(row.get("governance_family") or "")
        if qbr and not owner:
            orphans.append(
                {
                    "requirement_id": row.get("requirement_id"),
                    "issue": "queue_backed_without_owner",
                    "governance_family": family,
                }
            )
        elif owner == ORG_REVIEW_OWNER:
            orphans.append(
                {
                    "requirement_id": row.get("requirement_id"),
                    "issue": "stale_org_review_owner",
                    "governance_family": family,
                    "review_owner": owner,
                }
            )
        elif owner and not qbr:
            orphans.append(
                {
                    "requirement_id": row.get("requirement_id"),
                    "issue": "review_owner_without_queue_backed",
                    "review_owner": owner,
                }
            )
    return orphans


async def _load_enriched_client_requirements(
    db,
    *,
    client_id: str,
    property_id: Optional[str] = None,
    limit: int = 500,
) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]], Dict[str, List[Dict[str, Any]]]]:
    query: Dict[str, Any] = {"client_id": client_id}
    if property_id:
        query["property_id"] = property_id
    requirements = await db.requirements.find(query, {"_id": 0}).limit(limit).to_list(limit)
    client_doc = await db.clients.find_one({"client_id": client_id}, {"_id": 0}) or {}
    prop_ids = list({str(r.get("property_id") or "") for r in requirements if r.get("property_id")})
    props: Dict[str, Dict[str, Any]] = {}
    if prop_ids:
        cur = db.properties.find({"client_id": client_id, "property_id": {"$in": prop_ids}}, {"_id": 0})
        async for p in cur:
            pid = p.get("property_id")
            if pid:
                props[str(pid)] = p
    filtered = await filter_requirement_rows_for_client_runtime_surfaces(
        db,
        client_id=client_id,
        requirements=requirements,
        client_doc=client_doc,
        properties=list(props.values()),
    )
    enriched, _ = await enrich_requirements_for_client(db, client_id, filtered)
    rid_list = [str(r.get("requirement_id") or "") for r in enriched if r.get("requirement_id")]
    cer_map = await batch_list_evidence_records_for_requirements(db, client_id=client_id, requirement_ids=rid_list)
    return enriched, props, cer_map


async def list_org_review_queue(
    db,
    *,
    client_id: str,
    property_id: Optional[str] = None,
    limit: int = 100,
) -> Dict[str, Any]:
    enriched, props, cer_map = await _load_enriched_client_requirements(
        db, client_id=client_id, property_id=property_id, limit=500
    )
    rows: List[Dict[str, Any]] = []
    for req in enriched:
        if not matches_org_review_queue(req):
            continue
        rid = str(req.get("requirement_id") or "")
        cer = _primary_pending_cer(cer_map.get(rid) or [], req)
        if cer and str(cer.get("verification_status") or "").upper() not in ("", VERIFICATION_PENDING):
            continue
        pid = str(req.get("property_id") or "")
        prop = props.get(pid) or {}
        prop_label = str(prop.get("address_line_1") or prop.get("name") or prop.get("property_name") or pid)
        rows.append(
            build_queue_row_payload(req, property_label=prop_label, cer_record=cer)
        )
        if len(rows) >= limit:
            break
    orphans = audit_orphan_queue_states(enriched)
    return {
        "queue_type": "org_admin_review",
        "deprecated": True,
        "deprecation_reason": "REVIEW-ASSURANCE-SIMPLIFICATION-01 — org review removed; use PLATFORM_REVIEWED escalation queue",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "items": rows,
        "total": len(rows),
        "governance_invariant": "deprecated_always_empty",
        "orphan_queue_states": orphans,
    }


async def list_escalation_review_queue(
    db,
    *,
    client_id: Optional[str] = None,
    limit: int = 100,
    skip: int = 0,
) -> Dict[str, Any]:
    """Platform escalation queue — not routine document verification."""
    query: Dict[str, Any] = {
        "$or": [
            {"evidence_authority.manual_review_flag": True},
            {"evidence_authority.state": {"$in": ["MISMATCH_FLAGGED", "EA_MISMATCH_FLAGGED"]}},
            {"evidence_state": "MISMATCH_FLAGGED"},
        ]
    }
    if client_id:
        query["client_id"] = client_id
    requirements = await db.requirements.find(query, {"_id": 0}).skip(skip).limit(min(limit * 3, 300)).to_list(min(limit * 3, 300))
    if not requirements:
        return {
            "queue_type": "platform_admin_escalation",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "items": [],
            "total": 0,
            "governance_invariant": "review_owner=platform_admin_escalation",
            "orphan_queue_states": [],
        }

    by_client: Dict[str, List[Dict[str, Any]]] = {}
    for r in requirements:
        cid = str(r.get("client_id") or "")
        by_client.setdefault(cid, []).append(r)

    rows: List[Dict[str, Any]] = []
    all_enriched: List[Dict[str, Any]] = []
    for cid, reqs in by_client.items():
        _enriched, props, cer_map = await _load_enriched_client_requirements(db, client_id=cid, limit=500)
        id_set = {str(x.get("requirement_id") or "") for x in reqs}
        for req in _enriched:
            if str(req.get("requirement_id") or "") not in id_set:
                continue
            all_enriched.append(req)
            if not matches_escalation_queue(req):
                continue
            rid = str(req.get("requirement_id") or "")
            cer = _primary_pending_cer(cer_map.get(rid) or [], req)
            pid = str(req.get("property_id") or "")
            prop = props.get(pid) or {}
            prop_label = str(prop.get("address_line_1") or prop.get("name") or prop.get("property_name") or pid)
            client_doc = await db.clients.find_one({"client_id": cid}, {"_id": 0, "full_name": 1, "customer_reference": 1}) or {}
            payload = build_queue_row_payload(req, property_label=prop_label, cer_record=cer)
            payload["client_id"] = cid
            payload["client_name"] = client_doc.get("full_name")
            payload["customer_reference"] = client_doc.get("customer_reference")
            rows.append(payload)
            if len(rows) >= limit:
                break
        if len(rows) >= limit:
            break

    return {
        "queue_type": "platform_admin_escalation",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "items": rows[:limit],
        "total": len(rows[:limit]),
        "governance_invariant": "review_owner=platform_admin_escalation",
        "orphan_queue_states": audit_orphan_queue_states(all_enriched),
        "note": "Separate from GET /api/admin/documents/pending-verification (D-family certificates)",
    }
