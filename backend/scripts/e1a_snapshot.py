"""
E1a harness refinement: fixture gating, semantic replay fingerprints, vacuous-proof prevention.

Verification/governance only — no authority-writer changes.
"""
from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional, Tuple

from scripts.c2_snapshot import fp32
from scripts.e1_snapshot import (
    authority_cardinality_snapshot,
    authority_source_rank,
    supersession_state_fingerprint,
)
from services.document_operational_state import derive_document_operational_state
from services.evidence_review_migration import effective_evidence_review_state as _effective_review

# Re-export for e1a_staging
__all__ = [
    "FIXTURE_AUTHORITY_CAPABLE",
    "FIXTURE_PARTIALLY_CAPABLE",
    "FIXTURE_INCAPABLE",
    "normalize_evidence_authority_semantic",
    "semantic_authority_fingerprint",
    "supersession_replay_equal",
    "authority_explainability_snapshot_e1a",
    "authority_cardinality_snapshot_e1a",
    "classify_e1_fixture",
    "discover_staging_fixture_candidates",
    "detect_primary_rc_e1a",
    "replay_authority_comparison",
]

FIXTURE_AUTHORITY_CAPABLE = "authority-capable"
FIXTURE_PARTIALLY_CAPABLE = "partially-authority-capable"
FIXTURE_INCAPABLE = "authority-incapable"

# Verification-only: strip non-semantic churn from replay compare (D1b pattern).
SEMANTIC_EVIDENCE_AUTHORITY_OMIT_KEYS: Tuple[str, ...] = (
    "evidence_last_updated_at",
    "evidence_last_verified_at",
)


def reconciliation_suppression_fingerprint_semantic(outcomes: List[Dict[str, Any]]) -> str:
    """Replay fingerprint excluding per-run labels (verification normalization only)."""
    semantic = [
        {k: v for k, v in o.items() if k not in ("run", "dry_run")}
        for o in outcomes
    ]
    return fp32({"outcomes": semantic})


