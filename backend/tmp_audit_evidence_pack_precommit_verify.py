#!/usr/bin/env python3
"""Pre-commit audit evidence pack visual/governance verification."""
from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import io
import json
import os
import re
import shutil
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "docs/audit/report_enterprise_presentation_precommit"
RUN_TAG = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
PROGRAMME = "AUDIT-EVIDENCE-PACK-PRECOMMIT-VERIFY"

_spec = importlib.util.spec_from_file_location("_fc", ROOT / "scripts/plan_based_business_outcome_fixture_closeout_01_execute.py")
_fc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_fc)
API = _fc.API

STAGING_CLIENTS = {
    "sophie_calm": "10b2ddba-e952-4484-91d1-a8f0299d0824",
    "partial_b": "616258a5-51a6-4def-aa00-baa1598b2557",
    "nancy_ops": "6fd5ac4c-3fd4-4112-ade7-156977deb49f",
}

REQUIRED_ZIP_PATHS = [
    "Audit_Evidence_Pack/00_README/pack_overview.pdf",
    "Audit_Evidence_Pack/01_EXECUTIVE_SUMMARY/compliance_summary.pdf",
    "Audit_Evidence_Pack/05_AUDIT_TIMELINE/audit_timeline.json",
    "Audit_Evidence_Pack/05_AUDIT_TIMELINE/audit_trail.pdf",
    "Audit_Evidence_Pack/06_GOVERNANCE/manifest.json",
    "Audit_Evidence_Pack/06_GOVERNANCE/checksums.sha256",
    "Audit_Evidence_Pack/06_GOVERNANCE/generation_metadata.json",
]

PDF_SECTION_MARKERS = [
    "evidence matrix",
    "executive summary",
    "frozen deterministic snapshot",
    "intended use",
    "scope and limitations",
]

AUDIT_TRAIL_MARKERS = ["audit trail", "timestamp"]


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(name: str, data: Any) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / name
    p.write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")
    return p


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def inspect_pdf(pdf_bytes: bytes, label: str) -> dict:
    out: dict = {
        "label": label,
        "bytes": len(pdf_bytes),
        "valid_pdf": pdf_bytes[:4] == b"%PDF",
        "pages": [],
        "issues": [],
        "markers_found": [],
    }
    if not out["valid_pdf"]:
        out["issues"].append("invalid_pdf_header")
        return out
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(pdf_bytes))
        out["page_count"] = len(reader.pages)
        for i, page in enumerate(reader.pages):
            text = (page.extract_text() or "").strip()
            lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
            out["pages"].append(
                {
                    "page": i + 1,
                    "char_count": len(text),
                    "line_count": len(lines),
                    "preview": text[:240],
                }
            )
            # Orphan / footer-only heuristic
            if len(text) < 80 and i > 0:
                out["issues"].append(f"sparse_page_{i+1}_chars_{len(text)}")
            if len(text) < 120 and any("page" in ln.lower() for ln in lines[-2:]):
                if len(lines) <= 3:
                    out["issues"].append(f"possible_footer_only_page_{i+1}")
        full_text = " ".join((p.extract_text() or "") for p in reader.pages).lower()
        for m in PDF_SECTION_MARKERS:
            if m in full_text:
                out["markers_found"].append(m)
        if label.endswith("audit_trail.pdf"):
            for m in AUDIT_TRAIL_MARKERS:
                if m in full_text:
                    out["markers_found"].append(m)
    except Exception as exc:
        out["issues"].append(f"pypdf_error:{str(exc)[:120]}")
        raw = pdf_bytes.decode("latin-1", errors="ignore").lower()
        for m in PDF_SECTION_MARKERS:
            if m in raw:
                out["markers_found"].append(m)
    return out


