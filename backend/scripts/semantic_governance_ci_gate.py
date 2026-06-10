#!/usr/bin/env python3
"""S2-A semantic governance CI gate — deterministic drift check (no network)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.vocabulary_contract_v1 import contract_export_snapshot, scan_registered_customer_surfaces


def main() -> int:
    snap = contract_export_snapshot()
    scan = scan_registered_customer_surfaces()
    failures = []
    if scan.get("prohibited_hits"):
        failures.append({"type": "prohibited_phrases", "detail": scan["prohibited_hits"]})
    if scan.get("telemetry_leaks"):
        failures.append({"type": "telemetry_leaks", "detail": scan["telemetry_leaks"]})

    report = {
        "programme": "SEMANTIC-GOVERNANCE-CI-GATE",
        "contract_version": snap["version"],
        "scan": scan,
        "failures": failures,
        "pass": not failures,
    }
    print(json.dumps(report, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
