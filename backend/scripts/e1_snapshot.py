"""
Shared read-only snapshots and authority analysis for E1 evidence verification.
Verification/governance only — no authority-writer changes.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional, Tuple

from scripts.c2_snapshot import fp32, select_control_entity  # noqa: F401

from services.document_operational_state import derive_document_operational_state
from services.evidence_review_migration import effective_evidence_review_state

__all__ = [
    "fp32",
    "select_control_entity",
    "authority_source_rank",
    "resolve_authority_precedence",
    "authority_precedence_snapshot",
    "authority_cardinality_snapshot",
    "authority_fingerprint",
    "supersession_state_fingerprint",
    "supersession_transition_matrix",
    "authority_collapse_snapshot",
    "collapse_boundedness_snapshot",
    "reconciliation_suppression_fingerprint",
    "human_review_preservation_snapshot",
    "lineage_boundedness_snapshot",
    "authority_explainability_snapshot",
    "audit_authority_noise_snapshot",
    "detect_primary_rc",
    "cross_layer_consistency_row",
]


# Governed precedence (highest rank = wins). Verification taxonomy only.
PRECEDENCE_ORDER: Tuple[str, ...] = (
    "human_review",
    "external_verification",
    "governed_reconciliation",
    "extraction_assistance",
    "document_heuristic",
)


def _rank(source: str) -> int:
    try:
        return PRECEDENCE_ORDER.index(source)
    except ValueError:
        return len(PRECEDENCE_ORDER)


def authority_source_rank(doc: Dict[str, Any]) -> str:
    """Classify dominant authority source for a document snapshot."""
    review = effective_evidence_review_state(doc)
    tier = str(doc.get("assurance_tier") or doc.get("evidence_assurance_tier") or "").upper()
    if review in ("REJECTED", "EXPIRED", "SUPERSEDED"):
        return "human_review"
    if review in ("VERIFIED", "ACCEPTED_UNVERIFIED", "EXTERNALLY_VERIFIED"):
        if tier == "EXTERNALLY_VERIFIED" or review == "EXTERNALLY_VERIFIED":
            return "external_verification"
        return "human_review"
    if doc.get("extraction_reconciliation_at") or doc.get("extraction_reconciliation_reason"):
        return "governed_reconciliation"
    if doc.get("extraction_confirmation_superseded") or (
        isinstance(doc.get("ai_extraction"), dict) and doc["ai_extraction"].get("superseded_by_admin_decision")
    ):
        return "human_review"
    extraction_status = str(doc.get("extraction_status") or "").upper()
    if extraction_status in ("NEEDS_REVIEW", "EXTRACTED") or (
        isinstance(doc.get("ai_extraction"), dict) and doc["ai_extraction"].get("status") == "completed"
    ):
        return "extraction_assistance"
    return "document_heuristic"


def resolve_authority_precedence(
    doc: Dict[str, Any],
    *,
    entity_key: str,
) -> Dict[str, Any]:
    """Build one precedence resolution row from document fields."""
    sources: List[str] = []
    review = effective_evidence_review_state(doc)
    if review:
        sources.append("human_review")
    tier = str(doc.get("assurance_tier") or "").upper()
    if tier == "EXTERNALLY_VERIFIED":
        sources.append("external_verification")
    if doc.get("extraction_reconciliation_at"):
        sources.append("governed_reconciliation")
    if str(doc.get("extraction_status") or "").upper() in ("EXTRACTED", "NEEDS_REVIEW", "CONFIRMED", "REJECTED"):
        sources.append("extraction_assistance")
    sources.append("document_heuristic")
    unique = sorted(set(sources), key=_rank)
    winning = min(unique, key=_rank) if unique else "document_heuristic"
    overridden = [s for s in unique if s != winning]
    dominant = authority_source_rank(doc)
    precedence_pass = dominant == winning
    return {
        "entity_key": entity_key,
        "conflicting_sources": unique,
        "winning_authority_source": dominant,
        "overridden_authority_sources": overridden,
        "resolution_reason": f"effective_review={review}",
        "precedence_pass": precedence_pass,
    }


def authority_precedence_snapshot(
    doc: Optional[Dict[str, Any]],
    *,
    entity_key: str,
) -> Dict[str, Any]:
    if not doc:
        return {"authority_precedence_resolution": [], "precedence_pass": True}
    row = resolve_authority_precedence(doc, entity_key=entity_key)
    return {
        "authority_precedence_resolution": [row],
        "precedence_pass": bool(row.get("precedence_pass")),
    }


def authority_cardinality_snapshot(doc: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Single active winning authority source per document window (§3b)."""
    if not doc:
        return {
            "expected_active_authority_count": 1,
            "actual_active_authority_count": 0,
            "unexpected_parallel_authority_count": 0,
            "authority_cardinality_pass": True,
        }
    row = resolve_authority_precedence(doc, entity_key=str(doc.get("document_id") or ""))
    winning = str(row.get("winning_authority_source") or "document_heuristic")
    winner_rank = _rank(winning)
    overridden = list(row.get("overridden_authority_sources") or [])
    parallel_winners = [s for s in overridden if _rank(s) == winner_rank]
    unexpected = len(parallel_winners)
    if not row.get("precedence_pass"):
        unexpected = max(unexpected, 1)
    actual = 1 if unexpected == 0 else 1 + unexpected
    return {
        "expected_active_authority_count": 1,
        "actual_active_authority_count": actual,
        "unexpected_parallel_authority_count": unexpected,
        "winning_authority_source": winning,
        "parallel_authority_sources": parallel_winners,
        "authority_cardinality_pass": unexpected == 0 and bool(row.get("precedence_pass")),
    }