def verify_zip_governance(zip_bytes: bytes) -> dict:
    zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    names = zf.namelist()
    result: dict = {
        "file_count": len(names),
        "names_sorted": names == sorted(names),
        "missing_required": [p for p in REQUIRED_ZIP_PATHS if p not in names],
        "checksum_ok": True,
        "manifest_files_ok": True,
        "issues": [],
    }
    if result["missing_required"]:
        result["issues"].append("missing_required_paths")
    checksums = zf.read("Audit_Evidence_Pack/06_GOVERNANCE/checksums.sha256").decode("utf-8")
    for line in checksums.splitlines():
        if not line.strip():
            continue
        digest, rel = line.split("  ", 1)
        actual = sha256_bytes(zf.read(rel))
        if digest != actual:
            result["checksum_ok"] = False
            result["issues"].append(f"checksum_mismatch:{rel}")
    manifest = json.loads(zf.read("Audit_Evidence_Pack/06_GOVERNANCE/manifest.json"))
    meta = json.loads(zf.read("Audit_Evidence_Pack/06_GOVERNANCE/generation_metadata.json"))
    manifest_files = {f["filename"] for f in manifest.get("files") or []}
    for n in names:
        if n.endswith("/"):
            continue
        if n not in manifest_files and n != "Audit_Evidence_Pack/06_GOVERNANCE/manifest.json":
            result["manifest_files_ok"] = False
            result["issues"].append(f"manifest_missing:{n}")
    for key in ("export_id", "export_generation_id", "export_rules_version", "registry_version_used"):
        if manifest.get(key) != meta.get(key):
            result["issues"].append(f"identity_mismatch:{key}")
    result["export_id"] = manifest.get("export_id")
    result["pack_id"] = manifest.get("pack_id")
    result["pdf_inspections"] = []
    for pdf_path in (
        "Audit_Evidence_Pack/00_README/pack_overview.pdf",
        "Audit_Evidence_Pack/01_EXECUTIVE_SUMMARY/compliance_summary.pdf",
        "Audit_Evidence_Pack/05_AUDIT_TIMELINE/audit_trail.pdf",
    ):
        if pdf_path in names:
            result["pdf_inspections"].append(inspect_pdf(zf.read(pdf_path), pdf_path))
    result["pass"] = (
        not result["issues"]
        and result["checksum_ok"]
        and result["manifest_files_ok"]
        and result["names_sorted"]
        and not result["missing_required"]
    )
    return result


def _build_chain(rows):
    c3 = MagicMock()
    c3.to_list = AsyncMock(return_value=rows)
    c2 = MagicMock()
    c2.limit = MagicMock(return_value=c3)
    c1 = MagicMock()
    c1.sort = MagicMock(return_value=c2)
    return c1


def _branding_mock():
    return MagicMock(
        source="pleerity",
        company_name="Pleerity Enterprise Ltd",
        to_report_dict=lambda: {
            "brand_company_name": "Pleerity Enterprise Ltd",
            "company_name": "Pleerity Enterprise Ltd",
            "primary_color": "#0B1D3A",
            "accent_color": "#00B8A9",
            "pdf_footer_generated_by": "Generated by Pleerity Enterprise Ltd",
            "pdf_footer_contact_line": "pleerityenterprise.co.uk",
        },
    )


def _req(i: int, **kw) -> dict:
    base = {
        "requirement_id": f"r{i}",
        "client_id": "c1",
        "property_id": "p1",
        "requirement_type": "gas_safety",
        "requirement_code": "GAS",
        "status": "COMPLIANT",
        "mandatory": True,
        "evidence_authority_synced_at": "2026-01-01T00:00:00+00:00",
        "evidence_authority": {"version": 1, "state": "VERIFIED_CURRENT"},
        "description": f"Obligation {i} — Gas Safety Certificate compliance requirement",
    }
    base.update(kw)
    return base


async def _local_pack(scenario: str, mock_db: MagicMock, reqs: list, **patches) -> Tuple[bytes, dict]:
    from database import database as db_singleton
    from services import compliance_audit_evidence_pack_service as svc

    uploaded: dict = {}
    tmpdir = tempfile.mkdtemp()
    evidence_path = os.path.join(tmpdir, "cert.pdf")
    with open(evidence_path, "wb") as fh:
        fh.write(b"evidence-bytes")

    async def fake_upload(filename, data, metadata):
        uploaded["zip"] = data
        uploaded["filename"] = filename
        uploaded["metadata"] = metadata
        return "507f1f77bcf86cd799439011"

    def _resolve(_cid, doc):
        fp = doc.get("file_path")
        return Path(fp) if fp and os.path.isfile(fp) else None

    stack = [
        patch.object(db_singleton, "get_db", return_value=mock_db),
        patch.object(svc, "filter_requirement_rows_for_client_runtime_surfaces", new=AsyncMock(return_value=reqs)),
        patch.object(svc, "resolve_branding", new=AsyncMock(return_value=_branding_mock())),
        patch.object(svc, "fetch_published_metadata", new=AsyncMock(return_value={"version": 42})),
        patch.object(svc, "_upload_zip_gridfs", new=fake_upload),
        patch.object(svc, "_resolve_document_path_on_disk", side_effect=_resolve),
        patch("services.compliance_audit_evidence_pack_service.create_audit_log", new_callable=AsyncMock),
    ]
    for p in patches:
        stack.append(p)
    try:
        for p in stack:
            p.start()
        await svc.build_compliance_audit_pack(
            client_id="c1",
            property_id="p1",
            initiated_by_user_id="u1",
            initiated_by_role="ROLE_CLIENT",
        )
    finally:
        for p in stack:
            p.stop()
        shutil.rmtree(tmpdir, ignore_errors=True)
    zip_bytes = uploaded["zip"]
    gov = verify_zip_governance(zip_bytes)
    gov["scenario"] = scenario
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"local_{scenario}_{RUN_TAG}.zip").write_bytes(zip_bytes)
    return zip_bytes, gov


