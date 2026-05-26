"""
Bounded OPS fixtures for PRELAUNCH-ADMIN-CONTROL-REMEDIATION-01 closeout.

  python -m scripts.admin_remediation_probe_seed --client-id CID --property-id PID

Seeds:
- UNRESOLVED evidence document (OPS_ADMIN_REMEDIATION_PROBE)
- FAILED extraction pair (document + extracted_documents) for retry proof

Verification mutations must use admin API/browser — not this script.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PROBE_MARKER = "OPS_ADMIN_REMEDIATION_PROBE"
CID_DEFAULT = "6fd5ac4c-3fd4-4112-ade7-156977deb49f"
PID_DEFAULT = "d35a58ae-3c81-491c-9694-1d021dd3b8ad"


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Admin remediation probe seed")
    p.add_argument("--client-id", default=CID_DEFAULT)
    p.add_argument("--property-id", default=PID_DEFAULT)
    p.add_argument("--out", default="docs/audit/admin_control_remediation_01/probe_seed.json")
    return p.parse_args()


async def seed_admin_remediation_probe(client_id: str, property_id: str) -> Dict[str, Any]:
    """Seed bounded OPS probe fixtures; returns report dict (no HTTP mutations)."""
    from database import database
    from models.core import DocumentStatus

    cid = client_id.strip()
    pid = property_id.strip()
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    db = database.get_db()

    async def upsert_unresolved(suffix: str) -> tuple[str, str]:
        doc_id = str(uuid.uuid4())
        payload: Dict[str, Any] = {
            "document_id": doc_id,
            "client_id": cid,
            "evidence_scope_type": "UNRESOLVED",
            "file_name": f"{PROBE_MARKER}_{suffix}.pdf",
            "file_path": f"{cid}/ops_admin_remediation_probe/{doc_id}.pdf",
            "file_size": 512,
            "mime_type": "application/pdf",
            "status": DocumentStatus.PENDING.value,
            "uploaded_by": "admin_remediation_probe_seed",
            "uploaded_at": now_iso,
            "source": "ops_admin_remediation_probe",
            "ops_admin_remediation_probe": PROBE_MARKER,
            "ops_probe_suffix": suffix,
            "manual_review_flag": True,
        }
        existing = await db.documents.find_one(
            {"ops_admin_remediation_probe": PROBE_MARKER, "ops_probe_suffix": suffix, "client_id": cid},
            {"_id": 0},
        )
        if existing:
            doc_id = str(existing["document_id"])
            await db.documents.update_one({"document_id": doc_id}, {"$set": payload})
            return doc_id, "updated"
        await db.documents.insert_one(payload)
        return doc_id, "inserted"

    unresolved_resolve_id, unresolved_resolve_action = await upsert_unresolved("resolve")
    unresolved_link_id, unresolved_link_action = await upsert_unresolved("link")
    unresolved_reject_id, unresolved_reject_action = await upsert_unresolved("reject")

    retry_doc_id = str(uuid.uuid4())
    extraction_id = str(uuid.uuid4())
    retry_doc: Dict[str, Any] = {
        "document_id": retry_doc_id,
        "client_id": cid,
        "property_id": pid,
        "evidence_scope_type": "PROPERTY",
        "evidence_scope_id": pid,
        "authoritative_property_id": pid,
        "file_name": f"{PROBE_MARKER}_extraction_retry.pdf",
        "file_path": f"{cid}/ops_admin_remediation_probe/{retry_doc_id}.pdf",
        "file_size": 1024,
        "mime_type": "application/pdf",
        "status": DocumentStatus.PENDING.value,
        "uploaded_by": "admin_remediation_probe_seed",
        "uploaded_at": now_iso,
        "source": "ops_admin_remediation_probe",
        "ops_admin_remediation_probe": PROBE_MARKER,
        "extraction_status": "FAILED",
        "extraction_id": extraction_id,
    }
    existing_retry = await db.documents.find_one(
        {"ops_admin_remediation_probe": PROBE_MARKER, "extraction_status": "FAILED", "client_id": cid},
        {"_id": 0},
    )
    if existing_retry:
        retry_doc_id = str(existing_retry["document_id"])
        extraction_id = str(existing_retry.get("extraction_id") or extraction_id)
        retry_doc["document_id"] = retry_doc_id
        retry_doc["extraction_id"] = extraction_id
        await db.documents.update_one({"document_id": retry_doc_id}, {"$set": retry_doc})
        retry_doc_action = "updated"
    else:
        await db.documents.insert_one(retry_doc)
        retry_doc_action = "inserted"

    ext_payload = {
        "extraction_id": extraction_id,
        "document_id": retry_doc_id,
        "client_id": cid,
        "file_name": retry_doc["file_name"],
        "status": "FAILED",
        "extracted": {},
        "errors": {"message": f"{PROBE_MARKER} bounded failed extraction for retry proof"},
        "source": "ops_admin_remediation_probe",
        "audit": {"created_at": now, "updated_at": now},
        "ops_admin_remediation_probe": PROBE_MARKER,
    }
    await db.extracted_documents.update_one(
        {"extraction_id": extraction_id},
        {"$set": ext_payload},
        upsert=True,
    )

    req = await db.requirements.find_one(
        {"client_id": cid, "property_id": pid, "status": {"$nin": ["NOT_REQUIRED"]}},
        {"_id": 0, "requirement_id": 1},
    )

    report = {
        "probe_marker": PROBE_MARKER,
        "captured_at_utc": now_iso,
        "client_id": cid,
        "property_id": pid,
        "unresolved_resolve_document_id": unresolved_resolve_id,
        "unresolved_resolve_action": unresolved_resolve_action,
        "unresolved_link_document_id": unresolved_link_id,
        "unresolved_link_action": unresolved_link_action,
        "unresolved_reject_document_id": unresolved_reject_id,
        "unresolved_reject_action": unresolved_reject_action,
        "retry_document_id": retry_doc_id,
        "retry_extraction_id": extraction_id,
        "retry_doc_action": retry_doc_action,
        "sample_requirement_id": req.get("requirement_id") if req else None,
    }
    return report


async def main() -> None:
    from database import database

    await database.connect()
    args = _parse_args()
    report = await seed_admin_remediation_probe(args.client_id, args.property_id)
    out_path = Path(args.out)
    if not out_path.is_absolute():
        out_path = ROOT / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
