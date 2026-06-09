#!/usr/bin/env python3
"""Evidence Readiness operational PDF presentation verification."""
from __future__ import annotations

import io
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import reportlab.rl_config

reportlab.rl_config.pageCompression = 0

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "docs/audit/evidence_readiness_operational_presentation"
RUN_TAG = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

TELEMETRY_NOISE = (
    "COMPLIANCE_RECALC_SLA_BREACH",
    "RISK_SIGNAL_REGEN_COMPLETED",
    "HEARTBEAT_",
    "EVENT_",
)

PRESENTATION_MARKERS = {
    "operational_matrix": "operational evidence matrix",
    "metadata_appendix": "reference metadata appendix",
    "remediation": "recommended remediation actions",
    "audit_chronology": "operational activity chronology",
    "readiness_indicators": "audit readiness indicators",
    "frozen_snapshot_once": "frozen deterministic snapshot",
    "compact_footer_live": "point-in-time export",
    "compact_footer_frozen": "frozen snapshot export",
}

RAW_TELEMETRY_IN_BODY = re.compile(
    r"\b(COMPLIANCE_RECALC_SLA_BREACH|RISK_SIGNAL_REGEN_|HEARTBEAT_|_[A-Z]{3,}_[A-Z]{3,})\b"
)


def _branding() -> dict:
    return {"primary_color": "#0B1D3A", "secondary_color": "#00B8A9", "company_name": "Presentation Verify Ltd"}


def _client() -> dict:
    return {
        "company_name": "Presentation Verify Ltd",
        "customer_reference": "CRN-PRES-001",
        "effective_jurisdiction_label": "England",
    }


def _prop(pid: str = "p1", **kw) -> dict:
    base = {
        "property_id": pid,
        "address_line_1": "123 Very Long Street Name For Overflow Testing, London",
        "city": "London",
        "postcode": "E1 1AA",
        "compliance_score": 68,
        "risk_level": "Medium",
        "compliance_last_calculated_at": "2026-05-01T10:00:00+00:00",
    }
    base.update(kw)
    return base


def _req(i: int, pid: str = "p1", **kw) -> dict:
    statuses = ["COMPLIANT", "OVERDUE", "EXPIRING_SOON", "MISSING", "PENDING", "VALID"]
    types = ["gas_safety", "eicr", "epc", "fire_alarm", "legionella", "right_to_rent"]
    base = {
        "requirement_id": f"r{i}",
        "property_id": pid,
        "client_id": "c1",
        "requirement_type": types[i % len(types)],
        "requirement_code": types[i % len(types)][:4].upper(),
        "description": f"Obligation {i} — {types[i % len(types)].replace('_', ' ').title()} compliance requirement",
        "status": statuses[i % len(statuses)],
        "mandatory": i % 3 != 2,
        "due_date": f"2026-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}",
        "evidence_authority": {"version": 1, "state": "VERIFIED_CURRENT" if i % 4 == 0 else "MISSING"},
    }
    base.update(kw)
    return base


def _audit_log(i: int, action: str | None = None) -> dict:
    actions = [
        "DOCUMENT_UPLOADED",
        "DOCUMENT_VERIFIED",
        "COMPLIANCE_RECALC_SLA_BREACH",
        "RISK_SIGNAL_REGEN_COMPLETED",
        "REQUIREMENT_STATUS_CHANGED",
        "TENANT_DELIVERY_PROOF_RECORDED",
        "COMPLIANCE_SCORE_RECALCULATED",
    ]
    act = action or actions[i % len(actions)]
    return {
        "timestamp": f"2026-06-{(i % 28) + 1:02d}T{(i % 24):02d}:00:00+00:00",
        "action": act,
        "actor_role": "ROLE_CLIENT" if i % 2 == 0 else "system",
        "resource_id": f"r{i % 12}",
        "metadata": {"summary": f"Operational event {i}", "requirement_id": f"r{i % 12}"},
    }


def _extract_pdf(pdf_bytes: bytes) -> dict:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(pdf_bytes))
    pages = []
    full = []
    for i, page in enumerate(reader.pages):
        text = (page.extract_text() or "").strip()
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        pages.append({"page": i + 1, "chars": len(text), "lines": len(lines), "preview": text[:200]})
        full.append(text)
    joined = "\n".join(full)
    low = joined.lower()
    return {
        "page_count": len(reader.pages),
        "bytes": len(pdf_bytes),
        "valid_pdf": pdf_bytes[:4] == b"%PDF",
        "pages": pages,
        "full_text_lower": low,
        "markers": {k: v in low for k, v in PRESENTATION_MARKERS.items()},
    }