def normalize_evidence_authority_semantic(
    evidence_authority: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    if not evidence_authority or not isinstance(evidence_authority, dict):
        return {}
    out = copy.deepcopy(evidence_authority)
    for key in SEMANTIC_EVIDENCE_AUTHORITY_OMIT_KEYS:
        out.pop(key, None)
    return out


def semantic_authority_fingerprint(
    *,
    doc: Optional[Dict[str, Any]],
    requirement: Optional[Dict[str, Any]],
) -> str:
    """Replay fingerprint excluding timestamp/metadata churn only."""
    ops = derive_document_operational_state(doc or {}) if doc else {}
    req_auth = normalize_evidence_authority_semantic((requirement or {}).get("evidence_authority"))
    return fp32(
        {
            "operational_state": ops.get("document_operational_state"),
            "review": _effective_review(doc or {}),
            "evidence_authority": req_auth,
            "superseded": (doc or {}).get("extraction_confirmation_superseded"),
            "extraction_status": (doc or {}).get("extraction_status"),
            "winning_authority_source": authority_source_rank(doc) if doc else None,
        }
    )


def replay_authority_comparison(
    runs: List[Dict[str, Any]],
) -> Dict[str, Any]:
    raw_fps = {str(r["run"]): r.get("authority_fingerprint_after") for r in runs}
    sem_fps = {str(r["run"]): r.get("semantic_authority_fingerprint_after") for r in runs}
    raw_stable = raw_fps.get("R2") == raw_fps.get("R3") and bool(raw_fps.get("R2"))
    semantic_stable = sem_fps.get("R2") == sem_fps.get("R3")
    return {
        "raw_fingerprint": {"R2": raw_fps.get("R2"), "R3": raw_fps.get("R3"), "replay_stable": raw_stable},
        "semantic_fingerprint": {
            "R2": sem_fps.get("R2"),
            "R3": sem_fps.get("R3"),
            "replay_stable": semantic_stable,
        },
        "lineage_replay_stable_raw": raw_stable,
        "lineage_replay_stable_semantic": semantic_stable,
        "timestamp_only_drift": (not raw_stable) and semantic_stable,
    }


def supersession_replay_equal(sup_fps: Dict[str, Optional[str]]) -> bool:
    """Empty supersession state is a valid stable replay outcome."""
    return sup_fps.get("R2") == sup_fps.get("R3")


def _has_review_or_supersession_lineage(doc: Optional[Dict[str, Any]]) -> bool:
    if not doc:
        return False
    review = _effective_review(doc)
    if review in (
        "VERIFIED",
        "ACCEPTED_UNVERIFIED",
        "REJECTED",
        "EXTERNALLY_VERIFIED",
        "SUPERSEDED",
        "EXPIRED",
    ):
        return True
    if doc.get("extraction_confirmation_superseded"):
        return True
    if str(doc.get("extraction_status") or "").upper() in (
        "CONFIRMED",
        "REJECTED",
        "NEEDS_REVIEW",
        "EXTRACTED",
    ):
        return True
    ai = doc.get("ai_extraction")
    if isinstance(ai, dict) and ai.get("status") == "completed":
        return True
    return False


def _fixture_gate_flags(
    *,
    requirement: Optional[Dict[str, Any]],
    document: Optional[Dict[str, Any]],
    document_count: int,
    requirements_with_evidence_doc: int,
) -> Dict[str, Any]:
    req = requirement or {}
    doc_id = str(req.get("evidence_doc_id") or "").strip()
    return {
        "has_evidence_doc_id": bool(doc_id),
        "has_governed_document": bool(document and document.get("document_id")),
        "has_evidence_authority": bool(req.get("evidence_authority")),
        "has_review_or_supersession_lineage": _has_review_or_supersession_lineage(document),
        "property_document_count": document_count,
        "property_requirements_with_evidence_doc": requirements_with_evidence_doc,
    }


def classify_e1_fixture(
    *,
    requirement: Optional[Dict[str, Any]],
    document: Optional[Dict[str, Any]],
    document_count: int,
    requirements_with_evidence_doc: int,
    client_id: str,
    property_id: str,
    requirement_id: str,
    document_id: str,
) -> Dict[str, Any]:
    gates = _fixture_gate_flags(
        requirement=requirement,
        document=document,
        document_count=document_count,
        requirements_with_evidence_doc=requirements_with_evidence_doc,
    )
    fail_reasons: List[str] = []
    if not gates["has_evidence_doc_id"]:
        fail_reasons.append("missing_evidence_doc_id")
    if not gates["has_governed_document"]:
        fail_reasons.append("missing_governed_document")
    if not gates["has_evidence_authority"]:
        fail_reasons.append("missing_evidence_authority")

    if fail_reasons:
        klass = FIXTURE_INCAPABLE
        proof_eligible = False
    elif not gates["has_review_or_supersession_lineage"]:
        klass = FIXTURE_PARTIALLY_CAPABLE
        proof_eligible = True
    else:
        klass = FIXTURE_AUTHORITY_CAPABLE
        proof_eligible = True

    return {
        "client_id": client_id,
        "property_id": property_id,
        "requirement_id": requirement_id,
        "document_id": document_id,
        "fixture_classification": klass,
        "proof_eligible": proof_eligible,
        "fail_fast_reasons": fail_reasons,
        "gates": gates,
        "vacuous_proof_prevented": klass == FIXTURE_INCAPABLE,
    }


async def discover_staging_fixture_candidates(
    db,
    *,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """Read-only scan for properties with evidence-linked requirements."""
    pipeline = [
        {
            "$match": {
                "evidence_doc_id": {"$exists": True, "$nin": [None, ""]},
            }
        },
        {
            "$group": {
                "_id": {"client_id": "$client_id", "property_id": "$property_id"},
                "requirement_id": {"$first": "$requirement_id"},
                "evidence_doc_id": {"$first": "$evidence_doc_id"},
                "count": {"$sum": 1},
            }
        },
        {"$limit": limit},
    ]
    out: List[Dict[str, Any]] = []
    async for row in db.requirements.aggregate(pipeline):
        ident = row.get("_id") or {}
        out.append(
            {
                "client_id": ident.get("client_id"),
                "property_id": ident.get("property_id"),
                "requirement_id": row.get("requirement_id"),
                "evidence_doc_id": row.get("evidence_doc_id"),
                "linked_requirement_count": row.get("count"),
            }
        )
    return out


async def resolve_e1a_fixture(
    db,
    *,
    cid: str,
    pid: str,
    requirement_id: Optional[str] = None,
    document_id: Optional[str] = None,
) -> Dict[str, Any]:
    document_count = await db.documents.count_documents({"client_id": cid, "property_id": pid})
    req_with_doc = await db.requirements.count_documents(
        {
            "client_id": cid,
            "property_id": pid,
            "evidence_doc_id": {"$exists": True, "$nin": [None, ""]},
        }
    )

    req = None
    doc = None
    rid = ""
    did = ""

    if requirement_id:
        req = await db.requirements.find_one({"requirement_id": requirement_id}, {"_id": 0})
        if req:
            rid = str(req.get("requirement_id") or "")
            did = str(document_id or req.get("evidence_doc_id") or "").strip()
    else:
        req = await db.requirements.find_one(
            {
                "client_id": cid,
                "property_id": pid,
                "evidence_doc_id": {"$exists": True, "$nin": [None, ""]},
            },
            {"_id": 0},
        )
        if req:
            rid = str(req.get("requirement_id") or "")
            did = str(req.get("evidence_doc_id") or "").strip()

    if not req:
        req = await db.requirements.find_one(
            {"client_id": cid, "property_id": pid},
            {"_id": 0},
        )
        if req:
            rid = str(req.get("requirement_id") or "")

    if did:
        doc = await db.documents.find_one({"document_id": did}, {"_id": 0})
    elif document_count:
        async for d in db.documents.find(
            {"client_id": cid, "property_id": pid},
            {"_id": 0},
        ).sort("updated_at", -1).limit(1):
            doc = d
            did = str(d.get("document_id") or "")

    classification = classify_e1_fixture(
        requirement=req,
        document=doc,
        document_count=document_count,
        requirements_with_evidence_doc=req_with_doc,
        client_id=cid,
        property_id=pid,
        requirement_id=rid,
        document_id=did,
    )
    candidates = await discover_staging_fixture_candidates(db, limit=5)
    return {
        "requirement": req,
        "document": doc,
        "requirement_id": rid,
        "document_id": did,
        "classification": classification,
        "staging_fixture_candidates": candidates,
    }


def authority_cardinality_snapshot_e1a(
    doc: Optional[Dict[str, Any]],
    *,
    fixture_classification: str,
) -> Dict[str, Any]:
    if fixture_classification == FIXTURE_INCAPABLE:
        return {
            "expected_active_authority_count": 1,
            "actual_active_authority_count": 0,
            "unexpected_parallel_authority_count": 0,
            "authority_cardinality_pass": None,
            "vacuous": True,
            "skipped_reason": "authority-incapable_fixture",
        }
    snap = authority_cardinality_snapshot(doc)
    snap["vacuous"] = False
    return snap


def authority_explainability_snapshot_e1a(
    *,
    requirement_id: str,
    document_id: Optional[str],
    doc: Optional[Dict[str, Any]],
    requirement: Optional[Dict[str, Any]],
    lineage: Optional[Dict[str, Any]],
    fixture_classification: str,
) -> Dict[str, Any]:
    from scripts.e1_snapshot import authority_explainability_snapshot

    base = authority_explainability_snapshot(
        requirement_id=requirement_id,
        document_id=document_id,
        doc=doc,
        requirement=requirement,
        lineage=lineage,
    )
    if fixture_classification in (FIXTURE_INCAPABLE, FIXTURE_PARTIALLY_CAPABLE):
        gaps = list(base.get("gaps") or [])
        if "insufficient_governed_history" in gaps:
            gaps = [g for g in gaps if g != "insufficient_governed_history"]
        gaps.append("insufficient_governed_fixture")
        return {
            **base,
            "gaps": gaps,
            "reconstructable": None,
            "explainability_qualified": False,
            "explainability_classification": "insufficient_governed_fixture",
        }
    qualified = bool(base.get("reconstructable"))
    return {
        **base,
        "explainability_qualified": qualified,
        "explainability_classification": "operational_reconstructable" if qualified else "operational_opacity",
    }


def detect_primary_rc_e1a(checks: Dict[str, Any]) -> Optional[str]:
    if not checks.get("fixture_gate_pass"):
        return "E1a-RC-FIXTURE"
    mapping = [
        ("precedence_pass", "E1-RC-16"),
        ("authority_cardinality_pass", "E1-RC-21"),
        ("human_review_preservation_pass", "E1-RC-23"),
        ("lineage_replay_stable_semantic", "E1-RC-2"),
        ("supersession_replay_equal", "E1-RC-17"),
        ("collapse_deterministic", "E1-RC-18"),
        ("collapse_growth_pass", "E1-RC-24"),
        ("reconciliation_replay_equal", "E1-RC-22"),
        ("cross_layer_pass", "E1-RC-12"),
        ("lineage_growth_pass", "E1-RC-19"),
        ("explainability_reconstruction_pass", "E1-RC-20"),
        ("unrelated_delta_zero", "E1-RC-6"),
        ("audit_noise_pass", "E1-RC-10"),
    ]
    for key, rc in mapping:
        val = checks.get(key)
        if val is False:
            return rc
    return None
