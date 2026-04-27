import asyncio
import hashlib
import io
import json
import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from database import database as db_singleton
from services import compliance_audit_evidence_pack_service as svc


def _find_one_side_effect(filter_q, *_args, **_kwargs):
    fq = filter_q or {}
    if fq.get("property_id") == "p1" and fq.get("client_id") == "c1":
        return {
            "property_id": "p1",
            "client_id": "c1",
            "address_line_1": "Laurel Gardens",
            "city": "London",
            "postcode": "E1 1AA",
            "nickname": "Laurel Gardens",
            "effective_jurisdiction_label": "England",
        }
    if fq.get("client_id") == "c1":
        return {"client_id": "c1", "company_name": "Premier Property Management Ltd"}
    if "filename" in fq:
        return None
    return None


def _build_chain(rows):
    c3 = MagicMock()
    c3.to_list = AsyncMock(return_value=rows)
    c2 = MagicMock()
    c2.limit = MagicMock(return_value=c3)
    c1 = MagicMock()
    c1.sort = MagicMock(return_value=c2)
    return c1


def test_enterprise_pack_deterministic_structure_and_governance():
    req_active = {
        "requirement_id": "r1",
        "client_id": "c1",
        "property_id": "p1",
        "requirement_type": "gas_safety",
        "requirement_code": "GAS",
        "status": "OVERDUE",
        "mandatory": True,
        "evidence_authority_synced_at": "2026-01-01T00:00:00+00:00",
        "evidence_authority": {"version": 1, "state": "VERIFIED_CURRENT"},
    }
    req_hidden = {
        "requirement_id": "ghost_hidden_1",
        "client_id": "c1",
        "property_id": "p1",
        "requirement_type": "legacy_type",
        "status": "PENDING",
    }

    mock_db = MagicMock()
    mock_db.compliance_evidence_records = MagicMock()
    mock_db.compliance_evidence_records.find = MagicMock(
        return_value=MagicMock(to_list=AsyncMock(return_value=[]))
    )
    mock_db.properties.find_one = AsyncMock(side_effect=_find_one_side_effect)
    mock_db.clients.find_one = AsyncMock(side_effect=_find_one_side_effect)
    mock_db.requirements.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[req_active, req_hidden])))
    tmpdir = tempfile.mkdtemp()
    evidence_path = os.path.join(tmpdir, "certificate.pdf")
    try:
        with open(evidence_path, "wb") as fh:
            fh.write(b"verified-evidence-bytes")
        mock_db.documents.find = MagicMock(
            side_effect=[
                MagicMock(
                    to_list=AsyncMock(
                        return_value=[
                            {
                                "document_id": "doc-1",
                                "client_id": "c1",
                                "property_id": "p1",
                                "requirement_id": "r1",
                                "status": "VERIFIED",
                                "file_name": "Gas Certificate.pdf",
                                "file_path": evidence_path,
                                "uploaded_by_user_id": "uploader-1",
                                "uploaded_at": datetime(2026, 1, 2, 10, 30, tzinfo=timezone.utc),
                                "verified_by_user_id": "verifier-1",
                                "verified_at": datetime(2026, 1, 3, 11, 45, tzinfo=timezone.utc),
                                "source_type": "upload",
                            }
                        ]
                    )
                ),
                MagicMock(
                    to_list=AsyncMock(
                        return_value=[
                            {
                                "document_id": "doc-hidden-1",
                                "client_id": "c1",
                                "property_id": "p1",
                                "requirement_id": "ghost_hidden_1",
                                "status": "VERIFIED",
                                "file_name": "Legacy Hidden.pdf",
                            }
                        ]
                    )
                ),
            ]
        )
        mock_db.audit_logs.find = MagicMock(
            return_value=_build_chain(
                [
                    {
                        "action": "REQUIREMENT_STATUS_CHANGED",
                        "timestamp": "2026-01-03T00:00:00+00:00",
                        "metadata": {"property_id": "p1", "requirement_id": "ghost_hidden_1"},
                        "resource_type": "requirement",
                        "resource_id": "ghost_hidden_1",
                    }
                ]
            )
        )
        mock_db.tenant_delivery_proofs.find = MagicMock(return_value=_build_chain([]))
        mock_db.compliance_audit_packs.insert_one = AsyncMock()
        mock_db.compliance_audit_packs.find_one = AsyncMock(return_value=None)

        uploaded = {}

        async def fake_upload(filename, data, metadata):
            uploaded["filename"] = filename
            uploaded["zip"] = data
            uploaded["metadata"] = metadata
            return "507f1f77bcf86cd799439011"

        def _resolve_doc(_client_id, doc):
            fp = doc.get("file_path")
            if fp and os.path.isfile(fp):
                return Path(fp)
            return None

        with (
            patch.object(db_singleton, "get_db", return_value=mock_db),
            patch.object(
                svc,
                "filter_requirement_rows_for_client_runtime_surfaces",
                new=AsyncMock(return_value=[req_active]),
            ),
            patch.object(
                svc,
                "resolve_branding",
                new=AsyncMock(
                    return_value=MagicMock(
                        source="pleerity",
                        company_name="Pleerity Enterprise Ltd",
                        to_report_dict=lambda: {
                            "brand_company_name": "Pleerity Enterprise Ltd",
                            "company_name": "Pleerity Enterprise Ltd",
                            "primary_color": "#0B1D3A",
                            "pdf_footer_generated_by": "Generated by Pleerity Enterprise Ltd",
                            "pdf_footer_contact_line": "pleerityenterprise.co.uk",
                        },
                    )
                ),
            ),
            patch.object(svc, "fetch_published_metadata", new=AsyncMock(return_value={"version": 42})),
            patch.object(svc, "_upload_zip_gridfs", new=fake_upload),
            patch.object(svc, "_resolve_document_path_on_disk", side_effect=_resolve_doc),
            patch("services.compliance_audit_evidence_pack_service.create_audit_log", new_callable=AsyncMock),
        ):
            summary = asyncio.run(
                svc.build_compliance_audit_pack(
                    client_id="c1",
                    property_id="p1",
                    initiated_by_user_id="u1",
                    initiated_by_role="ROLE_CLIENT_ADMIN",
                )
            )

        assert summary["overall_compliance_status"] in {"ACTION REQUIRED", "HIGH RISK"}
        assert uploaded["filename"].startswith("CVP_Audit_Evidence_Pack_")
        assert uploaded["filename"].endswith(".zip")
        assert "string-vic" not in uploaded["filename"].lower()

        zf = zipfile.ZipFile(io.BytesIO(uploaded["zip"]))
        names = zf.namelist()
        assert names == sorted(names), "ZIP entries should be deterministic and sorted"
        assert "Audit_Evidence_Pack/00_README/pack_overview.pdf" in names
        assert "Audit_Evidence_Pack/01_EXECUTIVE_SUMMARY/compliance_summary.pdf" in names
        assert "Audit_Evidence_Pack/06_GOVERNANCE/manifest.json" in names
        assert "Audit_Evidence_Pack/06_GOVERNANCE/checksums.sha256" in names
        assert "Audit_Evidence_Pack/06_GOVERNANCE/generation_metadata.json" in names
        assert "Audit_Evidence_Pack/07_EXCEPTIONS/missing_or_pending_items.json" in names

        manifest = json.loads(zf.read("Audit_Evidence_Pack/06_GOVERNANCE/manifest.json").decode("utf-8"))
        metadata = json.loads(zf.read("Audit_Evidence_Pack/06_GOVERNANCE/generation_metadata.json").decode("utf-8"))
        exceptions = json.loads(zf.read("Audit_Evidence_Pack/07_EXCEPTIONS/missing_or_pending_items.json").decode("utf-8"))
        checksums = zf.read("Audit_Evidence_Pack/06_GOVERNANCE/checksums.sha256").decode("utf-8")
        overview_pdf = zf.read("Audit_Evidence_Pack/00_README/pack_overview.pdf")
        summary_pdf = zf.read("Audit_Evidence_Pack/01_EXECUTIVE_SUMMARY/compliance_summary.pdf")

        assert metadata["export_version"] == "2026.04"
        assert metadata["evidence_pack_version"] == "2.0.0"
        assert metadata["source_registry_version"] == "1"
        assert metadata["registry_version_used"] == "42"
        assert metadata["export_rules_version"] == "audit_evidence_pack_rules_2026.04.1"
        assert metadata["compliance_status_rules_version"] == "compliance_status_authority_v1"
        assert metadata["runtime_visibility_rules_version"] == "requirement_client_runtime_surface_v1"
        assert metadata["generation_engine_version"] == "compliance_audit_evidence_pack_service_v2"
        assert "Audit_Evidence_Pack/01_EXECUTIVE_SUMMARY/compliance_summary.pdf" in checksums
        assert "files" in manifest and len(manifest["files"]) > 0
        assert "ghost_hidden_1" in manifest["excluded_non_runtime_visible_requirement_ids"]
        assert any(x.get("requirement_id") == "ghost_hidden_1" for x in exceptions["excluded_historical_items"])

        for key in ("export_id", "export_generated_at", "export_generation_id", "export_rules_version", "registry_version_used"):
            assert key in manifest
            assert key in metadata
            assert manifest[key] == metadata[key]
        assert isinstance(manifest["export_id"], str) and manifest["export_id"].startswith("exp_")
        assert manifest["export_generation_id"] == manifest["pack_id"]

        evidence_entry = next(
            x
            for x in manifest["files"]
            if x["filename"].startswith("Audit_Evidence_Pack/03_COMPLIANCE_EVIDENCE/")
            and not x["filename"].endswith("NO_ACTIVE_EVIDENCE_FOUND.json")
        )
        for key in (
            "source_document_id",
            "uploaded_by_user_id",
            "uploaded_at",
            "verification_status",
            "verified_by_user_id",
            "verified_at",
            "evidence_source_type",
            "sha256",
            "included_in_active_compliance",
        ):
            assert key in evidence_entry
        assert evidence_entry["included_in_active_compliance"] is True
        assert evidence_entry["source_document_id"] == "doc-1"
        assert evidence_entry["verification_status"] == "VERIFIED"
        assert evidence_entry["uploaded_at"].endswith("+00:00")
        assert evidence_entry["verified_at"].endswith("+00:00")
        assert evidence_entry["sha256"] == evidence_entry["checksum"]

        excluded_evidence = exceptions["excluded_evidence"]
        assert all("included_in_active_compliance" in row for row in excluded_evidence)
        assert any(row["included_in_active_compliance"] is False for row in excluded_evidence)

        for row in manifest["files"]:
            assert row["generated_at"].endswith("+00:00")

        assert b"SCOPE AND LIMITATIONS" in overview_pdf
        assert b"SCOPE AND LIMITATIONS" in summary_pdf
        assert manifest["export_id"].encode("utf-8") in overview_pdf
        assert manifest["export_id"].encode("utf-8") in summary_pdf

        assert uploaded["metadata"]["export_id"] == manifest["export_id"]
        assert uploaded["metadata"]["export_generation_id"] == manifest["export_generation_id"]
        assert uploaded["metadata"]["registry_version_used"] == manifest["registry_version_used"]
        inserted_doc = mock_db.compliance_audit_packs.insert_one.await_args.args[0]
        assert inserted_doc["export_identity"]["export_id"] == manifest["export_id"]
        assert inserted_doc["export_identity"]["export_generated_at"] == manifest["export_generated_at"]
        assert inserted_doc["generation_metadata"]["export_id"] == manifest["export_id"]

        checksum_lines = [ln for ln in checksums.splitlines() if ln.strip()]
        for line in checksum_lines:
            digest, rel = line.split("  ", 1)
            actual = hashlib.sha256(zf.read(rel)).hexdigest()
            assert digest == actual
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def _find_marker_pack_side_effect(filter_q, *_args, **_kwargs):
    fq = filter_q or {}
    if fq.get("property_id") == "p2" and fq.get("client_id") == "cx":
        return {
            "property_id": "p2",
            "client_id": "cx",
            "address_line_1": "1 Test Street",
            "city": "London",
            "postcode": "E1 1AA",
            "effective_jurisdiction_label": "England",
        }
    if fq.get("client_id") == "cx":
        return {"client_id": "cx", "company_name": "Acme Ltd"}
    if "filename" in fq:
        return None
    return None


