"""Sanity checks for build_storage_health_report (shape + resolves)."""

from utils.storage_paths import build_storage_health_report


def test_build_storage_health_report_shape(monkeypatch, tmp_path):
    monkeypatch.setenv("PYTEST_RUNNING", "1")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.delenv("DOCUMENT_STORAGE_PATH", raising=False)
    monkeypatch.delenv("INTAKE_UPLOAD_DIR", raising=False)
    monkeypatch.delenv("INTAKE_QUARANTINE_DIR", raising=False)
    r = build_storage_health_report()
    assert "DATA_DIR" in r
    assert "DOCUMENT_STORAGE_PATH" in r
    assert "INTAKE_UPLOAD_DIR" in r
    assert "INTAKE_QUARANTINE_DIR" in r
    assert "env" in r
    for key in ("DATA_DIR", "DOCUMENT_STORAGE_PATH", "INTAKE_UPLOAD_DIR", "INTAKE_QUARANTINE_DIR"):
        block = r[key]
        assert set(block.keys()) >= {"path", "exists", "is_directory", "writable", "ephemeral_unix_tmp", "deploy_runtime_fallback"}
        assert isinstance(block["path"], str)
    assert r["env"]["DATA_DIR"] is True
    assert tmp_path.name in r["DATA_DIR"]["path"] or str(tmp_path.resolve()) == r["DATA_DIR"]["path"]
