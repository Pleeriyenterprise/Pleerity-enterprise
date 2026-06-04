"""REPORTING-IMMUTABLE-ARTIFACT-GOVERNANCE-PHASE-03 tests."""

import io
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services import immutable_report_artifact_service as svc
from services.reporting_semantics_v1 import (
    EXPORT_DETERMINISM_IMMUTABLE_ARTIFACT,
    GRADE_AUDIT_ARTIFACT,
    GRADE_REGULATORY,
)


def test_immutable_scope_includes_governed_surfaces():
    assert "evidence_readiness" in svc.IMMUTABLE_SCOPE
    assert "professional_compliance" in svc.IMMUTABLE_SCOPE
    assert "audit_evidence_pack" in svc.IMMUTABLE_SCOPE
    assert svc.IMMUTABLE_SCOPE["evidence_readiness"]["export_grade"] == GRADE_AUDIT_ARTIFACT
    assert svc.IMMUTABLE_SCOPE["professional_compliance"]["export_grade"] == GRADE_REGULATORY


def test_snapshot_context_hash_stable():
    data = {
        "now_iso": "2026-06-02T12:00:00+00:00",
        "properties": [{"property_id": "p1"}],
        "requirements": [{"requirement_id": "r1"}],
    }
    h1 = svc.compute_snapshot_context_hash(
        client_id="c1", report_type="evidence_readiness", scope="portfolio", property_id=None, report_data=data
    )
    h2 = svc.compute_snapshot_context_hash(
        client_id="c1", report_type="evidence_readiness", scope="portfolio", property_id=None, report_data=data
    )
    assert h1 == h2
    assert len(h1) == 64


def test_prepare_artifact_identity_embeds_immutable_fields():
    embed = svc.prepare_artifact_identity(
        client_id="c1",
        report_type="evidence_readiness",
        scope="portfolio",
        report_data={"client": {}, "properties": [], "requirements": []},
    )
    assert embed["artifact_id"].startswith("rpt_")
    assert embed["determinism"] == EXPORT_DETERMINISM_IMMUTABLE_ARTIFACT
    assert embed["immutable_status"] == svc.IMMUTABLE_STATUS_FROZEN


def test_artifact_http_headers_immutable():
    lineage = {
        "artifact_id": "rpt_abc",
        "export_grade": GRADE_AUDIT_ARTIFACT,
        "export_grade_label": "Audit artifact",
        "content_sha256": "a" * 64,
    }
    headers = svc.artifact_http_headers(lineage, filename="test.pdf")
    assert headers["X-Report-Determinism"] == EXPORT_DETERMINISM_IMMUTABLE_ARTIFACT
    assert headers["X-Artifact-Id"] == "rpt_abc"
    assert headers["X-Immutable-Status"] == svc.IMMUTABLE_STATUS_FROZEN


@pytest.mark.asyncio
async def test_store_and_serve_artifact_tenant_isolation():
    pdf = b"%PDF-1.4 immutable test content"
    stored_lineage = {
        "artifact_id": "rpt_test123",
        "export_grade": GRADE_AUDIT_ARTIFACT,
        "export_grade_label": "Audit artifact",
        "content_sha256": svc._sha256_bytes(pdf),
        "original_generated_at": datetime.now(timezone.utc).isoformat(),
    }

    mock_fs = MagicMock()
    mock_fs.upload_from_stream = AsyncMock(return_value="507f1f77bcf86cd799439011")
    mock_fs.download_to_stream = AsyncMock(side_effect=lambda _oid, stream: stream.write(pdf))

    record = {
        "artifact_id": "rpt_test123",
        "client_id": "c1",
        "gridfs_id": "507f1f77bcf86cd799439011",
        "content_sha256": svc._sha256_bytes(pdf),
        "filename": "test.pdf",
        "export_grade": GRADE_AUDIT_ARTIFACT,
        "export_grade_label": "Audit artifact",
    }
    artifacts_coll = MagicMock()
    artifacts_coll.insert_one = AsyncMock()
    artifacts_coll.find_one = AsyncMock(return_value=record)
    mock_db = MagicMock()

    def _getitem(_self, key):
        if key == svc.COLLECTION:
            return artifacts_coll
        return MagicMock()

    mock_db.__getitem__ = _getitem

    with patch.object(svc.database, "get_db", return_value=mock_db):
        with patch("motor.motor_asyncio.AsyncIOMotorGridFSBucket", return_value=mock_fs):
            result = await svc.store_pdf_artifact(
                client_id="c1",
                report_type="evidence_readiness",
                pdf_bytes=pdf,
                filename="test.pdf",
                scope="portfolio",
                preset_artifact_id="rpt_test123",
                preset_lineage=stored_lineage,
            )
            assert result["artifact_id"] == "rpt_test123"

            served = await svc.serve_artifact_pdf(client_id="c1", artifact_id="rpt_test123")
            assert served is not None
            data, headers, _ = served
            assert data == pdf
            assert headers["X-Artifact-Id"] == "rpt_test123"

            artifacts_coll.find_one = AsyncMock(return_value=None)
            wrong_tenant = await svc.serve_artifact_pdf(client_id="c_other", artifact_id="rpt_test123")
            assert wrong_tenant is None


def test_lineage_metadata_complete():
    now = datetime(2026, 6, 2, 12, 0, 0, tzinfo=timezone.utc)
    lineage = svc.build_lineage_metadata(
        artifact_id="rpt_x",
        client_id="c1",
        report_type="evidence_readiness",
        scope="portfolio",
        property_id=None,
        export_grade=GRADE_AUDIT_ARTIFACT,
        original_generated_at=now,
        snapshot_context_hash="abc123",
        content_sha256="def456",
        jurisdiction_scope="England portfolio",
    )
    assert lineage["generation_engine"] == svc.GENERATION_ENGINE
    assert lineage["immutable_status"] == svc.IMMUTABLE_STATUS_FROZEN
    assert lineage["semantics_version"] == "v1"
