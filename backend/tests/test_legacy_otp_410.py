"""
Legacy Twilio Verify endpoints must return 410 Gone with clear migration message.
Canonical OTP is POST /api/otp/send and POST /api/otp/verify (orchestrator-only).
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routes.sms import router as sms_router


@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(sms_router)
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


def test_legacy_send_otp_returns_410_gone(client: TestClient):
    """POST /api/sms/send-otp returns 410 with LEGACY_OTP_ENDPOINT_DEPRECATED and use /api/otp/send and /api/otp/verify."""
    resp = client.post(
        "/api/sms/send-otp",
        json={"phone_number": "+447700900123"},
    )
    assert resp.status_code == 410
    data = resp.json()
    assert data.get("error") == "LEGACY_OTP_ENDPOINT_DEPRECATED"
    assert "api/otp/send" in data.get("use", "") and "api/otp/verify" in data.get("use", "")


def test_legacy_verify_otp_returns_410_gone(client: TestClient):
    """POST /api/sms/verify-otp returns 410 with LEGACY_OTP_ENDPOINT_DEPRECATED and use /api/otp/send and /api/otp/verify."""
    resp = client.post(
        "/api/sms/verify-otp",
        json={"phone_number": "+447700900123", "code": "123456"},
    )
    assert resp.status_code == 410
    data = resp.json()
    assert data.get("error") == "LEGACY_OTP_ENDPOINT_DEPRECATED"
    assert "api/otp/send" in data.get("use", "") and "api/otp/verify" in data.get("use", "")
