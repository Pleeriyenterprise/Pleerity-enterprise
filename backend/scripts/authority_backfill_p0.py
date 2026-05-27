#!/usr/bin/env python3
"""
P0-D historical lifecycle backfill (INV-RS-002, INV-IS-002, INV-JO-002).

Dry-run by default. Pass --apply to write. Never fabricates timestamps without a recoverable source.

Usage:
  python scripts/authority_backfill_p0.py
  python scripts/authority_backfill_p0.py --apply --client-id <uuid>
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Allow running from backend/
_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from database import database  # noqa: E402

AUTHORITY_BACKFILL_VERSION = "p0-authority-2026-05-27"


def _parse_dt(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
    except Exception:
        return None


def _pick_recoverable_ts(*candidates: Any) -> Optional[str]:
    for c in candidates:
        if c is None:
            continue
        if hasattr(c, "isoformat"):
            return c.isoformat()
        s = str(c).strip()
        if s:
            return s
    return None


async def _backfill_risk_signals(db, client_id: Optional[str], apply: bool) -> Dict[str, Any]:
    q: Dict[str, Any] = {"status": "resolved", "resolved_at": {"$in": [None, ""]}}
    if client_id:
        q["client_id"] = client_id
    report = {
        "collection": "risk_signals",
        "invariant": "INV-RS-002",
        "recoverable": 0,
        "non_recoverable": 0,
        "ambiguous": 0,
        "applied": 0,
        "samples": [],
    }
    cursor = db.risk_signals.find(q, {"_id": 0})
    async for doc in cursor:
        sid = doc.get("signal_id")
        src = _pick_recoverable_ts(doc.get("updated_at"), doc.get("generated_at"))
        if src:
            report["recoverable"] += 1
            if apply:
                await db.risk_signals.update_one(
                    {"signal_id": sid, "client_id": doc.get("client_id")},
                    {
                        "$set": {
                            "resolved_at": src,
                            "authority_backfill_version": AUTHORITY_BACKFILL_VERSION,
                        }
                    },
                )
                report["applied"] += 1
            if len(report["samples"]) < 5:
                report["samples"].append({"signal_id": sid, "resolved_at": src, "source": "updated_at|generated_at"})
        else:
            report["non_recoverable"] += 1

    q2: Dict[str, Any] = {"status": "acknowledged", "acknowledged_at": {"$in": [None, ""]}}
    if client_id:
        q2["client_id"] = client_id
    async for doc in db.risk_signals.find(q2, {"_id": 0}):
        sid = doc.get("signal_id")
        src = _pick_recoverable_ts(doc.get("updated_at"), doc.get("generated_at"))
        if src:
            report.setdefault("ack_recoverable", 0)
            report["ack_recoverable"] = report.get("ack_recoverable", 0) + 1
            if apply:
                await db.risk_signals.update_one(
                    {"signal_id": sid, "client_id": doc.get("client_id")},
                    {
                        "$set": {
                            "acknowledged_at": src,
                            "authority_backfill_version": AUTHORITY_BACKFILL_VERSION,
                        }
                    },
                )
                report["applied"] += 1
        else:
            report.setdefault("ack_non_recoverable", 0)
            report["ack_non_recoverable"] = report.get("ack_non_recoverable", 0) + 1
    return report


async def _backfill_issues(db, client_id: Optional[str], apply: bool) -> Dict[str, Any]:
    q: Dict[str, Any] = {"status": {"$in": ["closed", "cancelled", "resolved"]}, "closed_at": {"$in": [None, ""]}}
    if client_id:
        q["client_id"] = client_id
    report = {
        "collection": "maintenance_issues",
        "invariant": "INV-IS-002",
        "recoverable": 0,
        "non_recoverable": 0,
        "ambiguous": 0,
        "applied": 0,
        "samples": [],
    }
    async for doc in db.maintenance_issues.find(q, {"_id": 0}):
        iid = doc.get("issue_id")
        wo = None
        if doc.get("issue_id"):
            wo = await db.work_orders.find_one(
                {"issue_id": iid, "client_id": doc.get("client_id"), "status": {"$in": ["VERIFIED", "CLOSED", "COMPLETED"]}},
                {"verified_at": 1, "completed_at": 1, "updated_at": 1},
            )
        src = _pick_recoverable_ts(
            doc.get("resolved_at"),
            (wo or {}).get("verified_at"),
            (wo or {}).get("completed_at"),
            doc.get("updated_at"),
        )
        if src:
            report["recoverable"] += 1
            if apply:
                patch = {
                    "closed_at": src,
                    "authority_backfill_version": AUTHORITY_BACKFILL_VERSION,
                }
                if not doc.get("closed_by"):
                    patch["closed_by"] = "backfill:authority_p0"
                await db.maintenance_issues.update_one(
                    {"issue_id": iid, "client_id": doc.get("client_id")},
                    {"$set": patch},
                )
                report["applied"] += 1
            if len(report["samples"]) < 5:
                report["samples"].append({"issue_id": iid, "closed_at": src})
        elif wo:
            report["ambiguous"] += 1
        else:
            report["non_recoverable"] += 1
    return report


async def _backfill_work_orders(db, client_id: Optional[str], apply: bool) -> Dict[str, Any]:
    q: Dict[str, Any] = {"status": "VERIFIED", "verified_at": {"$in": [None, ""]}}
    if client_id:
        q["client_id"] = client_id
    report = {
        "collection": "work_orders",
        "invariant": "INV-JO-002",
        "recoverable": 0,
        "non_recoverable": 0,
        "applied": 0,
        "samples": [],
    }
    async for doc in db.work_orders.find(q, {"_id": 0}):
        wid = doc.get("work_order_id")
        src = _pick_recoverable_ts(doc.get("completed_at"), doc.get("updated_at"))
        if src:
            report["recoverable"] += 1
            if apply:
                await db.work_orders.update_one(
                    {"work_order_id": wid},
                    {
                        "$set": {
                            "verified_at": src,
                            "authority_backfill_version": AUTHORITY_BACKFILL_VERSION,
                        }
                    },
                )
                report["applied"] += 1
            if len(report["samples"]) < 5:
                report["samples"].append({"work_order_id": wid, "verified_at": src})
        else:
            report["non_recoverable"] += 1
    return report


async def run_backfill(client_id: Optional[str], apply: bool) -> Dict[str, Any]:
    await database.connect()
    db = database.get_db()
    out = {
        "programme": "PRELAUNCH-AUTHORITY-HARDENING-P0-D",
        "mode": "apply" if apply else "dry_run",
        "authority_backfill_version": AUTHORITY_BACKFILL_VERSION,
        "client_id_filter": client_id,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "sections": [],
    }
    for fn in (_backfill_risk_signals, _backfill_issues, _backfill_work_orders):
        out["sections"].append(await fn(db, client_id, apply))
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="P0-D authority backfill (dry-run default)")
    parser.add_argument("--apply", action="store_true", help="Apply safe backfills")
    parser.add_argument("--client-id", default=None, help="Limit to one client")
    parser.add_argument("--out", default=None, help="Write JSON report path")
    args = parser.parse_args()
    report = asyncio.run(run_backfill(args.client_id, args.apply))
    text = json.dumps(report, indent=2)
    print(text)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