def _inspect_presentation(label: str, pdf_bytes: bytes) -> dict:
    info = _extract_pdf(pdf_bytes)
    low = info["full_text_lower"]
    issues: List[str] = []

    # Required sections for property/portfolio operational reports
    for key in ("operational_matrix", "remediation", "readiness_indicators"):
        if not info["markers"].get(key):
            issues.append(f"missing_section:{key}")

    # 6-column matrix headers
    matrix_headers = ["obligation", "status", "evidence", "expiry", "risk", "action required"]
    if not all(h in low for h in matrix_headers):
        issues.append("matrix_headers_incomplete")

    # Raw telemetry should not appear in body (humanised labels expected)
    from pypdf import PdfReader as PR

    full_text = "\n".join((p.extract_text() or "") for p in PR(io.BytesIO(pdf_bytes)).pages)
    for tok in TELEMETRY_NOISE:
        if tok in full_text:
            issues.append(f"raw_telemetry_leak:{tok}")

    # Footer repetition: full frozen wording should appear limited times
    frozen_count = low.count("this report is a frozen deterministic snapshot")
    if frozen_count > 2:
        issues.append(f"frozen_wording_repeated:{frozen_count}x")

    # Compact footer vs long frozen on every page footer band
    footer_frozen_snippets = low.count("generation timestamp boundary")
    if footer_frozen_snippets > 3:
        issues.append(f"footer_boundary_repeated:{footer_frozen_snippets}x")

    # Orphan / sparse page heuristics
    for p in info["pages"]:
        if p["page"] > 1 and p["chars"] < 120 and p["lines"] <= 4:
            issues.append(f"sparse_page_{p['page']}_chars_{p['chars']}")
        if p["chars"] < 100 and any("scope and limitations" in p["preview"].lower() for _ in [1]):
            if len(p["preview"]) < 150:
                issues.append(f"possible_footer_only_page_{p['page']}")

    # Audit chronology human labels when logs present
    if info["markers"].get("audit_chronology"):
        human_ok = any(
            phrase in low
            for phrase in (
                "evidence lifecycle",
                "compliance document uploaded",
                "risk assessment",
                "compliance scoring",
            )
        )
        if not human_ok:
            issues.append("audit_chronology_missing_human_labels")

    # Metadata appendix when matrix present
    if info["markers"].get("operational_matrix") and "reference metadata appendix" not in low:
        issues.append("metadata_appendix_missing")

    # Remediation priority blocks
    if info["markers"].get("remediation"):
        if "priority 1" not in low and "no immediate remediation" not in low:
            issues.append("remediation_priorities_unclear")

    return {
        "scenario": label,
        "pdf_info": {k: v for k, v in info.items() if k != "full_text_lower"},
        "markers": info["markers"],
        "issues": issues,
        "pass": not issues,
    }


def _build_scenarios() -> Dict[str, bytes]:
    from services.pdf_report_builder import build_portfolio_report, build_property_report

    now_iso = "2026-06-09T12:00:00+00:00"
    branding = _branding()
    client = _client()
    pdfs: Dict[str, bytes] = {}

    # 1. Property 12 mixed statuses
    reqs_12 = [_req(i) for i in range(12)]
    pdfs["mixed_12_property"] = build_property_report(
        "c1",
        "p1",
        {
            "client": client,
            "properties": [_prop()],
            "requirements": reqs_12,
            "audit_logs": [_audit_log(i) for i in range(8)],
            "now_iso": now_iso,
            "branding": branding,
        },
    )

    # 2. Sparse 1 requirement
    pdfs["sparse_1_property"] = build_property_report(
        "c1",
        "p1",
        {
            "client": client,
            "properties": [_prop(compliance_score=55)],
            "requirements": [_req(0, description="Single gas safety certificate requirement")],
            "audit_logs": [],
            "now_iso": now_iso,
            "branding": branding,
        },
    )

    # 3. Portfolio 75+ obligations (15 properties x 5 reqs)
    props = [_prop(f"p{i}", address_line_1=f"{100 + i} Portfolio Street Block {i}") for i in range(15)]
    reqs_75 = [_req(i, pid=f"p{i // 5}") for i in range(75)]
    pdfs["portfolio_75_plus"] = build_portfolio_report(
        "c1",
        {
            "client": client,
            "properties": props,
            "requirements": reqs_75,
            "audit_logs": [_audit_log(i) for i in range(15)],
            "now_iso": now_iso,
            "branding": branding,
        },
    )

    # 4. Long obligation names
    long_name = (
        "HMO fire safety management plan and emergency lighting certificate including communal areas "
        "and annual professional review documentation"
    )
    pdfs["long_obligation_names"] = build_property_report(
        "c1",
        "p1",
        {
            "client": client,
            "properties": [_prop()],
            "requirements": [
                _req(0, description=long_name),
                _req(1, description=long_name + " — duplicate row for wrap stress"),
            ]
            + [_req(i) for i in range(2, 6)],
            "audit_logs": [_audit_log(0)],
            "now_iso": now_iso,
            "branding": branding,
        },
    )

    # 5. Large audit log volume
    pdfs["large_audit_log"] = build_property_report(
        "c1",
        "p1",
        {
            "client": client,
            "properties": [_prop()],
            "requirements": [_req(i) for i in range(8)],
            "audit_logs": [_audit_log(i) for i in range(120)],
            "now_iso": now_iso,
            "branding": branding,
        },
    )

    return pdfs