def test_no_active_evidence_marker_when_nothing_exported_under_03():
    mock_db = MagicMock()
    mock_db.compliance_evidence_records = MagicMock()
    mock_db.compliance_evidence_records.find = MagicMock(
        return_value=MagicMock(to_list=AsyncMock(return_value=[]))
    )
    mock_db.properties.find_one = AsyncMock(side_effect=_find_marker_pack_side_effect)
    mock_db.clients.find_one = AsyncMock(side_effect=_find_marker_pack_side_effect)
    mock_db.requirements.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[])))
    mock_db.documents.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[])))
    mock_db.audit_logs.find = MagicMock(return_value=_build_chain([]))
    mock_db.tenant_delivery_proofs.find = MagicMock(return_value=_build_chain([]))
    mock_db.compliance_audit_packs.insert_one = AsyncMock()
    mock_db.compliance_audit_packs.find_one = AsyncMock(return_value=None)

    uploaded: dict = {}

    async def fake_upload(filename, data, metadata):
        uploaded["zip"] = data
        return "507f1f77bcf86cd799439011"

    with (
        patch.object(db_singleton, "get_db", return_value=mock_db),
        patch.object(
            svc,
            "filter_requirement_rows_for_client_runtime_surfaces",
            new=AsyncMock(return_value=[]),
        ),
        patch.object(
            svc,
            "resolve_branding",
            new=AsyncMock(
                return_value=MagicMock(
                    source="pleerity",
                    company_name="Pleerity Enterprise Ltd",
                    to_report_dict=lambda: {
                        "brand_company_name": "Pleerity Enterprise Ltd",
                        "company_name": "Pleerity Enterprise Ltd",
                        "primary_color": "#0B1D3A",
                        "pdf_footer_generated_by": "Generated by Pleerity Enterprise Ltd",
                        "pdf_footer_contact_line": "pleerityenterprise.co.uk",
                    },
                )
            ),
        ),
        patch.object(svc, "fetch_published_metadata", new=AsyncMock(return_value={"version": 1})),
        patch.object(svc, "_upload_zip_gridfs", new=fake_upload),
        patch("services.compliance_audit_evidence_pack_service.create_audit_log", new_callable=AsyncMock),
    ):
        asyncio.run(
            svc.build_compliance_audit_pack(
                client_id="cx",
                property_id="p2",
                initiated_by_user_id="u1",
                initiated_by_role="ROLE_CLIENT_ADMIN",
            )
        )

    zf = zipfile.ZipFile(io.BytesIO(uploaded["zip"]))
    marker = "Audit_Evidence_Pack/03_COMPLIANCE_EVIDENCE/NO_ACTIVE_EVIDENCE_FOUND.json"
    assert marker in zf.namelist()
    payload = json.loads(zf.read(marker).decode("utf-8"))
    assert "No qualifying active evidence files" in payload["message"]
    assert payload["property_id"] == "p2"
    assert payload["requirements_reviewed_count"] == 0
    assert "hidden" in payload["hidden_and_non_runtime_visible_exclusion"].lower()
    assert "non-runtime-visible" in payload["hidden_and_non_runtime_visible_exclusion"].lower()


