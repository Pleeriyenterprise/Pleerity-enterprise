#!/usr/bin/env python3
"""REPORTING-ENTERPRISE-PRESENTATION-GOVERNANCE-01"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/audit/reporting_governance_and_presentation_audit_01"
PROGRAMME = "REPORTING-ENTERPRISE-PRESENTATION-GOVERNANCE-01"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write(name: str, data: Any) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


def template_inventory() -> Dict[str, Any]:
    return {
        "programme": PROGRAMME,
        "audited_at": _utc(),
        "templates": [
            {
                "id": "evidence_readiness_portfolio_pdf",
                "engine": "reportlab",
                "module": "services/pdf_report_builder.py:build_portfolio_report",
                "layout_system": "platypus SimpleDocTemplate A4; branded TableStyle via _build_styles_and_table_style",
                "reusable_template": "partial — shared styles/table_style, no external template file",
                "typography": "Helvetica 8–24pt; branded primary/secondary hex",
                "branding": "branding_resolver via report_data.branding",
                "pagination": "PageBreak cover only; no running header/footer on every page",
                "appendix": "audit snapshot table only; no indexed evidence appendix",
                "evidence_refs": "requirement matrix by property; no doc_id hyperlinks",
                "print_readiness": "adequate A4; wide tables may clip on narrow print",
                "mobile_readiness": "poor — dense tables",
            },
            {
                "id": "evidence_readiness_property_pdf",
                "engine": "reportlab",
                "module": "pdf_report_builder.py:build_property_report",
                "layout_system": "same family as portfolio",
                "reusable_template": "shared with portfolio builder",
                "pagination": "limited",
                "print_readiness": "adequate",
            },
            {
                "id": "score_explanation_pdf",
                "engine": "reportlab",
                "module": "pdf_report_builder.py:build_score_explanation_report",
                "layout_system": "executive summary + bucket breakdown when v2 present",
                "tier": "EXECUTIVE_SUMMARY grade",
                "governance_copy": "Snapshot as of; forbids live calculator language (tested)",
                "print_readiness": "good for 1–3 pages",
            },
            {
                "id": "professional_compliance_summary_pdf",
                "engine": "reportlab",
                "module": "services/professional_reports.py:generate_compliance_summary_pdf",
                "layout_system": "SimpleDocTemplate; create_styles/create_table_style",
                "branding": "get_branding(client_id) white-label",
                "pagination": "no page numbers in builder",
                "appendix": "expiry schedule section inline",
                "tier": "CLIENT_PRESENTABLE",
            },
            {
                "id": "professional_expiry_schedule_pdf",
                "engine": "reportlab",
                "module": "professional_reports.py",
                "tier": "CLIENT_PRESENTABLE",
            },
            {
                "id": "professional_audit_log_pdf",
                "engine": "reportlab",
                "module": "professional_reports.py",
                "tier": "AUDIT_READY (activity trail, not evidence pack)",
            },
            {
                "id": "compliance_summary_jspdf",
                "engine": "jspdf",
                "module": "frontend/ReportsPage.js:generatePDF",
                "layout_system": "imperative coordinates + jspdf-autotable",
                "reusable_template": "none — duplicated header/footer inline",
                "typography": "8–20pt; hard-coded midnight-blue header bar",
                "branding": "CVP product header only — not client white-label resolver",
                "pagination": "page x of y footer",
                "governance_gaps": "no score_status_message block; local browser date not UTC; no assurance tier column",
                "tier": "CLIENT_PRESENTABLE (weak)",
            },
            {
                "id": "requirements_jspdf",
                "engine": "jspdf",
                "module": "ReportsPage.js generatePDF requirements branch",
                "overflow": "7pt font wide table — overflow risk on long descriptions",
                "tier": "INTERNAL_OPERATIONAL_ONLY",
            },
            {
                "id": "monthly_digest_jspdf",
                "engine": "jspdf",
                "module": "ReportsPage.js:downloadDigestPdf",
                "tier": "EXECUTIVE_READY (summary only)",
                "governance": "email content re-rendered client-side — not immutable",
            },
            {
                "id": "compliance_summary_csv",
                "engine": "csv_text",
                "module": "reporting_service._generate_compliance_csv",
                "semantics_preamble": "reporting_semantics_v1 csv_semantics_preamble_rows",
                "tier": "OPERATIONAL_EXPORT / handoff",
            },
            {
                "id": "requirements_report_csv",
                "engine": "csv_text",
                "module": "reporting_service._generate_requirements_csv",
                "tier": "CLIENT_PRESENTABLE data; not print layout",
            },
            {
                "id": "score_drivers_csv",
                "engine": "csv_text",
                "module": "routes/reports.py get_score_drivers_csv",
                "tier": "OPERATIONAL_EXPORT",
            },
            {
                "id": "audit_evidence_pack_zip",
                "engine": "zip + reportlab summary pdf + files",
                "module": "compliance_audit_evidence_pack_service.py",
                "layout_system": "ROOT_DIR folder contract + manifest JSON + checksums",
                "appendix": "03_COMPLIANCE_EVIDENCE verified files + NO_ACTIVE_EVIDENCE marker",
                "export_identity": "export_id, export_rules_version, registry_version_used",
                "tier": "REGULATOR_READY / AUDIT_READY",
                "print_readiness": "ZIP navigation requires desktop unzip literacy",
            },
            {
                "id": "evidence_pack_jobs_zip",
                "engine": "zip csv",
                "module": "evidence_pack_service",
                "tier": "OPERATIONAL_EXPORT only",
            },
            {
                "id": "scheduled_report_email",
                "engine": "html email + csv attachment",
                "module": "jobs.py SCHEDULED_REPORT",
                "tier": "CLIENT_PRESENTABLE email body; CSV operational",
            },
            {
                "id": "admin_reports_hub",
                "engine": "reportlab + openpyxl + csv",
                "module": "routes/reporting.py",
                "tier": "INTERNAL_OPERATIONAL_ONLY",
            },
        ],
    }


def presentation_quality() -> Dict[str, Any]:
    ratings = {
        "evidence_readiness_reportlab": {
            "tier": "CLIENT_PRESENTABLE",
            "hierarchy": "strong cover + exec summary + sections; weak running nav",
            "typography": "consistent Helvetica stack; score meta in 8pt sublines — readable",
            "whitespace": "adequate; property matrix dense after ~10 properties",
            "evidence_grouping": "by property tables; no assurance chip per row",
            "overflow": "tables hard-truncate text [:35]; no repeat header on page split",
            "page_breaks": "cover break only — long portfolios run together",
            "cover": "title + CRN + scope + UTC timestamp — no logo image on cover",
            "disclaimers": "legal footer + jurisdiction notice + snapshot framing paragraph",
            "unresolved_risk": "top risk drivers section when overdue/expiring — not full backlog",
            "assurance_visibility": "weak — uses computed status labels not lifecycle/assurance tier",
            "harsh_notes": [
                "Matrix omits platform review vs self-recorded distinction",
                "Cap 20 properties / 30 reqs per property silently truncates large portfolios",
                "Claims snapshot in PDF body but HTTP re-download is live_regenerated",
            ],
        },
        "professional_compliance_pdf": {
            "tier": "CLIENT_PRESENTABLE",
            "hierarchy": "executive blocks + tables",
            "branding": "white-label colors — stronger than jsPDF",
            "harsh_notes": ["No page numbers", "Property RAG from DB may stale vs live dashboard"],
        },
        "audit_evidence_pack": {
            "tier": "REGULATOR_READY",
            "hierarchy": "folder contract + summary PDF + manifest",
            "governance": "export identity block, scope/limitations, compliance status authority",
            "harsh_notes": [
                "UX depends on ZIP literacy — not single scrollable PDF for councils",
                "Summary PDF lacks branded cover sheet with logo slot (text-only)",
            ],
        },
        "jspdf_compliance_requirements": {
            "tier": "INTERNAL_OPERATIONAL_ONLY",
            "hierarchy": "flat header bar + autotable",
            "harsh_notes": [
                "Not white-label — product branding only",
                "No immutable artifact framing",
                "Must not be used for lender/regulator submission",
            ],
        },
        "score_explanation_pdf": {
            "tier": "EXECUTIVE_READY",
            "harsh_notes": ["Strong trust-safe copy tests; not a evidence catalog"],
        },
        "csv_exports": {
            "tier": "OPERATIONAL_EXPORT",
            "harsh_notes": ["Semantically strong post phase-01; visually N/A"],
        },
    }
    return {"programme": PROGRAMME, "audited_at": _utc(), "ratings": ratings}


def governance_visibility() -> Dict[str, Any]:
    return {
        "programme": PROGRAMME,
        "audited_at": _utc(),
        "checks": [
            {
                "concept": "generated_timestamp",
                "evidence_readiness_pdf": "pass — UTC on cover + Snapshot generated at",
                "audit_pack": "pass — Generated at UTC + export_id",
                "jspdf_client": "partial — locale date only",
                "csv": "pass — Generated row",
            },
            {
                "concept": "snapshot_vs_live_disclosure",
                "evidence_readiness_pdf": "pass — body text warns point-in-time",
                "evidence_readiness_http": "pass — X-Report-Determinism live_regenerated",
                "jspdf": "fail — no disclosure",
            },
            {
                "concept": "assurance_tiers",
                "audit_pack": "pass — authority_state in pack JSON",
                "evidence_readiness_matrix": "fail — status label only",
                "requirements_csv": "partial — evidence_state column not assurance_tier",
            },
            {
                "concept": "estimated_vs_confirmed_dates",
                "score_drivers_csv": "pass — date_confidence column",
                "evidence_readiness_matrix": "fail — due date without confidence flag",
            },
            {
                "concept": "platform_review_pending",
                "requirements_page_ui": "pass — pending review hint",
                "exports": "partial — not in PDF matrix",
            },
            {
                "concept": "immutable_artifact_notice",
                "audit_pack_ui": "pass — ReportsAuditPackPage disclosure",
                "operational_zip_ui": "pass — OPERATIONAL_ZIP_DISCLOSURE",
            },
            {
                "concept": "report_grade",
                "api_available": "pass — export_grade on /reports/available",
                "jspdf_download": "fail — grade not embedded in PDF metadata",
            },
        ],
        "overstatement_risks": [
            "jspdf uses domain labels that may read as verified without assurance column",
            "COMPLIANT/VALID in matrix can imply regulator verification",
            "professional PDF property GREEN/AMBER/RED from DB without recalc footnote per row",
        ],
        "buried_risk_patterns": [
            "Silent truncation in evidence readiness property loop",
            "Missing items only in counts paragraph — no full unresolved index in PDF",
        ],
    }


def export_usability() -> Dict[str, Any]:
    return {
        "programme": PROGRAMME,
        "audited_at": _utc(),
        "personas": {
            "councils": {
                "best_artifact": "audit_evidence_pack_zip",
                "friction": "ZIP structure learning curve; strong manifest",
                "score": "B+",
            },
            "insurers_lenders": {
                "best_artifact": "audit_evidence_pack + professional compliance PDF",
                "friction": "jsPDF exports inadequate — must use governed pack",
                "score": "B",
            },
            "legal_review": {
                "best_artifact": "audit pack manifest + checksums",
                "friction": "evidence readiness re-download non-frozen",
                "score": "B",
            },
            "landlords_agencies": {
                "best_artifact": "professional PDF + evidence readiness",
                "friction": "dual PDF engines confusing",
                "score": "B-",
            },
            "executives": {
                "best_artifact": "score_explanation_pdf + monthly digest",
                "friction": "digest client re-render",
                "score": "B",
            },
            "support_teams": {
                "best_artifact": "csv + score drivers",
                "friction": "semantics preamble requires training",
                "score": "A-",
            },
        },
        "multi_property": "evidence readiness caps display; audit pack per-property scope",
        "csv_import": "utf-8-sig score drivers; comment preamble rows in compliance csv",
        "print": "reportlab adequate; jsPDF autotable may clip",
        "accessibility": "PDFs not tagged; tables not structured for screen readers",
        "low_tech_users": "jspdf familiar; ZIP pack needs guidance copy (present)",
    }


def template_convergence_plan() -> Dict[str, Any]:
    return {
        "programme": PROGRAMME,
        "audited_at": _utc(),
        "primitives_to_extract": [
            "ReportCoverBlock(title, scope, crn, generated_at_utc, logo_optional)",
            "GovernanceFooterBlock(disclaimer, generated_by, contact, report_grade)",
            "SnapshotFramingParagraph(determinism, score_status, last_calculated_at)",
            "MetadataTable(export_identity | score headline | semantics counts)",
            "BrandedTableStyle from professional_reports + pdf_report_builder unify",
            "RequirementRowPresentation(status, assurance_tier, date_confidence, lifecycle)",
        ],
        "do_not_migrate_yet": ["jsPDF → ReportLab (product decision)", "HTML-to-PDF"],
        "quick_wins_no_engine_swap": [
            "Shared footer constant across ReportLab builders",
            "Add assurance_tier + date_confidence columns to evidence readiness matrix",
            "Embed export_grade text in ReportLab cover metadata block",
            "Deprecate jsPDF for compliance_summary when reports_pdf (route to professional PDF)",
        ],
    }


def enterprise_gaps() -> Dict[str, Any]:
    gaps = [
        {"id": "no_frozen_evidence_readiness_bytes", "class": "regulator-risk", "severity": "operational"},
        {"id": "jspdf_not_white_label", "class": "operational", "severity": "operational"},
        {"id": "matrix_silent_truncation", "class": "scalability-risk", "severity": "regulator-risk"},
        {"id": "no_running_page_numbers_reportlab", "class": "cosmetic", "severity": "cosmetic"},
        {"id": "no_logo_on_cover", "class": "cosmetic", "severity": "operational"},
        {"id": "assurance_not_in_matrix", "class": "regulator-risk", "severity": "operational"},
        {"id": "no_evidence_chronology_section", "class": "operational", "severity": "operational"},
        {"id": "no_digital_signature", "class": "operational", "severity": "cosmetic"},
        {"id": "pdf_untagged_accessibility", "class": "operational", "severity": "cosmetic"},
        {"id": "large_table_page_split_headers", "class": "scalability-risk", "severity": "operational"},
    ]
    return {"programme": PROGRAMME, "audited_at": _utc(), "gaps": gaps}


def priority_roadmap() -> Dict[str, Any]:
    return {
        "programme": PROGRAMME,
        "audited_at": _utc(),
        "P0_trust_legal_governance": [
            "Route compliance/requirements PDF downloads to server ReportLab (retire jsPDF for external sharing)",
            "Add assurance_tier + date_confidence + lifecycle to evidence readiness matrix tables",
            "Explicit unresolved obligations index in CLIENT_PRESENTABLE PDFs",
            "Frozen PDF artifact option for evidence readiness (or disable re-download without warning banner)",
        ],
        "P1_enterprise_readability": [
            "Running headers/footers with page numbers on ReportLab exports",
            "Logo on cover via branding_resolver",
            "Portfolio truncation → appendix continuation pages with index",
            "Professional PDF property RAG footnote (persisted vs live)",
        ],
        "P2_template_consistency": [
            "Extract shared report_layout_v1 module for ReportLab builders",
            "Unify table styles between pdf_report_builder and professional_reports",
            "Monthly digest server-side PDF option",
        ],
        "P3_advanced": [
            "PDF/UA accessibility tags",
            "Digital signature / sealed manifest for audit packs",
            "Executive one-pager template",
        ],
    }


def run_regression() -> Dict[str, Any]:
    suites = [
        "tests/test_pdf_report_builder.py",
        "tests/test_reporting_semantics_v1.py",
        "tests/test_enterprise_presentation_governance.py",
    ]
    results = {}
    all_ok = True
    for s in suites:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", s, "-q", "--tb=no"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=180,
        )
        ok = proc.returncode == 0
        results[s] = {"passed": ok, "tail": (proc.stdout or proc.stderr)[-500:]}
        all_ok = all_ok and ok
    return {"all_passed": all_ok, "suites": results, "audited_at": _utc()}


def classify(regression: Dict[str, Any]) -> Dict[str, Any]:
    primary = "VERIFIED_OPERATIONALLY" if regression.get("all_passed") else "PARTIAL"
    gaps = ["PRESENTATION_GAP", "GOVERNANCE_VISIBILITY_GAP", "ENTERPRISE_DELIVERY_GAP"]
    if not regression.get("all_passed"):
        primary = "PARTIAL"
    return {
        "programme": PROGRAMME,
        "classified_at": _utc(),
        "classification": primary,
        "gap_classes": gaps,
        "summary": "Governance semantics are sound; presentation fragmentation (jsPDF vs ReportLab) and matrix assurance visibility are main enterprise blockers.",
    }


def main() -> int:
    _write("report_template_inventory_runtime.json", template_inventory())
    _write("presentation_quality_runtime.json", presentation_quality())
    _write("governance_visibility_runtime.json", governance_visibility())
    _write("export_usability_runtime.json", export_usability())
    _write("template_convergence_runtime.json", template_convergence_plan())
    _write("enterprise_gap_runtime.json", enterprise_gaps())
    _write("priority_roadmap_runtime.json", priority_roadmap())
    regression = run_regression()
    _write("regression_runtime.json", regression)
    classifications = classify(regression)
    _write("classifications.json", classifications)

    (OUT / "REPORT.md").write_text(
        f"""# {PROGRAMME}

