"""
Optional one-time / ops: set clients.default_jurisdiction + clients.enabled_jurisdictions
from the union of properties.jurisdiction when those client fields are missing or empty.

Safe: does not overwrite non-empty stored enabled_jurisdictions / valid default_jurisdiction.

Run (from backend/, with MONGO_URL / DB_NAME set):
  python -m scripts.backfill_client_jurisdiction_from_properties
"""
from __future__ import annotations

import os

from pymongo import MongoClient

from services.compliance_rules_registry import (
    canonicalize_uk_portfolio_label,
    derive_account_jurisdiction_fields_from_property_labels,
)


def main() -> None:
    url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "compliance_vault_pro")
    mc = MongoClient(url, serverSelectionTimeoutMS=15_000)
    db = mc[db_name]
    updated = 0
    scanned = 0
    for row in db.clients.find({}, {"_id": 0, "client_id": 1, "default_jurisdiction": 1, "enabled_jurisdictions": 1}):
        scanned += 1
        cid = row.get("client_id")
        if not cid:
            continue
        has_def = bool(canonicalize_uk_portfolio_label(row.get("default_jurisdiction")))
        raw_en = row.get("enabled_jurisdictions")
        has_en = isinstance(raw_en, list) and len([x for x in raw_en if canonicalize_uk_portfolio_label(x)]) > 0
        if has_def and has_en:
            continue
        props = list(db.properties.find({"client_id": cid}, {"_id": 0, "jurisdiction": 1}))
        dd, dlist = derive_account_jurisdiction_fields_from_property_labels([p.get("jurisdiction") for p in props])
        if not dd or not dlist:
            continue
        db.clients.update_one(
            {"client_id": cid},
            {"$set": {"default_jurisdiction": dd, "enabled_jurisdictions": dlist}},
        )
        updated += 1
    print(f"scanned_clients={scanned} updated_clients={updated}")


if __name__ == "__main__":
    main()
