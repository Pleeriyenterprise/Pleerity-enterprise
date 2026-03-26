from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from middleware import admin_route_guard
from server import app


def _as_admin():
    return {"user_id": "admin-1", "email": "admin@example.com", "role": "ADMIN"}


def test_document_token_uses_api_base_for_preview_url(monkeypatch):
    app.dependency_overrides[admin_route_guard] = _as_admin
    client = TestClient(app)
    try:
        monkeypatch.setattr(
            "routes.admin_orders.get_order",
            AsyncMock(return_value={"order_id": "ord-1", "service_code": "MR_BASIC"}),
        )
        monkeypatch.setattr(
            "services.document_generator.get_document_versions",
            AsyncMock(
                return_value=[
                    SimpleNamespace(version=1, filename_pdf="draft-v1.pdf", filename_docx="draft-v1.docx")
                ]
            ),
        )
        monkeypatch.setattr(
            "utils.app_urls.get_api_base_url",
            lambda: "https://api.example.com",
        )

        resp = client.get("/api/admin/orders/ord-1/documents/1/token?format=pdf")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["preview_url"].startswith("https://api.example.com/api/admin/orders/ord-1/documents/1/view")
        assert "token=" in body["preview_url"]
    finally:
        app.dependency_overrides.clear()
        client.close()


def test_document_token_returns_404_when_requested_file_missing(monkeypatch):
    app.dependency_overrides[admin_route_guard] = _as_admin
    client = TestClient(app)
    try:
        monkeypatch.setattr(
            "routes.admin_orders.get_order",
            AsyncMock(return_value={"order_id": "ord-2", "service_code": "MR_BASIC"}),
        )
        monkeypatch.setattr(
            "services.document_generator.get_document_versions",
            AsyncMock(return_value=[SimpleNamespace(version=1, filename_pdf=None, filename_docx=None)]),
        )

        resp = client.get("/api/admin/orders/ord-2/documents/1/token?format=pdf")
        assert resp.status_code == 404
        assert "No pdf file stored for version 1" in resp.text
    finally:
        app.dependency_overrides.clear()
        client.close()
