#!/usr/bin/env python3
"""Emit Phase 1 lifecycle semantics classification coverage report (stdout JSON)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.lifecycle_semantics_validation import (  # noqa: E402
    build_classification_report_for_codes,
    documented_fallback_coverage_report,
)

STAGING_CODES = [
    "gas_safety",
    "eicr",
    "epc",
    "hmo_license",
    "legionella",
    "deposit_pi",
    "right_to_rent",
    "tenancy_agreement",
    "smoke_heat_alarms",
    "fitness_for_human_habitation",
]


def main() -> int:
    report = build_classification_report_for_codes(STAGING_CODES)
    out = {
        "classification_coverage": report.to_dict(),
        "fallback_map_coverage": documented_fallback_coverage_report(),
        "staging_scenarios": {
            "S1_gas_safety": "EXPIRY_BASED",
            "S2_eicr": "EXPIRY_BASED",
            "S3_epc": "EXPIRY_BASED",
            "S4_hmo": "EXPIRY_BASED",
            "S5_legionella": "REVIEW_BASED",
            "S6_deposit_pi": "DECLARATION_BASED",
            "S7_right_to_rent": "OCCUPANCY_LIFECYCLE",
            "S8_tenancy_agreement": "TENANCY_LIFECYCLE",
            "S9_smoke_alarms": "EVENT_BASED",
            "S10_operational": "OPERATIONAL",
        },
    }
    print(json.dumps(out, indent=2))
    return 0 if not report.unresolved else 1


if __name__ == "__main__":
    raise SystemExit(main())
