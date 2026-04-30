"""
Idempotent applicability provenance backfill (operational command only).

Initializes pipeline/effective/source from legacy applicability fields with
no active operator override. Does not run on deploy — invoke via script.

Skips documents where operator_override_active is True (governance).
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from services.applicability_provenance_selector import build_provenance_mongo_set
from services.applicability_state_parse import normalize_applicability_state


def pipeline_from_legacy_requirement(doc: Dict[str, Any]) -> str:
    """Derive pipeline applicability from existing requirement row (legacy)."""
    return normalize_applicability_state(doc if isinstance(doc, dict) else {})


def operator_override_from_doc(doc: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """Read operator override intent from nested or flat hints (PR1 shape)."""
    nested = doc.get("applicability_provenance")
    if isinstance(nested, dict):
        ov = nested.get("operator_override")
        if isinstance(ov, dict) and ov.get("active"):
            st = ov.get("applicability_state")
            return True, str(st).strip().upper() if st else None
    if doc.get("operator_override_active"):
        return True, None
    return False, None


def _nested_operator_matches(patch_ov: Any, doc_ov: Any) -> bool:
    if not isinstance(patch_ov, dict):
        return False
    if not isinstance(doc_ov, dict):
        return False
    return bool(patch_ov.get("active")) == bool(doc_ov.get("active")) and patch_ov.get(
        "applicability_state"
    ) == doc_ov.get("applicability_state")


def logical_provenance_matches_document(doc: Dict[str, Any], patch: Dict[str, Any]) -> bool:
    """True if doc already reflects the same logical provenance as patch (ignores timestamps)."""
    if not isinstance(doc, dict) or not isinstance(patch, dict):
        return False
    if doc.get("pipeline_applicability_state") != patch.get("pipeline_applicability_state"):
        return False
    if doc.get("effective_applicability_state") != patch.get("effective_applicability_state"):
        return False
    if str(doc.get("applicability_resolution_source") or "").upper() != str(
        patch.get("applicability_resolution_source") or ""
    ).upper():
        return False
    if bool(doc.get("operator_override_active")) != bool(patch.get("operator_override_active")):
        return False
    dn = doc.get("applicability_provenance")
    pn = patch.get("applicability_provenance")
    if not isinstance(dn, dict) or not isinstance(pn, dict):
        return False
    if dn.get("pipeline_applicability_state") != pn.get("pipeline_applicability_state"):
        return False
    if dn.get("effective_applicability_state") != pn.get("effective_applicability_state"):
        return False
    if str(dn.get("applicability_resolution_source") or "").upper() != str(
        pn.get("applicability_resolution_source") or ""
    ).upper():
        return False
    return _nested_operator_matches(
        pn.get("operator_override"), dn.get("operator_override")
    )


def build_backfill_set_for_document(doc: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Return $set dict for PR1 provenance from legacy fields, or None if skip
    (active operator override).
    """
    if not isinstance(doc, dict):
        return None
    active, _ = operator_override_from_doc(doc)
    if active:
        return None
    pipeline = pipeline_from_legacy_requirement(doc)
    return build_provenance_mongo_set(
        pipeline_applicability_state=pipeline,
        operator_override_active=False,
        operator_override_applicability_state=None,
    )


def summarize_backfill_eligibility(
    doc: Dict[str, Any], *, force_refresh_from_legacy: bool
) -> str:
    """For dry-run / logging: skip reason or update."""
    if not isinstance(doc, dict):
        return "invalid"
    active, _ = operator_override_from_doc(doc)
    if active:
        return "skip_operator_override_active"
    patch = build_backfill_set_for_document(doc)
    if not patch:
        return "skip_no_patch"
    nested = doc.get("applicability_provenance")
    flat_p = doc.get("pipeline_applicability_state")
    if not force_refresh_from_legacy:
        if isinstance(nested, dict) and flat_p is not None and logical_provenance_matches_document(doc, patch):
            return "skip_already_aligned"
    else:
        desired_pipeline = pipeline_from_legacy_requirement(doc)
        if isinstance(nested, dict) and nested.get("pipeline_applicability_state") != desired_pipeline:
            return "update"
        if isinstance(nested, dict) and flat_p is not None and logical_provenance_matches_document(doc, patch):
            return "skip_already_aligned"
    return "update"


async def run_applicability_provenance_backfill(
    db: Any,
    *,
    client_id: Optional[str] = None,
    limit: Optional[int] = None,
    dry_run: bool = False,
    force_refresh_from_legacy: bool = False,
) -> Dict[str, int]:
    """
    Scan requirements and apply provenance $set where eligible.

    Returns counts: examined, updated, skipped_operator, skipped_aligned, skipped_no_patch.
    """
    examined = 0
    updated = 0
    skipped_operator = 0
    skipped_aligned = 0
    skipped_no_patch = 0
    flt: Dict[str, Any] = {}
    if client_id:
        flt["client_id"] = client_id
    # Stable iteration order for repeatable --limit batches (wider operational runs).
    cursor = db.requirements.find(flt).sort("_id", 1)
    async for doc in cursor:
        if limit is not None and examined >= limit:
            break
        examined += 1
        st = summarize_backfill_eligibility(doc, force_refresh_from_legacy=force_refresh_from_legacy)
        if st == "skip_operator_override_active":
            skipped_operator += 1
            continue
        if st == "skip_already_aligned":
            skipped_aligned += 1
            continue
        if st in ("invalid", "skip_no_patch"):
            skipped_no_patch += 1
            continue
        patch = build_backfill_set_for_document(doc)
        if not patch:
            skipped_no_patch += 1
            continue
        if dry_run:
            updated += 1
            continue
        rid = doc.get("requirement_id")
        cid = doc.get("client_id")
        if rid is None:
            skipped_no_patch += 1
            continue
        q: Dict[str, Any] = {"requirement_id": rid}
        if cid is not None:
            q["client_id"] = cid
        await db.requirements.update_one(q, {"$set": patch})
        updated += 1
    return {
        "examined": examined,
        "updated": updated,
        "skipped_operator_override_active": skipped_operator,
        "skipped_already_aligned": skipped_aligned,
        "skipped_no_patch": skipped_no_patch,
    }
