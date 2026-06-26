"""Tests for document vault file_path resolution in extraction jobs."""
import os
from pathlib import Path

import pytest

from utils.storage_paths import resolve_stored_document_file_path


@pytest.fixture
def vault_root(tmp_path, monkeypatch):
    vault = tmp_path / "documents"
    vault.mkdir(parents=True)
    monkeypatch.setenv("DOCUMENT_STORAGE_PATH", str(vault))
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    return vault


def test_resolve_relative_path_under_document_storage(vault_root):
  rel = "client-abc/cert.pdf"
  target = vault_root / "client-abc" / "cert.pdf"
  target.parent.mkdir(parents=True, exist_ok=True)
  target.write_bytes(b"%PDF-1.4 test")

  resolved = resolve_stored_document_file_path(rel)
  assert resolved == target.resolve()
  assert resolved.is_file()


def test_resolve_absolute_path_unchanged(tmp_path, vault_root):
  absolute = tmp_path / "outside.pdf"
  absolute.write_bytes(b"%PDF-1.4 outside")

  resolved = resolve_stored_document_file_path(str(absolute))
  assert resolved == absolute.resolve()
  assert resolved.is_file()


def test_resolve_relative_missing_file(vault_root):
  resolved = resolve_stored_document_file_path("client-abc/missing.pdf")
  assert not resolved.is_file()
