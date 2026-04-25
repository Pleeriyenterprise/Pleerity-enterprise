"""
Idempotent backfill: explicit document evidence scope + requirement evidence_authority projection.

Run from backend directory:
  python -m scripts.backfill_evidence_authority
  python -m scripts.backfill_evidence_authority --dry-run

Uses the same rules as runtime (see services.requirement_evidence_authority):
- PROPERTY when property_id is set (legacy rows).
- INTAKE_STAGING for pre-provision intake uploads still on a session.
- PROPERTY from linked requirement when requirement_id is set and property_id was null (safe inference).
- PORTFOLIO when client_id is known, no property_id, no requirement_id (explicit client-level vault row).
- UNRESOLVED + manual_review_flag when ownership cannot be determined (never invent a property_id).

Phase 2 recomputes evidence_authority for every requirement (safe to re-run).

Requires: MONGO_URL, DB_NAME (same as main app).
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


async def _scope_patch_for_document(db, doc: Dict[str, Any]) -> Tuple[Dict[str, Any], str]:
    from services.requirement_evidence_authority import (
        SCOPE_UNRESOLVED,
        normalize_document_evidence_scope,
    )

    pid = (doc.get("property_id") or "").strip()
    cid = (doc.get("client_id") or "").strip()
    rid = (doc.get("requirement_id") or "").strip()
    source = (doc.get("source") or "").strip().upper()
    sess = (doc.get("intake_session_id") or "").strip()

    if source == "INTAKE_UPLOAD" and sess and not pid:
        p = normalize_document_evidence_scope(
            property_id=None,
            client_id=cid or "",
            evidence_scope_type="INTAKE_STAGING",
            intake_session_id=sess,
        )
        return p, "INTAKE_STAGING"
    if pid and cid:
        p = normalize_document_evidence_scope(property_id=pid, client_id=cid, evidence_scope_type="PROPERTY")
        return p, "PROPERTY"
    if rid and cid:
        req = await db.requirements.find_one({"requirement_id": rid, "client_id": cid}, {"_id": 0, "property_id": 1})
        rpid = ((req or {}).get("property_id") or "").strip()
        if rpid:
            p = normalize_document_evidence_scope(property_id=rpid, client_id=cid, evidence_scope_type="PROPERTY")
            return p, "PROPERTY_FROM_REQUIREMENT"
    if cid and not rid and not pid:
        p = normalize_document_evidence_scope(property_id=None, client_id=cid, evidence_scope_type="PORTFOLIO")
        return p, "PORTFOLIO"
    return (
        {
            "evidence_scope_type": SCOPE_UNRESOLVED,
            "evidence_scope_id": None,
            "authoritative_property_id": None,
            "manual_review_flag": True,
        },
        "UNRESOLVED",
    )


DOC_FILTER: Dict[str, Any] = {
    "$or": [
        {"evidence_scope_type": {"$exists": False}},
        {"evidence_scope_type": None},
        {"evidence_scope_type": ""},
    ]
}


async def gather_backfill_plan(db: Any, *, apply_writes: bool = False) -> Dict[str, Any]:
    """
    Classify unscoped documents and optionally apply patches + sync all requirements.
    When apply_writes is False (dry-run), returns counts only; DB unchanged.
    """
    from services.requirement_evidence_authority import sync_requirement_evidence_authority

    doc_stats: Dict[str, int] = {}
    touched = 0
    async for doc in db.documents.find(DOC_FILTER, {"_id": 0}):
        patch, reason = await _scope_patch_for_document(db, doc)
        doc_stats[reason] = doc_stats.get(reason, 0) + 1
        touched += 1
        if apply_writes:
            await db.documents.update_one({"document_id": doc["document_id"]}, {"$set": patch})

    req_ids: List[str] = []
    async for r in db.requirements.find({}, {"_id": 0, "requirement_id": 1}):
        rid = r.get("requirement_id")
        if rid:
            req_ids.append(str(rid))

    if apply_writes:
        for rid in req_ids:
            await sync_requirement_evidence_authority(db, rid)

    return {
        "documents_matched_unscoped": touched,
        "document_scope_plan": dict(doc_stats),
        "document_unresolved_planned": doc_stats.get("UNRESOLVED", 0),
        "requirements_synced": len(req_ids),
    }


async def run(*, dry_run: bool) -> None:
    from database import database

    await database.connect()
    db = database.get_db()

    result = await gather_backfill_plan(db, apply_writes=not dry_run)

    print("--- backfill_evidence_authority ---")
    print(f"dry_run={dry_run}")
    print(f"documents_matched_unscoped={result['documents_matched_unscoped']}")
    for k, v in sorted((result.get("document_scope_plan") or {}).items(), key=lambda x: -x[1]):
        print(f"  document_scope_plan[{k}]={v}")
    print(f"requirements_synced={result['requirements_synced']}")
    await database.close()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="Report counts only; do not write")
    args = ap.parse_args()
    asyncio.run(run(dry_run=bool(args.dry_run)))


if __name__ == "__main__":
    main()
