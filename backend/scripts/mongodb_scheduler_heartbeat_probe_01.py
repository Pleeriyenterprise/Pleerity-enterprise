"""Governed staging scheduler heartbeat probe — valid Atlas aggregations only."""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
OUT = ROOT / "docs" / "audit" / "mongodb_scheduler_heartbeat_probe_01.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def main() -> int:
    window = 130
    for a in sys.argv[1:]:
        if a.startswith("--window="):
            window = int(a.split("=", 1)[1])

    uri = os.environ.get("MONGO_URL") or os.environ.get("MONGO_URI")
    if not uri:
        print("NO_URI", file=sys.stderr)
        return 2

    client = MongoClient(uri, serverSelectionTimeoutMS=20000)
    db = client["pleerity_staging"]
    before = db.scheduler_heartbeat.find_one({"_id": "default"})
    before_at = (before or {}).get("last_heartbeat_at")
    job_runs_before = db.job_runs.count_documents({})
    # Top jobs without invalid Atlas operators — simple find+count
    sample = list(
        db.job_runs.find({}, {"job_name": 1, "created_at": 1, "run_type": 1})
        .sort("created_at", -1)
        .limit(10)
    )

    time.sleep(window)

    after = db.scheduler_heartbeat.find_one({"_id": "default"})
    after_at = (after or {}).get("last_heartbeat_at")
    job_runs_after = db.job_runs.count_documents({})

    if before_at is None and after_at is None:
        state = "missing"
    elif before_at != after_at:
        state = "advancing"
    else:
        state = "unchanged_or_stale"

    evidence = {
        "probe": "mongodb_scheduler_heartbeat_probe_01",
        "database": "pleerity_staging",
        "window_seconds": window,
        "captured_at": _now(),
        "before": {"last_heartbeat_at": before_at, "job_runs": job_runs_before},
        "after": {"last_heartbeat_at": after_at, "job_runs": job_runs_after},
        "state": state,
        "recent_job_runs_sample": [
            {
                "job_name": d.get("job_name"),
                "created_at": d.get("created_at"),
                "run_type": d.get("run_type"),
            }
            for d in sample
        ],
        "exit_hint": 0 if state in ("advancing", "unchanged_or_stale", "missing") else 1,
    }
    OUT.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(json.dumps({"wrote": str(OUT), "state": state, "before": before_at, "after": after_at}, indent=2))
    client.close()
    # advancing = success(0); missing/stale = 3 (runtime defect signal, probe itself OK)
    if state == "advancing":
        return 0
    if state == "missing":
        return 3
    return 4  # unchanged/stale


if __name__ == "__main__":
    raise SystemExit(main())