def _verify_audit_pack_unchanged() -> dict:
    """Confirm audit evidence pack still uses archive layout (not operational matrix)."""
    import asyncio
    from unittest.mock import AsyncMock, MagicMock, patch

    from services import compliance_audit_evidence_pack_service as svc
    from database import database as db_singleton

    uploaded: dict = {}

    async def fake_upload(filename, data, metadata):
        uploaded["zip"] = data
        return "507f1f77bcf86cd799439011"

    reqs = [_req(i) for i in range(3)]
    mock_db = MagicMock()
    mock_db.properties.find_one = AsyncMock(
        return_value={
            "property_id": "p1",
            "client_id": "c1",
            "address_line_1": "1 Test St",
            "effective_jurisdiction_label": "England",
        }
    )
    mock_db.clients.find_one = AsyncMock(return_value={"client_id": "c1", "company_name": "Test"})
    mock_db.requirements.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=reqs)))
    mock_db.compliance_evidence_records.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[])))
    mock_db.documents.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[])))
    c3 = MagicMock()
    c3.to_list = AsyncMock(return_value=[])
    c2 = MagicMock()
    c2.limit = MagicMock(return_value=c3)
    c1 = MagicMock()
    c1.sort = MagicMock(return_value=c2)
    mock_db.audit_logs.find = MagicMock(return_value=c1)
    mock_db.tenant_delivery_proofs.find = MagicMock(return_value=c1)
    mock_db.compliance_audit_packs.insert_one = AsyncMock()
    mock_db.compliance_audit_packs.find_one = AsyncMock(return_value=None)

    stack = [
        patch.object(db_singleton, "get_db", return_value=mock_db),
        patch.object(svc, "filter_requirement_rows_for_client_runtime_surfaces", new=AsyncMock(return_value=reqs)),
        patch.object(svc, "resolve_branding", new=AsyncMock(return_value=MagicMock(
            source="pleerity",
            company_name="Pleerity",
            to_report_dict=lambda: {"brand_company_name": "Pleerity", "primary_color": "#0B1D3A"},
        ))),
        patch.object(svc, "fetch_published_metadata", new=AsyncMock(return_value={"version": 42})),
        patch.object(svc, "_upload_zip_gridfs", new=fake_upload),
        patch.object(svc, "_resolve_document_path_on_disk", return_value=None),
        patch("services.compliance_audit_evidence_pack_service.create_audit_log", new_callable=AsyncMock),
    ]
    for p in stack:
        p.start()
    try:
        asyncio.run(
            svc.build_compliance_audit_pack(
                client_id="c1",
                property_id="p1",
                initiated_by_user_id="u1",
                initiated_by_role="ROLE_CLIENT",
            )
        )
    finally:
        for p in stack:
            p.stop()

    import zipfile

    zf = zipfile.ZipFile(io.BytesIO(uploaded["zip"]))
    names = zf.namelist()
    has_trail = "Audit_Evidence_Pack/05_AUDIT_TIMELINE/audit_trail.pdf" in names
    summary = zf.read("Audit_Evidence_Pack/01_EXECUTIVE_SUMMARY/compliance_summary.pdf")
    from pypdf import PdfReader

    text = "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(summary)).pages).lower()
    has_archive_matrix = "evidence matrix" in text
    has_operational_matrix = "operational evidence matrix" in text
    return {
        "pass": has_trail and has_archive_matrix and not has_operational_matrix,
        "has_audit_trail_pdf": has_trail,
        "has_evidence_matrix_archive_wording": has_archive_matrix,
        "has_operational_matrix_wording": has_operational_matrix,
        "zip_file_count": len(names),
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    pdfs = _build_scenarios()
    results: dict = {
        "programme": "EVIDENCE-READINESS-OPERATIONAL-PRESENTATION-VERIFY",
        "run_tag": RUN_TAG,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "scenarios": {},
        "audit_pack_unchanged": None,
    }

    paths: Dict[str, str] = {}
    for name, pdf_bytes in pdfs.items():
        fname = f"evidence_readiness_{name}_{RUN_TAG}.pdf"
        path = OUT / fname
        path.write_bytes(pdf_bytes)
        paths[name] = str(path)
        results["scenarios"][name] = _inspect_presentation(name, pdf_bytes)
        results["scenarios"][name]["pdf_path"] = str(path)

    results["pdf_paths"] = paths
    results["primary_sample"] = paths.get("mixed_12_property")
    results["audit_pack_unchanged"] = _verify_audit_pack_unchanged()

    all_pass = all(s.get("pass") for s in results["scenarios"].values())
    results["all_scenarios_pass"] = all_pass and results["audit_pack_unchanged"].get("pass")
    results["watch_items"] = []
    for name, sc in results["scenarios"].items():
        for issue in sc.get("issues") or []:
            if issue.startswith("sparse_page") or issue.startswith("possible_footer"):
                results["watch_items"].append(f"{name}:{issue}")

    artifact = OUT / f"EVIDENCE_READINESS_PRESENTATION_VERIFY_{RUN_TAG}.json"
    artifact.write_text(json.dumps(results, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps({"artifact": str(artifact), "all_pass": results["all_scenarios_pass"], "paths": paths}, indent=2))
    return 0 if results["all_scenarios_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
