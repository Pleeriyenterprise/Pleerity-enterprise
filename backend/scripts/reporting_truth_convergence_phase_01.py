#!/usr/bin/env python3
"""REPORTING-TRUTH-CONVERGENCE-PHASE-01 — closeout artifacts."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/audit/reporting_governance_and_presentation_audit_01"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
PROGRAMME = "REPORTING-TRUTH-CONVERGENCE-PHASE-01"


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write(name: str, data: Any) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


def run_tests() -> Dict[str, Any]:
    suites = [
        "tests/test_reporting_semantics_v1.py",
        "tests/test_reporting_compliance_export_snapshot.py",
    ]
    results = {}
    all_ok = True
    for s in suites:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", s, "-q", "--tb=no"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=120,
        )
        ok = proc.returncode == 0
        results[s] = {"passed": ok, "tail": (proc.stdout or proc.stderr)[-400:]}
        all_ok = all_ok and ok
    return {"all_passed": all_ok, "suites": results, "audited_at": _utc()}


def main() -> int:
    from services.reporting_semantics_v1 import (
        REPORTING_METRIC_DEFINITIONS,
        SURFACE_EXPORT_REGISTRY,
        PDF_ENGINE_RULES,
        EXPORT_GRADE_DEFINITIONS,
    )

    _write(
        "reporting_semantics_runtime.json",
        {
            "programme": PROGRAMME,
            "module": "services/reporting_semantics_v1.py",
            "version": "v1",
            "metrics": list(REPORTING_METRIC_DEFINITIONS.keys()),
            "definitions": REPORTING_METRIC_DEFINITIONS,
            "loader": "load_score_projection_portal_rows (filter → enrich → project → portal-visible)",
        },
    )
    _write(
        "surface_convergence_runtime.json",
        {
            "programme": PROGRAMME,
            "surfaces": {
                "dashboard_score_widget": {
                    "semantic_mode": "score_projection",
                    "metrics": ["score_tracked_requirement_count", "compliant_requirement_count"],
                    "api": "GET /client/compliance-score",
                    "labels": "dashboardScoreWidgetLabels.js",
                },
                "requirements_page": {
                    "semantic_mode": "tracked_registry_lifecycle",
                    "metrics": ["tracked_requirement_count", "satisfied_requirement_count", "verified_requirement_count"],
                    "api": "GET /client/requirements + reporting_semantics block",
                    "labels": "reportingSemanticsLabels.js",
                },
                "compliance_summary_csv": {
                    "semantic_mode": "score_projection",
                    "pipeline": "load_score_projection_portal_rows (aligned with compliance-score)",
                },
                "requirements_report_csv": {
                    "semantic_mode": "score_projection rows + semantics preamble",
                },
            },
            "intentional_divergence": "tracked_requirement_count may exceed score_tracked_requirement_count — disclosed in CSV preamble and UI tooltips",
        },
    )
    _write(
        "evidence_pack_governance_runtime.json",
        {
            "programme": PROGRAMME,
            "governed": {
                "route": "POST /client/compliance/audit-pack/generate",
                "grade": "AUDIT_ARTIFACT",
                "immutability": "GridFS + manifest checksums",
                "ui": "ReportsAuditPackPage immutable disclosure",
            },
            "operational": {
                "route": "POST /client/evidence-pack/jobs",
                "grade": "OPERATIONAL_EXPORT",
                "ui": "ReportsPage OPERATIONAL_ZIP_DISCLOSURE",
            },
        },
    )
    _write(
        "deterministic_export_runtime.json",
        {
            "programme": PROGRAMME,
            "registry": SURFACE_EXPORT_REGISTRY,
            "live_regenerated": ["evidence_readiness_pdf", "evidence_readiness_redownload", "score_explanation_pdf"],
            "immutable": ["audit_evidence_pack_zip"],
            "point_in_time": ["compliance_summary_csv", "requirements_report_csv", "score_drivers_csv"],
        },
    )
    _write(
        "report_grade_runtime.json",
        {"programme": PROGRAMME, "grades": EXPORT_GRADE_DEFINITIONS, "surface_map": SURFACE_EXPORT_REGISTRY},
    )
    _write(
        "pdf_engine_governance_runtime.json",
        {"programme": PROGRAMME, "rules": PDF_ENGINE_RULES},
    )
    _write(
        "async_reporting_governance_runtime.json",
        {
            "programme": PROGRAMME,
            "module": "async_reporting_disclosure in reporting_semantics_v1",
            "wired": ["compliance_summary CSV async_score_note rows", "compliance-score reporting_semantics"],
        },
    )

    regression = run_tests()
    _write("regression_runtime.json", regression)

    classification = "VERIFIED_OPERATIONALLY" if regression["all_passed"] else "PARTIAL"
    _write(
        "classifications.json",
        {
            "programme": PROGRAMME,
            "classified_at": _utc(),
            "classification": classification,
            "prior_audit": "REPORT_TRUTH_DRIFT",
            "remediation": [
                "Central reporting_semantics_v1 layer",
                "Exports use enrich+projection pipeline",
                "Explicit metric definitions in API and CSV",
                "Export grades and determinism registry",
                "UI disclosures for live vs immutable exports",
            ],
            "residual_watchlist": [
                "Evidence Readiness still live-regenerated (disclosed, not snapshotted)",
                "jsPDF client PDFs remain CLIENT_PRESENTATION grade only",
            ],
        },
    )

    report = f"""# {PROGRAMME}

Audited at: {_utc()}
Classification: **{classification}**

## Summary
Introduced `services/reporting_semantics_v1.py` as the canonical definitions layer. Compliance exports and compliance-score API now share `load_score_projection_portal_rows` (filter → enrich → project). Requirements API and page labels disclose **tracked registry** vs **score-tracked** semantics.

## Regression
{'PASS' if regression['all_passed'] else 'FAIL — see regression_runtime.json'}

## Prior audit
REPORTING-GOVERNANCE-AND-PRESENTATION-AUDIT-01 identified REPORT_TRUTH_DRIFT from missing enrich on exports and undisclosed metric definitions.
"""
    (OUT / "REPORT.md").write_text(report, encoding="utf-8")
    (OUT / "watchlist.md").write_text(
        f"""# Watchlist — reporting truth convergence ({_utc()[:10]})

## Classification: {classification}

- [ ] Optional: snapshot Evidence Readiness PDF bytes at first generation
- [ ] Property RAG in compliance summary CSV still from DB field (label or recompute)
- [ ] Migrate client jsPDF compliance PDF to server ReportLab when product approves

## Completed in phase 01
- reporting_semantics_v1 metrics A–I
- CSV/API semantics preamble
- Export grade + determinism on /reports/available
- Evidence pack vs operational ZIP copy
""",
        encoding="utf-8",
    )
    print(f"{PROGRAMME} classification={classification}")
    return 0 if classification == "VERIFIED_OPERATIONALLY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
