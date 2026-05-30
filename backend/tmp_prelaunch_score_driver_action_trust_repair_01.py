#!/usr/bin/env python3
"""PRELAUNCH-SCORE-DRIVER-ACTION-TRUST-REPAIR-01 — score-driver action column verification."""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "docs/audit/prelaunch_score_driver_action_trust_repair_01"
PROGRAMME = "PRELAUNCH-SCORE-DRIVER-ACTION-TRUST-REPAIR-01"

LEAK_PATTERNS = [
    r"server-confirmed",
    r"remediation step is available",
    r"remediation metadata",
    r"no server-confirmed",
    r"score-driver-remediation-non-actionable",
]

TARGET_FILES = [
    ROOT.parent / "frontend/src/pages/ComplianceScorePage.js",
    ROOT.parent / "frontend/src/pages/ComplianceScorePage.scoreDriverActions.js",
    ROOT.parent / "docs/governance/TRUST_LANGUAGE_GOVERNANCE.md",
]


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def static_audit() -> dict:
    hits = []
    for path in TARGET_FILES:
        if not path.exists():
            hits.append({"file": str(path), "issue": "missing"})
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        rel = str(path.relative_to(ROOT.parent))
        if path.name.endswith(".md"):
            continue
        for line in text.splitlines():
            if "FORBIDDEN" in line or "validateCustomerCopy" in line or "queryByText" in line:
                continue
            for pat in LEAK_PATTERNS:
                if re.search(pat, line, re.I):
                    hits.append({"file": rel, "pattern": pat, "line": line.strip()[:120]})
        if path.name == "ComplianceScorePage.scoreDriverActions.js":
            if "resolveScoreDriverActionPresentation" not in text:
                hits.append({"file": rel, "issue": "missing tier resolver"})
            if "Open requirement" not in text:
                hits.append({"file": rel, "issue": "missing Level B label"})
    return {"forbidden_hits": hits, "pass": not hits}


def main() -> int:
    audit = static_audit()
    classification = "OPERATIONALLY_GUIDED" if audit["pass"] else "FALLBACK_DIAGNOSTIC_LEAK"
    result = {
        "programme": PROGRAMME,
        "classification": classification,
        "static_audit": audit,
        "captured_at": _utc(),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "static_audit.json").write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    (OUT / "classifications.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    (OUT / "REPORT.md").write_text(
        f"# {PROGRAMME}\n\nClassification: **{classification}**\n",
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2))
    return 0 if audit["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
