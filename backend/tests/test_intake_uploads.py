"""
Tests for Intake Preferences & Consents uploads: validation, migration idempotency, quarantined never migrate.
"""
import pytest
import os
import io
import uuid
from pathlib import Path
from unittest.mock import patch, MagicMock
from pathlib import Path

# Async tests with database
pytestmark = pytest.mark.asyncio

BACKEND_DIR = Path(__file__).resolve().parent.parent
os.chdir(BACKEND_DIR)
import sys
sys.path.insert(0, str(BACKEND_DIR))

from database import database
from models.intake_uploads import IntakeUploadStatus


class TestIntakeUploadValidation:
    """Server-side validation: file types, size, session bytes."""

    @pytest.fixture
    def app_client(self):
        from fastapi.testclient import TestClient
        from server import app
        return TestClient(app)

    def test_upload_rejects_disallowed_type(self, app_client):
        """Upload with disallowed MIME/extension returns 400."""
        session_id = str(uuid.uuid4())
        files = [("files", ("bad.exe", io.BytesIO(b"x"), "application/x-msdownload"))]
        data = {"intake_session_id": session_id}
        r = app_client.post("/api/intake/uploads/upload", data=data, files=files)
        assert r.status_code == 400
        body = r.json()
        assert "detail" in body
        detail = body["detail"]
        if isinstance(detail, dict):
            assert detail.get("message") or "allowed" in str(detail).lower()
        else:
            assert "allowed" in str(detail).lower()

    def test_upload_rejects_file_over_20mb(self, app_client):
        """Upload with file > 20MB returns 413."""
        session_id = str(uuid.uuid4())
        big = io.BytesIO(b"x" * (21 * 1024 * 1024))
        big.name = "large.pdf"
        files = [("files", ("large.pdf", big, "application/pdf"))]
        data = {"intake_session_id": session_id}
        r = app_client.post("/api/intake/uploads/upload", data=data, files=files)
        assert r.status_code == 413
        body = r.json()
        assert "detail" in body

    def test_upload_accepts_pdf(self, app_client):
        """Upload with PDF is accepted (200) when ClamAV returns CLEAN."""
        session_id = str(uuid.uuid4())
        content = b"%PDF-1.4 minimal"
        files = [("files", ("test.pdf", io.BytesIO(content), "application/pdf"))]
        data = {"intake_session_id": session_id}
        with patch("services.clamav_scanner.scan_file", return_value=("CLEAN", None)):
            r = app_client.post("/api/intake/uploads/upload", data=data, files=files)
        assert r.status_code == 200
        assert r.json().get("success") is True
        assert len(r.json().get("uploaded", [])) == 1
        assert r.json()["uploaded"][0]["status"] == "CLEAN"

    def test_upload_rejects_more_than_20_files_per_request(self, app_client):
        """More than 20 files in one request returns 400 with TOO_MANY_FILES."""
        session_id = str(uuid.uuid4())
        content = b"%PDF-1.4 minimal"
        files = [("files", (f"f{i}.pdf", io.BytesIO(content), "application/pdf")) for i in range(21)]
        data = {"intake_session_id": session_id}
        r = app_client.post("/api/intake/uploads/upload", data=data, files=files)
        assert r.status_code == 400
        body = r.json()
        assert body.get("detail", {}).get("error_code") == "TOO_MANY_FILES"
        assert "20" in str(body.get("detail", {}).get("message", ""))

    def test_scanner_unavailable_marks_quarantined_not_clean(self, app_client):
        """When ClamAV is unavailable or scan errors, file is QUARANTINED and never CLEAN."""
        session_id = str(uuid.uuid4())
        content = b"%PDF-1.4 minimal"
        files = [("files", ("test.pdf", io.BytesIO(content), "application/pdf"))]
        data = {"intake_session_id": session_id}
        with patch("services.clamav_scanner.scan_file", return_value=("QUARANTINED", "ClamAV not installed")):
            r = app_client.post("/api/intake/uploads/upload", data=data, files=files)
        assert r.status_code == 200
        assert r.json().get("success") is True
        assert len(r.json().get("uploaded", [])) == 1
        assert r.json()["uploaded"][0]["status"] == "QUARANTINED"
        assert r.json()["uploaded"][0].get("error")


