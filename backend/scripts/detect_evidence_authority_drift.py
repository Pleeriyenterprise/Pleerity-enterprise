"""
Detect drift between requirement evidence_authority and mirrored legacy fields.

Run:
  python -m scripts.detect_evidence_authority_drift
  python -m scripts.detect_evidence_authority_drift --json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


async def run(json_out: bool = False) -> Dict[str, object]:
    from database import database
    from services.requirement_evidence_authority import detect_requirement_mirror_drift

    await database.connect()
    db = database.get_db()
    findings: List[Dict[str, object]] = []
    async for req in db.requirements.find(
        {"evidence_authority_synced_at": {"$ne": None}, "evidence_authority.version": {"$gte": 1}},
        {"_id": 0},
    ):
        d = detect_requirement_mirror_drift(req)
        if d.get("drift"):
            findings.append(
                {
                    "requirement_id": req.get("requirement_id"),
                    "client_id": req.get("client_id"),
                    "property_id": req.get("property_id"),
                    "reasons": d.get("reasons") or [],
                    "expected": d.get("expected") or {},
                    "actual": {
                        "status": req.get("status"),
                        "evidence_state": req.get("evidence_state"),
                        "due_date": req.get("due_date"),
                    },
                }
            )
    out = {"drift_count": len(findings), "findings": findings}
    await database.close()
    if json_out:
        print(json.dumps(out, indent=2))
    else:
        print(f"drift_count={out['drift_count']}")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    asyncio.run(run(json_out=bool(args.json)))


if __name__ == "__main__":
    main()