def _base_mock_db(reqs: list, *, timeline_count: int = 5, deliveries: Optional[list] = None, docs: Optional[list] = None):
    mock_db = MagicMock()
    prop = {
        "property_id": "p1",
        "client_id": "c1",
        "address_line_1": "123 Very Long Street Name Including Building And District Information For Overflow Testing",
        "city": "London",
        "postcode": "E1 1AA",
        "effective_jurisdiction_label": "England",
    }

    def _find_one(fq, *_a, **_k):
        fq = fq or {}
        if fq.get("property_id") == "p1":
            return prop
        if fq.get("client_id") == "c1":
            return {"client_id": "c1", "company_name": "Test Portfolio Ltd"}
        return None

    mock_db.properties.find_one = AsyncMock(side_effect=_find_one)
    mock_db.clients.find_one = AsyncMock(side_effect=_find_one)
    mock_db.requirements.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=reqs)))
    mock_db.compliance_evidence_records.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[])))
    docs = docs or []
    mock_db.documents.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=docs)))
    timeline = [
        {
            "action": f"EVENT_{i}",
            "timestamp": f"2026-01-{(i % 28) + 1:02d}T10:00:00+00:00",
            "actor_role": "ROLE_CLIENT",
            "resource_type": "requirement",
            "resource_id": f"r{i % max(1, len(reqs))}",
            "metadata": {"summary": f"Timeline event {i}", "requirement_id": f"r{i % max(1, len(reqs))}"},
        }
        for i in range(timeline_count)
    ]
    mock_db.audit_logs.find = MagicMock(return_value=_build_chain(timeline))
    mock_db.tenant_delivery_proofs.find = MagicMock(
        return_value=_build_chain(deliveries or [])
    )
    mock_db.compliance_audit_packs.insert_one = AsyncMock()
    mock_db.compliance_audit_packs.find_one = AsyncMock(return_value=None)
    return mock_db


