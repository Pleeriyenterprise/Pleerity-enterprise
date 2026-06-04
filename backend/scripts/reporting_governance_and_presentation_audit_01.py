#!/usr/bin/env python3
"""REPORTING-GOVERNANCE-AND-PRESENTATION-AUDIT-01 — evidence-based reporting audit (no redesign)."""
from __future__ import annotations

import csv
import io
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/audit/reporting_governance_and_presentation_audit_01"
API = os.getenv("STAGING_API", "https://pleerity-enterprise.onrender.com/api").rstrip("/")
FE = os.getenv("STAGING_FE", "https://pleerityenterprise.co.uk").rstrip("/")
PROGRAMME = "REPORTING-GOVERNANCE-AND-PRESENTATION-AUDIT-01"


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write(name: str, data: Any) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


def _client_creds() -> Tuple[str, str]:
    email = (os.getenv("STAGING_CLIENT_ADMIN_EMAIL") or "nancy@yopmail.com").strip()
    pw = (os.getenv("STAGING_CLIENT_ADMIN_PASSWORD") or "").strip()
    if not pw:
        for p in (
            ROOT / "docs/audit/ops_verify_01_6fd5ac4c_d35a58ae/.ops_verify_temp_pw.txt",
            ROOT / "docs/audit/ops_verify_01_6a614499_f1c7b5df_landlord_registration_ni/.ops_verify_temp_pw.txt",
        ):
            if p.is_file():
                pw = p.read_text(encoding="utf-8").strip()
                break
    if not pw:
        raise SystemExit("Set STAGING_CLIENT_ADMIN_PASSWORD or ops_verify temp pw file")
    return email, pw


def _login(email: str, password: str) -> Optional[str]:
    for _ in range(4):
        try:
            r = httpx.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=120)
            if r.status_code == 200:
                return r.json().get("access_token")
        except Exception:
            pass
    return None


