#!/usr/bin/env python3
"""
P0-STAGING-RENT-PAYMENT-IDEMPOTENCY-INDEX-REMEDIATION-01

Audit and remediate duplicate (client_id, idempotency_key) rows in rent_payments
on staging, then rebuild the partial unique index.

Usage:
  python scripts/p0_staging_rent_payment_idempotency_remediation_01.py --dry-run
  python scripts/p0_staging_rent_payment_idempotency_remediation_01.py --execute
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
import os

load_dotenv(ROOT / ".env")
if not os.environ.get("MONGO_URL") and os.environ.get("MONGO_URI"):
    os.environ["MONGO_URL"] = os.environ["MONGO_URI"]
if not os.environ.get("DB_NAME"):
    os.environ["DB_NAME"] = "pleerity_staging"

OUT_DIR = ROOT / "docs/audit/p0_staging_rent_payment_idempotency_index_remediation_01"
ARCHIVE_COLLECTION = "rent_payments_idempotency_remediation_archive_01"
INDEX_NAME = "client_id_1_idempotency_key_1"


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _canonical_key(doc: Dict[str, Any]) -> str:
    """Stable fingerprint for exact-duplicate detection (exclude _id, payment_id)."""
    keys = (
        "client_id",
        "idempotency_key",
        "ledger_id",
        "property_id",
        "tenancy_id",
        "schedule_id",
        "amount_minor",
        "currency",
        "payment_date",
        "payment_method",
        "reference",
        "note",
        "document_id",
    )
    return json.dumps({k: doc.get(k) for k in keys}, sort_keys=True, default=str)


async def find_duplicate_groups(db) -> List[Dict[str, Any]]:
    pipeline = [
        {"$match": {"idempotency_key": {"$type": "string"}}},
        {
            "$group": {
                "_id": {"client_id": "$client_id", "idempotency_key": "$idempotency_key"},
                "count": {"$sum": 1},
                "docs": {
                    "$push": {
                        "_id": "$_id",
                        "payment_id": "$payment_id",
                        "created_at": "$created_at",
                        "amount_minor": "$amount_minor",
                        "ledger_id": "$ledger_id",
                        "tenancy_id": "$tenancy_id",
                        "schedule_id": "$schedule_id",
                        "property_id": "$property_id",
                        "reference": "$reference",
                        "payment_date": "$payment_date",
                        "currency": "$currency",
                        "payment_method": "$payment_method",
                        "note": "$note",
                        "document_id": "$document_id",
                        "recorded_by": "$recorded_by",
                    }
                },
            }
        },
        {"$match": {"count": {"$gt": 1}}},
        {"$sort": {"count": -1}},
    ]
    return await db.rent_payments.aggregate(pipeline).to_list(500)


def classify_group(group: Dict[str, Any]) -> Dict[str, Any]:
    docs = list(group["docs"])
    docs.sort(key=lambda d: (d.get("created_at") or "", str(d.get("_id"))))
    fingerprints = {_canonical_key(d): d for d in docs}
    exact_duplicate = len(fingerprints) == 1
    canonical = docs[0]
    duplicates = docs[1:]
    return {
        "client_id": group["_id"]["client_id"],
        "idempotency_key": group["_id"]["idempotency_key"],
        "count": group["count"],
        "classification": "exact_duplicate" if exact_duplicate else "conflicting_duplicate",
        "canonical": canonical,
        "duplicates": duplicates,
        "documents": docs,
    }


async def remediate_group(db, group: Dict[str, Any], *, execute: bool) -> Dict[str, Any]:
    result = {
        "client_id": group["client_id"],
        "idempotency_key": group["idempotency_key"],
        "classification": group["classification"],
        "action": "none",
        "removed_ids": [],
    }
    if group["classification"] == "conflicting_duplicate":
        result["action"] = "quarantined"
        if execute:
            await db[ARCHIVE_COLLECTION].insert_one(
                {
                    "remediated_at": _utc(),
                    "programme": "P0-STAGING-RENT-PAYMENT-IDEMPOTENCY-INDEX-REMEDIATION-01",
                    "status": "quarantined_conflicting",
                    "group": group,
                }
            )
        return result

    dup_ids = [d["_id"] for d in group["duplicates"]]
    result["action"] = "remove_duplicates_keep_earliest"
    result["removed_ids"] = [str(i) for i in dup_ids]
    result["kept_payment_id"] = group["canonical"].get("payment_id")
    if execute and dup_ids:
        archive_docs = []
        for d in group["duplicates"]:
            full = await db.rent_payments.find_one({"_id": d["_id"]})
            if full:
                full["remediated_at"] = _utc()
                full["remediation_action"] = "duplicate_removed"
                full["canonical_payment_id"] = group["canonical"].get("payment_id")
                archive_docs.append(full)
        if archive_docs:
            await db[ARCHIVE_COLLECTION].insert_many(archive_docs)
        await db.rent_payments.delete_many({"_id": {"$in": dup_ids}})
    return result


async def rebuild_index(db) -> Dict[str, Any]:
    from database import database

    coll = db.rent_payments
    try:
        await coll.drop_index(INDEX_NAME)
    except Exception:
        pass
    await database._ensure_compound_idempotency_index(coll, label="rent_payments")
    indexes = await coll.index_information()
    return {
        "index_present": INDEX_NAME in indexes,
        "index_spec": indexes.get(INDEX_NAME),
    }


async def verify_no_duplicates(db) -> int:
    groups = await find_duplicate_groups(db)
    return len(groups)


async def recalc_affected_ledgers(db, classified: List[Dict[str, Any]], *, execute: bool) -> List[Dict[str, Any]]:
    """Recalculate ledger balances for ledgers touched by duplicate removal."""
    from services import rent_ledger_service

    ledger_ids = sorted({g["canonical"].get("ledger_id") for g in classified if g.get("canonical", {}).get("ledger_id")})
    results = []
    for lid in ledger_ids:
        sample = next(g for g in classified if g["canonical"].get("ledger_id") == lid)
        client_id = sample["client_id"]
        before = await db.rent_ledger_periods.find_one({"ledger_id": lid, "client_id": client_id})
        entry = {
            "ledger_id": lid,
            "client_id": client_id,
            "before_total_paid_minor": (before or {}).get("total_paid_minor"),
            "before_outstanding_balance_minor": (before or {}).get("outstanding_balance_minor"),
        }
        if execute:
            after_doc = await rent_ledger_service.recalculate_and_persist_ledger(lid, client_id)
            entry["after_total_paid_minor"] = (after_doc or {}).get("total_paid_minor")
            entry["after_outstanding_balance_minor"] = (after_doc or {}).get("outstanding_balance_minor")
        results.append(entry)
    return results


async def verify_post_remediation(db, sample_client_id: str, sample_ledger_id: str) -> Dict[str, Any]:
    """Verify index, duplicate rejection, and distinct insert acceptance."""
    from pymongo.errors import DuplicateKeyError

    indexes = await db.rent_payments.index_information()
    index_ok = INDEX_NAME in indexes and indexes[INDEX_NAME].get("unique") is True

    dup_key = f"P0-IDEM-VERIFY-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    base_doc = {
        "client_id": sample_client_id,
        "ledger_id": sample_ledger_id,
        "idempotency_key": dup_key,
        "payment_id": f"rp_verify_{dup_key[-8:]}",
        "amount_minor": 1,
        "currency": "GBP",
        "payment_date": datetime.now(timezone.utc).date().isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "reference": dup_key,
    }
    await db.rent_payments.insert_one(dict(base_doc))
    dup_rejected = False
    try:
        await db.rent_payments.insert_one({**base_doc, "payment_id": f"rp_verify_dup_{dup_key[-8:]}"})
    except DuplicateKeyError:
        dup_rejected = True
    finally:
        await db.rent_payments.delete_many({"client_id": sample_client_id, "idempotency_key": dup_key})

    distinct_key = f"{dup_key}-distinct"
    distinct_ok = False
    try:
        await db.rent_payments.insert_one({**base_doc, "idempotency_key": distinct_key, "payment_id": f"rp_verify_dist_{dup_key[-8:]}"})
        distinct_ok = True
    finally:
        await db.rent_payments.delete_many({"client_id": sample_client_id, "idempotency_key": distinct_key})

    return {
        "index_exists": index_ok,
        "duplicate_insert_rejected": dup_rejected,
        "distinct_insert_succeeded": distinct_ok,
    }


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    execute = bool(args.execute)
    dry_run = not execute

    from database import database

    await database.connect()
    db = database.get_db()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    report: Dict[str, Any] = {
        "programme": "P0-STAGING-RENT-PAYMENT-IDEMPOTENCY-INDEX-REMEDIATION-01",
        "executed_at": _utc(),
        "db_name": db.name,
        "mode": "dry_run" if dry_run else "execute",
    }

    groups_raw = await find_duplicate_groups(db)
    classified = [classify_group(g) for g in groups_raw]
    report["duplicate_group_count"] = len(classified)
    report["duplicate_groups"] = classified

    remediations = []
    quarantined = []
    for g in classified:
        r = await remediate_group(db, g, execute=execute)
        remediations.append(r)
        if r["classification"] == "conflicting_duplicate":
            quarantined.append(r)

    report["remediations"] = remediations
    report["quarantined_count"] = len(quarantined)

    if execute:
        index_info = await rebuild_index(db)
        report["index"] = index_info
        report["remaining_duplicate_groups"] = await verify_no_duplicates(db)
        report["ledger_recalc"] = await recalc_affected_ledgers(db, classified, execute=True)
        if classified:
            sample = classified[0]
            report["verification"] = await verify_post_remediation(
                db,
                sample["client_id"],
                sample["canonical"].get("ledger_id") or "",
            )
        report["verdict"] = (
            "RENT_PAYMENT_IDEMPOTENCY_RESTORED"
            if report["remaining_duplicate_groups"] == 0
            and index_info.get("index_present")
            and report.get("verification", {}).get("duplicate_insert_rejected")
            else "RENT_PAYMENT_IDEMPOTENCY_RESTORED_WITH_CONDITIONS"
            if quarantined
            else "RENT_PAYMENT_IDEMPOTENCY_BLOCKED"
        )
    else:
        report["verdict"] = "DRY_RUN_COMPLETE"

    (OUT_DIR / "REMEDIATION_REPORT.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    md = [
        "# Rent Payment Idempotency Index Remediation",
        "",
        f"**Executed:** {report['executed_at']}",
        f"**Mode:** {report['mode']}",
        f"**Duplicate groups:** {report['duplicate_group_count']}",
        f"**Quarantined (conflicting):** {report['quarantined_count']}",
        "",
    ]
    if execute:
        md.append(f"**Verdict:** `{report.get('verdict')}`")
        md.append(f"**Remaining duplicates:** {report.get('remaining_duplicate_groups')}")
    (OUT_DIR / "REMEDIATION_REPORT.md").write_text("\n".join(md), encoding="utf-8")

    print(json.dumps({"verdict": report["verdict"], "groups": report["duplicate_group_count"], "execute": execute}, indent=2))
    await database.close()
    return 0 if report["verdict"] != "RENT_PAYMENT_IDEMPOTENCY_BLOCKED" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