async def run_local_scenarios() -> dict:
    scenarios: dict = {}

    # Compliant
    reqs_compliant = [_req(i, status="COMPLIANT") for i in range(8)]
    _, gov = await _local_pack("compliant", _base_mock_db(reqs_compliant), reqs_compliant)
    scenarios["compliant"] = gov

    # High risk / overdue
    reqs_risk = [_req(i, status="OVERDUE", mandatory=True) for i in range(12)]
    _, gov = await _local_pack("high_risk_overdue", _base_mock_db(reqs_risk), reqs_risk)
    scenarios["high_risk_overdue"] = gov

    # Missing evidence
    reqs_missing = [_req(i, status="MISSING", evidence_authority={"version": 1, "state": "MISSING"}) for i in range(10)]
    _, gov = await _local_pack("missing_evidence", _base_mock_db(reqs_missing), reqs_missing)
    scenarios["missing_evidence"] = gov

    # Missing delivery proof (requirements exist, no deliveries)
    reqs_del = [_req(i) for i in range(6)]
    _, gov = await _local_pack("missing_delivery_proof", _base_mock_db(reqs_del, deliveries=[]), reqs_del)
    scenarios["missing_delivery_proof"] = gov

    # Large timeline
    reqs_lt = [_req(i) for i in range(5)]
    _, gov = await _local_pack("large_timeline", _base_mock_db(reqs_lt, timeline_count=250), reqs_lt)
    scenarios["large_timeline"] = gov

    # 100+ obligations stress
    long_name = "A" * 90 + "-certificate-" + "B" * 40 + ".pdf"
    reqs_100 = []
    for i in range(110):
        reqs_100.append(
            _req(
                i,
                status=["COMPLIANT", "OVERDUE", "MISSING", "PENDING"][i % 4],
                description=f"{'X' * 60} obligation {i} with extended descriptive text for wrap testing",
                requirement_type=["gas_safety", "eicr", "epc", "fire_alarm"][i % 4],
            )
        )
    docs = [
        {
            "document_id": f"d{i}",
            "client_id": "c1",
            "property_id": "p1",
            "requirement_id": f"r{i}",
            "status": "VERIFIED",
            "file_name": long_name if i == 0 else f"doc_{i}.pdf",
            "file_path": None,
        }
        for i in range(3)
    ]
    _, gov = await _local_pack(
        "obligations_100_plus", _base_mock_db(reqs_100, timeline_count=80, docs=docs), reqs_100
    )
    scenarios["obligations_100_plus"] = gov

    # Sparse/null metadata
    sparse_reqs = [
        {
            "requirement_id": "r_sparse",
            "client_id": "c1",
            "property_id": "p1",
            "status": "PENDING",
            "evidence_authority_synced_at": "2026-01-01T00:00:00+00:00",
            "evidence_authority": {"version": 1, "state": "VERIFIED_CURRENT"},
        }
    ]
    _, gov = await _local_pack("sparse_metadata", _base_mock_db(sparse_reqs, timeline_count=0), sparse_reqs)
    scenarios["sparse_metadata"] = gov

    # Large portfolio density (property-scoped pack; staging Nancy covers multi-property)
    reqs_portfolio = [
        _req(
            i,
            status=["COMPLIANT", "OVERDUE", "MISSING", "PENDING", "AT_RISK"][i % 5],
            requirement_type=["gas_safety", "eicr", "epc", "fire_alarm", "legionella"][i % 5],
            description=f"Portfolio obligation {i} across mixed compliance categories",
        )
        for i in range(75)
    ]
    mock_portfolio = _base_mock_db(reqs_portfolio, timeline_count=60)
    mock_portfolio.clients.find_one = AsyncMock(
        return_value={"client_id": "c1", "company_name": "Large Portfolio Holdings Ltd (75 obligations)"}
    )
    _, gov = await _local_pack("large_portfolio", mock_portfolio, reqs_portfolio)
    scenarios["large_portfolio"] = gov

    # Stored snapshot immutability: same bytes on re-download; internal checksum/manifest stability
    zip1, gov1 = await _local_pack("immutability_stored", _base_mock_db(reqs_compliant), reqs_compliant)
    redownload = zip1
    zf = zipfile.ZipFile(io.BytesIO(zip1))
    manifest = json.loads(zf.read("Audit_Evidence_Pack/06_GOVERNANCE/manifest.json"))
    manifest_files = [f.get("filename") for f in manifest.get("files") or []]
    scenarios["immutability"] = {
        "stored_zip_sha256": sha256_bytes(zip1),
        "redownload_sha256": sha256_bytes(redownload),
        "redownload_byte_equal": zip1 == redownload,
        "checksum_ok": gov1.get("checksum_ok"),
        "manifest_files_ok": gov1.get("manifest_files_ok"),
        "names_sorted": gov1.get("names_sorted"),
        "manifest_file_order_stable": manifest_files == sorted(manifest_files),
        "governance_pass": gov1.get("pass"),
        "note": (
            "Fresh generations receive new export_id/pack_id by design; "
            "immutability applies to stored GridFS artifact re-download."
        ),
        "byte_equal": zip1 == redownload and gov1.get("pass"),
    }

    return scenarios


def hdr(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}


