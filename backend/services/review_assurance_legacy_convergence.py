"""
REVIEW-ASSURANCE-POST-DEPLOY-CLEANUP-01 — classify and converge legacy org-review artifacts.

Read-time convergence only; does not delete audit history or mutate verified certificates.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from services.cer_governance_presentation import (
    ASSURANCE_PLATFORM_REVIEWED,
    ASSURANCE_SELF_RECORDED,
    ASSURANCE_VERIFIED_DOCUMENT,
    GF_PLATFORM_VER,
    attach_cer_governance_presentation,
    derive_assurance_tier,
    resolve_governance_meta,
    derive_truth_presentation,
)

LEGACY_ORG_OWNER = "org_admin"
LEGACY_ORG_STAGE = "org_verification_pending"
LEGACY_ORG_FAMILY = "ORG_ADMIN_REVIEWED"

CLASS_HARMLESS = "harmless_historical"
CLASS_MIGRATABLE = "migratable"
CLASS_DANGEROUS = "operationally_dangerous"
CLASS_ORPHANED = "orphaned"


def normalize_legacy_truth_stage(stage: str) -> str:
    """Map deprecated org-review stage to post-simplification presentation stage."""
    s = str(stage or "").strip().lower()
    if s == LEGACY_ORG_STAGE:
        return "declaration_recorded"
    return s


def classify_legacy_org_review_artifact(row: Dict[str, Any]) -> str:
    """
    Classify a requirement row (raw or enriched) for legacy org-review cleanup.

    Returns: harmless_historical | migratable | operationally_dangerous | orphaned
    """
    if not row or not isinstance(row, dict):
        return CLASS_HARMLESS

    raw_owner = str(row.get("review_owner") or "").strip()
    raw_family = str(row.get("governance_family") or "").strip().upper()
    raw_stage = str(row.get("truth_presentation_stage") or "").strip().lower()
    qbr = row.get("queue_backed_review") is True

    enriched = attach_cer_governance_presentation(row)
    tier = str(enriched.get("assurance_tier") or "")
    en_owner = str(enriched.get("review_owner") or "").strip()
    en_stage = str(enriched.get("truth_presentation_stage") or "").strip().lower()
    en_family = str(enriched.get("governance_family") or "").strip().upper()

    has_legacy_marker = (
        raw_owner == LEGACY_ORG_OWNER
        or raw_family == LEGACY_ORG_FAMILY
        or raw_stage == LEGACY_ORG_STAGE
        or (qbr and raw_owner == LEGACY_ORG_OWNER)
    )
    if not has_legacy_marker:
        return CLASS_HARMLESS

    if tier == ASSURANCE_VERIFIED_DOCUMENT:
        return CLASS_HARMLESS

    if en_owner == LEGACY_ORG_OWNER and enriched.get("queue_backed_review") is True:
        return CLASS_DANGEROUS

    if raw_owner == LEGACY_ORG_OWNER and en_owner != LEGACY_ORG_OWNER and tier in (
        ASSURANCE_SELF_RECORDED,
        ASSURANCE_PLATFORM_REVIEWED,
    ):
        return CLASS_MIGRATABLE

    if raw_family == LEGACY_ORG_FAMILY and en_family != LEGACY_ORG_FAMILY:
        return CLASS_MIGRATABLE

    if raw_stage == LEGACY_ORG_STAGE and en_stage != LEGACY_ORG_STAGE:
        return CLASS_MIGRATABLE

    if en_owner == LEGACY_ORG_OWNER or en_stage == LEGACY_ORG_STAGE:
        return CLASS_ORPHANED

    return CLASS_HARMLESS


def converge_legacy_row_presentation(row: Dict[str, Any]) -> Dict[str, Any]:
    """
    Return enriched presentation fields with legacy org-review semantics removed.
    Safe for API responses — does not persist to database.
    """
    base = dict(row or {})
    classification = classify_legacy_org_review_artifact(base)
    enriched = attach_cer_governance_presentation(base)
    out = {**base, **enriched, "legacy_org_review_classification": classification}
    if classification in (CLASS_MIGRATABLE, CLASS_ORPHANED, CLASS_DANGEROUS):
        out["legacy_org_review_converged"] = True
        out["legacy_org_review_compat"] = "SELF_RECORDED_OR_PLATFORM_REVIEWED"
    return out


def audit_legacy_org_review_batch(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Summarise legacy org-review markers across a requirement batch."""
    counts = {CLASS_HARMLESS: 0, CLASS_MIGRATABLE: 0, CLASS_DANGEROUS: 0, CLASS_ORPHANED: 0}
    samples: Dict[str, List[Dict[str, Any]]] = {k: [] for k in counts}
    forbidden_phrases = (
        "organisation review",
        "organization review",
        "org admin",
        "pending org review",
        "queue-backed org",
    )
    phrase_hits: List[Dict[str, Any]] = []

    for row in rows or []:
        cls = classify_legacy_org_review_artifact(row)
        counts[cls] = counts.get(cls, 0) + 1
        if len(samples[cls]) < 5:
            rid = str(row.get("requirement_id") or "")
            samples[cls].append(
                {
                    "requirement_id": rid,
                    "requirement_type": row.get("requirement_type"),
                    "raw_review_owner": row.get("review_owner"),
                    "raw_governance_family": row.get("governance_family"),
                    "raw_truth_stage": row.get("truth_presentation_stage"),
                }
            )
        enriched = attach_cer_governance_presentation(row)
        blob = " ".join(
            str(enriched.get(k) or "")
            for k in (
                "truth_presentation_label",
                "truth_presentation_subline",
                "truth_presentation_stage",
            )
        ).lower()
        for phrase in forbidden_phrases:
            if phrase in blob:
                phrase_hits.append({"requirement_id": row.get("requirement_id"), "phrase": phrase})

    return {
        "counts": counts,
        "samples": samples,
        "forbidden_phrase_hits_in_enriched_copy": phrase_hits,
        "pass": counts[CLASS_DANGEROUS] == 0 and counts[CLASS_ORPHANED] == 0 and not phrase_hits,
    }


def propose_stored_field_convergence(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Optional DB patch proposal for persisted legacy markers (never applied automatically).

    Returns None when no stored mutation is recommended.
    """
    cls = classify_legacy_org_review_artifact(row)
    if cls not in (CLASS_MIGRATABLE, CLASS_ORPHANED, CLASS_DANGEROUS):
        return None

    meta = resolve_governance_meta(row)
    truth = derive_truth_presentation(row, meta)
    tier = derive_assurance_tier(row, meta, truth)
    patch: Dict[str, Any] = {
        "requirement_id": row.get("requirement_id"),
        "property_id": row.get("property_id"),
        "classification": cls,
        "read_only_compat_marker": "legacy_org_review_removed",
    }
    if tier == ASSURANCE_PLATFORM_REVIEWED:
        patch["note"] = "Preserve escalation — do not downgrade to self-recorded"
        return patch
    if str(meta.get("governance_family") or "") == GF_PLATFORM_VER:
        patch["note"] = "Document verification unchanged"
        return patch
    patch["recommended_assurance_tier"] = ASSURANCE_SELF_RECORDED
    patch["clear_stored_review_owner"] = True
    patch["clear_stored_queue_backed_review"] = True
    return patch
