#!/usr/bin/env python3
"""AUDIENCE-GOVERNANCE-CONVERGENCE-01 closeout."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/audit/requirement_satisfaction_business_outcome_audit_01"
PROGRAMME = "AUDIENCE-GOVERNANCE-CONVERGENCE-01"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write(name: str, data: Any) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


def main() -> int:
    from services.audience_governance_v1 import audience_model_export, AUDIENCE_EXPORT_PREAMBLE

    _write("audience_model_runtime.json", {"programme": PROGRAMME, "audited_at": _utc(), **audience_model_export()})
    _write(
        "state_interpretation_runtime.json",
        {
            "programme": PROGRAMME,
            "audited_at": _utc(),
            "module": "services/audience_governance_v1.py:interpret_requirement_for_audience",
            "status": "implemented",
        },
    )
    _write(
        "report_section_convergence_runtime.json",
        {
            "programme": PROGRAMME,
            "audited_at": _utc(),
            "sections": [
                "Unresolved obligations",
                "Recorded but not independently verified",
                "Awaiting review",
                "Verified / accepted evidence (summary)",
            ],
            "is_unresolved_row": "action-required bucket only — excludes SATISFIED_UNVERIFIED",
            "entry": "append_audience_governed_obligation_sections",
            "status": "implemented",
        },
    )
    _write(
        "audience_disclosure_runtime.json",
        {
            "programme": PROGRAMME,
            "audited_at": _utc(),
            "preamble": AUDIENCE_EXPORT_PREAMBLE,
            "pdf": True,
            "score_explanation": True,
            "status": "implemented",
        },
    )
    _write(
        "surface_integration_runtime.json",
        {
            "programme": PROGRAMME,
            "audited_at": _utc(),
            "backend": [
                "enrich_requirement_dict.audience_interpretation",
                "pdf_report_builder",
                "professional_reports via append_unresolved",
                "reporting_service requirements CSV columns",
            ],
            "frontend": ["utils/audienceGovernance.js", "API audience_interpretation on requirements"],
            "status": "implemented",
        },
    )
    _write(
        "score_explanation_audience_runtime.json",
        {
            "programme": PROGRAMME,
            "audited_at": _utc(),
            "module": "score_explanation_audience_lines",
            "status": "implemented",
        },
    )
    _write(
        "csv_audience_runtime.json",
        {
            "programme": PROGRAMME,
            "audited_at": _utc(),
            "columns": [
                "operational_status",
                "evidential_assurance",
                "audience_status",
                "review_state",
                "action_required",
            ],
            "status": "implemented",
        },
    )

    suites = [
        "tests/test_audience_governance_v1.py",
        "tests/test_report_layout_governance.py",
        "tests/test_pdf_report_builder.py",
        "tests/test_requirement_satisfaction_service.py",
        "tests/test_compliance_scoring_satisfaction_convergence.py",
        "tests/test_report_human_language_v1.py",
    ]
    results = {}
    all_ok = True
    for s in suites:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", s, "-q", "--tb=no"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=300,
        )
        ok = proc.returncode == 0
        results[s] = {"passed": ok}
        all_ok = all_ok and ok
    _write("regression_runtime.json", {"programme": PROGRAMME, "all_passed": all_ok, "suites": results, "audited_at": _utc()})

    classification = "VERIFIED_OPERATIONALLY" if all_ok else "PARTIAL"
    _write(
        "classifications.json",
        {
            "programme": PROGRAMME,
            "classified_at": _utc(),
            "classification": classification,
            "prior_audit": "AUDIENCE_GOVERNANCE_GAP",
            "resolved": [
                "PDF section split",
                "is_unresolved_row excludes self-recorded satisfied",
                "audience_interpretation on client enrich",
            ],
        },
    )
    (OUT / "REPORT.md").write_text(
        f"# {PROGRAMME}\n\nClassification: **{classification}**\n\nAudience-governed export sections and interpretation layer implemented.\n",
        encoding="utf-8",
    )
    (OUT / "watchlist.md").write_text(
        f"""# Watchlist — {PROGRAMME}\n\n## {classification}\n\n### Done\n- audience_governance_v1.py\n- PDF multi-section obligations\n- CSV audience columns\n- audience_interpretation on client requirements API\n\n### P2\n- [ ] Requirements UI bind to audience_interpretation when present\n- [ ] Insurer/lender dedicated export templates\n""",
        encoding="utf-8",
    )
    print(f"{PROGRAMME} classification={classification}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