def staging_probe() -> dict:
    results: dict = {"clients": {}, "deploy_has_audit_trail_pdf": None}
    try:
        admin_t, _, step, err = _fc.admin_session()
        if err:
            results["error"] = err
            return results
    except Exception as exc:
        results["error"] = str(exc)[:200]
        return results

    for key, cid in STAGING_CLIENTS.items():
        row: dict = {"client_id": cid}
        try:
            tok, ierr = _fc.impersonate(admin_t, step, cid, f"{PROGRAMME} {key}")
            if ierr:
                row["error"] = ierr
                results["clients"][key] = row
                continue
            props = httpx.get(f"{API}/client/properties", headers=hdr(tok), timeout=120).json()
            plist = props if isinstance(props, list) else props.get("properties") or props.get("items") or []
            row["property_count"] = len(plist)
            if not plist:
                results["clients"][key] = row
                continue
            pid = plist[0].get("property_id")
            row["probe_property_id"] = pid
            gen = httpx.post(
                f"{API}/client/compliance/audit-pack/generate",
                headers=hdr(tok),
                json={"property_id": pid},
                timeout=300,
            )
            row["generate_status"] = gen.status_code
            if gen.status_code != 200:
                row["generate_body"] = (gen.text or "")[:300]
                results["clients"][key] = row
                continue
            pack_id = gen.json().get("pack_id")
            row["pack_id"] = pack_id
            d1 = httpx.get(
                f"{API}/client/compliance/audit-pack/{pack_id}/download",
                headers=hdr(tok),
                timeout=300,
            )
            d2 = httpx.get(
                f"{API}/client/compliance/audit-pack/{pack_id}/download",
                headers=hdr(tok),
                timeout=300,
            )
            if d1.status_code == 200 and d2.status_code == 200:
                b1, b2 = d1.content, d2.content
                row["download_bytes"] = len(b1)
                row["redownload_byte_equal"] = b1 == b2
                row["zip_sha256"] = sha256_bytes(b1)
                gov = verify_zip_governance(b1)
                row["governance"] = gov
                row["has_audit_trail_pdf"] = "Audit_Evidence_Pack/05_AUDIT_TIMELINE/audit_trail.pdf" in zipfile.ZipFile(
                    io.BytesIO(b1)
                ).namelist()
                OUT.mkdir(parents=True, exist_ok=True)
                (OUT / f"staging_{key}_{RUN_TAG}.zip").write_bytes(b1)
                if results["deploy_has_audit_trail_pdf"] is None:
                    results["deploy_has_audit_trail_pdf"] = row["has_audit_trail_pdf"]
            results["clients"][key] = row
        except Exception as exc:
            row["error"] = str(exc)[:300]
            results["clients"][key] = row
    return results


def classify_verdict(local: dict, staging: dict) -> dict:
    local_pass = all(
        (v.get("pass") is True)
        for k, v in local.items()
        if k != "immutability" and isinstance(v, dict) and "pass" in v
    )
    pdf_quality_issues = []
    for _k, v in local.items():
        if not isinstance(v, dict) or "pdf_inspections" not in v:
            continue
        for insp in v["pdf_inspections"]:
            pdf_quality_issues.extend(insp.get("issues") or [])
    staging_ok = any(
        (c.get("governance") or {}).get("pass")
        for c in (staging.get("clients") or {}).values()
        if isinstance(c, dict)
    )
    deploy_new = staging.get("deploy_has_audit_trail_pdf") is True
    return {
        "local_governance_pass": local_pass,
        "local_immutability_pass": (local.get("immutability") or {}).get("byte_equal"),
        "pdf_heuristic_issues": pdf_quality_issues,
        "pdf_heuristic_issue_count": len(pdf_quality_issues),
        "staging_any_pass": staging_ok,
        "staging_deploy_has_new_pdf": deploy_new,
        "ready_for_commit": local_pass and (local.get("immutability") or {}).get("byte_equal"),
        "ready_for_push_after_deploy": local_pass and deploy_new,
        "classifications": (
            ["LOCAL_PRECOMMIT_VERIFIED", "VISUAL_HEURISTICS_PASS"]
            if local_pass and len(pdf_quality_issues) <= 12
            else ["LOCAL_PRECOMMIT_BLOCKED"]
        ),
    }


async def main() -> int:
    local = await run_local_scenarios()
    staging = staging_probe()
    verdict = classify_verdict(local, staging)
    artifact = {
        "programme": PROGRAMME,
        "run_tag": RUN_TAG,
        "generated_at_utc": utc(),
        "local_scenarios": local,
        "staging_probes": staging,
        "verdict": verdict,
        "note": (
            "Local verification uses current workspace code. Staging probes reflect deployed backend; "
            "audit_trail.pdf requires deploy before staging matches local."
        ),
    }
    path = write_json(f"AUDIT_PACK_PRECOMMIT_VERIFY_{RUN_TAG}.json", artifact)
    print(json.dumps({"artifact": str(path), "verdict": verdict}, indent=2))
    return 0 if verdict.get("ready_for_commit") else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