class TestIntakeUploadMigrationIdempotency:
    """Migration is idempotent: do not duplicate Documents or re-migrate."""

    @pytest.fixture
    async def db(self):
        await database.connect()
        yield database.get_db()
        # teardown optional

    async def test_migrate_skips_already_migrated(self, db):
        """CLEAN uploads with migrated_to_document_id are not re-migrated."""
        from services.intake_upload_migration import migrate_intake_uploads_to_vault
        client_id = str(uuid.uuid4())
        session_id = str(uuid.uuid4())
        await db.clients.insert_one({
            "client_id": client_id,
            "intake_session_id": session_id,
            "email": "mig@test.com",
        })
        # Insert one already migrated (no need for property; migration uses client-level when no mapping)
        await db.intake_uploads.insert_one({
            "upload_id": str(uuid.uuid4()),
            "intake_session_id": session_id,
            "status": IntakeUploadStatus.CLEAN.value,
            "migrated_to_document_id": "doc-already",
            "storage_path": "/tmp/foo.pdf",
            "original_filename": "foo.pdf",
            "file_size": 100,
            "content_type": "application/pdf",
            "filename": "abc.pdf",
        })
        result = await migrate_intake_uploads_to_vault(client_id)
        assert result.get("migrated", 0) == 0
        # Cleanup
        await db.clients.delete_one({"client_id": client_id})
        await db.properties.delete_many({"client_id": client_id})
        await db.intake_uploads.delete_many({"intake_session_id": session_id})

    async def test_migration_creates_client_level_document_when_no_property_mapping(self, db):
        """Migrated documents get property_id=None (client-level) when intake provides no explicit mapping."""
        from services.intake_upload_migration import migrate_intake_uploads_to_vault
        import tempfile
        client_id = str(uuid.uuid4())
        session_id = str(uuid.uuid4())
        await db.clients.insert_one({
            "client_id": client_id,
            "intake_session_id": session_id,
            "email": "noprop@test.com",
        })
        tmpdir = tempfile.mkdtemp()
        tmp_path = os.path.join(tmpdir, "doc.pdf")
        with open(tmp_path, "wb") as f:
            f.write(b"%PDF-1.4 minimal")
        try:
            await db.intake_uploads.insert_one({
                "upload_id": str(uuid.uuid4()),
                "intake_session_id": session_id,
                "status": IntakeUploadStatus.CLEAN.value,
                "storage_path": tmp_path,
                "original_filename": "doc.pdf",
                "file_size": 14,
                "content_type": "application/pdf",
                "filename": "x.pdf",
                # no property_id = client-level
            })
            import services.intake_upload_migration as mig
            orig_path = mig.DOCUMENT_STORAGE_PATH
            try:
                mig.DOCUMENT_STORAGE_PATH = Path(tmpdir)
                result = await migrate_intake_uploads_to_vault(client_id)
            finally:
                mig.DOCUMENT_STORAGE_PATH = orig_path
            assert result.get("migrated", 0) == 1
            doc = await db.documents.find_one({"client_id": client_id}, {"_id": 0})
            assert doc is not None
            assert doc.get("property_id") is None
        finally:
            import shutil
            if os.path.isdir(tmpdir):
                shutil.rmtree(tmpdir, ignore_errors=True)
            await db.clients.delete_one({"client_id": client_id})
            await db.intake_uploads.delete_many({"intake_session_id": session_id})
            await db.documents.delete_many({"client_id": client_id})


class TestQuarantinedNeverMigrate:
    """QUARANTINED uploads must never be migrated."""

    @pytest.fixture
    async def db(self):
        await database.connect()
        yield database.get_db()

    async def test_migrate_ignores_quarantined(self, db):
        """Uploads with status QUARANTINED are not selected for migration."""
        from services.intake_upload_migration import migrate_intake_uploads_to_vault
        client_id = str(uuid.uuid4())
        session_id = str(uuid.uuid4())
        await db.clients.insert_one({
            "client_id": client_id,
            "intake_session_id": session_id,
            "email": "q@test.com",
        })
        await db.intake_uploads.insert_one({
            "upload_id": str(uuid.uuid4()),
            "intake_session_id": session_id,
            "status": IntakeUploadStatus.QUARANTINED.value,
            "storage_path": "/quarantine/foo.pdf",
            "original_filename": "foo.pdf",
            "file_size": 100,
            "content_type": "application/pdf",
            "filename": "abc.pdf",
        })
        result = await migrate_intake_uploads_to_vault(client_id)
        assert result.get("migrated", 0) == 0
        # No new document created for this upload
        count = await db.documents.count_documents({"client_id": client_id})
        assert count == 0
        await db.clients.delete_one({"client_id": client_id})
        await db.properties.delete_many({"client_id": client_id})
        await db.intake_uploads.delete_many({"intake_session_id": session_id})
