"""
Static audit for legacy requirement/document truth field reads.

Classifications:
- allowed: tests, migrations/backfills, model definitions, explicit mirror/drift tools.
- transitional: compatibility fallbacks inside authority/expiry adapters.
- forbidden: runtime readers outside adapters that may treat legacy fields as authoritative.

Run:
  python -m scripts.audit_authority_legacy_reads
  python -m scripts.audit_authority_legacy_reads --json
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parent.parent

LEGACY_PATTERNS = [
    re.compile(r'get\("confirmed_expiry_date"\)'),
    re.compile(r'get\("extracted_expiry_date"\)'),
    re.compile(r'get\("due_date"\)'),
    re.compile(r'get\("evidence_state"\)'),
    re.compile(r'get\("status"\)\s*==\s*"(COMPLIANT|PENDING|OVERDUE|EXPIRED|EXPIRING_SOON|MISSING)"'),
]

ALLOWED_PATH_PARTS = (
    "\\tests\\",
    "/tests/",
    "\\models\\core.py",
    "/models/core.py",
    "\\scripts\\",
    "/scripts/",
)
TRANSITIONAL_FILES = {
    "utils/expiry_utils.py",
    "services/requirement_evidence_authority.py",
    "services/compliance_scoring_v2.py",
}
CRITICAL_RUNTIME_PREFIXES = (
    "services/reminder_truth_service.py",
    "services/lead_automation_service.py",
    "services/client_priority_stream.py",
    "services/unified_tasks_service.py",
)
IGNORE_SNIPPET_PARTS = (
    '"due_date":',
    '"evidence_state":',
    "metadata={",
    't.get("due_date")',
)


def _classify(path: Path) -> str:
    p = str(path).replace("\\", "/")
    if any(x in p for x in ALLOWED_PATH_PARTS):
        return "allowed"
    if any(p.endswith(x) for x in TRANSITIONAL_FILES):
        return "transitional"
    if any(p.endswith(x) for x in CRITICAL_RUNTIME_PREFIXES):
        return "forbidden"
    return "allowed"


def run_audit() -> Dict[str, object]:
    findings: List[Dict[str, object]] = []
    for py in ROOT.rglob("*.py"):
        p = str(py).replace("\\", "/")
        if "/.venv/" in p or "/__pycache__/" in p:
            continue
        txt = py.read_text(encoding="utf-8", errors="ignore")
        lines = txt.splitlines()
        for i, line in enumerate(lines, start=1):
            if not any(rx.search(line) for rx in LEGACY_PATTERNS):
                continue
            if any(part in line for part in IGNORE_SNIPPET_PARTS):
                continue
            cls = _classify(py)
            findings.append(
                {
                    "path": str(py.relative_to(ROOT)).replace("\\", "/"),
                    "line": i,
                    "classification": cls,
                    "snippet": line.strip()[:220],
                }
            )
    summary = {"allowed": 0, "transitional": 0, "forbidden": 0}
    for f in findings:
        summary[str(f["classification"])] += 1
    return {"summary": summary, "findings": findings}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    out = run_audit()
    if args.json:
        print(json.dumps(out, indent=2))
        return
    s = out["summary"]
    print("authority_legacy_read_audit")
    print(f"allowed={s['allowed']} transitional={s['transitional']} forbidden={s['forbidden']}")
    for f in out["findings"]:
        if f["classification"] == "forbidden":
            print(f"FORBIDDEN {f['path']}:{f['line']} {f['snippet']}")


if __name__ == "__main__":
    main()