def _hdr(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def build_report_inventory() -> Dict[str, Any]:
    surfaces = [
        {
            "id": "compliance_status_summary",
            "name": "Compliance Status Summary",
            "route_component": "ReportsPage → GET /api/reports/compliance-summary",
            "api_source": "routes/reports.py → reporting_service.generate_compliance_summary_report",
            "generation_method": "Server CSV stream or JSON pdf_data for client jsPDF",
            "sync_async": "sync",
            "formats": ["csv", "pdf_client_jsPDF"],
            "audience": "landlord, agency internal review",
            "authoritative_source": "requirements via filter_requirement_rows + compute_client_portal_requirement_stats; headline score via calculate_compliance_score; property RAG from DB field (may lag live dashboard)",
        },
        {
            "id": "requirements_report",
            "name": "Requirements Report",
            "route_component": "ReportsPage → GET /api/reports/requirements",
            "api_source": "reporting_service.generate_requirements_report",
            "generation_method": "Server CSV or JSON for jsPDF",
            "sync_async": "sync",
            "formats": ["csv", "pdf_client_jsPDF"],
            "audience": "internal compliance, advisers",
            "authoritative_source": "project_requirement_row_client_runtime + document linkage counts",
        },
        {
            "id": "evidence_readiness_pdf",
            "name": "Evidence Readiness Report",
            "route_component": "ReportsPage → POST /api/reports/generate",
            "api_source": "report_service.load_evidence_readiness_data + pdf_report_builder (ReportLab thread)",
            "generation_method": "ReportLab template (sync build in thread)",
            "sync_async": "sync_request_async_thread",
            "formats": ["pdf"],
            "audience": "portfolio review, lender prep (informational)",
            "authoritative_source": "authority_runtime_requirement_status + persisted property scores in matrix; re-download uses current data not snapshot",
        },
        {
            "id": "score_explanation_pdf",
            "name": "Compliance Score Summary (Informational) PDF",
            "route_component": "ComplianceScorePage → GET /api/reports/score-explanation.pdf",
            "api_source": "calculate_compliance_score + build_score_explanation_report",
            "generation_method": "ReportLab",
            "sync_async": "sync",
            "formats": ["pdf"],
            "audience": "client education, internal",
            "authoritative_source": "live calculate_compliance_score at export time",
        },
        {
            "id": "regulatory_system_export",
            "name": "Regulatory/System Export (Score Drivers CSV)",
            "route_component": "ReportsPage regulatory section → GET /api/reports/score-drivers.csv",
            "api_source": "calculate_compliance_score drivers",
            "generation_method": "CSV serializer sync",
            "sync_async": "sync",
            "formats": ["csv"],
            "audience": "external systems, analysts",
            "authoritative_source": "live score projection + driver rows; point-in-time comment rows",
        },
        {
            "id": "audit_evidence_pack_governed",
            "name": "Audit Evidence Pack (governed property ZIP)",
            "route_component": "ReportsAuditPackPage → POST /api/client/compliance/audit-pack/generate",
            "api_source": "compliance_audit_evidence_pack_service",
            "generation_method": "ZIP + ReportLab summary + GridFS; manifest checksums",
            "sync_async": "sync_build_store",
            "formats": ["zip"],
            "audience": "council, tribunal, insurer, audit",
            "authoritative_source": "classify_compliance_status + authority_state + verified docs on disk",
        },
        {
            "id": "evidence_pack_zip_legacy",
            "name": "Evidence Pack ZIP (CSVs + manifest, not governed audit pack)",
            "route_component": "ReportsPage → POST /api/client/evidence-pack/jobs",
            "api_source": "evidence_pack_service",
            "generation_method": "async job optional; GridFS ZIP",
            "sync_async": "async_job_or_sync",
            "formats": ["zip"],
            "audience": "data export; explicitly not legal audit pack",
            "authoritative_source": "filtered requirements + metadata CSVs; binary docs not in archive",
        },
        {
            "id": "professional_compliance_summary_pdf",
            "name": "Professional Compliance Summary PDF",
            "route_component": "GET /api/reports/professional/compliance-summary",
            "api_source": "professional_reports.generate_compliance_summary_pdf",
            "generation_method": "ReportLab branded",
            "sync_async": "sync",
            "formats": ["pdf"],
            "audience": "client-facing professional export",
            "authoritative_source": "reporting_service data + persisted score batch time labels",
        },
        {
            "id": "professional_expiry_schedule_pdf",
            "name": "Professional Expiry Schedule PDF",
            "route_component": "GET /api/reports/professional/expiry-schedule",
            "api_source": "professional_reports",
            "generation_method": "ReportLab",
            "sync_async": "sync",
            "formats": ["pdf"],
            "audience": "operations, renewals planning",
            "authoritative_source": "get_effective_expiry_date on filtered requirements",
        },
        {
            "id": "professional_audit_log_pdf",
            "name": "Professional Audit Log PDF",
            "route_component": "GET /api/reports/professional/audit-log",
            "api_source": "professional_reports + audit_logs collection",
            "generation_method": "ReportLab",
            "sync_async": "sync",
            "formats": ["pdf"],
            "audience": "professional plan audit trail",
            "authoritative_source": "audit_logs query (filtered)",
        },
        {
            "id": "scheduled_reports_email",
            "name": "Scheduled Reports (email CSV attachment)",
            "route_component": "ReportsPage schedules → jobs scheduled_reports",
            "api_source": "report_schedules + jobs.py notification SCHEDULED_REPORT",
            "generation_method": "CSV via reporting_service; email orchestrator",
            "sync_async": "async_cron",
            "formats": ["csv_email"],
            "audience": "configured recipients",
            "authoritative_source": "same as compliance_summary or requirements at job run time",
        },
        {
            "id": "monthly_digest",
            "name": "Monthly Compliance Digest",
            "route_component": "ReportsPage digests + job monthly_digest",
            "api_source": "monthly_digest_assembly_service",
            "generation_method": "email HTML + stored digest record; client jsPDF re-render",
            "sync_async": "async_monthly_job",
            "formats": ["email", "pdf_client_jsPDF"],
            "audience": "account owner",
            "authoritative_source": "persisted headline + assembly snapshot at send time",
        },
        {
            "id": "evidence_reminders_report",
            "name": "Evidence Reminders Report",
            "route_component": "NOT_FOUND — no dedicated report surface",
            "api_source": "daily_reminders job + COMPLIANCE_EXPIRY_REMINDER email template",
            "generation_method": "notification emails not export report",
            "sync_async": "async",
            "formats": ["email_only"],
            "audience": "account contacts",
            "authoritative_source": "reminder engine projection (semantic_state read contract target)",
            "note": "Listed in audit scope; implemented as notifications not downloadable report",
        },
        {
            "id": "dashboard_compliance_summary",
            "name": "Dashboard compliance summary (live UI)",
            "route_component": "ClientDashboard + GET /api/client/dashboard or compliance-score",
            "api_source": "calculate_compliance_score + portfolio summary",
            "generation_method": "live_render",
            "sync_async": "sync_api",
            "formats": ["live_ui"],
            "audience": "portal user",
            "authoritative_source": "mixed: persisted headline + live stats projection",
        },
        {
            "id": "requirements_page",
            "name": "Requirements list / stats",
            "route_component": "RequirementsPage → GET /api/client/requirements",
            "api_source": "client.py requirements list",
            "generation_method": "live_render",
            "sync_async": "sync",
            "formats": ["live_ui"],
            "audience": "portal user",
            "authoritative_source": "full tracked list; FE stats use lifecycle VERIFIED semantics",
        },
        {
            "id": "property_compliance_matrix",
            "name": "Property compliance matrix",
            "route_component": "Property page → GET /api/portfolio/properties/{id}/compliance-detail",
            "api_source": "catalog_compliance",
            "generation_method": "live_render",
            "sync_async": "sync",
            "formats": ["live_ui"],
            "audience": "portal user",
            "authoritative_source": "live matrix; preview_matrix_score non-authoritative",
        },
        {
            "id": "documents_tab",
            "name": "Documents tab exports",
            "route_component": "Documents UI — per-document download",
            "api_source": "document storage routes",
            "generation_method": "file_stream",
            "sync_async": "sync",
            "formats": ["binary"],
            "audience": "evidence holder",
            "authoritative_source": "stored document + verification state",
        },
        {
            "id": "operational_rent_expense_summary",
            "name": "Operational rent & expense summary",
            "route_component": "ReportsPage card → GET /api/client/operations/rent/summary",
            "api_source": "rent_ledger_service",
            "generation_method": "live_render on Reports (not PDF export)",
            "sync_async": "sync",
            "formats": ["live_ui"],
            "audience": "landlord operations",
            "authoritative_source": "rent ledger operational cache — not compliance score",
        },
        {
            "id": "admin_reports_hub",
            "name": "Admin Reports Hub",
            "route_component": "Admin → /api/admin/reports/*",
            "api_source": "routes/reporting.py",
            "generation_method": "CSV/JSON/PDF/XLSX ReportLab openpyxl",
            "sync_async": "sync + scheduled admin jobs",
            "formats": ["csv", "json", "pdf", "xlsx"],
            "audience": "internal staff",
            "authoritative_source": "per report_type (revenue, orders, compliance, etc.)",
        },
        {
            "id": "admin_audit_log_extract",
            "name": "Admin Audit Log Extract",
            "route_component": "GET /api/reports/audit-logs (admin)",
            "api_source": "reporting_service.generate_audit_log_report",
            "generation_method": "CSV or JSON for jsPDF",
            "sync_async": "sync",
            "formats": ["csv", "pdf_client_jsPDF"],
            "audience": "ROLE_ADMIN",
            "authoritative_source": "audit_logs collection",
        },
        {
            "id": "admin_score_ledger_csv",
            "name": "Admin score ledger export",
            "route_component": "GET /api/admin/ledger/export.csv",
            "api_source": "score_ledger_service",
            "generation_method": "CSV",
            "sync_async": "sync",
            "formats": ["csv"],
            "audience": "admin diagnostics",
            "authoritative_source": "score_change_log / ledger persistence",
        },
        {
            "id": "compliance_matrix_export_implicit",
            "name": "Compliance matrix in Evidence Readiness / audit pack",
            "route_component": "embedded in PDF/ZIP exports",
            "api_source": "pdf_report_builder / audit pack JSON sections",
            "generation_method": "embedded tables",
            "sync_async": "with parent export",
            "formats": ["pdf", "zip_json"],
            "audience": "varies",
            "authoritative_source": "requirement rows at export time — not catalog_matrix preview from portfolio API",
        },
        {
            "id": "portal_analytics_summary",
            "name": "Portal activity summary (Reports card)",
            "route_component": "ReportsPage analytics card",
            "api_source": "portal analytics aggregation",
            "generation_method": "live_render",
            "sync_async": "sync",
            "formats": ["live_ui"],
            "audience": "account owner",
            "authoritative_source": "first-party event counters — not compliance truth",
        },
    ]
    return {
        "programme": PROGRAMME,
        "audited_at": _utc(),
        "surface_count": len(surfaces),
        "surfaces": surfaces,
        "hidden_or_admin": [
            "admin_reports_hub",
            "admin_audit_log_extract",
            "admin_score_ledger_csv",
            "admin audit-pack download /api/admin/compliance/audit-packs",
        ],
    }


def build_source_of_truth() -> Dict[str, Any]:
    return {
        "programme": PROGRAMME,
        "audited_at": _utc(),
        "authoritative_layers": {
            "live_requirement_lifecycle": {
                "modules": [
                    "requirement_client_runtime_surface",
                    "requirement_evidence_authority",
                    "requirement_truth",
                ],
                "used_by": ["requirements page", "matrix", "audit pack", "evidence readiness loader"],
            },
            "persisted_score_snapshot": {
                "fields": ["compliance_score", "compliance_breakdown", "compliance_last_calculated_at", "compliance_score_pending"],
                "used_by": ["dashboard headline", "score explanation PDF buckets", "professional PDF headline labels"],
            },
            "live_score_projection": {
                "module": "compliance_score.calculate_compliance_score",
                "used_by": ["dashboard stats", "score drivers CSV", "compliance summary headline block"],
            },
            "non_authoritative": [
                "catalog_matrix_portfolio_preview",
                "preview_matrix_score on compliance-detail",
                "legacy_matrix_portfolio_preview",
            ],
        },
        "per_report": {
            "compliance_status_summary": {
                "authoritative_fields": ["portal_req stats", "compliance_score_headline from calculate_compliance_score"],
                "non_authoritative": ["property.compliance_status from DB without live recompute in report"],
                "stale_risk": "medium — property RAG in CSV may differ from dashboard live RAG",
                "duplicated_logic": "compute_client_portal_requirement_stats shared with dashboard stats path but FE Requirements page uses different valid definition",
                "report_only_forks": ["jsPDF client layout separate from server professional PDF"],
            },
            "requirements_report": {
                "authoritative_fields": ["project_requirement_row_client_runtime status/evidence_state"],
                "stale_risk": "low at generation instant",
                "duplicated_logic": "document count from requirements query not evidence_authority primary record only",
            },
            "evidence_readiness_pdf": {
                "authoritative_fields": ["authority_runtime_requirement_status", "persisted compliance_score on property"],
                "stale_risk": "high on re-download — metadata score_at_time stored but PDF rebuilt from live data",
                "report_only_forks": ["_derive_counts uses get_computed_status not identical to portal stats"],
            },
            "score_drivers_csv": {
                "authoritative_fields": ["drivers from calculate_compliance_score"],
                "stale_risk": "low — explicit export_snapshot_generated_at comments",
            },
            "audit_evidence_pack": {
                "authoritative_fields": ["classify_compliance_status", "checksum manifest", "verified file bytes"],
                "stale_risk": "low post-generation — immutable GridFS artifact",
                "governance": "strongest export path for legal defensibility",
            },
            "scheduled_email_csv": {
                "stale_risk": "medium — async delay up to next cron window",
            },
        },
        "truth_divergence_summary": "Reporting mixes three lenses: (1) persisted portfolio/property scores, (2) live portal projection stats/drivers, (3) DB property RAG without always recomputing. Dashboard Requirements count semantics already documented as COUNT_CONVERGENCE_DRIFT vs Requirements page.",
    }


def build_propagation_matrix() -> Dict[str, Any]:
    actions = {
        "A_upload_document_evidence": {
            "expected_affected": ["requirements_report", "evidence_readiness_pdf", "audit_pack_next_generation", "matrix", "dashboard_stats_after_recalc"],
            "latency": "immediate in DB; score drivers after recalc enqueue (seconds–minutes)",
            "sync_async": "write sync; score async via compliance_recalc_worker",
            "stale_window": "until recalc completes — exports taken mid-flight show old score headline",
            "verification_mode": "code_trace + read_only_staging_snapshot",
        },
        "B_structured_declaration": {
            "expected_affected": ["requirements_report evidence_state", "matrix presentation fields", "audit pack governance summary"],
            "latency": "immediate row update; score may lag",
            "sync_async": "sync truth update; async score",
        },
        "C_platform_review_pending": {
            "expected_affected": ["requirements_report", "matrix", "score drivers next_step_label"],
            "missing_risk": "older exports label Upload when portal shows review pending",
        },
        "D_verified_document": {
            "expected_affected": ["all compliance exports", "audit pack includes file", "score after recalc"],
            "latency": "document immediate; score async",
        },
        "E_rejected_evidence": {
            "expected_affected": ["requirements_report latest_doc_status", "matrix", "drivers"],
            "contradiction_risk": "CSV may still list rejected doc as latest_document if last in array",
        },
        "F_requirement_satisfaction_convergence": {
            "expected_affected": ["stats compliant count", "matrix requirement_satisfied fields", "audit pack status"],
            "latency": "immediate on row; dashboard widget uses different compliant definition than requirements page",
        },
        "G_expiry_date_update": {
            "expected_affected": ["expiry schedule PDF", "compliance summary expiring_* counts", "drivers date_used"],
            "latency": "immediate effective expiry in projection",
        },
        "H_property_score_recalculation": {
            "expected_affected": ["persisted headline", "professional PDF batch time", "evidence readiness property score"],
            "latency": "worker queue SLA (verified <60s typical in prior audit)",
            "stale_window": "compliance_score_pending / calculating states",
        },
        "I_portfolio_score_recalculation": {
            "expected_affected": ["dashboard headline", "compliance summary headline block", "score explanation PDF"],
            "latency": "after all property recalcs + aggregate",
        },
        "J_requirement_not_applicable": {
            "expected_affected": ["filtered out of portal_reqs — drops from reports using filter_requirement_rows"],
            "latency": "immediate filter on next export",
        },
    }
    return {
        "programme": PROGRAMME,
        "audited_at": _utc(),
        "note": "Mutation flows not executed on staging in this audit run (read-only). Propagation expectations traced from services and prior convergence audits.",
        "actions": actions,
        "missing_propagation_watchlist": [
            "Evidence Readiness re-download does not replay historical snapshot",
            "Scheduled report email may attach CSV generated before overnight recalc",
            "Client jsPDF compliance PDF uses download-time JSON not immutable artifact",
        ],
    }


def build_export_engine() -> Dict[str, Any]:
    return {
        "programme": PROGRAMME,
        "audited_at": _utc(),
        "engines": {
            "reportlab_server": {
                "modules": ["pdf_report_builder", "professional_reports", "compliance_audit_evidence_pack_service", "report_service legacy path"],
                "html_to_pdf": False,
                "deterministic": "template-only, no AI",
            },
            "jspdf_client": {
                "modules": ["ReportsPage.generatePDF", "ReportsPage.downloadDigestPdf"],
                "risk": "second layout engine — formatting divergence from server PDFs",
            },
            "csv_serializer": {
                "modules": ["reporting_service", "reports.score_drivers", "routes/reporting.py openpyxl"],
            },
            "zip_governed": {
                "module": "compliance_audit_evidence_pack_service",
                "features": ["manifest", "sha256", "GridFS retention", "export_identity block"],
            },
        },
        "scalability": {
            "large_portfolio": "requirements to_list(10000) — memory bound",
            "large_evidence_pack": "disk read per verified doc — property-scoped mitigates",
            "pagination": "ReportLab tables without automatic row pagination controls in all builders",
            "multi_property": "supported; portfolio evidence readiness aggregates all properties in scope",
        },
        "determinism": "audit pack deterministic; evidence readiness re-fetch non-deterministic across time",
        "branding": "branding_resolver_service for client PDFs",
    }


def build_scalability_governance() -> Dict[str, Any]:
    return {
        "programme": PROGRAMME,
        "audited_at": _utc(),
        "rate_limits": {
            "report_export_per_client_per_hour": "security_limits.report_export_per_client_per_hour via _enforce_report_export_rate",
            "evidence_pack_jobs": "5 per client per 24h",
            "admin_export": "admin_export_per_staff_per_hour",
        },
        "caching": "No report result CDN cache; compliance_score may serve cached calculate path internally",
        "snapshot_versioning": {
            "evidence_readiness": "reports collection stores score_at_time but download regenerates live",
            "audit_pack": "immutable pack_id + GridFS",
            "monthly_digest": "stored digest document per period",
        },
        "audit_traceability": "create_audit_log on exports; REPORT_EXPORTED / ADMIN_ACTION",
        "retention": "GridFS audit packs; report metadata list limit 100",
        "signed_urls": "not used for client report downloads — bearer auth streaming",
        "tenant_isolation": "client_id on all queries",
        "async_governance": {
            "scheduled_reports": "plan_registry scheduled_reports + BLOCKED_PLAN message_logs",
            "monthly_digest": "billing block may disable background jobs",
        },
        "risks": [
            {"risk": "REPORT_TRUTH_DRIFT", "detail": "Re-download Evidence Readiness PDF with new data while filename implies historical run"},
            {"risk": "GOVERNANCE_GAP", "detail": "Dual evidence pack products with different defensibility"},
            {"risk": "SCALABILITY_GAP", "detail": "10k requirement load per sync export"},
            {"risk": "LEGAL_DEFENSIBILITY", "detail": "Client jsPDF reports lack checksum manifest"},
        ],
    }


def build_presentation_tiers() -> Dict[str, Any]:
    tiers = {
        "INTERNAL_OPERATIONAL_ONLY": [
            "portal_analytics_summary",
            "operational_rent_expense_summary",
            "admin_score_ledger_csv",
            "score_drivers_csv",
        ],
        "CLIENT_PRESENTABLE": [
            "compliance_status_summary",
            "requirements_report",
            "professional_compliance_summary_pdf",
            "professional_expiry_schedule_pdf",
            "monthly_digest",
            "evidence_readiness_pdf",
        ],
        "REGULATOR_READY": ["audit_evidence_pack_governed"],
        "AUDIT_READY": ["audit_evidence_pack_governed", "professional_audit_log_pdf"],
        "INVESTOR_READY": [],
    }
    critiques = {
        "audit_evidence_pack_governed": {
            "structure": "strong — manifest, sections, checksums",
            "governance_clarity": "export_identity, rules versions, jurisdiction notice",
            "operational_trust": "highest — challengeable via manifest",
            "delivery": "ZIP not print-ready PDF alone",
        },
        "evidence_readiness_pdf": {
            "structure": "adequate sections; methodology present",
            "governance_clarity": "disclaimer + generated-by; score batch labeling improved",
            "gaps": ["re-download drift", "matrix counts may diverge from dashboard"],
            "delivery": "PDF print-ok; weak for regulator without pack",
        },
        "compliance_status_summary_client_pdf": {
            "structure": "jsPDF autoTable — basic",
            "governance_clarity": "weaker than server professional PDF",
            "delivery": "acceptable internal only",
        },
        "regulatory_system_export": {
            "delivery": "CSV usable; requires scoring_metadata literacy",
            "governance_clarity": "good comment/header contract when scoring_metadata=true",
        },
    }
    return {
        "programme": PROGRAMME,
        "audited_at": _utc(),
        "tiers": tiers,
        "critiques": critiques,
        "strict_summary": "Only governed Audit Evidence Pack meets REGULATOR_READY/AUDIT_READY bar. Client jsPDF and legacy evidence ZIP must not be marketed as tribunal-ready.",
    }


def _parse_csv_summary(text: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for line in text.splitlines():
        if line.startswith("Total Requirements,"):
            out["total_requirements"] = int(line.split(",", 1)[1])
        if line.startswith("Compliant,") and "===" not in line:
            try:
                out["compliant"] = int(line.split(",", 1)[1])
            except ValueError:
                pass
    return out


def staging_consistency_probe(token: str) -> Dict[str, Any]:
    h = _hdr(token)
    probes: Dict[str, Any] = {"audited_at": _utc(), "api": API}
    try:
        cs = httpx.get(f"{API}/client/compliance-score", headers=h, timeout=120)
        probes["compliance_score_status"] = cs.status_code
        if cs.status_code == 200:
            j = cs.json()
            probes["dashboard_stats"] = {
                "total_requirements": j.get("stats", {}).get("total_requirements"),
                "compliant": j.get("stats", {}).get("compliant"),
                "overdue": j.get("stats", {}).get("overdue"),
                "expiring_soon": j.get("stats", {}).get("expiring_soon"),
                "headline_score": j.get("score"),
                "score_status": j.get("score_status"),
            }
    except Exception as e:
        probes["compliance_score_error"] = str(e)

    try:
        req = httpx.get(f"{API}/client/requirements", headers=h, timeout=120)
        probes["requirements_status"] = req.status_code
        if req.status_code == 200:
            rows = req.json().get("requirements") or []
            tracked = [r for r in rows if str(r.get("applicability", "")).upper() != "NOT_REQUIRED"]
            verified = sum(
                1
                for r in tracked
                if str(r.get("lifecycle_state") or r.get("semantic_state") or "").upper()
                in ("VERIFIED", "SATISFIED_UNVERIFIED")
            )
            probes["requirements_page_stats"] = {
                "tracked_count": len(tracked),
                "lifecycle_valid_like": verified,
            }
    except Exception as e:
        probes["requirements_error"] = str(e)

    try:
        rpt = httpx.get(
            f"{API}/reports/compliance-summary",
            headers=h,
            params={"format": "csv"},
            timeout=120,
        )
        probes["compliance_summary_csv_status"] = rpt.status_code
        if rpt.status_code == 200:
            probes["compliance_summary_csv"] = _parse_csv_summary(rpt.text)
        elif rpt.status_code == 403:
            probes["compliance_summary_csv"] = {"gated": True}
    except Exception as e:
        probes["compliance_summary_error"] = str(e)

    try:
        rr = httpx.get(f"{API}/reports/requirements", headers=h, params={"format": "csv"}, timeout=120)
        if rr.status_code == 200:
            m = re.search(r"Total Requirements:\s*(\d+)", rr.text)
            probes["requirements_report_csv_count"] = int(m.group(1)) if m else None
        elif rr.status_code == 403:
            probes["requirements_report_csv_count"] = {"gated": True}
    except Exception as e:
        probes["requirements_report_error"] = str(e)

    ds = probes.get("dashboard_stats") or {}
    cs_csv = probes.get("compliance_summary_csv") or {}
    rp = probes.get("requirements_page_stats") or {}
    align = {}
    if ds and cs_csv and not cs_csv.get("gated"):
        align["dashboard_vs_compliance_summary_total"] = ds.get("total_requirements") == cs_csv.get("total_requirements")
        align["dashboard_vs_compliance_summary_compliant"] = ds.get("compliant") == cs_csv.get("compliant")
    if ds and rp:
        align["dashboard_total_vs_requirements_page_tracked"] = ds.get("total_requirements") == rp.get("tracked_count")
        align["dashboard_compliant_vs_requirements_lifecycle"] = ds.get("compliant") == rp.get("lifecycle_valid_like")
    probes["alignment_checks"] = align
    probes["count_drift_detected"] = any(v is False for v in align.values())
    return probes


def classify_all(
    consistency: Dict[str, Any],
    inventory: Dict[str, Any],
) -> Dict[str, Any]:
    gaps: List[Dict[str, str]] = []
    if consistency.get("count_drift_detected"):
        gaps.append({"class": "REPORT_TRUTH_DRIFT", "severity": "operational", "detail": "Dashboard/compliance-summary/requirements-page count semantics diverge"})
    gaps.append({"class": "REPORT_TRUTH_DRIFT", "severity": "operational", "detail": "Evidence Readiness re-download regenerates from live DB; score_at_time metadata not bound into PDF body"})
    gaps.append({"class": "EXPORT_ENGINE_GAP", "severity": "operational", "detail": "Parallel PDF engines (ReportLab vs jsPDF) with inconsistent governance metadata"})
    gaps.append({"class": "GOVERNANCE_GAP", "severity": "operational", "detail": "Two evidence pack products — only audit-pack/generate is governed for regulators"})
    gaps.append({"class": "PRESENTATION_GAP", "severity": "cosmetic", "detail": "Client jsPDF compliance reports lack manifest/checksum and weaker typography than professional ReportLab"})
    gaps.append({"class": "SCALABILITY_GAP", "severity": "operational", "detail": "Sync 10k requirement exports and unbounded audit log extract default limit 1000"})
    gaps.append({"class": "NO_MATERIAL_GAP", "severity": "info", "detail": "Audit evidence pack service v2 contract, score drivers export snapshot headers, rate limits present"})

    primary = "REPORT_TRUTH_DRIFT" if consistency.get("count_drift_detected") else "GOVERNANCE_GAP"
    return {
        "programme": PROGRAMME,
        "classified_at": _utc(),
        "primary_classification": primary,
        "gaps": gaps,
        "cosmetic_vs_dangerous": {
            "cosmetic": [g for g in gaps if g.get("severity") == "cosmetic"],
            "operational": [g for g in gaps if g.get("severity") == "operational"],
        },
        "surface_count": inventory.get("surface_count"),
    }


def run_regression() -> Dict[str, Any]:
    suites = [
        "tests/test_reporting_compliance_export_snapshot.py",
        "tests/test_reporting.py",
    ]
    results = {}
    all_ok = True
    for suite in suites:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", suite, "-q"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=300,
        )
        ok = proc.returncode == 0
        results[suite] = {"passed": ok}
        all_ok = all_ok and ok
    return {"all_passed": all_ok, "suites": results}


def write_report_md(
    classifications: Dict[str, Any],
    consistency: Dict[str, Any],
    regression: Dict[str, Any],
) -> None:
    body = f"""# {PROGRAMME}

Audited at: {_utc()}
Primary classification: **{classifications.get('primary_classification')}**

## 1. Reporting architecture
Multiple export lanes coexist: server ReportLab PDFs, client jsPDF renders, CSV serializers, governed audit ZIP (GridFS), and admin openpyxl hub. Inventory: `{classifications.get('surface_count')}` surfaces in `report_inventory_runtime.json`.

## 2. Operational truth convergence
Reports draw from **three lenses**: persisted property/portfolio scores, live `calculate_compliance_score` projection, and raw DB fields (e.g. property `compliance_status`). Compliance summary CSV aligns portal stats when gated access succeeds; Requirements **page** uses lifecycle semantics that differ from dashboard **compliant** count (known drift).

## 3. Propagation
Lifecycle/evidence changes propagate immediately to requirement rows; **score headline** and **scheduled email** exports lag async recalc. Evidence Readiness **re-download** is not a point-in-time artifact. Details: `propagation_runtime.json`.

## 4. Consistency (staging read-only)
```
{json.dumps(consistency.get('alignment_checks', {}), indent=2)}
```
Count drift detected: **{consistency.get('count_drift_detected')}**

## 5. Presentation quality
Only **governed Audit Evidence Pack** is REGULATOR_READY / AUDIT_READY. Other PDFs are CLIENT_PRESENTABLE or INTERNAL_OPERATIONAL_ONLY. See `presentation_runtime.json`.

## 6. Export engine
ReportLab template PDFs (deterministic) + jsPDF client branch + CSV/ZIP. No HTML-to-PDF. See `export_engine_runtime.json`.

## 7. Governance / scalability
Rate limits on exports; audit pack immutable; weak snapshot binding on evidence readiness list/download. See `scalability_governance_runtime.json`.

## 8. Classification summary
{json.dumps([g['class'] for g in classifications.get('gaps', [])], indent=2)}

## Regression
{'PASS' if regression.get('all_passed') else 'FAIL'}

## Recommended next priorities (no redesign in this audit)
1. Bind Evidence Readiness download to stored snapshot or label re-download as "current data as of {now}".
2. Unify compliant/requirement count semantics across dashboard, compliance summary CSV, and Requirements page.
3. Recompute property RAG in compliance summary export (match dashboard) or label CSV RAG as persisted DB.
4. Deprecate or relabel legacy evidence-pack ZIP vs governed audit pack in UI copy only after product sign-off.
5. Consolidate PDF generation to server ReportLab for client-facing professional exports.
"""
    (OUT / "REPORT.md").write_text(body, encoding="utf-8")

    watchlist = f"""# Watchlist — reporting governance ({_utc()[:10]})

## Primary: {classifications.get('primary_classification')}

- [ ] Evidence Readiness `GET /reports/{{id}}/download` regenerates live data — legal/challenge risk
- [ ] Dashboard stats vs Requirements page lifecycle counts (see dashboard_score_widget_semantic_convergence_01)
- [ ] Compliance summary CSV property `compliance_status` from DB vs live dashboard RAG
- [ ] jsPDF vs ReportLab dual engine — formatting and metadata divergence
- [ ] Legacy `evidence-pack/jobs` ZIP not equivalent to `audit-pack/generate`
- [ ] Evidence Reminders: no report surface — email-only (document in product matrix)
- [ ] Scheduled report CSV attachment timing vs overnight recalc

## Safe / strong paths
- Governed audit evidence pack v2 (manifest + checksums + GridFS)
- Score drivers CSV snapshot header contract
"""
    (OUT / "watchlist.md").write_text(watchlist, encoding="utf-8")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    inventory = build_report_inventory()
    _write("report_inventory_runtime.json", inventory)
    _write("source_of_truth_runtime.json", build_source_of_truth())
    _write("propagation_runtime.json", build_propagation_matrix())
    _write("export_engine_runtime.json", build_export_engine())
    _write("presentation_runtime.json", build_presentation_tiers())
    _write("scalability_governance_runtime.json", build_scalability_governance())

    consistency_path = OUT / "consistency_runtime.json"
    if consistency_path.is_file() and os.getenv("AUDIT_SKIP_STAGING") == "1":
        consistency = json.loads(consistency_path.read_text(encoding="utf-8"))
    else:
        email, pw = _client_creds()
        token = _login(email, pw)
        consistency = {"login": bool(token), "note": "read_only_probe"}
        if token:
            consistency = staging_consistency_probe(token)
        _write("consistency_runtime.json", consistency)

    if os.getenv("AUDIT_SKIP_REGRESSION") == "1":
        regression = {
            "all_passed": None,
            "note": "skipped AUDIT_SKIP_REGRESSION=1",
            "suites": {},
        }
    else:
        regression = run_regression()
    _write("regression_runtime.json", regression)
    classifications = classify_all(consistency, inventory)
    _write("classifications.json", classifications)
    write_report_md(classifications, consistency, regression)

    print(f"{PROGRAMME} primary={classifications.get('primary_classification')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