def authority_fingerprint(
    *,
    doc: Optional[Dict[str, Any]],
    requirement: Optional[Dict[str, Any]],
) -> str:
    ops = derive_document_operational_state(doc or {}) if doc else {}
    req_auth = (requirement or {}).get("evidence_authority")
    return fp32(
        {
            "operational_state": ops.get("document_operational_state"),
            "review": effective_evidence_review_state(doc or {}),
            "evidence_authority": req_auth,
            "superseded": (doc or {}).get("extraction_confirmation_superseded"),
        }
    )


def supersession_state_fingerprint(doc: Optional[Dict[str, Any]]) -> str:
    if not doc:
        return ""
    return fp32(
        {
            "superseded": doc.get("extraction_confirmation_superseded"),
            "review": effective_evidence_review_state(doc),
            "extraction_status": doc.get("extraction_status"),
            "ai_review": (doc.get("ai_extraction") or {}).get("review_status")
            if isinstance(doc.get("ai_extraction"), dict)
            else None,
        }
    )


def supersession_transition_matrix(
    runs: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    matrix: List[Dict[str, Any]] = []
    for r in runs:
        doc = r.get("document") or {}
        before = r.get("supersession_fingerprint_before") or ""
        after = r.get("supersession_fingerprint_after") or supersession_state_fingerprint(doc)
        matrix.append(
            {
                "run": r.get("run"),
                "from_state": before,
                "to_state": after,
                "trigger": r.get("mutation"),
                "governed": True,
            }
        )
    return matrix


def authority_collapse_snapshot(
    runs: List[Dict[str, Any]],
) -> Dict[str, Any]:
    collapsed: List[Dict[str, Any]] = []
    for r in runs:
        label = str(r.get("run") or "")
        if label not in ("R2", "R3"):
            continue
        if r.get("authority_write_suppressed"):
            collapsed.append(
                {
                    "run": label,
                    "collapse_reason": r.get("authority_write_suppress_reason") or "idempotent_replay",
                    "mutation": r.get("mutation"),
                }
            )
    states = [str(r.get("authority_collapse_state") or "expanded") for r in runs if r.get("run") in ("R2", "R3")]
    if len(states) >= 2 and states[0] == states[1]:
        collapse_state = states[0]
    elif not collapsed:
        collapse_state = "expanded"
    else:
        collapse_state = "collapsed_stable" if all(s == "collapsed_stable" for s in states) else "inconsistent"
    return {
        "authority_collapse_state": collapse_state,
        "collapsed_authority_mutations": collapsed,
        "retained_authority_visibility": True,
        "collapse_deterministic": len(set(states)) <= 1 if states else True,
    }


def collapse_boundedness_snapshot(
    runs: List[Dict[str, Any]],
) -> Dict[str, Any]:
    collapse_runs = [r for r in runs if str(r.get("run")) in ("R2", "R3")]
    counts = [len(r.get("collapsed_authority_mutations") or []) for r in collapse_runs]
    growth = (counts[-1] - counts[0]) if len(counts) >= 2 else 0
    depths = [int(r.get("collapsed_lineage_depth") or 0) for r in collapse_runs]
    depth_growth = (depths[-1] - depths[0]) if len(depths) >= 2 else 0
    return {
        "collapse_history_growth": growth,
        "collapse_growth_pass": growth == 0 and depth_growth == 0,
        "collapsed_lineage_depth": depths[-1] if depths else 0,
    }


def reconciliation_suppression_fingerprint(outcomes: List[Dict[str, Any]]) -> str:
    return fp32({"outcomes": outcomes})


def human_review_preservation_snapshot(
    before: Dict[str, Any],
    after: Dict[str, Any],
) -> Dict[str, Any]:
    """Compare human settlement markers across replay window."""
    attempts: List[Dict[str, Any]] = []

    def _human_settled(doc: Dict[str, Any]) -> bool:
        review = effective_evidence_review_state(doc)
        return review in ("VERIFIED", "ACCEPTED_UNVERIFIED", "REJECTED", "EXTERNALLY_VERIFIED", "SUPERSEDED")

    before_doc = before.get("document") or {}
    after_doc = after.get("document") or {}
    if _human_settled(before_doc) and not _human_settled(after_doc):
        attempts.append({"type": "human_review_erased", "detail": "review state degraded on replay"})
    before_review = effective_evidence_review_state(before_doc)
    after_review = effective_evidence_review_state(after_doc)
    if before_review in ("REJECTED", "VERIFIED") and after_review not in (before_review, "SUPERSEDED"):
        if _rank(authority_source_rank(after_doc)) < _rank("human_review"):
            attempts.append(
                {
                    "type": "human_review_downgraded",
                    "before": before_review,
                    "after": after_review,
                }
            )
    preserved = 1 if _human_settled(before_doc) and _human_settled(after_doc) else 0
    return {
        "human_review_preservation_pass": len(attempts) == 0,
        "review_override_attempts": attempts,
        "preserved_human_authority_count": preserved,
    }


def lineage_boundedness_snapshot(
    runs: List[Dict[str, Any]],
) -> Dict[str, Any]:
    def _depth(run: Dict[str, Any], key: str) -> int:
        return int(run.get(key) or 0)

    replay = [r for r in runs if str(r.get("run")) in ("R2", "R3")]
    if len(replay) < 2:
        return {
            "lineage_depth_growth": 0,
            "supersession_chain_growth": 0,
            "override_chain_growth": 0,
            "lineage_growth_pass": True,
        }
    r2, r3 = replay[0], replay[1]
    lineage_depth_growth = _depth(r3, "lineage_depth") - _depth(r2, "lineage_depth")
    supersession_chain_growth = _depth(r3, "supersession_chain_depth") - _depth(r2, "supersession_chain_depth")
    override_chain_growth = _depth(r3, "override_chain_depth") - _depth(r2, "override_chain_depth")
    return {
        "lineage_depth_growth": lineage_depth_growth,
        "supersession_chain_growth": supersession_chain_growth,
        "override_chain_growth": override_chain_growth,
        "lineage_growth_pass": (
            lineage_depth_growth == 0
            and supersession_chain_growth == 0
            and override_chain_growth == 0
        ),
    }


def authority_explainability_snapshot(
    *,
    requirement_id: str,
    document_id: Optional[str],
    doc: Optional[Dict[str, Any]],
    requirement: Optional[Dict[str, Any]],
    lineage: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    ops = derive_document_operational_state(doc or {}) if doc else {}
    state = str(ops.get("document_operational_state") or "unknown")
    sources_used: List[str] = []
    gaps: List[str] = []
    if doc:
        sources_used.append("document_operational_state")
        if effective_evidence_review_state(doc):
            sources_used.append("evidence_review_state")
    if requirement and requirement.get("evidence_authority"):
        sources_used.append("requirement_evidence_authority")
    if lineage and lineage.get("correlation_id"):
        sources_used.append("lineage_correlation")
    outcome_map = {
        "EVIDENCE_VERIFIED": "satisfied",
        "EVIDENCE_ACCEPTED_ON_FILE": "satisfied",
        "EXTERNALLY_VERIFIED": "externally_verified",
        "EVIDENCE_REJECTED": "rejected",
        "EVIDENCE_SUPERSEDED": "superseded",
        "ADMIN_REVIEW_PENDING": "pending_review",
    }
    operational_outcome = outcome_map.get(state, state)
    if operational_outcome == "unknown" or not sources_used:
        gaps.append("insufficient_governed_history")
    reconstructable = len(gaps) == 0 and bool(sources_used)
    return {
        "requirement_id": requirement_id,
        "document_id": document_id,
        "operational_outcome": operational_outcome,
        "reconstructable": reconstructable,
        "sources_used": sources_used,
        "gaps": gaps,
    }


def audit_authority_noise_snapshot(
    before: Dict[str, int],
    after: Dict[str, int],
) -> Dict[str, Any]:
    audit_delta = int(after.get("audit_authority_events", 0)) - int(before.get("audit_authority_events", 0))
    return {
        "audit_authority_event_delta": audit_delta,
        "noise_pass": audit_delta == 0,
        "before": before,
        "after": after,
    }


def cross_layer_consistency_row(
    *,
    layer: str,
    entity_key: str,
    fingerprint: str,
    consistent: bool,
    notes: str = "",
) -> Dict[str, Any]:
    return {
        "layer": layer,
        "entity_key": entity_key,
        "fingerprint": fingerprint,
        "consistent": consistent,
        "notes": notes,
    }


def detect_primary_rc(checks: Dict[str, bool]) -> Optional[str]:
    mapping = [
        ("precedence_pass", "E1-RC-16"),
        ("authority_cardinality_pass", "E1-RC-21"),
        ("human_review_preservation_pass", "E1-RC-23"),
        ("lineage_replay_stable", "E1-RC-2"),
        ("supersession_replay_equal", "E1-RC-17"),
        ("collapse_deterministic", "E1-RC-18"),
        ("collapse_growth_pass", "E1-RC-24"),
        ("reconciliation_replay_equal", "E1-RC-22"),
        ("cross_layer_pass", "E1-RC-12"),
        ("supersession_consistent", "E1-RC-3"),
        ("lineage_growth_pass", "E1-RC-19"),
        ("explainability_reconstruction_pass", "E1-RC-20"),
        ("lineage_attributable", "E1-RC-4"),
        ("reconciliation_convergent", "E1-RC-5"),
        ("suppression_explainable", "E1-RC-7"),
        ("temporal_sane", "E1-RC-8"),
        ("amplification_pass", "E1-RC-9"),
        ("audit_noise_pass", "E1-RC-10"),
        ("bounded_growth_pass", "E1-RC-11"),
        ("unrelated_delta_zero", "E1-RC-6"),
    ]
    for key, rc in mapping:
        if not checks.get(key, True):
            return rc
    return None


async def gather_document_requirement_context(
    db,
    *,
    cid: str,
    pid: str,
) -> Dict[str, Any]:
    """Resolve pilot requirement + primary linked document for verification."""
    req = await db.requirements.find_one(
        {"client_id": cid, "property_id": pid, "evidence_doc_id": {"$exists": True, "$ne": None}},
        {"_id": 0},
    )
    if not req:
        req = await db.requirements.find_one(
            {"client_id": cid, "property_id": pid},
            {"_id": 0},
        )
    rid = str((req or {}).get("requirement_id") or "")
    doc_id = str((req or {}).get("evidence_doc_id") or "")
    doc = None
    if doc_id:
        doc = await db.documents.find_one({"document_id": doc_id}, {"_id": 0})
    if not doc:
        async for d in db.documents.find(
            {"client_id": cid, "property_id": pid},
            {"_id": 0},
        ).sort("updated_at", -1).limit(1):
            doc = d
            doc_id = str(d.get("document_id") or "")
    return {
        "requirement": req,
        "requirement_id": rid,
        "document_id": doc_id,
        "document": doc,
    }


async def authority_snapshot_bundle(
    db,
    *,
    cid: str,
    pid: str,
    requirement_id: str,
    document_id: Optional[str],
) -> Dict[str, Any]:
    req = await db.requirements.find_one(
        {"requirement_id": requirement_id},
        {"_id": 0},
    )
    doc = None
    if document_id:
        doc = await db.documents.find_one({"document_id": document_id}, {"_id": 0})
    ops = derive_document_operational_state(doc or {}) if doc else {}
    prec = authority_precedence_snapshot(doc, entity_key=document_id or requirement_id)
    card = authority_cardinality_snapshot(doc)
    return {
        "client_id": cid,
        "property_id": pid,
        "requirement_id": requirement_id,
        "document_id": document_id,
        "document_operational": ops,
        "effective_evidence_review_state": effective_evidence_review_state(doc or {}),
        "evidence_authority": (req or {}).get("evidence_authority"),
        "authority_fingerprint": authority_fingerprint(doc=doc, requirement=req),
        "supersession_fingerprint": supersession_state_fingerprint(doc),
        **prec,
        **card,
    }
