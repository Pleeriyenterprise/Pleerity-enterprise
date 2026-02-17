"""
Legacy and duplicate OTP routes must be removed (404). Only /api/otp/send and /api/otp/verify exist.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes.sms import router as sms_router
from routes.otp import router as otp_router


@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(sms_router)
    app.include_router(otp_router)
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


def test_legacy_send_otp_returns_404(client: TestClient):
    """POST /api/sms/send-otp returns 404 (route removed)."""
    resp = client.post(
        "/api/sms/send-otp",
        json={"phone_number": "+447700900123"},
    )
    assert resp.status_code == 404


def test_legacy_verify_otp_returns_404(client: TestClient):
    """POST /api/sms/verify-otp returns 404 (route removed)."""
    resp = client.post(
        "/api/sms/verify-otp",
        json={"phone_number": "+447700900123", "code": "123456"},
    )
    assert resp.status_code == 404


def test_sms_otp_send_returns_404(client: TestClient):
    """POST /api/sms/otp/send returns 404 (duplicate surface removed)."""
    resp = client.post(
        "/api/sms/otp/send",
        json={"phone_e164": "+447700900123", "purpose": "verify_phone"},
    )
    assert resp.status_code == 404


def test_sms_otp_verify_returns_404(client: TestClient):
    """POST /api/sms/otp/verify returns 404 (duplicate surface removed)."""
    resp = client.post(
        "/api/sms/otp/verify",
        json={"phone_e164": "+447700900123", "code": "123456", "purpose": "verify_phone"},
    )
    assert resp.status_code == 404


def test_canonical_otp_send_returns_200(client: TestClient):
    """POST /api/otp/send exists and returns 200 with generic message."""
    resp = client.post(
        "/api/otp/send",
        json={"phone_number": "+447700900123", "action": "verify_phone"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("ok") is True
    assert "message" in data


def test_canonical_otp_verify_returns_400_without_valid_code(client: TestClient):
    """POST /api/otp/verify exists; invalid code returns 400."""
    resp = client.post(
        "/api/otp/verify",
        json={"phone_number": "+447700900123", "action": "verify_phone", "code": "000000"},
    )
    assert resp.status_code == 400
    assert "detail" in resp.json()