def test_professional_filename_prefers_address_over_casual_nickname():
    async def run():
        m = MagicMock()
        m.compliance_audit_packs.find_one = AsyncMock(return_value=None)
        m.clients.find_one = AsyncMock(return_value={"client_id": "cx", "company_name": "Acme Holdings Ltd"})
        prop = {
            "property_id": "p9",
            "nickname": "string vic",
            "address_line_1": "100 Victoria Gardens",
            "city": "London",
            "postcode": "N1 1AA",
        }
        dt = datetime(2026, 4, 27, tzinfo=timezone.utc)
        return await svc._build_enterprise_filename(db=m, client_id="cx", property_doc=prop, generated_at=dt)

    fn = asyncio.run(run())
    assert "string-vic" not in fn.lower()
    assert "Victoria" in fn or "100" in fn
    assert fn.startswith("CVP_Audit_Evidence_Pack_Acme-Holdings-Ltd_")
    assert fn.endswith(".zip")


def test_professional_filename_neutral_when_client_and_property_ids_only():
    async def run():
        m = MagicMock()
        m.compliance_audit_packs.find_one = AsyncMock(return_value=None)
        m.clients.find_one = AsyncMock(return_value={"client_id": "cx"})
        prop = {"property_id": "11111111-1111-1111-1111-111111111111"}
        dt = datetime(2026, 4, 27, tzinfo=timezone.utc)
        return await svc._build_enterprise_filename(db=m, client_id="cx", property_doc=prop, generated_at=dt)

    fn = asyncio.run(run())
    assert fn == "CVP_Audit_Evidence_Pack_Client_Property_2026-04-27.zip"


def test_professional_filename_stable_for_identical_inputs():
    async def run():
        m = MagicMock()
        m.compliance_audit_packs.find_one = AsyncMock(return_value=None)
        m.clients.find_one = AsyncMock(return_value={"company_name": "Stable Co"})
        prop = {"property_id": "pz", "address_line_1": "1 Stable Row", "postcode": "AB1 2CD"}
        dt = datetime(2026, 5, 1, tzinfo=timezone.utc)
        return await svc._build_enterprise_filename(db=m, client_id="c9", property_doc=prop, generated_at=dt)

    a = asyncio.run(run())
    b = asyncio.run(run())
    assert a == b
    assert a.startswith("CVP_Audit_Evidence_Pack_Stable-Co_")