Audited at: {_utc()}
Classification: **{classifications['classification']}**

## Executive summary
Reporting **governance correctness** from TRUTH-CONVERGENCE-PHASE-01 holds. **Enterprise presentation** is uneven: governed audit ZIP and ReportLab evidence/score PDFs are defensible; **client jsPDF** exports remain unsuitable for lenders/regulators; assurance and date-confidence are under-visible in matrix PDFs.

## Template inventory
{len(template_inventory()['templates'])} templates catalogued — see `report_template_inventory_runtime.json`.

## Presentation (harsh)
- **REGULATOR_READY:** audit evidence pack only
- **CLIENT_PRESENTABLE:** evidence readiness + professional ReportLab (with truncation/assurance caveats)
- **INTERNAL_OPERATIONAL_ONLY:** jsPDF compliance/requirements PDFs, admin hub

## Governance visibility
Snapshot/disclosure strong on server PDFs and API; **jspdf** lacks live/immutable and grade metadata.

## Priority
P0: server PDF for client downloads, matrix assurance columns, unresolved index. P1: page numbers, logo cover, truncation appendix.

## Regression
{'PASS' if regression.get('all_passed') else 'FAIL'}
""",
        encoding="utf-8",
    )
    (OUT / "watchlist.md").write_text(
        f"""# Watchlist — enterprise presentation ({_utc()[:10]})

## {classifications['classification']}

### P0
- [ ] Replace jsPDF compliance/requirements PDF with server ReportLab for external sharing
- [ ] Evidence readiness matrix: assurance_tier, date_confidence, lifecycle columns
- [ ] Unresolved obligations index in PDF exports

### P1
- [ ] ReportLab running footers + page numbers
- [ ] Branding logo on cover sheet
- [ ] Portfolio >20 properties: continuation appendix not silent truncation

### P2
- [ ] Shared report_layout_v1 primitives across ReportLab modules
""",
        encoding="utf-8",
    )
    print(f"{PROGRAMME} classification={classifications['classification']}")
    return 0 if classifications["classification"] == "VERIFIED_OPERATIONALLY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
