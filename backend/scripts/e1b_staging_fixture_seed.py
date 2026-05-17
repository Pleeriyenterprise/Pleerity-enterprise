"""
E1b governed staging fixture seed — authority-capable evidence proof window.

  python -m scripts.e1b_staging_fixture_seed --client-id CID --property-id PID

Verification/governance only. Does not modify authority-writer code paths.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from models.core import DocumentStatus  # noqa: E402
from scripts.e1a_snapshot import (  # noqa: E402
    FIXTURE_AUTHORITY_CAPABLE,
    classify_e1_fixture,
    resolve_e1a_fixture,
)

CID_DEFAULT = "6fd5ac4c-3fd4-4112-ade7-156977deb49f"
PID_DEFAULT = "d35a58ae-3c81-491c-9694-1d021dd3b8ad"
FIXTURE_MARKER = "E1b_authority_capable_v1"
PREFERRED_REQUIREMENT_TYPES = ("gas_safety", "eicr", "epc", "fire_alarm", "portable_appliance_test")


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="E1b governed staging fixture seed")
    p.add_argument("--client-id", default=CID_DEFAULT)
    p.add_argument("--property-id", default=PID_DEFAULT)
    p.add_argument("--requirement-id", default=None, help="Override requirement selection")
    p.add_argument("--out-dir", default="docs/audit")
    p.add_argument("--slug-suffix", default="6fd5ac4c_d35a58ae")
    p.add_argument("--dry-run", action="store_true")
    return p.parse_args()


async def _select_requirement(db, *, cid: str, pid: str, requirement_id: Optional[str]) -> Dict[str, Any]:
    if requirement_id:
        req = await db.requirements.find_one({"requirement_id": requirement_id}, {"_id": 0})
        if not req:
            raise RuntimeError(f"requirement not found: {requirement_id}")
        return req
    for rtype in PREFERRED_REQUIREMENT_TYPES:
        req = await db.requirements.find_one(
            {
                "client_id": cid,
                "property_id": pid,
                "requirement_type": rtype,
                "status": {"$nin": ["NOT_REQUIRED"]},
            },
            {"_id": 0},
        )
        if req:
            return req
    req = await db.requirements.find_one(
        {
            "client_id": cid,
            "property_id": pid,
            "status": {"$nin": ["NOT_REQUIRED"]},
            "evidence_authority.state": {"$nin": ["NOT_REQUIRED", None]},
        },
        {"_id": 0},
    )
    if not req:
        raise RuntimeError("no suitable requirement for E1b fixture on property")
    return req


def _build_fixture_document(
    *,
    document_id: str,
    cid: str,
    pid: str,
    requirement_id: str,
    requirement_type: str,
    now: datetime,
) -> Dict[str, Any]:
    expiry = (now + timedelta(days=365)).date().isoformat()
    issue = (now - timedelta(days=30)).date().isoformat()
    now_iso = now.isoformat()
    return {
        "document_id": document_id,
        "client_id": cid,
        "property_id": pid,
        "evidence_scope_type": "PROPERTY",
        "evidence_scope_id": pid,
        "authoritative_property_id": pid,
        "requirement_id": requirement_id,
        "file_name": f"e1b_staging_{requirement_type}_fixture.pdf",
        "file_path": f"{cid}/e1b_staging_fixture/{document_id}.pdf",
        "file_size": 1024,
        "mime_type": "application/pdf",
        "status": DocumentStatus.VERIFIED.value,
        "uploaded_by": "E1b_STAGING_FIXTURE_SEED",
        "uploaded_at": now_iso,
        "document_type": requirement_type,
        "source": "e1b_staging_fixture_seed",
        "staging_verification_fixture": FIXTURE_MARKER,
        "evidence_review_state": "ACCEPTED_UNVERIFIED",
        "assurance_tier": "HUMAN_ACCEPTED",
        "review_decision_at": now_iso,
        "review_decision_by": "e1b_staging_fixture_seed",
        "extraction_status": "CONFIRMED",
        "extraction_confirmation_superseded": True,
        "extraction_confirmation_superseded_at": now_iso,
        "extraction_confirmation_superseded_by": "e1b_staging_fixture_seed",
        "ai_extraction": {
            "status": "completed",
            "review_status": "approved",
            "superseded_by_admin_decision": "accepted",
            "data": {"fixture": FIXTURE_MARKER, "requirement_type": requirement_type},
        },
        "evidence_satisfies_requirement": True,
        "match_outcome": "MATCH_CONFIRMED",
        "match_confidence": 0.99,
        "matched_requirement_family": requirement_type,
        "expiry_date": expiry,
        "issue_date": issue,
        "verified_at": now_iso,
        "updated_at": now_iso,
    }


async def main() -> None:
    from database import database
    from services.requirement_evidence_authority import sync_requirement_evidence_authority

    await database.connect()
    args = _parse_args()
    cid = args.client_id.strip()
    pid = args.property_id.strip()
    slug = args.slug_suffix
    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    db = database.get_db()
    run_at = datetime.now(timezone.utc)
    seed_path = out_dir / f"e1b_fixture_seed_{slug}.json"

    existing_seed: Optional[Dict[str, Any]] = None
    if seed_path.exists():
        existing_seed = json.loads(seed_path.read_text(encoding="utf-8"))

    document_id = str((existing_seed or {}).get("document_id") or uuid.uuid4())
    req = await _select_requirement(db, cid=cid, pid=pid, requirement_id=args.requirement_id)
    rid = str(req["requirement_id"])
    rtype = str(req.get("requirement_type") or "evidence")

    existing_doc = await db.documents.find_one(
        {"staging_verification_fixture": FIXTURE_MARKER, "client_id": cid, "property_id": pid},
        {"_id": 0},
    )
    if existing_doc:
        document_id = str(existing_doc["document_id"])

    doc_payload = _build_fixture_document(
        document_id=document_id,
        cid=cid,
        pid=pid,
        requirement_id=rid,
        requirement_type=rtype,
        now=run_at,
    )

    seed_report: Dict[str, Any] = {
        "captured_at_utc": run_at.isoformat(),
        "micro_unit": "E1b",
        "fixture_marker": FIXTURE_MARKER,
        "client_id": cid,
        "property_id": pid,
        "requirement_id": rid,
        "requirement_type": rtype,
        "document_id": document_id,
        "dry_run": args.dry_run,
        "idempotent_reuse": bool(existing_doc),
    }

    if not args.dry_run:
        if existing_doc:
            await db.documents.update_one(
                {"document_id": document_id},
                {"$set": doc_payload},
            )
            seed_report["document_action"] = "updated"
        else:
            await db.documents.insert_one(doc_payload)
            seed_report["document_action"] = "inserted"

        await db.requirements.update_one(
            {"requirement_id": rid},
            {
                "$set": {
                    "evidence_doc_id": document_id,
                    "document_id": document_id,
                    "updated_at": run_at.isoformat(),
                }
            },
        )
        seed_report["requirement_action"] = "linked_evidence_doc_id"

        await sync_requirement_evidence_authority(db, rid, property_id_hint=pid)
        seed_report["authority_sync"] = "sync_requirement_evidence_authority"

        await db.audit_logs.insert_one(
            {
                "audit_id": str(uuid.uuid4()),
                "action": "UPDATE",
                "actor_id": "e1b_staging_fixture_seed",
                "client_id": cid,
                "property_id": pid,
                "resource_type": "document",
                "resource_id": document_id,
                "event_type": "EVIDENCE_REVIEW",
                "metadata": {
                    "fixture": FIXTURE_MARKER,
                    "requirement_id": rid,
                    "review_outcome": "ACCEPTED_UNVERIFIED",
                    "governed_seed": True,
                },
                "timestamp": run_at,
            }
        )
        seed_report["audit_lineage"] = "EVIDENCE_REVIEW_seeded"

    resolved = await resolve_e1a_fixture(db, cid=cid, pid=pid, requirement_id=rid, document_id=document_id)
    classification = resolved["classification"]
    seed_report["fixture_classification"] = classification
    seed_report["authority_capable"] = classification["fixture_classification"] == FIXTURE_AUTHORITY_CAPABLE

    if classification["fixture_classification"] != FIXTURE_AUTHORITY_CAPABLE:
        seed_report["seed_failed"] = True
        seed_report["fail_fast_reasons"] = classification.get("fail_fast_reasons") or []

    _write(seed_path, seed_report)
    print(json.dumps(seed_report, indent=2, default=str))

    if not seed_report.get("authority_capable"):
        raise SystemExit(3)


def _write(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(main())
